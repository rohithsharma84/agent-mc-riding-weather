"""Persist the previous run's result so the morning email can report what
changed since the night-before recommendation. Persistence itself (commit +
push) is handled by the GitHub Actions workflow, not by this module.
"""

from __future__ import annotations

from pathlib import Path

from ride_agent.models import Change, RunResult

DEFAULT_STATE_PATH = Path("state/last_run.json")

_NOISE_TEMP_DELTA_F = 3.0
_NOISE_POP_DELTA = 0.10


def save(run_result: RunResult, path: Path = DEFAULT_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run_result.model_dump_json(indent=2), encoding="utf-8")


def load(path: Path = DEFAULT_STATE_PATH) -> RunResult | None:
    if not path.exists():
        return None
    return RunResult.model_validate_json(path.read_text(encoding="utf-8"))


def load_baseline_for(target_office_day: str, path: Path = DEFAULT_STATE_PATH) -> RunResult | None:
    """Load the previous run only if it's a valid night-before baseline for today."""
    previous = load(path)
    if previous is None:
        return None
    if previous.mode != "night_before":
        return None
    if previous.target_office_day != target_office_day:
        return None
    return previous


def diff(previous: RunResult | None, current: RunResult) -> list[Change]:
    if previous is None:
        return []

    changes: list[Change] = []

    if previous.verdict.overall != current.verdict.overall:
        changes.append(
            Change(
                description=(
                    f"Verdict changed from {previous.verdict.overall.value} "
                    f"to {current.verdict.overall.value}"
                )
            )
        )

    for label, prev_fc, cur_fc in (
        ("morning", previous.morning_forecast, current.morning_forecast),
        ("evening", previous.evening_forecast, current.evening_forecast),
    ):
        temp_delta = abs(cur_fc.temp_max_f - prev_fc.temp_max_f)
        if temp_delta >= _NOISE_TEMP_DELTA_F:
            changes.append(
                Change(
                    description=(
                        f"{label.capitalize()} high temp shifted from "
                        f"{prev_fc.temp_max_f:.0f}F to {cur_fc.temp_max_f:.0f}F"
                    )
                )
            )
        pop_delta = abs(cur_fc.pop_max - prev_fc.pop_max)
        if pop_delta >= _NOISE_POP_DELTA:
            changes.append(
                Change(
                    description=(
                        f"{label.capitalize()} chance of rain shifted from "
                        f"{prev_fc.pop_max:.0%} to {cur_fc.pop_max:.0%}"
                    )
                )
            )
        if prev_fc.has_rain_forecast != cur_fc.has_rain_forecast:
            changes.append(
                Change(
                    description=(
                        f"{label.capitalize()} rain forecast "
                        f"{'appeared' if cur_fc.has_rain_forecast else 'cleared'}"
                    )
                )
            )

    if previous.best_route_to_work != current.best_route_to_work:
        changes.append(
            Change(
                description=(
                    f"Best route to work changed from {previous.best_route_to_work!r} "
                    f"to {current.best_route_to_work!r}"
                )
            )
        )
    if previous.best_route_to_home != current.best_route_to_home:
        changes.append(
            Change(
                description=(
                    f"Best route home changed from {previous.best_route_to_home!r} "
                    f"to {current.best_route_to_home!r}"
                )
            )
        )

    prev_warnings = {w for r in previous.routes for w in r.warnings}
    cur_warnings = {w for r in current.routes for w in r.warnings}
    new_warnings = cur_warnings - prev_warnings
    for w in sorted(new_warnings):
        changes.append(Change(description=f"New warning: {w}"))

    return changes
