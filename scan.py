#!/usr/bin/env python3
"""Morning scan (PAPER): rank the universe and write today's watchlist.
Run ~09:35 Rome (after EU opening range). Idempotent: keeps today's list unless --force."""
import json, sys
import numpy as np, pandas as pd
from common import *
from news import news_signal, macro_signal

def z(s):
    s = s.astype(float)
    sd = s.std()
    return (s - s.mean()) / sd if sd and sd == sd else s * 0

def main():
    force = "--force" in sys.argv
    if is_weekend() and "--any-day" not in sys.argv:
        log("weekend: no scan", "scan"); return
    with Lock():
        if os.path.exists(watchlist_path()) and not force:
            wl = load_watchlist(); log(f"watchlist already exists for today: {[w['ticker'] for w in wl['items']]}", "scan")
            return
        con = db(); ensure_day(con)
        uni = load_universe()
        tick = [u["ticker"] for u in uni]
        daily = daily_bars(tick, "3mo")
        us = [u["ticker"] for u in uni if u["region"] == "US"]
        pre = yf_intraday_bars(us, period="2d", interval="5m", prepost=True)  # US premarket (Yahoo USD, not LS EUR)
        td = today()
        rows = []
        for u in uni:
            t = u["ticker"]; d = daily.get(t)
            if d is None or len(d) < 25:
                continue
            d = d.copy(); d.index = pd.to_datetime(d.index).date
            has_today = d.index[-1] == td
            hist = d.iloc[:-1] if has_today else d
            prev_close = float(hist["Close"].iloc[-1])
            prev2 = float(hist["Close"].iloc[-2])
            avgvol = float(hist["Volume"].iloc[-20:].mean()) or np.nan
            atr_pct = float(atr(hist).iloc[-1]) / prev_close
            sma20 = float(hist["Close"].iloc[-20:].mean())
            if has_today:
                last = float(d["Close"].iloc[-1]); opn = float(d["Open"].iloc[-1])
                gap = opn / prev_close - 1
                o, c, _ = session_times(u["region"])
                frac = min(max((now() - o).total_seconds() / (c - o).total_seconds(), 0.03), 1)
                rvol = float(d["Volume"].iloc[-1]) / (avgvol * frac) if avgvol else np.nan
            else:
                last = prev_close; gap = 0.0
                p = pre.get(t)
                if p is not None and len(p) and p.index[-1].date() == td:
                    last = float(p["Close"].iloc[-1]); gap = last / prev_close - 1
                rvol = float(hist["Volume"].iloc[-1]) / avgvol if avgvol else np.nan
            rows.append(dict(ticker=t, name=u["name"], region=u["region"], currency=u["currency"],
                             last=last, prev_close=prev_close, gap=gap, mom1d=prev_close / prev2 - 1,
                             mom5d=prev_close / float(hist["Close"].iloc[-6]) - 1, rvol=rvol,
                             atr_pct=atr_pct, trend=1.0 if prev_close > sma20 else 0.0, live_today=has_today))
        df = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["rvol", "atr_pct"])
        df = df[df["atr_pct"] >= 0.012]
        ns = {t: news_signal(t) for t in df["ticker"]}
        df["news"] = df["ticker"].map(lambda t: ns[t]["score"])
        df["news_n"] = df["ticker"].map(lambda t: ns[t]["count"])
        df = df[df["news"] > -0.4]  # strongly negative news -> no long candidates  # need range: 2 EUR fees on ~300 EUR = 0.67% hurdle
        df["score"] = (1.0 * z(df["gap"].clip(-0.08, 0.08)) + 0.5 * z(df["gap"].abs().clip(0, 0.08))
                       + 0.75 * z(df["mom1d"].clip(-0.1, 0.1)) + 1.0 * z(df["rvol"].clip(0, 5))
                       + 0.75 * z(df["atr_pct"].clip(0, 0.08)) + 0.5 * df["trend"]
                       + 1.5 * df["news"] + 0.25 * (df["news_n"] >= 5))   # news catalyst boost
        df = df.sort_values("score", ascending=False)
        pick = pd.concat([df[df.region == "EU"].head(CFG["watchlist_eu"]),
                          df[df.region == "US"].head(CFG["watchlist_us"])])
        items = []
        for _, r in pick.iterrows():
            why = (f"gap {r.gap:+.2%}, ieri {r.mom1d:+.2%}, 5gg {r.mom5d:+.2%}, volume relativo {r.rvol:.1f}x, "
                   f"ATR {r.atr_pct:.2%}, {'sopra' if r.trend else 'sotto'} la media 20gg, "
                   f"news {r.news:+.2f} ({int(r.news_n)} notizie 24h)" + (f": {ns[r.ticker]['top']}" if ns[r.ticker]["top"] else ""))
            items.append(dict(ticker=r.ticker, name=r["name"], region=r.region, currency=r.currency,
                              score=round(float(r.score), 3), last=round(float(r.last), 4), rationale=why))
        wl = dict(date=td.isoformat(), macro_news=macro_signal(), created=now().isoformat(timespec="seconds"),
                  universe_scanned=int(len(df)), items=items)
        with open(watchlist_path(), "w") as f:
            json.dump(wl, f, indent=2, ensure_ascii=False)
        md = [f"# Watchlist {td:%d/%m/%Y} (creata {now():%H:%M} ora di Roma)", ""]
        for i, it in enumerate(items, 1):
            md.append(f"{i}. **{it['name']}** ({it['ticker']}, {it['region']}) punteggio {it['score']}: {it['rationale']}")
        with open(os.path.join(REPORTS, f"watchlist_{td:%Y-%m-%d}.md"), "w") as f:
            f.write("\n".join(md) + "\n")
        print("\n".join(md))
        log(f"watchlist written: {[i['ticker'] for i in items]} (scanned {len(df)})", "scan")

if __name__ == "__main__":
    main()
