"""
E1 I0012 -- SUPPLEMENT to run_drop2021.py.

run_drop2021.py answered the worklist question (does 2022-2024 still decay: YES). This
supplement answers the follow-on that decides what a confirmation run would actually face:
how much of the 2022-2024 pooled effect survives if you drop the OLDEST remaining season
too, i.e. what is left in the seasons nearest the holdout.

  D1  2023-2024 pooled dR2_OxM + placebo
  D2  2024 alone  pooled dR2_OxM + placebo   (the season immediately before the holdout)

PARTITION: 2022/2023/2024 only. The 2025/2026 confirmation holdout is never read, joined,
filtered, counted, plotted or described.  R2 convention: plain unweighted OLS (E0 convention).
WRITE SCOPE: this directory only; base.OUT re-pointed here defensively.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

E0 = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0012_layer3_noncollinear"
OUTDIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0012_survivor_2021drop"
sys.path.insert(0, E0)

import base as B                 # noqa: E402
import f34_style_rest as F       # noqa: E402

B.OUT = OUTDIR
F.B.OUT = OUTDIR

DIM, TARGET = "dpace", "reb"
HOLDOUT_FORBIDDEN = {2025, 2026}
N_PERM = 400


def guard(df, label, allowed):
    s = sorted(int(x) for x in pd.unique(df["season"]))
    print("  [PARTITION] %-34s seasons=%s  n=%d" % (label, s, len(df)))
    assert not (set(s) & HOLDOUT_FORBIDDEN), "HOLDOUT TOUCHED at %s" % label
    assert set(s) <= set(allowed), "PARTITION VIOLATION at %s: %s" % (label, s)
    return df


def main():
    seasons_all = [2022, 2023, 2024]
    B.PARTITION = list(seasons_all)     # # FILTER-POINT
    F.B.PARTITION = list(seasons_all)
    B.hdr("SUPPLEMENT -- recency slices of the survivor (dpace x own rebound rate, reb)")
    mp = guard(B.load_player(), "master_player after load", seasons_all)
    mt = guard(B.load_team(), "master_team after load", seasons_all)
    played = mp[(mp["minutes"].fillna(0) > 0) & (mp["possessions"] > 0)].copy()
    STY, _ = F.build_team_style(mt)
    PS = F.player_style(played)
    opp_sty = STY.rename(columns={"team_id": "opp_team_id"}).drop(columns=["game_id"])
    d = B.build_base(played, TARGET)
    d = d.merge(opp_sty, on=["season", "opp_team_id", "gdate"], how="left")
    d = d.merge(PS, on=["season", "game_id", "player_id"], how="left")
    guard(d, "merged feature frame", seasons_all)

    rng = np.random.default_rng(B.SEED)
    res = {}
    for label, seas in [("2023_2024", [2023, 2024]), ("2024_alone", [2024])]:
        B.hdr("slice = %s" % label)
        sub = d[d["season"].isin(seas)].copy()      # # FILTER-POINT
        guard(sub, "slice frame " + label, seas)
        w = B.prep_frame(sub, extra_required=[DIM])
        guard(w, "analysis frame " + label, seas)
        eff = B.screen_increment(w, DIM, label, seasons=list(seas))
        rows = {r["scope"]: r for r in eff["rows"]}
        print("  PLACEBO (%d perms):" % N_PERM)
        plc, V = F.placebo(w, DIM, rng, n=N_PERM)
        V.assign(slice=label).to_csv(
            os.path.join(OUTDIR, "placebo_draws_%s.csv" % label), index=False)
        key = "POOLED" if "POOLED" in rows else str(seas[0])
        res[label] = {
            "seasons": [int(s) for s in seas],
            "n": int(rows[key]["n"]),
            "pooled_dR2_OxM": float(rows[key]["dR2_OxM"]),
            "pooled_beta_OxM": float(rows[key]["beta_OxM"]),
            "per_season_beta_OxM": {r["scope"]: float(r["beta_OxM"])
                                    for r in eff["rows"] if r["scope"] != "POOLED"},
            "placebo": plc, "placebo_n_perm": N_PERM,
            "placebo_degenerate": bool(plc["dR2_OxM"]["sd"] == 0.0)}

    B.hdr("SUPPLEMENT SUMMARY")
    for k, v in res.items():
        print("  %-12s n=%5d  pooled dR2_OxM=%.6f  beta=%+.4f  placebo mean=%.7f sd=%.7f "
              "frac>=real=%.3f" % (k, v["n"], v["pooled_dR2_OxM"], v["pooled_beta_OxM"],
                                   v["placebo"]["dR2_OxM"]["mean"], v["placebo"]["dR2_OxM"]["sd"],
                                   v["placebo"]["dR2_OxM"]["frac_ge"]))
    with open(os.path.join(OUTDIR, "results_recency.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    print("\n  wrote results_recency.json")
    return res


if __name__ == "__main__":
    main()
