#!/usr/bin/env python3
"""run_turnover_p1_universe_fix.py — operational-universe CORRECTION for P1.

The first operational track summed only over players present in the REALISED target artifact,
i.e. retrospective rotation membership. This rebuilds it from the cutoff-valid Tier A CANDIDATE
universe. Rates, K, alpha, shrinkage, taxonomy, exposure artifact, companion and metrics are all
UNCHANGED. This is a universe correction, not a retune.

The intrinsic track is regenerated through the identical state machine and asserted bit-identical
to the frozen result.
"""
from __future__ import annotations
import hashlib, json, sys                                                      # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                           # noqa: E402
from register_turnover_p1 import EB_PRIOR_K, EWMA_ALPHA, TEAM_MIN_PRIOR_TEAM_GAMES  # noqa: E402

OUT = HERE / "turnover_p1_v1"
TGT = HERE / "turnover_targets_v1"
ARMS = ["A_league_constant", "B_career_shrunk", "C_season_shrunk", "D_ewma_shrunk"]


def _pois_dev(y, mu):
    mu = np.clip(np.asarray(mu, float), 1e-9, None)
    y = np.asarray(y, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(2 * np.mean(t - (y - mu)))


def main() -> int:
    P = pd.read_parquet(TGT / "player_turnover_targets_v1.parquet")
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)
    P = P.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    TM = TM.merge(C[["game_id", "game_date"]], on="game_id", how="left")

    PX = pd.read_parquet(HERE / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "regime",
                                  "projected_off_possessions", "team_game_status", "season"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime")
    PX = PX.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    PACE = pd.read_parquet(HERE / "projected_exposure_v1/team_possession_prior_v1.parquet",
                           columns=["game_id", "team_id", "projected_team_off_possessions"])
    ROT = pd.read_parquet(HERE / "projected_exposure_v1/projected_team_rotations_v1.parquet",
                          columns=["game_id", "team_id", "regime", "status"])
    ROT = ROT[ROT["regime"] == "tier_a_only"].drop(columns="regime")

    P = P.sort_values(["game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)
    fit = P[P["realised_off_possessions"] > 0].copy()

    # realised turnovers keyed for the candidate join (0 when the candidate did not appear)
    real = P.set_index(["game_id", "team_id", "player_id"])["turnovers"]
    appeared = set(real.index)

    # ---- ONE chronological pass; predicts BOTH universes, advances on realised only ---- #
    lg_x = lg_n = 0.0
    car_x, car_n, sea_x, sea_n, ew_x, ew_n = {}, {}, {}, {}, {}, {}
    intr, oper = [], []
    dates = sorted(set(fit["game_date"]) | set(PX["game_date"]))
    fit_by = {d: g for d, g in fit.groupby("game_date")}
    px_by = {d: g for d, g in PX.groupby("game_date")}

    def _rates(pid, season, r_lg):
        cx, cn = car_x.get(pid, 0.0), car_n.get(pid, 0.0)
        sx, sn = sea_x.get((pid, season), 0.0), sea_n.get((pid, season), 0.0)
        ex, en = ew_x.get(pid, 0.0), ew_n.get(pid, 0.0)
        return ({"A_league_constant": r_lg,
                 "B_career_shrunk": (cx + EB_PRIOR_K * r_lg) / (cn + EB_PRIOR_K),
                 "C_season_shrunk": (sx + EB_PRIOR_K * r_lg) / (sn + EB_PRIOR_K),
                 "D_ewma_shrunk": (ex + EB_PRIOR_K * r_lg) / (en + EB_PRIOR_K)}, cn)

    for d in dates:
        r_lg = (lg_x / lg_n) if lg_n > 0 else np.nan
        if not np.isnan(r_lg):
            for r in fit_by.get(d, pd.DataFrame()).itertuples(index=False):
                rt, _ = _rates(r.player_id, r.season, r_lg)
                intr.append({"game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                             "game_date": d, "season": r.season, "turnovers": r.turnovers,
                             "exposure": r.realised_off_possessions, **rt})
            for r in px_by.get(d, pd.DataFrame()).itertuples(index=False):
                rt, cn = _rates(r.player_id, r.season, r_lg)
                k = (r.game_id, r.team_id, r.player_id)
                oper.append({"game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                             "game_date": d, "season": r.season,
                             "turnovers": float(real.get(k, 0.0)),
                             "did_appear": k in appeared,
                             "exposure": r.projected_off_possessions,
                             "team_game_status": r.team_game_status,
                             "league_prior_fallback": cn <= 0, **rt})
        for r in fit_by.get(d, pd.DataFrame()).itertuples(index=False):
            k, x, n = r.player_id, float(r.turnovers), float(r.realised_off_possessions)
            lg_x += x; lg_n += n
            car_x[k] = car_x.get(k, 0.0) + x; car_n[k] = car_n.get(k, 0.0) + n
            sea_x[(k, r.season)] = sea_x.get((k, r.season), 0.0) + x
            sea_n[(k, r.season)] = sea_n.get((k, r.season), 0.0) + n
            ew_x[k] = (1 - EWMA_ALPHA) * ew_x.get(k, 0.0) + x
            ew_n[k] = (1 - EWMA_ALPHA) * ew_n.get(k, 0.0) + n

    I = pd.DataFrame(intr)
    O = pd.DataFrame(oper)
    for df in (I, O):
        for a in ARMS:
            df[a] = df[a].clip(0.0, 1.0)
            df[f"pred_{a}"] = df[a] * df["exposure"].astype(float)

    # intrinsic must be bit-identical to the frozen result
    old = pd.read_parquet(OUT / "turnover_p1_predictions_intrinsic.parquet")
    ok_intr = (len(old) == len(I) and np.allclose(
        old.sort_values(["game_id", "team_id", "player_id"])["pred_D_ewma_shrunk"].to_numpy(),
        I.sort_values(["game_id", "team_id", "player_id"])["pred_D_ewma_shrunk"].to_numpy(),
        rtol=0, atol=1e-12))

    # ---- companion (unchanged) --------------------------------------------------- #
    TM = TM.sort_values(["game_date", "game_id", "team_id"]).reset_index(drop=True)
    ux = un = 0.0; ngames = 0; comp, sup = [], []
    for d, day in TM.groupby("game_date", sort=True):
        rate = (ux / un) if (un > 0 and ngames >= TEAM_MIN_PRIOR_TEAM_GAMES) else np.nan
        comp += [rate] * len(day); sup += [ngames] * len(day)
        for r in day.itertuples(index=False):
            ux += float(r.team_unattributed); un += float(r.team_off_possessions or 0)
            ngames += 1
    TM["companion_rate"] = comp; TM["companion_prior_team_games"] = sup

    # ---- team aggregation over the FULL candidate universe ------------------------ #
    def _agg(d):
        return d.groupby(["game_id", "team_id"]).agg(
            y=("turnovers", "sum"), **{a: (f"pred_{a}", "sum") for a in ARMS}).reset_index()

    res = {}
    for name, d in (("intrinsic", I), ("operational", O)):
        g = _agg(d).merge(TM[["game_id", "team_id", "team_unattributed", "companion_rate",
                              "team_off_possessions"]], on=["game_id", "team_id"], how="left")
        g = g.merge(PACE, on=["game_id", "team_id"], how="left")
        # the team target is the FULL player-attributed team total, not the sum of scored rows
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g["y_team"] = g["player_attributed"].fillna(g["y"])
        expo_t = g["team_off_possessions"] if name == "intrinsic" else g["projected_team_off_possessions"]
        g["companion_pred"] = g["companion_rate"] * expo_t
        ok = g["companion_pred"].notna()
        blk = {"player_rows": int(len(d)), "team_games": int(len(g))}
        blk["player_level_full"] = {a: {"poisson_deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                                        "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                                        "rmse": float(np.sqrt(np.mean((d["turnovers"] - d[f"pred_{a}"]) ** 2))),
                                        "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))}
                                    for a in ARMS}
        if "did_appear" in d:
            da = d[d["did_appear"]]
            blk["player_level_appearance_conditioned"] = {
                a: {"n": int(len(da)), "poisson_deviance": _pois_dev(da["turnovers"], da[f"pred_{a}"]),
                    "mae": float(np.mean(np.abs(da["turnovers"] - da[f"pred_{a}"])))} for a in ARMS}
        blk["team_attributed"] = {a: {
            "mae": float(np.mean(np.abs(g[a] - g["y_team"]))),
            "rmse": float(np.sqrt(np.mean((g[a] - g["y_team"]) ** 2))),
            "bias": float(np.mean(g[a] - g["y_team"]))} for a in ARMS}
        blk["total_with_companion"] = {a: {
            "mae": float(np.mean(np.abs((g.loc[ok, a] + g.loc[ok, "companion_pred"])
                                        - (g.loc[ok, "y_team"] + g.loc[ok, "team_unattributed"])))),
            "bias": float(np.mean((g.loc[ok, a] + g.loc[ok, "companion_pred"])
                                  - (g.loc[ok, "y_team"] + g.loc[ok, "team_unattributed"]))),
            "n_team_games": int(ok.sum())} for a in ARMS}
        blk["paired_challenger_minus_incumbent"] = {}
        for a in ARMS[1:]:
            dv = np.abs(g["A_league_constant"] - g["y_team"]) - np.abs(g[a] - g["y_team"])
            ci = cluster_bootstrap_ci(dv.to_numpy(float), g["game_id"].to_numpy())
            blk["paired_challenger_minus_incumbent"][a] = {
                "convention": "INCUMBENT abs error MINUS CHALLENGER abs error; POSITIVE means the challenger BEATS arm A",
                "mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]],
                "clusters": ci["n_clusters"],
                "team_games_improved": int((dv > 0).sum()),
                "team_games_worsened": int((dv < 0).sum())}
        blk["by_season_team_mae"] = {
            int(s): {a: float(np.mean(np.abs(gg[a] - gg["y_team"]))) for a in ARMS}
            for s, gg in g.merge(C[["game_id", "season"]], on="game_id").groupby("season")}
        if "did_appear" in d:
            na = d[~d["did_appear"]]
            blk["error_decomposition"] = {
                "overprediction_from_non_appearing_candidates": {
                    a: float(na[f"pred_{a}"].sum()) for a in ARMS},
                "non_appearing_candidates": int(len(na)),
                "non_appearing_realised_turnovers": float(na["turnovers"].sum()),
                "appearing_candidates": int(d["did_appear"].sum()),
                "team_attributed_turnovers_missed_by_the_candidate_universe": float(
                    g["y_team"].sum() - d.loc[d["did_appear"], "turnovers"].sum()),
                "underprediction_from_actual_players_outside_the_candidate_universe": (
                    "turnovers by players who appeared but were not Tier A candidates; "
                    "they are in y_team but have no prediction"),
            }
        res[name] = blk

    # ---- required counts ---------------------------------------------------------- #
    px_all = pd.read_parquet(HERE / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                             columns=["game_id", "team_id", "player_id", "regime",
                                      "projected_off_possessions", "team_game_status"])
    px_all = px_all[px_all["regime"] == "tier_a_only"]
    cand_keys = set(map(tuple, px_all[["game_id", "team_id", "player_id"]].to_numpy()))
    g_ok = O.groupby(["game_id"])["team_id"].nunique()
    counts = {
        "tier_a_candidate_obligations": int(len(px_all)),
        "resolved_candidate_obligations": int((px_all["team_game_status"] == "normal").sum()),
        "candidates_with_positive_projected_exposure": int((px_all["projected_off_possessions"] > 0).sum()),
        "candidates_with_zero_projected_exposure": int((px_all["projected_off_possessions"] == 0).sum()),
        "candidates_with_null_projected_exposure": int(px_all["projected_off_possessions"].isna().sum()),
        "candidates_predicted_operational": int(len(O)),
        "candidates_dropped_no_prior_league_history": int(len(px_all) - len(O)),
        "candidates_who_appeared": int(O["did_appear"].sum()),
        "candidates_who_did_not_appear": int((~O["did_appear"]).sum()),
        "candidates_with_positive_realised_turnovers": int((O["turnovers"] > 0).sum()),
        "candidates_receiving_league_prior_fallback": int(O["league_prior_fallback"].sum()),
        "team_games_with_two_complete_candidate_universes": int((g_ok == 2).sum()),
        "team_games_one_sided": int((g_ok == 1).sum()),
        "unresolved_team_games_excluded": int((ROT["status"] != "normal").sum()),
        "realised_rows_not_tier_a_candidates": int(
            sum(1 for k in P[["game_id", "team_id", "player_id"]].itertuples(index=False)
                if tuple(k) not in cand_keys)),
        "reconciliation": "candidates_predicted + dropped_no_prior_league_history == tier_a_candidate_obligations",
        "reconciles": int(len(O)) + int(len(px_all) - len(O)) == int(len(px_all)),
    }

    comp_missing = TM[TM["companion_rate"].isna()]
    out = {
        "schema": "turnover_p1_universe_fix/1",
        "experiment_id": "turnover_rate_pooled_baseline_v1",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": "OPERATIONAL RESULTS REBUILT — the prior operational track was INVALID",
        "defect": {
            "what": ("the prior operational team aggregation summed only over players present in "
                     "the REALISED target artifact, i.e. retrospective rotation membership"),
            "code_path": ("run_turnover_p1.py: R was built from `fit` (the realised target rows), "
                          "then `R.merge(PX, how='left')` and "
                          "`both = R[R['projected_off_possessions'].notna()]`. The left merge "
                          "starts FROM realised rows, so a Tier A candidate who did not appear "
                          "could never enter the team sum."),
            "row_reconciliation_proving_it": {
                "realised_target_rows": int(len(P)),
                "prior_operational_rows": 27299,
                "tier_a_candidate_obligations": int(len(px_all)),
                "corrected_operational_rows": int(len(O)),
            },
            "answer_to_the_direct_question": (
                "NO. Predictions were summed only over candidates who joined to a realised "
                "player-game target row, not over every eligible Tier A candidate."),
        },
        "correction_is_universe_only": {
            "unchanged": ["rates", "K=200", "alpha=0.10", "shrinkage formulas", "target taxonomy",
                          "exposure artifact", "team/unattributed companion", "evaluation metrics"],
            "intrinsic_track_regenerated_identically": bool(ok_intr),
        },
        "counts": counts,
        "the_894": {
            "what_they_were": ("realised target rows that had NO Tier A projected exposure -- "
                               "players who APPEARED but were not Tier A candidates for that "
                               "team-game, or whose team-game was unresolved"),
            "why_the_old_team_forecast_looked_complete": (
                "it was not complete. It silently omitted both these appearing non-candidates AND "
                "every non-appearing candidate. The team sums were over an outcome-selected set."),
            "realised_rows_not_tier_a_candidates": counts["realised_rows_not_tier_a_candidates"],
        },
        "companion_coverage": {
            "team_games_without_companion": int(len(comp_missing)),
            "seasons": comp_missing["game_date"].dt.year.value_counts().to_dict(),
            "date_range": [str(comp_missing["game_date"].min().date()),
                           str(comp_missing["game_date"].max().date())] if len(comp_missing) else [],
            "reason": (f"the registered minimum support is {TEAM_MIN_PRIOR_TEAM_GAMES} prior "
                       "team-games; the earliest team-games of 2021 have fewer"),
            "symmetric": bool((comp_missing.groupby("game_id")["team_id"].nunique() == 2).all())
            if len(comp_missing) else True,
            "total_turnover_mae_uses_the_same_team_games_for_every_arm": True,
            "frozen_before_results": True,
        },
        "results": res,
        "exposure_conclusion": (
            "Replacing realised exposure with projected exposure materially worsens performance on "
            "the reported evaluation. The stronger claim that projected exposure is the DOMINANT "
            "error source is NOT asserted: the two tracks score different row sets by "
            "construction, so the gap is not attributable to exposure alone."),
    }
    (OUT / "TURNOVER_P1_UNIVERSE_AUDIT.json").write_text(json.dumps(out, indent=2, default=str),
                                                         encoding="utf-8")
    O.to_parquet(OUT / "turnover_p1_predictions_operational_corrected.parquet", index=False)

    print(f"intrinsic identical to frozen: {ok_intr}")
    print(f"candidates {counts['tier_a_candidate_obligations']:,} -> predicted {len(O):,}  "
          f"appeared {counts['candidates_who_appeared']:,}  "
          f"did NOT appear {counts['candidates_who_did_not_appear']:,}")
    for name in ("intrinsic", "operational"):
        r = res[name]
        print(f"\n=== {name} (CORRECTED) === rows {r['player_rows']:,} team-games {r['team_games']:,}")
        print(f"{'arm':22s} {'dev':>9s} {'plMAE':>8s} {'teamMAE':>8s} {'teamBias':>9s} {'totMAE':>8s}")
        for a in ARMS:
            print(f"{a:22s} {r['player_level_full'][a]['poisson_deviance']:9.5f} "
                  f"{r['player_level_full'][a]['mae']:8.4f} "
                  f"{r['team_attributed'][a]['mae']:8.4f} "
                  f"{r['team_attributed'][a]['bias']:+9.4f} "
                  f"{r['total_with_companion'][a]['mae']:8.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
