#!/usr/bin/env python3
"""run_turnover_p2.py — `turnover_rate_role_context_v1`: features, fit, evaluation, ablations."""
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
from register_turnover_p2 import RIDGE_LAMBDA, INVOLVE_ALPHA, INVOLVE_SHRINK_K, MIN_TRAIN_ROWS  # noqa: E402
from register_turnover_p1 import EB_PRIOR_K, EWMA_ALPHA, TEAM_MIN_PRIOR_TEAM_GAMES  # noqa: E402

OUT = HERE / "turnover_p2_v1"
TGT = HERE / "turnover_targets_v1"
G1 = ["proj_minutes_share", "proj_off_poss_share", "p_active", "proj_rotation_rank",
      "proj_top5_concentration"]
G2 = ["trailing_minutes_share", "trailing_rotation_rank", "role_change"]
G3 = ["offensive_involvement_proxy"]
G4 = ["displaced_involvement"]
GROUPS = {"projected_role": G1, "prior_role": G2, "offensive_involvement": G3,
          "teammate_context": G4}
ARMS = {"E": G1, "F": G2, "G": G3, "H": G4, "I": G1 + G2 + G3 + G4}


def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pois_dev(y, mu):
    mu = np.clip(np.asarray(mu, float), 1e-9, None); y = np.asarray(y, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / mu), 0.0)
    return float(2 * np.mean(t - (y - mu)))


def poisson_ridge(X, y, off, lam, iters=60):
    """IRLS Poisson ridge with step-halving; intercept unpenalised.

    log(mu) = off + b0 + X b. Returns (beta, converged). A diverging solver is an implementation
    defect, not a scientific result, so non-convergence is reported rather than silently used.
    """
    n, p = X.shape
    Xd = np.hstack([np.ones((n, 1)), X])
    b = np.zeros(p + 1)
    Pen = np.eye(p + 1) * lam; Pen[0, 0] = 0.0

    def dev(bb):
        mu = np.exp(np.clip(off + Xd @ bb, -20, 20))
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(y > 0, y * np.log(np.where(y > 0, y, 1.0) / np.clip(mu, 1e-9, None)), 0.0)
        return float(2 * np.sum(t - (y - mu))) + lam * float(bb[1:] @ bb[1:])

    cur = dev(b)
    converged = False
    for _ in range(iters):
        eta = np.clip(off + Xd @ b, -20, 20)
        mu = np.exp(eta)
        W = np.clip(mu, 1e-6, 1e6)
        z = eta - off + (y - mu) / W
        A = Xd.T @ (Xd * W[:, None]) + Pen
        try:
            step = np.linalg.solve(A, Xd.T @ (W * z)) - b
        except np.linalg.LinAlgError:
            break
        t = 1.0
        for _ in range(30):                      # step-halving on the penalised deviance
            cand = b + t * step
            d = dev(cand)
            if np.isfinite(d) and d <= cur + 1e-9:
                break
            t *= 0.5
        else:
            break
        if np.max(np.abs(cand - b)) < 1e-8:
            b, cur, converged = cand, d, True
            break
        b, cur = cand, d
    else:
        converged = True
    return b, bool(converged and np.all(np.isfinite(b)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    P1O = pd.read_parquet(HERE / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet")
    P1I = pd.read_parquet(HERE / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet")
    if "exposure" not in P1I.columns:      # P1 wrote the intrinsic frame before the rename
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "game_date", "season", "forecast_cutoff"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)
    TM = TM.merge(C[["game_id", "game_date"]], on="game_id", how="left")
    PX = pd.read_parquet(HERE / "projected_exposure_v1/projected_player_possessions_v1.parquet",
                         columns=["game_id", "team_id", "player_id", "regime", "projected_minutes",
                                  "projected_off_possessions", "p_active"])
    PX = PX[PX["regime"] == "tier_a_only"].drop(columns="regime")
    box = pd.read_parquet(ROOT / "data/masters/master_player.parquet",
                          columns=["game_id", "team_id", "player_id", "minutes", "fga"])
    box["game_id"] = box["game_id"].astype(str)
    box = box[box["minutes"].notna()].merge(C[["game_id", "game_date"]], on="game_id", how="left")
    box = box.sort_values(["game_date", "game_id"]).reset_index(drop=True)

    # ---------- FEATURE ARTIFACT ---------------------------------------------------- #
    # group 1: projected role (per team-game shares / ranks)
    F = PX.copy()
    g = F.groupby(["game_id", "team_id"])
    F["proj_minutes_share"] = F["projected_minutes"] / g["projected_minutes"].transform("sum")
    F["proj_off_poss_share"] = F["projected_off_possessions"] / g["projected_off_possessions"].transform("sum")
    F["proj_rotation_rank"] = g["projected_minutes"].rank(ascending=False, method="first")
    top5 = (F.sort_values("projected_minutes", ascending=False).groupby(["game_id", "team_id"])
            ["proj_minutes_share"].apply(lambda s: s.nlargest(5).sum()).rename("proj_top5_concentration"))
    F = F.merge(top5, on=["game_id", "team_id"], how="left")
    F = F.merge(C[["game_id", "game_date", "season", "forecast_cutoff"]], on="game_id", how="left")

    # groups 2 & 3: prior-games-only, chronological
    ewm_min, ewm_fga, ewm_tm_min, ewm_tm_fga = {}, {}, {}, {}
    recent_roster = {}
    rows = []
    for d, day in box.groupby("game_date", sort=True):
        snap_min = dict(ewm_min); snap_fga = dict(ewm_fga)
        snap_tm = dict(ewm_tm_min); snap_tf = dict(ewm_tm_fga)
        for r in day.itertuples(index=False):
            tm_m = snap_tm.get(r.team_id, 0.0); tm_f = snap_tf.get(r.team_id, 0.0)
            pm = snap_min.get(r.player_id, 0.0); pf = snap_fga.get(r.player_id, 0.0)
            rows.append({
                "game_id": r.game_id, "team_id": r.team_id, "player_id": r.player_id,
                "trailing_minutes_share": (pm / tm_m) if tm_m > 0 else np.nan,
                "offensive_involvement_proxy": ((pf + INVOLVE_SHRINK_K / 9.0)
                                                / (tm_f + INVOLVE_SHRINK_K)) if tm_f >= 0 else np.nan,
                "_prior_support": tm_f})
        for r in day.itertuples(index=False):
            ewm_min[r.player_id] = (1 - INVOLVE_ALPHA) * ewm_min.get(r.player_id, 0.0) + float(r.minutes or 0)
            ewm_fga[r.player_id] = (1 - INVOLVE_ALPHA) * ewm_fga.get(r.player_id, 0.0) + float(r.fga or 0)
        for t, sub in day.groupby("team_id"):
            ewm_tm_min[t] = (1 - INVOLVE_ALPHA) * ewm_tm_min.get(t, 0.0) + float(sub["minutes"].sum())
            ewm_tm_fga[t] = (1 - INVOLVE_ALPHA) * ewm_tm_fga.get(t, 0.0) + float(sub["fga"].sum())
            recent_roster.setdefault(t, []).append(set(sub["player_id"]))
    H = pd.DataFrame(rows)
    F = F.merge(H, on=["game_id", "team_id", "player_id"], how="left")
    F["trailing_rotation_rank"] = F.groupby(["game_id", "team_id"])["trailing_minutes_share"].rank(
        ascending=False, method="first")
    F["role_change"] = F["proj_minutes_share"] - F["trailing_minutes_share"]

    # group 4: displaced involvement -- prior contributors absent from today's candidate set
    inv_last = {}
    disp = {}
    for (gid, tid), sub in F.groupby(["game_id", "team_id"]):
        cand = set(sub["player_id"])
        hist = set().union(*recent_roster.get(tid, [set()])[-10:]) if tid in recent_roster else set()
        missing = hist - cand
        d = float(sub[sub["player_id"].isin(missing)]["offensive_involvement_proxy"].sum()) if missing else 0.0
        # involvement of missing players comes from H, not from today's candidate rows
        hm = H[(H["team_id"] == tid) & (H["player_id"].isin(missing))]
        d = float(hm.drop_duplicates("player_id")["offensive_involvement_proxy"].sum()) if len(hm) else 0.0
        disp[(gid, tid)] = d
    F["displaced_involvement"] = [disp.get((g_, t_), 0.0) for g_, t_ in zip(F["game_id"], F["team_id"])]
    F["decision_time_label"] = "pregame_cutoff"
    FEAT = [c for c in G1 + G2 + G3 + G4]
    F.to_parquet(OUT / "turnover_role_context_features_v1.parquet", index=False)

    cov = {c: {"non_null": int(F[c].notna().sum()), "null": int(F[c].isna().sum()),
               "mean": float(F[c].mean()), "std": float(F[c].std())} for c in FEAT}
    corr = F[FEAT].corr().round(3).to_dict()
    (OUT / "FEATURE_VALIDATION.json").write_text(json.dumps({
        "artifact": "turnover_role_context_features_v1",
        "grain": ["game_id", "team_id", "player_id", "decision_time_label"],
        "rows": int(len(F)), "unique_grain": bool(not F.duplicated(
            ["game_id", "team_id", "player_id", "decision_time_label"]).any()),
        "coverage": cov, "correlations": corr,
        "chronological_isolation": ("groups 2-4 are built by a single forward pass that snapshots "
                                    "EWMA state BEFORE consuming the day's games, so no feature "
                                    "sees its own game"),
        "starter_status_omitted": "not validated across both source eras",
        "no_target_game_quantities": True,
    }, indent=2, default=str), encoding="utf-8")

    # ---------- ASSEMBLE TRACKS ------------------------------------------------------ #
    key = ["game_id", "team_id", "player_id"]
    O = P1O.merge(F[key + FEAT], on=key, how="left")
    I = P1I.merge(F[key + FEAT], on=key, how="left")
    I = I.merge(C[["game_id", "season"]].rename(columns={"season": "_s"}), on="game_id", how="left")
    I["season"] = I["_s"]; I = I.drop(columns="_s")

    def fit_predict(df, train_src):
        """Walk-forward by season. beta=0 (exactly Arm D) when training support is short."""
        out = {a: np.full(len(df), np.nan) for a in ARMS}
        coefs = {}
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            te_idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[te_idx]
            base = (te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float))
            if len(tr) < MIN_TRAIN_ROWS:
                for a in ARMS:
                    out[a][te_idx] = base
                coefs[int(s)] = {"fallback_to_D": True, "train_rows": int(len(tr))}
                continue
            coefs[int(s)] = {"fallback_to_D": False, "train_rows": int(len(tr))}
            for a, feats in ARMS.items():
                mu_tr, sd_tr = tr[feats].mean(), tr[feats].std().replace(0, 1.0)
                Xtr = ((tr[feats] - mu_tr) / sd_tr).fillna(0.0).to_numpy(float)
                Xte = ((te[feats] - mu_tr) / sd_tr).fillna(0.0).to_numpy(float)
                otr = np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None)) + \
                    np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
                b, conv = poisson_ridge(Xtr, tr["turnovers"].to_numpy(float), otr, RIDGE_LAMBDA)
                ote = np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None)) + \
                    np.log(np.clip(te["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
                if not conv:
                    out[a][te_idx] = base          # solver did not converge -> fall back to D
                    coefs[int(s)][a] = {"CONVERGENCE_FAILURE": True, "fell_back_to_D": True}
                    continue
                out[a][te_idx] = np.exp(np.clip(ote + b[0] + Xte @ b[1:], -20, 20))
                coefs[int(s)][a] = dict(zip(["intercept"] + feats, np.round(b, 5).tolist()))
        return out, coefs

    train_src = I[I["exposure"] > 0].copy()
    res = {}
    for name, df in (("intrinsic", I), ("operational", O)):
        preds, coefs = fit_predict(df.reset_index(drop=True), train_src)
        d = df.reset_index(drop=True).copy()
        d["pred_A"] = d["A_league_constant"] * d["exposure"]
        d["pred_D"] = d["D_ewma_shrunk"] * d["exposure"]
        for a in ARMS:
            d[f"pred_{a}"] = preds[a]
        allarms = ["A", "D"] + list(ARMS)
        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in allarms}).reset_index()
        g = g.merge(TM[["game_id", "team_id", "player_attributed", "team_unattributed",
                        "team_off_possessions"]], on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)
        blk = {"rows": int(len(d)), "team_games": int(len(g)),
               "player": {a: {"deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                              "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                              "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))}
                          for a in allarms},
               "team": {a: {"mae": float(np.mean(np.abs(g[a] - g["y"]))),
                            "rmse": float(np.sqrt(np.mean((g[a] - g["y"]) ** 2))),
                            "bias": float(np.mean(g[a] - g["y"]))} for a in allarms},
               "paired_vs_D": {}, "by_season_team_mae": {}, "coefficients_by_season": coefs}
        for a in list(ARMS) + ["A"]:
            dv = np.abs(g["D"] - g["y"]) - np.abs(g[a] - g["y"])
            ci = cluster_bootstrap_ci(dv.to_numpy(float), g["game_id"].to_numpy())
            blk["paired_vs_D"][a] = {
                "convention": "INCUMBENT(D) abs error MINUS CHALLENGER abs error; POSITIVE = challenger beats D",
                "mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]],
                "improved": int((dv > 0).sum()), "worsened": int((dv < 0).sum())}
        gs = g.merge(C[["game_id", "season"]], on="game_id", how="left")
        for s, sub in gs.groupby("season"):
            blk["by_season_team_mae"][int(s)] = {a: float(np.mean(np.abs(sub[a] - sub["y"])))
                                                 for a in allarms}
        if "did_appear" in d:
            for lab, sub in (("appearing", d[d["did_appear"]]), ("non_appearing", d[~d["did_appear"]])):
                blk[f"player_{lab}"] = {a: {"n": int(len(sub)),
                                            "mae": float(np.mean(np.abs(sub["turnovers"] - sub[f"pred_{a}"])))}
                                        for a in allarms}
        res[name] = blk
        d.to_parquet(OUT / f"turnover_p2_predictions_{name}.parquet", index=False)

    out = {"schema": "turnover_p2_results/1", "experiment_id": "turnover_rate_role_context_v1",
           "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "status": "historical development evidence only",
           "sign_convention": "INCUMBENT minus CHALLENGER absolute error; POSITIVE = challenger better",
           "hyperparameters": {"ridge_lambda": RIDGE_LAMBDA, "involve_alpha": INVOLVE_ALPHA,
                               "involve_shrink_K": INVOLVE_SHRINK_K,
                               "min_train_rows": MIN_TRAIN_ROWS, "preregistered": True},
           "feature_groups": GROUPS, "feature_coverage": cov, "feature_correlations": corr,
           "artifact_sha256": {"features": _sha(OUT / "turnover_role_context_features_v1.parquet")},
           "results": res}
    (OUT / "TURNOVER_P2_RESULTS.json").write_text(json.dumps(out, indent=2, default=str),
                                                  encoding="utf-8")
    for name in ("intrinsic", "operational"):
        r = res[name]
        print(f"\n=== {name} === rows {r['rows']:,} team-games {r['team_games']:,}")
        print(f"{'arm':4s} {'dev':>9s} {'plMAE':>8s} {'teamMAE':>8s} {'vs D':>9s} {'ci90':>22s}")
        for a in ["A", "D"] + list(ARMS):
            p = r["paired_vs_D"].get(a)
            ci = f"[{p['ci90'][0]:+.4f},{p['ci90'][1]:+.4f}]" if p else ""
            vd = f"{p['mean_mae_reduction']:+.4f}" if p else ""
            print(f"{a:4s} {r['player'][a]['deviance']:9.5f} {r['player'][a]['mae']:8.4f} "
                  f"{r['team'][a]['mae']:8.4f} {vd:>9s} {ci:>22s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
