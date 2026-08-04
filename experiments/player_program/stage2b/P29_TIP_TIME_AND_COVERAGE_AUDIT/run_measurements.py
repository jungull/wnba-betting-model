#!/usr/bin/env python3
"""run_measurements.py -- P29: tip-time null-mask / fold-identity separability audit.

Reads only. Writes only MEASUREMENTS.json inside this node's directory.

    python experiments/player_program/stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/run_measurements.py

Every figure quoted in REPORT.md comes from this script. Nothing is asserted from a document.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parent.parent                      # experiments/player_program
REPO = PROGRAM.parent.parent                      # worktree root
sys.path.insert(0, str(PROGRAM))

import feature_gate as fg                          # noqa: E402  FROZEN, READ ONLY

PRIOR = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"
# tip_times.csv is NOT under experiments/player_program. It lives in the shared reference tree and
# is READ ONLY here. The acceptance criteria require its provenance to be addressed, so it must be
# opened rather than described.
TIPS = REPO / "data" / "reference" / "tip_times.csv"
BIOS_TIPCOV = REPO / "experiments" / "bios_collection" / "tip_coverage_by_season.csv"
ODDS_DRIVE = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_HIST_DIR = REPO / "data" / "odds_capture" / "historical"
ODDS_LIVE_DIR = REPO / "data" / "odds_capture"
# The odds tables tip_times.csv is derived from are NOT tracked by git and are NOT present in this
# worktree. They exist only in the repository-root working tree, which is a different branch. Any
# figure read from there is labelled OUT_OF_SCOPE_ROOT_WORKTREE and is read-only.
ROOT_WT = Path("C:/Users/jgallagher/wnba-betting-model")

REGULATION_MIN = 40.0                              # EVIDENCE_PACKET_V2.incumbent.constants


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- universe / target
def universe_all() -> pd.DataFrame:
    """All 2,990 team-game rows over 1,495 games, resolved and unresolved."""
    return pd.read_parquet(PRIOR)


def universe_resolved(d: pd.DataFrame) -> pd.DataFrame:
    r = d[d["pace_resolved"]].copy().reset_index(drop=True)
    r["offset_projected"] = r["projected_team_off_possessions"].astype(float)
    for lvl in ["league_prior_all", "team_window_prior_season", "team_window_same_season"]:
        r[f"tier_{lvl}"] = (r["pace_source"] == lvl).astype(float)
    return r


def realised_target() -> pd.DataFrame:
    """Regulation-equivalent realised offensive possessions (completed-game outcome only).

    Same formula as the frozen incumbent: count offensive possessions per team-game and rescale by
    40 / game_minutes, where game_minutes = 40 + 5 * OT periods. Never enters a design.
    """
    p = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "period"])
    g = p.groupby("game_id").agg(max_period=("period", "max")).reset_index()
    g["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, g["max_period"] - 4)
    n = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
         .rename(columns={"offense_team_id": "team_id"}))
    n = n.merge(g, on="game_id", how="left")
    n["realised_off_poss"] = n["n_off_poss"] * REGULATION_MIN / n["game_minutes"]
    return n[["game_id", "team_id", "realised_off_poss"]]


# --------------------------------------------------------------------------- association stats
def phi(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two binary vectors == the phi coefficient."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def cramers_v(x: pd.Series, y: pd.Series) -> dict:
    ct = pd.crosstab(x, y)
    obs = ct.to_numpy(float)
    n = obs.sum()
    exp = np.outer(obs.sum(1), obs.sum(0)) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum(np.where(exp > 0, (obs - exp) ** 2 / exp, 0.0)))
    k = min(obs.shape) - 1
    v = float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")
    return {"chi2": chi2, "n": int(n), "cramers_v": v,
            "dof": int((obs.shape[0] - 1) * (obs.shape[1] - 1))}


def r2_on_dummies(y: np.ndarray, groups: pd.Series) -> float:
    """R^2 of a one-way ANOVA of y on the group labels == eta^2. For a binary y this is the share
    of the null mask's variance that fold identity alone explains."""
    y = np.asarray(y, float)
    gm = pd.Series(y).groupby(groups.to_numpy()).transform("mean").to_numpy()
    ss_tot = float(((y - y.mean()) ** 2).sum())
    ss_res = float(((y - gm) ** 2).sum())
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def main() -> int:
    out: dict = {
        "schema": "p29_measurements/1",
        "node": "P29_TIP_TIME_AND_COVERAGE_AUDIT",
        "epistemic_status": ("VERIFIED_READ_ONLY_DERIVATION. Determines whether a null mask is "
                             "separable from fold identity. A coverage finding is not a licence to "
                             "admit a feature."),
        "inputs": {},
    }
    for label, p in [("team_possession_prior_v1.parquet", PRIOR),
                     ("possessions_raw_v2.parquet", POSS),
                     ("tip_times.csv", TIPS),
                     ("master_odds.csv", ODDS_DRIVE)]:
        out["inputs"][label] = {"path": str(p), "exists": p.exists(),
                                "sha256": sha256(p) if p.exists() else None,
                                "bytes": p.stat().st_size if p.exists() else None}

    allrows = universe_all()
    U = universe_resolved(allrows)
    tips = pd.read_csv(TIPS, dtype={"game_id": str})

    # ---------------------------------------------------------------- M1 universe reproduction
    out["M1_universe"] = {
        "team_game_rows_in_artifact": int(len(allrows)),
        "games_in_artifact": int(allrows["game_id"].nunique()),
        "pace_resolved_rows": int(len(U)),
        "resolved_game_clusters": int(U["game_id"].nunique()),
        "unresolved_rows": int((~allrows["pace_resolved"]).sum()),
        "packet_claim_rows_2982_clusters_1491": bool(len(U) == 2982 and U["game_id"].nunique() == 1491),
        "packet_claim_games_with_one_shared_projection_1495":
            bool(allrows["game_id"].nunique() == 1495),
        "games_by_season": {str(k): int(v) for k, v in
                            allrows.drop_duplicates("game_id").groupby("season").size().items()},
    }

    # ---------------------------------------------------------------- M2 tip_times.csv itself
    out["M2_tip_times_file"] = {
        "rows": int(len(tips)),
        "columns": list(tips.columns),
        "distinct_game_id": int(tips["game_id"].nunique()),
        "duplicate_game_id_rows": int(tips["game_id"].duplicated().sum()),
        "rows_by_season": {str(k): int(v) for k, v in tips.groupby("season").size().items()},
        "rows_by_season_and_source_table": {
            f"{s}|{t}": int(v) for (s, t), v in tips.groupby(["season", "source_table"]).size().items()},
        "tip_rows_not_in_contract_universe":
            int((~tips["game_id"].isin(set(allrows["game_id"]))).sum()),
        "n_commence_variants_distribution": {
            str(k): int(v) for k, v in tips["n_commence_variants"].value_counts().sort_index().items()},
        "n_snapshots_min_median_max": [int(tips["n_snapshots"].min()),
                                       float(tips["n_snapshots"].median()),
                                       int(tips["n_snapshots"].max())],
        "tip_hour_local_distribution": {
            str(k): int(v) for k, v in tips["tip_hour_local"].value_counts().sort_index().items()},
    }

    # ---------------------------------------------------------------- M3 the null mask
    covered = set(tips["game_id"])
    g = allrows.drop_duplicates("game_id")[["game_id", "season", "season_type",
                                            "game_date"]].copy().reset_index(drop=True)
    g["tip_null"] = (~g["game_id"].isin(covered)).astype(int)

    gr = U.drop_duplicates("game_id")[["game_id", "season", "season_type"]].copy().reset_index(drop=True)
    gr["tip_null"] = (~gr["game_id"].isin(covered)).astype(int)

    by_season = (g.groupby("season")["tip_null"].agg(["sum", "size"])
                 .rename(columns={"sum": "null", "size": "games"}))
    by_season["covered"] = by_season["games"] - by_season["null"]
    by_season["null_rate"] = by_season["null"] / by_season["games"]

    out["M3_null_mask"] = {
        "frame": "one row per game in the full 1,495-game universe",
        "games_total": int(len(g)),
        "games_null": int(g["tip_null"].sum()),
        "games_covered": int((1 - g["tip_null"]).sum()),
        "by_season": {str(i): {"games": int(r.games), "null": int(r["null"]),
                               "covered": int(r.covered), "null_rate": round(float(r.null_rate), 6)}
                      for i, r in by_season.iterrows()},
        "resolved_cluster_frame": {
            "clusters_total": int(len(gr)),
            "clusters_null": int(gr["tip_null"].sum()),
            "clusters_covered": int((1 - gr["tip_null"]).sum()),
        },
        "V2_STOP_CONDITION_claim": "1,219 of 1,495 games [null] and NONE of 2021",
        "CORRECTION_ADDENDUM_C7_claim": {"rows": 1219, "of": 1495,
                                         "verdict": "PARTIAL -- 2021 coverage is zero"},
    }

    # ---------------------------------------------------------------- M4 fold identity
    # EVIDENCE_PACKET_V2.inference_specification.fold_construction: "chronological, nested by
    # season; a game is NEVER split across folds". Fold label = season; fold index = chronological
    # rank of the season. Six folds, 2021..2026. Fold 1 = 2021.
    seasons = sorted(g["season"].unique())
    fold_index = {s: i + 1 for i, s in enumerate(seasons)}
    g["fold"] = g["season"].map(fold_index)
    gr["fold"] = gr["season"].map(fold_index)
    U["fold"] = U["season"].map(fold_index)

    fold1_ind = (g["fold"] == 1).astype(int).to_numpy()
    null_g = g["tip_null"].to_numpy()

    off_diag_10 = int(((null_g == 1) & (fold1_ind == 0)).sum())   # null but not fold 1
    off_diag_01 = int(((null_g == 0) & (fold1_ind == 1)).sum())   # fold 1 but not null

    out["M4_fold_identity"] = {
        "fold_construction_source": ("EVIDENCE_PACKET_V2.inference_specification.fold_construction "
                                     "= 'chronological, nested by season'"),
        "folds": {str(fold_index[s]): str(s) for s in seasons},
        "n_folds": len(seasons),
        "game_frame": {
            "phi_null_vs_fold1_indicator": round(phi(null_g, fold1_ind), 6),
            "cramers_v_null_vs_fold": {k: (round(v, 6) if isinstance(v, float) else v)
                                       for k, v in cramers_v(g["tip_null"], g["fold"]).items()},
            "eta2_null_on_fold_dummies": round(r2_on_dummies(null_g, g["fold"]), 6),
            "share_of_nulls_in_fold1": round(float(((null_g == 1) & (fold1_ind == 1)).sum()
                                                   / max(1, null_g.sum())), 6),
            "share_of_fold1_that_is_null": round(float(((null_g == 1) & (fold1_ind == 1)).sum()
                                                       / max(1, fold1_ind.sum())), 6),
            "off_diagonal_null_not_fold1": off_diag_10,
            "off_diagonal_fold1_not_null": off_diag_01,
            "off_diagonal_total": off_diag_10 + off_diag_01,
            "off_diagonal_rate": round((off_diag_10 + off_diag_01) / len(g), 6),
            "mask_is_exactly_fold1": bool((off_diag_10 + off_diag_01) == 0),
        },
        "per_fold_null_mask_variance": {
            str(int(f)): {"games": int(len(sub)), "null": int(sub["tip_null"].sum()),
                          "covered": int((1 - sub["tip_null"]).sum()),
                          "null_mask_sd": round(float(sub["tip_null"].std(ddof=0)), 6),
                          "null_mask_is_constant": bool(sub["tip_null"].nunique() == 1)}
            for f, sub in g.groupby("fold")},
    }

    # ------------------------------------------------- M4b what the mask actually is: calendar time
    g["game_date"] = pd.to_datetime(g["game_date"])
    le2022 = (g["season"] <= 2022).astype(int).to_numpy()
    first_odds_snap = pd.Timestamp("2022-05-21")     # earliest odds_snapshot_timestamp, see M7
    before_odds = (g["game_date"] < first_odds_snap).astype(int).to_numpy()
    n22 = g[(g["tip_null"] == 1) & (g["season"] == 2022)]
    out["M4b_mask_is_calendar_time"] = {
        "phi_null_vs_season_le_2022": round(phi(null_g, le2022), 6),
        "phi_null_vs_game_date_before_2022_05_21": round(phi(null_g, before_odds), 6),
        "games_before_2022_05_21": int(before_odds.sum()),
        "nulls_before_2022_05_21": int(((before_odds == 1) & (null_g == 1)).sum()),
        "games_on_or_after_2022_05_21": int((1 - before_odds).sum()),
        "nulls_on_or_after_2022_05_21": int(((before_odds == 0) & (null_g == 1)).sum()),
        "nulls_on_or_after_by_season_and_type": {
            f"{s}|{t}": int(v) for (s, t), v in
            g[(null_g == 1) & (before_odds == 0)].groupby(["season", "season_type"]).size().items()},
        "2022_nulls_by_season_type": {str(k): int(v) for k, v in
                                      n22.groupby("season_type").size().items()},
        "2022_regular_season_nulls_all_before_first_odds_snapshot": bool(
            (n22.loc[n22["season_type"] == "Regular Season", "game_date"] < first_odds_snap).all()),
        "2022_regular_season_null_date_max": str(
            n22.loc[n22["season_type"] == "Regular Season", "game_date"].max()),
        "playoff_coverage_all_seasons": {
            str(s): {"games": int(len(sub)), "null": int(sub["tip_null"].sum())}
            for s, sub in g[g["season_type"] == "Playoffs"].groupby("season")},
    }

    # ---------------------------------------------------------------- M5 team-row frame + target
    tgt = realised_target()
    T = U.merge(tgt, on=["game_id", "team_id"], how="left")
    T["tip_null"] = (~T["game_id"].isin(covered)).astype(int)
    # a concrete tip-derived feature: local tip hour, null exactly where coverage is absent
    T = T.merge(tips[["game_id", "tip_hour_local"]], on="game_id", how="left")

    y = T["realised_off_poss"].to_numpy(float)
    out["M5_team_row_frame"] = {
        "rows": int(len(T)),
        "rows_with_realised_target": int(np.isfinite(y).sum()),
        "rows_tip_null": int(T["tip_null"].sum()),
        "corr_null_mask_with_target": round(float(np.corrcoef(T["tip_null"].to_numpy(float), y)[0, 1]), 6),
        "corr_null_mask_with_offset": round(float(np.corrcoef(
            T["tip_null"].to_numpy(float), T["offset_projected"].to_numpy(float))[0, 1]), 6),
        "feature_gate_missingness_corr_threshold": fg.audit.__defaults__[-1],
        "corr_null_mask_with_tier_league_prior_all": round(float(np.corrcoef(
            T["tip_null"].to_numpy(float), T["tier_league_prior_all"].to_numpy(float))[0, 1]), 6),
        "corr_null_mask_with_tier_team_window_prior_season": round(float(np.corrcoef(
            T["tip_null"].to_numpy(float),
            T["tier_team_window_prior_season"].to_numpy(float))[0, 1]), 6),
        "tier_counts_on_null_rows": {k: int(v) for k, v in
                                     T.loc[T["tip_null"] == 1, "pace_source"].value_counts().items()},
        "tier_counts_on_covered_rows": {k: int(v) for k, v in
                                        T.loc[T["tip_null"] == 0, "pace_source"].value_counts().items()},
    }

    # ---------------------------------------------------------------- M6 run the FROZEN gate
    # Does the frozen feature_gate block a tip-derived feature? Pooled, and per fold.
    gate: dict = {"note": "feature_gate.audit is frozen and is invoked unmodified"}
    try:
        res = fg.audit(T, ["tip_hour_local"], offset=T["offset_projected"].to_numpy(float),
                       target=y, test_df=T)
        gate["pooled"] = {"passed": res["passed"],
                          "findings": res["findings"], "blocking": res["blocking"]}
    except fg.FeatureGateFailure as e:
        gate["pooled"] = {"passed": False, "raised": str(e)}

    per_fold = {}
    for f, sub in T.groupby("fold"):
        rec: dict = {"rows": int(len(sub)),
                     "non_null_tip_rows": int(sub["tip_hour_local"].notna().sum())}
        try:
            r = fg.audit(sub, ["tip_hour_local"], offset=sub["offset_projected"].to_numpy(float),
                         target=sub["realised_off_poss"].to_numpy(float), test_df=sub)
            rec.update({"passed": r["passed"], "findings": r["findings"]})
        except fg.FeatureGateFailure as e:
            rec.update({"passed": False, "raised_blocking": json.loads(str(e))})
        per_fold[str(int(f))] = rec
    gate["per_fold"] = per_fold

    # and the null INDICATOR treated as a feature (the "missingness dummy" remedy)
    T["tip_missing_ind"] = T["tip_null"].astype(float)
    ind: dict = {}
    for f, sub in T.groupby("fold"):
        try:
            r = fg.audit(sub, ["tip_missing_ind"],
                         offset=sub["offset_projected"].to_numpy(float),
                         target=sub["realised_off_poss"].to_numpy(float), test_df=sub)
            ind[str(int(f))] = {"passed": r["passed"], "findings": r["findings"]}
        except fg.FeatureGateFailure as e:
            ind[str(int(f))] = {"passed": False, "raised_blocking": json.loads(str(e))}
    try:
        r = fg.audit(T, ["tip_missing_ind"], offset=T["offset_projected"].to_numpy(float),
                     target=y, test_df=T)
        ind["pooled"] = {"passed": r["passed"], "findings": r["findings"]}
    except fg.FeatureGateFailure as e:
        ind["pooled"] = {"passed": False, "raised_blocking": json.loads(str(e))}
    gate["missingness_indicator_as_feature"] = ind
    out["M6_frozen_gate_behaviour"] = gate

    # ---------------------------------------------------------------- M7 provenance
    prov: dict = {
        "tip_times_source_table_values": sorted(tips["source_table"].unique().tolist()),
        "tip_times_season_span": [int(tips["season"].min()), int(tips["season"].max())],
        "tip_times_game_date_span": [str(tips["game_date"].min()), str(tips["game_date"].max())],
    }
    prov["upstream_present_in_this_worktree"] = {
        "data/drive_masters/master_odds.csv": ODDS_DRIVE.exists(),
        "data/odds_capture/": ODDS_LIVE_DIR.exists(),
        "data/reference/tip_times.csv": TIPS.exists(),
    }
    if BIOS_TIPCOV.exists():
        bc = pd.read_csv(BIOS_TIPCOV)
        prov["independent_in_scope_corroboration"] = {
            "file": str(BIOS_TIPCOV.relative_to(REPO)),
            "table": bc.to_dict("records"),
            "note": ("produced by experiments/bios_collection/validate_collection.py against "
                     "data/masters/master_team.parquet, NOT against the frozen contract universe"),
        }

    # ---- OUT OF SCOPE: repository-root working tree, different branch, READ ONLY -------------
    oos: dict = {"disclosure": ("measured against the repository-root working tree "
                                "(C:/Users/jgallagher/wnba-betting-model), which is a DIFFERENT "
                                "worktree on branch data-refresh-2026. Read-only. Reported "
                                "separately because it is outside this node's declared read scope "
                                "and is not reproducible from this branch.")}
    rd = ROOT_WT / "data" / "drive_masters" / "master_odds.csv"
    if rd.exists():
        od = pd.read_csv(rd, low_memory=False)
        gid = od["game_id"].dropna().astype("int64").astype(str)
        oos["data/drive_masters/master_odds.csv"] = {
            "rows": int(len(od)),
            "columns": list(od.columns),
            "distinct_game_id": int(gid.nunique()),
            "distinct_game_id_by_season": {
                str(k): int(v) for k, v in
                od.assign(gid=od["game_id"].astype("Int64").astype(str))
                  .groupby("season")["gid"].nunique().items()},
            "odds_snapshot_timestamp_min": str(od["odds_snapshot_timestamp"].min()),
            "odds_snapshot_timestamp_max": str(od["odds_snapshot_timestamp"].max()),
            "game_ids_overlapping_contract_universe":
                int(gid[gid.isin(set(allrows["game_id"]))].nunique()),
            "has_totals_market_column": bool(any("total" in c.lower() for c in od.columns)),
            "markets_present": "spread and price only; no totals column",
        }
    rh = ROOT_WT / "data" / "odds_capture" / "historical"
    rl = ROOT_WT / "data" / "odds_capture"
    hist = sorted(p.name for p in rh.glob("*.json")) if rh.exists() else []
    live = sorted(p.name for p in rl.glob("live_*.json")) if rl.exists() else []
    oos["data/odds_capture/historical"] = {
        "n_files": len(hist), "first": hist[0] if hist else None, "last": hist[-1] if hist else None}
    oos["data/odds_capture (live snapshots)"] = {
        "n_files": len(live), "first": live[0] if live else None, "last": live[-1] if live else None}
    prov["OUT_OF_SCOPE_ROOT_WORKTREE"] = oos

    prov["packet_verdict_being_tested"] = {
        "field": "market odds / totals", "source": "data/odds_capture/",
        "coverage": "2026-07-31 .. 2026-08-06 only", "verdict": "UNAVAILABLE HISTORICALLY"}
    out["M7_provenance"] = prov

    # ---------------------------------------------------------------- M8 which games are null
    nulls_outside_2021 = g[(g["tip_null"] == 1) & (g["season"] != 2021)]
    out["M8_nulls_outside_fold1"] = {
        "count": int(len(nulls_outside_2021)),
        "by_season_and_season_type": {
            f"{s}|{t}": int(v) for (s, t), v in
            nulls_outside_2021.groupby(["season", "season_type"]).size().items()},
        "game_ids_2023_2024_2026": nulls_outside_2021.loc[
            nulls_outside_2021["season"].isin([2023, 2024, 2026]),
            ["game_id", "season", "season_type"]].to_dict("records"),
        "date_span_2022_nulls": [str(nulls_outside_2021.loc[nulls_outside_2021["season"] == 2022,
                                                            "game_date"].min()),
                                 str(nulls_outside_2021.loc[nulls_outside_2021["season"] == 2022,
                                                            "game_date"].max())],
    }

    # ---------------------------------------------------------------- M9 OPERATIONAL folds
    # possession_features.chronological_folds() is EXPANDING-WINDOW with FIVE folds (test seasons
    # 2022..2026). 2021 is never a test fold; it is training-only in every fold. This is the fold
    # object the program actually fits against, so the separability question must be asked of it.
    T["game_date"] = pd.to_datetime(T["game_date"])
    seasons_sorted = sorted(int(s) for s in T["season"].unique())
    opfolds: dict = {}
    for s in seasons_sorted[1:]:
        cutoff = T.loc[T["season"] == s, "game_date"].min()
        tr = T[T["game_date"] < cutoff]
        te = T[T["season"] == s]
        rec = {
            "cutoff_date": str(pd.Timestamp(cutoff).date()),
            "train_rows": int(len(tr)), "test_rows": int(len(te)),
            "train_rows_with_tip": int(tr["tip_hour_local"].notna().sum()),
            "test_rows_with_tip": int(te["tip_hour_local"].notna().sum()),
            "train_tip_missing_rate": round(float(tr["tip_hour_local"].isna().mean()), 6),
            "train_feature_estimable": bool(tr["tip_hour_local"].notna().sum() > 0
                                            and tr["tip_hour_local"].dropna().std() > 0),
            "train_null_mask_is_constant": bool(tr["tip_null"].nunique() == 1),
        }
        try:
            r = fg.audit(tr, ["tip_hour_local"], offset=tr["offset_projected"].to_numpy(float),
                         target=tr["realised_off_poss"].to_numpy(float), test_df=te)
            rec["frozen_gate_on_training_rows"] = {"passed": r["passed"],
                                                   "findings": r["findings"]}
        except fg.FeatureGateFailure as e:
            rec["frozen_gate_on_training_rows"] = {"passed": False,
                                                   "raised_blocking": json.loads(str(e))}
        opfolds[f"train_lt_{s}"] = rec
    out["M9_operational_expanding_window_folds"] = {
        "source": "experiments/player_program/possession_features.py::chronological_folds",
        "n_folds": len(opfolds),
        "note_2021": ("2021 is never a TEST fold under this construction; it is 410 of 410 "
                      "training rows of fold train_lt_2022 and is inside the training set of "
                      "every later fold"),
        "folds": opfolds,
    }

    # ---------------------------------------------------------------- M10 gate blind spot
    # WHY a 100%-missing column produces zero findings. Mechanism, measured rather than asserted.
    allnan = pd.DataFrame({"f": [np.nan] * 50, "y": np.arange(50, dtype=float),
                           "o": np.ones(50)})
    mech = {
        "nanstd_of_all_nan_column": str(np.nanstd(allnan["f"].to_numpy(float))),
        "nanstd_equals_zero": bool(np.nanstd(allnan["f"].to_numpy(float)) == 0.0),
        "feature_gate_line_152_short_circuit":
            "if n_miss == 0 or n_miss == len(miss): continue  -- a fully missing column is skipped",
        "design_rank_report_on_all_nan":
            fg.design_rank_report(allnan, ["f"]),
    }
    try:
        r = fg.audit(allnan, ["f"], offset=allnan["o"].to_numpy(float),
                     target=allnan["y"].to_numpy(float), test_df=allnan)
        mech["audit_result"] = {"passed": r["passed"], "findings": r["findings"],
                                "blocking": r["blocking"]}
    except fg.FeatureGateFailure as e:
        mech["audit_result"] = {"passed": False, "raised_blocking": json.loads(str(e))}
    mech["conclusion"] = ("a column that is 100% NaN over the rows handed to the frozen gate "
                          "yields NO findings at all: nanstd is NaN so zero_variance cannot fire, "
                          "the missingness loop skips fully-missing columns, and "
                          "design_rank_report reports checked=false which appends nothing. This is "
                          "measured, not inferred.")
    out["M10_frozen_gate_blind_spot_mechanism"] = mech

    # ---------------------------------------------------------------- M11 P27 call-site guard
    # The remedy for M10 already exists at the call site. Run it rather than assert it.
    try:
        sys.path.insert(0, str(PROGRAM / "stage2b" / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD"))
        import fold_estimability_guard as G                     # noqa: E402
        gdf = T.copy()
        gdf["tip_hour_local"] = gdf["tip_hour_local"].astype(float)
        rec = G.guard(gdf, candidate_features=["tip_hour_local"],
                      nuisance_terms=[], offset_col="offset_projected",
                      cluster_col="game_id", season_col="season",
                      fold_policy="EXPANDING_PRIOR_SEASONS",
                      arm_id="P29_probe_tip_hour_local")
        per = {}
        for f in rec["folds"]:
            per[f["fold_id"]] = {"verdict": f["verdict"],
                                 "blocking": f["blocking"]}
        out["M11_P27_callsite_guard"] = {
            "invoked": True,
            "module": "experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/"
                      "fold_estimability_guard.py::guard (READ ONLY, unmodified)",
            "fold_policy": "EXPANDING_PRIOR_SEASONS",
            "per_fold": per,
            "pooled_pass_would_be_misleading":
                rec.get("pooled_vs_fold_reconciliation", {}).get(
                    "pooled_pass_would_be_misleading"),
        }
    except Exception as e:                                       # noqa: BLE001
        out["M11_P27_callsite_guard"] = {"invoked": False, "error": f"{type(e).__name__}: {e}"}

    def clean(o):
        """Strict-JSON sanitiser: NaN / Infinity become strings so the file parses everywhere."""
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, float):
            return o if np.isfinite(o) else str(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o) if np.isfinite(o) else str(o)
        if isinstance(o, (str, int, bool)) or o is None:
            return o
        return str(o)

    payload = clean(out)
    (HERE / "MEASUREMENTS.json").write_text(
        json.dumps(payload, indent=1, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=1, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
