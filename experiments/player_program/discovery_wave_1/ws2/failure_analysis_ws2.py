#!/usr/bin/env python3
"""failure_analysis_ws2.py -- why the responsibility-transfer constructions do not move team MAE.

Every fitted arm carries an UNPENALISED intercept that Arm D does not have, so any arm can beat D
purely by recalibrating the overall rate level. This script fits an intercept-only control arm
("K0", zero features) through the identical pipeline and re-expresses every construction against
it, which isolates the part of the gain that is actually attributable to the transfer mechanism.

It also measures how much of the player-level movement survives aggregation to the team-game grain.
"""
from __future__ import annotations
import json, sys                                                                # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
ROOT = PP.parents[1]
sys.path.insert(0, str(PP)); sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                            # noqa: E402
from register_turnover_p2 import RIDGE_LAMBDA, MIN_TRAIN_ROWS                   # noqa: E402
from run_turnover_p2 import poisson_ridge                                       # noqa: E402
from run_ws2_responsibility_transfer import build_constructions, ARMS, ALLFEAT  # noqa: E402

TGT = PP / "turnover_targets_v1"
CONV = "INCUMBENT abs error MINUS CHALLENGER abs error; POSITIVE = challenger beats the incumbent"


def main() -> int:
    F = build_constructions(pd.read_parquet(
        PP / "turnover_p2_v1/turnover_role_context_features_v1.parquet"))
    P1O = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet")
    P1I = pd.read_parquet(PP / "turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet")
    if "exposure" not in P1I.columns:
        P1I = P1I.rename(columns={"realised_off_possessions": "exposure"})
    C = pd.read_parquet(ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet",
                        columns=["game_id", "season"]).drop_duplicates("game_id")
    C["game_id"] = C["game_id"].astype(str)
    TM = pd.read_parquet(TGT / "team_turnover_reconciliation_v1.parquet")

    key = ["game_id", "team_id", "player_id"]
    O = P1O.merge(F[key + ALLFEAT], on=key, how="left")
    I = P1I.merge(F[key + ALLFEAT], on=key, how="left").merge(
        C.rename(columns={"season": "_s"}), on="game_id", how="left")
    I["season"] = I["_s"]; I = I.drop(columns="_s")
    train_src = I[I["exposure"] > 0].copy()

    # ---- intercept-only control arm, identical pipeline ------------------------------- #
    def fit_k0(df):
        out = np.full(len(df), np.nan)
        for s in sorted(df["season"].unique()):
            tr = train_src[train_src["season"] < s]
            idx = np.where(df["season"].to_numpy() == s)[0]
            te = df.iloc[idx]
            base = te["D_ewma_shrunk"].to_numpy(float) * te["exposure"].to_numpy(float)
            if len(tr) < MIN_TRAIN_ROWS:
                out[idx] = base
                continue
            otr = np.log(np.clip(tr["exposure"].to_numpy(float), 1e-6, None)) + \
                np.log(np.clip(tr["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
            ote = np.log(np.clip(te["exposure"].to_numpy(float), 1e-6, None)) + \
                np.log(np.clip(te["D_ewma_shrunk"].to_numpy(float), 1e-9, None))
            b, conv = poisson_ridge(np.zeros((len(tr), 0)), tr["turnovers"].to_numpy(float),
                                    otr, RIDGE_LAMBDA)
            out[idx] = base if not conv else np.exp(np.clip(ote + b[0], -20, 20))
        return out

    rep: dict = {}
    for name in ("intrinsic", "operational"):
        d = pd.read_parquet(HERE / f"ws2_predictions_{name}.parquet")
        src = I if name == "intrinsic" else O
        d["pred_K0"] = fit_k0(src.reset_index(drop=True))
        arms = ["D", "K0"] + list(ARMS)

        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in arms}).reset_index()
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)

        blk = {"intercept_only_control": {
            "purpose": "K0 has zero features and only the free unpenalised intercept that Arm D "
                       "lacks; it is the level of 'improvement' available from recalibration alone",
            "team_mae": float(np.mean(np.abs(g["K0"] - g["y"]))),
            "player_mae": float(np.mean(np.abs(d["turnovers"] - d["pred_K0"])))}}

        for ref in ("D", "K0"):
            for grain, frame, err_ref, cl in (
                    ("team", g, None, g["game_id"].to_numpy()),
                    ("player", d, None, d["game_id"].to_numpy())):
                slot = blk.setdefault(f"{grain}_paired_vs_{ref}", {})
                yv = frame["y"] if grain == "team" else frame["turnovers"]
                for a in arms:
                    if a == ref:
                        continue
                    pa = frame[a] if grain == "team" else frame[f"pred_{a}"]
                    pr = frame[ref] if grain == "team" else frame[f"pred_{ref}"]
                    dv = (np.abs(pr - yv) - np.abs(pa - yv)).to_numpy(float)
                    ci = cluster_bootstrap_ci(dv, cl)
                    slot[a] = {"convention": CONV, "incumbent": ref,
                               "mean_mae_reduction": float(dv.mean()),
                               "ci90": [ci["low"], ci["high"]],
                               "ci_excludes_zero": bool(ci["low"] > 0 or ci["high"] < 0)}

        # how much player-level movement survives aggregation
        surv = {}
        for a in list(ARMS):
            pl = float((d[f"pred_{a}"] - d["pred_D"]).abs().mean())
            gg = d.groupby(["game_id", "team_id"]).agg(A=(f"pred_{a}", "sum"), Dd=("pred_D", "sum"))
            tm_abs = float((gg.A - gg.Dd).abs().mean())
            tm_signed = float((gg.A - gg.Dd).mean())
            n_per = len(d) / len(gg)
            surv[a] = {"player_mean_abs_delta_vs_D": pl,
                       "team_mean_abs_delta_vs_D": tm_abs,
                       "team_mean_signed_delta_vs_D": tm_signed,
                       "candidates_per_team_game": n_per,
                       "cancellation_ratio": tm_abs / (pl * n_per) if pl > 0 else None,
                       "reads_as": "cancellation_ratio near 1 means the per-player perturbations "
                                   "ADD at the team grain rather than redistributing"}
        blk["aggregation_survival"] = surv
        rep[name] = blk

    out = {"schema": "ws2_failure_analysis/1", "workstream": "ws2_responsibility_transfer",
           "executed_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "sign_convention": CONV, "results": rep}
    (HERE / "WS2_FAILURE_ANALYSIS.json").write_text(json.dumps(out, indent=2, default=str),
                                                    encoding="utf-8")

    for name in ("intrinsic", "operational"):
        b = rep[name]
        print(f"\n=== {name} ===  K0 team MAE {b['intercept_only_control']['team_mae']:.4f} "
              f"| player MAE {b['intercept_only_control']['player_mae']:.4f}")
        print(f"{'arm':5s} {'teamVsD':>9s} {'teamVsK0':>9s} {'ci90 team vs K0':>21s} "
              f"{'plVsD':>9s} {'plVsK0':>9s} {'ci90 player vs K0':>23s}")
        for a in ["K0"] + list(ARMS):
            t0 = b["team_paired_vs_D"][a]["mean_mae_reduction"]
            p0 = b["player_paired_vs_D"][a]["mean_mae_reduction"]
            if a == "K0":
                print(f"{a:5s} {t0:+9.4f} {'':>9s} {'':>21s} {p0:+9.6f}")
                continue
            tk = b["team_paired_vs_K0"][a]; pk = b["player_paired_vs_K0"][a]
            print(f"{a:5s} {t0:+9.4f} {tk['mean_mae_reduction']:+9.4f} "
                  f"[{tk['ci90'][0]:+.4f},{tk['ci90'][1]:+.4f}]".rjust(0).ljust(0).rjust(21)
                  + f" {p0:+9.6f} {pk['mean_mae_reduction']:+9.6f} "
                  f"[{pk['ci90'][0]:+.6f},{pk['ci90'][1]:+.6f}]".rjust(23))
    return 0


if __name__ == "__main__":
    sys.exit(main())
