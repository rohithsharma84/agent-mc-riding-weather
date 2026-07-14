"""Office-day check and commute-window computation.

Which *slot* runs (night_before vs morning) is decided by the GitHub Actions
cron schedule and passed explicitly to `--mode`. Which *days* count as office
days stays private in config.yaml, so the crons fire every day and this module
filters to the configured office days — a plain weekday-membership test, with no
timezone tolerance math (the mode already tells us which slot fired).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def get_zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def is_office_day(day: date, office_days: list[str]) -> bool:
    """True if `day`'s weekday is one of the configured office-day codes."""
    return DAY_CODES[day.weekday()] in office_days


def commute_windows(
    target_office_day: date,
    tz: ZoneInfo,
    morning_depart: str,
    morning_window_minutes: int,
    evening_depart: str,
    evening_window_minutes: int,
) -> tuple[datetime, datetime, datetime, datetime]:
    """Return (morning_start, morning_end, evening_start, evening_end), all aware UTC."""

    def _window(depart_str: str, window_minutes: int) -> tuple[datetime, datetime]:
        h, m = (int(x) for x in depart_str.split(":"))
        start_local = datetime.combine(target_office_day, time(h, m), tzinfo=tz)
        end_local = start_local + timedelta(minutes=window_minutes)
        return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))

    morning_start, morning_end = _window(morning_depart, morning_window_minutes)
    evening_start, evening_end = _window(evening_depart, evening_window_minutes)
    return morning_start, morning_end, evening_start, evening_end
