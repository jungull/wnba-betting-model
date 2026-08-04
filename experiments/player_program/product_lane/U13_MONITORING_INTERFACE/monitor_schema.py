"""
U13_MONITORING_INTERFACE -- snapshot schema and status vocabulary.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

This module defines WHAT a monitoring snapshot is. It contains no model, no estimator, no arm
identifier and no knowledge of which model produced any number. The model version and the artifact
hashes are DATA carried on the snapshot; the interface treats them as opaque strings.

Two properties are load-bearing and are enforced by monitor_state.py and asserted by TESTS.py:

  1. FAIL-CLOSED. Every status enum has an explicit "unknown" member, and an absent, null,
     unparseable or out-of-vocabulary value maps to it. "Unknown" is a suppressing condition, not
     a benign one. There is no code path in which missing information becomes a default OK.

  2. ABSENCE IS NOT A NUMBER. A displayable quantity is never rendered as a bare float. It is
     rendered through a display cell that is either kind=NUMBER (value present AND every
     dependency healthy) or kind=ALERT (carrying the codes that suppressed it).
"""

from __future__ import annotations

SNAPSHOT_SCHEMA = "player_program/monitor_snapshot/1"
EVALUATION_SCHEMA = "player_program/monitor_evaluation/1"

# ---------------------------------------------------------------------------------------------
# Status vocabularies. The LAST member of each is the fail-closed default.
# ---------------------------------------------------------------------------------------------

INPUT_OK = "OK"
INPUT_STALE = "STALE"
INPUT_MISSING = "MISSING"
INPUT_UNBOUND = "UNBOUND"
INPUT_ERROR = "ERROR"
INPUT_UNKNOWN = "UNKNOWN"
INPUT_STATUSES = (INPUT_OK, INPUT_STALE, INPUT_MISSING, INPUT_UNBOUND, INPUT_ERROR, INPUT_UNKNOWN)

# lineup_status values are the D11 capture vocabulary, quoted rather than invented:
# experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/capture_schema.py:98
LINEUP_OBSERVED = ("PROJECTED", "ANNOUNCED", "CONFIRMED")
LINEUP_MISSING = "MISSING"
LINEUP_UNBOUND = "UNBOUND"
LINEUP_STALE = "STALE"
LINEUP_UNKNOWN = "UNKNOWN"
LINEUP_STATUSES = LINEUP_OBSERVED + (LINEUP_MISSING, LINEUP_UNBOUND, LINEUP_STALE, LINEUP_UNKNOWN)

JOB_SUCCEEDED = "SUCCEEDED"
JOB_RUNNING = "RUNNING"
JOB_LATE = "LATE"
JOB_FAILED = "FAILED"
JOB_DID_NOT_RUN = "DID_NOT_RUN"
JOB_UNKNOWN = "UNKNOWN"
JOB_STATUSES = (JOB_SUCCEEDED, JOB_RUNNING, JOB_LATE, JOB_FAILED, JOB_DID_NOT_RUN, JOB_UNKNOWN)

ROLLBACK_NONE = "NONE"
ROLLBACK_ACTIVE = "ACTIVE"
ROLLBACK_PENDING = "PENDING"
ROLLBACK_FAILED = "FAILED"
ROLLBACK_UNKNOWN = "UNKNOWN"
ROLLBACK_STATES = (
    ROLLBACK_NONE, ROLLBACK_ACTIVE, ROLLBACK_PENDING, ROLLBACK_FAILED, ROLLBACK_UNKNOWN,
)

# Statuses under which a dependent quantity may NOT be shown as a number.
SUPPRESSING_INPUT = (INPUT_STALE, INPUT_MISSING, INPUT_UNBOUND, INPUT_ERROR, INPUT_UNKNOWN)
SUPPRESSING_LINEUP = (LINEUP_MISSING, LINEUP_UNBOUND, LINEUP_STALE, LINEUP_UNKNOWN)
SUPPRESSING_JOB = (JOB_RUNNING, JOB_LATE, JOB_FAILED, JOB_DID_NOT_RUN, JOB_UNKNOWN)
# ROLLBACK_ACTIVE does NOT suppress: a rolled-back version is still a serving version and its
# numbers are real. It raises a mandatory banner instead. PENDING/FAILED/UNKNOWN suppress,
# because in those states which version is serving is not established.
SUPPRESSING_ROLLBACK = (ROLLBACK_PENDING, ROLLBACK_FAILED, ROLLBACK_UNKNOWN)

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_ORDER = {SEVERITY_CRITICAL: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

# ---------------------------------------------------------------------------------------------
# Alert codes. Each of the four contract-named failure classes has its own code family, so the
# four are individually visible rather than collapsed into one "unhealthy" light.
# ---------------------------------------------------------------------------------------------

ALERT_CODES = {
    # stale / absent inputs
    "INPUT_STALE": (SEVERITY_WARNING, "an input is older than its declared maximum age"),
    "INPUT_MISSING": (SEVERITY_CRITICAL, "an input has never been observed"),
    "INPUT_UNBOUND": (SEVERITY_CRITICAL, "no live source is bound to this input domain"),
    "INPUT_ERROR": (SEVERITY_CRITICAL, "the input adapter reported an error"),
    "INPUT_UNKNOWN": (SEVERITY_CRITICAL, "input state could not be determined; fail-closed"),
    # lineups
    "LINEUP_MISSING": (SEVERITY_CRITICAL, "no lineup observation exists for this game/team"),
    "LINEUP_UNBOUND": (SEVERITY_CRITICAL, "no lineup source is bound"),
    "LINEUP_STALE": (SEVERITY_WARNING, "the lineup observation is older than its maximum age"),
    "LINEUP_UNKNOWN": (SEVERITY_CRITICAL, "lineup state could not be determined; fail-closed"),
    # jobs
    "JOB_FAILED": (SEVERITY_CRITICAL, "a job ran and failed"),
    "JOB_DID_NOT_RUN": (SEVERITY_CRITICAL, "a job was due and no run exists"),
    "JOB_LATE": (SEVERITY_WARNING, "a job completed after its own cutoff"),
    "JOB_RUNNING": (SEVERITY_WARNING, "a job is still in flight past its cutoff"),
    "JOB_UNKNOWN": (SEVERITY_CRITICAL, "job state could not be determined; fail-closed"),
    # rollback
    "ROLLBACK_ACTIVE": (SEVERITY_WARNING, "the serving version is a rollback target"),
    "ROLLBACK_PENDING": (SEVERITY_CRITICAL, "a rollback is in flight; serving version indeterminate"),
    "ROLLBACK_FAILED": (SEVERITY_CRITICAL, "a rollback attempt failed"),
    "ROLLBACK_UNKNOWN": (SEVERITY_CRITICAL, "rollback state could not be determined; fail-closed"),
    # binding / structural
    "MODEL_VERSION_ABSENT": (SEVERITY_CRITICAL, "the snapshot carries no model version"),
    "ARTIFACT_HASHES_ABSENT": (SEVERITY_CRITICAL, "the snapshot carries no artifact hashes"),
    "ARTIFACT_HASH_NULL": (SEVERITY_CRITICAL, "an artifact hash is present but null or empty"),
    "SNAPSHOT_MALFORMED": (SEVERITY_CRITICAL, "the snapshot is not a readable monitor snapshot"),
    "SNAPSHOT_ABSENT": (SEVERITY_CRITICAL, "no snapshot exists for this evaluation"),
    "SNAPSHOT_STALE": (SEVERITY_CRITICAL, "the snapshot itself is older than its maximum age"),
    "CLOCK_UNKNOWN": (SEVERITY_CRITICAL, "the evaluation clock is absent or unparseable"),
    "PROJECTION_VALUE_ABSENT": (SEVERITY_CRITICAL, "a projection row carries no value"),
    "PROJECTION_ROW_ABSENT": (SEVERITY_CRITICAL,
                              "an expected projection is missing from the snapshot entirely"),
    "PROJECTION_ROW_UNEXPECTED": (SEVERITY_WARNING,
                                  "a projection appears that the expected slate does not contain"),
    "EXPECTED_COVERAGE_UNDECLARED": (SEVERITY_CRITICAL,
                                     "the snapshot declares no expected slate, so a silently "
                                     "vanished row could not be detected"),
    "DEPENDENCY_UNDECLARED": (SEVERITY_CRITICAL, "a projection names a dependency that does not exist"),
    "NO_PROJECTIONS": (SEVERITY_WARNING, "the snapshot carries no projection rows"),
}

DISPLAY_NUMBER = "NUMBER"
DISPLAY_ALERT = "ALERT"

# The text an alert cell renders. It is never numeric, never blank, and never a dash that could be
# mistaken for a zero.
ALERT_CELL_TEXT = "UNAVAILABLE"


def severity_of(code: str) -> str:
    """Fail-closed: an unregistered alert code is CRITICAL, not INFO."""
    entry = ALERT_CODES.get(code)
    return entry[0] if entry else SEVERITY_CRITICAL


def describe(code: str) -> str:
    entry = ALERT_CODES.get(code)
    return entry[1] if entry else "unregistered alert code; treated as critical"


def coerce_status(value, vocabulary, unknown):
    """Map any value onto the vocabulary, defaulting to the fail-closed member."""
    if isinstance(value, str) and value in vocabulary:
        return value
    return unknown
