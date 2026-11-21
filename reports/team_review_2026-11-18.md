# Revisione del team (HR) – 18/11/2026
_Solo raccomandazioni: nessuna regola viene cambiata automaticamente._

## Quadro generale
- Giorni di trading registrati: 5; equity 963,89 € (-3,61% dall'avvio)
- Operazioni chiuse totali: 10, oggi 6
- Lordo -16,11 €, commissioni 20,00 €, tasse 0,00 €, netto -36,11 €
- Win rate 10%; media vincita 0,14 €, media perdita -4,03 €; durata media 61 min
- Lordo non positivo: i costi peggiorano solo il risultato

### Per setup
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| ORB+VWAP | 10 | -36,11 € | 10% | 20,00 € | 0,00 € |

### Per orario di ingresso
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| 20:00-20:59 | 2 | -1,19 € | 0% | 4,00 € | 0,00 € |
| 16:00-16:59 | 8 | -34,92 € | 12% | 16,00 € | 0,00 € |

### Per mercato
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| US | 10 | -36,11 € | 10% | 20,00 € | 0,00 € |

### Per titolo
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| CVLT | 1 | 0,14 € | 100% | 2,00 € | 0,00 € |
| LCID | 1 | -0,12 € | 0% | 2,00 € | 0,00 € |
| OLLI | 1 | -0,41 € | 0% | 2,00 € | 0,00 € |
| TSN | 1 | -0,48 € | 0% | 2,00 € | 0,00 € |
| WING | 1 | -1,07 € | 0% | 2,00 € | 0,00 € |
| PLNT | 1 | -5,19 € | 0% | 2,00 € | 0,00 € |
| EAT | 1 | -6,59 € | 0% | 2,00 € | 0,00 € |
| BRKR | 1 | -6,98 € | 0% | 2,00 € | 0,00 € |
| CELH | 1 | -7,22 € | 0% | 2,00 € | 0,00 € |
| MOH | 1 | -8,20 € | 0% | 2,00 € | 0,00 € |

### Per tipo di uscita
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| chiusura fine giornata | 1 | -1,07 € | 0% | 2,00 € | 0,00 € |
| stop loss | 9 | -35,04 € | 11% | 18,00 € | 0,00 € |

## Perché non si è entrati (oggi)
- momentum Nm negativo: 3555
- troppo esteso, non inseguo: 3419
- max N posizioni aperte: 1856
- nessun breakout: 1472
- fuori finestra ingressi: 1294
- filtro commissioni (guadagno atteso sotto 6 €): 1255
- quotazione vecchia: 1119
- sotto VWAP: 434

## Analista grafico
- Segnali valutati 52: approvati 10, rifiutati 42, punteggio medio 8

- Ingressi bloccati da notizie/clima macro finora: 0

## Raccomandazioni
- Campione ancora piccolo (10 operazioni): servono almeno 20-30 trade prima di cambiare regole; continuare a raccogliere dati.
- Oltre il 60% delle uscite è su stop: far rivedere al Risk manager la distanza dello stop (ATR x1.5) o filtrare i breakout falsi.
- La sessione USA rende meno di quella europea: valutare uno **specialista sessione USA** (apertura 15:30, premarket, dati macro USA alle 14:30).
- Molti breakout scartati perché già 'troppo estesi' (8839): valutare un setup **pullback su VWAP** gestito da un analista dedicato, per entrare dopo il ritracciamento invece di inseguire.
- L'analista grafico rifiuta oltre l'80% dei segnali: verificare con un backtest se la soglia 25 è troppo severa.
- Ruoli da valutare (in ordine di priorità suggerita):
  1. **Analista calendario/eventi**: trimestrali, dividendi e dati macro (BCE, Fed, CPI, payroll) per evitare ingressi a ridosso di eventi binari.
  2. **Monitor qualità delle quotazioni**: i dati gratuiti hanno ~15 min di ritardo sui titoli europei; misurare lo scarto con i prezzi LS Exchange prima di passare a soldi veri.
  3. **Specialista sessione USA**: regole proprie per 15:30-21:50 (apertura volatile, premarket).
  4. **Quant/backtester**: validare ogni nuova regola su mesi di dati storici a 5 minuti prima di adottarla.
  5. **Analista notizie con modello linguistico**: l'attuale sentiment è basato su parole chiave; un modello migliore ridurrebbe i falsi segnali.
