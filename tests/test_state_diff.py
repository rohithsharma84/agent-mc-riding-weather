from __future__ import annotations

from pathlib import Path

from ride_agent import state
from ride_agent.models import Verdict
from tests.factories import make_forecast, make_run_result


def test_diff_with_no_previous_is_empty():
    current = make_run_result()
    assert state.diff(None, current) == []


def test_diff_detects_verdict_change():
    previous = make_run_result(overall=Verdict.GO)
    current = make_run_result(overall=Verdict.NO_GO)

    changes = state.diff(previous, current)

    assert any("Verdict changed" in c.description for c in changes)


def test_diff_detects_temp_shift_above_noise_threshold():
    previous = make_run_result(morning_forecast=make_forecast(label="morning", temp_max_f=70))
    current = make_run_result(morning_forecast=make_forecast(label="morning", temp_max_f=76))

    changes = state.diff(previous, current)

    assert any("high temp shifted" in c.description for c in changes)


def test_diff_ignores_small_temp_shift():
    previous = make_run_result(morning_forecast=make_forecast(label="morning", temp_max_f=70))
    current = make_run_result(morning_forecast=make_forecast(label="morning", temp_max_f=71))

    changes = state.diff(previous, current)

    assert not any("high temp shifted" in c.description for c in changes)


def test_diff_detects_pop_shift():
    previous = make_run_result(morning_forecast=make_forecast(label="morning", pop_max=0.1))
    current = make_run_result(morning_forecast=make_forecast(label="morning", pop_max=0.35))

    changes = state.diff(previous, current)

    assert any("chance of rain shifted" in c.description for c in changes)


def test_diff_detects_best_route_change():
    previous = make_run_result(best_route_to_work="Route A")
    current = make_run_result(best_route_to_work="Route B")

    changes = state.diff(previous, current)

    assert any("Best route to work changed" in c.description for c in changes)


def test_diff_detects_new_warning():
    previous = make_run_result(routes=[])
    from tests.factories import make_route

    current = make_run_result(routes=[make_route(direction="to_work", warnings=["Accident reported"])])

    changes = state.diff(previous, current)

    assert any("New warning: Accident reported" in c.description for c in changes)


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "last_run.json"
    original = make_run_result()

    state.save(original, path=path)
    loaded = state.load(path=path)

    assert loaded is not None
    assert loaded.mode == original.mode
    assert loaded.verdict.overall == original.verdict.overall
    assert loaded.target_office_day == original.target_office_day


def test_load_baseline_returns_none_when_missing(tmp_path: Path):
    path = tmp_path / "last_run.json"
    assert state.load_baseline_for("2024-01-15", path=path) is None


def test_load_baseline_rejects_stale_date(tmp_path: Path):
    path = tmp_path / "last_run.json"
    state.save(make_run_result(mode="night_before", target_office_day="2024-01-15"), path=path)

    assert state.load_baseline_for("2024-01-16", path=path) is None


def test_load_baseline_rejects_wrong_mode(tmp_path: Path):
    path = tmp_path / "last_run.json"
    state.save(make_run_result(mode="morning", target_office_day="2024-01-15"), path=path)

    assert state.load_baseline_for("2024-01-15", path=path) is None


def test_load_baseline_accepts_matching_night_before(tmp_path: Path):
    path = tmp_path / "last_run.json"
    state.save(make_run_result(mode="night_before", target_office_day="2024-01-15"), path=path)

    baseline = state.load_baseline_for("2024-01-15", path=path)

    assert baseline is not None
    assert baseline.target_office_day == "2024-01-15"
