#!/usr/bin/env python3
"""One intraday decision pass (PAPER). Safe to run every 5-15 min from a scheduler.
Rules: long-only opening-range breakout confirmed by VWAP + momentum, ATR stop, 2R target,
breakeven after +1R, one entry per ticker per day, chart-analyst APPROVE required for every buy,
chart-analyst verdict checked before every discretionary sell, time-based flatten. See README."""
import math, sys
from datetime import timedelta
from common import *
import logging; logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import chart_analysis as CA
from news import news_signal, macro_signal

S = "trade"

def manage_open(con, bars, daily, stops_only=False, catchup=False):
    """Replay every bar since the last check to simulate resting stop / take-profit orders.
    Bars: 1-min LS bars from bars.sqlite (finest), else yfinance 1m, else the 5-min bars, plus the
    live quote (Low = bid) - see common.replay_bars. A box pause therefore never skips a stop.
    Conservative: within one bar the stop is tested before the target; a stop fills at the stop
    or at the bar open if the bar gapped through it, minus half the live spread, minus slippage.
    Bars after the position's cutoff (21:50 of its entry day) are ignored.
    stops_only=True (position-watch job): only stops, targets and breakeven - no chart exits."""
    for p in positions(con):
        b = bars.get(p["ticker"])
        if b is None or b.empty:
            log(f"WARN no data for open position {p['ticker']}", S); continue
        since, cutoff = watch_checkpoint(con, p), position_cutoff(p)
        new = replay_bars(p, b, since, cutoff)
        stop, target, entry = p["stop_local"], p["target_local"], p["entry_local"]
        r = entry - p["initial_stop_local"]
        fx = eurusd() if p["currency"] == "USD" else 1.0
        be = entry + (2 * CFG["fee_per_order"] * fx) / p["qty"]  # breakeven incl. both fees
        hs = half_spread(b)
        done = False
        tag = " [recupero pausa]" if catchup else ""
        for ts, bar in new.iterrows():
            if bar["Low"] <= stop:
                px = min(stop, bar["Open"]) - (hs if bar.get("src") != "quote" else 0.0)
                a = CA.analyze(p["ticker"], "sell", b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
                fill, pnl = close_position(con, p, px, f"stop {stop:.4f} colpito alle {ts:%H:%M}{tag}", chart=a["chart"])
                log(f"SELL {p['ticker']} @ {fill:.4f} STOP ({bar.get('src')} bar {ts:%H:%M}) P&L {pnl:+.2f} EUR", S)
                if catchup: gap_log(f"CATCHUP-STOP {p['ticker']} stop {stop:.4f} bar {ts:%H:%M} fill {fill:.4f} netto {pnl:+.2f} EUR")
                done = True; break
            if bar["High"] >= target:
                px = max(target, bar["Open"])
                a = CA.analyze(p["ticker"], "sell", b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
                fill, pnl = close_position(con, p, px, f"take profit {target:.4f} alle {ts:%H:%M}{tag}", apply_slippage=False, chart=a["chart"])
                log(f"SELL {p['ticker']} @ {fill:.4f} TARGET ({bar.get('src')} bar {ts:%H:%M}) P&L {pnl:+.2f} EUR", S)
                if catchup: gap_log(f"CATCHUP-TARGET {p['ticker']} target {target:.4f} bar {ts:%H:%M} fill {fill:.4f} netto {pnl:+.2f} EUR")
                done = True; break
            if bar["High"] >= entry + CFG["breakeven_at_r"] * r and stop < be:
                stop = be   # applies from the next bar (conservative)
                log(f"{p['ticker']}: +{CFG['breakeven_at_r']}R reached ({ts:%H:%M}), stop moved to breakeven {be:.4f}", S)
        if done:
            continue
        # checkpoint = start of the last replayed bar (it may still be forming, so it is re-checked next time)
        ck = new.index[-1] if len(new) else since
        def save():
            con.execute("UPDATE positions SET stop_local=? WHERE ticker=?", (stop, p["ticker"]))
            set_watch_checkpoint(con, p["ticker"], ck)
            con.commit()
        if stops_only:
            log(f"{p['ticker']}: watch stop {stop:.4f} target {target:.4f} last {float(b['Close'].iloc[-1]):.4f} "
                f"({len(new)} barre da {since:%H:%M})", S)
            save(); continue
        # discretionary sell decision: ask the chart analyst (no PNG unless we act)
        ok, age = quote_ok(b, p["region"])
        a = CA.analyze(p["ticker"], "sell", b, daily.get(p["ticker"]), stop, target, save_chart=False)
        if ok and a["verdict"] == "EXIT":
            a = CA.analyze(p["ticker"], "sell", b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
            fill, pnl = close_position(con, p, float(b["Close"].iloc[-1]),
                                       f"uscita anticipata: grafico ribassista (score {a['score']})", chart=a["chart"],
                                       quote_bars=b)
            log(f"SELL {p['ticker']} @ {fill:.4f} CHART-EXIT score {a['score']} netto {pnl:+.2f} EUR", S); continue
        log(f"{p['ticker']}: analista grafico {a['verdict']} (score {a['score']}), stop {stop:.4f} target {target:.4f}", S)
        save()

def try_entry(con, it, b, eq, cash, n_open, daily):
    t, region = it["ticker"], it["region"]
    o, c, last_entry = session_times(region)
    n = now()
    if not (o + timedelta(minutes=CFG["or_minutes"]) <= n <= last_entry):
        return f"fuori finestra ingressi ({o + timedelta(minutes=CFG['or_minutes']):%H:%M}-{last_entry:%H:%M})"
    sess = today_session(b, region)  # LS/TR window 07:30-22:00
    if len(sess) < 8:
        return "dati di oggi insufficienti (festivo/ritardo?)"
    ok, age = quote_ok(b, region)
    if not ok:
        return f"quotazione vecchia ({age:.0f} min, ritardo normale {feed_delay_min(b, region)} min): non opero"
    # Opening range is the first 30 min of the CASH session (EU 09:00, US 15:30), not LS pre-market.
    orb = sess[(sess.index >= o) & (sess.index < o + timedelta(minutes=CFG["or_minutes"]))]
    if len(orb) < 4:
        return "opening range incompleto"
    orh, orl = float(orb["High"].max()), float(orb["Low"].min())
    vw = float(vwap(sess).iloc[-1])
    a = float(atr(b).iloc[-1])
    close = float(sess["Close"].iloc[-1])
    mom = close - float(sess["Close"].iloc[-4])
    info = f"prezzo {close:.3f}, ORH {orh:.3f}, ORL {orl:.3f}, VWAP {vw:.3f}, ATR5m {a:.3f}"
    if close <= orh:   return "nessun breakout: " + info
    if close <= vw:    return "sotto VWAP: " + info
    if mom <= 0:       return "momentum 15m negativo: " + info
    if close > orh + CFG["max_extension_atr"] * a: return "troppo esteso, non inseguo: " + info
    stop = max(orl, close - CFG["atr_stop_mult"] * a)
    dist = close - stop
    dist = min(max(dist, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    stop = close - dist
    target = close + CFG["reward_r"] * dist
    ccy = quote_currency(b, t)
    raw_px = b.attrs.get("ask") or close
    px_eur = to_eur(raw_px if b.attrs.get("ask") else close * (1 + CFG["slippage"]), ccy)
    dist_eur = to_eur(dist, ccy)
    fees = 2 * CFG["fee_per_order"]
    q_risk = (CFG["risk_per_trade"] * eq - fees) / dist_eur
    q_cap = CFG["max_position_pct"] * eq / px_eur
    q_cash = (cash - CFG["fee_per_order"]) / px_eur
    qty = max(0.0, min(q_risk, q_cap, q_cash))
    qty = math.floor(qty * 1e4) / 1e4 if CFG["fractional"] else math.floor(qty)
    value = qty * px_eur
    if value < CFG["min_position_eur"]:
        return f"posizione troppo piccola ({value:.0f} EUR) per giustificare le commissioni"
    reward = qty * CFG["reward_r"] * dist_eur
    if reward < CFG["min_reward_vs_fees"] * fees:
        return f"guadagno atteso {reward:.2f} EUR < {CFG['min_reward_vs_fees']:.0f}x commissioni"
    ns, ms = news_signal(t, 6), macro_signal(6)
    if ns["score"] <= -0.4:
        return f"segnale ORB bloccato da notizie negative ({ns['score']:+.2f}): {ns['top']}"
    if ms["score"] <= -0.4 and ms["count"] >= 10:
        return f"segnale ORB bloccato: clima macro risk-off ({ms['score']:+.2f})"
    a = CA.analyze(t, "buy", b, daily.get(t), stop, target)
    if a["verdict"] != "APPROVE":
        CA.record(con, a, 0)
        return f"segnale ORB ma analista grafico RIFIUTA (score {a['score']}): " + "; ".join(a["reasons"][:4])
    CA.record(con, a, 1)
    why = f"ORB long: {info}; stop {stop:.3f}, target {target:.3f} (2R); grafico score {a['score']}; news {ns['score']:+.2f}"
    fill = open_position(con, t, qty, close, stop, target, qty * dist_eur + fees, why, str(sess.index[-1]),
                         setup="ORB+VWAP", chart_score=a["score"], chart=a["chart"], currency=ccy, quote_bars=b)
    log(f"BUY {qty:.4f} {t} @ {fill:.4f} {ccy} (~{value:.2f} EUR) stop {stop:.4f} target {target:.4f} | {info}", S)
    return "ENTRATO"

def manage_only(catchup=False):
    """Light position-watch pass: stops/targets only, no entries or chart exits. Cheap when flat.
    catchup=True (scheduler, after a box pause): also runs outside the TR window / on weekends,
    replays bars only up to each position's cutoff, and closes stale positions (previous day or
    after 22:00) at the last price inside the window, flagged in the ledger and logs/gaps.log."""
    global S
    S = "catchup" if catchup else "watch"
    if not catchup:
        if is_weekend():
            return
        t0, t1 = TR_WINDOW
        if not (t0 <= now().time() <= t1):
            return
    with Lock():
        con = db()
        pos = positions(con)
        if not pos:
            if catchup: log("recupero: nessuna posizione aperta", S)
            return
        tickers = [p["ticker"] for p in pos]
        bars = intraday_bars(tickers)
        daily = daily_bars(tickers, "6mo")
        manage_open(con, bars, daily, stops_only=True, catchup=catchup)
        stale = [p for p in positions(con) if is_stale(p)]
        if stale:
            late_flatten(con, stale, bars, S)
        n = now()
        if TR_WINDOW[0] <= n.time() < TR_WINDOW[1] and not is_weekend():
            for region in ("EU", "US"):
                if n >= flatten_time(region):
                    flatten(con, [region], f"chiusura fine giornata {region}", S)
        if not is_weekend():
            ensure_day(con)
        prices = {t: (b.attrs.get("last_mid", float(b["Close"].iloc[-1])), b.attrs.get("last_ts", b.index[-1]))
                  for t, b in bars.items() if len(b)}
        eq, cash, mv = equity(con, prices)
        log(f"{S} {len(pos)} pos, equity {eq:.2f} EUR", S)

def main():
    if "--manage" in sys.argv:
        manage_only(catchup="--catchup" in sys.argv); return
    if is_weekend():
        log("weekend: nothing to do", S); return
    t0, t1 = TR_WINDOW
    if not (t0 <= now().time() <= t1):
        log(f"fuori orario Trade Republic ({t0:%H:%M}-{t1:%H:%M}): nulla da fare", S); return
    with Lock():
        con = db()
        wl = load_watchlist()
        if wl is None:
            log("no watchlist for today -> running scan", S)
            import scan; Lock.__enter__ = lambda self: self; Lock.__exit__ = lambda self, *a: None
            scan.main(); wl = load_watchlist()
            if wl is None: return
        items = wl["items"]
        held = [p["ticker"] for p in positions(con)]
        tickers = sorted(set([i["ticker"] for i in items] + held))
        bars = intraday_bars(tickers)
        daily = daily_bars(tickers, "6mo")
        prices = {t: (float(b["Close"].iloc[-1]), b.index[-1]) for t, b in bars.items()}
        day = ensure_day(con)
        manage_open(con, bars, daily)
        stale = [p for p in positions(con) if is_stale(p)]   # e.g. left open by a box pause yesterday
        if stale:
            late_flatten(con, stale, bars, S)
        n = now()
        for region in ("EU", "US"):
            if n >= flatten_time(region):
                flatten(con, [region], f"chiusura fine giornata {region}", S)
        eq, cash, _ = equity(con, prices)
        pnl_pct = eq / day["start_equity"] - 1
        if not day["halted"] and pnl_pct <= CFG["daily_loss_limit"]:
            log(f"DAILY LOSS LIMIT hit ({pnl_pct:+.2%}) -> flatten all, halt for today", S)
            flatten(con, ["EU", "US"], "limite perdita giornaliera -3%", S)
            con.execute("UPDATE days SET halted=1 WHERE day=?", (day["day"],)); con.commit()
            day["halted"] = 1
        if day["halted"]:
            log("trading halted for today", S); return
        traded = {r[0] for r in con.execute("SELECT DISTINCT ticker FROM trades WHERE day=? AND side='BUY'", (day["day"],))}
        for it in items:
            eq, cash, _ = equity(con, prices)
            n_open = len(positions(con))
            t = it["ticker"]
            if t in [p["ticker"] for p in positions(con)]:
                log(f"{t}: posizione aperta, gestita", S); continue
            if n_open >= CFG["max_positions"]:
                log(f"{t}: max {CFG['max_positions']} posizioni aperte", S); continue
            if t in traded:
                log(f"{t}: già tradato oggi (1 ingresso/giorno)", S); continue
            b = bars.get(t)
            if b is None or b.empty:
                log(f"{t}: nessun dato", S); continue
            log(f"{t}: {try_entry(con, it, b, eq, cash, n_open, daily)}", S)
        eq, cash, mv = equity(con, prices)
        log(f"equity {eq:.2f} EUR (cash {cash:.2f}, posizioni {sum(mv.values()):.2f}), oggi {eq/day['start_equity']-1:+.2%}", S)

if __name__ == "__main__":
    main()
