# Revisione del team (HR) – 12/11/2026
_Solo raccomandazioni: nessuna regola viene cambiata automaticamente._

## Quadro generale
- Giorni di trading registrati: 1; equity 1.000,00 € (+0,00% dall'avvio)
- Operazioni chiuse totali: 0
## Perché non si è entrati (oggi)
- nessun breakout: 135
- fuori finestra ingressi: 60
- momentum 15m negativo: 50
- troppo esteso, non inseguo: 31
- sotto VWAP: 14
- guadagno atteso 2.40 EUR < 3x commissioni: 4
- guadagno atteso 4.16 EUR < 3x commissioni: 1
- guadagno atteso 2.93 EUR < 3x commissioni: 1

- Ingressi bloccati da notizie/clima macro finora: 0

## Raccomandazioni
- Campione ancora piccolo (0 operazioni): servono almeno 20-30 trade prima di cambiare regole; continuare a raccogliere dati.
- Molti breakout scartati perché già 'troppo estesi' (59): valutare un setup **pullback su VWAP** gestito da un analista dedicato, per entrare dopo il ritracciamento invece di inseguire.
- Nessun breakout nella maggior parte dei controlli: aggiungere un secondo setup (es. mean-reversion su VWAP nei giorni laterali) o un **quant/backtester** che testi le regole sui dati storici prima di usarle.
- Ruoli da valutare (in ordine di priorità suggerita):
  1. **Analista calendario/eventi**: trimestrali, dividendi e dati macro (BCE, Fed, CPI, payroll) per evitare ingressi a ridosso di eventi binari.
  2. **Monitor qualità delle quotazioni**: i dati gratuiti hanno ~15 min di ritardo sui titoli europei; misurare lo scarto con i prezzi LS Exchange prima di passare a soldi veri.
  3. **Specialista sessione USA**: regole proprie per 15:30-21:50 (apertura volatile, premarket).
  4. **Quant/backtester**: validare ogni nuova regola su mesi di dati storici a 5 minuti prima di adottarla.
  5. **Analista notizie con modello linguistico**: l'attuale sentiment è basato su parole chiave; un modello migliore ridurrebbe i falsi segnali.
