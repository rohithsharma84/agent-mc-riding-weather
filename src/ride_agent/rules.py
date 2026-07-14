"""Deterministic verdict engine. This is the safety core: the LLM never
overrides anything decided here, it only narrates it.
"""

from __future__ import annotations

from ride_agent.config import ThresholdsConfig
from ride_agent.models import LegVerdict, RideVerdict, RouteAssessment, Verdict, WindowForecast


def _classify_leg(leg_name: str, forecast: WindowForecast, thresholds: ThresholdsConfig) -> LegVerdict:
    reasons: list[str] = []
    label = leg_name.capitalize()

    if forecast.has_rain_forecast or forecast.pop_max >= thresholds.pop_no_go:
        reasons.append(
            f"{label} window: rain forecast "
            f"(conditions={forecast.conditions}, pop={forecast.pop_max:.2f} "
            f">= {thresholds.pop_no_go:.2f})"
        )
        return LegVerdict(leg=leg_name, verdict=Verdict.NO_GO, reasons=reasons)

    if forecast.temp_min_f < thresholds.temp_min_f or forecast.temp_max_f > thresholds.temp_max_f:
        reasons.append(
            f"{label} window: temperature "
            f"{forecast.temp_min_f:.1f}-{forecast.temp_max_f:.1f}F outside "
            f"{thresholds.temp_min_f:.0f}-{thresholds.temp_max_f:.0f}F range"
        )
        return LegVerdict(leg=leg_name, verdict=Verdict.NO_GO, reasons=reasons)

    if forecast.pop_max >= thresholds.pop_rain_gear:
        reasons.append(
            f"{label} window: chance of rain "
            f"(pop={forecast.pop_max:.2f} >= {thresholds.pop_rain_gear:.2f}) - bring rain gear"
        )
        return LegVerdict(leg=leg_name, verdict=Verdict.GO_WITH_RAIN_GEAR, reasons=reasons)

    reasons.append(
        f"{label} window: clear, "
        f"{forecast.temp_min_f:.0f}-{forecast.temp_max_f:.0f}F, pop={forecast.pop_max:.2f}"
    )
    return LegVerdict(leg=leg_name, verdict=Verdict.GO, reasons=reasons)


def _all_routes_closed(routes: list[RouteAssessment], direction: str) -> bool:
    leg_routes = [r for r in routes if r.direction == direction]
    return bool(leg_routes) and all(r.is_closed for r in leg_routes)


def decide(
    morning_forecast: WindowForecast,
    evening_forecast: WindowForecast,
    routes: list[RouteAssessment],
    thresholds: ThresholdsConfig,
) -> RideVerdict:
    morning_leg = _classify_leg("morning", morning_forecast, thresholds)
    evening_leg = _classify_leg("evening", evening_forecast, thresholds)

    legs = [morning_leg, evening_leg]

    if _all_routes_closed(routes, "to_work"):
        legs[0] = LegVerdict(
            leg="morning",
            verdict=Verdict.NO_GO,
            reasons=morning_leg.reasons + ["No passable route to work: all routes closed"],
        )
    if _all_routes_closed(routes, "to_home"):
        legs[1] = LegVerdict(
            leg="evening",
            verdict=Verdict.NO_GO,
            reasons=evening_leg.reasons + ["No passable route home: all routes closed"],
        )

    overall = Verdict.worst_of([leg.verdict for leg in legs])
    flattened_reasons = [r for leg in legs for r in leg.reasons]

    return RideVerdict(overall=overall, legs=legs, reasons=flattened_reasons)


def best_route(routes: list[RouteAssessment], direction: str) -> RouteAssessment | None:
    passable = [r for r in routes if r.direction == direction and not r.is_closed]
    if not passable:
        return None
    return min(passable, key=lambda r: r.duration_min)
