"""
E1 I0008 -- STAGE 1 ADDENDUM. Makes the kill precise rather than merely negative.

Stage 1 killed the headline +0.018-0.020: it sits inside its own permutation null.
The decomposition showed why -- rung*_height_diff = (own height) - (opponent aggregate),
and own height carries essentially all of it. Two follow-ups, both cheap:

  (1) Does the genuinely OPPONENT-SPECIFIC residual (+0.00026 dR2, the part left after own
      height is already in the model) clear ITS OWN noise floor? This distinguishes
      "the lead is 75x smaller than advertised but real" from "there is nothing there."
      Same real control as Stage 1 B1: permute which already-computed opponent aggregate
      each row receives, aggregate itself keyed on true opponents.

  (2) The E0 lead's most specific claim is that the effect is "concentrated in forwards."
      Re-run the decomposition within each position class. If the forward concentration is
      just a stronger own-height gradient within forwards, that claim dies with the headline.

R2 convention: plain unweighted OLS R2 (same as stage1_noise_floor.py).
PARTITION: 2021-2024 only, re-asserted on season column values.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
FORBIDDEN_SEASONS = {2025, 2026}
N_DRAWS = 400
SEED = 771120


def assert_partition(df, name):
    seasons = sorted(int(s) for s in pd.unique(df["season"]))
    print(f"  [partition] {name}: seasons = {seasons}  rows = {len(df)}")
    if FORBIDDEN_SEASONS.intersection(seasons):
        sys.exit(f"PARTITION VIOLATION in {name}")
    return seasons


def ols(y, X):
    n = len(y)
    A = np.column_stack([np.ones(n)] + [X[:, j] for j in range(X.shape[1])])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return (1.0 - ss_res / ss_tot), beta, ss_res


df = pd.read_parquet(os.path.join(OUT, "frame.parquet"))
assert_partition(df, "frame.parquet on load")

TARGETS = [("offensive_rebound_percentage", "own_recent_oreb_pct", "OREB%"),
           ("defensive_rebound_percentage", "own_recent_dreb_pct", "DREB%")]

rng = np.random.default_rng(SEED)
addendum = {}

print()
print("=" * 78)
print("(1) DOES THE OPPONENT-SPECIFIC RESIDUAL CLEAR ITS OWN NOISE FLOOR?")
print("    model: target ~ own_recent_rate + own_height  [+ opponent_roster_aggregate]")
print("=" * 78)

for target, own, tlabel in TARGETS:
    sub = df.dropna(subset=[target, own, "height_inches", "opp_roster_mean_height"]).copy()
    assert_partition(sub, f"rows / {tlabel}")
    y = sub[target].to_numpy(float)
    own_v = sub[own].to_numpy(float)
    own_h = sub["height_inches"].to_numpy(float)
    opp_v = sub["opp_roster_mean_height"].to_numpy(float)
    season_arr = sub["season"].to_numpy()
    opp_arr = sub["opp_team_id"].to_numpy()
    n = len(sub)

    r2_base, _, ssr_base = ols(y, np.column_stack([own_v, own_h]))
    r2_full, beta_full, ssr_full = ols(y, np.column_stack([own_v, own_h, opp_v]))
    real = r2_full - r2_base
    # classical F for the single added regressor
    k_full = 4
    F = ((ssr_base - ssr_full) / 1.0) / (ssr_full / (n - k_full))
    print(f"\n  {tlabel}   n={n}")
    print(f"    R2(own rate + own height)                     = {r2_base:.6f}")
    print(f"    R2(own rate + own height + opponent aggregate) = {r2_full:.6f}")
    print(f"    OPPONENT-SPECIFIC incremental R2 = {real:+.6f}   "
          f"beta_own_height={float(beta_full[2]):+.6f}  beta_opp={float(beta_full[3]):+.6f}")
    print(f"    classical F(1, {n - k_full}) = {F:.3f}   (t = {np.sqrt(F):+.3f})")

    # per-season lookup of the true aggregates
    prof = (sub[["opp_team_id", "season", "opp_roster_mean_height"]]
            .drop_duplicates().rename(columns={"opp_team_id": "team_id",
                                               "opp_roster_mean_height": "prof"}))
    lut = {}
    for s, g in prof.groupby("season"):
        teams = g["team_id"].to_numpy()
        vals = g["prof"].to_numpy(float)
        lut[int(s)] = (teams, vals, {t: i for i, t in enumerate(teams)})
    idx_of_opp = np.empty(n, dtype=int)
    for s in np.unique(season_arr):
        m = season_arr == s
        pos = lut[int(s)][2]
        idx_of_opp[m] = [pos[t] for t in opp_arr[m]]

    draws = np.empty(N_DRAWS)
    for d in range(N_DRAWS):
        fake = np.empty(n)
        for s in np.unique(season_arr):
            m = season_arr == s
            _, vals, _ = lut[int(s)]
            fake[m] = vals[rng.permutation(len(vals))][idx_of_opp[m]]
        r2_f, _, _ = ols(y, np.column_stack([own_v, own_h, fake]))
        draws[d] = r2_f - r2_base
    frac = float((draws >= real).mean())
    print(f"    NULL (permute which already-computed opponent aggregate each row gets), "
          f"{N_DRAWS} draws")
    print(f"      mean = {draws.mean():+.8f}   sd = {draws.std(ddof=0):.8f}   "
          f"max = {draws.max():+.8f}")
    print(f"      frac_ge_real = {frac:.4f}  -> "
          f"{'INSIDE its own noise floor' if frac > 0.05 else 'clears its own noise floor'}")

    addendum[f"opponent_specific|{target}"] = dict(
        n=int(n), r2_own_rate_plus_own_height=r2_base, r2_plus_opponent=r2_full,
        opponent_specific_incremental_r2=real,
        beta_own_height=float(beta_full[2]), beta_opponent_aggregate=float(beta_full[3]),
        F_stat=float(F), t_stat=float(np.sqrt(F)),
        null=dict(draws=N_DRAWS, mean=float(draws.mean()), sd=float(draws.std(ddof=0)),
                  max=float(draws.max()), frac_ge_real=frac),
        clears_null=bool(frac <= 0.05),
    )

print()
print("=" * 78)
print("(2) THE 'CONCENTRATED IN FORWARDS' CLAIM, DECOMPOSED (DREB%, rung1)")
print("=" * 78)
target, own = "defensive_rebound_percentage", "own_recent_dreb_pct"
pos_rows = {}
for pos in ["G", "F", "C"]:
    sub = df[(df["position"] == pos)].dropna(
        subset=[target, own, "rung1_height_diff", "height_inches", "opp_roster_mean_height"]).copy()
    if len(sub) < 200:
        continue
    assert_partition(sub, f"position={pos}")
    y = sub[target].to_numpy(float)
    own_v = sub[own].to_numpy(float)
    own_h = sub["height_inches"].to_numpy(float)
    opp_v = sub["opp_roster_mean_height"].to_numpy(float)
    diff = sub["rung1_height_diff"].to_numpy(float)

    r2_own, _, _ = ols(y, np.column_stack([own_v]))
    r2_diff, _, _ = ols(y, np.column_stack([own_v, diff]))
    r2_oh, _, _ = ols(y, np.column_stack([own_v, own_h]))
    r2_oh_opp, b3, _ = ols(y, np.column_stack([own_v, own_h, opp_v]))
    raw_r = float(np.corrcoef(diff, y)[0, 1])
    print(f"\n  position={pos}  n={len(sub)}   raw corr(height_diff, DREB%) = {raw_r:+.4f}")
    print(f"    dR2 height_diff over own-rate                = {r2_diff - r2_own:+.6f}")
    print(f"    dR2 OWN HEIGHT alone over own-rate           = {r2_oh - r2_own:+.6f}")
    print(f"    dR2 OPPONENT aggregate given own height      = {r2_oh_opp - r2_oh:+.6f}"
          f"   beta_opp={float(b3[3]):+.6f}")
    share = (r2_oh - r2_own) / (r2_diff - r2_own) if (r2_diff - r2_own) != 0 else np.nan
    print(f"    share of the height_diff effect that is OWN HEIGHT = {share:.1%}")
    pos_rows[pos] = dict(n=int(len(sub)), raw_corr_height_diff=raw_r,
                         dr2_height_diff=r2_diff - r2_own,
                         dr2_own_height=r2_oh - r2_own,
                         dr2_opponent_given_own_height=r2_oh_opp - r2_oh,
                         beta_opponent=float(b3[3]),
                         own_height_share_of_effect=float(share),
                         own_height_sd=float(sub["height_inches"].std(ddof=0)))
addendum["position_decomposition_dreb"] = pos_rows

with open(os.path.join(OUT, "stage1_addendum.json"), "w", encoding="utf-8") as fh:
    json.dump(addendum, fh, indent=2)
print("\nwrote stage1_addendum.json")
print("DONE stage1_addendum")
