"""MARKET_IMPLIED_PROJECTIONS -- D033 source-agnostic projection table schema.

Track: MARKET-IMPLIED (D033_ACQUISITION_STRATEGY_REVISION, item 4/5). This
module implements the SHARED LANDING FORMAT that every source of a player
projection -- market-implied, expert/vendor, DFS-salary-derived, or a future
fundamental-model row -- lands into, so downstream consumers never depend on
a single vendor's continuous-history availability (the stated purpose of the
D033 source-agnostic table: "no single-vendor continuous-history
dependency").

This module owns the SCHEMA ONLY. `implied_mean.py` and `engine.py` own the
market-implied-specific math that fills these rows for the `source ==
"MARKET_IMPLIED"` case. A future expert-projection or DFS-salary node fills
the same row shape with a different `source` value and its own per-source
extension fields under `source_extra`.

Epistemic status (write verbatim wherever this schema's rows are cited):
"SOURCE-AGNOSTIC PROJECTION LANDING ROW. A row in this table is a claim
about what one named SOURCE asserted, at one SNAPSHOT TIME, about one
player's expected production in one game. It is not, by itself, an
adjudicated evidence-ladder result (contract MARKET_PROGRAM_CONTRACT.md
section 3) and confers no opportunity-taxonomy label (section 1)."

Contract: experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/
MARKET_PROGRAM_CONTRACT.md sha256
1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json

CONTRACT_SHA256 = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"

SCHEMA_ID = "market_program/D033/source_agnostic_projection_row/1"

EPISTEMIC_STATUS_LINE = (
    "SOURCE-AGNOSTIC PROJECTION LANDING ROW. A row in this table is a claim "
    "about what one named SOURCE asserted, at one SNAPSHOT TIME, about one "
    "player's expected production in one game. It is not, by itself, an "
    "adjudicated evidence-ladder result and confers no opportunity-taxonomy "
    "label."
)

# ---------------------------------------------------------------------------
# D033 core fields -- every row, regardless of source, carries these.
# "player_id, game_id, source, source_snapshot_ts, per-stat projections,
#  status, salary, source_quality, timestamp_quality" (D033 ruling, item 4)
# ---------------------------------------------------------------------------
CORE_FIELDS = [
    "row_id",                 # sha256 of the canonical row body (assigned last)
    "player_id",               # our entity-resolved id if available, else null
    "player_key_raw",          # the raw name/id string as the source gave it
    "player_key_resolution",   # enum: RESOLVED_ENTITY_ID / RAW_NAME_UNRESOLVED
    "game_id",                 # our canonical game_id if resolvable
    "game_key_raw",            # the raw event/game key as the source gave it
    "game_key_resolution",     # enum: RESOLVED_GAME_ID / RAW_EVENT_KEY_UNRESOLVED
    "scheduled_tipoff_ts",     # commence_time, ISO8601 UTC, if known
    "source",                  # enum, see SOURCE_ENUM
    "source_snapshot_ts",      # when the SOURCE asserted this (its own clock)
    "stat_projections",        # dict: {stat_name: {"mean": float|null, ...}}
    "status",                  # player status the source implies/asserts, or UNKNOWN
    "salary",                  # DFS salary if the source carries one, else null
    "source_quality",          # enum, see SOURCE_QUALITY_ENUM (D033 hierarchy rank)
    "timestamp_quality",       # enum: WITNESSED / VENDOR_ASSERTED / INFERRED
    "source_extra",            # dict: per-source extension fields (market-implied's live here)
]

# amendment-4 field set (contract section 6.1), carried on every row per the
# lane-wide freeze even though a single landing row is not itself a
# reaction-time claim (mirrors the interpretive choice M11 documents).
AMENDMENT4_FIELDS = [
    "t_lower", "t_upper", "poll_interval_event", "poll_interval_quote",
    "vendor_latency_bound", "clock_skew_bound", "censor_type", "tier",
    "n_trusted", "n_excluded",
]

ALL_FIELDS = CORE_FIELDS + AMENDMENT4_FIELDS

# D033 source hierarchy, frozen, highest precedence first. `source_quality`
# on every row is one of these exact tokens.
SOURCE_QUALITY_ENUM = [
    "OFFICIAL_QUARTER_HOUR_INJURY_REPORT",
    "OFFICIAL_TEAM_LEAGUE_ANNOUNCEMENT",
    "CREDENTIALED_REPORTER",
    "ARCHIVED_PROJECTION_DFS_STATUS",
    "GENERAL_NEWS",
    "WIKIPEDIA_REVISION",
    "PARTICIPATION_INFERENCE",
    "MARKET_IMPLIED",   # this track's own source: not in the injury-status
                         # hierarchy above (which ranks *status* sources) --
                         # market-implied projections are a distinct S-MKT
                         # signal, listed separately and never conflated with
                         # a status-hierarchy rank.
]

SOURCE_ENUM = [
    "MARKET_IMPLIED",          # this track
    "EXPERT_VENDOR_PROJECTION",
    "DFS_SALARY_DERIVED",
    "OFFICIAL_INJURY_REPORT",
    "TEAM_ANNOUNCEMENT",
    "CREDENTIALED_REPORTER",
    "WIKIPEDIA_REVISION",
    "FUNDAMENTAL_MODEL",       # S-FUND interface, future
]

STATUS_ENUM = [
    "ACTIVE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL", "OUT", "UNKNOWN",
]


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def new_row(*, player_id=None, player_key_raw, player_key_resolution,
            game_id=None, game_key_raw, game_key_resolution,
            scheduled_tipoff_ts, source, source_snapshot_ts,
            stat_projections, status="UNKNOWN", salary=None,
            source_quality, timestamp_quality, source_extra=None,
            t_lower="NOT_A_REACTION_TIME_CLAIM",
            t_upper="NOT_A_REACTION_TIME_CLAIM",
            poll_interval_event="N/A_NO_EVENT_STREAM",
            poll_interval_quote="UNKNOWN",
            vendor_latency_bound=None, clock_skew_bound="UNMEASURED",
            censor_type="N/A", tier="T1", n_trusted=None, n_excluded=None):
    """Build one D033 source-agnostic projection landing row.

    Validates enums strictly (fail closed on an unrecognised token -- a typo
    here would otherwise silently create a new, unregistered vocabulary
    entry, exactly what the contract's amendment procedure forbids for the
    market-lane taxonomy and what this schema mirrors for its own enums).
    """
    if source not in SOURCE_ENUM:
        raise ValueError(f"unregistered source: {source!r}")
    if source_quality not in SOURCE_QUALITY_ENUM:
        raise ValueError(f"unregistered source_quality: {source_quality!r}")
    if status not in STATUS_ENUM:
        raise ValueError(f"unregistered status: {status!r}")
    if timestamp_quality not in ("WITNESSED", "VENDOR_ASSERTED", "INFERRED"):
        raise ValueError(f"unregistered timestamp_quality: {timestamp_quality!r}")
    if player_key_resolution not in ("RESOLVED_ENTITY_ID", "RAW_NAME_UNRESOLVED"):
        raise ValueError("bad player_key_resolution")
    if game_key_resolution not in ("RESOLVED_GAME_ID", "RAW_EVENT_KEY_UNRESOLVED"):
        raise ValueError("bad game_key_resolution")

    row = {
        "schema": SCHEMA_ID,
        "epistemic_status": EPISTEMIC_STATUS_LINE,
        "player_id": player_id,
        "player_key_raw": player_key_raw,
        "player_key_resolution": player_key_resolution,
        "game_id": game_id,
        "game_key_raw": game_key_raw,
        "game_key_resolution": game_key_resolution,
        "scheduled_tipoff_ts": scheduled_tipoff_ts,
        "source": source,
        "source_snapshot_ts": source_snapshot_ts,
        "stat_projections": stat_projections,
        "status": status,
        "salary": salary,
        "source_quality": source_quality,
        "timestamp_quality": timestamp_quality,
        "source_extra": source_extra or {},
        "t_lower": t_lower,
        "t_upper": t_upper,
        "poll_interval_event": poll_interval_event,
        "poll_interval_quote": poll_interval_quote,
        "vendor_latency_bound": vendor_latency_bound if vendor_latency_bound is not None else "UNBOUNDED",
        "clock_skew_bound": clock_skew_bound,
        "censor_type": censor_type,
        "tier": tier,
        "n_trusted": n_trusted,
        "n_excluded": n_excluded,
    }
    row["row_id"] = sha256_hex(canonical_json(row))
    return row
