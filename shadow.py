#!/usr/bin/env python3
"""Strategie in SHADOW (PAPER): registrano solo segnali ipotetici, MAI ordini né scritture sul ledger.

Attive dal 13/11/2026 (regole pre-registrate in R&D reports/preregistration_2026-11-12.md):
- REBOUND: rimbalzo "VWAP reclaim" dopo forte calo, su watchlist statica (scan 09:35) ∪ dinamica (rescan.py).
  minimo seduta <= chiusura ieri x (1 - max(2,5%; ATR14 giornaliero %)), minimo fatto >= 15 min prima,
  chiusura > VWAP con almeno una delle 3 barre precedenti <= VWAP, momentum 15m > 0, prezzo < chiusura di ieri,
  analista grafico APPROVE (>= 25). Stop max(minimo, prezzo - 2 ATR5m) (0,4%-3%), target 2R, breakeven a +1R.
- ORB_DYN: regole ORB v0 identiche a trade.py, ma solo sui candidati della watchlist dinamica non presenti nella
  statica (lato USA dopo l'OR 15:30-16:00). Diagnostico.
Backtest 19/08-11/11 (61 sedute): entrambe peggiori della v0 -> NON in produzione; qui solo per accumulare evidenza.
Uso: ./run.sh shadow (ogni 10 min, minuto :x3)  |  ./run.sh shadow --eod (21:56, esito ipotetico + report)
     python3 shadow.py --dry-run  (stampa i segnali senza scrivere)
File: data/shadow_signals.jsonl e data/shadow_results.jsonl (solo in aggiunta), reports/shadow_YYYY-MM-DD.md.
"""
import json, math, os, sys
from datetime import datetime, timedelta
import pandas as pd
from common import (CFG, ROME, DATA, REPORTS, log, now, today, is_weekend, session_times, flatten_time, load_watchlist,
                    load_universe, intraday_bars, daily_bars, today_session, atr, vwap, quote_ok, quote_currency,
                    to_eur, TAX_RATE)
import chart_analysis as CA
import rescan

S = "shadow"
OUT = os.environ.get("PT_SHADOW_DIR", DATA)
SIG = os.path.join(OUT, "shadow_signals.jsonl")
RES = os.path.join(OUT, "shadow_results.jsonl")
RB = dict(min_drop=0.025, drop_atr=1.0, min_bars_after_low=3, reclaim_lookback=3, stop_atr=2.0)
NOTIONAL = CFG["start_cash"]   # sizing ipotetico su 1.000 € (non legge l'equity del ledger)


def _lines(path):
    if not os.path.exists(path):
        return []
    out = []
    for l in open(path):
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def append(path, row):
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def size(close, dist, ccy):
    px = to_eur(close, ccy); de = to_eur(dist, ccy); fees = 2 * CFG["fee_per_order"]
    q = max(0.0, min((CFG["risk_per_trade"] * NOTIONAL - fees) / de, CFG["max_position_pct"] * NOTIONAL / px))
    q = math.floor(q * 1e4) / 1e4
    if q * px < CFG["min_position_eur"] or q * CFG["reward_r"] * de < CFG["min_reward_vs_fees"] * fees:
        return 0.0
    return q


def size_diag(close, dist, ccy):
    """Quantita' diagnostica: stesso rischio/cap della v0 ma SENZA i filtri minimo/commissioni.
    Serve solo a misurare il vantaggio lordo dei segnali che il filtro commissioni blocca (mai ordini)."""
    px = to_eur(close, ccy); de = to_eur(dist, ccy); fees = 2 * CFG["fee_per_order"]
    if de <= 0 or px <= 0:
        return 0.0
    q = max(0.0, min((CFG["risk_per_trade"] * NOTIONAL - fees) / de, CFG["max_position_pct"] * NOTIONAL / px))
    return math.floor(q * 1e4) / 1e4


def prev_close_from_bars(b, region):
    d = today()
    prior = [x for x in sorted(set(b.index.date)) if x < d]
    if not prior:
        return None
    o, c, _ = session_times(region, prior[-1])
    s = b[(b.index >= o) & (b.index < c)]
    return float(s["Close"].iloc[-1]) if len(s) else None


def rebound(b, sess, region, daily):
    if len(sess) < 8 or daily is None or len(daily) < 25:
        return None
    pc = prev_close_from_bars(b, region)
    if not pc:
        return None
    dd = daily.copy(); dd.index = pd.to_datetime(dd.index).date; dd = dd[dd.index < today()]
    ad = float(atr(dd).iloc[-1]) / float(dd["Close"].iloc[-1])
    a = float(atr(b).iloc[-1])
    low = float(sess["Low"].min())
    if low > pc * (1 - max(RB["min_drop"], RB["drop_atr"] * ad)):
        return None
    if len(sess) - 1 - int(sess["Low"].values.argmin()) < RB["min_bars_after_low"]:
        return None
    vw = vwap(sess); close = float(sess["Close"].iloc[-1])
    if close <= float(vw.iloc[-1]):
        return None
    k = RB["reclaim_lookback"]
    if not (sess["Close"].iloc[-1 - k:-1].values <= vw.iloc[-1 - k:-1].values).any():
        return None
    if close - float(sess["Close"].iloc[-4]) <= 0 or close >= pc:
        return None
    stop = max(low, close - RB["stop_atr"] * a)
    dist = min(max(close - stop, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    return close, close - dist, close + CFG["reward_r"] * dist, f"minimo {low:.3f} vs chiusura ieri {pc:.3f}, VWAP {float(vw.iloc[-1]):.3f}"


def orb(b, sess, region):
    o, _, _ = session_times(region)
    r = sess[(sess.index >= o) & (sess.index < o + timedelta(minutes=CFG["or_minutes"]))]
    if len(r) < 4 or len(sess) < 8:
        return None
    orh, orl = float(r["High"].max()), float(r["Low"].min())
    a = float(atr(b).iloc[-1]); close = float(sess["Close"].iloc[-1]); vw = float(vwap(sess).iloc[-1])
    if not (close > orh and close > vw and close - float(sess["Close"].iloc[-4]) > 0
            and close <= orh + CFG["max_extension_atr"] * a):
        return None
    stop = max(orl, close - CFG["atr_stop_mult"] * a)
    dist = min(max(close - stop, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    return close, close - dist, close + CFG["reward_r"] * dist, f"ORH {orh:.3f}, VWAP {vw:.3f}"


def scan(dry=False):
    n = now()
    if is_weekend():
        return
    static = (load_watchlist() or {}).get("items", [])
    dyn = rescan.load_dyn()
    st_t = {i["ticker"] for i in static}
    plan = [(i, "REBOUND") for i in static] + [(i, "REBOUND") for i in dyn if i["ticker"] not in st_t] + \
           [(i, "ORB_DYN") for i in dyn if i["ticker"] not in st_t]
    done = {(r["strategy"], r["ticker"]) for r in _lines(SIG) if r.get("day") == today().isoformat()}
    plan = [(i, s) for i, s in plan if (s, i["ticker"]) not in done]
    tick = sorted({i["ticker"] for i, _ in plan})[:20]       # LS: max 20 titoli per ciclo
    if not tick:
        log("shadow: nessun titolo da valutare", S); return
    bars = intraday_bars(tick)
    try:
        daily = rescan.daily_cached([u["ticker"] for u in load_universe()])
    except Exception:
        daily = daily_bars(tick, "6mo")
    found = 0
    for it, strat in plan:
        t, region = it["ticker"], it["region"]
        if t not in tick:
            continue
        o, c, last_entry = session_times(region)
        if not (o + timedelta(minutes=CFG["or_minutes"]) <= n <= last_entry):
            continue
        b = bars.get(t)
        if b is None or b.empty or not quote_ok(b, region)[0]:
            continue
        sess = today_session(b, region, cash_only=False)
        sess = sess[sess.index >= o]
        sig = rebound(b, sess, region, daily.get(t)) if strat == "REBOUND" else orb(b, sess, region)
        if not sig:
            continue
        close, stop, target, info = sig
        ccy = quote_currency(b, t)
        entry = float(b.attrs.get("ask") or close * (1 + CFG["slippage"]))
        qty = size(entry, close - stop, ccy)
        a = CA.analyze(t, "buy", b, daily.get(t), stop, target, save_chart=False)
        row = dict(day=today().isoformat(), ts=n.isoformat(timespec="seconds"), strategy=strat, ticker=t, region=region,
                   currency=ccy, price=round(close, 4), entry=round(entry, 4), stop=round(stop, 4), target=round(target, 4),
                   qty=qty, qty_diag=size_diag(entry, close - stop, ccy), chart_score=a["score"], chart_verdict=a["verdict"], approved=a["verdict"] == "APPROVE" and qty > 0,
                   bar=str(sess.index[-1]), source=b.attrs.get("source"), info=info,
                   dyn=t not in st_t, note="SHADOW: nessun ordine")
        found += 1
        if a["verdict"] != "APPROVE" and strat in ("REBOUND", "ORB_DYN"):
            # registra comunque il segnale grezzo (serve al conteggio), ma con approved=False; non lo ripete oggi
            pass
        if dry:
            print(json.dumps(row, ensure_ascii=False)); continue
        append(SIG, row)
        log(f"SHADOW {strat} {t} @ {entry:.4f} stop {stop:.4f} target {target:.4f} grafico {a['score']} {a['verdict']}", S)
    log(f"shadow: {len(plan)} valutazioni, {found} segnali", S)


def eod(dry=False):
    d = today().isoformat()
    sigs = [r for r in _lines(SIG) if r.get("day") == d]
    done = {(r["strategy"], r["ticker"]) for r in _lines(RES) if r.get("day") == d}
    todo = [r for r in sigs if (r["strategy"], r["ticker"]) not in done]
    bars = intraday_bars(sorted({r["ticker"] for r in todo})[:20]) if todo else {}
    out = []
    for r in todo:
        b = bars.get(r["ticker"])
        res = dict(r, outcome="n/d", exit=None, net_ante_tasse=None)
        q = r["qty"] if r.get("approved") and r["qty"] > 0 else 0.0
        diag = False
        if q <= 0 and r.get("chart_verdict") == "APPROVE" and (r.get("qty_diag") or 0) > 0:
            q, diag = r["qty_diag"], True          # bloccato solo dal filtro commissioni: esito diagnostico
        if q > 0 and b is not None and len(b):
            res["diag"] = diag
            fl = flatten_time(r["region"])
            fut = b[(b.index > pd.Timestamp(r["bar"])) & (b.index < fl)]
            st, tg, e = r["stop"], r["target"], r["entry"]; risk = e - st
            px, why = None, "fine giornata"
            for ts, x in fut.iterrows():
                if x["Low"] <= st:
                    px, why = min(st, x["Open"]) * (1 - CFG["slippage"]), "stop"; break
                if x["High"] >= tg:
                    px, why = max(tg, x["Open"]), "target"; break
                if x["High"] >= e + risk:
                    st = max(st, e + 2 * CFG["fee_per_order"] / q)
            if px is None and len(fut):
                px = float(fut["Close"].iloc[-1]) * (1 - CFG["slippage"])
            if px is not None:
                gross = to_eur(q * (px - e), r["currency"])
                pnl = gross - 2 * CFG["fee_per_order"]
                res.update(outcome=why, exit=round(px, 4), gross=round(gross, 2), net_ante_tasse=round(pnl, 2),
                           tax_if_gain=round(max(pnl, 0) * TAX_RATE, 2), qty_used=q)
        out.append(res)
        if not dry:
            append(RES, res)
    allres = [x for x in _lines(RES) if x.get("day") == d] if not dry else out
    md = [f"# Shadow {today():%d/%m/%Y} – segnali ipotetici, NESSUN ordine (ora di Roma)", "",
          "Strategie non validate dal backtest: REBOUND (rimbalzo VWAP dopo forte calo) e ORB_DYN (ORB v0 su candidati dinamici).",
          "Sizing ipotetico su 1.000 €, commissioni 2 €; netto ante tasse (tassa 26% solo se in utile, zainetto non applicato).", ""]
    if not allres:
        md.append("Nessun segnale oggi.")
    tot = totd = 0.0
    for x in allres:
        v = x.get("net_ante_tasse")
        if x.get("diag"):
            totd += v or 0
        else:
            tot += v or 0
        if v is not None:
            tag = (f", DIAGNOSTICO (bloccato dal filtro commissioni, qty {x.get('qty_used')}): lordo {x.get('gross', 0):+.2f} €, "
                   f"netto ante tasse {v:+.2f} €") if x.get("diag") else f", netto ante tasse {v:+.2f} €"
        elif x.get("chart_verdict") != "APPROVE":
            tag = " (respinto dall'analista grafico: solo conteggio)"
        else:
            tag = " (approvato dal grafico ma senza barre/quantità: solo conteggio)"
        md.append(f"- {x['ts'][11:16]} {x['strategy']} {x['ticker']} ingresso {x['entry']} stop {x['stop']} target {x['target']} "
                  f"grafico {x['chart_score']} ({x['chart_verdict']}) -> {x['outcome']}" + tag)
    md += ["", f"Totale netto ante tasse dei segnali operativi (passano anche il filtro commissioni): {tot:+.2f} €",
           f"Totale netto ante tasse dei segnali diagnostici (solo filtro commissioni li blocca): {totd:+.2f} €"]
    if dry:
        print("\n".join(md)); return
    open(os.path.join(REPORTS, f"shadow_{today():%Y-%m-%d}.md"), "w").write("\n".join(md) + "\n")
    log(f"shadow eod: {len(out)} esiti nuovi, totale {tot:+.2f} EUR", S)


def main():
    dry = "--dry-run" in sys.argv
    if "--eod" in sys.argv:
        eod(dry)
    else:
        scan(dry)


if __name__ == "__main__":
    main()
