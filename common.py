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
    debate_shadow=False,        # filtro dibattito LLM (solo shadow): spento dal 19/11/2026, giudice SCARTA 14/14 in 3 sedute (non informativo)
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
    max_extension_atr=1.5,      # don't chase: close <= OR high + 1.5*ATR (short: close >= OR low - 1.5*ATR)
    allow_short=False,          # mirror ORB breakdown short side (1x, notional reserved as collateral). Code ready and tested,
                                # OFF in production: backtest 61 sessions long+short -69.31 EUR vs long-only -7.09 (16/11/2026).
                                # Runs in shadow as V0_SHORT. Set True to trade shorts.
    wide_universe=True,         # 17/11/2026: every pass also scans ALL universe.csv names of wide_regions (09:35 watchlist first)
    wide_regions=("EU", "US"),  # 17/11 notte: ordine esplicito di Andrea, tutti i titoli TR disponibili (universe_wide.csv, ~1.230)
                                # nonostante il backtest peggiore (vedi CHANGELOG). Prima: ("EU",) -5,74 EUR vs v0 -7,09.
    wide_file=True,             # usa core + universe_wide.csv nella scansione larga (False = solo universe.csv)
    wide_chunk=200,             # titoli per richiesta Yahoo nella scansione larga (batch, una pausa breve tra i blocchi)
    ls_priority_max=20,         # live LS quotes for at most this many names per pass (held + breakout candidates first);
                                # the others are screened on the one-call Yahoo 5m batch (EU ~15 min late)
    lev_to_gate=False,          # leverage ONLY as much as needed for the fee gate. Code ready, OFF: backtest 62 sessions
                                # -414.74 EUR on the 09:35 list (169 trades, mostly 0.4% noise stops), -753.78 wide (17/11/2026)
    max_leverage=5.0,           # cap: notional <= 5x the 30% slot; margin = min(notional, slot), rest financed (paper)
    rank_signals=False,         # rank same-pass signals by chart score before entering (see CHANGELOG)
    ema_fast=9,                 # v0 alignment filter (15/11/2026): longs only if EMA9 > EMA21 on 5m closes
    ema_slow=21,
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
    """Core universe (71 names with ISIN for live L&S quotes): 09:35 scan, rescan, shadow."""
    with open(os.path.join(BASE, "universe.csv")) as f:
        return list(csv.DictReader(f))

WIDE_UNIVERSE = os.path.join(BASE, "universe_wide.csv")

def load_wide_universe():
    """Core universe + universe_wide.csv (TR-tradable index constituents filtered for liquidity and Yahoo 5m data,
    built 16/11/2026: DAX/MDAX/SDAX, FTSE MIB/Mid Cap, CAC 40, AEX/AMX, IBEX 35, Euro Stoxx 50, BEL 20, PSI, ATX,
    OMX Helsinki 25, ISEQ 20, S&P 500, S&P 400, extra large US names). Core rows first; no duplicates."""
    out = load_universe()
    have = {r["ticker"] for r in out}
    if os.path.exists(WIDE_UNIVERSE):
        with open(WIDE_UNIVERSE) as f:
            out += [r for r in csv.DictReader(f) if r["ticker"] not in have]
    return out

_meta_map = None
def meta(ticker):
    """Universe row for ticker (core first, then universe_wide.csv); map built once per process."""
    global _meta_map
    if _meta_map is None:
        m = {}
        for r in load_wide_universe():
            m.setdefault(r["ticker"], r)
        _meta_map = m
    r = _meta_map.get(ticker)
    if r is not None:
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

def yf_intraday_bars_chunked(tickers, period="2d", interval="5m", chunk=200, pause=0.5):
    """Yahoo 5m bars for many names in polite batches (one request per `chunk` names). Failed chunks are skipped."""
    import time as _t
    tickers = list(tickers); out = {}
    for i in range(0, len(tickers), chunk):
        try:
            out.update(yf_intraday_bars(tickers[i:i + chunk], period=period, interval=interval))
        except Exception as e:
            log(f"WARN Yahoo batch {i}-{i + chunk} fallito: {e}", "marketdata")
        if i + chunk < len(tickers):
            _t.sleep(pause)
    return out

def intraday_bars(tickers, period="5d", interval="5m", prepost=False, use_ls=True, yf_bars=None):
    """Primary: LS Exchange live mid/bid/ask (EUR, typically ~20-40s) plus 1m mid chart.

    Previous days' 5m bars still come from yfinance (LS public chart is the current session
    only); they are spliced behind today's LS bars. US Yahoo bars are converted to EUR so
    the series matches LS / Trade Republic. Pass use_ls=False to force Yahoo (see scan.py).
    """
    tickers = list(tickers)
    if yf_bars is None:     # callers that already hold the one-call Yahoo batch (wide scan) pass it in
        yf_bars = yf_intraday_bars(tickers, period=period, interval=interval, prepost=prepost)
    else:
        yf_bars = {t: yf_bars[t] for t in tickers if t in yf_bars}
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

def to_5m(df):
    """5-minute OHLC. If the series is already 5-minute, return it unchanged."""
    if df is None or getattr(df, "empty", True):
        return df
    idx = df.index
    if len(idx) >= 2:
        med = (idx[1:] - idx[:-1]).median()
        sec = med.total_seconds() if hasattr(med, "total_seconds") else float(med) / 1e9
        if 200 <= sec <= 400:
            return df
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg["Volume"] = "sum"
    cols = {k: v for k, v in agg.items() if k in df.columns}
    if "Close" not in cols:
        return df.iloc[0:0]
    return df.resample("5min", label="left", closed="left").agg(cols).dropna(subset=["Close"])

def ema(series, n):
    return series.ewm(span=int(n), adjust=False).mean()

def ema_aligned(bars, side="long", fast=None, slow=None):
    """EMA alignment on 5-minute closes (same timeframe as the 15/11/2026 validation).

    long: EMA(fast) > EMA(slow); short: EMA(fast) < EMA(slow).
    Returns (ok, ema_fast, ema_slow). ok is False if the series is too short or a value is NaN.
    """
    fast = int(CFG["ema_fast"] if fast is None else fast)
    slow = int(CFG["ema_slow"] if slow is None else slow)
    nan = float("nan")
    b = to_5m(bars)
    if b is None or getattr(b, "empty", True) or "Close" not in b.columns or len(b) < slow:
        return False, nan, nan
    e_fast = float(ema(b["Close"], fast).iloc[-1])
    e_slow = float(ema(b["Close"], slow).iloc[-1])
    if e_fast != e_fast or e_slow != e_slow:
        return False, e_fast, e_slow
    if (side or "long").lower() == "short":
        return e_fast < e_slow, e_fast, e_slow
    return e_fast > e_slow, e_fast, e_slow

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
  stop_local REAL, initial_stop_local REAL, target_local REAL, risk_eur REAL, rationale TEXT, entry_bar TEXT, setup TEXT, chart_score REAL, entry_chart TEXT, mae_local REAL, mfe_local REAL, side TEXT DEFAULT 'long', loan_eur REAL DEFAULT 0);
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

def _migrate_positions(con):
    """Add MAE/MFE and side columns to ledgers created before they existed."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(positions)")}
    for col in ("mae_local", "mfe_local"):
        if col not in cols:
            con.execute(f"ALTER TABLE positions ADD COLUMN {col} REAL")
    if "side" not in cols:
        con.execute("ALTER TABLE positions ADD COLUMN side TEXT DEFAULT 'long'")
    if "loan_eur" not in cols:
        con.execute("ALTER TABLE positions ADD COLUMN loan_eur REAL DEFAULT 0")
    con.commit()

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    _migrate_positions(con)
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
    out = [dict(r) for r in con.execute("SELECT * FROM positions")]
    for p in out:
        p["side"] = (p.get("side") or "long").lower()
    return out

def is_short(p):
    return (p.get("side") or "long").lower() == "short"

# trades.side values: BUY (open long), SELL (close long), SHORT (open short = sell short), COVER (close short = buy back)
ENTRY_SIDES = ("BUY", "SHORT")
EXIT_SIDES = ("SELL", "COVER")

def loan(p):
    """Financed part of a leveraged paper position (0 for 1x positions and old ledgers)."""
    return float(p.get("loan_eur") or 0.0)

def leverage(p):
    """Notional / own margin of a position (1.0 = no leverage)."""
    notional = p["qty"] * p["entry_eur"]
    own = notional - loan(p)
    return notional / own if own > 0 else 1.0

def position_value_eur(p, px_local):
    """Equity contribution of an open position at px_local, net of the financed part (loan_eur).
    Long: market value - loan. Short (notional reserved at entry): reserved notional + unrealized P&L - loan."""
    px_eur = to_eur(px_local, p["currency"])
    if is_short(p):
        return p["qty"] * p["entry_eur"] + p["qty"] * (p["entry_eur"] - px_eur) - loan(p)
    return p["qty"] * px_eur - loan(p)

def size_position(eq, cash, px_eur, dist_eur):
    """Paper sizing (EUR). 2% risk per trade (stop distance x qty + both fees), 30% equity slot; the
    expected 2R reward must be >= min_reward_vs_fees x round-trip fees (6 EUR). With lev_to_gate the
    notional may exceed the slot ONLY as much as needed to reach that gate, up to max_leverage x slot,
    never above the 2% risk. Margin = min(notional, slot); the rest is a paper loan repaid at close.
    Returns dict(qty, value, reward, margin, loan, lev, gate, why) - why is '' when tradeable."""
    fees = 2 * CFG["fee_per_order"]
    gate = CFG["min_reward_vs_fees"] * fees
    out = dict(qty=0.0, value=0.0, reward=0.0, margin=0.0, loan=0.0, lev=1.0, gate=gate, why="")
    if px_eur <= 0 or dist_eur <= 0:
        out["why"] = "prezzo o stop non validi"; return out
    slot = CFG["max_position_pct"] * eq
    q_risk = (CFG["risk_per_trade"] * eq - fees) / dist_eur
    q_cap = slot / px_eur
    q = min(q_risk, q_cap)
    if CFG.get("lev_to_gate") and q_cap * CFG["reward_r"] * dist_eur < gate:
        q_gate = gate / (CFG["reward_r"] * dist_eur) * 1.0005
        q = min(q_risk, max(q_cap, min(q_gate, CFG.get("max_leverage", 1.0) * slot / px_eur)))
    margin = min(q * px_eur, slot)
    avail = cash - CFG["fee_per_order"]
    if margin > avail:                       # scale down to the cash available for the margin
        q = q * max(avail, 0.0) / margin if margin > 0 else 0.0
    q = math.floor(max(q, 0.0) * 1e4) / 1e4 if CFG["fractional"] else math.floor(max(q, 0.0))
    value = q * px_eur
    margin = min(value, slot)
    out.update(qty=q, value=value, reward=q * CFG["reward_r"] * dist_eur, margin=margin,
               loan=max(0.0, value - margin), lev=(value / margin) if margin > 0 else 1.0)
    if value < CFG["min_position_eur"]:
        out["why"] = f"posizione troppo piccola ({value:.0f} EUR) per giustificare le commissioni"
    elif out["reward"] < gate:
        out["why"] = (f"filtro commissioni: guadagno atteso {out['reward']:.2f} EUR < {gate:.0f} EUR "
                      f"({CFG['min_reward_vs_fees']:.0f}x commissioni)")
    return out


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
        mv[p["ticker"]] = position_value_eur(p, px)
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
                  setup="ORB", chart_score=None, chart=None, currency=None, quote_bars=None, side="long",
                  margin_eur=None):
    """Open a PAPER position. side="short": sell short at the bid (or mid - slippage); the notional is
    reserved from cash as collateral and released with the P&L at cover.
    margin_eur (leverage, see size_position): own cash committed; notional - margin is a paper loan
    (loan_eur) repaid at close. None = 1x (whole notional from cash)."""
    m = dict(meta(ticker))
    if currency:
        m["currency"] = currency
    side = (side or "long").lower()
    order = "SELL" if side == "short" else "BUY"
    fill = fill_price(order, price_local, quote_bars, apply_spread=True, apply_slippage=True)
    fx, px_eur, value, fee = record_trade(con, ticker, "SHORT" if side == "short" else "BUY", qty, fill, rationale,
                                          setup=setup, chart=chart, currency=m["currency"])
    ln = max(0.0, value - margin_eur) if margin_eur is not None else 0.0
    set_cash(con, get_cash(con) - value - fee + ln)
    cols = dict(ticker=ticker, name=m["name"], region=m["region"], currency=m["currency"], qty=qty,
                entry_ts=now().isoformat(timespec="seconds"), entry_local=fill, entry_fx=fx, entry_eur=px_eur,
                entry_fee=fee, stop_local=stop, initial_stop_local=stop, target_local=target, risk_eur=risk_eur,
                rationale=rationale, entry_bar=entry_bar, setup=setup, chart_score=chart_score, entry_chart=chart,
                mae_local=fill, mfe_local=fill, side=side, loan_eur=round(ln, 6))
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
    """Close the whole position (long: sell; short: buy to cover). Records gross P&L, fees (2 EUR
    round trip), tax and net P&L (EUR). Marketable orders (flatten, chart-exit) use the bid (long) /
    ask (short) when quote_bars has one; stop/target keep the simulated resting-order price."""
    short = is_short(p)
    order = "BUY" if short else "SELL"
    if quote_bars is not None and apply_slippage:
        fill = fill_price(order, price_local, quote_bars, apply_spread=True, apply_slippage=True)
    elif apply_slippage:
        fill = price_local * (1 + CFG["slippage"] if short else 1 - CFG["slippage"])
    else:
        fill = price_local
    fx = eurusd() if p["currency"] == "USD" else 1.0
    exit_value = p["qty"] * fill / fx
    cost = p["qty"] * p["entry_eur"]
    if short:
        gross = cost - exit_value
        cash_back = cost + gross          # release reserved notional +/- P&L
    else:
        gross = exit_value - cost
        cash_back = exit_value
    fees = p["entry_fee"] + CFG["fee_per_order"]
    pnl = gross - fees
    tax, used = apply_tax(con, pnl, p["ticker"])
    net = pnl - tax
    record_trade(con, p["ticker"], "COVER" if short else "SELL", p["qty"], fill, reason, pnl_eur=round(pnl, 4),
                 setup=p.get("setup"), gross_pnl_eur=round(gross, 4), tax_eur=tax, loss_credit_used=round(used, 4),
                 net_pnl_eur=round(net, 4), chart=chart)
    set_cash(con, get_cash(con) + cash_back - CFG["fee_per_order"] - tax - loan(p))
    con.execute("DELETE FROM positions WHERE ticker=?", (p["ticker"],))
    con.commit()
    try:
        import trade_log as TL
        TL.from_position(p, fill, reason, gross, fees, tax, net, used=used, source="production", fx=fx)
    except Exception as e:
        log(f"WARN trade_log non scritto per {p.get('ticker')}: {e}", "trade_log")
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
        log(f"{'COVER' if is_short(p) else 'SELL'} {p['qty']:.4f} {p['ticker']} @ {fill:.4f} {p['currency']} ({reason}) netto {pnl:+.2f} EUR", script)
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
            try:
                import trade_log as TL
                start_mae = p.get("mae_local") if p.get("mae_local") is not None else p["entry_local"]
                start_mfe = p.get("mfe_local") if p.get("mfe_local") is not None else p["entry_local"]
                mae, mfe = start_mae, start_mfe
                for _, bar in rb.iterrows():
                    mae, mfe = TL.update_excursion(mae, mfe, p["entry_local"], bar["Low"], bar["High"], p.get("side") or "long")
                p["mae_local"], p["mfe_local"] = mae, mfe
            except Exception:
                pass
        else:
            px, at = float(p["entry_local"]), _aware(p["entry_ts"])
            log(f"WARN {p['ticker']}: nessuna barra prima di {cut:%H:%M}, chiudo al prezzo di ingresso", script)
        px += half_spread(b) if is_short(p) else -half_spread(b)
        reason = f"{reason_tag}: prezzo delle {at:%d/%m %H:%M} (limite {cut:%H:%M})"
        fill, net = close_position(con, p, px, reason, apply_slippage=True)
        log(f"{'COVER' if is_short(p) else 'SELL'} {p['qty']:.4f} {p['ticker']} @ {fill:.4f} [LATE] {reason} netto {net:+.2f} EUR", script)
        gap_log(f"LATE-FLATTEN {p['ticker']} @ {fill:.4f} ({reason}) netto {net:+.2f} EUR")
        out.append(p["ticker"])
    return out
