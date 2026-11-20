#!/usr/bin/env python3
"""Test: filtro SPK12 (movimento brusco / gap contrario) in trade.spike_gap_block; ROLLBACK con CFG['spike_filter']=False."""
import os, tempfile
import numpy as np, pandas as pd
from zoneinfo import ZoneInfo
TD = tempfile.mkdtemp(prefix="pt-spk-")
os.environ.update(PT_DB=os.path.join(TD, "l.sqlite"), PT_LOCK=os.path.join(TD, ".lock"), PT_LOGS=os.path.join(TD, "logs"),
                  PT_REPORTS=os.path.join(TD, "reports"), PT_CHARTS=os.path.join(TD, "charts"))
import common as C
import trade as T
R = ZoneInfo("Europe/Rome"); failed = 0
def check(c, n):
    global failed
    print(("ok  " if c else "FAIL ") + n); failed += (not c)
check(C.CFG.get("spike_filter") is True and C.CFG.get("spike_filter_atr") == 1.2 and C.CFG.get("gap_down_skip") == 0.02, "config SPK12 attiva (1,2 ATR, gap 2%)")
o = pd.Timestamp("2026-11-20 15:30", tz=R)
idx = pd.date_range("2026-11-20 07:30", "2026-11-20 20:35", freq="5min", tz=R)
c = 100 + np.arange(len(idx)) * 0.01
s = pd.DataFrame({"Open": c, "High": c + 0.05, "Low": c - 0.05, "Close": c, "Volume": 1000.0}, index=idx)
d = pd.DataFrame({"Open": [99.0, 99.5], "High": [100.0, 101.0], "Low": [98.0, 99.0], "Close": [99.5, 100.5]},
                 index=pd.to_datetime(["2026-11-18", "2026-11-19"]))
check(T.spike_gap_block(s, o, d, 0.5) is None, "seduta regolare: nessun blocco")
s2 = s.copy(); s2.iloc[-2, s2.columns.get_loc("Close")] -= 1.0   # barra brusca di ~1 punto, ATR 0,5 -> 2 ATR
check("brusco" in (T.spike_gap_block(s2, o, d, 0.5) or ""), "spike > 1,2 ATR nelle ultime 6 barre: blocca")
s3 = s.copy(); s3.iloc[-9, s3.columns.get_loc("Close")] -= 1.0   # spike fuori dalla finestra di 30 min
check(T.spike_gap_block(s3, o, d, 0.5) is None, "spike piu' vecchio di 6 barre: non blocca")
s4 = s.copy(); s4.loc[s4.index >= o, "Open"] = 97.0               # apertura cash -3,5% sotto ieri
check("gap" in (T.spike_gap_block(s4, o, d, 5.0) or ""), "gap contrario > 2%: blocca")
s5 = s.copy(); s5.iloc[5, s5.columns.get_loc("Close")] -= 3.0      # spike nel pre-market LS: ignorato
check(T.spike_gap_block(s5, o, d, 0.5) is None, "spike nel pre-market LS ignorato (solo seduta cash)")
C.CFG["spike_filter"] = False
check(T.spike_gap_block(s2, o, d, 0.5) is None and T.spike_gap_block(s4, o, d, 5.0) is None, "rollback: spike_filter=False disattiva")
print("FAILED" if failed else "ALL OK"); raise SystemExit(1 if failed else 0)
