"""Shared config, market data, ledger and risk rules for the PAPER trading system.
PAPER ONLY: no broker connection exists anywhere in this code."""
import csv, fcntl, json, math, os, sqlite3, sys, warnings
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")
import pandas as pd
import yfinance as yf

ROME = ZoneInfo("Europe/Rome")
NY = ZoneInfo("America/New_York")
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
REPORTS = os.environ.get("PT_REPORTS", os.path.join(BASE, "reports"))
LOGS = os.environ.get("PT_LOGS", os.path.join(BASE, "logs"))
DB = os.environ.get("PT_DB", os.path.join(DATA, "ledger.sqlite"))  # PT_DB=/tmp/x.sqlite for tests
LOCK_PATH = os.environ.get("PT_LOCK", os.path.join(DATA, ".lock"))  # PT_LOCK=/tmp/x.lock so tests don't block the live bot
for d in (DATA, REPORTS, LOGS):
    os.makedirs(d, exist_ok=True)

# ---------------- configuration / risk rules ----------------
CFG = dict(
    start_cash=1000.0,
    fee_per_order=1.0,          # Trade Republic external cost per order
    slippage=0.0005,            # 0.05% adverse slippage on every simulated fill
    risk_per_trade=0.02,        # max 2% of equity at risk (stop distance x qty + fees)
    max_positions=3,
    max_position_pct=0.30,      # max 30% of equity per position
    min_position_eur=200.0,     # below this the 2 EUR round-trip fee (>1%) kills the edge
    min_reward_vs_fees=3.0,     # expected gain at target must be >= 3x round-trip fees
    daily_loss_limit=-0.03,     # -3% vs start-of-day equity -> flatten & halt for the day
    or_minutes=30,              # opening range length
    atr_stop_mult=1.5,          # stop = max(OR low, entry - 1.5*ATR(5m,14))
    min_stop_pct=0.004,         # stop at least 0.4% away (noise)
    max_stop_pct=0.03,
    reward_r=2.0,               # take profit at 2R
    breakeven_at_r=1.0,         # move stop to breakeven once +1R reached
    max_extension_atr=1.5,      # don't chase: close <= OR high + 1.5*ATR
    fractional=True,            # TR allows fractional/euro-amount orders on many stocks; set False for whole shares           # skip ticker if latest bar older than this (holiday/halt)
    watchlist_eu=5, watchlist_us=3,
    benchmark="EXS1.DE",        # iShares Core DAX ETF (EUR)
    benchmark_fallback="^GDAXI",
)

TR_WINDOW = (time(7, 30), time(22, 0))   # Trade Republic hours (Rome). LS itself quotes until 23:00.
FEED_DELAY = {"EU": 15, "US": 0}          # yfinance fallback delay (min): EU ~15 min, US ~real-time
LS_FEED_DELAY_MIN = 1                     # live LS page quote ~20-40s; chart fallback still << 15 min
MAX_EXTRA_STALE = 15                      # skip a name if its newest quote is >this older than the feed delay
# Cash-session times (Xetra / NYSE). Opening-range is the first or_minutes of this window.
# last_entry / flatten use the LS/TR window now that we have live quotes into the evening.
SESSIONS = {
    "EU": dict(tz=ROME, open=time(9, 0), close=time(17, 30), last_entry=time(21, 15), flatten=time(21, 50)),
    "US": dict(tz=NY, open=time(9, 30), close=time(16, 0), last_entry=time(21, 15), flatten=time(21, 50)),
}
FINAL_FLATTEN = time(21, 50)              # everything flat by 21:50 Rome, before LS closes at 22:00
TAX_RATE = 0.26                           # Italian capital gains tax (regime amministrato)

def now():
    return datetime.now(ROME)

def today():
    return now().date()

def is_weekend(d=None):
    return (d or today()).weekday() >= 5

def session_times(region, d=None):
    """Return (open, close, last_entry) as Rome-aware datetimes for date d."""
    d = d or today()
    s = SESSIONS[region]
    tz = s["tz"]
    o = datetime.combine(d, s["open"], tz).astimezone(ROME)
    c = datetime.combine(d, s["close"], tz).astimezone(ROME)
    le = datetime.combine(d, s["last_entry"], ROME)
    return o, c, le

def flatten_time(region, d=None):
    return datetime.combine(d or today(), SESSIONS[region]["flatten"], ROME)

def log(msg, script="system"):
    line = f"{now():%Y-%m-%d %H:%M:%S} [{script}] {msg}"
    print(line)
    with open(os.path.join(LOGS, f"{today():%Y-%m-%d}.log"), "a") as f:
        f.write(line + "\n")

class Lock:
    """Process lock so overlapping scheduled runs never corrupt the ledger."""
    def __enter__(self):
        self.f = open(LOCK_PATH, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self
    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()

# ---------------- universe ----------------
def load_universe():
    with open(os.path.join(BASE, "universe.csv")) as f:
        return list(csv.DictReader(f))

def meta(ticker):
    for r in load_universe():
        if r["ticker"] == ticker:
            return r
    return dict(name=ticker, ticker=ticker, region="EU", currency="EUR", isin="")

# ---------------- market data ----------------
def _split(df, tickers):
    out = {}
    for t in tickers:
        try:
            x = df[t] if isinstance(df.columns, pd.MultiIndex) else df
            x = x.dropna(subset=["Close"])
            if len(x):
                out[t] = x
        except KeyError:
            pass
    return out

def daily_bars(tickers, period="3mo"):
    df = yf.download(list(tickers), period=period, interval="1d", progress=False,
                     group_by="ticker", auto_adjust=False, threads=True)
    return _split(df, tickers)

def yf_intraday_bars(tickers, period="5d", interval="5m", prepost=False):
    """Yahoo Finance bars only (used for FX, the LS fallback, and the morning US pre-market scan)."""
    tickers = list(tickers)
    if not tickers:
        return {}
    df = yf.download(tickers, period=period, interval=interval, progress=False,
                     group_by="ticker", auto_adjust=False, threads=True, prepost=prepost)
    out = _split(df, tickers)
    for t, x in out.items():
        idx = x.index
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        x.index = idx.tz_convert(ROME)
        m = meta(t)
        attrs = dict(getattr(x, "attrs", {}) or {})
        attrs.update(source="yfinance", currency=m.get("currency") or "EUR", last_ts=x.index[-1])
        x.attrs = attrs
    return out

def _merge_ls_bars(yf_df, ls_df, row):
    """Today's bars (LS, EUR) plus previous days from yfinance. US prior days converted to EUR."""
    prior = None
    if yf_df is not None and len(yf_df):
        y = yf_df.copy()
        day = today()
        prior = y[[i.astimezone(ROME).date() < day for i in y.index]].copy()
        if len(prior) and row.get("currency") == "USD":
            fx = eurusd()
            for col in ("Open", "High", "Low", "Close"):
                prior[col] = prior[col] / fx
        if prior is not None and not prior.empty:
            prior = prior[~prior.index.isin(ls_df.index)]
            if "ls_volume" in ls_df.columns and "ls_volume" not in prior.columns:
                prior["ls_volume"] = 0.0
        else:
            prior = None
    if prior is not None and len(prior):
        merged = pd.concat([prior, ls_df]).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
    else:
        merged = ls_df
    merged.attrs = dict(ls_df.attrs)
    return merged

def intraday_bars(tickers, period="5d", interval="5m", prepost=False, use_ls=True):
    """Primary: LS Exchange live mid/bid/ask (EUR, typically ~20-40s) plus 1m mid chart.

    Previous days' 5m bars still come from yfinance (LS public chart is the current session
    only); they are spliced behind today's LS bars. US Yahoo bars are converted to EUR so
    the series matches LS / Trade Republic. Pass use_ls=False to force Yahoo (see scan.py).
    """
    tickers = list(tickers)
    yf_bars = yf_intraday_bars(tickers, period=period, interval=interval, prepost=prepost)
    if not use_ls or not tickers:
        return yf_bars
    uni = {r["ticker"]: r for r in load_universe()}
    want = [uni[t] for t in tickers if t in uni]
    if not want:
        return yf_bars
    try:
        import marketdata as MD
        ls_iv = "5min" if str(interval).startswith("5") else "1min"
        ls_bars = MD.fetch_ls_for_tickers(want, interval=ls_iv, yf_bars=yf_bars)
    except Exception as e:
        log(f"LS feed unavailable, using yfinance: {e}", "marketdata")
        return yf_bars
    out = dict(yf_bars)
    for t, ls in ls_bars.items():
        out[t] = _merge_ls_bars(out.get(t), ls, uni[t])
    if ls_bars:
        summary = MD.last_delay_summary()
        if summary and (_ls_log_at is None or (now() - _ls_log_at).total_seconds() > 30):
            log(summary, "marketdata")
            globals()["_ls_log_at"] = now()
    return out

_fx_cache = {}
_ls_log_at = None
def eurusd():
    """Live-ish EURUSD (USD per 1 EUR) from Yahoo (EURUSD=X). Always yfinance, never LS."""
    if "v" in _fx_cache:
        return _fx_cache["v"]
    b = yf_intraday_bars(["EURUSD=X"], period="5d", interval="5m").get("EURUSD=X")
    if b is None or b.empty:
        b = daily_bars(["EURUSD=X"], period="5d").get("EURUSD=X")
    v = float(b["Close"].iloc[-1])
    _fx_cache["v"] = v
    return v

def to_eur(price, currency):
    return price / eurusd() if currency == "USD" else price

def quote_currency(bars, ticker):
    """Currency of the prices in `bars` (LS is always EUR, including US names)."""
    if bars is not None and hasattr(bars, "attrs") and bars.attrs.get("currency"):
        return bars.attrs["currency"]
    return meta(ticker).get("currency") or "EUR"

def today_session(bars, region, d=None, cash_only=False):
    """Session bars of date d (Rome). Default is the LS/TR window 07:30-22:00.
    cash_only=True restricts to the primary exchange session (EU 09:00-17:30, US 15:30-22:00)."""
    d = d or today()
    if cash_only:
        o, c, _ = session_times(region, d)
        return bars[(bars.index >= o) & (bars.index < c)]
    start = datetime.combine(d, TR_WINDOW[0], ROME)
    end = datetime.combine(d, TR_WINDOW[1], ROME)
    return bars[(bars.index >= start) & (bars.index < end)]

def atr(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def vwap(df):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    v = df["Volume"].fillna(0)
    if v.sum() <= 0:
        return tp.expanding().mean()
    return (tp * v).cumsum() / v.cumsum().replace(0, math.nan)

def bar_age_min(bars):
    """Minutes since the last quote (LS last_ts) or, for yfinance, the end of the latest 5m bar."""
    ts = bars.attrs.get("last_ts") if hasattr(bars, "attrs") else None
    if ts is not None:
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(ROME)
        return (now() - ts.astimezone(ROME)).total_seconds() / 60
    last_end = bars.index[-1] + timedelta(minutes=5)
    return (now() - last_end).total_seconds() / 60

# ---------------- ledger (SQLite) ----------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS positions(
  ticker TEXT PRIMARY KEY, name TEXT, region TEXT, currency TEXT, qty REAL,
  entry_ts TEXT, entry_local REAL, entry_fx REAL, entry_eur REAL, entry_fee REAL,
  stop_local REAL, initial_stop_local REAL, target_local REAL, risk_eur REAL, rationale TEXT, entry_bar TEXT, setup TEXT, chart_score REAL, entry_chart TEXT);
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, ticker TEXT, name TEXT, side TEXT,
  qty REAL, price_local REAL, currency TEXT, fx REAL, price_eur REAL, value_eur REAL,
  fee REAL, pnl_eur REAL, reason TEXT, setup TEXT, gross_pnl_eur REAL, tax_eur REAL,
  loss_credit_used REAL, net_pnl_eur REAL, chart TEXT);
CREATE TABLE IF NOT EXISTS tax_losses(id INTEGER PRIMARY KEY AUTOINCREMENT, origin_day TEXT, expires TEXT,
  amount REAL, remaining REAL, ticker TEXT);
CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, ticker TEXT,
  side TEXT, score REAL, verdict TEXT, reasons TEXT, chart TEXT, acted INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS days(day TEXT PRIMARY KEY, start_equity REAL, end_equity REAL, halted INTEGER DEFAULT 0);
"""

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if con.execute("SELECT 1 FROM state WHERE key='cash'").fetchone() is None:
        con.execute("INSERT INTO state VALUES('cash',?)", (str(CFG["start_cash"]),))
        con.execute("INSERT INTO state VALUES('start_cash',?)", (str(CFG["start_cash"]),))
        con.execute("INSERT INTO state VALUES('created',?)", (now().isoformat(timespec="seconds"),))
        con.commit()
    return con

def get_cash(con):
    return float(con.execute("SELECT value FROM state WHERE key='cash'").fetchone()[0])

def set_cash(con, v):
    con.execute("UPDATE state SET value=? WHERE key='cash'", (str(round(v, 6)),))

def positions(con):
    return [dict(r) for r in con.execute("SELECT * FROM positions")]


def quote_bid_ask(bars):
    """Return (bid, ask) from bar attrs, or (None, None)."""
    if bars is None or not hasattr(bars, "attrs"):
        return None, None
    return bars.attrs.get("bid"), bars.attrs.get("ask")

def fill_price(side, mid, bars=None, apply_spread=True, apply_slippage=True):
    """BUY at ask / SELL at bid when the live quote is available; otherwise mid +/- slippage."""
    bid, ask = quote_bid_ask(bars)
    if apply_spread and side == "BUY" and ask:
        return float(ask)
    if apply_spread and side == "SELL" and bid:
        return float(bid)
    if apply_slippage:
        return mid * (1 + CFG["slippage"] if side == "BUY" else 1 - CFG["slippage"])
    return mid

def last_prices(tickers):

    """Latest quote (LS mid when available, else 5m close) + timestamp for tickers."""
    bars = intraday_bars(tickers)
    out = {}
    for t, b in bars.items():
        px = b.attrs.get("last_mid", float(b["Close"].iloc[-1])) if hasattr(b, "attrs") else float(b["Close"].iloc[-1])
        ts = b.attrs.get("last_ts", b.index[-1]) if hasattr(b, "attrs") else b.index[-1]
        out[t] = (float(px), ts)
    return out, bars

def equity(con, prices=None):
    pos = positions(con)
    cash = get_cash(con)
    if not pos:
        return cash, cash, {}
    if prices is None:
        prices, _ = last_prices([p["ticker"] for p in pos])
    mv = {}
    for p in pos:
        px = prices.get(p["ticker"], (p["entry_local"], None))[0]
        mv[p["ticker"]] = p["qty"] * to_eur(px, p["currency"])
    return cash + sum(mv.values()), cash, mv

def ensure_day(con, eq=None):
    d = today().isoformat()
    r = con.execute("SELECT * FROM days WHERE day=?", (d,)).fetchone()
    if r is None:
        if eq is None:
            eq = equity(con)[0]
        con.execute("INSERT INTO days(day,start_equity) VALUES(?,?)", (d, eq))
        con.commit()
        r = con.execute("SELECT * FROM days WHERE day=?", (d,)).fetchone()
    return dict(r)

def record_trade(con, ticker, side, qty, price_local, reason, **extra):
    m = dict(meta(ticker))
    cur = extra.pop("currency", None)   # passed by open_position; must not reach cols twice (TypeError)
    if cur:
        m["currency"] = cur
    fx = eurusd() if m["currency"] == "USD" else 1.0
    px_eur = price_local / fx
    value = qty * px_eur
    fee = CFG["fee_per_order"]
    cols = dict(ts=now().isoformat(timespec="seconds"), day=today().isoformat(), ticker=ticker, name=m["name"],
                side=side, qty=qty, price_local=price_local, currency=m["currency"], fx=fx, price_eur=px_eur,
                value_eur=value, fee=fee, reason=reason, **extra)
    con.execute(f"INSERT INTO trades({','.join(cols)}) VALUES({','.join('?'*len(cols))})", tuple(cols.values()))
    return fx, px_eur, value, fee

def open_position(con, ticker, qty, price_local, stop, target, risk_eur, rationale, entry_bar,
                  setup="ORB", chart_score=None, chart=None, currency=None, quote_bars=None):
    m = dict(meta(ticker))
    if currency:
        m["currency"] = currency
    fill = fill_price("BUY", price_local, quote_bars, apply_spread=True, apply_slippage=True)
    fx, px_eur, value, fee = record_trade(con, ticker, "BUY", qty, fill, rationale, setup=setup, chart=chart,
                                          currency=m["currency"])
    set_cash(con, get_cash(con) - value - fee)
    cols = dict(ticker=ticker, name=m["name"], region=m["region"], currency=m["currency"], qty=qty,
                entry_ts=now().isoformat(timespec="seconds"), entry_local=fill, entry_fx=fx, entry_eur=px_eur,
                entry_fee=fee, stop_local=stop, initial_stop_local=stop, target_local=target, risk_eur=risk_eur,
                rationale=rationale, entry_bar=entry_bar, setup=setup, chart_score=chart_score, entry_chart=chart)
    con.execute(f"INSERT INTO positions({','.join(cols)}) VALUES({','.join('?'*len(cols))})", tuple(cols.values()))
    con.commit()
    return fill

# ---------------- Italian tax (regime amministrato) ----------------
def tax_credit_available(con, d=None):
    d = (d or today()).isoformat()
    r = con.execute("SELECT COALESCE(SUM(remaining),0) FROM tax_losses WHERE expires>=? AND remaining>0", (d,)).fetchone()
    return float(r[0])

def apply_tax(con, pnl, ticker):
    """pnl = realized result after fees (fees are deductible costs). Gains: offset with oldest unexpired
    minusvalenze first, then 26% withheld. Losses: added to the bucket, usable until 31/12 of year+4."""
    d = today()
    if pnl < 0:
        con.execute("INSERT INTO tax_losses(origin_day,expires,amount,remaining,ticker) VALUES(?,?,?,?,?)",
                    (d.isoformat(), date(d.year + 4, 12, 31).isoformat(), -pnl, -pnl, ticker))
        return 0.0, 0.0
    used = 0.0
    left = pnl
    for lot in con.execute("SELECT id, remaining FROM tax_losses WHERE expires>=? AND remaining>0 ORDER BY origin_day, id",
                           (d.isoformat(),)).fetchall():
        if left <= 0: break
        u = min(left, lot["remaining"])
        con.execute("UPDATE tax_losses SET remaining=remaining-? WHERE id=?", (u, lot["id"]))
        used += u; left -= u
    return round(left * TAX_RATE, 2), used

def close_position(con, p, price_local, reason, apply_slippage=True, chart=None, quote_bars=None):
    """Sell whole position. Records gross P&L, fees (2 EUR round trip), tax and net P&L (EUR).
    Marketable sells (flatten, chart-exit) use the bid when quote_bars has one; stop/target
    keep the simulated resting-order price (apply_slippage/spread off or no quote_bars)."""
    if quote_bars is not None and apply_slippage:
        fill = fill_price("SELL", price_local, quote_bars, apply_spread=True, apply_slippage=True)
    elif apply_slippage:
        fill = price_local * (1 - CFG["slippage"])
    else:
        fill = price_local
    fx = eurusd() if p["currency"] == "USD" else 1.0
    proceeds = p["qty"] * fill / fx
    gross = proceeds - p["qty"] * p["entry_eur"]
    fees = p["entry_fee"] + CFG["fee_per_order"]
    pnl = gross - fees
    tax, used = apply_tax(con, pnl, p["ticker"])
    net = pnl - tax
    record_trade(con, p["ticker"], "SELL", p["qty"], fill, reason, pnl_eur=round(pnl, 4), setup=p.get("setup"),
                 gross_pnl_eur=round(gross, 4), tax_eur=tax, loss_credit_used=round(used, 4),
                 net_pnl_eur=round(net, 4), chart=chart)
    set_cash(con, get_cash(con) + proceeds - CFG["fee_per_order"] - tax)
    con.execute("DELETE FROM positions WHERE ticker=?", (p["ticker"],))
    con.commit()
    return fill, net

def quote_ok(bars, region):
    """(ok, age_min): newest quote not older than the source's delay + MAX_EXTRA_STALE."""
    age = bar_age_min(bars)
    src = bars.attrs.get("source", "yfinance") if hasattr(bars, "attrs") else "yfinance"
    base = LS_FEED_DELAY_MIN if str(src).startswith("ls") else FEED_DELAY[region]
    return age <= base + MAX_EXTRA_STALE, age

def feed_delay_min(bars, region):
    src = bars.attrs.get("source", "yfinance") if bars is not None and hasattr(bars, "attrs") else "yfinance"
    return LS_FEED_DELAY_MIN if str(src).startswith("ls") else FEED_DELAY[region]

def flatten(con, which, reason, script):
    """Close positions of region(s) in `which` at the latest available price."""
    pos = [p for p in positions(con) if p["region"] in which]
    if not pos:
        return []
    prices, bars = last_prices([p["ticker"] for p in pos])
    out = []
    for p in pos:
        if p["ticker"] not in prices:
            log(f"WARN no price for {p['ticker']}, cannot flatten now", script); continue
        fill, pnl = close_position(con, p, prices[p["ticker"]][0], reason, quote_bars=bars.get(p["ticker"]))
        log(f"SELL {p['qty']:.4f} {p['ticker']} @ {fill:.4f} {p['currency']} ({reason}) netto {pnl:+.2f} EUR", script)
        out.append(p["ticker"])
    return out

def watchlist_path(d=None):
    return os.path.join(DATA, f"watchlist_{(d or today()):%Y-%m-%d}.json")

def load_watchlist(d=None):
    p = watchlist_path(d)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)

# ---------------- box-pause robustness (gap catch-up) ----------------
# The box can be paused for minutes/hours; the scheduler then wakes up late. These helpers let
# trade.py replay every bar since the last check (so a stop is never skipped) and close stale
# positions at the last price inside the trading window. See README "Pause della macchina".
GAPS_LOG = os.path.join(LOGS, "gaps.log")

def gap_log(msg):
    """Append one line to logs/gaps.log (read by update.py / the 3-hourly updates)."""
    with open(GAPS_LOG, "a") as f:
        f.write(f"{now():%Y-%m-%d %H:%M:%S} {msg}\n")

def _aware(ts):
    ts = pd.Timestamp(ts)
    return ts.tz_localize(ROME) if ts.tzinfo is None else ts.tz_convert(ROME)

def position_cutoff(p):
    """Last moment the position may legally live: min(now, final flatten of its entry day)."""
    d = _aware(p["entry_ts"]).date()
    return min(pd.Timestamp(now()), pd.Timestamp(flatten_time(p["region"], d)))

def is_stale(p):
    """True if the position should already be closed and the TR window for it is over
    (entry on a previous day, or now past 22:00): it must be flattened at a historical price."""
    d = _aware(p["entry_ts"]).date()
    return d < today() or now().time() >= TR_WINDOW[1]

def _ckpt_key(ticker):
    return f"watch_ckpt:{ticker}"

def watch_checkpoint(con, p):
    """Start of the first bar not yet fully checked for this position (Rome-aware)."""
    first = _aware(p["entry_ts"]).floor("min") + pd.Timedelta(minutes=1)   # never the entry minute itself
    r = con.execute("SELECT value FROM state WHERE key=?", (_ckpt_key(p["ticker"]),)).fetchone()
    if r:
        try:
            first = max(first, _aware(r[0]))
        except Exception:
            pass
    return first

def set_watch_checkpoint(con, ticker, ts):
    con.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (_ckpt_key(ticker), str(_aware(ts))))

def replay_bars(p, b5, since, cutoff):
    """Bars to replay for position p over [since, cutoff], finest data first:
    1) 1-minute LS bars from data/bars.sqlite (EUR mid; only for EUR-priced positions),
    2) yfinance 1m when the store has nothing for a gap longer than 3 min,
    3) the 5-minute bars `b5` for any 5-min bucket the 1m data does not fully cover,
    4) a final synthetic bar from the live quote (Low = bid) if it is newer than the bars.
    Returns a DataFrame (Open/High/Low/Close) sorted by bar start, plus a 'src' column."""
    since, cutoff = _aware(since), _aware(cutoff)
    one = None
    if p.get("currency", "EUR") == "EUR":
        try:
            import marketdata as MD
            one = MD.load_stored_bars(p["ticker"], "1min")
        except Exception:
            one = None
    if (one is None or one[(one.index >= since)].empty) and (cutoff - since) > pd.Timedelta(minutes=3):
        try:
            y = yf_intraday_bars([p["ticker"]], period="5d", interval="1m").get(p["ticker"])
            if y is not None and len(y) and (y.attrs.get("currency") or "EUR") == p.get("currency", "EUR"):
                one = y
        except Exception:
            pass
    parts = []
    if one is not None and len(one):
        one = one[(one.index >= since) & (one.index <= cutoff)][["Open", "High", "Low", "Close"]].copy()
        one["src"] = "1m"
        parts.append(one)
    covered = parts[0] if parts else None
    if b5 is not None and len(b5):
        five = b5[(b5.index + pd.Timedelta(minutes=5) > since) & (b5.index <= cutoff)][["Open", "High", "Low", "Close"]].copy()
        keep = []
        for ts in five.index:
            end = min(ts + pd.Timedelta(minutes=5), cutoff + pd.Timedelta(minutes=1))
            expect = max(1, int((end - max(ts, since)).total_seconds() // 60))
            n1 = 0 if covered is None else int(((covered.index >= ts) & (covered.index < end)).sum())
            keep.append(n1 < expect)
        five = five[keep]
        if len(five):
            # drop 1m bars inside buckets replaced by the (complete) 5m bar
            if covered is not None and len(covered):
                mask = pd.Series(False, index=covered.index)
                for ts in five.index:
                    mask |= (covered.index >= ts) & (covered.index < ts + pd.Timedelta(minutes=5))
                parts[0] = covered[~mask.values]
            five["src"] = "5m"
            parts.append(five)
    a = getattr(b5, "attrs", {}) or {}
    lts, mid = a.get("last_ts"), a.get("last_mid")
    if lts is not None and mid is not None:
        lts = _aware(lts)
        if since <= lts <= cutoff:
            bid = a.get("bid") or mid
            ask = a.get("ask") or mid
            parts.append(pd.DataFrame({"Open": [mid], "High": [max(mid, min(ask, mid))], "Low": [min(mid, bid)],
                                       "Close": [mid], "src": ["quote"]}, index=pd.DatetimeIndex([lts.floor("min")])))
    if not parts:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "src"])
    out = pd.concat(parts).sort_index(kind="stable")
    return out

def half_spread(bars):
    bid, ask = quote_bid_ask(bars)
    if bid and ask and ask > bid:
        return (float(ask) - float(bid)) / 2
    return 0.0

def late_flatten(con, ps, bars, script, reason_tag="chiusura in ritardo (pausa macchina)"):
    """Close stale positions at the last price at/before their cutoff (inside the TR window).
    Fill = that mid - half spread (if known) - normal slippage; 1 EUR fee via close_position."""
    out = []
    for p in ps:
        cut = position_cutoff(p)
        b = bars.get(p["ticker"])
        rb = replay_bars(p, b, _aware(p["entry_ts"]), cut)
        rb = rb[rb.index < cut] if len(rb) else rb
        if len(rb):
            px, at = float(rb["Close"].iloc[-1]), rb.index[-1]
        else:
            px, at = float(p["entry_local"]), _aware(p["entry_ts"])
            log(f"WARN {p['ticker']}: nessuna barra prima di {cut:%H:%M}, chiudo al prezzo di ingresso", script)
        px -= half_spread(b)
        reason = f"{reason_tag}: prezzo delle {at:%d/%m %H:%M} (limite {cut:%H:%M})"
        fill, net = close_position(con, p, px, reason, apply_slippage=True)
        log(f"SELL {p['qty']:.4f} {p['ticker']} @ {fill:.4f} [LATE] {reason} netto {net:+.2f} EUR", script)
        gap_log(f"LATE-FLATTEN {p['ticker']} @ {fill:.4f} ({reason}) netto {net:+.2f} EUR")
        out.append(p["ticker"])
    return out
