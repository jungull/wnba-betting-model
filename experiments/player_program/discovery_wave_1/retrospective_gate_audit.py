#!/usr/bin/env python3
"""retrospective_gate_audit.py -- RETROSPECTIVE INTEGRITY AUDIT of discovery wave 1.

WHAT THIS IS
    The eight discovery-wave-1 workstreams were executed against a PRE-FIX `feature_gate.py`.
    Neither the rank/conditioning fix (55f4500) nor the informative-missingness fix (42af2cd)
    is an ancestor of ANY of the eight result commits: all eight carry the identical gate blob
    a8a8ea6416c9613302209a4c71008ef9927d6f82 inherited from base commit eb1103c.

    This script re-runs the CURRENT gate (the one in the coordinator worktree at HEAD) against
    every design those workstreams actually fitted -- the final assembled training design AND
    every chronological training fold separately, because a pooled audit cannot establish that
    every fold is identified.

WHAT THIS IS NOT
    It is an AUDIT. It refits nothing for selection, re-runs no model selection, changes no
    feature, and produces no new decision result. Model coefficients are never recomputed. The
    only numbers produced are gate findings, numerical ranks, condition numbers, singular
    values and missingness statistics of designs that were already fitted and published.

    The eight agent worktrees are read STRICTLY READ-ONLY. `feature_gate.py` is imported,
    never modified.

OUTPUTS (written into the coordinator worktree only)
    RETROSPECTIVE_GATE_AUDIT.json   machine-readable, per workstream / per arm / per fold
    RETROSPECTIVE_GATE_AUDIT.md     human-readable summary with the classification table

Run::  python experiments/player_program/discovery_wave_1/retrospective_gate_audit.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent                 # .../discovery_wave_1
PP = HERE.parent                                       # .../experiments/player_program
COORD_ROOT = PP.parents[1]                             # coordinator worktree root
WT = COORD_ROOT.parent                                 # .../.claude/worktrees

sys.path.insert(0, str(PP))
import feature_gate                                                            # noqa: E402
from feature_gate import FeatureGateFailure                                     # noqa: E402

# ---------------------------------------------------------------------------------------- #
# the eight workstreams
# ---------------------------------------------------------------------------------------- #
WS = {
    "ws1": {"worktree": "agent-a062ec7d27d10b55b", "commit": "5313ebd",
            "title": "repaired projected role",
            "superseded_commit": "3726991"},
    "ws2": {"worktree": "agent-a366d924a9b4dfcd5", "commit": "863a900",
            "title": "responsibility transfer"},
    "ws3": {"worktree": "agent-a96f23f70cffc45d0", "commit": "1e3509f",
            "title": "team total + allocation"},
    "ws4": {"worktree": "agent-a578166bb62b091a5", "commit": "1b634fb",
            "title": "EWMA timescale family"},
    "ws5": {"worktree": "agent-ab8223114ea98f146", "commit": "6d9e3f2",
            "title": "opportunity proxies"},
    "ws6": {"worktree": "agent-abba0a0dbf84578f1", "commit": "5ef1f25",
            "title": "mechanism decomposition"},
    "ws7": {"worktree": "agent-ab4ac90b1f887b5b7", "commit": "e858e96",
            "title": "nonlinear / heterogeneous"},
    "ws8": {"worktree": "agent-a5694dab4e5ccdb3d", "commit": "c1d2637",
            "title": "operational error decomposition"},
}
PRE_FIX_GATE_BLOB = "a8a8ea6416c9613302209a4c71008ef9927d6f82"
BASE_COMMIT = "eb1103c"
FIX_COMMITS = {"55f4500": "rank / conditioning", "42af2cd": "informative missingness"}
GATE_PATH = "experiments/player_program/feature_gate.py"

# frozen constants reused verbatim from register_turnover_p2 (not re-derived here)
MIN_TRAIN_ROWS = 2000
MIN_TG = 200                       # ws3 stage-1 minimum training team-games
WQ = [0.005, 0.995]                # ws3 winsorisation quantiles


def wpath(ws: str) -> Path:
    return WT / WS[ws]["worktree"]


def dpath(ws: str) -> Path:
    return wpath(ws) / "experiments/player_program/discovery_wave_1" / ws


def ppath(ws: str) -> Path:
    return wpath(ws) / "experiments/player_program"


# ---------------------------------------------------------------------------------------- #
# gate harness
# ---------------------------------------------------------------------------------------- #
def gate(label: str, df: pd.DataFrame, names: list[str], *, offset=None, target=None,
         test_df=None, outcome_mask=None) -> dict:
    """Run the CURRENT gate and return a COMPACT record. Never raises."""
    rec: dict = {"label": label, "n_features": len(names), "n_rows": int(len(df)),
                 "features": list(names)}
    try:
        a = feature_gate.audit(df, names, offset=offset, target=target, test_df=test_df,
                               outcome_mask=outcome_mask)
        rec["passed"] = True
        rec["blocking_kinds"] = []
        rec["finding_kinds"] = sorted({f["kind"] for f in a["findings"]})
        rec["findings"] = a["findings"]
        rec["design_rank"] = _rank_compact(a["design_rank"])
    except FeatureGateFailure as e:
        blocking = json.loads(str(e))
        rec["passed"] = False
        rec["blocking_kinds"] = sorted({b["kind"] for b in blocking})
        rec["blocking"] = blocking
        rec["design_rank"] = _rank_compact(feature_gate.design_rank_report(df, names))
        # the gate raises on the FIRST blocking set; recover the non-blocking findings too
        rec["finding_kinds"] = rec["blocking_kinds"]
    rec["missingness"] = _missingness(df, names, target, outcome_mask)
    return rec


def _rank_compact(r: dict) -> dict:
    sv = r.get("singular_values") or []
    return {"checked": r.get("checked"), "n_features": r.get("n_features"),
            "n_complete_rows": r.get("n_complete_rows"),
            "numerical_rank": r.get("numerical_rank"), "full_rank": r.get("full_rank"),
            "smallest_singular_value": (float(sv[-1]) if sv else None),
            "largest_singular_value": (float(sv[0]) if sv else None),
            "condition_number": r.get("condition_number"),
            "condition_ok": r.get("condition_ok")}


def _missingness(df: pd.DataFrame, names: list[str], target=None, outcome_mask=None) -> dict:
    out: dict = {"any_missing": False, "per_feature": {}}
    if not names:
        out["note"] = "zero-feature design: no missingness surface"
        return out
    y = np.asarray(target, float) if target is not None else None
    om = np.asarray(outcome_mask, bool) if outcome_mask is not None else None
    for c in names:
        miss = df[c].isna().to_numpy()
        n = int(miss.sum())
        rec = {"n_missing": n, "missing_rate": round(float(n / max(len(miss), 1)), 6)}
        if n:
            out["any_missing"] = True
            if om is not None:
                off = int((miss & om).sum() + ((~miss) & (~om)).sum())
                off = min(off, len(miss) - off)
                rec["off_diagonal_vs_outcome_mask"] = off
                rec["null_mask_is_exact_outcome_indicator"] = bool(off == 0)
            if y is not None and n < len(miss):
                m = np.isfinite(y)
                if m.sum() > 10 and np.std(y[m]) > 0:
                    rec["corr_null_mask_with_target"] = round(
                        float(np.corrcoef(miss[m].astype(float), y[m])[0, 1]), 6)
        out["per_feature"][c] = rec
    verdicts = []
    for c, r in out["per_feature"].items():
        if r.get("null_mask_is_exact_outcome_indicator"):
            verdicts.append(f"{c}: null mask IS the outcome indicator")
        elif abs(r.get("corr_null_mask_with_target") or 0.0) >= 0.5:
            verdicts.append(f"{c}: null mask correlates {r['corr_null_mask_with_target']} with target")
    out["outcome_associated_missingness_verdict"] = (
        "; ".join(verdicts) if verdicts
        else ("no missingness present" if not out["any_missing"]
              else "missingness present but not shown to be outcome-associated"))
    return out


def summarise(records: list[dict]) -> dict:
    return {"n_audits": len(records),
            "all_passed": bool(all(r["passed"] for r in records)),
            "n_blocked": int(sum(0 if r["passed"] else 1 for r in records)),
            "blocking_kinds": sorted({k for r in records for k in r.get("blocking_kinds", [])}),
            "all_finding_kinds": sorted({k for r in records for k in r.get("finding_kinds", [])}),
            "worst_condition_number": max(
                [r["design_rank"].get("condition_number") or 0.0 for r in records] + [0.0]),
            "any_rank_deficient": bool(any(
                r["design_rank"].get("full_rank") is False for r in records)),
            "blocked_labels": [r["label"] for r in records if not r["passed"]]}


# ---------------------------------------------------------------------------------------- #
# ancestry / blob verification
# ---------------------------------------------------------------------------------------- #
def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(COORD_ROOT), *args],
                          capture_output=True, text=True).stdout.strip()


def _is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(COORD_ROOT), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def verify_provenance() -> dict:
    out: dict = {
        "claim": ("neither 55f4500 (rank/conditioning) nor 42af2cd (informative missingness) is "
                  "an ancestor of any of the eight result commits; all eight carry the identical "
                  f"PRE-FIX feature_gate.py blob {PRE_FIX_GATE_BLOB} from base commit {BASE_COMMIT}"),
        "method": "git merge-base --is-ancestor + git rev-parse <commit>:" + GATE_PATH,
        "current_gate": {
            "worktree": str(COORD_ROOT),
            "head": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "gate_blob_at_head": _git("rev-parse", "HEAD:" + GATE_PATH),
            "gate_blob_on_disk": _git("hash-object", GATE_PATH),
            "blocking_kinds": sorted(feature_gate.BLOCKING),
            "RANK_TOL": feature_gate.RANK_TOL, "COND_MAX": feature_gate.COND_MAX},
        "fix_commits": {c: {"subject": _git("log", "-1", "--format=%s", c), "role": r}
                        for c, r in FIX_COMMITS.items()},
        "per_workstream": {}}
    for ws, meta in WS.items():
        c = meta["commit"]
        out["per_workstream"][ws] = {
            "result_commit": _git("rev-parse", c),
            "gate_blob_at_result_commit": _git("rev-parse", f"{c}:{GATE_PATH}"),
            "gate_blob_is_the_prefix_blob": _git("rev-parse", f"{c}:{GATE_PATH}") == PRE_FIX_GATE_BLOB,
            "base_eb1103c_is_ancestor": _is_ancestor(BASE_COMMIT, c),
            "rank_fix_55f4500_is_ancestor": _is_ancestor("55f4500", c),
            "missingness_fix_42af2cd_is_ancestor": _is_ancestor("42af2cd", c),
            "worktree_head_matches_result_commit": (
                subprocess.run(["git", "-C", str(wpath(ws)), "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
                == _git("rev-parse", c)),
        }
    p = out["per_workstream"]
    out["verdict"] = {
        "all_eight_carry_the_prefix_blob": all(v["gate_blob_is_the_prefix_blob"] for v in p.values()),
        "rank_fix_governs_none": not any(v["rank_fix_55f4500_is_ancestor"] for v in p.values()),
        "missingness_fix_governs_none": not any(
            v["missingness_fix_42af2cd_is_ancestor"] for v in p.values()),
        "conclusion": "the strengthened gate did NOT govern discovery wave 1"}
    return out


# ---------------------------------------------------------------------------------------- #
# shared reconstruction helper: the P1/P2 walk-forward-by-season protocol
# ---------------------------------------------------------------------------------------- #
def _offset(d: pd.DataFrame) -> np.ndarray:
    return (np.log(np.clip(d["exposure"].to_numpy(float), 1e-6, None))
            + np.log(np.clip(d["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))


def walk_forward_audit(arm: str, feats: list[str], I: pd.DataFrame, O: pd.DataFrame,
                       *, standardise: bool = False, prefix: str = "") -> list[dict]:
    """Audit the pooled training design and every chronological training fold of one arm.

    `standardise=True` reproduces the training-fold standardise-then-fillna(0) design that
    actually entered the estimator (ws2, ws5). `standardise=False` audits the raw feature
    frame of the fold (ws1, ws7), which is what those workstreams gated.
    """
    recs: list[dict] = []
    train_src = I[I["exposure"] > 0].reset_index(drop=True)
    seasons = sorted(int(s) for s in pd.unique(pd.concat([I["season"], O["season"]])))
    for s in seasons:
        tr = train_src[train_src["season"] < s]
        if len(tr) < MIN_TRAIN_ROWS:
            recs.append({"label": f"{prefix}{arm}/fold_{s}", "skipped": True, "passed": True,
                         "reason": "fold falls back to Arm D (beta=0); no design is fitted",
                         "n_features": len(feats), "n_rows": int(len(tr)), "features": list(feats),
                         "blocking_kinds": [], "finding_kinds": [],
                         "design_rank": _rank_compact({"checked": False}),
                         "missingness": {"any_missing": False,
                                         "outcome_associated_missingness_verdict": "fold not fitted"}})
            continue
        te = pd.concat([I[I["season"] == s], O[O["season"] == s]]).head(0) if False else None
        otr, ytr = _offset(tr), tr["turnovers"].to_numpy(float)
        if standardise:
            mu, sd = tr[feats].mean(), tr[feats].std().replace(0, 1.0)
            X = ((tr[feats] - mu) / sd).fillna(0.0) if feats else pd.DataFrame(index=tr.index)
        else:
            X = tr
        recs.append(gate(f"{prefix}{arm}/fold_{s}", X, feats, offset=otr, target=ytr,
                         test_df=O if s in set(O["season"]) else I))
    # pooled / final assembled training design
    otr, ytr = _offset(train_src), train_src["turnovers"].to_numpy(float)
    if standardise:
        mu, sd = train_src[feats].mean(), train_src[feats].std().replace(0, 1.0)
        Xp = (((train_src[feats] - mu) / sd).fillna(0.0) if feats
              else pd.DataFrame(index=train_src.index))
    else:
        Xp = train_src
    recs.append(gate(f"{prefix}{arm}/FINAL_ASSEMBLED_DESIGN", Xp, feats, offset=otr, target=ytr,
                     test_df=O))
    return recs


def operational_frame_audit(arm: str, feats: list[str], O: pd.DataFrame, prefix: str = "") -> dict:
    """Audit the OPERATIONAL prediction frame with did_appear as the outcome mask.

    Training folds are drawn from the intrinsic track, which contains only appearers and
    therefore structurally CANNOT reveal a null mask that encodes did_appear. This is the only
    frame on which `missingness_encodes_outcome` can fire.
    """
    om = O["did_appear"].astype(bool).to_numpy() if "did_appear" in O.columns else None
    return gate(f"{prefix}{arm}/OPERATIONAL_PREDICTION_FRAME", O, feats,
                offset=_offset(O), target=O["turnovers"].to_numpy(float), outcome_mask=om)


# ---------------------------------------------------------------------------------------- #
# WS1 -- repaired projected role
# ---------------------------------------------------------------------------------------- #
WS1_ARMS = {
    "K0_intercept_only": [],
    "L1_linear": ["proj_minutes_share", "role_change", "rotation_rank_change",
                  "expanded_role_bounded"],
    "N1_split": ["proj_minutes_share", "role_change_pos", "role_change_neg",
                 "rotation_rank_change", "expanded_role_bounded"],
    "D0_level_only": ["proj_minutes_share"],
    "D0_change_only": ["role_change", "rotation_rank_change", "expanded_role_bounded"],
    "S1_trailing_basis": ["trailing_minutes_share", "role_change", "rotation_rank_change",
                          "expanded_role_bounded"],
    "X_literal_card_set": ["proj_minutes_share", "trailing_minutes_share", "role_change",
                           "rotation_rank_change", "expanded_role_bounded"],
}
WS1_DIAGNOSTIC_ONLY = {"X_literal_card_set"}


def audit_ws1() -> dict:
    d = dpath("ws1")
    I = pd.read_parquet(d / "ws1_predictions_intrinsic.parquet")
    O = pd.read_parquet(d / "ws1_predictions_operational.parquet")
    per_arm: dict = {}
    for arm, feats in WS1_ARMS.items():
        recs = walk_forward_audit(arm, feats, I, O)
        recs.append(operational_frame_audit(arm, feats, O))
        per_arm[arm] = {"features": feats, "diagnostic_only": arm in WS1_DIAGNOSTIC_ONLY,
                        "summary": summarise(recs), "audits": recs}
    return {"reconstructed": True,
            "source": "ws1_predictions_{intrinsic,operational}.parquet (committed at 5313ebd)",
            "protocol": ("walk-forward by season on the intrinsic track, train_src = "
                         "I[exposure > 0], offset = log(exposure) + log(D_ewma_shrunk), "
                         f"MIN_TRAIN_ROWS = {MIN_TRAIN_ROWS}"),
            "per_arm": per_arm}


# ---------------------------------------------------------------------------------------- #
# WS2 -- responsibility transfer
# ---------------------------------------------------------------------------------------- #
WS2_ARMS = {
    "H": ["displaced_involvement"],
    "T1": ["transfer_direct"],
    "T2": ["transfer_allocated"],
    "T3": ["transfer_role_sensitive"],
    "T123": ["transfer_direct", "transfer_allocated", "transfer_role_sensitive"],
    "HT2": ["displaced_involvement", "transfer_allocated"],
    "HT3": ["displaced_involvement", "transfer_role_sensitive"],
}


def audit_ws2() -> dict:
    d = dpath("ws2")
    I = pd.read_parquet(d / "ws2_predictions_intrinsic.parquet")
    O = pd.read_parquet(d / "ws2_predictions_operational.parquet")
    per_arm: dict = {}
    for arm, feats in WS2_ARMS.items():
        # ws2 gated the STANDARDISED, fillna(0) design -- reproduce exactly that
        recs = walk_forward_audit(arm, feats, I, O, standardise=True)
        recs.append(operational_frame_audit(arm, feats, O))
        per_arm[arm] = {"features": feats, "summary": summarise(recs), "audits": recs}

    # --- the imputation that the as-fitted design cannot show ------------------------------ #
    # build_constructions() imputes the RAW P2 inputs before the constructions are formed:
    #   prior_involvement = offensive_involvement_proxy.fillna(0.0)
    #   role_expansion    = (proj_minutes_share - trailing_minutes_share).fillna(0.0).clip(0)
    # Those two P2 columns are null on EXACTLY the non-appearers. Audit the raw inputs.
    P2 = pd.read_parquet(ppath("ws2") / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
                         columns=["game_id", "team_id", "player_id",
                                  "offensive_involvement_proxy", "trailing_minutes_share",
                                  "role_change", "displaced_involvement"])
    key = ["game_id", "team_id", "player_id"]
    J = O[key + ["did_appear", "turnovers", "exposure", "D_ewma_shrunk"]].merge(
        P2, on=key, how="left")
    raw = gate("RAW_P2_INPUTS_BEFORE_IMPUTATION/OPERATIONAL_PREDICTION_FRAME", J,
               ["offensive_involvement_proxy", "trailing_minutes_share", "role_change",
                "displaced_involvement"],
               offset=_offset(J), target=J["turnovers"].to_numpy(float),
               outcome_mask=J["did_appear"].astype(bool).to_numpy())

    # --- where the imputed null mask ended up: a VALUE the gate structurally cannot see ----- #
    da = O["did_appear"].astype(bool).to_numpy()
    launder: dict = {
        "question": ("after build_constructions() imputes the null inputs to 0.0, is the "
                     "resulting ZERO an indicator of non-appearance? the gate's missingness "
                     "checks read `isna()` only, so an imputed value is invisible to them"),
        "operational_rows": int(len(O)), "appearers": int(da.sum()),
        "non_appearers": int((~da).sum()), "per_feature": {}}
    for c in ["displaced_involvement", "transfer_direct", "transfer_allocated",
              "transfer_role_sensitive"]:
        v = O[c].to_numpy(float)
        z = (v == 0)
        launder["per_feature"][c] = {
            "n_zero": int(z.sum()),
            "zero_and_non_appearing": int((z & ~da).sum()),
            "zero_and_appearing": int((z & da).sum()),
            "NONZERO_AND_NON_APPEARING": int((~z & ~da).sum()),
            "nonzero_implies_did_appear": bool((~z & ~da).sum() == 0),
            "corr_value_with_did_appear": round(
                float(np.corrcoef(v, da.astype(float))[0, 1]), 6)}
    launder["verdict"] = (
        "the three transfer constructions are EXACTLY zero on all 8,278 non-appearers and "
        "non-zero only on appearers, so a non-zero value certifies appearance -- post-cutoff "
        "information -- even though the design contains no nulls and the current gate passes it"
        if all(launder["per_feature"][c]["nonzero_implies_did_appear"]
               for c in ["transfer_direct", "transfer_allocated", "transfer_role_sensitive"])
        else "the imputed zero does not one-sidedly certify appearance")
    return {"reconstructed": True,
            "imputed_zero_encodes_non_appearance": launder,
            "source": "ws2_predictions_{intrinsic,operational}.parquet (committed at 863a900)",
            "protocol": ("walk-forward by season; ws2 gated the TRAINING-FOLD STANDARDISED "
                         "design with .fillna(0.0) already applied, so the gate never saw a "
                         "null mask; reproduced exactly here"),
            "per_arm": per_arm,
            "raw_p2_inputs_before_imputation": raw,
            "raw_input_summary": summarise([raw])}


# ---------------------------------------------------------------------------------------- #
# WS3 -- team total + allocation (two stage)
# ---------------------------------------------------------------------------------------- #
S1_DECLARED = ["log_personnel_rate", "team_tov_rate_ewma", "team_tov_rate_shrunk",
               "roster_continuity_minutes", "roster_continuity_jaccard",
               "displaced_creation_responsibility", "proj_top5_concentration",
               "n_candidates", "frac_candidates_cold_start", "log_proj_team_off_poss"]
S2_DECLARED = ["offensive_involvement_proxy", "proj_off_poss_share", "proj_minutes_share",
               "proj_rotation_rank", "p_active", "prior_tov_share", "role_change",
               "trailing_minutes_share", "responsibility_transfer",
               "displaced_creation_responsibility"]
S1_FEATS = [c for c in S1_DECLARED if c != "log_proj_team_off_poss"]
S2_PAIRWISE_OK = [c for c in S2_DECLARED
                  if c not in ("proj_minutes_share", "displaced_creation_responsibility")]
S2_FEATS = [c for c in S2_PAIRWISE_OK if c != "trailing_minutes_share"]


def _group_bounds(grp: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.r_[True, grp[1:] != grp[:-1]])


def _winsorise(df, names, idx, q):
    lo, hi = df[names].iloc[idx].quantile(q[0]), df[names].iloc[idx].quantile(q[1])
    return df[names].clip(lower=lo, upper=hi, axis=1)


def _within_group_center(df, cols, gidx):
    out = pd.DataFrame(index=df.index)
    for c in cols:
        v = df[c].to_numpy(float)
        ok = np.isfinite(v).astype(float)
        s = np.bincount(gidx, weights=np.where(np.isfinite(v), v, 0.0))
        k = np.bincount(gidx, weights=ok)
        mean = np.divide(s, k, out=np.zeros_like(s), where=k > 0)
        out[c] = np.where(np.isfinite(v), v - mean[gidx], 0.0)
    return out


def audit_ws3() -> dict:
    d = dpath("ws3")
    F = pd.read_parquet(d / "ws3_player_features_v1.parquet")
    T = pd.read_parquet(d / "ws3_team_features_v1.parquet")
    tkey = T["game_id"].astype(str) + "|" + T["team_id"].astype(str)
    fkey = F["game_id"].astype(str) + "|" + F["team_id"].astype(str)
    tindex = {k: i for i, k in enumerate(tkey)}
    gidx = fkey.map(tindex).to_numpy()
    order = np.argsort(gidx, kind="stable")
    F = F.iloc[order].reset_index(drop=True)
    gidx = gidx[order]
    starts = _group_bounds(gidx)
    assert len(starts) == len(T), "group bounds must cover every team-game exactly once"

    off1 = T["log_proj_team_off_poss"].to_numpy(float)
    y_t = T["y_team"].to_numpy(float)
    off2 = np.log(np.clip(F["pred_D_ewma_shrunk"].to_numpy(float), 1e-12, None))
    n_pl = F["turnovers"].to_numpy(float)
    seasons = sorted(int(s) for s in T["season"].unique())
    Xc_all = _within_group_center(F, S2_FEATS, gidx)

    s1: list[dict] = []
    s2: list[dict] = []
    for s in seasons:
        tr_t = np.where(T["season"].to_numpy() < s)[0]
        te_t = np.where(T["season"].to_numpy() == s)[0]
        tr_p = np.where(np.isin(gidx, tr_t))[0]
        # ---- stage 1 -------------------------------------------------------------------- #
        if len(tr_t) < MIN_TG:
            s1.append({"label": f"stage1/fold_{s}", "skipped": True, "passed": True,
                       "reason": "falls back to the Arm D aggregate; no design is fitted",
                       "n_features": len(S1_FEATS), "n_rows": int(len(tr_t)),
                       "features": S1_FEATS, "blocking_kinds": [], "finding_kinds": [],
                       "design_rank": _rank_compact({"checked": False}),
                       "missingness": {"any_missing": False,
                                       "outcome_associated_missingness_verdict": "fold not fitted"}})
        else:
            X1w = _winsorise(T[S1_FEATS], S1_FEATS, tr_t, WQ)
            s1.append(gate(f"stage1/fold_{s}", X1w.iloc[tr_t], S1_FEATS,
                           offset=off1[tr_t], target=y_t[tr_t]))
        # ---- stage 2 -------------------------------------------------------------------- #
        if len(tr_p) < MIN_TRAIN_ROWS:
            s2.append({"label": f"stage2/fold_{s}", "skipped": True, "passed": True,
                       "reason": "falls back to D-proportional shares; no design is fitted",
                       "n_features": len(S2_FEATS), "n_rows": int(len(tr_p)),
                       "features": S2_FEATS, "blocking_kinds": [], "finding_kinds": [],
                       "design_rank": _rank_compact({"checked": False}),
                       "missingness": {"any_missing": False,
                                       "outcome_associated_missingness_verdict": "fold not fitted"}})
        else:
            Xw = _winsorise(Xc_all, S2_FEATS, tr_p, WQ)
            s2.append(gate(f"stage2/fold_{s}", Xw.iloc[tr_p], S2_FEATS,
                           offset=off2[tr_p], target=n_pl[tr_p]))
    # ---- final assembled designs -------------------------------------------------------- #
    s1.append(gate("stage1/FINAL_ASSEMBLED_DESIGN", T[S1_FEATS], S1_FEATS,
                   offset=off1, target=y_t))
    s2.append(gate("stage2/FINAL_ASSEMBLED_DESIGN", Xc_all, S2_FEATS, offset=off2, target=n_pl))
    # ---- the DECLARED designs that ws3 itself rejected before fitting -------------------- #
    declared = [
        gate("stage1_AS_DECLARED_rejected_by_ws3", T, S1_DECLARED, offset=off1, target=y_t),
        gate("stage2_AS_DECLARED_rejected_by_ws3",
             _within_group_center(F, S2_DECLARED, gidx), S2_DECLARED, offset=off2, target=n_pl),
    ]
    # ---- outcome-associated missingness on the player frame ----------------------------- #
    om = F["did_appear"].astype(bool).to_numpy()
    raw = gate("stage2_RAW_FEATURES/did_appear_outcome_mask", F, S2_FEATS,
               offset=off2, target=n_pl, outcome_mask=om)
    return {"reconstructed": True,
            "source": "ws3_{player,team}_features_v1.parquet (committed at 1e3509f)",
            "protocol": (f"stage 1: team frame, winsorised at training-fold quantiles {WQ}, "
                         f"MIN_TRAIN_TEAM_GAMES = {MIN_TG}; stage 2: within-team-game centred "
                         f"player frame, winsorised, MIN_TRAIN_ROWS = {MIN_TRAIN_ROWS}"),
            "stage1_features_fitted": S1_FEATS, "stage2_features_fitted": S2_FEATS,
            "stage1": {"summary": summarise(s1), "audits": s1},
            "stage2": {"summary": summarise(s2), "audits": s2},
            "declared_designs_rejected_before_fitting": {
                "summary": summarise(declared), "audits": declared},
            "raw_feature_frame_with_outcome_mask": raw}


# ---------------------------------------------------------------------------------------- #
# WS4 / WS8 -- no feature design
# ---------------------------------------------------------------------------------------- #
def _no_fit_evidence(ws: str, script: str) -> dict:
    src = (dpath(ws) / script).read_text(encoding="utf-8", errors="replace")
    probes = ["feature_gate", "poisson_ridge", "np.linalg", "lstsq", "design matrix",
              "RIDGE_LAMBDA", "sklearn", "statsmodels", "coef"]
    return {"script": script, "n_lines": src.count("\n") + 1,
            "token_hits": {t: src.count(t) for t in probes},
            "imports_feature_gate": "import feature_gate" in src or "from feature_gate" in src,
            "fits_any_regression": any(t in src for t in
                                       ("poisson_ridge", "np.linalg.lstsq", "np.linalg.solve",
                                        "sklearn", "statsmodels"))}


def audit_ws4() -> dict:
    ev = _no_fit_evidence("ws4", "ws4_run.py")
    d = dpath("ws4")
    P = pd.read_parquet(d / "ws4_predictions_intrinsic.parquet")
    variants = [c for c in P.columns if c.startswith("pred_V")]
    return {"reconstructed": False, "reason_not_reconstructed":
            "there is no design matrix to reconstruct: ws4 fits no coefficients",
            "no_fit_evidence": ev,
            "what_it_produced": {
                "kind": "chronological EWMA state-machine variants, compared pairwise",
                "variants": variants, "n_rows_intrinsic": int(len(P)),
                "note": ("each variant is a different EWMA alpha / gating rule applied by a "
                         "left-to-right pass over game dates; no feature enters a linear "
                         "predictor, so feature_gate has no design to audit")},
            "per_arm": {}}


def audit_ws8() -> dict:
    ev = _no_fit_evidence("ws8", "run_ws8_error_decomposition.py")
    dec = json.loads((dpath("ws8") / "WS8_ERROR_DECOMPOSITION.json").read_text(encoding="utf-8"))
    return {"reconstructed": False, "reason_not_reconstructed":
            "there is no design matrix to reconstruct: ws8 fits nothing",
            "no_fit_evidence": ev,
            "what_it_produced": {
                "kind": "five labelled exposure-swap counterfactuals over the FROZEN Arm D rate",
                "schema": dec.get("schema"),
                "counterfactuals": sorted([k for k in (dec.get("counterfactuals") or {})]) or None,
                "note": ("every counterfactual reuses the identical frozen per-row Arm D rate and "
                         "changes only the exposure vector; no coefficient is estimated")},
            "per_arm": {}}


# ---------------------------------------------------------------------------------------- #
# WS5 -- opportunity proxies
# ---------------------------------------------------------------------------------------- #
PROXIES = ["x1_fga_share", "x2_pe_per36", "x3_pe_share", "x4_pe_share_delta",
           "x5_involvement_rank", "x6_responsibility_share"]


def _ws5_specs() -> dict:
    specs: dict = {"K0": {"base": [], "inter": []}, "Dfree": {"base": ["logD"], "inter": []}}
    for i, p in enumerate(PROXIES):
        specs[f"R{i+1}"] = {"base": [p], "inter": []}
    specs["ALL"] = {"base": list(PROXIES), "inter": []}
    for i, p in enumerate(PROXIES):
        specs[f"X{i+1}"] = {"base": [p, "logD"], "inter": [(p, "logD")]}
    return specs


def _ws5_standardise(tr, te, cols, inter):
    """Verbatim run_ws5.standardise: training-fold moments only, products AFTER standardising."""
    if not cols:
        return pd.DataFrame(index=tr.index), pd.DataFrame(index=te.index), []
    mu, sd = tr[cols].mean(), tr[cols].std().replace(0, 1.0)
    Ztr = ((tr[cols] - mu) / sd).fillna(0.0)
    Zte = ((te[cols] - mu) / sd).fillna(0.0)
    names = list(cols)
    for a, b in inter:
        n = f"{a}__X__{b}"
        Ztr[n], Zte[n] = Ztr[a] * Ztr[b], Zte[a] * Zte[b]
        names.append(n)
    return Ztr[names], Zte[names], names


def audit_ws5() -> dict:
    d = dpath("ws5")
    I = pd.read_parquet(d / "ws5_predictions_intrinsic.parquet")
    O = pd.read_parquet(d / "ws5_predictions_operational.parquet")
    train_src = I[I["exposure"] > 0].reset_index(drop=True)
    seasons = sorted(int(s) for s in pd.unique(pd.concat([I["season"], O["season"]])))
    per_arm: dict = {}
    for arm, sp in _ws5_specs().items():
        recs: list[dict] = []
        for s in seasons:
            tr = train_src[train_src["season"] < s]
            if len(tr) < MIN_TRAIN_ROWS:
                recs.append({"label": f"{arm}/fold_{s}", "skipped": True, "passed": True,
                             "reason": "fold falls back to Arm D (beta=0); no design is fitted",
                             "n_features": len(sp["base"]), "n_rows": int(len(tr)),
                             "features": sp["base"], "blocking_kinds": [], "finding_kinds": [],
                             "design_rank": _rank_compact({"checked": False}),
                             "missingness": {"any_missing": False,
                                             "outcome_associated_missingness_verdict":
                                                 "fold not fitted"}})
                continue
            te = (O if s in set(O["season"]) else I)
            te = te[te["season"] == s]
            Z, Zte, names = _ws5_standardise(tr, te, sp["base"], sp["inter"])
            recs.append(gate(f"{arm}/fold_{s}", Z, names, offset=_offset(tr),
                             target=tr["turnovers"].to_numpy(float), test_df=Zte))
        Z, Zo, names = _ws5_standardise(train_src, O, sp["base"], sp["inter"])
        recs.append(gate(f"{arm}/FINAL_ASSEMBLED_DESIGN", Z, names, offset=_offset(train_src),
                         target=train_src["turnovers"].to_numpy(float), test_df=Zo))
        recs.append(operational_frame_audit(arm, sp["base"], O))
        per_arm[arm] = {"features": sp["base"], "interactions": [list(t) for t in sp["inter"]],
                        "summary": summarise(recs), "audits": recs}
    # pooled raw six-proxy admissibility matrix, as ws5 gated it
    pooled_raw = gate("POOLED_SIX_PROXY_RAW_MATRIX", train_src, PROXIES,
                      offset=_offset(train_src), target=train_src["turnovers"].to_numpy(float))
    return {"reconstructed": True,
            "source": "ws5_predictions_{intrinsic,operational}.parquet (committed at 6d9e3f2)",
            "protocol": ("walk-forward by season; gate on the EXACT training-fold standardised "
                         "design matrix, products formed AFTER standardisation"),
            "pooled_six_proxy_raw_matrix": pooled_raw,
            "per_arm": per_arm}


# ---------------------------------------------------------------------------------------- #
# WS6 -- mechanism decomposition
# ---------------------------------------------------------------------------------------- #
def audit_ws6() -> dict:
    root = wpath("ws6")
    pp = ppath("ws6")
    sys.path.insert(0, str(pp))
    try:
        from register_turnover_targets import MECHANISM_CROSSWALK      # noqa: E402
        crosswalk = list(MECHANISM_CROSSWALK)
    finally:
        sys.path.remove(str(pp))

    key = ["game_id", "team_id", "player_id"]
    T = pd.read_parquet(pp / "turnover_targets_v1/player_turnover_targets_v1.parquet")
    TM = pd.read_parquet(pp / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet")
    TM["team_id"] = TM["team_id"].astype("Int64")
    F = pd.read_parquet(pp / "turnover_p2_v1/turnover_role_context_features_v1.parquet")
    P1I = pd.read_parquet(pp / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet")
    C = pd.read_parquet(root / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    F2 = F[key + ["offensive_involvement_proxy", "role_change", "trailing_minutes_share",
                  "proj_minutes_share"]].copy()
    F2["team_id"] = F2["team_id"].astype("Int64")
    F2["player_id"] = F2["player_id"].astype("Int64")
    D = (T.merge(TM[["game_id", "team_id", "source_system"]], on=["game_id", "team_id"], how="left")
           .merge(C, on="game_id", how="left").merge(F2, on=key, how="left"))
    P1I["team_id"] = P1I["team_id"].astype("Int64")
    P1I["player_id"] = P1I["player_id"].astype("Int64")
    F1 = D.merge(P1I[key + ["D_ewma_shrunk", "season"]].rename(columns={"season": "_s"}),
                 on=key, how="inner")
    F1 = F1[(F1["realised_off_possessions"] > 0) & F1["D_ewma_shrunk"].notna()].copy()
    F1["exposure"] = F1["realised_off_possessions"].astype(float)
    F1 = F1.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    off = _offset(F1)
    seasons = sorted(int(s) for s in F1["season"].unique())
    season_arr = F1["season"].to_numpy()
    MECH = [m for m in crosswalk if m in T.columns]
    FEATS, FEATS2 = ["offensive_involvement_proxy"], ["offensive_involvement_proxy", "role_change"]

    dec = json.loads((dpath("ws6") / "WS6_MECHANISM_DECOMPOSITION.json").read_text(encoding="utf-8"))
    fitted = [m for m, v in (dec.get("per_mechanism_fits") or dec.get("fits") or {}).items()
              if isinstance(v, dict) and v.get("status") == "FITTED"]
    targets = [("TOTAL", "turnovers")] + [(m, m) for m in (fitted or MECH)]

    per_arm: dict = {}
    for tag, col in targets:
        y = F1[col].to_numpy(float)
        recs: list[dict] = []
        # (1) parity: arm G's exact protocol, standardise then fillna(0)
        mu_, sd_ = F1[FEATS].mean(), F1[FEATS].std().replace(0, 1.0)
        Zp = pd.DataFrame({"_z": ((F1[FEATS] - mu_) / sd_).fillna(0.0).to_numpy(float).ravel()})
        recs.append(gate(f"{tag}/pooled_parity", Zp, ["_z"], offset=off, target=y))
        # (2) complete case
        cc = F1["offensive_involvement_proxy"].notna().to_numpy()
        Fc = F1.loc[cc]
        muc, sdc = Fc[FEATS].mean(), Fc[FEATS].std().replace(0, 1.0)
        Zc = pd.DataFrame({"_z": ((Fc[FEATS] - muc) / sdc).to_numpy(float).ravel()})
        recs.append(gate(f"{tag}/pooled_complete_case", Zc, ["_z"], offset=off[cc], target=y[cc]))
        # (3) + role change, complete case
        cc2 = (F1["offensive_involvement_proxy"].notna() & F1["role_change"].notna()).to_numpy()
        F2c = F1.loc[cc2]
        mu2, sd2 = F2c[FEATS2].mean(), F2c[FEATS2].std().replace(0, 1.0)
        Xz2 = (F2c[FEATS2] - mu2) / sd2
        Z2 = pd.DataFrame({f"_z{i}": Xz2[c].to_numpy(float) for i, c in enumerate(FEATS2)})
        zn = list(Z2.columns)
        recs.append(gate(f"{tag}/pooled_with_role_change", Z2, zn, offset=off[cc2], target=y[cc2]))
        # (4) walk-forward folds, arm G protocol
        for s in seasons:
            tr = season_arr < s
            if tr.sum() < 2000 or F1.loc[tr, col].sum() < 100:
                recs.append({"label": f"{tag}/walkforward_{s}", "skipped": True, "passed": True,
                             "reason": "insufficient training support; falls back",
                             "n_features": 1, "n_rows": int(tr.sum()), "features": ["_z"],
                             "blocking_kinds": [], "finding_kinds": [],
                             "design_rank": _rank_compact({"checked": False}),
                             "missingness": {"any_missing": False,
                                             "outcome_associated_missingness_verdict":
                                                 "fold not fitted"}})
                continue
            TR = F1.loc[tr]
            mt_, st_ = TR[FEATS].mean(), TR[FEATS].std().replace(0, 1.0)
            Xtr = pd.DataFrame(((TR[FEATS] - mt_) / st_).fillna(0.0).to_numpy(float),
                               columns=["_z"])
            recs.append(gate(f"{tag}/walkforward_{s}", Xtr, ["_z"], offset=off[tr],
                             target=F1.loc[tr, col].to_numpy(float)))
        per_arm[tag] = {"features": FEATS, "summary": summarise(recs), "audits": recs}

    # the RAW, un-imputed columns -- the only place informative missingness can be seen
    raw = gate("RAW_P2_COLUMNS_BEFORE_IMPUTATION/intrinsic_fit_frame", F1, FEATS2,
               offset=off, target=F1["turnovers"].to_numpy(float))
    return {"reconstructed": True,
            "source": ("rebuilt from turnover_targets_v1 + turnover_p2_v1 + turnover_p1_v1 + "
                       "prediction_contract_v5 at 5ef1f25 (ws6 committed no feature parquet)"),
            "protocol": ("arm G's exact design on the intrinsic fit frame; the response is a "
                         "mechanism count instead of the total; parity fits standardise then "
                         "fillna(0), complete-case fits drop nulls"),
            "fit_frame_rows": int(len(F1)), "mechanisms_fitted": [t for t, _ in targets],
            "per_arm": per_arm,
            "raw_columns_before_imputation": raw}


# ---------------------------------------------------------------------------------------- #
# WS7 -- nonlinear / heterogeneous
# ---------------------------------------------------------------------------------------- #
def _rcs_basis(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    k1, k2, k3 = k
    def p(v): return np.clip(v, 0.0, None) ** 3
    return (p(x - k1) - p(x - k2) * (k3 - k1) / (k3 - k2)
            + p(x - k3) * (k2 - k1) / (k3 - k2)) / (k3 - k1) ** 2


def _ws7_basis(spec: dict, form: str, tr: pd.DataFrame, te: pd.DataFrame):
    """Verbatim reimplementation of run_ws7.build_basis.

    Returns (Btr, Bte, names). EVERY data-dependent parameter (spline knots, tier ECDF) comes
    from `tr` only and is APPLIED to `te`, exactly as run_ws7 does. Both halves are returned so
    the gate receives the same `test_df` that run_ws7 gave it -- passing the raw frame instead
    would manufacture a spurious `schema_mismatch` on the derived basis columns.
    """
    if form == "intercept_only":
        return tr[[]].copy(), te[[]].copy(), []
    if form == "linear_control":
        cols = list(spec["cols"])
        return tr[cols].copy(), te[cols].copy(), cols
    if form == "piecewise_linear":
        v = spec["var"]
        kn = np.nanquantile(tr[v].to_numpy(float), spec["knot_quantiles"])
        names = [v] + [f"{v}_hinge_{i+1}" for i in range(len(kn))]

        def mk(df):
            x = df[v].to_numpy(float)
            return pd.DataFrame(np.column_stack([x] + [np.clip(x - z, 0.0, None) for z in kn]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names
    if form == "restricted_cubic_spline":
        v = spec["var"]
        kn = np.nanquantile(tr[v].to_numpy(float), spec["knot_quantiles"])
        names = [v, f"{v}_rcs1"]

        def mk(df):
            x = df[v].to_numpy(float)
            return pd.DataFrame(np.column_stack([x, _rcs_basis(x, kn)]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names
    if form in ("asymmetric_split", "asymmetric_split_plus_group"):
        v, extra = spec["var"], list(spec.get("extra", []))
        names = extra + [f"{v}_expansion", f"{v}_contraction"]

        def mk(df):
            x = df[v].to_numpy(float)
            cols = [df[c].to_numpy(float) for c in extra]
            return pd.DataFrame(np.column_stack(cols + [np.clip(x, 0.0, None),
                                                        np.clip(-x, 0.0, None)]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names
    if form == "interaction":
        a, b = spec["a"], spec["b"]
        names = [a, b, f"{a}_x_{b}"]

        def mk(df):
            va, vb = df[a].to_numpy(float), df[b].to_numpy(float)
            return pd.DataFrame(np.column_stack([va, vb, va * vb]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names
    if form == "partial_pool_continuous_tier":
        v, tv = spec["var"], spec["tier_var"]
        ref = np.sort(tr[tv].dropna().to_numpy(float))
        names = [v, f"tier_{tv}", f"{v}_x_tier", f"{v}_x_tier2"]

        def mk(df):
            x, t = df[v].to_numpy(float), df[tv].to_numpy(float)
            pct = np.full(t.shape, np.nan)
            m = np.isfinite(t)
            if ref.size:
                pct[m] = np.searchsorted(ref, t[m], side="right") / ref.size
            tier = pct - 0.5
            return pd.DataFrame(np.column_stack([x, tier, x * tier, x * tier * tier]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names
    raise ValueError(f"unregistered form {form}")


def audit_ws7() -> dict:
    d = dpath("ws7")
    sys.path.insert(0, str(d))
    try:
        import register_ws7 as R                                             # noqa: E402
        ARMS = {a: dict(v) for a, v in R.ARMS.items()}
    finally:
        sys.path.remove(str(d))
    I = pd.read_parquet(d / "ws7_predictions_intrinsic.parquet")
    O = pd.read_parquet(d / "ws7_predictions_operational.parquet")
    Iv1 = pd.read_parquet(d / "ws7_predictions_intrinsic_v1_leaky.parquet")
    Ov1 = pd.read_parquet(d / "ws7_predictions_operational_v1_leaky.parquet")

    def run(I_, O_, prefix):
        train_src = I_[I_["exposure"] > 0].reset_index(drop=True)
        seasons = sorted(int(s) for s in pd.unique(pd.concat([I_["season"], O_["season"]])))
        per_arm: dict = {}
        for arm, meta in ARMS.items():
            recs: list[dict] = []
            for s in seasons:
                tr = train_src[train_src["season"] < s]
                if len(tr) < MIN_TRAIN_ROWS:
                    recs.append({"label": f"{prefix}{arm}/fold_{s}", "skipped": True,
                                 "passed": True, "n_rows": int(len(tr)),
                                 "reason": "fold falls back to Arm D (beta=0)",
                                 "n_features": meta.get("n_params"), "features": [],
                                 "blocking_kinds": [], "finding_kinds": [],
                                 "design_rank": _rank_compact({"checked": False}),
                                 "missingness": {"any_missing": False,
                                                 "outcome_associated_missingness_verdict":
                                                     "fold not fitted"}})
                    continue
                te = (O_ if s in set(O_["season"]) else I_)
                te = te[te["season"] == s]
                B, Bte, names = _ws7_basis(meta["spec"], meta["form"], tr, te)
                recs.append(gate(f"{prefix}{arm}/fold_{s}", B, names, offset=_offset(tr),
                                 target=tr["turnovers"].to_numpy(float), test_df=Bte))
            B, Bo, names = _ws7_basis(meta["spec"], meta["form"], train_src, O_)
            recs.append(gate(f"{prefix}{arm}/FINAL_ASSEMBLED_DESIGN", B, names,
                             offset=_offset(train_src),
                             target=train_src["turnovers"].to_numpy(float), test_df=Bo))
            # operational prediction design (training-fitted basis params), did_appear as mask
            recs.append(gate(f"{prefix}{arm}/OPERATIONAL_PREDICTION_FRAME", Bo, names,
                             offset=_offset(O_), target=O_["turnovers"].to_numpy(float),
                             outcome_mask=O_["did_appear"].astype(bool).to_numpy()))
            per_arm[arm] = {"form": meta["form"], "summary": summarise(recs), "audits": recs}
        return per_arm

    v2 = run(I, O, "")
    v1 = run(Iv1, Ov1, "v1_leaky/")
    return {"reconstructed": True,
            "source": "ws7_predictions_{intrinsic,operational}[_v1_leaky].parquet (at e858e96)",
            "protocol": ("walk-forward by season; every basis parameter (knots, tier ECDF) is "
                         "fitted on the TRAINING FOLD only; the gate sees the RAW basis before "
                         "standardisation, exactly as run_ws7 called it"),
            "per_arm": v2,
            "superseded_v1_leaky": {"per_arm": v1,
                                    "note": ("the contaminated first execution, preserved in the "
                                             "same commit as WS7_RESULTS_v1_leaky.json and "
                                             "explicitly superseded by the v2_rebuilt run")}}


# ---------------------------------------------------------------------------------------- #
# CLASSIFICATION -- two independent axes, each with its own rationale and receipts.
#
# AXIS 1  feature-design integrity: what the CURRENT gate says about the designs that were fitted.
# AXIS 2  decision validity: whether the PUBLISHED decision result stands. A gate pass does NOT
#         establish this -- comparison parity, candidate universe, chronological isolation,
#         evaluation rows and pipeline leakage are separate requirements.
#
# Assignment rule used for the axis-1 codes, stated so it is reproducible rather than narrative:
#   * `fails_current_gate`               the gate blocks a design the workstream BELIEVED.
#   * `manual_equivalent_checks_documented`
#                                        the gate blocks (or would block) something at the result
#                                        commit AND the workstream implemented, documented and
#                                        ACTED on an equivalent check. Cited per workstream.
#   * `corrected_after_gate_defect`      the gate blocks nothing at the result commit, and the
#                                        reason it blocks nothing is the workstream's own
#                                        corrected rerun.
#   * `posthoc_current_gate_pass`        the gate blocks nothing and no correction was needed.
#   * `not_applicable_no_feature_fit`    no coefficient is estimated from any design.
#   * `not_reconstructable`              the design cannot be rebuilt from committed artifacts.
# ---------------------------------------------------------------------------------------- #
CLASSIFY: dict[str, dict] = {
    "ws1": {
        "axis1_feature_design_integrity": "manual_equivalent_checks_documented",
        "axis1_rationale": (
            "At 5313ebd the current gate passes clean on the final assembled design AND on every "
            "chronological training fold of all six SCIENTIFIC arms (K0, L1, N1, D0_level, "
            "D0_change, S1); worst condition number 15.79, full rank everywhere. It BLOCKS the "
            "seventh arm, X_literal_card_set, as `rank_deficient` in 7 of 8 audits (numerical "
            "rank 4 of 5, smallest singular value 0.0, condition 7.14e14). ws1 detected exactly "
            "that itself, with an SVD rank/condition check it wrote and which feature_gate.py now "
            "names as its own reference implementation, and ACTED on it by marking the arm "
            "`identified: False, diagnostic_only: True` and excluding it from the verdict. So the "
            "gate flags something and the workstream had the equivalent check."),
        "axis2_decision_validity": "valid_only_after_corrected_rerun",
        "axis2_rationale": (
            "The original run 3726991 imputed P2 trailing columns whose null mask is an exact "
            "did_appear indicator, so its operational numbers were contaminated. 5313ebd rebuilt "
            "the signal leak-free and the published numbers CHANGED: L1_linear operational player "
            "deviance 1.227685 -> 1.229904, non-appearer MAE 0.51051 -> 0.51545, L1 vs K0 team "
            "MAE -0.0004 -> -0.0014. The FALSIFIES verdict is unchanged, but only the corrected "
            "commit's numbers may be cited."),
        "rank_and_conditioning_independently_checked": True,
        "rank_check_citation": (
            "run_ws1.py:132-163 design_rank_report(); feature_gate.py:38 cites it verbatim as "
            "'Reference implementation: discovery_wave_1/ws1/run_ws1.py::design_rank_report'"),
        "rank_check_ran_per_fold": False,
        "rank_check_per_fold_note": (
            "run_ws1.py:390 computes ident_report on the POOLED frame F once per arm, not per "
            "training fold. THIS AUDIT closes that gap and finds it changes nothing: every fold "
            "of every scientific arm is full rank and well conditioned."),
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "run_ws1.py:166 LEAKING_P2_COLUMNS dropped outright at :255 and rebuilt in "
            "build_trailing_role_state() :170-220; fail-closed leakage guard :353-387 raises "
            "SystemExit rather than imputing; crosstab evidence in build_features() :239-253"),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": "run_ws1.py:403-414, one feature_gate.audit per (arm, season)",
        "matched_k0_present": True,
        "matched_k0_citation": (
            "run_ws1.py:70-74 ARMS['K0_intercept_only'] = {'features': []}; audit persisted at "
            "ws1/gate_audit_K0_intercept_only.json"),
        "comparison_parity_receipt": (
            "ws1/gate_audit_K0_intercept_only.json + WS1_RESULTS.json "
            "results.*.by_season_paired_vs_K0 -- zero features, identical pipeline, folds, "
            "offset and standardisation path"),
        "corrected_rerun_supersedes_original": True,
        "corrected_rerun_commit": "5313ebd supersedes 3726991",
        "any_reported_result_changed_by_corrected_rerun": True,
        "result_change_detail": (
            "yes: L1_linear operational player deviance 1.227685 -> 1.229904 (D 1.228542, "
            "K0 1.228481); the features went from beating D and K0 to losing to both. The leak "
            "lived entirely in the non-appearer block (appearer MAE 0.94742 -> 0.94743)."),
        "decision_result_artifact":
            "experiments/player_program/discovery_wave_1/ws1/WS1_RESULTS.json (at 5313ebd)",
        "commit_containing_the_valid_decision_result": "5313ebd",
        "published_decision_result_still_valid": (
            "TRUE at 5313ebd only. The verdict FALSIFIES (the apparent +0.0029 team-MAE win over "
            "frozen Arm D is the free unpenalised intercept, not the role features) survives the "
            "current gate on every fold. The 3726991 numbers must not be cited."),
    },
    "ws2": {
        "axis1_feature_design_integrity": "posthoc_current_gate_pass",
        "axis1_rationale": (
            "All seven arms reconstructed. The current gate passes clean on the final assembled "
            "design AND every chronological training fold of every arm (56 fold/final audits plus "
            "7 operational-frame audits, zero blocking findings). Full rank everywhere; worst "
            "condition number 12.80 (T123). No correction was required and none exists."),
        "axis2_decision_validity": "valid_only_after_corrected_rerun",
        "axis2_rationale": (
            "The gate pass does not settle the decision. build_constructions() imputes "
            "offensive_involvement_proxy and trailing_minutes_share to 0.0 BEFORE forming the "
            "constructions (run_ws2:58-62). This audit re-measures those raw inputs on the "
            "operational frame and the current gate BLOCKS them with `missingness_encodes_"
            "outcome`: 8,278 nulls, zero off-diagonal against did_appear, all three columns. The "
            "imputation launders that mask into a VALUE the gate cannot see: transfer_direct, "
            "transfer_allocated and transfer_role_sensitive are exactly 0 on all 8,278 "
            "non-appearers and non-zero ONLY on appearers (corr with did_appear 0.4665, 0.4624, "
            "0.1819). The headline NULL on operational team MAE survives a fortiori -- removing "
            "an inflating leak cannot turn a null into a win. The PRESERVED POSITIVE does not: "
            "T1 +0.00178 and T2 +0.00225 player-level operational vs K0 with CIs excluding zero "
            "are the same order as ws1's measured leak effect in the same non-appearer block. "
            "ws2 never tested this -- the string 'did_appear' appears nowhere in its artifacts. "
            "No corrected rerun exists."),
        "rank_and_conditioning_independently_checked": False,
        "rank_check_citation": (
            "none: zero svd / numerical_rank / condition_number hits in "
            "run_ws2_responsibility_transfer.py or failure_analysis_ws2.py. THIS AUDIT supplies "
            "it: full rank in every fold of every arm, worst condition 12.80."),
        "rank_check_ran_per_fold": False,
        "missingness_independently_checked": False,
        "missingness_check_citation": (
            "NO appearance test exists. FROZEN_CONSTRUCTIONS.json documents the imputation as a "
            "mechanistic choice -- 'NULL IMPUTED TO 0.0' with null_imputation_rationale 'a player "
            "with no prior offensive history has no established creation share' -- but never "
            "tests the null mask against did_appear. WS2_VERDICT.json's oracle_check tests a "
            "DIFFERENT question (whether the effect hides on the oracle track)."),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": (
            "run_ws2_responsibility_transfer.py:180, one audit per (track, season, arm) on the "
            "standardised design; 70 audits recorded in ws2/FEATURE_GATE_LOG.json"),
        "matched_k0_present": True,
        "matched_k0_citation": (
            "NOT in run_ws2_responsibility_transfer.py -- its ARMS dict has no zero-feature arm "
            "and the string 'K0' does not occur in WS2_RESULTS.json. It is supplied by a SECOND "
            "script at the same commit: failure_analysis_ws2.py:51-88 fit_k0(), 'intercept-only "
            "control arm, identical pipeline'"),
        "comparison_parity_receipt":
            "ws2/WS2_FAILURE_ANALYSIS.json (produced by failure_analysis_ws2.py at 863a900)",
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": "none exists",
        "any_reported_result_changed_by_corrected_rerun": False,
        "result_change_detail": "no corrected rerun was performed for ws2",
        "decision_result_artifact":
            "experiments/player_program/discovery_wave_1/ws2/WS2_VERDICT.json (at 863a900)",
        "commit_containing_the_valid_decision_result": (
            "863a900 for the NULL half only; no commit contains a leak-free measurement of the "
            "preserved player-level operational positive"),
        "published_decision_result_still_valid": (
            "PARTLY. Valid: 'NULL on the registered primary metric (operational team MAE)' and "
            "the disposition 'does not qualify as a challenger to Arm D'. NOT valid without a "
            "leak-free rerun: the preserved weak POSITIVE player-level operational finding "
            "(T1 +0.00178, T2 +0.00225, T123 +0.00214 vs K0, CIs excluding zero). The intrinsic "
            "counterpart (T2 +0.00128 [+0.00107,+0.00149]) is unaffected, because the intrinsic "
            "track contains only appearers and the training folds are intrinsic, so the fitted "
            "coefficients are clean."),
    },
    "ws3": {
        "axis1_feature_design_integrity": "manual_equivalent_checks_documented",
        "axis1_rationale": (
            "Reconstructed both stages. The current gate BLOCKS stage2/fold_2022 with "
            "`impossible_scaling` (proj_off_poss_share std 7.80e-09, p_active std 5.14e-17) and "
            "BLOCKS both AS-DECLARED designs -- stage 1 with `deterministic_transform_of_offset` "
            "(log_proj_team_off_poss corr 1.0 with the offset) and stage 2 with `near_collinear` "
            "+ `rank_deficient` (rank 9 of 10, smallest singular value 0.0, condition 3.33e15). "
            "Every one of those is a defect ws3 found FIRST and acted on: fold_gate() drops the "
            "degenerate features for that fold, rank_check() reports the null-space loadings, and "
            "the declared feature sets were reduced BEFORE any fit. The designs actually fitted "
            "(S1_FEATS 9 features, S2_FEATS 7 features) pass on every remaining fold."),
        "axis2_decision_validity": "valid_as_published",
        "axis2_rationale": (
            "Comparison parity is in-pipeline (K0_total, zero features, identical folds, offset "
            "and pipeline) and the falsification is measured against it: stage-1 features add "
            "-0.00340 [-0.03975,+0.03398] over K0. Stage 2 is evaluated with the team total held "
            "EXACTLY at the D aggregate so the team metric is identical to the incumbent by "
            "construction, and the allocation constraint holds to 1.07e-14. ws3 also WITHDREW its "
            "own motivating observation on cutoff-valid grounds rather than defending it. Nothing "
            "in the current gate disturbs the NULL."),
        "rank_and_conditioning_independently_checked": True,
        "rank_check_citation": (
            "run_ws3_two_stage.py:413-440 rank_check(), including null_space_loadings; results in "
            "ws3/WS3_FEATURE_GATE.json.multiway_rank_check"),
        "rank_check_ran_per_fold": False,
        "rank_check_per_fold_note": (
            "rank_check ran on the pooled stage-1 and stage-2 designs, not per fold; the PER-FOLD "
            "coverage came from fold_gate(), which caught the 2022 degeneracy. THIS AUDIT ran the "
            "rank check per fold too: full rank in every fitted fold of both stages."),
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "run_ws3_two_stage.py:540-563 leakage_audit with null_pattern_is_exactly_did_appear, "
            "run against BOTH the canonical P2 artifact and the ws3 rebuild; the rebuilt columns "
            "are clean and the finding is carried into LEDGER_UPDATE_ws3.json."
            "motivating_observation_withdrawn"),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": (
            "run_ws3_two_stage.py:378-410 fold_gate(), 'Run the PERMANENT gate on the TRAINING "
            "FOLD ACTUALLY BEING FITTED. Auditing the pooled matrix once is not enough.'"),
        "matched_k0_present": True,
        "matched_k0_citation": (
            "run_ws3_two_stage.py:582 T['K0_total'] and :613-617 'K0: intercept only, identical "
            "pipeline, zero features'"),
        "comparison_parity_receipt": (
            "ws3/WS3_RESULTS.json + LEDGER_UPDATE_ws3.json.result, which quotes the K0 comparison "
            "-0.00340 CI [-0.03975,+0.03398] directly"),
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": (
            "none; the first execution's failure is PRESERVED in-script as "
            "run_ws3_two_stage.py:SOFTMAX_SATURATION 'NEGATIVE RESULT, PRESERVED' rather than "
            "being replaced by a separate commit"),
        "any_reported_result_changed_by_corrected_rerun": True,
        "result_change_detail": (
            "within the same commit: the first execution's stage-2 softmax saturated (shares "
            "exactly 0.0 and 1.0, deviance 8.2465). Three in-script corrections followed, the "
            "first of which was moving the gate to run PER TRAINING FOLD. Both the failed and the "
            "corrected numbers are published side by side."),
        "decision_result_artifact": (
            "experiments/player_program/discovery_wave_1/ws3/LEDGER_UPDATE_ws3.json "
            "(result + disposition) and ws3/WS3_RESULTS.json (at 1e3509f)"),
        "commit_containing_the_valid_decision_result": "1e3509f",
        "published_decision_result_still_valid": (
            "TRUE. 'NULL. The two-stage formulation does not improve player identity and does not "
            "match the D aggregate on the team total.' Stage 1 team MAE 3.00926 vs D aggregate "
            "2.96745; against K0 the nine stage-1 features add nothing."),
    },
    "ws4": {
        "axis1_feature_design_integrity": "not_applicable_no_feature_fit",
        "axis1_rationale": (
            "ws4_run.py estimates no coefficients. Machine-checked at the result commit: zero "
            "occurrences of feature_gate, poisson_ridge, np.linalg, lstsq, sklearn or "
            "statsmodels in the 619-line script. The seven variants are EWMA state machines that "
            "differ only in decay constant and gating rule, applied by one left-to-right pass "
            "over game dates. There is no design matrix, so the feature gate has no purchase."),
        "axis2_decision_validity": "valid_as_published",
        "axis2_rationale": (
            "Comparison parity is structural rather than K0-shaped: every variant runs through "
            "the identical chronological state machine over the identical rows, so V0 (the frozen "
            "registered alpha=0.10) is an exactly matched incumbent. Candidate set, folds, "
            "strata, gate threshold and selection rule were frozen in PREREGISTRATION.json before "
            "any number was produced, and the verdict rule was applied mechanically. ws4 also "
            "avoided the wave's shared leak by construction: it does not consume the P2 "
            "role_change column, it rebuilds the signal reading state for every candidate. The "
            "verdict is NOT_SUPPORTED and the report explicitly refuses to promote the winner."),
        "rank_and_conditioning_independently_checked": "not applicable -- no design matrix exists",
        "rank_check_citation": "n/a",
        "rank_check_ran_per_fold": "not applicable",
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "ws4_run.py:77-105 leakage_receipt(), which verifies by crosstab that "
            "role_change.notna() is an exact did_appear indicator (off_diagonal 0) and records "
            "'WS4 does NOT use this column. It rebuilds the signal with the identical EWMA state "
            "machine and constant but reads the state for every candidate on the date'"),
        "gate_checks_ran_per_fold": "not applicable -- no design is fitted in any fold",
        "gate_per_fold_citation": "n/a",
        "matched_k0_present": False,
        "matched_k0_citation": (
            "not applicable: with no fitted intercept there is no free-recalibration confound to "
            "control. The matched control is V0_incumbent_a010, the frozen registered alpha "
            "running through the identical state machine (ws4_run.py:44-46, INCUMBENT)"),
        "comparison_parity_receipt": (
            "ws4/PREREGISTRATION.json (candidate set, FOLD_SEASONS [2022..2026] with 2021 as "
            "burn-in, strata, selection rule C1-C4) + ws4/WS4_VERDICT.json.rule"),
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": "none exists",
        "any_reported_result_changed_by_corrected_rerun": False,
        "result_change_detail": "no corrected rerun was performed for ws4",
        "decision_result_artifact":
            "experiments/player_program/discovery_wave_1/ws4/WS4_VERDICT.json (at 1b634fb)",
        "commit_containing_the_valid_decision_result": "1b634fb",
        "published_decision_result_still_valid": (
            "TRUE. hypothesis_verdict NOT_SUPPORTED; the evidence runs opposite to the "
            "hypothesis (longer memory is better in stable AND unstable strata), and the report "
            "states its own effect-size honesty: the largest pooled gain is 0.00216 MAE, about a "
            "quarter of one percent of the incumbent."),
    },
    "ws5": {
        "axis1_feature_design_integrity": "posthoc_current_gate_pass",
        "axis1_rationale": (
            "All 15 arms reconstructed (K0, Dfree, R1-R6, ALL, X1-X6). The current gate passes "
            "clean on the final assembled design AND every chronological training fold of every "
            "arm, plus the pooled six-proxy admissibility matrix and every operational prediction "
            "frame. Full rank everywhere; worst condition number 28.66 (the six-proxy ALL arm). "
            "Zero missingness on all 35,629 operational rows for all six proxies, so neither new "
            "missingness check has anything to fire on."),
        "axis2_decision_validity": "valid_as_published",
        "axis2_rationale": (
            "This workstream carries the wave's only surviving positive, so the parity "
            "requirements matter most here and they are met. K0 is in-pipeline and every proxy is "
            "reported against BOTH Arm D and K0; Wfree/WKfree renormalise the NO-PROXY arm the "
            "same way, controlling for 'is the reallocation gain the proxy's, or just a relaxed "
            "Arm-D coefficient?'. The wave's shared did_appear defect was found by ws5 "
            "independently and ws5 consumes none of the affected columns -- it rebuilt all six "
            "proxies, non-null on all 35,629 operational rows, and its x1 reproduces the "
            "canonical FGA-share formula to max_abs_diff 0.0 wherever the canonical is defined. "
            "The preregistered bar was stated before results and the verdict reports which half "
            "clears it and which does not."),
        "rank_and_conditioning_independently_checked": False,
        "rank_check_citation": (
            "none: zero svd / numerical_rank / condition_number hits in run_ws5.py, "
            "build_ws5_features.py or freeze_ws5.py. THIS AUDIT supplies it -- full rank in every "
            "fold of every arm, worst condition 28.66, no ill-conditioning."),
        "rank_check_ran_per_fold": False,
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "run_ws5.py:74-111 input_defect_receipt() -> ws5/WS5_INPUT_DEFECT_RECEIPT.json and "
            "WS5_VERDICT.json.shared_input_defect_found, which proves both halves: the canonical "
            "P2 columns ARE exact did_appear indicators, and ws5 consumes none of them"),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": (
            "run_ws5.py:198, 'MANDATORY PREFIT GATE on the exact design matrix, fails closed', "
            "one audit per (arm, season, track); 151 audits in ws5/WS5_FEATURE_GATE.json"),
        "matched_k0_present": True,
        "matched_k0_citation": (
            "run_ws5.py:41 CONTROL = {'K0': []}, 'the recalibration-only control. Zero features, "
            "unpenalised intercept, same everything else'"),
        "comparison_parity_receipt": (
            "ws5/WS5_VERDICT.json.per_proxy and .best_role_overall, both reported vs D AND vs K0; "
            "plus the Wfree/WKfree no-proxy renormalisation controls (run_ws5.py:226-235)"),
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": "none needed",
        "any_reported_result_changed_by_corrected_rerun": False,
        "result_change_detail": (
            "no corrected rerun. ws5 did record that its own target-leakage probe failed on first "
            "run and that investigation showed the PROBE was wrong, not the streamer "
            "(WS5_VERDICT.json.gate_summary.target_derived_leakage.probe_history)."),
        "decision_result_artifact":
            "experiments/player_program/discovery_wave_1/ws5/WS5_VERDICT.json (at 6d9e3f2)",
        "commit_containing_the_valid_decision_result": "6d9e3f2",
        "published_decision_result_still_valid": (
            "TRUE. 'PARTIAL SUPPORT -- allocation only; expected direction FALSIFIED.' The "
            "allocation role clears the preregistered bar against both D and K0 for x1, x2, x3, "
            "x5, x6; the rate and interaction roles are null to negative; and the verdict itself "
            "records not_promotable."),
    },
    "ws6": {
        "axis1_feature_design_integrity": "posthoc_current_gate_pass",
        "axis1_rationale": (
            "CONTRARY TO THE STANDING ASSUMPTION, ws6 DOES fit feature designs: Poisson ridge and "
            "cluster-robust Poisson on offensive_involvement_proxy (and on that plus role_change) "
            "for 20 targets. Reconstructed in full from turnover_targets_v1 + turnover_p2_v1 + "
            "turnover_p1_v1 + prediction_contract_v5, since ws6 committed no feature parquet. The "
            "current gate passes clean on all 180 audits -- 4 designs x 20 targets plus 5 "
            "walk-forward folds each. Full rank everywhere; worst condition number 1.549. The "
            "raw un-imputed columns carry 894 nulls (3.17%) but the null mask correlates only "
            "-0.0075 with the target, so `missingness_informative` does not fire either."),
        "axis2_decision_validity": "diagnostic_only",
        "axis2_rationale": (
            "Two independent reasons, neither of which is a gate finding. First, no matched K0 or "
            "any featureless control exists anywhere in ws6, so it can make a mechanism claim but "
            "not a comparison claim; it promotes nothing and registers nothing. Second, its "
            "central question presupposes the arm-G phenomenon AS MEASURED IN P2 (its own key "
            "'arm_G_phenomenon_as_measured_in_P2'), and that measurement rests on the leaking P2 "
            "involvement column: ws3 withdrew exactly this motivating observation ('the "
            "aggregation-cancellation reading of arm G is not established on cutoff-valid "
            "inputs', leak worth 0.02180 player deviance = 15.9x the published arm-G gain of "
            "0.00137) and ws5 measured the clean replacement. ws6's own fits are on the INTRINSIC "
            "track, where every row is an appearer and the null mask means 'first appearances', "
            "not did_appear -- so the fits are internally sound and the decomposition is "
            "arithmetically closed. The verdict is a rejection of a cause, which is legitimate "
            "diagnostic output, but it cannot carry a decision."),
        "rank_and_conditioning_independently_checked": False,
        "rank_check_citation": (
            "none: zero svd / numerical_rank / condition_number hits in "
            "run_ws6_mechanism_decomposition.py. THIS AUDIT supplies it -- every design is at "
            "most 2 features, full rank, worst condition 1.549, so the rank fix could not have "
            "changed any ws6 result."),
        "rank_check_ran_per_fold": False,
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "run_ws6_mechanism_decomposition.py:26-30 'NULLS ARE PRESERVED ... Diagnostics NEVER "
            "impute. Two fits are reported side by side: parity (mean-imputation, exactly what "
            "arm G did) and complete_case (nulls dropped). Divergence between them is itself "
            "reported.' Counts recorded in WS6_MECHANISM_DECOMPOSITION.json."
            "join_coverage_nulls_preserved. This is an equivalent of the missingness fix for the "
            "intrinsic track, but it is NOT an appearance test -- ws6 never runs one, and does "
            "not need to, because it never touches the operational track."),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": (
            "run_ws6_mechanism_decomposition.py:161-167 GATE() and :483-484 "
            "GATE(f'{m}|walkforward_{int(s)}'), one audit per (mechanism, season)"),
        "matched_k0_present": False,
        "matched_k0_citation": (
            "NONE. There is no zero-feature control in run_ws6_mechanism_decomposition.py. The "
            "reference is arm G refitted on the TOTAL through the identical protocol "
            "(:527-540 'this reproduces arm G on the TOTAL count, for reference') plus a "
            "walk-forward share_baseline (:409-423). Both are same-feature references, not "
            "featureless ones, so the free-intercept confound named by ws1/ws2/ws5/ws7 is "
            "uncontrolled here."),
        "comparison_parity_receipt": (
            "NONE EXISTS for a featureless baseline. The available parity receipt is protocol "
            "parity only: WS6_MECHANISM_DECOMPOSITION.json plus the docstring PROTOCOL PARITY "
            "clause ('same offset, same ridge lambda, same walk-forward-by-season split, same "
            "standardisation ... the single change that the response is a mechanism count')"),
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": "none exists",
        "any_reported_result_changed_by_corrected_rerun": False,
        "result_change_detail": "no corrected rerun was performed for ws6",
        "decision_result_artifact": (
            "experiments/player_program/discovery_wave_1/ws6/WS6_MECHANISM_DECOMPOSITION.json "
            "(.verdict) at 5ef1f25"),
        "commit_containing_the_valid_decision_result": (
            "5ef1f25, for the DIAGNOSTIC finding only"),
        "published_decision_result_still_valid": (
            "AS A DIAGNOSTIC, yes: 'REJECTED_AS_CAUSE__HETEROGENEITY_REAL_BUT_NOT_OFFSETTING'. "
            "The negative -- offsetting mechanism effects do NOT explain the arm-G phenomenon -- "
            "is robust to the gate. As a claim about arm G's operational behaviour it is not "
            "independently valid, because the phenomenon it decomposes was measured on the "
            "leaking P2 column and ws3 withdrew that reading."),
    },
    "ws7": {
        "axis1_feature_design_integrity": "corrected_after_gate_defect",
        "axis1_rationale": (
            "All ten arms reconstructed for BOTH the superseded v1_leaky run and the v2_rebuilt "
            "run preserved at the same commit. On v2_rebuilt the current gate passes clean on the "
            "final assembled design AND every chronological training fold of every arm -- full "
            "rank everywhere, worst condition number 25.13 (W4_inv_x_minutes), zero missingness "
            "on all 35,629 operational rows. The reason it passes is ws7's own repair: "
            "build_trailing_v2.py rebuilt the leaking prior-role columns and run_ws7.py's "
            "leakage_check() blocks any basis whose null pattern agrees with did_appear at "
            ">= 0.999. Without that repair the same designs carry the defect the missingness fix "
            "was written to catch."),
        "axis2_decision_validity": "valid_only_after_corrected_rerun",
        "axis2_rationale": (
            "The repair CHANGED a published conclusion, not merely the decimals: "
            "expected_direction went to 'REFUTED for primary creators -- after the leakage repair "
            "every arm is significantly NEGATIVE there (W1 -0.00204 vs K0, CI excluding zero); "
            "the leakage had been masking a real loss.' Only WS7_RESULTS.json (v2_rebuilt) may be "
            "cited; WS7_RESULTS_v1_leaky.json and gate_v1_leaky/ are preserved as the "
            "contaminated 'before' and are explicitly superseded. Comparison parity is met: "
            "K0_intercept_only is a registered arm and ws7 independently reproduced the "
            "externally measured K0 operational team MAE of 2.96419."),
        "rank_and_conditioning_independently_checked": False,
        "rank_check_citation": (
            "none: zero svd / numerical_rank / condition_number hits in run_ws7.py. ws7 did run "
            "gate_selftest() (:178-189) proving the gate still catches the algebraically "
            "identical projected-share pair, but that is a gate-integrity check, not a rank "
            "check. THIS AUDIT supplies the rank check -- full rank in every fold of every arm, "
            "worst condition 25.13, including the 4-column partial-pool tier basis."),
        "rank_check_ran_per_fold": False,
        "missingness_independently_checked": True,
        "missingness_check_citation": (
            "run_ws7.py:143-175 leakage_check(), 'a feature whose NULL PATTERN coincides with "
            "did_appear is leakage ... This is checked on the OPERATIONAL prediction frame, "
            "because the intrinsic training frame contains only appearers and therefore cannot "
            "reveal the defect', enforced per fold at :296-301; audits in ws7/gate/GATE_*.json"),
        "gate_checks_ran_per_fold": True,
        "gate_per_fold_citation": (
            "run_ws7.py:280-304, feature_gate.audit plus leakage_check per (arm, track, season), "
            "fail-closed with fallback to Arm D; ws7/gate/ and ws7/gate_v1_leaky/"),
        "matched_k0_present": True,
        "matched_k0_citation": (
            "register_ws7.ARMS['K0_intercept_only'] (form 'intercept_only'); run_ws7.py:58-60 "
            "'zero features. The unpenalised intercept is supplied by poisson_ridge itself.'"),
        "comparison_parity_receipt": (
            "ws7/WS7_LEDGER_UPDATE.json.patch.new_confound_found, which states the K0 figure "
            "2.9642 vs Arm D 2.9675 and that ws7 independently reproduced the externally measured "
            "2.96419; every arm is reported against both"),
        "corrected_rerun_supersedes_original": True,
        "corrected_rerun_commit": (
            "e858e96 contains BOTH: WS7_RESULTS.json (v2_rebuilt, authoritative) supersedes "
            "WS7_RESULTS_v1_leaky.json. The mode switch is run_ws7.py:193-198."),
        "any_reported_result_changed_by_corrected_rerun": True,
        "result_change_detail": (
            "yes, and a conclusion flipped: expected_direction for primary creators went from "
            "masked to REFUTED, every arm significantly negative there after the repair. The "
            "headline NULL/REFUTED verdict is unchanged."),
        "decision_result_artifact": (
            "experiments/player_program/discovery_wave_1/ws7/WS7_RESULTS.json + "
            "ws7/WS7_LEDGER_UPDATE.json (at e858e96). NOT WS7_RESULTS_v1_leaky.json."),
        "commit_containing_the_valid_decision_result": "e858e96 (v2_rebuilt artifacts only)",
        "published_decision_result_still_valid": (
            "TRUE for the v2_rebuilt artifacts. 'NULL on the hypothesis; REFUTED on the "
            "operational decision metric. DO NOT CARRY FORWARD.' Zero of seven variants beat Arm "
            "D with a CI excluding zero; five of seven are significantly worse than fitting no "
            "features at all."),
    },
    "ws8": {
        "axis1_feature_design_integrity": "not_applicable_no_feature_fit",
        "axis1_rationale": (
            "Machine-checked at the result commit: zero occurrences of feature_gate, "
            "poisson_ridge, np.linalg, lstsq, sklearn or statsmodels in the 689-line script. "
            "Every counterfactual reuses the identical frozen per-row Arm D rate and changes only "
            "the exposure vector, so no coefficient is estimated and there is no design matrix "
            "for the gate to audit. Consistent with the operator's adjudication."),
        "axis2_decision_validity": "diagnostic_only",
        "axis2_rationale": (
            "Self-declared and structurally true: CF2..CF5 each consume information unavailable "
            "at the forecast cutoff (who played, how much, how many possessions the game ran). "
            "The script states 'ORACLE VARIANTS ARE DIAGNOSTICS, NOT MODELS ... None of them is a "
            "forecast, none is promotion evidence, none may be registered as an arm.' Consistent "
            "with the operator's adjudication."),
        "rank_and_conditioning_independently_checked": "not applicable -- no design matrix exists",
        "rank_check_citation": "n/a",
        "rank_check_ran_per_fold": "not applicable",
        "missingness_independently_checked": "not applicable -- no feature is imputed or fitted",
        "missingness_check_citation": "n/a",
        "gate_checks_ran_per_fold": "not applicable -- no design is fitted in any fold",
        "gate_per_fold_citation": "n/a",
        "matched_k0_present": False,
        "matched_k0_citation": (
            "not applicable: no arm is fitted, so there is no free intercept to control. Parity "
            "is by construction -- every counterfactual reuses the identical frozen Arm D rate "
            "from the single chronological pass in run_turnover_p1_universe_fix.py"),
        "comparison_parity_receipt": (
            "ws8/WS8_ERROR_DECOMPOSITION.json; parity is the shared frozen rate vector plus the "
            "single stated sign convention, not a fitted control"),
        "corrected_rerun_supersedes_original": False,
        "corrected_rerun_commit": "none exists",
        "any_reported_result_changed_by_corrected_rerun": False,
        "result_change_detail": "no corrected rerun was performed for ws8",
        "decision_result_artifact": (
            "experiments/player_program/discovery_wave_1/ws8/WS8_ERROR_DECOMPOSITION.json and "
            "ws8/WS8_LEDGER_RESULT.json (at c1d2637)"),
        "commit_containing_the_valid_decision_result": "c1d2637",
        "published_decision_result_still_valid": (
            "TRUE as a labelled diagnostic decomposition. It is not a forecasting result and was "
            "never offered as one."),
    },
}

ACCEPTANCE_FIELDS = [
    "original_result_commit", "gate_blob_used_during_execution",
    "retrospective_audit_receipt", "fold_level_audit_status",
    "matched_k0_or_comparison_parity_status", "corrected_rerun_commit",
    "exact_supporting_artifact", "axis1_rationale", "axis2_rationale",
]


def _digest(obj) -> str:
    import hashlib
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def assemble(ws: str, audit: dict, prov: dict) -> dict:
    """Merge the audit facts with the classification and enforce the acceptance gate."""
    c = dict(CLASSIFY[ws])
    p = prov["per_workstream"][ws]

    # roll the per-arm audit records up into the required summary fields
    arms = dict(audit.get("per_arm") or {})
    for k in ("stage1", "stage2"):
        if k in audit:
            arms[k] = audit[k]
    gate_result: dict = {}
    rank_block: dict = {}
    miss_block: dict = {}
    for arm, blk in arms.items():
        s = blk["summary"]
        gate_result[arm] = {"n_audits": s["n_audits"], "all_passed": s["all_passed"],
                            "n_blocked": s["n_blocked"],
                            "blocking_kinds": s["blocking_kinds"],
                            "blocked_labels": s["blocked_labels"]}
        rank_block[arm] = {a["label"]: a["design_rank"] for a in blk["audits"]
                           if a.get("design_rank", {}).get("checked")}
        miss_block[arm] = {a["label"]: a["missingness"] for a in blk["audits"]
                           if a.get("missingness", {}).get("any_missing")}
    entry = {
        # ---- acceptance-gate fields ---------------------------------------------------- #
        "original_result_commit": p["result_commit"],
        "gate_blob_used_during_execution": {
            "blob": p["gate_blob_at_result_commit"],
            "is_the_prefix_blob": p["gate_blob_is_the_prefix_blob"],
            "inherited_from": f"{BASE_COMMIT} (base commit of the wave)",
            "rank_fix_55f4500_is_ancestor": p["rank_fix_55f4500_is_ancestor"],
            "missingness_fix_42af2cd_is_ancestor": p["missingness_fix_42af2cd_is_ancestor"]},
        "retrospective_audit_receipt": {
            "path": ("experiments/player_program/discovery_wave_1/"
                     "RETROSPECTIVE_GATE_AUDIT.json#/workstreams/" + ws),
            "produced_by": ("experiments/player_program/discovery_wave_1/"
                            "retrospective_gate_audit.py"),
            "audit_block_sha256": _digest(audit),
            "current_gate_blob_used_for_this_audit": prov["current_gate"]["gate_blob_at_head"]},
        "fold_level_audit_status": (
            {"reconstructed": True, "per_arm": gate_result}
            if arms else
            {"reconstructed": False,
             "reason": audit.get("reason_not_reconstructed", "no design matrix exists")}),
        "matched_k0_or_comparison_parity_status": {
            "matched_k0_present": c["matched_k0_present"],
            "citation": c["matched_k0_citation"],
            "comparison_parity_receipt": c["comparison_parity_receipt"]},
        "corrected_rerun_commit": c["corrected_rerun_commit"],
        "exact_supporting_artifact": c["decision_result_artifact"],
        # ---- the two axes, each with its own rationale ---------------------------------- #
        "axis1_feature_design_integrity": c["axis1_feature_design_integrity"],
        "axis1_rationale": c["axis1_rationale"],
        "axis2_decision_validity": c["axis2_decision_validity"],
        "axis2_rationale": c["axis2_rationale"],
        # ---- the explicitly required per-workstream reports ------------------------------ #
        "rank_and_conditioning_independently_checked":
            c["rank_and_conditioning_independently_checked"],
        "rank_check_citation": c["rank_check_citation"],
        "rank_check_ran_per_fold": c["rank_check_ran_per_fold"],
        "rank_check_per_fold_note": c.get("rank_check_per_fold_note"),
        "missingness_independently_checked": c["missingness_independently_checked"],
        "missingness_check_citation": c["missingness_check_citation"],
        "gate_checks_ran_per_fold": c["gate_checks_ran_per_fold"],
        "gate_per_fold_citation": c["gate_per_fold_citation"],
        "matched_k0_present": c["matched_k0_present"],
        "corrected_rerun_supersedes_original": c["corrected_rerun_supersedes_original"],
        "any_reported_result_changed_by_corrected_rerun":
            c["any_reported_result_changed_by_corrected_rerun"],
        "result_change_detail": c["result_change_detail"],
        "commit_containing_the_valid_decision_result":
            c["commit_containing_the_valid_decision_result"],
        "published_decision_result_still_valid": c["published_decision_result_still_valid"],
        # ---- raw audit output ------------------------------------------------------------ #
        "current_gate_audit_result": gate_result or "no design fitted",
        "fold_level_rank_and_conditioning": rank_block or "no design fitted",
        "fold_level_missingness": miss_block or "no design fitted",
        "reconstruction": {k: audit.get(k) for k in
                           ("reconstructed", "source", "protocol",
                            "reason_not_reconstructed", "no_fit_evidence",
                            "what_it_produced", "fit_frame_rows",
                            "stage1_features_fitted", "stage2_features_fitted",
                            "mechanisms_fitted")
                           if audit.get(k) is not None},
        "supplementary_probes": {k: audit[k] for k in
                                 ("raw_p2_inputs_before_imputation",
                                  "imputed_zero_encodes_non_appearance",
                                  "raw_columns_before_imputation",
                                  "raw_feature_frame_with_outcome_mask",
                                  "pooled_six_proxy_raw_matrix",
                                  "declared_designs_rejected_before_fitting",
                                  "superseded_v1_leaky")
                                 if k in audit},
        "full_audits": {"per_arm": audit.get("per_arm"),
                        "stage1": audit.get("stage1"), "stage2": audit.get("stage2")},
    }
    entry["acceptance_gate"] = {
        "required_fields": ACCEPTANCE_FIELDS,
        "missing_fields": [f for f in ACCEPTANCE_FIELDS
                           if entry.get(f) in (None, "", [], {})],
    }
    entry["acceptance_gate"]["passes"] = not entry["acceptance_gate"]["missing_fields"]
    return entry


# ---------------------------------------------------------------------------------------- #
# markdown report
# ---------------------------------------------------------------------------------------- #
def write_markdown(out: dict, json_sha: str) -> None:
    W = out["workstreams"]
    prov = out["provenance_verification"]
    L: list[str] = []
    A = L.append
    A("# Retrospective gate audit — discovery wave 1")
    A("")
    A(f"*Generated by `experiments/player_program/discovery_wave_1/retrospective_gate_audit.py` "
      f"at {out['executed_utc']}.*")
    A("")
    A("**AUDIT ONLY.** No model was refitted for selection, no feature was changed, no decision "
      "result was recomputed. Design matrices were recomputed solely in order to audit them. The "
      "eight agent worktrees were read strictly read-only and `feature_gate.py` was imported, "
      "never modified.")
    A("")
    A(f"Machine-readable companion: `RETROSPECTIVE_GATE_AUDIT.json` (sha256 `{json_sha}`).")
    A("")
    A("## 1. Ancestry and blob verification")
    A("")
    v = prov["verdict"]
    A(f"- All eight result commits carry the pre-fix gate blob: **{v['all_eight_carry_the_prefix_blob']}**")
    A(f"- `55f4500` (rank / conditioning) is an ancestor of **none** of them: **{v['rank_fix_governs_none']}**")
    A(f"- `42af2cd` (informative missingness) is an ancestor of **none** of them: **{v['missingness_fix_governs_none']}**")
    A(f"- Conclusion: **{v['conclusion']}**")
    A("")
    A(f"Current gate used for this audit: blob `{prov['current_gate']['gate_blob_at_head']}` at "
      f"HEAD `{prov['current_gate']['head']}` on branch `{prov['current_gate']['branch']}` "
      f"(RANK_TOL {prov['current_gate']['RANK_TOL']}, COND_MAX "
      f"{prov['current_gate']['COND_MAX']:g}).")
    A("")
    A("| WS | result commit | gate blob at that commit | pre-fix? | 55f4500 anc. | 42af2cd anc. |")
    A("|---|---|---|---|---|---|")
    for ws in WS:
        p = prov["per_workstream"][ws]
        A(f"| {ws} | `{p['result_commit'][:7]}` | `{p['gate_blob_at_result_commit'][:12]}…` | "
          f"{'yes' if p['gate_blob_is_the_prefix_blob'] else 'NO'} | "
          f"{'yes' if p['rank_fix_55f4500_is_ancestor'] else 'no'} | "
          f"{'yes' if p['missingness_fix_42af2cd_is_ancestor'] else 'no'} |")
    A("")
    A("## 2. Classification — two independent axes")
    A("")
    A("| WS | title | Axis 1 — feature-design integrity | Axis 2 — decision validity | valid decision commit |")
    A("|---|---|---|---|---|")
    for ws in WS:
        e = W[ws]
        A(f"| **{ws}** | {WS[ws]['title']} | `{e['axis1_feature_design_integrity']}` | "
          f"`{e['axis2_decision_validity']}` | "
          f"`{e['commit_containing_the_valid_decision_result']}` |")
    A("")
    A("## 3. Independent-check matrix")
    A("")
    A("| WS | rank/cond checked | per fold | missingness checked | gate per fold | matched K0 | corrected rerun |")
    A("|---|---|---|---|---|---|---|")
    for ws in WS:
        e = W[ws]
        def f(x):
            return {True: "yes", False: "**no**"}.get(x, str(x))
        A(f"| **{ws}** | {f(e['rank_and_conditioning_independently_checked'])} | "
          f"{f(e['rank_check_ran_per_fold'])} | {f(e['missingness_independently_checked'])} | "
          f"{f(e['gate_checks_ran_per_fold'])} | {f(e['matched_k0_present'])} | "
          f"{f(e['corrected_rerun_supersedes_original'])} |")
    A("")
    A("## 4. What the current gate actually says")
    A("")
    A("| WS | arms/stages | audits | blocked | blocking kinds | worst condition | rank deficient |")
    A("|---|---|---|---|---|---|---|")
    for ws in WS:
        e = W[ws]
        fa = e["full_audits"]
        blocks = {k: v for k, v in (fa.get("per_arm") or {}).items()}
        for k in ("stage1", "stage2"):
            if fa.get(k):
                blocks[k] = fa[k]
        if not blocks:
            A(f"| **{ws}** | — | — | — | *no design fitted* | — | — |")
            continue
        n = sum(b["summary"]["n_audits"] for b in blocks.values())
        nb = sum(b["summary"]["n_blocked"] for b in blocks.values())
        kinds = sorted({k for b in blocks.values() for k in b["summary"]["blocking_kinds"]})
        cond = max(b["summary"]["worst_condition_number"] for b in blocks.values())
        rd = any(b["summary"]["any_rank_deficient"] for b in blocks.values())
        A(f"| **{ws}** | {len(blocks)} | {n} | {nb} | "
          f"{', '.join('`%s`' % k for k in kinds) if kinds else 'none'} | {cond:.4g} | "
          f"{'**yes**' if rd else 'no'} |")
    A("")
    A("## 5. Per-workstream detail")
    for ws in WS:
        e = W[ws]
        A("")
        A(f"### {ws} — {WS[ws]['title']}")
        A("")
        A(f"- **Result commit:** `{e['original_result_commit']}`")
        g = e["gate_blob_used_during_execution"]
        A(f"- **Gate blob during execution:** `{g['blob']}` "
          f"(pre-fix: {g['is_the_prefix_blob']}, inherited from {g['inherited_from']})")
        r = e["retrospective_audit_receipt"]
        A(f"- **Retrospective receipt:** `{r['path']}`, block sha256 `{r['audit_block_sha256']}`")
        A(f"- **Corrected-rerun commit:** {e['corrected_rerun_commit']}")
        A(f"- **Supporting artifact:** `{e['exact_supporting_artifact']}`")
        k = e["matched_k0_or_comparison_parity_status"]
        A(f"- **Matched K0 / parity:** {k['matched_k0_present']} — {k['citation']}")
        A(f"- **Comparison-parity receipt:** {k['comparison_parity_receipt']}")
        A("")
        A(f"**Axis 1 — `{e['axis1_feature_design_integrity']}`.** {e['axis1_rationale']}")
        A("")
        A(f"**Axis 2 — `{e['axis2_decision_validity']}`.** {e['axis2_rationale']}")
        A("")
        A(f"**Published decision result still valid:** {e['published_decision_result_still_valid']}")
        A("")
        A(f"**Rank / conditioning independently checked:** "
          f"{e['rank_and_conditioning_independently_checked']} — {e['rank_check_citation']}")
        if e.get("rank_check_per_fold_note"):
            A("")
            A(f"**Rank check per fold:** {e['rank_check_ran_per_fold']} — "
              f"{e['rank_check_per_fold_note']}")
        A("")
        A(f"**Missingness independently checked:** {e['missingness_independently_checked']} — "
          f"{e['missingness_check_citation']}")
        A("")
        A(f"**Gate checks ran per fold:** {e['gate_checks_ran_per_fold']} — "
          f"{e['gate_per_fold_citation']}")
        A("")
        A(f"**Result changed by a corrected rerun:** "
          f"{e['any_reported_result_changed_by_corrected_rerun']} — {e['result_change_detail']}")
        A("")
        A(f"**Acceptance gate:** passes = {e['acceptance_gate']['passes']}"
          + ("" if e["acceptance_gate"]["passes"]
             else f", missing {e['acceptance_gate']['missing_fields']}"))
    A("")
    A("## 6. Designs the current gate blocks")
    A("")
    for ws in WS:
        e = W[ws]
        fa = e["full_audits"]
        blocks = {k: v for k, v in (fa.get("per_arm") or {}).items()}
        for k in ("stage1", "stage2"):
            if fa.get(k):
                blocks[k] = fa[k]
        rows = [(arm, b) for arm, b in blocks.items() if b["summary"]["n_blocked"]]
        if not rows:
            continue
        for arm, b in rows:
            A(f"- **{ws} / {arm}** — {b['summary']['n_blocked']} of "
              f"{b['summary']['n_audits']} audits blocked, kinds "
              f"{b['summary']['blocking_kinds']}; labels "
              f"{b['summary']['blocked_labels'][:6]}")
    A("")
    A("Plus the following, which are NOT designs any workstream believed, but are recorded "
      "because the current gate blocks them:")
    A("")
    A("- **ws2 / raw P2 inputs before imputation** — `missingness_encodes_outcome` on "
      "`offensive_involvement_proxy`, `trailing_minutes_share` and `role_change`, 8,278 nulls "
      "each, zero off-diagonal against `did_appear`. These are the inputs `build_constructions()` "
      "imputes to 0.0 before the gate ever sees the matrix.")
    A("- **ws3 / stage-1 and stage-2 AS DECLARED** — rejected by ws3 itself before any fit.")
    A("")
    A("## 7. A blind spot the strengthened gate still has")
    A("")
    A("The `missingness_encodes_outcome` and `missingness_informative` checks read `isna()`. They "
      "therefore see nothing once a null has been imputed **before** `audit()` is called. ws2 is "
      "the worked example, measured here rather than asserted:")
    A("")
    lz = (W["ws2"].get("supplementary_probes") or {}).get("imputed_zero_encodes_non_appearance")
    if lz:
        A("| ws2 feature | zeros | zero & non-appearing | **non-zero & non-appearing** | "
          "non-zero ⇒ did_appear | corr(value, did_appear) |")
        A("|---|---|---|---|---|---|")
        for c, r in lz["per_feature"].items():
            A(f"| `{c}` | {r['n_zero']:,} | {r['zero_and_non_appearing']:,} | "
              f"**{r['NONZERO_AND_NON_APPEARING']:,}** | "
              f"{'**yes**' if r['nonzero_implies_did_appear'] else 'no'} | "
              f"{r['corr_value_with_did_appear']:+.4f} |")
        A("")
        A(f"{lz['verdict']}")
        A("")
    A("The three raw inputs block on `missingness_encodes_outcome` (8,278 nulls, zero "
      "off-diagonal). After `.fillna(0.0)` the design has no nulls at all, every fold passes, and "
      "the laundered indicator survives as a value. Neither the value-based checks nor the "
      "missingness checks can reach it. The structural fix is the one ws1 adopted: require the "
      "operational design to be fully populated so that imputation is a no-op, and raise "
      "otherwise (run_ws1.py:353-387). Recommend the gate grow an optional "
      "`outcome_mask`-against-VALUES check, or that callers be required to pass the "
      "pre-imputation frame.")
    A("")
    A("## 8. Limitations")
    A("")
    A("- Fold-level audits are drawn from the **intrinsic** training track, which contains only "
      "appearers. `missingness_encodes_outcome` can therefore never fire on a training fold in "
      "this programme; it is testable only on the operational prediction frame, which this audit "
      "audits separately for every arm.")
    A("- ws6 committed no feature parquet, so its fit frame was rebuilt from the same upstream "
      "artifacts its script reads (`turnover_targets_v1`, `turnover_p2_v1`, `turnover_p1_v1`, "
      "`prediction_contract_v5`) at the result commit. Row count and column semantics match the "
      "script; the reconstruction is faithful but is a rebuild, not a replay of a stored matrix.")
    A("- Axis-2 judgements about comparison parity, universes and evaluation rows are read off "
      "the workstreams' own committed artifacts. Where no parity receipt exists this report says "
      "so rather than inferring one (ws6).")
    A("- No model was refitted for selection and no decision result was recomputed, so this audit "
      "cannot say what ws2's preserved player-level positive would become after a leak-free "
      "rebuild — only that it is not established as published.")
    A("")
    A("## 9. Reproducing this audit")
    A("")
    A("```")
    A("cd .claude/worktrees/player-model-program")
    A("python experiments/player_program/discovery_wave_1/retrospective_gate_audit.py")
    A("```")
    A("")
    A("The script imports the gate from the coordinator worktree, reads every feature and "
      "prediction parquet from the agent worktrees read-only, and rewrites both output files.")
    A("")
    (HERE / "RETROSPECTIVE_GATE_AUDIT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------- #
# driver
# ---------------------------------------------------------------------------------------- #
AUDITORS = {"ws1": audit_ws1, "ws2": audit_ws2, "ws3": audit_ws3, "ws4": audit_ws4,
            "ws5": audit_ws5, "ws6": audit_ws6, "ws7": audit_ws7, "ws8": audit_ws8}


def main() -> int:
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    prov = verify_provenance()
    print("ancestry/blob verification:", json.dumps(prov["verdict"], indent=2))

    results: dict = {}
    for ws, fn in AUDITORS.items():
        print(f"--- {ws} ({WS[ws]['title']}) ---", flush=True)
        try:
            results[ws] = fn()
        except Exception:
            results[ws] = {"reconstructed": False, "ERROR": traceback.format_exc()}
            print(results[ws]["ERROR"])
            continue
        r = results[ws]
        blocks = dict(r.get("per_arm") or {})
        for k in ("stage1", "stage2", "declared_designs_rejected_before_fitting"):
            if k in r:
                blocks[k] = r[k]
        if blocks:
            for arm, blk in blocks.items():
                s = blk["summary"]
                print(f"  {arm:38s} audits={s['n_audits']:3d} blocked={s['n_blocked']:3d} "
                      f"rank_deficient={s['any_rank_deficient']} "
                      f"worst_cond={s['worst_condition_number']:.4g} "
                      f"kinds={s['blocking_kinds']}")
        else:
            print(f"  no feature design: {r.get('reason_not_reconstructed')}")
        for k in ("raw_p2_inputs_before_imputation", "raw_columns_before_imputation",
                  "raw_feature_frame_with_outcome_mask", "pooled_six_proxy_raw_matrix"):
            if k in r:
                a = r[k]
                print(f"  [{k}] passed={a['passed']} blocking={a['blocking_kinds']} "
                      f"| {a['missingness']['outcome_associated_missingness_verdict']}")

    import hashlib
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = {"schema": "retrospective_gate_audit/2",
           "executed_utc": started,
           "spec_version": "v3 (original brief + two-axis extension + acceptance gate)",
           "lane": "AUDIT ONLY -- no model was refitted for selection, no feature changed, "
                   "no decision result recomputed",
           "audit_script": "experiments/player_program/discovery_wave_1/"
                           "retrospective_gate_audit.py",
           "audit_script_sha256": script_sha,
           "provenance_verification": prov,
           "workstreams": {ws: {**WS[ws], **assemble(ws, results[ws], prov)} for ws in WS}}
    out["acceptance_gate_summary"] = {
        ws: out["workstreams"][ws]["acceptance_gate"]["passes"] for ws in WS}
    p = HERE / "RETROSPECTIVE_GATE_AUDIT.json"
    p.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    json_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    write_markdown(out, json_sha)

    print("\n=== CLASSIFICATION ===")
    for ws in WS:
        e = out["workstreams"][ws]
        print(f"{ws}  axis1={e['axis1_feature_design_integrity']:38s} "
              f"axis2={e['axis2_decision_validity']:32s} "
              f"accept={e['acceptance_gate']['passes']} "
              f"valid_commit={e['commit_containing_the_valid_decision_result'][:9]}")
    print(f"\nwrote RETROSPECTIVE_GATE_AUDIT.json (sha256 {json_sha})")
    print("wrote RETROSPECTIVE_GATE_AUDIT.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
