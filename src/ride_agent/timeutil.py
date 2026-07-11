"""Local-time scheduling gate and commute-window computation.

GitHub Actions cron fires in UTC and can't express "22:00 America/New_York"
across a DST boundary, and it fires with several minutes of jitter. Instead of
trying to get the cron expression exactly right, the workflow fires at every
plausible UTC time and this module decides, in local Eastern time, whether
the current run is actually a scheduled slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

NIGHT_HOUR_START = 22
NIGHT_HOUR_TOLERANCE_MIN = 90  # accept 22:00-23:29 local
MORNING_HOUR_START = 7
MORNING_HOUR_TOLERANCE_MIN = 75  # accept 07:00-08:14 local


@dataclass(frozen=True)
class RunPlan:
    mode: str  # "night_before" | "morning"
    target_office_day: date


def get_zone(tz_name: str) -> ZoneInfo:
    return ZoneInfo(tz_name)


def _within_tolerance(local_dt: datetime, start_hour: int, tolerance_min: int) -> bool:
    slot_start = local_dt.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    delta = (local_dt - slot_start).total_seconds() / 60
    return 0 <= delta <= tolerance_min


def resolve_run(now_local: datetime, office_days: list[str]) -> RunPlan | None:
    """Decide whether `now_local` (aware, in the target timezone) is a scheduled slot.

    - night_before: local hour is ~22:00 and *tomorrow* is an office day.
    - morning: local hour is ~07:00 and *today* is an office day.
    Returns None if neither condition holds (the caller should exit quietly).
    """
    today_code = DAY_CODES[now_local.weekday()]
    tomorrow = now_local.date() + timedelta(days=1)
    tomorrow_code = DAY_CODES[tomorrow.weekday()]

    if _within_tolerance(now_local, NIGHT_HOUR_START, NIGHT_HOUR_TOLERANCE_MIN):
        if tomorrow_code in office_days:
            return RunPlan(mode="night_before", target_office_day=tomorrow)

    if _within_tolerance(now_local, MORNING_HOUR_START, MORNING_HOUR_TOLERANCE_MIN):
        if today_code in office_days:
            return RunPlan(mode="morning", target_office_day=now_local.date())

    return None


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
