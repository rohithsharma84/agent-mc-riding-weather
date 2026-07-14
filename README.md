# agent-mc-riding-weather

AI agent that checks weather, traffic, and road closures to decide whether it's a good day to
ride a motorcycle to work — and emails the recommendation.

- **~9:00 pm ET** the night before each office day: a recommendation for tomorrow.
- **~6:00 am ET** the office-day morning: an always-sent update noting what, if anything,
  changed overnight.

(In winter each lands an hour earlier — ~8 pm / ~5 am — since the schedule is a fixed UTC time
and doesn't chase DST. An hour of drift is harmless at these times, which is why there's no
timezone gating.)

Office days, commute departure times, home/work locations, routes, and temperature/rain
thresholds are all set in your own `config.yaml` (see [Setup](#setup) — this file is gitignored
and never committed, since it holds your real address and schedule). The workflow fires every
night and morning; the agent no-ops on any day not listed in `office_days`, so your actual
schedule never appears in the repo.

The verdict (GO / GO-WITH-RAIN-GEAR / NO-GO) is decided by deterministic rules in
[`src/ride_agent/rules.py`](src/ride_agent/rules.py) — no rain, temperature within your configured
range, and at least one passable route. An LLM call only writes the narrative explanation; it
never overrides the verdict.

## How it decides

For both the morning and evening commute windows (as configured in `config.yaml`):

1. Rain forecast or ≥ your configured no-go rain probability → **NO-GO**.
2. Temperature outside your configured min/max → **NO-GO**.
3. ≥ your configured rain-gear probability → **GO, bring rain gear**.
4. Otherwise → **GO**.

The overall verdict is the worse of the two commute legs. Traffic congestion never flips the
verdict (it only affects route ranking/notes) — except if every configured route in a direction is
reported closed, which forces a NO-GO for that leg. All of this is unit-tested in `tests/`.

## Setup

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Credentials

Copy `.env.example` to `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `OPENAI_API_KEY`, `OPENAI_MODEL_NAME` | You already have these. |
| `OPENWEATHERAPP_API_KEY` | You already have this (free tier — uses the 5-day/3-hour forecast endpoint). |
| `GOOGLE_MAPS_API_KEY` | **New.** Google Cloud Console → create/select a project → enable the **Routes API** → Credentials → Create API key → restrict the key to the Routes API. Requires a billing account on the project, but usage here (~30 calls/week) is well within the free monthly credit. |
| `RESEND_API_KEY` | **New.** Sign up at [resend.com](https://resend.com) → API Keys → Create. The default `from` address in `config.yaml` (`onboarding@resend.dev`) works out of the box and delivers to your own account email — no domain verification needed to get started. |

### 3. Configure your routes

Copy the template and fill in your real details:

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is gitignored — it holds your home/work address and email, so it's never committed.
Edit it:

- `office_days`, `commute`: your real office days and departure times.
- `locations.home` / `locations.work`: your real address or lat/lon.
- `routes.to_work` (2 routes) / `routes.to_home` (3 routes): name each route and, for any route
  that isn't just "the default route Google picks," add a `waypoints` entry (`address:` or
  `lat`/`lon`) to steer it onto a different road than the others.
- `thresholds`, `email.to`/`email.from`: adjust as needed.

### 4. Test locally

```bash
python -m ride_agent --mode night_before --dry-run
```

This prints the subject line and writes `preview.html` (open it in a browser) without sending
anything or touching `state/last_run.json`. Try `--mode morning --dry-run` too. Once it looks
right, drop `--dry-run` to send a real email via Resend.

```bash
pytest
```

## Deploying on GitHub Actions

The workflow at [`.github/workflows/ride-check.yml`](.github/workflows/ride-check.yml) runs on a
schedule and needs no server of your own. **Steps to take in your GitHub repo:**

1. **Push this repo to GitHub** (if not already).
2. **Add secrets** — repo Settings → Secrets and variables → Actions → *Secrets* tab → New
   repository secret, for each of:
   - `OPENAI_API_KEY`
   - `OPENWEATHERAPP_API_KEY`
   - `GOOGLE_MAPS_API_KEY`
   - `RESEND_API_KEY`
   - `RIDE_CONFIG_YAML` — the **entire contents** of your local `config.yaml`, pasted as one
     secret (since `config.yaml` itself is gitignored and never committed, this is the only way
     the workflow's checkout — which starts from a clean copy of the repo every run — gets your
     real routes/addresses). Easiest via CLI: `gh secret set RIDE_CONFIG_YAML < config.yaml`.
     **Re-run that command any time you edit `config.yaml` locally** — the secret is a snapshot,
     it doesn't update itself.
3. **Add one repo variable** — same page → *Variables* tab → New repository variable:
   - `OPENAI_MODEL_NAME` (e.g. `gpt-4.1-mini`)
4. **Confirm Actions can push commits.** The workflow commits `state/last_run.json` back to the
   repo after each real (non-dry-run) send so the 7 am run knows what changed overnight. This
   needs Settings → Actions → General → Workflow permissions → **"Read and write permissions"**
   enabled (the workflow file also declares `permissions: contents: write`, but the repo-level
   setting must allow it too).
5. **Smoke-test before trusting the cron.** Actions tab → "Ride check" workflow → **Run workflow**
   → mode `night_before`, dry_run `true`. Check the run logs and confirm no errors (it won't send
   an email or touch state in dry-run mode). Repeat with `dry_run` unchecked to confirm you
   receive a real email.
6. **Let the schedule take over.** The workflow fires two fixed UTC crons every day — `15 1 * * *`
   (night_before, ~9 pm ET) and `15 10 * * *` (morning, ~6 am ET) — passing the mode explicitly.
   The agent then no-ops on any day not in your `office_days`, so you'll see quiet ~30s runs in the
   Actions history on non-office days; that's expected (it's how the day list stays private).
   GitHub's scheduler can jitter by ~15–30 minutes, so don't be surprised if an email lands a bit
   after the target time.

### Notes / limitations

- Google's Routes API has no motorcycle travel mode; `DRIVE` is used as the closest proxy for
  traffic-aware duration and closures.
- The free OpenWeatherMap forecast endpoint returns 3-hour buckets, not exact-minute forecasts —
  windows are matched to whichever bucket(s) overlap the commute time.
- If the OpenAI call fails for any reason, the email still sends with a plain, template-generated
  narrative (see `llm.fallback_narrative`) — only the verdict and data matter for safety.
