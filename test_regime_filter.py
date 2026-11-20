#!/usr/bin/env python3
"""Test del filtro di regime sui long (21/11/2026): CFG['regime_filter_long'], trade.index_regime / regime_block.
Indice sopra VWAP -> passa; sotto -> blocca; dati mancanti/vecchi/flag spento -> non blocca (degrado sicuro)."""
import os, tempfile
import numpy as np, pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
TD = tempfile.mkdtemp(prefix="pt-rg-")
os.environ.update(PT_DB=os.path.join(TD, "l.sqlite"), PT_LOCK=os.path.join(TD, ".lock"), PT_LOGS=os.path.join(TD, "logs"),
                  PT_REPORTS=os.path.join(TD, "reports"), PT_CHARTS=os.path.join(TD, "charts"))
import common as C
import trade as T
R = ZoneInfo("Europe/Rome"); failed = 0
def check(c, n):
    global failed
    print(("ok  " if c else "FAIL ") + n); failed += (not c)
def bars(start, n, slope, vol=1000.0):
    idx = pd.date_range(start, periods=n, freq="5min", tz=R); c = 100 + np.cumsum(np.full(n, slope))
    return pd.DataFrame({"Open": c, "High": c + 0.02, "Low": c - 0.02, "Close": c, "Volume": np.full(n, vol)}, index=idx)
check(C.CFG.get("regime_filter_long") is True, "flag di produzione acceso")
at = datetime(2026, 11, 20, 11, 0, tzinfo=R)
up, down = bars("2026-11-20 09:00", 30, 0.05), bars("2026-11-20 09:00", 30, -0.05)
check(T.index_regime("EU", up, at)[0] == 1, "EU in salita: sopra VWAP")
check(T.index_regime("EU", down, at)[0] == -1, "EU in discesa: sotto VWAP")
check(T.regime_block("EU", up, at) is None, "regime rialzista: long consentito")
check(T.regime_block("EU", down, at) is not None and "ribassista" in T.regime_block("EU", down, at), "regime ribassista: long bloccato")
# solo barre chiuse: la barra delle 10:55 (in formazione alle 11:00) non conta
check(T.index_regime("EU", up[up.index < pd.Timestamp("2026-11-20 10:55", tz=R)], at)[0] == 1, "usa solo barre chiuse")
# degrado sicuro
_yf = T.yf_intraday_bars; T.yf_intraday_bars = lambda *a, **k: {}; T._regime_cache.clear()
check(T.index_regime("EU", None, at)[0] is None and T.regime_block("EU", None, at) is None, "download senza dati: non blocca")
def _boom(*a, **k): raise RuntimeError("rete giu'")
T.yf_intraday_bars = _boom; T._regime_cache.clear()
check(T.regime_block("EU", None, at) is None, "download in errore: non blocca")
T.yf_intraday_bars = _yf; T._regime_cache.clear()
check(T.regime_block("EU", pd.DataFrame(columns=up.columns), at) is None, "DataFrame vuoto: non blocca")
old = bars("2026-11-20 09:00", 6, -0.05)   # finisce alle 09:25, alle 11:00 e' vecchia
check(T.index_regime("EU", old, at)[0] is None and T.regime_block("EU", old, at) is None, "barra vecchia > 30 min: non blocca")
y = bars("2026-11-19 09:00", 30, -0.05)
check(T.regime_block("EU", y, at) is None, "solo dati di ieri: non blocca")
z = down.copy(); z["Volume"] = 0.0
check(T.index_regime("EU", z, at)[0] == -1, "volumi a zero: VWAP = media dei prezzi tipici")
# US: seduta cash dalle 15:30
us = bars("2026-11-20 15:30", 20, -0.5, vol=3e8); at_us = datetime(2026, 11, 20, 17, 20, tzinfo=R)
check(T.regime_block("US", us, at_us) is not None, "US ^GSPC sotto VWAP alle 17:20: long bloccato")
check(T.index_regime("US", us, datetime(2026, 11, 20, 15, 32, tzinfo=R))[0] is None, "US prima della prima barra chiusa: indeterminato")
# rollback
C.CFG["regime_filter_long"] = False
check(T.regime_block("EU", down, at) is None, "flag spento (rollback): non blocca mai")
C.CFG["regime_filter_long"] = True
print("TUTTI OK" if not failed else f"{failed} FALLITI"); raise SystemExit(1 if failed else 0)
