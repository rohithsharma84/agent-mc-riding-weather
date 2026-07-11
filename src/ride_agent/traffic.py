"""Google Routes API (computeRoutes) client: predicted-traffic duration,
congestion scoring, and closure detection for a single named route.
"""

from __future__ import annotations

import re
from datetime import datetime

import requests

from ride_agent.config import LocationConfig, RouteConfig, ThresholdsConfig
from ride_agent.models import RouteAssessment

COMPUTE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = (
    "routes.duration,routes.staticDuration,routes.distanceMeters,"
    "routes.description,routes.warnings,routes.travelAdvisory"
)

_CLOSURE_PATTERN = re.compile(r"\bclos(e|ed|ure)\b", re.IGNORECASE)


def _waypoint_to_google(waypoint: dict) -> dict:
    if "lat" in waypoint and "lon" in waypoint:
        return {"location": {"latLng": {"latitude": waypoint["lat"], "longitude": waypoint["lon"]}}}
    return {"address": waypoint["address"]}


def _location_to_google(loc: LocationConfig) -> dict:
    return {"location": {"latLng": {"latitude": loc.lat, "longitude": loc.lon}}}


def _parse_duration_seconds(duration_str: str) -> float:
    # Google returns durations as e.g. "1234s"
    return float(duration_str.rstrip("s"))


def assess_route(
    origin: LocationConfig,
    destination: LocationConfig,
    route: RouteConfig,
    direction: str,
    departure_time: datetime,
    thresholds: ThresholdsConfig,
    api_key: str,
) -> RouteAssessment:
    body = {
        "origin": _location_to_google(origin),
        "destination": _location_to_google(destination),
        "intermediates": [_waypoint_to_google(w) for w in route.waypoints],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "departureTime": departure_time.isoformat(),
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    resp = requests.post(COMPUTE_ROUTES_URL, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    routes = data.get("routes", [])
    if not routes:
        return RouteAssessment(
            name=route.name,
            direction=direction,
            duration_min=float("inf"),
            static_duration_min=float("inf"),
            congestion_ratio=float("inf"),
            congestion_level="HEAVY",
            warnings=["No route returned by Google Maps"],
            is_closed=True,
        )

    r = routes[0]
    duration_s = _parse_duration_seconds(r["duration"])
    static_duration_s = _parse_duration_seconds(r.get("staticDuration", r["duration"]))
    ratio = duration_s / static_duration_s if static_duration_s else 1.0

    if ratio >= thresholds.congestion_heavy:
        level = "HEAVY"
    elif ratio >= thresholds.congestion_moderate:
        level = "MODERATE"
    else:
        level = "LIGHT"

    warnings = list(r.get("warnings", []))
    advisory = r.get("travelAdvisory", {})
    closure_warnings = advisory.get("closures", [])
    if closure_warnings:
        warnings.append("Road closures reported on this route")

    is_closed = bool(closure_warnings) or any(_CLOSURE_PATTERN.search(w) for w in warnings)

    return RouteAssessment(
        name=route.name,
        direction=direction,
        duration_min=duration_s / 60,
        static_duration_min=static_duration_s / 60,
        congestion_ratio=ratio,
        congestion_level=level,
        warnings=warnings,
        is_closed=is_closed,
    )
