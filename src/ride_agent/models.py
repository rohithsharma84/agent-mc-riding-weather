"""Shared data models used across the ride-agent pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Verdict(str, Enum):
    GO = "GO"
    GO_WITH_RAIN_GEAR = "GO_WITH_RAIN_GEAR"
    NO_GO = "NO_GO"

    @staticmethod
    def worst_of(verdicts: list["Verdict"]) -> "Verdict":
        """Combine per-leg verdicts: NO_GO beats GEAR beats GO."""
        if Verdict.NO_GO in verdicts:
            return Verdict.NO_GO
        if Verdict.GO_WITH_RAIN_GEAR in verdicts:
            return Verdict.GO_WITH_RAIN_GEAR
        return Verdict.GO


class WindowForecast(BaseModel):
    label: str  # "morning" | "evening"
    start: datetime
    end: datetime
    temp_min_f: float
    temp_max_f: float
    pop_max: float  # 0.0-1.0, max probability of precipitation across overlapping buckets
    conditions: list[str]  # OWM condition names seen in overlapping buckets
    has_rain_forecast: bool


class RouteAssessment(BaseModel):
    name: str
    direction: str  # "to_work" | "to_home"
    duration_min: float
    static_duration_min: float
    congestion_ratio: float
    congestion_level: str  # "LIGHT" | "MODERATE" | "HEAVY"
    warnings: list[str]
    is_closed: bool


class LegVerdict(BaseModel):
    leg: str  # "morning" | "evening"
    verdict: Verdict
    reasons: list[str]


class RideVerdict(BaseModel):
    overall: Verdict
    legs: list[LegVerdict]
    reasons: list[str]  # flattened, for convenience


class Narrative(BaseModel):
    subject_line: str
    summary_paragraph: str
    weather_notes: str
    traffic_notes: str
    route_recommendation_reasoning: str
    changes_since_last_night: str | None = None
    gear_tips: str | None = None


class Change(BaseModel):
    description: str


class RunResult(BaseModel):
    mode: str  # "night_before" | "morning"
    run_at: datetime
    target_office_day: str  # ISO date of the office day this run is about
    verdict: RideVerdict
    morning_forecast: WindowForecast
    evening_forecast: WindowForecast
    routes: list[RouteAssessment]
    best_route_to_work: str | None
    best_route_to_home: str | None
    narrative: Narrative | None = None
