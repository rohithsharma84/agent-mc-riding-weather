"""Render the ride-check email and send it via Resend."""

from __future__ import annotations

from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ride_agent.models import Narrative, RideVerdict, RouteAssessment, WindowForecast

RESEND_URL = "https://api.resend.com/emails"

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)
_env.filters["localtime"] = lambda dt, tz: dt.astimezone(tz)


def render(
    mode: str,
    run_at,
    tz,
    verdict: RideVerdict,
    morning_forecast: WindowForecast,
    evening_forecast: WindowForecast,
    routes: list[RouteAssessment],
    best_route_to_work: str | None,
    best_route_to_home: str | None,
    narrative: Narrative,
) -> tuple[str, str]:
    template = _env.get_template("email.html.j2")
    html = template.render(
        mode=mode,
        run_at=run_at,
        tz=tz,
        verdict=verdict,
        morning_forecast=morning_forecast,
        evening_forecast=evening_forecast,
        routes=routes,
        best_route_to_work=best_route_to_work,
        best_route_to_home=best_route_to_home,
        narrative=narrative,
    )
    return narrative.subject_line, html


def send(subject: str, html: str, to: str, from_: str, api_key: str) -> None:
    resp = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": from_, "to": [to], "subject": subject, "html": html},
        timeout=15,
    )
    resp.raise_for_status()
