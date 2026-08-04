#!/usr/bin/env python3
"""build_final_matrix.py — the consolidated WS1-WS8 audit matrix.

The ranking at the end of discovery wave 1 is DERIVED FROM THIS MATRIX, not transcribed from
the handoff. That distinction is the whole point: the handoff's ranking was written before the
retrospective audit existed, and two of its load-bearing claims did not survive contact with the
artifacts.

Sources, all machine-read:
  * RETROSPECTIVE_GATE_AUDIT.json   two-axis classifications and their evidence
  * HYPOTHESIS_LEDGER.json          preregistration, commits, dispositions

Four things are deliberately NOT collapsed:
  * a valid null is not an integrity failure
  * a diagnostic is not a challenger
  * a fitted coefficient is not a forecast gain
  * a post-hoc audit is not proof that the current gate governed the original execution

Deterministic and idempotent: no wall-clock timestamps, sorted keys, stable ordering.

Run::

    python experiments/player_program/discovery_wave_1/build_final_matrix.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE / "RETROSPECTIVE_GATE_AUDIT.json"
LEDGER = HERE / "HYPOTHESIS_LEDGER.json"
OUT_JSON = HERE / "FINAL_AUDIT_MATRIX.json"
OUT_MD = HERE / "FINAL_AUDIT_MATRIX.md"

PREFIX_GATE_BLOB = "a8a8ea6416c9613302209a4c71008ef9927d6f82"

#: comparison parity is its own axis. A current-gate pass says nothing about it.
PARITY = {
    "k0_matched_control_present": "a featureless K0 from the arm's own pipeline exists and was fitted",
    "k0_present_via_companion_script": "a K0 exists but was produced by a second script, not the "
                                       "arm runner itself",
    "no_featureless_control_confound_uncontrolled": "no zero-feature control exists; the "
                                                    "free-intercept confound is uncontrolled",
    "not_applicable_no_fitted_intercept": "nothing is fitted, so there is no free-recalibration "
                                          "confound to control",
}

# ------------------------------------------------------------------------------------------
# Coordinator interpretation. Everything here is traceable to a cited artifact; the mechanical
# fields come from the audit and ledger and are NOT restated by hand.
# ------------------------------------------------------------------------------------------
INTERP: dict[str, dict] = {
    "ws1": {
        "hypothesis": "turnover rate changes most when a player occupies a substantially "
                      "DIFFERENT offensive role than normal, not merely a large one",
        "parity": "k0_matched_control_present",
        "valid_decision_metric": (
            "operational team MAE vs matched K0: L1_linear -0.00145 (CI [-0.00792,+0.00477]); "
            "N1_split -0.00378 (CI [-0.01170,+0.00343]). ZERO arms beat K0 with a CI excluding "
            "zero. Against the unfitted Arm D the arms look better, but K0 -- no features at all "
            "-- already collects +0.00326 of that."),
        "evidence_status": "original run contaminated; corrected rerun preserved and reproducible",
        "substantive_disposition": (
            "The tested projected-role formulation is FALSIFIED on the operational decision "
            "metric. The bounded expansion coefficient is stable -- +0.02647, sd 0.00175, "
            "positive in all five walk-forward folds -- but it is a COEFFICIENT, NOT A FORECAST "
            "GAIN. Intrinsic expansion-segment improvement vs K0 is +0.01314 with CI "
            "[-0.00032,+0.02771] INCLUDING zero, while the 2,283 non-expansion team-games are "
            "-0.00995 with CI [-0.01750,-0.00371] EXCLUDING zero, i.e. significantly worse. On "
            "the operational track the split is 946/1,968 and the sign REVERSES: -0.00758 vs D "
            "with expansion, +0.00632 without -- and that +0.00632 vanishes against K0 "
            "(-0.00089, CI spans zero)."),
        "role": "hypothesis_generating",
        "future_challenger": "NO. Retained only as a formulation-dependent discovery lead. A "
                             "genuinely cutoff-valid, player-specific responsibility-transition "
                             "measure could still matter; the tested role variables do not "
                             "justify a frozen challenger.",
    },
    "ws2": {
        "hypothesis": "turnovers rise specifically for players positioned to ABSORB missing "
                      "teammates' offensive responsibility",
        "parity": "k0_present_via_companion_script",
        "override_axis2": "invalid",
        "valid_decision_metric": (
            "NONE ESTABLISHED OPERATIONALLY. The operational design encoded did_appear through "
            "values produced by PRE-GATE imputation to 0.0: transfer_direct, transfer_allocated "
            "and transfer_role_sensitive are non-zero on 25,522 / 25,522 / 9,577 appearers and "
            "on ZERO of the 8,278 non-appearers, so a non-zero value certifies appearance. The "
            "published operational fit is therefore contaminated, and no clean operational rerun "
            "is preserved."),
        "evidence_status": "operational result INVALID as published; no clean corrected rerun "
                           "exists; intrinsic track classified separately",
        "substantive_disposition": (
            "INVALID AS PUBLISHED; THE FORMULATION REMAINS UNRESOLVED OPERATIONALLY. The "
            "player-level operational positive (T1 +0.00178, T2 +0.00225 vs K0, CIs excluding "
            "zero) is invalid. The aggregate null is NOT claimed to survive a fortiori: removing "
            "a favourable leak would usually weaken a positive, but refitting alters every "
            "coefficient and prediction, and no clean corrected aggregate result is in hand. The "
            "INTRINSIC track is classified separately and is not subject to the operational "
            "appearance leak, because intrinsic training folds contain appearers only. "
            "Responsibility-transfer directionality is HYPOTHESIS-GENERATING ONLY."),
        "role": "hypothesis_generating",
        "future_challenger": "NOT ON THIS EVIDENCE. A clean operational rerun would be required "
                             "before any claim, in either direction, about the aggregate.",
    },
    "ws3": {
        "hypothesis": "one model should not have to control BOTH how many turnovers a team "
                      "commits AND which players commit them",
        "parity": "k0_matched_control_present",
        "valid_decision_metric": (
            "two-stage team-total + compositional allocation did not improve player identity "
            "under fixed team totals; the premise as originally stated was withdrawn by the "
            "workstream itself"),
        "evidence_status": "preserved and reproducible; pooled-only gate invocation was "
                           "insufficient and the workstream's own fold_gate() caught it",
        "substantive_disposition": (
            "A VALID DISCOVERY NULL for this formulation, with a redirection. Fold-level "
            "retrospective audit supports it: ws3's own fold_gate() dropped "
            "proj_off_poss_share (std 7.80e-09) and p_active (std 5.14e-17) in the 2022 stage-2 "
            "fold, while the POOLED audit over the same 8 columns and 35,629 rows returned "
            "findings [] and passed. That pooled-versus-fold divergence is the measured "
            "justification for mandatory per-fold invocation."),
        "role": "diagnostic",
        "future_challenger": "NO. Its value is the redirection toward team-possession totals.",
    },
    "ws4": {
        "hypothesis": "one decay rate cannot suit both stable and unstable roles",
        "parity": "not_applicable_no_fitted_intercept",
        "valid_decision_metric": (
            "by-stratum deviance and team MAE against the frozen registered alpha=0.10 running "
            "through the identical state machine; error is monotone in memory LENGTH"),
        "evidence_status": "preserved and reproducible; unfitted state-machine comparison, no "
                           "feature design to audit",
        "substantive_disposition": (
            "FALSIFIED IN THE OPPOSITE DIRECTION from the hypothesis. Faster adaptation helps in "
            "NO stratum; the ordering favours longer memory and is directional and small. This "
            "is a valid null, not an integrity failure -- there is no feature matrix here to be "
            "unidentified. One team-level interval excludes zero (V5_dual_precision, +0.00331) "
            "and the workstream itself declines to claim it; recorded as a caveat, not a result."),
        "role": "diagnostic",
        "future_challenger": "NO.",
    },
    "ws5": {
        "hypothesis": "FGA share is an incomplete proxy for ball-handling responsibility",
        "parity": "k0_matched_control_present",
        "valid_decision_metric": (
            "conditional rate deviance and allocation weight quality vs K0; proxies fail as RATE "
            "predictors; allocation-only gain approximately +0.0017 (~0.2%) at the player level"),
        "evidence_status": "preserved and reproducible; features clean, gate passes post hoc",
        "substantive_disposition": (
            "PARTIAL, ALLOCATION ONLY. The expected direction is falsified: clean opportunity "
            "proxies do not improve the conditional rate, and the rate and interaction arms are "
            "CLOSED. A small player-level allocation value survives at zero team cost -- and by "
            "construction it cannot improve the team total, because projected exposure sums to "
            "exactly 5x projected team possessions."),
        "role": "diagnostic",
        "future_challenger": "NOT AS A RATE MODEL. Possible small value as an allocation weight "
                             "under fixed team totals.",
    },
    "ws6": {
        "hypothesis": "the arm G player-level gain and team-level loss arise from OFFSETTING "
                      "mechanism effects",
        "parity": "no_featureless_control_confound_uncontrolled",
        "valid_decision_metric": (
            "per-mechanism deviance and error contribution across 20 targets, 180 gate audits, "
            "max condition 1.549; NO promotion metric by design"),
        "evidence_status": "preserved and reproducible; fitted designs pass the current gate post "
                           "hoc, but NO featureless control exists, so the free-intercept "
                           "confound is uncontrolled",
        "substantive_disposition": (
            "MECHANISM CANCELLATION REJECTED AS THE CAUSE; the real cause was identified. The "
            "involvement proxy is a SHARE, so 92.6% of its variance is within-team: within "
            "effect +0.036, between effect -0.107, reversal present in 9 of 9 fitted mechanisms. "
            "Given a free coefficient the fit spends it at the team level, where it is wrong. "
            "This survives as an ARCHITECTURAL diagnostic."),
        "role": "diagnostic",
        "future_challenger": "NO. It is an explanation and a design direction, not a candidate.",
    },
    "ws7": {
        "hypothesis": "role and involvement effects may be hidden by linear pooling",
        "parity": "k0_matched_control_present",
        "valid_decision_metric": (
            "stratum-wise deviance and operational team MAE vs K0; null on the hypothesis and "
            "REFUTED on the decision metric for primary creators"),
        "evidence_status": "original run contaminated (WS7_RESULTS_v1_leaky.json preserved); "
                           "corrected v2 rebuild preserved and reproducible",
        "substantive_disposition": (
            "NULL ON THE HYPOTHESIS, ADVERSE ON THE DECISION METRIC, under the corrected rerun. "
            "Bounded nonlinear and heterogeneous formulations do not beat K0, and the "
            "primary-creator concentration hypothesis is refuted under the tested formulation. "
            "The leaky v1 run is retained as contaminated evidence and must not be cited."),
        "role": "hypothesis_generating",
        "future_challenger": "NO under the tested formulations.",
    },
    "ws8": {
        "hypothesis": "where does operational error actually come from: availability, candidate "
                      "precision, minute allocation, possession allocation, or rate",
        "parity": "not_applicable_no_fitted_intercept",
        "valid_decision_metric": (
            "incremental team MAE per labelled counterfactual: team possession-total projection "
            "+0.1033 [0.0833, 0.1244]; within-team allocation -0.0181 (the oracle is WORSE); "
            "availability -0.0034 (null); missing participants -0.0003 (null); ratio to the MAD "
            "floor 0.9969"),
        "evidence_status": "preserved and reproducible; oracle counterfactuals, not models",
        "substantive_disposition": (
            "DECISIVE ON DIRECTION. Team-possession-total projection is the clearest addressable "
            "team-aggregate exposure error. The rate model sits at its Poisson noise floor. "
            "Oracle variants are NOT models and are NOT promotion evidence."),
        "role": "diagnostic_only",
        "future_challenger": "NO ARM. It identifies WHERE to work, not WHAT to register.",
    },
}


def build() -> tuple[dict, str]:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    A, L = audit["workstreams"], ledger["workstreams"]
    lk = {k.split("_")[0]: k for k in L}

    rows = []
    for ws in [f"ws{i}" for i in range(1, 9)]:
        a, lg = A[ws], L[lk[ws]]
        m, it = lg["merge"], INTERP[ws]
        sup = m.get("superseded_commits") or []
        gate = a["gate_blob_used_during_execution"]
        blob = gate["blob"] if isinstance(gate, dict) else gate
        rows.append({
            "workstream": ws,
            "title": a.get("title", ""),
            "hypothesis": it["hypothesis"],
            "preregistration_commit": m.get("preregistration_commit"),
            "original_result_commit": sup[0] if sup else m.get("result_commit"),
            "corrected_result_commit": m.get("result_commit") if sup else None,
            "gate_blob_actually_used": blob,
            "gate_blob_is_the_prefix_blob": blob == PREFIX_GATE_BLOB,
            "gate_fixes_in_force_during_execution": {
                "55f4500_rank_and_conditioning": False,
                "42af2cd_informative_missingness": False,
            },
            "feature_design_integrity": a["axis1_feature_design_integrity"],
            "feature_design_integrity_rationale": a["axis1_rationale"],
            "comparison_parity": it["parity"],
            "comparison_parity_meaning": PARITY[it["parity"]],
            "comparison_parity_evidence": a["matched_k0_or_comparison_parity_status"],
            "decision_validity": it.get("override_axis2", a["axis2_decision_validity"]),
            "decision_validity_rationale": (
                it["substantive_disposition"] if "override_axis2" in it else a["axis2_rationale"]),
            "decision_validity_overridden_by_coordinator": "override_axis2" in it,
            "valid_decision_metric": it["valid_decision_metric"],
            "evidence_status": it["evidence_status"],
            "substantive_disposition": it["substantive_disposition"],
            "evidence_role": it["role"],
            "may_justify_future_frozen_challenger": it["future_challenger"],
            "execution_status": "COMPLETE",
            "integration_status": "INTEGRATED",
            "supporting_artifacts": a.get("exact_supporting_artifact"),
            "retrospective_audit_receipt": a.get("retrospective_audit_receipt"),
            "fold_level_audit_status": a.get("fold_level_audit_status"),
        })

    matrix = {
        "schema": "discovery_wave_1_final_audit_matrix/1",
        "wave": "discovery_wave_1",
        "lane": "DISCOVERY (development folds only)",
        "derived_from": [str(AUDIT.name), str(LEDGER.name)],
        "frozen_incumbent": ledger["frozen_incumbent"],
        "what_this_matrix_refuses_to_collapse": [
            "a valid null is NOT a failure of integrity",
            "a diagnostic is NOT a challenger",
            "a fitted coefficient is NOT a forecast gain",
            "a post-hoc audit is NOT proof that the current gate governed the original execution",
        ],
        "gate_governance_statement": (
            "The strengthened feature gate did NOT govern discovery wave 1. All eight result "
            f"commits carry the pre-fix blob {PREFIX_GATE_BLOB}; neither 55f4500 nor 42af2cd is "
            "an ancestor of any of them. Every classification on the feature-design axis is a "
            "RETROSPECTIVE application of the current gate, not a record of what ran."),
        "rows": rows,
        "wave_status": {
            "execution_status": "COMPLETE",
            "integrity_audit_status": "COMPLETE",
            "comparison_audit_status": "COMPLETE",
            "decision_status": "COMPLETE",
            "integration_status": "COMPLETE",
            "overall": "DISCOVERY WAVE 1 AUDIT COMPLETE; no challenger registered; Arm D unchanged",
        },
    }
    return matrix, render(matrix)


def render(mx: dict) -> str:
    L = ["# Discovery wave 1 — final audit matrix", "",
         "Derived from `RETROSPECTIVE_GATE_AUDIT.json` and `HYPOTHESIS_LEDGER.json`.",
         "The end-of-wave ranking is derived from THIS matrix, not transcribed from the handoff.",
         "", "## Gate governance", "", mx["gate_governance_statement"], "",
         "## What this matrix refuses to collapse", ""]
    L += [f"* {x}" for x in mx["what_this_matrix_refuses_to_collapse"]]
    L += ["", "## Matrix", "",
          "| WS | prereg | original | corrected | gate blob | feature-design integrity | "
          "comparison parity | decision validity | role |", "|---|---|---|---|---|---|---|---|---|"]
    for r in mx["rows"]:
        L.append("| {} | {} | {} | {} | {} | `{}` | `{}` | `{}` | {} |".format(
            r["workstream"], r["preregistration_commit"] or "—", r["original_result_commit"] or "—",
            r["corrected_result_commit"] or "—", r["gate_blob_actually_used"][:7],
            r["feature_design_integrity"], r["comparison_parity"], r["decision_validity"],
            r["evidence_role"]))
    L += ["", "All eight executed under the same pre-fix gate blob. Every feature-design "
              "classification is retrospective.", ""]
    for r in mx["rows"]:
        L += [f"### {r['workstream']} — {r['title']}", "",
              f"**Hypothesis.** {r['hypothesis']}", "",
              f"* preregistration: `{r['preregistration_commit'] or 'none'}`",
              f"* original result: `{r['original_result_commit'] or '—'}`",
              f"* corrected result: `{r['corrected_result_commit'] or 'none — original stands'}`",
              f"* gate blob actually used: `{r['gate_blob_actually_used'][:12]}` (pre-fix)",
              f"* feature-design integrity: `{r['feature_design_integrity']}`",
              f"* comparison parity: `{r['comparison_parity']}` — {r['comparison_parity_meaning']}",
              f"* decision validity: `{r['decision_validity']}`"
              + ("  **(coordinator override)**" if r["decision_validity_overridden_by_coordinator"]
                 else ""),
              f"* evidence role: **{r['evidence_role']}**",
              f"* execution: {r['execution_status']} · integration: {r['integration_status']}", "",
              f"**Valid decision metric.** {r['valid_decision_metric']}", "",
              f"**Evidence status.** {r['evidence_status']}", "",
              f"**Substantive disposition.** {r['substantive_disposition']}", "",
              f"**May justify a future frozen challenger?** {r['may_justify_future_frozen_challenger']}",
              "", f"Supporting artifact: `{r['supporting_artifacts']}`", ""]
    return "\n".join(L) + "\n"


def main() -> int:
    mx, md = build()
    OUT_JSON.write_text(json.dumps(mx, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.name} and {OUT_MD.name}: {len(mx['rows'])} rows")
    for r in mx["rows"]:
        print(f"  {r['workstream']:4s} {r['feature_design_integrity']:36s} "
              f"{r['decision_validity']:32s} {r['evidence_role']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
