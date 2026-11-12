#!/usr/bin/env python3
"""Chart / technical-analysis analyst (PAPER). Multi-timeframe study of one ticker:
daily trend (SMA20/50, RSI), 15m (EMA9/21, MACD, RSI), 5m (VWAP, MACD, RSI), volume,
support/resistance (prev-day H/L, 20-day high/low, today's high/low), candlestick context.
Returns score (-100..+100, positive = bullish) and verdict. trade.py requires APPROVE for buys
and asks for a verdict before every sell decision. Saves a PNG chart under charts/YYYY-MM-DD/.
CLI: python3 chart_analysis.py TICKER [--side buy|sell] [--no-chart]"""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import mplfinance as mpf
from common import *

CHARTS = os.environ.get("PT_CHARTS", os.path.join(BASE, "charts"))
APPROVE_BUY = 25     # min score to approve a long entry
EXIT_SELL = -30      # score at/below which an open long should be exited early

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def macd(c):
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sig = m.ewm(span=9, adjust=False).mean()
    return m, sig, m - sig

def resample15(b):
    return b.resample("15min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()

def analyze(ticker, side="buy", bars5=None, daily=None, stop=None, target=None, save_chart=True):
    m = meta(ticker); region = m["region"]
    if bars5 is None:
        bars5 = intraday_bars([ticker]).get(ticker)
    if daily is None:
        daily = daily_bars([ticker], "6mo").get(ticker)
    R = []; score = 0
    def add(pts, txt):
        nonlocal score; score += pts; R.append(f"{pts:+d} {txt}")
    if bars5 is None or len(bars5) < 30 or daily is None or len(daily) < 50:
        return dict(ticker=ticker, side=side, score=-100, verdict="REJECT", reasons=["dati insufficienti"], chart=None)
    sess = today_session(bars5, region)
    if len(sess) < 3:
        sess = bars5[bars5.index.date == bars5.index[-1].date()]
    c5 = bars5["Close"]; last = float(c5.iloc[-1])
    a5 = float(atr(bars5).iloc[-1]) or last * 0.002
    # ---- daily trend
    d = daily.copy(); d.index = pd.to_datetime(d.index).date
    hist = d[d.index < today()] if d.index[-1] == today() else d
    dc = hist["Close"]; sma20, sma50 = dc.rolling(20).mean().iloc[-1], dc.rolling(50).mean().iloc[-1]
    add(10 if last > sma20 else -10, f"daily: prezzo {'sopra' if last > sma20 else 'sotto'} SMA20 ({sma20:.2f})")
    add(10 if sma20 > sma50 else -10, f"daily: SMA20 {'>' if sma20 > sma50 else '<'} SMA50 (trend {'rialzista' if sma20 > sma50 else 'ribassista'})")
    drsi = float(rsi(dc).iloc[-1])
    if drsi > 75: add(-10, f"daily RSI {drsi:.0f} ipercomprato")
    elif drsi < 30: add(-5, f"daily RSI {drsi:.0f} debole")
    else: R.append(f"+0 daily RSI {drsi:.0f} neutro")
    # ---- 15m
    b15 = resample15(bars5)
    e9, e21 = b15["Close"].ewm(span=9).mean().iloc[-1], b15["Close"].ewm(span=21).mean().iloc[-1]
    add(10 if e9 > e21 else -10, f"15m: EMA9 {'>' if e9 > e21 else '<'} EMA21")
    h15 = macd(b15["Close"])[2]
    add(10 if h15.iloc[-1] > 0 else -10, f"15m: MACD istogramma {'positivo' if h15.iloc[-1] > 0 else 'negativo'}")
    r15 = float(rsi(b15["Close"]).iloc[-1])
    if r15 > 78: add(-15, f"15m RSI {r15:.0f} ipercomprato")
    elif 50 <= r15 <= 70: add(10, f"15m RSI {r15:.0f} momentum sano")
    elif r15 < 40: add(-10, f"15m RSI {r15:.0f} debole")
    else: R.append(f"+0 15m RSI {r15:.0f}")
    # ---- 5m
    vw = float(vwap(sess).iloc[-1]) if len(sess) else last
    add(10 if last > vw else -10, f"5m: prezzo {'sopra' if last > vw else 'sotto'} VWAP ({vw:.2f})")
    h5 = macd(c5)[2]
    add(5 if h5.iloc[-1] > h5.iloc[-2] else -5, f"5m: MACD {'in accelerazione' if h5.iloc[-1] > h5.iloc[-2] else 'in rallentamento'}")
    r5 = float(rsi(c5).iloc[-1])
    if r5 > 80: add(-10, f"5m RSI {r5:.0f} ipercomprato, rischio pullback")
    # ---- volume
    v = bars5["Volume"].fillna(0)
    if v.iloc[-20:].sum() > 0:
        vr = float(v.iloc[-3:].mean() / max(v.iloc[-23:-3].mean(), 1))
        up = c5.iloc[-1] > c5.iloc[-4]
        if vr >= 1.2 and up: add(10, f"volume {vr:.1f}x la media sul rialzo (conferma)")
        elif vr >= 1.2 and not up: add(-10, f"volume {vr:.1f}x la media sul ribasso (distribuzione)")
        elif vr < 0.7: add(-5, f"volume basso ({vr:.1f}x), movimento poco convinto")
        else: R.append(f"+0 volume nella norma ({vr:.1f}x)")
    # ---- support / resistance
    pdh, pdl = float(hist["High"].iloc[-1]), float(hist["Low"].iloc[-1])
    h20, l20 = float(hist["High"].iloc[-20:].max()), float(hist["Low"].iloc[-20:].min())
    levels = {"massimo di ieri": pdh, "minimo di ieri": pdl, "massimo 20gg": h20, "minimo 20gg": l20}
    if len(sess): levels["massimo di oggi"] = float(sess["High"].iloc[:-1].max()) if len(sess) > 1 else float(sess["High"].max())
    res = {k: x for k, x in levels.items() if x > last}
    sup = {k: x for k, x in levels.items() if x <= last}
    if res:
        k, x = min(res.items(), key=lambda kv: kv[1])
        if (x - last) < 0.75 * a5 * 3: add(-15, f"resistenza vicina: {k} {x:.2f} ({(x/last-1):+.2%})")
        else: R.append(f"+0 prossima resistenza {k} {x:.2f} ({(x/last-1):+.2%})")
    else:
        add(5, "nessuna resistenza sopra (massimi)")
    for k in ("massimo di ieri", "massimo 20gg"):
        lv = levels[k]
        if last > lv and float(c5.iloc[-4]) <= lv * 1.002:
            add(10, f"rottura recente del {k} ({lv:.2f})")
    if sup:
        k, x = max(sup.items(), key=lambda kv: kv[1]); R.append(f"+0 supporto più vicino {k} {x:.2f} ({(x/last-1):+.2%})")
    # ---- candlestick context (last 2 x 5m)
    o1, h1, l1, c1 = [float(bars5[k].iloc[-1]) for k in ("Open", "High", "Low", "Close")]
    o0, c0 = float(bars5["Open"].iloc[-2]), float(bars5["Close"].iloc[-2])
    rng = max(h1 - l1, 1e-9); body = abs(c1 - o1)
    if (h1 - max(o1, c1)) > 2 * body and (h1 - max(o1, c1)) / rng > 0.5: add(-10, "candela con lunga ombra superiore (rifiuto/shooting star)")
    elif c1 > o1 and c0 < o0 and c1 >= o0 and o1 <= c0: add(10, "engulfing rialzista")
    elif c1 < o1 and c0 > o0 and c1 <= o0 and o1 >= c0: add(-10, "engulfing ribassista")
    elif c1 > o1 and (h1 - c1) / rng < 0.2 and body / rng > 0.6: add(5, "candela rialzista piena, chiusura sui massimi")
    elif body / rng < 0.1: R.append("+0 doji (indecisione)")
    score = int(max(-100, min(100, score)))
    if side == "buy":
        verdict = "APPROVE" if score >= APPROVE_BUY else "REJECT"
    else:  # sell decision for an open long: EXIT if chart turned clearly bearish
        verdict = "EXIT" if score <= EXIT_SELL else "HOLD"
    chart = None
    if save_chart:
        try:
            chart = save_png(ticker, side, bars5, sess, levels, stop, target, score, verdict)
        except Exception as e:
            R.append(f"(grafico non salvato: {e})")
    return dict(ticker=ticker, side=side, score=score, verdict=verdict, reasons=R, chart=chart,
                last=last, vwap=vw, atr5=a5)

def save_png(ticker, side, bars5, sess, levels, stop, target, score, verdict):
    day = today().isoformat()
    out = os.path.join(CHARTS, day); os.makedirs(out, exist_ok=True)
    plot = bars5.iloc[-120:].copy()
    plot.index = plot.index.tz_localize(None)
    s = sess.copy(); s.index = s.index.tz_localize(None)
    vw = vwap(s).reindex(plot.index) if len(s) else pd.Series(np.nan, index=plot.index)
    e9 = plot["Close"].ewm(span=9).mean(); e21 = plot["Close"].ewm(span=21).mean()
    r = rsi(plot["Close"]); mline, msig, mh = macd(plot["Close"])
    ap = [mpf.make_addplot(e9, color="tab:blue", width=0.8), mpf.make_addplot(e21, color="tab:orange", width=0.8),
          mpf.make_addplot(r, panel=2, color="purple", ylabel="RSI", ylim=(0, 100)),
          mpf.make_addplot(mh, panel=3, type="bar", color="gray", ylabel="MACD"),
          mpf.make_addplot(mline, panel=3, color="tab:blue"), mpf.make_addplot(msig, panel=3, color="tab:red")]
    if vw.notna().any():
        ap.insert(0, mpf.make_addplot(vw, color="black", linestyle="--", width=1))
    lo, hi = plot["Low"].min(), plot["High"].max(); pad = (hi - lo) * 0.5
    hl = [x for x in levels.values() if lo - pad <= x <= hi + pad]; cols = ["gray"] * len(hl)
    if stop: hl.append(stop); cols.append("red")
    if target: hl.append(target); cols.append("green")
    path = os.path.join(out, f"{now():%H%M}_{ticker}_{side}.png")
    mpf.plot(plot, type="candle", style="yahoo", volume=True, addplot=ap, panel_ratios=(4, 1, 1, 1),
             hlines=dict(hlines=hl, colors=cols, linestyle=":", linewidths=0.8) if hl else None,
             title=f"{ticker} 5m  {side.upper()} score {score} -> {verdict}", savefig=dict(fname=path, dpi=90),
             figsize=(11, 8), warn_too_much_data=10000)
    return os.path.relpath(path, BASE) if path.startswith(BASE) else path

def record(con, a, acted=0):
    con.execute("INSERT INTO analyses(ts,day,ticker,side,score,verdict,reasons,chart,acted) VALUES(?,?,?,?,?,?,?,?,?)",
                (now().isoformat(timespec="seconds"), today().isoformat(), a["ticker"], a["side"], a["score"],
                 a["verdict"], " | ".join(a["reasons"]), a["chart"], acted))
    con.commit()

if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "SAP.DE"
    side = sys.argv[sys.argv.index("--side") + 1] if "--side" in sys.argv else "buy"
    a = analyze(t, side, save_chart="--no-chart" not in sys.argv)
    print(f"{t} {side}: score {a['score']} -> {a['verdict']}")
    for r in a["reasons"]: print("  ", r)
    print("grafico:", a["chart"])
