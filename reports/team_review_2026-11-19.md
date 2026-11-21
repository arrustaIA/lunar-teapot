# Revisione del team (HR) – 19/11/2026
_Solo raccomandazioni: nessuna regola viene cambiata automaticamente._

## Quadro generale
- Giorni di trading registrati: 6; equity 943,56 € (-5,64% dall'avvio)
- Operazioni chiuse totali: 16, oggi 6
- Lordo -24,44 €, commissioni 32,00 €, tasse 0,00 €, netto -56,44 €
- Win rate 6%; media vincita 0,14 €, media perdita -3,77 €; durata media 111 min
- Lordo non positivo: i costi peggiorano solo il risultato

### Per setup
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| ORB+VWAP | 16 | -56,44 € | 6% | 32,00 € | 0,00 € |

### Per orario di ingresso
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| 20:00-20:59 | 2 | -1,19 € | 0% | 4,00 € | 0,00 € |
| 17:00-17:59 | 2 | -6,05 € | 0% | 4,00 € | 0,00 € |
| 14:00-14:59 | 3 | -12,20 € | 0% | 6,00 € | 0,00 € |
| 16:00-16:59 | 9 | -37,01 € | 11% | 18,00 € | 0,00 € |

### Per mercato
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| EU | 4 | -14,28 € | 0% | 8,00 € | 0,00 € |
| US | 12 | -42,16 € | 8% | 24,00 € | 0,00 € |

### Per titolo
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| CVLT | 1 | 0,14 € | 100% | 2,00 € | 0,00 € |
| LCID | 1 | -0,12 € | 0% | 2,00 € | 0,00 € |
| VVV | 1 | -0,14 € | 0% | 2,00 € | 0,00 € |
| OLLI | 1 | -0,41 € | 0% | 2,00 € | 0,00 € |
| TSN | 1 | -0,48 € | 0% | 2,00 € | 0,00 € |
| WING | 1 | -1,07 € | 0% | 2,00 € | 0,00 € |
| MONC.MI | 1 | -1,66 € | 0% | 2,00 € | 0,00 € |
| ERF.PA | 1 | -2,09 € | 0% | 2,00 € | 0,00 € |
| 8TRA.DE | 1 | -4,85 € | 0% | 2,00 € | 0,00 € |
| PLNT | 1 | -5,19 € | 0% | 2,00 € | 0,00 € |
| APAM.AS | 1 | -5,69 € | 0% | 2,00 € | 0,00 € |
| GME | 1 | -5,90 € | 0% | 2,00 € | 0,00 € |
| EAT | 1 | -6,59 € | 0% | 2,00 € | 0,00 € |
| BRKR | 1 | -6,98 € | 0% | 2,00 € | 0,00 € |
| CELH | 1 | -7,22 € | 0% | 2,00 € | 0,00 € |
| MOH | 1 | -8,20 € | 0% | 2,00 € | 0,00 € |

### Per tipo di uscita
| | N | Netto | Win rate | Commissioni | Tasse |
|---|---|---|---|---|---|
| chiusura fine giornata | 3 | -8,01 € | 0% | 6,00 € | 0,00 € |
| stop loss | 13 | -48,43 € | 8% | 26,00 € | 0,00 € |

## Perché non si è entrati (oggi)
- max N posizioni aperte: 1109
- nessun breakout: 679
- momentum Nm negativo: 564
- troppo esteso, non inseguo: 426
- filtro commissioni (guadagno atteso sotto 6 €): 391
- fuori finestra ingressi: 359
- quotazione vecchia: 277
- dati di oggi insufficienti: 47

## Analista grafico
- Segnali valutati 65: approvati 13, rifiutati 52, punteggio medio 8

- Ingressi bloccati da notizie/clima macro finora: 0

## Raccomandazioni
- Campione ancora piccolo (16 operazioni): servono almeno 20-30 trade prima di cambiare regole; continuare a raccogliere dati.
- Oltre il 60% delle uscite è su stop: far rivedere al Risk manager la distanza dello stop (ATR x1.5) o filtrare i breakout falsi.
- La sessione USA rende meno di quella europea: valutare uno **specialista sessione USA** (apertura 15:30, premarket, dati macro USA alle 14:30).
- Molti breakout scartati perché già 'troppo estesi' (9691): valutare un setup **pullback su VWAP** gestito da un analista dedicato, per entrare dopo il ritracciamento invece di inseguire.
- Ruoli da valutare (in ordine di priorità suggerita):
  1. **Analista calendario/eventi**: trimestrali, dividendi e dati macro (BCE, Fed, CPI, payroll) per evitare ingressi a ridosso di eventi binari.
  2. **Monitor qualità delle quotazioni**: i dati gratuiti hanno ~15 min di ritardo sui titoli europei; misurare lo scarto con i prezzi LS Exchange prima di passare a soldi veri.
  3. **Specialista sessione USA**: regole proprie per 15:30-21:50 (apertura volatile, premarket).
  4. **Quant/backtester**: validare ogni nuova regola su mesi di dati storici a 5 minuti prima di adottarla.
  5. **Analista notizie con modello linguistico**: l'attuale sentiment è basato su parole chiave; un modello migliore ridurrebbe i falsi segnali.
