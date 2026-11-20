# Changelog

## 2026-11-20 (~22:55 ora di Roma) - Controlli serali 20/11 (routine R&D): nessun deploy, nessun rollback

- **Scheduler GitHub**: run 22:01 e 22:18 ok, heartbeat 22:25 (ora di Roma). Box fermo come previsto.
- **Reale 20/11 (CH45, primo giorno intero)**: 2 trade, 0 vincenti: CAR -1,60 EUR (stop a breakeven), TTWO -8,42 EUR (stop iniziale); lordo -6,01, commissioni 4, netto **-10,01 EUR**. Equity 933,54 EUR (-6,65% dall'avvio), 18 operazioni totali, 1 vincente, lordo cumulato -30,46. Volume 2 trade contro 1,5/seduta attesi dal backtest CH45: in linea. Il confronto puntuale col backtest CH45 sul 20/11 (cache_w4, 63 sedute) e i filtri anti-stop sono nel lavoro R&D separato in corso (reports/progress_2026-11-20b.md, richiesta Sguattera ~21:00): non duplicato qui.
- **Shadow 20/11**: V0_SHORT 3 operativi +6,93 EUR ante tasse (cumulato 18-20/11: 7 operativi, circa +15 EUR): troppo pochi, resta in ombra. USLEAD_DAX primo segnale live: long, stop, -26,49 EUR (spread KO incluso): resta in ombra. V0_FEE4, V0_WIDE 0 operativi; REBOUND/ORB_DYN/V0_LOOSE tutti respinti dall'analista grafico (solo conteggio). V0_LOOSE resta in ombra.
- **Natasia** (news_eval.py): 230 coppie. LLM segno 58,8%, Spearman +0,143; parole chiave 41,4%, +0,084; giudizi forti (|impact x conf| >= 0,2) ancora solo 3 (-0,42% nel verso). Correlazione leggermente migliore ma nessun vantaggio netto fuori campione dimostrabile: non integro.
- **Raccomandazioni HR 20/11**: identiche al 19/11 (cambiano solo i conteggi). Stop/breakout falsi: oggetto dei test anti-stop in corso. Pullback VWAP: scartato il 20/11 (PB_L_STK lordo negativo). Specialista USA: gli ingressi USA restano da Q4_90 (17:00); nessuna regola USA separata con vantaggio lordo. Ruoli (calendario, qualita' quotazioni, LLM notizie): nessun vantaggio misurabile da validare; non applicate.

## 2026-11-20 (00:55 ora di Roma) - Ritocchi alla config prudente a capitale fisso: deploy soglia analista grafico 45 (CH45)

- **Contesto**: W2 ritirata alle 23:40 (rollback cef6597 su main, verificato). Ordine di Andrea 23:37: "Se e' peggiore allora eliminala e migliorala". Pre-registrazione in `rd-paper-trading/reports/prereg_prudent_tweaks_2026-11-19.md` (scritta prima dei risultati). Script `tweaks_test.py` sopra il metodo a capitale fisso di Lerabuns (`w2var_test.py`, W2V_FIXED=1: sizing su 1.000 EUR fissi, limite giornaliero -3% disattivato; 1+1 EUR, slippage 0,05%, tassa 26% con zainetto, WF 5 blocchi + holdout; cache_w3, 62 sedute 26/08-19/11, 1.233 titoli). 14 prove (2 basi + 12 ritocchi): rischio data-snooping alto.
- **Risultati** (P0 = produzione prima di questo cambio = Q4_90; B0 = senza Q4_90):

  | Config | Trade | /seduta | Vincite | Netto EUR | OOS EUR | Holdout EUR | Batte P0 su tutti e 3 |
  |---|---|---|---|---|---|---|---|
  | B0 | 371 | 6,0 | 27,5% | -699,58 | -594,62 | -361,74 | |
  | **P0 (Q4_90)** | 210 | 3,4 | 25,2% | **-330,56** | **-253,68** | **-180,23** | base |
  | FEE8 (soglia 8 EUR) | 70 | 1,1 | 30,0% | -160,78 | -151,80 | -123,76 | si |
  | FEE10 (10 EUR) | 23 | 0,4 | 30,4% | -51,04 | -54,94 | -48,78 | si, ma < 30 trade |
  | MP1 (1 posizione) | 114 | 1,8 | 27,2% | -150,27 | -108,47 | -55,32 | si |
  | MP2 (2 posizioni) | 178 | 2,9 | 23,0% | -304,74 | -231,41 | -143,26 | si |
  | SL40 (slot 40%) | 500 | 8,1 | 24,6% | -1.013,62 | -831,84 | -430,08 | no |
  | SL50 (slot 50%) | 785 | 12,7 | 21,8% | -1.987,41 | -1.602,75 | -839,46 | no |
  | NOEU (solo USA) | 153 | 2,5 | 26,8% | -228,00 | -171,26 | -131,39 | si |
  | NOUS (solo EU) | 57 | 0,9 | 21,1% | -95,46 | -73,71 | -49,52 | si |
  | FLUS2030 (flatten USA 20:30) | 198 | 3,2 | 26,8% | -295,72 | -226,34 | -155,24 | si (poco) |
  | FLEU1500 (flatten EU 15:00) | 206 | 3,3 | 26,2% | -311,74 | -238,70 | -183,49 | no (holdout) |
  | CH35 (analista >= 35) | 157 | 2,5 | 24,2% | -267,31 | -231,69 | -174,38 | si (poco) |
  | **CH45 (analista >= 45)** | **93** | **1,5** | **30,1%** | **-76,09** | **-79,04** | **-74,64** | **si** |

- **Scelta**: CH45. E' la sola con netto migliore tra quelle che battono P0 su netto, OOS e holdout e hanno almeno 30 trade (FEE10 ne ha 23). Famiglia coerente: soglia 25 -> 35 -> 45 migliora netto (-331, -267, -76) e OOS in modo monotono; lordo +112,9 EUR (contro +91,8 di P0) con meno trade. Onesta': **resta in perdita** (-76 EUR in 62 sedute, ~-1,2 EUR a seduta contro -5,3 di P0), meno operativa (1,5 trade a seduta), e quasi tutto il guadagno viene dal meno commissioni; il lordo non cambia molto. Nessuna combinazione e' stata provata (evita altro snooping). Tutti i ritocchi che battono P0 lo fanno soprattutto riducendo le commissioni.
- **Cosa cambia**: `CFG["chart_approve_buy"]=45` (nuovo, in `common.py`); `chart_analysis.py` lo usa per approvare gli ingressi long (prima costante 25). Uscite (EXIT_SELL -30), stop, target, universo, Q4_90, fee gate, 3 posizioni, slot 30% invariati. Gli shadow che usano l'analista (se presenti) ricevono la stessa soglia. **ROLLBACK**: `chart_approve_buy=25` in `common.py`, commit e push.
- Test: nuovo `test_chart_threshold.py`; `test_us_entry_delay.py` reso indipendente dalla data di oggi (falliva dopo mezzanotte perche' `session_times()` usava la data reale); tutti gli altri test ok.

## 2026-11-20 (~00:45 ora di Roma) - R&D: setup alternativi all'ORB (7 varianti pre-registrate); NESSUN deploy, USLEAD_DAX in shadow

- **Perche'**: richiesta di Sguattera (19/11 23:40): l'ORB non ha lordo positivo in nessuna versione; servono setup diversi e "pochi trade ma grandi" per diluire le commissioni fisse. Ritocchi della config prudente lasciati a Sguattera; universo e Q4_90 invariati.
- **Metodo** (pre-registrazione `rd-paper-trading/reports/prereg_alt_2026-11-20.md` scritta prima dei risultati; script `rd-paper-trading/alt_test.py`): cache_w3, 62 sedute 26/08-19/11, 1.233 titoli + ^GDAXI/^NDX/^GSPC; capitale FISSO 1.000 EUR; 1 posizione alla volta, max 2 ingressi/giorno; azioni long a pronti fino a 1.000 EUR (slippage 0,05%/lato), short su azioni solo KO x2 (spread 0,50%), indici solo KO x5 (spread 0,12%, mezzo spread min 1 cent su certificato da 10 EUR, knock-out modellato); rischio 20 EUR allo stop; filtro costi 3x; 1+1 EUR; tassa 26% con zainetto; ingressi EU 10:00-16:30, USA 17:00-21:00, chiusura 17:25/21:45; holdout ultimo 1/3, WF 5 blocchi. Riferimento P0f (config prudente a capitale fisso, stesso dataset): 210 trade, lordo +91,81, netto -330,56, OOS -253,68 (0/5), holdout -180,23.
- **Risultati** (netto in EUR dopo commissioni e tasse):

  | Variante | Trade (/seduta) | Lordo | Netto | Win | Exp/trade | OOS (blocchi+) | Holdout |
  |---|---|---|---|---|---|---|---|
  | P0f prudente (rif.) | 210 (3,4) | +91,81 | -330,56 | 25,2% | -1,57 | -253,68 (0/5) | -180,23 |
  | PB_L_STK pullback EMA20 nel trend, long | 124 (2,0) | -126,27 | -383,34 | 34,7% | -3,09 | -253,77 (0/5) | -195,00 |
  | PB_LS_STK idem long+short KO x2 | 124 (2,0) | -270,68 | -527,75 | 35,5% | -4,26 | -387,35 (0/5) | -180,03 |
  | MR_L_STK eccesso sotto VWAP (z<=-3, RSI<=25), long | 124 (2,0) | -102,46 | -350,46 | 29,0% | -2,83 | -248,95 (0/5) | -172,16 |
  | MR_LS_STK idem long+short KO x2 | 124 (2,0) | -421,23 | -669,23 | 27,4% | -5,40 | -471,83 (0/5) | -355,47 |
  | PB_IDX pullback su DAX/Nasdaq 100, KO x5 | 51 (0,8) | -90,13 | -192,13 | 41,2% | -3,77 | -66,76 (1/5) | -51,07 |
  | MR_IDX eccesso su DAX/Nasdaq 100, KO x5 | 37 (0,6) | -361,40 | -435,40 | 21,6% | -11,77 | -330,44 (1/5) | -233,74 |
  | USLEAD_DAX S&P 15:30-15:55 -> DAX 16:00, KO x5 | 13 (0,2) | +97,78 | +53,11 | 69,2% | +4,09 | +69,78 (3/5) | +57,94 |

  Lettura: sulle azioni, pullback ed eccessi hanno lordo NEGATIVO anche con posizioni da 1.000 EUR (costi fissi 0,2%): diluire le commissioni non basta se il segnale non ha vantaggio; gli short via KO x2 pagano lo spread 0,5% e peggiorano tutto. Indici: pullback quasi in pari prima dei costi ma negativo, mean reversion pessima. Solo USLEAD_DAX ha lordo positivo e batte P0f su netto, OOS e holdout, ma con 13 trade (soglia pre-registrata 60) e 1 solo target che vale 38 EUR di lordo. Vicini (informativi): soglia 0,2% 25 trade netto +3,26; 0,4% 7 trade +42,95; target 1,5R +56,43; 2,5R +40,36. Controllo su barre 1h 2024-2026 (proxy: S&P prima ora -> DAX 17:00-17:30, 217 casi): -1,6 bp a trade, negativo nel 2024 e nel 2025 -> l'effetto non e' dimostrato su storia lunga.
- **Decisione** (regole pre-registrate): nessuna variante soddisfa il criterio di deploy (netto, OOS e holdout > 0 e > P0f, lordo > 0, >= 60 trade, >= 3/5 blocchi, griglia). **Nessun deploy.** PB_*, MR_* scartate. **USLEAD_DAX in shadow** (lordo > 0 e batte P0f ovunque, volume insufficiente): `shadow.py` registra fra le 16:00 e le 16:40 un segnale al giorno (nessun ordine, nessuna scrittura sul ledger) e l'esito alle 21:56 (spread KO 2 EUR incluso, niente breakeven, chiusura 17:25). Test: replay 16-19/11 con data simulata su file temporanei (16/11 short, esito +7,10 EUR ante tasse vs +9,58 del backtest: lo shadow applica in piu' lo slippage 0,05% sul nozionale); `shadow.py --dry-run` ok; backup `/tmp/shadow.py.bak-20261120`.
- File: `rd-paper-trading/alt_test.py`, `reports/alt_results.jsonl`, `reports/alt.out`, `reports/alt_<VAR>_trades.csv`, `reports/progress_2026-11-20.md`. Produzione (`trade.py`, config), scheduler e ledger non toccati.

## 2026-11-19 (23:40 ora di Roma) - ROLLBACK di W2 (ordine di Andrea 23:37: "Se e' peggiore allora eliminala")

- **Perche'**: il controllo a capitale fisso di Lerabuns (`w2var_test.py`, commit 7397911, 1.000 EUR senza tetto da capitale che scende) da per W2 circa 9,6 trade a seduta, 12% di vincite, **-1.370 EUR in 62 sedute** (~-22 EUR a seduta). Il mio -337 EUR di mattina era un artefatto: l'equity scendeva a ~663 EUR e il backtest smetteva di aprire posizioni (min 200 EUR a posizione).
- **Cosa**: `min_stop_pct` 0.0105 -> **0.004**; `ema_filter`, `chart_veto`, `chart_exit` -> **True**. Restano Q4_90 (`us_entry_delay_min=90`), universo 1.233 (EU+US), fee gate 3x, rischio 2%, slot 30%, 3 posizioni, solo long, leva 1x. I flag nuovi in `trade.py` restano (default acceso). Test tutti ok.
- Effetto sugli shadow: tornano a stop minimo 0,4% come prima.

## 2026-11-19 (~23:40 ora di Roma) - R&D serale 19/11: varianti di W2 (uscite, ranking, orari EU); NESSUN deploy

- **W2 reale 19/11** (report 21:55 e ledger, sola lettura): attiva dalle ~14:00. 6 trade chiusi (8TRA, APAM, MONC, ERF, VVV, GME), **0 vincenti**, lordo -8,33 EUR, commissioni 12 EUR, netto **-20,33 EUR**; equity 943,56 EUR (-5,64% dall'avvio). Non 7 entrate/5 perdite/-18 come stimato a meta' giornata.
- **Backtest W2 sullo stesso giorno** (cache_w3 = cache_w2 + barre del 19/11, capitale fisso): 15 trade, lordo -17,35, netto -47,35 EUR; dopo le 14:00 12 trade, in comune col reale solo MONC.MI ed ERF.PA. Differenza strutturale: il backtest chiude gli EU alle 17:25, la produzione li tiene fino alle 21:50 (Traton ed Eurofins chiusi alle 21:50).
- **Scoperta metodologica**: nel backtest a capitale composto (quello usato per W2 alle 13:50) tutte le config finiscono a circa -335/-338 EUR perche' l'equity scende a ~663 EUR, lo slot del 30% va sotto i 200 EUR minimi e il bot smette di aprire (W2 a 62 sedute identico a 61: 0 trade il 19/11). Quindi netto/holdout composti NON sono confrontabili tra varianti. Nuova modalita' `W2V_FIXED=1` in `rd-paper-trading/w2var_test.py`: sizing sempre su 1.000 EUR, cassa non vincolante, limite giornaliero -3% disattivato (con equity bassa bloccava tutto: prima prova invalida, salvata come `w2var_fixed_halt_bug.*`). In questa modalita' **W2 = 593 trade in 62 sedute (9,6 a seduta), win rate 12,0%, lordo -183,79, netto -1.369,79 EUR (circa -22 EUR a seduta), OOS -969,95, holdout -513,85, 0/5 blocchi WF positivi**.
- **Varianti** (pre-registrate in `rd-paper-trading/reports/prereg_w2_variants_2026-11-19.md` prima dei risultati; 14 varianti + W2, rischio data-snooping alto; universo e Q4_90 invariati, filtro commissioni sempre su 2R; 1+1 EUR, slippage, tassa 26% con zainetto). Capitale fisso, 62 sedute 26/08-19/11:

  | Variante | Trade/seduta | Win rate | Netto EUR | Lordo/trade | OOS EUR | Holdout EUR | WF blocchi >0 |
  |---|---|---|---|---|---|---|---|
  | **W2** | 9,6 | 12,0% | -1.369,79 | -0,31 | -969,95 | -513,85 | 0/5 |
  | RK_MOM (ranking momentum/ATR) | 9,8 | 13,8% | -1.403,81 | -0,31 | -918,81 | -467,66 | 0/5 (meglio di W2 in 2/5) |
  | EPAUSE (niente ingressi 11:30-14:30) | 9,4 | 11,0% | -1.382,47 | -0,38 | -973,61 | -518,87 | 0/5 |
  | TP150 | 9,7 | 14,2% | -1.400,74 | -0,32 | -994,54 | -538,38 | 0/5 |
  | RK_BRK (forza breakout/ATR) | 9,7 | 12,7% | -1.507,66 | -0,51 | -1.007,91 | -562,08 | 0/5 |
  | TP125 | 10,0 | 16,9% | -1.457,30 | -0,35 | -1.023,26 | -536,54 | 0/5 |
  | E1000 (EU dalle 10:00) | 9,8 | 11,2% | -1.504,34 | -0,48 | -1.059,72 | -569,32 | 0/5 |
  | TP100 | 10,4 | 24,1% | -1.553,72 | -0,41 | -1.090,59 | -563,75 | 0/5 |
  | RK_RVOL | 10,9 | 14,8% | -1.672,41 | -0,48 | -1.190,21 | -657,95 | 0/5 |
  | TM90 / TM60 / TM30 (uscita a tempo) | 25,5 / 36,6 / 68,8 | 7,2 / 4,4 / 2,5% | -3.752 / -5.486 / -10.066 | -0,37 / -0,42 / -0,36 | | | 0/5 |
  | TR20 / TR15 / TR10 (trailing k*ATR) | 36,0 / 55,5 / 91,6 | 5,7 / 4,0 / 2,0% | -5.275 / -7.976 / -13.177 | -0,37 / -0,32 / -0,32 | | | 0/5 |

  Lettura: nessuna variante ha lordo positivo. TP piu' vicini alzano il win rate (fino al 24%) ma non l'expectancy. Trailing e uscita a tempo liberano gli slot e moltiplicano i trade (e le commissioni): rovinosi. L'unica che batte W2 sia in OOS (+51 EUR) sia in holdout (+46 EUR) e' RK_MOM, ma perde nel netto totale, vince solo 2 blocchi WF su 5 e le altre due regole di ranking (stessa famiglia) peggiorano: non regge, **nessun deploy**. 09:15/09:30 non testabili/uguali alla base (opening range EU 09:00-09:30).
- **Shadow 19/11**: V0_SHORT 3 operativi, +8,25 EUR ante tasse (18/11: 1 operativo, -0,15): 4 operativi in 2 sedute, troppo pochi, resta in ombra. V0_FEE4 e V0_WIDE 0 operativi; REBOUND SAN.PA -8,40. V0_LOOSE resta in ombra.
- **Natasia** (`news_eval.py`): 190 coppie. LLM segno 55,9%, Spearman +0,104; parole chiave 44,8%, +0,098; giudizi forti solo 3 (-0,42% nel verso). Nessun vantaggio netto dimostrato: non integro.
- **Raccomandazioni HR 19/11**: identiche al 18/11 (stop 1,5 ATR, specialista USA, pullback VWAP, ruoli): gia' valutate e scartate il 16-18/11, nessun elemento nuovo.
- **Scheduler GitHub**: regolare (run 22:26 ok, heartbeat 22:25). Produzione non toccata.

## 2026-11-19 (13:50 ora di Roma) - Ordine di Andrea: comprare molto di piu'. Config "W2" (stop minimo 1,05%, senza analista grafico e senza filtro EMA)

- **Ordine** (12:38, verbatim): "Ancora niente? Allora trova il perche' hai comprato poco e sei in perdita e inizia a comprare il piu' possibile tutto quello che ti sembra che faccia guadagnare".
- **Perche' comprava poco (log 19/11 07:30-12:25, 30 passaggi, 153 titoli arrivati almeno a una valutazione completa)**: il collo di bottiglia e' il **filtro commissioni** (guadagno 2R atteso >= 6 EUR). Con slot 30% (~289 EUR) e stop minimo 0,4%, il guadagno atteso e' 2,31 EUR (110 volte lo stesso valore): **84 titoli su 153 hanno passato breakout, VWAP, momentum, estensione ed EMA e sono stati bloccati solo dalle commissioni**. Altri: momentum 15m negativo 61 titoli, "troppo esteso" 36, EMA disallineata 6, analista grafico che rifiuta 6 (dopo aver passato il filtro commissioni), sotto VWAP 4. Prima delle 16:00 gli USA sono fuori finestra, dopo Q4_90 dalle 17:00.
- **Perche' perdeva (17-18/11)**: 10 trade tutti USA, lordo -16,11 EUR e 20 EUR di commissioni (124%); 8 ingressi su 10 tra 16:00 e 16:59 (-34,92 EUR), 5 su 6 il 18/11 usciti in stop; il backtest B0 mostra lordo +66 EUR su 408 EUR di commissioni in 59 sedute.
- **Cosa cambia (CFG in common.py)**: `min_stop_pct` 0.004 -> **0.0105**; `ema_filter` (nuovo) **False**; `chart_veto` (nuovo) **False**; `chart_exit` (nuovo) **False**; `mom_filter` (nuovo) True. Invariati: universo 1.233 (EU+US), Q4_90 (US da 17:00), filtro commissioni 3x, rischio 2%, slot 30%, max 3 posizioni, solo long, leva 1x, stop/target 2R/breakeven/flatten 21:50. Nota: i flag in `trade.py` (plan_entry e manage_open); `shadow.py` condivide `min_stop_pct`, quindi anche gli shadow V0_* usano ora stop minimo 1,05%.
- **ROLLBACK**: in `common.py` mettere `min_stop_pct=0.004, ema_filter=True, chart_veto=True, chart_exit=True`, commit e push.
- **Backtest** (R&D `rd-paper-trading/loose_test.py`, cache_w2, 61 sedute 26/08-18/11, 1.233 titoli, 1+1 EUR, slippage, tassa 26% con zainetto; tutte le varianti sopra Q4_90 = produzione prima di questo cambio):

  | Config | Trade | Trade/seduta | di cui EU | Netto EUR | Lordo EUR | OOS EUR | Holdout EUR | Note |
  |---|---|---|---|---|---|---|---|---|
  | B0 (prima di Q4_90, 17/11) | ~216 | 3,5 | ~20 | circa -384 | | | | -342,55 sulle 59 sedute + -41,69 del 17-18/11 |
  | P0 = Q4_90 (produzione stamattina) | 146 | 2,4 | 37 | -261,85 | +33,85 | -184,06 | -125,24 | |
  | **W2 (scelta)**: P0 + stop 1,05% + no analista + no EMA | **221** | **3,6** | **74** | **-337,07** | +104,93 | -182,81 | -128,04 | vincite 23,5% |
  | L1: P0 senza analista | 217 | 3,6 | 57 | -332,21 | +105,53 | -223,46 | -136,79 | |
  | W10: P0 + stop 1,05% senza analista, con EMA | 177 | 2,9 | 58 | -341,48 | +12,52 | -189,84 | -86,49 | |
  | W5: P0 + stop 1,05% senza Q4_90 | 199 | 3,3 | 31 | -333,88 | | | | |
  | W1: P0 + stop 1,05% | 147 | 2,4 | 47 | -293,50 | +0,50 | -174,15 | -119,32 | |
  | L2: P0 senza EMA | 144 | 2,4 | 37 | -275,51 | +14,73 | | | |
  | L5/L3/L4/L7/L8 (soglia commissioni 1,5x/1x, 6 posizioni) | 134-158 | | | circa -334 e lo zainetto si ferma | | | | in 13-15 sedute l'equity scende a ~667 EUR (sotto 200 EUR a posizione) e il bot non apre piu' |
  | L6/L9/L10/L11/W3 (leva fino a 5x) | 245-343 | 4-5,6 | | da -751 a -831 | | | | rovinose: vincite 3-13% |

  Lettura onesta: **nessuna config che compra di piu' guadagna**. W2 compra +50% (EU piu' che doppi: 74 contro 37) e perde circa 75 EUR piu' di Q4_90 in 61 sedute (~1,2 EUR a seduta), ma meno di B0 e quasi come L1 con piu' operazioni EU. Abbassare la soglia commissioni o usare la leva moltiplica le perdite (stop da 0,4% presi dal rumore: vincite 3-13%). Scelta secondo l'ordine di Andrea: massima attivita' senza ricadere nelle varianti che azzerano il conto.
- Test: `test_loose_flags.py` (nuovo, flag EMA/momentum) e tutti gli altri test ok.

## 2026-11-19 (mattina, ora di Roma) - Prova di 1 giorno: ingressi USA dalle 17:00 (Q4_90)

- Prova di 1 giorno decisa da Sguattera su regole permanenti di Andrea (applicare subito cambi che testano meglio): ingressi USA dalle 17:00 (Q4_90). Forward 17-18/11: -6,65 vs -41,69 EUR; 59 sedute meglio; holdout misto. Rollback: `CFG["us_entry_delay_min"]=None` in `common.py` (torna a 16:00).
- Come: nuovo flag `us_entry_delay_min=90` (minuti dopo l'apertura cash USA, 15:30 + 90 = 17:00 Roma) controllato in `trade.py: plan_entry` solo per `region == "US"`. Titoli EU, universo (1.233), fee gate, stop/target e uscite delle posizioni già aperte invariati. Test: `test_us_entry_delay.py` (nuovo) e tutti gli altri test ok.

## 2026-11-18 (~22:50 ora di Roma) - R&D serale 18/11: filtro dibattito LLM spento (solo shadow); nessuna regola di trading cambiata

- **Cosa**: nuovo interruttore `CFG["debate_shadow"]=False` in `common.py`. Con l'interruttore spento `shadow.spawn_debate()` non lancia più il worker `debate.py` (nessuna chiamata a Pollinations) e `debate.eod_lines()` scrive nel report delle 21:56 solo una riga "spento" invece di simulare i segnali. `test_debate.py` riaccende l'interruttore solo dentro il test (16/16 controlli ok); ok anche test_fee4_shadow, test_short e test_wide_scan. Backup della versione precedente in `backups/2026-11-18_debate_off/` (fuori dal repo). Produzione v0 invariata.
- **Perché**: regola pre-registrata il 16-17/11. Se il giudice scarta di nuovo tutto, la prova non è informativa e si spegne. Il giudice ha scartato **14 segnali su 14** in tre sedute (16, 17 e 18/11). Il cumulativo senza filtro è di 14 segnali, netto ante tasse **-32,27 €**, 0 vincenti il 18/11. Un filtro che scarta sempre non si distingue da questo giudice, quindi il confronto ENTRA contro nessun filtro non si può fare (0 ENTRA). Spegnerlo libera anche fino a ~25 minuti per ogni passaggio del worker sui runner GitHub. Lo storico resta in `data/debate_*.jsonl` (solo in aggiunta, non toccato).
- **Nota**: durante la verifica ho lanciato per errore `shadow.py` sul box alle 22:45 (34 valutazioni, 0 segnali, fuori orario). Non ha toccato il ledger né lo stato GitHub, perché lo stato vivo sta sul branch `state`.
- **Reale 18/11** (report 21:55, revisione HR): 6 trade chiusi, tutti USA ORB long, 5 su stop, netto **-20,34 €** (lordo -8,34, commissioni 12 € = 144%). Cumulato dall'avvio: 10 trade, -36,11 €, equity 963,89 €. 8 ingressi su 10 tra 16:00 e 16:59 (-34,92 €).
- **Controllo in avanti 17-18/11** (pre-registrato in `rd-paper-trading/reports/prereg_forward_2026-11-18.md` prima dei risultati; cache nuova `cache_w2` con le barre del 18/11, `cache_w` non toccata; solo B0, Q4_90 e Q5):
  - **B0 (produzione)**: 12 trade, netto **-41,69 €** (lordo -17,69). Il reale è 10 trade, -36,11 €, quindi il backtest è leggermente pessimista ma coerente. 6 titoli su 10 coincidono (BRKR, TSN, LCID, CELH, CVLT, WING). Gli altri cambiano perché con 1.233 titoli molti breakout scattano nello stesso passaggio e i 3 posti disponibili vanno a chi viene prima: la scelta dei titoli è quasi casuale e aumenta la varianza.
  - **Q4_90 (USA da 17:00)**: 7 trade, **-6,65 €** (lordo +7,35). **Q5 (soglia 8 €)**: 8 trade, -29,99 €. Q4_90 resta un candidato con evidenza mista: netto e OOS migliori di B0 sulle 59 sedute e nelle 2 sedute in avanti, ma holdout peggiore di 55 €. Due sedute non bastano e non cambiano la bocciatura pre-registrata del 17/11: **nessun deploy**. Lo rivaluto quando ci saranno almeno 10 sedute in avanti.
  - Nota tecnica: `filt_test.py` usa il prefisso fisso `f17_` per i CSV dei trade, quindi questo controllo ha sovrascritto `f17_B0/Q4_90/Q5_trades.csv` della notte scorsa. I risultati del 17/11 restano in `f17_results.jsonl` e `f17b_results.jsonl`.
- **Verdetti shadow 18/11** (1 giorno non basta per promuovere): **V0_SHORT** 6 segnali, 1 operativo (NVDA, -0,15 €), 5 bloccati dalle commissioni (diagnostico -16,63 €). **V0_FEE4** 5 segnali, 0 operativi (+0,00 €). **V0_WIDE** 0 segnali. **Debate** 5 su 5 scartati, quindi spento (vedi sopra). REBOUND e ORB_DYN: nessun segnale operativo, diagnostici negativi.
- **Natasia** (`news_eval.py`): **151 coppie**. LLM: segno giusto 55,4%, Spearman +0,173. Parole chiave: 48,9%, +0,130. Sui giudizi forti (|impact×conf| ≥ 0,2) ci sono solo 3 casi, con rendimento medio nel verso del giudizio -0,42%. Il vantaggio di correlazione non diventa un netto fuori campione: non integro, la misura in ombra continua.
- **Raccomandazioni HR 18/11**: "20-30 trade" accolta (10 trade reali). Stop 1,5 ATR: la griglia 1,25/1,75 ATR non migliora (16/11). Pullback VWAP: già bocciato (12-15/11). Soglia 25 dell'analista grafico "troppo severa": scartata, perché senza analista il backtest peggiora (no_chart -68,30 € contro -18,82 €, 13/11) e il 18/11 anche i segnali respinti (DBK, IFX, VOW3) sono finiti in stop. Specialista USA, calendario eventi e monitor quotazioni: rinviati per gli stessi motivi del 13/11. Analista notizie LLM: già attivo (Natasia, in ombra).
- **Scheduler GitHub**: regolare (run 22:22 ok, heartbeat 22:25). La sessione di domattina caricherà il nuovo main all'avvio (pull ff-only).

## 2026-11-18 (~03:00 ora di Roma) - R&D serale 17/11: filtri qualità USA, RVOL, orario/retest USA; NESSUN deploy (completo)

- **Produzione invariata** (commit 8a4a779: 1.233 titoli, EMA9>EMA21, filtro commissioni 6 €, solo long). Nessun codice cambiato; il fee gate di Sguattera non risulta ancora su main. Scheduler GitHub regolare (ultimo run 17/11 23:29 ok, heartbeat 22:24 = chiusura sessione).
- **Verifica 17/11 dal ledger (sola lettura) e da trade_log**: BRKR -6,98, TSN -0,48, MOH -8,20, LCID -0,12 = **-15,77 €** (lordo -7,77, commissioni 8 € = 103%). Tre ingressi su quattro tra le 16:10 e le 16:41, LCID alle 20:00; tutti usciti per stop (LCID in trailing, lordo +1,88). Dal backtest B0: i titoli USA perdono quasi tutto nella prima ora (16:00-16:29: 107 trade, -190 €; 16:30-16:59: 40 trade, -94 €; da 17:00: 22 trade, circa -6 €).
- **Test** (script R&D fuori repo `filt_test.py`, copia isolata `rd-paper-trading`, cache Yahoo 5m `cache_w`, 59 sedute 26/08-16/11, 1.233 titoli, stesse regole e costi della produzione, 1+1 €, slippage del backtest, tassa 26% con zainetto). Pre-registrazione `reports/prereg_filters_2026-11-17.md` (+ addendum 00:35 per RT) scritta prima dei risultati. Riferimento B0 = produzione: **-342,55 €, 204 trade, OOS -210,60, holdout -65,81, WF 0/4, lordo/trade +0,33**.
  Criteri di promozione (tutti): netto, OOS e holdout migliori di B0; meglio di B0 in almeno 3 blocchi su 4; >= 30 trade; lordo/trade migliore; vicini della griglia che battono B0. **Varianti provate: 36 eseguite sulle 40 pre-registrate (28 della prima griglia + 4 RT + Q4_45/Q4_90/Q6_60/Q6_180; non eseguiti i 4 vicini di Q3, bocciata per lordo negativo), rischio data-snooping alto. Nessuna passa.**

  | Variante | Trade | Netto € | OOS € | Holdout € | WF blocchi > B0 | Esito |
  |---|---|---|---|---|---|---|
  | B0 produzione | 204 | -342,55 | -210,60 | -65,81 | - | riferimento |
  | Q1 prezzo >= 10 $ (USA) | 206 | -336,07 | -209,84 | -72,30 | 1/4 | no (holdout; vicini 5/20 $: 205/-337,89, 207/-333,76, holdout -68,62/-77,43) |
  | Q2 liquidità >= 100 M$ | 198 | -334,81 | -205,01 | -66,64 | 2/4 | no (holdout, WF; vicini 50/200 M$ -337,89 / -342,67) |
  | Q3 ATR% 1,5-5% | 146 | -341,97 | -176,26 | -81,47 | 2/4 | no (holdout, lordo/trade -0,33) |
  | QC Q1+Q2+Q3 | 155 | -337,89 | -211,71 | -105,52 | 3/4 | no (holdout, lordo -0,17) |
  | Q4 USA da 16:30 | 172 | -336,75 | -189,47 | -65,93 | 3/4 | no (holdout -0,12 €, lordo/trade 0,04) |
  | Q4_45 USA da 16:15 | 210 | -334,99 | -223,31 | -94,77 | 2/4 | no |
  | Q4_90 USA da 17:00 | 144 | -261,36 | -183,57 | -120,81 | 2/4 | no: netto migliore (-81 €) ma holdout -55 € peggio, lordo/trade 0,21 |
  | Q5 soglia commissioni 8 € | 183 | -152,00 | -161,89 | -100,67 | 3/4 | **no**: dimezza il netto ma holdout -100,67 contro -65,81 (lordo/trade 1,24); tenuto in shadow come V0_FEE4 |
  | Q6 niente USA dopo le 20:00 | 200 | -340,39 | -202,82 | -65,81 | 2/4 | no (effetto trascurabile) |
  | RVOL cumulato x1,25 / 1,5 / 1,75 / 2 / 2,5 / 3 / 4, tutti | 191 / 164 / 146 / 121 / 86 / 64 / 43 | -325,54 / -318,59 / -300,09 / -255,68 / -204,90 / -168,85 / -112,57 | -260,66 ... -92,51 | -161,85 ... -69,87 | 2-3/4 | no: meno trade e meno perdita ma holdout sempre peggiore, lordo/trade negativo da x1,75 |
  | RVOL cumulato solo USA x1,25 / 1,5 / 1,75 / 2 / 2,5 / 3 / 4 | 180 / 172 / 155 / 131 / 105 / 93 / 75 | -339,94 / -330,11 / -301,97 / -259,64 / -235,74 / -207,34 / -159,43 | -258,33 ... -115,72 | -158,01 ... -85,14 | 2-3/4 | no |
  | RVOL barra x2, tutti | 175 | -307,73 | -243,29 | -144,14 | 2/4 | no |
  | QC + RVOL 2 solo USA | 100 | -253,48 | -178,58 | -86,72 | 3/4 | no (lordo -0,54) |
  | RT_US retest ORH (0,10 ATR) | 168 | -337,93 | -200,98 | -131,51 | 2/4 | no |
  | RT_US_05 / RT_US_20 | 176 / 171 | -310,94 / -335,74 | -195,91 / -191,35 | -122,97 / -110,81 | 2/4 | no |
  | RT_ALL retest su tutti | 161 | -320,13 | -180,58 | -107,41 | 3/4 | no (holdout, lordo/trade 0,01) |
  | Q6_60 / Q6_180 (niente USA nelle ultime 1 / 3 ore) | 204 / 199 | -342,55 / -342,54 | -210,60 / -208,09 | -65,81 / -65,81 | 0/4, 1/4 | no (nessun effetto) |

  Lettura: i filtri riducono il numero di trade (e quindi le commissioni) ma non migliorano la qualità, e l'holdout (ultimo terzo) peggiora quasi sempre. Il lordo medio per trade resta vicino a zero: le commissioni (408 € in 59 sedute) valgono più del lordo (+66 €). L'unico segno robusto è che la perdita nasce dai breakout USA dei primi 60 minuti dopo l'OR, ma ritardare o filtrare gli ingressi non l'ha corretta. Nessuna variante ha passato i criteri, quindi nessuna modifica in produzione. Tornare ai 55 titoli (-5,74 €) resta possibile solo per decisione di Andrea (`wide_file=False`).
- **Verdetti di 1 giorno (shadow 17/11, non bastano per promuovere)**:
  - V0_SHORT: 8 segnali, 0 operativi, diagnostici bloccati dalle commissioni -12,51 € (NVDA unico target, +0,88 €); non informativo.
  - V0_FEE4: 5 segnali, 0 operativi (grafico o filtro 8 €), +0,00 €; in prova, non informativo.
  - Dibattito LLM: l'API Pollinations risponde dai runner (3 chiamate per segnale, ritardo 2-3 min), nessun NON_DECISO, ma il giudice ha scartato 9 segnali su 9 in due giorni (5 oggi: -10,32 €, tutti perdenti). Non informativo: nessun segnale ENTRA da confrontare, e le motivazioni ripetono i filtri già esistenti (tetto commissioni, analista grafico). Raccomando di spegnerlo se anche domani scarta tutto; non l'ho spento oggi (nessun effetto sugli ordini).
  - V0_WIDE: 0 segnali; non informativo.
- **Natasia**: `news_eval.py` 105 coppie (titolo, seduta successiva), soglia 100 superata. Hit rate del segno 54,3% (LLM) contro 46,7% (parole chiave); Spearman LLM +0,123 contro parole chiave +0,092; con confidence >= 0,6 solo 15 coppie. Vantaggio piccolo, non significativo (p circa 0,2) e non valutato fuori campione al netto dei costi: **nessuna integrazione**, la misura in ombra continua.
- **Backup/ledger**: nessun deploy, quindi nessun backup; `data/ledger.sqlite` letto solo in modalità sola lettura.

## 2026-11-17 (~00:30 ora di Roma) - Scansione di tutto l'universo TR liquido: 1.233 titoli a ogni passaggio (ordine di Andrea)

- **Cosa**: per ordine esplicito di Andrea ("controlla tutti quelli in Trade Republic"), la produzione controlla a ogni passaggio (ogni 10 minuti) **1.233 titoli**: i 71 di `universe.csv` più il nuovo `universe_wide.csv` (1.162 titoli: 246 europei in EUR, 916 USA in USD). `CFG["wide_regions"]=("EU","US")`, `wide_file=True`. Le altre regole di rischio restano: rischio 2%, max 3 posizioni, tetto 30%, filtro commissioni 6 €, filtro EMA9>EMA21, solo long, limite giornaliero −3%.
- **Universo**: costituenti pubblici (Wikipedia) di DAX, MDAX, SDAX, FTSE MIB, FTSE Italia Mid Cap, CAC 40, AEX, AMX, IBEX 35, Euro Stoxx 50, BEL 20, PSI, ATX, OMX Helsinki 25, ISEQ 20, S&P 500, S&P 400, più circa 45 grandi titoli USA/ADR (ARM, TSM, PDD, MELI, SHOP, ecc.). Su 1.394 candidati restano quelli con prezzo ≥ 2, scambi mediani a 20 giorni ≥ 3 M€ (EU) o ≥ 20 M$ (USA) e barre Yahoo 5m disponibili. Esclusi i titoli in CHF, GBP, SEK e DKK (il ledger converte solo EUR e USD), quindi niente SMI o FTSE 100 per ora.
- **Come gira**: Yahoo 5m (2 sedute) per tutti i titoli in blocchi da 200 (`yf_intraday_bars_chunked`, ~15 s per tutti). Poi uno screen economico (`breakout_candidates`) tiene i titoli con chiusura ≥ massimo dell'opening range − 0,5 ATR. Solo questi, le posizioni aperte e la watchlist delle 09:35 vengono valutati per intero (~100-140 titoli; gli altri non possono dare un segnale v0 sulle stesse barre). Le quotazioni live L&S restano al massimo 20, nell'ordine posizioni, candidati, watchlist. Prova reale dal box (16/11 sera): 28 s per scaricare e filtrare 1.233 titoli; 132 vicini alla rottura, 138 valutati per intero, 20 quotazioni live. Copertura: tutti i titoli a ogni passaggio, nessuna rotazione necessaria. Se il batch Yahoo manca posizioni aperte o watchlist, queste vengono riscaricate a parte.
- **Limite noto**: i titoli nuovi non hanno ISIN nel file, quindi niente quotazione live L&S. Per gli europei il prezzo Yahoo arriva con ~15 minuti di ritardo (gli USA sono quasi in tempo reale): ingressi e uscite su quei titoli sono simulati su prezzi più vecchi.
- **Backtest** (script R&D fuori repo `bigwide_test.py`, cache Yahoo 5m `cache_w`, 59 sedute 26/08-16/11/2026, stesse regole e costi della v0; lo screen riproduce esattamente la versione da 55 titoli: −5,74 €, 24 trade):
  - v0 (8 titoli): −7,09 € netto, OOS −13,86, holdout −6,95, 19 trade, DD −2,0%
  - 55 titoli (EU core + lista USA, commit 28a349b): −5,74 €, OOS −12,51, holdout −5,45, 24 trade, DD −2,2%
  - ~300 EU + lista USA: −73,94 €, OOS −61,18, holdout −29,64, 58 trade, DD −8,3%
  - **1.233 titoli EU+USA (in produzione)**: −344,43 €, OOS −211,83, holdout −67,08, 204 trade (188 su titoli nuovi; 184 USA −304,63 €), WF 0/4, **DD −34,6%**. Lordo +64,44 €, commissioni 408 €.
- **Decisione**: in produzione per ordine esplicito di Andrea, che ha accettato il rischio sapendo che gli universi larghi andavano peggio. Per tornare indietro: `wide_file=False` (55 titoli) oppure `wide_regions=("EU",)`.
- **Test**: `test_wide_scan.py` aggiornato (screen di tutto l'universo, valutazione completa solo dei candidati, priorità live, `wide_regions`, file universo senza duplicati e solo EUR/USD, `meta()` sui titoli nuovi). Passano anche gli altri test e `gh/secret_check.py`.
- **Altro**: nessuna modifica al branch `state`, allo scheduler o ai workflow (il passaggio dura circa 1 minuto, molto meno dei 10).

## 2026-11-16 (~23:30 ora di Roma) - Scansione larga in produzione: tutti i titoli europei a ogni passaggio (55 titoli invece di 8)

- **Cosa**: `trade.py` non guarda più solo gli 8 titoli scelti alle 09:35. A ogni passaggio (ogni 10 minuti, 07:30-21:45) valuta **tutti i titoli europei di `universe.csv` (52)** più la watchlist delle 09:35 (che porta i 3 USA): 55 titoli. Config `CFG["wide_universe"]=True`, `CFG["wide_regions"]=("EU",)`. Dati: un solo download Yahoo 5m per tutti i titoli; quotazioni live L&S (max 20 per passaggio, `ls_priority_max`) per posizioni aperte, titoli vicini alla rottura del massimo dell'opening range (`breakout_candidates`) e watchlist; barre giornaliere solo per i titoli che possono dare un segnale. Prova reale dal box: ~20 s a passaggio, ben dentro i 10 minuti e i limiti di GitHub Actions (repo pubblico, minuti gratuiti; ogni job resta sotto le 6 ore). Ordine di valutazione come nel backtest: watchlist (punteggio scan), poi l'universo.
- **USA larghi in shadow**: i 16 titoli USA fuori dalla watchlist girano come `V0_WIDE` in `shadow.py` (regole v0, un batch Yahoo, nessun ordine; sezione "V0_WIDE" nel report delle 21:56). Così domani vengono controllati tutti i 71 titoli: 55 in produzione, 16 in shadow.
- **Filtro commissioni**: il sizing è ora in `common.size_position`. Con il tetto del 30% (300 €) e stop minimo 0,4% il guadagno a 2R arriva a 2,40 €, quindi il filtro 6 € passa solo con stop ≥ 1%. Correzione implementata e testata: leva "solo quanto basta" per arrivare a 6 € (`lev_to_gate`, max 5x lo slot, rischio sempre ≤ 2%, margine = slot, il resto è un prestito paper `positions.loan_eur` con migrazione automatica, restituito alla chiusura; equity e report al netto del prestito, leva indicata nelle posizioni aperte). **Spenta** (`lev_to_gate=False`) perché il backtest la boccia: −414,74 € sulla lista 09:35 (169 trade, 165 a leva, win rate 14%, DD −41%) e −753,78 € con la scansione larga. I breakout "tranquilli" con stop 0,4% vengono stoppati dal rumore: lordo −87 € prima ancora di 330 € di commissioni. Anche abbassare il filtro perde: 2x −80,91 €, 1x peggio; alzare lo stop minimo a 1% −27,03 €, 1,2% −170,77 €.
- **Report 21:55**: i motivi di scarto sono raggruppati senza numeri, così tutti gli scarti del filtro commissioni finiscono in una sola voce "filtro commissioni (guadagno atteso sotto 6 €)", sempre mostrata anche fuori dalla top 5, più una riga con il numero di scarti per titolo.
- **Validazione** (script R&D fuori repo `wide_test.py`, 62 sedute 21/08-16/11/2026, stesso harness della v0: costi 1+1 €, slippage 0,05%, tassa 26% dopo commissioni con zainetto; netto / OOS / holdout / WF / DD / trade):
  - v0 attuale (lista 5 EU + 3 USA): −7,09 / −8,06 / −6,95 / 2/5 / −2,0% / 19
  - **larga EU + lista USA (in produzione)**: −5,74 / −6,71 / −5,45 / 2/5 / −2,2% / 24 (16 giorni con trade invece di 14)
  - larga su tutti i 71: −106,33 / −71,32 / −51,82 / 1/5 / −11,0% / 56 (USA: 46 trade, −106,54 €; EU: 10 trade, +0,21 €)
  - lista + leva al filtro: −414,74 / −290,11 / −144,83 / 0/5 / −41,5% / 169; larga + leva: −753,78 / 0/5 / −75,4% / 298; + classifica per punteggio grafico (3 o 5 posizioni): −755,01, identico (i segnali quasi mai arrivano insieme); larga + classifica senza leva −106,30
  - larga + filtro 8 €: −31,56 / −8,18 / −2,53 / 17; larga EU + filtro 8 €: +8,77 / +5,63 / +6,83 / 11 trade (meno trade della v0); watchlist 10+6: −53,52; passaggi ogni 5 min: v0 −20,87, larga −126,54 -> si resta a 10 minuti
  - sensitività larga EU contro v0 (netto/OOS): stop 1,25 ATR −6,93/−10,72 contro −7,02/−10,81; 1,75 ATR −44,18 contro −39,00; target 1,75R −4,01 contro −3,14; 2,25R −30,51 contro −27,16; estensione 1,25 −5,12 contro −6,48; 1,75 −5,97 contro −7,32; filtro 2,5x −51,66 contro −45,57; 3,5x +0,19; stop min 0,3%/0,5% invariato. Segue la v0 entro ~6 € su tutta la griglia.
  - Con lo split R&D 26/08-16/11 (59 sedute, quello di Lerabuns): v0 −7,09 / OOS −13,86 (WF 1/4); larga EU −5,74 / OOS −12,51 (WF 1/4).
  - Cautela: la scelta "EU sì, USA no" è stata fatta dopo aver visto il risultato per regione della versione larga su tutti i titoli.
- **Decisione**: regola del giorno (netto e OOS non peggiori della v0 di oltre ~15 €, DD < 10%) rispettata e il bot fa più trade, quindi la scansione larga EU va in produzione da martedì 17/11 alle 07:30. Leva al filtro e scansione larga USA no.
- **Più titoli nell'universo**: provati 40 titoli europei liquidi in più (DAX, FTSE MIB, CAC, IBEX, AEX: universo 111). Fattibile con Yahoo (un batch, nessun limite incontrato) ma il backtest peggiora: larga EU su 92 titoli EU −12,35 € (OOS −19,12, WF 0/4, 26 trade) contro −5,74 su 52 nella stessa finestra. Non aggiunti. Le quotazioni live L&S restano limitate a 20 per passaggio.
- **Test**: nuovo `python3 test_wide_scan.py` (sizing e filtro, leva al filtro e contabilità del prestito, screen dei breakout, ordine e priorità live della scansione larga, piano shadow V0_WIDE, raggruppamento del filtro commissioni nel report). Passano anche `test_short.py`, `test_fee4_shadow.py`, `test_ema_filter.py`, `test_trade_log.py`, `test_scan_watchlist.py`, `test_debate.py`, `gh/test_chain.py` e `gh/secret_check.py`.
- **Altro**: nessuna modifica al branch `state`, allo scheduler o ai workflow.

## 2026-11-16 (~23:20 ora di Roma) - R&D serale: verdetti dibattito LLM, V0_FEE4 e filtro EMA (nessun deploy)

- **Stato**: run GitHub regolari (ultima schedule 21:34 success, heartbeat 22:25). Produzione 16/11: 0 trade, equity 1.000,00 €; DAX ETF −0,41%. Motivi di non ingresso: nessun breakout 287, fuori finestra 237, momentum 15m negativo 72, troppo esteso 56, sotto VWAP 24, filtro commissioni 7 (2,40-3,19 € < 6 €, tema che Sguattera sta correggendo stanotte).
- **(1) Filtro dibattito LLM (prova shadow, commit 010f4e1)**: l'API Pollinations gpt-oss-20b ha risposto dai runner GitHub (3 chiamate per dibattito, 0 NON_DECISO, decisioni tutte in tempo, ritardo 2,4-5,5 min). 4 setup unici (RHM, HAG, BAYN, DTE): giudice SCARTA 4/4, ENTRA 0. Nessun filtro −6,13 € ante tasse (0/4 vincenti, tutti chiusi in stop/trailing); ENTRA 0 €; SCARTA −6,13 €. Il giudice ha evitato tutti i perdenti in una giornata di mercato debole (56 titoli su 76 in calo), ma con 4/4 scarti non si distingue da "scarta sempre"; nota: le motivazioni citano spesso il REJECT dell'analista grafico, possibile ancoraggio. **Verdetto**: secondo la regola pre-registrata ENTRA non è peggio di nessun filtro, quindi resta in prova shadow anche martedì 17/11; nessun ordine. Se il giudice scarta tutto anche martedì, va considerato non informativo.
- **(2) V0_FEE4 (shadow, commit f3fdeb5)**: 0 segnali il 16/11 (la copia V0 a 6 € ne ha avuti 4, tutti respinti da grafico/commissioni). Nessun dato per giudicare: lo shadow continua. Da rivalutare dopo il fix del fee gate di Sguattera (cambia la soglia di riferimento); promozione solo con ≥ 20 trade OOS e walk-forward migliore della v0.
- **(3) Filtro EMA9>EMA21 in produzione (f5a5f76), verifica con regola completa**: oggi `ema_misaligned` = 0 nei log e nei contatori (confermato; i 7 candidati arrivati al filtro commissioni avevano già EMA allineate), quindi oggi neutrale. Ritest `indicators_test.py` su dati aggiornati 24/08-16/11 (61 sedute, costi 1+1 €, slippage 0,05%, tassa 26% con zainetto): v0 senza EMA −18,82 € (20 trade, OOS −25,59 € su 16, WF 0/5, holdout −12,58 €, DD −3,1%); v0+EMA −7,09 € (19, OOS −13,86 € su 15, WF 1/5, holdout −6,95 €, DD −2,0%); griglia stabile (EMA8/21, EMA9/26, prezzo>EMA50 identiche; EMA9>21>50 OOS −10,24 €). Non supera la soglia assoluta (netto OOS > 0, ≥ 20 trade OOS) ma batte la v0 senza filtro su tutti i confronti e non crolla con piccoli cambi. **Decisione**: nessun rollback (tornare alla v0 senza EMA peggiorerebbe il netto atteso); resta in produzione.
- **Backtest vs reale**: `run_rd.sh` 24/08-16/11 baseline v0 20 trade −18,82 € (invariato), tutte le varianti NON VALIDATE; reale 0 trade oggi, coerente con la scarsità di segnali. Leva (`--leverage`): run ancora in corso al momento di questa voce (strict_fees 0 trade); ultimo risultato completo 13/11 da −283 a −740 €, nessun segnale con vantaggio lordo, quindi nessun uso della leva.
- **Notizie (Natasia)**: `news_eval.py` 89 coppie valutabili (< 100): LLM hit rate 53,9%, Spearman +0,088; parole chiave 47,4%, +0,067. Campione insufficiente, nessuna integrazione.
- **V0_SHORT**: committato alle 22:08, gira dal 17/11; `test_short.py` e tutti i test passano, `shadow.py` compila. Nessun errore da segnalare.
- **Revisione HR 16/11**: pullback VWAP e mean-reversion nei giorni laterali già bocciati il 14-15/11 (validate.py); quant/backtester e analista notizie LLM già attivi; calendario eventi, monitor quotazioni e specialista USA rinviati per gli stessi motivi del 13/11 (nessun calendario storico, ORB USA già bocciato). Campione 0 trade: nessuna modifica.
- **Altro**: nessuna modifica a codice, ledger, branch `state`, scheduler o workflow. Le modifiche non committate presenti nel checkout (lavoro notturno di Sguattera su scansione ampia e fee gate) non sono state toccate.

## 2026-11-16 (~22:15 ora di Roma) - Lato SHORT della v0: codice pronto, in shadow (V0_SHORT), non in produzione

- **Cosa**: lato short speculare della v0. Si entra con chiusura sotto il minimo dell'opening range, sotto VWAP, momentum 15m negativo ed EMA9<EMA21, a non più di 1,5 ATR sotto ORL. Lo stop è a min(ORH, prezzo + 1,5 ATR), con limiti 0,4%-3%, e il target 2R sotto il prezzo, con breakeven a +1R. Sizing e filtro commissioni sono gli stessi (2R ≥ 6 €). L'analista grafico deve dare un punteggio ≤ −25 e chiude in anticipo uno short se il punteggio sale a ≥ +30. Le notizie bloccano lo short se positive (≥ +0,4).
- **Ledger** (`common.py`): nuova colonna `positions.side` con migrazione automatica; le posizioni esistenti restano `long`. Gli ordini short sono registrati come `SHORT` (vendita al bid) e `COVER` (riacquisto all'ask o a prezzo + slippage). Il nozionale dello short viene accantonato dal cash all'ingresso, a 1x e senza leva aggiuntiva, e restituito alla chiusura insieme al P&L. Nell'equity uno short vale nozionale + (ingresso − prezzo) × qtà. Il lordo è (ingresso − uscita) × qtà; commissioni 1+1 € e tassa 26% dopo le commissioni con zainetto, come per i long. `trade_log` registra `side=short` e MAE/MFE con il segno corretto. `trade.py` gestisce stop, target, breakeven, uscita da grafico e chiusura a fine giornata per entrambi i lati. Report, aggiornamenti e `round_trips` riconoscono SHORT/COVER.
- **Validazione** (script R&D fuori repo `short_test.py`, 61 sedute 21/08-13/11/2026, report `short_2026-11-16.md`): v0 solo long −7,09 € (19 trade, OOS −8,06, holdout −6,95, WF 2/5, DD max −2,0%); long+short −69,31 € (46 trade di cui 29 short, OOS −57,71, holdout −16,45, WF 1/5, DD −7,4%). I soli short fanno −69,35 € su 29 trade: lordo −10,28 €, commissioni 58 €. Con una watchlist "ribassista" speculare il risultato è −49,09 € (OOS −40,69). Con short su entrambe le watchlist −120,52 €. Su tutta la griglia (stop 1,25/1,75 ATR, target 1,75/2,25R, estensione 1,25/1,75, filtro commissioni 2,5x/3,5x, soglia grafico −15/−35) long+short resta sotto la sola long. Simulazione dei giorni: il 13/11 avrebbe fatto 3 short (AMD, MU, NVDA), tutti chiusi in stop, −8,09 €. Il 16/11 (56 titoli su 76 in calo) 0 trade anche con gli short: i breakdown erano già oltre 1,5 ATR, sotto la soglia commissioni o con momentum girato.
- **Decisione**: la regola di deploy (netto e OOS non peggiori di oltre ~10 € e DD < 10%) non è rispettata, quindi `CFG["allow_short"] = False` e la produzione resta solo long, con lo stesso comportamento di prima. Il lato short gira in shadow come `V0_SHORT` sulla watchlist statica dal 17/11, senza ordini. Gli esiti finiscono nel `trade_log` con `source=shadow` e nella sezione "Lato SHORT V0_SHORT" del report delle 21:56. Per attivarlo basta `allow_short=True`.
- **Test**: nuovo `python3 test_short.py` (contabilità e tassa short, zainetto, cover all'ask, migrazione, ingresso short in `try_entry`, stop short, shadow `orb_short` + eod). Passano anche `test_trade_log.py`, `test_scan_watchlist.py`, `test_debate.py`, `gh/test_chain.py`, `test_ema_filter.py`, `test_fee4_shadow.py` e `gh/secret_check.py`.
- **Altro**: nessuna modifica al branch `state`, allo scheduler o ai workflow.

## 2026-11-16 (~15:35 ora di Roma) - Shadow V0_FEE4: v0 con filtro commissioni 4x (prova di un giorno, nessun ordine)

- **Cosa**: nuova strategia shadow `V0_FEE4` in `shadow.py`, con regole identiche alla v0 in produzione (ORB + VWAP + momentum 15m + EMA9>EMA21, estensione max 1,5 ATR, analista grafico, stop 1,5 ATR, target 2R). L'unica differenza è il filtro commissioni: il guadagno al target deve essere almeno 4 volte le commissioni (8 €) invece di 3 volte (6 €). Gira sulla watchlist statica ogni 10 minuti come le altre shadow. Gli esiti delle 21:56 vanno in `data/trade_log.jsonl` con `source=shadow` e `strategy_id=V0_FEE4`, e il report shadow ha una nuova sezione "Prova V0_FEE4". Quella sezione mette a confronto i segnali e il netto di V0_FEE4, la copia V0 (filtro 6 €) e i trade della v0 in produzione chiusi oggi. V0_FEE4 non passa dal dibattito LLM, quindi non fa chiamate in più.
- **Perché**: è il candidato migliore di `sizing_scan_2026-11-16` (script R&D fuori repo `sizing_scan_test.py`, 61 sedute 21/08-13/11/2026, costi 1+1 €, slippage 0,05%, tassa 26%). Ha fatto +7,26 € su 7 trade, contro −7,09 € su 19 della v0+EMA, con OOS +4,12 € (−8,06 €) e holdout +5,32 € (−6,95 €). La griglia è stabile, con 5 punti su 7 positivi. Non va in produzione perché il walk-forward è 2/5, uguale alla v0 e non migliore, e i trade OOS sono solo 6 contro un minimo di 20. Lo stesso test ha bocciato il ranking e il sizing Monte Carlo (instabile e dipendente dal seed) e la leva 2x/3x/5x (−125 / −318 / −371 €, max DD fino a −37%). Ha bocciato anche il filtro commissioni 2x e i re-scan alle 10:30, 11:30, 15:30 e 16:30 (tutti tra −34 e −70 €), oltre alle watchlist più larghe.
- **Prova**: attiva da oggi 16/11, dal primo ciclo shadow dopo il pull di main. Si giudica nel report delle 21:56, con la regola della prova di un giorno.
- **Test**: nuovo `python3 test_fee4_shadow.py` (filtro 8 € contro 6 €, collegamento al piano, nessuna chiamata al dibattito, riga del trade_log `V0_FEE4`, sezione del report). Passano anche `test_trade_log.py`, `test_scan_watchlist.py`, `test_debate.py`, `gh/test_chain.py`, `test_ema_filter.py` e `gh/secret_check.py`.
- **Altro**: produzione (`trade.py`, `common.py`, ledger, sizing) invariata. Nessuna modifica al branch `state`, allo scheduler o ai workflow.

## 2026-11-15 (~11:10 ora di Roma) - Filtro EMA9>EMA21 in produzione (v0)

- **Cosa**: la v0 (ORB + VWAP + momentum 15m) entra in long solo se, sulla stessa barra a 5 minuti usata nel test, EMA9 è sopra EMA21 (`ema_aligned` in `common.py`, periodi 9 e 21, `ewm(span, adjust=False)` sulle chiusure). Se le EMA non sono pronte o non sono allineate, l'ingresso è rifiutato con motivo `ema_misaligned`, che compare nei conteggi del report giornaliero. Un eventuale short (oggi la v0 è solo long) richiederebbe EMA9 sotto EMA21. Stop, target, commissioni, sizing e analista grafico restano quelli della v0.
- **Validazione** (script fuori repo `indicators_test.py`, 61 sedute 21/08-13/11/2026, barre 5 min, CON.DE escluso, costi 1+1 €, slippage 0,05%, tassa 26% dopo le commissioni):
  - v0 (prima, già in produzione): −18,82 €, 20 trade, OOS −19,79 € (17), holdout −12,58 €, walk-forward 0/5
  - v0 + EMA9>EMA21 (parametri scelti, quelli messi in produzione): −7,09 €, 19 trade, OOS −8,06 € (16), holdout −6,95 €, walk-forward 2/5; griglia stabile (EMA8>EMA21 e EMA9>EMA26 identiche al centro; EMA9>EMA21>EMA50 OOS −4,44 € su 18 trade; prezzo>EMA50 identica al centro)
  - altri candidati dello stesso test, non adottati: v0+ADX(14)>20 −20,04 € (19); stop su EMA50 −172,39 € (101); v0 senza long se RSI>70 −6,91 € ma solo 9 trade; incrocio EMA9/21+EMA200+ADX −34,61 € (15); MACD + squeeze Bollinger −17,96 € (5)
- **Perché**: il filtro batte la v0 su netto, OOS, holdout e blocchi walk-forward, e la griglia non crolla. Resta un netto negativo (con 1.000 € e 2 € a giro nessuna regola testata è in utile), ma perde meno della v0 precedente. Attivo da lunedì 16/11 alle 07:30.
- **Shadow**: la copia diagnostica V0 del dibattito (e ORB_DYN / V0_LOOSE, che condividono `orb()`) usa lo stesso filtro, così il confronto di lunedì sera è sulla v0 aggiornata. Nessun ordine dallo shadow.
- **Test**: `python3 test_ema_filter.py`; `test_trade_log.py`, `test_scan_watchlist.py`, `test_debate.py`, `gh/test_chain.py`.
- **Altro**: nessuna modifica al branch `state`, allo scheduler o ai workflow. Ledger e sizing invariati.


## 2026-11-15 (~00:18 ora di Roma) – Validazione walk-forward + sensitività: nessun deploy

- **Cosa**: script riutilizzabile `rd-paper-trading/validate.py` (fuori dal repo pubblico). Walk-forward a blocchi
  (IS minimo 20 sedute, OOS da 10, holdout ultimo 1/3) più griglia one-at-a-time intorno ai parametri scelti, al netto
  di commissioni 1+1 €, slippage 0,05% e tassa 26% dopo le commissioni (zainetto FIFO, nessun lookahead). CON.DE escluso.
  Finestra 21/08–13/11/2026 (61 sedute, barre 5 min). Un candidato passa solo se batte la v0 fuori campione (OOS e holdout,
  entrambi con netto > 0), è stabile sui blocchi walk-forward e non crolla a piccoli cambi di parametri.
- **Candidati (netto totale / trade / netto OOS / stabilità / robustezza / esito)**:
  - v0 (riferimento, già in produzione): −18,82 €, 20 trade, OOS −19,79 € (17), 0/5 blocchi, non validata walk-forward
  - V0_LOOSE (estensione 3 ATR, filtro 1,5×): −210,39 €, 95, OOS −155,04 €, 0/5, instabile — FAIL
  - v0 watchlist 10 UE + 6 USA: −59,82 €, 30, OOS −47,53 €, 1/5 — FAIL
  - pullback VWAP dopo breakout troppo esteso: identico alla v0 (0 trade in più) — FAIL
  - fade del falso breakout OR (1×, non KO x5): −272,28 €, 100, OOS −192,82 € — FAIL
  - momentum ultima ora USA (1×): −10,19 €, 7 trade, OOS +4,87 € e holdout +10,29 € ma solo 3 trade OOS (< 20) — FAIL
  - fade del gap overnight (regime e ingresso solo su dati già noti): −212,14 €, 79, OOS −123,64 € — FAIL
  - ORB USA A/B/C (1×): A −63,37 € (56), B −51,89 € (31), C −16,31 € (38, OOS −0,75 €, 3/5 blocchi) ma holdout peggiore della v0 e OOS non > 0 — FAIL
  - mean-reversion su VWAP solo in giorni range-bound (regime = range/chiusura di ieri ≤ mediana dei 20 giorni precedenti): −320,02 €, 139, OOS −131,51 € — FAIL
- **Decisione**: nessun candidato supera i tre criteri → **nessun deploy**, la v0 resta invariata. Il registro trade `a8c8f61` è già su `main`.
- Codice di produzione, scheduler, workflow e ledger non toccati in questo passo.


## 2026-11-14 (~23:42 ora di Roma) – Registro trade in append-only (produzione e shadow)

- **Cosa**: ogni chiusura (produzione e shadow, compreso il filtro dibattito) scrive una riga in `data/trade_log.jsonl`
  (solo in aggiunta, mai riscritto; vive sul branch `state`). Campi: `strategy_id`, titolo, verso, orario e prezzo di
  ingresso/uscita, quantità, motivo di ingresso e di uscita, MAE e MFE (prezzo e EUR: minimo/massimo delle barre mentre
  la posizione è aperta), slippage modellato 0,05%, commissioni 1+1 €, lordo, risultato dopo le commissioni, tassa
  italiana 26% sull'utile dopo le commissioni (con zainetto in produzione) e netto. In produzione `mae_local`/`mfe_local`
  restano sulla posizione aperta e si aggiornano a ogni barra in `trade.py`.
- **Perché**: richiesta di Andrea (registro più ricco, con motivo di uscita e escursione massima a favore/contro).
- **Test**: `python3 test_trade_log.py` (escursioni long/short, tassa dopo le commissioni, append-only, chiusura
  produzione che scrive il log). `test_scan_watchlist.py`, `test_debate.py` (16/16) e `gh/test_chain.py` ok.
- **Altro**: corretto un refuso in `shadow.py` per cui la copia V0 del dibattito usava l'estensione 3 ATR di V0_LOOSE
  invece di 1,5; il filtro dibattito non è stato cambiato per il resto. Nessuna modifica a ordini, sizing, scheduler
  o workflow. Percorso del log sovrascrivibile con `PT_TRADE_LOG` (test isolati).


## 2026-11-14 (~23:40 ora di Roma) – Filtro sperimentale "dibattito" LLM, SOLO shadow, attivo da lunedì 16/11

- **Cosa**: nuovo `debate.py` + aggancio in `shadow.py` (richiesta di Andrea via Sguattera, prova di un giorno). Per ogni segnale live V0
  (copia diagnostica delle regole di `trade.py` sulla watchlist statica, compresi i segnali bloccati dal filtro commissioni o respinti dal grafico),
  V0_LOOSE e NEWS_LLM (giudizi di Natasia non scaduti ed emessi prima del segnale, |impact| ≥ 0,5, confidence ≥ 0,6; verso = segno dell'impact,
  stop 1,5 ATR5m limitato a 0,4–3%, target 2R) tre chiamate LLM: PRO, CONTRO, GIUDICE → ENTRA/SCARTA + motivo. Input solo dati noti al segnale
  (prezzo, ORH/ORL, VWAP, momentum 15m, ATR5m, chiusura di ieri, stop/target, punteggio grafico, titoli pubblicati e scaricati entro l'ora del segnale).
- **Dove**: segnali V0/NEWS_LLM in `data/debate_signals.jsonl` (fuori dai totali shadow), decisioni con timestamp in `data/debate_decisions.jsonl`,
  esiti in `data/debate_results.jsonl` (tutti solo in aggiunta, branch `state`); confronto ENTRA / SCARTA / nessun filtro / non decisi nel report
  `reports/shadow_YYYY-MM-DD.md` delle 21:56, con cumulativo dopo tassa 26%. Esito con sizing diagnostico su 1.000 €, stesse uscite della v0
  (stop, 2R, breakeven a +1R, 21:50), netto 1 € + 1 €. Una decisione conta solo se registrata prima dell'uscita simulata (anti-lookahead).
  V0 e V0_LOOSE identici (stessa barra/ingresso/stop) usano una sola decisione e contano una volta nei totali.
- **LLM**: GitHub Models è stato ritirato il 30/07/2026 (docs GitHub), quindi niente `permissions: models` nel workflow (non toccato). Si usa
  l'endpoint anonimo gratuito di Pollinations (`text.pollinations.ai/openai`, modello gpt-oss-20b), senza chiavi né header Authorization.
  Limiti: max 3 chiamate per segnale, 40 segnali e 120 chiamate al giorno, timeout 45 s, ≥ 31 s tra chiamate (limite per IP), worker in
  background con lock (max 25 min per avvio), mai bloccante per shadow/trade; errore o tetto → NON_DECISO. Attivo solo dal 16/11.
- **Perché**: richiesta di Andrea; misura a costo zero se un filtro "dibattito" migliora i segnali. Pre-registrazione:
  R&D `reports/preregistration_2026-11-16_debate.md` (un giorno non basta per operare; nettamente peggio → si scarta; meglio → prova anche martedì).
- **Test**: `python3 test_debate.py` 16/16 (orologio finto 16/11, API finta: decisione prima dell'esito, dedup, API in errore → NON_DECISO,
  DEBATE_OFF, long al target, short allo stop, decisione tardiva esclusa). Chiamata reale all'API dal box: 3 chiamate in 68 s, verdetto valido.
  End-to-end con orologio finto sul 12/11 17:03 (barre Yahoo): 8 segnali (3 V0, 3 V0_LOOSE, 1 NEWS_LLM finto, 1 ORB_DYN), 4 dibattiti reali
  (12 chiamate, 3 decisioni riusate), tutti SCARTA; report 21:56 generato con confronto. Endpoint irraggiungibile → NON_DECISO senza eccezioni.
  `shadow.py --dry-run` e `--eod --dry-run` senza errori e senza scritture; `test_scan_watchlist.py` e `gh/test_chain.py` ok.
- **Altro**: `gh/session_runner.py` aspetta anche `python3 debate.py` prima di salvare lo stato. Nessuna modifica a `trade.py`, ordini, ledger,
  scheduler o workflow. Backup: `backups/20261114-231812/`.

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
