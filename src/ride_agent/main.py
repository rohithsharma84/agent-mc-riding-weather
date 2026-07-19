"""CLI entrypoint. Orchestrates one run: fetch weather + traffic, decide the
verdict, synthesize the narrative, and send (or print) the email.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from ride_agent import emailer, llm, rules, state, tracing, weather
from ride_agent.config import Config, load_config
from ride_agent.models import RideVerdict, RouteAssessment, RunResult, WindowForecast
from ride_agent.timeutil import commute_windows, get_zone, is_office_day
from ride_agent.traffic import assess_route

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ride_agent")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Motorcycle commute ride-check agent")
    parser.add_argument(
        "--mode",
        choices=["night_before", "morning"],
        required=True,
        help="night_before targets tomorrow; morning targets today. "
        "The GitHub Actions schedule supplies this per slot.",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the email instead of sending it")
    parser.add_argument(
        "--force",
        action="store_true",
        help="run even when the target day isn't a configured office day (for manual/test runs)",
    )
    parser.add_argument("--date", help="target office day (YYYY-MM-DD), overrides the inferred date")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    return parser.parse_args(argv)


def _target_day_for_mode(mode: str, date_arg: str | None, now_local: datetime) -> date:
    if date_arg:
        return date.fromisoformat(date_arg)
    if mode == "night_before":
        return (now_local + timedelta(days=1)).date()
    return now_local.date()


def _fetch_forecasts(
    cfg: Config, morning_start, morning_end, evening_start, evening_end
) -> tuple[WindowForecast, WindowForecast]:
    home = cfg.locations["home"]
    work = cfg.locations["work"]

    home_raw = weather.fetch_forecast(home.lat, home.lon, cfg.openweather_api_key)
    morning_forecast = weather.extract_window(home_raw, "morning", morning_start, morning_end)

    work_raw = weather.fetch_forecast(work.lat, work.lon, cfg.openweather_api_key)
    evening_forecast = weather.extract_window(work_raw, "evening", evening_start, evening_end)

    return morning_forecast, evening_forecast


def _fetch_routes(cfg: Config, morning_start, evening_start) -> list[RouteAssessment]:
    home = cfg.locations["home"]
    work = cfg.locations["work"]

    routes: list[RouteAssessment] = []
    for route in cfg.routes["to_work"]:
        routes.append(
            assess_route(home, work, route, "to_work", morning_start, cfg.thresholds, cfg.google_maps_api_key)
        )
    for route in cfg.routes["to_home"]:
        routes.append(
            assess_route(work, home, route, "to_home", evening_start, cfg.thresholds, cfg.google_maps_api_key)
        )
    return routes


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    load_dotenv()
    tracing.configure_tracing()
    cfg = load_config(args.config)
    tz = get_zone(cfg.timezone)
    now_local = datetime.now(tz)

    mode = args.mode
    target_day = _target_day_for_mode(mode, args.date, now_local)

    if not args.force and not is_office_day(target_day, cfg.office_days):
        logger.info("%s is not a configured office day; exiting quietly", target_day.isoformat())
        return 0

    logger.info("Running mode=%s target_office_day=%s", mode, target_day.isoformat())

    morning_start, morning_end, evening_start, evening_end = commute_windows(
        target_day,
        tz,
        cfg.commute.morning.depart,
        cfg.commute.morning.window_minutes,
        cfg.commute.evening.depart,
        cfg.commute.evening.window_minutes,
    )

    morning_forecast, evening_forecast = _fetch_forecasts(
        cfg, morning_start, morning_end, evening_start, evening_end
    )
    routes = _fetch_routes(cfg, morning_start, evening_start)

    verdict: RideVerdict = rules.decide(morning_forecast, evening_forecast, routes, cfg.thresholds)
    best_to_work = rules.best_route(routes, "to_work")
    best_to_home = rules.best_route(routes, "to_home")

    previous = state.load_baseline_for(target_day.isoformat()) if mode == "morning" else None

    current = RunResult(
        mode=mode,
        run_at=now_local,
        target_office_day=target_day.isoformat(),
        verdict=verdict,
        morning_forecast=morning_forecast,
        evening_forecast=evening_forecast,
        routes=routes,
        best_route_to_work=best_to_work.name if best_to_work else None,
        best_route_to_home=best_to_home.name if best_to_home else None,
    )

    changes = state.diff(previous, current)

    narrative = llm.synthesize(
        mode=mode,
        verdict=verdict,
        morning_forecast=morning_forecast,
        evening_forecast=evening_forecast,
        routes=routes,
        best_route_to_work=current.best_route_to_work,
        best_route_to_home=current.best_route_to_home,
        changes=changes,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model_name,
    )
    current.narrative = narrative

    subject, html = emailer.render(
        mode=mode,
        run_at=now_local,
        tz=tz,
        verdict=verdict,
        morning_forecast=morning_forecast,
        evening_forecast=evening_forecast,
        routes=routes,
        best_route_to_work=current.best_route_to_work,
        best_route_to_home=current.best_route_to_home,
        narrative=narrative,
    )

    if args.dry_run:
        print(f"Subject: {subject}\n")
        preview_path = Path("preview.html")
        preview_path.write_text(html, encoding="utf-8")
        print(f"Wrote {preview_path.resolve()}")
        # Deliberately not saving state: a dry run must not overwrite the real
        # baseline that the next scheduled run will diff against.
        return 0

    try:
        emailer.send(subject, html, cfg.email.to, cfg.email.from_, cfg.resend_api_key)
    except Exception:
        logger.exception("Failed to send email")
        return 1

    state.save(current)
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
