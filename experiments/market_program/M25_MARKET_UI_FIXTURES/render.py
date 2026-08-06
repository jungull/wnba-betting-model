"""
render.py -- M25_MARKET_UI_FIXTURES rendering engine.

PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply that
any edge, signal or tradable opportunity exists: fixtures render as fixtures.

This module contains the only logic that decides what the market screen shell may display.
It is deliberately separated from fixture data (fixtures/*.json) and from the static HTML
builder (build_shell.py) so that:
  * TESTS.py can exercise the rendering rules directly, in Python, without a browser;
  * the rules governing staleness, absence, evidence-ladder gating and mode-badge behavior
    live in exactly one place;
  * no live wiring is possible by construction -- this module never performs network I/O,
    never reads live odds, and its only inputs are fixture dicts already loaded from JSON.

Frozen behavioral rules encoded here (cite MARKET_PROGRAM_CONTRACT.md section numbers):
  * section 4 (point-in-time integrity): a value whose retrieval_ts is missing, or whose age
    exceeds max_staleness_bound_seconds, NEVER renders as a number. It renders as a WARNING.
  * section 3 (evidence ladder): nothing below PRODUCTION_ELIGIBLE renders as actionable.
    Since no market-lane strategy has been promoted (this is a fixture scaffold), nothing
    in this shell is ever actionable -- that is a required, tested property, not a gap.
  * section 6 (amendment 4, timestamp-uncertainty discipline): a reaction-time claim missing
    any of the mandatory fields renders UNSUPPORTABLE, never as a bare timing figure. No
    reaction-time point estimate is ever displayed as a bare scalar finer than the poll grid.
  * section 7 (D024 execution-mode ladder): the mode badge defaults to SHADOW. A requested
    transition to CONFIRM or AUTO without an explicit user_required_gate_ref is refused and
    rendered back as SHADOW with a warning -- mode transitions are never self-grantable.
  * TAXONOMY.json opportunity_taxonomy.reserved_terms: the string "arbitrage" (case
    insensitive) may only be attached to class TRUE_CROSS_BOOK_ARBITRAGE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"

EVIDENCE_LADDER_LABELS = [
    "MARKET_MECHANISM_SUPPORTED",
    "LINE_MOVEMENT_PREDICTIVE_ONLY",
    "CLOSING_LINE_VALUE_SUPPORTED",
    "HISTORICALLY_PROFITABLE",
    "EXECUTION_FEASIBLE",
    "PROSPECTIVELY_SUPPORTED",
    "PRODUCTION_ELIGIBLE",
]

OPPORTUNITY_CLASSES = [
    "TRUE_CROSS_BOOK_ARBITRAGE",
    "MIDDLES_AND_DISLOCATIONS",
    "STALE_LINE_DELAYED_REACTION",
    "MODEL_VS_MARKET_VALUE",
    "THIRD_PARTY_PROJECTION_VALUE",
    "PURE_MICROSTRUCTURE",
]

RESERVED_ARBITRAGE_TERM = "arbitrage"
RESERVED_ARBITRAGE_CLASS = "TRUE_CROSS_BOOK_ARBITRAGE"

HARD_RISK_CONTROLS = [
    "approved event source",
    "minimum confidence",
    "minimum edge",
    "maximum quote age",
    "maximum stake",
    "per-game and per-player exposure caps",
    "minimum liquidity",
    "no duplicate or correlated-order conflict",
    "no trading through a suspension",
    "daily loss and volume caps",
    "global kill switch",
]

MODES = ("OFF", "SHADOW", "CONFIRM", "AUTO")
DEFAULT_MODE = "SHADOW"

REACTION_TIME_MANDATORY_FIELDS = [
    "t_lower",
    "t_upper",
    "poll_interval_event_seconds",
    "poll_interval_quote_seconds",
    "vendor_latency_bound",
    "clock_skew_bound",
    "censor_type",
    "tier",
    "n_trusted",
    "n_excluded",
]


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compute_freshness(
    retrieval_ts: str | None,
    max_staleness_bound_seconds: float | None,
    now: datetime,
) -> dict[str, Any]:
    """Return a freshness stamp. Every displayed number must carry one of these (section 4/6)."""
    parsed = _parse_ts(retrieval_ts)
    if parsed is None:
        return {
            "retrieval_ts": None,
            "age_seconds": None,
            "max_staleness_bound_seconds": max_staleness_bound_seconds,
            "status": "ABSENT",
        }
    age_seconds = (now - parsed).total_seconds()
    if max_staleness_bound_seconds is None:
        # A bound-less item (e.g. a frozen pre-commence projection) is never judged stale by
        # age; it is judged by its own publication semantics elsewhere. We still report age.
        status = "FRESH_NO_BOUND"
    elif age_seconds > max_staleness_bound_seconds:
        status = "STALE"
    else:
        status = "FRESH"
    return {
        "retrieval_ts": retrieval_ts,
        "age_seconds": age_seconds,
        "max_staleness_bound_seconds": max_staleness_bound_seconds,
        "status": status,
    }


def render_numeric_signal(
    label: str,
    value: Any,
    retrieval_ts: str | None,
    max_staleness_bound_seconds: float | None,
    now: datetime,
    evidence_labels_held: list[str] | None = None,
) -> dict[str, Any]:
    """
    Render a single displayed number (a quote, a consensus prob, a usable edge, ...).

    Returns either:
      {"display": "value", "value": ..., "freshness": {...}, "actionable": bool, ...}
      {"display": "warning", "reason": "ABSENT_INPUT" | "STALE_INPUT", "freshness": {...}}
    A "warning" render NEVER carries the numeric value in the visible field -- the raw value
    is dropped from the display payload entirely, even though it may still be present in the
    fixture, so a UI author cannot accidentally surface it.
    """
    evidence_labels_held = evidence_labels_held or []
    freshness = compute_freshness(retrieval_ts, max_staleness_bound_seconds, now)

    if value is None or freshness["status"] == "ABSENT":
        return {
            "label": label,
            "display": "warning",
            "reason": "ABSENT_INPUT",
            "freshness": freshness,
        }
    if freshness["status"] == "STALE":
        return {
            "label": label,
            "display": "warning",
            "reason": "STALE_INPUT",
            "freshness": freshness,
        }

    actionable = PRODUCTION_ELIGIBLE in evidence_labels_held
    return {
        "label": label,
        "display": "value",
        "value": value,
        "freshness": freshness,
        "evidence_labels_held": list(evidence_labels_held),
        "actionable": actionable,
    }


def render_reaction_time_claim(candidate: dict[str, Any]) -> dict[str, Any]:
    """
    Render a STALE_LINE_DELAYED_REACTION-style timing claim under amendment-4 discipline
    (MARKET_PROGRAM_CONTRACT.md section 6). Missing any mandatory field -> UNSUPPORTABLE.
    """
    missing = [f for f in REACTION_TIME_MANDATORY_FIELDS if candidate.get(f) in (None, "")]
    if missing:
        return {
            "candidate_id": candidate.get("candidate_id"),
            "display": "UNSUPPORTABLE",
            "missing_fields": missing,
        }
    return {
        "candidate_id": candidate.get("candidate_id"),
        "display": "reaction_time_claim",
        "t_lower": candidate["t_lower"],
        "t_upper": candidate["t_upper"],
        "poll_interval_event_seconds": candidate["poll_interval_event_seconds"],
        "poll_interval_quote_seconds": candidate["poll_interval_quote_seconds"],
        "vendor_latency_bound": candidate["vendor_latency_bound"],
        "clock_skew_bound": candidate["clock_skew_bound"],
        "censor_type": candidate["censor_type"],
        "tier": candidate["tier"],
        "n_trusted": candidate["n_trusted"],
        "n_excluded": candidate["n_excluded"],
        "actionable": False,  # a fixture-stage reaction-time claim is never actionable
    }


def render_usable_edge(opp: dict[str, Any], now: datetime) -> dict[str, Any]:
    """
    usable_edge = model_edge - fees - expected_slippage - latency_penalty - uncertainty_buffer
    (MARKET_PROGRAM_CONTRACT.md section 2, S-EXEC interface). Renders as a warning under the
    same absent/stale rules as any other displayed number (section 4).
    """
    freshness = compute_freshness(
        opp.get("retrieval_ts"), opp.get("max_staleness_bound_seconds"), now
    )
    if freshness["status"] in ("ABSENT", "STALE"):
        return {
            "opportunity_id": opp.get("opportunity_id"),
            "display": "warning",
            "reason": "ABSENT_INPUT" if freshness["status"] == "ABSENT" else "STALE_INPUT",
            "freshness": freshness,
        }

    required = ["model_edge", "fees", "expected_slippage", "latency_penalty", "uncertainty_buffer"]
    missing = [f for f in required if opp.get(f) is None]
    if missing:
        return {
            "opportunity_id": opp.get("opportunity_id"),
            "display": "warning",
            "reason": "ABSENT_INPUT",
            "missing_fields": missing,
            "freshness": freshness,
        }

    usable_edge = (
        opp["model_edge"]
        - opp["fees"]
        - opp["expected_slippage"]
        - opp["latency_penalty"]
        - opp["uncertainty_buffer"]
    )
    capacity_status = opp.get("capacity_status") or "CAPACITY_UNKNOWN"
    evidence_labels_held = opp.get("evidence_labels_held") or []
    return {
        "opportunity_id": opp.get("opportunity_id"),
        "opportunity_class": opp.get("opportunity_class"),
        "display": "value",
        "usable_edge": usable_edge,
        "capacity_status": capacity_status,
        "freshness": freshness,
        "evidence_labels_held": evidence_labels_held,
        "actionable": PRODUCTION_ELIGIBLE in evidence_labels_held,
    }


def render_opportunity_age(fixture: dict[str, Any], now: datetime) -> dict[str, Any]:
    """
    Render opportunity age as a grid-bounded interval, never a bare finer-than-grid scalar
    (section 6.2 sharpness prohibition applied defensively even outside strict reaction-time
    claims, since "opportunity age" is a timing-adjacent quantity).
    """
    freshness = compute_freshness(
        fixture.get("retrieval_ts"), fixture.get("max_staleness_bound_seconds"), now
    )
    if freshness["status"] in ("ABSENT", "STALE"):
        return {
            "opportunity_id": fixture.get("opportunity_id"),
            "display": "warning",
            "reason": "ABSENT_INPUT" if freshness["status"] == "ABSENT" else "STALE_INPUT",
            "freshness": freshness,
        }

    first_observed = _parse_ts(fixture.get("first_observed_ts"))
    retrieval = _parse_ts(fixture.get("retrieval_ts"))
    grid = fixture.get("poll_interval_at_capture_seconds") or 0
    if first_observed is None or retrieval is None:
        return {
            "opportunity_id": fixture.get("opportunity_id"),
            "display": "warning",
            "reason": "ABSENT_INPUT",
            "freshness": freshness,
        }

    raw_age_seconds = (retrieval - first_observed).total_seconds()
    age_lower = max(0.0, raw_age_seconds - grid)
    age_upper = raw_age_seconds + grid
    return {
        "opportunity_id": fixture.get("opportunity_id"),
        "display": "interval",
        "age_lower_seconds": age_lower,
        "age_upper_seconds": age_upper,
        "poll_grid_seconds": grid,
        "freshness": freshness,
    }


def render_mode_badge(scenario: dict[str, Any]) -> dict[str, Any]:
    """
    Mode badge (D024, section 7). Default and starting mode for every strategy is SHADOW.
    A requested transition away from SHADOW without an explicit user_required_gate_ref is
    refused: the badge renders SHADOW with a warning, and the requested mode is never shown
    as granted. This module never GRANTS a transition -- it can only refuse an ungated one.
    """
    requested = scenario.get("requested_mode", DEFAULT_MODE)
    gate_ref = scenario.get("user_required_gate_ref")

    if requested not in MODES:
        return {
            "badge_mode": DEFAULT_MODE,
            "requested_mode": requested,
            "warning": "UNKNOWN_MODE_REQUESTED_FORCED_TO_SHADOW",
        }

    if requested == "SHADOW" or requested == "OFF":
        return {"badge_mode": requested, "requested_mode": requested, "warning": None}

    # CONFIRM or AUTO requested.
    if not gate_ref:
        return {
            "badge_mode": DEFAULT_MODE,
            "requested_mode": requested,
            "warning": "MODE_TRANSITION_UNGATED_FORCED_TO_SHADOW",
        }

    # A gate_ref is present in the fixture, but this scaffold does not (and must not) verify
    # that a real USER_REQUIRED gate was actually granted -- it has no access to that ledger.
    # Per the mandate ("render SHADOW as default"), the shell still displays SHADOW as the
    # badge and surfaces the requested transition + gate reference as informational only.
    return {
        "badge_mode": DEFAULT_MODE,
        "requested_mode": requested,
        "user_required_gate_ref": gate_ref,
        "warning": "MODE_TRANSITION_NOT_SELF_VERIFIABLE_DISPLAYING_SHADOW",
    }


def check_reserved_arbitrage_term(opportunity_class: str, label_text: str) -> bool:
    """
    Return True iff usage is compliant: 'arbitrage' (any case) may appear in label_text only
    when opportunity_class == TRUE_CROSS_BOOK_ARBITRAGE (TAXONOMY.json reserved_terms).
    """
    contains_term = RESERVED_ARBITRAGE_TERM in label_text.lower()
    if not contains_term:
        return True
    return opportunity_class == RESERVED_ARBITRAGE_CLASS


def render_hard_risk_control_checklist(fixture: dict[str, Any]) -> dict[str, Any]:
    """
    Execution warnings (section 7 hard risk controls). Every one of the 11 frozen controls
    is rendered explicitly -- a control silently absent from the checklist is a defect. This
    scaffold's fixture data has all 11 unsatisfied, which is the honest state before any
    non-SHADOW execution path exists.
    """
    items = fixture.get("hard_risk_controls_checklist", [])
    present_controls = {item["control"] for item in items}
    missing_controls = [c for c in HARD_RISK_CONTROLS if c not in present_controls]
    rows = []
    for item in items:
        rows.append(
            {
                "control": item["control"],
                "satisfied": bool(item.get("satisfied", False)),
                "display": "warning" if not item.get("satisfied", False) else "ok",
            }
        )
    for c in missing_controls:
        rows.append({"control": c, "satisfied": False, "display": "warning_control_absent_from_fixture"})
    return {
        "rows": rows,
        "all_controls_present": len(missing_controls) == 0,
        "any_satisfied": any(r["satisfied"] for r in rows),
    }
