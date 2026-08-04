#!/usr/bin/env python3
"""addendum_ws7.py -- the ledger's own falsification test, plus the aggregation diagnostic.

The ws7 card falsifies on: "linear and nonlinear indistinguishable, or gains only in fold".
run_ws7.py compares every arm to Arm D. That is the promotion question. It is NOT the
falsification question, which is whether the bounded nonlinear form is distinguishable from its
LINEAR counterpart. This file answers that directly from the saved out-of-fold predictions.

It also explains why player-level error falls while team-level error rises.

No fitting happens here. No new variant is introduced.
"""
from __future__ import annotations
import json, sys                                                                # noqa: E401
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from evalharness.compare import cluster_bootstrap_ci                            # noqa: E402
import register_ws7 as R                                                        # noqa: E402  # noqa

sys.path.insert(0, str(HERE))
import register_ws7 as R                                                        # noqa: E402,F811

PP = HERE.parents[1]

# each bounded nonlinear form and the linear arm it is meant to unmask.
# W2/W4/W5/W6 all extend the single linear involvement term; W1 does too. W3/W3b extend the
# prior-role group, whose only directional term is role_change.
NONLINEAR_VS_LINEAR = {
    "W1_pw_involvement": "L_involvement",
    "W2_rcs_involvement": "L_involvement",
    "W4_inv_x_minutes": "L_involvement",
    "W5_inv_x_support": "L_involvement",
    "W6_partial_pool_tier": "L_involvement",
    "W3b_priorrole_asym": "L_priorrole",
    "W3_expansion_contraction": "L_priorrole",
}


def main() -> int:
    out: dict = {
        "schema": "discovery_ws7_addendum/1",
        "workstream": "ws7_nonlinear_heterogeneous",
        "purpose": ("the ledger falsification test (nonlinear vs its LINEAR counterpart) and the "
                    "aggregation diagnostic explaining the player/team divergence"),
        "sign_convention": "LINEAR abs err MINUS NONLINEAR abs err; POSITIVE = nonlinear beats linear",
        "tracks": {},
    }
    for track in ("intrinsic", "operational"):
        d = pd.read_parquet(HERE / f"ws7_predictions_{track}.parquet")
        ALL = ["A", "D"] + list(R.ARMS)
        g = d.groupby(["game_id", "team_id"]).agg(
            **{a: (f"pred_{a}", "sum") for a in ALL},
            max_abs_rc=("role_change", lambda s: float(np.nanmax(np.abs(s))) if s.notna().any() else np.nan),
        ).reset_index()
        TM = pd.read_parquet(PP / "turnover_targets_v1/team_turnover_reconciliation_v1.parquet")
        g = g.merge(TM[["game_id", "team_id", "player_attributed"]],
                    on=["game_id", "team_id"], how="left")
        g["y"] = g["player_attributed"].fillna(0)

        blk: dict = {"falsification_nonlinear_vs_linear_team": {},
                     "falsification_nonlinear_vs_linear_player": {},
                     "aggregation_diagnostic": {}}

        for nl, lin in NONLINEAR_VS_LINEAR.items():
            dv = (np.abs(g[lin] - g["y"]) - np.abs(g[nl] - g["y"])).to_numpy(float)
            ci = cluster_bootstrap_ci(dv, g["game_id"].to_numpy())
            blk["falsification_nonlinear_vs_linear_team"][nl] = {
                "linear_counterpart": lin, "mean_mae_reduction": float(dv.mean()),
                "ci90": [ci["low"], ci["high"]],
                "distinguishable_at_90": bool(ci["low"] > 0 or ci["high"] < 0)}
            pv = (np.abs(d["turnovers"] - d[f"pred_{lin}"])
                  - np.abs(d["turnovers"] - d[f"pred_{nl}"])).to_numpy(float)
            pci = cluster_bootstrap_ci(pv, d["game_id"].to_numpy())
            blk["falsification_nonlinear_vs_linear_player"][nl] = {
                "linear_counterpart": lin, "mean_mae_reduction": float(pv.mean()),
                "ci90": [pci["low"], pci["high"]],
                "distinguishable_at_90": bool(pci["low"] > 0 or pci["high"] < 0)}

        # ---- aggregation diagnostic ---------------------------------------------------- #
        # why does mean |player error| fall while |team total error| rises?
        ab = g["max_abs_rc"] >= R.RC_ABRUPT
        for a in ["D"] + list(R.ARMS):
            pe = d[f"pred_{a}"] - d["turnovers"]                     # signed player error
            te = g[a] - g["y"]                                       # signed team error
            blk["aggregation_diagnostic"][a] = {
                "player_mean_abs_err": float(np.mean(np.abs(pe))),
                "player_mean_signed_err": float(np.mean(pe)),
                "player_pred_sd": float(np.std(d[f"pred_{a}"])),
                "team_mean_abs_err": float(np.mean(np.abs(te))),
                "team_mean_signed_err": float(np.mean(te)),
                "team_signed_err_abrupt": float(np.mean(te[ab])),
                "team_signed_err_not_abrupt": float(np.mean(te[~ab])),
                "team_abs_err_abrupt": float(np.mean(np.abs(te[ab]))),
            }
        blk["n_team_games_abrupt"] = int(ab.sum())
        blk["n_team_games_not_abrupt"] = int((~ab).sum())
        out["tracks"][track] = blk

    (HERE / "WS7_ADDENDUM.json").write_text(json.dumps(out, indent=2, default=str),
                                            encoding="utf-8")

    for track in ("intrinsic", "operational"):
        b = out["tracks"][track]
        print(f"\n=== {track}: FALSIFICATION TEST -- nonlinear vs its LINEAR counterpart ===")
        print(f"{'nonlinear arm':26s} {'linear':16s} {'team dMAE':>10s} {'ci90':>24s} {'distinct':>9s}"
              f" | {'player dMAE':>11s} {'ci90':>24s} {'distinct':>9s}")
        for nl, e in b["falsification_nonlinear_vs_linear_team"].items():
            p = b["falsification_nonlinear_vs_linear_player"][nl]
            print(f"{nl:26s} {e['linear_counterpart']:16s} {e['mean_mae_reduction']:+10.5f} "
                  f"[{e['ci90'][0]:+.5f},{e['ci90'][1]:+.5f}] {str(e['distinguishable_at_90']):>9s} | "
                  f"{p['mean_mae_reduction']:+11.5f} [{p['ci90'][0]:+.5f},{p['ci90'][1]:+.5f}] "
                  f"{str(p['distinguishable_at_90']):>9s}")
        print(f"\n--- {track}: aggregation diagnostic "
              f"({b['n_team_games_abrupt']} abrupt / {b['n_team_games_not_abrupt']} not) ---")
        print(f"{'arm':26s} {'plAbsE':>8s} {'plSgnE':>8s} {'predSD':>8s} {'tmAbsE':>8s} "
              f"{'tmSgnE':>8s} {'sgn|abrupt':>11s} {'sgn|not':>9s}")
        for a, e in b["aggregation_diagnostic"].items():
            print(f"{a:26s} {e['player_mean_abs_err']:8.4f} {e['player_mean_signed_err']:+8.4f} "
                  f"{e['player_pred_sd']:8.4f} {e['team_mean_abs_err']:8.4f} "
                  f"{e['team_mean_signed_err']:+8.4f} {e['team_signed_err_abrupt']:+11.4f} "
                  f"{e['team_signed_err_not_abrupt']:+9.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
