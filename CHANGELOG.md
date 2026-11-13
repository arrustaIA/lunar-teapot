# Changelog

## 2026-11-13 (~23:10 ora di Roma) – R&D serale: nessun deploy; misure in ombra aggiornate

- **Stato**: run GitHub di oggi tutte riuscite, heartbeat 22:25. Oggi 0 operazioni, equity 1.000,00 €, ledger invariato.
- **Backtest serale** (21/08–13/11, 61 sedute, dati aggiornati): baseline v0 20 trade, netto −18,82 € (OOS 17 trade −19,79 €); no_chart −68,30 €;
  delay15 −13,82 € (OOS 14 trade, non validato: netto negativo); pullback identico alla baseline; us_rescan −57,93 €. Leva: tutte le varianti
  da −283 € (factor x2) a −740 € (KO x5 stretto), nessuna validata. Nessun segnale con vantaggio lordo che giustifichi short o leva.
- **Reale vs backtest**: il backtest sul 12/11 apre AMD (netto +0,01 €) e AVGO (−5,38 €), la produzione no. AMD era bloccato dal filtro commissioni
  (target 4,16 € < 6 €), AVGO è finito nello shadow diagnostico (−3,90 €). La differenza è la larghezza dello stop (barre yfinance 5 min nel
  backtest, L&S a 1 min in produzione): il backtest sovrastima un po' il numero di trade; effetto netto sui due giorni +5,37 € a favore della produzione.
- **Shadow cumulativo (12–13/11)**: 0 segnali operativi; 5 segnali ORB_DYN diagnostici (bloccati solo dal filtro commissioni) per −10,31 € ante tasse;
  REBOUND 3 segnali, tutti respinti dall'analista grafico. Nessuna promozione (campione troppo piccolo e negativo).
- **Notizie (Natasia)**: `rd-paper-trading/news_eval.py` (corretto: Spearman calcolato senza scipy) su 163 giudizi → 51 coppie (titolo, seduta
  successiva) valutabili, quasi tutte su una sola seduta: LLM hit rate 60,8%, Spearman +0,14; parole chiave 57,4%, Spearman +0,21; giudizi forti
  (|impatto×confidenza| ≥ 0,2) n=3, rendimento medio nel verso del giudizio −0,42%. Nessun vantaggio dimostrato, nessuna integrazione (soglia ≥ 100 coppie su più sedute).
- **strict_fees_cap50**: ritest pre-registrato rinviato, servono ≥ 20 trade OOS e il campione 5 min disponibile ne dà ~10.
- **Raccomandazioni HR del 13/11, valutate**: identiche a quelle del 12/11. "Servono 20-30 trade": accolta. Pullback VWAP: scartata (0 trade in più
  rispetto alla v0). Mean-reversion VWAP: già testata (REBOUND, negativa) → resta in shadow. Quant/backtester, monitor quotazioni (feed L&S) e
  analista notizie LLM (Natasia): già attivi. Specialista USA: ORB USA scartato più volte (−57,93 € stasera). Analista calendario/eventi: rinviato,
  con 20 trade in backtest il filtro sarebbe inverificabile.
- Codice di produzione, scheduler, workflow e ledger non toccati.

## 2026-11-13 (21:25 ora di Roma) – Diagnosi zero trade: nessun guasto sul percorso ordini; fix scan 09:35

- **Richiesta** (Andrea: «Qualcosa non va se ancora nessun trade»): capire perché il bot paper non ha eseguito alcun ordine dal lancio (12-13/11).
- **Diagnosi del percorso ordini (filtri, non un bug di esecuzione)**: sessione GitHub in corso dalle 18:32, heartbeat 21:18, 83 passaggi `trade.py` oggi (07:30-21:10 ogni 10 min) senza eccezioni, senza quotazioni stantie e senza dati mancanti. Ledger invariato: 1.000,00 €, 0 posizioni, 0 trade. L'analista grafico (soglia 25) **non è mai stato chiamato** in produzione: i setup si fermano prima, al filtro commissioni.
- **Valutazioni del 13/11** (664, 8 titoli della watchlist): fuori finestra ingressi 213, nessun breakout 365, troppo esteso 35, momentum 15m negativo 32, guadagno atteso < 3× commissioni 15, sotto VWAP 4. Stesso schema il 12/11 (296 valutazioni: nessun breakout 135, fuori finestra 60, momentum 50, troppo esteso 31, sotto VWAP 14, commissioni 6).
- **Quanto è andata vicina la v0**: il filtro chiede un target 2R ≥ 6 € (3× le 2 € di andata e ritorno) su un tetto posizione di 300 €, quindi serve uno stop ≥ 1%. Con lo stop minimo dello 0,4% il target vale esattamente 2,40 € (11 dei 15 rifiuti di oggi). Il più vicino oggi è **ENR.DE alle 09:30: 3,40 €** (stop ~0,57%); ieri il massimo è stato AMD 4,16 €. Lo shadow ha visto 4 segnali ORB_DYN con score grafico 25-40 (TTE.PA, SAP.DE, MSFT, META) altrettanto bloccati dalle commissioni (qty 0); esito diagnostico già noto −6,41 €, quindi il filtro oggi ha evitato perdite. Nessuna soglia di strategia è stata allentata.
- **Bug reale (non un filtro)**: alle 07:30, senza watchlist, `trade.py` lancia `scan.py` e congela la lista di prima dell'apertura (oggi tutti i gap EU a +0,00%). Alle 09:35 lo scan ufficiale ha trovato il file e si è fermato (`watchlist already exists`). Lo scan delle 09:35 adesso rifà una lista scritta prima delle 09:35, così gap e volume relativo sono quelli della seduta. Test: `python3 test_scan_watchlist.py`. Nessun impatto sugli ordini di oggi (le 09:35 sono già passate); vale da lunedì.
- **Cosa non è un bug**: orari (EU 09:30-21:15, USA 16:00-21:15 in novembre), feed L&S, persistenza dello stato, size arrotondata a 0 (le size al tetto 300 € passavano il nozionale minimo da 200 €). Il tetto 30% × filtro 3× commissioni è un filtro deliberato; R&D ha già scartato tetto 100% e leva.


## 2026-11-13 (21:20 ora di Roma) – Zero operazioni: diagnosi, 6 rimedi testati OOS → nessun deploy di ordini; shadow esteso a V0_LOOSE

- **Richiesta** (Sguattera): zero operazioni il 12 e il 13/11. Testare rimedi concreti out-of-sample al netto di tutto e fare il deploy di
  qualunque configurazione batta la v0; se nulla è positivo, stimare quanto costerebbe una variante che opera davvero a size piccola.
- **Diagnosi produzione (nessun bug trovato)**: run GitHub di oggi tutti ok, heartbeat regolare, `trade.py` ha fatto 82 passaggi
  (07:30-21:00 ogni 10 min) senza errori. Su 656 valutazioni (8 titoli): fuori finestra 213, nessun breakout 359 (NVDA, MU e AVGO sempre
  sotto il massimo dell'opening range in una giornata in calo), e dopo un breakout UE: troppo esteso 33, momentum 15m negativo 32,
  guadagno atteso < 3× commissioni 15 (stop minimo 0,4% × tetto 30% = 2,40 € al target), sotto VWAP 4. L'analista grafico non è mai
  stato raggiunto; il 12/11 stesso schema. Lo shadow ha visto 4 segnali APPROVE bloccati solo dal filtro commissioni (TTE.PA, SAP.DE,
  MSFT, META): esito diagnostico **−6,41 €** ante tasse, quindi il filtro oggi ha evitato perdite. Il backtest della v0 prevede 19 trade in
  61 sedute (75% delle sedute senza trade): due giorni a zero sono il comportamento atteso (probabilità ≈ 57%), non un guasto.
- **Metodo**: regole pre-registrate alle 21:06 prima dei risultati (`rd-paper-trading/reports/preregistration_2026-11-13_zerotrade.md`),
  6 varianti senza griglie. yfinance 5 minuti (v0 e V1/V1b sullo stesso motore e dati della baseline, 19/08-11/11; le altre 21/08-13/11),
  CON.DE escluso, OOS dopo 20 sedute, holdout ultimo 1/3. Commissioni 1+1 €, slippage 0,05%, spread (KO x5: 0,50% del certificato),
  knock-out per barra, tassa 26% dopo commissioni con zainetto in ordine di chiusura. Soglia: ≥ 30 trade OOS, netto OOS > 0, PF > 1,1,
  senza il migliore ≥ 0, DD ≤ 15%, holdout > 0, meglio della v0.
- **Risultati OOS**:

  | Variante | Trade tot/OOS | Lordo OOS | Netto OOS | PF | Holdout | Max DD | Esito |
  |---|---|---|---|---|---|---|---|
  | v0 attuale (riferimento) | 19/16 | +17,23 € | −15,35 € | 0,59 | −7,64 € | −3,1% | – |
  | V1 v0 con estensione 3 ATR e filtro commissioni 1,5× | 89/66 | −19,53 € | **−151,53 €** | 0,05 | −79,51 € | −20,3% | respinta |
  | V1b v0 con watchlist 10 UE + 6 USA | 30/24 | −1,19 € | −49,19 € | 0,33 | −26,65 € | −7,6% | respinta |
  | V2 giudizi di Natasia (KO x5) | 2/2 | +23,60 € | +12,19 € | 2,37 | – | −0,9% | non valutabile: storico dal 12/11, 4 giudizi forti |
  | V3 segnale parole chiave news.py (KO x5) | 8/8 | −33,00 € | −49,00 € | 0,12 | – | −5,6% | non valutabile, negativa |
  | V4 fade del falso breakout dopo l'OR, 09:30-11:00 UE / 16:00-17:30 USA, 70 titoli (KO x5) | 252/78 | −45,11 € | −201,11 € | 0,01 | capitale esaurito | −89,9% | respinta |
  | V5 momentum ultima ora USA, 21:00-21:45 (KO x5) | 164/107 | −133,22 € | −347,22 € | 0,12 | −139,33 € | −66,2% | respinta |

  La v0 è l'unica con lordo positivo (+36 bp a trade); allentare i filtri aggiunge trade a lordo negativo (V1 −10 bp a trade).
- **Dati live L&S dal 12/11 (troppo pochi per validare, usati solo come controllo dei costi)**: 3.554 esecuzioni su 18 titoli contro il mid
  a 1 minuto, mezzo spread effettivo mediano 7,1 bp (p90 30 bp), quindi il backtest con 5 bp è un po' ottimista. Bid/ask alle 21:05 su 72
  titoli: spread mediano 27 bp (USA 8, UE 37, P911.DE 176): la sera i titoli UE costano molto di più.
- **Decisione**: nessuna variante supera i criteri → **nessun deploy di ordini**, la v0 resta invariata. La variante meno negativa che opera
  davvero (≥ 30 trade OOS) è V1: circa 34 trade/mese, costo atteso **≈ −78 €/mese** a size di produzione (DD −20%) e **≈ −71 €/mese** anche a
  100 € di nozionale, perché le commissioni fisse dominano. La v0 costa ≈ −8 €/mese con ≈ 8 trade/mese. Gli stessi dati si raccolgono a
  costo zero: **`shadow.py` registra da lunedì 16/11 anche `V0_LOOSE`** (= V1, sulla watchlist statica, analista grafico come la v0), mai ordini.
- **Test del deploy**: copia isolata (`PT_SHADOW_DIR`, `PT_REPORTS`, `PT_LOGS`, `PT_BARS`, `PT_LOCK`, `PT_DB` temporanei) con orologio finto:
  alle 11:35 V0_LOOSE scatta su IFX.DE dove la v0 dice "troppo esteso" e coincide con la v0 su MB.MI; alle 21:10 27 valutazioni e 1 segnale.
  In produzione `shadow.py --dry-run` e `--eod --dry-run` girano senza errori. Ledger, `trade.py`, scheduler e workflow non toccati.
- **Backup**: `backups/20261113-211512/` (`shadow.py`, `README.md`, `CHANGELOG.md`). Rollback: ripristinare `shadow.py`.
- **File R&D**: `rd-paper-trading/rd1113z/` (`v1_runner.py`, `sim.py`, `ls_spread.py`, risultati JSON e trade CSV) e
  `rd-paper-trading/reports/zerotrade_2026-11-13.md`.

## 2026-11-13 (14:33 ora di Roma) – R&D: posizioni più grandi con leva KO x5 (C e v0) → NON validato, nessun deploy; verifica regola fiscale

- **Richiesta** (Andrea tramite Sguattera): diluire i 2 € fissi con nozionale 2.000–3.000 € via leva fino a x5, rischio 2–3%, e una versione
  "meno trade di qualità più alta". Nessuna regola di trading è cambiata: il bot continua con la v0.
- **Regola fiscale (confermata da Andrea) – verifica**: 26% sull'utile di ogni operazione al netto delle commissioni di acquisto e vendita;
  perdite nette (commissioni incluse) nello zainetto per 4 anni, compensano solo le plusvalenze successive.
  - Produzione (`common.apply_tax` / `close_position`, usati da `trade.py` e `close_all.py`): **già corretta**, nessuna modifica.
  - Motori R&D `backtest.py` (`./run_rd.sh`) e `backtest_leverage.py`: **già corretti** (tasse alla chiusura, in ordine temporale). La v0 e i risultati
    precedenti non cambiano.
  - `shadow.py`: riporta il netto **ante tasse** ed è dichiarato come tale (solo misura, nessun ordine). Nessuna modifica.
  - `backtest_usorb.py` (test di stamattina): **2 errori corretti** in R&D. Le tasse venivano applicate in ordine di ingresso invece che di chiusura.
    Inoltre il dimensionamento e il limite giornaliero usavano l'esito di trade non ancora chiusi, quindi c'era informazione futura.
  - **Da dove venivano i ~15 € di C (+46,01 lordo − 44 commissioni = +2,01 ante tasse, ma −12,86 netto)**: non da un bug della regola. Sono 14,87 €
    di tasse pagate sui trade vincenti di settembre e inizio ottobre (COIN, AMD, META, TSLA), quando lo zainetto era vuoto. Le perdite sono arrivate
    dopo (ottobre e novembre) e a fine periodo restano ~69 € di zainetto non usato: le tasse già pagate non tornano. Spread e slippage erano già dentro il lordo.
  - **Ricalcolo cronologico corretto** (`rd-paper-trading/recalc_usorb_chrono.py`): C 19 trade OOS, lordo −21,53 €, tasse 2,02 €, **netto −61,55 €**,
    PF 0,61. A 39 trade, −240,52 € (prima −235,37). B 28 trade, −155,90 € (prima −155,48). Le conclusioni non cambiano: nessuna variante validata.
    C peggiora perché il suo risultato dipendeva da quali trade restavano sopra il nozionale minimo di 1.000 €: il campione è fragile.
- **Metodo**: le regole sono pre-registrate alle 14:23, prima dei risultati (`rd-paper-trading/reports/preregistration_2026-11-13_sizing.md`).
  - Combinazioni, 4 al massimo: C_2000_r2, C_3000_r3, V0_2000_r3 e V0Q_3000_r3 (analista ≥ 40 e un solo ingresso al giorno).
  - Strumento: KO x5 su azione con spread 0,50%, 1 € + 1 €, slippage 0,05% e tasse corrette. Sizing cronologico, limitato dalla cassa libera, al massimo 3 posizioni.
  - Criteri: netto OOS > 0, ≥ 20 trade OOS, PF > 1,2, netto senza il migliore ≥ 0, DD ≤ 15% e P(−20% in 60 sedute) ≤ 10% (bootstrap da 10.000 simulazioni).
    Per C serve anche una conferma su barre 1h di circa 2 anni (dal 15/12/2023 al 19/08/2026, 697 sedute non usate stamattina).
- **Risultati OOS**:

  | Combinazione | Trade OOS | Netto OOS | PF | Max DD | Peggior giorno | KO | P(−20%/60 sed.) | P(−50%) | 1h 2 anni | Esito |
  |---|---|---|---|---|---|---|---|---|---|---|
  | C_2000_r2 | 1 | −19,07 € | 0 | −1,9% | −19,07 € | 0 | 0% | 0% | 0 trade | respinta |
  | C_3000_r3 | 1 | −28,55 € | 0 | −2,9% | −28,55 € | 0 | 0,05% | 0% | 0 trade | respinta |
  | V0_2000_r3 | 56 | **−330,38 €** | 0,25 | −60,2% | −36,60 € | 0 | 100% | 88% | – | respinta |
  | V0Q_3000_r3 | 39 | **−319,60 €** | 0,37 | −40,6% | −41,36 € | 0 | 99% | 39% | – | respinta |

- **Motivo preciso**:
  - Con il rischio fisso al 2–3%, un nozionale di 2.000–3.000 € richiede uno stop entro circa 0,7–0,8% del prezzo. Lo stop mediano dei segnali C
    è dell'1,4% sulle barre a 5 minuti e del 3% su quelle da 1 ora, quindi C non genera quasi trade: 1 in OOS e 0 su 2 anni. Aumentare il rischio
    per arrivare al minimo violerebbe le regole di rischio.
  - **Diagnostica, non usata come criterio**: i 218 segnali C su 1h a 2 anni, a nozionale fisso, hanno lordo negativo, −2,04 € a trade su 1.000 €
    e −6,11 € su 3.000 € (PF ante tasse 0,49–0,62). Il vantaggio di C visto stamattina non si conferma su dati indipendenti.
  - v0 a leva: lordo per trade negativo (−3,90 € e −6,19 €), quindi più leva amplifica le perdite. Il risultato è coerente con cap100 del 12/11
    (−360 €). La versione "qualità" (analista ≥ 40, un trade al giorno) fa meno trade ma ha un lordo per trade peggiore.
  - Il collo di bottiglia non sono solo le commissioni. Questi segnali non hanno un vantaggio lordo e la leva non lo crea: serve prima un segnale
    con lordo positivo e stabile a 1x.
- **File** (copia R&D): `backtest_sizing.py`, `recalc_usorb_chrono.py`, `diag_c1h.py`, `reports/backtest_sizing_2026-11-13.json`,
  `reports/backtest_usorb_2026-11-13_recalc.json` e `reports/trades_sizing_*.csv`. Codice di produzione, scheduler e ledger non sono stati toccati;
  è stato pubblicato solo questo CHANGELOG.

## 2026-11-13 (~14:40 ora di Roma) – R&D: altri rimedi testati su 3 anni di barre orarie → nessuno supera la v0, nessun deploy

- **Perché**: zero trade dal 12/11. Abbiamo cercato rimedi diversi da quelli già in test da Lerabuns (ORB USA e leva sulla v0).
  Nessuna regola di trading è cambiata.
- **Dati e metodo**: barre yfinance da 1 ora dal 12/2023 al 12/11/2026 sui 71 titoli dell'universo TR (circa 50.600 giornate-titolo),
  più indici (DAX, Euro Stoxx 50, S&P 500, Nasdaq 100) e i 60 giorni a 5 minuti come controllo. Il 2024 è in-sample, 2025-2026 è
  fuori campione (OOS). Slippage 0,05% per lato, commissioni 1 € + 1 €, tassa 26% sull'utile dopo commissioni con zainetto, rischio 2%,
  tetto 30% per posizione (oppure KO x5 con spread 0,10% sul nozionale), al massimo 3 posizioni al giorno.
- **Risultati** (bp = rendimento medio a trade dopo lo slippage e prima delle commissioni):

  | Rimedio | Esito |
  |---|---|
  | Gap fade all'apertura, gap ≥ 1 ATR, stop 1 ATR, target chiusura del gap (UE+USA) | Portafoglio realistico OOS 2025-26: 118 trade, **−339,90 €**, PF 0,29, DD −34%; con KO x5: 242 trade, **−764,59 €**, DD −77%. IS 2024: −338,69 €. Media dei trade presi ≈ 0 bp. L'effetto medio positivo (+46 bp) viene quasi tutto dal crollo dell'aprile 2025 (2025Q2 +182 bp); senza quel trimestre, UE +0,5 bp. |
  | Gap fade solo UE, gap ≥ 1,5 ATR | OOS 89 trade, **−338,11 €**, PF 0,15, DD −34% |
  | Gap fade USA solo nei giorni in cui anche l'S&P 500 apre in gap ≥ 1% nella stessa direzione | 2024: 26 trade, −80,93 €, PF 0,40; 2025-26: 51 trade, **−4,64 €**, PF 0,98 (KO x5 −7,86 €) |
  | Gap-and-go (stessa direzione del gap) | dall'apertura −4 / −36 bp (soglie 0,3 / 1 ATR); dopo la prima ora ≈ 0 bp |
  | Momentum della prima ora fino alla chiusura (\|r1\| ≥ 0,5-1 ATR) | da −4 a +3 bp dopo lo slippage; servirebbero ≥ 20 bp solo per le commissioni |
  | Rottura del massimo/minimo di ieri dopo la prima ora | −0,5 bp (21.590 casi) |
  | Trend di fine giornata (dalle 15:00 UE / 19:30 USA alla chiusura) | da −0,5 a +2 bp |
  | Momentum intraday sugli indici (DAX, ESTX50, SPX, NDX; ultima ora e resto della giornata) | da −2,5 a +1,5 bp; l'S&P 500 negli ultimi anni tende a invertire |
  | Uscite sull'ORB (proxy a 1 ora, 38.926 casi): 2R+BE, 3R+BE, trailing 1R, uscita a tempo | tutte fra −9,1 e −10,0 bp, cioè vantaggio lordo zero: il tipo di uscita non cambia nulla |
  | Universo più volatile (ORB per quintile di ATR%, fino a ATR 4,9%) | da −8,3 a −11 bp in ogni quintile: nessun vantaggio |
  | Inversione/continuazione dopo un giorno di forte movimento (≥ 1,5-3 ATR) | da −22 a +2 bp, segno instabile da un anno all'altro |

- **Conclusione**: su questi titoli e con dati gratuiti non abbiamo trovato setup intraday con un vantaggio lordo che superi stabilmente
  2 € di commissioni su posizioni da 300-1.500 €. La leva amplifica le perdite, il filtro su volatilità e uscite non crea vantaggio. Il
  criterio di deploy (netto OOS > 0 e migliore della v0, DD < 15%) non è soddisfatto da nessuna variante. Non aggiungiamo shadow nuovi:
  nessuna idea è abbastanza promettente da giustificare un'altra fonte di segnali.
- **Nota sui dati**: in yfinance CON.DE ha un falso "gap" dopo lo spin-off di Aumovio (09/2025), che falsa i test sui gap se non si
  filtra.
- **File**: gli script e i risultati sono in `rd-paper-trading/rd1113/` (copia R&D, fuori dal repo). Codice di produzione, workflow e
  ledger non sono stati toccati.

## 2026-11-13 (14:20 ora di Roma) – R&D urgente: ORB sessione USA long+short via knock-out x5 → NON validato, nessun deploy

- **Richiesta** (Andrea tramite Sguattera): un setup ORB sulla sessione USA, long e short, con filtri meno restrittivi, live prima delle 15:30
  **solo se** ha valore atteso netto positivo. Nessuna regola di trading è cambiata: il bot continua con la v0.
- **Metodo**: le regole sono pre-registrate prima dei test, alle 14:18 (`rd-paper-trading/reports/preregistration_2026-11-13_usorb.md`).
  - Universo: 19 titoli USA dell'universo TR. Dati: barre yfinance a 5 minuti, 55 sedute complete dal 20/08 al 12/11.
  - Le prime 20 sedute sono riscaldamento; l'OOS va dal 18/09 al 12/11 (35 sedute).
  - Strumento: long e short tramite KO su azione x5 (`derivatives.py`), con spread 0,50% sul certificato, knock-out controllato su ogni barra,
    1 € + 1 € di commissioni, slippage 0,05% per lato, tasse 26% con zainetto. Rischio 2% compresi i costi, nozionale minimo 1.000 €, investimento
    massimo pari a equity/3, al massimo 3 posizioni.
  - Regole: OR 15:30-16:00, ingressi 16:00-17:30 all'apertura della barra successiva, stop max(OR opposto, 1,5·ATR5m) fra 0,4% e 3%,
    target 2R, breakeven a +1R, uscita forzata alle 21:45.
  - Filtri: VWAP, trend del giorno, nessun inseguimento e volume relativo dell'OR ≥ 1,2.
  - Criteri: netto OOS > 0, almeno 20 trade OOS, PF OOS > 1,1, netto OOS senza il trade migliore ≥ 0.
- **Risultati OOS** (netto dopo tutti i costi e le tasse):

  | Variante | Trade OOS | Lordo OOS | Commissioni | Netto OOS | PF | Senza il migliore | Esito |
  |---|---|---|---|---|---|---|---|
  | A: ORB long+short senza analista | 39 | −157,37 € | 78 € | **−235,37 €** | 0,20 | −248,87 € | respinta |
  | B: A + analista coerente (±15) | 28 | −99,48 € | 56 € | **−155,48 €** | 0,36 | −173,91 € | respinta |
  | C: A solo gap ≥ 1,5% nella sua direzione | 22 | +46,01 € | 44 € | **−12,86 €** | 0,92 | −38,99 € | respinta |

  - Sull'intero campione: A −374,28 € (71 trade), B −220,55 € (40 trade, tutti short: nessun long ha punteggio ≥ +15), C −11,25 € (33 trade).
  - Blocchi OOS di C: +50,98 / −0,86 / −71,54 / +8,56 €.
- **Motivo preciso del mancato deploy**: nessuna variante soddisfa i criteri.
  - A e B hanno già un lordo negativo: il breakout USA con filtri allentati perde prima dei costi, e gli short peggiorano il risultato.
  - C è l'unica con lordo positivo, +46 € su 22 trade, cioè circa 2,1 € a trade. Questo margine è più o meno uguale alle commissioni
    (2 € a trade) e lascia +2 € prima delle tasse, ma il netto è −12,86 € e il PF 0,92.
  - Allentare i filtri aumenta i trade ma non il margine per trade. Come stabilito, i criteri non sono stati allentati dopo i risultati.
- **File**: `rd-paper-trading/backtest_usorb.py`, `reports/backtest_usorb_2026-11-13.json` e `reports/trades_usorb_{A,B,C}.csv` (copia R&D).
  Codice di produzione, scheduler e ledger non sono stati toccati.

## 2026-11-12 (~23:05 ora di Roma) – R&D serale: shadow diagnostico sul filtro commissioni; nessuna regola di trading cambiata

- **Stato**: sessione GitHub regolare (heartbeat 22:25, job di attesa notturno in corso verso le ~07:10). Oggi 0 operazioni, equity 1.000,00 €.
- **shadow.py (solo misura, mai ordini)**: oggi il segnale ORB_DYN su AVGO (grafico APPROVE 40) risultava "non approvato" perché il filtro
  commissioni dava quantità 0; il report lo etichettava in modo fuorviante. Ora ogni segnale salva `qty_diag` (rischio 2%, tetto 30%, senza
  filtri minimo/commissioni) e a fine giornata i segnali APPROVE bloccati solo da quel filtro ricevono un esito diagnostico (`diag: true`),
  sommato separatamente. Etichette corrette: "respinto dall'analista grafico" vs "diagnostico". Prova isolata (PT_SHADOW_DIR/PT_REPORTS/PT_BARS
  temporanei) sui segnali di oggi: AVGO stop, lordo −1,90 €, netto −3,90 € (il filtro oggi ha evitato una perdita); `--dry-run` della scansione ok.
- **Backtest serale** (20/08–12/11, 61 sedute, dati aggiornati): baseline v0 21 trade, netto −23,93 € (OOS 18 trade −20,70 €); no_chart −62,78 €;
  delay15 −18,95 €; pullback identico alla baseline; us_rescan −59,38 €. Leva: da ko_ls_x1 −53,14 € a ko_ls_x5 −731,65 €, factor x2–x5 da −272 a −690 €;
  strict_fees 0 trade (non testabile). Nessuna variante validata.
- **Ipotesi pre-registrata `cap100`** (tetto posizione 100% invece di 30%, per diluire le commissioni fisse): 112 trade, netto **−360,53 €**,
  OOS 74 trade −225,28 €, DD −37,8% → **scartata**. Diagnosi: un tetto più alto fa passare il filtro commissioni a molti trade con stop stretto,
  e quei trade marginali hanno vantaggio lordo nettamente negativo; il filtro commissioni oggi funziona anche da filtro di qualità. Stesso
  messaggio dalla leva: più esposizione = più perdita. Nessun ritocco del parametro su questo campione.
- **Raccomandazioni HR del 12/11, valutate**:
  - "servono 20-30 trade": accolta (nessuna regola cambiata).
  - pullback su VWAP: **scartata nella forma attuale** — nel backtest le condizioni del pullback coincidono con quelle dell'ORB (sopra ORH, sopra VWAP,
    momentum > 0, non esteso), quindi un breakout esteso che rientra viene già preso dalla v0: 0 trade aggiuntivi. Andrebbe ridefinito come setup diverso.
  - mean-reversion su VWAP: già testata (REBOUND, −14,25 € in 61 sedute, −336 € su 2 anni di barre 1h) → resta solo in shadow.
  - quant/backtester: esiste già (`/workspace/rd-paper-trading`, walk-forward); corretto `run_rd.sh` che senza argomenti passava un argomento vuoto e falliva.
  - monitor qualità quotazioni: già coperto dal feed L&S (ritardo misurato 5-40 s, mediana ~40 s dai runner GitHub).
  - analista notizie LLM: già attivo (Natasia); nuovo `rd-paper-trading/news_eval.py` misura in ombra giudizio LLM vs punteggio a parole chiave
    sul rendimento open→close della seduta successiva. Oggi 0 coppie valutabili (storico con prezzo solo da oggi); integrazione solo con ≥ 100 coppie e vantaggio netto OOS.
  - analista calendario/eventi e specialista sessione USA: non ancora testabili sui dati (nessun calendario storico; ORB USA già scartato −36,44 €); rinviati.
- Backup in `backups/20261112-230537/`. Ledger non toccato.

## 2026-11-12 (~21:20 ora di Roma) – Catena notturna verso l'apertura, indipendente dal cron

- **Perché**: il workflow è attivo su `main`, ma a sera i run erano solo `workflow_dispatch` (nessuno
  innescato da `schedule`). Su un repo nuovo o rinominato GitHub può registrare i cron in ritardo, e
  senza catena dopo le 22:25 la sessione di domani potrebbe non partire.
- **Nuovo**: `gh/chain.py` e il modo `wait` in `gh/session_runner.py` / `gh/decide.py` /
  `.github/workflows/session.yml`. A fine giornata (lun-gio) la sessione lancia un job che dorme fino
  alle ~07:10 ora di Roma (due hop da 340 minuti al massimo) e poi apre la sessione. Il job di attesa
  non installa dipendenze e non tocca il branch `state`. Prima di ogni dispatch verifica che non ci
  sia già un run in coda (oltre al gruppo di concorrenza `paper-state`).
- Venerdì sera la catena si ferma; il lunedì riparte il cron, con la routine feriale come riserva se
  il cron non è ancora attivo.
- `permissions: actions: write` resta, serve a lanciare il run successivo con `GITHUB_TOKEN`.
- Test locali: `python3 gh/test_chain.py` (47 controlli su orari e hop) e `--dry-run` del runner,
  senza toccare la sessione in corso né lo stato.

## 2026-11-12 (~19:30 ora di Roma) – Il bot gira su GitHub Actions (repo pubblico), scheduler del box spento

- **Perché**: il box va in pausa quando nessun agente è attivo e il bot si fermava (oggi più pause, apertura USA persa).
- **Nuovo**: `.github/workflows/session.yml`, `gh/session_runner.py`, `gh/decide.py`, `gh/state.py`, `gh/secret_check.py`,
  `sync_github.sh`, `gh_status.sh`, `requirements.txt`, `.gitignore`. Dettagli nel README, sezione «Dove gira».
- Sessioni lunghe (max 340 min) a catena dalle ~06:15 alle 22:25, cron di controllo ogni 30 min, notizie ogni ora fuori orario.
- Stato sul branch `state` (un solo commit, force push), salvato ogni 15 min; il box lo scarica con `./sync_github.sh pull`.
- `scheduler.py`: rifiuta di partire fuori da GitHub senza `PT_LOCAL_SCHEDULER=1`. **Bug corretto**: dopo una pausa a
  cavallo della mezzanotte il recupero segnava il `close_all` di oggi come già fatto e quello delle 21:50 saltava.
- `start_scheduler.sh`: non avvia più lo scheduler locale, mostra lo stato delle sessioni GitHub.
- `update.py`: scarica prima lo stato da GitHub, salva l'ora dell'ultimo aggiornamento in `local/update_state.json`
  (non più nel ledger, che viene sovrascritto), segnala se la sessione GitHub è ferma; le pause diventano «pause o cambi di sessione».
- `sync_github.sh news`: pubblica solo i giudizi di Natasia; `update.py` lo esegue dopo il pull.
- Test su GitHub (19:23-19:35): news, rescan e notizie ok; trade fallito per `six` mancante → aggiunto a `requirements.txt`. Sessione live dalle 19:37: L&S raggiungibile dai runner (ritardo mediano ~40 s), Yahoo ok, cicli trade/manage/shadow/news regolari, stato salvato alle 19:51 e scaricato sul box.
- Backup in `backups/20261112-191915/`.

## 2026-11-12 (~18:45 ora di Roma) – news.py ogni 10 minuti + notizie forti nella watchlist dinamica

- **Scheduler**: `news.py` (raccolta RSS e sentiment a parole chiave, senza agenti) ora gira ogni 10 minuti, al minuto :x5, dalle 07:00 alle 22:00 nei giorni feriali. Fuori da quella finestra e nel weekend resta ogni ora al :05. I job di Natasia (`news_llm`) non sono stati toccati.
- **Robustezza e rispetto delle fonti**:
  - lock non bloccante `data/.news.lock`;
  - GET condizionali con ETag e Last-Modified (`data/news_fetch_state.json`); i server di MarketWatch, Investing.com, FXStreet e Il Sole 24 Ore li forniscono e rispondono 304;
  - ogni titolo viene interrogato al massimo ogni 30 minuti, ogni 10 se è in watchlist;
  - pausa di 30 minuti per un host che risponde 429 o 503.
  - Durata misurata in una copia isolata: 6-7 s per la run completa, circa 1 s quella successiva, con 0 titoli dovuti e i feed macro in 304. Due run lanciate insieme: la seconda esce con "run precedente ancora in corso".
- **Notizie forti → watchlist dinamica**: le soglie sono fissate a priori (vedi README):
  - A) |sentiment keyword 6h| ≥ 0,5 su almeno 3 notizie;
  - B) almeno 5 notizie in 60 minuti, e almeno 3 volte la media oraria dei 7 giorni precedenti.
  - Valgono lun-ven dalle 07:30 alle 21:00, con al massimo 5 aggiunte per run. L'aggiunta è immediata, tramite `rescan.add_items`, con un lock sul file della watchlist dinamica. Ogni aggiunta va in `logs/dwl_additions.log` con ora e motivo.
  - È solo un candidato, non un segnale di acquisto. Gli ordini restano solo della v0 sulla watchlist statica; i candidati dinamici alimentano solo lo shadow.
- **Test in una copia isolata** (`PT_NEWS_DB`, `PT_NEWS_STATE`, `PT_NEWS_LOCK`, `PT_DWL_DIR`, `PT_LOGS` temporanei):
  - dry-run: notizie forti su NVDA (raffica di 7-22 notizie in un'ora), SAP.DE, SIE.DE ed ENR.DE (sentiment da +0,54 a +0,74);
  - caso sintetico: 6 titoli "BASF shares plunge after profit warning" negli ultimi 30 minuti. BAS.DE viene aggiunto con il motivo "sentiment −0,67 su 11 notizie; raffica di 8 in 60 min" e registrato nel log; nessun doppione alla run successiva;
  - fuori finestra (sabato, oppure 22:30): nessuna aggiunta;
  - scheduler con orologio finto: venerdì 99 run di news (ogni 10 minuti dalle 07:05 alle 21:55, più quelle orarie), sabato 24.
- **Deploy**: backup in `backups/20261112-184217/` (`news.py`, `rescan.py`, `shadow.py`, `scheduler.py`, `README.md`, `CHANGELOG.md`). Scheduler riavviato alle 18:42 con ambiente pulito; heartbeat regolare. Ledger non toccato.

## 2026-11-12 (sera, ~18:45 ora di Roma) – Watchlist dinamica + strategie in SHADOW; nessuna regola di trading cambiata

**Attivo da domani 13/11:**
- **In produzione (ordini)**: invariata la strategia v0 (ORB+VWAP+momentum 15m+analista grafico) sulla watchlist statica delle 09:35. Nessuna nuova strategia supera la validazione, quindi **nessuna** aggiunta agli ordini.
- **Infrastruttura nuova**: `rescan.py`, la watchlist dinamica. Ogni 30 minuti dalle 09:30 alle 21:00 rianalizza tutti i 71 titoli dell'universo; i titoli USA entrano solo dopo l'opening range USA, 15:30-16:00. Un titolo diventa candidato se il movimento rispetto a ieri è almeno max(2%; ATR giornaliero) e il volume relativo è almeno 1,5. Diventa candidato anche con un giudizio non scaduto di `news_llm.json` con |impact| ≥ 0,5 e confidence ≥ 0,6. Per ogni rescan c'è una sola richiesta batch Yahoo. I candidati sono usati **solo in shadow**: `trade.py` non li legge.
- **SHADOW** (`shadow.py`): registra soltanto segnali ipotetici, senza ordini e senza scrivere sul ledger. Gira ogni 10 minuti al minuto :x3; l'esito viene calcolato alle 21:56 in `reports/shadow_YYYY-MM-DD.md`.
  - `REBOUND`: rimbalzo con riconquista del VWAP dopo un forte calo.
  - `ORB_DYN`: ORB v0 sui soli candidati dinamici, quindi anche l'ORB della sessione USA sui titoli che si muovono.
  - Servono ad accumulare evidenza, non sono candidate al deploy a breve (vedi i numeri sotto).
- `scheduler.py` lancia i nuovi job, compresi il recupero dopo una pausa e `shadow_eod` una sola volta al giorno. È stato riavviato alle 18:36 e l'heartbeat è regolare.

**Perché**: oggi zero trade e il caso NVDA (crollo sulla notizia di Huang, poi rimbalzo) non è stato visto, perché NVDA non era nella watchlist statica.

**Test**: walk-forward su yfinance 5m dal 19/08 all'11/11, 61 sedute. 20 sedute IS, blocchi OOS da 10, holdout finale di 1/3. Commissioni 1+1 €, slippage 0,05%, tassa 26% con zainetto. Le regole sono pre-registrate prima dei risultati in `rd-paper-trading/reports/preregistration_2026-11-12.md`, una variante per strategia, senza griglie. Netto sull'intero campione / trade OOS e netto OOS / netto holdout / max DD:

| Strategia | Netto | Trade OOS, netto OOS | Netto holdout | Max DD |
|---|---|---|---|---|
| Baseline v0 (19 trade) | −18,58 € | 16 trade, −15,35 € | −7,64 € | −3,14% |
| S1, ORB su watchlist statica ∪ dinamica (28 trade) | −37,94 € | 24 trade, −34,14 € | −24,64 € | −5,29% |
| S2, ORB + rimbalzo VWAP (30 trade, di cui 2 rimbalzi) | −45,28 € | 26 trade, −41,48 € | −27,16 € | −6,01% |
| S2, solo rimbalzo (3 trade) | −14,25 € | 3 trade, −14,25 € | −9,39 € | −1,43% |
| S3, ORB USA su candidati dinamici dalle 16:00 (20 trade) | −36,44 € | 17 trade, −33,26 € | −32,13 € | −3,82% |
| Rimbalzo senza analista grafico, diagnostico (39 trade) | −75,41 € | 33 trade, −69,00 € | −60,37 € | −7,76% |

- **Robustezza 1h**: rimbalzo semplificato su 2 anni di barre orarie, dal 12/2023 all'11/2026: 133 trade, netto **−336,21 €**. Il netto è negativo in ogni anno, il win rate è del 19,5% e solo 6 blocchi OOS su 73 sono positivi.
- Benchmark buy&hold EXS1.DE nello stesso periodo: +12,93 €.
- **Leva e short**: non testati, come pre-registrato. La condizione era una strategia non levata con lordo OOS > 0, e nessuna la soddisfa: il rimbalzo da solo ha un lordo di −8,25 €.
- **(c) Segnali**: nella v0, 84 segnali ORB arrivano all'analista grafico in 61 sedute (circa 1,4 al giorno). Ne approva 19 e 46 sedute su 61 restano senza trade. Il problema non è la scarsità di segnali ma un margine lordo (+20 €) inferiore alle commissioni (38 €). Allentare i filtri peggiora: senza analista grafico −62,65 € (test precedente), rimbalzo senza grafico −75,41 €. Nessun filtro è stato allentato.
- **Controllo qualitativo NVDA del 12/11**, fatto dopo i test e non usato per i parametri: la watchlist dinamica avrebbe incluso NVDA alle 16:00. Però gran parte del rimbalzo (da 149 a 163 $) avviene dentro l'opening range 15:30-16:00. Dopo le 16:00 l'ORB dà segnali alle 16:20, 16:30 e 17:00, ma l'analista grafico li respinge (punteggio da −40 a −45: daily sotto SMA20, SMA20 < SMA50, RSI 29). Il rimbalzo scatta solo alle 18:00, con punteggio −80, respinto.
- **Bug di `open_position`** (corretto alle 16:30): verificato in una copia isolata (`PT_DB` temporaneo). L'acquisto e la vendita di SAP.DE (EUR) e NVDA (USD) vengono registrati correttamente: trade, cassa, commissioni e zainetto per le perdite.
- **Prove dei job nuovi**:
  - `rescan.py --dry-run`, `shadow.py --dry-run` e `shadow.py --eod --dry-run` girano senza errori in produzione. `./run.sh rescan` e `./run.sh shadow` sono stati eseguiti davvero alle 18:36: candidato AVGO e un segnale shadow `ORB_DYN` registrato.
  - Lo scheduler è stato provato con orologio finto: orari dei job, `shadow_eod` una volta sola, piano di recupero dopo una pausa.
  - Simulazione dell'esito con un segnale di prova in una copia isolata.
- **Backup**: `backups/20261112-183446/` contiene `scheduler.py`, `README.md`, `CHANGELOG.md` e `run.sh`. I file nuovi sono `rescan.py` e `shadow.py`. Per il rollback: ripristinare `scheduler.py`, rimuovere i due file nuovi e riavviare lo scheduler.
- **Ledger**: non toccato. Tutti i test hanno usato copie isolate.

## 2026-11-12 (16:30, ora di Roma) – Robustezza alle pause della macchina

La macchina viene messa in pausa quando nessun agente è attivo, e con lei lo scheduler. Oggi 15:42-16:15 i passaggi trade delle 16:00/16:10 e i controlli stop ogni 2 minuti non sono partiti. Non c'erano posizioni aperte, quindi nessun impatto sul conto.

- **scheduler.py**: se il ciclo si risveglia più di 3 minuti dopo il tick precedente, oppure all'avvio trova `logs/scheduler_heartbeat` vecchio di oltre 3 minuti, esegue subito una catena ordinata di recupero: `trade --manage --catchup`, poi `close_all` se le 21:50 sono passate (o la pausa ha superato la mezzanotte), `scan` se le 09:35 sono state saltate, un passaggio `trade` completo se si è ancora nella finestra 07:30-21:45, e infine `report`, `team_review` e `news` se sono stati saltati. I job una tantum (scan, close_all, report, team_review) registrano il giorno dell'ultima esecuzione in `logs/scheduler_state.json`, così non partono mai due volte. Funzioni testabili con orologio finto: `main(clock=..., sleep=..., run=..., max_ticks=...)`.
- **trade.py `manage_open`**: rigioca **tutte** le barre dall'ultimo controllo (checkpoint per titolo nella tabella `state`, chiave `watch_ckpt:<ticker>`), non solo il prezzo attuale. Usa, in ordine, le barre a 1 minuto L&S di `data/bars.sqlite`, poi yfinance a 1 minuto, poi le barre a 5 minuti per gli intervalli non coperti, e infine la quotazione live con low = bid (`common.replay_bars`). Lo stop si esegue al livello dello stop, oppure all'apertura della barra se il prezzo ci è passato sopra con un gap, meno mezzo spread live e lo slippage; il target come prima. Se stop e target cadono nella stessa barra, vale lo stop. Il breakeven vale dalla barra successiva. Le barre successive alle 21:50 del giorno di ingresso vengono ignorate. La barra ancora in formazione viene ricontrollata al passaggio successivo (prima veniva saltata).
- **Chiusura mai saltata**: le posizioni "scadute" (aperte in un giorno precedente, oppure con risveglio dopo le 22:00) vengono prima rigiocate fino alle 21:50 e poi chiuse all'ultimo prezzo prima delle 21:50 (`common.late_flatten`), con motivo "chiusura in ritardo (pausa macchina)" nel registro. Lo fanno `trade.py --manage --catchup`, `close_all.py` e il passaggio `trade` completo.
- **logs/gaps.log**: una riga per pausa (inizio, fine, durata, azioni di recupero) più le righe `CATCHUP-STOP`, `CATCHUP-TARGET` e `LATE-FLATTEN`. `update.py` riporta le pause avvenute dall'ultimo aggiornamento.
- **Bug corretto** in `common.record_trade`: `open_position` passava `currency` due volte, causando un `TypeError` a **ogni acquisto**. Finora non era mai scattato perché nessun ingresso era ancora avvenuto.
- Test isolati (`PT_DB`, `PT_LOGS`, `PT_REPORTS`, `PT_CHARTS`, `PT_BARS`, `PT_LOCK`) con orologio finto: 6 scenari di pausa per lo scheduler e 8 scenari di stop, gap e chiusura in ritardo, tutti superati. Più un passaggio reale `--manage --catchup` su dati L&S, che ha rigiocato 50 barre a 1 minuto, pausa inclusa.
- Backup in `backups/20261112-161748/`.

## 2026-11-12 (dopo le 15:36, ora di Roma) – Provenienza e prezzo nello storico LLM

- Da questo momento ogni **nuova** riga di `data/news_llm_history.jsonl` contiene anche: `news_published_from`, `news_published_to`, `news_ids` (id delle notizie in `data/news.sqlite` usate per il giudizio), `price_at_issue`, `price_source`, `price_time` (`null` se non disponibili).
- `issued_at` e `expires_at` sono sempre ISO 8601 con fuso orario esplicito.
- Lo storico è solo in aggiunta: le righe precedenti non si riscrivono mai e non hanno questi campi.

## 2026-11-12 (pomeriggio) – Quotazione live, volume e controllo stop ogni 2 minuti

- **Ritardo**: la quotazione usata per decidere non è più il mid del chart a 1 minuto (1-7 min). Si legge bid/ask/mid e l'orario dalla pagina pubblica L&S (stessi campi aggiornati dal push del sito). Ritardo misurato da questa macchina: **circa 5-40 secondi** (mediana tipica ~10-20 s), contro ~15 min di Yahoo UE e 2-6 min del solo chart.
- **Volume / VWAP**: CSV ufficiale delle esecuzioni L&S di oggi (`lstctradestoday`) per il volume sulla sede. Nelle ore di borsa ufficiale il volume delle barre è quello Yahoo (confrontabile con lo storico); il tape L&S copre gli ultimi minuti in ritardo e gli orari estesi, scalato quando possibile. Fallback Yahoo se il tape non ha print.
- **Spread**: acquisto all'ask e vendita al bid quando il book L&S c'è; altrimenti resta lo slippage 0,05%. Stop e target restano simulati come ordini in attesa.
- **Scheduler**: ogni 2 minuti, se c'è una posizione aperta, `trade.py --manage` controlla solo stop e target (niente nuovi ingressi né uscite discrezionali sul grafico). Se il conto è piatto il passaggio termina subito. I processi figli vengono raccolti (niente zombie).
- Backup in `backups/20261112-1439/`.

## 2026-11-12 – Feed L&S quasi in tempo reale (soldi finti)

Fonte primaria dei prezzi: endpoint JSON pubblici di Lang & Schwarz TradeCenter (`ls-tc.de`), la sede su cui esegue Trade Republic.

- Nuovo modulo `marketdata.py`: ricerca strumento per ISIN, chart mid a 1 minuto, ricampionamento a barre da 5 minuti, cache su disco (`data/ls_instruments.json`, `data/bars.sqlite`).
- `intraday_bars` / `last_prices` usano L&S come fonte principale, Yahoo Finance come fallback automatico. I prezzi L&S sono in EUR anche per i titoli USA (niente doppia conversione).
- Ritardo misurato da questa macchina oggi: Yahoo UE ~15 minuti; L&S circa 1-7 minuti (spesso 2-3, a volte ~6 se il titolo quota poco). Non serve una chiave API.
- Con i prezzi L&S si possono gestire (e, dopo l'opening range ufficiale, anche aprire) posizioni UE anche dopo le 17:30, fino alle 21:15; chiusura forzata di tutto alle 21:50. L'opening range resta 09:00-09:30 (UE) / 15:30-16:00 (USA, ora di Roma).
- ISIN di Telecom Italia aggiornato a `IT0005712671` (il precedente `IT0003497168` non è più presente su L&S).
- `PT_LOCK` evita che i test isolati blocchino lo scheduler dal vivo.
- Backup dei file modificati in `backups/20261112-140727/`.

Fonti valutate e non integrate: Tradegate (`refresh.php`, prezzi simili ma sede diversa da Trade Republic, senza timestamp); Finnhub e Twelve Data (richiedono una chiave API dell'utente). Lo stream Lightstreamer del sito L&S esiste ma è più fragile: il chart HTTP è sufficiente e più educato.
