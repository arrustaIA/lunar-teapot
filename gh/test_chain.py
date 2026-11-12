#!/usr/bin/env python3
"""Prove locali della logica di catena (senza toccare GitHub né lo stato)."""
import datetime, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain

def dt(*a):
    return datetime.datetime(*a)

# giovedì 12, ven 13, sab 14, dom 15, lun 16 novembre 2026
THU, FRI, SAT, SUN, MON = 12, 13, 14, 15, 16
Y, M = 2026, 11
ok = 0
fail = 0

def check(name, got, exp):
    global ok, fail
    if got == exp:
        ok += 1
        return
    fail += 1
    print(f"FAIL {name}: ottenuto {got!r}, atteso {exp!r}")

def check_plan(name, now, minutes, action, then, wake=None):
    p = chain.wait_plan(now, minutes)
    check(f"{name}.action", p["action"], action)
    check(f"{name}.then", p["then"], then)
    if wake is not None:
        check(f"{name}.wake", p["wake"], wake)

# --- next_weekday_open ---
check("open gio 22:26", chain.next_weekday_open(dt(Y,M,THU,22,26)), dt(Y,M,FRI,7,10))
check("open ven 03:00", chain.next_weekday_open(dt(Y,M,FRI,3,0)), dt(Y,M,FRI,7,10))
check("open ven 07:10", chain.next_weekday_open(dt(Y,M,FRI,7,10)), dt(Y,M,FRI,7,10))
check("open ven 07:11", chain.next_weekday_open(dt(Y,M,FRI,7,11)), dt(Y,M,MON,7,10))
check("open ven 22:26", chain.next_weekday_open(dt(Y,M,FRI,22,26)), dt(Y,M,MON,7,10))
check("open sab 12:00", chain.next_weekday_open(dt(Y,M,SAT,12,0)), dt(Y,M,MON,7,10))
check("open dom 23:00", chain.next_weekday_open(dt(Y,M,SUN,23,0)), dt(Y,M,MON,7,10))
check("open lun 06:00", chain.next_weekday_open(dt(Y,M,MON,6,0)), dt(Y,M,MON,7,10))
check("open lun 07:10", chain.next_weekday_open(dt(Y,M,MON,7,10)), dt(Y,M,MON,7,10))
check("open mer 10:00", chain.next_weekday_open(dt(Y,M,11,10,0)), dt(Y,M,12,7,10))  # mer 11 -> gio 12

# --- in_overnight_window ---
check("win gio 22:25", chain.in_overnight_window(dt(Y,M,THU,22,25)), True)
check("win gio 22:24", chain.in_overnight_window(dt(Y,M,THU,22,24)), False)
check("win gio 15:00", chain.in_overnight_window(dt(Y,M,THU,15,0)), False)
check("win ven 03:00", chain.in_overnight_window(dt(Y,M,FRI,3,0)), True)
check("win ven 07:09", chain.in_overnight_window(dt(Y,M,FRI,7,9)), True)
check("win ven 07:10", chain.in_overnight_window(dt(Y,M,FRI,7,10)), False)
check("win ven 22:25", chain.in_overnight_window(dt(Y,M,FRI,22,25)), False)
check("win sab 03:00", chain.in_overnight_window(dt(Y,M,SAT,3,0)), False)
check("win dom 23:00", chain.in_overnight_window(dt(Y,M,SUN,23,0)), False)
check("win lun 03:00", chain.in_overnight_window(dt(Y,M,MON,3,0)), True)

# --- should_start_session ---
check("start ven 07:10", chain.should_start_session(dt(Y,M,FRI,7,10)), True)
check("start ven 07:09", chain.should_start_session(dt(Y,M,FRI,7,9)), False)
check("start ven 22:24", chain.should_start_session(dt(Y,M,FRI,22,24)), True)
check("start ven 22:25", chain.should_start_session(dt(Y,M,FRI,22,25)), False)
check("start sab 10:00", chain.should_start_session(dt(Y,M,SAT,10,0)), False)

# --- wait_plan ---
# gio 22:26 + 340 min = ven 04:06, -6 = ven 04:00, poi altro wait
check_plan("plan gio 22:26/340", dt(Y,M,THU,22,26), 340, "sleep", "wait", dt(Y,M,FRI,4,0))
check_plan("plan ven 04:00/340", dt(Y,M,FRI,4,0), 340, "sleep", "session", dt(Y,M,FRI,7,10))
check_plan("plan ven 07:10", dt(Y,M,FRI,7,10), 340, "dispatch", "session")
check_plan("plan ven 22:26", dt(Y,M,FRI,22,26), 340, "exit", None)
check_plan("plan sab 12:00", dt(Y,M,SAT,12,0), 340, "exit", None)
check_plan("plan lun 06:00/340", dt(Y,M,MON,6,0), 340, "sleep", "session", dt(Y,M,MON,7,10))
# minuti corti: dopo 1 minuto ancora notte -> dispatch wait (il default del successivo è 340)
check_plan("plan gio 22:26/1", dt(Y,M,THU,22,26), 1, "sleep", "wait", dt(Y,M,THU,22,27))

# --- next_after_session ---
check("after mer intra", chain.next_after_session(dt(Y,M,11,17,30), True), "session")
check("after gio 22:25", chain.next_after_session(dt(Y,M,THU,22,25), False), "wait")
check("after gio 22:19", chain.next_after_session(dt(Y,M,THU,22,19), False), "wait")
check("after ven 22:25", chain.next_after_session(dt(Y,M,FRI,22,25), False), None)

print(f"{ok} ok, {fail} falliti")
sys.exit(1 if fail else 0)
