#!/usr/bin/env python3
"""run_turnover_p1.py — fit and evaluate `turnover_rate_pooled_baseline_v1`.

Registered before execution. Four pooled arms, one shared team companion, two tracks.
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


def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    P = pd.read_parquet(TGT / "player_turnover_targets_v1.parquet")
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)
    P = P.merge(C, on="game_id", how="left")
    TM = TM.merge(C, on="game_id", how="left")
    PX = pd.read_parquet(HERE / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "regime",
                                  "projected_off_possessions"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime")
    PACE = pd.read_parquet(HERE / "projected_exposure_v1/team_possession_prior_v1.parquet",
                           columns=["game_id", "team_id", "projected_team_off_possessions"])

    P = P.sort_values(["game_date", "game_id", "team_id", "player_id"]).reset_index(drop=True)
    fit = P[P["realised_off_possessions"] > 0].copy()          # zero-exposure excluded from rates

    # ---- chronological pass: one prediction per row from strictly earlier games ---- #
    lg_x = lg_n = 0.0
    car_x, car_n = {}, {}
    sea_x, sea_n = {}, {}
    ew_x, ew_n = {}, {}
    cur_season = None
    rows = []
    for d, day in fit.groupby("game_date", sort=True):
        r_lg = (lg_x / lg_n) if lg_n > 0 else np.nan
        for r in day.itertuples(index=False):
            if r.season != cur_season:
                pass
            key = r.player_id
            out = {"game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                   "game_date": r.game_date, "season": r.season, "turnovers": r.turnovers,
                   "realised_off_possessions": r.realised_off_possessions,
                   "prior_off_possessions": car_n.get(key, 0.0)}
            if np.isnan(r_lg):
                out["eligible"] = False
                rows.append(out); continue
            out["eligible"] = True
            out["A_league_constant"] = r_lg
            cx, cn = car_x.get(key, 0.0), car_n.get(key, 0.0)
            out["B_career_shrunk"] = (cx + EB_PRIOR_K * r_lg) / (cn + EB_PRIOR_K)
            sx, sn = sea_x.get((key, r.season), 0.0), sea_n.get((key, r.season), 0.0)
            out["C_season_shrunk"] = (sx + EB_PRIOR_K * r_lg) / (sn + EB_PRIOR_K)
            ex, en = ew_x.get(key, 0.0), ew_n.get(key, 0.0)
            out["D_ewma_shrunk"] = (ex + EB_PRIOR_K * r_lg) / (en + EB_PRIOR_K)
            rows.append(out)
        # advance history AFTER predicting the whole day
        for r in day.itertuples(index=False):
            k = r.player_id
            x, n = float(r.turnovers), float(r.realised_off_possessions)
            lg_x += x; lg_n += n
            car_x[k] = car_x.get(k, 0.0) + x; car_n[k] = car_n.get(k, 0.0) + n
            sea_x[(k, r.season)] = sea_x.get((k, r.season), 0.0) + x
            sea_n[(k, r.season)] = sea_n.get((k, r.season), 0.0) + n
            ew_x[k] = (1 - EWMA_ALPHA) * ew_x.get(k, 0.0) + x
            ew_n[k] = (1 - EWMA_ALPHA) * ew_n.get(k, 0.0) + n
    R = pd.DataFrame(rows)
    R = R[R["eligible"]].copy()
    for a in ARMS:
        R[a] = R[a].clip(0.0, 1.0)

    # ---- team/unattributed companion: league-pooled prior-games-only ratio -------- #
    TM = TM.sort_values(["game_date", "game_id", "team_id"]).reset_index(drop=True)
    ux = un = 0.0
    ngames = 0
    comp, sup = [], []
    for d, day in TM.groupby("game_date", sort=True):
        rate = (ux / un) if (un > 0 and ngames >= TEAM_MIN_PRIOR_TEAM_GAMES) else np.nan
        for _ in range(len(day)):
            comp.append(rate); sup.append(ngames)
        for r in day.itertuples(index=False):
            ux += float(r.team_unattributed); un += float(r.team_off_possessions or 0)
            ngames += 1
    TM["companion_rate"] = comp
    TM["companion_prior_team_games"] = sup

    # ---- both tracks --------------------------------------------------------------- #
    R = R.merge(PX, on=["game_id", "team_id", "player_id"], how="left")
    both = R[R["projected_off_possessions"].notna()].copy()
    tracks = {}
    for name, expo in (("intrinsic", "realised_off_possessions"),
                       ("operational", "projected_off_possessions")):
        df = R if name == "intrinsic" else both
        d = df.copy()
        for a in ARMS:
            d[f"pred_{a}"] = d[a] * d[expo]
        tracks[name] = d

    def _pois_dev(y, mu):
        mu = np.clip(mu, 1e-9, None)
        t = np.where(y > 0, y * np.log(y / mu), 0.0)
        return float(2 * np.mean(t - (y - mu)))

    def _metrics(d, expo_col):
        y = d["turnovers"].to_numpy(float)
        out = {}
        for a in ARMS:
            mu = d[f"pred_{a}"].to_numpy(float)
            out[a] = {"n": int(len(d)),
                      "poisson_deviance": _pois_dev(y, mu),
                      "player_mae": float(np.mean(np.abs(y - mu))),
                      "player_rmse": float(np.sqrt(np.mean((y - mu) ** 2))),
                      "player_bias": float(np.mean(mu - y))}
        return out

    def _team(d):
        g = d.groupby(["game_id", "team_id"]).agg(
            y=("turnovers", "sum"),
            **{a: (f"pred_{a}", "sum") for a in ARMS}).reset_index()
        return g

    results = {}
    for name, d in tracks.items():
        pm = _metrics(d, None)
        g = _team(d)
        g = g.merge(TM[["game_id", "team_id", "team_unattributed", "companion_rate",
                        "team_off_possessions", "companion_prior_team_games"]],
                    on=["game_id", "team_id"], how="left")
        g = g.merge(PACE, on=["game_id", "team_id"], how="left")
        expo_team = (g["team_off_possessions"] if name == "intrinsic"
                     else g["projected_team_off_possessions"])
        g["companion_pred"] = g["companion_rate"] * expo_team
        ok = g["companion_pred"].notna()
        tm_res, tot_res = {}, {}
        for a in ARMS:
            e = g[a] - g["y"]
            tm_res[a] = {"team_game_mae": float(np.mean(np.abs(e))),
                         "team_game_bias": float(np.mean(e)),
                         "n_team_games": int(len(g))}
            yt = g.loc[ok, "y"] + g.loc[ok, "team_unattributed"]
            pt = g.loc[ok, a] + g.loc[ok, "companion_pred"]
            tot_res[a] = {"total_team_turnover_mae": float(np.mean(np.abs(pt - yt))),
                          "total_team_turnover_bias": float(np.mean(pt - yt)),
                          "n_team_games": int(ok.sum())}
        # paired vs arm A, game-clustered
        paired = {}
        for a in ARMS[1:]:
            dv = np.abs(g["A_league_constant"] - g["y"]) - np.abs(g[a] - g["y"])
            ci = cluster_bootstrap_ci(dv.to_numpy(float), g["game_id"].to_numpy())
            paired[a] = {"team_mae_improvement_vs_A": float(dv.mean()),
                         "ci90": [ci["low"], ci["high"]], "clusters": ci["n_clusters"],
                         "team_games_improved": int((dv > 0).sum()),
                         "team_games_worsened": int((dv < 0).sum())}
        by_season = {}
        for s, sub in d.groupby("season"):
            gg = _team(sub)
            by_season[int(s)] = {a: float(np.mean(np.abs(gg[a] - gg["y"]))) for a in ARMS}
        results[name] = {"player_level": pm, "team_attributed": tm_res,
                         "total_with_companion": tot_res, "paired_vs_A": paired,
                         "by_season_team_mae": by_season,
                         "player_rows": int(len(d)), "team_games": int(len(g))}

    common = set(map(tuple, both[["game_id", "team_id", "player_id"]].to_numpy()))
    out = {
        "schema": "turnover_p1_results/1", "experiment_id": "turnover_rate_pooled_baseline_v1",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "historical development evidence only; promotes nothing",
        "hyperparameters": {"EB_PRIOR_K": EB_PRIOR_K, "EWMA_ALPHA": EWMA_ALPHA,
                            "preregistered_not_learned": True},
        "coverage": {
            "target_rows": int(len(P)),
            "zero_exposure_excluded_from_rates": int((P["realised_off_possessions"] == 0).sum()),
            "rate_eligible_rows": int(len(fit)),
            "predicted_rows_intrinsic": int(len(R)),
            "dropped_no_prior_league_history": int(len(fit) - len(R)),
            "predicted_rows_operational": int(len(both)),
            "operational_loss_no_projected_exposure": int(len(R) - len(both)),
            "common_observation_set": len(common),
            "note": ("intrinsic and operational metrics are reported on their own rows; the "
                     "operational set is a strict subset, so cross-track comparison uses the "
                     "common set only"),
        },
        "companion_component": {
            "policy": "league-pooled prior-games-only team/unattributed rate per team offensive possession",
            "team_games_with_companion": int(TM["companion_rate"].notna().sum()),
            "team_games_without": int(TM["companion_rate"].isna().sum()),
            "identical_across_all_arms": True,
        },
        "results": results,
    }
    (OUT / "TURNOVER_P1_RESULTS.json").write_text(json.dumps(out, indent=2, default=str),
                                                  encoding="utf-8")
    tracks["intrinsic"].to_parquet(OUT / "turnover_p1_predictions_intrinsic.parquet", index=False)
    tracks["operational"].to_parquet(OUT / "turnover_p1_predictions_operational.parquet", index=False)

    for name in ("intrinsic", "operational"):
        r = results[name]
        print(f"\n=== {name} ===  player rows {r['player_rows']:,}  team-games {r['team_games']:,}")
        print(f"{'arm':22s} {'PoisDev':>9s} {'plMAE':>8s} {'plBias':>8s} {'teamMAE':>8s} {'totMAE':>8s}")
        for a in ARMS:
            print(f"{a:22s} {r['player_level'][a]['poisson_deviance']:9.5f} "
                  f"{r['player_level'][a]['player_mae']:8.4f} "
                  f"{r['player_level'][a]['player_bias']:+8.4f} "
                  f"{r['team_attributed'][a]['team_game_mae']:8.4f} "
                  f"{r['total_with_companion'][a]['total_team_turnover_mae']:8.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
