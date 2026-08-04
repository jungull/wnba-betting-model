#!/usr/bin/env python3
"""run_ws1.py -- DISCOVERY workstream `ws1_repaired_projected_role`.

HYPOTHESIS (frozen card, discovery_wave_1/HYPOTHESIS_LEDGER.json):
    turnover rate changes most when a player occupies a substantially DIFFERENT offensive role
    than normal, not simply because the role is large.

REPAIR OF THE PRIOR ARM E/I DEFECT
    `proj_minutes_share` and `proj_off_poss_share` are ALGEBRAICALLY IDENTICAL under the v1
    exposure mapping (projected possessions = pace x minutes / 40).  Verified here:
    max |difference| = 5.6e-17 over all 35,629 candidate rows.  Only the minutes share is used.
    `proj_off_poss_share` is never read.

ESTIMATOR (mirrors experiments/player_program/run_turnover_p2.py exactly)
    Poisson ridge (lambda 10, intercept unpenalised, IRLS with step-halving), imported --
    not re-implemented -- from run_turnover_p2 so the incumbent comparison is estimator-identical.
    offset = log(exposure) + log(D_ewma_shrunk)  =>  beta = 0 reproduces frozen Arm D exactly.
    Walk-forward by season; standardisation uses TRAINING-FOLD statistics only.

LANE
    DISCOVERY / development folds only.  Nothing here may replace Arm D.  No canonical artifact,
    no shared contract and no arm_registry.jsonl entry is written by this script.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent                 # .../discovery_wave_1/ws1
PP = HERE.parents[1]                                   # .../experiments/player_program
ROOT = PP.parents[1]                                   # repo root
sys.path.insert(0, str(PP))
sys.path.insert(0, str(ROOT))

import feature_gate                                                             # noqa: E402
from feature_gate import FeatureGateFailure                                      # noqa: E402,F401
from evalharness.compare import cluster_bootstrap_ci                             # noqa: E402
from run_turnover_p2 import poisson_ridge, _pois_dev                             # noqa: E402
from register_turnover_p2 import RIDGE_LAMBDA, MIN_TRAIN_ROWS, INVOLVE_ALPHA     # noqa: E402

# --------------------------------------------------------------------------------------------- #
# PREREGISTRATION -- every tunable is a module constant fixed before the first fit.
# --------------------------------------------------------------------------------------------- #
MATERIAL_EXPANSION_LO = 0.05     # role expansion (share points) at which "material" begins
MATERIAL_EXPANSION_HI = 0.10     # ... and at which the bounded ramp saturates
RANK_TOL = 1e-8                  # relative singular-value tolerance for the design-rank check
COND_MAX = 1e6                   # condition-number ceiling for an identified design

BASE = ["proj_minutes_share", "trailing_minutes_share", "role_change",
        "rotation_rank_change", "expanded_role_bounded"]

# The frozen card lists projected share, trailing share AND their difference.  Those three are an
# EXACT rank-2 system (role_change == proj - trailing by construction), so the literal five-feature
# design is singular.  feature_gate.audit is pairwise and does not see it; the design is repaired
# here (not the gate) by dropping the redundant third coordinate.  The literal set is still fitted,
# flagged, and reported as a diagnostic because documenting an unidentified design is the whole
# reason this workstream exists.
ARMS = {
    # -- recalibration control (coordinator amendment) --------------------------------------- #
    # Every Poisson-ridge arm here carries an UNPENALISED intercept that frozen Arm D does not.
    # Free recalibration alone is worth roughly the size of the effects being hunted, so K0 -- zero
    # features, identical pipeline, identical folds, identical offset -- is the honest baseline.
    # An arm that beats D but not K0 has demonstrated recalibration, not mechanism.
    "K0_intercept_only": {
        "features": [],
        "role": "CONTROL: intercept-only recalibration of the frozen Arm D offset. Any arm that "
                "does not beat K0 has added nothing beyond a free level shift.",
        "identified": True, "diagnostic_only": False},
    # -- primary --------------------------------------------------------------------------- #
    "L1_linear": {
        "features": ["proj_minutes_share", "role_change", "rotation_rank_change",
                     "expanded_role_bounded"],
        "role": "PRIMARY linear arm: role level (projected share) + role change + rank change "
                "+ bounded material-expansion ramp",
        "identified": True, "diagnostic_only": False},
    "N1_split": {
        "features": ["proj_minutes_share", "role_change_pos", "role_change_neg",
                     "rotation_rank_change", "expanded_role_bounded"],
        "role": "PRIMARY bounded nonlinear arm: the ONE preregistered nonlinear form -- "
                "role_change replaced by its positive/negative hinge split",
        "identified": True, "diagnostic_only": False},
    # -- level-vs-change decomposition (the actual hypothesis test) -------------------------- #
    "D0_level_only": {
        "features": ["proj_minutes_share"],
        "role": "role LEVEL alone -- 'the role is large'",
        "identified": True, "diagnostic_only": False},
    "D0_change_only": {
        "features": ["role_change", "rotation_rank_change", "expanded_role_bounded"],
        "role": "role CHANGE alone -- 'the role is DIFFERENT than normal'",
        "identified": True, "diagnostic_only": False},
    # -- basis sensitivity: same column span as L1, different ridge parameterisation --------- #
    "S1_trailing_basis": {
        "features": ["trailing_minutes_share", "role_change", "rotation_rank_change",
                     "expanded_role_bounded"],
        "role": "same 4-D span as L1 with the NORMAL role as the level coordinate; a coefficient "
                "conclusion that flips between L1 and S1 is a parameterisation artefact",
        "identified": True, "diagnostic_only": False},
    # -- deliberately unidentified, reported not believed ------------------------------------ #
    "X_literal_card_set": {
        "features": BASE,
        "role": "the literal five-feature card set; EXACTLY rank deficient (role_change == "
                "proj - trailing). Ridge returns a finite fit anyway. Reported as evidence that "
                "the pairwise gate does not catch a three-term dependency. NOT a scientific result.",
        "identified": False, "diagnostic_only": True},
}
PRIMARY = ["L1_linear", "N1_split"]

INPUTS = {
    "intrinsic": PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet",
    "operational": PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet",
    "features": PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet",
    "team_recon": PP / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet",
    "contract": ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
    "master_player": ROOT / "data/masters/master_player.parquet",
}


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def design_rank_report(df: pd.DataFrame, names: list[str]) -> dict:
    """Multivariate identifiability check.

    feature_gate.audit is PAIRWISE.  It cannot see `c = a - b`.  This is an independent
    diagnostic run alongside (never instead of) the mandatory gate call; the gate itself is
    untouched.
    """
    if len(names) == 0:                      # intercept-only control: nothing to be collinear with
        return {"checked": True, "n_complete_rows": int(len(df)), "n_features": 0,
                "singular_values": [], "numerical_rank": 0, "full_rank": True,
                "condition_number": 1.0, "condition_ok": True,
                "note": "zero-feature design is trivially identified"}
    X = df[names].to_numpy(float)
    m = np.all(np.isfinite(X), axis=1)
    Xc = X[m]
    if len(Xc) < 10:
        return {"checked": False, "n_complete_rows": int(m.sum()), "n_features": len(names),
                "singular_values": [], "numerical_rank": 0, "full_rank": False,
                "condition_number": float("inf"), "condition_ok": False,
                "note": "insufficient complete rows to assess rank"}
    sd = Xc.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Z = (Xc - Xc.mean(0)) / sd
    sv = np.linalg.svd(Z, compute_uv=False)
    rank = int((sv > RANK_TOL * sv.max()).sum())
    cond = float(sv.max() / sv.min()) if sv.min() > 0 else float("inf")
    return {"checked": True, "n_complete_rows": int(m.sum()), "n_features": len(names),
            "singular_values": [float(x) for x in np.round(sv, 8)],
            "numerical_rank": rank, "full_rank": bool(rank == len(names)),
            "condition_number": cond, "condition_ok": bool(cond <= COND_MAX),
            "note": "exact rank deficiency means ridge chooses a point in a flat direction; the "
                    "coefficients are then a property of the penalty, not of the data"}


LEAKING_P2_COLUMNS = ["trailing_minutes_share", "trailing_rotation_rank", "role_change",
                      "offensive_involvement_proxy", "displaced_involvement", "_prior_support"]


def build_trailing_role_state(C: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the trailing-role signal so state is read for EVERY row of `universe`.

    THE DEFECT BEING REPAIRED (coordinator amendment, verified here):
        turnover_p2_v1's trailing columns were produced by iterating the REALISED box score
        (master_player filtered to minutes.notna()) and left-merging onto the candidate universe.
        A candidate who did not appear never generated a row, so the column is NULL for exactly the
        non-appearers -- verified crosstab 27,351 non-null / 8,278 null with ZERO off-diagonal
        against `did_appear`.  The null mask IS a post-cutoff outcome indicator, and any imputation
        of it encodes "did not appear" into the design.

    THE REPAIR
        Same EWMA machine (alpha = INVOLVE_ALPHA = 0.10, update new = (1-alpha)*old + value, state
        snapshotted BEFORE the day's games are consumed, so strictly prior games only).  The only
        change is WHERE state is read: the forward pass now emits a row for every universe member
        on its own game date, whether or not that player later appeared.  The box score is used
        only to UPDATE state, never to decide who gets a row.

    The canonical artifact is not modified; this writes its own copy under the ws1 directory.
    """
    box = pd.read_parquet(INPUTS["master_player"],
                          columns=["game_id", "team_id", "player_id", "minutes"])
    box["game_id"] = box["game_id"].astype(str)
    box["team_id"] = box["team_id"].astype("int64")
    box["player_id"] = box["player_id"].astype("int64")
    box = box[box["minutes"].notna()].merge(C[["game_id", "game_date"]], on="game_id", how="left")
    box = box[box["game_date"].notna()].sort_values(["game_date", "game_id"])

    ewm_min: dict[int, float] = {}
    ewm_tm: dict[int, float] = {}
    uni_by_date = {d: sub for d, sub in universe.groupby("game_date", sort=False)}
    box_by_date = {d: sub for d, sub in box.groupby("game_date", sort=False)}
    rows = []
    for d in sorted(set(uni_by_date) | set(box_by_date)):
        # ---- SNAPSHOT: read state for every universe member on this date, appearers or not ---- #
        for r in uni_by_date.get(d, pd.DataFrame()).itertuples(index=False):
            tm = ewm_tm.get(r.team_id, 0.0)
            pm = ewm_min.get(r.player_id, 0.0)
            rows.append({"game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                         "trailing_minutes_share_raw": (pm / tm) if tm > 0 else np.nan,
                         "team_prior_support": tm, "player_prior_support": pm})
        # ---- CONSUME: only now do this date's realised games update the EWMA state ------------ #
        day = box_by_date.get(d)
        if day is None:
            continue
        for r in day.itertuples(index=False):
            ewm_min[r.player_id] = ((1 - INVOLVE_ALPHA) * ewm_min.get(r.player_id, 0.0)
                                    + float(r.minutes or 0))
        for t, sub in day.groupby("team_id"):
            ewm_tm[t] = (1 - INVOLVE_ALPHA) * ewm_tm.get(t, 0.0) + float(sub["minutes"].sum())
    return pd.DataFrame(rows)


def build_features() -> tuple[pd.DataFrame, dict]:
    """Assemble the WS1 feature frame.

    Projected-role columns are taken from the frozen P2 artifact (they are clean: zero nulls,
    built from pre-cutoff projections).  The trailing-role columns are REBUILT here -- the P2
    versions are dropped outright, never imputed.
    """
    F = pd.read_parquet(INPUTS["features"])
    ident = float(np.nanmax(np.abs(F["proj_minutes_share"] - F["proj_off_poss_share"])))
    C = pd.read_parquet(INPUTS["contract"],
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    # quantify the defect in the source artifact before discarding it
    O = pd.read_parquet(INPUTS["operational"], columns=["game_id", "team_id", "player_id",
                                                        "did_appear"])
    chk = O.merge(F[["game_id", "team_id", "player_id"] + LEAKING_P2_COLUMNS[:3]],
                  on=["game_id", "team_id", "player_id"], how="left")
    leak_ev = {}
    for c in LEAKING_P2_COLUMNS[:3]:
        ct = pd.crosstab(chk[c].isna(), chk["did_appear"])
        leak_ev[c] = {"null_and_did_not_appear": int(ct.get(False, {}).get(True, 0)),
                      "nonnull_and_appeared": int(ct.get(True, {}).get(False, 0)),
                      "null_but_appeared": int(ct.get(True, {}).get(True, 0)),
                      "nonnull_but_did_not_appear": int(ct.get(False, {}).get(False, 0))}
    leak_ev = {c: {"n_null": int(chk[c].isna().sum()),
                   "n_nonnull": int(chk[c].notna().sum()),
                   "null_mask_equals_not_did_appear": bool(
                       (chk[c].isna() == ~chk["did_appear"].astype(bool)).all()),
                   "off_diagonal_rows": int((chk[c].isna() != ~chk["did_appear"].astype(bool)).sum())}
               for c in LEAKING_P2_COLUMNS[:3]}

    F = F.drop(columns=[c for c in LEAKING_P2_COLUMNS if c in F.columns]).copy()

    # universe for the rebuild: candidate rows PLUS intrinsic rows outside the candidate universe
    I = pd.read_parquet(INPUTS["intrinsic"], columns=["game_id", "team_id", "player_id"])
    uni = pd.concat([F[["game_id", "team_id", "player_id"]], I], ignore_index=True) \
            .drop_duplicates(["game_id", "team_id", "player_id"])
    uni = uni.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    uni = uni[uni["game_date"].notna()]

    T = build_trailing_role_state(C, uni)
    T.to_parquet(HERE / "ws1_trailing_role_state_v1.parquet", index=False)

    F = F.merge(T, on=["game_id", "team_id", "player_id"], how="left")
    # Residual missingness is a TEAM-GAME property (the team has no prior history at all), never a
    # player-level outcome.  Neutralise it using projection-only information: no prior history =>
    # no evidence of role change.  This cannot encode appearance because every candidate on such a
    # team-game is treated identically.
    no_hist = F["trailing_minutes_share_raw"].isna()
    F["trailing_history_missing"] = no_hist
    F["trailing_minutes_share"] = F["trailing_minutes_share_raw"].where(
        ~no_hist, F["proj_minutes_share"])
    F["trailing_rotation_rank"] = F.groupby(["game_id", "team_id"])["trailing_minutes_share"].rank(
        ascending=False, method="first")
    F["role_change"] = F["proj_minutes_share"] - F["trailing_minutes_share"]
    F["rotation_rank_change"] = F["trailing_rotation_rank"] - F["proj_rotation_rank"]
    F["expanded_role_bounded"] = np.clip(
        (F["role_change"] - MATERIAL_EXPANSION_LO) / (MATERIAL_EXPANSION_HI - MATERIAL_EXPANSION_LO),
        0.0, 1.0)
    F["role_change_pos"] = np.clip(F["role_change"], 0.0, None)
    F["role_change_neg"] = np.clip(F["role_change"], None, 0.0)
    prov = {
        "source": str(INPUTS["features"].relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": _sha(INPUTS["features"]),
        "source_unmodified": True,
        "p2_trailing_columns_DISCARDED": {
            "columns": LEAKING_P2_COLUMNS,
            "defect": "built by iterating the realised box score and left-merging onto the "
                      "candidate universe, so the null mask is an EXACT did_appear indicator -- "
                      "post-cutoff outcome information",
            "evidence": leak_ev,
            "action": "dropped outright and rebuilt; never imputed"},
        "trailing_role_rebuild": {
            "artifact": "ws1_trailing_role_state_v1.parquet",
            "machine": f"EWMA alpha={INVOLVE_ALPHA}, new = (1-alpha)*old + value, state "
                       "snapshotted BEFORE the day's games are consumed (strictly prior games)",
            "change_vs_p2": "state is READ for every universe member on its own game date, "
                            "appearer or not; the box score only UPDATES state",
            "universe": "Tier A candidate rows UNION intrinsic realised-participant rows"},
        "share_identity_check": {
            "claim": "proj_minutes_share and proj_off_poss_share are algebraically identical",
            "max_abs_difference": ident, "identical": bool(ident < 1e-12),
            "consequence": "proj_off_poss_share is NEVER read by this workstream"},
        "derived_columns": {
            "rotation_rank_change": "trailing_rotation_rank - proj_rotation_rank; POSITIVE = the "
                                    "player is projected further UP the rotation than normal",
            "expanded_role_bounded": f"clip((role_change - {MATERIAL_EXPANSION_LO}) / "
                                     f"({MATERIAL_EXPANSION_HI} - {MATERIAL_EXPANSION_LO}), 0, 1); "
                                     "bounded ramp, zero unless the role expands materially",
            "role_change_pos": "max(role_change, 0)  [nonlinear arm only]",
            "role_change_neg": "min(role_change, 0)  [nonlinear arm only]"},
        "no_new_leakage_surface": "all derived columns are pointwise functions of P2 columns whose "
                                  "chronological isolation was already validated",
    }
    return F, prov


def main() -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    F, feat_prov = build_features()

    P1I = pd.read_parquet(INPUTS["intrinsic"])
    if "exposure" not in P1I.columns:
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    P1O = pd.read_parquet(INPUTS["operational"])
    TM = pd.read_parquet(INPUTS["team_recon"])
    C = pd.read_parquet(INPUTS["contract"],
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    key = ["game_id", "team_id", "player_id"]
    allfeat = sorted({f for a in ARMS.values() for f in a["features"]})
    FF = F[key + allfeat]

    I = P1I.merge(FF, on=key, how="left")
    O = P1O.merge(FF, on=key, how="left")
    merge_cov = {
        "intrinsic": {"rows": int(len(I)),
                      "rows_without_candidate_features": int(I["proj_minutes_share"].isna().sum()),
                      "note": "realised participants absent from the Tier A candidate universe; "
                              "their standardised features are set to the training mean (0), so "
                              "they receive the Arm D prediction times exp(intercept)"},
        "operational": {"rows": int(len(O)),
                        "rows_without_candidate_features": int(O["proj_minutes_share"].isna().sum())},
    }
    for nm, d in (("intrinsic", I), ("operational", O)):
        merge_cov[nm]["feature_null_fraction"] = {
            c: round(float(d[c].isna().mean()), 5) for c in allfeat}

    # ------------------------------------------------------- LEAKAGE GUARD (fail closed) ------ #
    # The P2 defect was invisible because a null mask carried outcome information and imputation
    # laundered it into the design.  The guard is therefore structural, not statistical: on the
    # operational track every feature must be FULLY POPULATED, so there is no mask to leak and
    # fillna is a no-op.  A feature that cannot be computed without knowing the outcome cannot be
    # used, and this raises rather than silently imputing.
    did = O["did_appear"].astype(bool).to_numpy()
    guard = {"track": "operational", "n_rows": int(len(O)),
             "n_did_appear": int(did.sum()), "n_did_not_appear": int((~did).sum()),
             "features": {}}
    violations = []
    for c in allfeat:
        v = O[c]
        nmask = v.isna().to_numpy()
        rec = {"n_null": int(nmask.sum()),
               "null_mask_off_diagonal_vs_did_appear": int((nmask != ~did).sum())}
        if nmask.sum():
            rec["null_mask_equals_not_did_appear"] = bool((nmask == ~did).all())
            violations.append(c)
        vv = v.to_numpy(float)
        m = np.isfinite(vv)
        rec["corr_with_did_appear"] = (float(np.corrcoef(vv[m], did[m].astype(float))[0, 1])
                                       if m.sum() > 10 and np.std(vv[m]) > 0 else None)
        rec["mean_if_appeared"] = float(np.nanmean(vv[did]))
        rec["mean_if_not"] = float(np.nanmean(vv[~did]))
        guard["features"][c] = rec
    guard["all_features_fully_populated"] = not violations
    guard["violations"] = violations
    if violations:
        raise SystemExit(
            "LEAKAGE GUARD: operational features still contain nulls, so imputing them would "
            f"encode a post-cutoff mask: {violations}")
    guard["note"] = ("zero nulls on the operational track means no missingness indicator exists "
                     "and fillna(0) is a no-op there; a non-zero corr_with_did_appear is legitimate "
                     "signal only because these values are computable strictly before the cutoff")

    # ------------------------------------------------------------------ identifiability ------ #
    ident_report = {a: design_rank_report(F, spec["features"]) for a, spec in ARMS.items()}
    for a in PRIMARY:
        r = ident_report[a]
        if not (r["full_rank"] and r["condition_ok"]):
            raise SystemExit(f"design {a} is not identified: {r}")

    # ------------------------------------------------------------------ mandatory gate ------- #
    train_src = I[I["exposure"] > 0].reset_index(drop=True)
    seasons = sorted(int(s) for s in pd.unique(pd.concat([I["season"], O["season"]])))
    gate_audits: dict[str, dict] = {}
    for a, spec in ARMS.items():
        feats = spec["features"]
        per = {}
        for s in seasons:
            tr = train_src[train_src["season"] < s]
            if len(tr) < MIN_TRAIN_ROWS:
                per[str(s)] = {"skipped": True, "reason": "fold falls back to Arm D (beta=0)",
                               "train_rows": int(len(tr))}
                continue
            off = (np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
            # MANDATORY: audit the exact training matrix, offset and target of THIS fit.
            per[str(s)] = feature_gate.audit(
                tr, feats, offset=off, target=tr["turnovers"].to_numpy(float),
                test_df=O if s in set(O["season"]) else I)
        off_all = (np.log(np.clip(train_src["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(train_src["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
        pooled = feature_gate.audit(train_src, feats, offset=off_all,
                                    target=train_src["turnovers"].to_numpy(float), test_df=O)
        gate_audits[a] = {
            "arm": a, "features": feats,
            "gate_module": "experiments/player_program/feature_gate.py (unmodified)",
            "gate_passed_all_folds": bool(pooled["passed"]
                                          and all(v.get("passed", True) for v in per.values())),
            "pooled_training_audit": pooled, "per_fold_audits": per,
            "independent_design_rank_check": ident_report[a],
            "gate_limitation_observed": (
                "feature_gate.audit is pairwise and returned PASSED for a design whose numerical "
                "rank is %d of %d" % (ident_report[a]["numerical_rank"], len(feats))
            ) if not ident_report[a]["full_rank"] else None,
        }
        (HERE / f"gate_audit_{a}.json").write_text(
            json.dumps(gate_audits[a], indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------ fit ------------------ #
    def fit_predict(df: pd.DataFrame):
        out = {a: np.full(len(df), np.nan) for a in ARMS}
        coefs: dict[int, dict] = {}
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            te_idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[te_idx]
            base = te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float)
            if len(tr) < MIN_TRAIN_ROWS:
                for a in ARMS:
                    out[a][te_idx] = base
                coefs[int(s)] = {"fallback_to_D": True, "train_rows": int(len(tr))}
                continue
            coefs[int(s)] = {"fallback_to_D": False, "train_rows": int(len(tr)),
                             "test_rows": int(len(te))}
            otr = (np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
            ote = (np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(te["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
            for a, spec in ARMS.items():
                feats = spec["features"]
                mu_tr = tr[feats].mean()
                sd_tr = tr[feats].std().replace(0, 1.0)
                Xtr = ((tr[feats] - mu_tr) / sd_tr).fillna(0.0).to_numpy(float)
                Xte = ((te[feats] - mu_tr) / sd_tr).fillna(0.0).to_numpy(float)
                b, conv = poisson_ridge(Xtr, tr["turnovers"].to_numpy(float), otr, RIDGE_LAMBDA)
                if not conv:
                    out[a][te_idx] = base
                    coefs[int(s)][a] = {"CONVERGENCE_FAILURE": True, "fell_back_to_D": True}
                    continue
                out[a][te_idx] = np.exp(np.clip(ote + b[0] + Xte @ b[1:], -20, 20))
                coefs[int(s)][a] = dict(zip(["intercept"] + feats, np.round(b, 6).tolist()))
        return out, coefs

    res: dict[str, dict] = {}
    for name, df in (("intrinsic", I), ("operational", O)):
        d = df.reset_index(drop=True).copy()
        preds, coefs = fit_predict(d)
        d["pred_A"] = d["A_league_constant"] * d["exposure"]
        d["pred_D"] = d["D_ewma_shrunk"] * d["exposure"]
        for a in ARMS:
            d[f"pred_{a}"] = preds[a]
        allarms = ["A", "D"] + list(ARMS)

        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in allarms}).reset_index()
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g = g.merge(C[["game_id", "game_date", "season"]], on="game_id", how="left")
        g["y"] = g["player_attributed"].fillna(0)
        gdate = g["game_date"].astype(str).to_numpy()

        blk = {
            "rows": int(len(d)), "team_games": int(len(g)),
            "player": {a: {"deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                           "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                           "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))}
                       for a in allarms},
            "team": {a: {"mae": float(np.mean(np.abs(g[a] - g["y"]))),
                         "rmse": float(np.sqrt(np.mean((g[a] - g["y"]) ** 2))),
                         "bias": float(np.mean(g[a] - g["y"]))} for a in allarms},
            "paired_vs_D": {}, "paired_vs_K0": {},
            "by_season_team_mae": {}, "by_season_paired_vs_D": {}, "by_season_paired_vs_K0": {},
            "coefficients_by_season": coefs,
        }
        for inc, dest in (("D", "paired_vs_D"), ("K0_intercept_only", "paired_vs_K0")):
            for a in list(ARMS) + ["A"]:
                if a == inc:
                    continue
                dv = (np.abs(g[inc] - g["y"]) - np.abs(g[a] - g["y"])).to_numpy(float)
                ci = cluster_bootstrap_ci(dv, g["game_id"].to_numpy())
                cid = cluster_bootstrap_ci(dv, gdate)
                blk[dest][a] = {
                    "convention": f"INCUMBENT({inc}) abs error MINUS CHALLENGER abs error; "
                                  f"POSITIVE = challenger beats {inc}",
                    "mean_mae_reduction": float(dv.mean()),
                    "ci90_game_clustered": [ci["low"], ci["high"]],
                    "ci90_date_clustered_sensitivity": [cid["low"], cid["high"]],
                    "ci_excludes_zero": bool(ci["low"] > 0 or ci["high"] < 0),
                    "improved": int((dv > 0).sum()), "worsened": int((dv < 0).sum()),
                    "tied": int((dv == 0).sum())}
        for s, sub in g.groupby("season"):
            blk["by_season_team_mae"][int(s)] = {a: float(np.mean(np.abs(sub[a] - sub["y"])))
                                                 for a in allarms}
            for inc, dest in (("D", "by_season_paired_vs_D"),
                              ("K0_intercept_only", "by_season_paired_vs_K0")):
                blk[dest][int(s)] = {
                    a: float(np.mean(np.abs(sub[inc] - sub["y"]) - np.abs(sub[a] - sub["y"])))
                    for a in list(ARMS) + ["A"] if a != inc}
        if "did_appear" in d.columns:
            for lab, sub in (("appearing", d[d["did_appear"]]),
                             ("non_appearing", d[~d["did_appear"]])):
                blk[f"player_{lab}"] = {
                    a: {"n": int(len(sub)),
                        "mae": float(np.mean(np.abs(sub["turnovers"] - sub[f"pred_{a}"])))}
                    for a in allarms}
        res[name] = blk
        d.to_parquet(HERE / f"ws1_predictions_{name}.parquet", index=False)

    # ------------------------------------------------------------------ mechanism ------------ #
    # A null on team MAE is only interpretable if we also know whether the MECHANISM exists and
    # how much of the population it can touch.  Two model-free diagnostics plus one targeted
    # subgroup comparison.
    ROLE_BINS = [-np.inf, -0.10, -0.05, -0.02, 0.02, 0.05, 0.10, np.inf]
    mech: dict[str, dict] = {}
    for name in ("intrinsic", "operational"):
        d = pd.read_parquet(HERE / f"ws1_predictions_{name}.parquet")
        sub = d[d["role_change"].notna()].copy()
        sub["_bin"] = pd.cut(sub["role_change"], ROLE_BINS)
        # model-free: observed turnovers vs the frozen Arm D expectation, by role-change bin
        obs_exp = {}
        for b, s in sub.groupby("_bin", observed=True):
            e = float(s["pred_D"].sum())
            obs_exp[str(b)] = {
                "n_rows": int(len(s)), "observed_turnovers": float(s["turnovers"].sum()),
                "expected_under_D": e,
                "observed_over_expected": (float(s["turnovers"].sum()) / e) if e > 0 else None,
                "mean_role_change": float(s["role_change"].mean())}
        # targeted subgroup: rows the bounded material-expansion term can actually touch
        matl = d[d["expanded_role_bounded"].fillna(0.0) > 0]
        e = float(matl["pred_D"].sum())
        seg = {"n_rows": int(len(matl)), "share_of_rows": float(len(matl) / len(d)),
               "observed_turnovers": float(matl["turnovers"].sum()), "expected_under_D": e,
               "observed_over_expected": (float(matl["turnovers"].sum()) / e) if e > 0 else None,
               "player_mae": {a: float(np.mean(np.abs(matl["turnovers"] - matl[f"pred_{a}"])))
                              for a in ["A", "D"] + list(ARMS)}}
        # team-level restricted to team-games that CONTAIN at least one materially expanded role
        d["_matl"] = d["expanded_role_bounded"].fillna(0.0) > 0
        gg = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in ["A", "D"] + list(ARMS)},
            has_matl=("_matl", "any")).reset_index()
        gg = gg.merge(TM[["game_id", "team_id", "player_attributed"]],
                      on=["game_id", "team_id"], how="left")
        gg["y"] = gg["player_attributed"].fillna(0)
        restricted = {}
        for lab, gs in (("team_games_with_material_expansion", gg[gg["has_matl"]]),
                        ("team_games_without", gg[~gg["has_matl"]])):
            blk2 = {"team_games": int(len(gs)),
                    "team_mae": {a: float(np.mean(np.abs(gs[a] - gs["y"])))
                                 for a in ["A", "D"] + list(ARMS)}}
            for inc, dest in (("D", "paired_vs_D"), ("K0_intercept_only", "paired_vs_K0")):
                for a in PRIMARY + ["D0_change_only"]:
                    dv = (np.abs(gs[inc] - gs["y"]) - np.abs(gs[a] - gs["y"])).to_numpy(float)
                    ci = cluster_bootstrap_ci(dv, gs["game_id"].to_numpy())
                    blk2.setdefault(dest, {})[a] = {
                        "mean_mae_reduction": float(dv.mean()),
                        "ci90_game_clustered": [ci["low"], ci["high"]]}
            restricted[lab] = blk2
        mech[name] = {"observed_over_expected_by_role_change_bin": obs_exp,
                      "materially_expanded_role_segment": seg,
                      "team_games_split_by_exposure_to_mechanism": restricted,
                      "reading": "observed_over_expected > 1 means the frozen Arm D rate "
                                 "UNDER-predicts turnovers in that bin"}

    # ----------------------------------------------------- exposure-error attribution -------- #
    # The operational track differs from the intrinsic track ONLY by which exposure is used.  If
    # the role-change features earn their operational gain by correcting the PROJECTED EXPOSURE
    # rather than the turnover RATE, they will predict the exposure error directly.  That is the
    # load-bearing claim of the failure analysis, so it is tested rather than asserted.
    j = (P1I[key + ["exposure"]].rename(columns={"exposure": "realised_exposure"})
         .merge(P1O[key + ["exposure", "did_appear"]].rename(
             columns={"exposure": "projected_exposure"}), on=key, how="inner")
         .merge(FF, on=key, how="left"))
    j["exposure_error"] = j["realised_exposure"] - j["projected_exposure"]
    expo = {"n_rows_in_both_tracks": int(len(j)),
            "mean_exposure_error": float(j["exposure_error"].mean()),
            "sd_exposure_error": float(j["exposure_error"].std())}
    for c in ["role_change", "proj_minutes_share", "trailing_minutes_share",
              "rotation_rank_change", "expanded_role_bounded"]:
        v = j[c].to_numpy(float)
        m = np.isfinite(v) & np.isfinite(j["exposure_error"].to_numpy(float))
        expo[f"corr_{c}_with_exposure_error"] = float(
            np.corrcoef(v[m], j["exposure_error"].to_numpy(float)[m])[0, 1])
    jj = j[j["role_change"].notna()].copy()
    jj["_bin"] = pd.cut(jj["role_change"], ROLE_BINS)
    expo["mean_exposure_error_by_role_change_bin"] = {
        str(b): {"n": int(len(s)), "mean_exposure_error": float(s["exposure_error"].mean()),
                 "mean_projected": float(s["projected_exposure"].mean()),
                 "mean_realised": float(s["realised_exposure"].mean())}
        for b, s in jj.groupby("_bin", observed=True)}
    expo["reading"] = ("a strong monotone gradient here means the role-change features are an "
                       "EXPOSURE-projection correction, not a turnover-RATE effect")

    # ------------------------------------------------------------------ stability ------------ #
    stability = {}
    for track in ("intrinsic", "operational"):
        coefs = res[track]["coefficients_by_season"]
        st = {}
        for a, spec in ARMS.items():
            rows = {}
            for s, blk in coefs.items():
                c = blk.get(a)
                if isinstance(c, dict) and "intercept" in c:
                    rows[int(s)] = c
            if not rows:
                continue
            per_feat = {}
            for f in ["intercept"] + spec["features"]:
                v = np.array([rows[s][f] for s in sorted(rows)], float)
                per_feat[f] = {"by_season": {str(s): float(rows[s][f]) for s in sorted(rows)},
                               "mean": float(v.mean()), "sd": float(v.std(ddof=0)),
                               "sign_consistent": bool(np.all(v > 0) or np.all(v < 0)),
                               "sign": "positive" if np.all(v > 0) else
                                       ("negative" if np.all(v < 0) else "MIXED")}
            st[a] = per_feat
        stability[track] = st

    # ------------------------------------------------------------------ verdict -------------- #
    # Decision rule, applied mechanically to the numbers above.
    #   supports  : a PRIMARY arm beats the K0 recalibration control on operational team MAE with a
    #               90% game-clustered CI excluding zero, and its role-change coefficient is
    #               sign-stable across folds.
    #   falsifies : no primary arm beats K0 in point estimate on either track.
    #   ambiguous : anything else.
    def _verdict() -> dict:
        ev = {}
        for a in PRIMARY:
            op = res["operational"]["paired_vs_K0"][a]
            it = res["intrinsic"]["paired_vs_K0"][a]
            ev[a] = {"operational_vs_K0": op["mean_mae_reduction"],
                     "operational_ci_excludes_zero": op["ci_excludes_zero"],
                     "intrinsic_vs_K0": it["mean_mae_reduction"],
                     "beats_K0_operationally": op["mean_mae_reduction"] > 0,
                     "beats_K0_intrinsically": it["mean_mae_reduction"] > 0}
        wins = [a for a in PRIMARY
                if ev[a]["operational_vs_K0"] > 0 and ev[a]["operational_ci_excludes_zero"]]
        any_point = [a for a in PRIMARY
                     if ev[a]["beats_K0_operationally"] or ev[a]["beats_K0_intrinsically"]]
        v = "supports" if wins else ("falsifies" if not any_point else "ambiguous")
        return {"verdict": v, "rule": "primary arm must beat the K0 recalibration control on "
                                      "operational team MAE with a 90% game-clustered CI "
                                      "excluding zero", "primary_arm_evidence": ev,
                "arms_beating_K0_with_ci_excluding_zero": wins}

    verdict = _verdict()

    out = {
        "schema": "discovery_ws1_results/1",
        "workstream": "ws1_repaired_projected_role",
        "wave": "discovery_wave_1",
        "lane": "DISCOVERY (development folds only) -- may not replace Arm D",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hypothesis": ("turnover rate changes most when a player occupies a substantially "
                       "DIFFERENT offensive role than normal, not simply because the role is large"),
        "sign_convention": "INCUMBENT(D) absolute error MINUS CHALLENGER absolute error; "
                           "POSITIVE = challenger beats D",
        "frozen_incumbent": {"arm": "D_ewma_shrunk", "operational_team_mae": 2.9675,
                             "intrinsic_team_mae": 2.8960},
        "recalibration_control": {
            "arm": "K0_intercept_only",
            "why": "every ridge arm here has an unpenalised intercept that frozen Arm D lacks, so "
                   "free recalibration alone is worth about the size of the effect being hunted",
            "coordinator_reported_operational_team_mae": 2.96419,
            "reproduced_operational_team_mae": res["operational"]["team"]["K0_intercept_only"]["mae"],
            "reproduced_intrinsic_team_mae": res["intrinsic"]["team"]["K0_intercept_only"]["mae"],
            "standard": "vs-K0 is the honest test of whether the FEATURES add anything"},
        "verdict_block": verdict,
        "estimator": {"family": "Poisson ridge (IRLS, step-halving, intercept unpenalised)",
                      "ridge_lambda": RIDGE_LAMBDA, "min_train_rows": MIN_TRAIN_ROWS,
                      "offset": "log(exposure) + log(D_ewma_shrunk); beta=0 reproduces Arm D",
                      "validation": "walk-forward by season; training-fold standardisation only",
                      "implementation": "imported from experiments/player_program/run_turnover_p2.py",
                      "preregistered": True},
        "preregistered_constants": {"MATERIAL_EXPANSION_LO": MATERIAL_EXPANSION_LO,
                                    "MATERIAL_EXPANSION_HI": MATERIAL_EXPANSION_HI,
                                    "RANK_TOL": RANK_TOL, "COND_MAX": COND_MAX},
        "arms": {a: {k: v for k, v in spec.items()} for a, spec in ARMS.items()},
        "primary_arms": PRIMARY,
        "feature_provenance": feat_prov,
        "merge_coverage": merge_cov,
        "leakage_guard": guard,
        "identifiability": ident_report,
        "gate_audit_summary": {
            a: {"passed": gate_audits[a]["gate_passed_all_folds"],
                "n_findings_pooled": len(gate_audits[a]["pooled_training_audit"]["findings"]),
                "blocking": gate_audits[a]["pooled_training_audit"]["blocking"],
                "numerical_rank": ident_report[a]["numerical_rank"],
                "n_features": len(ARMS[a]["features"]),
                "gate_limitation_observed": gate_audits[a]["gate_limitation_observed"],
                "file": f"gate_audit_{a}.json"} for a in ARMS},
        "input_sha256": {k: _sha(v) for k, v in INPUTS.items()},
        "coefficient_stability": stability,
        "mechanism_diagnostics": mech,
        "exposure_error_attribution": expo,
        "results": res,
    }
    (HERE / "WS1_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    for name in ("intrinsic", "operational"):
        r = res[name]
        print(f"\n=== {name} === rows {r['rows']:,}  team-games {r['team_games']:,}")
        print(f"{'arm':20s} {'dev':>9s} {'teamMAE':>8s} {'vs D':>9s} {'ci90(game)':>20s} "
              f"{'vs K0':>9s} {'ci90(game)':>20s}")
        for a in ["A", "D"] + list(ARMS):
            def _f(blk):
                p = blk.get(a)
                if not p:
                    return "", ""
                return (f"{p['mean_mae_reduction']:+.4f}",
                        f"[{p['ci90_game_clustered'][0]:+.4f},{p['ci90_game_clustered'][1]:+.4f}]")
            vd, cd = _f(r["paired_vs_D"])
            vk, ck = _f(r["paired_vs_K0"])
            print(f"{a:20s} {r['player'][a]['deviance']:9.5f} {r['team'][a]['mae']:8.4f} "
                  f"{vd:>9s} {cd:>20s} {vk:>9s} {ck:>20s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
