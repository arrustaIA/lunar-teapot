#!/usr/bin/env python3
"""Unit tests for scan.stale_preopen_watchlist (no market data, no files written)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import scan

ROME = ZoneInfo("Europe/Rome")

def _wl(created):
    return {"created": created, "items": [{"ticker": "SAP.DE"}]}

def test_preopen_list_is_kept_before_0935():
    n = datetime(2026, 11, 13, 7, 30, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T07:30:16+01:00"), n) is False

def test_preopen_list_is_rebuilt_at_official_scan():
    n = datetime(2026, 11, 13, 9, 35, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T07:30:16+01:00"), n) is True

def test_preopen_list_is_rebuilt_later_in_the_day():
    n = datetime(2026, 11, 13, 15, 0, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T07:30:16+01:00"), n) is True

def test_official_list_is_kept():
    n = datetime(2026, 11, 13, 9, 35, 11, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T09:35:11+01:00"), n) is False
    later = datetime(2026, 11, 13, 16, 0, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T09:35:11+01:00"), later) is False

def test_naive_created_treated_as_rome():
    n = datetime(2026, 11, 13, 9, 35, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T07:30:16"), n) is True
    assert scan.stale_preopen_watchlist(_wl("2026-11-13T09:35:00"), n) is False

def test_missing_or_bad_created_is_rebuilt_after_0935():
    n = datetime(2026, 11, 13, 9, 35, tzinfo=ROME)
    assert scan.stale_preopen_watchlist({"items": []}, n) is True
    assert scan.stale_preopen_watchlist(_wl("not-a-timestamp"), n) is True

def test_empty_watchlist():
    n = datetime(2026, 11, 13, 9, 35, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(None, n) is False

def test_previous_day_list_is_stale():
    n = datetime(2026, 11, 13, 9, 35, tzinfo=ROME)
    assert scan.stale_preopen_watchlist(_wl("2026-11-12T09:35:11+01:00"), n) is True

if __name__ == "__main__":
    import sys
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok  {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL {name}: {e}")
            except Exception as e:
                failed += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)
