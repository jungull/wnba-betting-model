"""
U10_PREDICTION_API_SCHEMA -- `player_prediction_response/1`.

A versioned, MODEL-AGNOSTIC response schema plus its validator and its builder.

Epistemic status: PRODUCT SCAFFOLD built against fixtures. Carries no scientific
claim and must not imply a model has been promoted.

Three properties this module exists to guarantee, structurally rather than by
convention:

  1. MODEL AGNOSTICISM.  Nothing here knows which estimator produced a number.
     The model identity, its family, its artifact hashes and its control pairing
     arrive as DATA on a `ModelDescriptor`.  There is no branch, no default and
     no literal anywhere in this file that names an arm, a challenger or an
     incumbent.  `TESTS.py` enforces that by scanning this source against every
     identifier in `arm_registry.jsonl`.

  2. ABSENCE RENDERS AS A WARNING, NEVER AS A NUMBER.  A projection whose inputs
     are stale, missing or produced by a failed job is emitted WITHHELD: point
     null, uncertainty null, market edge null, and at least one BLOCKING warning
     naming the offending input.  The builder decides this; a caller cannot
     hand-assemble a served projection over a degraded input and get it past
     `validate_response`.  There is no fallback value, no last-known-good and no
     zero.

  3. VERSIONING.  Every response carries `schema` and `schema_version`, and the
     audit block repeats them so a stored response is self-describing after it
     leaves the process that made it.

Nothing in this module reads a model, a fit, an out-of-fold artifact or any
sealed result.  Its only runtime inputs are fixtures.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------
# Envelope identity and versioning
# --------------------------------------------------------------------------

SCHEMA_ID = "player_prediction_response"
SCHEMA_MAJOR = 1
SCHEMA_NAME = f"{SCHEMA_ID}/{SCHEMA_MAJOR}"
SCHEMA_VERSION = "1.0.0"

EPISTEMIC_STATUS = (
    "PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and "
    "must not imply a model has been promoted."
)

# The only promotion vocabulary the schema accepts.  A response cannot assert a
# promotion by inventing a word for it.
PROMOTION_STATUS_VALUES = (
    "no_challenger_promoted",
    "promoted_by_registered_decision",
)

FRESHNESS_VALUES = ("fresh", "stale", "missing")
JOB_STATUS_VALUES = ("ok", "failed", "not_run")
PROJECTION_STATUS_VALUES = ("served", "withheld")
WARNING_SEVERITY_VALUES = ("blocking", "advisory")
SUBJECT_TYPE_VALUES = ("player", "team")

# An input in any of these conditions is DEGRADED: it cannot support a number.
DEGRADED_FRESHNESS = ("stale", "missing")
DEGRADED_JOB_STATUS = ("failed", "not_run")

# --------------------------------------------------------------------------
# Prediction-path prohibition (call-site enforcement)
# --------------------------------------------------------------------------
#
# The settled primary target is REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS.
# Current-game realized overtime, game_minutes, duration, overtime periods and
# any exact or approximate same-game surrogate for those are prohibited from the
# prediction path.  `feature_gate.py` carries no name-based prohibition list
# (it audits rank, collinearity and offset dependence only), so this schema
# enforces the naming prohibition at ITS OWN call site.  It does not edit, wrap
# or weaken any shared gate; it refuses to SERIALISE a prohibited term.
#
# This list is deliberately conservative and matches on token boundaries.
PROHIBITED_PREDICTION_PATH_TERMS = (
    "game_minutes",
    "is_overtime",
    "overtime_periods",
    "n_overtime",
    "ot_periods",
    "realized_duration",
    "realized_minutes",
    "game_duration",
    "elapsed_minutes",
    "team_minutes",
    "player_minutes_realized",
    "regulation_seconds_remaining",
)

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class SchemaViolation(ValueError):
    """Raised by `validate_response` and by the builder's own guards."""


# --------------------------------------------------------------------------
# Version compatibility
# --------------------------------------------------------------------------


def parse_version(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SchemaViolation(f"schema_version is not semver: {v!r}")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def is_compatible(v: str) -> bool:
    """A consumer written against SCHEMA_VERSION can read `v`.

    Same major, and not from the future at minor level.  A different major is
    a different envelope name (`player_prediction_response/2`) and is NOT
    silently readable.
    """
    major, minor, _ = parse_version(v)
    my_major, my_minor, _ = parse_version(SCHEMA_VERSION)
    return major == my_major and minor <= my_minor


# --------------------------------------------------------------------------
# Descriptors -- everything model-specific arrives here as data
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelDescriptor:
    """Opaque model identity.

    `model_version` and `model_family` are strings this module never compares
    against a literal.  `artifact_sha256` binds the response to bytes.
    `control_pairing` records which control this model's numbers were produced
    against, or None when the producing pipeline declares none -- it is echoed,
    never interpreted.
    """

    model_version: str
    model_family: str
    artifact_sha256: dict[str, str]
    promotion_status: str
    control_pairing: str | None = None
    registry_record: str | None = None
    produced_by: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "model_family": self.model_family,
            "artifact_sha256": dict(sorted(self.artifact_sha256.items())),
            "promotion_status": self.promotion_status,
            "control_pairing": self.control_pairing,
            "registry_record": self.registry_record,
            "produced_by": self.produced_by,
        }


@dataclass(frozen=True)
class InputRecord:
    """One upstream input, with its freshness verdict already measured.

    `age_seconds` and `max_age_seconds` are supplied by the caller's clock; this
    module does not invent a now().  `freshness` is derived here from those two
    when both are present, so a caller cannot label a two-day-old file "fresh".
    """

    input_id: str
    source: str
    sha256: str | None
    as_of_utc: str | None
    observed_at_utc: str | None
    age_seconds: float | None
    max_age_seconds: float | None
    job_status: str
    declared_freshness: str | None = None

    def freshness(self) -> str:
        if self.sha256 is None and self.as_of_utc is None:
            return "missing"
        if self.age_seconds is None or self.max_age_seconds is None:
            # Unmeasurable age is not evidence of freshness.
            return self.declared_freshness or "missing"
        return "fresh" if self.age_seconds <= self.max_age_seconds else "stale"

    def is_degraded(self) -> bool:
        return (
            self.freshness() in DEGRADED_FRESHNESS
            or self.job_status in DEGRADED_JOB_STATUS
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "source": self.source,
            "sha256": self.sha256,
            "as_of_utc": self.as_of_utc,
            "observed_at_utc": self.observed_at_utc,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
            "job_status": self.job_status,
            "freshness": self.freshness(),
            "degraded": self.is_degraded(),
        }


@dataclass(frozen=True)
class Component:
    """One named contribution to a projection.

    `basis` says what the contribution IS (`prior`, `trailing_window`,
    `adjustment`, `offset`) without naming an estimator.
    """

    name: str
    basis: str
    contribution: float | None
    unit: str


@dataclass(frozen=True)
class MarketComparison:
    """Market side-by-side, or an explicit statement that there is none.

    `available=False` is a first-class outcome: line null, edge null, reason
    populated.  There is no "assume the line equals the projection" path.
    """

    available: bool
    book: str | None = None
    line: float | None = None
    over_price: int | None = None
    under_price: int | None = None
    captured_at_utc: str | None = None
    unavailable_reason: str | None = None

    def to_json(self, edge: float | None) -> dict[str, Any]:
        return {
            "available": self.available,
            "book": self.book,
            "line": self.line,
            "over_price": self.over_price,
            "under_price": self.under_price,
            "captured_at_utc": self.captured_at_utc,
            "unavailable_reason": self.unavailable_reason,
            "edge_vs_line": edge,
        }


@dataclass
class ProjectionSpec:
    """What the caller ASKS to be emitted.

    `point` and `uncertainty` are the numbers the producing pipeline computed.
    Whether they are actually SERIALISED is decided by the builder from
    `depends_on` against the input ledger -- not by the caller.
    """

    projection_id: str
    subject_type: str
    subject_id: str
    team_id: str
    target: str
    unit: str
    point: float | None
    uncertainty: dict[str, float | None]
    components: list[Component] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    market: MarketComparison | None = None


@dataclass(frozen=True)
class GameRef:
    game_id: str
    game_cluster_id: str
    season: int
    home_team_id: str
    away_team_id: str
    forecast_cutoff_utc: str
    scheduled_tip_utc: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_cluster_id": self.game_cluster_id,
            "season": self.season,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "scheduled_tip_utc": self.scheduled_tip_utc,
            "forecast_cutoff_utc": self.forecast_cutoff_utc,
        }


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _tokens(name: str) -> set[str]:
    return {t for t in _TOKEN_SPLIT.split(name.lower()) if t}


def prohibited_terms_in(name: str) -> list[str]:
    """Return prohibited prediction-path terms implicated by `name`.

    Matches a prohibited term when its own tokens are a contiguous subsequence
    of the candidate's tokens, so `team_minutes_lag1` and `home.game_minutes`
    are both caught while `minutes_played_prior_season_mean` is not caught by
    `team_minutes` (different tokens) and plain `minutes` is not a term.
    """
    cand = _TOKEN_SPLIT.split(name.lower())
    cand = [t for t in cand if t]
    hits: list[str] = []
    for term in PROHIBITED_PREDICTION_PATH_TERMS:
        tt = [t for t in _TOKEN_SPLIT.split(term) if t]
        n = len(tt)
        for i in range(len(cand) - n + 1):
            if cand[i : i + n] == tt:
                hits.append(term)
                break
    return hits


def inputs_digest(inputs: Iterable[dict[str, Any]]) -> str:
    """Order-independent digest binding the response to its input ledger."""
    rows = sorted(
        (
            f"{r['input_id']}|{r['sha256']}|{r['as_of_utc']}|"
            f"{r['job_status']}|{r['freshness']}"
        )
        for r in inputs
    )
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# --------------------------------------------------------------------------
# Builder -- the withholding decision lives here
# --------------------------------------------------------------------------

UNCERTAINTY_FIELDS = ("sd", "p10", "p50", "p90")


def build_response(
    *,
    response_id: str,
    generated_at_utc: str,
    request: dict[str, Any],
    game: GameRef,
    model: ModelDescriptor,
    inputs: list[InputRecord],
    projections: list[ProjectionSpec],
    code_version: str,
    fixture_mode: bool,
    node_id: str = "U10_PREDICTION_API_SCHEMA",
) -> dict[str, Any]:
    """Assemble a `player_prediction_response/1` document.

    The caller supplies numbers.  This function decides which of them may be
    serialised.  Any projection depending on a degraded input is withheld and
    a blocking warning is raised naming both the projection and the input.
    """
    input_json = [i.to_json() for i in inputs]
    by_id = {i.input_id: i for i in inputs}
    warnings: list[dict[str, Any]] = []

    for rec in inputs:
        if rec.freshness() == "missing":
            warnings.append(
                _warn(
                    "INPUT_MISSING",
                    "blocking",
                    f"input {rec.input_id!r} ({rec.source}) is absent; "
                    "no value is substituted",
                    f"input:{rec.input_id}",
                )
            )
        elif rec.freshness() == "stale":
            warnings.append(
                _warn(
                    "INPUT_STALE",
                    "blocking",
                    f"input {rec.input_id!r} is {rec.age_seconds}s old against a "
                    f"{rec.max_age_seconds}s bound",
                    f"input:{rec.input_id}",
                )
            )
        if rec.job_status == "failed":
            warnings.append(
                _warn(
                    "JOB_FAILED",
                    "blocking",
                    f"the job producing {rec.input_id!r} failed; its last "
                    "successful output is NOT reused",
                    f"input:{rec.input_id}",
                )
            )
        elif rec.job_status == "not_run":
            warnings.append(
                _warn(
                    "JOB_NOT_RUN",
                    "blocking",
                    f"the job producing {rec.input_id!r} has not run for this "
                    "cutoff",
                    f"input:{rec.input_id}",
                )
            )

    proj_json: list[dict[str, Any]] = []
    for spec in projections:
        for c in spec.components:
            bad = prohibited_terms_in(c.name)
            if bad:
                raise SchemaViolation(
                    f"projection {spec.projection_id!r} component {c.name!r} "
                    f"names prohibited prediction-path term(s) {bad}"
                )
        bad_t = prohibited_terms_in(spec.target)
        if bad_t:
            raise SchemaViolation(
                f"projection {spec.projection_id!r} target {spec.target!r} "
                f"names prohibited prediction-path term(s) {bad_t}"
            )

        unknown = [d for d in spec.depends_on if d not in by_id]
        blocking_inputs = [d for d in spec.depends_on if d in by_id and by_id[d].is_degraded()]

        for d in unknown:
            warnings.append(
                _warn(
                    "INPUT_UNDECLARED",
                    "blocking",
                    f"projection {spec.projection_id!r} declares dependency "
                    f"{d!r} which is absent from the input ledger",
                    f"projection:{spec.projection_id}",
                )
            )

        withheld_reasons: list[str] = []
        if unknown:
            withheld_reasons.append("undeclared_input")
        if blocking_inputs:
            withheld_reasons.append("degraded_input")
        if spec.point is None:
            withheld_reasons.append("no_value_produced")
        elif not _finite(spec.point):
            withheld_reasons.append("non_finite_value")

        served = not withheld_reasons

        if served:
            missing_unc = [
                f for f in UNCERTAINTY_FIELDS if not _finite(spec.uncertainty.get(f))
            ]
            if missing_unc:
                served = False
                withheld_reasons.append("incomplete_uncertainty")

        if not served:
            for d in blocking_inputs:
                warnings.append(
                    _warn(
                        "PROJECTION_WITHHELD",
                        "blocking",
                        f"projection {spec.projection_id!r} withheld: depends on "
                        f"degraded input {d!r} "
                        f"(freshness={by_id[d].freshness()}, "
                        f"job_status={by_id[d].job_status})",
                        f"projection:{spec.projection_id}",
                    )
                )
            if not blocking_inputs and not unknown:
                warnings.append(
                    _warn(
                        "PROJECTION_WITHHELD",
                        "blocking",
                        f"projection {spec.projection_id!r} withheld: "
                        + ", ".join(withheld_reasons),
                        f"projection:{spec.projection_id}",
                    )
                )

        market = spec.market or MarketComparison(
            available=False, unavailable_reason="no_market_capture_supplied"
        )
        if served and market.available and _finite(market.line):
            edge = round(float(spec.point) - float(market.line), 6)
        else:
            edge = None
            if market.available and not served:
                warnings.append(
                    _warn(
                        "MARKET_EDGE_SUPPRESSED",
                        "advisory",
                        f"a market line exists for {spec.projection_id!r} but no "
                        "edge is computed against a withheld projection",
                        f"projection:{spec.projection_id}",
                    )
                )
            if not market.available:
                warnings.append(
                    _warn(
                        "MARKET_UNAVAILABLE",
                        "advisory",
                        f"no market line for {spec.projection_id!r}: "
                        f"{market.unavailable_reason}",
                        f"projection:{spec.projection_id}",
                    )
                )

        proj_json.append(
            {
                "projection_id": spec.projection_id,
                "subject_type": spec.subject_type,
                "subject_id": spec.subject_id,
                "team_id": spec.team_id,
                "target": spec.target,
                "unit": spec.unit,
                "status": "served" if served else "withheld",
                "withheld_reasons": [] if served else sorted(set(withheld_reasons)),
                "point": float(spec.point) if served else None,
                "uncertainty": (
                    {f: float(spec.uncertainty[f]) for f in UNCERTAINTY_FIELDS}
                    if served
                    else {f: None for f in UNCERTAINTY_FIELDS}
                ),
                "components": [
                    {
                        "name": c.name,
                        "basis": c.basis,
                        "unit": c.unit,
                        "contribution": (
                            float(c.contribution)
                            if served and _finite(c.contribution)
                            else None
                        ),
                    }
                    for c in spec.components
                ],
                "depends_on": list(spec.depends_on),
                "market": market.to_json(edge),
            }
        )

    doc: dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "response_id": response_id,
        "generated_at_utc": generated_at_utc,
        "game": game.to_json(),
        "model": model.to_json(),
        "inputs": input_json,
        "projections": proj_json,
        "warnings": warnings,
        "audit": {
            "schema": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "node_id": node_id,
            "code_version": code_version,
            "fixture_mode": fixture_mode,
            "epistemic_status": EPISTEMIC_STATUS,
            "inputs_digest": inputs_digest(input_json),
            "request_echo": dict(request),
            "n_projections_served": sum(
                1 for p in proj_json if p["status"] == "served"
            ),
            "n_projections_withheld": sum(
                1 for p in proj_json if p["status"] == "withheld"
            ),
            "n_blocking_warnings": sum(
                1 for w in warnings if w["severity"] == "blocking"
            ),
        },
    }
    validate_response(doc)
    return doc


def _warn(code: str, severity: str, message: str, scope: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "scope": scope,
    }


# --------------------------------------------------------------------------
# Validator -- the invariants, checked on a plain dict
# --------------------------------------------------------------------------

INVARIANTS = (
    "I1_envelope_versioned",
    "I2_model_identity_is_opaque_data",
    "I3_every_input_carries_a_freshness_verdict",
    "I4_degraded_input_forces_withheld_projection",
    "I5_withheld_carries_no_number_and_a_blocking_warning",
    "I6_served_carries_finite_point_and_complete_uncertainty",
    "I7_no_prohibited_prediction_path_term_is_serialised",
    "I8_audit_block_is_complete_and_digest_recomputes",
    "I9_market_comparison_is_explicit_about_absence",
    "I10_game_identity_is_present_and_cluster_bound",
)


def validate_response(doc: dict[str, Any]) -> None:
    """Raise `SchemaViolation` on the first invariant breach."""
    _req(doc, ("schema", "schema_version", "response_id", "generated_at_utc",
               "game", "model", "inputs", "projections", "warnings", "audit"),
         "response")

    # I1
    if doc["schema"] != SCHEMA_NAME:
        raise SchemaViolation(f"I1: unknown envelope {doc['schema']!r}")
    if not is_compatible(doc["schema_version"]):
        raise SchemaViolation(
            f"I1: schema_version {doc['schema_version']!r} incompatible with "
            f"{SCHEMA_VERSION}"
        )
    if not _UTC_RE.match(doc["generated_at_utc"]):
        raise SchemaViolation("I1: generated_at_utc is not ISO-8601 UTC 'Z'")

    # I10
    g = doc["game"]
    _req(g, ("game_id", "game_cluster_id", "season", "home_team_id",
             "away_team_id", "scheduled_tip_utc", "forecast_cutoff_utc"), "game")
    for k in ("game_id", "game_cluster_id", "home_team_id", "away_team_id"):
        if not isinstance(g[k], str) or not g[k]:
            raise SchemaViolation(f"I10: game.{k} must be a non-empty string")
    if not _UTC_RE.match(g["forecast_cutoff_utc"] or ""):
        raise SchemaViolation("I10: game.forecast_cutoff_utc must be UTC 'Z'")

    # I2
    m = doc["model"]
    _req(m, ("model_version", "model_family", "artifact_sha256",
             "promotion_status", "control_pairing", "registry_record",
             "produced_by"), "model")
    if not isinstance(m["model_version"], str) or not m["model_version"]:
        raise SchemaViolation("I2: model.model_version must be a non-empty string")
    if m["promotion_status"] not in PROMOTION_STATUS_VALUES:
        raise SchemaViolation(
            f"I2: promotion_status {m['promotion_status']!r} outside "
            f"{PROMOTION_STATUS_VALUES}"
        )
    if not isinstance(m["artifact_sha256"], dict) or not m["artifact_sha256"]:
        raise SchemaViolation("I2: model.artifact_sha256 must be a non-empty map")
    for k, v in m["artifact_sha256"].items():
        if not isinstance(v, str) or not _SHA256_RE.match(v):
            raise SchemaViolation(f"I2: artifact_sha256[{k!r}] is not 64 hex chars")

    # I3
    if not isinstance(doc["inputs"], list) or not doc["inputs"]:
        raise SchemaViolation("I3: inputs must be a non-empty list")
    seen_inputs: set[str] = set()
    degraded: set[str] = set()
    for r in doc["inputs"]:
        _req(r, ("input_id", "source", "sha256", "as_of_utc", "observed_at_utc",
                 "age_seconds", "max_age_seconds", "job_status", "freshness",
                 "degraded"), "input")
        if r["input_id"] in seen_inputs:
            raise SchemaViolation(f"I3: duplicate input_id {r['input_id']!r}")
        seen_inputs.add(r["input_id"])
        if r["freshness"] not in FRESHNESS_VALUES:
            raise SchemaViolation(
                f"I3: input {r['input_id']!r} freshness {r['freshness']!r} "
                f"outside {FRESHNESS_VALUES}"
            )
        if r["job_status"] not in JOB_STATUS_VALUES:
            raise SchemaViolation(
                f"I3: input {r['input_id']!r} job_status {r['job_status']!r} "
                f"outside {JOB_STATUS_VALUES}"
            )
        is_deg = (
            r["freshness"] in DEGRADED_FRESHNESS
            or r["job_status"] in DEGRADED_JOB_STATUS
        )
        if bool(r["degraded"]) != is_deg:
            raise SchemaViolation(
                f"I3: input {r['input_id']!r} degraded flag disagrees with its "
                "freshness/job_status"
            )
        if is_deg:
            degraded.add(r["input_id"])
        if r["sha256"] is not None and not _SHA256_RE.match(str(r["sha256"])):
            raise SchemaViolation(
                f"I3: input {r['input_id']!r} sha256 is not 64 hex chars"
            )

    warns = doc["warnings"]
    if not isinstance(warns, list):
        raise SchemaViolation("warnings must be a list")
    for w in warns:
        _req(w, ("code", "severity", "message", "scope"), "warning")
        if w["severity"] not in WARNING_SEVERITY_VALUES:
            raise SchemaViolation(
                f"warning {w['code']!r} severity {w['severity']!r} outside "
                f"{WARNING_SEVERITY_VALUES}"
            )
    blocking_scopes = {w["scope"] for w in warns if w["severity"] == "blocking"}

    for iid in degraded:
        if f"input:{iid}" not in blocking_scopes:
            raise SchemaViolation(
                f"I4: degraded input {iid!r} carries no blocking warning"
            )

    seen_proj: set[str] = set()
    for p in doc["projections"]:
        _req(p, ("projection_id", "subject_type", "subject_id", "team_id",
                 "target", "unit", "status", "withheld_reasons", "point",
                 "uncertainty", "components", "depends_on", "market"),
             "projection")
        pid = p["projection_id"]
        if pid in seen_proj:
            raise SchemaViolation(f"duplicate projection_id {pid!r}")
        seen_proj.add(pid)
        if p["subject_type"] not in SUBJECT_TYPE_VALUES:
            raise SchemaViolation(f"projection {pid!r} bad subject_type")
        if p["status"] not in PROJECTION_STATUS_VALUES:
            raise SchemaViolation(f"projection {pid!r} bad status")

        for d in p["depends_on"]:
            if d not in seen_inputs:
                raise SchemaViolation(
                    f"I4: projection {pid!r} depends on {d!r}, absent from the "
                    "input ledger"
                )

        # I7
        for nm in [p["target"]] + [c["name"] for c in p["components"]]:
            bad = prohibited_terms_in(nm)
            if bad:
                raise SchemaViolation(
                    f"I7: projection {pid!r} serialises prohibited "
                    f"prediction-path term(s) {bad} in {nm!r}"
                )

        deg_deps = [d for d in p["depends_on"] if d in degraded]

        if p["status"] == "served":
            # I4
            if deg_deps:
                raise SchemaViolation(
                    f"I4: projection {pid!r} is served over degraded input(s) "
                    f"{deg_deps}"
                )
            # I6
            if not _finite(p["point"]):
                raise SchemaViolation(
                    f"I6: served projection {pid!r} has non-finite point"
                )
            for f in UNCERTAINTY_FIELDS:
                if not _finite(p["uncertainty"].get(f)):
                    raise SchemaViolation(
                        f"I6: served projection {pid!r} uncertainty.{f} missing"
                    )
            if p["withheld_reasons"]:
                raise SchemaViolation(
                    f"I6: served projection {pid!r} carries withheld_reasons"
                )
        else:
            # I5 -- no number may survive on a withheld projection
            if p["point"] is not None:
                raise SchemaViolation(
                    f"I5: withheld projection {pid!r} carries a point value"
                )
            for f in UNCERTAINTY_FIELDS:
                if p["uncertainty"].get(f) is not None:
                    raise SchemaViolation(
                        f"I5: withheld projection {pid!r} carries "
                        f"uncertainty.{f}"
                    )
            for c in p["components"]:
                if c["contribution"] is not None:
                    raise SchemaViolation(
                        f"I5: withheld projection {pid!r} carries a component "
                        f"contribution for {c['name']!r}"
                    )
            if p["market"].get("edge_vs_line") is not None:
                raise SchemaViolation(
                    f"I5: withheld projection {pid!r} carries a market edge"
                )
            if not p["withheld_reasons"]:
                raise SchemaViolation(
                    f"I5: withheld projection {pid!r} states no reason"
                )
            if f"projection:{pid}" not in blocking_scopes:
                raise SchemaViolation(
                    f"I5: withheld projection {pid!r} has no blocking warning"
                )

        # I9
        mk = p["market"]
        _req(mk, ("available", "book", "line", "over_price", "under_price",
                  "captured_at_utc", "unavailable_reason", "edge_vs_line"),
             "market")
        if mk["available"]:
            if not _finite(mk["line"]):
                raise SchemaViolation(
                    f"I9: projection {pid!r} market available with no line"
                )
        else:
            if mk["line"] is not None or mk["edge_vs_line"] is not None:
                raise SchemaViolation(
                    f"I9: projection {pid!r} market unavailable but carries a "
                    "number"
                )
            if not mk["unavailable_reason"]:
                raise SchemaViolation(
                    f"I9: projection {pid!r} market unavailable with no reason"
                )

    # I8
    a = doc["audit"]
    _req(a, ("schema", "schema_version", "node_id", "code_version",
             "fixture_mode", "epistemic_status", "inputs_digest",
             "request_echo", "n_projections_served", "n_projections_withheld",
             "n_blocking_warnings"), "audit")
    if a["schema"] != doc["schema"] or a["schema_version"] != doc["schema_version"]:
        raise SchemaViolation("I8: audit block disagrees with the envelope")
    if a["epistemic_status"] != EPISTEMIC_STATUS:
        raise SchemaViolation("I8: audit.epistemic_status was altered")
    recomputed = inputs_digest(doc["inputs"])
    if a["inputs_digest"] != recomputed:
        raise SchemaViolation(
            f"I8: inputs_digest {a['inputs_digest']} != recomputed {recomputed}"
        )
    served = sum(1 for p in doc["projections"] if p["status"] == "served")
    withheld = sum(1 for p in doc["projections"] if p["status"] == "withheld")
    if a["n_projections_served"] != served or a["n_projections_withheld"] != withheld:
        raise SchemaViolation("I8: audit projection counts disagree with the body")
    nb = sum(1 for w in warns if w["severity"] == "blocking")
    if a["n_blocking_warnings"] != nb:
        raise SchemaViolation("I8: audit blocking-warning count disagrees")


def _req(d: Any, keys: tuple[str, ...], what: str) -> None:
    if not isinstance(d, dict):
        raise SchemaViolation(f"{what} must be an object, got {type(d).__name__}")
    missing = [k for k in keys if k not in d]
    if missing:
        raise SchemaViolation(f"{what} missing required key(s): {missing}")
    extra = [k for k in d if k not in keys]
    if extra:
        raise SchemaViolation(f"{what} carries unknown key(s): {extra}")


def load_and_validate(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    validate_response(doc)
    return doc
