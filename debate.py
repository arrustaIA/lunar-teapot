#!/usr/bin/env python3
"""Filtro sperimentale "dibattito" LLM – SOLO SHADOW (PAPER): nessun ordine, nessuna scrittura sul ledger.

Prova pre-registrata (R&D reports/preregistration_2026-11-16_debate.md), richiesta di Andrea per il 16/11/2026.
Per ogni segnale live V0 / V0_LOOSE / NEWS_LLM visto da shadow.py tre chiamate LLM:
PRO (argomenta l'ingresso nel verso del segnale), CONTRO, GIUDICE -> ENTRA / SCARTA + motivo.
Input: solo dati noti al momento del segnale (prezzo, OR, VWAP, momentum, ATR, titoli di notizie pubblicati
fino a quel momento, giudizio Natasia). La decisione è scritta in data/debate_decisions.jsonl (solo in aggiunta)
con il suo timestamp; l'esito si calcola solo a fine giornata (shadow.py --eod) e una decisione conta solo se
registrata prima dell'uscita simulata.

LLM: GitHub Models è stato ritirato il 30/07/2026, quindi si usa l'endpoint anonimo gratuito di Pollinations
(OpenAI-compatibile, modello gpt-oss-20b), SENZA chiavi né header Authorization. Limiti: max 3 chiamate per
segnale, max 40 segnali e 120 chiamate al giorno, dedup giorno+strategia+titolo, timeout 45 s, >= 31 s tra due
chiamate (limite per IP del servizio). Errore/limite -> verdetto NON_DECISO, mai blocchi per gli altri job.

Uso: python3 debate.py --worker            (lanciato in background da shadow.py dopo ogni ciclo, lock esclusivo)
     python3 debate.py --worker --dry-run  (mostra i segnali in attesa e il prompt, nessuna chiamata)
     python3 debate.py --eod [--dry-run]   (esiti e confronto; normalmente chiamato da shadow.py --eod)
     python3 debate.py --ping              (una chiamata di prova all'API)
Variabili (solo test): DEBATE_DIR (cartella dati), DEBATE_ENDPOINT, DEBATE_OFF=1 (nessuna chiamata).
"""
import fcntl, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta
from common import CFG, ROME, DATA, log, now, today, flatten_time, to_eur, TAX_RATE

S = "debate"
OUT = os.environ.get("DEBATE_DIR", os.environ.get("PT_SHADOW_DIR", DATA))
SHADOW_SIG = os.path.join(OUT, "shadow_signals.jsonl")      # V0_LOOSE (scritto da shadow.py)
SIGF = os.path.join(OUT, "debate_signals.jsonl")            # V0 e NEWS_LLM (scritti da shadow.py, solo per il dibattito)
DEC = os.path.join(OUT, "debate_decisions.jsonl")
RESF = os.path.join(OUT, "debate_results.jsonl")
LOCKF = os.path.join(OUT, ".debate.lock")
NEWS_DB = os.path.join(DATA, "news.sqlite")
NEWS_LLM = os.path.join(DATA, "news_llm.json")
STRATS = ("V0", "V0_LOOSE", "NEWS_LLM")
ENDPOINT = os.environ.get("DEBATE_ENDPOINT", "https://text.pollinations.ai/openai")
MODEL = "openai"            # alias Pollinations del modello anonimo gratuito (oggi gpt-oss-20b)
PROVIDER = "pollinations-anonimo"
LIM = dict(max_signals_day=40, max_calls_day=120, timeout=45, min_gap_s=31, worker_max_s=25 * 60, retries=1,
           first_day="2026-11-16")
_last_call = [0.0]


def _lines(path):
    out = []
    if os.path.exists(path):
        for l in open(path):
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def append(path, row):
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def key(r):
    return (r.get("day"), r.get("strategy"), r.get("ticker"))


def signals(day):
    rows = [r for r in _lines(SHADOW_SIG) if r.get("day") == day and r.get("strategy") == "V0_LOOSE"]
    rows += [r for r in _lines(SIGF) if r.get("day") == day and r.get("strategy") in STRATS]
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: x.get("ts", "")):
        if key(r) not in seen:
            seen.add(key(r)); out.append(r)
    return out


def pending(day):
    done = {key(d) for d in _lines(DEC) if d.get("day") == day}
    return [r for r in signals(day) if key(r) not in done]


# ---------------- contesto (solo dati noti al momento del segnale) ----------------
def headlines(ticker, ts, n=4, hours=24):
    if not os.path.exists(NEWS_DB):
        return []
    try:
        con = sqlite3.connect(f"file:{NEWS_DB}?mode=ro", uri=True, timeout=10)
        t0 = (datetime.fromisoformat(ts) - timedelta(hours=hours)).isoformat()
        rows = con.execute("SELECT published, title FROM news WHERE published>=? AND published<=? AND fetched<=? "
                           "AND (','||tickers||',') LIKE ? ORDER BY published DESC LIMIT ?",
                           (t0, ts, ts, f"%,{ticker},%", n)).fetchall()
        con.close()
        return [f"{p[11:16]} {t[:140]}" for p, t in rows]
    except Exception:
        return []


def macro_note(ts):
    try:
        j = json.load(open(NEWS_LLM))
        if j.get("generated_at") and j["generated_at"] <= ts:
            m = j.get("macro") or {}
            return f"bias macro {m.get('bias')} (conf. {m.get('confidence')}): {str(m.get('summary', ''))[:220]}"
    except Exception:
        pass
    return None


def facts(r):
    side = r.get("side", "long")
    c = r.get("ctx") or {}
    lines = [f"Titolo {r['ticker']} ({r.get('region')}), strategia {r['strategy']}, verso {side.upper()}, "
             f"ora segnale {r['ts'][11:16]} (Roma).",
             f"Prezzo {r.get('price')} {r.get('currency', 'EUR')}, ingresso simulato {r.get('entry')}, stop {r.get('stop')}, "
             f"target {r.get('target')} (2R, breakeven a +1R, chiusura forzata 21:50)."]
    if c:
        lines.append("Dati intraday: " + ", ".join(f"{k} {v}" for k, v in c.items() if v is not None))
    if r.get("info"):
        lines.append(f"Note del segnale: {r['info']}")
    if r.get("chart_score") is not None:
        lines.append(f"Analista grafico: punteggio {r.get('chart_score')} ({r.get('chart_verdict')}).")
    nat = r.get("natasia")
    if nat:
        lines.append(f"Giudizio analista notizie (emesso {str(nat.get('issued_at'))[:16]}): impatto {nat.get('impact')}, "
                     f"confidenza {nat.get('confidence')}, orizzonte {nat.get('horizon')}: {str(nat.get('rationale', ''))[:300]}")
    h = headlines(r["ticker"], r["ts"])
    if not h and nat:
        h = [x[:140] for x in (nat.get("key_headlines") or [])[:3]]
    lines.append("Ultime notizie pubblicate: " + (" | ".join(h) if h else "nessuna"))
    m = macro_note(r["ts"])
    if m:
        lines.append(m)
    return "\n".join(lines)


SYS = ("Sei un analista di trading intraday (simulazione con soldi finti). Commissioni 1 EUR per ordine, tassa 26% sui "
       "guadagni. Usa SOLO i dati forniti, non inventare prezzi o notizie. Rispondi in italiano, conciso.")


def prompts(r):
    f = facts(r); side = r.get("side", "long")
    verso = "rialzo (LONG)" if side == "long" else "ribasso (SHORT)"
    pro = [{"role": "system", "content": SYS},
           {"role": "user", "content": f"{f}\n\nSei l'avvocato A FAVORE: argomenta in massimo 70 parole perché conviene "
                                       f"entrare ORA in {verso} con questo stop e target."}]
    con = [{"role": "system", "content": SYS},
           {"role": "user", "content": f"{f}\n\nSei l'avvocato CONTRO: argomenta in massimo 70 parole perché NON conviene "
                                       f"entrare ora in {verso} (rischi, falso segnale, costi)."}]
    return f, pro, con


def judge_msgs(f, a, b):
    return [{"role": "system", "content": SYS + ' Sei il GIUDICE. Rispondi SOLO con JSON: {"verdetto": "ENTRA" oppure '
                                                '"SCARTA", "motivo": "massimo 30 parole"}.'},
            {"role": "user", "content": f"{f}\n\nTesi A FAVORE:\n{a}\n\nTesi CONTRO:\n{b}\n\nDecidi se entrare."}]


# ---------------- API ----------------
class ApiError(Exception):
    pass


def chat(messages, max_tokens=500):
    if os.environ.get("DEBATE_OFF") == "1":
        raise ApiError("API disattivata (DEBATE_OFF=1)")
    wait = LIM["min_gap_s"] - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    body = json.dumps(dict(model=MODEL, messages=messages, max_tokens=max_tokens, reasoning_effort="low",
                           temperature=0.3)).encode()
    last = None
    for attempt in range(LIM["retries"] + 1):
        req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json",
                                                                   "User-Agent": "paper-sim-research/1.0"})
        try:
            _last_call[0] = time.time()
            with urllib.request.urlopen(req, timeout=LIM["timeout"]) as resp:
                d = json.loads(resp.read().decode())
                txt = (d["choices"][0]["message"].get("content") or "").strip()
                if not txt:
                    raise ApiError("risposta vuota")
                return txt, resp.headers.get("x-model-used") or d.get("model") or MODEL
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            ra = e.headers.get("Retry-After") if e.headers else None
            if e.code in (402, 429, 503) and attempt < LIM["retries"]:
                time.sleep(min(60, max(LIM["min_gap_s"], int(float(ra)) if ra else LIM["min_gap_s"])))
                continue
            break
        except ApiError:
            raise
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:120]}"
            if attempt < LIM["retries"]:
                time.sleep(LIM["min_gap_s"]); continue
    raise ApiError(last or "errore sconosciuto")


def parse_verdict(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            v = str(j.get("verdetto", "")).upper().strip()
            if v in ("ENTRA", "SCARTA"):
                return v, str(j.get("motivo", ""))[:300]
        except Exception:
            pass
    u = txt.upper()
    has_e, has_s = "ENTRA" in u, "SCARTA" in u
    if has_e != has_s:
        return ("ENTRA" if has_e else "SCARTA"), txt[:300]
    return None, txt[:300]


def calls_today(day):
    return sum(int(d.get("calls") or 0) for d in _lines(DEC) if d.get("day") == day)


def decide(r, call=chat):
    """Esegue PRO, CONTRO, GIUDICE. Ritorna la riga di decisione (non la scrive)."""
    day = r["day"]
    base = dict(day=day, strategy=r["strategy"], ticker=r["ticker"], region=r.get("region"), side=r.get("side", "long"),
                ts_signal=r["ts"], bar=r.get("bar"), price=r.get("price"), entry=r.get("entry"), stop=r.get("stop"),
                target=r.get("target"), currency=r.get("currency", "EUR"), provider=PROVIDER, note="SHADOW: nessun ordine")
    n_dec = len({key(d) for d in _lines(DEC) if d.get("day") == day and d.get("verdict") != "NON_DECISO"})
    used = calls_today(day)
    if n_dec >= LIM["max_signals_day"] or used + 3 > LIM["max_calls_day"]:
        return dict(base, ts_decision=now().isoformat(timespec="seconds"), verdict="NON_DECISO", calls=0, model=None,
                    error=f"tetto giornaliero ({n_dec} segnali, {used} chiamate)")
    f, pro, con = prompts(r)
    calls, model, out = 0, None, {}
    try:
        out["pro"], model = call(pro, 450); calls += 1
        out["contro"], model = call(con, 450); calls += 1
        jt, model = call(judge_msgs(f, out["pro"][:800], out["contro"][:800]), 350); calls += 1
        v, why = parse_verdict(jt)
        err = None if v else "verdetto non leggibile"
    except ApiError as e:
        v, why, err = None, None, str(e)
    ts = now()
    return dict(base, ts_decision=ts.isoformat(timespec="seconds"),
                lag_min=round((ts - datetime.fromisoformat(r["ts"])).total_seconds() / 60, 1),
                verdict=v or "NON_DECISO", motivo=why, pro=(out.get("pro") or "")[:500], contro=(out.get("contro") or "")[:500],
                model=model, calls=calls, error=err)


def worker(dry=False, max_s=None, call=chat):
    max_s = max_s or LIM["worker_max_s"]
    d = today().isoformat()
    if d < LIM["first_day"] and not os.environ.get("DEBATE_DIR"):
        return 0
    lk = open(LOCKF, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0              # un altro worker è già attivo
    t0, n = time.time(), 0
    while time.time() - t0 < max_s:
        todo = [r for r in pending(d) if now() < flatten_time(r.get("region", "EU"), datetime.fromisoformat(r["ts"]).date())]
        if not todo:
            break
        r = todo[0]
        if dry:
            for x in todo:
                print(f"in attesa: {x['strategy']} {x['ticker']} {x.get('side', 'long')} {x['ts']}")
            print("--- prompt PRO del primo ---\n" + prompts(r)[1][1]["content"]); break
        twin = next((x for x in _lines(DEC) if x.get("day") == d and x.get("ticker") == r["ticker"]
                     and x.get("bar") == r.get("bar") and x.get("side") == r.get("side", "long")
                     and x.get("entry") == r.get("entry") and x.get("stop") == r.get("stop")
                     and x.get("verdict") in ("ENTRA", "SCARTA")), None)
        if twin:   # stesso setup già discusso (es. V0 e V0_LOOSE sulla stessa barra): riuso, zero chiamate
            row = dict(twin, strategy=r["strategy"], ts_signal=r["ts"], target=r.get("target"), calls=0,
                       ts_decision=now().isoformat(timespec="seconds"), riuso_da=twin["strategy"])
        else:
            row = decide(r, call=call)
        append(DEC, row); n += 1
        log(f"DIBATTITO {row['strategy']} {row['ticker']} {row['side']}: {row['verdict']} "
            f"({row.get('calls')} chiamate, ritardo {row.get('lag_min')} min){' – ' + row['error'] if row.get('error') else ''}", S)
    fcntl.flock(lk, fcntl.LOCK_UN); lk.close()
    return n


# ---------------- esiti a fine giornata ----------------
def simulate(r, b):
    """Stesse regole d'uscita della strategia (stop, target 2R, breakeven a +1R, chiusura 21:50), long o short.
    Sizing diagnostico su 1.000 € (rischio 2%, cap 30%, senza filtri minimi). Ritorna dict o None."""
    import pandas as pd
    side = r.get("side", "long"); sgn = 1 if side == "long" else -1
    e, st, tg = float(r["entry"]), float(r["stop"]), float(r["target"])
    risk = abs(e - st)
    if risk <= 0:
        return None
    ccy = r.get("currency", "EUR"); fees = 2 * CFG["fee_per_order"]; notional = CFG["start_cash"]
    px_e, de = to_eur(e, ccy), to_eur(risk, ccy)
    q = max(0.0, min((CFG["risk_per_trade"] * notional - fees) / de, CFG["max_position_pct"] * notional / px_e))
    q = int(q * 1e4) / 1e4
    if q <= 0:
        return None
    fl = flatten_time(r.get("region", "EU"), datetime.fromisoformat(r["ts"]).date())
    fut = b[(b.index > pd.Timestamp(r["bar"])) & (b.index < fl)]
    px, why, exit_ts = None, "fine giornata", fl
    step = timedelta(minutes=5)
    for ts, x in fut.iterrows():
        if (x["Low"] <= st) if sgn > 0 else (x["High"] >= st):
            px = (min(st, x["Open"]) * (1 - CFG["slippage"])) if sgn > 0 else (max(st, x["Open"]) * (1 + CFG["slippage"]))
            why, exit_ts = "stop", ts.to_pydatetime() + step; break
        if (x["High"] >= tg) if sgn > 0 else (x["Low"] <= tg):
            px = max(tg, x["Open"]) if sgn > 0 else min(tg, x["Open"])
            why, exit_ts = "target", ts.to_pydatetime() + step; break
        if (x["High"] >= e + risk) if sgn > 0 else (x["Low"] <= e - risk):
            be = 2 * CFG["fee_per_order"] / q
            st = max(st, e + be) if sgn > 0 else min(st, e - be)
    if px is None:
        if not len(fut):
            return None
        px = float(fut["Close"].iloc[-1]) * (1 - sgn * CFG["slippage"])
    gross = to_eur(q * (px - e) * sgn, ccy)
    return dict(outcome=why, exit=round(px, 4), exit_ts=exit_ts.isoformat(timespec="seconds"), qty=q,
                gross=round(gross, 2), net_ante_tasse=round(gross - fees, 2))


def _stats(rows):
    v = [x["net_ante_tasse"] for x in rows if x.get("net_ante_tasse") is not None]
    if not v:
        return "0 segnali"
    tot = sum(v); win = sum(1 for x in v if x > 0)
    return f"{len(v)} segnali, netto ante tasse {tot:+.2f} € (medio {tot / len(v):+.2f} €), vincenti {win}/{len(v)}"


def _after_tax(tot):
    return tot - max(tot, 0) * TAX_RATE


def eod_lines(dry=False, bars_fn=None):
    d = today().isoformat()
    sigs = signals(d)
    if not sigs:
        return ["", "## Filtro dibattito LLM (prova shadow)", "", "Nessun segnale V0 / V0_LOOSE / NEWS_LLM oggi."]
    decs = {}
    for x in _lines(DEC):
        if x.get("day") == d:
            decs.setdefault(key(x), x)
    have = {key(x) for x in _lines(RESF) if x.get("day") == d}
    if bars_fn is None:
        from common import intraday_bars as bars_fn
    tick = sorted({r["ticker"] for r in sigs if key(r) not in have})[:20]
    bars = bars_fn(tick) if tick else {}
    new = []
    for r in sigs:
        if key(r) in have:
            continue
        dec = decs.get(key(r)) or {}
        b = bars.get(r["ticker"])
        sim = simulate(r, b) if b is not None and len(b) else None
        verdict = dec.get("verdict", "NON_DECISO")
        in_time = bool(sim and dec.get("ts_decision") and
                       datetime.fromisoformat(dec["ts_decision"]) < datetime.fromisoformat(sim["exit_ts"]))
        group = verdict if (verdict in ("ENTRA", "SCARTA") and in_time) else "NON_DECISO"
        row = dict(day=d, strategy=r["strategy"], ticker=r["ticker"], side=r.get("side", "long"), ts_signal=r["ts"], bar=r.get("bar"),
                   entry=r.get("entry"), stop=r.get("stop"), target=r.get("target"), verdict=verdict, group=group,
                   ts_decision=dec.get("ts_decision"), decided_in_time=in_time, model=dec.get("model"),
                   **(sim or dict(outcome="n/d", net_ante_tasse=None)))
        new.append(row)
        if not dry:
            append(RESF, row)
    rows = [x for x in _lines(RESF) if x.get("day") == d] + (new if dry else [])
    g = lambda rs, name: [x for x in rs if x.get("group") == name]

    def uniq(rs):   # V0 e V0_LOOSE sullo stesso setup (stessa barra, ingresso, stop) contano una volta sola nei totali
        seen, out = set(), []
        for x in rs:
            k = (x.get("day"), x.get("ticker"), x.get("bar"), x.get("side"), x.get("entry"), x.get("stop"))
            if k not in seen:
                seen.add(k); out.append(x)
        return out
    md = ["", "## Filtro dibattito LLM (prova shadow, NESSUN ordine)", "",
          f"Modello: {PROVIDER} ({', '.join(sorted({str(x.get('model')) for x in rows if x.get('model')})) or 'nessuna risposta'}). "
          "Esito con sizing diagnostico su 1.000 € (rischio 2%, nessun filtro minimo), stesse uscite della strategia, "
          "netto di 1 € + 1 €, prima delle tasse. Una decisione conta solo se registrata prima dell'uscita simulata.", ""]
    for x in sorted(rows, key=lambda y: y.get("ts_signal", "")):
        v = x.get("net_ante_tasse")
        md.append(f"- {x['ts_signal'][11:16]} {x['strategy']} {x['ticker']} {x['side']} -> {x['verdict']}"
                  f"{'' if x.get('decided_in_time') or x['verdict'] == 'NON_DECISO' else ' (deciso DOPO l esito: escluso)'}"
                  f", esito {x.get('outcome')}" + (f", netto ante tasse {v:+.2f} €" if v is not None else ""))
    u = uniq(rows)
    md += ["", "Totali per setup unico (V0 e V0_LOOSE identici contati una volta):",
           f"- Nessun filtro (tutti i segnali con esito): {_stats(u)}",
           f"- Approvati (ENTRA): {_stats(g(u, 'ENTRA'))}",
           f"- Scartati (SCARTA): {_stats(g(u, 'SCARTA'))}",
           f"- Non decisi / fuori tempo: {_stats(g(u, 'NON_DECISO'))}"]
    for s in STRATS:
        rs = [x for x in rows if x["strategy"] == s]
        if rs:
            md.append(f"  - {s}: tutti {_stats(rs)}; ENTRA {_stats(g(rs, 'ENTRA'))}; SCARTA {_stats(g(rs, 'SCARTA'))}")
    allr = uniq([x for x in _lines(RESF) if x.get("net_ante_tasse") is not None] +
                ([x for x in rows if x.get("net_ante_tasse") is not None] if dry else []))
    def cum(rs):
        t = sum(x["net_ante_tasse"] for x in rs)
        return f"{len(rs)} segnali, netto ante tasse {t:+.2f} €, dopo tassa 26% sul netto positivo {_after_tax(t):+.2f} €"
    md += ["", "Cumulativo dalla partenza della prova (tassa 26% solo se il totale del gruppo è positivo, zainetto non applicato):",
           f"- Nessun filtro: {cum(allr)}", f"- ENTRA: {cum(g(allr, 'ENTRA'))}", f"- SCARTA: {cum(g(allr, 'SCARTA'))}",
           "Regola pre-registrata: un giorno non basta per operare; se ENTRA è nettamente peggio di nessun filtro si scarta, "
           "se è meglio resta in prova shadow anche martedì."]
    return md


def main():
    dry = "--dry-run" in sys.argv
    if "--ping" in sys.argv:
        txt, model = chat([{"role": "user", "content": 'Rispondi solo con JSON {"verdetto":"ENTRA","motivo":"test"}'}], 200)
        print(model, parse_verdict(txt)); return
    if "--eod" in sys.argv:
        print("\n".join(eod_lines(dry))); return
    if "--worker" in sys.argv:
        print(f"decisioni scritte: {worker(dry)}")


if __name__ == "__main__":
    main()
