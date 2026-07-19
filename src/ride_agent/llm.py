"""LLM narrative synthesis.

Exactly one OpenAI structured-output call per run. The verdict has already
been decided by rules.py and is passed in as a fixed fact the model is told
not to change — its only job is to explain the data and write the email
copy. If the call fails for any reason, `fallback_narrative` produces a
plain but complete narrative from the same data so the email still sends.
"""

from __future__ import annotations

import json
import logging

from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

from ride_agent.models import Change, Narrative, RideVerdict, RouteAssessment, WindowForecast

logger = logging.getLogger(__name__)

_SCHEMA = {
    "name": "ride_narrative",
    "schema": {
        "type": "object",
        "properties": {
            "subject_line": {"type": "string"},
            "summary_paragraph": {"type": "string"},
            "weather_notes": {"type": "string"},
            "traffic_notes": {"type": "string"},
            "route_recommendation_reasoning": {"type": "string"},
            "changes_since_last_night": {"type": ["string", "null"]},
            "gear_tips": {"type": ["string", "null"]},
        },
        "required": [
            "subject_line",
            "summary_paragraph",
            "weather_notes",
            "traffic_notes",
            "route_recommendation_reasoning",
            "changes_since_last_night",
            "gear_tips",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}


def _build_payload(
    mode: str,
    verdict: RideVerdict,
    morning_forecast: WindowForecast,
    evening_forecast: WindowForecast,
    routes: list[RouteAssessment],
    best_route_to_work: str | None,
    best_route_to_home: str | None,
    changes: list[Change],
) -> dict:
    return {
        "mode": mode,
        "verdict": verdict.model_dump(mode="json"),
        "morning_forecast": morning_forecast.model_dump(mode="json"),
        "evening_forecast": evening_forecast.model_dump(mode="json"),
        "routes": [r.model_dump(mode="json") for r in routes],
        "best_route_to_work": best_route_to_work,
        "best_route_to_home": best_route_to_home,
        "changes_since_last_night": [c.description for c in changes],
    }


@traceable(run_type="chain", name="synthesize_narrative")
def synthesize(
    mode: str,
    verdict: RideVerdict,
    morning_forecast: WindowForecast,
    evening_forecast: WindowForecast,
    routes: list[RouteAssessment],
    best_route_to_work: str | None,
    best_route_to_home: str | None,
    changes: list[Change],
    api_key: str,
    model: str,
) -> Narrative:
    payload = _build_payload(
        mode,
        verdict,
        morning_forecast,
        evening_forecast,
        routes,
        best_route_to_work,
        best_route_to_home,
        changes,
    )

    try:
        # wrap_openai adds a LangSmith span for the chat completion call. When
        # tracing is disabled (no LANGSMITH_API_KEY) the wrapper is a no-op.
        client = wrap_openai(OpenAI(api_key=api_key))
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write a short, friendly daily email for a motorcycle commuter. "
                        f"The ride verdict is already decided: {verdict.overall.value}. "
                        "Do not contradict or second-guess it - your job is to explain the "
                        "weather and traffic data behind it, recommend the best route each way, "
                        "and (in morning mode) summarize what changed since last night's email. "
                        "Keep each field to 1-3 sentences. If changes_since_last_night is empty "
                        "and mode is 'morning', write a short confirmation that nothing changed. "
                        "If mode is 'night_before', set changes_since_last_night to null."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_schema", "json_schema": _SCHEMA},
        )
        data = json.loads(completion.choices[0].message.content)
        return Narrative(**data)
    except Exception:
        logger.exception("LLM narrative synthesis failed; falling back to template narrative")
        return fallback_narrative(
            mode, verdict, morning_forecast, evening_forecast, best_route_to_work, best_route_to_home, changes
        )


def fallback_narrative(
    mode: str,
    verdict: RideVerdict,
    morning_forecast: WindowForecast,
    evening_forecast: WindowForecast,
    best_route_to_work: str | None,
    best_route_to_home: str | None,
    changes: list[Change],
) -> Narrative:
    verdict_text = {
        "GO": "Good day to ride.",
        "GO_WITH_RAIN_GEAR": "Rideable, but bring rain gear.",
        "NO_GO": "Not a good day to ride.",
    }[verdict.overall.value]

    return Narrative(
        subject_line=f"Ride check: {verdict_text}",
        summary_paragraph=verdict_text + " " + " ".join(verdict.reasons),
        weather_notes=(
            f"Morning: {morning_forecast.temp_min_f:.0f}-{morning_forecast.temp_max_f:.0f}F, "
            f"pop {morning_forecast.pop_max:.0%}. "
            f"Evening: {evening_forecast.temp_min_f:.0f}-{evening_forecast.temp_max_f:.0f}F, "
            f"pop {evening_forecast.pop_max:.0%}."
        ),
        traffic_notes="See route table below for congestion and warnings.",
        route_recommendation_reasoning=(
            f"Best route to work: {best_route_to_work or 'none passable'}. "
            f"Best route home: {best_route_to_home or 'none passable'}."
        ),
        changes_since_last_night=(
            "; ".join(c.description for c in changes) if changes else "No changes since last night."
        )
        if mode == "morning"
        else None,
        gear_tips="Bring rain gear." if verdict.overall.value == "GO_WITH_RAIN_GEAR" else None,
    )
