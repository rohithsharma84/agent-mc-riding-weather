"""Target-day resolution, including the GitHub Actions delay edge case.

The night_before slot is scheduled for ~9pm ET but the hosted cron can be
delayed hours, sometimes past local midnight. The target office day must stay
correct either way, so a delayed run does not fire a day too early.
"""

from __future__ import annotations

from datetime import date, datetime

from ride_agent.main import _target_day_for_mode
from ride_agent.timeutil import get_zone

ET = get_zone("America/New_York")


def test_night_before_on_time_targets_tomorrow():
    # Saturday 9:15pm ET -> targets Sunday.
    now = datetime(2026, 7, 18, 21, 15, tzinfo=ET)
    assert _target_day_for_mode("night_before", None, now) == date(2026, 7, 19)


def test_night_before_delayed_past_midnight_targets_same_day():
    # The Saturday 9:15pm run delayed to 12:35am Sunday must still target Sunday,
    # not Monday. This is the reported bug (a "Saturday night" email for Monday).
    now = datetime(2026, 7, 19, 0, 35, tzinfo=ET)
    assert _target_day_for_mode("night_before", None, now) == date(2026, 7, 19)


def test_night_before_delayed_sunday_run_targets_monday():
    # The Sunday 9:15pm run delayed to 12:35am Monday still targets Monday.
    now = datetime(2026, 7, 20, 0, 35, tzinfo=ET)
    assert _target_day_for_mode("night_before", None, now) == date(2026, 7, 20)


def test_morning_targets_today():
    now = datetime(2026, 7, 20, 6, 15, tzinfo=ET)  # Monday morning
    assert _target_day_for_mode("morning", None, now) == date(2026, 7, 20)


def test_explicit_date_arg_wins():
    now = datetime(2026, 7, 20, 6, 15, tzinfo=ET)
    assert _target_day_for_mode("morning", "2026-07-22", now) == date(2026, 7, 22)
