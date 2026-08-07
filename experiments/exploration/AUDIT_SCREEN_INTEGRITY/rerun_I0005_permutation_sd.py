"""
AUDIT re-run: measure the SPREAD of I0005's permutation null.

I0005's summary.json records the p-value but NOT the null sd, so the no-op diagnostic
(sd == exactly 0) cannot be read off the shipped artifacts. This is a COPY of the
permutation block from
  experiments/exploration/E0_I0005_turnover_interaction/analyze.py  (lines 60-94)
with the input read READ-ONLY and ALL output repointed into AUDIT_SCREEN_INTEGRITY/.
Nothing in the original screen directory is touched.

Same seed (20260807) and same n_perm (2000) as the original, so the null is reproduced
exactly, not merely resembled.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
SRC = os.path.join(ROOT, "experiments", "exploration", "E0_I0005_turnover_interaction",
                   "player_game_analysis.csv")           # READ ONLY
HERE = os.path.join(ROOT, "experiments", "exploration", "AUDIT_SCREEN_INTEGRITY")

df = pd.read_csv(SRC)
assert set(df["season"].unique()).issubset({2021, 2022, 2023, 2024}), "PARTITION VIOLATION"
print("rows:", len(df), "seasons:", sorted(df["season"].unique()))

Y = df["turnovers_per_100_off_poss"].to_numpy(float)
X1 = df["player_tendency_loo"].to_numpy(float)
X2 = df["opponent_pressure_loo"].to_numpy(float)


def design(*cols):
    return np.column_stack([np.ones(len(cols[0]))] + list(cols))


def residualize(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta


inter = X1 * X2
Xadd = design(X1, X2)
obs_stat = float(np.corrcoef(residualize(Y, Xadd), residualize(inter, Xadd))[0, 1])
print(f"observed partial correlation: {obs_stat:.6f}")

rng = np.random.default_rng(20260807)
n_perm = 2000
season_arr = df["season"].to_numpy()
null_stats = np.empty(n_perm)
for i in range(n_perm):
    X1_perm = X1.copy()
    for s in np.unique(season_arr):
        idx = np.where(season_arr == s)[0]
        X1_perm[idx] = rng.permutation(X1_perm[idx])
    inter_perm = X1_perm * X2
    Xadd_perm = design(X1_perm, X2)
    null_stats[i] = np.corrcoef(residualize(Y, Xadd_perm),
                                residualize(inter_perm, Xadd_perm))[0, 1]

p = float(np.mean(np.abs(null_stats) >= abs(obs_stat)))
out = {
    "n_perm": n_perm,
    "observed_partial_corr": obs_stat,
    "null_mean": float(null_stats.mean()),
    "null_sd": float(null_stats.std()),
    "null_min": float(null_stats.min()),
    "null_max": float(null_stats.max()),
    "null_n_unique": int(len(np.unique(null_stats))),
    "p_two_sided_reproduced": p,
    "p_two_sided_in_shipped_summary_json": 0.004,
    "no_op_signature_present": bool(float(null_stats.std()) == 0.0),
}
print(json.dumps(out, indent=2))
with open(os.path.join(HERE, "rerun_I0005_permutation_sd.json"), "w") as f:
    json.dump(out, f, indent=2)
print("\nwrote rerun_I0005_permutation_sd.json")
