#!/usr/bin/env python3
"""ordering_contract.py -- CALL-SITE enforcement of the P28 primary/secondary ordering contract.

This module edits nothing. It does not import-and-patch `feature_gate.py`, `comparison_gate.py`,
`gate_invocation.py` or the frozen scorer. It is the wrapper a candidate's own run harness calls,
in this order:

    1.  seal_primary_verdict(record)        -> sealed primary verdict + its digest
    2.  authorize_downstream(sealed)        -> raises unless the primary verdict permits it
    3.  ... only now may the frozen turnover scorer be run ...
    4.  validate_downstream_receipt(receipt, sealed)
    5.  adjudicate(sealed, receipt)         -> the final verdict

Every function fails CLOSED: a missing field, an unknown field, an unsealed record or a broken
binding raises `OrderingContractFailure`. Nothing here can turn a primary FAIL into a PASS; the
adjudication function has no code path that reads a downstream number when the primary verdict is
FAIL, and that is asserted in TESTS.py.

Sign convention, fixed here and nowhere else: the primary metric is **MAE on
REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS**, and **lower is better**. `primary_delta_vs_k0`
is `challenger - K0_MATCHED`, so a **negative** delta is an improvement and a **positive** delta is
a worsening.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

CONTRACT_ID = "PRIMARY_SECONDARY_ORDERING_CONTRACT_v1"

PRIMARY_TARGET = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
PRIMARY_METRIC = "mae"
PRIMARY_LOWER_IS_BETTER = True

#: the frozen scorer and the exact line whose pairing creates the mismatch. Restated, never repaired.
FROZEN_SCORER = "experiments/player_program/run_turnover_p1_universe_fix.py"
FROZEN_SCORER_LINE = 149
FROZEN_SCORER_SHA256 = "612e0543a98f2ef945b7e92ff6b0c75679f5c8253f0a983a031918b993d57338"

DOCUMENTED_MISMATCH = {
    "exposure": "regulation-equivalent projected possessions",
    "outcome": "RAW full-game turnovers",
    # verbatim from EVIDENCE_PACKET_V2.downstream_operational_boundary.recorded_pairing.consumer
    "consumer": "run_turnover_p1_universe_fix.py:149, operational track",
    "status": "A KNOWN, DOCUMENTED MISMATCH on overtime games",
    "measured_gap_on_OT_rows_possessions": 11.0564,
    "measured_gap_on_non_OT_rows_possessions": 0.0,
    "n_OT_rows": 132,
    "n_OT_game_clusters": 66,
    "disposition": "RESTATED, NOT REPAIRED. The scorer is frozen.",
}

#: the epistemic role of every downstream number, pinned.
DOWNSTREAM_ROLE = "secondary_diagnostic"

#: carriers whose benefit channel is presumptively the raw/regulation-equivalent exposure
#: mismatch. Presence requires an ADJUDICATED non-mismatch channel demonstrated on the PRIMARY
#: target; absent that, the feature may not be credited (rule R5).
MISMATCH_CARRIER_PATTERNS = (
    r"trailing.*(ot|overtime)", r"(ot|overtime).*(rate|freq|propensity|prob|hazard)",
    r"(ot|overtime).*corrected", r"corrected.*(ot|overtime)",
    r"game_minutes", r"max_period", r"\bduration\b", r"overtime_period",
    r"(ot|overtime).*(adjust|inflat|scale|rescal)", r"(inflat|rescal).*(ot|overtime)",
    r"raw_(full_game|possessions|off_poss)", r"exposure_mismatch",
)

MISMATCH_CHANNEL_LABEL = "ot_mismatch_arbitrage"

PRIMARY_REQUIRED = (
    "schema", "contract_id", "candidate_id", "arm_id", "target", "metric_name",
    "lower_is_better", "k0_matched_arm_id", "row_universe_digest", "n_rows", "n_game_clusters",
    "primary_mae_challenger", "primary_mae_k0_matched", "primary_delta_vs_k0", "registered_med",
    "med_registered_before_fitting", "per_fold", "feature_channel_declarations", "verdict",
    "sealed_by", "downstream_computed",
)
PRIMARY_OPTIONAL = ("note", "uncertainty", "adjudications")

DOWNSTREAM_REQUIRED = (
    "schema", "contract_id", "candidate_id", "primary_verdict_digest", "epistemic_role",
    "scorer", "documented_mismatch_restated", "strata", "may_overturn_primary",
)
DOWNSTREAM_OPTIONAL = ("note", "pooled")

STRATA_REQUIRED = ("overtime", "regulation")
STRATUM_FIELDS = ("n_rows", "n_game_clusters", "mae")


class OrderingContractFailure(RuntimeError):
    """Raised on any ordering, binding, sign-convention or channel violation. Fail closed."""


# --------------------------------------------------------------------------- #
# digests
# --------------------------------------------------------------------------- #

def canonical_digest(obj: Mapping[str, Any], *, exclude: tuple[str, ...] = ()) -> str:
    """sha256 over a canonical JSON rendering, with `exclude` keys removed."""
    body = {k: v for k, v in obj.items() if k not in exclude}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _require(record: Mapping[str, Any], required: tuple[str, ...], optional: tuple[str, ...],
             what: str, findings: list[dict]) -> None:
    missing = [k for k in required if k not in record]
    if missing:
        findings.append({"kind": f"{what}_field_missing", "fields": sorted(missing)})
    unknown = [k for k in record if k not in required and k not in optional
               and k not in ("primary_verdict_digest", "sealed_at")]
    if unknown:
        findings.append({"kind": f"{what}_unknown_field", "fields": sorted(unknown),
                         "detail": "unknown keys are refused so a typo cannot silently disable a "
                                   "rule"})


# --------------------------------------------------------------------------- #
# R5 -- benefit-channel classification
# --------------------------------------------------------------------------- #

def classify_feature_channel(declaration: Mapping[str, Any]) -> dict:
    """Classify ONE declared feature's benefit channel.

    A declaration is `{"feature": str, "declared_benefit_channels": [str, ...],
    "primary_target_contribution_demonstrated": bool, "adjudication": str|None}`.
    """
    name = str(declaration.get("feature", ""))
    channels = list(declaration.get("declared_benefit_channels") or [])
    demonstrated = bool(declaration.get("primary_target_contribution_demonstrated", False))
    adjudication = declaration.get("adjudication")

    matched = [p for p in MISMATCH_CARRIER_PATTERNS if re.search(p, name, re.IGNORECASE)]
    declared_mismatch = MISMATCH_CHANNEL_LABEL in channels
    only_mismatch = bool(channels) and set(channels) == {MISMATCH_CHANNEL_LABEL}

    out = {"feature": name, "name_matches_mismatch_carrier": bool(matched),
           "matched_patterns": matched, "declared_channels": channels,
           "declares_mismatch_channel": declared_mismatch,
           "only_channel_is_the_mismatch": only_mismatch,
           "primary_target_contribution_demonstrated": demonstrated,
           "adjudication": adjudication, "creditable": True, "findings": []}

    if not channels:
        out["findings"].append({"kind": "benefit_channel_not_declared", "feature": name,
                                "detail": "R5 requires every declared feature to name its benefit "
                                          "channel(s); an undeclared channel is not creditable"})
    if only_mismatch:
        out["findings"].append({"kind": "benefit_channel_is_only_the_mismatch", "feature": name,
                                "detail": "the sole declared benefit channel is arbitrage of the "
                                          "raw/regulation-equivalent exposure mismatch"})
    if matched and not demonstrated:
        out["findings"].append({
            "kind": "mismatch_carrier_without_primary_contribution", "feature": name,
            "matched_patterns": matched,
            "detail": "a presumptive mismatch carrier may be credited only with an ADJUDICATED "
                      "non-mismatch channel demonstrated on the PRIMARY target"})
    if matched and demonstrated and not adjudication:
        out["findings"].append({
            "kind": "mismatch_carrier_adjudication_missing", "feature": name,
            "detail": "a demonstrated primary contribution must carry a named adjudication record"})
    out["creditable"] = not out["findings"]
    return out


# --------------------------------------------------------------------------- #
# step 1 -- seal the primary verdict
# --------------------------------------------------------------------------- #

def seal_primary_verdict(record: Mapping[str, Any], *, raise_on_block: bool = True) -> dict:
    """Validate and SEAL the primary verdict. Nothing downstream may be computed before this."""
    findings: list[dict] = []
    _require(record, PRIMARY_REQUIRED, PRIMARY_OPTIONAL, "primary", findings)

    if record.get("schema") != "player_program_primary_verdict/1":
        findings.append({"kind": "primary_schema_wrong", "got": record.get("schema")})
    if record.get("contract_id") != CONTRACT_ID:
        findings.append({"kind": "primary_contract_id_wrong", "got": record.get("contract_id")})
    if record.get("target") != PRIMARY_TARGET:
        findings.append({"kind": "primary_target_substituted", "got": record.get("target"),
                         "required": PRIMARY_TARGET,
                         "detail": "the primary target is settled and may not be swapped"})
    if record.get("metric_name") != PRIMARY_METRIC:
        findings.append({"kind": "primary_metric_substituted", "got": record.get("metric_name")})
    if record.get("lower_is_better") is not True:
        findings.append({"kind": "primary_sign_convention_wrong",
                         "detail": "MAE: lower_is_better must be True"})
    if record.get("downstream_computed") is not False:
        findings.append({
            "kind": "downstream_computed_before_primary_sealed",
            "detail": "R2: the primary verdict must be sealed BEFORE any downstream number "
                      "exists. downstream_computed must be False at seal time."})
    if not record.get("k0_matched_arm_id"):
        findings.append({"kind": "k0_matched_missing",
                         "detail": "K0_MATCHED is per arm (see P26); the primary verdict is "
                                   "against the arm's own matched null, not K0_FLAT"})
    if record.get("med_registered_before_fitting") is not True:
        findings.append({"kind": "med_not_registered_before_fitting",
                         "detail": "the minimum effect size on the PRIMARY target must be frozen "
                                   "before fitting, or the verdict is a post-hoc judgement"})
    if not record.get("per_fold"):
        findings.append({"kind": "per_fold_primary_verdict_missing",
                         "detail": "GATE_INVOCATION_CONTRACT s1: a pooled verdict does not "
                                   "discharge the per-fold obligation"})

    # sign-convention consistency and R4 (worsening primary is terminal)
    try:
        ch = float(record["primary_mae_challenger"])
        k0 = float(record["primary_mae_k0_matched"])
        delta = float(record["primary_delta_vs_k0"])
        if abs((ch - k0) - delta) > 1e-9:
            findings.append({"kind": "primary_delta_inconsistent", "challenger": ch, "k0": k0,
                             "declared_delta": delta, "recomputed": ch - k0,
                             "detail": "primary_delta_vs_k0 must equal challenger - K0_MATCHED"})
        worsens = delta > 0.0
        if worsens and record.get("verdict") != "FAIL":
            findings.append({
                "kind": "worsening_primary_not_marked_FAIL", "primary_delta_vs_k0": delta,
                "detail": "R4: a candidate whose PRIMARY regulation-equivalent possession MAE is "
                          "worse than its matched null FAILS. There is no downstream number that "
                          "can change this."})
        med = float(record["registered_med"])
        if med < 0.0:
            findings.append({"kind": "registered_med_negative", "got": med,
                             "detail": "the MED is a magnitude; it must be >= 0"})
        if (not worsens) and delta > -med and record.get("verdict") != "FAIL":
            findings.append({
                "kind": "primary_improvement_below_registered_med", "primary_delta_vs_k0": delta,
                "registered_med": med,
                "detail": "an improvement smaller than the pre-registered MED is not a pass"})
    except (KeyError, TypeError, ValueError) as exc:
        findings.append({"kind": "primary_metrics_unreadable", "detail": str(exc)})

    if record.get("verdict") not in ("PASS", "FAIL"):
        findings.append({"kind": "primary_verdict_not_binary", "got": record.get("verdict")})

    # R5 on the declared features. The per-feature findings are REPORTED on every record -- a FAIL
    # must still be sealable so that it can be recorded -- but they only BLOCK a PASS, because R5
    # is a rule about what may be CREDITED.
    channel_reports = [classify_feature_channel(d)
                       for d in (record.get("feature_channel_declarations") or [])]
    uncreditable = [c for c in channel_reports if not c["creditable"]]
    if record.get("verdict") == "PASS" and uncreditable:
        for c in uncreditable:
            findings.extend(c["findings"])
        findings.append({
            "kind": "uncreditable_feature_in_a_PASSING_candidate",
            "features": [c["feature"] for c in uncreditable],
            "detail": "R5: a feature whose only benefit channel is the exposure mismatch may not "
                      "be credited, so a candidate carrying one may not be recorded PASS"})

    sealed = dict(record)
    sealed["channel_reports"] = channel_reports
    sealed["ordering_findings"] = findings
    sealed["sealed"] = not findings
    sealed["primary_verdict_digest"] = canonical_digest(
        record, exclude=("primary_verdict_digest", "sealed_at"))
    if findings and raise_on_block:
        raise OrderingContractFailure(json.dumps(findings[:8], default=str))
    return sealed


# --------------------------------------------------------------------------- #
# step 2 -- the gate on entering the frozen scorer
# --------------------------------------------------------------------------- #

def authorize_downstream(sealed: Mapping[str, Any], *, raise_on_block: bool = True) -> dict:
    """R1/R3: may this candidate enter the frozen turnover scorer at all?

    Returns `{"authorized": bool, "findings": [...]}`. It reads NO downstream number, because at
    the moment this is called no downstream number is permitted to exist.
    """
    findings: list[dict] = []
    if not sealed.get("sealed"):
        findings.append({"kind": "primary_verdict_not_sealed",
                         "detail": "R1: the registered PRIMARY possession-target gate must be "
                                   "passed and sealed before the frozen turnover scorer runs"})
    if not sealed.get("primary_verdict_digest"):
        findings.append({"kind": "primary_verdict_digest_missing"})
    if sealed.get("verdict") != "PASS":
        findings.append({
            "kind": "primary_verdict_is_FAIL", "verdict": sealed.get("verdict"),
            "detail": "R3: a candidate that fails the primary possession-target gate does not "
                      "enter the frozen turnover scorer. No downstream number may be computed for "
                      "it, because a number that does not exist cannot rescue anything."})
    out = {"authorized": not findings, "findings": findings,
           "primary_verdict_digest": sealed.get("primary_verdict_digest"),
           "contract_id": CONTRACT_ID}
    if findings and raise_on_block:
        raise OrderingContractFailure(json.dumps(findings[:8], default=str))
    return out


# --------------------------------------------------------------------------- #
# step 4 -- the downstream receipt
# --------------------------------------------------------------------------- #

def validate_downstream_receipt(receipt: Mapping[str, Any], sealed: Mapping[str, Any], *,
                                raise_on_block: bool = True) -> dict:
    findings: list[dict] = []
    _require(receipt, DOWNSTREAM_REQUIRED, DOWNSTREAM_OPTIONAL, "downstream", findings)

    if receipt.get("schema") != "player_program_downstream_receipt/1":
        findings.append({"kind": "downstream_schema_wrong", "got": receipt.get("schema")})
    if receipt.get("contract_id") != CONTRACT_ID:
        findings.append({"kind": "downstream_contract_id_wrong", "got": receipt.get("contract_id")})
    if receipt.get("candidate_id") != sealed.get("candidate_id"):
        findings.append({"kind": "downstream_candidate_mismatch",
                         "downstream": receipt.get("candidate_id"),
                         "primary": sealed.get("candidate_id")})
    if receipt.get("epistemic_role") != DOWNSTREAM_ROLE:
        findings.append({"kind": "downstream_role_relabelled", "got": receipt.get("epistemic_role"),
                         "required": DOWNSTREAM_ROLE})
    if receipt.get("may_overturn_primary") is not False:
        findings.append({"kind": "downstream_claims_authority_over_primary",
                         "detail": "R3/R7: the downstream figure is reportable, never decisive"})

    # R2 -- the binding. A downstream receipt must bind the digest of the verdict that was sealed
    # BEFORE it, and that digest must still reproduce from the primary record's own bytes.
    bound = receipt.get("primary_verdict_digest")
    if bound != sealed.get("primary_verdict_digest"):
        findings.append({"kind": "primary_binding_broken", "bound": bound,
                         "sealed": sealed.get("primary_verdict_digest"),
                         "detail": "R2: the primary verdict was mutated, re-sealed or substituted "
                                   "after the downstream number was computed"})
    recomputed = canonical_digest({k: v for k, v in sealed.items()
                                   if k in PRIMARY_REQUIRED or k in PRIMARY_OPTIONAL},
                                  exclude=("primary_verdict_digest", "sealed_at"))
    if recomputed != sealed.get("primary_verdict_digest"):
        findings.append({"kind": "primary_verdict_mutated_after_sealing",
                         "recomputed": recomputed, "sealed": sealed.get("primary_verdict_digest")})

    # R6 -- the scorer is frozen and the mismatch is restated, not repaired
    sc = receipt.get("scorer") or {}
    if sc.get("file") != FROZEN_SCORER:
        findings.append({"kind": "scorer_substituted", "got": sc.get("file")})
    if sc.get("line") != FROZEN_SCORER_LINE:
        findings.append({"kind": "scorer_line_substituted", "got": sc.get("line")})
    if sc.get("sha256") != FROZEN_SCORER_SHA256:
        findings.append({"kind": "scorer_bytes_changed", "got": sc.get("sha256"),
                         "expected": FROZEN_SCORER_SHA256,
                         "detail": "R6: the scorer is FROZEN. The mismatch is restated, not "
                                   "repaired."})
    if sc.get("modified") is not False:
        findings.append({"kind": "scorer_declared_modified"})
    restated = receipt.get("documented_mismatch_restated") or {}
    for k, v in DOCUMENTED_MISMATCH.items():
        if restated.get(k) != v:
            findings.append({"kind": "documented_mismatch_not_restated_verbatim", "field": k,
                             "got": restated.get(k), "required": v})

    # R7 -- OT and non-OT reported separately, with row counts
    strata = receipt.get("strata") or {}
    for s in STRATA_REQUIRED:
        if s not in strata:
            findings.append({"kind": "downstream_stratum_missing", "stratum": s,
                             "detail": "the packet requires OT and non-OT diagnostics separately"})
            continue
        for fld in STRATUM_FIELDS:
            if fld not in strata[s]:
                findings.append({"kind": "downstream_stratum_field_missing", "stratum": s,
                                 "field": fld})

    out = {"valid": not findings, "findings": findings, "contract_id": CONTRACT_ID}
    if findings and raise_on_block:
        raise OrderingContractFailure(json.dumps(findings[:8], default=str))
    return out


# --------------------------------------------------------------------------- #
# step 5 -- adjudication
# --------------------------------------------------------------------------- #

def adjudicate(sealed: Mapping[str, Any],
               downstream_receipt: Mapping[str, Any] | None = None) -> dict:
    """The final verdict. The downstream number is READ ONLY FOR REPORTING.

    There is no branch in this function in which a downstream figure changes `final_verdict`.
    """
    primary = sealed.get("verdict")
    if primary != "PASS":
        return {
            "contract_id": CONTRACT_ID, "candidate_id": sealed.get("candidate_id"),
            "final_verdict": "FAIL", "decided_by": "PRIMARY_TARGET_ONLY",
            "primary_verdict": primary,
            "primary_delta_vs_k0": sealed.get("primary_delta_vs_k0"),
            "downstream_consulted": False,
            "reason": ("R3: the primary regulation-equivalent possession-target gate was not "
                       "passed. No downstream turnover figure was read, and none could have "
                       "changed this outcome."),
        }
    delta = float(sealed.get("primary_delta_vs_k0", 0.0))
    report = None
    if downstream_receipt is not None:
        strata = downstream_receipt.get("strata") or {}
        report = {"epistemic_role": DOWNSTREAM_ROLE, "may_overturn_primary": False,
                  "strata": {s: dict(strata.get(s, {})) for s in STRATA_REQUIRED},
                  "documented_mismatch": DOCUMENTED_MISMATCH}
    return {
        "contract_id": CONTRACT_ID, "candidate_id": sealed.get("candidate_id"),
        "final_verdict": "PASS", "decided_by": "PRIMARY_TARGET_ONLY",
        "primary_verdict": primary, "primary_delta_vs_k0": delta,
        "downstream_consulted": downstream_receipt is not None,
        "downstream_report": report,
        "reason": ("the candidate passed the registered PRIMARY possession-target gate against "
                   "its own K0_MATCHED. Any downstream turnover figure is reported as a SECONDARY "
                   "DIAGNOSTIC and contributed nothing to this verdict."),
    }


def contract_summary() -> dict:
    """The machine-readable statement of the contract itself."""
    return {
        "contract_id": CONTRACT_ID,
        "primary_target": PRIMARY_TARGET,
        "primary_metric": PRIMARY_METRIC,
        "primary_lower_is_better": PRIMARY_LOWER_IS_BETTER,
        "downstream_role": DOWNSTREAM_ROLE,
        "frozen_scorer": {"file": FROZEN_SCORER, "line": FROZEN_SCORER_LINE,
                          "sha256": FROZEN_SCORER_SHA256},
        "documented_mismatch": DOCUMENTED_MISMATCH,
        "rules": {
            "R1": "a candidate must pass its registered PRIMARY possession-target gate before it "
                  "may enter the frozen turnover scorer",
            "R2": "the primary verdict is SEALED (content-addressed) before any downstream number "
                  "is computed; the downstream receipt binds that digest",
            "R3": "no downstream number may rescue a primary FAIL; adjudicate() does not read one",
            "R4": "a candidate improving downstream turnover MAE while WORSENING the primary "
                  "regulation-equivalent possession target FAILS",
            "R5": "trailing overtime rate, or any feature whose only benefit channel is "
                  "arbitraging the raw/regulation-equivalent exposure mismatch, may not be credited",
            "R6": "the documented scorer mismatch is RESTATED, not repaired: the scorer is frozen",
            "R7": "downstream figures are reportable, never decisive, and OT / non-OT are reported "
                  "separately with row counts",
            "R8": "'PRIMARY' in this contract means the primary TARGET. comparison_gate's "
                  "primary_incremental_test means the primary CONTRAST (challenger_vs_k0). Both "
                  "must hold; neither substitutes for the other",
        },
    }


if __name__ == "__main__":                                        # pragma: no cover
    print(json.dumps(contract_summary(), indent=1))
