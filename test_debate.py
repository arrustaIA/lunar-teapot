#!/usr/bin/env python3
"""Test del filtro dibattito (solo shadow) con orologio finto, API finta e barre sintetiche. Nessuna rete, nessun ledger.
Uso: python3 test_debate.py"""
import json, os, sys, tempfile
from datetime import datetime, timedelta
TMP = tempfile.mkdtemp(prefix="debate-test-")
os.environ["DEBATE_DIR"] = TMP
import pandas as pd
import debate as D
from common import ROME, CFG
CFG["debate_shadow"] = True   # il test verifica la logica del dibattito anche se in produzione è spento

T0 = datetime(2026, 11, 16, 10, 3, tzinfo=ROME)
clock = [T0]
D.now = lambda: clock[0]
D.today = lambda: clock[0].date()
D.log = lambda *a, **k: None
D.LIM["min_gap_s"] = 0
D.to_eur = lambda p, c: p

def bars(path):
    idx = pd.date_range(datetime(2026, 11, 16, 9, 0, tzinfo=ROME), periods=len(path), freq="5min")
    return pd.DataFrame({"Open": path, "High": [p + 0.2 for p in path], "Low": [p - 0.2 for p in path], "Close": path}, index=idx)

SIG = dict(day="2026-11-16", ts=T0.isoformat(), strategy="V0", ticker="SAP.DE", region="EU", side="long", currency="EUR",
           price=100.0, entry=100.05, stop=99.0, target=102.1, bar=str(datetime(2026, 11, 16, 10, 0, tzinfo=ROME)),
           ctx={"ORH": 99.8, "VWAP": 99.5}, info="ORH 99.8", chart_score=40, chart_verdict="APPROVE")
seen = []
def fake_call(msgs, mt):
    seen.append(msgs[-1]["content"])
    if "GIUDICE" in msgs[0]["content"]:
        return '{"verdetto": "ENTRA", "motivo": "breakout pulito"}', "fake-model"
    return "argomento", "fake-model"

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg; ok += 1; print("OK", msg)

# 1) segnale V0 in attesa -> worker decide con 3 chiamate, registra PRIMA dell'esito
open(os.path.join(TMP, "debate_signals.jsonl"), "w").write(json.dumps(SIG) + "\n")
check(len(D.pending("2026-11-16")) == 1, "segnale in attesa")
clock[0] = T0 + timedelta(minutes=2)
n = D.worker(call=fake_call)
dec = [json.loads(l) for l in open(D.DEC)]
check(n == 1 and dec[0]["verdict"] == "ENTRA" and dec[0]["calls"] == 3 and dec[0]["model"] == "fake-model", "decisione ENTRA con 3 chiamate")
check(dec[0]["ts_decision"] == (T0 + timedelta(minutes=2)).isoformat(timespec="seconds") and dec[0]["lag_min"] == 2.0, "timestamp decisione da orologio finto")
check(not os.path.exists(D.RESF), "nessun esito calcolato al momento della decisione")
check(all("SAP.DE" in s and "102.1" in s for s in seen[:2]) and "Tesi A FAVORE" in seen[2], "prompt con dati del segnale e tesi al giudice")
check(D.pending("2026-11-16") == [], "dedup: niente seconda decisione")

# 2) secondo segnale: API in errore -> NON_DECISO, nessuna eccezione
def bad_call(msgs, mt):
    raise D.ApiError("HTTP 402")
s2 = dict(SIG, strategy="NEWS_LLM", ticker="ENR.DE", side="short", entry=49.95, price=50.0, stop=50.75, target=48.5,
          natasia={"impact": -0.6, "confidence": 0.7, "rationale": "test", "issued_at": "2026-11-16T08:00:00+01:00"})
with open(os.path.join(TMP, "debate_signals.jsonl"), "a") as f:
    f.write(json.dumps(s2) + "\n")
D.worker(call=bad_call)
dec = [json.loads(l) for l in open(D.DEC)]
check(dec[-1]["verdict"] == "NON_DECISO" and "402" in dec[-1]["error"], "API in errore -> NON_DECISO")
os.environ["DEBATE_OFF"] = "1"
try:
    D.chat([{"role": "user", "content": "x"}]); check(False, "DEBATE_OFF")
except D.ApiError:
    check(True, "DEBATE_OFF=1 -> ApiError gestito (modello assente)")
del os.environ["DEBATE_OFF"]

# 3) parse del verdetto
check(D.parse_verdict('bla {"verdetto":"SCARTA","motivo":"x"}')[0] == "SCARTA", "parse JSON")
check(D.parse_verdict("Decido: ENTRA, perché...")[0] == "ENTRA", "parse testo")
check(D.parse_verdict("boh")[0] is None, "verdetto illeggibile -> None")

# 4) esito a fine giornata: long al target, short allo stop, confronto gruppi
clock[0] = datetime(2026, 11, 16, 21, 56, tzinfo=ROME)
path_long = [100.0] * 13 + [100.5, 101.0, 101.5, 102.0, 102.5, 103.0] + [103.0] * 20
path_short = [50.0] * 13 + [50.3, 50.6, 50.9, 51.2] + [51.2] * 20
md = D.eod_lines(bars_fn=lambda t: {"SAP.DE": bars(path_long), "ENR.DE": bars(path_short)})
res = {r["ticker"]: r for r in (json.loads(l) for l in open(D.RESF))}
check(res["SAP.DE"]["outcome"] == "target" and res["SAP.DE"]["group"] == "ENTRA" and res["SAP.DE"]["net_ante_tasse"] > 0, "long al target, gruppo ENTRA")
check(res["ENR.DE"]["outcome"] == "stop" and res["ENR.DE"]["net_ante_tasse"] < 0 and res["ENR.DE"]["group"] == "NON_DECISO", "short allo stop, NON_DECISO")
txt = "\n".join(md)
check("Approvati (ENTRA): 1 segnali" in txt and "Nessun filtro (tutti i segnali con esito): 2 segnali" in txt and "setup unico" in txt, "confronto approvati/scartati/nessun filtro")
check("dopo tassa 26%" in txt, "riepilogo cumulativo con tassa")
# 5) decisione registrata DOPO l'uscita -> esclusa
D.RESF = os.path.join(TMP, "r2.jsonl"); D.DEC = os.path.join(TMP, "d2.jsonl")
late = dict(day="2026-11-16", strategy="V0", ticker="SAP.DE", verdict="ENTRA", ts_decision="2026-11-16T20:00:00+01:00")
open(D.DEC, "w").write(json.dumps(late) + "\n")
D.eod_lines(bars_fn=lambda t: {"SAP.DE": bars(path_long), "ENR.DE": bars(path_short)})
r2 = {r["ticker"]: r for r in (json.loads(l) for l in open(D.RESF))}
check(r2["SAP.DE"]["decided_in_time"] is False and r2["SAP.DE"]["group"] == "NON_DECISO", "decisione dopo l'esito esclusa (anti-lookahead)")
print(f"tutti i {ok} controlli superati ({TMP})")
