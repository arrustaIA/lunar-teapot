#!/usr/bin/env python3
"""Decide cosa fa un run del workflow (stampa mode=... per $GITHUB_OUTPUT).
- workflow_dispatch: usa l'input mode (session/news/wait). Un `wait` resta `wait` anche se il
  dispatch avviene in orario di mercato (decide gira subito, il job `run` può restare in coda
  fino a fine sessione); venerdì dopo le 22:25 e nel weekend diventa `skip`.
- schedule: se c'è già un'altra sessione in corso o in coda -> skip; lun-ven 06:00-22:10 (Roma) -> session
  (avvio mattutino + cane da guardia se la catena si è rotta); fuori orario solo il cron orario -> news."""
import datetime, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain
event = os.environ.get("EVENT", ""); inp = os.environ.get("INPUT_MODE", "") or "session"
sched = os.environ.get("SCHEDULE", ""); me = os.environ.get("GITHUB_RUN_ID", "")
now = datetime.datetime.now()   # TZ=Europe/Rome
def out(mode, why):
    print(f"decisione: {mode} ({why}) alle {now:%Y-%m-%d %H:%M} ora di Roma", file=sys.stderr)
    print(f"mode={mode}")
    sys.exit(0)
if event == "workflow_dispatch":
    if inp == "wait":
        # Non promuovere a session qui: questo job gira all'istante del dispatch,
        # anche se il job run resta in coda dietro la sessione in corso.
        if now.weekday() >= 5 or (now.weekday() == 4 and (now.hour, now.minute) >= chain.DAY_END):
            out("skip", "wait fuori finestra (weekend o venerdì sera)")
        out("wait", "attesa verso l'apertura")
    out(inp, "avvio manuale / catena")
try:
    runs = json.loads(subprocess.run(["gh", "run", "list", "-w", "session.yml", "-L", "30", "--json", "databaseId,status"],
                                     capture_output=True, text=True, check=True).stdout)
    busy = [r for r in runs if str(r["databaseId"]) != me and r["status"] in ("in_progress", "queued", "waiting", "pending", "requested")]
except Exception as e:
    out("skip", f"impossibile leggere i run: {e}")
if busy:
    out("skip", f"già attivo/in coda: run {busy[0]['databaseId']}")
hm = (now.hour, now.minute)
if now.weekday() < 5 and (6, 0) <= hm <= (22, 10):
    out("session", "orario di mercato senza sessione attiva")
if sched.strip() == "25 * * * *":
    out("news", "fuori orario: solo notizie")
out("skip", "fuori orario")
