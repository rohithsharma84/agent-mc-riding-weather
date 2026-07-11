"""OpenWeatherMap client: free 5-day/3-hour forecast, mapped onto commute windows.

Isolated behind `extract_window` so that upgrading to the paid One Call 3.0
API (hourly forecast + `pop`) later only requires changing `fetch_forecast`
and the bucket-shape it hands to `extract_window`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests

from ride_agent.models import WindowForecast

FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
BUCKET_HOURS = 3

# OWM condition-code first digit -> "counts as rain/snow for ride purposes"
_RAIN_LIKE_GROUPS = {2, 3, 5, 6}  # thunderstorm, drizzle, rain, snow


def fetch_forecast(lat: float, lon: float, api_key: str) -> dict:
    resp = requests.get(
        FORECAST_URL,
        params={"lat": lat, "lon": lon, "units": "imperial", "appid": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def extract_window(raw: dict, label: str, window_start: datetime, window_end: datetime) -> WindowForecast:
    """Aggregate all 3-hour buckets that overlap [window_start, window_end) into one forecast."""
    bucket_span = timedelta(hours=BUCKET_HOURS)
    overlapping = []
    for bucket in raw.get("list", []):
        bucket_start = datetime.fromtimestamp(bucket["dt"], tz=timezone.utc)
        bucket_end = bucket_start + bucket_span
        if bucket_start < window_end and bucket_end > window_start:
            overlapping.append(bucket)

    if not overlapping:
        raise ValueError(
            f"No forecast buckets overlap the {label} window "
            f"{window_start.isoformat()}..{window_end.isoformat()} "
            "(window is likely more than 5 days out)"
        )

    temp_min = min(b["main"]["temp_min"] for b in overlapping)
    temp_max = max(b["main"]["temp_max"] for b in overlapping)
    pop_max = max(b.get("pop", 0.0) for b in overlapping)

    conditions: list[str] = []
    has_rain_forecast = False
    for bucket in overlapping:
        for w in bucket.get("weather", []):
            conditions.append(w.get("main", "Unknown"))
            if w.get("id", 0) // 100 in _RAIN_LIKE_GROUPS:
                has_rain_forecast = True

    return WindowForecast(
        label=label,
        start=window_start,
        end=window_end,
        temp_min_f=temp_min,
        temp_max_f=temp_max,
        pop_max=pop_max,
        conditions=sorted(set(conditions)),
        has_rain_forecast=has_rain_forecast,
    )
