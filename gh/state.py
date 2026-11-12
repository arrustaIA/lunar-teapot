#!/usr/bin/env python3
"""Stato del bot PAPER (soldi finti) sul branch `state` del repo GitHub.

  python3 gh/state.py pull          # scarica il branch `state` e lo sovrappone a data/ logs/ reports/ charts/
  python3 gh/state.py push          # (solo GitHub Actions, o --seed) fotografa lo stato e forza il push su `state`

Proprietà dei file (niente conflitti):
- GitHub (sessioni Actions) scrive: data/*.sqlite, data/*.json, data/*.jsonl, logs/, reports/, charts/
- il box (agenti) scrive solo: codice + BOX_OWNED (giudizi di Natasia), che viaggiano sul branch `main`.
`state` contiene sempre UN solo commit (force push): la dimensione del repo non cresce.
Le copie sqlite usano l'API di backup (snapshot coerente anche con job in corso)."""
import os, sys, shutil, sqlite3, subprocess, tempfile, time, datetime, re, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
BOX_OWNED = {"data/news_llm.json", "data/news_llm_history.jsonl", "data/news_llm_state.json"}
DIRS = ["data", "logs", "reports", "charts"]
KEEP_DAYS_FILES = 21      # log/grafici/watchlist con data nel nome più vecchi di così non vanno nello snapshot
KEEP_DAYS_BARS = 45       # barre/quote più vecchie vengono potate nello snapshot
BRANCH = "state"
DATE_RE = re.compile(r"(20\d\d-\d\d-\d\d)")

def git(*a, env=None, check=True, capture=True):
    r = subprocess.run(["git", *a], cwd=BASE, env={**os.environ, **(env or {})},
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr.strip()}")
    return (r.stdout or "").strip()

def wanted(rel):
    name = os.path.basename(rel)
    if rel in BOX_OWNED or name.startswith(".") or name.endswith((".tmp", ".pkl", "-wal", "-shm", "-journal", ".lock")):
        return False
    if rel.startswith("reports/updates/"):       # aggiornamenti scritti sul box
        return False
    if rel.startswith("data/") and not name.endswith((".sqlite", ".json", ".jsonl", ".csv")):
        return False
    m = DATE_RE.search(rel)
    if m:
        try:
            if (datetime.date.today() - datetime.date.fromisoformat(m.group(1))).days > KEEP_DAYS_FILES:
                return False
        except ValueError:
            pass
    return True

def sqlite_snapshot(src, dst):
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=60)
    d = sqlite3.connect(dst)
    s.backup(d); s.close()
    if os.path.basename(src) == "bars.sqlite":
        cut = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS_BARS)).isoformat()
        for t in ("bars_1m", "bars_5m", "quotes", "tape"):
            try:
                d.execute(f"DELETE FROM {t} WHERE ts < ?", (cut,))
            except sqlite3.Error:
                pass
        d.commit()
    d.execute("PRAGMA journal_mode=DELETE"); d.execute("VACUUM"); d.close()

MARKER = os.path.join(BASE, ".git", "state-pulled")

def push(msg=None):
    if not os.environ.get("GITHUB_ACTIONS") and "--seed" not in sys.argv:
        sys.exit("push dello stato solo da GitHub Actions (usa --seed per il primo caricamento dal box)")
    if os.environ.get("GITHUB_ACTIONS") and not os.path.exists(MARKER):
        sys.exit("stato non scaricato in questa sessione: non sovrascrivo il branch state")
    stage = tempfile.mkdtemp(prefix="pt-state-")
    n = 0
    for d in DIRS:
        for root, _, files in os.walk(d):
            for f in files:
                rel = os.path.join(root, f)
                if not wanted(rel):
                    continue
                dst = os.path.join(stage, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
                if f.endswith(".sqlite"):
                    sqlite_snapshot(rel, dst)
                else:
                    shutil.copy2(rel, dst)
                n += 1
    open(os.path.join(stage, "STATE_README.md"), "w").write(
        "Stato della simulazione PAPER (soldi finti). Generato automaticamente da gh/state.py; non modificare a mano.\n")
    idx = os.path.join(BASE, ".git", "state-index")
    if os.path.exists(idx):
        os.remove(idx)
    env = {"GIT_WORK_TREE": stage, "GIT_INDEX_FILE": idx}
    git("add", "-A", ".", env=env)
    tree = git("write-tree", env=env)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    commit = git("commit-tree", tree, "-m", msg or f"stato paper {stamp} (ora di Roma)", env=env)
    for i in range(3):
        try:
            git("push", "-q", "-f", "origin", f"{commit}:refs/heads/{BRANCH}")
            break
        except RuntimeError as e:
            if i == 2:
                raise
            time.sleep(10)
    shutil.rmtree(stage, ignore_errors=True); os.remove(idx)
    print(f"stato salvato su '{BRANCH}': {n} file, {stamp}")

def pull(box=False):
    if not git("ls-remote", "--heads", "origin", BRANCH):     # errore di rete -> eccezione, non stato vuoto
        print("nessuno stato remoto: parto dallo stato locale"); open(MARKER, "w").write("new"); return
    git("fetch", "-q", "origin", f"+refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
    tmp = tempfile.mkdtemp(prefix="pt-pull-")
    arch = subprocess.run(["git", "archive", f"origin/{BRANCH}"], cwd=BASE, stdout=subprocess.PIPE, check=True).stdout
    subprocess.run(["tar", "-x", "-C", tmp], input=arch, check=True)
    n = 0
    for root, _, files in os.walk(tmp):
        for f in files:
            src = os.path.join(root, f); rel = os.path.relpath(src, tmp)
            if rel == "STATE_README.md" or rel in BOX_OWNED or rel.split("/")[0] not in DIRS:
                continue
            os.makedirs(os.path.dirname(rel), exist_ok=True)
            part = rel + ".pulltmp"
            shutil.copy2(src, part)
            if rel.endswith(".sqlite"):
                for suf in ("-wal", "-shm", "-journal"):
                    if os.path.exists(rel + suf):
                        os.remove(rel + suf)
            os.replace(part, rel); n += 1
    shutil.rmtree(tmp, ignore_errors=True)
    open(MARKER, "w").write("ok")
    when = git("log", "-1", "--format=%cd", "--date=format-local:%Y-%m-%d %H:%M", f"origin/{BRANCH}", check=False,
               env={"TZ": "Europe/Rome"})
    print(f"stato scaricato da '{BRANCH}' ({n} file, salvato {when} ora di Roma)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "push":
        push()
    elif cmd == "pull":
        pull(box="--box" in sys.argv)
    else:
        sys.exit(__doc__)
