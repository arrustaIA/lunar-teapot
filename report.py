#!/usr/bin/env python3
"""Daily report in Italian (PAPER). Run after close (~21:55) or any time for a partial-day view.
Writes reports/report_YYYY-MM-DD.md and prints it. Idempotent (overwrites today's report)."""
import sys
from common import *
from stats import *
from news import macro_signal

def main():
    d = today().isoformat()
    with Lock():
        con = db()
        start_cash = float(con.execute("SELECT value FROM state WHERE key='start_cash'").fetchone()[0])
        dayrow = ensure_day(con)
        pos, prices = open_positions_view(con)
        eq = get_cash(con) + sum(p["value"] for p in pos)
        con.execute("UPDATE days SET end_equity=? WHERE day=?", (eq, d)); con.commit()
        rt = round_trips(con, d); rt_all = round_trips(con)
        tr = trades_df(con, d)
        credit = tax_credit_available(con)
        an = pd.read_sql_query("SELECT * FROM analyses WHERE day=?", con, params=(d,))
    day_pnl = eq - dayrow["start_equity"]; cum = eq - start_cash
    L = [f"# Report giornaliero paper trading – {today():%d/%m/%Y}",
         f"_Generato alle {now():%H:%M} ora di Roma. Soldi finti: nessun broker reale coinvolto._", "",
         "## Conto", f"- Equity: **{eur(eq)}** (inizio giornata {eur(dayrow['start_equity'])})",
         f"- P&L di oggi (netto commissioni e tasse realizzate): **{eur(day_pnl)} ({pct(day_pnl / dayrow['start_equity'])})**",
         f"- P&L cumulato dall'avvio ({eur(start_cash)}): **{eur(cum)} ({pct(cum / start_cash)})**"]
    if dayrow.get("halted"): L.append("- ⚠️ Limite di perdita giornaliera -3% raggiunto: trading sospeso per oggi.")
    g = rt["gross"].sum() if len(rt) else 0; f = tr["fee"].sum() if len(tr) else 0
    tx = rt["tax"].sum() if len(rt) else 0; n = rt["net"].sum() if len(rt) else 0
    L += ["", "## Risultato realizzato oggi", f"- P&L lordo: {eur(g)}", f"- Commissioni pagate: {eur(f)} ({len(tr)} ordini × 1 €)",
          f"- Imposta 26% trattenuta: {eur(tx)}", f"- P&L netto dopo tasse: **{eur(g - f - tx)}**",
          f"- Zainetto fiscale (minusvalenze compensabili, scadenza 4 anni): {eur(credit)}"]
    if len(rt):
        wins = (rt.net > 0).sum()
        L.append(f"- Operazioni chiuse: {len(rt)}, vincenti {wins} → win rate {wins / len(rt):.0%}")
    if len(rt_all):
        L.append(f"- Win rate storico: {(rt_all.net > 0).mean():.0%} su {len(rt_all)} operazioni")
    L += ["", "## Operazioni di oggi"]
    if len(tr):
        L.append("| Ora | Titolo | Lato | Qtà | Prezzo | Valore | Comm. | Netto | Motivo |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for _, r in tr.iterrows():
            net = eur(r.net_pnl_eur) if r.side == "SELL" and r.net_pnl_eur == r.net_pnl_eur else ""
            L.append(f"| {r.ts[11:16]} | {r['name']} ({r.ticker}) | {'ACQUISTO' if r.side == 'BUY' else 'VENDITA'} | {r.qty:.4f} | "
                     f"{r.price_local:.3f} {r.currency} | {eur(r.value_eur)} | {eur(r.fee)} | {net} | {r.reason[:90]} |")
    else:
        L.append("Nessuna operazione oggi: nessun segnale ha superato tutti i filtri (regole, analisi grafica, notizie, rischio).")
    if pos:
        L += ["", "## Posizioni aperte"]
        for p in pos:
            L.append(f"- {p['name']} ({p['ticker']}): {p['qty']:.4f} @ {p['entry_local']:.3f} → {p['last']:.3f} {p['currency']}, "
                     f"valore {eur(p['value'])}, non realizzato {eur(p['unreal'])} (incl. commissioni), stop {p['stop_local']:.3f}")
    b = benchmark_day()
    L += ["", "## Confronto con benchmark"]
    if b:
        port_ret = day_pnl / dayrow["start_equity"]
        bench_net = (dayrow["start_equity"] * b["ret"] - 2) / dayrow["start_equity"]
        L.append(f"- {b['ticker']} (ETF DAX) dall'apertura: {pct(b['ret'])} (netto 2 € di commissioni su {eur(dayrow['start_equity'])}: {pct(bench_net)})")
        L.append(f"- Team: {pct(port_ret)} → {'meglio' if port_ret > bench_net else 'peggio'} del semplice acquisto del benchmark di {pct(port_ret - bench_net)}")
    else:
        L.append("- Dati benchmark non disponibili oggi (festivo?).")
    L += ["", "## Cosa ha funzionato / cosa no"]
    if len(rt):
        best, worst = rt.loc[rt.net.idxmax()], rt.loc[rt.net.idxmin()]
        L.append(f"- Migliore: {best['name']} {eur(best.net)} ({exit_kind(best.exit_reason)}); peggiore: {worst['name']} {eur(worst.net)} ({exit_kind(worst.exit_reason)})")
        kinds = rt.exit_reason.map(exit_kind).value_counts()
        L.append("- Uscite: " + ", ".join(f"{k} {v}" for k, v in kinds.items()))
        if f > 0 and abs(g) > 0: L.append(f"- Peso delle commissioni: {f / abs(g):.0%} del P&L lordo")
    if len(an):
        buys = an[an.side == "buy"]
        L.append(f"- Analista grafico: {len(buys)} segnali valutati, {int((buys.verdict == 'APPROVE').sum())} approvati, {int((buys.verdict == 'REJECT').sum())} rifiutati")
    reasons = log_reasons(d)
    if reasons:
        L.append("- Motivi principali per cui non si è entrati: " + "; ".join(f"{k} ({v})" for k, v in list(reasons.items())[:5]))
    m = macro_signal()
    L.append(f"- Clima notizie macro (12h): {m['score']:+.2f} su {m['count']} titoli")
    charts = [c for c in list(tr.chart.dropna()) if c] if len(tr) else []
    if charts:
        L += ["", "## Grafici delle operazioni"] + [f"![{os.path.basename(c)}]({os.path.join('..', c)})" for c in charts]
    txt = "\n".join(L) + "\n"
    path = os.path.join(REPORTS, f"report_{d}.md")
    with open(path, "w") as fh: fh.write(txt)
    print(txt); log(f"report scritto: {path}", "report")

if __name__ == "__main__":
    main()
