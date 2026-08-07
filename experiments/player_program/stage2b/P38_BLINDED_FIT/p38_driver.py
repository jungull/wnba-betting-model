#!/usr/bin/env python3
"""p38_driver.py -- P38_BLINDED_FIT executor driver (D039; EXEC-M1..M7 binding).

Executes the frozen P36 shared runner end-to-end on the frozen real universe for every
fit-eligible arm-module instance, into experiments/player_program/stage2b/SEALED_RESULTS/P38/.

BLINDING DISCIPLINE OF THIS DRIVER: it never prints, logs, returns or summarises any
comparative performance number. Receipts (which contain the sealed numbers) are written by
the frozen runner directly to the sealed directory; everything this driver emits is
operational (statuses, guard verdicts, hashes, wall time, structural counts).

Fold policy is NAMED on the record here, before any real fit (EXEC-M2, D039 frozen-
precedence ruling): EXPANDING_PRIOR_SEASONS. The shipped harness default (SEASON_BLOCK) is
never relied on: every p27 invocation in this driver and in the runner receives the named
policy explicitly.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent                      # stage2b/P38_BLINDED_FIT
STAGE2B = HERE.parent
PP = STAGE2B.parent                                          # experiments/player_program
RUNNER_DIR = STAGE2B / "P36_IMPLEMENT_ARMS" / "runner"
ARMS_DIR = STAGE2B / "P36_IMPLEMENT_ARMS" / "arms"
SEALED = STAGE2B / "SEALED_RESULTS"
SEALED_P38 = SEALED / "P38"

PRIOR_PARQUET = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS_PARQUET = PP / "possessions_v2" / "possessions_raw_v2.parquet"

for _p in (str(RUNNER_DIR), str(PP), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# EXEC-M2: the executor NAMES the fold policy on the record before any real fit.
FOLD_POLICY_NAMED = "EXPANDING_PRIOR_SEASONS"
FOLD_POLICY_BASIS = ("D039 ratification of the P37 frozen-precedence analysis: the D006 "
                     "operative fold masks (train_lt_2022..train_lt_2026) ARE the "
                     "EXPANDING_PRIOR_SEASONS masks; SEASON_BLOCK is preserved on the record "
                     "as the historical shape of the S7 statement, not an operative mask.")

FINAL_FOLD_ID = "FINAL_ASSEMBLED_DESIGN"


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ascii(s):
    return str(s).encode("ascii", "replace").decode("ascii")


# ------------------------------------------------------------------------- module imports --
def import_arm(arm_code: str, filename: str):
    """Import one arm module file under a unique module name, with the arm's own directory
    transiently first on sys.path so its sibling `feature_construction` (a name several arms
    share) resolves to ITS OWN copy and is evicted from the cache afterwards."""
    arm_dir = ARMS_DIR / arm_code
    evicted = sys.modules.pop("feature_construction", None)
    sys.path.insert(0, str(arm_dir))
    try:
        name = f"p38_arm_{arm_code}"
        spec = importlib.util.spec_from_file_location(name, arm_dir / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(arm_dir))
        sys.modules.pop("feature_construction", None)
        if evicted is not None:
            sys.modules["feature_construction"] = evicted


# --------------------------------------------------------------------------- data assembly --
def build_universe():
    """The frozen 2,982-row universe via possession_features.load_universe(), positional
    index, plus the caller-supplied columns individual frozen cards require by name:
    log_exposure (the receipted offset), own_est/opp_est (A02, P25 registered contrast
    inputs), opp_id (A22's opponent key name), is_home_offense (A25's schedule flag,
    derived two-sidedly from the frozen possessions artifact)."""
    import possession_features as pf
    u = pf.load_universe()
    F = u.frame.reset_index(drop=True).copy()

    # offset: log_exposure must be byte-identical to log(projected_team_off_possessions)
    le = np.log(F["projected_team_off_possessions"].to_numpy(float))
    stored = F["log_projected_team_off_possessions"].to_numpy(float)
    max_abs = float(np.max(np.abs(le - stored)))
    F["log_exposure"] = stored

    F["own_est"] = F["team_pace_estimate"].astype(float)
    F["opp_est"] = F["opp_pace_estimate"].astype(float)
    F["opp_id"] = F["opp_team_id"]

    poss_home = pd.read_parquet(POSS_PARQUET,
                                columns=["game_id", "offense_team_id", "is_home_offense"])
    hm = (poss_home.loc[poss_home["is_home_offense"] == 1, ["game_id", "offense_team_id"]]
          .drop_duplicates())
    per_game = hm.groupby("game_id")["offense_team_id"].nunique()
    if int(per_game.max()) != 1:
        raise RuntimeError("home-team derivation ambiguous: some game has >1 home team")
    home_map = hm.set_index("game_id")["offense_team_id"]
    mapped = F["game_id"].map(home_map)
    if mapped.isna().any():
        raise RuntimeError(f"{int(mapped.isna().sum())} universe rows have no home-team fact")
    F["is_home_offense"] = (F["team_id"].to_numpy() == mapped.to_numpy()).astype(float)
    # two-sided sanity: exactly one home row per game
    per = F.groupby("game_id")["is_home_offense"].sum()
    if not np.all(per.to_numpy() == 1.0):
        raise RuntimeError("is_home_offense is not exactly one-per-game")

    checks = {
        "n_rows": int(len(F)), "n_clusters": int(F["game_id"].nunique()),
        "row_universe_digest": u.contract["row_universe_digest"],
        "log_exposure_max_abs_diff_vs_log_projection": max_abs,
        "seasons": sorted(int(s) for s in F["season"].unique()),
    }
    return F, u, checks


def build_folds(F: pd.DataFrame):
    """The five frozen D006 expanding folds, positional. Season-mask definition (the D006 /
    P27 EXPANDING_PRIOR_SEASONS masks); verified equal to the date-cutoff definition of
    possession_features.chronological_folds on this archive."""
    season = F["season"].to_numpy(int)
    gd = F["game_date"].to_numpy()
    seasons = sorted(set(int(s) for s in season))
    folds, equiv = [], {}
    for s in seasons[1:]:
        train = np.flatnonzero(season < s)
        test = np.flatnonzero(season == s)
        cutoff = gd[season == s].min()
        train_by_date = np.flatnonzero(gd < cutoff)
        equiv[f"train_lt_{s}"] = bool(np.array_equal(train, train_by_date))
        folds.append({"fold_id": f"train_lt_{s}", "train_idx": train, "test_idx": test})
    # games never split: both team-rows of every game land in the same fold part
    gid = F["game_id"].to_numpy()
    for f in folds:
        for part in ("train_idx", "test_idx"):
            part_gids = gid[f[part]]
            vc = pd.Series(part_gids).value_counts()
            if int(len(f[part])) != int(vc.sum()) or (len(vc) and int(vc.min()) != 2):
                raise RuntimeError(f"fold {f['fold_id']} splits a game cluster ({part})")
    return folds, equiv


def build_archive_and_sources():
    """The 2,990-row contract-schedule archive (schedule identity + realised completed-game
    facts), the possession-level frame (season normalised to int at the call site; the
    frozen artifact bytes are untouched), and A13's lineup-membership long frame."""
    prior = pd.read_parquet(PRIOR_PARQUET)
    poss = pd.read_parquet(POSS_PARQUET)

    n_off = (poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss")
             .reset_index().rename(columns={"offense_team_id": "team_id"}))
    mp = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()

    archive = prior[["game_id", "team_id", "game_date", "season"]].merge(
        n_off, on=["game_id", "team_id"], how="left", validate="1:1")
    archive = archive.merge(mp, on="game_id", how="left", validate="m:1")
    if archive["n_off_poss"].isna().any() or archive["max_period"].isna().any():
        raise RuntimeError("contract-schedule row without realised possession facts")
    archive["n_off_poss"] = archive["n_off_poss"].astype(float)
    archive["max_period"] = archive["max_period"].astype(float)
    archive["season"] = archive["season"].astype(int)
    denom = 40.0 + 5.0 * np.maximum(0.0, archive["max_period"].to_numpy(float) - 4.0)
    archive["pace"] = archive["n_off_poss"].to_numpy(float) * 40.0 / denom

    poss = poss.copy()
    poss["season"] = poss["season"].astype(int)

    slots_off = [f"off_p{i}" for i in range(1, 6)]
    slots_def = [f"def_p{i}" for i in range(1, 6)]
    parts = []
    for team_col, slots in (("offense_team_id", slots_off), ("defense_team_id", slots_def)):
        for s in slots:
            part = poss[[team_col, "game_id", s]].rename(
                columns={team_col: "team_id", s: "player_id"})
            parts.append(part)
    lineup = pd.concat(parts, ignore_index=True)
    lineup = lineup[lineup["player_id"].notna()]
    lineup["player_id"] = lineup["player_id"].astype("int64")
    lineup = lineup.drop_duplicates(subset=["team_id", "game_id", "player_id"]).reset_index(
        drop=True)

    openers = prior.loc[~prior["pace_resolved"].astype(bool),
                        ["game_id", "team_id", "season", "game_date"]]
    return archive, poss, lineup, prior, openers


# ------------------------------------------------------------------------------- pre-pass --
def p27_prepass(gh, governor, F, folds, arm_id):
    """Run the frozen P27 guard exactly as the runner will (same frame, same args, the NAMED
    fold policy), tolerating overall FAIL, and derive the P38 per-fold exclusion map and any
    whole-arm blockers from the guard's OWN per-fold verdicts (EXEC-M1)."""
    final_fold = {"fold_id": FINAL_FOLD_ID, "train_idx": np.arange(len(F)),
                  "test_idx": np.empty(0, int)}
    bundle = governor.build_design(final_fold, F)
    W = F.copy()
    for name, v in bundle["columns"].items():
        W[name] = np.asarray(v, float)
    cand = [c for c in bundle["treatment_cols"] if c != "intercept"]
    nuis = [c for c in bundle["nuisance_cols"] if c != "intercept"]
    k0 = bundle["k0_matched_design"]
    nullf = [c for c in k0["treatment_cols"] if c != "intercept"]
    nulln = [c for c in k0["nuisance_cols"] if c != "intercept"]
    rule = governor.p27_rule()
    rule_kwargs, prereg_kwargs = (rule if rule is not None else (None, None))
    try:
        rec = gh.p27_check(W, candidate_features=cand, nuisance_terms=nuis,
                           cluster_col="game_id", season_col="season",
                           fold_policy=FOLD_POLICY_NAMED,
                           null_features=nullf, null_nuisance=nulln,
                           rule_kwargs=rule_kwargs, prereg_kwargs=prereg_kwargs,
                           arm_id=arm_id)
    except Exception as e:
        rec = getattr(e, "record", None)
        if not isinstance(rec, dict):
            raise

    excl, blockers = {}, []
    split_ok = bool((rec.get("games_not_split_check") or {}).get("ok"))
    if not split_ok:
        blockers.append("P27_GAMES_SPLIT_ACROSS_FOLDS")
    for f in rec.get("folds", []):
        fid = str(f["fold_id"])
        if f.get("verdict") == "UNEVALUABLE_PROSPECTIVELY":
            excl[fid] = "P27_UNEVALUABLE (guard per-fold verdict; EXEC-M1)"
        else:
            rr = f.get("active_set_rule") or {}
            if rr.get("applied") and rr.get("dropped"):
                excl[fid] = ("P27_ACTIVE_SET_RULE_COLLAPSE (preregistered rule dropped "
                             + ",".join(rr["dropped"]) + "; arm collapses to incumbent for "
                             "this fold per the card; EXEC-M1)")
    recon = rec.get("pooled_vs_fold_reconciliation", {}) or {}
    for fid in recon.get("affected_folds_without_an_explicit_verdict", []) or []:
        if fid != FINAL_FOLD_ID and fid not in excl:
            excl[str(fid)] = ("P27_TERM_ABSENT_WITHOUT_EXPLICIT_VERDICT (fail-closed P38 "
                              "exclusion; EXEC-M1)")
    for fid in rec.get("folds_with_unreconciled_parameter_counts", []) or []:
        if fid == FINAL_FOLD_ID:
            blockers.append("P27_FINAL_DESIGN_PARAMETER_COUNTS_UNRECONCILED")
        elif fid not in excl:
            excl[str(fid)] = "P27_PARAM_COUNT_UNRECONCILED (fail-closed P38 exclusion)"
    final = rec.get("final_design") or {}
    if final.get("verdict") == "UNEVALUABLE_PROSPECTIVELY":
        blockers.append("P27_FINAL_ASSEMBLED_DESIGN_UNEVALUABLE")
    return rec, excl, blockers, bundle, W


def p25_fold_prepass(gh, governor, F, folds):
    """D040: invoke the frozen P25 wrapper per fold EXACTLY as the runner's bundle loop does
    (same wrapper, same argument pins, the fold's TRAINING design), and derive the P38
    per-fold exclusion map from the guard's own verdicts. A block on the
    FINAL_ASSEMBLED_DESIGN is never fold-local and becomes a whole-arm blocker (fail
    closed). Returns (per_fold_records, exclusions, blockers); the full guard records are
    dependency diagnostics only (no performance number exists at design time)."""
    final_fold = {"fold_id": FINAL_FOLD_ID, "train_idx": np.arange(len(F)),
                  "test_idx": np.empty(0, int)}
    per_fold, excl, blockers = {}, {}, []
    for fold in list(folds) + [final_fold]:
        fid = str(fold["fold_id"])
        bundle = governor.build_design(fold, F)
        W = F.copy()
        for name, v in bundle["columns"].items():
            W[name] = np.asarray(v, float)
        tr = np.asarray(fold["train_idx"], int)
        W_tr = W.iloc[tr].reset_index(drop=True)
        cand = [c for c in bundle["treatment_cols"] if c != "intercept"]
        nuis = [c for c in bundle["nuisance_cols"] if c != "intercept"]
        try:
            rec = gh.p25_check(
                W_tr, candidate_features=cand, nuisance_features=nuis,
                preregistered_contrasts=governor.preregistered_contrasts(),
                prereg_digest_expected=governor.prereg_digest_expected())
            per_fold[fid] = {"verdict": "PASS", "record": rec}
        except Exception as e:
            rec = getattr(e, "record", None)
            if not isinstance(rec, dict):
                raise
            fired = [{"kind": f.get("kind"), "feature": f.get("feature")}
                     for f in rec.get("blocking", [])]
            per_fold[fid] = {"verdict": "BLOCK", "fired": fired, "record": rec}
            if fid == FINAL_FOLD_ID:
                blockers.append("P25_FINAL_ASSEMBLED_DESIGN_BLOCK (not fold-local; the "
                                "D040 wrapper does not apply; fail closed)")
            else:
                excl[fid] = ("P25_FOLD_LOCAL_BLOCK -> FOLD_UNEVALUABLE (frozen P25 guard "
                             "per-fold verdict honoured at the call site, arm AND null "
                             "identically; D040)")
    return per_fold, excl, blockers


def p26_bind_check(gh, record):
    """EXEC-M7: invoke the P26 wrapper's bind path (delegation into the frozen
    comparison_gate.require_matched_k0) at scoring time. Outcome classification:
      bound                      -- bind path ran to completion;
      tolerated_r8_shape         -- calibration_only arm whose RAW validation carries only
                                    the three R8-shaped findings; the frozen P35
                                    r8_scope_adjudication (ratified at P37) governs, the
                                    adjudicated (non-bind) wrapper validation must pass,
                                    and the refusal of the stricter raw bind path is
                                    recorded verbatim rather than hidden;
      blocked                    -- any other bind failure (a result: the arm does not fit).
    """
    arm_kind = record.get("arm_kind")
    try:
        out = gh.p26_check(record, bind=True)
        return {"outcome": "bound", "valid": bool(out.get("valid")),
                "binding_matched": bool((out.get("binding") or {}).get("matched")),
                "r8_filtered": [f.get("kind") for f in out.get("r8_filtered_findings", [])]}, out
    except Exception as e:
        # The adjudicated (non-bind) wrapper must still pass for the R8 tolerance to apply.
        if arm_kind == "calibration_only":
            try:
                out2 = gh.p26_check(record, bind=False)
            except Exception as e2:
                return {"outcome": "blocked", "stage": "adjudicated_wrapper",
                        "error_type": type(e2).__name__,
                        "error": _ascii(str(e2))[:600]}, None
            return {"outcome": "tolerated_r8_shape",
                    "bind_error_type": type(e).__name__,
                    "bind_error": _ascii(str(e))[:600],
                    "basis": ("P35 r8_scope_adjudication (P37 RAISED-4 ratified SOUND; "
                              "R-F2 recorded: code rule = ALL tested parameters "
                              "null_value 0); raw bind path applies the unadjudicated R8 "
                              "branch the frozen adjudication scopes out for "
                              "calibration_only arms")}, out2
        return {"outcome": "blocked", "stage": "bind",
                "error_type": type(e).__name__, "error": _ascii(str(e))[:600]}, None
