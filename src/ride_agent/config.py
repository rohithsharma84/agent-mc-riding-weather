"""Load and validate config.yaml plus required environment variables."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class LocationConfig(BaseModel):
    label: str
    address: str
    lat: float
    lon: float


class RouteConfig(BaseModel):
    name: str
    waypoints: list[dict] = []


class CommuteLegConfig(BaseModel):
    depart: str  # "HH:MM"
    window_minutes: int


class CommuteConfig(BaseModel):
    morning: CommuteLegConfig
    evening: CommuteLegConfig


class ThresholdsConfig(BaseModel):
    temp_min_f: float
    temp_max_f: float
    pop_rain_gear: float
    pop_no_go: float
    congestion_moderate: float
    congestion_heavy: float


class EmailConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    to: str
    from_: str = Field(alias="from")


class Config(BaseModel):
    timezone: str
    office_days: list[str]  # e.g. ["MON", "TUE", "WED"] — which days you ride in
    commute: CommuteConfig
    locations: dict[str, LocationConfig]
    routes: dict[str, list[RouteConfig]]
    thresholds: ThresholdsConfig
    email: EmailConfig

    # secrets, populated from environment, not from the yaml file
    openai_api_key: str
    openai_model_name: str
    openweather_api_key: str
    google_maps_api_key: str
    resend_api_key: str


def load_config(path: str | Path = "config.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    missing = [
        name
        for name in (
            "OPENAI_API_KEY",
            "OPENAI_MODEL_NAME",
            "OPENWEATHERAPP_API_KEY",
            "GOOGLE_MAPS_API_KEY",
            "RESEND_API_KEY",
        )
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        **raw,
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_model_name=os.environ["OPENAI_MODEL_NAME"],
        openweather_api_key=os.environ["OPENWEATHERAPP_API_KEY"],
        google_maps_api_key=os.environ["GOOGLE_MAPS_API_KEY"],
        resend_api_key=os.environ["RESEND_API_KEY"],
    )
