#!/usr/bin/env python3
"""Strategie in SHADOW (PAPER): registrano solo segnali ipotetici, MAI ordini né scritture sul ledger.

Attive dal 13/11/2026 (regole pre-registrate in R&D reports/preregistration_2026-11-12.md):
- REBOUND: rimbalzo "VWAP reclaim" dopo forte calo, su watchlist statica (scan 09:35) ∪ dinamica (rescan.py).
  minimo seduta <= chiusura ieri x (1 - max(2,5%; ATR14 giornaliero %)), minimo fatto >= 15 min prima,
  chiusura > VWAP con almeno una delle 3 barre precedenti <= VWAP, momentum 15m > 0, prezzo < chiusura di ieri,
  analista grafico APPROVE (>= 25). Stop max(minimo, prezzo - 2 ATR5m) (0,4%-3%), target 2R, breakeven a +1R.
- ORB_DYN: regole ORB v0 identiche a trade.py, ma solo sui candidati della watchlist dinamica non presenti nella
  statica (lato USA dopo l'OR 15:30-16:00). Diagnostico.
- V0_LOOSE (attiva dal 16/11/2026, pre-registrazione R&D reports/preregistration_2026-11-13_zerotrade.md, variante V1): ORB v0 sulla
  watchlist statica con i due filtri che bloccano quasi tutti i breakout allentati: non oltre 3,0 ATR5m sopra ORH (v0: 1,5) e
  guadagno al target >= 1,5x commissioni (v0: 3x). Analista grafico APPROVE come la v0. Backtest 19/08-11/11: 89 trade,
  netto -203,29 EUR (OOS 66 trade, -151,53 EUR) -> NON in produzione: misura a costo zero di quanto opererebbe dal vivo.
- DIBATTITO (prova di un giorno dal 16/11/2026, pre-registrazione R&D reports/preregistration_2026-11-16_debate.md): per i segnali
  V0 (copia diagnostica delle regole di trade.py, compresi quelli bloccati dal filtro commissioni), V0_LOOSE e NEWS_LLM (giudizi forti
  di Natasia, |impact| >= 0,5 e confidence >= 0,6) debate.py fa argomentare PRO e CONTRO a un LLM gratuito e un giudice decide
  ENTRA/SCARTA. V0 e NEWS_LLM vanno in data/debate_signals.jsonl (non nei totali shadow). Worker in background, mai bloccante.
- V0_FEE4 (prova di un giorno dal 16/11/2026, R&D reports/sizing_scan_2026-11-16.md): regole identiche alla v0 in produzione
  (ORB + VWAP + momentum + EMA9>EMA21, estensione max 1,5 ATR, analista grafico) ma filtro commissioni piu' severo: guadagno al
  target 2R >= 4x commissioni (8 EUR invece di 6). Backtest 61 sedute: 7 trade, +7,26 EUR (OOS +4,12, WF 2/5 come la v0) ->
  NON in produzione (pochi trade). Non passa dal dibattito LLM. Confronto con la v0 nel report delle 21:56.
- V0_SHORT (dal 17/11/2026, R&D reports/short_2026-11-16.md): lato SHORT speculare della v0 (rottura sotto il minimo dell'opening
  range, prezzo sotto VWAP, momentum 15m negativo, EMA9<EMA21, estensione max 1,5 ATR sotto ORL, stop min(ORH, prezzo+1,5 ATR),
  target 2R sotto, stesso sizing e filtro commissioni 6 €, analista grafico con punteggio <= -25). Backtest 61 sedute: 29 short,
  -69,35 EUR (OOS -55,88) e long+short -69,31 contro -7,09 della sola v0 long -> NON in produzione, qui per misurarlo dal vivo.
- USLEAD_DAX (dal 20/11/2026, R&D reports/prereg_alt_2026-11-20.md): direzione dell'S&P 500 fra le 15:30 e le 15:55 (|r| >= 0,30%)
  -> DAX nella stessa direzione alle 16:00 via KO x5 (esposizione ipotetica 5.000 EUR, spread 0,2% sul certificato), stop 0,4%,
  target 2R, chiusura alla barra 17:25. Backtest a capitale fisso 62 sedute: 13 trade, netto +53,11 EUR (OOS +69,78, holdout +57,94)
  ma volume troppo basso e controllo su barre 1h 2024-2026 negativo (-1,6 bp) -> NON in produzione, qui per misurarlo dal vivo.
- A4_ADAPT (dal 23/11/2026, R&D reports/prereg_adaptive_2026-11-21.md, variante A4): SHADOW OSSERVATIVA su richiesta di Andrea (via
  Sguattera), NON un candidato validato (scartata dai criteri pre-registrati: OOS 2025-26 -31,40 EUR vs produzione). Interruttore per
  regione: ON se l'indice (DAX per EU, Nasdaq 100 per US) ha reso <= -3% sulle ultime 5 chiusure fino a ieri. Se ON: short ombra
  via KO x5 sull'indice (nozionale 1.200 EUR, stop +1,5%, ingresso a fine prima ora solo se l'indice e' sotto l'apertura, uscita 17:00
  DAX / 21:30 NDX, fee 2 EUR, spread KO 0,2% sul certificato, slippage 0,02%/lato) e i long di produzione della regione 'bloccati'
  (solo conteggio del loro netto reale). Calcolato a fine giornata (--eod) in data/adaptive_shadow.jsonl; sezione nel report serale.
  Verifica a data simulata: python3 shadow.py --a4-sim 2026-11-18,2026-11-19,2026-11-20 (non scrive nulla).
Backtest 19/08-11/11 (61 sedute): entrambe peggiori della v0 -> NON in produzione; qui solo per accumulare evidenza.
Uso: ./run.sh shadow (ogni 10 min, minuto :x3)  |  ./run.sh shadow --eod (21:56, esito ipotetico + report)
     python3 shadow.py --dry-run  (stampa i segnali senza scrivere)
File: data/shadow_signals.jsonl e data/shadow_results.jsonl (solo in aggiunta), reports/shadow_YYYY-MM-DD.md.
"""
import json, math, os, subprocess, sys
from datetime import datetime, timedelta, time as dtime
import pandas as pd
from common import (CFG, ROME, DATA, REPORTS, log, now, today, is_weekend, session_times, flatten_time, load_watchlist,
                    load_universe, intraday_bars, yf_intraday_bars, daily_bars, today_session, atr, vwap, ema_aligned, quote_ok, quote_currency,
                    to_eur, TAX_RATE)
import chart_analysis as CA
import rescan

S = "shadow"
OUT = os.environ.get("PT_SHADOW_DIR", DATA)
SIG = os.path.join(OUT, "shadow_signals.jsonl")
RES = os.path.join(OUT, "shadow_results.jsonl")
DSIG = os.path.join(OUT, "debate_signals.jsonl")   # segnali V0 / NEWS_LLM per il filtro dibattito (solo shadow)
NEWS_MAX_TICKERS = 6                               # NEWS_LLM: max titoli extra scaricati per ciclo
RB = dict(min_drop=0.025, drop_atr=1.0, min_bars_after_low=3, reclaim_lookback=3, stop_atr=2.0)
LOOSE = dict(max_extension_atr=3.0, min_reward_vs_fees=1.5)   # variante V0_LOOSE (solo shadow)
FEE4 = dict(min_reward_vs_fees=4.0)                            # variante V0_FEE4: v0 con filtro commissioni 4x (solo shadow)
MIN_RR = {"V0_LOOSE": LOOSE["min_reward_vs_fees"], "V0_FEE4": FEE4["min_reward_vs_fees"]}
USLEAD = dict(thr=0.003, stop=0.004, rr=2.0, lev=5.0, expo=5000.0, half_spread=0.001)  # USLEAD_DAX (solo shadow)
A4 = dict(k=5, thr=0.03, lev=5.0, expo=1200.0, stop=0.015, half_spread=0.001, slip=0.0002, fees=2.0,
          idx={"EU": "^GDAXI", "US": "^NDX"}, exit={"EU": dtime(17, 0), "US": dtime(21, 30)})  # A4_ADAPT (solo shadow)
ADAPT = os.path.join(OUT, "adaptive_shadow.jsonl")
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


def size(close, dist, ccy, min_rr=None):
    px = to_eur(close, ccy); de = to_eur(dist, ccy); fees = 2 * CFG["fee_per_order"]
    q = max(0.0, min((CFG["risk_per_trade"] * NOTIONAL - fees) / de, CFG["max_position_pct"] * NOTIONAL / px))
    q = math.floor(q * 1e4) / 1e4
    if q * px < CFG["min_position_eur"] or q * CFG["reward_r"] * de < (CFG["min_reward_vs_fees"] if min_rr is None else min_rr) * fees:
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


def orb(b, sess, region, max_ext=None):
    o, _, _ = session_times(region)
    r = sess[(sess.index >= o) & (sess.index < o + timedelta(minutes=CFG["or_minutes"]))]
    if len(r) < 4 or len(sess) < 8:
        return None
    orh, orl = float(r["High"].max()), float(r["Low"].min())
    a = float(atr(b).iloc[-1]); close = float(sess["Close"].iloc[-1]); vw = float(vwap(sess).iloc[-1])
    if not (close > orh and close > vw and close - float(sess["Close"].iloc[-4]) > 0
            and close <= orh + (CFG["max_extension_atr"] if max_ext is None else max_ext) * a):
        return None
    # stessa regola della produzione: long solo se EMA9 > EMA21 sulle chiusure 5m
    if not ema_aligned(b, side="long")[0]:
        return None
    stop = max(orl, close - CFG["atr_stop_mult"] * a)
    dist = min(max(close - stop, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    return close, close - dist, close + CFG["reward_r"] * dist, f"ORH {orh:.3f}, VWAP {vw:.3f}"


def orb_short(b, sess, region):
    """Specchio ribassista di orb(): breakdown sotto ORL, sotto VWAP, momentum 15m < 0, EMA9 < EMA21, max 1,5 ATR sotto ORL.
    Ritorna (close, stop, target, info) con stop SOPRA e target SOTTO il prezzo."""
    o, _, _ = session_times(region)
    r = sess[(sess.index >= o) & (sess.index < o + timedelta(minutes=CFG["or_minutes"]))]
    if len(r) < 4 or len(sess) < 8:
        return None
    orh, orl = float(r["High"].max()), float(r["Low"].min())
    a = float(atr(b).iloc[-1]); close = float(sess["Close"].iloc[-1]); vw = float(vwap(sess).iloc[-1])
    if not (close < orl and close < vw and close - float(sess["Close"].iloc[-4]) < 0
            and close >= orl - CFG["max_extension_atr"] * a):
        return None
    if not ema_aligned(b, side="short")[0]:
        return None
    stop = min(orh, close + CFG["atr_stop_mult"] * a)
    dist = min(max(stop - close, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
    return close, close + dist, close - CFG["reward_r"] * dist, f"ORL {orl:.3f}, VWAP {vw:.3f}"


def ctx_for(b, sess, region, close):
    """Dati noti al momento del segnale (per il contesto del dibattito; nessun dato futuro)."""
    out = {}
    try:
        o, _, _ = session_times(region)
        r = sess[(sess.index >= o) & (sess.index < o + timedelta(minutes=CFG["or_minutes"]))]
        if len(r):
            out.update(ORH=round(float(r["High"].max()), 4), ORL=round(float(r["Low"].min()), 4))
        out["VWAP"] = round(float(vwap(sess).iloc[-1]), 4)
        if len(sess) >= 4:
            out["momentum15m_pct"] = round((close / float(sess["Close"].iloc[-4]) - 1) * 100, 2)
        out["ATR5m"] = round(float(atr(b).iloc[-1]), 4)
        ok_ema, e9, e21 = ema_aligned(b, side="long")
        if e9 == e9 and e21 == e21:
            out["EMA9"], out["EMA21"], out["ema_aligned"] = round(e9, 4), round(e21, 4), bool(ok_ema)
        pc = prev_close_from_bars(b, region)
        if pc:
            out.update(chiusura_ieri=round(pc, 4), var_giorno_pct=round((close / pc - 1) * 100, 2))
        out["max_seduta"], out["min_seduta"] = round(float(sess["High"].max()), 4), round(float(sess["Low"].min()), 4)
    except Exception:
        pass
    return out


def news_candidates(n):
    """Giudizi forti di Natasia non scaduti ed emessi prima di adesso: [(item, giudizio)]."""
    try:
        j = json.load(open(os.path.join(DATA, "news_llm.json")))
    except Exception:
        return []
    uni = {u["ticker"]: u for u in load_universe()}
    out = []
    for t in j.get("tickers", []):
        try:
            iss, exp = pd.Timestamp(t.get("issued_at")), pd.Timestamp(t.get("expires_at"))
            if iss.tzinfo is None or exp.tzinfo is None or not (iss <= pd.Timestamp(n) < exp):
                continue
            if abs(float(t.get("impact") or 0)) < 0.5 or float(t.get("confidence") or 0) < 0.6 or t["ticker"] not in uni:
                continue
        except Exception:
            continue
        out.append((dict(ticker=t["ticker"], region=uni[t["ticker"]].get("region") or "EU"), t))
    return out


def news_scan(n, bars, done, dry):
    """NEWS_LLM: un segnale per titolo/giorno nel verso del giudizio di Natasia (solo per il dibattito, nessun ordine)."""
    cands = [(it, j) for it, j in news_candidates(n) if ("NEWS_LLM", it["ticker"]) not in done]
    cands = [(it, j) for it, j in cands if session_times(it["region"])[0] + timedelta(minutes=CFG["or_minutes"]) <= n
             <= session_times(it["region"])[2]]
    if not cands:
        return 0
    extra = sorted({it["ticker"] for it, _ in cands if it["ticker"] not in bars})[:NEWS_MAX_TICKERS]
    if extra:
        bars = dict(bars); bars.update(intraday_bars(extra))
    found = 0
    for it, j in cands:
        t, region = it["ticker"], it["region"]
        b = bars.get(t)
        if b is None or b.empty or not quote_ok(b, region)[0]:
            continue
        o, _, _ = session_times(region)
        sess = today_session(b, region, cash_only=False)
        sess = sess[sess.index >= o]
        if len(sess) < 4:
            continue
        side = "long" if float(j["impact"]) > 0 else "short"
        close = float(sess["Close"].iloc[-1]); a = float(atr(b).iloc[-1])
        dist = min(max(CFG["atr_stop_mult"] * a, close * CFG["min_stop_pct"]), close * CFG["max_stop_pct"])
        sg = 1 if side == "long" else -1
        q = b.attrs.get("ask") if side == "long" else b.attrs.get("bid")
        entry = float(q or close * (1 + sg * CFG["slippage"]))
        ccy = quote_currency(b, t)
        row = dict(day=today().isoformat(), ts=n.isoformat(timespec="seconds"), strategy="NEWS_LLM", ticker=t, region=region,
                   side=side, currency=ccy, price=round(close, 4), entry=round(entry, 4), stop=round(close - sg * dist, 4),
                   target=round(close + sg * CFG["reward_r"] * dist, 4), qty_diag=size_diag(entry, dist, ccy),
                   chart_score=None, chart_verdict=None, bar=str(sess.index[-1]), source=b.attrs.get("source"),
                   ctx=ctx_for(b, sess, region, close),
                   natasia=dict(impact=j.get("impact"), confidence=j.get("confidence"), horizon=j.get("horizon"),
                                rationale=str(j.get("rationale", ""))[:400], key_headlines=(j.get("key_headlines") or [])[:3],
                                issued_at=j.get("issued_at")),
                   note="SHADOW: nessun ordine (solo filtro dibattito)")
        found += 1
        if dry:
            print(json.dumps(row, ensure_ascii=False)); continue
        append(DSIG, row)
        log(f"SHADOW NEWS_LLM {t} {side} @ {entry:.4f} stop {row['stop']} target {row['target']} (Natasia {j.get('impact')})", S)
    return found


def spawn_debate():
    """Lancia il worker del dibattito in background (lock esclusivo dentro debate.py): shadow.py non aspetta mai l'LLM."""
    if not CFG.get("debate_shadow", True):
        return
    try:
        import debate
        if not debate.pending(today().isoformat()):
            return
        base = os.path.dirname(os.path.abspath(__file__))
        # "python3 debate.py" letterale: gh/session_runner.py lo riconosce (JOB_PAT) e lo aspetta prima di salvare lo stato
        subprocess.Popen(["python3", "debate.py", "--worker"], cwd=base,
                         stdout=open(os.path.join(base, "logs", "debate.log"), "a"),
                         stderr=subprocess.STDOUT, start_new_session=True)
    except Exception as e:
        log(f"dibattito: worker non avviato ({e})", S)


def uslead_scan(n, dry=False):
    """USLEAD_DAX (solo shadow): S&P 500 15:30-15:55 -> DAX alle 16:00 via KO x5. Una volta al giorno, fra le 16:00 e le 16:40."""
    d = today()
    if not (dtime(16, 0) <= n.time() <= dtime(16, 40)):
        return 0
    if any(r.get("strategy") == "USLEAD_DAX" and r.get("day") == d.isoformat() for r in _lines(SIG)):
        return 0
    b = yf_intraday_bars(["^GSPC", "^GDAXI"])
    spx, dax = b.get("^GSPC"), b.get("^GDAXI")
    if spx is None or dax is None or spx.empty or dax.empty:
        log("shadow USLEAD_DAX: barre Yahoo ^GSPC/^GDAXI non disponibili", S); return 0
    o = datetime.combine(d, dtime(15, 30), ROME)
    sp = spx[spx.index >= o]
    if not len(sp) or sp.index[0] != o:
        log("shadow USLEAD_DAX: apertura USA non alle 15:30 (settimana con ora legale sfasata) o barre mancanti", S); return 0
    last = sp[sp.index == o + timedelta(minutes=25)]
    e = dax[dax.index == o + timedelta(minutes=30)]
    if not len(last) or not len(e):
        return 0
    r = float(last["Close"].iloc[0]) / float(sp["Open"].iloc[0]) - 1
    if abs(r) < USLEAD["thr"]:
        log(f"shadow USLEAD_DAX: S&P 15:30-15:55 {r:+.2%} sotto soglia, nessun segnale", S); return 0
    sg = 1 if r > 0 else -1; entry = float(e["Open"].iloc[0]); dist = entry * USLEAD["stop"]
    qty = round(USLEAD["expo"] / entry, 4)
    row = dict(day=d.isoformat(), ts=n.isoformat(timespec="seconds"), strategy="USLEAD_DAX", ticker="^GDAXI", region="EU",
               currency="EUR", price=round(entry, 2), entry=round(entry, 2), stop=round(entry - sg * dist, 2),
               target=round(entry + sg * USLEAD["rr"] * dist, 2), qty=qty, qty_diag=qty, chart_score=None,
               chart_verdict="N/A", approved=True, bar=str(last.index[0]), source="yfinance",
               info=f"S&P 15:30-15:55 {r:+.2%}; KO x5 ipotetico, esposizione {USLEAD['expo']:.0f} EUR",
               dyn=False, side="long" if sg > 0 else "short", inst="ko5",
               spread_cost=round(2 * USLEAD["half_spread"] * USLEAD["expo"] / USLEAD["lev"], 2), note="SHADOW: nessun ordine")
    if dry:
        print(json.dumps(row, ensure_ascii=False)); return 1
    append(SIG, row)
    log(f"SHADOW USLEAD_DAX ^GDAXI {row['side']} @ {entry:.2f} (S&P {r:+.2%})", S)
    return 1


# ---------------- A4_ADAPT: interruttore di regime adattivo (SHADOW osservativa, nessun ordine) ----------------
def a4_state(closes, d):
    """closes: Serie di chiusure giornaliere indicizzata per data. Usa solo chiusure < d. -> (on, ret5) o (None, None)."""
    s = closes[[x < d for x in closes.index]].dropna()
    if len(s) < A4["k"] + 1:
        return None, None
    r = float(s.iloc[-1]) / float(s.iloc[-1 - A4["k"]]) - 1
    return r <= -A4["thr"], r


def a4_closes(daily, b, region, d):
    """Chiusure giornaliere dell'indice: Yahoo 1d, con le sedute mancanti (Yahoo a volte omette l'ultima in download multipli)
    riempite con l'ultima barra 5m della seduta cash. -> (Serie per data, lista dei giorni riempiti dal 5m)."""
    cl = pd.Series(dtype=float)
    if daily is not None and len(daily):
        cl = daily["Close"].astype(float).dropna().copy(); cl.index = [pd.Timestamp(x).date() for x in cl.index]
    filled = []
    if b is not None and len(b):
        for dd in sorted(set(b.index.date)):
            if dd >= d or dd in cl.index:
                continue
            o, c = session_times(region, dd)[:2]
            sess = b[(b.index >= o) & (b.index < c)]
            if len(sess) >= 30:
                cl.loc[dd] = float(sess["Close"].iloc[-1]); filled.append(str(dd))
    cl = cl[~pd.Index(cl.index).duplicated(keep="first")].sort_index()
    return (cl if len(cl) else None), filled


def a4_short(b, region, d):
    """Short ombra KO x5 sull'indice: ingresso a fine prima ora se sotto l'apertura, stop +1,5%, uscita a orario fisso."""
    if b is None or not len(b):
        return dict(status="barre non disponibili")
    o = session_times(region, d)[0]; ent = o + timedelta(minutes=60); ex = datetime.combine(d, A4["exit"][region], ROME)
    day = b[(b.index >= o) & (b.index.date == d)]
    first = day[day.index + timedelta(minutes=5) <= ent]
    path = day[(day.index + timedelta(minutes=5) > ent) & (day.index + timedelta(minutes=5) <= ex)]
    if not len(first) or first.index[0] != o or not len(path):
        return dict(status="barre incomplete")
    op, px = float(first["Open"].iloc[0]), float(first["Close"].iloc[-1])
    if not px < op:
        return dict(status="nessuno short: indice sopra l'apertura alle " + ent.strftime("%H:%M"), open=round(op, 2), entry_px=round(px, 2))
    lev, e = A4["lev"], A4["expo"]; barrier, st = px * (1 + 1 / lev), px * (1 + A4["stop"])
    sx, why, xts = float(path["Close"].iloc[-1]), "orario", path.index[-1] + timedelta(minutes=5)
    for ts, bar in path.iterrows():
        if float(bar["High"]) >= barrier:
            sx, why, xts = None, "knock-out", ts + timedelta(minutes=5); break
        if float(bar["High"]) >= st:
            sx, why, xts = max(st, float(bar["Open"])), "stop", ts + timedelta(minutes=5); break
    v0 = e / lev; rel = 0.0 if sx is None else max(0.0, 1 + lev * (1 - sx / px)); hs = A4["half_spread"]
    gross = v0 * rel * (1 - hs) - v0 * (1 + hs) - 2 * A4["slip"] * e
    return dict(status="short", open=round(op, 2), entry_px=round(px, 2), entry_ts=ent.isoformat(timespec="minutes"),
                exit_px=round(sx if sx is not None else barrier, 2), exit_ts=xts.isoformat(timespec="minutes"), exit_reason=why,
                move_pct=round((1 - (sx if sx is not None else barrier) / px) * 100, 3), gross=round(gross, 2), net_ante_tasse=round(gross - A4["fees"], 2))


def a4_prod_trades(d):
    """Long di produzione con ingresso nel giorno d (trade_log), con regione e netto reale."""
    try:
        import trade_log as TL
        rows = _lines(TL.log_path())
    except Exception:
        return []
    try:
        reg = {u["ticker"]: u["region"] for u in load_universe()}
    except Exception:
        reg = {}
    out = []
    for r in rows:
        if r.get("source") != "production" or str(r.get("entry_ts", ""))[:10] != d.isoformat():
            continue
        sym = r.get("symbol", "")
        out.append(dict(symbol=sym, region=reg.get(sym, "EU" if "." in sym else "US"), side=r.get("side", "long"),
                        entry_ts=r.get("entry_ts"), net=round(float(r.get("net_pnl_eur") or 0), 2)))
    return out


def a4_eval(d, bars, daily):
    """Riga giornaliera A4_ADAPT per il giorno d (pura: nessuna scrittura)."""
    row = dict(day=d.isoformat(), strategy="A4_ADAPT", note="SHADOW osservativa: nessun ordine, nessuna scrittura sul ledger", regions={})
    prod = a4_prod_trades(d); short_net = 0.0; blocked_net = 0.0
    for region, tk in A4["idx"].items():
        cl, filled = a4_closes(daily.get(tk), bars.get(tk), region, d)
        on, r5 = a4_state(cl, d) if cl is not None else (None, None)
        x = dict(index=tk, on=on, ret5_pct=None if r5 is None else round(r5 * 100, 2),
                 last_close_day=None if cl is None or not len(cl[[c < d for c in cl.index]]) else str(max(c for c in cl.index if c < d)),
                 closes_from_5m=filled)
        if on:
            x["short"] = a4_short(bars.get(tk), region, d)
            bl = [p for p in prod if p["region"] == region and p["side"] == "long"]
            x["blocked"] = bl; x["blocked_net"] = round(sum(p["net"] for p in bl), 2)
            short_net += x["short"].get("net_ante_tasse") or 0.0; blocked_net += x["blocked_net"]
        row["regions"][region] = x
    row["short_net"] = round(short_net, 2); row["blocked_net"] = round(blocked_net, 2)
    row["delta"] = round(short_net - blocked_net, 2)
    return row


def a4_fetch(period="1mo"):
    tks = list(A4["idx"].values())
    return yf_intraday_bars(tks, period=period), daily_bars(tks, period="3mo")


def a4_lines(dry=False):
    d = today(); md = ["", "## A4_ADAPT — interruttore di regime adattivo (SHADOW osservativa su richiesta di Andrea, non validato; nessun ordine)", ""]
    if is_weekend(d):
        return md + ["- nessuna seduta (fine settimana)"]
    try:
        hist = [r for r in _lines(ADAPT) if r.get("strategy") == "A4_ADAPT"]
        row = next((r for r in hist if r.get("day") == d.isoformat()), None)
        if row is None:
            bars, daily = a4_fetch()
            row = a4_eval(d, bars, daily)
            if not dry:
                append(ADAPT, row); hist.append(row)
        md += a4_row_lines(row)
        cum = sum(r.get("delta") or 0 for r in hist if r.get("day", "") <= d.isoformat()) + (0 if row in hist else row["delta"])
        md.append(f"- Δ cumulato A4 vs produzione dal 23/11: {cum:+.2f} € ({len([r for r in hist if r.get('day', '') <= d.isoformat()])} sedute registrate)")
    except Exception as e:
        md.append(f"- A4_ADAPT non calcolato ({type(e).__name__}: {e})")
    return md


def a4_row_lines(row):
    md = []
    for region, x in row["regions"].items():
        st = "ACCESO" if x.get("on") else ("spento" if x.get("on") is False else "n/d")
        line = (f"- {x['index']} ({region}): interruttore {st}, rendimento 5 giorni {x['ret5_pct'] if x['ret5_pct'] is not None else 'n/d'}% "
                f"(ultima chiusura usata {x.get('last_close_day')}" + (", chiusure da barre 5m: " + ", ".join(x['closes_from_5m']) if x.get('closes_from_5m') else "") + ")")
        if x.get("on"):
            sh = x.get("short") or {}
            if sh.get("status") == "short":
                line += (f"; short ombra {sh['entry_ts'][11:16]} @ {sh['entry_px']} -> {sh['exit_ts'][11:16]} @ {sh['exit_px']} ({sh['exit_reason']}, "
                         f"{sh['move_pct']:+.2f}%), netto ante tasse {sh['net_ante_tasse']:+.2f} €")
            else:
                line += f"; {sh.get('status', 'nessuno short')}"
            bl = x.get("blocked") or []
            line += (f"; long di produzione che A4 avrebbe bloccato: {len(bl)}"
                     + (" (" + ", ".join(f"{p['symbol']} {p['net']:+.2f}" for p in bl) + f"; netto reale {x['blocked_net']:+.2f} €)" if bl else ""))
        md.append(line)
    md.append(f"- Δ del giorno A4 vs produzione: {row['delta']:+.2f} € (short {row['short_net']:+.2f} € ante tasse, meno long bloccati {row['blocked_net']:+.2f} € netti)")
    return md


def a4_sim(days_csv):
    """Verifica a data simulata: ricalcola A4 per i giorni dati (barre Yahoo 5m ultimi 60 giorni). Non scrive nulla."""
    from datetime import date as _date
    bars, daily = a4_fetch(period="1mo"); tot = 0.0
    for ds in days_csv.split(","):
        row = a4_eval(_date.fromisoformat(ds.strip()), bars, daily); tot += row["delta"]
        print(f"### {row['day']}"); print("\n".join(a4_row_lines(row))); print(json.dumps(row, ensure_ascii=False, default=str))
    print(f"Δ totale simulato: {tot:+.2f} €")


def scan(dry=False):
    n = now()
    if is_weekend():
        return
    try:
        uslead_scan(n, dry)
    except Exception as e:
        log(f"shadow USLEAD_DAX: errore {e}", S)
    static = (load_watchlist() or {}).get("items", [])
    dyn = rescan.load_dyn()
    st_t = {i["ticker"] for i in static}
    plan = [(i, "REBOUND") for i in static] + [(i, "REBOUND") for i in dyn if i["ticker"] not in st_t] + \
           [(i, "ORB_DYN") for i in dyn if i["ticker"] not in st_t] + [(i, "V0_LOOSE") for i in static] + \
           [(i, "V0_FEE4") for i in static] + [(i, "V0_SHORT") for i in static] + [(i, "V0") for i in static]
    wide_regs = set(CFG.get("wide_regions") or ()) if CFG.get("wide_universe") else set()
    wide = [u for u in load_universe() if u["ticker"] not in st_t and u["region"] not in wide_regs]
    plan += [(u, "V0_WIDE") for u in wide]      # v0 sui titoli che la produzione NON scansiona (oggi: USA fuori lista)
    done = {(r["strategy"], r["ticker"]) for r in _lines(SIG) + _lines(DSIG) if r.get("day") == today().isoformat()}
    plan = [(i, s) for i, s in plan if (s, i["ticker"]) not in done]
    tick = sorted({i["ticker"] for i, s_ in plan if s_ != "V0_WIDE"})[:20]       # LS: max 20 titoli per ciclo
    wide_t = sorted({i["ticker"] for i, s_ in plan if s_ == "V0_WIDE"} - set(tick))  # V0_WIDE: un solo batch Yahoo
    if not tick and not wide_t:
        log("shadow: nessun titolo da valutare", S)
        try:
            news_scan(n, {}, done, dry)
            if not dry:
                spawn_debate()
        except Exception as e:
            log(f"shadow NEWS_LLM: errore {e}", S)
        return
    bars = intraday_bars(tick) if tick else {}
    if wide_t:
        try:
            ywide = yf_intraday_bars(wide_t)
            bars = dict(bars); bars.update({t: b for t, b in ywide.items() if t not in bars})
        except Exception as e:
            log(f"shadow V0_WIDE: dati Yahoo non disponibili ({e})", S)
    try:
        daily = rescan.daily_cached([u["ticker"] for u in load_universe()])
    except Exception:
        daily = daily_bars(tick, "6mo")
    found = 0
    for it, strat in plan:
        t, region = it["ticker"], it["region"]
        if t not in tick and not (strat == "V0_WIDE" and t in wide_t):
            continue
        o, c, last_entry = session_times(region)
        if not (o + timedelta(minutes=CFG["or_minutes"]) <= n <= last_entry):
            continue
        b = bars.get(t)
        if b is None or b.empty or not quote_ok(b, region)[0]:
            continue
        sess = today_session(b, region, cash_only=False)
        sess = sess[sess.index >= o]
        if strat == "REBOUND":
            sig = rebound(b, sess, region, daily.get(t))
        elif strat == "V0_SHORT":
            sig = orb_short(b, sess, region)
        elif strat in ("V0_LOOSE", "V0", "V0_FEE4", "V0_WIDE"):   # V0 / V0_FEE4 = stesse regole di trade.py (estensione 1,5 ATR)
            sig = orb(b, sess, region, max_ext=LOOSE["max_extension_atr"] if strat == "V0_LOOSE" else None)
        else:
            sig = orb(b, sess, region)
        if not sig:
            continue
        close, stop, target, info = sig
        ccy = quote_currency(b, t)
        side = "short" if strat == "V0_SHORT" else "long"
        if side == "short":
            entry = float(b.attrs.get("bid") or close * (1 - CFG["slippage"]))
        else:
            entry = float(b.attrs.get("ask") or close * (1 + CFG["slippage"]))
        qty = size(entry, abs(close - stop), ccy, min_rr=MIN_RR.get(strat))
        a = CA.analyze(t, "short" if side == "short" else "buy", b, daily.get(t), stop, target, save_chart=False)
        row = dict(day=today().isoformat(), ts=n.isoformat(timespec="seconds"), strategy=strat, ticker=t, region=region,
                   currency=ccy, price=round(close, 4), entry=round(entry, 4), stop=round(stop, 4), target=round(target, 4),
                   qty=qty, qty_diag=size_diag(entry, abs(close - stop), ccy), chart_score=a["score"], chart_verdict=a["verdict"], approved=a["verdict"] == "APPROVE" and qty > 0,
                   bar=str(sess.index[-1]), source=b.attrs.get("source"), info=info,
                   dyn=t not in st_t, side=side, ctx=ctx_for(b, sess, region, close), note="SHADOW: nessun ordine")
        found += 1
        if a["verdict"] != "APPROVE" and strat in ("REBOUND", "ORB_DYN", "V0_LOOSE", "V0_FEE4", "V0_SHORT", "V0_WIDE"):
            # registra comunque il segnale grezzo (serve al conteggio), ma con approved=False; non lo ripete oggi
            pass
        if dry:
            print(json.dumps(row, ensure_ascii=False)); continue
        if strat == "V0":
            row["blocked_by_fees"] = qty <= 0
            append(DSIG, row)          # copia diagnostica della v0: solo per il dibattito, fuori dai totali shadow
            log(f"SHADOW V0 (dibattito) {t} @ {entry:.4f} grafico {a['score']} {a['verdict']} qty {qty}", S)
            continue
        append(SIG, row)
        log(f"SHADOW {strat} {t} @ {entry:.4f} stop {stop:.4f} target {target:.4f} grafico {a['score']} {a['verdict']}", S)
    try:
        found += news_scan(n, bars, done, dry)
    except Exception as e:
        log(f"shadow NEWS_LLM: errore {e}", S)
    if not dry:
        spawn_debate()            # anche senza segnali nuovi: riprende quelli rimasti in attesa
    log(f"shadow: {len(plan)} valutazioni, {found} segnali", S)


def eod(dry=False):
    d = today().isoformat()
    sigs = [r for r in _lines(SIG) if r.get("day") == d]
    done = {(r["strategy"], r["ticker"]) for r in _lines(RES) if r.get("day") == d}
    todo = [r for r in sigs if (r["strategy"], r["ticker"]) not in done]
    tk = sorted({r["ticker"] for r in todo})
    bars = intraday_bars(tk[:20]) if todo else {}
    if len(tk) > 20:                     # V0_WIDE può superare i 20 titoli live: il resto da un batch Yahoo
        try:
            bars = dict(bars); bars.update({t: b for t, b in yf_intraday_bars(tk[20:]).items() if t not in bars})
        except Exception as e:
            log(f"shadow eod: Yahoo non disponibile per {len(tk) - 20} titoli ({e})", S)
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
            if r.get("strategy") == "USLEAD_DAX":
                fl = datetime.combine(today(), dtime(17, 30), ROME)
            fut = b[(b.index > pd.Timestamp(r["bar"])) & (b.index < fl)]
            st, tg, e = r["stop"], r["target"], r["entry"]
            short = (r.get("side") or "long") == "short"
            sg = -1 if short else 1
            risk = sg * (e - st)
            px, why, exit_ts = None, "fine giornata", fl
            import trade_log as TL
            mae, mfe = e, e
            for ts, x in fut.iterrows():
                mae, mfe = TL.update_excursion(mae, mfe, e, x["Low"], x["High"], r.get("side") or "long")
                if (x["High"] >= st) if short else (x["Low"] <= st):
                    px = max(st, x["Open"]) * (1 + CFG["slippage"]) if short else min(st, x["Open"]) * (1 - CFG["slippage"])
                    why, exit_ts = "stop", ts; break
                if (x["Low"] <= tg) if short else (x["High"] >= tg):
                    px, why, exit_ts = (min(tg, x["Open"]) if short else max(tg, x["Open"])), "target", ts; break
                if r.get("strategy") == "USLEAD_DAX":
                    continue                         # niente breakeven (come nel backtest)
                if short and x["Low"] <= e - risk:
                    st = min(st, e - 2 * CFG["fee_per_order"] / q)
                elif not short and x["High"] >= e + risk:
                    st = max(st, e + 2 * CFG["fee_per_order"] / q)
            if px is None and len(fut):
                px = float(fut["Close"].iloc[-1]) * (1 - sg * CFG["slippage"])
                exit_ts = fut.index[-1]
            if px is not None:
                gross = to_eur(sg * q * (px - e), r["currency"]) - float(r.get("spread_cost") or 0)
                fees = 2 * CFG["fee_per_order"]
                pnl = gross - fees
                tax = round(max(pnl, 0) * TAX_RATE, 2)
                res.update(outcome=why, exit=round(px, 4), gross=round(gross, 2), net_ante_tasse=round(pnl, 2),
                           tax_if_gain=tax, qty_used=q, mae=round(mae, 4), mfe=round(mfe, 4))
                if not dry:
                    try:
                        TL.record_close(
                            source="shadow", strategy_id=r.get("strategy") or "SHADOW",
                            symbol=r["ticker"], side=r.get("side") or "long", qty=q,
                            entry_ts=r.get("ts"), entry_price=e, exit_ts=str(exit_ts),
                            exit_price=px, entry_reason=r.get("info") or "", exit_reason=why,
                            fees=fees, gross_pnl_eur=gross, tax_eur=tax, net_pnl_eur=pnl - tax,
                            currency=r.get("currency") or "EUR",
                            mae_price=mae, mfe_price=mfe, excursion_incomplete=False,
                            diag=diag, approved=bool(r.get("approved")),
                        )
                    except Exception as ex:
                        log(f"WARN trade_log shadow non scritto per {r.get('ticker')}: {ex}", S)
        out.append(res)
        if not dry:
            append(RES, res)
    allres = [x for x in _lines(RES) if x.get("day") == d] if not dry else out
    md = [f"# Shadow {today():%d/%m/%Y} – segnali ipotetici, NESSUN ordine (ora di Roma)", "",
          "Strategie non validate dal backtest: REBOUND (rimbalzo VWAP dopo forte calo), ORB_DYN (ORB v0 su candidati dinamici) e "
          "V0_LOOSE (ORB v0 sulla watchlist statica con estensione max 3 ATR e filtro commissioni 1,5x) e "
          "V0_FEE4 (v0 identica alla produzione ma con guadagno al target >= 4x commissioni, cioe' 8 € invece di 6; prova di un giorno).",
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
    md += fee4_lines(allres, d)
    md += short_lines(allres, d)
    md += wide_lines(allres, d)
    ul = [x for x in allres if x.get("strategy") == "USLEAD_DAX"]
    md += ["", "## USLEAD_DAX (S&P 15:30-15:55 -> DAX 16:00-17:25 via KO x5 ipotetico, nessun ordine)", "",
           (f"- USLEAD_DAX: {ul[0].get('side')} {ul[0].get('info')} -> {ul[0].get('outcome')}, netto ante tasse "
            f"{(ul[0].get('net_ante_tasse') or 0):+.2f} € (spread KO incluso)") if ul else "- USLEAD_DAX: nessun segnale oggi"]
    md += a4_lines(dry)
    try:
        import debate
        md += debate.eod_lines(dry)
    except Exception as e:
        md += ["", f"Filtro dibattito: confronto non calcolato ({type(e).__name__}: {e})"]
    if dry:
        print("\n".join(md)); return
    open(os.path.join(REPORTS, f"shadow_{today():%Y-%m-%d}.md"), "w").write("\n".join(md) + "\n")
    log(f"shadow eod: {len(out)} esiti nuovi, totale {tot:+.2f} EUR", S)


def fee4_lines(allres, d):
    """Confronto della prova V0_FEE4 con la v0 in produzione (ledger) e con la copia V0 vista dallo shadow."""
    f4 = [x for x in allres if x.get("strategy") == "V0_FEE4"]
    op = [x for x in f4 if not x.get("diag") and x.get("net_ante_tasse") is not None]
    md = ["", "## Prova V0_FEE4 (v0 con filtro commissioni 4x, nessun ordine)", ""]
    md.append(f"- V0_FEE4: {len(f4)} segnali, {len(op)} operativi (passano grafico e filtro 8 €), "
              f"netto ante tasse {sum(x['net_ante_tasse'] for x in op):+.2f} €")
    v0 = [r for r in _lines(DSIG) if r.get("day") == d and r.get("strategy") == "V0"]
    v0_ok = [r for r in v0 if r.get("chart_verdict") == "APPROVE" and not r.get("blocked_by_fees")]
    md.append(f"- Copia V0 (regole di produzione, filtro 6 €): {len(v0)} segnali, {len(v0_ok)} passano grafico e filtro commissioni")
    prod = []
    try:
        import trade_log as TL
        prod = [r for r in _lines(TL.log_path()) if str(r.get("exit_ts", ""))[:10] == d and r.get("source") == "production"]
    except Exception:
        pass
    md.append(f"- v0 in produzione: {len(prod)} trade chiusi oggi, netto {sum(float(r.get('net_pnl_eur') or 0) for r in prod):+.2f} €")
    return md


def short_lines(allres, d):
    """Lato short in shadow (V0_SHORT) contro la v0 long in produzione."""
    sh = [x for x in allres if x.get("strategy") == "V0_SHORT"]
    op = [x for x in sh if not x.get("diag") and x.get("net_ante_tasse") is not None]
    dg = [x for x in sh if x.get("diag") and x.get("net_ante_tasse") is not None]
    md = ["", "## Lato SHORT V0_SHORT (specchio della v0, nessun ordine)", ""]
    md.append(f"- V0_SHORT: {len(sh)} segnali, {len(op)} operativi (grafico <= -25 e filtro 6 €), "
              f"netto ante tasse {sum(x['net_ante_tasse'] for x in op):+.2f} €"
              + (f"; diagnostici bloccati solo dalle commissioni {len(dg)}, {sum(x['net_ante_tasse'] for x in dg):+.2f} €" if dg else ""))
    return md


def wide_lines(allres, d):
    """V0_WIDE: regole v0 sui titoli dell'universo che la produzione non scansiona (oggi gli USA fuori dalla lista 09:35)."""
    w = [x for x in allres if x.get("strategy") == "V0_WIDE"]
    op = [x for x in w if not x.get("diag") and x.get("net_ante_tasse") is not None]
    regs = "+".join(sorted(CFG.get("wide_regions") or ())) if CFG.get("wide_universe") else "nessuna"
    return ["", f"## V0_WIDE (v0 sui titoli fuori dalla scansione di produzione; produzione larga su: {regs}; nessun ordine)", "",
            f"- V0_WIDE: {len(w)} segnali, {len(op)} operativi (grafico e filtro 6 €), "
            f"netto ante tasse {sum(x['net_ante_tasse'] for x in op):+.2f} €"]


def main():
    dry = "--dry-run" in sys.argv
    if "--a4-sim" in sys.argv:
        a4_sim(sys.argv[sys.argv.index("--a4-sim") + 1]); return
    if "--eod" in sys.argv:
        eod(dry)
    else:
        scan(dry)


if __name__ == "__main__":
    main()
