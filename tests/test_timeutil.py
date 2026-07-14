from __future__ import annotations

from datetime import date

from ride_agent.timeutil import commute_windows, get_zone, is_office_day

ET = get_zone("America/New_York")
OFFICE_DAYS = ["MON", "TUE", "WED"]


def test_is_office_day_true_for_configured_weekday():
    assert is_office_day(date(2024, 1, 15), OFFICE_DAYS)  # Monday
    assert is_office_day(date(2024, 1, 17), OFFICE_DAYS)  # Wednesday


def test_is_office_day_false_for_other_weekdays():
    assert not is_office_day(date(2024, 1, 18), OFFICE_DAYS)  # Thursday
    assert not is_office_day(date(2024, 1, 13), OFFICE_DAYS)  # Saturday


def test_commute_windows_returns_aware_utc_datetimes():
    morning_start, morning_end, evening_start, evening_end = commute_windows(
        date(2024, 1, 15), ET, "08:30", 60, "17:30", 60
    )
    assert morning_start.tzinfo is not None
    assert (morning_end - morning_start).total_seconds() == 60 * 60
    assert (evening_end - evening_start).total_seconds() == 60 * 60
    assert morning_start < evening_start
