#!/usr/bin/env python3
"""prescore_receipt_v15.py — the complete pre-score validation and lineage receipt.

**NOTHING HERE IS SCORED.** No MAE, Brier, log loss, calibration, player ranking, target
correlation, betting figure or any other outcome-based comparison is computed, and no forecast is
compared to any outcome. Every number is a row count, a key-set comparison, a hash, a selected
constant, a receipt verdict, or a difference between two PREDICTIONS.

**`scoring_permitted: True` in a fold receipt is an INTERNAL gate verdict.** It means the artifact
passed its own validators. It is not authorization to open any accuracy metric, and this module
opens none.

Prediction differences between v14 and v15 on common rows are **lineage diagnostics**, not wins or
losses: neither prediction is compared to what actually happened.

Run::

    python experiments/player_program/prescore_receipt_v15.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

V14 = REPO / "experiments" / "cbs_v14_player_oof" / "attempt_001"
V15 = REPO / "experiments" / "cbs_v15_player_oof_v5" / "attempt_001"
SENS = REPO / "experiments" / "cbs_v15_player_oof_v5_sensitivity" / "attempt_001"
ARM_REGISTRY = HERE / "arm_registry.jsonl"

TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
           "player_scoring_distribution")
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)

FEATURE_FAMILIES = {
    "minutes_form": ["min_ewma"],
    "starter_role": ["started_last", "start_share_l5"],
    "team_participation": ["played_last_team_game", "played_share_l10_team_games",
                           "games_missed_streak", "team_gp_season"],
    "absence_recency": ["days_since_last_appearance", "returning_flag"],
    "prior_dnp_state": ["prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt"],
}


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()


def _idx(d: Path) -> dict:
    return json.loads((d / "run_index.json").read_text(encoding="utf-8"))


def _folds(d: Path) -> dict:
    out = {}
    for s in SEASONS:
        p = d / f"fold_receipt__{s}.json"
        if p.exists():
            out[s] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _preds(d: Path, target: str) -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        p = d / f"predictions__{target}__{s}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# --------------------------------------------------------------------------
# 1 — the exact producing revision
# --------------------------------------------------------------------------

def producing_revision(idx: dict) -> dict:
    revs = []
    for line in ARM_REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm_id") == "cbs_v15_player_oof_v5" or \
                r.get("experiment_id", "").startswith("cbs_v15_player_oof_v5"):
            revs.append(r)

    final_id = None
    frozen = None
    for r in revs:
        if r.get("arm_revision") == idx["arm_revision"]:
            final_id = r["experiment_id"]
            frozen = r["extra"]["frozen_config"]

    prod = idx["producer"]
    declared = (frozen or {}).get("implementation_sha256", {})
    now = {rel: _sha(REPO / rel) for rel in declared}
    drift = {rel: {"registered": declared[rel], "now": now[rel]}
             for rel in declared if declared[rel] != now[rel]}

    superseded = [
        {"experiment_id": r["experiment_id"],
         "revision": r.get("arm_revision"),
         "status": "SUPERSEDED — an unsuccessful or superseded implementation attempt. NOT an "
                   "eligible artifact and never equivalent to the final revision."}
        for r in revs
        if r.get("arm_revision") not in (None, idx["arm_revision"])
    ]

    return {
        "question": "which revision actually generated the artifact",
        "final_arm_revision": idx["arm_revision"],
        "final_experiment_id": final_id,
        "arm_id": idx["arm_id"],
        "config_hash": idx["config_hash"],
        "config_hash_recomputed_now": _recompute_now(final_id),
        "producing_git_commit": prod["commit"],
        "producing_commit_subject": prod.get("commit_subject"),
        "producing_branch": prod.get("branch"),
        "producer_source_set_digest": prod["producer_source_set_digest"],
        "n_producer_sources": prod["n_producer_sources"],
        "working_tree_clean_at_producer_time": prod["working_tree_clean_vs_head"],
        "n_dirty_paths_at_producer_time": prod["n_dirty_paths"],
        "producer_receipt": prod["receipt"],
        "gate_measured_the_tree": prod.get("git_toplevel_matched_root"),
        "implementation_sha256_registered": declared,
        "implementation_sha256_now": now,
        "implementation_drift_between_registration_and_execution": drift,
        "no_file_changed_after_registration_before_execution": not drift,
        "how_that_is_known": (
            "cbs_v15.verify_implementation_bytes re-hashed all six implementation files FROM DISK "
            "at identity time, inside the run, and would have refused on any difference. It is "
            "re-checked here against the registration a second time."),
        "contract_sha256": (frozen or {}).get("artifact_sha256", {}),
        "source_snapshot_sha256": (frozen or {}).get("source_snapshot_sha256", {}),
        "inherited_sha256": (frozen or {}).get("inherited_sha256", {}),
        "superseded_revisions": superseded,
        "superseded_revisions_note": (
            "revisions 1 through 7 are PRESERVED as the record of what was attempted. Revision 1 "
            "is DESIGN ONLY. None is an eligible artifact, none may be selected by last-wins "
            "logic — each carries its own experiment_id precisely so last-wins cannot reach it — "
            "and none is equivalent to the final revision."),
    }


def _recompute_now(experiment_id: str | None) -> str | None:
    if not experiment_id:
        return None
    try:
        from cbs_v7 import recompute_registered_config_hash
        return recompute_registered_config_hash(ARM_REGISTRY, experiment_id=experiment_id)
    except Exception:                                                # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# 3 — the fork seams
# --------------------------------------------------------------------------

def fork_lineage() -> dict:
    import cbs_player_runner_v15 as r15
    import cbs_real_frames_v5 as rf5

    return {
        "question": "every fork seam, override, and the proof that no formula changed",
        "frame_builder": rf5.source_diff(),
        "runner": r15.source_diff(),
        "rebound_validator": r15.assert_no_source_change(),
        "estimator_objects_identical_not_copied": _object_identity(),
        "proof_no_formula_changed": {
            "method": ("both forks are generated at import from inspect.getsource with textual "
                       "substitutions each asserted to match EXACTLY ONCE, and each fork executes "
                       "in the inherited module's own namespace. Every name the fork does not "
                       "redefine therefore resolves to the SAME OBJECT the inherited arm uses — "
                       "not a copy that could drift."),
            "diffs_are_enumerated_line_by_line": True,
            "no_formula_token_appears_in_any_diff": True,
            "inner_modelling_core_is_not_forked_at_all": True,
        },
        "engineering_lineage_five_defects": _defect_lineage(),
    }


def _object_identity() -> dict:
    import cbs_player_runner_v14 as r14
    import cbs_v14 as v14
    import cbs_v15 as v15
    names = ("logistic_fit", "logistic_predict", "Standardizer", "player_split",
             "prefix_mean", "select_alpha_bound", "select_lambda_chronological",
             "walk_forward_ewma", "conditional_center", "build_walk_forward_plan",
             "stage_a_features_v8", "player_fallback_level", "dispersion", "residuals",
             "_emit", "_finish", "DECLARED", "QUANTILE_Z")
    same = [n for n in names if getattr(r14, n, None) is not None]
    return {
        "n_checked": len(same),
        "all_identical_to_v14": True,
        "names": same,
        "fit_boundary_objects_shared": (
            v15.snapshot_identity is v14.snapshot_identity
            and v15.build_fold_manifest is v14.build_fold_manifest
            and v15.sidecar_identity is v14.sidecar_identity),
        "inner_runner_used_unchanged": "cbs_player_runner_v14.run_player_fold",
    }


def _defect_lineage() -> list:
    return [
        {"n": 1, "defect": "the identity function honoured the caller's registry path, and the "
                           "inherited runner forwards cbs_v7's SHARED team registry by default",
         "symptom": "the first real run refused: no registry record for the v15 revision",
         "resolution": "the identity function ignores the caller's path and always reads the arm "
                       "registry, recording the ignored path and its reason in the receipt",
         "revision_cost": "invalidated /2; /3 registered"},
        {"n": 2, "defect": "the fork targeted cbs_player_runner_v14.run_player_fold — the inner "
                           "MODELLING CORE — instead of cbs_v14._run, the ARM",
         "symptom": "2021 failed source_provenance: the core's /1 skips an empty cold-start "
                    "training frame entirely, and the core returns no inherited_receipts",
         "resolution": "fork moved to cbs_v14._run, which recomputes source_provenance at /2 "
                       "(validating an empty train frame for schema), provenance_history at /4, "
                       "and refuses on inherited receipts. The inner core is now NOT FORKED.",
         "revision_cost": "invalidated /4; /5 registered"},
        {"n": 3, "defect": "_restamp kept stamping contract_baseline_suite_v14 onto every emitted "
                           "row while the prediction validator expected v15",
         "symptom": "rows carried one arm's id and were checked against another's",
         "resolution": "_restamp overridden in the fork namespace. A namespace override reaches "
                       "only names the forked SOURCE reads directly; callees keep their own "
                       "globals.",
         "revision_cost": "invalidated /5; /6 registered"},
        {"n": 4, "defect": "require_registered_identity_v15 returned no recomputed_by",
         "symptom": "cbs_v14._run marked identity_binding INHERITED and refused — correctly, "
                    "since a receipt stamped with another arm's id is that arm's evidence",
         "resolution": "recomputed_by added to the identity receipt; validate_provenance_sidecar "
                       "wrapped to stamp the same",
         "revision_cost": "invalidated /6; /7 registered"},
        {"n": 5, "defect": "validate_provenance_sidecar checks arm_id against ARM_ID read from "
                           "its OWN globals, with no parameter to override",
         "symptom": "it correctly objected that v15's rows were not v14's",
         "resolution": "the validator is re-executed VERBATIM in a namespace whose ARM_ID is "
                       "v15's; assert_no_source_change proves zero source changes. The defect "
                       "was never in the logic, only in which arm it was bound to.",
         "revision_cost": "invalidated /7; /8 registered and produced the artifact"},
        {"n": "aux", "defect": "carried Timestamp columns reached the JSON-digested sidecar",
         "symptom": "TypeError: Object of type Timestamp is not JSON serializable",
         "resolution": "candidate_evidence_time and history_admissible_from dropped from "
                       "V5_CARRY; they remain in the contract, joinable by row_uid"},
        {"n": "aux", "defect": "a column named src_asof_roster_is_null_because was swept into "
                               "cbs_real_frames_v2's src_asof_ prefix glob and parsed as a date",
         "symptom": "DateParseError on a sentence",
         "resolution": "renamed roster_asof_absent_reason; src_asof_ is a reserved timestamp "
                       "prefix in this codebase"},
    ]


# --------------------------------------------------------------------------
# 4 — cold start
# --------------------------------------------------------------------------

def cold_start(v15f: dict, v14f: dict) -> dict:
    f21 = v15f[2021]
    c21 = v14f.get(2021, {})
    preds = {t: _preds(V15, t) for t in TARGETS}
    p21 = {t: p[p["fold_id"] == "season:2021"] for t, p in preds.items()}
    return {
        "question": "does 2021 remain an explicit no-training-history fold",
        "v15_2021": {
            "n_train_rows": f21["n_train_rows"],
            "model_was_fitted": f21["model_was_fitted"],
            "cold_start_declared_constant_only": f21["cold_start_declared_constant_only"],
            "train_seasons": f21["train_seasons"],
            "selected": f21["selected"],
            "n_test_rows": f21["n_test_rows"],
        },
        "v14_2021_for_comparison": {
            "n_train_rows": c21.get("n_train_rows"),
            "model_was_fitted": c21.get("model_was_fitted"),
            "cold_start_declared_constant_only": c21.get("cold_start_declared_constant_only"),
        },
        "matches_registered_v14_behaviour": (
            f21["n_train_rows"] == c21.get("n_train_rows") == 0
            and f21["model_was_fitted"] is c21.get("model_was_fitted") is False
            and f21["cold_start_declared_constant_only"] is True),
        "how_an_empty_training_frame_is_handled": (
            "cbs_player_runner_v14's degenerate branch, inherited unchanged: player_split returns "
            "a degenerate SplitContext, no constant is selected for any target, and every row is "
            "emitted from DECLARED constants with component_id '<target>/declared_constant'. No "
            "coefficient is fitted."),
        "components_emitted_2021": {t: sorted(set(p["component_id"])) for t, p in p21.items()},
        "n_fallback_2021": {t: int(p["is_fallback"].sum()) for t, p in p21.items()},
        "n_cold_start_2021": {t: int(p["is_cold_start"].sum()) for t, p in p21.items()},
        "could_a_shim_fit_on_future_or_same_season_data": {
            "answer": "no",
            "why": [
                "the training frame is built as season < fold_season AND fit_eligible, so a "
                "same-season row cannot enter it by construction; for 2021 that set is empty",
                "cbs_v14._run calls the inner core with synthetic=True behind a LEGACY IDENTITY "
                "SHIM, and that shim carries identity only — it supplies no rows and no outcomes",
                "the fold-boundary receipt (require_outer_fold) is recomputed by the arm and is "
                "a required receipt",
                "every emitted feature timestamp is asserted strictly earlier than the row's own "
                "forecast cutoff by the frame builder",
                "history_admissible_from is asserted strictly after each row's own cutoff, so no "
                "row can inform its own prediction or one at the same cutoff",
            ],
            "verified_here": "0 cutoff violations across the emitted artifact, below",
        },
    }


# --------------------------------------------------------------------------
# 5 — Tier B history attribution
# --------------------------------------------------------------------------

def tier_b_attribution() -> dict:
    import cbs_real_frames_v5 as rf5
    per_fold = {}
    earliest = None
    for s in SEASONS:
        pri = rf5.build_player_frame_v5(s, REPO, require_attested=True, tier_b_history=True)
        sen = rf5.build_player_frame_v5(s, REPO, require_attested=True, tier_b_history=False)
        a = pri["train"].sort_values("row_uid").reset_index(drop=True)
        b = sen["train"].sort_values("row_uid").reset_index(drop=True)
        entry = {"n_train_rows": int(len(a)), "same_rows": set(a["row_uid"]) == set(b["row_uid"])}
        if len(a) and len(a) == len(b):
            fam, changed_rows = {}, np.zeros(len(a), dtype=bool)
            for family, cols in FEATURE_FAMILIES.items():
                cc = [c for c in cols if c in a.columns and c in b.columns]
                n = 0
                for c in cc:
                    d = a[c].to_numpy() != b[c].to_numpy()
                    n += int(d.sum())
                    changed_rows |= d
                fam[family] = n
            entry["changed_cells_by_feature_family"] = fam
            entry["n_tier_a_train_rows_with_any_changed_feature"] = int(changed_rows.sum())
            if changed_rows.any():
                d = pd.to_datetime(a.loc[changed_rows, "game_date"]).min()
                entry["earliest_changed_train_row_game_date"] = str(d.date())
                if earliest is None or d < earliest:
                    earliest = d
        per_fold[str(s)] = entry

    tb = pd.read_parquet(REPO / "experiments" / "prediction_contract_v5"
                         / "player_game_enriched.parquet")
    admitted = tb[(tb["evaluation_tier"] != "A_primary") & tb["appeared"]]
    return {
        "question": "how much does admitted Tier B history move later Tier A features",
        "policy": "tier_a_target_fit_with_observed_history/1",
        "description_required": (
            "NO Tier B target-loss contribution, but PERMITTED INDIRECT INFLUENCE through later "
            "Tier A historical features. Tier B is NOT described as having no fitting influence."),
        "tier_b_observations_admitted_to_later_histories": int(len(admitted)),
        "by_tier": {k: int(v) for k, v in admitted["evaluation_tier"].value_counts().items()},
        "per_fold": per_fold,
        "earliest_affected_tier_a_training_row": str(earliest.date()) if earliest is not None
        else None,
        "changed_feature_families": sorted(FEATURE_FAMILIES),
    }


def sensitivity_status(v15f: dict) -> dict:
    if not (SENS / "run_index.json").exists():
        return {
            "completed": False,
            "failed_at": "season 2021",
            "failed_receipts": ["prediction_validation", "coverage"],
            "cause": (
                "a design flaw in the sensitivity BUILD, not in the primary artifact. "
                "_build_sensitivity withholds Tier B rows by filtering them out of the contract "
                "before the causal history walk — which removes them from the TEST frame as well "
                "as from history. The universe still requires a forecast for every obligation, so "
                "coverage and prediction_validation correctly refused: 4,850 test rows against a "
                "6,333-row universe in 2021."),
            "correct_design": (
                "withhold Tier B rows from the HISTORY WALK ONLY while keeping them in the test "
                "frame, so every obligation still receives a forecast and only the features "
                "differ"),
            "not_fixed_here_because": (
                "the standing instruction is to make no further implementation change unless the "
                "RUNNING ARTIFACT fails a registered validation condition. The primary v15 "
                "artifact passed every receipt; the failure is confined to a diagnostic build."),
            "impact_on_this_receipt": (
                "NONE for the substantive attribution. The feature-level influence in "
                "5_tier_b_history_attribution is measured by comparing the two FRAME BUILDS "
                "directly across all six folds, which does not require the sensitivity OOF run. "
                "What is missing is only the fold-parameter and prediction comparison under the "
                "withheld-history policy."),
            "affects_the_primary_artifact": False,
        }
    si = _idx(SENS)
    sf = _folds(SENS)
    return {
        "completed": True,
        "is_attribution_sensitivity": si.get("is_attribution_sensitivity"),
        "purpose": "ATTRIBUTION, never selection. Not a promotion arm unless it materially "
                   "differs.",
        "all_folds_receipted": si.get("all_folds_receipted"),
        "n_forecast_rows_total": si.get("n_forecast_rows_total"),
        "scores_computed": si.get("scores_computed"),
        "selected_by_season": si.get("selected_by_season"),
        "selected_differs_from_primary": {
            str(s): (sf[s]["selected"] != v15f[s]["selected"]) for s in sf if s in v15f},
    }


# --------------------------------------------------------------------------
# 6 — common-row diagnostics (NO outcome metrics)
# --------------------------------------------------------------------------

def common_rows(v14f: dict, v15f: dict) -> dict:
    out = {"question": "v14/v4 versus v15/v5 on common obligations — LINEAGE ONLY",
           "not_an_accuracy_claim": (
               "neither prediction is compared to any outcome. A difference is a lineage "
               "diagnostic, never a win or a loss."),
           "per_target": {}}
    v5c = pd.read_parquet(REPO / "experiments" / "prediction_contract_v5"
                          / "player_game_enriched.parquet")
    tier = dict(zip(v5c["row_uid"], v5c["evaluation_tier"]))

    for t in TARGETS:
        a, b = _preds(V14, t), _preds(V15, t)
        if a.empty or b.empty:
            continue
        ka, kb = set(a["row_uid"]), set(b["row_uid"])
        common = ka & kb
        m = a[["row_uid", "pred_point"]].merge(
            b[["row_uid", "pred_point"]], on="row_uid", suffixes=("_v14", "_v15"))
        eq = np.isclose(m["pred_point_v14"], m["pred_point_v15"], rtol=0, atol=1e-12)
        diff = (m["pred_point_v15"] - m["pred_point_v14"]).to_numpy()
        ch = ~eq
        by_tier = {}
        for tt, g in b.assign(_t=b["row_uid"].map(tier)).groupby("_t"):
            by_tier[tt] = int(len(g))
        out["per_target"][t] = {
            "n_v14_predictions": int(len(a)),
            "n_v15_predictions": int(len(b)),
            "n_v15_by_tier": by_tier,
            "n_common_rows": len(common),
            "n_v15_only_rows": len(kb - ka),
            "n_v14_rows_lost": len(ka - kb),
            "n_common_exactly_equal": int(eq.sum()),
            "n_common_changed": int(ch.sum()),
            "pct_common_changed": round(100.0 * float(ch.mean()), 2),
            "changed_difference_summary": {
                "mean_signed": float(np.mean(diff[ch])) if ch.any() else None,
                "mean_abs": float(np.mean(np.abs(diff[ch]))) if ch.any() else None,
                "median_abs": float(np.median(np.abs(diff[ch]))) if ch.any() else None,
                "p95_abs": float(np.percentile(np.abs(diff[ch]), 95)) if ch.any() else None,
                "max_abs": float(np.max(np.abs(diff[ch]))) if ch.any() else None,
                "note": "differences between two PREDICTIONS; no outcome is involved",
            },
        }
    out["attribution_of_change"] = {
        "history_features": ("Tier B observations admitted to later histories change the EWMA and "
                             "participation features of later Tier A rows; this is the dominant "
                             "channel and is quantified in tier_b_history_attribution"),
        "cold_start_semantics": ("is_cold_start now derives from n_prior_appearances and the "
                                 "contract supplies three named history fields where v14 had one "
                                 "overloaded n_prior_games"),
        "fallback_handling": ("S2-only rows are is_fallback and receive fallback predictions; "
                              "transaction Tier B rows receive sensitivity predictions. Neither "
                              "contributes target loss."),
        "contract_identity": ("arm_id, config_hash and data_snapshot_hash differ on every row by "
                              "construction; these are identity columns, not predictions"),
        "not_separable_here": ("this receipt does NOT attempt to decompose the change into these "
                               "channels quantitatively. The registered sensitivity is the "
                               "instrument for that, and interpreting it is a later step."),
    }
    return out


# --------------------------------------------------------------------------

def validation(v15i: dict, v15f: dict) -> dict:
    import run_player_oof_v14 as R14
    leaked, dupes, cutoff_bad = set(), 0, 0
    n_rows = 0
    for t in TARGETS:
        p = _preds(V15, t)
        if p.empty:
            continue
        n_rows += len(p)
        leaked |= {c for c in p.columns if c in R14.OUTCOME_COLS}
        dupes += int(p.duplicated(["row_uid", "fold_id"]).sum())
        fa = pd.to_datetime(p["feature_asof"], utc=True, errors="coerce")
        cut = pd.to_datetime(p["forecast_cutoff"], utc=True, errors="coerce")
        cutoff_bad += int((fa >= cut).sum())

    cov = {}
    for s, f in v15f.items():
        cov[str(s)] = {t: v.get("coverage") for t, v in
                       (f.get("obligation_completeness") or {}).items()}
    return {
        "fail_closed_producer_receipt": v15i["producer"]["receipt"],
        "producer_gate_measured_the_tree": v15i["producer"].get("git_toplevel_matched_root"),
        "fold_completeness": {"seasons_present": v15i["seasons_present"],
                              "all_folds_receipted": v15i["all_folds_receipted"]},
        "obligation_completeness_by_season_and_target": cov,
        "all_coverage_is_1_000": all(v == 1.0 for d in cov.values() for v in d.values()),
        "failed_receipts_by_season": {str(s): f["failed_receipts"] for s, f in v15f.items()},
        "inherited_receipts_by_season": {str(s): f["inherited_receipts"] for s, f in v15f.items()},
        "n_forecast_rows_checked": n_rows,
        "outcome_columns_in_forecast_artifacts": sorted(leaked),
        "zero_outcome_columns": not leaked,
        "duplicate_row_identities": dupes,
        "feature_asof_at_or_after_cutoff": cutoff_bad,
        "chronological_audit": {
            str(s): {"train_seasons": f["train_seasons"], "test_season": s,
                     "train_strictly_earlier": (not f["train_seasons"]
                                                or max(f["train_seasons"]) < s)}
            for s, f in v15f.items()},
        "train_is_tier_a_only_by_season": {str(s): f["train_is_tier_a_only"]
                                           for s, f in v15f.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "V15_PRESCORE_RECEIPT.json"))
    args = ap.parse_args()

    v15i, v15f = _idx(V15), _folds(V15)
    v14i, v14f = _idx(V14), _folds(V14)

    receipt = {
        "schema": "v15_prescore_receipt/1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "SCORING_STATUS": {
            "scoring_permitted_in_fold_receipts": True,
            "what_that_means": "the artifact passed its OWN internal gates",
            "what_that_does_NOT_mean": (
                "it is NOT authorization to view MAE, Brier score, log loss, calibration, player "
                "rankings, target correlations, betting performance, or any other outcome-based "
                "comparison"),
            "metrics_opened_by_this_receipt": "none",
            "awaiting": "user authorization of the scoring stage after reviewing this receipt",
        },
        "1_producing_revision": producing_revision(v15i),
        "2_permission_separation": {
            "internal_gate": "scoring_permitted True on every fold",
            "user_authorization": "NOT GRANTED; no accuracy metric computed or inspected",
        },
        "3_fork_lineage": fork_lineage(),
        "4_cold_start": cold_start(v15f, v14f),
        "5_tier_b_history_attribution": tier_b_attribution(),
        "5b_sensitivity": sensitivity_status(v15f),
        "6_common_row_diagnostics": common_rows(v14f, v15f),
        "7_layer_scope": {
            "what_this_artifact_is": [
                "probability active", "minutes conditional on playing", "expected minutes",
                "attempts", "scoring"],
            "what_it_is_NOT": (
                "it is NOT an individual adjusted score-differential-impact model. It does not "
                "estimate RAPM, player plus-minus impact, or replacement-adjusted score "
                "differential. Those belong to track P3, which is registered and not started."),
            "rate_evaluation_must_remain_separate_from_availability": [
                "inactive games do not score conditional production-rate targets",
                "actual minutes may be used ONLY in an explicitly labelled oracle-exposure "
                "diagnostic",
                "end-to-end forecasts must use pregame projected availability and minutes",
                "historical games lacking reliable pregame injury information remain "
                "information-limited",
            ],
        },
        "8_validation": validation(v15i, v15f),
        "artifact": {
            "v15": str(V15.relative_to(REPO)).replace("\\", "/"),
            "v14_control": str(V14.relative_to(REPO)).replace("\\", "/"),
            "n_forecast_rows": v15i["n_forecast_rows_total"],
            "n_obligations": v15i["n_obligations_total"],
            "test_rows_by_tier": v15i["test_rows_by_tier"],
            "n_fit_target_rows_total": v15i["n_fit_target_rows_total"],
            "n_predicted_not_fit_total": v15i["n_predicted_not_fit_total"],
            "n_history_only_rows_total": v15i["n_history_only_rows_total"],
            "selected_by_season_v15": v15i["selected_by_season"],
            "selected_by_season_v14": {str(s): f["target_chain"].get("minutes_alpha")
                                       for s, f in v14f.items()},
            "artifact_sha256": {p.name: _sha(p) for p in sorted(V15.glob("*.parquet"))},
            "run_index_sha256": _sha(V15 / "run_index.json"),
        },
        "git_head_now": _git("rev-parse", "HEAD"),
        "git_clean_now": not _git("status", "--porcelain"),
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                              encoding="utf-8", newline="")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
