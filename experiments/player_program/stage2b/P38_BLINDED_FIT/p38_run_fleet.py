#!/usr/bin/env python3
"""p38_run_fleet.py -- execute the P38 blinded fleet through the frozen runner.

Usage:  python p38_run_fleet.py            (whole fleet)
        python p38_run_fleet.py A25 A02    (named arm codes only; used for staged execution)

Emits ONLY operational facts to stdout/progress log. All results land sealed under
stage2b/SEALED_RESULTS/P38/. See p38_driver.py for the mandate map.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import p38_driver as D
from p38_wrappers import (FoldGovernor, P27GuardHarnessView, a03_tier_records,
                          a07_near_affinity_records, history_bound_a09, history_bound_a10,
                          measure_clock_divergence)

# the runner unsealing flag: P38 is the only context in which it may exist (RUNNER_INTERFACE
# section 6). This process IS the P38 executor.
import os
os.environ["P38_UNSEALED"] = "1"

sys.path.insert(0, str(D.RUNNER_DIR))
import guard_harness as gh                     # noqa: E402  (frozen harness, imported)
import runner as runner_mod                    # noqa: E402  (frozen runner, imported)

PROGRESS = D.HERE / "progress.jsonl"
INPUT_PATHS = {"team_possession_prior_v1.parquet": str(D.PRIOR_PARQUET),
               "possessions_raw_v2.parquet": str(D.POSS_PARQUET)}


def log(event: dict):
    event = dict(event)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with open(PROGRESS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str) + "\n")
    print(json.dumps(event, default=str), flush=True)


def write_json(path: Path, obj) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return D.sha256_file(path)


# ------------------------------------------------------------------------------ inventory --
def build_inventory(F, folds, archive, poss, lineup, prior):
    """Every fit-eligible module instance (one per enumeration element), with its P38
    construction record. A08/A24 are excluded pre-P38 (D039); A20/A21/A23 are blocked by
    executor mandate/pin (EXEC-M6 / PIN-A21) and never constructed."""
    fold_ids = [f["fold_id"] for f in folds]
    n_rows = len(F)
    sched = archive[["game_id", "team_id", "game_date", "season"]]
    inv = []

    a02 = D.import_arm("A02", "arm_a02.py")
    inv.append({"key": "A02_cal_blend_contrast__single", "arm_code": "A02",
                "module": a02.ArmA02(fold_ids, n_rows), "m4": None, "extra": {}})

    a03 = D.import_arm("A03", "arm_a03.py")
    inv.append({"key": "A03_cal_shallow_tier_intercept__t3", "arm_code": "A03",
                "module": a03.ArmA03(fold_ids, n_rows), "m4": None, "extra": {},
                "a03_module": a03})

    a05 = D.import_arm("A05", "a05_cal_playoff_intercept.py")
    inv.append({"key": "A05_cal_playoff_intercept__single", "arm_code": "A05",
                "module": a05.A05CalPlayoffIntercept(fold_ids), "m4": None, "extra": {}})

    a07 = D.import_arm("A07", "A07_early_season_transient.py")
    inv.append({"key": "A07_early_season_transient__single", "arm_code": "A07",
                "module": a07.A07EarlySeasonTransient(sched, fold_ids, n_rows),
                "m4": {"binding": "contract_schedule (2,990 rows) constructor-bound, per "
                                  "the frozen module's own signature"},
                "extra": {}, "a07_module": a07})

    a09 = D.import_arm("A09", "arm.py")
    uni_hist = F[["team_id", "game_id", "game_date"]].merge(
        archive[["team_id", "game_id", "n_off_poss", "max_period"]],
        on=["team_id", "game_id"], how="left", validate="1:1")
    div09 = measure_clock_divergence(a09.align_n_t_d_t_by_key, uni_hist,
                                     archive, key_cols=("team_id", "game_id"))
    for inst in a09.make_arms(fold_ids, n_rows):
        inv.append({"key": inst.element_id(), "arm_code": "A09", "module": inst,
                    "m4": {"binding": "EXEC-M4 call-site wrapper: build_design re-bound to "
                                      "the arm's own frozen pure functions with the "
                                      "2,990-row contract-schedule archive as the clock; "
                                      "the 2,982-row universe supplies target keys only "
                                      "and never enters the clock",
                           "history_rows": int(len(archive)),
                           "history_games": int(archive["game_id"].nunique()),
                           "clock_divergence_universe_vs_contract": div09},
                    "extra": {}, "override": history_bound_a09(a09, inst, archive)})

    a10 = D.import_arm("A10", "arm.py")
    for inst in a10.make_arms(fold_ids, n_rows):
        inv.append({"key": inst.element_id(), "arm_code": "A10", "module": inst,
                    "m4": {"binding": "EXEC-M4 call-site wrapper (as A09); d_t shared "
                                      "construction, c_t EWMA on the same contract clock",
                           "history_rows": int(len(archive)),
                           "history_games": int(archive["game_id"].nunique()),
                           "clock_divergence_universe_vs_contract": div09},
                    "extra": {}, "override": history_bound_a10(a10, inst, archive)})

    a11 = D.import_arm("A11", "arm_a11.py")
    for inst in a11.make_arms(archive, fold_ids, n_rows):
        inv.append({"key": inst.element_id(), "arm_code": "A11", "module": inst,
                    "m4": {"binding": "contract-schedule archive constructor-bound (the "
                                      "module's own frozen pattern)"}, "extra": {}})

    a12 = D.import_arm("A12", "A12_carryover_additive_decay.py")
    inv.append({"key": "A12_carryover_additive_decay__single", "arm_code": "A12",
                "module": a12.A12CarryoverAdditiveDecay(archive, fold_ids, n_rows,
                                                        pace_col="pace"),
                "m4": {"binding": "contract-schedule archive constructor-bound; pace column "
                                  "computed by the frozen lagged_regulation_equivalent_pin "
                                  "formula at the call site"}, "extra": {}})

    a13 = D.import_arm("A13", "arm_a13.py")
    inv.append({"key": "A13_carryover_roster_continuity_moderator__single", "arm_code": "A13",
                "module": a13.make_arms(sched, archive, lineup, fold_ids, n_rows)[0],
                "m4": {"binding": "contract schedule + realised-history archive + lineup "
                                  "membership (off_p1..5/def_p1..5 collapsed to (team_id, "
                                  "game_id, player_id)) constructor-bound"}, "extra": {}})

    a14 = D.import_arm("A14", "A14_expansion_intercept_decay.py")
    inv.append({"key": "A14_expansion_intercept_decay__single", "arm_code": "A14",
                "module": a14.A14ExpansionInterceptDecay(sched, fold_ids, n_rows),
                "m4": {"binding": "contract schedule constructor-bound"}, "extra": {}})

    a15 = D.import_arm("A15", "A15_gap_by_depth_asymmetry.py")
    inv.append({"key": "A15_gap_by_depth_asymmetry__single", "arm_code": "A15",
                "module": a15.A15GapByDepthAsymmetry(fold_ids, n_rows), "m4": None,
                "extra": {}})

    a16 = D.import_arm("A16", "arm_a16.py")
    inv.append({"key": "A16_lag_residual_own_minus_opp", "arm_code": "A16",
                "module": a16, "m4": None, "extra": {}})

    a17 = D.import_arm("A17", "a17_transition_mix_share.py")
    inv.append({"key": "A17_transition_mix_share__single", "arm_code": "A17",
                "module": a17.A17TransitionMixShare(poss, fold_ids),
                "m4": {"binding": "possessions_raw_v2 constructor-bound (season column "
                                  "normalised to int at the call site; artifact bytes "
                                  "untouched)"}, "extra": {}})

    a18 = D.import_arm("A18", "arm_a18.py")
    inv.append({"key": "A18_median_duration_contrast", "arm_code": "A18",
                "module": a18.make_arm(poss, fold_ids, n_rows)[0],
                "m4": {"binding": "possessions_raw_v2 constructor-bound; A3-C5: the E-clock "
                                  "game set equals the contract-schedule game set "
                                  "(1,495 games), measured at P37"}, "extra": {}})

    a22 = D.import_arm("A22", "arm_a22.py")
    inv.append({"key": "A22_lineup_churn_tv_distance__single", "arm_code": "A22",
                "module": a22.make_arms(fold_ids, n_rows, lineups=poss)[0],
                "m4": {"binding": "possessions_raw_v2 constructor-bound as the lineup "
                                  "source (off_p1..off_p5)"}, "extra": {}})

    a25 = D.import_arm("A25", "arm_a25.py")
    inv.append({"key": "A25_home_offense_contrast__single", "arm_code": "A25",
                "module": a25.make_arm(fold_ids)[0], "m4": None, "extra": {}})

    a26 = D.import_arm("A26", "arm_a26.py")
    inv.append({"key": "A26_sos_correction_own_minus_opp", "arm_code": "A26",
                "module": a26.make_arm(poss, fold_ids, n_rows)[0],
                "m4": {"binding": "possessions_raw_v2 constructor-bound; EXEC-M6: fitted on "
                                  "the contract-clock adjudication with the two P37-verified "
                                  "exact mitigations carried (league-mean cancellation is an "
                                  "algebraic identity in z5; residual divergence confined to "
                                  "2021 opener-team rows and early-season opponents' LOO "
                                  "means)"}, "extra": {}})
    return inv


# ------------------------------------------------------------------------------ execution --
def execute_instance(entry, F, folds, basis, openers_record):
    key = entry["key"]
    t0 = time.time()
    out_dir = D.SEALED_P38 / key
    sidecar = {
        "schema": "p38_execution_sidecar/1",
        "element": key, "arm_code": entry["arm_code"],
        "fold_policy_named": D.FOLD_POLICY_NAMED,
        "fold_policy_basis": D.FOLD_POLICY_BASIS,
        "exec_m4": entry.get("m4"),
        "openers_structural_record": openers_record,
        "note": "operational record only; zero performance numbers by construction",
    }
    governor = FoldGovernor(entry["module"], {}, entry.get("override"))

    # ---- P27 pre-pass (EXEC-M1) -----------------------------------------------------------
    try:
        p27rec, excl, blockers, bundle, W = D.p27_prepass(gh, governor, F, folds,
                                                          entry["module"].arm_id)
    except Exception as e:
        sidecar["status"] = "FAILED_PREPASS"
        sidecar["error_type"] = type(e).__name__
        sidecar["error"] = D._ascii(str(e))[:800]
        sidecar["traceback_tail"] = D._ascii(traceback.format_exc()[-1500:])
        sidecar["wall_seconds"] = round(time.time() - t0, 1)
        sha = write_json(out_dir / "P38_EXECUTION_SIDECAR.json", sidecar)
        return {"element": key, "status": "FAILED_PREPASS", "sidecar_sha256": sha}

    sidecar["p27_overall_prepass"] = p27rec.get("overall")
    sidecar["p27_fold_verdicts"] = {str(f["fold_id"]): f.get("verdict")
                                    for f in p27rec.get("folds", [])}
    sidecar["p27_final_design_verdict"] = (p27rec.get("final_design") or {}).get("verdict")

    # ---- EXEC-M5: A03 tier symmetry, both tiers, per fold, arm and null identically --------
    if entry["arm_code"] == "A03":
        tier = a03_tier_records(entry["a03_module"], F, folds)
        sidecar["exec_m5_tier_symmetry"] = tier
        for fid, rec in tier.items():
            if not rec["evaluable"] and fid not in excl:
                excl[fid] = "A03_TIER_SYMMETRY_EITHER_TIER_BELOW_FLOOR (EXEC-M5)"

    # ---- A07 near-affinity + '>= 2 folds' retirement arithmetic (EXEC-M1) ------------------
    if entry["arm_code"] == "A07":
        a07m = entry["a07_module"]
        transient = bundle["columns"][a07m.TREATMENT_COL]
        depth = F[a07m.DEPTH_COL].to_numpy(float)
        near = a07_near_affinity_records(transient, depth, folds,
                                         a07m.NEAR_AFFINE_R2, a07m.NEAR_AFFINE_SPEARMAN)
        sidecar["a07_near_affinity"] = near
        for fid, rec in near.items():
            if rec["trigger_fired"] and fid not in excl:
                excl[fid] = "A07_NEAR_AFFINITY_REFUSE_TO_SCORE_FOLD (card S7 rule)"
        if len(excl) >= 2:
            sidecar["status"] = "RETIRED_PREREGISTERED_RULE"
            sidecar["retirement_basis"] = ("A07 card: unevaluable in >= 2 folds retires the "
                                           "hypothesis (EXEC-M1 arithmetic); folds: "
                                           + ", ".join(sorted(excl)))
            sidecar["fold_exclusions"] = excl
            sidecar["wall_seconds"] = round(time.time() - t0, 1)
            sha = write_json(out_dir / "P38_EXECUTION_SIDECAR.json", sidecar)
            return {"element": key, "status": "RETIRED_PREREGISTERED_RULE",
                    "sidecar_sha256": sha}

    sidecar["fold_exclusions"] = dict(excl)

    if blockers:
        sidecar["status"] = "BLOCKED_P27"
        sidecar["block_basis"] = blockers
        sidecar["wall_seconds"] = round(time.time() - t0, 1)
        sha = write_json(out_dir / "P38_EXECUTION_SIDECAR.json", sidecar)
        return {"element": key, "status": "BLOCKED_P27", "blockers": blockers,
                "sidecar_sha256": sha}

    # ---- EXEC-M7: P26 bind path at scoring time ---------------------------------------------
    bind_rec, _ = D.p26_bind_check(gh, entry["module"].p26_k0_record())
    sidecar["exec_m7_p26_bind"] = bind_rec
    if bind_rec["outcome"] == "blocked":
        sidecar["status"] = "BLOCKED_P26_BIND"
        sidecar["wall_seconds"] = round(time.time() - t0, 1)
        sha = write_json(out_dir / "P38_EXECUTION_SIDECAR.json", sidecar)
        return {"element": key, "status": "BLOCKED_P26_BIND", "sidecar_sha256": sha}

    # ---- run the frozen runner --------------------------------------------------------------
    card_deacts = list(getattr(entry["module"], "structurally_deactivated_folds",
                               lambda: [])())
    governor = FoldGovernor(entry["module"], excl, entry.get("override"))
    allowed = set(card_deacts) | set(excl)
    view = P27GuardHarnessView(gh, allowed)
    runner_mod.gh = view
    try:
        rec = runner_mod.run_arm(
            governor, F, folds,
            p27_fold_policy=D.FOLD_POLICY_NAMED,
            prohibited_basis=basis,
            input_paths=INPUT_PATHS,
            out_path=out_dir / "receipt.json",
            run_git=False)
        status = "FITTED"
        sidecar["receipt_sha256"] = rec.get("receipt_file_sha256")
        sidecar["fold_statuses"] = {f.get("fold_id"): f.get("status")
                                    for f in rec.get("folds", [])}
        sidecar["evaluable_folds"] = rec.get("results", {}).get("evaluable_folds")
        sidecar["deactivated_folds_in_receipt"] = rec.get("results", {}).get(
            "structurally_deactivated_folds")
        sidecar["exec_m1_p27_tolerance"] = view.tolerance_basis
        sidecar["guard_verdicts"] = {
            "p26_valid": bool((rec.get("guard_records", {}).get("p26") or {}).get("valid")),
            "p23_valid": bool((rec.get("guard_records", {}).get("p23") or {}).get("valid")),
            "p27_overall": (rec.get("guard_records", {}).get("p27") or {}).get("overall"),
            "guard_pins_all_match": bool((rec.get("guard_pins") or {}).get("all_match")),
            "blinding_unsealed": bool((rec.get("blinding") or {}).get("unsealed")),
        }
    except Exception as e:
        status = "BLOCKED_GUARD" if type(e).__name__ == "GuardHarnessFailure" else "FAILED"
        sidecar["error_type"] = type(e).__name__
        sidecar["error"] = D._ascii(str(e))[:800]
        guard_rec = getattr(e, "record", None)
        if isinstance(guard_rec, dict):
            # the frozen guard's own machine-readable record, sealed alongside the sidecar
            # (dependency diagnostics only; contains no comparative performance number)
            sidecar["guard_block_record_sha256"] = write_json(
                out_dir / "GUARD_BLOCK_RECORD.json",
                {"schema": "p38_guard_block_record/1", "element": key,
                 "error_type": type(e).__name__, "record": guard_rec})
        if status == "FAILED":
            sidecar["traceback_tail"] = D._ascii(traceback.format_exc()[-1500:])
    finally:
        runner_mod.gh = gh

    sidecar["status"] = status
    sidecar["wall_seconds"] = round(time.time() - t0, 1)
    sha = write_json(out_dir / "P38_EXECUTION_SIDECAR.json", sidecar)
    out = {"element": key, "status": status, "wall_seconds": sidecar["wall_seconds"],
           "sidecar_sha256": sha}
    if status == "FITTED":
        out["receipt_sha256"] = sidecar.get("receipt_sha256")
        out["evaluable_folds"] = sidecar.get("evaluable_folds")
    return out


BLOCKED_ARMS = {
    "A20_forced_turnover_contrast": {
        "basis_mandate": "EXEC-M6 (A3-B1)",
        "ruling": ("n_clock_pin scope adjudicated UNIVERSAL by its own frozen text and "
                   "frozen-bytes precedence (D039-ratified compiler observation); A20's "
                   "trailing ftr window and E=3 count run on the barred universe-row clock, "
                   "the module has no contract-schedule input, and re-derivation on the "
                   "contract clock is a code change -- a remediation node (GRAPH_POLICY s5), "
                   "never a silent P38 patch. BLOCKED at invocation; block is a result."),
    },
    "A21_garbage_time_contamination": {
        "basis_mandate": "PIN-A21 (A3-B2)",
        "ruling": ("D039 ratified PIN-A21 verbatim: the preregistered reading of nc is "
                   "A17's possession-weighted construction; A21 as implemented carries the "
                   "game-weighted construction, recorded as implemented-but-rejected, and "
                   "must be rebuilt under a remediation node with targeted re-audit. "
                   "Fitting the rejected construction would seal a non-preregistered "
                   "result. BLOCKED at invocation; block is a result. NOTE: this blocks an "
                   "arm the dispatch counted fit-eligible -- contradiction recorded in "
                   "EXECUTION_LOG.md, not resolved silently."),
    },
    "A23_rest_differential_contrast__bundle_AI": {
        "basis_mandate": "EXEC-M6 (A3-B4)",
        "ruling": ("Same universal n_clock_pin adjudication as A20: rest is computed on the "
                   "fitting universe frame with no contract-schedule input; the 8 opener "
                   "teams' second 2021 games misresolve under the P35 L2/OP-4 redefinition; "
                   "A24's constructor pattern is the in-fleet remedy and is remediation-node "
                   "work. BLOCKED at invocation; block is a result."),
    },
    "A23_rest_differential_contrast__bundle_OM": {
        "basis_mandate": "EXEC-M6 (A3-B4)",
        "ruling": "As bundle_AI (one fleet-wide adjudication, applied per element).",
    },
}

EXCLUDED_PRE_P38 = {
    "A08_league_lag_level": {
        "basis": ("D039: A08 remediation CONFIRMED (12/12, bitwise d_t parity restored) but "
                  "NOT FIT-ELIGIBLE until a non-implementer targeted re-audit passes; "
                  "A08-lane blocking only. Elements K in {20, 80} join the fleet when the "
                  "re-audit passes."),
    },
    "A24_rest_advantage_symmetric": {
        "basis": ("D039: A24 disposition option (a) -- adjudicated fallback for the "
                  "franchise-debut rows, frozen as a registry-appended amendment BEFORE A24 "
                  "ever fits; the amendment had not been appended at P38 execution time, so "
                  "A24 is not fitted (never a silent P38 patch; A24 is the lag-operator "
                  "positive control and must not fail at fit time)."),
    },
}


def main(argv):
    only = set(a.upper() for a in argv[1:])
    t_start = time.time()
    log({"event": "fleet_start", "fold_policy_named_on_the_record": D.FOLD_POLICY_NAMED,
        "basis": D.FOLD_POLICY_BASIS, "only": sorted(only) or "ALL"})

    F, u, checks = D.build_universe()
    folds, fold_equiv = D.build_folds(F)
    archive, poss, lineup, prior, openers = D.build_archive_and_sources()
    log({"event": "data_ready", "universe_checks": checks,
         "fold_mask_equivalence_season_vs_date": fold_equiv,
         "archive_rows": int(len(archive)), "archive_games": int(archive['game_id'].nunique()),
         "lineup_membership_rows": int(len(lineup)),
         "openers_excluded_from_universe": int(len(openers))})

    psg = gh._load("P22_postgame_surrogate_guard")
    basis = psg.realised_duration_basis(F.index, game_id=F["game_id"],
                                        possessions_path=D.POSS_PARQUET)

    openers_record = {
        "n_opener_rows_in_contract_schedule_not_in_universe": int(len(openers)),
        "opener_game_ids": sorted(set(openers["game_id"].astype(str))),
        "opener_team_ids": sorted(set(int(t) for t in openers["team_id"])),
        "n_2021_universe_rows_of_opener_teams": int(
            ((F["season"] == 2021) & F["team_id"].isin(set(openers["team_id"]))).sum()),
    }

    # blocked / excluded records first (results, not failures)
    if not only:
        for key, payload in BLOCKED_ARMS.items():
            rec = {"schema": "p38_block_verdict/1", "element_or_arm": key,
                   "verdict": "BLOCKED_AT_INVOCATION_BY_RATIFIED_MANDATE",
                   **payload,
                   "recorded_by": "P38_BLINDED_FIT executor", "authority": "D039",
                   "fold_policy_named": D.FOLD_POLICY_NAMED}
            sha = write_json(D.SEALED_P38 / key / "BLOCK_VERDICT.json", rec)
            log({"event": "block_recorded", "element": key, "sha256": sha})
        for key, payload in EXCLUDED_PRE_P38.items():
            rec = {"schema": "p38_exclusion_record/1", "arm": key,
                   "verdict": "EXCLUDED_PRE_P38_PER_D039", **payload,
                   "recorded_by": "P38_BLINDED_FIT executor", "authority": "D039"}
            sha = write_json(D.SEALED_P38 / key / "EXCLUSION_RECORD.json", rec)
            log({"event": "exclusion_recorded", "arm": key, "sha256": sha})

    inventory = build_inventory(F, folds, archive, poss, lineup, prior)
    log({"event": "inventory_built", "n_instances": len(inventory),
         "elements": [e["key"] for e in inventory]})

    results = []
    for entry in inventory:
        if only and entry["arm_code"].upper() not in only:
            continue
        log({"event": "arm_start", "element": entry["key"]})
        try:
            res = execute_instance(entry, F, folds, basis, openers_record)
        except Exception as e:  # never let one arm kill the fleet
            res = {"element": entry["key"], "status": "FAILED_DRIVER",
                   "error_type": type(e).__name__, "error": D._ascii(str(e))[:800]}
            tb = D._ascii(traceback.format_exc()[-1500:])
            write_json(D.SEALED_P38 / entry["key"] / "P38_DRIVER_FAILURE.json",
                       {**res, "traceback_tail": tb})
        results.append(res)
        log({"event": "arm_done", **res})

    log({"event": "fleet_done", "n_executed": len(results),
         "wall_seconds_total": round(time.time() - t_start, 1),
         "statuses": {r["element"]: r["status"] for r in results}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
