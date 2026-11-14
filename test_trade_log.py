#!/usr/bin/env python3
"""Unit tests for the append-only closed-trade log (no live ledger, no market data)."""
import json, os, tempfile, math
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

ROME = ZoneInfo("Europe/Rome")

def _env(td):
    os.environ["PT_DB"] = os.path.join(td, "ledger.sqlite")
    os.environ["PT_LOCK"] = os.path.join(td, ".lock")
    os.environ["PT_TRADE_LOG"] = os.path.join(td, "trade_log.jsonl")
    os.environ["PT_LOGS"] = os.path.join(td, "logs")
    os.environ["PT_REPORTS"] = os.path.join(td, "reports")
    os.makedirs(os.environ["PT_LOGS"], exist_ok=True)
    os.makedirs(os.environ["PT_REPORTS"], exist_ok=True)

# Isolate env before importing project modules
TD = tempfile.mkdtemp(prefix="pt-tradelog-")
_env(TD)

import common as C
import trade_log as TL

failed = 0

def check(cond, name):
    global failed
    if cond:
        print(f"ok  {name}")
    else:
        failed += 1
        print(f"FAIL {name}")


def read_log():
    path = TL.log_path()
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def test_update_excursion_long():
    mae, mfe = TL.update_excursion(None, None, 100, 99, 101, "long")
    mae, mfe = TL.update_excursion(mae, mfe, 100, 98.5, 100.2, "long")
    mae, mfe = TL.update_excursion(mae, mfe, 100, 99.0, 103.0, "long")
    check(mae == 98.5 and mfe == 103.0, "long MAE is the lowest low, MFE the highest high")


def test_update_excursion_short():
    mae, mfe = TL.update_excursion(None, None, 100, 99, 101, "short")
    mae, mfe = TL.update_excursion(mae, mfe, 100, 97, 102, "short")
    check(mae == 102 and mfe == 97, "short MAE is the highest high, MFE the lowest low")


def test_tax_after_fees():
    tax, used, cred = TL.tax_after_fees(10.0, credit=0)
    check(tax == 2.60 and used == 0, f"26% of 10 € gain after fees is 2.60 (got tax={tax} used={used})")
    tax, used, cred = TL.tax_after_fees(10.0, credit=4.0)
    check(tax == 1.56 and used == 4.0 and abs(cred) < 1e-9, f"gain offset by 4 € credit: tax 1.56 (got {tax}, {used}, {cred})")
    tax, used, cred = TL.tax_after_fees(-7.0, credit=1.0)
    check(tax == 0.0 and used == 0.0 and abs(cred - 8.0) < 1e-9, f"loss is not taxed and adds to credit (got {tax}, {used}, {cred})")


def test_slippage_and_gross():
    slip = TL.slippage_eur(10, 100, 102, fx=1.0, rate=0.0005)
    check(abs(slip - 10 * 202 * 0.0005) < 1e-9, "slippage is 5 bp of both fills")
    g = TL.gross_at(10, 90, 100, fx=1.0, side="long")
    check(g == -100.0, "long MAE gross at 90 vs entry 100")
    g = TL.gross_at(10, 90, 100, fx=1.0, side="short")
    check(g == 100.0, "short MFE gross at 90 vs entry 100")


def test_append_only_and_fields():
    open(TL.log_path(), "w").close()  # start empty for this test
    TL.record_close(
        source="production", strategy_id="ORB+VWAP", symbol="SAP.DE", side="long",
        qty=5, entry_ts="2026-11-16T10:00:00+01:00", entry_price=100.0,
        exit_ts="2026-11-16T15:00:00+01:00", exit_price=104.0,
        entry_reason="ORB long", exit_reason="take profit",
        fees=2.0, gross_pnl_eur=20.0, tax_eur=4.68, net_pnl_eur=13.32,
        currency="EUR", mae_price=99.0, mfe_price=104.0,
    )
    TL.record_close(
        source="shadow", strategy_id="V0_LOOSE", symbol="IFX.DE", side="long",
        qty=8, entry_ts="2026-11-16T11:00:00+01:00", entry_price=30.0,
        exit_ts="2026-11-16T16:00:00+01:00", exit_price=29.0,
        entry_reason="loose ORB", exit_reason="stop",
        fees=2.0, gross_pnl_eur=-8.0, tax_eur=0.0, net_pnl_eur=-10.0,
        currency="EUR", mae_price=28.5, mfe_price=30.5,
    )
    rows = read_log()
    check(len(rows) == 2, f"append-only: two closes -> two lines (got {len(rows)})")
    a, b = rows
    needed = {"source", "strategy_id", "symbol", "side", "qty", "entry_ts", "entry_price",
              "exit_ts", "exit_price", "entry_reason", "exit_reason", "mae_price", "mfe_price",
              "mae_eur", "mfe_eur", "slippage_eur", "fees", "gross_pnl_eur", "pnl_after_fees_eur",
              "tax_eur", "net_pnl_eur"}
    check(needed <= set(a) and needed <= set(b), "required fields present")
    check(a["pnl_after_fees_eur"] == 18.0 and a["tax_eur"] == 4.68 and a["net_pnl_eur"] == 13.32,
          "tax is applied on gains after both fees (20-2=18, 26%=4.68, net=13.32)")
    check(b["tax_eur"] == 0.0 and b["net_pnl_eur"] == -10.0, "losses are not taxed")
    check(a["mae_eur"] == -5.0 and a["mfe_eur"] == 20.0, f"MAE/MFE in EUR (got {a['mae_eur']}, {a['mfe_eur']})")
    # rewrite protection: file still has exactly two lines after another read
    check(len(read_log()) == 2, "existing lines are not rewritten")


def test_production_close_writes_log():
    # fresh db + log
    for fn in ("ledger.sqlite", "trade_log.jsonl"):
        fp = os.path.join(TD, fn)
        if os.path.exists(fp):
            os.remove(fp)
    C.DB = os.environ["PT_DB"]
    C.LOCK_PATH = os.environ["PT_LOCK"]
    # reopen via db()
    con = C.db()
    # Freeze FX and use a EUR name so eurusd is not needed... open_position calls eurusd only for USD.
    # Use a universe ticker if possible; meta() falls back to EUR.
    ticker = "TEST.DE"
    # monkeypatch meta
    orig_meta = C.meta
    C.meta = lambda t: dict(name="Test", ticker=t, region="EU", currency="EUR", isin="")
    fill = C.open_position(con, ticker, 10.0, 50.0, stop=49.0, target=52.0, risk_eur=12.0,
                           rationale="unit test entry", entry_bar="2026-11-16 10:00",
                           setup="ORB+VWAP")
    # entry fill includes 5 bp slippage on a mid of 50
    check(abs(fill - 50.0 * (1 + C.CFG["slippage"])) < 1e-9, f"entry fill includes slippage (got {fill})")
    pos = C.positions(con)[0]
    check(pos["mae_local"] == fill and pos["mfe_local"] == fill, "new position MAE/MFE start at entry fill")
    # simulate adverse then favorable move
    import trade_log as TL2
    mae, mfe = TL2.update_excursion(pos["mae_local"], pos["mfe_local"], pos["entry_local"], 49.2, 50.4)
    pos["mae_local"], pos["mfe_local"] = mae, mfe
    exit_px = 52.0
    fill2, net = C.close_position(con, pos, exit_px, "take profit 52.0000 alle 15:00", apply_slippage=False)
    rows = [r for r in read_log() if r["symbol"] == ticker and r["source"] == "production"]
    check(len(rows) == 1, f"production close writes exactly one log line (got {len(rows)})")
    r = rows[0]
    check(r["strategy_id"] == "ORB+VWAP" and r["side"] == "long" and r["exit_reason"].startswith("take profit"),
          "strategy, side and exit reason recorded")
    check(r["fees"] == 2.0, f"round-trip fees are 2 € (got {r['fees']})")
    # gross = qty*(exit - entry_eur); entry_eur is the slipped fill
    expected_gross = 10.0 * (fill2 - fill)
    check(abs(r["gross_pnl_eur"] - expected_gross) < 1e-6, f"gross matches qty*(exit-entry) (got {r['gross_pnl_eur']} vs {expected_gross})")
    expected_pnl = expected_gross - 2.0
    check(abs(r["pnl_after_fees_eur"] - expected_pnl) < 1e-6, "pnl_after_fees = gross - 2 €")
    if expected_pnl > 0:
        check(abs(r["tax_eur"] - round(expected_pnl * 0.26, 2)) < 1e-9, f"tax 26% after fees (got {r['tax_eur']})")
        check(abs(r["net_pnl_eur"] - (expected_pnl - r["tax_eur"])) < 1e-6, "net = after fees minus tax")
    check(abs(r["mae_price"] - 49.2) < 1e-9 and abs(r["mfe_price"] - 50.4) < 1e-9,
          f"MAE/MFE prices persisted through close (got {r['mae_price']}, {r['mfe_price']})")
    check(C.positions(con) == [], "position is closed in the ledger")
    C.meta = orig_meta
    con.close()


def test_excursions_from_bars():
    idx = pd.date_range("2026-11-16 10:05", periods=3, freq="5min", tz=ROME)
    bars = pd.DataFrame({"High": [101, 103, 102], "Low": [99.5, 100.0, 98.0], "Close": [100.5, 102, 99]}, index=idx)
    mae, mfe, inc = TL.excursions_from_bars(100.0, bars, "long")
    check(not inc and mae == 98.0 and mfe == 103.0, f"excursions_from_bars long (got mae={mae} mfe={mfe} inc={inc})")


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
