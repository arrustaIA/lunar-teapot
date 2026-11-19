#!/usr/bin/env python3
"""One intraday decision pass (PAPER). Safe to run every 5-15 min from a scheduler.
Rules: opening-range breakout (long) or breakdown (short, mirror rules, from 17/11/2026) confirmed by VWAP +
momentum + EMA9 vs EMA21 (5m), ATR stop, 2R target,
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
        short = is_short(p)
        sg = -1 if short else 1                      # +1 long, -1 short
        r = sg * (entry - p["initial_stop_local"])   # 1R in price, positive
        fx = eurusd() if p["currency"] == "USD" else 1.0
        be = entry + sg * (2 * CFG["fee_per_order"] * fx) / p["qty"]  # breakeven incl. both fees
        hs = half_spread(b)
        done = False
        tag = " [recupero pausa]" if catchup else ""
        xside = "cover" if short else "sell"
        xlab = "COVER" if short else "SELL"
        import trade_log as TL
        for ts, bar in new.iterrows():
            mae, mfe = TL.update_excursion(p.get("mae_local"), p.get("mfe_local"), entry, bar["Low"], bar["High"], p["side"])
            p["mae_local"], p["mfe_local"] = mae, mfe
            hit_stop = bar["High"] >= stop if short else bar["Low"] <= stop
            if hit_stop:
                adj = hs if bar.get("src") != "quote" else 0.0
                px = max(stop, bar["Open"]) + adj if short else min(stop, bar["Open"]) - adj
                a = CA.analyze(p["ticker"], xside, b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
                fill, pnl = close_position(con, p, px, f"stop {stop:.4f} colpito alle {ts:%H:%M}{tag}", chart=a["chart"])
                log(f"{xlab} {p['ticker']} @ {fill:.4f} STOP ({bar.get('src')} bar {ts:%H:%M}) P&L {pnl:+.2f} EUR", S)
                if catchup: gap_log(f"CATCHUP-STOP {p['ticker']} stop {stop:.4f} bar {ts:%H:%M} fill {fill:.4f} netto {pnl:+.2f} EUR")
                done = True; break
            hit_tgt = bar["Low"] <= target if short else bar["High"] >= target
            if hit_tgt:
                px = min(target, bar["Open"]) if short else max(target, bar["Open"])
                a = CA.analyze(p["ticker"], xside, b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
                fill, pnl = close_position(con, p, px, f"take profit {target:.4f} alle {ts:%H:%M}{tag}", apply_slippage=False, chart=a["chart"])
                log(f"{xlab} {p['ticker']} @ {fill:.4f} TARGET ({bar.get('src')} bar {ts:%H:%M}) P&L {pnl:+.2f} EUR", S)
                if catchup: gap_log(f"CATCHUP-TARGET {p['ticker']} target {target:.4f} bar {ts:%H:%M} fill {fill:.4f} netto {pnl:+.2f} EUR")
                done = True; break
            reached_1r = (bar["Low"] <= entry - CFG["breakeven_at_r"] * r) if short else (bar["High"] >= entry + CFG["breakeven_at_r"] * r)
            if reached_1r and (stop > be if short else stop < be):
                stop = be   # applies from the next bar (conservative)
                log(f"{p['ticker']}: +{CFG['breakeven_at_r']}R reached ({ts:%H:%M}), stop moved to breakeven {be:.4f}", S)
        if done:
            continue
        # checkpoint = start of the last replayed bar (it may still be forming, so it is re-checked next time)
        ck = new.index[-1] if len(new) else since
        def save():
            con.execute("UPDATE positions SET stop_local=?, mae_local=?, mfe_local=? WHERE ticker=?",
                        (stop, p.get("mae_local"), p.get("mfe_local"), p["ticker"]))
            set_watch_checkpoint(con, p["ticker"], ck)
            con.commit()
        if stops_only:
            log(f"{p['ticker']}: watch stop {stop:.4f} target {target:.4f} last {float(b['Close'].iloc[-1]):.4f} "
                f"({len(new)} barre da {since:%H:%M})", S)
            save(); continue
        # discretionary sell decision: ask the chart analyst (no PNG unless we act)
        ok, age = quote_ok(b, p["region"])
        a = CA.analyze(p["ticker"], xside, b, daily.get(p["ticker"]), stop, target, save_chart=False)
        if ok and a["verdict"] == "EXIT" and CFG.get("chart_exit", True):
            a = CA.analyze(p["ticker"], xside, b, daily.get(p["ticker"]), stop, target); CA.record(con, a, 1)
            fill, pnl = close_position(con, p, float(b["Close"].iloc[-1]),
                                       f"uscita anticipata: grafico {'rialzista' if short else 'ribassista'} (score {a['score']})",
                                       chart=a["chart"], quote_bars=b)
            log(f"{xlab} {p['ticker']} @ {fill:.4f} CHART-EXIT score {a['score']} netto {pnl:+.2f} EUR", S); continue
        log(f"{p['ticker']}: analista grafico {a['verdict']} (score {a['score']}), stop {stop:.4f} target {target:.4f}", S)
        save()

def plan_entry(con, it, b, eq, cash, n_open, daily):
    """All entry checks; returns a reason string (no entry) or a plan dict for execute_entry."""
    t, region = it["ticker"], it["region"]
    o, c, last_entry = session_times(region)
    n = now()
    if not (o + timedelta(minutes=CFG["or_minutes"]) <= n <= last_entry):
        return f"fuori finestra ingressi ({o + timedelta(minutes=CFG['or_minutes']):%H:%M}-{last_entry:%H:%M})"
    us_delay = CFG.get("us_entry_delay_min")
    if region == "US" and us_delay is not None and n < o + timedelta(minutes=us_delay):
        return f"ingressi USA solo da {o + timedelta(minutes=us_delay):%H:%M} (us_entry_delay_min={us_delay})"
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
    if close > orh:
        side = "long"
    elif close < orl and CFG.get("allow_short"):
        side = "short"
    else:
        return ("nessun breakout né breakdown: " if CFG.get("allow_short") else "nessun breakout: ") + info
    if side == "long":
        if close <= vw:    return "sotto VWAP: " + info
        if mom <= 0 and CFG.get("mom_filter", True): return "momentum 15m negativo: " + info
        if close > orh + CFG["max_extension_atr"] * a: return "troppo esteso, non inseguo: " + info
    else:
        if close >= vw:    return "short: sopra VWAP: " + info
        if mom >= 0 and CFG.get("mom_filter", True): return "short: momentum 15m positivo: " + info
        if close < orl - CFG["max_extension_atr"] * a: return "short: troppo esteso, non inseguo: " + info
    ok_ema, e9, e21 = ema_aligned(b, side=side)
    if e9 == e9 and e21 == e21:
        info = info + f", EMA9 {e9:.3f}, EMA21 {e21:.3f}"
    if not ok_ema and CFG.get("ema_filter", True):
        rel = "sotto" if side == "short" else "sopra"
        detail = f"EMA9 {e9:.3f} non {rel} EMA21 {e21:.3f}" if e9 == e9 and e21 == e21 else "EMA non pronte"
        return ("short: " if side == "short" else "") + f"ema_misaligned: {detail}; " + info
    sg = 1 if side == "long" else -1
    if side == "long":
        stop = max(orl, close - CFG["atr_stop_mult"] * a)
        dist = close - stop
    else:
        stop = min(orh, close + CFG["atr_stop_mult"] * a)
        dist = stop - close
    dist = min(max(dist, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    stop = close - sg * dist
    target = close + sg * CFG["reward_r"] * dist
    ccy = quote_currency(b, t)
    q_attr = "ask" if side == "long" else "bid"
    raw_px = b.attrs.get(q_attr) or close
    px_eur = to_eur(raw_px if b.attrs.get(q_attr) else close * (1 + sg * CFG["slippage"]), ccy)
    dist_eur = to_eur(dist, ccy)
    fees = 2 * CFG["fee_per_order"]
    sz = size_position(eq, cash, px_eur, dist_eur)
    qty, value = sz["qty"], sz["value"]
    if sz["why"]:
        return sz["why"]
    ns, ms = news_signal(t, 6), macro_signal(6)
    if side == "long":
        if ns["score"] <= -0.4:
            return f"segnale ORB bloccato da notizie negative ({ns['score']:+.2f}): {ns['top']}"
        if ms["score"] <= -0.4 and ms["count"] >= 10:
            return f"segnale ORB bloccato: clima macro risk-off ({ms['score']:+.2f})"
    else:
        if ns["score"] >= 0.4:
            return f"short bloccato da notizie positive ({ns['score']:+.2f}): {ns['top']}"
        if ms["score"] >= 0.4 and ms["count"] >= 10:
            return f"short bloccato: clima macro risk-on ({ms['score']:+.2f})"
    a = CA.analyze(t, "buy" if side == "long" else "short", b, daily.get(t), stop, target)
    if a["verdict"] != "APPROVE" and CFG.get("chart_veto", True):
        CA.record(con, a, 0)
        return (f"segnale ORB ma analista grafico RIFIUTA (score {a['score']}): " if side == "long" else
                f"segnale short ma analista grafico RIFIUTA (score {a['score']}, serve <= -{CA.APPROVE_BUY}): ") + "; ".join(a["reasons"][:4])
    lev_txt = f", leva {sz['lev']:.2f}x (margine {sz['margin']:.0f} EUR, finanziato {sz['loan']:.0f} EUR)" if sz["loan"] > 0 else ""
    why = (f"ORB {side}: {info}; stop {stop:.3f}, target {target:.3f} (2R); grafico score {a['score']}; news {ns['score']:+.2f}{lev_txt}")
    return dict(ticker=t, side=side, qty=qty, value=value, close=close, stop=stop, target=target,
                risk=qty * dist_eur + fees, why=why, bar=str(sess.index[-1]), analysis=a, ccy=ccy, bars=b,
                info=info, margin=sz["margin"] if sz["loan"] > 0 else None, lev=sz["lev"], score=a["score"])

def execute_entry(con, pl):
    a = pl["analysis"]; side = pl["side"]; t = pl["ticker"]
    CA.record(con, a, 1)
    fill = open_position(con, t, pl["qty"], pl["close"], pl["stop"], pl["target"], pl["risk"], pl["why"], pl["bar"],
                         setup="ORB+VWAP" if side == "long" else "ORB-SHORT", chart_score=a["score"], chart=a["chart"],
                         currency=pl["ccy"], quote_bars=pl["bars"], side=side, margin_eur=pl["margin"])
    lev = f" leva {pl['lev']:.2f}x" if pl["margin"] is not None else ""
    log(f"{'BUY' if side == 'long' else 'SHORT'} {pl['qty']:.4f} {t} @ {fill:.4f} {pl['ccy']} (~{pl['value']:.2f} EUR{lev}) "
        f"stop {pl['stop']:.4f} target {pl['target']:.4f} | {pl['info']}", S)
    return "ENTRATO"

def try_entry(con, it, b, eq, cash, n_open, daily):
    pl = plan_entry(con, it, b, eq, cash, n_open, daily)
    return pl if isinstance(pl, str) else execute_entry(con, pl)

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

def breakout_candidates(yf_bars, uni_rows, n=None):
    """Cheap screen of the WHOLE universe on the one-call Yahoo 5m batch: names whose last close is at/above the
    cash-session opening-range high minus 0.5 x ATR5m (or at/below the low + 0.5 x ATR when shorts are on).
    Returns tickers sorted by closeness/strength of the breakout (EU Yahoo is ~15 min late, so 'near' counts)."""
    out = []
    for u in uni_rows:
        t = u["ticker"]; b = yf_bars.get(t)
        if b is None or b.empty:
            continue
        try:
            o, c, _ = session_times(u["region"])
            sess = today_session(b, u["region"], cash_only=True)
            orb = sess[sess.index < o + timedelta(minutes=CFG["or_minutes"])]
            if len(orb) < 4 or len(sess) <= len(orb):
                continue
            a = float(atr(b).iloc[-1]); close = float(sess["Close"].iloc[-1])
            orh, orl = float(orb["High"].max()), float(orb["Low"].min())
            if not a or a != a:
                continue
            up = (close - orh) / a
            dn = (orl - close) / a if CFG.get("allow_short") else -9
            k = max(up, dn)
            if k >= -0.5:
                out.append((k, t))
        except Exception:
            continue
    out.sort(key=lambda x: -x[0])
    return [t for _, t in out][: n or len(out)]

def wide_data(wl_items, held):
    """Wide scan (CFG wide_universe): every name of the wide universe (core universe.csv + universe_wide.csv when
    CFG wide_file, ~1.230 TR-tradable liquid stocks) in CFG wide_regions, plus the 09:35 watchlist.
    Data: Yahoo 5m (2 sessions) for ALL names in batches of CFG wide_chunk (~15 s for 1.230 names); a cheap screen
    keeps the names at/near their opening-range high (breakout_candidates). Only those, the held positions and the
    watchlist get the full v0 evaluation; live L&S quotes (max ls_priority_max) go to held, candidates, watchlist.
    Returns (items_to_evaluate, bars, daily, n_scanned)."""
    uni = load_wide_universe() if CFG.get("wide_file", True) else load_universe()
    regions = set(CFG.get("wide_regions") or ("EU", "US"))
    have = {i["ticker"] for i in wl_items}
    scan_rows = [u for u in uni if u["region"] in regions or u["ticker"] in have or u["ticker"] in set(held)]
    all_t = sorted({u["ticker"] for u in scan_rows} | have | set(held))
    yfb = yf_intraday_bars_chunked(all_t, period="2d", chunk=CFG.get("wide_chunk", 200))
    cands = breakout_candidates(yfb, scan_rows)
    prio = []
    for t in list(held) + cands + [i["ticker"] for i in wl_items]:
        if t not in prio:
            prio.append(t)
    live = prio[:CFG.get("ls_priority_max", 20)]
    bars = dict(yfb)
    bars.update(intraday_bars(live, yf_bars=yfb))
    missing = [t for t in list(held) + [i["ticker"] for i in wl_items] if t not in bars]
    if missing:   # Yahoo batch failed/limited for these: normal per-name path (Yahoo 5d + L&S)
        log(f"WARN scansione larga: dati mancanti per {', '.join(missing)}, li riscarico a parte", S)
        bars.update(intraday_bars(missing))
    evaluate = set(prio)
    need_daily = sorted(evaluate)
    daily = {}
    for i in range(0, len(need_daily), 200):
        daily.update(daily_bars(need_daily[i:i + 200], "6mo"))
    rows = {u["ticker"]: u for u in scan_rows}
    items = [i for i in wl_items] + [dict(ticker=t, name=rows[t]["name"], region=rows[t]["region"], currency=rows[t]["currency"],
                                          score=None, rationale="scansione larga") for t in prio if t not in have and t in rows]
    log(f"scansione larga: {len(all_t)} titoli controllati ({'+'.join(sorted(regions))}), {len(yfb)} con dati Yahoo, "
        f"{len(cands)} vicini al massimo dell'opening range ({', '.join(cands[:10])}{'…' if len(cands) > 10 else ''}), "
        f"{len(items)} valutati per intero, quotazioni live per {len(live)}; "
        f"altri {max(0, len(all_t) - len(evaluate))} lontani dalla rottura", S)
    return items, bars, daily

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
        if CFG.get("wide_universe"):
            items, bars, daily = wide_data(items, held)
        else:
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
        traded = {r[0] for r in con.execute("SELECT DISTINCT ticker FROM trades WHERE day=? AND side IN ('BUY','SHORT')", (day["day"],))}
        plans = []
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
            if CFG.get("rank_signals"):
                pl = plan_entry(con, it, b, eq, cash, n_open, daily)
                if isinstance(pl, str):
                    log(f"{t}: {pl}", S)
                else:
                    plans.append(pl)
            else:
                log(f"{t}: {try_entry(con, it, b, eq, cash, n_open, daily)}", S)
        # rank_signals: best chart score first, as many as free slots / cash allow
        for pl in sorted(plans, key=lambda x: -(x["score"] or 0)):
            if len(positions(con)) >= CFG["max_positions"]:
                log(f"{pl['ticker']}: segnale valido ma max {CFG['max_positions']} posizioni (classifica per score)", S); continue
            need = (pl["margin"] if pl["margin"] is not None else pl["value"]) + CFG["fee_per_order"]
            if get_cash(con) < need:
                log(f"{pl['ticker']}: segnale valido ma cash insufficiente ({get_cash(con):.0f} < {need:.0f} EUR)", S); continue
            log(f"{pl['ticker']}: {execute_entry(con, pl)}", S)
        eq, cash, mv = equity(con, prices)
        log(f"equity {eq:.2f} EUR (cash {cash:.2f}, posizioni {sum(mv.values()):.2f}), oggi {eq/day['start_equity']-1:+.2%}", S)

if __name__ == "__main__":
    main()
