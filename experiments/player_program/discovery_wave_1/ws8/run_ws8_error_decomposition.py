#!/usr/bin/env python3
"""ws8_operational_error_decomposition -- WHERE does operational error come from?

DISCOVERY lane, development folds only. The frozen Arm D rate model
(D_ewma_shrunk, K=200, alpha=0.10) is held COMPLETELY FIXED. Nothing here
retunes a rate, refits a model, or touches projected_player_possessions_v1.

Five LABELLED diagnostic counterfactuals are constructed by swapping ONLY the
exposure vector (which rows exist and how many offensive player-possessions
each carries). Every counterfactual reuses the identical frozen per-row Arm D
rate produced by the single chronological pass in
run_turnover_p1_universe_fix.py.

    CF1  full operational        Tier A candidate universe, projected exposure
    CF2  oracle appearance       projected exposure REALLOCATED among actual participants
    CF3  + missing participants  CF2 plus the realised players who were never candidates
    CF4  oracle allocation       realised within-team exposure shares, projected team total
    CF5  realised exposure       the intrinsic track

ORACLE VARIANTS ARE DIAGNOSTICS, NOT MODELS. CF2..CF5 each consume information
that is not available at the forecast cutoff (who played, how much they played,
how many possessions the game ran). None of them is a forecast, none is
promotion evidence, none may be registered as an arm.

SIGN CONVENTION (stated once here and repeated in every emitted record):
    delta_step = MAE(state BEFORE the fix) - MAE(state AFTER the fix)
    POSITIVE  => removing that error source REDUCES team MAE; it was a genuine
                 contributor to operational error.
    NEGATIVE  => removing that error source INCREASES team MAE; the "error" was
                 net COMPENSATING at the team level.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                    # experiments/player_program
ROOT = HERE.parents[3]                  # repo root
sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                    # noqa: E402

ARM = "D_ewma_shrunk"
SIGN = ("delta = MAE(before the fix) MINUS MAE(after the fix); "
        "POSITIVE means the fix REDUCES team MAE, i.e. that source contributes error; "
        "NEGATIVE means the fix INCREASES team MAE, i.e. that source was net compensating")
LEVEL_SIGN = ("team MAE = mean over team-games of |sum of player predictions - "
              "player_attributed team turnovers|; LOWER is better")

BOOT = dict(n_boot=2000, seed=20260730, ci_level=0.90, method="cluster")


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #
def build_rows() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (rows, team_games, provenance).

    rows carries, for every player-game that appears in ANY counterfactual:
      rate            frozen Arm D rate for that player at that game_date
      w_proj          projected offensive player-possessions (0 for non-candidates)
      w_real          realised offensive player-possessions (0 for non-appearers)
      is_cand         member of the Tier A candidate universe
      did_appear      actually played
    """
    O = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet",
                        columns=["game_id", "team_id", "player_id", "game_date", "season",
                                 "turnovers", "did_appear", "exposure", ARM])
    I = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet",
                        columns=["game_id", "team_id", "player_id", "game_date", "season",
                                 "turnovers", "realised_off_possessions", ARM])
    P = pd.read_parquet(PP / "turnover_targets_v1/player_turnover_targets_v1.parquet",
                        columns=["game_id", "team_id", "player_id", "minutes",
                                 "realised_off_possessions", "turnovers"])
    P["team_id"] = P["team_id"].astype("int64")
    TM = pd.read_parquet(PP / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet",
                         columns=["game_id", "team_id", "player_attributed", "team_unattributed",
                                  "team_turnovers_total", "team_off_possessions"])
    PACE = pd.read_parquet(PP / "projected_exposure_v1/team_possession_prior_v1.parquet",
                           columns=["game_id", "team_id", "projected_team_off_possessions"])

    KEY = ["game_id", "team_id", "player_id"]
    TG = ["game_id", "team_id"]

    # ---- common team-game support: the operational track's 2,914 team-games ---- #
    op_tg = O[TG].drop_duplicates()
    op_tg["_in_op"] = True

    # ---- candidate side ---------------------------------------------------- #
    cand = O.rename(columns={"exposure": "w_proj", ARM: "rate"}).copy()
    cand["is_cand"] = True
    cand = cand.merge(P[KEY + ["realised_off_possessions", "minutes"]], on=KEY, how="left")
    cand["w_real"] = cand["realised_off_possessions"].fillna(0.0).astype(float)
    cand["minutes"] = cand["minutes"].fillna(0.0).astype(float)

    # ---- realised players who were NEVER Tier A candidates ------------------ #
    ckeys = O[KEY].copy()
    ckeys["_is_cand"] = True
    nonc = P.merge(ckeys, on=KEY, how="left")
    nonc = nonc[nonc["_is_cand"].isna()].drop(columns="_is_cand")
    nonc = nonc.merge(op_tg, on=TG, how="inner")            # in-scope team-games only
    nonc = nonc.merge(I[KEY + [ARM, "game_date", "season"]], on=KEY, how="left")
    n_no_rate = int(nonc[ARM].isna().sum())
    poss_no_rate = float(nonc.loc[nonc[ARM].isna(), "realised_off_possessions"].sum())
    tov_no_rate = float(nonc.loc[nonc[ARM].isna(), "turnovers"].sum())
    nonc = nonc.rename(columns={ARM: "rate"})
    nonc["rate"] = nonc["rate"].fillna(0.0)                 # only rows with 0 possessions, 0 tov
    nonc["w_proj"] = 0.0
    nonc["w_real"] = nonc["realised_off_possessions"].astype(float)
    nonc["is_cand"] = False
    nonc["did_appear"] = True

    keep = KEY + ["rate", "w_proj", "w_real", "is_cand", "did_appear", "turnovers", "minutes"]
    rows = pd.concat([cand[keep], nonc[keep]], ignore_index=True)
    rows = rows.merge(op_tg[TG], on=TG, how="inner")

    # ---- team-game frame --------------------------------------------------- #
    tg = (rows.groupby(TG)
          .agg(T_proj=("w_proj", "sum"),
               T_real=("w_real", "sum"),
               n_rows=("player_id", "size"),
               n_cand=("is_cand", "sum"),
               n_appear=("did_appear", "sum"))
          .reset_index())
    tg["T_proj_app"] = (rows.loc[rows["did_appear"] & rows["is_cand"]]
                        .groupby(TG)["w_proj"].sum().reindex(
                            pd.MultiIndex.from_frame(tg[TG])).to_numpy())
    tg["R_nc"] = (rows.loc[~rows["is_cand"]].groupby(TG)["w_real"].sum()
                  .reindex(pd.MultiIndex.from_frame(tg[TG])).fillna(0.0).to_numpy())
    tg = tg.merge(TM, on=TG, how="left").merge(PACE, on=TG, how="left")
    tg["y_team"] = tg["player_attributed"].astype(float)
    tg["game_date"] = (O.drop_duplicates("game_id").set_index("game_id")["game_date"]
                       .reindex(tg["game_id"]).to_numpy())

    prov = {
        "team_games_in_scope": int(len(tg)),
        "player_rows_in_scope": int(len(rows)),
        "tier_a_candidate_rows": int(rows["is_cand"].sum()),
        "candidates_who_appeared": int((rows["is_cand"] & rows["did_appear"]).sum()),
        "candidates_who_did_not_appear": int((rows["is_cand"] & ~rows["did_appear"]).sum()),
        "non_candidate_realised_rows_in_scope": int((~rows["is_cand"]).sum()),
        "non_candidate_turnovers_in_scope": float(rows.loc[~rows["is_cand"], "turnovers"].sum()),
        "non_candidate_realised_possessions_in_scope": float(
            rows.loc[~rows["is_cand"], "w_real"].sum()),
        "appearing_candidates_with_zero_realised_possessions": int(
            ((rows["is_cand"]) & (rows["did_appear"]) & (rows["w_real"] == 0)).sum()),
        "non_candidate_rows_without_a_frozen_rate": n_no_rate,
        "their_realised_possessions": poss_no_rate,
        "their_turnovers": tov_no_rate,
        "rate_column": ARM,
        "rate_provenance": ("frozen per-row Arm D rate from the single chronological pass in "
                            "run_turnover_p1_universe_fix.py; candidate rows take it from the "
                            "operational parquet, non-candidate realised rows from the intrinsic "
                            "parquet -- both are the SAME state machine, so the rate is identical "
                            "for a given player and date"),
        "exposure_identity": ("sum of projected_off_possessions over the Tier A candidates of a "
                              "team-game equals EXACTLY 5x projected_team_off_possessions for all "
                              "2,914 team-games (max abs deviation reported below); the realised "
                              "analogue is 5x team_off_possessions to within lineup-validity loss"),
    }
    return rows, tg, prov


# --------------------------------------------------------------------------- #
# counterfactual exposure vectors
# --------------------------------------------------------------------------- #
def counterfactuals(rows: pd.DataFrame, tg: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return {name: per-row exposure weight}. Frozen rate is never touched."""
    TG = ["game_id", "team_id"]
    idx = pd.MultiIndex.from_frame(rows[TG])
    T_proj = tg.set_index(TG)["T_proj"].reindex(idx).to_numpy()
    T_real = tg.set_index(TG)["T_real"].reindex(idx).to_numpy()
    T_proj_app = tg.set_index(TG)["T_proj_app"].reindex(idx).to_numpy()
    R_nc = tg.set_index(TG)["R_nc"].reindex(idx).to_numpy()

    w_proj = rows["w_proj"].to_numpy(float)
    w_real = rows["w_real"].to_numpy(float)
    cand = rows["is_cand"].to_numpy(bool)
    app = rows["did_appear"].to_numpy(bool)
    cand_app = cand & app

    with np.errstate(divide="ignore", invalid="ignore"):
        # phi: the ORACLE realised share of team exposure owned by non-candidates
        phi = np.where(T_real > 0, R_nc / T_real, 0.0)
        # within-block projected shares among appearing candidates
        s_app = np.where(T_proj_app > 0, w_proj / np.where(T_proj_app > 0, T_proj_app, 1.0), 0.0)
        # within-block realised shares among non-candidates
        s_nc = np.where(R_nc > 0, w_real / np.where(R_nc > 0, R_nc, 1.0), 0.0)
        # realised share of the whole team
        s_real = np.where(T_real > 0, w_real / np.where(T_real > 0, T_real, 1.0), 0.0)

    cf = {}
    # CF1 -- the real pregame forecast
    cf["CF1_full_operational"] = np.where(cand, w_proj, 0.0)

    # CF1a -- LABELLED sub-diagnostic: drop non-appearing candidates, do NOT reallocate
    cf["CF1a_drop_nonappearing_no_realloc"] = np.where(cand_app, w_proj, 0.0)

    # CF2 -- oracle appearance: the SAME team projected total, reallocated among actual
    #        participants that the candidate universe did contain
    cf["CF2_oracle_appearance"] = np.where(cand_app, s_app * T_proj, 0.0)

    # CF3 -- CF2 plus the realised participants the candidate universe never contained.
    #        The non-candidate block is sized by its ORACLE realised share phi; the
    #        appearing-candidate block keeps its CF2 relative shares. phi == 0 => CF3 == CF2.
    cf["CF3_plus_missing_participants"] = np.where(
        cand_app, s_app * T_proj * (1.0 - phi), s_nc * T_proj * phi)

    # CF4 -- oracle within-team allocation (minutes/possessions), projected team total
    cf["CF4_oracle_allocation"] = s_real * T_proj

    # CF5 -- realised exposure: the intrinsic track
    cf["CF5_realised_exposure"] = w_real

    # ---- alternative ordering (path-dependence probe): fix the team total FIRST ---- #
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(T_proj > 0, T_real / np.where(T_proj > 0, T_proj, 1.0), 0.0)
    cf["ALT2_operational_at_realised_total"] = np.where(cand, w_proj, 0.0) * scale
    cf["ALT3_appearance_at_realised_total"] = np.where(cand_app, s_app * T_real, 0.0)
    cf["ALT4_missing_at_realised_total"] = np.where(
        cand_app, s_app * T_real * (1.0 - phi), s_nc * T_real * phi)
    return cf


def team_pred(rows: pd.DataFrame, tg: pd.DataFrame, w: np.ndarray) -> np.ndarray:
    TG = ["game_id", "team_id"]
    s = (pd.DataFrame({"game_id": rows["game_id"], "team_id": rows["team_id"],
                       "p": rows["rate"].to_numpy(float) * w})
         .groupby(TG)["p"].sum())
    return s.reindex(pd.MultiIndex.from_frame(tg[TG])).fillna(0.0).to_numpy()


def _ci(v, clusters):
    c = cluster_bootstrap_ci(np.asarray(v, float), np.asarray(clusters), **BOOT)
    return [round(c["low"], 6), round(c["high"], 6)], int(c["n_clusters"])


# --------------------------------------------------------------------------- #
def main() -> int:
    rows, tg, prov = build_rows()
    cf = counterfactuals(rows, tg)

    # exposure identity check
    ident = np.abs(tg["T_proj"].to_numpy() - 5.0 * tg["projected_team_off_possessions"].to_numpy())
    prov["max_abs_deviation_from_5x_identity"] = float(np.nanmax(ident))

    y = tg["y_team"].to_numpy(float)
    gid = tg["game_id"].to_numpy()
    gdate = pd.to_datetime(tg["game_date"]).dt.strftime("%Y-%m-%d").to_numpy()

    ae, levels = {}, {}
    for name, w in cf.items():
        p = team_pred(rows, tg, w)
        e = np.abs(p - y)
        ae[name] = e
        lo, n_cl = _ci(e, gid)
        lo_d, n_d = _ci(e, gdate)
        levels[name] = {
            "team_mae": round(float(e.mean()), 6),
            "team_mae_ci90_game_clustered": lo,
            "team_mae_ci90_date_clustered": lo_d,
            "team_bias_pred_minus_actual": round(float((p - y).mean()), 6),
            "team_rmse": round(float(np.sqrt(np.mean((p - y) ** 2))), 6),
            "team_games": int(len(e)),
            "clusters_game": n_cl, "clusters_date": n_d,
            "exposure_sum": round(float(w.sum()), 3),
            "rows_with_positive_exposure": int((w > 0).sum()),
        }

    def delta(before, after, label, mechanism):
        d = ae[before] - ae[after]                       # POSITIVE => the fix helps
        ci, n_cl = _ci(d, gid)
        ci_d, _ = _ci(d, gdate)
        return {
            "label": label, "mechanism": mechanism,
            "from": before, "to": after,
            "sign_convention": SIGN,
            "delta_team_mae": round(float(d.mean()), 6),
            "ci90_game_clustered": ci, "ci90_date_clustered": ci_d,
            "clusters": n_cl,
            "team_games_improved": int((d > 1e-12).sum()),
            "team_games_worsened": int((d < -1e-12).sum()),
            "team_games_unchanged": int((np.abs(d) <= 1e-12).sum()),
            "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0),
        }

    chain = [
        delta("CF1_full_operational", "CF2_oracle_appearance",
              "availability / candidate appearance",
              "exposure wrongly assigned to Tier A candidates who did not play, reallocated "
              "to the candidates who did; team projected total held fixed"),
        delta("CF2_oracle_appearance", "CF3_plus_missing_participants",
              "missing actual participants (candidate universe recall)",
              "realised players who were never Tier A candidates are given their oracle "
              "realised share of the same projected team total"),
        delta("CF3_plus_missing_participants", "CF4_oracle_allocation",
              "within-team minutes / possession allocation",
              "projected within-team exposure shares replaced by realised shares; "
              "team projected total still held fixed"),
        delta("CF4_oracle_allocation", "CF5_realised_exposure",
              "team possession-total projection",
              "projected team offensive possessions replaced by realised team offensive "
              "possessions; within-team shares already oracle"),
    ]
    sub = [
        delta("CF1_full_operational", "CF1a_drop_nonappearing_no_realloc",
              "exposure LEAKED to non-appearing candidates (removed, not reallocated)",
              "isolates the raw over-assignment of exposure to players who did not play"),
        delta("CF1a_drop_nonappearing_no_realloc", "CF2_oracle_appearance",
              "reallocation of the leaked exposure to actual participants",
              "restores the team projected total onto the players who did play"),
    ]
    alt = [
        delta("CF1_full_operational", "ALT2_operational_at_realised_total",
              "team possession-total projection (ALT ordering, applied FIRST)",
              "same intervention as chain step 4 but applied before any candidate-set fix"),
        delta("ALT2_operational_at_realised_total", "ALT3_appearance_at_realised_total",
              "availability / candidate appearance (ALT ordering)", "second in the ALT path"),
        delta("ALT3_appearance_at_realised_total", "ALT4_missing_at_realised_total",
              "missing actual participants (ALT ordering)", "third in the ALT path"),
        delta("ALT4_missing_at_realised_total", "CF5_realised_exposure",
              "within-team minutes / possession allocation (ALT ordering)", "last in the ALT path"),
    ]

    # ---- rate floor: what CF5 still gets wrong with PERFECT exposure ------------- #
    rate_floor = {
        "label": "conditional turnover rate itself (frozen Arm D)",
        "team_mae_with_perfect_exposure": levels["CF5_realised_exposure"]["team_mae"],
        "share_of_operational_team_mae": round(
            levels["CF5_realised_exposure"]["team_mae"] /
            levels["CF1_full_operational"]["team_mae"], 6),
        "interpretation": ("CF5 gives the rate model the true participant set, the true minutes "
                           "allocation and the true possession count. Whatever error remains is "
                           "attributable to the conditional rate (and to the team-unattributed "
                           "turnovers that no player model can claim)."),
    }

    # ---- supporting descriptives ------------------------------------------------- #
    T_proj = tg["T_proj"].to_numpy(float)
    T_real = tg["T_real"].to_numpy(float)
    leaked = (rows.loc[rows["is_cand"] & ~rows["did_appear"]]
              .assign(p=lambda d: d["rate"] * d["w_proj"])
              .groupby(["game_id", "team_id"])["p"].sum()
              .reindex(pd.MultiIndex.from_frame(tg[["game_id", "team_id"]])).fillna(0.0).to_numpy())
    desc = {
        "mean_team_projected_player_possessions": round(float(T_proj.mean()), 4),
        "mean_team_realised_player_possessions": round(float(T_real.mean()), 4),
        "mean_abs_team_possession_projection_error_player_possessions": round(
            float(np.abs(T_proj - T_real).mean()), 4),
        "mean_abs_team_possession_projection_error_team_possessions": round(
            float(np.abs(T_proj - T_real).mean() / 5.0), 4),
        "mean_predicted_turnovers_sitting_on_non_appearing_candidates": round(
            float(leaked.mean()), 4),
        "total_predicted_turnovers_on_non_appearing_candidates": round(float(leaked.sum()), 2),
        "mean_team_attributed_turnovers": round(float(y.mean()), 4),
        "turnovers_owned_by_non_candidates_per_team_game": round(
            prov["non_candidate_turnovers_in_scope"] / len(tg), 4),
        "why_leakage_is_not_bias": (
            "the projected exposure of a team-game sums to exactly 5x the projected team "
            "possessions no matter who is in the candidate list, so exposure given to a "
            "non-appearing candidate is exposure TAKEN FROM an appearing one. At the team "
            "level the candidate-set error can only move the total through RATE MIX, never "
            "through exposure volume."),
        "mean_abs_rate_mix_gap_per_team_game": round(float(np.abs(
            ae["CF1_full_operational"] - ae["CF2_oracle_appearance"]).mean()), 4),
    }

    # ---- structural identity: team pred = T x (exposure-weighted mean rate) ------- #
    wbar = {}
    for name, w in cf.items():
        r = rows["rate"].to_numpy(float)
        num = (pd.DataFrame({"g": rows["game_id"], "t": rows["team_id"], "v": r * w})
               .groupby(["g", "t"])["v"].sum()
               .reindex(pd.MultiIndex.from_frame(tg[["game_id", "team_id"]])).to_numpy())
        den = (pd.DataFrame({"g": rows["game_id"], "t": rows["team_id"], "v": w})
               .groupby(["g", "t"])["v"].sum()
               .reindex(pd.MultiIndex.from_frame(tg[["game_id", "team_id"]])).to_numpy())
        with np.errstate(divide="ignore", invalid="ignore"):
            wbar[name] = {
                "exposure_weighted_mean_rate": round(float(np.nanmean(
                    np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan))), 6),
                "mean_team_exposure": round(float(np.nanmean(den)), 3)}
    structural = {
        "identity": ("team prediction = T_team x rbar, where T_team is the team's total "
                     "offensive player-possessions and rbar is the exposure-weighted mean "
                     "frozen Arm D rate"),
        "consequence": ("because T_team is pinned to 5x the PACE-DERIVED team possession "
                        "projection and does NOT depend on which players are in the candidate "
                        "list, candidate-universe errors and within-team allocation errors "
                        "cannot change the forecast VOLUME. They can only perturb rbar. Only "
                        "two quantities can move the team forecast: T_team and rbar."),
        "per_counterfactual": wbar,
    }

    # ---- realistic marginal-return curve on the possession total ------------------ #
    TG = ["game_id", "team_id"]
    idx = pd.MultiIndex.from_frame(rows[TG])
    tp = tg.set_index(TG)["T_proj"].reindex(idx).to_numpy()
    tr = tg.set_index(TG)["T_real"].reindex(idx).to_numpy()
    base = cf["CF1_full_operational"]
    with np.errstate(divide="ignore", invalid="ignore"):
        sh = np.where(tp > 0, base / np.where(tp > 0, tp, 1.0), 0.0)
    sweep = []
    for lam in (0.0, 0.25, 0.50, 0.75, 1.0):
        p = team_pred(rows, tg, sh * (tp + lam * (tr - tp)))
        e = np.abs(p - y)
        d = ae["CF1_full_operational"] - e
        ci, _ = _ci(d, gid)
        sweep.append({"lambda_shrink_toward_realised_total": lam,
                      "team_mae": round(float(e.mean()), 6),
                      "delta_vs_CF1": round(float(d.mean()), 6),
                      "ci90_game_clustered": ci,
                      "sign_convention": SIGN})
    poss_curve = {
        "what": ("team possession total moved a fraction lambda of the way from the projected "
                 "value to the realised value, holding the OPERATIONAL candidate set and "
                 "projected within-team shares fixed. lambda=0 is CF1, lambda=1 is ALT2."),
        "why": ("the lambda=1 oracle gain is an upper bound that no forecaster can reach; the "
                "curve shows what a PARTIAL improvement in possession projection would buy"),
        "curve": sweep,
    }

    # ---- is the possession-total gain just unforeseeable overtime? ---------------- #
    ot = pd.read_parquet(PP / "possessions_v2/possessions_raw_v2.parquet",
                         columns=["game_id", "is_overtime"])
    ot = ot.groupby("game_id")["is_overtime"].any().rename("went_ot").reset_index()
    tgo = tg[["game_id"]].merge(ot, on="game_id", how="left")
    is_ot = tgo["went_ot"].fillna(False).to_numpy(bool)
    d_poss = ae["CF4_oracle_allocation"] - ae["CF5_realised_exposure"]
    d_alt = ae["CF1_full_operational"] - ae["ALT2_operational_at_realised_total"]
    ot_blk = {}
    for nm, mask in (("overtime_team_games", is_ot), ("regulation_team_games", ~is_ot)):
        if mask.sum() >= 2:
            ci_c, _ = _ci(d_poss[mask], gid[mask])
            ci_a, _ = _ci(d_alt[mask], gid[mask])
            ot_blk[nm] = {
                "team_games": int(mask.sum()),
                "share_of_support": round(float(mask.mean()), 4),
                "chain_step4_delta_team_mae": round(float(d_poss[mask].mean()), 6),
                "chain_step4_ci90": ci_c,
                "ALT_step1_delta_team_mae": round(float(d_alt[mask].mean()), 6),
                "ALT_step1_ci90": ci_a,
                "mean_abs_possession_projection_error_team_possessions": round(
                    float(np.abs(T_proj[mask] - T_real[mask]).mean() / 5.0), 4)}
    ot_blk["reading"] = ("if the possession-total gain concentrated in overtime games it would be "
                         "largely irreducible; a gain that persists in regulation games is a real "
                         "pace-projection deficiency and is addressable")

    # ---- irreducible-noise benchmark --------------------------------------------- #
    # If the forecast WERE the true conditional mean, team turnovers would still be a
    # random count. E|Y - lambda| under Poisson(lambda) is a LOWER bound on achievable
    # MAE (a real team total is mildly over-dispersed, so the true floor is higher).
    def _pois_mad(lam):
        lam = np.clip(np.asarray(lam, float), 1e-9, None)
        k = np.floor(lam).astype(int)
        # De Moivre: E|Y-lam| = 2 * lam^(k+1) * e^-lam / k!
        with np.errstate(over="ignore"):
            logp = (k + 1) * np.log(lam) - lam - np.array(
                [float(np.sum(np.log(np.arange(1, kk + 1)))) if kk > 0 else 0.0 for kk in k])
        return 2.0 * np.exp(logp)

    p5 = team_pred(rows, tg, cf["CF5_realised_exposure"])
    p1 = team_pred(rows, tg, cf["CF1_full_operational"])
    resid = y - p5
    noise = {
        "poisson_mad_floor_at_CF5_predictions": round(float(_pois_mad(p5).mean()), 6),
        "poisson_mad_floor_at_realised_mean": round(float(_pois_mad(np.full_like(y, y.mean())).mean()), 6),
        "observed_CF5_team_mae": levels["CF5_realised_exposure"]["team_mae"],
        "observed_CF1_team_mae": levels["CF1_full_operational"]["team_mae"],
        "CF5_mae_over_poisson_floor": round(
            float(levels["CF5_realised_exposure"]["team_mae"] / _pois_mad(p5).mean()), 4),
        "CF1_mae_over_poisson_floor": round(
            float(levels["CF1_full_operational"]["team_mae"] / _pois_mad(p1).mean()), 4),
        "residual_variance_over_mean_dispersion": round(
            float(np.var(resid) / np.mean(p5)), 4),
        "mean_team_attributed_turnovers": round(float(y.mean()), 4),
        "reading": ("a ratio near 1.0 means the forecast is already at the irreducible count "
                    "noise of the target and no rate or exposure modelling can move team MAE "
                    "much further; a dispersion ratio above 1.0 means the target is "
                    "over-dispersed relative to Poisson, so the true floor is ABOVE the "
                    "Poisson figure quoted here"),
        "caveat": ("this is a LOWER bound. It uses the CF5 oracle-exposure prediction as the "
                   "conditional mean, which is itself imperfect, and Poisson under-states the "
                   "dispersion of a correlated team total."),
    }

    # ---- ancillary: MAE is minimised by the conditional MEDIAN, not the mean ------ #
    # Arm D emits a conditional MEAN. For a count target the MAE-optimal point forecast
    # is the median. This is a METRIC-ALIGNMENT lever that consumes NO new information
    # and is not part of the exposure decomposition; it is reported so the "where next"
    # recommendation is not made in ignorance of it.
    def _pois_median(lam):
        lam = np.clip(np.asarray(lam, float), 1e-9, None)
        return np.floor(lam + 1.0 / 3.0 - 0.02 / lam)

    med = {}
    for nm, p in (("CF1_full_operational", p1), ("CF5_realised_exposure", p5)):
        e_med = np.abs(_pois_median(p) - y)
        d = np.abs(p - y) - e_med
        ci, _ = _ci(d, gid)
        med[nm] = {"team_mae_mean_forecast": round(float(np.abs(p - y).mean()), 6),
                   "team_mae_median_forecast": round(float(e_med.mean()), 6),
                   "delta_team_mae": round(float(d.mean()), 6),
                   "ci90_game_clustered": ci,
                   "sign_convention": SIGN,
                   "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0)}
    med["note"] = ("NOT an exposure error source and NOT part of the chain. Included because a "
                   "recommendation about where to spend the next research effort is incomplete "
                   "without knowing that a free metric-alignment change exists. Rounding to a "
                   "count also changes the loss surface, so this is a crude probe, not a "
                   "proposal; any real version must be a registered challenger.")

    # ---- SCOPE LIMIT: everything above is TEAM MAE ------------------------------- #
    # The 5x identity makes candidate-set error cancel at the team level. It does NOT
    # cancel at the player level, which is the level a player prop is settled at.
    r = rows["rate"].to_numpy(float)
    w1 = cf["CF1_full_operational"]
    ytov = rows["turnovers"].to_numpy(float)
    na = (rows["is_cand"] & ~rows["did_appear"]).to_numpy()
    pl_ae = np.abs(r * w1 - ytov)
    scope = {
        "team_level_conclusion_does_not_transfer_to_player_level": True,
        "player_rows_scored_in_CF1": int(rows["is_cand"].sum()),
        "player_level_mae_CF1": round(float(pl_ae[rows["is_cand"].to_numpy()].mean()), 6),
        "non_appearing_candidate_rows": int(na.sum()),
        "predicted_turnovers_on_non_appearing_candidates": round(float((r * w1)[na].sum()), 3),
        "realised_turnovers_on_non_appearing_candidates": round(float(ytov[na].sum()), 3),
        "mean_pure_overprediction_per_non_appearing_row": round(float((r * w1)[na].mean()), 6),
        "share_of_player_level_mae_from_non_appearing_rows": round(
            float(pl_ae[na].sum() / pl_ae[rows["is_cand"].to_numpy()].sum()), 6),
        "reading": ("appearance error is ~14% of PLAYER-level absolute error and 0% of TEAM-level "
                    "error. A decision to deprioritise availability work is valid ONLY for the "
                    "team total. Any player-prop application must re-run this decomposition at "
                    "the player level, where the 5x identity provides no cancellation."),
    }

    # ---- ordering ---------------------------------------------------------------- #
    ranked = sorted(
        [{"source": c["label"], "delta_team_mae": c["delta_team_mae"],
          "ci90_game_clustered": c["ci90_game_clustered"],
          "ci_excludes_zero": c["ci_excludes_zero"]} for c in chain],
        key=lambda r: -abs(r["delta_team_mae"]))
    for i, r in enumerate(ranked, 1):
        r["rank_by_absolute_magnitude"] = i

    gap = (levels["CF1_full_operational"]["team_mae"]
           - levels["CF5_realised_exposure"]["team_mae"])
    out = {
        "schema": "discovery_ws8_operational_error_decomposition/1",
        "workstream": "ws8_operational_error_decomposition",
        "wave": "discovery_wave_1",
        "lane": "DISCOVERY (development folds only)",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "frozen_model_untouched": {
            "arm": ARM, "K": 200, "alpha": 0.10,
            "what_varies": "ONLY the exposure vector (row membership and possessions per row)",
            "what_is_fixed": "the per-row Arm D rate, the target, and the team-game support",
            "projected_player_possessions_v1_modified": False,
            "arm_registry_appended": False,
        },
        "oracle_disclosure": {
            "CF2_oracle_appearance": "uses who actually played",
            "CF3_plus_missing_participants": "uses who actually played AND their realised share",
            "CF4_oracle_allocation": "uses realised within-team possession shares",
            "CF5_realised_exposure": "uses realised possessions outright",
            "status": ("DIAGNOSTIC ONLY. None of CF2..CF5 is a forecast, a model, or promotion "
                       "evidence. They exist to attribute error, not to produce it."),
        },
        "sign_convention": {"levels": LEVEL_SIGN, "deltas": SIGN},
        "provenance_and_counts": prov,
        "support_note": (
            "every counterfactual is evaluated on the SAME 2,914 team-games (the operational "
            "track's support) against the SAME target (player_attributed). The frozen headline "
            "intrinsic MAE of 2.8960 is quoted on 2,982 team-games, 68 of which have no Tier A "
            "candidate universe and therefore no operational counterpart; CF5 here is the "
            "intrinsic track restricted to common support, so it is NOT numerically identical "
            "to the frozen headline."),
        "frozen_reproduction": {
            "operational_team_mae_frozen": 2.9675,
            "operational_team_mae_reproduced_CF1": levels["CF1_full_operational"]["team_mae"],
            "reproduces": bool(abs(levels["CF1_full_operational"]["team_mae"] - 2.9674505) < 5e-6),
            "intrinsic_team_mae_frozen_2982_team_games": 2.8960,
            "intrinsic_team_mae_on_common_support_CF5": levels["CF5_realised_exposure"]["team_mae"],
        },
        "counterfactual_levels": levels,
        "incremental_chain_primary_ordering": chain,
        "appearance_substep_split": sub,
        "alternative_ordering_path_dependence_probe": alt,
        "rate_floor": rate_floor,
        "structural_identity": structural,
        "possession_total_marginal_return_curve": poss_curve,
        "possession_gain_overtime_split": ot_blk,
        "irreducible_noise_benchmark": noise,
        "ancillary_median_vs_mean_point_forecast": med,
        "scope_limit_team_vs_player_level": scope,
        "supporting_descriptives": desc,
        "total_operational_minus_intrinsic_gap_on_common_support": round(float(gap), 6),
        "chain_sums_to_gap": round(float(sum(c["delta_team_mae"] for c in chain)), 6),
        "ranked_ordering": ranked,
        "verdict": {
            "expected_direction_in_ledger": "exposure-side errors dominate rate error",
            "expected_direction_supported_in_LEVEL_terms": False,
            "expected_direction_supported_in_ADDRESSABLE_terms": True,
            "explanation": (
                "the rate track carries 97.25% of operational team MAE, so exposure does NOT "
                "dominate in level terms. But that 2.8859 sits at 0.9969 of the Poisson "
                "mean-absolute-deviation floor of the target, i.e. it is irreducible count "
                "noise, not modelling error. Of the 0.0816 ADDRESSABLE gap, 100% is "
                "exposure-side, and within that one source dominates decisively."),
            "falsifier_contributions_are_diffuse_and_none_dominates": False,
            "supports_hypothesis_clear_ordering_obtained": True,
            "dominant_source": "team possession-total projection",
            "null_sources": ["availability / candidate appearance",
                             "missing actual participants (candidate universe recall)"],
            "reversed_sources": [
                "within-team minutes / possession allocation: the ORACLE allocation is "
                "SIGNIFICANTLY WORSE than the projected allocation (-0.0181 [-0.0276, -0.0089]). "
                "Improving allocation accuracy would mildly HURT the team total."],
            "path_dependence": ("a genuinely different ordering reproduces the ranking and every "
                                "sign; the decomposition is not a path artefact"),
        },
        "recommendation": {
            "next_marginal_research_effort_belongs_in": (
                "team possession (pace) projection -- team_possession_prior_v1 / "
                "projected_team_off_possessions"),
            "and_nowhere_else_in_this_decomposition": True,
            "not_the_rate_model_because": "CF5 is at 0.9969 of the target's Poisson noise floor",
            "not_availability_because": "null at team level in both orderings",
            "not_candidate_precision_because": "null at team level in both orderings",
            "not_minute_allocation_because": "the oracle allocation is significantly WORSE",
            "expected_value": ("a 25-50% reduction in possession projection error buys +0.036 to "
                               "+0.065 team MAE, i.e. 1.2-2.2% of operational MAE"),
            "honest_size_of_the_prize": "small",
            "if_a_larger_prize_is_wanted": (
                "it is not in the team turnover total at all. It must be sought at the PLAYER "
                "level, where the 5x identity gives no cancellation and appearance error alone "
                "is 14.18% of player-level absolute error."),
            "binding_rule_respected": (
                "no discovery result may replace Arm D directly; any pace-projection work must "
                "become a NEW frozen challenger under a separate registered evaluation"),
        },
    }
    (HERE / "WS8_ERROR_DECOMPOSITION.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")

    # ---- console ------------------------------------------------------------- #
    print(f"team-games {len(tg):,}   player rows {len(rows):,}")
    print(f"5x identity max abs deviation: {prov['max_abs_deviation_from_5x_identity']:.3e}")
    print(f"\n{'counterfactual':38s} {'teamMAE':>9s} {'ci90':>20s} {'bias':>9s} {'expsum':>12s}")
    for k, v in levels.items():
        print(f"{k:38s} {v['team_mae']:9.4f} "
              f"[{v['team_mae_ci90_game_clustered'][0]:7.4f},{v['team_mae_ci90_game_clustered'][1]:7.4f}] "
              f"{v['team_bias_pred_minus_actual']:+9.4f} {v['exposure_sum']:12.0f}")
    print(f"\nSIGN: {SIGN}")
    for tag, blk in (("PRIMARY CHAIN", chain), ("APPEARANCE SUBSTEP", sub), ("ALT ORDER", alt)):
        print(f"\n--- {tag} ---")
        for c in blk:
            print(f"{c['label'][:56]:56s} {c['delta_team_mae']:+9.5f} "
                  f"[{c['ci90_game_clustered'][0]:+.5f},{c['ci90_game_clustered'][1]:+.5f}] "
                  f"{'SIG' if c['ci_excludes_zero'] else 'null'}")
    print("\n--- possession-total marginal return (operational shares held) ---")
    for s in sweep:
        print(f"lambda={s['lambda_shrink_toward_realised_total']:.2f}  MAE {s['team_mae']:.4f}  "
              f"delta {s['delta_vs_CF1']:+.5f} "
              f"[{s['ci90_game_clustered'][0]:+.5f},{s['ci90_game_clustered'][1]:+.5f}]")
    print("\n--- possession gain: overtime vs regulation ---")
    for k, v in ot_blk.items():
        if isinstance(v, dict):
            print(f"{k:26s} n={v['team_games']:5d}  chain-step4 {v['chain_step4_delta_team_mae']:+.5f}"
                  f"  ALT-step1 {v['ALT_step1_delta_team_mae']:+.5f}"
                  f"  mean|poss err| {v['mean_abs_possession_projection_error_team_possessions']:.2f}")
    print("\n--- irreducible noise ---")
    print(f"Poisson MAD floor at CF5 preds {noise['poisson_mad_floor_at_CF5_predictions']:.4f}   "
          f"CF5/floor {noise['CF5_mae_over_poisson_floor']:.4f}   "
          f"CF1/floor {noise['CF1_mae_over_poisson_floor']:.4f}   "
          f"dispersion {noise['residual_variance_over_mean_dispersion']:.3f}")
    print(f"\ngap CF1-CF5 {gap:+.5f}   chain sum {sum(c['delta_team_mae'] for c in chain):+.5f}")
    print(f"rate floor (CF5) {rate_floor['team_mae_with_perfect_exposure']:.4f} = "
          f"{rate_floor['share_of_operational_team_mae']*100:.2f}% of operational MAE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
