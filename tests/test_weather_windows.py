from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ride_agent.weather import extract_window


def _bucket(dt_unix, temp_min, temp_max, pop, weather_id, weather_main):
    return {
        "dt": dt_unix,
        "main": {"temp_min": temp_min, "temp_max": temp_max},
        "pop": pop,
        "weather": [{"id": weather_id, "main": weather_main}],
    }


def _ts(y, m, d, h):
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())


def test_single_bucket_exact_overlap():
    raw = {
        "list": [
            _bucket(_ts(2024, 1, 15, 12), 68, 74, 0.1, 800, "Clear"),
        ]
    }
    window_start = datetime(2024, 1, 15, 13, tzinfo=timezone.utc)
    window_end = datetime(2024, 1, 15, 14, tzinfo=timezone.utc)

    result = extract_window(raw, "morning", window_start, window_end)

    assert result.temp_min_f == 68
    assert result.temp_max_f == 74
    assert result.pop_max == 0.1
    assert result.has_rain_forecast is False
    assert result.conditions == ["Clear"]


def test_window_spanning_two_buckets_aggregates():
    raw = {
        "list": [
            _bucket(_ts(2024, 1, 15, 12), 60, 65, 0.1, 800, "Clear"),
            _bucket(_ts(2024, 1, 15, 15), 66, 72, 0.4, 500, "Rain"),
        ]
    }
    # window overlaps both the [12,15) and [15,18) buckets
    window_start = datetime(2024, 1, 15, 14, tzinfo=timezone.utc)
    window_end = datetime(2024, 1, 15, 16, tzinfo=timezone.utc)

    result = extract_window(raw, "evening", window_start, window_end)

    assert result.temp_min_f == 60
    assert result.temp_max_f == 72
    assert result.pop_max == 0.4
    assert result.has_rain_forecast is True
    assert set(result.conditions) == {"Clear", "Rain"}


@pytest.mark.parametrize(
    "weather_id,expected_rain",
    [
        (200, True),  # thunderstorm
        (300, True),  # drizzle
        (500, True),  # rain
        (600, True),  # snow
        (800, False),  # clear
        (801, False),  # few clouds
    ],
)
def test_rain_like_condition_groups(weather_id, expected_rain):
    raw = {"list": [_bucket(_ts(2024, 1, 15, 12), 70, 75, 0.0, weather_id, "X")]}
    window_start = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
    window_end = datetime(2024, 1, 15, 13, tzinfo=timezone.utc)

    result = extract_window(raw, "morning", window_start, window_end)

    assert result.has_rain_forecast is expected_rain


def test_no_overlapping_bucket_raises():
    raw = {"list": [_bucket(_ts(2024, 1, 15, 12), 70, 75, 0.0, 800, "Clear")]}
    window_start = datetime(2024, 1, 20, 12, tzinfo=timezone.utc)
    window_end = datetime(2024, 1, 20, 13, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        extract_window(raw, "morning", window_start, window_end)
