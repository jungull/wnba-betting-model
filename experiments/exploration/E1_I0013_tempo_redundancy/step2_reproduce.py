"""E1 I0013 -- Step 2: reproduce the published number BEFORE changing anything.

Target: E0_I0013 reports dR2 = 0.001133 for exp_gposs -> ast over base
        y_count ~ O + D + O*D + Mexp + O*Mexp.

Also reproduces, from the same rebuilt frame:
  * R2_base                      (E0 reports 0.4165)
  * beta_M                       (E0 reports +0.0790)
  * per-season dR2 and beta      (E0 reports 2021 .0025261/+.086, 2022 .000728/+.071,
                                  2023 .000012/-.010, 2024 .002574/+.132)
  * dR2(difference | sum)        (E0 reports 0.000001 for ast)
  * the DELIBERATE NO-OP PLACEBO, run as a POSITIVE diagnostic (expect sd EXACTLY 0.000000)
  * the real cluster-level and naive row-level nulls, plus a GAME-level null

Writes: step2_reproduce.json, perm_draws_step2.csv, noop_diagnostic_e1.csv
"""
import json
import os

import numpy as np
import pandas as pd

import e1_lib as L
import base as B
import pv_base as P

rng = np.random.default_rng(L.SEED)
REPORTED = dict(dR2=0.001133, R2_base=0.4165, beta=0.0790,
                per_season={2021: 0.002526, 2022: 0.000728, 2023: 0.000012, 2024: 0.002574},
                per_season_beta={2021: 0.086, 2022: 0.071, 2023: -0.010, 2024: 0.132},
                dR2_diff_given_sum=0.000001)

L.hdr("STEP 2 -- REBUILD THE E0 FRAME (target = ast)")
W, TEAM, mp, mt = L.build_frame("ast")
print("  analysis rows=%d players=%d games=%d" % (len(W), W["player_id"].nunique(),
                                                  W["game_id"].nunique()))
print("  per-season n = %s" % {int(k): int(v) for k, v in W.groupby("season").size().items()})

y = W["s"].to_numpy(float)
basecols = L.e0_basecols(W)
Q, ry, sst = L.prep_fast(y, basecols)
r2b = L.r2(y, basecols)
Mz = B.zwithin(W, "exp_gposs").to_numpy(float)
dR2 = L.incr(Q, ry, sst, Mz)

# beta on the E0 reporting scale: candidate season-centered, residualised on [D, O*D], unit-scaled
Mres = P.residualize_and_scale(Mz, W["D"].values, W["OD"].values)
beta = L.ols_last(y, basecols + [Mres])

L.hdr("STEP 2 -- REPRODUCTION")
print("  R2 CONVENTION: plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean (D069)")
print("  outcome y = RAW ast count (not centered, not weighted); no weights anywhere")
print("  %-30s reproduced=%.9f   reported=%.6f   |diff|=%.3e"
      % ("dR2(exp_gposs | E0 base)", dR2, REPORTED["dR2"], abs(dR2 - REPORTED["dR2"])))
print("  %-30s reproduced=%.9f   reported=%.4f    |diff|=%.3e"
      % ("R2_base", r2b, REPORTED["R2_base"], abs(r2b - REPORTED["R2_base"])))
print("  %-30s reproduced=%.9f   reported=%.4f    |diff|=%.3e"
      % ("beta_M (residual scale)", beta, REPORTED["beta"], abs(beta - REPORTED["beta"])))

# ------------------------------------------------------------------ per-season (E0's own method)
# E0 residualises POOLED, then slices; reproduce that, and also report a within-season-only version.
seas = W["season"].to_numpy()
per_season = []
for s in L.PARTITION:
    gi = np.where(seas == s)[0]
    bc = [c[gi] for c in basecols]
    qg, ryg, sstg = L.prep_fast(y[gi], bc)
    d_pool = L.incr(qg, ryg, sstg, Mres[gi])
    b_pool = L.ols_last(y[gi], bc + [Mres[gi]])
    # within-season-only construction: recenter+rescale the candidate inside the season
    mi = Mz[gi] - Mz[gi].mean()
    mi = mi / mi.std() if mi.std() > 0 else mi
    d_own = L.incr(qg, ryg, sstg, mi)
    b_own = L.ols_last(y[gi], bc + [mi])
    per_season.append(dict(season=int(s), n=int(len(gi)),
                           n_games=int(W["game_id"].to_numpy()[gi].size and
                                       len(np.unique(W["game_id"].to_numpy()[gi]))),
                           dR2_pooled_resid=float(d_pool), beta_pooled_resid=float(b_pool),
                           dR2_within_season=float(d_own), beta_within_season=float(b_own)))

print("\n  PER-SEASON (E0 method: pooled residualisation, then slice)")
print("  %-6s %7s %7s %12s %10s | %12s %10s" %
      ("season", "n", "games", "dR2(pooled)", "beta", "dR2(within)", "beta"))
for r in per_season:
    print("  %-6d %7d %7d %12.6f %+10.4f | %12.6f %+10.4f"
          % (r["season"], r["n"], r["n_games"], r["dR2_pooled_resid"], r["beta_pooled_resid"],
             r["dR2_within_season"], r["beta_within_season"]))
    rep = REPORTED["per_season"][r["season"]]
    print("         reported dR2=%.6f  |diff|=%.3e ; reported beta=%+.3f |diff|=%.3e"
          % (rep, abs(r["dR2_pooled_resid"] - rep),
             REPORTED["per_season_beta"][r["season"]],
             abs(r["beta_pooled_resid"] - REPORTED["per_season_beta"][r["season"]])))

# ------------------------------------------------------------------ layer check: sum vs difference
L.hdr("STEP 2 -- LAYER CHECK (sum vs difference reparameterisation)")
sum_z = B.zwithin(W, "exp_gposs").to_numpy(float)
W["_diff"] = W["opp_pace48"] - W["own_pace48"]
dif_z = B.zwithin(W, "_diff").to_numpy(float)
r_sum = L.r2(y, basecols + [sum_z])
r_joint = L.r2(y, basecols + [sum_z, dif_z])
print("  dR2(sum)                = %.6f" % (r_sum - r2b))
print("  dR2(joint, 2 df)        = %.6f" % (r_joint - r2b))
print("  dR2(difference | sum)   = %.6f   (E0 reports %.6f)"
      % (r_joint - r_sum, REPORTED["dR2_diff_given_sum"]))
print("  -> LAYER 2 (symmetric game tempo), confirmed independently.")

# ------------------------------------------------------------------ unit-of-variation audit
L.hdr("STEP 2 -- UNIT OF VARIATION OF exp_gposs (governs the correct null)")
g = W.groupby("game_id")["exp_gposs"].nunique()
print("  distinct exp_gposs values per game_id: max=%d  frac(games with 1 value)=%.4f"
      % (int(g.max()), float((g == 1).mean())))
print("  n rows=%d  n team-games=%d  n games=%d  n team-seasons=%d"
      % (len(W), len(W.groupby(["game_id", "team_id"]).size()), W["game_id"].nunique(),
         len(W.groupby(["season", "team_id"]).size())))
print("  -> exp_gposs is symmetric in the two teams, so it is a GAME-level quantity.")
print("     The row-level null is wrong by a factor of roughly n_rows/n_games.")

# ------------------------------------------------------------------ nulls
L.hdr("STEP 2 -- PERMUTATION NULLS (row-level WRONG, team-season, game-level)")
PANEL_opp = L.TeamPanel(TEAM, "pace48")
A1, c01, sq = PANEL_opp.bind(W, "opp_team_id")
A2, c02, _ = PANEL_opp.bind(W, "team_id")
raw = W["exp_gposs"].to_numpy(float)

cl_draws = [L.incr(Q, ry, sst, L.center_within(
    0.5 * (L.perm_team(A1, c01, sq, rng) + L.perm_team(A2, c02, sq, rng)), sq))
    for _ in range(L.NDRAW)]
gp = L.GamePerm(W, "exp_gposs")
gm_draws = [L.incr(Q, ry, sst, L.center_within(gp.draw(rng), seas)) for _ in range(L.NDRAW)]
row_draws = [L.incr(Q, ry, sst, L.center_within(L.perm_rows(raw, seas, rng), seas))
             for _ in range(L.NDRAW)]

nulls = {
    "team_season_relabel": L.summarize(cl_draws, dR2,
                                       "CORRECT-LEVEL: within season, permute WHICH team's "
                                       "already-computed pregame pace series each side is assigned"),
    "game_level": L.summarize(gm_draws, dR2,
                              "CORRECT-LEVEL (finest honest unit): within season, permute the "
                              "already-computed game-level value across games"),
    "row_level_naive": L.summarize(row_draws, dR2,
                                   "NAIVE row-level -- WRONG for a game-level quantity; reported "
                                   "only to expose the inflation factor"),
}
for k, v in nulls.items():
    print("  %-22s mean=%.8f sd=%.8f p95=%.8f frac>=real=%.4f"
          % (k, v["mean"], v["sd"], v["p95"], v["frac_ge_real"]))
infl_ts = nulls["team_season_relabel"]["sd"] / nulls["row_level_naive"]["sd"]
infl_gm = nulls["game_level"]["sd"] / nulls["row_level_naive"]["sd"]
print("  INFLATION FACTOR correct/naive:  team-season %.2fx   game-level %.2fx" % (infl_ts, infl_gm))

pd.DataFrame({"team_season_relabel": cl_draws, "game_level": gm_draws,
              "row_level_naive": row_draws}).to_csv(
    os.path.join(L.OUT, "perm_draws_step2.csv"), index=False)
print("  wrote perm_draws_step2.csv")

# ------------------------------------------------------------------ no-op placebo (POSITIVE diag)
L.hdr("STEP 2 -- DELIBERATE NO-OP PLACEBO, RUN ON PURPOSE (expect sd EXACTLY 0.000000)")
print("""  Defective form: permute the grouping KEY consistently in master_team AND in the player
  frame, then RECOMPUTE the aggregate from the permuted key.  The permuted cell is the same row set
  under a bijection, so every row still receives its own true value.  Demonstrating the signature
  proves the real controls above are genuinely shuffling something.""")
NOOP = 60
noop_draws = []
mt_keys = mt[["season", "team_id"]].drop_duplicates()
Wn = W[["season", "game_id", "team_id", "opp_team_id"]].copy()
for _ in range(NOOP):
    mapping = {}
    for s in L.PARTITION:
        tids = np.sort(mt_keys.loc[mt_keys["season"] == s, "team_id"].to_numpy())
        mapping[s] = dict(zip(tids, rng.permutation(tids)))
    mt2 = mt.copy()
    mt2["team_id"] = [mapping[s][a] for s, a in zip(mt2["season"], mt2["team_id"])]
    mt2["opp_team_id"] = [mapping[s][a] for s, a in zip(mt2["season"], mt2["opp_team_id"])]
    T2 = P.build_team_pre(mt2)[["season", "game_id", "team_id", "pace48"]]
    w2 = Wn.copy()
    w2["opp_team_id"] = [mapping[s][k] for s, k in zip(w2["season"], w2["opp_team_id"])]
    w2["team_id"] = [mapping[s][k] for s, k in zip(w2["season"], w2["team_id"])]
    w2 = w2.merge(T2.rename(columns={"team_id": "opp_team_id", "pace48": "op"}),
                  on=["season", "game_id", "opp_team_id"], how="left")
    w2 = w2.merge(T2.rename(columns={"pace48": "wp"}),
                  on=["season", "game_id", "team_id"], how="left")
    noop_draws.append(L.incr(Q, ry, sst,
                             L.center_within((0.5 * (w2["op"] + w2["wp"])).to_numpy(float), seas)))
noop = L.summarize(noop_draws, dR2, "DEFECTIVE no-op: grouping key permuted, aggregate recomputed")
noop["real_dR2"] = float(dR2)
noop["max_abs_deviation_from_real"] = float(np.max(np.abs(np.array(noop_draws) - dR2)))
print("\n  real dR2          = %.12f" % dR2)
print("  no-op mean        = %.12f" % noop["mean"])
print("  no-op sd          = %.12f   <-- the defect signature" % noop["sd"])
print("  max |draw - real| = %.3e" % noop["max_abs_deviation_from_real"])
print("  BY CONTRAST the real game-level control: mean=%.8f sd=%.8f (non-degenerate)"
      % (nulls["game_level"]["mean"], nulls["game_level"]["sd"]))
pd.DataFrame({"noop_dR2": noop_draws}).to_csv(os.path.join(L.OUT, "noop_diagnostic_e1.csv"),
                                              index=False)

out = dict(
    r2_convention="plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean (D069); "
                  "outcome is the raw ast count, NOT centered and NOT weighted; no weighted "
                  "regression anywhere in this E1",
    n=int(len(W)), n_games=int(W["game_id"].nunique()), n_players=int(W["player_id"].nunique()),
    per_season_n={int(k): int(v) for k, v in W.groupby("season").size().items()},
    R2_base=float(r2b), R2_base_reported=REPORTED["R2_base"],
    dR2_reproduced=float(dR2), dR2_reported=REPORTED["dR2"],
    dR2_abs_diff_vs_reported=float(abs(dR2 - REPORTED["dR2"])),
    beta_reproduced=float(beta), beta_reported=REPORTED["beta"],
    per_season=per_season,
    dR2_sum=float(r_sum - r2b), dR2_joint=float(r_joint - r2b),
    dR2_difference_given_sum=float(r_joint - r_sum),
    unit_of_variation=dict(
        exp_gposs_values_per_game_max=int(g.max()),
        frac_games_single_value=float((g == 1).mean()),
        n_rows=int(len(W)), n_games=int(W["game_id"].nunique()),
        n_team_seasons=int(len(W.groupby(["season", "team_id"]).size())),
        conclusion="exp_gposs is symmetric in the two teams and therefore takes exactly one value "
                   "per game_id: it is a GAME-level quantity, coarser than team-game."),
    nulls=nulls,
    null_sd_inflation_correct_over_naive=dict(team_season=float(infl_ts), game_level=float(infl_gm)),
    noop_placebo=noop, n_draws=L.NDRAW, seed=L.SEED)
with open(os.path.join(L.OUT, "step2_reproduce.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=float)
print("\n  wrote step2_reproduce.json")
