#!/usr/bin/env python3
"""Blocca il push se i file tracciati contengono dati sensibili (repo PUBBLICO).
Uso: python3 gh/secret_check.py [file ...]   (senza argomenti: tutti i file tracciati/da tracciare)"""
import re, subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAT = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]{2,}"),
    "token GitHub": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "chiave privata": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "chiave API generica": re.compile(r"(?i)\b(api[_-]?key|secret|passw(or)?d|bearer)\b\s*[:=]\s*['\"][^'\"]{8,}"),
    "AWS/Google/Slack": re.compile(r"\b(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[abpr]-[0-9A-Za-z-]{10,})"),
    "UUID (id agenti)": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    "percorsi account": re.compile(r"(/home/box/agent-data|/cursor/stores|\.config/gh)"),
    "dati personali": re.compile(r"(?i)\b(morganti|hotmail|protonmail|proton\.me)\b"),
}
files = sys.argv[1:] or subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True).stdout.split()
bad = 0
for f in files:
    if f == "gh/secret_check.py" or not os.path.isfile(f):
        continue
    try:
        txt = open(f, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for name, rx in PAT.items():
        for m in rx.finditer(txt):
            line = txt.count("\n", 0, m.start()) + 1
            print(f"SENSIBILE? {f}:{line} [{name}] {m.group(0)[:60]}"); bad += 1
if bad:
    sys.exit(f"{bad} possibili dati sensibili: push bloccato (repo pubblico)")
print(f"controllo dati sensibili ok ({len(files)} file)")
