from __future__ import annotations

from ride_agent import rules
from ride_agent.models import Verdict
from tests.factories import make_forecast, make_route, make_thresholds


def test_clear_day_is_go():
    thresholds = make_thresholds()
    morning = make_forecast(label="morning", temp_min_f=70, temp_max_f=80, pop_max=0.05)
    evening = make_forecast(label="evening", temp_min_f=72, temp_max_f=82, pop_max=0.05)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.GO


def test_moderate_pop_triggers_rain_gear():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.25, has_rain_forecast=False)
    evening = make_forecast(pop_max=0.05)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.GO_WITH_RAIN_GEAR
    assert any("rain gear" in r for r in result.reasons)


def test_high_pop_is_no_go():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.65)
    evening = make_forecast(pop_max=0.05)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO


def test_rain_condition_overrides_low_pop():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.05, has_rain_forecast=True, conditions=["Rain"])
    evening = make_forecast(pop_max=0.05)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO


def test_temp_below_range_is_no_go():
    thresholds = make_thresholds()
    morning = make_forecast(temp_min_f=58, temp_max_f=64, pop_max=0.0)
    evening = make_forecast(pop_max=0.0)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO
    assert any("temperature" in r for r in result.reasons)


def test_temp_above_range_is_no_go():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.0)
    evening = make_forecast(temp_min_f=90, temp_max_f=96, pop_max=0.0)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO


def test_temp_boundary_values_are_go():
    thresholds = make_thresholds()
    morning = make_forecast(temp_min_f=65, temp_max_f=95, pop_max=0.0)
    evening = make_forecast(temp_min_f=65, temp_max_f=95, pop_max=0.0)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.GO


def test_one_bad_leg_makes_overall_no_go():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.0)
    evening = make_forecast(pop_max=0.99, has_rain_forecast=True)
    routes = [make_route(direction="to_work"), make_route(direction="to_home")]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO
    morning_leg = next(leg for leg in result.legs if leg.leg == "morning")
    evening_leg = next(leg for leg in result.legs if leg.leg == "evening")
    assert morning_leg.verdict == Verdict.GO
    assert evening_leg.verdict == Verdict.NO_GO


def test_all_routes_closed_forces_no_go():
    thresholds = make_thresholds()
    morning = make_forecast(pop_max=0.0)
    evening = make_forecast(pop_max=0.0)
    routes = [
        make_route(name="A", direction="to_work", is_closed=True),
        make_route(name="B", direction="to_work", is_closed=True),
        make_route(name="C", direction="to_home", is_closed=False),
    ]

    result = rules.decide(morning, evening, routes, thresholds)

    assert result.overall == Verdict.NO_GO
    assert any("closed" in r for r in result.reasons)


def test_best_route_picks_fastest_passable():
    routes = [
        make_route(name="Slow", direction="to_work", duration_min=40, static_duration_min=35),
        make_route(name="Fast", direction="to_work", duration_min=25, static_duration_min=25),
        make_route(name="Closed", direction="to_work", duration_min=10, static_duration_min=10, is_closed=True),
    ]

    best = rules.best_route(routes, "to_work")

    assert best is not None
    assert best.name == "Fast"


def test_best_route_returns_none_when_all_closed():
    routes = [make_route(name="A", direction="to_home", is_closed=True)]

    assert rules.best_route(routes, "to_home") is None
