#!/usr/bin/env python3
"""Catena delle sessioni GitHub Actions (soldi finti, nessun broker reale).

Dopo una sessione diurna lancia la successiva; a fine giornata (lun-gio) lancia un job
`wait` che dorme fino a poco prima delle 07:30 ora di Roma (i job durano al massimo
340 minuti, quindi di notte servono due hop). Venerdì sera e nel weekend non lancia
niente: il lunedì riparte il cron, e se il cron non è ancora registrato ci pensa la
routine nei giorni feriali.
Prima di un dispatch controlla che non ci sia già un run in coda (il gruppo di
concorrenza `paper-state` evita due sessioni attive insieme)."""
from __future__ import annotations
import datetime, json, os, subprocess, sys

DAY_END = (22, 25)
OPEN_HM = (7, 10)          # pochi minuti prima delle 07:30, per checkout/pip/stato
MAX_MIN = 340
LEAD_MIN = 6
WORKFLOW = "session.yml"
REF = "main"
QUEUED = ("queued", "waiting", "pending", "requested")


def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)


def next_weekday_open(now: datetime.datetime) -> datetime.datetime:
    """Prossima 07:10 Roma di un giorno feriale (incluso l'istante esatto di oggi)."""
    t = now.replace(hour=OPEN_HM[0], minute=OPEN_HM[1], second=0, microsecond=0)
    if now.weekday() < 5 and now <= t:
        return t
    d = (now + datetime.timedelta(days=1)).replace(
        hour=OPEN_HM[0], minute=OPEN_HM[1], second=0, microsecond=0
    )
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d


def in_overnight_window(now: datetime.datetime) -> bool:
    """Lun-gio dopo le 22:25, o mattina feriale prima delle 07:10. Non ven 22:25–dom."""
    hm = (now.hour, now.minute)
    if now.weekday() < 5 and hm < OPEN_HM:
        return True
    if now.weekday() < 4 and hm >= DAY_END:
        return True
    return False


def should_start_session(now: datetime.datetime) -> bool:
    hm = (now.hour, now.minute)
    return now.weekday() < 5 and OPEN_HM <= hm < DAY_END


def next_after_session(session_end: datetime.datetime, more_today: bool) -> str | None:
    """Cosa lanciare a fine sessione: 'session', 'wait', oppure nulla."""
    if more_today:
        return "session"
    if session_end.weekday() < 4:  # lunedì-giovedì
        return "wait"
    return None


def wait_plan(now: datetime.datetime, minutes: int = MAX_MIN) -> dict:
    """Piano di un job wait: action=sleep|dispatch|exit, then=session|wait|None."""
    minutes = min(max(int(minutes), 1), MAX_MIN)
    target = next_weekday_open(now)
    if should_start_session(now):
        return dict(action="dispatch", then="session", wake=now, target=target,
                    reason="ora di aprire")
    if not in_overnight_window(now):
        return dict(action="exit", then=None, wake=now, target=target,
                    reason="weekend o venerdì sera: riprende il cron o la routine")
    job_end = now + datetime.timedelta(minutes=minutes)
    latest = job_end - datetime.timedelta(minutes=LEAD_MIN) if minutes > 8 else job_end
    wake = min(target, latest)
    then = "session" if wake >= target - datetime.timedelta(minutes=1) else "wait"
    if wake <= now:
        return dict(action="dispatch", then=then, wake=now, target=target,
                    reason="fine attesa")
    return dict(action="sleep", then=then, wake=wake, target=target,
                reason="attesa notturna verso l'apertura")


def other_runs():
    """Altri run dello stesso workflow, o None se la lista non è disponibile."""
    me = str(os.environ.get("GITHUB_RUN_ID", "") or "")
    try:
        raw = subprocess.run(
            ["gh", "run", "list", "-w", WORKFLOW, "-L", "30",
             "--json", "databaseId,status,event"],
            capture_output=True, text=True, check=True,
        ).stdout
        runs = json.loads(raw or "[]")
    except Exception as e:
        log(f"impossibile leggere i run: {e}")
        return None
    return [r for r in runs if str(r.get("databaseId", "")) != me]


def has_queued(runs=None) -> bool:
    if runs is None:
        runs = other_runs()
    if runs is None:
        return False
    return any(r.get("status") in QUEUED for r in runs)


def has_other_in_progress(runs=None) -> bool:
    if runs is None:
        runs = other_runs()
    if runs is None:
        return False
    return any(r.get("status") == "in_progress" for r in runs)


def dispatch(mode: str, minutes: int | None = None, unless_running: bool = False) -> bool:
    """Lancia un workflow_dispatch su main. Non propaga `minutes` (il default è 340).
    Salta se c'è già un run in coda; con unless_running=True salta anche se uno è già attivo."""
    runs = other_runs()
    if runs is not None:
        if has_queued(runs):
            ids = [r.get("databaseId") for r in runs if r.get("status") in QUEUED]
            log(f"non lancio {mode}: già in coda {ids}")
            return False
        if unless_running and has_other_in_progress(runs):
            ids = [r.get("databaseId") for r in runs if r.get("status") == "in_progress"]
            log(f"non lancio {mode}: già attivo {ids}")
            return False
    cmd = ["gh", "workflow", "run", WORKFLOW, "--ref", REF, "-f", f"mode={mode}"]
    if minutes is not None:
        cmd += ["-f", f"minutes={int(minutes)}"]
    r = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.stdout and r.stdout.strip():
        log(r.stdout.strip()[-800:])
    if r.returncode == 0:
        log(f"lanciato workflow mode={mode}")
        return True
    log(f"ATTENZIONE: dispatch mode={mode} fallito (codice {r.returncode})")
    return False


if __name__ == "__main__":
    now = datetime.datetime.now()
    p = wait_plan(now)
    print(f"ora={now:%Y-%m-%d %H:%M} action={p['action']} then={p['then']} "
          f"wake={p['wake']:%Y-%m-%d %H:%M} target={p['target']:%Y-%m-%d %H:%M} ({p['reason']})")
