#!/usr/bin/env python3
"""Watchlist dinamica intraday (PAPER). Rescan dell'intero universo ogni 30 minuti (scheduler :00/:30).

Regole pre-registrate (R&D reports/preregistration_2026-11-12.md), NON ottimizzate:
- EU dalle 09:30, USA dall'apertura 15:30 + 30 min di opening range (di solito 16:00 Roma), ultimo rescan 21:00;
- candidato se |variazione vs chiusura di ieri| >= max(2%, 1 x ATR14 giornaliero %) E volume relativo >= 1,5;
- oppure giudizio NON scaduto in data/news_llm.json con |impact| >= 0,5 e confidence >= 0,6 (solo input, non segnale);
- massimo 5 nuovi titoli per rescan, un titolo aggiunto resta fino a fine giornata.
Uso dei candidati (12/11/2026): SOLO shadow (shadow.py). trade.py NON li usa per ordini finché una strategia
che li usa non è validata walk-forward (S1 ORB su watchlist dinamica peggiorava il netto).
Fonte: Yahoo 5m in un'unica richiesta batch per rescan (UE ~15 min di ritardo, va bene per selezionare candidati);
daily in cache una volta al giorno. Non scrive mai sul ledger.
Uso: ./run.sh rescan   |  python3 rescan.py --dry-run (stampa senza scrivere)  |  --any-time (ignora orari, per test)
"""
import json, os, sys
import numpy as np, pandas as pd
from common import (log, now, today, is_weekend, session_times, load_universe, daily_bars, yf_intraday_bars,
                    atr, DATA, REPORTS, CFG)

DWL = dict(min_move=0.02, move_atr=1.0, min_rvol=1.5, max_add=5, news_impact=0.5, news_conf=0.6,
           eu_from=(9, 30), last=(21, 0))
OUT_DIR = os.environ.get("PT_DWL_DIR", DATA)
S = "rescan"


def dyn_path(d=None):
    return os.path.join(OUT_DIR, f"watchlist_dyn_{(d or today()):%Y-%m-%d}.json")


ADD_LOG = os.path.join(os.environ.get("PT_LOGS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")),
                       "dwl_additions.log")


class _DynLock:
    """Lock dedicato al file della watchlist dinamica (rescan.py e news.py possono scriverlo entrambi)."""
    def __enter__(self):
        import fcntl
        self.f = open(os.path.join(OUT_DIR, ".watchlist_dyn.lock"), "w"); fcntl.flock(self.f, fcntl.LOCK_EX); return self
    def __exit__(self, *a):
        import fcntl
        fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()


def add_items(new, scan_info=None, dry=False):
    """Aggiunge candidati (dict con ticker/name/region/currency/added_at/source/rationale) alla watchlist dinamica
    di oggi, senza duplicati, in modo atomico. Ogni aggiunta va in logs/dwl_additions.log. Ritorna i titoli aggiunti."""
    with _DynLock():
        prev = {"date": today().isoformat(), "items": [], "scans": []}
        if os.path.exists(dyn_path()):
            try:
                prev = json.load(open(dyn_path()))
            except Exception:
                pass
        have = {i["ticker"] for i in prev["items"]}
        new = [x for x in new if x["ticker"] not in have]
        if dry:
            return [x["ticker"] for x in new]
        prev["items"] += new
        if scan_info:
            prev["scans"].append(scan_info)
        prev["updated"] = now().isoformat(timespec="seconds")
        tmp = dyn_path() + ".tmp"
        json.dump(prev, open(tmp, "w"), indent=1, ensure_ascii=False); os.replace(tmp, dyn_path())
        with open(ADD_LOG, "a") as f:
            for x in new:
                f.write(f"{now().isoformat(timespec='seconds')} ADD {x['ticker']} fonte={x.get('source')} motivo: {x.get('rationale')}\n")
        md = [f"# Watchlist dinamica {today():%d/%m/%Y} (aggiornata {now():%H:%M} ora di Roma) – solo candidati, usati in SHADOW", ""]
        for i, it in enumerate(prev["items"], 1):
            md.append(f"{i}. {it['added_at']} **{it['name']}** ({it['ticker']}, {it['region']}) [{it.get('source')}]: {it['rationale']}")
        open(os.path.join(REPORTS, f"watchlist_dyn_{today():%Y-%m-%d}.md"), "w").write("\n".join(md) + "\n")
        return [x["ticker"] for x in new]


def load_dyn(d=None):
    """Candidati dinamici di oggi (lista di dict) o [] se assenti."""
    try:
        return json.load(open(dyn_path(d))).get("items", [])
    except Exception:
        return []


def _aware(s):
    try:
        t = pd.Timestamp(s)
        return t.tz_localize("Europe/Rome") if t.tzinfo is None else t
    except Exception:
        return None


def strong_news(n=None):
    """Giudizi LLM non scaduti e forti: {ticker: dict(impact, confidence, rationale, expires_at)}."""
    n = n or now()
    try:
        j = json.load(open(os.path.join(DATA, "news_llm.json")))
    except Exception:
        return {}
    out = {}
    for t in j.get("tickers", []):
        exp = _aware(t.get("expires_at"))
        if exp is None or exp <= pd.Timestamp(n):
            continue
        if abs(float(t.get("impact") or 0)) >= DWL["news_impact"] and float(t.get("confidence") or 0) >= DWL["news_conf"]:
            out[t["ticker"]] = dict(impact=t.get("impact"), confidence=t.get("confidence"),
                                    rationale=t.get("rationale", ""), expires_at=t.get("expires_at"))
    return out


def regions_open(n):
    hm = (n.hour, n.minute)
    regs = []
    if DWL["eu_from"] <= hm <= DWL["last"]:
        regs.append("EU")
    us_from = session_times("US", n.date())[0] + pd.Timedelta(minutes=CFG["or_minutes"])
    if n >= us_from and hm <= DWL["last"]:
        regs.append("US")
    return regs


def daily_cached(tickers):
    p = os.path.join(OUT_DIR, f".dwl_daily_{today():%Y-%m-%d}.pkl")
    if os.path.exists(p):
        try:
            return pd.read_pickle(p)
        except Exception:
            pass
    d = daily_bars(tickers, "3mo")
    try:
        pd.to_pickle(d, p)
    except Exception:
        pass
    return d


def main():
    dry = "--dry-run" in sys.argv
    anytime = "--any-time" in sys.argv
    n = now()
    if is_weekend() and not anytime:
        log("weekend: niente rescan", S); return
    regs = regions_open(n) if not anytime else ["EU", "US"]
    if not regs:
        log(f"fuori dalle finestre di rescan (EU 09:30-21:00, USA da apertura+30 min): nulla da fare", S); return
    uni = [u for u in load_universe() if u["region"] in regs]
    tick = [u["ticker"] for u in uni]
    prev = {"date": today().isoformat(), "items": [], "scans": []}
    if os.path.exists(dyn_path()):
        try:
            prev = json.load(open(dyn_path()))
        except Exception:
            pass
    have = {i["ticker"] for i in prev["items"]}
    daily = daily_cached([u["ticker"] for u in load_universe()])
    bars = yf_intraday_bars(tick, period="1d", interval="5m")
    news = strong_news(n)
    rows, scanned = [], 0
    for u in uni:
        t = u["ticker"]
        if t in have:
            continue
        d = daily.get(t); b = bars.get(t)
        if d is None or len(d) < 25:
            continue
        dd = d.copy(); dd.index = pd.to_datetime(dd.index).date
        hist = dd[dd.index < today()]
        if len(hist) < 25:
            continue
        pc = float(hist["Close"].iloc[-1]); av = float(hist["Volume"].iloc[-20:].mean())
        a = float(atr(hist).iloc[-1])
        if not pc or a != a:
            continue
        atr_d = a / pc
        o, c, _ = session_times(u["region"])
        move = rvol = None
        if b is not None and len(b):
            sess = b[(b.index >= o) & (b.index < c) & (b.index.date == today())]
            if len(sess):
                scanned += 1
                frac = min(max((n - o).total_seconds() / (c - o).total_seconds(), 0.03), 1)
                rvol = float(sess["Volume"].fillna(0).sum()) / (av * frac) if av else 0.0
                move = float(sess["Close"].iloc[-1]) / pc - 1
        price_ok = move is not None and abs(move) >= max(DWL["min_move"], DWL["move_atr"] * atr_d) and rvol >= DWL["min_rvol"]
        nw = news.get(t)
        if not price_ok and not nw:
            continue
        sc = (abs(move) / atr_d + 0.5 * min(rvol, 5)) if price_ok else 0.0
        reason = []
        if price_ok:
            reason.append(f"movimento {move:+.2%} (soglia {max(DWL['min_move'], atr_d):.2%}), volume relativo {rvol:.1f}x")
        if nw:
            reason.append(f"notizia forte impact {nw['impact']:+.2f} conf {nw['confidence']:.2f} (scade {nw['expires_at']})")
        rows.append((sc + (1.0 if nw else 0.0), dict(
            ticker=t, name=u["name"], region=u["region"], currency=u["currency"],
            added_at=n.strftime("%H:%M"), move=None if move is None else round(move, 4),
            rvol=None if rvol is None else round(rvol, 2), atr_d=round(atr_d, 4),
            source="+".join(x for x, f in (("prezzo/volume", price_ok), ("notizie", bool(nw))) if f),
            news_impact=nw["impact"] if nw else None, rationale="; ".join(reason))))
    rows.sort(key=lambda x: -x[0])
    new = [r[1] for r in rows[:DWL["max_add"]]]
    info = dict(at=n.isoformat(timespec="seconds"), regions=regs, scanned=scanned, candidates=len(rows),
                added=[x["ticker"] for x in new])
    msg = f"rescan {n:%H:%M} {'+'.join(regs)}: {scanned} titoli con barre, {len(rows)} candidati, aggiunti {[x['ticker'] for x in new]}"
    if dry:
        print(msg); print(json.dumps(new, indent=1, ensure_ascii=False)); return
    add_items(new, info)
    log(msg, S); print(msg)


if __name__ == "__main__":
    main()
