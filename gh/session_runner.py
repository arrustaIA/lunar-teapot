#!/usr/bin/env python3
"""Sessione GitHub Actions del bot PAPER (soldi finti, nessun broker reale).

  python3 gh/session_runner.py --mode session [--minutes N] [--no-chain]
  python3 gh/session_runner.py --mode news

session: avvia scheduler.py (stessi orari del box) fino a min(avvio+340 min, 22:25 Roma); ogni 15 min
         aggiorna il codice da main (ff-only, così le modifiche di R&D e i giudizi di Natasia arrivano in
         corsa) e salva lo stato sul branch `state`; 6 min prima della fine lancia la sessione successiva
         (workflow_dispatch: resta in coda finché questa non finisce) se la giornata non è finita.
news:    una passata di news.py e salvataggio dello stato (fuori orario / weekend)."""
import argparse, datetime, os, signal, subprocess, sys, time
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
MAX_MIN = 340
DAY_END = (22, 25)                      # dopo team_review delle 22:15
NO_HANDOFF = [((9, 0), (9, 45)), ((15, 20), (15, 50))]   # aperture EU/USA: niente cambio sessione qui
SAVE_EVERY = 15 * 60
JOB_PAT = r"python3 (news|scan|trade|rescan|shadow|close_all|report|team_review)\.py"

def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)

def sh(cmd, check=False):
    r = subprocess.run(cmd, shell=True, cwd=BASE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.stdout.strip():
        log(r.stdout.strip()[-1500:])
    return r.returncode

def save():
    before = open("requirements.txt").read()
    sh("git pull -q --ff-only origin main || echo 'pull main non riuscito (continuo con il codice attuale)'")
    if open("requirements.txt").read() != before:
        sh("pip install -q -r requirements.txt")
    if sh("python3 gh/state.py push"):
        log("ATTENZIONE: salvataggio stato fallito, riprovo al prossimo giro")

def session_end(start, minutes):
    end = start + datetime.timedelta(minutes=minutes)
    day_end = start.replace(hour=DAY_END[0], minute=DAY_END[1], second=0, microsecond=0)
    end = min(end, day_end)
    for (a, b) in NO_HANDOFF:
        wa = end.replace(hour=a[0], minute=a[1], second=0); wb = end.replace(hour=b[0], minute=b[1], second=0)
        if wa <= end < wb and end != day_end:
            end = wa - datetime.timedelta(minutes=5)
    return end, end < day_end - datetime.timedelta(minutes=3)

def jobs_running():
    return subprocess.run(["pgrep", "-f", JOB_PAT], stdout=subprocess.DEVNULL).returncode == 0

def run_session(minutes, chain):
    start = datetime.datetime.now()
    end, more_today = session_end(start, minutes)
    log(f"sessione PAPER {start:%Y-%m-%d %H:%M} -> {end:%H:%M} (ora di Roma); catena={chain and more_today}")
    # sonda fonti dati dal runner (L&S può essere bloccato/limitato: marketdata ripiega su Yahoo)
    sh("timeout 60 python3 marketdata.py --quote SIE.DE 2>&1 | tail -3 | sed 's/^/sonda L&S: /'")
    sh("timeout 60 python3 -c \"import yfinance as y; d=y.download('SAP.DE', period='1d', interval='1m', progress=False); print('sonda Yahoo: barre 1m', len(d))\" 2>&1 | tail -2")
    sched = subprocess.Popen(["python3", "scheduler.py"], stdout=open("logs/scheduler.log", "a"), stderr=subprocess.STDOUT)
    last_save, dispatched = time.time(), False
    while datetime.datetime.now() < end:
        time.sleep(30)
        if sched.poll() is not None:
            log(f"scheduler terminato (codice {sched.returncode}), lo riavvio")
            sched = subprocess.Popen(["python3", "scheduler.py"], stdout=open("logs/scheduler.log", "a"), stderr=subprocess.STDOUT)
        if time.time() - last_save > SAVE_EVERY:
            save(); last_save = time.time()
        if chain and more_today and not dispatched and datetime.datetime.now() >= end - datetime.timedelta(minutes=6):
            rc = sh("gh workflow run session.yml --ref main -f mode=session")
            log("sessione successiva in coda" if rc == 0 else "ATTENZIONE: dispatch sessione successiva fallito (ci pensa il cron di controllo)")
            dispatched = True
    log("fine finestra: fermo lo scheduler e aspetto i job in corso")
    sched.send_signal(signal.SIGTERM)
    try:
        sched.wait(30)
    except subprocess.TimeoutExpired:
        sched.kill()
    t0 = time.time()
    while jobs_running() and time.time() - t0 < 600:
        time.sleep(5)
    save()
    log("sessione chiusa")

def run_news():
    sh("./run.sh news")
    save()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="session", choices=["session", "news", "skip"])
    ap.add_argument("--minutes", type=int, default=MAX_MIN)
    ap.add_argument("--no-chain", action="store_true")
    a = ap.parse_args()
    os.makedirs("logs", exist_ok=True)
    if a.mode == "session":
        run_session(min(a.minutes, MAX_MIN), chain=not a.no_chain and a.minutes >= MAX_MIN)
    elif a.mode == "news":
        run_news()
