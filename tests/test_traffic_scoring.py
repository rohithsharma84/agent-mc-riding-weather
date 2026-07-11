from __future__ import annotations

from datetime import datetime, timezone

import responses

from ride_agent.config import LocationConfig, RouteConfig
from ride_agent.traffic import COMPUTE_ROUTES_URL, assess_route
from tests.factories import make_thresholds

ORIGIN = LocationConfig(label="Home", address="1 Home St", lat=40.0, lon=-74.0)
DEST = LocationConfig(label="Work", address="1 Work St", lat=40.1, lon=-74.1)
ROUTE = RouteConfig(name="Route A", waypoints=[])
DEPARTURE = datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc)


def _mock_response(duration_s, static_duration_s, warnings=None, closures=None):
    responses.add(
        responses.POST,
        COMPUTE_ROUTES_URL,
        json={
            "routes": [
                {
                    "duration": f"{duration_s}s",
                    "staticDuration": f"{static_duration_s}s",
                    "distanceMeters": 10000,
                    "warnings": warnings or [],
                    "travelAdvisory": {"closures": closures or []},
                }
            ]
        },
        status=200,
    )


@responses.activate
def test_light_congestion():
    _mock_response(1000, 1000)
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.congestion_level == "LIGHT"
    assert result.congestion_ratio == 1.0
    assert result.is_closed is False


@responses.activate
def test_moderate_congestion():
    _mock_response(1200, 1000)
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.congestion_level == "MODERATE"


@responses.activate
def test_heavy_congestion():
    _mock_response(1500, 1000)
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.congestion_level == "HEAVY"


@responses.activate
def test_closure_via_travel_advisory():
    _mock_response(1000, 1000, closures=[{"description": "I-95 closed"}])
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.is_closed is True


@responses.activate
def test_closure_via_warning_text():
    _mock_response(1000, 1000, warnings=["Route includes a road closure"])
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.is_closed is True


@responses.activate
def test_no_routes_returned_marks_closed():
    responses.add(responses.POST, COMPUTE_ROUTES_URL, json={"routes": []}, status=200)
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.is_closed is True
    assert result.congestion_level == "HEAVY"


@responses.activate
def test_non_closure_warning_does_not_mark_closed():
    _mock_response(1000, 1000, warnings=["Unpaved road ahead"])
    result = assess_route(ORIGIN, DEST, ROUTE, "to_work", DEPARTURE, make_thresholds(), "fake-key")
    assert result.is_closed is False
    assert result.warnings == ["Unpaved road ahead"]
