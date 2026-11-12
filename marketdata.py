#!/usr/bin/env python3
"""Lang & Schwarz TradeCenter (ls-tc.de) public market data for the PAPER bot.

Trade Republic executes on Lang & Schwarz. L&S publishes real-time pre- and
post-trade data on www.ls-tc.de under MiFID II / MiFIR, free to use. This
module talks only to the same unauthenticated public endpoints the website
and the official download page use: instrument search by ISIN, the 1-minute
mid chart, the instrument-page quote (bid/ask/mid + timestamp), and the
MiFID post-trade CSV of today's prints (volume and last trade).

Quotes are in EUR, including US names. Chart timestamps are Europe/Berlin
wall-clock times encoded as UTC milliseconds (a Highcharts convention used
by the site); we reinterpret them as Berlin local time.

Polite use: persistent instrument-id cache, in-memory chart cache (~60s,
matching the CDN max-age), a minimum gap between HTTP calls, short timeouts,
one retry. If LS is unreachable, callers fall back to yfinance.

Local 1-minute and 5-minute bars are accumulated in data/bars.sqlite
(override with PT_BARS) so history builds up even though the public chart
only returns the current session.

CLI: python3 marketdata.py --ping          # delay vs yfinance for the watchlist
     python3 marketdata.py --quote SAP.DE
"""
from __future__ import annotations

import json, os, sqlite3, time, urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
INSTR_CACHE = os.path.join(DATA, "ls_instruments.json")
BARS_DB = os.environ.get("PT_BARS", os.path.join(DATA, "bars.sqlite"))

LS_BASE = "https://www.ls-tc.de"
SEARCH_URL = LS_BASE + "/_rpc/json/.lstc/instrument/search/main"
CHART_URL = LS_BASE + "/_rpc/json/instrument/chart/dataForInstrument"
TRADES_URL = "https://www.ls-x.de/_rpc/json/.lstc/instrument/list/lstctradestoday"
QUOTE_PATH = LS_BASE + "/de/aktie/{id}"
UA = "PaperTradingBot/1.0 (personal paper-trading; public MiFID data)"
BERLIN = ZoneInfo("Europe/Berlin")
ROME = ZoneInfo("Europe/Rome")

# Telecom Italia ordinary share ISIN was replaced; keep both keys in the cache.
ISIN_ALIASES = {
    "IT0003497168": "IT0005712671",
}

MIN_INTERVAL_SEC = 0.25          # polite gap between HTTP calls
CHART_CACHE_SEC = 60             # LS CDN caches the chart for 60s
QUOTE_CACHE_SEC = 20             # instrument page Cache-Control is max-age=30
TRADES_CACHE_SEC = 45            # official daily tape; cache-bust so we don't get yesterday
HTTP_TIMEOUT = 15
MAX_TICKERS_PER_CALL = 20        # never scrape the whole universe in one go

_session = None
_last_http = 0.0
_chart_memo = {}                 # instrumentId -> (fetched_monotonic, points, raw_info)
_quote_memo = {}                 # instrumentId -> (fetched_monotonic, quote_dict)
_trades_memo = None              # (fetched_monotonic, dict ticker -> list of (ts, price, size))
_instr = None
_delay_log = []                  # recent (ticker, delay_sec, mid, ts) for the last fetch batch


def _sess():
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "de,en;q=0.8",
        })
        _session = s
    return _session


def _pace():
    global _last_http
    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_http)
    if wait > 0:
        time.sleep(wait)
    _last_http = time.monotonic()


def _get(url, params=None, retries=1):
    last_err = None
    for attempt in range(retries + 1):
        _pace()
        try:
            r = _sess().get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            if not r.content or r.content.strip() in (b"", b'""', b"null"):
                return None
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err


def _get_raw(url, params=None, retries=1):
    last_err = None
    for attempt in range(retries + 1):
        _pace()
        try:
            r = _sess().get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.content, r.headers
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (attempt + 1))
    raise last_err


def _num(s):
    """Parse a German or English decimal ('210,2250' or '210.2250' or '1.234,56')."""
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", "").replace(" ", "")
    s = "".join(ch for ch in s if ch.isdigit() or ch in ",.-")
    if not s or s in "-.":
        return None
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def now_rome():
    return datetime.now(ROME)


def ls_chart_ts(ms):
    """Convert an LS chart timestamp (Berlin wall clock stored as UTC ms) to aware datetime."""
    naive = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return naive.replace(tzinfo=BERLIN)


# ---------------- instrument id cache ----------------
def _load_instr():
    global _instr
    if _instr is not None:
        return _instr
    if os.path.exists(INSTR_CACHE):
        with open(INSTR_CACHE) as f:
            _instr = json.load(f)
    else:
        _instr = {}
    return _instr


def _save_instr():
    os.makedirs(DATA, exist_ok=True)
    tmp = INSTR_CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_instr, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, INSTR_CACHE)


def _pick_stock(hits, isin):
    exact = [h for h in hits if str(h.get("isin", "")).upper() == isin.upper()]
    pool = exact or hits
    stock = [h for h in pool if h.get("categorySymbol") == "STK" or h.get("categoryName") == "Aktie"]
    return (stock or pool)[0] if pool else None


def resolve_instrument(isin, name=None, ticker=None):
    """Return {instrumentId, isin, name, ...} or None. Caches on disk."""
    if not isin:
        return None
    isin = isin.strip().upper()
    cache = _load_instr()
    if isin in cache and cache[isin].get("instrumentId"):
        return cache[isin]
    alias = ISIN_ALIASES.get(isin)
    if alias and alias in cache and cache[alias].get("instrumentId"):
        rec = dict(cache[alias])
        rec["queried_isin"] = isin
        rec["alias_of"] = alias
        cache[isin] = rec
        _save_instr()
        return rec
    # search by ISIN, then alias, then name
    queries = [isin]
    if alias:
        queries.append(alias)
    if name:
        queries.append(name)
    rec = None
    last_hits = []
    for q in queries:
        try:
            hits = _get(SEARCH_URL, {"q": q, "localeId": 2}) or []
        except Exception:
            hits = []
        last_hits = hits
        target = alias if (q == alias and alias) else isin
        picked = _pick_stock(hits, target) if q in (isin, alias) else None
        if picked is None and q == name:
            # name search: only accept STK whose ISIN country prefix matches, or alias hit
            stocks = [h for h in hits if h.get("categorySymbol") == "STK"]
            if alias:
                picked = _pick_stock(stocks, alias)
            if picked is None and isin[:2].isalpha():
                same = [h for h in stocks if str(h.get("isin", "")).startswith(isin[:2])]
                # prefer a display name that shares a token with our name
                tokens = {t for t in (name or "").upper().replace("-", " ").split() if len(t) >= 4}
                if tokens and same:
                    scored = []
                    for h in same:
                        dn = str(h.get("displayname", "")).upper()
                        scored.append((sum(1 for t in tokens if t in dn), h))
                    scored.sort(key=lambda x: -x[0])
                    if scored and scored[0][0] >= 1:
                        picked = scored[0][1]
        if picked:
            rec = {
                "instrumentId": int(picked["instrumentId"]),
                "isin": picked.get("isin"),
                "name": picked.get("displayname"),
                "ticker": ticker,
                "queried_isin": isin,
            }
            if alias:
                rec["alias_of"] = alias
            break
    if rec:
        cache[isin] = rec
        if rec.get("isin") and rec["isin"] != isin:
            cache[rec["isin"]] = dict(rec)
        _save_instr()
    return rec


# ---------------- chart / last mid ----------------
def fetch_intraday_points(instrument_id, use_cache=True):
    """Return (list of (datetime, mid), info_dict). Points are Berlin-aware."""
    instrument_id = int(instrument_id)
    if use_cache and instrument_id in _chart_memo:
        t0, pts, info = _chart_memo[instrument_id]
        if time.monotonic() - t0 < CHART_CACHE_SEC:
            return pts, info
    data = _get(CHART_URL, {
        "instrumentId": instrument_id,
        "marketId": 1,
        "quotetype": "mid",
        "series": "intraday",
        "localeId": 2,
    })
    pts, info = [], {}
    if data:
        info = data.get("info") or {}
        raw = ((data.get("series") or {}).get("intraday") or {}).get("data") or []
        for row in raw:
            if not row or len(row) < 2 or row[1] is None:
                continue
            try:
                pts.append((ls_chart_ts(row[0]), float(row[1])))
            except Exception:
                continue
    _chart_memo[instrument_id] = (time.monotonic(), pts, info)
    return pts, info


def points_to_bars(points, interval="5min"):
    """Build OHLC bars from mid samples. Volume is 0 (LS chart has no size)."""
    if not points:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    s = pd.Series([p[1] for p in points], index=pd.DatetimeIndex([p[0] for p in points], tz=BERLIN))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    ohlc = s.resample(interval, label="left", closed="left").ohlc()
    ohlc.columns = ["Open", "High", "Low", "Close"]
    ohlc["Volume"] = 0.0
    ohlc = ohlc.dropna(subset=["Close"])
    if ohlc.index.tz is None:
        ohlc.index = ohlc.index.tz_localize(BERLIN)
    ohlc.index = ohlc.index.tz_convert(ROME)
    return ohlc


# ---------------- local bar store ----------------
_BARS_SCHEMA = """
CREATE TABLE IF NOT EXISTS bars_1m(
  ticker TEXT, ts TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, source TEXT,
  PRIMARY KEY(ticker, ts));
CREATE TABLE IF NOT EXISTS bars_5m(
  ticker TEXT, ts TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, source TEXT,
  PRIMARY KEY(ticker, ts));
CREATE TABLE IF NOT EXISTS quotes(
  ticker TEXT, ts TEXT, mid REAL, source TEXT, delay_sec REAL,
  bid REAL, ask REAL, PRIMARY KEY(ticker, ts));
CREATE TABLE IF NOT EXISTS tape(
  ticker TEXT, ts TEXT, price REAL, size REAL,
  PRIMARY KEY(ticker, ts, price, size));
"""


def _bars_db():
    os.makedirs(os.path.dirname(BARS_DB) or ".", exist_ok=True)
    con = sqlite3.connect(BARS_DB)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(_BARS_SCHEMA)
    return con


def _store_points(ticker, points, delay_sec=None):
    if not points:
        return
    bars1 = points_to_bars(points, "1min")
    bars5 = points_to_bars(points, "5min")
    con = _bars_db()
    try:
        con.executemany(
            "INSERT OR REPLACE INTO bars_1m(ticker,ts,open,high,low,close,volume,source) VALUES(?,?,?,?,?,?,?,?)",
            [(ticker, str(ts), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume), "ls")
             for ts, r in bars1.iterrows()],
        )
        con.executemany(
            "INSERT OR REPLACE INTO bars_5m(ticker,ts,open,high,low,close,volume,source) VALUES(?,?,?,?,?,?,?,?)",
            [(ticker, str(ts), float(r.Open), float(r.High), float(r.Low), float(r.Close), float(r.Volume), "ls")
             for ts, r in bars5.iterrows()],
        )
        ts, mid = points[-1]
        con.execute(
            "INSERT OR REPLACE INTO quotes(ticker,ts,mid,source,delay_sec) VALUES(?,?,?,?,?)",
            (ticker, ts.isoformat(timespec="seconds"), mid, "ls", delay_sec),
        )
        con.commit()
    finally:
        con.close()


def load_stored_bars(ticker, interval="5min"):
    table = "bars_5m" if interval.startswith("5") else "bars_1m"
    if not os.path.exists(BARS_DB):
        return None
    con = _bars_db()
    try:
        rows = con.execute(
            f"SELECT ts,open,high,low,close,volume FROM {table} WHERE ticker=? ORDER BY ts",
            (ticker,),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    idx = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(ROME)
    df = df.drop(columns=["ts"])
    df.index = idx
    return df



# ---------------- official post-trade tape (volume + last print) ----------------
def _trade_ts(raw):
    """Tape timestamps are Berlin wall-clock values with a misleading trailing Z."""
    s = str(raw).strip().replace("Z", "").replace("z", "")
    if "." in s:
        head, frac = s.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        s = head + "." + frac
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BERLIN)
    return dt


def fetch_today_tape(universe_rows, use_cache=True):
    """Download today's L&S prints (official MiFID CSV). Return ticker -> [(ts, price, size)].

    Timestamps are treated as Europe/Berlin (the file's 'Z' suffix is not true UTC;
    the first print of the day is 07:30 local, and the last print matches the
    'stand_HH:MM:SS' stamp in the filename).
    """
    global _trades_memo
    if use_cache and _trades_memo is not None:
        t0, data = _trades_memo
        if time.monotonic() - t0 < TRADES_CACHE_SEC:
            return data
    by_isin = {}
    rows = list(universe_rows)
    for u in rows:
        inst = resolve_instrument(u.get("isin", ""), name=u.get("name"), ticker=u["ticker"]) or {}
        for isin in {u.get("isin"), inst.get("isin"), inst.get("alias_of"), inst.get("queried_isin")}:
            if isin:
                by_isin[str(isin).upper()] = u["ticker"]
        for alias_src, alias_dst in ISIN_ALIASES.items():
            if u.get("isin") in (alias_src, alias_dst):
                by_isin[alias_src] = u["ticker"]
                by_isin[alias_dst] = u["ticker"]
    out = {u["ticker"]: [] for u in rows}
    try:
        # Bucketed cache-bust: without a query string the CDN may serve yesterday's file for hours.
        bucket = int(time.time() // TRADES_CACHE_SEC) * int(TRADES_CACHE_SEC)
        raw, _hdrs = _get_raw(TRADES_URL, params={"t": bucket})
        text = raw.decode("utf-8-sig", errors="replace")
        import csv as csvmod, io
        reader = csvmod.reader(io.StringIO(text), delimiter=";")
        header = next(reader, None)
        if not header:
            _trades_memo = (time.monotonic(), out)
            return out
        # isin;displayName;tradeTime;price;currency;size;orderId
        for row in reader:
            if len(row) < 6:
                continue
            isin = row[0].strip().strip('"').upper()
            ticker = by_isin.get(isin)
            if not ticker:
                continue
            try:
                ts = _trade_ts(row[2].strip().strip('"'))
                px = _num(row[3])
                sz = _num(row[5])
            except Exception:
                continue
            if px is None or sz is None:
                continue
            out[ticker].append((ts, px, sz))
        for t in out:
            out[t].sort(key=lambda x: x[0])
        _trades_memo = (time.monotonic(), out)
        try:
            _store_tape(out)
        except Exception:
            pass
        return out
    except Exception:
        if _trades_memo is not None:
            return _trades_memo[1]
        return out


def tape_to_volume(tape_rows, interval="5min"):
    """Resample LS prints to a Volume series (share size) at the given bar size."""
    if not tape_rows:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex([t for t, p, s in tape_rows], tz=BERLIN)
    s = pd.Series([s for t, p, s in tape_rows], index=idx)
    if s.index.tz is None:
        s.index = s.index.tz_localize(BERLIN)
    s.index = s.index.tz_convert(ROME)
    return s.resample(interval, label="left", closed="left").sum().fillna(0.0)


def blend_volume(bars, yf_df, tape_rows, interval="5min"):
    """Set bars['Volume'] and bars['ls_volume'].

    Cash-session bars that exist on yfinance keep official primary-exchange volume
    (comparable to historical rvol). The delayed tail and extended hours use LS
    tape volume scaled by today's yfinance/LS ratio when that ratio is available.
    """
    out = bars.copy()
    out["ls_volume"] = 0.0
    tv = tape_to_volume(tape_rows, interval)
    if len(tv):
        aligned = tv.reindex(out.index).fillna(0.0)
        # prints that fall after the last bar start still belong on the last / new bar
        out["ls_volume"] = aligned
    out["Volume"] = out["ls_volume"]
    ratio = None
    vol_src = "ls_tape"
    if yf_df is not None and len(yf_df) and "Volume" in yf_df.columns:
        yv = yf_df["Volume"].copy()
        if yv.index.tz is None:
            yv.index = yv.index.tz_localize(ROME)
        yv.index = yv.index.tz_convert(ROME)
        common = out.index.intersection(yv.index)
        if len(common):
            yvals = yv.reindex(common).fillna(0.0)
            lsvals = out.loc[common, "ls_volume"].fillna(0.0)
            out.loc[common, "Volume"] = yvals
            mask = (lsvals > 0) & (yvals > 0)
            if mask.any() and float(lsvals[mask].sum()) > 0:
                ratio = float(yvals[mask].sum()) / float(lsvals[mask].sum())
            tail = out.index.difference(common)
            if len(tail):
                if ratio and ratio > 0:
                    out.loc[tail, "Volume"] = out.loc[tail, "ls_volume"] * ratio
                else:
                    # no scale: if we are still in the cash session, extrapolate recent yf pace
                    recent = yvals[yvals > 0].tail(3)
                    avg = float(recent.mean()) if len(recent) else 0.0
                    for ts in tail:
                        if out.at[ts, "ls_volume"] > 0:
                            continue
                        if avg > 0:
                            out.at[ts, "Volume"] = avg
            vol_src = "yfinance+ls_tape"
    out.attrs = dict(getattr(bars, "attrs", {}) or {})
    out.attrs["volume_source"] = vol_src
    if ratio:
        out.attrs["ls_vol_scale"] = ratio
    return out


# ---------------- live bid/ask/mid from the public instrument page ----------------
def fetch_html_quote(instrument_id, use_cache=True):
    """Parse bid/ask/mid/midTime from the public instrument page (same fields the live stream updates).

    Measured delay is typically ~20-40 seconds (page max-age=30). Returns a dict or None.
    """
    instrument_id = int(instrument_id)
    if use_cache and instrument_id in _quote_memo:
        t0, q = _quote_memo[instrument_id]
        if time.monotonic() - t0 < QUOTE_CACHE_SEC:
            return q
    try:
        raw, _hdrs = _get_raw(QUOTE_PATH.format(id=instrument_id))
        html = raw.decode("utf-8", errors="replace")
    except Exception:
        return _quote_memo.get(instrument_id, (0, None))[1] if instrument_id in _quote_memo else None
    import re
    from html import unescape
    item = f"{instrument_id}@1"
    def field(name):
        pats = [
            rf'<span[^>]*item="{item}"[^>]*field="{name}"[^>]*>(.*?)</span>',
            rf'<span[^>]*field="{name}"[^>]*item="{item}"[^>]*>(.*?)</span>',
        ]
        for p in pats:
            ms = re.findall(p, html, re.S)
            if ms:
                return unescape(re.sub(r"<[^>]+>", "", ms[0])).replace("\xa0", " ").strip()
        return None
    mid, bid, ask = _num(field("mid")), _num(field("bid")), _num(field("ask"))
    mid_time_s = field("midTime")
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
    if mid is None:
        return None
    now = now_rome()
    ts = now
    if mid_time_s:
        try:
            hh, mm, *rest = mid_time_s.replace(".", ":").split(":")
            ss = int(rest[0]) if rest else 0
            ts = datetime(now.year, now.month, now.day, int(hh), int(mm), ss, tzinfo=BERLIN).astimezone(ROME)
            # crossed midnight: if quote time is way in the future, it was yesterday
            if (ts - now).total_seconds() > 12 * 3600:
                ts = ts - __import__("datetime").timedelta(days=1)
        except Exception:
            ts = now
    q = dict(
        mid=mid, bid=bid, ask=ask, last_ts=ts,
        bid_size=_num(field("bidSize")), ask_size=_num(field("askSize")),
        delay_sec=(now - ts).total_seconds(), source="ls_quote",
    )
    _quote_memo[instrument_id] = (time.monotonic(), q)
    return q


def _apply_live_quote(bars, quote, last_trade=None, interval="5min"):
    """Update attrs and the current bar with a live mid/bid/ask and optional last print."""
    a = dict(getattr(bars, "attrs", {}) or {})
    now = now_rome()
    if quote:
        a["bid"] = quote.get("bid")
        a["ask"] = quote.get("ask")
        a["bid_size"] = quote.get("bid_size")
        a["ask_size"] = quote.get("ask_size")
        if quote.get("last_ts") is not None and (a.get("last_ts") is None or quote["last_ts"] >= a["last_ts"]):
            a["last_mid"] = quote["mid"]
            a["last_ts"] = quote["last_ts"]
            a["source"] = "ls_quote"
        a["delay_sec"] = (now - a["last_ts"]).total_seconds() if a.get("last_ts") is not None else quote.get("delay_sec")
    if last_trade:
        tts, tpx, tsz = last_trade
        a["last_trade"] = tpx
        a["last_trade_ts"] = tts
        a["last_trade_size"] = tsz
        # a very recent print is a better last than a slightly stale mid
        if a.get("last_ts") is None or tts >= a["last_ts"]:
            # don't overwrite mid with trade if the quote is newer
            if quote is None or tts >= quote.get("last_ts", tts):
                a["last_mid"] = tpx
                a["last_ts"] = tts
                a["source"] = a.get("source") or "ls_tape"
                a["delay_sec"] = (now - tts).total_seconds()
    # extend the current (or new) bar so 1-2 min position watches can hit intra-bar stops
    px = a.get("last_mid")
    ts = a.get("last_ts")
    if px is not None and ts is not None and len(bars):
        minutes = 5 if str(interval).startswith("5") else 1
        bucket = ts.astimezone(ROME).replace(second=0, microsecond=0)
        bucket = bucket.replace(minute=(bucket.minute // minutes) * minutes)
        bid = a.get("bid") if a.get("bid") is not None else px
        ask = a.get("ask") if a.get("ask") is not None else px
        if bucket in bars.index:
            bars.at[bucket, "High"] = max(float(bars.at[bucket, "High"]), px, ask)
            bars.at[bucket, "Low"] = min(float(bars.at[bucket, "Low"]), px, bid)
            bars.at[bucket, "Close"] = px
        elif bucket > bars.index[-1]:
            last_close = float(bars["Close"].iloc[-1])
            bars.loc[bucket] = {
                "Open": last_close, "High": max(last_close, px, ask),
                "Low": min(last_close, px, bid), "Close": px,
                "Volume": bars["ls_volume"].iloc[-1] * 0 if "ls_volume" in bars.columns else 0.0,
                **({"ls_volume": 0.0} if "ls_volume" in bars.columns else {}),
            }
            bars.sort_index(inplace=True)
    bars.attrs = a
    return bars


def _store_tape(tape_by_ticker):
    con = _bars_db()
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS tape("
            "ticker TEXT, ts TEXT, price REAL, size REAL, PRIMARY KEY(ticker, ts, price, size))"
        )
        for ticker, rows in tape_by_ticker.items():
            con.executemany(
                "INSERT OR IGNORE INTO tape(ticker,ts,price,size) VALUES(?,?,?,?)",
                [(ticker, ts.isoformat(timespec="milliseconds"), px, sz) for ts, px, sz in rows],
            )
        con.commit()
    finally:
        con.close()


# ---------------- public API used by common.py ----------------
def last_delay_summary():
    """Human-readable delay summary for the most recent LS batch, or empty string."""
    if not _delay_log:
        return ""
    bits = [f"{t} {d:.0f}s" for t, d, mid, ts in _delay_log]
    delays = [d for t, d, mid, ts in _delay_log]
    return (f"LS quote delay median {sorted(delays)[len(delays)//2]:.0f}s "
            f"(n={len(delays)}, {', '.join(bits)})")


def fetch_ls_for_tickers(universe_rows, interval="5min", yf_bars=None):
    """Fetch LS today-bars + live quote for a list of universe dicts (must have ticker, isin).

    Returns dict ticker -> DataFrame (5m or 1m OHLC, Rome tz) with attrs:
      source, currency='EUR', last_ts, last_mid, bid, ask, delay_sec, instrumentId,
      volume_source, last_trade (if any).
    Volume is a yfinance + LS-tape blend when yf_bars is provided (see blend_volume).
    Missing/failed names are omitted (caller falls back to yfinance).
    """
    global _delay_log
    _delay_log = []
    out = {}
    rows = list(universe_rows)[:MAX_TICKERS_PER_CALL]
    iv = "5min" if str(interval).startswith("5") else "1min"
    try:
        tape = fetch_today_tape(rows)
    except Exception:
        tape = {}
    now = now_rome()
    for u in rows:
        ticker = u["ticker"]
        try:
            inst = resolve_instrument(u.get("isin", ""), name=u.get("name"), ticker=ticker)
            if not inst:
                continue
            pts, info = fetch_intraday_points(inst["instrumentId"])
            if not pts:
                continue
            last_ts, last_mid = pts[-1]
            delay = (now - last_ts).total_seconds()
            if delay < -7200:
                continue
            bars = points_to_bars(pts, iv)
            if bars.empty:
                continue
            bars.attrs = dict(
                source="ls",
                currency="EUR",
                last_ts=last_ts,
                last_mid=last_mid,
                delay_sec=delay,
                instrumentId=inst["instrumentId"],
                isin=inst.get("isin") or u.get("isin"),
            )
            yf_one = None
            if yf_bars and ticker in yf_bars:
                yf_one = yf_bars[ticker]
            bars = blend_volume(bars, yf_one, tape.get(ticker) or [], iv)
            quote = None
            try:
                quote = fetch_html_quote(inst["instrumentId"])
            except Exception:
                quote = None
            last_tr = (tape.get(ticker) or [None])[-1] if tape.get(ticker) else None
            bars = _apply_live_quote(bars, quote, last_tr, iv)
            delay = bars.attrs.get("delay_sec", delay)
            last_mid = bars.attrs.get("last_mid", last_mid)
            last_ts = bars.attrs.get("last_ts", last_ts)
            out[ticker] = bars
            _delay_log.append((ticker, delay, last_mid, last_ts))
            try:
                _store_points(ticker, pts, delay)
            except Exception:
                pass
        except Exception:
            continue
    return out

# ---------------- CLI diagnostics ----------------
def _cli():
    import argparse, csv, sys
    sys.path.insert(0, BASE)
    p = argparse.ArgumentParser(description="LS public quote diagnostics (paper trading)")
    p.add_argument("--ping", action="store_true", help="measure LS vs yfinance delay for today's watchlist")
    p.add_argument("--quote", metavar="TICKER", help="print LS last mid for one ticker")
    p.add_argument("--universe", action="store_true", help="resolve + quote a few sample names")
    args = p.parse_args()

    uni = list(csv.DictReader(open(os.path.join(BASE, "universe.csv"))))
    by_t = {r["ticker"]: r for r in uni}

    if args.quote:
        u = by_t.get(args.quote)
        if not u:
            print("unknown ticker", args.quote); return 1
        got = fetch_ls_for_tickers([u], interval="1min")
        b = got.get(args.quote)
        if b is None:
            print("no LS quote"); return 2
        a = b.attrs
        print(f"{args.quote} mid={a['last_mid']} EUR  bid={a.get('bid')} ask={a.get('ask')}  "
              f"ts={a['last_ts']}  delay={a['delay_sec']:.0f}s  src={a.get('source')}  id={a['instrumentId']}")
        vol = float(b['Volume'].sum()) if 'Volume' in b.columns else 0
        lsv = float(b['ls_volume'].sum()) if 'ls_volume' in b.columns else 0
        print(f"bars {len(b)}  last {b.index[-1]} close={float(b['Close'].iloc[-1])}  "
              f"vol={vol:.0f} ls_vol={lsv:.0f} ({a.get('volume_source')}) last_trade={a.get('last_trade')}")
        return 0

    tickers = []
    wl_path = os.path.join(DATA, f"watchlist_{now_rome():%Y-%m-%d}.json")
    if args.ping and os.path.exists(wl_path):
        wl = json.load(open(wl_path))
        tickers = [it["ticker"] for it in wl.get("items", [])]
    if not tickers:
        tickers = ["SAP.DE", "SIE.DE", "TIT.MI", "AAPL", "AMD", "ASML.AS"]
    rows = [by_t[t] for t in tickers if t in by_t]
    print("NOW", now_rome().isoformat(timespec="seconds"))
    got = fetch_ls_for_tickers(rows, interval="5min")
    print(last_delay_summary())
    # optional yfinance comparison
    try:
        import yfinance as yf
        yf_tickers = [t for t in tickers if t in got]
        if yf_tickers:
            df = yf.download(yf_tickers, period="1d", interval="1m", progress=False,
                             auto_adjust=False, threads=True, prepost=True)
            now = now_rome()
            for t, b in got.items():
                try:
                    if isinstance(df.columns, pd.MultiIndex):
                        y = df[t] if t in df.columns.get_level_values(0) else df.xs(t, axis=1, level=-1, drop_level=True) if False else None
                        if t in df.columns.get_level_values(0):
                            y = df[t].dropna(subset=["Close"])
                        else:
                            y = None
                    else:
                        y = df.dropna(subset=["Close"]) if len(yf_tickers) == 1 else None
                    if y is None or y.empty:
                        print(f"  {t}: LS mid={b.attrs['last_mid']:.4f} EUR delay={b.attrs['delay_sec']:.0f}s  (no yfinance 1m)")
                        continue
                    idx = y.index
                    if idx.tz is None:
                        idx = idx.tz_localize("UTC")
                    y = y.copy(); y.index = idx.tz_convert(ROME)
                    yclose = float(y["Close"].iloc[-1])
                    yage = (now - y.index[-1]).total_seconds()
                    ccy_note = "EUR" if t.endswith((".DE", ".MI", ".AS", ".PA", ".MC")) else "USD(yf)/EUR(ls)"
                    print(f"  {t}: LS mid={b.attrs['last_mid']:.4f} EUR delay={b.attrs['delay_sec']:.0f}s | "
                          f"YF 1m close={yclose:.4f} age={yage:.0f}s ({ccy_note})")
                except Exception as e:
                    print(f"  {t}: LS mid={b.attrs['last_mid']:.4f} delay={b.attrs['delay_sec']:.0f}s | yfinance cmp skip ({e})")
    except Exception as e:
        print("yfinance comparison skipped:", e)
        for t, b in got.items():
            print(f"  {t}: LS mid={b.attrs['last_mid']:.4f} EUR delay={b.attrs['delay_sec']:.0f}s ts={b.attrs['last_ts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
