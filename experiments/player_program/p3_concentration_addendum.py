#!/usr/bin/env python3
"""p3_concentration_addendum.py — complete the registered concentration reporting.

The registration required reporting whether any apparent gain is concentrated in one season, one
TEAM, HIGH-EXPOSURE PLAYERS or a small number of games. The first and last were reported; the
per-team and per-player-exposure breakdowns were not. This adds them.

No arm, universe, coefficient or allocation is touched. This reads the frozen result rows and
recomputes only descriptive breakdowns, then appends them to the result receipt under
``concentration_addendum``.

Run::

    python experiments/player_program/p3_concentration_addendum.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import run_p3_downstream as R  # noqa: E402

OUT = HERE / "p3_downstream_v1"
RESULTS = OUT / "P3_DOWNSTREAM_RESULTS.json"
ROWS = OUT / "p3_downstream_rows.parquet"
ARMS = R.ARMS


def main() -> int:
    rows = pd.read_parquet(ROWS)
    res = json.loads(RESULTS.read_text(encoding="utf-8"))

    preds = R.arm_predictions(rows)
    ph = rows["team_pts_h"].to_numpy(float)
    pa = rows["team_pts_a"].to_numpy(float)
    margin_true = ph - pa
    base_err = np.abs(margin_true - (preds["A_incumbent"][0] - preds["A_incumbent"][1]))

    # ---- per-club concentration -------------------------------------------------- #
    per_team = {}
    for arm in ARMS:
        if arm == "A_incumbent":
            continue
        h, a = preds[arm]
        d = base_err - np.abs(margin_true - (h - a))          # positive == arm better
        long = pd.concat([
            pd.DataFrame({"team_id": rows["team_id_h"].to_numpy(), "d": d}),
            pd.DataFrame({"team_id": rows["team_id_a"].to_numpy(), "d": d}),
        ], ignore_index=True)
        g = long.groupby("team_id")["d"].agg(["size", "sum", "mean"]).sort_values("sum")
        total = float(g["sum"].sum())
        top = g.sort_values("sum", ascending=False)
        per_team[arm] = {
            "clubs": int(len(g)),
            "total_margin_improvement_points_double_counted": total,
            "clubs_with_positive_mean": int((g["mean"] > 0).sum()),
            "clubs_with_negative_mean": int((g["mean"] < 0).sum()),
            "best_three": [{"team_id": int(i), "games": int(r["size"]),
                            "mean_improvement": round(float(r["mean"]), 4)}
                           for i, r in top.head(3).iterrows()],
            "worst_three": [{"team_id": int(i), "games": int(r["size"]),
                             "mean_improvement": round(float(r["mean"]), 4)}
                            for i, r in top.tail(3).iterrows()],
            "share_of_positive_total_from_top_club": (
                round(float(top["sum"].iloc[0] / top.loc[top["sum"] > 0, "sum"].sum()), 4)
                if (top["sum"] > 0).any() else None),
        }

    # ---- high-exposure-player concentration -------------------------------------- #
    players = pd.read_parquet(R.EXPOSURE)
    p3 = pd.read_parquet(R.P3)
    pl = players[players["regime"] == R.PRIMARY_REGIME][
        ["game_id", "team_id", "player_id", "season", "projected_off_possessions"]].copy()
    pl["cutoff"] = pl["season"] - 1
    pl = pl.merge(p3.rename(columns={"training_cutoff_season": "cutoff"})[
        ["cutoff", "player_id", "net_rapm_100"]], on=["cutoff", "player_id"], how="left")
    pl["net_rapm_100"] = pl["net_rapm_100"].fillna(0.0)
    pl["c_net"] = pl["net_rapm_100"] * pl["projected_off_possessions"] / 100.0
    top_player = (pl.assign(a=pl["c_net"].abs())
                  .groupby(["game_id", "team_id"])["a"].max().rename("top_player_abs_pts")
                  .reset_index())

    for side in ("h", "a"):
        rows = rows.merge(top_player.rename(columns={
            "team_id": f"team_id_{side}", "top_player_abs_pts": f"toppl_{side}"}),
            on=["game_id", f"team_id_{side}"], how="left")
    rows["_toppl"] = rows[["toppl_h", "toppl_a"]].max(axis=1)

    lab = pd.qcut(rows["_toppl"], 3, labels=["low", "mid", "high"])
    exposure_buckets = {}
    for b, sub in rows.groupby(lab, observed=True):
        p2 = R.arm_predictions(sub)
        r2 = R.evaluate(sub, p2)
        exposure_buckets[str(b)] = {
            "n_games": int(len(sub)),
            "largest_single_player_adjustment_points": [round(float(sub["_toppl"].min()), 3),
                                                        round(float(sub["_toppl"].max()), 3)],
            "margin_mae": {a: round(r2[a]["margin_mae"], 4) for a in ARMS},
        }

    res["concentration_addendum"] = {
        "note": ("completes the registered requirement to report concentration by TEAM and by "
                 "HIGH-EXPOSURE PLAYERS. No arm, universe or allocation was changed."),
        "per_club": per_team,
        "high_exposure_player_buckets": {
            "definition": ("games bucketed by the largest single-player absolute net personnel "
                           "contribution, in points, across the two clubs"),
            "buckets": exposure_buckets,
        },
    }
    RESULTS.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    print("per-club concentration (margin improvement, points):")
    for arm, d in per_team.items():
        print(f"  {arm:26s} clubs+{d['clubs_with_positive_mean']:3d} "
              f"clubs-{d['clubs_with_negative_mean']:3d}  "
              f"top-club share of positive total {d['share_of_positive_total_from_top_club']}")
    print("\nhigh-exposure-player buckets (margin MAE):")
    for b, d in exposure_buckets.items():
        print(f"  {b:5s} n={d['n_games']:3d} range={d['largest_single_player_adjustment_points']} "
              f"A={d['margin_mae']['A_incumbent']:.4f} C={d['margin_mae']['C_net']:.4f} "
              f"E={d['margin_mae']['E_defensive_diagnostic']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
