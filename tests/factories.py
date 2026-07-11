from __future__ import annotations

from datetime import datetime, timezone

from ride_agent.config import ThresholdsConfig
from ride_agent.models import LegVerdict, RideVerdict, RouteAssessment, RunResult, Verdict, WindowForecast


def make_thresholds(**overrides) -> ThresholdsConfig:
    defaults = dict(
        temp_min_f=65,
        temp_max_f=95,
        pop_rain_gear=0.20,
        pop_no_go=0.60,
        congestion_moderate=1.15,
        congestion_heavy=1.40,
    )
    defaults.update(overrides)
    return ThresholdsConfig(**defaults)


def make_forecast(
    label: str = "morning",
    temp_min_f: float = 70,
    temp_max_f: float = 80,
    pop_max: float = 0.0,
    conditions: list[str] | None = None,
    has_rain_forecast: bool = False,
) -> WindowForecast:
    return WindowForecast(
        label=label,
        start=datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
        end=datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),
        temp_min_f=temp_min_f,
        temp_max_f=temp_max_f,
        pop_max=pop_max,
        conditions=conditions or ["Clear"],
        has_rain_forecast=has_rain_forecast,
    )


def make_route(
    name: str = "Route A",
    direction: str = "to_work",
    duration_min: float = 30,
    static_duration_min: float = 28,
    is_closed: bool = False,
    warnings: list[str] | None = None,
) -> RouteAssessment:
    ratio = duration_min / static_duration_min if static_duration_min else 1.0
    if ratio >= 1.40:
        level = "HEAVY"
    elif ratio >= 1.15:
        level = "MODERATE"
    else:
        level = "LIGHT"
    return RouteAssessment(
        name=name,
        direction=direction,
        duration_min=duration_min,
        static_duration_min=static_duration_min,
        congestion_ratio=ratio,
        congestion_level=level,
        warnings=warnings or [],
        is_closed=is_closed,
    )


def make_run_result(
    mode: str = "night_before",
    target_office_day: str = "2024-01-15",
    overall: Verdict = Verdict.GO,
    morning_forecast: WindowForecast | None = None,
    evening_forecast: WindowForecast | None = None,
    routes: list[RouteAssessment] | None = None,
    best_route_to_work: str | None = "Route A",
    best_route_to_home: str | None = "Route A",
) -> RunResult:
    morning_forecast = morning_forecast or make_forecast(label="morning")
    evening_forecast = evening_forecast or make_forecast(label="evening")
    routes = routes if routes is not None else [make_route(direction="to_work"), make_route(direction="to_home")]
    return RunResult(
        mode=mode,
        run_at=datetime(2024, 1, 14, 22, 0, tzinfo=timezone.utc),
        target_office_day=target_office_day,
        verdict=RideVerdict(
            overall=overall,
            legs=[
                LegVerdict(leg="morning", verdict=overall, reasons=[]),
                LegVerdict(leg="evening", verdict=overall, reasons=[]),
            ],
            reasons=[],
        ),
        morning_forecast=morning_forecast,
        evening_forecast=evening_forecast,
        routes=routes,
        best_route_to_work=best_route_to_work,
        best_route_to_home=best_route_to_home,
    )
