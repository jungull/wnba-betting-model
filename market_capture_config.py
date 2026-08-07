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


# --------------------------------------------------------------------------
# M27_PER_BOOK_POLLING (ledger D052 + D053) -- bounded, scoped per-book
# polling upgrade. This is a SEPARATE kill switch layered on top of
# `is_enabled()` above, not a replacement for it: MARKET_LADDER_ENABLED
# must ALSO be truthy for any capture to run at all; this flag additionally
# gates the new per-book intensification layer specifically. Absent or any
# other value -> disabled, and disabling this flag alone (leaving
# MARKET_LADDER_ENABLED on) returns capture EXACTLY to the pre-M27 ladder +
# burst behavior -- no per-book calls, no new files, no behavior change of
# any kind on the existing bundled odds/props polls. This is the documented
# kill switch the M27 authorization requires.
PER_BOOK_ENV_VAR = "MARKET_PER_BOOK_POLLING_ENABLED"


def is_per_book_polling_enabled() -> bool:
    """True only if MARKET_PER_BOOK_POLLING_ENABLED is set to a truthy value
    ("1", "true", "yes", case-insensitive). Absent or any other value ->
    disabled (the pre-M27 behavior: only the bundled, single-payload odds and
    props polls run, exactly as before this node's changes)."""
    v = os.getenv(PER_BOOK_ENV_VAR, "").strip().lower()
    return v in ("1", "true", "yes")


# Scope declaration (D052/D053 authorization is BOUNDED, not an open-ended
# cadence change -- see M27_PER_BOOK_POLLING/M27_REPORT_BODY.md Section 2 for
# the tape evidence behind each of these three numbers). Declared as named
# constants, not re-derived ad hoc at each call site, and overridable only
# via the env vars below for operational flexibility (e.g. a narrower test
# run) -- the DEFAULTS are the authorized scope and must not silently drift.
#
# PER_BOOK_DECLARED_BOOKS: the 3 books with the densest measured price-change
# coverage in the existing tape (data/market_snapshots/snapshots.csv as of
# 2026-08-07): betrivers (265 changes), draftkings (204), fanduel (174) --
# together 643 of 863 total observed price-change events (74.5%) across all
# tracked books, vs. betonlineag (144) and williamhill_us (76) for the
# remaining two regularly-polled books. (Six other book keys appear in the
# tape with exactly 6 rows / 0 changes each -- these are single-poll
# artifacts from an unrelated M26 live-verification run, not ongoing
# coverage, and are excluded from this ranking.)
PER_BOOK_DECLARED_BOOKS = ["betrivers", "draftkings", "fanduel"]

# PER_BOOK_PRE_TIP_WINDOW_MINUTES: per-book polling only fires inside
# [tip - 60min, tip). Justified from the tape's own price-change rate,
# bucketed by hours-before-tip using ladder-rung-derived tip estimates
# (analyze_tape.py in this node's directory): the change rate rises from
# ~2.1 changes/min in the 2h-4h-before-tip bucket, to ~3.7/min in the
# 1h-2h bucket, to ~15.5/min in the final 15 minutes before tip -- a 7.4x
# acceleration from the 2h-4h baseline. The 60-minute window captures this
# entire acceleration and composes with the existing ladder's own T-60m /
# T-15m / final_pregame rungs rather than inventing a new window outside
# them.
PER_BOOK_PRE_TIP_WINDOW_MINUTES = 60.0

# PER_BOOK_POLL_INTERVAL_SECONDS: reuses the SAME cadence value this
# codebase's burst mechanism already uses (market_ladder_scheduler.
# BURST_LEG_INTERVAL_SECONDS = 5*60) rather than inventing a new number --
# up to 12 per-book poll cycles per game across the 60-minute window, one
# HTTP call per declared book per cycle (3 calls/cycle for the 3-book scope
# above).
PER_BOOK_POLL_INTERVAL_SECONDS = 5 * 60.0
