#!/usr/bin/env python3
"""End-of-day flatten (PAPER). Idempotent; safe to run repeatedly.
Positions that should already be flat (box paused past 22:00 or overnight) are replayed and closed
at the last price inside the window, flagged "chiusura in ritardo" (see common.late_flatten).
Default (time-aware): everything closed from 21:50 Rome (LS quotes stay live after the EU cash close, so we no longer flatten EU at 17:25).
  --all     close every position now regardless of time
  --region EU|US   close only that region now"""
import sys
from common import *
import logging; logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import chart_analysis as CA

def main():
    S = "close_all"
    with Lock():
        con = db()
        if not positions(con):
            log("nessuna posizione aperta", S); return
        # Box-pause safety: positions that should already be flat (previous day, or now past 22:00)
        # get their missed stops/targets replayed and are closed at the last price inside the window.
        stale = [p for p in positions(con) if is_stale(p)]
        if stale:
            import trade
            tickers = [p["ticker"] for p in stale]
            bars = intraday_bars(tickers)
            trade.S = S
            trade.manage_open(con, bars, daily_bars(tickers, "6mo"), stops_only=True, catchup=True)
            still = [p for p in positions(con) if is_stale(p)]
            done = late_flatten(con, still, bars, S)
            log(f"chiusura in ritardo: {done}", S)
            if not positions(con):
                log(f"equity {equity(con)[0]:.2f} EUR", S); return
        if "--all" in sys.argv:
            which = ["EU", "US"]
        elif "--region" in sys.argv:
            which = [sys.argv[sys.argv.index("--region") + 1].upper()]
        else:
            n = now(); which = [r for r in ("EU", "US") if n >= flatten_time(r)]
        if not which:
            log("troppo presto per la chiusura automatica (tutto alle 21:50); usa --all per forzare", S); return
        for p in positions(con):   # chart snapshot of every forced exit, for the report
            if p["region"] in which:
                try: CA.record(con, CA.analyze(p["ticker"], "sell"), 1)
                except Exception as e: log(f"chart skip {p['ticker']}: {e}", S)
        done = flatten(con, which, "chiusura fine giornata", S)
        eq = equity(con)[0]
        log(f"chiuse {done}; equity {eq:.2f} EUR", S)

if __name__ == "__main__":
    main()
