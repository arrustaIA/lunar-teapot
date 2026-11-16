#!/usr/bin/env python3
"""Tests for the V0_FEE4 shadow trial (v0 with fee gate 4x): sizing gate, plan wiring, trade_log id,
21:56 report comparison. No market data, no live ledger, no orders."""
import os, sys, json, tempfile
from datetime import datetime, timedelta
import numpy as np, pandas as pd

TD = tempfile.mkdtemp(prefix="pt-fee4-")
for k, v in dict(PT_DB="ledger.sqlite", PT_LOCK=".lock", PT_TRADE_LOG="trade_log.jsonl", PT_LOGS="logs",
                 PT_REPORTS="reports", PT_SHADOW_DIR="shadow").items():
    os.environ[k] = os.path.join(TD, v)
for d in ("logs", "reports", "shadow"):
    os.makedirs(os.path.join(TD, d), exist_ok=True)

import common as C
import shadow as SH

failed = 0


def check(cond, name):
    global failed
    print(("ok  " if cond else "FAIL ") + name)
    if not cond:
        failed += 1


def test_gate():
    # 3 shares x 2R x 1.15 = 6.90 EUR: passes the live 6 EUR gate, fails the 8 EUR one
    check(SH.size(100.0, 1.15, "EUR") > 0, "v0 gate (3x fees) accepts 6.90 EUR reward")
    check(SH.size(100.0, 1.15, "EUR", min_rr=SH.MIN_RR["V0_FEE4"]) == 0, "V0_FEE4 gate rejects 6.90 EUR reward")
    check(SH.size(100.0, 1.50, "EUR", min_rr=SH.MIN_RR["V0_FEE4"]) > 0, "V0_FEE4 gate accepts 9.00 EUR reward")
    check(SH.MIN_RR["V0_FEE4"] == 4.0 and C.CFG["min_reward_vs_fees"] == 3.0, "production gate untouched (3x), FEE4 = 4x")


def test_wiring():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shadow.py")).read()
    check('[(i, "V0_FEE4") for i in static]' in src, "V0_FEE4 planned on the static (production) watchlist")
    import debate
    check("V0_FEE4" not in debate.STRATS, "V0_FEE4 does not trigger LLM debate calls")


def test_eod_trade_log_and_report():
    d = C.today()
    o = datetime.combine(d, datetime.min.time()).replace(hour=10, tzinfo=C.ROME)
    idx = pd.date_range(o, periods=24, freq="5min")
    c = np.linspace(100, 104, len(idx))
    b = pd.DataFrame({"Open": c, "High": c + 0.05, "Low": c - 0.05, "Close": c, "Volume": 1000.0}, index=idx)
    row = dict(day=d.isoformat(), ts=idx[0].isoformat(), strategy="V0_FEE4", ticker="TST.DE", region="EU",
               currency="EUR", price=100.0, entry=100.05, stop=98.55, target=103.05, qty=3.0, qty_diag=3.0,
               chart_score=30, chart_verdict="APPROVE", approved=True, bar=str(idx[0]), info="test", side="long")
    SH.append(SH.SIG, row)
    SH.append(SH.DSIG, dict(row, strategy="V0", blocked_by_fees=False))
    SH.intraday_bars = C.intraday_bars = lambda tick, *a, **k: {"TST.DE": b}   # no network
    SH.eod(dry=False)
    tl = [json.loads(l) for l in open(os.environ["PT_TRADE_LOG"])]
    f4 = [r for r in tl if r.get("strategy_id") == "V0_FEE4"]
    check(len(f4) == 1 and f4[0]["source"] == "shadow", "eod writes one shadow trade_log line with strategy_id V0_FEE4")
    check(f4 and f4[0]["exit_reason"] == "target", "V0_FEE4 trade replayed to target")
    md = open(os.path.join(os.environ["PT_REPORTS"], f"shadow_{d:%Y-%m-%d}.md")).read()
    check("## Prova V0_FEE4" in md and "1 operativi" in md and "Copia V0" in md and "v0 in produzione" in md,
          "21:56 report has the V0_FEE4 vs v0 comparison")


if __name__ == "__main__":
    for f in (test_gate, test_wiring, test_eod_trade_log_and_report):
        try:
            f()
        except Exception as e:
            failed += 1
            print(f"FAIL {f.__name__}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
