#!/usr/bin/env python3
"""Append-only log of every closed PAPER trade (production and shadow).

Written to data/trade_log.jsonl (override with PT_TRADE_LOG). The file lives on the
`state` branch (data/*.jsonl), not on main. One JSON object per line; never rewritten.

Fields (all monetary values in EUR unless noted):
  source          "production" | "shadow"
  strategy_id     e.g. ORB+VWAP, V0_LOOSE, REBOUND, NEWS_LLM
  symbol, side    ticker and "long"/"short"
  qty
  entry_ts, entry_price   entry_price in the instrument's currency
  exit_ts, exit_price
  currency
  entry_reason, exit_reason
  mae_price, mfe_price    worst / best traded price while the position was open
  mae_eur, mfe_eur        unrealized gross P&L at those prices (before the exit fee)
  slippage_eur            modeled 0.05% adverse slippage on entry and exit fills
  fees                    round-trip commissions (1 € + 1 €)
  gross_pnl_eur           proceeds − cost, before fees and tax
  pnl_after_fees_eur      gross − fees (the tax base)
  tax_eur                 26% Italian tax on gains after fees, minusvalenze first
  net_pnl_eur             after fees and tax
  loss_credit_used        minusvalenze applied to this gain (production)
  excursion_incomplete    True if MAE/MFE could not be tracked bar-by-bar
"""
from __future__ import annotations

import json
import os
from datetime import datetime

from common import BASE, CFG, DATA, TAX_RATE, now

LOG = os.environ.get("PT_TRADE_LOG", os.path.join(DATA, "trade_log.jsonl"))


def log_path():
    return os.environ.get("PT_TRADE_LOG", os.path.join(DATA, "trade_log.jsonl"))


def update_excursion(mae, mfe, entry, low, high, side="long"):
    """Running min/max price. Returns (mae_price, mfe_price)."""
    entry = float(entry)
    mae = entry if mae is None else float(mae)
    mfe = entry if mfe is None else float(mfe)
    low, high = float(low), float(high)
    if str(side).lower() == "short":
        return max(mae, high, entry), min(mfe, low, entry)
    return min(mae, low, entry), max(mfe, high, entry)


def excursions_from_bars(entry, bars, side="long"):
    """MAE/MFE prices from a High/Low bar frame after entry (inclusive of those bars)."""
    mae = mfe = float(entry)
    if bars is None or len(bars) == 0:
        return mae, mfe, True
    for _, bar in bars.iterrows():
        mae, mfe = update_excursion(mae, mfe, entry, bar["Low"], bar["High"], side)
    return mae, mfe, False


def tax_after_fees(pnl_after_fees, credit=0.0):
    """26% on gains after fees, offset by available minusvalenze. Losses are not taxed.
    Returns (tax, credit_used, credit_remaining_after). Does not write the ledger."""
    pnl = float(pnl_after_fees)
    credit = max(0.0, float(credit or 0.0))
    if pnl < 0:
        return 0.0, 0.0, credit - pnl
    used = min(credit, pnl)
    return round((pnl - used) * TAX_RATE, 2), used, credit - used


def slippage_eur(qty, entry_price, exit_price, fx=1.0, rate=None):
    """Modeled adverse slippage in EUR on both fills (CFG 5 bp unless overridden)."""
    rate = CFG["slippage"] if rate is None else rate
    fx = fx or 1.0
    return float(qty) * (abs(entry_price) + abs(exit_price)) * rate / fx


def gross_at(qty, price, entry_eur, fx=1.0, side="long"):
    """Unrealized gross P&L in EUR at `price` (instrument currency)."""
    fx = fx or 1.0
    sgn = -1 if str(side).lower() == "short" else 1
    return float(qty) * (float(price) / fx - float(entry_eur)) * sgn


def record(row):
    """Append one closed-trade record. Never overwrites existing lines."""
    path = log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out = dict(row)
    out.setdefault("ts_logged", now().isoformat(timespec="seconds"))
    with open(path, "a") as f:
        f.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
    return out


def record_close(source, strategy_id, symbol, side, qty, entry_ts, entry_price,
                 exit_ts, exit_price, entry_reason, exit_reason, fees, gross_pnl_eur,
                 tax_eur, net_pnl_eur, currency="EUR", fx=1.0, entry_eur=None,
                 mae_price=None, mfe_price=None, loss_credit_used=0.0,
                 excursion_incomplete=False, **extra):
    """Build and append a standardized closed-trade line."""
    qty = float(qty)
    fx = float(fx or 1.0)
    side = "short" if str(side).lower() in ("short", "sell", "-1") else "long"
    if entry_eur is None:
        entry_eur = float(entry_price) / fx
    if mae_price is None or mfe_price is None:
        lo, hi = min(entry_price, exit_price), max(entry_price, exit_price)
        mae_price = mae_price if mae_price is not None else (hi if side == "short" else lo)
        mfe_price = mfe_price if mfe_price is not None else (lo if side == "short" else hi)
        excursion_incomplete = True
    pnl_after_fees = float(gross_pnl_eur) - float(fees)
    rec = dict(
        source=source,
        strategy_id=strategy_id or "unknown",
        symbol=symbol,
        side=side,
        qty=round(qty, 6),
        entry_ts=str(entry_ts),
        entry_price=round(float(entry_price), 6),
        exit_ts=str(exit_ts),
        exit_price=round(float(exit_price), 6),
        currency=currency or "EUR",
        entry_reason=entry_reason or "",
        exit_reason=exit_reason or "",
        mae_price=round(float(mae_price), 6),
        mfe_price=round(float(mfe_price), 6),
        mae_eur=round(gross_at(qty, mae_price, entry_eur, fx, side), 4),
        mfe_eur=round(gross_at(qty, mfe_price, entry_eur, fx, side), 4),
        slippage_eur=round(slippage_eur(qty, entry_price, exit_price, fx), 4),
        fees=round(float(fees), 4),
        gross_pnl_eur=round(float(gross_pnl_eur), 4),
        pnl_after_fees_eur=round(pnl_after_fees, 4),
        tax_eur=round(float(tax_eur), 4),
        net_pnl_eur=round(float(net_pnl_eur), 4),
        loss_credit_used=round(float(loss_credit_used or 0.0), 4),
        excursion_incomplete=bool(excursion_incomplete),
    )
    rec.update(extra)
    return record(rec)


def from_position(p, fill, reason, gross, fees, tax, net, used=0.0, source="production",
                  exit_ts=None, fx=None):
    """Log a production (or production-like) close from a ledger position dict."""
    side = p.get("side") or "long"
    fx = fx if fx is not None else (p.get("entry_fx") or 1.0)
    mae, mfe = p.get("mae_local"), p.get("mfe_local")
    incomplete = mae is None or mfe is None
    return record_close(
        source=source,
        strategy_id=p.get("setup") or "ORB+VWAP",
        symbol=p["ticker"],
        side=side,
        qty=p["qty"],
        entry_ts=p.get("entry_ts"),
        entry_price=p.get("entry_local"),
        exit_ts=exit_ts or now().isoformat(timespec="seconds"),
        exit_price=fill,
        entry_reason=p.get("rationale") or "",
        exit_reason=reason,
        fees=fees,
        gross_pnl_eur=gross,
        tax_eur=tax,
        net_pnl_eur=net,
        currency=p.get("currency") or "EUR",
        fx=fx,
        entry_eur=p.get("entry_eur"),
        mae_price=mae,
        mfe_price=mfe,
        loss_credit_used=used,
        excursion_incomplete=incomplete,
    )
