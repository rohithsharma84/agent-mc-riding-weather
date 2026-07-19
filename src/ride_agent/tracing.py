"""LangSmith tracing setup.

Tracing is opt-in and driven entirely by the environment. If LANGSMITH_API_KEY
is present (loaded from .env), we turn tracing on and point runs at the project
named by LANGSMITH_PROJECT. When the key is absent the agent runs exactly as
before with no LangSmith dependency active at runtime.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_tracing() -> bool:
    """Enable LangSmith tracing when an API key is available.

    Returns True if tracing was enabled. Safe to call more than once and safe
    to call when no key is set (it becomes a no-op).
    """
    api_key = os.environ.get("LANGSMITH_API_KEY")
    if not api_key:
        return False

    # The langsmith SDK reads these at trace time. LANGSMITH_API_KEY is already
    # in the environment; we make tracing explicit and default the project so a
    # run always lands somewhere sensible even if LANGSMITH_PROJECT is unset.
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    project = os.environ.get("LANGSMITH_PROJECT") or "ride-agent"
    os.environ["LANGSMITH_PROJECT"] = project

    logger.info("LangSmith tracing enabled (project=%s)", project)
    return True
