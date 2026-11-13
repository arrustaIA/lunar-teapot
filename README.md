# Paper trading intraday – "team" su titoli Trade Republic (SOLO SOLDI FINTI)

Nessun collegamento a broker reali: tutto è simulato in `data/ledger.sqlite`. Capitale iniziale 1.000 €.
Orario della macchina = Europe/Rome. Tutti gli orari qui sotto sono ora di Roma.

> **Simulazione di paper trading con soldi finti.** Nessun conto, nessun broker reale, nessun ordine vero.
> Questo progetto non è una consulenza finanziaria né un invito a investire.

## Dove gira: GitHub Actions (dal 12/11/2026)
Il box degli agenti va in pausa quando nessun agente è attivo, quindi i programmi del bot girano su GitHub
Actions (repo pubblico, gratis). Sul box lo **scheduler locale resta spento**: due scheduler sullo stesso
ledger opererebbero due volte (`scheduler.py` rifiuta di partire fuori da GitHub senza `PT_LOCAL_SCHEDULER=1`).

- **Sessioni** (`.github/workflows/session.yml` → `gh/session_runner.py`): ogni sessione esegue `scheduler.py`
  per al massimo 340 minuti, fino alle 22:25 (dopo `team_review` delle 22:15). 6 minuti prima della fine mette
  in coda la sessione successiva (stesso gruppo di concorrenza `paper-state`: parte appena finisce la
  precedente, il buco di 1-3 minuti è coperto dal recupero pause dello scheduler). Nessun cambio di sessione
  nelle aperture 09:00-09:45 e 15:20-15:50. Giornata tipo: ~07:10-12:50, ~12:50-18:30, ~18:30-22:25.
- **Catena notturna** (lun-gio): a fine giornata parte un job `wait` che dorme fino alle ~07:10 ora di Roma
  e poi lancia la sessione. Un job dura al massimo 340 minuti, quindi la notte sono due hop (~22:25-04:00
  e ~04:00-07:10). Il job di attesa non tocca lo stato sul branch `state`. Prima di lanciare un run
  successivo controlla che non ce ne sia già uno in coda. Venerdì sera la catena si ferma; il lunedì
  riparte il cron, e se il cron non è ancora registrato ci pensa la routine feriale (primo controllo
  intorno alle 09:00).
- **Cron** (UTC, ridondanti perché GitHub può partire in ritardo o, su un repo nuovo/rinominato, non
  registrare subito gli orari; `gh/decide.py` ragiona in ora di Roma, quindi vale con ora solare e legale):
  `10,40 4-20 * * 1-5` avvia la prima sessione dalle 06:00 e fa da cane da guardia se la catena si
  interrompe; `25 * * * *` fuori orario e nel weekend fa solo una raccolta notizie. Un run programmato
  salta se c'è già una sessione o un'attesa attiva o in coda.
- **Stato** sul branch `state` (`gh/state.py`): ledger, barre, notizie, watchlist, `logs/`, `reports/`,
  `charts/`. Salvato ogni 15 minuti e a fine sessione, scaricato all'avvio. Il branch ha sempre un solo
  commit (force push) e lo snapshot pota barre > 45 giorni e file datati > 21 giorni: il repo resta piccolo.
- **Proprietà dei file**: GitHub scrive lo stato; il box scrive solo il codice e i giudizi di Natasia
  (`data/news_llm.json`, `data/news_llm_history.jsonl`, `data/news_llm_state.json`), che viaggiano su `main`.
  Ogni sessione fa `git pull` di `main` ogni 15 minuti: codice e giudizi nuovi arrivano anche in corsa.

### Come lo usano gli agenti sul box
```
./sync_github.sh pull    # prima di leggere risultati/notizie: scarica lo stato live da GitHub
./sync_github.sh news    # pubblica solo i giudizi di Natasia (lo fa anche update.py a ogni aggiornamento)
./sync_github.sh push    # dopo aver cambiato codice o news_llm*.json: pubblica su main (con controllo dati sensibili)
./gh_status.sh           # salute: ultimi run GitHub + età dell'heartbeat dello scheduler
```
- **Natasia**: `./sync_github.sh pull` → legge `data/news.sqlite` → scrive `data/news_llm*.json[l]` → `./sync_github.sh news`.
- **Lerabuns (R&D)**: `./sync_github.sh pull` per i risultati; test sempre su copie isolate (`PT_DB`, `PT_LOGS`, …);
  deploy = `./sync_github.sh push` (la sessione in corso prende il codice entro 15 minuti).
- `update.py` fa da solo `sync_github.sh pull` prima di leggere lo stato e segnala se la sessione GitHub è ferma.
- Il repo è **pubblico**: niente email, nomi, token o percorsi di account. `gh/secret_check.py` blocca il push.
- Il ledger sul box è una copia: le scritture locali vengono sovrascritte al pull successivo.
- Emergenza (GitHub fermo per giorni): disattivare il workflow e `PT_LOCAL_SCHEDULER=1 ./start_scheduler.sh --local`.

## Il team (script)
| Ruolo | Script | Quando (suggerito) |
|---|---|---|
| Analista notizie/sentiment | `news.py` | ogni 10 min (:x5) lun-ven 07:00-22:00, altrimenti ogni ora al :05 (anche notte e weekend) |
| Analista mattutino | `scan.py` | lun-ven 09:35 (dopo l'opening range EU) |
| Watchlist dinamica | `rescan.py` | lun-ven ogni 30 min 09:30-21:00 (USA da apertura+30 min); solo candidati |
| Strategie in shadow | `shadow.py` | lun-ven ogni 10 min al minuto :x3, 09:33-21:13; `--eod` alle 21:56 (nessun ordine) |
| Trader + Risk manager | `trade.py` | lun-ven ogni 10 min, 07:30-22:00 |
| Analista grafico | `chart_analysis.py` (chiamato da trade.py; anche CLI) | prima di ogni acquisto/vendita |
| Chiusura | `close_all.py` | lun-ven 21:50 (tutto; recupero automatico dopo una pausa) |
| Aggiornamento | `update.py` | ogni 3 h nelle ore di mercato |
| Report serale | `report.py` | lun-ven 21:55 |
| HR / revisione team | `team_review.py` | ogni giorno ~22:15 (solo raccomandazioni) |

Wrapper per job pianificati: `./run.sh <script> [args]` (log in `logs/`). Ogni script prende un lock, quindi esecuzioni sovrapposte sono sicure; tutti sono idempotenti.

```
cd /workspace/paper-trading
./run.sh news                 # aggiorna notizie (python3 news.py --show per vedere senza scaricare)
./run.sh scan                 # watchlist del giorno (--force per rigenerarla)
./run.sh trade                # un passaggio decisionale
./run.sh rescan               # watchlist dinamica (python3 rescan.py --dry-run per vedere senza scrivere)
./run.sh shadow               # segnali shadow (--eod: esito ipotetico e reports/shadow_YYYY-MM-DD.md)
python3 chart_analysis.py SAP.DE --side buy   # analisi grafica manuale + PNG
./run.sh close_all            # chiusura in base all'orario (--all forza, --region EU|US)
./run.sh update               # aggiornamento breve in italiano
./run.sh report               # report giornaliero in italiano -> reports/report_YYYY-MM-DD.md
./run.sh team_review          # revisione HR -> reports/team_review_YYYY-MM-DD.md
```
Reset del conto: `rm data/ledger.sqlite` (si ricrea a 1.000 €). Test isolati: `PT_DB=/tmp/x.sqlite PT_LOCK=/tmp/x.lock PT_BARS=/tmp/x.bars PT_LOGS=/tmp/l PT_REPORTS=/tmp/r PT_CHARTS=/tmp/c python3 ...`.

## Universo
`universe.csv`: 71 azioni singole liquide negoziabili su Trade Republic (LS Exchange): DAX/MDAX (.DE), FTSE MIB (.MI), grandi EU (ASML, LVMH, TotalEnergies, Sanofi, Santander) e grandi USA. Solo azioni, **niente ETF** (le plusvalenze da ETF sono redditi di capitale e non compensano le minusvalenze); l'ETF DAX `EXS1.DE` è usato solo come benchmark di confronto. Titoli USA quotati in USD convertiti in EUR con il cambio EURUSD live (Yahoo `EURUSD=X`).

## Dati di mercato e orari
- **Fonte primaria**: Lang & Schwarz (sede di Trade Republic). I prezzi sono in **EUR** anche per i titoli USA. Tre endpoint pubblici, tutti senza chiave:
  - quotazione live della pagina strumento (`bid`/`ask`/`mid` + orario): ritardo misurato **circa 5-40 secondi**;
  - CSV ufficiale delle esecuzioni di oggi (`lstctradestoday` su ls-x.de): volume e ultimo print sulla sede L&S;
  - chart mid a 1 minuto per le barre della sessione (fallback se la pagina non risponde).
  Il modulo è `marketdata.py` (cache in `data/ls_instruments.json`, barre e tape in `data/bars.sqlite`). Uso educato: cache 20-60 s a seconda dell'endpoint, pausa minima 0,25 s, al massimo 20 titoli per ciclo.
- **Volume e VWAP**: nelle ore di borsa ufficiale il volume delle barre a 5 minuti è quello di Yahoo (Xetra / Borsa / NYSE, confrontabile con lo storico e il volume relativo). Il tape L&S (spesso più sottile) riempie gli ultimi minuti in ritardo e gli orari estesi, scalato sul rapporto Yahoo/L&S di oggi quando è disponibile. Se L&S non ha print (es. alcuni titoli italiani), resta il volume Yahoo.
- **Esecuzioni simulate**: se c'è il book L&S, l'acquisto è all'ask e la vendita al bid (niente slippage extra). Stop e target restano ordini in attesa sulle barre. Se manca il book, si usa lo slippage fisso 0,05%.
- **Fallback**: se L&S non risponde, si usa automaticamente Yahoo Finance (barre a 5 minuti; ritardo UE ~15 min, USA quasi in tempo reale). I giorni precedenti restano di Yahoo (i titoli USA storici sono convertiti in EUR).
- Trade Republic tratta 07:30-22:00 (L&S quota fino alle 23:00):
  - nessun ordine fuori 07:30-22:00;
  - un titolo non viene tradato se l'ultima quotazione è più vecchia del ritardo normale del feed + 15 min (quotazione L&S live: >16 min, fallback Yahoo UE: >30 min, Yahoo USA: >15 min);
  - l'opening range resta quello della borsa ufficiale (EU 09:00-09:30, USA 15:30-16:00 ora di Roma);
  - ingressi: EU 09:30-21:15, USA 16:00-21:15 (passaggio completo ogni 10 min);
  - **controllo stop/target** ogni 2 minuti se c'è una posizione aperta (`trade.py --manage`); niente nuovi ingressi in quel passaggio;
  - uscite forzate: **tutto chiuso entro 21:50**.
- Diagnostica: `python3 marketdata.py --ping` oppure `--quote SAP.DE`.
- Festivi: se non ci sono barre di oggi, nessun trade. Weekend: scan/trade non fanno nulla (news gira comunque).


### Pause della macchina (scheduler robusto)
La macchina può essere messa in pausa quando nessun agente è attivo. Al risveglio `scheduler.py` rileva il buco: un tick arrivato più di 3 minuti dopo il precedente, oppure un heartbeat vecchio all'avvio. A quel punto lancia subito `trade --manage --catchup`, che rigioca tutte le barre a 1 minuto della pausa e quindi non salta mai uno stop o un target. Poi esegue i job saltati: `close_all` dopo le 21:50, `scan` delle 09:35, un `trade` completo se si è ancora in finestra, e `report`, `team_review` e `news`. Ogni job una tantum parte una sola volta al giorno (`logs/scheduler_state.json`). Una posizione rimasta aperta oltre le 22:00 o fino al giorno dopo viene chiusa al prezzo dell'ultima barra prima delle 21:50, segnata come "chiusura in ritardo". Le pause e le azioni di recupero sono in `logs/gaps.log` e compaiono negli aggiornamenti.

## Watchlist dinamica e strategie in shadow (dal 13/11/2026)
- `rescan.py` riscansiona tutto l'universo ogni 30 minuti. Un titolo è candidato se `|variazione vs ieri| ≥ max(2%; 1×ATR14 giornaliero %)` e volume relativo ≥ 1,5, oppure se ha un giudizio **non scaduto** in `data/news_llm.json` con `|impact| ≥ 0,5` e `confidence ≥ 0,6`. Al massimo 5 nuovi titoli per rescan; restano in lista fino a sera. I titoli USA entrano solo dopo l'opening range USA (15:30-16:00). Fonte: un'unica richiesta Yahoo 5m per rescan (UE ~15 min di ritardo, sufficiente per scegliere i candidati), daily in cache una volta al giorno (`data/.dwl_daily_YYYY-MM-DD.pkl`). Output: `data/watchlist_dyn_YYYY-MM-DD.json`, `reports/watchlist_dyn_YYYY-MM-DD.md`.
- **`trade.py` NON usa i candidati dinamici per gli ordini**: nel backtest walk-forward del 12/11 l'ORB v0 sulla watchlist dinamica peggiorava il netto (vedi CHANGELOG). Le notizie sono solo un input della watchlist, non un segnale validato.
- **Notizie → watchlist dinamica** (`news.py`, dopo ogni raccolta; soglie fissate a priori il 12/11/2026, `NEWS_ALERT` in `news.py`): un titolo dell'universo viene aggiunto subito alla watchlist dinamica, senza aspettare il rescan, se
  - A) il sentiment a parole chiave sulle ultime 6 h (`news_signal`) ha |score| ≥ 0,5 su almeno 3 notizie, oppure
  - B) c'è una raffica di ≥ 5 notizie sul titolo pubblicate negli ultimi 60 min e ≥ 3× la sua media oraria dei 7 giorni precedenti.
  Solo lun-ven 07:30-21:00, massimo 5 aggiunte per run, mai doppioni. Ogni aggiunta (ora, titolo, fonte, motivo) va in `logs/dwl_additions.log` e nel log del giorno. È solo un candidato: nessun ordine, e l'eventuale ingresso passa dalle strategie e dai filtri (oggi solo shadow). Prova: `python3 news.py --alerts-only --dry-run`.
- **news.py "educato"**: lock non bloccante `data/.news.lock` (una run che trova la precedente ancora attiva esce subito); GET condizionali con ETag/Last-Modified salvati in `data/news_fetch_state.json` (risposta 304 = nessun download); ogni titolo interrogato su Yahoo/Google News al massimo ogni 30 min (10 min se è nella watchlist statica o dinamica di oggi), quindi ogni run da 10 min tocca circa un terzo dell'universo; pausa di 30 min per un host che risponde 429/503. Durata misurata di una run: 6-7 s (prima run completa), ~1 s quando non c'è nulla di dovuto.
- `shadow.py` registra solo segnali ipotetici (mai ordini, mai il ledger) in `data/shadow_signals.jsonl` e, alle 21:56, l'esito simulato in `data/shadow_results.jsonl` (entrambi solo in aggiunta) e `reports/shadow_YYYY-MM-DD.md`:
  - `REBOUND`: rimbalzo "VWAP reclaim" dopo un forte calo (minimo ≤ chiusura di ieri × (1 − max(2,5%; ATR%)), minimo fatto da ≥ 15 min, riconquista fresca del VWAP, momentum 15m > 0, prezzo ancora sotto la chiusura di ieri, analista grafico APPROVE), su watchlist statica ∪ dinamica;
  - `ORB_DYN`: regole ORB v0 sui soli candidati dinamici.
  - `V0_LOOSE` (attiva dal 16/11/2026): ORB v0 sulla watchlist statica con estensione massima 3,0 ATR5m sopra ORH (v0: 1,5) e guadagno al target ≥ 1,5× commissioni (v0: 3×); analista grafico come la v0. Backtest −203,29 € (89 trade): solo misura di quanto opererebbe dal vivo, nessun ordine.
  Dal 13/11/2026 anche i segnali APPROVE dell'analista grafico che il solo filtro commissioni bloccherebbe ricevono un esito **diagnostico** (`diag: true`, quantità `qty_diag` con rischio 2% e tetto 30%, senza filtri minimo/commissioni), sommato a parte nel report: serve a misurare se quel filtro toglie trade buoni o cattivi.
  Sizing ipotetico su 1.000 €, commissioni 2 €, slippage 0,05%. Regole pre-registrate in `/workspace/rd-paper-trading/reports/preregistration_2026-11-12.md`.

## Regole di trading (trade.py) – solo long (Trade Republic non permette lo short di azioni)
1. Opening range (OR) = primi 30 min della sessione.
2. Segnale: prezzo > massimo OR, > VWAP, momentum 15 min positivo, non più di 1,5×ATR(5m) sopra il massimo OR (non si insegue).
3. Notizie: blocco se sentiment del titolo nelle ultime 6 h ≤ -0,4 o clima macro ≤ -0,4.
4. Analista grafico deve dare **APPROVE** (punteggio ≥ 25 su -100..+100).
5. Stop = max(minimo OR, prezzo − 1,5×ATR5m), distanza tra 0,4% e 3%. Target = 2R. Raggiunto +1R lo stop va a pareggio (commissioni incluse).
6. Stop e target sono simulati come ordini in attesa: ad ogni passaggio si ripercorrono le barre successive all'ingresso (se nella stessa barra si toccano entrambi, si assume lo stop). Gap oltre lo stop = esecuzione al prezzo di apertura.
7. Prima di ogni vendita discrezionale si chiede l'analista grafico: se il verdetto è EXIT (punteggio ≤ -30) si esce in anticipo.
8. Un solo ingresso per titolo al giorno. Slippage simulato 0,05% per ordine.

## Rischio
- Rischio max per trade 2% dell'equity (distanza stop × quantità + 2 € commissioni).
- Max 3 posizioni aperte, max 30% dell'equity per posizione.
- Posizione minima 200 € e guadagno atteso al target ≥ 3× le commissioni (con 1.000 € le commissioni pesano molto).
- Limite di perdita giornaliera -3% sull'equity di inizio giornata → chiusura di tutto e stop per il giorno.
- Frazioni di azione ammesse (`CFG["fractional"]`, impostabile a False per sole azioni intere).

## Costi e tasse (Italia, regime amministrato)
- 1 € per ordine (acquisto e vendita) → 2 € per operazione completa. I piani di accumulo gratuiti non sono rilevanti.
- Plusvalenza netta di ogni operazione (dopo commissioni, che sono costi deducibili): prima si compensa con lo **zainetto fiscale** (minusvalenze più vecchie prima), poi si trattiene il 26%.
- Minusvalenze: accumulate nello zainetto con data di origine, utilizzabili fino al 31/12 del 4° anno successivo (tabella `tax_losses`).
- Tobin tax italiana e francese: non applicate perché gravano sul saldo netto di fine giornata e le posizioni intraday sono chiuse in giornata.
- Semplificazioni: nessun effetto fiscale sul cambio EUR/USD; nessuna ritenuta su dividendi (posizioni mai tenute la notte).

## Analisi grafica (chart_analysis.py)
Daily (SMA20/50, RSI), 15 min (EMA9/21, MACD, RSI), 5 min (VWAP, MACD, RSI), volume relativo, supporti/resistenze (max/min di ieri, max/min 20 gg, max di oggi), candele (engulfing, shooting star, doji). Punteggio e motivazioni in italiano, salvati in tabella `analyses`; grafico PNG in `charts/YYYY-MM-DD/` per ogni segnale valutato e ogni vendita.

## Notizie (news.py)
Fonti verificate da questa macchina: notizie per titolo da yfinance e Google News RSS (EN/IT/DE), notizie macro da CNBC, MarketWatch, Investing.com, FXStreet, Il Sole 24 Ore. Reuters e Borsa Italiana non hanno feed RSS utilizzabili (Reuters compare via Google News). Deduplicazione per titolo, notizia associata a un titolo solo se il nome della società compare nel titolo, sentiment con dizionario finanziario di parole chiave (EN/IT/DE), pesato per recenza (emivita ~12 h). Effetti: in `scan.py` bonus/malus sul punteggio (+catalizzatore con ≥5 notizie), esclusione dei titoli con sentiment ≤ -0,4; in `trade.py` blocco degli ingressi (vedi sopra). Database `data/news.sqlite` (conservazione 30 giorni).

## Scan (scan.py)
Punteggio = gap (con segno, favorisce i rialzi) + |gap| + rendimento di ieri + volume relativo + ATR% + trend sopra SMA20 + notizie. Esclusi titoli con ATR giornaliero < 1,2%. Watchlist: 5 EU + 3 USA → `data/watchlist_YYYY-MM-DD.json` e `reports/watchlist_YYYY-MM-DD.md`. Per i titoli USA il gap usa il prezzo di pre-market. Se la sessione notturna è già attiva, `trade.py` può scrivere una watchlist di riserva alle 07:30 (gap EU ancora a zero): lo scan ufficiale delle 09:35 la rifà con gap e volume della seduta in corso.

## Limiti noti
- La quotazione live è quella della pagina pubblica L&S (stessi campi del push del sito), non uno stream al tick: ritardo residuo tipico 5-40 secondi. Lo stream Lightstreamer del sito esiste ma l'API HTTP di sessione non è usabile in modo stabile da qui; non lo teniamo aperto in persistenza.
- Il volume L&S è quello della sede (spesso più sottile di Xetra). Per il volume relativo usiamo Yahoo sulla sessione ufficiale e il tape L&S solo per il ritardo e gli orari estesi. Alcuni titoli (es. Telecom Italia) possono non avere print L&S in giornata.
- Fuori dagli orari delle borse ufficiali lo spread L&S può allargarsi. Se L&S non è raggiungibile si torna a Yahoo (~15 min di ritardo sui titoli UE) e allo slippage fisso.
- Gli eseguiti sono simulati sull'ultima barra disponibile + slippage; nessuna simulazione del book.
- Sentiment basato su parole chiave: errori possibili (ironia, titoli ambigui, aziende con nomi comuni).
- Le regole non sono state ancora validate su dati storici (backtest) – vedi raccomandazioni HR.

## Analisi LLM delle notizie (news_llm.json)
Giudizi dell'Analista Notizie (modello linguistico) sulle notizie già raccolte da `news.py`. Non sostituiscono il punteggio a parole chiave usato da `scan.py` e `trade.py`: convivono, così R&D può confrontarli con i risultati. Prima analisi: 12/11/2026. Solo soldi finti.

File (tutti gli orari in ISO 8601 con offset Europe/Rome):
- `data/news_llm.json` — ultimo giudizio, schema stabile `schema_version` 1.0. Si scrive in modo atomico (file temporaneo + `rename`).
- `data/news_llm_history.jsonl` — storico solo in aggiunta (append-only): una riga JSON per ogni giudizio (macro e ciascun titolo) a ogni run, con `run_id` e `generated_at`. Le righe già scritte non si riscrivono mai.
- `data/news_llm_state.json` — cursore per il lavoro incrementale: `last_published` + `last_news_id` (e `last_fetched`). Le run successive devono leggere solo le notizie nuove.

Campi di `news_llm.json`:
- `schema_version`, `generated_at`, `run_id`, `analyst` (`Analista Notizie`).
- `sources_window.from` / `to`: intervallo delle notizie effettivamente lette (campo `published` di `news.sqlite`).
- `news_seen_count`: quante notizie cadono in quella finestra.
- `macro`: `bias` da −1 a +1 (clima atteso sui mercati nella finestra di validità), `confidence` da 0 a 1, `summary` in italiano, `valid_until`, più `keyword_score` e `keyword_news_count_12h` ripresi dalla formula di `news.py` (`macro_signal`, 12 ore) per il confronto.
- `tickers[]`: solo titoli di `universe.csv` con notizie rilevanti (assenza = nessun giudizio, non neutralità). Identificativi allineati al CSV (`ticker`, `isin`, `name`).
  - `impact` da −1 a +1: impatto atteso sul prezzo nella giornata di trading (non un giudizio di medio periodo).
  - `confidence` da 0 a 1; `horizon` uno tra `intraday`, `1-3d`, `settimana`.
  - `rationale`: una riga in italiano; `key_headlines`: titoli usati.
  - `keyword_score` e `keyword_news_count_24h`: punteggio a parole chiave di `news.py` (`news_signal`, 24 ore, emivita ~12 h).
  - `issued_at`, `expires_at`.
- `catalysts[]`: `ticker` (o `MACRO`), `event`, `datetime`, `expected_impact_note`. Date e ore da calendari ufficiali o IR quando disponibili; se la data è stimata lo si dice nella nota.

Scadenze tipiche (ora di Roma):
- `horizon=intraday`: fine sessione paper del giorno — 17:25 per i titoli EU, 21:50 per i titoli USA.
- `horizon=1-3d`: in genere fino alla chiusura paper del terzo giorno di mercato successivo (es. da giovedì fino a lunedì 21:50).
- `horizon=settimana`: chiusura paper del venerdì della settimana in corso o, se emesso a fine settimana, di quella successiva.
- `macro.valid_until`: di solito fino al prossimo dato macro rilevante o alla chiusura della seduta in cui quel dato viene digerito (es. dopo il PPI).
Dopo la scadenza il giudizio non va più usato per le decisioni: serve una nuova analisi.

Campi aggiuntivi dello storico (`data/news_llm_history.jsonl`), dal 12/11/2026 dopo le 15:36 (ora di Roma): ogni **nuova** riga contiene anche:
- `news_published_from`, `news_published_to`: intervallo del campo `published` delle notizie in `data/news.sqlite` usate per quel giudizio.
- `news_ids`: elenco degli `id` di quelle notizie.
- `price_at_issue`, `price_source`, `price_time`: prezzo di riferimento al momento dell'emissione, fonte e orario della quotazione; `null` se non disponibili (es. giudizio macro, o prezzo assente).
- `issued_at` e `expires_at` sono sempre ISO 8601 con fuso orario esplicito (offset Europe/Rome).
Le righe scritte fino alle 15:36 del 12/11/2026 non hanno `news_published_from`, `news_published_to`, `news_ids`, `price_at_issue`, `price_source` e `price_time`, e restano invariate.

Script di supporto (non è uno script di trading, non scrive sul database):
```
python3 news_llm/extract_new_news.py --json            # notizie più recenti dello stato
python3 news_llm/extract_new_news.py --hours 24 --json # finestra mobile, ignora lo stato
```
Ogni notizia estratta include già `id` e `published`, usati per compilare `news_ids` e la finestra `news_published_*` nello storico. Documentazione breve anche in `news_llm/README.md`. Non modificare `news.py`.
