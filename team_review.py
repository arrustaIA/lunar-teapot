#!/usr/bin/env python3
"""'HR' team review (PAPER), run DAILY after close (~22:15 Rome). Analyses performance by setup,
time of day, ticker, region, exit type, chart score and news, plus fee/tax drag, and writes
recommendations for new specialised roles or rule changes. It ONLY recommends: it never edits
code, config or the ledger. Output: reports/team_review_YYYY-MM-DD.md"""
from common import *
from stats import *

def table(df, by, label):
    if not len(df): return []
    g = df.groupby(by).agg(n=("net", "size"), net=("net", "sum"), win=("net", lambda s: (s > 0).mean()),
                           fees=("fees", "sum"), tax=("tax", "sum")).sort_values("net", ascending=False)
    L = [f"### Per {label}", "| | N | Netto | Win rate | Commissioni | Tasse |", "|---|---|---|---|---|---|"]
    for k, r in g.iterrows():
        L.append(f"| {k} | {int(r.n)} | {eur(r.net)} | {r.win:.0%} | {eur(r.fees)} | {eur(r.tax)} |")
    return L + [""]

def main():
    d = today().isoformat()
    con = db()
    rt = round_trips(con)
    an = pd.read_sql_query("SELECT * FROM analyses", con)
    days = pd.read_sql_query("SELECT * FROM days ORDER BY day", con)
    start_cash = float(con.execute("SELECT value FROM state WHERE key='start_cash'").fetchone()[0])
    eq = equity(con)[0]
    reasons_today, reasons_all = log_reasons(d), log_reasons()
    L = [f"# Revisione del team (HR) – {today():%d/%m/%Y}", "_Solo raccomandazioni: nessuna regola viene cambiata automaticamente._", "",
         "## Quadro generale", f"- Giorni di trading registrati: {len(days)}; equity {eur(eq)} ({pct(eq / start_cash - 1)} dall'avvio)",
         f"- Operazioni chiuse totali: {len(rt)}" + (f", oggi {int((rt.day == d).sum())}" if len(rt) else "")]
    rec = []
    if len(rt):
        g, f, t, n = rt.gross.sum(), rt.fees.sum(), rt.tax.sum(), rt.net.sum()
        L += [f"- Lordo {eur(g)}, commissioni {eur(f)}, tasse {eur(t)}, netto {eur(n)}",
              f"- Win rate {(rt.net > 0).mean():.0%}; media vincita {eur(rt[rt.net > 0].net.mean() if (rt.net > 0).any() else 0)}, "
              f"media perdita {eur(rt[rt.net <= 0].net.mean() if (rt.net <= 0).any() else 0)}; durata media {rt.hold_min.mean():.0f} min",
              f"- Peso costi (commissioni+tasse) sul lordo positivo: {((f + t) / g):.0%}" if g > 0 else "- Lordo non positivo: i costi peggiorano solo il risultato", ""]
        rt = rt.assign(fascia=rt.entry_hour.map(lambda h: f"{h:02d}:00-{h:02d}:59"), uscita=rt.exit_reason.map(exit_kind))
        for by, lab in (("setup", "setup"), ("fascia", "orario di ingresso"), ("region", "mercato"), ("ticker", "titolo"), ("uscita", "tipo di uscita")):
            L += table(rt, by, lab)
        if g > 0 and (f + t) / g > 0.5:
            rec.append("Costi > 50% del lordo: alzare la dimensione minima per operazione o selezionare meno trade con target più ampi (regola, non ruolo).")
        if (rt.uscita == "stop loss").mean() > 0.6 and len(rt) >= 5:
            rec.append("Oltre il 60% delle uscite è su stop: far rivedere al Risk manager la distanza dello stop (ATR x1.5) o filtrare i breakout falsi.")
        eu, us = rt[rt.region == "EU"].net.sum(), rt[rt.region == "US"].net.sum()
        if (rt.region == "US").sum() >= 3 and us < eu:
            rec.append("La sessione USA rende meno di quella europea: valutare uno **specialista sessione USA** (apertura 15:30, premarket, dati macro USA alle 14:30).")
    if len(rt) < 20:
        rec.insert(0, f"Campione ancora piccolo ({len(rt)} operazioni): servono almeno 20-30 trade prima di cambiare regole; continuare a raccogliere dati.")
    if reasons_today:
        L += ["## Perché non si è entrati (oggi)"] + [f"- {k}: {v}" for k, v in list(reasons_today.items())[:8]] + [""]
    ext = sum(v for k, v in reasons_all.items() if k.startswith("troppo esteso"))
    nobr = sum(v for k, v in reasons_all.items() if k.startswith("nessun breakout"))
    if ext >= 5:
        rec.append(f"Molti breakout scartati perché già 'troppo estesi' ({ext}): valutare un setup **pullback su VWAP** gestito da un analista dedicato, per entrare dopo il ritracciamento invece di inseguire.")
    if nobr >= 10 and len(rt) == 0:
        rec.append("Nessun breakout nella maggior parte dei controlli: aggiungere un secondo setup (es. mean-reversion su VWAP nei giorni laterali) o un **quant/backtester** che testi le regole sui dati storici prima di usarle.")
    if len(an):
        b = an[an.side == "buy"]
        if len(b):
            L += [f"## Analista grafico", f"- Segnali valutati {len(b)}: approvati {int((b.verdict == 'APPROVE').sum())}, rifiutati {int((b.verdict == 'REJECT').sum())}, punteggio medio {b.score.mean():.0f}", ""]
            if len(b) >= 10 and (b.verdict == "REJECT").mean() > 0.8:
                rec.append("L'analista grafico rifiuta oltre l'80% dei segnali: verificare con un backtest se la soglia 25 è troppo severa.")
    blocked = sum(v for k, v in reasons_all.items() if "notizie" in k or "macro" in k)
    L.append(f"- Ingressi bloccati da notizie/clima macro finora: {blocked}")
    rec += ["Ruoli da valutare (in ordine di priorità suggerita):",
            "  1. **Analista calendario/eventi**: trimestrali, dividendi e dati macro (BCE, Fed, CPI, payroll) per evitare ingressi a ridosso di eventi binari.",
            "  2. **Monitor qualità delle quotazioni**: i dati gratuiti hanno ~15 min di ritardo sui titoli europei; misurare lo scarto con i prezzi LS Exchange prima di passare a soldi veri.",
            "  3. **Specialista sessione USA**: regole proprie per 15:30-21:50 (apertura volatile, premarket).",
            "  4. **Quant/backtester**: validare ogni nuova regola su mesi di dati storici a 5 minuti prima di adottarla.",
            "  5. **Analista notizie con modello linguistico**: l'attuale sentiment è basato su parole chiave; un modello migliore ridurrebbe i falsi segnali."]
    L += ["", "## Raccomandazioni"] + [f"- {r}" if not r.startswith("  ") else r for r in rec]
    txt = "\n".join(L) + "\n"
    path = os.path.join(REPORTS, f"team_review_{d}.md")
    with open(path, "w") as fh: fh.write(txt)
    print(txt); log(f"team review scritta: {path}", "team_review")

if __name__ == "__main__":
    main()
