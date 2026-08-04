#!/usr/bin/env python3
"""run_ws7.py -- discovery workstream ws7_nonlinear_heterogeneous.

Mirrors experiments/player_program/run_turnover_p2.py: Poisson ridge, lambda 10, offset =
log(exposure) + log(frozen Arm D rate) so beta=0 reproduces Arm D exactly, walk-forward by season,
every fold statistic drawn from the training fold only.

The forms are frozen in register_ws7.py. This file MAY NOT define a form.
"""
from __future__ import annotations
import hashlib, json, sys                                                       # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                       # experiments/player_program
ROOT = HERE.parents[3]                     # repo root
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(PP)); sys.path.insert(0, str(ROOT))

import feature_gate                                                             # noqa: E402
from feature_gate import FeatureGateFailure                                      # noqa: E402
from evalharness.compare import cluster_bootstrap_ci                             # noqa: E402
from run_turnover_p2 import poisson_ridge, _pois_dev                             # noqa: E402
import register_ws7 as R                                                         # noqa: E402

OUT = HERE
GATE = HERE / "gate"
P2 = PP / "turnover_p2_v1"
P1 = PP / "turnover_p1_v1"
TGT = PP / "turnover_targets_v1"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------ #
# basis construction. Everything that depends on the data is fitted on `tr` and APPLIED to
# both tr and te. Nothing is ever read off the full history.
# ------------------------------------------------------------------------------------------ #
def _rcs_basis(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Harrell restricted cubic spline, 3 knots -> 1 basis column beyond the linear term."""
    k1, k2, k3 = k
    p = lambda v: np.clip(v, 0.0, None) ** 3                                    # noqa: E731
    return (p(x - k1) - p(x - k2) * (k3 - k1) / (k3 - k2)
            + p(x - k3) * (k2 - k1) / (k3 - k2)) / (k3 - k1) ** 2


def build_basis(arm: str, tr: pd.DataFrame, te: pd.DataFrame):
    """Return (Btr, Bte, colnames, fitted_params). Fitted params come from `tr` ONLY."""
    spec = R.ARMS[arm]["spec"]
    form = R.ARMS[arm]["form"]
    fit: dict = {}

    if form == "linear_control":
        cols = spec["cols"]
        return tr[cols].copy(), te[cols].copy(), list(cols), fit

    if form == "piecewise_linear":
        v = spec["var"]
        xt = tr[v].to_numpy(float)
        kn = np.nanquantile(xt, spec["knot_quantiles"])
        fit["knots"] = [float(z) for z in kn]
        fit["knot_quantiles"] = spec["knot_quantiles"]
        names = [v] + [f"{v}_hinge_{i+1}" for i in range(len(kn))]

        def mk(df):
            x = df[v].to_numpy(float)
            return pd.DataFrame(
                np.column_stack([x] + [np.clip(x - z, 0.0, None) for z in kn]),
                columns=names, index=df.index)
        return mk(tr), mk(te), names, fit

    if form == "restricted_cubic_spline":
        v = spec["var"]
        xt = tr[v].to_numpy(float)
        kn = np.nanquantile(xt, spec["knot_quantiles"])
        fit["knots"] = [float(z) for z in kn]
        fit["knot_quantiles"] = spec["knot_quantiles"]
        names = [v, f"{v}_rcs1"]

        def mk(df):
            x = df[v].to_numpy(float)
            return pd.DataFrame(np.column_stack([x, _rcs_basis(x, kn)]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names, fit

    if form in ("asymmetric_split", "asymmetric_split_plus_group"):
        v = spec["var"]
        extra = spec.get("extra", [])
        names = extra + [f"{v}_expansion", f"{v}_contraction"]
        fit["split"] = "expansion = max(role_change,0); contraction = max(-role_change,0)"

        def mk(df):
            x = df[v].to_numpy(float)
            cols = [df[c].to_numpy(float) for c in extra]
            return pd.DataFrame(np.column_stack(cols + [np.clip(x, 0.0, None),
                                                        np.clip(-x, 0.0, None)]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names, fit

    if form == "interaction":
        a, b = spec["a"], spec["b"]
        names = [a, b, f"{a}_x_{b}"]

        def mk(df):
            va, vb = df[a].to_numpy(float), df[b].to_numpy(float)
            return pd.DataFrame(np.column_stack([va, vb, va * vb]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names, fit

    if form == "partial_pool_continuous_tier":
        v, tv = spec["var"], spec["tier_var"]
        ref = np.sort(tr[tv].dropna().to_numpy(float))          # training-fold ECDF ONLY
        fit["tier_ecdf_n_train"] = int(ref.size)
        fit["tier_ecdf_quartiles"] = [float(z) for z in np.quantile(ref, [.25, .5, .75])] \
            if ref.size else []
        names = [v, f"tier_{tv}", f"{v}_x_tier", f"{v}_x_tier2"]

        def mk(df):
            x = df[v].to_numpy(float)
            t = df[tv].to_numpy(float)
            pct = np.full(t.shape, np.nan)
            m = np.isfinite(t)
            if ref.size:
                pct[m] = np.searchsorted(ref, t[m], side="right") / ref.size
            tier = pct - 0.5                                     # centred percentile in [-.5,.5]
            return pd.DataFrame(np.column_stack([x, tier, x * tier, x * tier * tier]),
                                columns=names, index=df.index)
        return mk(tr), mk(te), names, fit

    raise ValueError(f"unregistered form {form}")


# ------------------------------------------------------------------------------------------ #
def gate_selftest() -> dict:
    """Prove the permanent gate still catches the algebraically identical projected-share pair."""
    F = pd.read_parquet(P2 / "turnover_role_context_features_v1.parquet",
                        columns=R.FORBIDDEN_PAIR)
    try:
        feature_gate.audit(F, R.FORBIDDEN_PAIR)
        return {"gate_caught_forbidden_pair": False,
                "VERDICT": "GATE DEFECT -- the identical pair was not blocked"}
    except FeatureGateFailure as e:
        return {"gate_caught_forbidden_pair": True, "pair": R.FORBIDDEN_PAIR,
                "blocking": json.loads(str(e)),
                "note": "no arm in this workstream includes both columns"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True); GATE.mkdir(parents=True, exist_ok=True)
    prereg = json.loads((HERE / "PREREGISTRATION.json").read_text(encoding="utf-8"))

    selftest = gate_selftest()
    (GATE / "GATE_SELFTEST_forbidden_pair.json").write_text(
        json.dumps(selftest, indent=2), encoding="utf-8")
    if not selftest["gate_caught_forbidden_pair"]:
        print("ABORT: the permanent feature gate failed its own self-test")
        return 2

    # ---------------- inputs, all read-only ---------------- #
    F = pd.read_parquet(P2 / "turnover_role_context_features_v1.parquet")
    P1O = pd.read_parquet(P1 / "turnover_p1_predictions_operational_corrected.parquet")
    P1I = pd.read_parquet(P1 / "turnover_p1_predictions_intrinsic.parquet")
    if "exposure" not in P1I.columns:
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)

    # derived support column -- algebraic inversion of the P2 involvement proxy, no new data
    F["log1p_player_support"] = np.log1p(np.clip(
        F["offensive_involvement_proxy"] * (F["_prior_support"] + R.INVOLVE_SHRINK_K)
        - R.INVOLVE_SHRINK_K / 9.0, 0.0, None))

    FCOLS = ["offensive_involvement_proxy", "trailing_minutes_share", "trailing_rotation_rank",
             "role_change", "proj_minutes_share", "log1p_player_support",
             "proj_top5_concentration", "displaced_involvement"]
    key = ["game_id", "team_id", "player_id"]
    O = P1O.merge(F[key + FCOLS], on=key, how="left")
    I = P1I.merge(F[key + FCOLS], on=key, how="left")
    I = I.merge(C.rename(columns={"season": "_s"}), on="game_id", how="left")
    I["season"] = I["_s"]; I = I.drop(columns="_s")

    train_src = I[I["exposure"] > 0].copy()
    gate_log: dict = {a: {"arm": a, "form": R.ARMS[a]["form"], "folds": {}} for a in R.ARMS}

    # ---------------- walk-forward fit ---------------- #
    def fit_predict(df: pd.DataFrame, track: str):
        out = {a: np.full(len(df), np.nan) for a in R.ARMS}
        coefs: dict = {}
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            te_idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[te_idx]
            base = te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float)
            if len(tr) < R.MIN_TRAIN_ROWS:
                for a in R.ARMS:
                    out[a][te_idx] = base
                coefs[int(s)] = {"fallback_to_D": True, "train_rows": int(len(tr))}
                continue
            coefs[int(s)] = {"fallback_to_D": False, "train_rows": int(len(tr))}
            otr = (np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
            ote = (np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None))
                   + np.log(np.clip(te["D_ewma_shrunk"].to_numpy(float), 1e-9, None)))
            ytr = tr["turnovers"].to_numpy(float)

            for a in R.ARMS:
                Btr, Bte, names, fitp = build_basis(a, tr, te)

                # ---- MANDATORY GATE, before the fit, on the raw training design ---- #
                try:
                    aud = feature_gate.audit(Btr, names, offset=otr, target=ytr, test_df=Bte)
                    aud["passed"] = True
                except FeatureGateFailure as e:
                    gate_log[a]["folds"][f"{track}_{int(s)}"] = {
                        "passed": False, "blocking": json.loads(str(e))}
                    out[a][te_idx] = base
                    coefs[int(s)][a] = {"GATE_BLOCKED": True, "fell_back_to_D": True}
                    continue
                aud["fitted_params_from_training_fold"] = fitp
                aud["train_rows"] = int(len(tr))
                gate_log[a]["folds"][f"{track}_{int(s)}"] = aud

                mu, sd = Btr.mean(), Btr.std().replace(0, 1.0)
                Xtr = ((Btr - mu) / sd).fillna(0.0).to_numpy(float)
                Xte = ((Bte - mu) / sd).fillna(0.0).to_numpy(float)
                b, conv = poisson_ridge(Xtr, ytr, otr, R.RIDGE_LAMBDA)
                if not conv:
                    out[a][te_idx] = base
                    coefs[int(s)][a] = {"CONVERGENCE_FAILURE": True, "fell_back_to_D": True}
                    continue
                out[a][te_idx] = np.exp(np.clip(ote + b[0] + Xte @ b[1:], -20, 20))
                coefs[int(s)][a] = dict(zip(["intercept"] + names, np.round(b, 5).tolist()))
                if fitp:
                    coefs[int(s)][a]["_fold_fitted"] = fitp
        return out, coefs

    ALL = ["A", "D"] + list(R.ARMS)
    res: dict = {}
    for track, df in (("intrinsic", I), ("operational", O)):
        d = df.reset_index(drop=True).copy()
        preds, coefs = fit_predict(d, track)
        d["pred_A"] = d["A_league_constant"] * d["exposure"]
        d["pred_D"] = d["D_ewma_shrunk"] * d["exposure"]
        for a in R.ARMS:
            d[f"pred_{a}"] = preds[a]

        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in ALL}).reset_index()
        # preregistered team-game stratum flags, built from the candidate frame
        flags = d.groupby(["game_id", "team_id"]).agg(
            max_abs_rc=("role_change", lambda s: float(np.nanmax(np.abs(s))) if s.notna().any() else np.nan),
            top5=("proj_top5_concentration", "max"),
            disp=("displaced_involvement", "max")).reset_index()
        g = g.merge(flags, on=["game_id", "team_id"], how="left")
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)

        blk = {
            "rows": int(len(d)), "team_games": int(len(g)),
            "player": {a: {"deviance": _pois_dev(d["turnovers"], d[f"pred_{a}"]),
                           "mae": float(np.mean(np.abs(d["turnovers"] - d[f"pred_{a}"]))),
                           "bias": float(np.mean(d[f"pred_{a}"] - d["turnovers"]))} for a in ALL},
            "team": {a: {"mae": float(np.mean(np.abs(g[a] - g["y"]))),
                         "rmse": float(np.sqrt(np.mean((g[a] - g["y"]) ** 2))),
                         "bias": float(np.mean(g[a] - g["y"]))} for a in ALL},
            "paired_vs_D": {}, "by_season_team_mae": {},
            "team_stratum_vs_D": {}, "player_stratum_vs_D": {},
            "coefficients_by_season": coefs,
        }
        for a in list(R.ARMS) + ["A"]:
            dv = (np.abs(g["D"] - g["y"]) - np.abs(g[a] - g["y"])).to_numpy(float)
            ci = cluster_bootstrap_ci(dv, g["game_id"].to_numpy())
            blk["paired_vs_D"][a] = {
                "convention": "INCUMBENT(D) abs err MINUS CHALLENGER abs err; POSITIVE = challenger beats D",
                "mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]],
                "improved": int((dv > 0).sum()), "worsened": int((dv < 0).sum())}
        gs = g.merge(C, on="game_id", how="left")
        for s, sub in gs.groupby("season"):
            blk["by_season_team_mae"][int(s)] = {a: float(np.mean(np.abs(sub[a] - sub["y"])))
                                                 for a in ALL}

        # ---- preregistered TEAM-GAME strata ---- #
        tmasks = {
            "has_abrupt_change": g["max_abs_rc"] >= R.RC_ABRUPT,
            "no_abrupt_change": ~(g["max_abs_rc"] >= R.RC_ABRUPT),
            "high_displacement": g["disp"] >= R.DISPLACEMENT_HI,
            "low_displacement": g["disp"] < R.DISPLACEMENT_HI,
            "top_heavy": g["top5"] >= R.TOP5_HEAVY,
            "not_top_heavy": g["top5"] < R.TOP5_HEAVY,
        }
        for lab, m in tmasks.items():
            sub = g[m.fillna(False)]
            e = {"n_team_games": int(len(sub)), "D_mae": float(np.mean(np.abs(sub["D"] - sub["y"]))) if len(sub) else None}
            for a in R.ARMS:
                if len(sub) < 30:
                    e[a] = {"insufficient": True}
                    continue
                dv = (np.abs(sub["D"] - sub["y"]) - np.abs(sub[a] - sub["y"])).to_numpy(float)
                ci = cluster_bootstrap_ci(dv, sub["game_id"].to_numpy())
                e[a] = {"mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]]}
            blk["team_stratum_vs_D"][lab] = e

        # ---- preregistered PLAYER strata ---- #
        inv, rc = d["offensive_involvement_proxy"], d["role_change"]
        pmasks = {
            "primary_creator": inv >= R.INV_PRIMARY,
            "secondary_creator": (inv >= R.INV_LOW) & (inv < R.INV_PRIMARY),
            "low_usage": inv < R.INV_LOW,
            "secondary_expanded": (inv >= R.INV_LOW) & (inv < R.INV_PRIMARY) & (rc >= R.RC_EXPAND),
            "role_expansion": rc >= R.RC_EXPAND,
            "role_contraction": rc <= -R.RC_EXPAND,
            "abrupt_change": rc.abs() >= R.RC_ABRUPT,
            "stable_role": rc.abs() < R.RC_ABRUPT,
            "no_prior_history": inv.isna(),
        }
        for lab, m in pmasks.items():
            sub = d[m.fillna(False)]
            e = {"n_rows": int(len(sub)),
                 "D_mae": float(np.mean(np.abs(sub["turnovers"] - sub["pred_D"]))) if len(sub) else None,
                 "mean_turnovers": float(sub["turnovers"].mean()) if len(sub) else None}
            for a in R.ARMS:
                if len(sub) < 100:
                    e[a] = {"insufficient": True}
                    continue
                dv = (np.abs(sub["turnovers"] - sub["pred_D"])
                      - np.abs(sub["turnovers"] - sub[f"pred_{a}"])).to_numpy(float)
                ci = cluster_bootstrap_ci(dv, sub["game_id"].to_numpy())
                e[a] = {"mean_mae_reduction": float(dv.mean()), "ci90": [ci["low"], ci["high"]]}
            blk["player_stratum_vs_D"][lab] = e

        res[track] = blk
        d.to_parquet(OUT / f"ws7_predictions_{track}.parquet", index=False)

    for a in R.ARMS:
        (GATE / f"GATE_{a}.json").write_text(json.dumps(gate_log[a], indent=2, default=str),
                                             encoding="utf-8")

    op = res["operational"]["paired_vs_D"]
    positives = [a for a in R.NEW_VARIANTS if op[a]["ci90"][0] > 0]
    nominal = [a for a in R.NEW_VARIANTS if op[a]["mean_mae_reduction"] > 0]
    out = {
        "schema": "discovery_ws7_results/1",
        "workstream": "ws7_nonlinear_heterogeneous",
        "lane": "DISCOVERY -- development folds only, not promotion evidence",
        "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "preregistration_frozen_utc": prereg["frozen_utc"],
        "sign_convention": "INCUMBENT(D) minus CHALLENGER absolute error; POSITIVE = challenger beats D",
        "primary_metric": "operational team-game MAE",
        "n_new_variants_tested": len(R.NEW_VARIANTS),
        "n_linear_controls": len(R.CONTROLS),
        "multiplicity_statement": prereg["multiplicity_statement"],
        "arms_positive_point_estimate": nominal,
        "arms_ci90_excluding_zero_positive": positives,
        "gate_selftest": selftest,
        "gate_all_arms_passed": all(f.get("passed", False)
                                    for a in R.ARMS for f in gate_log[a]["folds"].values()),
        "input_sha256": {
            "features_p2": _sha(P2 / "turnover_role_context_features_v1.parquet"),
            "p1_operational_corrected": _sha(P1 / "turnover_p1_predictions_operational_corrected.parquet"),
            "p1_intrinsic": _sha(P1 / "turnover_p1_predictions_intrinsic.parquet"),
        },
        "results": res,
    }
    (OUT / "WS7_RESULTS.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    for track in ("intrinsic", "operational"):
        r = res[track]
        print(f"\n=== {track} === rows {r['rows']:,} team-games {r['team_games']:,}")
        print(f"{'arm':26s} {'dev':>9s} {'plMAE':>8s} {'teamMAE':>8s} {'vs D':>9s} {'ci90':>24s}")
        for a in ALL:
            p = r["paired_vs_D"].get(a)
            ci = f"[{p['ci90'][0]:+.5f},{p['ci90'][1]:+.5f}]" if p else ""
            vd = f"{p['mean_mae_reduction']:+.5f}" if p else ""
            print(f"{a:26s} {r['player'][a]['deviance']:9.5f} {r['player'][a]['mae']:8.4f} "
                  f"{r['team'][a]['mae']:8.4f} {vd:>9s} {ci:>24s}")
    print(f"\nnew variants tested: {len(R.NEW_VARIANTS)}   "
          f"positive point estimate: {nominal}   CI excludes 0: {positives}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
