# Revisione del team (HR) – 17/11/2026
_Solo raccomandazioni: nessuna regola viene cambiata automaticamente._

## Quadro generale
- Giorni di trading registrati: 4; equity 984,23 € (-1,58% dall'avvio)
- Operazioni chiuse totali: 4, oggi 4
- Lordo -7,77 €, commissioni 8,00 €, tasse 0,00 €, netto -15,77 €
- Win rate 0%; media vincita 0,00 €, media perdita -3,94 €; durata media 71 min
- Lordo non positivo: i costi peggiorano solo il risultato

### Per setup
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| ORB+VWAP | 4 | -15,77 € | 0% | 8,00 € | 0,00 € |

### Per orario di ingresso
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| 20:00-20:59 | 1 | -0,12 € | 0% | 2,00 € | 0,00 € |
| 16:00-16:59 | 3 | -15,66 € | 0% | 6,00 € | 0,00 € |

### Per mercato
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| US | 4 | -15,77 € | 0% | 8,00 € | 0,00 € |

### Per titolo
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| LCID | 1 | -0,12 € | 0% | 2,00 € | 0,00 € |
| TSN | 1 | -0,48 € | 0% | 2,00 € | 0,00 € |
| BRKR | 1 | -6,98 € | 0% | 2,00 € | 0,00 € |
| MOH | 1 | -8,20 € | 0% | 2,00 € | 0,00 € |

### Per tipo di uscita
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| stop loss | 4 | -15,77 € | 0% | 8,00 € | 0,00 € |

## Perché non si è entrati (oggi)
- nessun breakout: 1323
- momentum Nm negativo: 1179
- troppo esteso, non inseguo: 880
- filtro commissioni (guadagno atteso sotto 6 €): 669
- quotazione vecchia: 595
- fuori finestra ingressi: 373
- sotto VWAP: 318
- ema_misaligned: 172

## Analista grafico
- Segnali valutati 19: approvati 4, rifiutati 15, punteggio medio 7

- Ingressi bloccati da notizie/clima macro finora: 0

## Raccomandazioni
- Campione ancora piccolo (4 operazioni): servono almeno 20-30 trade prima di cambiare regole; continuare a raccogliere dati.
- La sessione USA rende meno di quella europea: valutare uno **specialista sessione USA** (apertura 15:30, premarket, dati macro USA alle 14:30).
- Molti breakout scartati perché già 'troppo estesi' (2001): valutare un setup **pullback su VWAP** gestito da un analista dedicato, per entrare dopo il ritracciamento invece di inseguire.
- Ruoli da valutare (in ordine di priorità suggerita):
  1. **Analista calendario/eventi**: trimestrali, dividendi e dati macro (BCE, Fed, CPI, payroll) per evitare ingressi a ridosso di eventi binari.
  2. **Monitor qualità delle quotazioni**: i dati gratuiti hanno ~15 min di ritardo sui titoli europei; misurare lo scarto con i prezzi LS Exchange prima di passare a soldi veri.
  3. **Specialista sessione USA**: regole proprie per 15:30-21:50 (apertura volatile, premarket).
  4. **Quant/backtester**: validare ogni nuova regola su mesi di dati storici a 5 minuti prima di adottarla.
  5. **Analista notizie con modello linguistico**: l'attuale sentiment è basato su parole chiave; un modello migliore ridurrebbe i falsi segnali.
