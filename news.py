#!/usr/bin/env python3
"""News & sentiment monitor (PAPER). Runs around the clock (every 1-2 h, nights/weekends too).
Sources (verified from this box): yfinance per-ticker news, Google News RSS per ticker (EN/IT/DE query),
macro RSS: CNBC Top/Markets, MarketWatch, Investing.com, FXStreet, Il Sole 24 Ore Finanza.
Dedupes by link/title hash, scores sentiment with a finance keyword lexicon (EN/IT/DE), tags tickers,
stores in data/news.sqlite. scan.py and trade.py read news_signal()/macro_signal().
It never trades. CLI: python3 news.py [--ticker SAP.DE] [--show] [--alerts-only [--dry-run]]

Dal 13/11/2026 (scheduler: ogni 10 min lun-ven 07:00-22:00, altrimenti ogni ora):
- lock non bloccante (data/.news.lock): se una run precedente è ancora in corso, questa esce subito;
- niente martellamento: GET condizionali con ETag/Last-Modified (data/news_fetch_state.json), ogni titolo
  interrogato al massimo ogni 30 min (10 min per i titoli in watchlist statica/dinamica di oggi), pausa di 30 min
  per un host che risponde 429/503;
- notizie forti -> watchlist dinamica (solo candidati, nessun ordine): vedi NEWS_ALERT e README."""
import hashlib, math, re, sqlite3, sys, time as _t
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import feedparser
from common import *

NEWS_DB = os.environ.get("PT_NEWS_DB", os.path.join(DATA, "news.sqlite"))
UA = "Mozilla/5.0 (X11; Linux x86_64) paper-trading-news/1.0"
MACRO_FEEDS = {
    "CNBC Top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Il Sole 24 Ore": "https://www.ilsole24ore.com/rss/finanza.xml",
}
POS = r"beat|beats|tops|surge|surges|soar|soars|jump|jumps|rall(y|ies)|upgrade[sd]?|raises? (guidance|outlook|forecast)|record|strong|outperform|buy rating|overweight|rebound|approv(al|ed)|wins?|contract|buyback|dividend (hike|increase)|profit rises|beats estimates|bullish|higher|gain[s]?|climb[s]?|" \
      r"rialz\w*|balz\w*|vola\b|corre\b|promoss\w*|utile in crescita|acquist\w*|positiv\w*|cresc\w*|guadagn\w*|" \
      r"steigt|steigen|kurssprung|hebt prognose|gewinnplus|kaufempfehlung"
NEG = r"miss(es|ed)?|plunge[sd]?|slump[ss]?|fall[s]?|fell|drop[s]?|downgrade[sd]?|cuts? (guidance|outlook|forecast)|warning|lawsuit|probe|investigation|recall|loss(es)?|weak|sell rating|underweight|layoffs?|cuts? jobs|fine[sd]?\b|sank|sink[s]?|tumble[sd]?|halt(ed)?|bankrupt\w*|fraud|crash\w*|tariff[s]?|bearish|lower|slide[s]?|selloff|sell-off|" \
      r"ribass\w*|croll\w*|scivol\w*|cede\b|perdit\w*|tagli\w*|boccia\w*|indagin\w*|mult[ae]\b|allarm\w*|negativ\w*|vendite|" \
      r"fällt|fallen|einbruch|senkt prognose|gewinnwarnung|verlust"
POS_RE, NEG_RE = re.compile(POS, re.I), re.compile(NEG, re.I)
FETCH_STATE = os.environ.get("PT_NEWS_STATE", os.path.join(DATA, "news_fetch_state.json"))
NEWS_LOCK = os.environ.get("PT_NEWS_LOCK", os.path.join(DATA, ".news.lock"))
MIN_TICKER_MIN, MIN_PRIORITY_MIN, BACKOFF_MIN = 30, 10, 30
# Soglie fissate a priori (12/11/2026, prima di qualsiasi test): notizia forte su un titolo dell'universo se
#  A) sentiment a parole chiave news_signal(6 h) con |score| >= 0,5 su almeno 3 notizie, oppure
#  B) raffica: >= 5 notizie sul titolo pubblicate negli ultimi 60 min e >= 3x la sua media oraria dei 7 giorni prima.
# Solo lun-ven 07:30-21:00; massimo 5 aggiunte per run. È un candidato per la watchlist dinamica, NON un segnale.
NEWS_ALERT = dict(score=0.5, min_count=3, hours=6, burst_n=5, burst_min=60, burst_x=3.0, max_add=5,
                  window=(time(7, 30), time(21, 0)))

def _load_state():
    try:
        return json.load(open(FETCH_STATE))
    except Exception:
        return {"feeds": {}, "tickers": {}, "backoff": {}}

def _save_state(st):
    tmp = FETCH_STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1); os.replace(tmp, FETCH_STATE)

def _parse(url, st, key, host):
    """feedparser con ETag/Last-Modified; marca il backoff dell'host su 429/503."""
    if _backoff_active(st, host):
        return None
    c = st["feeds"].get(key, {})
    f = feedparser.parse(url, agent=UA, etag=c.get("etag"), modified=c.get("modified"))
    code = f.get("status")
    if code in (429, 503):
        st["backoff"][host] = now().isoformat(timespec="seconds"); return None
    if f.get("etag") or f.get("modified"):
        st["feeds"][key] = dict(etag=f.get("etag"), modified=f.get("modified"))
    if code == 304:
        return []
    return f.entries

def _backoff_active(st, host):
    t = st.get("backoff", {}).get(host)
    return bool(t) and now() - datetime.fromisoformat(t) < timedelta(minutes=BACKOFF_MIN)

def _priority_tickers():
    out = set()
    try:
        out |= {i["ticker"] for i in (load_watchlist() or {}).get("items", [])}
    except Exception:
        pass
    try:
        import rescan
        out |= {i["ticker"] for i in rescan.load_dyn()}
    except Exception:
        pass
    return out

def ndb():
    con = sqlite3.connect(NEWS_DB); con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS news(id TEXT PRIMARY KEY, published TEXT, fetched TEXT, source TEXT,
                   title TEXT, link TEXT, tickers TEXT, scope TEXT, sentiment REAL)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_pub ON news(published)")
    return con

def sentiment(text):
    p, n = len(POS_RE.findall(text)), len(NEG_RE.findall(text))
    return 0.0 if p + n == 0 else round((p - n) / (p + n) * min(1.0, (p + n) / 2), 3)

def norm_title(t):
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t)  # drop " - Publisher" suffix (Google News)
    return re.sub(r"\W+", " ", t.lower()).strip()

def parse_dt(s):
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return now()
    if d.tzinfo is None: d = d.replace(tzinfo=ZoneInfo("UTC"))
    return d.astimezone(ROME)

def tag_tickers(title, uni):
    found = []
    for u in uni:
        nm = u["name"].split()[0] if u["name"] not in ("Deutsche Bank", "Deutsche Telekom", "Deutsche Boerse", "Siemens Energy", "Siemens Healthineers", "Munich Re", "Banco BPM", "Banco Santander", "Eli Lilly", "Poste Italiane", "Telecom Italia", "Heidelberg Materials") else u["name"]
        neg = r"(?!\s+(energy|healthineers))" if nm == "Siemens" else ""
        if len(nm) >= 3 and re.search(rf"\b{re.escape(nm)}\b{neg}", title, re.I):
            found.append(u["ticker"])
    return found

def fetch_ticker(u, st=None):
    out = []
    st = st if st is not None else {"feeds": {}, "tickers": {}, "backoff": {}}
    try:
        for n in (yf.Ticker(u["ticker"]).news or [])[:15]:
            c = n.get("content", n)
            link = (c.get("canonicalUrl") or {}).get("url") or c.get("link") or ""
            out.append(("yfinance", c.get("title", ""), link, c.get("pubDate") or c.get("providerPublishTime", "")))
    except Exception: pass
    kw = {"US": "stock", "EU": "stock OR azioni OR Aktie"}[u["region"]]
    q = quote_plus(f'"{u["name"]}" ({kw}) when:2d')
    lang = "hl=it&gl=IT&ceid=IT:it" if u["ticker"].endswith(".MI") else "hl=en-US&gl=US&ceid=US:en"
    try:
        entries = _parse(f"https://news.google.com/rss/search?q={q}&{lang}", st, "gn:" + u["ticker"], "news.google.com") or []
        for e in entries[:20]:
            out.append(("Google News", e.get("title", ""), e.get("link", ""), e.get("published", "")))
    except Exception: pass
    return u, out

def fetch_macro(item):
    name, url, st = item
    try:
        entries = _parse(url, st, "macro:" + name, url.split("/")[2]) or []
        return name, [(name, e.get("title", ""), e.get("link", ""), e.get("published", "")) for e in entries[:40]]
    except Exception:
        return name, []

def due_tickers(uni, st, n=None):
    """Titoli da interrogare in questa run: mai più spesso di MIN_TICKER_MIN (MIN_PRIORITY_MIN se in watchlist)."""
    n = n or now(); pri = _priority_tickers(); out = []
    for u in uni:
        last = st["tickers"].get(u["ticker"])
        gap = MIN_PRIORITY_MIN if u["ticker"] in pri else MIN_TICKER_MIN
        if not last or n - datetime.fromisoformat(last) >= timedelta(minutes=gap - 1):
            out.append(u)
    return out

def run():
    uni = load_universe(); con = ndb(); fetched = now().isoformat(timespec="seconds")
    st = _load_state(); st.setdefault("feeds", {}); st.setdefault("tickers", {}); st.setdefault("backoff", {})
    todo = due_tickers(uni, st)
    seen = {r[0] for r in con.execute("SELECT id FROM news")}
    new = 0; stats = {}
    def store(src, title, link, pub, tickers, scope):
        nonlocal new
        if not title: return
        key = hashlib.sha1(norm_title(title).encode()).hexdigest()[:16]
        if key in seen:
            if tickers:  # merge ticker tags
                r = con.execute("SELECT tickers FROM news WHERE id=?", (key,)).fetchone()
                tags = set(filter(None, (r[0] or "").split(","))) | set(tickers)
                con.execute("UPDATE news SET tickers=? WHERE id=?", (",".join(sorted(tags)), key))
            return
        seen.add(key); new += 1
        con.execute("INSERT INTO news VALUES(?,?,?,?,?,?,?,?,?)", (key, parse_dt(pub).isoformat(timespec="seconds"),
                    fetched, src, title, link, ",".join(sorted(set(tickers))), scope, sentiment(title)))
    with ThreadPoolExecutor(8) as ex:
        for u, items in ex.map(lambda x: fetch_ticker(x, st), todo):
            st["tickers"][u["ticker"]] = fetched
            for src, title, link, pub in items:
                if parse_dt(pub) < now() - timedelta(days=3): continue
                store(src, title, link, pub, tag_tickers(title, uni), "ticker")  # tag only if name is in the headline
                stats[src] = stats.get(src, 0) + 1
        for name, items in ex.map(fetch_macro, [(k, v, st) for k, v in MACRO_FEEDS.items()]):
            stats[name] = len(items)
            for src, title, link, pub in items:
                store(src, title, link, pub, tag_tickers(title, uni), "macro")
    con.execute("DELETE FROM news WHERE published < ?", ((now() - timedelta(days=30)).isoformat(),))
    con.commit()
    _save_state(st)
    bo = [h for h in st["backoff"] if _backoff_active(st, h)]
    log(f"news: {new} nuove notizie; titoli interrogati {len(todo)}/{len(uni)}; fonti: {stats}"
        + (f"; host in pausa: {bo}" if bo else ""), "news")
    return new

def news_alerts(n=None, dry=False):
    """Titoli dell'universo con notizia forte (soglie NEWS_ALERT) -> watchlist dinamica come candidati. Mai ordini."""
    n = n or now()
    if is_weekend(n.date()) or not (NEWS_ALERT["window"][0] <= n.time() <= NEWS_ALERT["window"][1]):
        return []
    if not os.path.exists(NEWS_DB):
        return []
    con = ndb(); found = []
    t60 = (n - timedelta(minutes=NEWS_ALERT["burst_min"])).isoformat()
    t7 = (n - timedelta(days=7)).isoformat()
    for u in load_universe():
        t = u["ticker"]; like = f"%,{t},%"
        sg = news_signal(t, NEWS_ALERT["hours"])
        why = []
        if abs(sg["score"]) >= NEWS_ALERT["score"] and sg["count"] >= NEWS_ALERT["min_count"]:
            why.append(f"sentiment parole chiave {NEWS_ALERT['hours']}h {sg['score']:+.2f} su {sg['count']} notizie")
        c60 = con.execute("SELECT COUNT(*) FROM news WHERE published>=? AND published<=? AND (','||tickers||',') LIKE ?",
                          (t60, n.isoformat(), like)).fetchone()[0]
        c7 = con.execute("SELECT COUNT(*) FROM news WHERE published>=? AND published<? AND (','||tickers||',') LIKE ?",
                         (t7, t60, like)).fetchone()[0]
        base = c7 / (7 * 24 - 1)
        if c60 >= NEWS_ALERT["burst_n"] and c60 >= NEWS_ALERT["burst_x"] * base:
            why.append(f"raffica di {c60} notizie in {NEWS_ALERT['burst_min']} min (media oraria 7gg {base:.1f})")
        if why:
            found.append((abs(sg["score"]) + c60 / 10, dict(
                ticker=t, name=u["name"], region=u["region"], currency=u["currency"], added_at=n.strftime("%H:%M"),
                move=None, rvol=None, atr_d=None, source="notizie (news.py)", news_impact=sg["score"],
                rationale="; ".join(why) + (f"; top: {sg['top']}" if sg.get("top") else ""))))
    found.sort(key=lambda x: -x[0])
    items = [x[1] for x in found]
    import rescan
    if dry:
        would = rescan.add_items(items, dry=True)[:NEWS_ALERT["max_add"]]
        print(f"notizie forti: {[i['ticker'] for i in items]}; da aggiungere (dry-run): {would}")
        for i in items:
            print(f"  {i['ticker']}: {i['rationale']}"[:220])
        return would
    have = {i["ticker"] for i in rescan.load_dyn()}
    items = [i for i in items if i["ticker"] not in have][:NEWS_ALERT["max_add"]]
    added = rescan.add_items(items, dict(at=n.isoformat(timespec="seconds"), regions=["news"], scanned=0,
                                         candidates=len(found), added=[i["ticker"] for i in items])) if items else []
    for i in items:
        if i["ticker"] in added:
            log(f"watchlist dinamica +{i['ticker']} (notizia forte): {i['rationale']}"[:300], "news")
    return added

# ---------- consumers ----------
def news_signal(ticker, hours=24):
    """Recency-weighted sentiment for a ticker: dict(score -1..1, count, top)."""
    if not os.path.exists(NEWS_DB): return dict(score=0.0, count=0, top=None)
    con = ndb(); since = (now() - timedelta(hours=hours)).isoformat()
    rows = con.execute("SELECT * FROM news WHERE published>=? AND (','||tickers||',') LIKE ?",
                       (since, f"%,{ticker},%")).fetchall()
    if not rows: return dict(score=0.0, count=0, top=None)
    num = den = 0.0; top = None
    for r in rows:
        age = (now() - datetime.fromisoformat(r["published"])).total_seconds() / 3600
        w = math.exp(-max(age, 0) / 12)
        num += w * r["sentiment"]; den += w
        if top is None or abs(r["sentiment"]) * w > abs(top["sentiment"]) * top["w"]:
            top = dict(r); top["w"] = w
    return dict(score=round(num / den, 3) if den else 0.0, count=len(rows),
                top=f"{top['title']} ({top['source']}, {top['published'][8:10]}/{top['published'][5:7]} {top['published'][11:16]})" if top else None)

def macro_signal(hours=12):
    if not os.path.exists(NEWS_DB): return dict(score=0.0, count=0)
    con = ndb()
    rows = con.execute("SELECT sentiment FROM news WHERE scope='macro' AND published>=?",
                       ((now() - timedelta(hours=hours)).isoformat(),)).fetchall()
    s = [r[0] for r in rows]
    return dict(score=round(sum(s) / len(s), 3) if s else 0.0, count=len(s))

class NewsLock:
    """Lock non bloccante: due run di news.py non si sovrappongono mai (quella nuova esce)."""
    def __enter__(self):
        import fcntl
        self.f = open(NEWS_LOCK, "w")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB); self.ok = True
        except OSError:
            self.ok = False
        return self
    def __exit__(self, *a):
        import fcntl
        if self.ok:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()

if __name__ == "__main__":
    if "--alerts-only" in sys.argv:
        news_alerts(dry="--dry-run" in sys.argv); sys.exit()
    if "--ticker" in sys.argv:
        t = sys.argv[sys.argv.index("--ticker") + 1]; print(t, news_signal(t)); sys.exit()
    if "--show" not in sys.argv:
        with NewsLock() as L:
            if not L.ok:
                log("news: run precedente ancora in corso, salto questa", "news"); sys.exit()
            t0 = _t.time()
            run()
            try:
                news_alerts()
            except Exception as e:
                log(f"news: errore nel collegamento notizie->watchlist dinamica: {e}", "news")
            log(f"news: run completata in {_t.time() - t0:.0f} s", "news")
    m = macro_signal(); print(f"sentiment macro 12h: {m['score']:+.2f} su {m['count']} titoli")
    sig = sorted(((u["ticker"], news_signal(u["ticker"])) for u in load_universe()), key=lambda x: -abs(x[1]["score"]))
    for t, s in sig[:10]:
        print(f"  {t:9} {s['score']:+.2f} ({s['count']} notizie) {s['top'] or ''}"[:160])
