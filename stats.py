"""Shared stats for report.py / update.py / team_review.py (PAPER)."""
import glob, re
from common import *

def eur(x):  # Italian formatting
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"

def pct(x):
    return f"{x*100:+.2f}%".replace(".", ",")

def trades_df(con, day=None):
    q = "SELECT * FROM trades" + (" WHERE day=?" if day else "") + " ORDER BY id"
    return pd.read_sql_query(q, con, params=(day,) if day else ())

def round_trips(con, day=None):
    """One row per closed trade (SELL joined with its BUY)."""
    t = trades_df(con)
    rows = []
    open_buys = {}
    for _, r in t.iterrows():
        if r.side == "BUY":
            open_buys[r.ticker] = r
        elif r.side == "SELL" and r.ticker in open_buys:
            b = open_buys.pop(r.ticker)
            rows.append(dict(day=r.day, ticker=r.ticker, name=r["name"], setup=b.setup or "ORB",
                             entry_ts=b.ts, exit_ts=r.ts, entry_hour=int(b.ts[11:13]),
                             region=meta(r.ticker)["region"], value=b.value_eur,
                             gross=r.gross_pnl_eur or 0.0, fees=b.fee + r.fee, pnl=r.pnl_eur or 0.0,
                             tax=r.tax_eur or 0.0, net=r.net_pnl_eur or 0.0, exit_reason=r.reason,
                             hold_min=(datetime.fromisoformat(r.ts) - datetime.fromisoformat(b.ts)).total_seconds() / 60,
                             entry_chart=b.chart, exit_chart=r.chart))
    df = pd.DataFrame(rows)
    if day and len(df):
        df = df[df.day == day]
    return df

def exit_kind(reason):
    r = (reason or "").lower()
    if r.startswith("stop"): return "stop loss"
    if r.startswith("take profit"): return "take profit"
    if "grafico" in r: return "uscita da analisi grafica"
    if "limite perdita" in r: return "limite perdita giornaliera"
    return "chiusura fine giornata"

def open_positions_view(con):
    pos = positions(con)
    if not pos: return [], {}
    prices, _ = last_prices([p["ticker"] for p in pos])
    out = []
    for p in pos:
        px = prices.get(p["ticker"], (p["entry_local"], None))[0]
        val = p["qty"] * to_eur(px, p["currency"])
        unreal = val - p["qty"] * p["entry_eur"] - p["entry_fee"] - CFG["fee_per_order"]  # incl. both fees
        out.append(dict(p, last=px, value=val, unreal=unreal))
    return out, prices

def log_reasons(day=None):
    """Parse trade.py log lines '[trade] TICKER: reason' for non-entry diagnostics."""
    files = [os.path.join(LOGS, f"{day}.log")] if day else sorted(glob.glob(os.path.join(LOGS, "*.log")))
    cnt = {}
    for f in files:
        if not os.path.exists(f): continue
        for line in open(f):
            m = re.search(r"\[trade\] [A-Z0-9.\-]+: (.+)$", line)
            if not m: continue
            k = m.group(1).split(":")[0].split("(")[0].strip()
            if k.startswith(("analista grafico", "posizione aperta", "equity")): continue
            cnt[k] = cnt.get(k, 0) + 1
    return dict(sorted(cnt.items(), key=lambda kv: -kv[1]))

def benchmark_day():
    """Intraday buy&hold of the benchmark ETF from today's open to latest price."""
    for t in (CFG["benchmark"], CFG["benchmark_fallback"]):
        b = intraday_bars([t]).get(t)
        if b is None: continue
        s = today_session(b, "EU")
        if len(s) >= 2:
            o, l = float(s["Open"].iloc[0]), float(s["Close"].iloc[-1])
            return dict(ticker=t, open=o, last=l, ret=l / o - 1, ts=s.index[-1])
    return None
