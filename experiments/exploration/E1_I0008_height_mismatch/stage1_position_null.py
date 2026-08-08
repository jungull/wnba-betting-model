"""
E1 I0008 -- STAGE 1, closing check. Per-position null for the opponent-specific residual.

The pooled opponent-specific residual already failed its null (addendum step 1). This closes
the one obvious remaining question -- "but the E0 lead said the effect is concentrated in
forwards, and the centers cell showed the largest opponent-specific share" -- rather than
leaving it open. These are POST-HOC SUBGROUPS OF AN ALREADY-DEAD EFFECT and are reported with
that caveat; passing here would NOT revive the lead, it would at most define a new, much
smaller, separately-screenable question.

Same real control as everywhere else: permute which already-computed opponent aggregate each
row receives; the aggregate itself stays keyed on true opponents.

R2 convention: plain unweighted OLS R2.  PARTITION: 2021-2024, re-asserted on column values.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
FORBIDDEN = {2025, 2026}
N_DRAWS = 400
rng = np.random.default_rng(31337)


def ols(y, X):
    A = np.column_stack([np.ones(len(y))] + [X[:, j] for j in range(X.shape[1])])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ beta
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum()), beta


df = pd.read_parquet(os.path.join(OUT, "frame.parquet"))
seasons = sorted(int(s) for s in pd.unique(df["season"]))
print("  [partition] frame:", seasons, len(df))
if FORBIDDEN.intersection(seasons):
    sys.exit("PARTITION VIOLATION")

print("\nposition value counts on the frame:")
print(df["position"].value_counts(dropna=False).to_string())
print("\nposition_raw value counts (bios):")
print(df["position_raw"].value_counts(dropna=False).to_string())

out = {}
for target, own, tlabel in [("offensive_rebound_percentage", "own_recent_oreb_pct", "OREB%"),
                            ("defensive_rebound_percentage", "own_recent_dreb_pct", "DREB%")]:
    for pos in ["G", "F", "C"]:
        sub = df[df["position"] == pos].dropna(
            subset=[target, own, "height_inches", "opp_roster_mean_height"]).copy()
        if len(sub) < 200:
            continue
        s_seasons = sorted(int(s) for s in pd.unique(sub["season"]))
        if FORBIDDEN.intersection(s_seasons):
            sys.exit("PARTITION VIOLATION")
        y = sub[target].to_numpy(float)
        base = np.column_stack([sub[own].to_numpy(float), sub["height_inches"].to_numpy(float)])
        opp_v = sub["opp_roster_mean_height"].to_numpy(float)
        r2_base, _ = ols(y, base)
        r2_full, b = ols(y, np.column_stack([base, opp_v]))
        real = r2_full - r2_base

        season_arr = sub["season"].to_numpy()
        opp_arr = sub["opp_team_id"].to_numpy()
        prof = (sub[["opp_team_id", "season", "opp_roster_mean_height"]].drop_duplicates())
        lut = {}
        for s, g in prof.groupby("season"):
            teams = g["opp_team_id"].to_numpy()
            vals = g["opp_roster_mean_height"].to_numpy(float)
            lut[int(s)] = (vals, {t: i for i, t in enumerate(teams)})
        idx = np.empty(len(sub), dtype=int)
        for s in np.unique(season_arr):
            m = season_arr == s
            idx[m] = [lut[int(s)][1][t] for t in opp_arr[m]]

        draws = np.empty(N_DRAWS)
        for d in range(N_DRAWS):
            fake = np.empty(len(sub))
            for s in np.unique(season_arr):
                m = season_arr == s
                vals = lut[int(s)][0]
                fake[m] = vals[rng.permutation(len(vals))][idx[m]]
            r2_f, _ = ols(y, np.column_stack([base, fake]))
            draws[d] = r2_f - r2_base
        frac = float((draws >= real).mean())
        print(f"\n  {tlabel} / position={pos}  n={len(sub)}   "
              f"opponent-specific dR2 = {real:+.6f}  beta_opp={float(b[3]):+.6f}")
        print(f"    null: mean={draws.mean():+.6f} sd={draws.std(ddof=0):.6f} "
              f"max={draws.max():+.6f}  frac_ge_real={frac:.4f}  -> "
              f"{'INSIDE null' if frac > 0.05 else 'clears null (POST-HOC SUBGROUP)'}")
        out[f"{target}|{pos}"] = dict(n=int(len(sub)), opponent_specific_dr2=real,
                                      beta_opp=float(b[3]), null_mean=float(draws.mean()),
                                      null_sd=float(draws.std(ddof=0)),
                                      null_max=float(draws.max()), frac_ge_real=frac,
                                      draws=N_DRAWS)

n_cells = len(out)
n_clear = sum(1 for v in out.values() if v["frac_ge_real"] <= 0.05)
print(f"\n  {n_clear} of {n_cells} post-hoc position cells clear a 0.05 null "
      f"(expected by chance at 0.05: {0.05 * n_cells:.1f})")
with open(os.path.join(OUT, "stage1_position_null.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(cells=out, n_cells=n_cells, n_clearing=n_clear,
                   expected_by_chance=0.05 * n_cells,
                   caveat=("post-hoc subgroups of an effect already killed pooled; no "
                           "multiplicity correction applied; passing here does not revive "
                           "the lead")), fh, indent=2)
print("wrote stage1_position_null.json")
print("DONE stage1_position_null")
