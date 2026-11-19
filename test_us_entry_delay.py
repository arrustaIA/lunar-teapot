#!/usr/bin/env python3
"""Test del flag us_entry_delay_min (Q4_90): ingressi USA solo da apertura+N min; EU invariati; uscite non toccate."""
import os, tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ROME = ZoneInfo("Europe/Rome")
TD = tempfile.mkdtemp(prefix="pt-usd-")
os.environ.update(PT_DB=os.path.join(TD, "l.sqlite"), PT_LOCK=os.path.join(TD, ".lock"), PT_TRADE_LOG=os.path.join(TD, "t.jsonl"),
                  PT_LOGS=os.path.join(TD, "logs"), PT_REPORTS=os.path.join(TD, "reports"))
import common as C
import trade as T
failed = 0
def check(c, n):
    global failed
    print(("ok  " if c else "FAIL ") + n); failed += (not c)

check(C.CFG.get("us_entry_delay_min") == 90, "flag attivo = 90 min")
d = datetime(2026, 11, 19).date()
class FakeNow:
    def __init__(s, t): s.t = t
def run(region, hhmm):
    h, m = map(int, hhmm.split(":"))
    T.now = lambda: datetime(2026, 11, 19, h, m, tzinfo=ROME)
    T.today = lambda: d
    return T.plan_entry(None, dict(ticker="X", region=region), None, 1000, 1000, 0, None)
# us window: prima di 17:00 respinto dal nuovo gate
for hh in ("16:00", "16:30", "16:59"):
    r = run("US", hh); check(isinstance(r, str) and "ingressi USA solo da 17:00" in r, f"US {hh} bloccato")
# dalle 17:00 il gate non risponde (passa ai controlli successivi, che falliscono sui dati None ma non con il nuovo messaggio)
for hh in ("17:00", "18:30"):
    try: r = run("US", hh)
    except Exception: r = "oltre il gate (dati finti)"
    check(not (isinstance(r, str) and "ingressi USA solo da" in r), f"US {hh} non bloccato dal gate")
# EU invariato
for hh in ("09:30", "11:00"):
    try: r = run("EU", hh)
    except Exception: r = "oltre il gate"
    check(not (isinstance(r, str) and "ingressi USA" in r), f"EU {hh} non toccato")
# rollback
C.CFG["us_entry_delay_min"] = None
try: r = run("US", "16:00")
except Exception: r = "oltre il gate"
check(not (isinstance(r, str) and "ingressi USA solo da" in r), "rollback None: US 16:00 di nuovo ammesso")
print("FAILED" if failed else "ALL OK"); raise SystemExit(1 if failed else 0)
