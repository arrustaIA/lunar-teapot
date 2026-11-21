#!/usr/bin/env python3
"""Test A4_ADAPT (shadow osservativa, nessun ordine): stato causale, short KO ombra, long bloccati, Δ. PAPER only."""
import os, json, tempfile
from datetime import date, datetime, timedelta, time
import pandas as pd
_tmp = tempfile.mkdtemp()
os.environ.update(PT_TRADE_LOG=os.path.join(_tmp, "trade_log.jsonl"), PT_SHADOW_DIR=_tmp, PT_DB=os.path.join(_tmp, "l.sqlite"), PT_LOGS=os.path.join(_tmp, "logs"), PT_REPORTS=os.path.join(_tmp, "reports"))
import shadow as SH
from common import ROME

ok = 0
def check(c, msg):
    global ok
    assert c, msg
    ok += 1

def closes(vals, end=date(2026, 11, 20)):
    days = pd.bdate_range(end=end, periods=len(vals)).date
    return pd.Series(vals, index=list(days))

D = date(2026, 11, 23)  # lunedi'
# 1) stato: -3% esatto acceso, -2,9% spento, usa solo chiusure < d
on, r = SH.a4_state(closes([100, 99, 98, 97, 96, 97.0]), D); check(on and abs(r + 0.03) < 1e-9, "-3% deve accendere")
on, r = SH.a4_state(closes([100, 99, 98, 97, 96, 97.1]), D); check(on is False, "-2,9% non accende")
s = closes([100, 99, 98, 97, 96, 97.0, 50.0], end=D)          # la chiusura di d stesso NON va usata
on, r = SH.a4_state(s, D); check(on and abs(r + 0.03) < 1e-9, "chiusura del giorno stesso ignorata")
check(SH.a4_state(closes([100, 99, 98]), D) == (None, None), "storia corta -> n/d")

def bars(region, d, open_px, first_close, path_highs, path_close):
    o = SH.session_times(region, d)[0]; idx = []; rows = []
    for i in range(12):   # prima ora
        ts = o + timedelta(minutes=5 * i); c = first_close if i == 11 else open_px
        idx.append(ts); rows.append(dict(Open=open_px, High=max(open_px, c), Low=min(open_px, c), Close=c, Volume=0))
    ex = datetime.combine(d, SH.A4["exit"][region], ROME); ts = o + timedelta(minutes=60); k = 0
    while ts + timedelta(minutes=5) <= ex:
        h = path_highs[k] if k < len(path_highs) else first_close
        idx.append(ts); rows.append(dict(Open=first_close, High=h, Low=min(first_close, path_close), Close=path_close, Volume=0)); ts += timedelta(minutes=5); k += 1
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))

# 2) short: sotto l'apertura -> short; uscita a orario; netto = formula KO
b = bars("EU", D, 100.0, 99.0, [], 98.0); sh = SH.a4_short(b, "EU", D)
v0 = 1200 / 5; g = v0 * (1 + 5 * (1 - 98 / 99)) * 0.999 - v0 * 1.001 - 2 * 0.0002 * 1200
check(sh["status"] == "short" and sh["exit_reason"] == "orario" and abs(sh["net_ante_tasse"] - round(g - 2, 2)) < 0.011, f"short orario {sh}")
check(sh["entry_ts"][11:16] == "10:00" and sh["exit_ts"][11:16] == "17:00", "orari DAX 10:00 -> 17:00")
# sopra l'apertura -> nessuno short
check(SH.a4_short(bars("EU", D, 100.0, 100.5, [], 99.0), "EU", D)["status"].startswith("nessuno short"), "sopra apertura: niente short")
# stop +1,5%
sh = SH.a4_short(bars("EU", D, 100.0, 99.0, [99.5, 100.6], 98.0), "EU", D)
check(sh["exit_reason"] == "stop" and abs(sh["exit_px"] - round(99 * 1.015, 2)) < 0.011 and sh["net_ante_tasse"] < 0, f"stop {sh}")
# NDX: orari 16:30 -> 21:30 (Roma, ora solare)
sh = SH.a4_short(bars("US", D, 100.0, 99.0, [], 98.0), "US", D)
check(sh["entry_ts"][11:16] == "16:30" and sh["exit_ts"][11:16] == "21:30", f"orari NDX {sh.get('entry_ts')} {sh.get('exit_ts')}")
check(SH.a4_short(None, "EU", D)["status"] == "barre non disponibili", "barre mancanti gestite")

# 3) a4_eval: long di produzione bloccati solo nella regione accesa, Δ = short - long bloccati
with open(os.environ["PT_TRADE_LOG"], "w") as f:
    for sym, net, src in (("SAP.DE", -5.0, "production"), ("AAPL", -3.0, "production"), ("BMW.DE", 9.0, "shadow")):
        f.write(json.dumps(dict(source=src, symbol=sym, side="long", entry_ts=f"{D}T10:30:00+01:00", net_pnl_eur=net)) + "\n")
daily = {"^GDAXI": pd.DataFrame({"Close": closes([100, 99, 98, 97, 96, 96.5])}), "^NDX": pd.DataFrame({"Close": closes([100, 100, 100, 100, 100, 99.0])})}
bb = {"^GDAXI": bars("EU", D, 100.0, 99.0, [], 98.0), "^NDX": bars("US", D, 100.0, 99.0, [], 98.0)}
row = SH.a4_eval(D, bb, daily)
check(row["regions"]["EU"]["on"] and row["regions"]["US"]["on"] is False, "EU acceso, US spento")
check([p["symbol"] for p in row["regions"]["EU"]["blocked"]] == ["SAP.DE"], "solo i long di produzione EU bloccati")
check(abs(row["delta"] - (row["short_net"] - (-5.0))) < 1e-9, "Δ = short - long bloccati")
check("short" not in row["regions"]["US"], "nessuno short con interruttore spento")
# 4) chiusura mancante nel giornaliero riempita dalla barra 5m
dd = {"^GDAXI": pd.DataFrame({"Close": closes([100, 99, 98, 97, 96], end=date(2026, 11, 19))})}
b20 = bars("EU", date(2026, 11, 20), 96.0, 96.0, [], 95.0)
cl, filled = SH.a4_closes(dd["^GDAXI"], b20, "EU", D)
check(filled == ["2026-11-20"] and abs(cl[date(2026, 11, 20)] - 95.0) < 1e-9, "chiusura 20/11 dal 5m")
# 5) righe del report
lines = SH.a4_row_lines(row); check(any("Δ del giorno" in l for l in lines) and any("ACCESO" in l for l in lines), "righe report")
print(f"test_a4_shadow: {ok} controlli ok")
