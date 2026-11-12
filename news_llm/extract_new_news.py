#!/usr/bin/env python3
"""Estrae le notizie nuove da data/news.sqlite (sola lettura) rispetto a data/news_llm_state.json.

Uso (dalla root del progetto o ovunque, i percorsi si risolvono da PT_* o da questa cartella):

  python3 news_llm/extract_new_news.py
  python3 news_llm/extract_new_news.py --hours 24          # ignora lo stato, finestra mobile
  python3 news_llm/extract_new_news.py --json               # un unico oggetto JSON
  python3 news_llm/extract_new_news.py --out /tmp/new.json  # scrive su file

Non modifica news.py, news.sqlite, ledger.sqlite né gli script di trading.
Il cursore incrementale è (last_published, last_news_id): una notizia è «nuova» se
published > last_published, oppure published == last_published e id > last_news_id.
"""
from __future__ import annotations

import argparse, json, os, sqlite3, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.environ.get("PT_DATA", os.path.join(ROOT, "data"))
NEWS_DB = os.environ.get("PT_NEWS_DB", os.path.join(DATA, "news.sqlite"))
STATE = os.environ.get("PT_NEWS_LLM_STATE", os.path.join(DATA, "news_llm_state.json"))


def now():
    return datetime.now(ROME)


def load_state():
    if not os.path.exists(STATE):
        return None
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def rows_to_dicts(rows):
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "published": r["published"],
            "fetched": r["fetched"],
            "source": r["source"],
            "title": r["title"],
            "link": r["link"],
            "tickers": [t for t in (r["tickers"] or "").split(",") if t],
            "scope": r["scope"],
            "sentiment": r["sentiment"],
        })
    return out


def main():
    p = argparse.ArgumentParser(description="Estrae notizie nuove per l'Analista Notizie LLM")
    p.add_argument("--hours", type=float, default=None,
                   help="Se impostato, ignora lo stato e prende le notizie delle ultime N ore")
    p.add_argument("--json", action="store_true", help="Stampa un oggetto JSON (default: JSON Lines)")
    p.add_argument("--out", default=None, help="Percorso di output; altrimenti stdout")
    args = p.parse_args()

    if not os.path.exists(NEWS_DB):
        print(f"errore: database notizie assente: {NEWS_DB}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(f"file:{NEWS_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    state = load_state()
    mode = "hours" if args.hours is not None else ("incremental" if state else "hours")
    hours = args.hours if args.hours is not None else 24

    if mode == "incremental":
        pub = state["last_published"]
        nid = state.get("last_news_id") or ""
        rows = con.execute(
            """SELECT * FROM news
               WHERE published > ?
                  OR (published = ? AND id > ?)
               ORDER BY published ASC, id ASC""",
            (pub, pub, nid),
        ).fetchall()
        window = {"from": pub, "to": None, "mode": "incremental",
                  "last_news_id": nid}
    else:
        since = (now() - timedelta(hours=hours)).isoformat(timespec="seconds")
        rows = con.execute(
            "SELECT * FROM news WHERE published >= ? ORDER BY published ASC, id ASC",
            (since,),
        ).fetchall()
        window = {"from": since, "to": now().isoformat(timespec="seconds"),
                  "mode": "hours", "hours": hours}

    items = rows_to_dicts(rows)
    if items:
        window["to"] = items[-1]["published"]
    payload = {
        "extracted_at": now().isoformat(timespec="seconds"),
        "news_db": NEWS_DB,
        "state_path": STATE,
        "window": window,
        "count": len(items),
        "items": items,
    }

    text = json.dumps(payload if args.json or args.out else payload, ensure_ascii=False, indent=2) \
        if (args.json or args.out) else "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + ("\n" if items else "")

    if args.json and not args.out:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    elif args.out:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, args.out)
        print(f"scritte {len(items)} notizie in {args.out} (mode={window['mode']})", file=sys.stderr)
        return
    else:
        # JSONL su stdout
        text = "".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items)

    sys.stdout.write(text)
    if not items:
        print(f"# 0 notizie nuove (mode={window['mode']})", file=sys.stderr)
    else:
        print(f"# {len(items)} notizie (mode={window['mode']})", file=sys.stderr)


if __name__ == "__main__":
    main()
