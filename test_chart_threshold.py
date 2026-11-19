#!/usr/bin/env python3
"""Test: la soglia d'ingresso long dell'analista grafico e' CFG['chart_approve_buy'] (45 dal 20/11/2026; 25 prima)."""
import os, tempfile
import numpy as np, pandas as pd
from zoneinfo import ZoneInfo
TD = tempfile.mkdtemp(prefix="pt-ch-")
os.environ.update(PT_DB=os.path.join(TD, "l.sqlite"), PT_LOCK=os.path.join(TD, ".lock"), PT_LOGS=os.path.join(TD, "logs"),
                  PT_REPORTS=os.path.join(TD, "reports"), PT_CHARTS=os.path.join(TD, "charts"))
import common as C
import chart_analysis as CA
failed = 0
def check(c, n):
    global failed
    print(("ok  " if c else "FAIL ") + n); failed += (not c)
check(C.CFG.get("chart_approve_buy") == 45, "soglia di produzione = 45")
idx = pd.date_range("2026-11-17 09:00", periods=400, freq="5min", tz=ZoneInfo("Europe/Rome"))
c = 100 + np.cumsum(np.full(400, 0.02))
b = pd.DataFrame({"Open": c, "High": c + 0.05, "Low": c - 0.05, "Close": c, "Volume": np.full(400, 1000.0)}, index=idx)
d = pd.DataFrame({"Open": np.linspace(80, 100, 80), "High": np.linspace(81, 101, 80), "Low": np.linspace(79, 99, 80),
                  "Close": np.linspace(80, 100, 80), "Volume": np.full(80, 1e6)}, index=pd.date_range("2026-08-01", periods=80, freq="B"))
def verdict():
    a = CA.analyze("TST", "buy", b, d, 99.0, 103.0, save_chart=False)
    return a["verdict"], a["score"]
C.CFG["chart_approve_buy"] = -101; v, s = verdict(); check(v == "APPROVE", f"soglia -101: approva (score {s})")
C.CFG["chart_approve_buy"] = 101;  v, s = verdict(); check(v == "REJECT", f"soglia 101: rifiuta (score {s})")
C.CFG["chart_approve_buy"] = s;    v, _ = verdict(); check(v == "APPROVE", "score uguale alla soglia: approva")
C.CFG["chart_approve_buy"] = s + 1; v, _ = verdict(); check(v == "REJECT", "score sotto la soglia di 1: rifiuta")
# le uscite non dipendono dalla soglia d'ingresso
C.CFG["chart_approve_buy"] = 101
a = CA.analyze("TST", "sell", b, d, 99.0, 103.0, save_chart=False); check(a["verdict"] in ("HOLD", "EXIT"), "uscita (sell) indipendente")
print("FAILED" if failed else "ALL OK"); raise SystemExit(1 if failed else 0)
