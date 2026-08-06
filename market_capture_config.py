#!/usr/bin/env python3
"""
Feature gate for the ladder/burst poller. SHIPS OFF BY DEFAULT.

Per the node's mandate (f): "the new ladder ships OFF by default behind an
explicit enable flag" and "you are NOT activating anything: no
scheduled-task changes". Nothing in this codebase's Task Scheduler
configuration references market_capture_run.py; even if something did,
`is_enabled()` defaults to False and requires an explicit opt-in env var,
so a stray invocation is a no-op, not a vendor-quota spend.
"""
import os

ENV_VAR = "MARKET_LADDER_ENABLED"


def is_enabled() -> bool:
    """True only if MARKET_LADDER_ENABLED is set to a truthy value
    ("1", "true", "yes", case-insensitive). Absent or any other value ->
    disabled. This is the explicit enable flag the node's stop conditions
    require before any vendor credit for the NEW ladder/burst mechanism can
    be spent (the pre-existing odds_capture_daily.py / props_capture_daily.py
    jobs are untouched and keep running regardless of this flag)."""
    v = os.getenv(ENV_VAR, "").strip().lower()
    return v in ("1", "true", "yes")
