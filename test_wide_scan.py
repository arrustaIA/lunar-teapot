#!/usr/bin/env python3
"""Tests for the wide universe scan, the fee-gate sizing (size_position, optional leverage-to-gate),
leveraged paper accounting (loan_eur) and the report's fee-gate reason grouping. No network, temp DB."""
import os, sys, tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

ROME = ZoneInfo("Europe/Rome")
TD = tempfile.mkdtemp(prefix="pt-wide-")
os.environ["PT_DB"] = os.path.join(TD, "ledger.sqlite")
os.environ["PT_LOCK"] = os.path.join(TD, ".lock")
os.environ["PT_TRADE_LOG"] = os.path.join(TD, "trade_log.jsonl")
os.environ["PT_LOGS"] = os.path.join(TD, "logs")
os.environ["PT_REPORTS"] = os.path.join(TD, "reports")
for k in ("PT_LOGS", "PT_REPORTS"):
    os.makedirs(os.environ[k], exist_ok=True)

import common as C
import stats as ST
import trade as T

failed = 0
def check(cond, name):
    global failed
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failed += 1


def test_size_position_gate():
    old = dict(C.CFG)
    try:
        C.CFG["lev_to_gate"] = False
        s = C.size_position(1000.0, 1000.0, 100.0, 0.4)          # 0.4% stop, 300 EUR cap -> 2R = 2.40 EUR
        check(s["qty"] > 0 and abs(s["reward"] - 2.4) < 0.01, "cap 300 EUR, stop 0.4%: reward 2.40 EUR")
        check(s["why"].startswith("filtro commissioni"), "fee gate rejects quiet breakout without leverage")
        s = C.size_position(1000.0, 1000.0, 100.0, 1.5)          # 1.5% stop -> 2R = 9 EUR
        check(s["why"] == "" and abs(s["value"] - 300) < 0.1 and s["loan"] == 0, "wide stop passes at 1x")
        C.CFG["lev_to_gate"] = True; C.CFG["max_leverage"] = 5.0
        s = C.size_position(1000.0, 1000.0, 100.0, 0.4)
        check(s["why"] == "" and 6.0 <= s["reward"] < 6.05, "leverage-to-gate: reward just reaches 6 EUR")
        check(abs(s["margin"] - 300) < 0.01 and 2.49 < s["lev"] < 2.52 and s["loan"] > 449, "margin 300, lev ~2.5x, loan ~450")
        check(s["qty"] * 0.4 + 2 <= 20.0 + 1e-6, "risk stays within 2% of equity")
        s = C.size_position(1000.0, 1000.0, 100.0, 1.5)
        check(s["loan"] == 0 and s["lev"] == 1.0, "no leverage when the gate is reachable at 1x")
        s = C.size_position(1000.0, 1000.0, 100.0, 0.05)       # absurdly tight stop: lev capped at 5x
        check(s["value"] <= 5 * 300 + 0.01, "notional capped at 5x the slot")
        s = C.size_position(1000.0, 150.0, 100.0, 0.4)          # little cash -> margin limited, below min size
        check(s["why"] != "", "insufficient cash for the margin -> no trade")
    finally:
        C.CFG.clear(); C.CFG.update(old)


def test_leveraged_ledger():
    con = C.db()
    cash0 = C.get_cash(con)
    C.open_position(con, "SAP.DE", 7.5, 100.0, stop=99.6, target=100.8, risk_eur=5.0, rationale="t", entry_bar="x",
                    margin_eur=300.0)
    p = C.positions(con)[0]
    check(abs(p["loan_eur"] - (p["qty"] * p["entry_eur"] - 300.0)) < 1e-4, "loan_eur stored")
    check(abs(C.get_cash(con) - (cash0 - 300.0 - 1.0)) < 1e-4, "cash debited by margin + fee only")
    eq, cash, mv = C.equity(con, {"SAP.DE": (p["entry_eur"], None)})
    check(abs(eq - (cash0 - 1.0)) < 1e-3, "equity at entry price = start - entry fee")
    check(abs(C.leverage(p) - p["qty"] * p["entry_eur"] / 300.0) < 1e-6, "leverage() = notional / margin")
    fill, net = C.close_position(con, p, 100.8, "take profit", apply_slippage=False)
    exp_gross = 7.5 * (100.8 - p["entry_eur"])
    check(abs(C.get_cash(con) - (cash0 + exp_gross - 2.0 - max(0, (exp_gross - 2.0)) * 0.26)) < 0.02,
          "cash after close = start + gross - fees - tax (loan repaid)")
    check(not C.positions(con), "position closed")


def _bars(day, orh=101.0, last=101.5):
    idx = pd.date_range(datetime.combine(day, datetime.min.time(), ROME) + timedelta(hours=9), periods=30, freq="5min")
    c = np.linspace(100.0, 100.8, 6).tolist() + [orh - 0.3] * 10 + np.linspace(orh - 0.2, last, 14).tolist()
    df = pd.DataFrame({"Open": c, "High": [x + 0.05 for x in c], "Low": [x - 0.05 for x in c], "Close": c,
                       "Volume": 1000}, index=idx)
    df.iloc[:6, df.columns.get_loc("High")] = [orh - 0.4, orh - 0.3, orh, orh - 0.2, orh - 0.1, orh - 0.3]
    return df


def test_breakout_candidates():
    d = C.today()
    old_st = C.session_times
    try:
        T.session_times = lambda region, dd=None: (datetime.combine(d, datetime.min.time(), ROME) + timedelta(hours=9),
                                                     datetime.combine(d, datetime.min.time(), ROME) + timedelta(hours=17, minutes=30), None)
        old_ts = T.today_session
        T.today_session = lambda b, region, dd=None, cash_only=False: b
        yfb = {"UP.DE": _bars(d, 101.0, 101.6), "FLAT.DE": _bars(d, 101.0, 99.0)}
        uni = [dict(ticker="UP.DE", region="EU"), dict(ticker="FLAT.DE", region="EU"), dict(ticker="NODATA.DE", region="EU")]
        c = T.breakout_candidates(yfb, uni)
        check(c == ["UP.DE"], f"breakout screen keeps only names at/above the OR high ({c})")
        T.today_session = old_ts
    finally:
        T.session_times = old_st


def test_wide_items_order_and_live_cap():
    uni = [dict(ticker=f"T{i}.DE", name=f"T{i}", region="EU", currency="EUR", isin="") for i in range(30)]
    uni += [dict(ticker="U1", name="U1", region="US", currency="USD", isin=""), dict(ticker="U2", name="U2", region="US", currency="USD", isin="")]
    calls = {}
    old = (T.load_wide_universe, T.yf_intraday_bars_chunked, T.intraday_bars, T.daily_bars, T.breakout_candidates)
    oldcfg = dict(C.CFG)
    try:
        T.load_wide_universe = lambda: uni
        def yb(tick, *a, **k):
            calls["yahoo"] = list(tick); return {t: pd.DataFrame({"Close": [1.0]}) for t in tick}
        T.yf_intraday_bars_chunked = yb
        def ib(tick, *a, **k):
            calls["live"] = list(tick); return {t: pd.DataFrame({"Close": [2.0]}) for t in tick}
        T.intraday_bars = ib
        T.daily_bars = lambda tick, *a, **k: {t: None for t in tick}
        T.breakout_candidates = lambda yfb, u, n=None: ["T29.DE", "U2"]
        wl = [dict(ticker="T0.DE", name="T0", region="EU", currency="EUR"),
              dict(ticker="U1", name="U1", region="US", currency="USD")]
        C.CFG["wide_regions"] = ("EU", "US"); C.CFG["ls_priority_max"] = 4
        items, bars, daily = T.wide_data(wl, ["T5.DE"])
        tk = [i["ticker"] for i in items]
        check(len(calls["yahoo"]) == 32, "Yahoo screen covers the whole wide universe (EU + US)")
        check(tk == ["T0.DE", "U1", "T5.DE", "T29.DE", "U2"], f"full evaluation only for watchlist, held and candidates ({tk})")
        check(calls["live"] == ["T5.DE", "T29.DE", "U2", "T0.DE"], "live quotes: held, candidates, watchlist, capped")
        check(float(bars["T29.DE"]["Close"].iloc[0]) == 2.0 and float(bars["T10.DE"]["Close"].iloc[0]) == 1.0,
              "live bars override Yahoo for priority names, Yahoo for the rest")
        check(set(daily) == {"T5.DE", "T29.DE", "U2", "T0.DE", "U1"}, "daily bars only for names that can signal")
        C.CFG["wide_regions"] = ("EU",)
        T.breakout_candidates = lambda yfb, u, n=None: []
        items, bars, daily = T.wide_data(wl, [])
        check("U2" not in calls["yahoo"] and "U1" in calls["yahoo"], "wide_regions limits the screen (watchlist always kept)")
    finally:
        T.load_wide_universe, T.yf_intraday_bars_chunked, T.intraday_bars, T.daily_bars, T.breakout_candidates = old
        C.CFG.clear(); C.CFG.update(oldcfg)


def test_wide_universe_file():
    w = C.load_wide_universe()
    core = C.load_universe()
    tk = [r["ticker"] for r in w]
    check(len(tk) == len(set(tk)), "wide universe has no duplicates")
    check(tk[:len(core)] == [r["ticker"] for r in core], "core rows (with ISIN) first")
    check(len(w) >= 1000, f"wide universe has >= 1000 names ({len(w)})")
    check(all(r["region"] in ("EU", "US") and r["currency"] in ("EUR", "USD") for r in w), "only EU/EUR and US/USD rows")
    m = C.meta(w[-1]["ticker"])
    check(m["ticker"] == w[-1]["ticker"] and m["currency"] == w[-1]["currency"], "meta() finds wide-universe names")


def test_report_reason_grouping():
    day = C.today().isoformat()
    with open(os.path.join(os.environ["PT_LOGS"], f"{day}.log"), "a") as f:
        f.write(f"{day} 10:00:00 [trade] BAYN.DE: filtro commissioni: guadagno atteso 2.40 EUR < 6 EUR (3x commissioni)\n")
        f.write(f"{day} 10:10:00 [trade] DTE.DE: filtro commissioni: guadagno atteso 2.31 EUR < 6 EUR (3x commissioni)\n")
        f.write(f"{day} 10:10:00 [trade] HAG.DE: guadagno atteso 4.19 EUR < 3x commissioni\n")
        for i in range(10):
            f.write(f"{day} 10:20:00 [trade] X{i}.DE: nessun breakout: prezzo {i}.0, ORH 2\n")
    r = ST.log_reasons(day)
    check(r.get(ST.FEE_GATE_KEY) == 3, f"fee-gate rejects grouped in one bucket ({r})")
    check(r.get("nessun breakout") == 10, "numbers stripped from other reasons")
    fg = ST.fee_gate_rejects(day)
    check(fg == {"BAYN.DE": 1, "DTE.DE": 1, "HAG.DE": 1}, "fee-gate rejects per ticker")


def test_shadow_v0_wide_plan():
    import shadow as SH, rescan
    os.environ["PT_SHADOW_DIR"] = TD
    uni = [dict(ticker="A.DE", name="A", region="EU", currency="EUR", isin=""),
           dict(ticker="B.DE", name="B", region="EU", currency="EUR", isin=""),
           dict(ticker="U1", name="U1", region="US", currency="USD", isin=""),
           dict(ticker="U2", name="U2", region="US", currency="USD", isin="")]
    calls = {}
    saved = (SH.load_watchlist, rescan.load_dyn, SH.load_universe, SH.intraday_bars, SH.yf_intraday_bars, SH.is_weekend,
             SH.news_scan, SH.spawn_debate, rescan.daily_cached)
    old = dict(C.CFG)
    try:
        C.CFG["wide_universe"] = True; C.CFG["wide_regions"] = ("EU",)
        SH.load_watchlist = lambda *a, **k: {"items": [dict(uni[0]), dict(uni[2])]}
        rescan.load_dyn = lambda *a, **k: []
        SH.load_universe = lambda: uni
        SH.is_weekend = lambda *a: False
        SH.news_scan = lambda *a, **k: 0
        SH.spawn_debate = lambda: None
        rescan.daily_cached = lambda *a, **k: {}
        def ib(t, *a, **k): calls["live"] = list(t); return {}
        def yb(t, *a, **k): calls["yahoo"] = list(t); return {}
        SH.intraday_bars, SH.yf_intraday_bars = ib, yb
        SH.scan(dry=True)
        check(calls.get("yahoo") == ["U2"], f"V0_WIDE: only US names outside the 09:35 list, one Yahoo batch ({calls})")
        check("U2" not in calls.get("live", []) and "B.DE" not in calls.get("yahoo", []),
              "names already scanned wide by production are not duplicated in shadow")
    finally:
        (SH.load_watchlist, rescan.load_dyn, SH.load_universe, SH.intraday_bars, SH.yf_intraday_bars, SH.is_weekend,
         SH.news_scan, SH.spawn_debate, rescan.daily_cached) = saved
        C.CFG.clear(); C.CFG.update(old)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as e:
                import traceback; traceback.print_exc()
                failed += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    print("tutti i controlli superati" if not failed else f"{failed} falliti")
    sys.exit(1 if failed else 0)
