#!/usr/bin/env python3
"""p38_finalize.py -- assemble SEALED_RESULTS/MANIFEST.json, EXECUTION_LOG.md and SPEC.json.

Reads sealed receipts PROGRAMMATICALLY for structural keys only (design columns, statuses,
hashes, seed digests). No performance field is ever extracted, printed or copied: the
extraction whitelist below is the complete list of receipt keys touched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import p38_driver as D

sys.path.insert(0, str(D.RUNNER_DIR))
import runner_constants as RC          # noqa: E402

EPISTEMIC_STATUS = (
    "SEALED RESULTS. Standing conditional authorisation: the fit executes automatically "
    "once P37 passes, because the preregistration and the implementation audit are exactly "
    "the conditions the contract requires. Outputs are sealed and unread until P39 verifies "
    "them.")

DISPATCH_COMMIT = "b8422d2ae16a29d0d65174f8cd4b0a1b0651744b"
DISPATCH_COMMIT_PROVENANCE = (
    "orchestration/GRAPH_EVENTS.jsonl agent_launched event for P38_BLINDED_FIT "
    "(ts 2026-08-06T22:52:46Z, workflow wf_6972ebba-bdb). git was NOT invoked by this node "
    "(standing rule 4: the coordinator makes the task-scoped commit); receipts therefore "
    "carry commit=null with the receipts.py commit_note, and this ledger-recorded HEAD is "
    "the commit the fleet executed from. CONTRADICTION RECORDED: receipts.py's own "
    "docstring expects run_git=True at P38; rule 4 of this node's contract forbids running "
    "git. The executor chose rule 4 and recorded the commit from the ledger instead.")

P_VALUE_FORMULA = ("p = min(1, 2*min( (1+#{delta_b <= 0})/(B+1), "
                   "(1+#{delta_b >= 0})/(B+1) ))")


def read_receipt_structural(path: Path) -> dict:
    """Whitelisted structural extraction from a sealed receipt. Keys touched, exhaustively:
    schema, arm_id, element_id, enumeration_element, manifest_digest, receipt_file_sha256,
    blinding.unsealed, guard_pins.all_match, code.sources, inputs,
    guard_records.p26.valid, guard_records.p23.valid, guard_records.p27.overall,
    guard_records.p27.fold_policy,
    guard_records.design_bundle_validation[FINAL].{arm,null}_design_columns/comparison,
    seeds.master_seed, seeds.per_fold (fold ids + stream digests only),
    folds[*].fold_id / folds[*].status, results.evaluable_folds,
    results.structurally_deactivated_folds. NOTHING ELSE IS READ."""
    rec = json.loads(path.read_text(encoding="utf-8"))
    gr = rec.get("guard_records", {}) or {}
    dbv = (gr.get("design_bundle_validation") or {}).get("FINAL_ASSEMBLED_DESIGN", {}) or {}
    seeds = rec.get("seeds", {}) or {}
    per_fold = {fid: {p: {"n_draws": v[p]["n_draws"], "stream_sha256": v[p]["stream_sha256"]}
                      for p in v}
                for fid, v in (seeds.get("per_fold") or {}).items()}
    return {
        "schema": rec.get("schema"),
        "arm_id": rec.get("arm_id"),
        "element_id": rec.get("element_id"),
        "enumeration_element": rec.get("enumeration_element"),
        "manifest_digest": rec.get("manifest_digest"),
        "receipt_file_sha256": rec.get("receipt_file_sha256"),
        "blinding_unsealed": (rec.get("blinding") or {}).get("unsealed"),
        "guard_pins_all_match": (rec.get("guard_pins") or {}).get("all_match"),
        "input_hashes": {k: v.get("sha256") for k, v in (rec.get("inputs") or {}).items()},
        "runner_source_hashes": {k: v.get("sha256")
                                 for k, v in ((rec.get("code") or {}).get("sources")
                                              or {}).items()},
        "p26_valid": (gr.get("p26") or {}).get("valid"),
        "p23_valid": (gr.get("p23") or {}).get("valid"),
        "p27_overall": (gr.get("p27") or {}).get("overall"),
        "p27_fold_policy": (gr.get("p27") or {}).get("fold_policy"),
        "k0_pairing": {"arm_design_columns": dbv.get("arm_design_columns"),
                       "null_design_columns": dbv.get("null_design_columns"),
                       "comparison": dbv.get("comparison")},
        "seed_master": seeds.get("master_seed"),
        "seed_streams_per_fold": per_fold,
        "fold_statuses": {f.get("fold_id"): f.get("status")
                          for f in (rec.get("folds") or [])},
        "evaluable_folds": (rec.get("results") or {}).get("evaluable_folds"),
        "deactivated_folds": (rec.get("results") or {}).get(
            "structurally_deactivated_folds"),
    }


def main():
    sealed_dirs = sorted(p for p in D.SEALED_P38.iterdir() if p.is_dir())
    arms = {}
    for d in sealed_dirs:
        entry = {"sealed_dir": f"stage2b/SEALED_RESULTS/P38/{d.name}"}
        side_p = d / "P38_EXECUTION_SIDECAR.json"
        if side_p.exists():
            side = json.loads(side_p.read_text(encoding="utf-8"))
            entry["status"] = side.get("status")
            entry["sidecar_sha256"] = D.sha256_file(side_p)
            entry["fold_exclusions"] = side.get("fold_exclusions")
            entry["exec_m7_p26_bind_outcome"] = (side.get("exec_m7_p26_bind") or {}).get(
                "outcome")
            entry["wall_seconds"] = side.get("wall_seconds")
            if side.get("error_type"):
                entry["error_type"] = side["error_type"]
                entry["error"] = side.get("error")
        blk = d / "BLOCK_VERDICT.json"
        if blk.exists():
            b = json.loads(blk.read_text(encoding="utf-8"))
            entry["status"] = b.get("verdict")
            entry["basis_mandate"] = b.get("basis_mandate")
            entry["block_verdict_sha256"] = D.sha256_file(blk)
        exc = d / "EXCLUSION_RECORD.json"
        if exc.exists():
            entry["status"] = "EXCLUDED_PRE_P38_PER_D039"
            entry["exclusion_record_sha256"] = D.sha256_file(exc)
        rc_p = d / "receipt.json"
        if rc_p.exists():
            entry["receipt"] = read_receipt_structural(rc_p)
            entry["receipt_sha256_measured"] = D.sha256_file(rc_p)
        gb = d / "GUARD_BLOCK_RECORD.json"
        if gb.exists():
            entry["guard_block_record_sha256"] = D.sha256_file(gb)
        bd = d / "BLOCK_DIAGNOSTICS.json"
        if bd.exists():
            diag = json.loads(bd.read_text(encoding="utf-8"))
            entry["block_diagnostics_sha256"] = D.sha256_file(bd)
            entry["p25_per_fold_verdicts"] = {
                fid: (v["verdict"] if v["verdict"] == "PASS" else
                      {"verdict": "BLOCK",
                       "fired": [(f.get("kind"), f.get("feature")) for f in v.get("fired", [])]})
                for fid, v in diag.get("p25_per_fold", {}).items()}
        arms[d.name] = entry

    # progress log facts
    prog = [json.loads(l) for l in (D.HERE / "progress.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    data_ready = next((e for e in prog if e["event"] == "data_ready"), {})
    fleet_done = [e for e in prog if e["event"] == "fleet_done"]
    wall_total = sum(e.get("wall_seconds_total", 0) for e in fleet_done)

    # fold structural facts (recomputed, cheap, deterministic)
    F, u, checks = D.build_universe()
    folds, fold_equiv = D.build_folds(F)
    fold_records = []
    for f in folds:
        gid = F["game_id"].to_numpy()
        fold_records.append({
            "fold_id": f["fold_id"],
            "n_train_rows": int(len(f["train_idx"])),
            "n_train_clusters": int(len(set(gid[f["train_idx"]]))),
            "n_test_rows": int(len(f["test_idx"])),
            "n_test_clusters": int(len(set(gid[f["test_idx"]]))),
            "season_mask_equals_date_cutoff_mask": bool(fold_equiv[f["fold_id"]]),
        })

    code_hashes = {}
    for name in ("p38_driver.py", "p38_wrappers.py", "p38_run_fleet.py", "p38_finalize.py",
                 "p38_block_diagnostics.py", "p38_write_log.py"):
        p = D.HERE / name
        if p.exists():
            code_hashes[f"stage2b/P38_BLINDED_FIT/{name}"] = D.sha256_file(p)
    arm_file_hashes = {}
    for d_ in sorted(D.ARMS_DIR.iterdir()):
        if d_.is_dir():
            for f_ in sorted(d_.glob("*.py")):
                arm_file_hashes[f"arms/{d_.name}/{f_.name}"] = D.sha256_file(f_)
    runner_hashes = {f"runner/{n}": D.sha256_file(D.RUNNER_DIR / n)
                     for n in ("runner.py", "runner_constants.py", "runner_interface.py",
                               "guard_harness.py", "cluster_bootstrap.py", "blinding.py",
                               "quasipoisson_irls.py", "seed_manifest.py", "receipts.py",
                               "k0_flat.py")}
    p35_hash = D.sha256_file(D.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json")

    manifest = {
        "schema": "p38_sealed_manifest/1",
        "node": "P38_BLINDED_FIT",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "epistemic_status": EPISTEMIC_STATUS,
        "authority": "D039_P37_ADJUDICATION (DECISION_LEDGER.jsonl); GRAPH_POLICY s5",
        "code": {
            "commit": DISPATCH_COMMIT,
            "commit_provenance": DISPATCH_COMMIT_PROVENANCE,
            "runner_sources_sha256": runner_hashes,
            "p38_executor_sources_sha256": code_hashes,
            "arm_module_sources_sha256": arm_file_hashes,
            "p35_spec_sha256_measured": p35_hash,
            "p35_spec_sha256_pinned": RC.P35_SPEC_SHA256,
            "p35_spec_pin_match": p35_hash == RC.P35_SPEC_SHA256,
        },
        "inputs": {
            "team_possession_prior_v1.parquet": {
                "path": str(D.PRIOR_PARQUET),
                "sha256_measured": D.sha256_file(D.PRIOR_PARQUET),
                "sha256_frozen_pin": "c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18"},
            "possessions_raw_v2.parquet": {
                "path": str(D.POSS_PARQUET),
                "sha256_measured": D.sha256_file(D.POSS_PARQUET),
                "sha256_frozen_pin": "7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a"},
        },
        "row_universe": {
            "n_rows": checks["n_rows"], "n_game_clusters": checks["n_clusters"],
            "row_universe_digest": checks["row_universe_digest"],
            "seasons": checks["seasons"],
            "target_column": RC.TARGET_COL_REAL,
            "offset_column": RC.OFFSET_COL,
            "offset_identity_max_abs_diff": checks[
                "log_exposure_max_abs_diff_vs_log_projection"],
            "cluster_column": RC.CLUSTER_COL,
            "contract_schedule_rows": 2990, "contract_schedule_games": 1495,
            "universe_construction": "possession_features.load_universe() "
                                     "(team_possession_universe/1), positional index",
        },
        "folds": {
            "policy_named_on_the_record": D.FOLD_POLICY_NAMED,
            "policy_basis": D.FOLD_POLICY_BASIS,
            "mandate": "EXEC-M2",
            "folds": fold_records,
        },
        "inference_pins": {
            "B_test_bootstrap": RC.B_TEST_BOOTSTRAP,
            "B_train_refit": RC.B_TRAIN_REFIT,
            "coef_interval_level": RC.COEF_INTERVAL_LEVEL,
            "irls": {"tol": RC.IRLS_TOL, "max_iter": RC.IRLS_MAX_ITER, "link": RC.LINK},
            "master_seed": RC.MASTER_SEED,
            "seed_derivation": RC.SEED_DERIVATION,
            "p_value_formula_byte_unchanged": P_VALUE_FORMULA,
            "p_value_mandate": "EXEC-M3: consumed byte-unchanged; cluster_bootstrap.py "
                               "sha256 above is the executed bytes",
            "k7_symmetric_na_rule": "as frozen (cluster_bootstrap.train_refit_bootstrap); "
                                    "NA for BOTH members, excluded from BOTH intervals, "
                                    "counts reported per arm/fold in every receipt",
            "k0_flat": "diagnostic only; offset-carrying reading is the referent of "
                       "'K0_FLAT' (D039 RAISED-1); both readings computed and labelled in "
                       "every receipt",
        },
        "executor_mandates": {
            "EXEC-M1": "per-fold P27 wrapper at the call site (p38_wrappers."
                       "P27GuardHarnessView + FoldGovernor); guard verdicts honoured "
                       "symmetrically; A07 >=2-fold retirement arithmetic implemented; "
                       "frozen guard/harness/runner bytes untouched",
            "EXEC-M2": "fold_policy=EXPANDING_PRIOR_SEASONS named on the record before any "
                       "real fit; lands in every P27 receipt (p27_fold_policy field)",
            "EXEC-M3": "bootstrap p-value formula consumed byte-unchanged",
            "EXEC-M4": "A09/A10 build_design re-bound at the call site to the 2,990-row "
                       "contract-schedule archive clock via the arms' own frozen pure "
                       "functions; the 2,982-row universe never used as the clock; clock "
                       "divergence measured and recorded in the A09/A10 sidecars; A08's "
                       "pace-column obligation recorded for its post-re-audit entry",
            "EXEC-M5": "A03 tier_symmetry_check invoked per fold, arm and null identically "
                       "(records in the A03 sidecar)",
            "EXEC-M6": "n_clock_pin scope adjudicated UNIVERSAL (frozen text precedence); "
                       "contract-clock branch taken: A20 and A23 (both bundles) BLOCKED "
                       "pending remediation nodes; A26 fitted under its two P37-verified "
                       "exact mitigations; structural exposure re-measured (openers record "
                       "in every sidecar)",
            "EXEC-M7": "p26_check(bind=True) invoked at scoring time for every fitted arm; "
                       "outcomes recorded per arm (bound / tolerated_r8_shape for "
                       "calibration_only raw-R8 shapes per the frozen P35 "
                       "r8_scope_adjudication / blocked)",
        },
        "arm_level_pins_carried": {
            "PIN-A13": "code's literal card-supported reading (any negative per-fold point "
                       "estimate fires beta3_negative_kill); docstring narrowing recorded "
                       "as rejected",
            "PIN-A12": "module's disclosed reading (sign(beta2) != sign(beta1), both "
                       "nonzero, any fold) WITH the beta1~=0 noise edge carried verbatim; "
                       "predicted-direction alternative preserved as the road not taken",
            "PIN-SIGN": "as-implemented sign-instability conventions pinned per arm: "
                        "A02/A03/A05 nonzero point-estimate signs over evaluable folds; "
                        "A08/A11 interval-excludes-zero folds only; missing-interval "
                        "conventions pinned as implemented (A05 counts missing as "
                        "covers-zero/kill-friendly; A02 blocks the non-rejection claim/"
                        "kill-unfriendly)",
            "PIN-A21": "A17's possession-weighted construction is the preregistered "
                       "reading; A21 blocked pending remediation-node rebuild "
                       "(implemented game-weighted construction recorded as rejected)",
            "PIN-A23-SIGN": "UNDECIDABLE_NO_PREDICTED_DIRECTION stands (C-level); A23 "
                            "blocked at P38 under EXEC-M6 regardless",
            "A2-C10": "concentrated-on-n<=5 pinned to majority share >= 0.5 (A07/A12), an "
                      "implementation pin, not frozen text",
            "A2-C9": "A02 degeneracy trigger sd(contrast)==0 implemented as min_std=1e-08 "
                     "floor (disclosed, affirmed)",
            "R-F2": "P26 R8 extended rule: the CODE rule (ALL declared tested parameters "
                    "null_value 0) is the implemented rule; the P36 SPEC '>=1' prose may "
                    "not be cited as the implemented rule",
        },
        "fleet": {
            "fit_eligible_arm_ids_measured": 20,
            "fit_eligible_module_instances_measured": 26,
            "instances_fitted_attempted": 22,
            "count_note": "D039 and the dispatch say '21 fit-eligible arms'; the measured "
                          "count is 20 arm ids (22 implemented arms minus A08 and A24). "
                          "Contradiction recorded in EXECUTION_LOG.md, not reconciled.",
            "arms": arms,
        },
        "wall_seconds_fleet": wall_total,
        "data_ready_record": data_ready,
        "raised_findings": {
            "P38-R1_p25_fold_local_whole_arm_escalation": (
                "RAISED, NOT RESOLVED IN-NODE. The frozen runner audits EVERY fold's design "
                "with P22/P25 (bundle loop) including folds the preregistration itself "
                "recognises as structurally degenerate (A12 card-deactivated train_lt_2022; "
                "A13/A14 preregistered active-set-rule collapses), and a P25 blocking "
                "finding in ANY single fold fails the whole arm closed -- the same "
                "whole-arm-vs-per-fold shape as R-F1, in the P25 branch, which P37 did not "
                "adjudicate and EXEC-M1 (worded for P27 only) does not cover. Measured "
                "consequence: 7 of 22 instances BLOCKED, every blocking finding fold-local "
                "(train_lt_2022 for A05/A12/A13/A15/A17/A22; the four pre-expansion folds "
                "for A14), every other fold PASS, FINAL design PASS for all seven. Two "
                "mechanisms, measured and sealed in BLOCK_DIAGNOSTICS.json per arm: "
                "(i) fired columns fold-constant (structurally zero) exactly in the "
                "recognised-degenerate folds (A12/A13/A14); (ii) fired columns GAME-LEVEL "
                "(constant within every game cluster) while the projection is game-shared "
                "for all 1,491 games, so every game pair is an offset tie group and the "
                "exact-determination clause reads any game-level column as offset-"
                "determined whenever the earliest fold's cross-game ties happen not to "
                "break constancy (A05/A17/A22 is_playoff_indicator; A15 pace_gap:asym). "
                "The executor held the fail-closed line: no ratified mandate authorises "
                "tolerating P25 findings at the call site, so the blocks stand as sealed "
                "results; a coordinator ruling (EXEC-M1-analogue for the runner's per-fold "
                "P22/P25 audits, or remediation nodes) is required before these arms can "
                "fit."),
        },
    }
    (D.SEALED / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print("MANIFEST written:", D.SEALED / "MANIFEST.json")
    print("manifest sha256:", D.sha256_file(D.SEALED / "MANIFEST.json"))
    return manifest, arms


if __name__ == "__main__":
    main()
