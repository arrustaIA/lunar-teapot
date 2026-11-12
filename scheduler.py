#!/usr/bin/env python3
"""Daemon PAPER: lancia i job del team agli orari previsti (ora di Roma). Avvio: ./start_scheduler.sh

Robust to box pauses (the machine is frozen when no agent is active):
- a gap is detected when the loop wakes up > GAP_SEC after its previous tick (or, at start-up,
  when logs/scheduler_heartbeat is older than GAP_SEC);
- on a gap one ordered catch-up chain runs: trade --manage --catchup (replays every bar of the
  gap, so stops/targets are never skipped, and closes stale positions), close_all if 21:50
  passed, scan if 09:35 was missed, a full trade pass if still inside 07:30-21:45, then
  missed report / team_review / news;
- one-shot jobs record their last run day in logs/scheduler_state.json, so nothing runs twice;
- every gap is appended to logs/gaps.log (start, end, duration, catch-up actions).
"""
import subprocess, time, datetime, os, json
os.chdir(os.path.dirname(os.path.abspath(__file__)))
LOGS = os.environ.get("PT_LOGS", "logs")
os.makedirs(LOGS, exist_ok=True)
STATE = os.path.join(LOGS, "scheduler_state.json")
HEARTBEAT = os.path.join(LOGS, "scheduler_heartbeat")
GAPS = os.path.join(LOGS, "gaps.log")
GAP_SEC = 180            # a tick more than 3 min after the previous one = the box was paused
TICK_SEC = 15
ONE_SHOT = {"scan": (9, 35), "close_all": (21, 50), "report": (21, 55), "shadow_eod": (21, 56), "team_review": (22, 15)}
RESCAN_WINDOW = ((9, 30), (21, 0))    # watchlist dinamica ogni 30 min (rescan.py; USA solo da apertura+30 min)
NEWS_FAST = ((7, 0), (22, 0))        # news.py ogni 10 minuti nei giorni feriali
SHADOW_WINDOW = ((9, 33), (21, 13))   # strategie shadow ogni 10 min al minuto :x3 (shadow.py, nessun ordine)
TRADE_WINDOW = ((7, 30), (21, 45))   # full trade passes (TR 07:30-22:00, last pass 21:45)

def jobs(now):
    wd = now.weekday() < 5; hm = (now.hour, now.minute); out = []
    # notizie (news.py, RSS + parole chiave): ogni 10 min (:x5) lun-ven 07:00-22:00, altrimenti ogni ora al :05
    if (now.minute % 10 == 5 and wd and NEWS_FAST[0] <= hm <= NEWS_FAST[1]) or now.minute == 5: out.append(["news"])
    if wd and hm == ONE_SHOT["scan"]: out.append(["scan"])
    if wd and (TRADE_WINDOW[0] <= hm <= TRADE_WINDOW[1]) and now.minute % 10 == 0: out.append(["trade"])
    # Light position watch every 2 min (skips minutes already covered by the full trade pass).
    if wd and ((7, 30) <= hm <= (21, 48)) and now.minute % 2 == 0 and now.minute % 10 != 0:
        out.append(["trade", "--manage"])
    if wd and (RESCAN_WINDOW[0] <= hm <= RESCAN_WINDOW[1]) and now.minute % 30 == 0: out.append(["rescan"])
    if wd and (SHADOW_WINDOW[0] <= hm <= SHADOW_WINDOW[1]) and now.minute % 10 == 3: out.append(["shadow"])
    if wd and hm == ONE_SHOT["close_all"]: out.append(["close_all"])  # EU no longer flattened at 17:26 (LS quotes are live into the evening)
    if wd and hm == ONE_SHOT["report"]: out.append(["report"])
    if wd and hm == ONE_SHOT["shadow_eod"]: out.append(["shadow", "--eod"])
    if wd and hm == ONE_SHOT["team_review"]: out.append(["team_review"])
    return out

# ---------------- state / logging ----------------
def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"last_run": {}}

def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1)
    os.replace(tmp, STATE)

def ran_today(st, name, day):
    return st.get("last_run", {}).get(name) == day.isoformat()

def mark(st, name, day):
    st.setdefault("last_run", {})[name] = day.isoformat()

def gap_line(msg):
    with open(GAPS, "a") as f:
        f.write(msg + "\n")

def spawn(cmds):
    """cmds: list of argv lists. One -> its own process; several -> one ordered shell chain."""
    if not cmds:
        return
    if len(cmds) == 1:
        subprocess.Popen(["./run.sh"] + cmds[0], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        chain = " ; ".join("./run.sh " + " ".join(c) for c in cmds)
        subprocess.Popen(["bash", "-c", chain], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def read_heartbeat():
    try:
        return datetime.datetime.fromisoformat(open(HEARTBEAT).read().strip()[:19])
    except Exception:
        return None

# ---------------- normal minute / gap catch-up ----------------
def run_minute(minute, st, run=spawn):
    todo = []
    for j in jobs(minute):
        key = "shadow_eod" if j == ["shadow", "--eod"] else j[0]
        if key in ONE_SHOT:
            if ran_today(st, key, minute.date()):
                continue
            mark(st, key, minute.date())
        todo.append(j)
    for j in todo:
        run([j])
    return todo

def catchup_plan(start, end, st):
    """Ordered catch-up commands for a pause from `start` (last tick) to `end` (wake-up minute)."""
    day = end.date(); wd = end.weekday() < 5; hm = (end.hour, end.minute)
    missed, m = set(), start.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    m = max(m, end - datetime.timedelta(days=3))
    while m <= end:
        for j in jobs(m):
            missed.add(j[0] if j[0] != "trade" or len(j) == 1 else "manage")
        m += datetime.timedelta(minutes=1)
    def due(name):   # one-shot whose time passed during the gap today and not run yet today
        t = end.replace(hour=ONE_SHOT[name][0], minute=ONE_SHOT[name][1], second=0, microsecond=0)
        return wd and start < t <= end and not ran_today(st, name, day)
    plan, notes = [["trade", "--manage", "--catchup"]], []
    # close_all is never skipped: after 21:50, or if the pause crossed midnight (stale positions)
    if due("close_all") or (wd and hm >= ONE_SHOT["close_all"] and not ran_today(st, "close_all", day)):
        plan.append(["close_all"]); mark(st, "close_all", day)
    elif start.date() < day:
        # pausa a cavallo della mezzanotte: chiude le posizioni rimaste aperte da ieri, ma NON segna il
        # close_all di oggi (prima veniva segnato e quello delle 21:50 saltava)
        plan.append(["close_all"])
    if due("scan"):
        plan.append(["scan"]); mark(st, "scan", day)
    if wd and TRADE_WINDOW[0] <= hm <= TRADE_WINDOW[1]:
        plan.append(["trade"])
    if wd and "rescan" in missed and RESCAN_WINDOW[0] <= hm <= RESCAN_WINDOW[1]:
        plan.append(["rescan"])          # un solo rescan di recupero (i candidati restano per tutto il giorno)
    for name in ("report", "team_review"):
        if due(name):
            plan.append([name]); mark(st, name, day)
    if due("shadow_eod"):
        plan.append(["shadow", "--eod"]); mark(st, "shadow_eod", day)
    if "news" in missed:
        plan.append(["news"])
    if start.date() < day:
        notes.append("pausa a cavallo della mezzanotte: report/team_review del giorno precedente non recuperati")
    return plan, notes

def handle_gap(start, end, st, run=spawn, reason="tick"):
    plan, notes = catchup_plan(start, end, st)
    run(plan)
    dur = int((end - start).total_seconds() // 60)
    gap_line(f"GAP start={start:%Y-%m-%d %H:%M:%S} end={end:%Y-%m-%d %H:%M:%S} durata={dur} min ({reason}) "
             f"recupero: {' -> '.join(' '.join(c) for c in plan)}" + (f" | {'; '.join(notes)}" if notes else ""))
    save_state(st)
    return plan

def reap():
    try:
        while True:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break
    except ChildProcessError:
        pass

def main(clock=datetime.datetime.now, sleep=time.sleep, run=spawn, max_ticks=None):
    st = load_state()
    last_min, prev = None, None
    hb = read_heartbeat()
    start_now = clock()
    if hb and (start_now - hb).total_seconds() > GAP_SEC:
        handle_gap(hb, start_now, st, run, reason="avvio, heartbeat vecchio")
        last_min = start_now.replace(second=0, microsecond=0)
    ticks = 0
    while max_ticks is None or ticks < max_ticks:
        ticks += 1
        wall = clock()
        minute = wall.replace(second=0, microsecond=0)
        if prev is not None and (wall - prev).total_seconds() > GAP_SEC:
            handle_gap(prev, wall, st, run)
            last_min = minute          # the catch-up chain covers this minute too
        elif minute != last_min:
            last_min = minute
            if run_minute(minute, st, run):
                save_state(st)
        if minute != getattr(main, "_hb", None):
            open(HEARTBEAT, "w").write(minute.isoformat())
            main._hb = minute
        prev = wall
        reap()
        sleep(TICK_SEC)

if __name__ == "__main__":
    # Il bot gira su GitHub Actions (gh/session_runner.py). Sul box lo scheduler resta spento per non far
    # operare due volte lo stesso ledger; per riattivarlo serve PT_LOCAL_SCHEDULER=1 (vedi README).
    if not os.environ.get("GITHUB_ACTIONS") and os.environ.get("PT_LOCAL_SCHEDULER") != "1":
        raise SystemExit("scheduler locale disattivato: il bot gira su GitHub Actions (usa ./sync_github.sh)")
    main()
