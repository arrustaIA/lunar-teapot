#!/usr/bin/env python3
"""Unit tests for the v0 EMA9>EMA21 alignment filter (no live ledger, no market data)."""
import os, tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

ROME = ZoneInfo("Europe/Rome")

def _env(td):
    os.environ["PT_DB"] = os.path.join(td, "ledger.sqlite")
    os.environ["PT_LOCK"] = os.path.join(td, ".lock")
    os.environ["PT_TRADE_LOG"] = os.path.join(td, "trade_log.jsonl")
    os.environ["PT_LOGS"] = os.path.join(td, "logs")
    os.environ["PT_REPORTS"] = os.path.join(td, "reports")
    os.makedirs(os.environ["PT_LOGS"], exist_ok=True)
    os.makedirs(os.environ["PT_REPORTS"], exist_ok=True)

TD = tempfile.mkdtemp(prefix="pt-ema-")
_env(TD)

import common as C
import stats as ST
import shadow as SH

failed = 0

def check(cond, name):
    global failed
    if cond:
        print(f"ok  {name}")
    else:
        failed += 1
        print(f"FAIL {name}")


def _ohlc(closes, start="2026-11-02 09:00", freq="5min"):
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz=ROME)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "Open": c, "High": c + 0.1, "Low": c - 0.1, "Close": c,
        "Volume": np.full(len(c), 1000.0),
    }, index=idx)


def test_long_ok_on_uptrend():
    # steadily rising 5m closes: EMA9 must end above EMA21
    b = _ohlc([100 + i * 0.2 for i in range(40)])
    ok, e9, e21 = C.ema_aligned(b, side="long")
    check(ok and e9 > e21, f"long aligned on uptrend (EMA9={e9:.4f} EMA21={e21:.4f})")


def test_long_rejected_on_downtrend():
    b = _ohlc([120 - i * 0.2 for i in range(40)])
    ok, e9, e21 = C.ema_aligned(b, side="long")
    check((not ok) and e9 < e21, f"long rejected on downtrend (EMA9={e9:.4f} EMA21={e21:.4f})")


def test_short_ok_on_downtrend():
    b = _ohlc([120 - i * 0.2 for i in range(40)])
    ok, e9, e21 = C.ema_aligned(b, side="short")
    check(ok and e9 < e21, f"short aligned on downtrend (EMA9={e9:.4f} EMA21={e21:.4f})")


def test_short_rejected_on_uptrend():
    b = _ohlc([100 + i * 0.2 for i in range(40)])
    ok, e9, e21 = C.ema_aligned(b, side="short")
    check((not ok) and e9 > e21, f"short rejected on uptrend (EMA9={e9:.4f} EMA21={e21:.4f})")


def test_strict_inequality():
    # flat series: EMA9 == EMA21, neither side is aligned
    b = _ohlc([100.0] * 40)
    ok_l, e9, e21 = C.ema_aligned(b, side="long")
    ok_s, _, _ = C.ema_aligned(b, side="short")
    check(abs(e9 - e21) < 1e-12 and (not ok_l) and (not ok_s),
          f"flat series is not aligned either way (EMA9={e9} EMA21={e21})")


def test_too_short_series():
    b = _ohlc([100 + i for i in range(10)])  # < 21 bars
    ok, e9, e21 = C.ema_aligned(b, side="long")
    check((not ok) and e9 != e9 and e21 != e21, "fewer than 21 5m bars -> EMA not ready")


def test_same_timeframe_from_1m_bars():
    # 40 five-minute closes, then the same path as 1-minute bars (constant inside each 5m bucket)
    closes5 = [100 + i * 0.2 for i in range(40)]
    b5 = _ohlc(closes5, freq="5min")
    closes1 = [c for c in closes5 for _ in range(5)]
    b1 = _ohlc(closes1, start="2026-11-02 09:00", freq="1min")
    ok5, e95, e215 = C.ema_aligned(b5, side="long")
    ok1, e91, e211 = C.ema_aligned(b1, side="long")
    check(ok5 is True and ok1 is True and abs(e95 - e91) < 1e-9 and abs(e215 - e211) < 1e-9,
          f"1m series resampled to 5m matches 5m EMA (5m {e95:.6f}/{e215:.6f} vs 1m {e91:.6f}/{e211:.6f})")


def test_periods_match_validation():
    check(C.CFG["ema_fast"] == 9 and C.CFG["ema_slow"] == 21, "CFG periods are 9 and 21")


def test_log_reasons_counts_ema_misaligned():
    day = "2026-11-16"
    path = os.path.join(C.LOGS, f"{day}.log")
    with open(path, "w") as f:
        f.write("2026-11-16 10:10:00 [trade] SAP.DE: ema_misaligned: EMA9 101.200 non sopra EMA21 102.400; prezzo 103.000\n")
        f.write("2026-11-16 10:20:00 [trade] SIE.DE: ema_misaligned: EMA9 80.100 non sopra EMA21 81.000; prezzo 82.000\n")
        f.write("2026-11-16 10:30:00 [trade] ALV.DE: sotto VWAP: prezzo 200.000, ORH 201.000\n")
        f.write("2026-11-16 10:40:00 [trade] SAP.DE: analista grafico HOLD (score 10), stop 1.0 target 2.0\n")
        f.write("2026-11-16 10:50:00 [trade] equity 1000.00 EUR\n")
    reasons = ST.log_reasons(day)
    check(reasons.get("ema_misaligned") == 2, f"ema_misaligned counted twice (got {reasons})")
    check(reasons.get("sotto VWAP") == 1, f"sotto VWAP still counted (got {reasons})")
    check("analista grafico HOLD" not in reasons and "equity" not in reasons,
          "management/equity lines are still skipped")


def test_shadow_orb_rejects_misaligned():
    """orb() (V0 / V0_LOOSE / ORB_DYN) must not fire a long when EMA9 <= EMA21."""
    o = datetime(2026, 11, 16, 9, 0, tzinfo=ROME)
    # Steep downtrend so EMA9 stays below EMA21, then a one-bar poke just above the OR high.
    prior = _ohlc([130 - 0.4 * i for i in range(100)], start="2026-11-12 09:00", freq="5min")
    today_closes = [90.0, 90.05, 90.02, 89.95, 89.9, 89.85] + [89.8] * 30 + [89.7, 89.75, 89.8, 90.35]
    today_b = _ohlc(today_closes, start="2026-11-16 09:00", freq="5min")
    b = pd.concat([prior, today_b])
    sess = b[b.index >= o]
    ok, e9, e21 = C.ema_aligned(b, side="long")
    check((not ok) and e9 < e21, f"fixture stays EMA-misaligned (EMA9={e9:.4f} EMA21={e21:.4f})")
    orig_st = C.session_times
    def _st(region, d=None):
        d = d or datetime(2026, 11, 16, tzinfo=ROME).date()
        return orig_st(region, d)
    try:
        C.session_times = _st
        SH.session_times = _st
        sig = SH.orb(b, sess, "EU")
    finally:
        C.session_times = orig_st
        SH.session_times = orig_st
    orh = float(sess.iloc[:6]["High"].max())
    close = float(sess["Close"].iloc[-1])
    mom = close - float(sess["Close"].iloc[-4])
    check(close > orh and mom > 0, f"fixture is an ORB breakout (close={close:.3f} ORH={orh:.3f} mom={mom:.3f})")
    check(sig is None, f"shadow orb returns None when EMA misaligned (EMA9={e9:.4f} EMA21={e21:.4f})")


if __name__ == "__main__":
    import sys
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as e:
                failed += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
