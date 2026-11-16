#!/usr/bin/env python3
"""Unit tests for the v0 SHORT side (mirror ORB breakdown) and short accounting in the PAPER ledger.
No live ledger, no network: everything runs on a temp DB with synthetic bars."""
import json, os, tempfile, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROME = ZoneInfo("Europe/Rome")
TD = tempfile.mkdtemp(prefix="pt-short-")
os.environ["PT_DB"] = os.path.join(TD, "ledger.sqlite")
os.environ["PT_LOCK"] = os.path.join(TD, ".lock")
os.environ["PT_TRADE_LOG"] = os.path.join(TD, "trade_log.jsonl")
os.environ["PT_LOGS"] = os.path.join(TD, "logs")
os.environ["PT_REPORTS"] = os.path.join(TD, "reports")
os.environ["PT_SHADOW_DIR"] = TD
for k in ("PT_LOGS", "PT_REPORTS"):
    os.makedirs(os.environ[k], exist_ok=True)

import common as C
import trade_log as TL
import stats as ST
import chart_analysis as CA
import trade as T

failed = 0
def check(cond, name):
    global failed
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failed += 1

C.meta = lambda t: dict(name="Test", ticker=t, region="EU", currency="EUR", isin="")
for mod in (T, ST):
    mod.meta = C.meta

def fresh():
    for fn in ("ledger.sqlite", "trade_log.jsonl"):
        fp = os.path.join(TD, fn)
        if os.path.exists(fp):
            os.remove(fp)
    return C.db()

def log_rows():
    p = TL.log_path()
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def test_short_open_close_profit_tax():
    con = fresh()
    fill = C.open_position(con, "TST.DE", 10.0, 50.0, stop=50.75, target=48.5, risk_eur=9.5,
                           rationale="ORB short test", entry_bar="2026-11-17 10:00", setup="ORB-SHORT", side="short")
    check(abs(fill - 50.0 * (1 - C.CFG["slippage"])) < 1e-9, f"short entry fills at mid - slippage (got {fill})")
    p = C.positions(con)[0]
    check(p["side"] == "short", "position stored as short")
    cash = C.get_cash(con)
    check(abs(cash - (1000 - 10 * fill - 1)) < 1e-6, f"short reserves notional + 1 € fee as collateral (cash {cash:.4f})")
    # equity at entry price ~ unchanged except fee; at a lower price it rises
    eq0 = C.equity(con, {"TST.DE": (fill, None)})[0]
    eq1 = C.equity(con, {"TST.DE": (fill - 1.0, None)})[0]
    check(abs(eq0 - 999.0) < 1e-6 and abs(eq1 - 1009.0) < 1e-6, f"short MTM: equity rises when price falls ({eq0:.2f} -> {eq1:.2f})")
    p["mae_local"], p["mfe_local"] = TL.update_excursion(p["mae_local"], p["mfe_local"], p["entry_local"], 48.4, 50.3, "short")
    fill2, net = C.close_position(con, p, 48.5, "take profit 48.5000 alle 12:00", apply_slippage=False)
    gross = 10 * (fill - 48.5)
    pnl = gross - 2.0
    tax = round(pnl * 0.26, 2)
    check(abs(net - (pnl - tax)) < 0.011, f"short net = (entry-exit)*qty - 2 € fees - 26% tax (got {net:.4f}, want {pnl - tax:.4f})")
    check(abs(C.get_cash(con) - (1000 + net)) < 1e-6 and abs(net - (pnl - 0.26 * pnl)) < 0.011, f"cash after cover = start + net ({C.get_cash(con):.4f})")
    sides = [r[0] for r in con.execute("SELECT side FROM trades ORDER BY id")]
    check(sides == ["SHORT", "COVER"], f"ledger sides SHORT then COVER (got {sides})")
    r = [x for x in log_rows() if x["symbol"] == "TST.DE"][-1]
    check(r["side"] == "short" and abs(r["gross_pnl_eur"] - gross) < 1e-4 and r["fees"] == 2.0
          and abs(r["tax_eur"] - tax) < 0.011 and abs(r["net_pnl_eur"] - net) < 1e-4 and abs(r["pnl_after_fees_eur"] - pnl) < 1e-4,
          f"trade_log short line: side/gross/fees/tax/net ({r['side']}, {r['gross_pnl_eur']}, {r['tax_eur']}, {r['net_pnl_eur']})")
    check(abs(r["mae_price"] - 50.3) < 1e-9 and abs(r["mfe_price"] - 48.4) < 1e-9
          and r["mae_eur"] < 0 and r["mfe_eur"] > 0, f"short MAE is the high (loss), MFE the low (gain): {r['mae_eur']} / {r['mfe_eur']}")
    rt = ST.round_trips(con)
    check(len(rt) == 1 and rt.iloc[0]["side"] == "short" and abs(rt.iloc[0]["net"] - net) < 1e-4,
          "round_trips pairs SHORT with COVER")
    con.close()


def test_short_loss_carryforward():
    con = fresh()
    fill = C.open_position(con, "TST.DE", 10.0, 50.0, stop=50.75, target=48.5, risk_eur=9.5, rationale="t",
                           entry_bar="x", setup="ORB-SHORT", side="short")
    p = C.positions(con)[0]
    fill2, net = C.close_position(con, p, 50.75, "stop 50.75 colpito alle 11:00", apply_slippage=True)
    check(abs(fill2 - 50.75 * (1 + C.CFG["slippage"])) < 1e-9, "short stop buys back at stop + slippage")
    loss = 10 * (fill - fill2) - 2.0
    check(loss < 0 and abs(net - loss) < 1e-6, f"short loss not taxed (net {net:.4f})")
    check(abs(C.tax_credit_available(con) - (-loss)) < 1e-6, "short loss goes into the 4-year minusvalenze bucket")
    con.close()


def test_short_marketable_cover_uses_ask():
    con = fresh()
    C.open_position(con, "TST.DE", 10.0, 50.0, stop=50.75, target=48.5, risk_eur=9.5, rationale="t", entry_bar="x",
                    side="short")
    p = C.positions(con)[0]
    qb = pd.DataFrame({"Close": [49.0]}); qb.attrs.update(bid=48.98, ask=49.02)
    fill2, _ = C.close_position(con, p, 49.0, "chiusura fine giornata EU", quote_bars=qb)
    check(abs(fill2 - 49.02) < 1e-9, f"flatten of a short buys at the ask (got {fill2})")
    con.close()


def test_long_unchanged():
    con = fresh()
    fill = C.open_position(con, "TST.DE", 10.0, 50.0, stop=49.0, target=52.0, risk_eur=12.0, rationale="t", entry_bar="x")
    p = C.positions(con)[0]
    check(p["side"] == "long", "default side is long")
    _, net = C.close_position(con, p, 52.0, "take profit", apply_slippage=False)
    pnl = 10 * (52.0 - fill) - 2.0
    check(abs(net - (pnl - round(pnl * 0.26, 2))) < 1e-6, "long P&L unchanged")
    check([r[0] for r in con.execute("SELECT side FROM trades ORDER BY id")] == ["BUY", "SELL"], "long sides BUY/SELL")
    con.close()


def test_migration_adds_side():
    import sqlite3
    path = os.path.join(TD, "old.sqlite")
    if os.path.exists(path):
        os.remove(path)
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE positions(ticker TEXT PRIMARY KEY, name TEXT, region TEXT, currency TEXT, qty REAL, entry_ts TEXT, "
                "entry_local REAL, entry_fx REAL, entry_eur REAL, entry_fee REAL, stop_local REAL, initial_stop_local REAL, "
                "target_local REAL, risk_eur REAL, rationale TEXT, entry_bar TEXT, setup TEXT, chart_score REAL, entry_chart TEXT)")
    old.execute("INSERT INTO positions(ticker, qty, entry_local, entry_eur, entry_fee, currency) VALUES('OLD.DE', 1, 10, 10, 1, 'EUR')")
    old.commit(); old.close()
    saved = C.DB
    C.DB = path
    try:
        con = C.db()
        ps = C.positions(con)
        check(len(ps) == 1 and ps[0]["side"] == "long", "old ledger migrated: existing position reads as long")
        con.close()
    finally:
        C.DB = saved


def test_chart_verdicts():
    check(CA.APPROVE_BUY == 25 and CA.EXIT_SELL == -30, "chart thresholds unchanged")
    src = open(CA.__file__).read()
    check('elif side == "short"' in src and "score <= -APPROVE_BUY" in src, "short entry needs chart score <= -25")
    check('elif side == "cover"' in src and "score >= -EXIT_SELL" in src, "short chart exit at score >= +30")


def _bars_breakdown(day):
    """Prior-day downtrend + today: OR 09:00-09:30 around 100, then a breakdown below the OR low."""
    prior = []
    t0 = datetime(day.year, day.month, day.day, 9, 0, tzinfo=ROME) - timedelta(days=1)
    for i in range(100):
        prior.append((t0 + timedelta(minutes=5 * i), 104 - 0.03 * i))
    o = datetime(day.year, day.month, day.day, 9, 0, tzinfo=ROME)
    today = [102.0, 101.5, 101.8, 101.0, 101.3, 100.5]           # OR: high 102.1, low 100.4
    today += [100.6, 100.55, 100.5, 100.45, 100.4, 100.35, 100.3, 100.25]  # drift down, close 100.25 < ORL 100.4 (within 1.5 ATR)
    rows = prior + [(o + timedelta(minutes=5 * i), c) for i, c in enumerate(today)]
    idx = pd.DatetimeIndex([r[0] for r in rows])
    c = np.array([r[1] for r in rows])
    b = pd.DataFrame({"Open": c + 0.02, "High": c + 0.1, "Low": c - 0.1, "Close": c, "Volume": 1000.0}, index=idx)
    return b, o + timedelta(minutes=5 * len(today) + 1)


def test_try_entry_short_signal():
    con = fresh()
    day = datetime(2026, 11, 17, tzinfo=ROME).date()
    b, wall = _bars_breakdown(day)
    b.attrs.update(source="ls", bid=float(b["Close"].iloc[-1]) - 0.01, ask=float(b["Close"].iloc[-1]) + 0.01)
    saved = dict(now=T.now, session_times=T.session_times, today_session=T.today_session, quote_ok=T.quote_ok,
                 news=T.news_signal, macro=T.macro_signal, analyze=CA.analyze, record=CA.record, atr=T.atr)
    seen = {}
    try:
        T.now = lambda: wall
        T.session_times = lambda region, d=None: C.session_times(region, day)
        T.today_session = lambda bb, region, d=None, cash_only=False: bb[bb.index >= datetime(day.year, day.month, day.day, 7, 30, tzinfo=ROME)]
        T.quote_ok = lambda bb, region: (True, 1.0)
        T.atr = lambda bb, n=14: pd.Series([0.8] * len(bb), index=bb.index)
        T.news_signal = lambda t, h=6: dict(score=0.0, top="")
        T.macro_signal = lambda h=6: dict(score=0.0, count=0)
        def fake_analyze(t, side, *a, **k):
            seen["side"] = side
            return dict(ticker=t, side=side, score=-40, verdict="APPROVE" if side == "short" else "REJECT", reasons=["test"], chart=None)
        CA.analyze = fake_analyze
        CA.record = lambda con, a, acted=0: None
        it = dict(ticker="TST.DE", region="EU")
        C.CFG["allow_short"] = True
        res = T.try_entry(con, it, b, 1000.0, 1000.0, 0, {})
        check(res == "ENTRATO", f"breakdown below ORL with EMA9<EMA21 opens a short (got: {res})")
        check(seen.get("side") == "short", "chart analyst asked for a short verdict")
        ps = C.positions(con)
        check(len(ps) == 1 and ps[0]["side"] == "short" and ps[0]["setup"] == "ORB-SHORT", "ledger has one ORB-SHORT position")
        if ps:
            p = ps[0]
            close = float(b["Close"].iloc[-1])
            check(p["stop_local"] > close and p["target_local"] < close, f"stop above, target below (stop {p['stop_local']:.3f}, target {p['target_local']:.3f}, close {close})")
            check(abs((p["stop_local"] - close) * 2 - (close - p["target_local"])) < 1e-6, "target is 2R below")
            check(abs(p["stop_local"] - close - 1.5 * 0.8) < 1e-6, "stop = close + 1.5 ATR (below ORH)")
            check(abs(p["entry_local"] - b.attrs["bid"]) < 1e-9, "short entry fills at the bid")
        # disabled short side -> no short
        con2 = fresh()
        C.CFG["allow_short"] = False
        res2 = T.try_entry(con2, it, b, 1000.0, 1000.0, 0, {})
        check(res2.startswith("nessun breakout") and not C.positions(con2), f"allow_short=False keeps v0 long-only (got: {res2[:40]})")
        # management: price rises through stop -> COVER at stop
        C.CFG["allow_short"] = True
        con3 = fresh()
        T.try_entry(con3, it, b, 1000.0, 1000.0, 0, {})
        p = C.positions(con3)[0]
        nxt = wall + timedelta(minutes=5)
        up = pd.DataFrame({"Open": [p["stop_local"] - 0.05], "High": [p["stop_local"] + 0.2], "Low": [p["stop_local"] - 0.1],
                           "Close": [p["stop_local"] + 0.1], "Volume": [1000.0]}, index=pd.DatetimeIndex([nxt.replace(second=0, microsecond=0) - timedelta(minutes=1)]))
        b2 = pd.concat([b, up]); b2.attrs.update(b.attrs)
        saved_replay = T.replay_bars
        T.replay_bars = lambda pp, bb, since, cutoff: up
        try:
            T.manage_open(con3, {"TST.DE": b2}, {}, stops_only=True)
        finally:
            T.replay_bars = saved_replay
        check(C.positions(con3) == [], "short stop hit when the bar High reaches the stop")
        last = con3.execute("SELECT side, price_local, net_pnl_eur FROM trades ORDER BY id DESC LIMIT 1").fetchone()
        check(last[0] == "COVER" and last[1] >= p["stop_local"] and last[2] < 0, f"stop closes with a COVER at/above the stop, net loss ({tuple(last)})")
    finally:
        C.CFG["allow_short"] = SHORT_DEFAULT
        T.now, T.session_times, T.today_session, T.quote_ok = saved["now"], saved["session_times"], saved["today_session"], saved["quote_ok"]
        T.news_signal, T.macro_signal, CA.analyze, CA.record, T.atr = saved["news"], saved["macro"], saved["analyze"], saved["record"], saved["atr"]


def test_shadow_orb_short_and_eod():
    import shadow as SH
    day = C.today()
    b, wall = _bars_breakdown(day)
    sess = b[b.index >= datetime(day.year, day.month, day.day, 9, 0, tzinfo=ROME)]
    saved = SH.session_times, SH.atr
    try:
        SH.session_times = lambda region, d=None: C.session_times(region, day)
        SH.atr = lambda bb, n=14: pd.Series([0.8] * len(bb), index=bb.index)
        sig = SH.orb_short(b, sess, "EU")
        check(sig is not None and sig[1] > sig[0] > sig[2], f"shadow orb_short fires with stop above / target below ({sig})")
        check(SH.orb(b, sess, "EU") is None, "long orb does not fire on the breakdown")
    finally:
        SH.session_times, SH.atr = saved
    src = open(SH.__file__).read()
    check('[(i, "V0_SHORT") for i in static]' in src, "V0_SHORT planned on the static watchlist")
    import debate
    check("V0_SHORT" not in debate.STRATS, "V0_SHORT does not trigger LLM debate calls")
    # eod replay of a short to target
    o = datetime(day.year, day.month, day.day, 10, 0, tzinfo=ROME)
    idx = pd.date_range(o, periods=24, freq="5min")
    c = np.linspace(100, 96, len(idx))
    bb = pd.DataFrame({"Open": c, "High": c + 0.05, "Low": c - 0.05, "Close": c, "Volume": 1000.0}, index=idx)
    row = dict(day=day.isoformat(), ts=idx[0].isoformat(), strategy="V0_SHORT", ticker="SHT.DE", region="EU", currency="EUR",
               price=100.0, entry=99.95, stop=101.45, target=96.95, qty=3.0, qty_diag=3.0, chart_score=-40,
               chart_verdict="APPROVE", approved=True, bar=str(idx[0]), info="test", side="short")
    SH.append(SH.SIG, row)
    saved_ib = SH.intraday_bars
    SH.intraday_bars = lambda tick, *a, **k: {"SHT.DE": bb}
    try:
        SH.eod(dry=False)
    finally:
        SH.intraday_bars = saved_ib
    tl = [r for r in log_rows() if r.get("strategy_id") == "V0_SHORT"]
    check(len(tl) == 1 and tl[0]["side"] == "short" and tl[0]["exit_reason"] == "target" and tl[0]["gross_pnl_eur"] > 0,
          f"eod replays the short to target with a positive gross ({tl[:1]})")
    if tl:
        check(abs(tl[0]["gross_pnl_eur"] - 3.0 * (99.95 - tl[0]["exit_price"])) < 1e-3 and tl[0]["exit_price"] <= 96.95 and tl[0]["mfe_eur"] > 0 and tl[0]["mae_eur"] <= 0,
              "short shadow gross = qty*(entry-exit), MFE/MAE signs")
    md = open(os.path.join(os.environ["PT_REPORTS"], f"shadow_{day:%Y-%m-%d}.md")).read()
    check("## Lato SHORT V0_SHORT" in md, "21:56 report has the V0_SHORT section")


SHORT_DEFAULT = C.CFG.get("allow_short")

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception as e:
                import traceback; traceback.print_exc()
                failed += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
