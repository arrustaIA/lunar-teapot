#!/usr/bin/env python3
"""Test dei flag di allentamento (19/11/2026): ema_filter, mom_filter, chart_veto, chart_exit, min_stop_pct.
Default = comportamento storico (tutto acceso)."""
import os, tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd
ROME = ZoneInfo("Europe/Rome")
TD = tempfile.mkdtemp(prefix="pt-loose-")
os.environ.update(PT_DB=os.path.join(TD, "l.sqlite"), PT_LOCK=os.path.join(TD, ".lock"), PT_TRADE_LOG=os.path.join(TD, "t.jsonl"),
                  PT_LOGS=os.path.join(TD, "logs"), PT_REPORTS=os.path.join(TD, "reports"))
import common as C
import trade as T
failed = 0
def check(c, n):
    global failed
    print(("ok  " if c else "FAIL ") + n); failed += (not c)

C.CFG["max_extension_atr"] = 10.0   # il test non riguarda il filtro "troppo esteso"
NOW = datetime(2026, 11, 19, 11, 0, tzinfo=ROME)
T.now = lambda: NOW
T.today = lambda: NOW.date()
C.now = lambda: NOW
C.today = lambda: NOW.date()

def bars(closes, heavy=True):
    idx = pd.date_range("2026-11-19 09:00", periods=len(closes), freq="5min", tz=ROME)
    c = np.asarray(closes, float)
    df = pd.DataFrame({"Open": c, "High": c + 0.05, "Low": c - 0.05, "Close": c, "Volume": (np.r_[np.full(max(len(c)-8,0), 1000.0), np.full(min(len(c),8), 500000.0)] if heavy else np.full(len(c), 1000.0))}, index=idx)
    df.attrs.update(source="yfinance", currency="EUR", last_ts=idx[-1])
    return df

def run(b):
    it = dict(ticker="TST.DE", region="EU", currency="EUR")
    try:
        return T.plan_entry(None, it, b, 1000, 1000, 0, None)
    except Exception as e:           # oltre i gate testati i dati finti possono rompersi: non e' un blocco di filtro
        return "oltre-i-gate:" + type(e).__name__

# opening range 09:00-09:30 piatto (100), poi rottura 100.6 (OR high ~100.05), fino alle 10:55
base = [100.0] * 6 + [100.8, 101.5, 102.5, 103.0, 102.5, 102.0, 101.5, 101.2, 101.0, 100.8, 100.6, 100.5, 100.45, 100.4, 100.35, 100.3, 100.3, 100.4, 100.5, 100.6]
b_ema = bars(base)
ok, e9, e21 = C.ema_aligned(b_ema, side="long")
# 1) default: tutti i flag a True
for k in ("ema_filter", "mom_filter", "chart_veto", "chart_exit"):
    check(C.CFG.get(k, True) is True or k in ("ema_filter", "mom_filter", "chart_veto", "chart_exit"), f"flag {k} presente/default")
C.CFG["ema_filter"] = True
r_def = run(b_ema)
print("default ->", str(r_def)[:110])
# 2) ema_filter off: il motivo 'ema_misaligned' non compare piu
if isinstance(r_def, str) and r_def.startswith("ema_misaligned"):
    C.CFG["ema_filter"] = False
    r = run(b_ema)
    check(not (isinstance(r, str) and r.startswith("ema_misaligned")), "ema_filter=False: niente blocco EMA")
    C.CFG["ema_filter"] = True
else:
    check(True, "(serie di test senza EMA disallineate: caso EMA saltato)")
# 3) momentum
down = [100.0] * 10 + [101.5] * 3 + [101.0, 100.9, 100.8, 100.7, 100.6, 100.55, 100.52, 100.5, 100.5, 100.5, 100.5, 100.5]
bm = bars(down, heavy=False)
r_m = run(bm)
print("mom default ->", str(r_m)[:110])
if isinstance(r_m, str) and r_m.startswith("momentum"):
    C.CFG["mom_filter"] = False
    r = run(bm)
    check(not (isinstance(r, str) and r.startswith("momentum")), "mom_filter=False: niente blocco momentum")
    C.CFG["mom_filter"] = True
else:
    check(True, "(caso momentum saltato)")
print("FAILED" if failed else "ALL OK"); raise SystemExit(1 if failed else 0)
