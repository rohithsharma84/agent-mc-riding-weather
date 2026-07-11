from __future__ import annotations

from datetime import date, datetime

from ride_agent.timeutil import commute_windows, get_zone, resolve_run

OFFICE_DAYS = ["MON", "TUE", "WED"]
ET = get_zone("America/New_York")


def _local(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=ET)


def test_sunday_night_maps_to_monday_night_before():
    # Sunday 2024-01-14, 22:00 -> night_before targeting Monday 2024-01-15
    plan = resolve_run(_local(2024, 1, 14, 22, 0), OFFICE_DAYS)
    assert plan is not None
    assert plan.mode == "night_before"
    assert plan.target_office_day == date(2024, 1, 15)


def test_monday_night_maps_to_tuesday_night_before():
    plan = resolve_run(_local(2024, 1, 15, 22, 0), OFFICE_DAYS)
    assert plan is not None
    assert plan.mode == "night_before"
    assert plan.target_office_day == date(2024, 1, 16)


def test_wednesday_night_has_no_night_before_since_thursday_is_not_office_day():
    plan = resolve_run(_local(2024, 1, 17, 22, 0), OFFICE_DAYS)
    assert plan is None


def test_monday_morning_is_morning_mode():
    plan = resolve_run(_local(2024, 1, 15, 7, 0), OFFICE_DAYS)
    assert plan is not None
    assert plan.mode == "morning"
    assert plan.target_office_day == date(2024, 1, 15)


def test_saturday_morning_is_not_scheduled():
    plan = resolve_run(_local(2024, 1, 13, 7, 0), OFFICE_DAYS)
    assert plan is None


def test_late_fire_within_tolerance_still_matches():
    # cron jitter: fires at 07:40 instead of 07:00
    plan = resolve_run(_local(2024, 1, 15, 7, 40), OFFICE_DAYS)
    assert plan is not None
    assert plan.mode == "morning"


def test_fire_outside_tolerance_does_not_match():
    plan = resolve_run(_local(2024, 1, 15, 9, 0), OFFICE_DAYS)
    assert plan is None


def test_night_fire_within_tolerance():
    plan = resolve_run(_local(2024, 1, 14, 23, 20), OFFICE_DAYS)
    assert plan is not None
    assert plan.mode == "night_before"


def test_around_spring_forward_dst_boundary():
    # 2024-03-10 is the US spring-forward date; Sunday 2024-03-10 22:00 ET
    # should still correctly target Monday 2024-03-11 regardless of the
    # UTC-offset shift that happened earlier that day.
    plan = resolve_run(_local(2024, 3, 10, 22, 0), OFFICE_DAYS)
    assert plan is not None
    assert plan.target_office_day == date(2024, 3, 11)


def test_around_fall_back_dst_boundary():
    # 2024-11-03 is the US fall-back date.
    plan = resolve_run(_local(2024, 11, 3, 7, 0), OFFICE_DAYS)
    assert plan is None  # Sunday is not an office day


def test_commute_windows_returns_aware_utc_datetimes():
    morning_start, morning_end, evening_start, evening_end = commute_windows(
        date(2024, 1, 15), ET, "08:30", 60, "17:30", 60
    )
    assert morning_start.tzinfo is not None
    assert morning_end - morning_start == morning_end - morning_start  # sanity
    assert (morning_end - morning_start).total_seconds() == 60 * 60
    assert (evening_end - evening_start).total_seconds() == 60 * 60
    assert morning_start < evening_start
