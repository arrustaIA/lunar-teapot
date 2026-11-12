#!/usr/bin/env python3
"""Short Italian status update (PAPER) for 3-hourly check-ins. Prints and writes
reports/updates/update_YYYY-MM-DD_HHMM.md. Remembers the last update time in the ledger."""
import subprocess
from common import *
from stats import *

# Sul box lo stato live arriva da GitHub Actions: prima scarica il branch `state` (./sync_github.sh pull).
# L'ora dell'ultimo aggiornamento sta in local/update_state.json (solo box), non nel ledger: il ledger
# viene sovrascritto a ogni sincronizzazione.
LOCAL_STATE = os.path.join(BASE, "local", "update_state.json")

def sync_first():
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("PT_NO_SYNC") or os.environ.get("PT_DB"):
        return ""
    r = subprocess.run([os.path.join(BASE, "sync_github.sh"), "pull"], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()

def github_health():
    try:
        hb = datetime.fromisoformat(open(os.path.join(LOGS, "scheduler_heartbeat")).read().strip()[:19])
    except (OSError, ValueError):
        return None
    age = (now().replace(tzinfo=None) - hb).total_seconds() / 60
    n = now(); live = n.weekday() < 5 and time(7, 30) <= n.time() <= time(22, 0)
    if live and age > 20:
        return f"- ATTENZIONE: sessione GitHub ferma, ultimo battito {hb:%H:%M} ({age:.0f} min fa)"
    return f"- Sessione GitHub: ultimo battito {hb:%d/%m %H:%M} ({age:.0f} min fa)"

def main():
    sync_msg = sync_first()
    try:
        local = json.load(open(LOCAL_STATE))
    except (OSError, ValueError):
        local = {}
    with Lock():
        con = db()
        start_cash = float(con.execute("SELECT value FROM state WHERE key='start_cash'").fetchone()[0])
        r = con.execute("SELECT value FROM state WHERE key='last_update'").fetchone()
        since = local.get("last_update") or (r[0] if r else today().isoformat() + "T00:00:00")
        dayrow = ensure_day(con)
        pos, _ = open_positions_view(con)
        eq = get_cash(con) + sum(p["value"] for p in pos)
        new = pd.read_sql_query("SELECT * FROM trades WHERE ts>? ORDER BY id", con, params=(since,))
        rt = round_trips(con, today().isoformat())
        all_tax = con.execute("SELECT COALESCE(SUM(tax_eur),0), COALESCE(SUM(fee),0) FROM trades").fetchone()
        credit = tax_credit_available(con)
        stamp = now().isoformat(timespec="seconds")
        os.makedirs(os.path.dirname(LOCAL_STATE), exist_ok=True)
        json.dump({"last_update": stamp}, open(LOCAL_STATE, "w"))
    day = eq - dayrow["start_equity"]; cum = eq - start_cash
    L = [f"**Aggiornamento paper trading – {now():%d/%m %H:%M} (ora di Roma)**",
         f"- Equity: {eur(eq)} | oggi {eur(day)} ({pct(day / dayrow['start_equity'])}) | dall'avvio {eur(cum)} ({pct(cum / start_cash)})",
         f"- Oggi realizzato netto dopo tasse: {eur(rt['net'].sum() if len(rt) else 0)}; commissioni totali {eur(all_tax[1])}, tasse totali {eur(all_tax[0])}, zainetto fiscale {eur(credit)}"]
    if pos:
        L.append("- Posizioni aperte: " + "; ".join(f"{p['name']} {p['qty']:.3f} @ {p['entry_local']:.2f}→{p['last']:.2f} {p['currency']} ({eur(p['unreal'])} non realizzato, lordo tasse)" for p in pos))
    else:
        L.append("- Nessuna posizione aperta.")
    if len(new):
        L.append(f"- Operazioni dalle {since[11:16]} del {since[8:10]}/{since[5:7]}: " + "; ".join(
            f"{t.ts[11:16]} {'ACQ' if t.side == 'BUY' else 'VEND'} {t['name']} {t.qty:.3f} @ {t.price_local:.2f}"
            + (f" netto {eur(t.net_pnl_eur)}" if t.side == "SELL" else "") for _, t in new.iterrows()))
    else:
        L.append(f"- Nessuna operazione dalle {since[11:16]} del {since[8:10]}/{since[5:7]}.")
    # Box pauses since the last update (logs/gaps.log, written by scheduler.py / catch-up passes)
    try:
        gaps = [l.strip() for l in open(GAPS_LOG) if l.startswith("GAP") and l.split("end=")[1][:19].replace(" ", "T") > since[:19]]
    except (FileNotFoundError, IndexError):
        gaps = []
    if gaps:
        L.append(f"- Pause o cambi di sessione dalle {since[11:16]}: " + "; ".join(
            g.split("start=")[1][11:16] + "-" + g.split("end=")[1][11:16] + " (" + g.split("durata=")[1].split(" min")[0] + " min, " + ("recupero automatico eseguito" if "recupero: trade" in g else "senza recupero") + ")"
            for g in gaps))
    h = github_health()
    if h:
        L.append(h)
    if sync_msg and "scaricato" not in sync_msg:
        L.append(f"- Sincronizzazione con GitHub: {sync_msg[-200:]}")
    txt = "\n".join(L) + "\n"
    out = os.path.join(REPORTS, "updates"); os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"update_{now():%Y-%m-%d_%H%M}.md"), "w") as f: f.write(txt)
    print(txt)

if __name__ == "__main__":
    main()
