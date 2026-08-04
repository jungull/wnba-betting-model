#!/usr/bin/env python
"""Schema for D11 prospective live-information capture.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

This module declares, and nothing else:

  * the eight capture domains the node contract requires;
  * the field set every observation record carries;
  * the payload-key blocklist that keeps realised target-game outcomes out of a *pregame* capture;
  * the canonical digest used to detect a change.

It contains no I/O and no network access. It reads nothing. Binding a real source to a domain is
a separate act, recorded in SOURCE_BINDING.json, and NOT performed by this node -- see REPORT.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

SCHEMA_ID = "player_program/live_capture_observation/1"
DOMAIN_SCHEMA_ID = "player_program/live_capture_domains/1"


# ----------------------------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------------------------

class CaptureError(Exception):
    """Base class. Every rejection carries a machine-readable ``code``."""

    code = "CAPTURE_ERROR"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code


class SchemaViolation(CaptureError):
    code = "SCHEMA_VIOLATION"


class ProhibitedPayloadKey(CaptureError):
    code = "PROHIBITED_PAYLOAD_KEY"


class BackdateViolation(CaptureError):
    code = "BACKDATE_VIOLATION"


class ScopeViolation(CaptureError):
    code = "SCOPE_VIOLATION"


class LedgerIntegrityError(CaptureError):
    code = "LEDGER_INTEGRITY_ERROR"


# ----------------------------------------------------------------------------------------------
# The eight domains the D11 contract enumerates
# ----------------------------------------------------------------------------------------------
#
# ``key_fields``      : the payload fields whose values form the entity identity. First-seen and
#                       change history are tracked PER ENTITY, so this is what "the same thing,
#                       seen again" means.
# ``required_fields`` : must be present and non-null in every payload.
# ``optional_fields`` : allowed; anything else is rejected. An unexpected field is a schema
#                       violation, not a silent extra column.
# ``pregame_only``    : True when the domain describes an ANNOUNCEMENT made before tip. The
#                       realised counterpart (who actually started, actual minutes, actual
#                       lineups) is a target-game outcome and is refused by the payload blocklist.

DOMAINS: dict[str, dict] = {
    "injury_designation": {
        "describes": "an official pregame availability-report line for one player",
        "key_fields": ["season", "team", "player"],
        "required_fields": ["season", "team", "player", "designation"],
        "optional_fields": ["reason", "report_label", "game_key", "status_detail"],
        "enums": {
            "designation": [
                "OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE", "AVAILABLE",
                "NOT_WITH_TEAM", "SUSPENDED",
            ]
        },
        "pregame_only": True,
        "contract_criterion": "injury designation changes",
    },
    "lineup": {
        "describes": "an announced or projected starting five for one team in one game",
        "key_fields": ["game_key", "team"],
        "required_fields": ["game_key", "team", "announced_five", "lineup_status"],
        "optional_fields": ["source_label", "note"],
        "enums": {"lineup_status": ["PROJECTED", "ANNOUNCED", "CONFIRMED"]},
        "pregame_only": True,
        "contract_criterion": "lineups",
    },
    "starter": {
        "describes": "an announced starter/bench assignment for one player in one game",
        "key_fields": ["game_key", "team", "player"],
        "required_fields": ["game_key", "team", "player", "starter_status"],
        "optional_fields": ["note", "source_label"],
        "enums": {"starter_status": ["ANNOUNCED_STARTER", "ANNOUNCED_BENCH", "UNANNOUNCED"]},
        "pregame_only": True,
        "contract_criterion": "starters",
    },
    "minute_restriction": {
        "describes": "a stated pregame cap or limitation on a player's playing time",
        "key_fields": ["season", "team", "player"],
        "required_fields": ["season", "team", "player", "restriction_type"],
        "optional_fields": ["minutes_cap", "restriction_note", "game_key"],
        "enums": {
            "restriction_type": [
                "NONE", "MINUTES_CAP", "LOAD_MANAGEMENT", "RETURN_TO_PLAY", "BACK_TO_BACK_REST",
            ]
        },
        "pregame_only": True,
        "contract_criterion": "minute restrictions",
    },
    "transaction": {
        "describes": "a roster transaction as reported by a wire",
        "key_fields": ["transaction_key"],
        "required_fields": ["transaction_key", "transaction_type", "player"],
        "optional_fields": ["from_team", "to_team", "season", "detail"],
        "enums": {
            "transaction_type": [
                "SIGNING", "WAIVER", "WAIVER_CLAIM", "TRADE", "DRAFT", "CONTRACT_CONVERSION",
                "CONTRACT_SUSPENSION", "RETIREMENT", "HARDSHIP", "FRONT_OFFICE",
            ]
        },
        "pregame_only": False,
        "contract_criterion": "transactions",
    },
    "coaching_change": {
        "describes": "who holds the head-coaching seat for a team, and any change to it",
        "key_fields": ["season", "team"],
        "required_fields": ["season", "team", "head_coach", "change_type"],
        "optional_fields": ["predecessor", "interim", "detail"],
        "enums": {
            "change_type": ["INCUMBENT", "HIRE", "DISMISSAL", "INTERIM", "RESIGNATION"]
        },
        "pregame_only": False,
        "contract_criterion": "coaching changes",
    },
    "odds": {
        "describes": "a posted market line for one game, book and market",
        "key_fields": ["game_key", "book", "market"],
        "required_fields": ["game_key", "book", "market", "line"],
        "optional_fields": ["price_over", "price_under", "price_home", "price_away", "note"],
        "enums": {"market": ["TOTAL", "SPREAD", "MONEYLINE", "TEAM_TOTAL"]},
        "pregame_only": True,
        "contract_criterion": "odds",
    },
    "news": {
        "describes": "a news item carrying an explicit attribution",
        "key_fields": ["source_item_id"],
        "required_fields": ["source_item_id", "headline", "attributed_to", "claim_type"],
        "optional_fields": ["url", "body_digest", "subjects", "teams"],
        "enums": {
            "claim_type": ["REPORT", "OFFICIAL_STATEMENT", "RUMOUR", "SPECULATION", "OPINION"]
        },
        "pregame_only": False,
        "contract_criterion": "attributable news",
        "note": (
            "attributed_to is REQUIRED and must be non-empty. An unattributed item is refused. "
            "This is what makes the domain 'attributable news' rather than 'news'."
        ),
    },
}

CONTRACT_CRITERIA = [
    "injury designation changes", "lineups", "starters", "minute restrictions",
    "transactions", "coaching changes", "odds", "attributable news",
]


# ----------------------------------------------------------------------------------------------
# Payload-key blocklist: realised target-game outcomes and their surrogates
# ----------------------------------------------------------------------------------------------
#
# Enforced HERE, at the call site, exactly as the standing rules require. No shared gate is
# edited. The blocklist encodes two program findings that this node must not re-open:
#
#   S1 -- master_team.minutes is an EXACT overtime indicator (minutes == 5 * game_minutes on
#         2990/2990 rows), so game_minutes is recoverable by division. Any function of
#         game_minutes is prohibited from the prediction path.
#   S8 -- is_overtime, the score-differential columns and non_competitive_conservative are
#         REALISED target-game outcomes, lagged-use-only, none adjudicated.
#
# A capture record is a PREGAME observation. Nothing on this list can be a pregame observation of
# the game it names, so the ledger refuses the key outright rather than trusting a convention.

BLOCKED_PAYLOAD_KEYS_EXACT = {
    "minutes", "minutes_played", "game_minutes", "duration", "game_duration",
    "is_overtime", "overtime", "n_overtime_periods", "overtime_periods", "ot_periods",
    "regulation_seconds_remaining", "possessions", "pace", "poss", "team_possessions",
    "non_competitive_conservative", "possession_kind", "lineup_valid_ten",
    "n_off_oncourt", "n_def_oncourt", "is_zero_duration", "is_technical_derived",
    "final_score", "box_score", "turnovers", "attendance_actual",
}

BLOCKED_PAYLOAD_KEY_PREFIXES = (
    "realised_", "realized_", "actual_", "final_", "score_diff", "abs_score_diff",
    "stint_", "boxscore_", "box_", "postgame_", "off_p", "def_p",
)

_ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


# ----------------------------------------------------------------------------------------------
# Time helpers -- every timestamp in the ledger is a UTC ISO-8601 string ending in Z
# ----------------------------------------------------------------------------------------------

def parse_utc(ts: str, field: str) -> datetime:
    if not isinstance(ts, str) or not _ISO_Z.match(ts):
        raise SchemaViolation(
            f"{field} must be an ISO-8601 UTC timestamp ending in Z, got {ts!r}"
        )
    base = ts[:-1].split(".")[0]          # drop the trailing Z, then any fractional seconds
    return datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------------------------
# Canonicalisation and digests
# ----------------------------------------------------------------------------------------------

def canonical_json(obj) -> str:
    """Sort keys, no whitespace slack, no NaN. Two payloads that mean the same thing hash the
    same; two that differ anywhere hash differently."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_digest(payload: dict) -> str:
    return sha256_text(canonical_json(payload))


def entity_key(domain: str, payload: dict) -> str:
    spec = DOMAINS[domain]
    parts = []
    for f in spec["key_fields"]:
        v = payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise SchemaViolation(f"domain {domain}: key field {f!r} is required and non-empty")
        parts.append(f"{f}={_scalar(v)}")
    return f"{domain}|" + "|".join(parts)


def _scalar(v) -> str:
    if isinstance(v, (list, tuple)):
        raise SchemaViolation("a key field may not be a list")
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


# ----------------------------------------------------------------------------------------------
# Payload validation
# ----------------------------------------------------------------------------------------------

def validate_payload(domain: str, payload: dict) -> None:
    if domain not in DOMAINS:
        raise SchemaViolation(f"unknown domain {domain!r}; known: {sorted(DOMAINS)}")
    if not isinstance(payload, dict):
        raise SchemaViolation("payload must be a dict")

    spec = DOMAINS[domain]
    allowed = set(spec["required_fields"]) | set(spec["optional_fields"])

    for k in payload:
        if not isinstance(k, str):
            raise SchemaViolation("payload keys must be strings")
        lk = k.lower()
        if lk in BLOCKED_PAYLOAD_KEYS_EXACT or lk.startswith(BLOCKED_PAYLOAD_KEY_PREFIXES):
            raise ProhibitedPayloadKey(
                f"payload key {k!r} is a realised target-game outcome or a surrogate for one "
                f"(D11 blocklist; program findings S1 and S8). A pregame capture may not carry it."
            )
        if k not in allowed:
            raise SchemaViolation(
                f"domain {domain}: field {k!r} is not declared. "
                f"declared: {sorted(allowed)}"
            )

    for f in spec["required_fields"]:
        v = payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
            raise SchemaViolation(f"domain {domain}: required field {f!r} is missing or empty")

    for f, choices in spec.get("enums", {}).items():
        if f in payload and payload[f] not in choices:
            raise SchemaViolation(
                f"domain {domain}: {f}={payload[f]!r} is not one of {choices}"
            )

    # canonical_json rejects NaN/Inf; force the check now rather than at write time
    canonical_json(payload)


def domain_table() -> dict:
    return {
        "schema": DOMAIN_SCHEMA_ID,
        "contract_criteria": CONTRACT_CRITERIA,
        "domains": DOMAINS,
        "blocked_payload_keys_exact": sorted(BLOCKED_PAYLOAD_KEYS_EXACT),
        "blocked_payload_key_prefixes": list(BLOCKED_PAYLOAD_KEY_PREFIXES),
    }
