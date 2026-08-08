"""
E0 I0009 -- four-rung screen of the ADDITIVE opponent-pressure hypothesis.

Rung 1: idealised (season leave-one-out) opponent pressure -- pooled AND per season.
Rung 2: pregame-observable (strictly-before-date expanding) opponent pressure -- the one that matters.
Rung 3: placebo -- permuted opponent identity within season, same construction, noise floor.
Rung 4: is the predictor itself forecastable? (season-over-season and split-half persistence)
Confound: does pressure survive an opponent-quality (points allowed per 100 def poss) control?

Reads only the already-partition-filtered CSVs written by build_data.py.
Deterministic: seed fixed below.
"""
import json
import numpy as np
import pandas as pd

from pressure_lib import PregamePressure, EXPLORATION_SEASONS

OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0009_additive_pressure"
SEED = 20260807
N_PERM = 200

df = pd.read_csv(f"{OUT}/player_game_analysis.csv", parse_dates=["game_date"])
tg = pd.read_csv(f"{OUT}/team_game_defense.csv", parse_dates=["game_date"])
assert set(df["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert set(tg["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
print("rows:", len(df), "seasons:", sorted(df["season"].unique()))
print("team-game rows:", len(tg), "seasons:", sorted(tg["season"].unique()))

Y = df["turnovers_per_100_off_poss"].to_numpy(float)
X1 = df["player_tendency_loo"].to_numpy(float)
P_LOO = df["opponent_pressure_loo"].to_numpy(float)
P_PRE = df["opponent_pressure_pregame"].to_numpy(float)
D_LOO = df["opponent_defrtg_loo"].to_numpy(float)
D_PRE = df["opponent_defrtg_pregame"].to_numpy(float)
W = df["realised_off_possessions"].to_numpy(float)
S = df["season"].to_numpy()


def wls_r2(y, X, w):
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    yw = y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    sse = float(resid @ resid)
    sst = float(((yw - yw.mean()) ** 2).sum())
    return beta, (1 - sse / sst if sst > 0 else np.nan)


def design(*cols):
    return np.column_stack([np.ones(len(cols[0]))] + list(cols))


def delta_r2(base_cols, add_col, mask=None):
    """R2 gain from adding add_col to a model containing base_cols (+ intercept)."""
    if mask is None:
        mask = np.ones(len(Y), dtype=bool)
    bc = [c[mask] for c in base_cols]
    _, r2_base = wls_r2(Y[mask], design(*bc), W[mask])
    beta, r2_full = wls_r2(Y[mask], design(*bc, add_col[mask]), W[mask])
    return r2_base, r2_full, r2_full - r2_base, beta[-1]


results = {}
SEASONS = sorted(df["season"].unique())

# ===========================================================================
# RUNG 1 -- idealised additive effect (season LOO opponent pressure)
# ===========================================================================
print("\n" + "=" * 78)
print("RUNG 1 -- idealised additive effect: tendency(LOO) -> + opponent pressure(LOO)")
print("=" * 78)
r2b, r2f, d, beta = delta_r2([X1], P_LOO)
print(f"POOLED  n={len(Y)}  R2 {r2b:.5f} -> {r2f:.5f}   dR2 = {d:.6f}   beta_pressure = {beta:+.4f}")
results["rung1_pooled"] = {"n": int(len(Y)), "r2_base": r2b, "r2_full": r2f, "dR2": d, "beta": beta}
results["rung1_per_season"] = {}
for s in SEASONS:
    m = S == s
    r2b_s, r2f_s, d_s, b_s = delta_r2([X1], P_LOO, m)
    print(f"  season {s}  n={int(m.sum()):5d}  R2 {r2b_s:.5f} -> {r2f_s:.5f}   dR2 = {d_s:.6f}   beta = {b_s:+.4f}")
    results["rung1_per_season"][int(s)] = {"n": int(m.sum()), "dR2": d_s, "beta": b_s}

spread = P_LOO.max() - P_LOO.min()
print(f"  practical size: opponent LOO pressure spans {P_LOO.min():.2f}-{P_LOO.max():.2f} per 100 "
      f"(range {spread:.2f}); pooled beta implies {beta * spread:+.3f} turnovers/100 off poss "
      f"end-to-end (outcome mean {Y.mean():.3f}).")

# ===========================================================================
# RUNG 2 -- pregame-observable version
# ===========================================================================
print("\n" + "=" * 78)
print("RUNG 2 -- PREGAME observable: tendency(LOO) -> + opponent pressure(pregame, expanding)")
print("=" * 78)
r2b2, r2f2, d2, beta2 = delta_r2([X1], P_PRE)
print(f"POOLED  n={len(Y)}  R2 {r2b2:.5f} -> {r2f2:.5f}   dR2 = {d2:.6f}   beta_pressure = {beta2:+.4f}")
results["rung2_pooled"] = {"n": int(len(Y)), "r2_base": r2b2, "r2_full": r2f2, "dR2": d2, "beta": beta2}
results["rung2_per_season"] = {}
for s in SEASONS:
    m = S == s
    r2b_s, r2f_s, d_s, b_s = delta_r2([X1], P_PRE, m)
    print(f"  season {s}  n={int(m.sum()):5d}  R2 {r2b_s:.5f} -> {r2f_s:.5f}   dR2 = {d_s:.6f}   beta = {b_s:+.4f}")
    results["rung2_per_season"][int(s)] = {"n": int(m.sum()), "dR2": d_s, "beta": b_s}

spread2 = P_PRE.max() - P_PRE.min()
print(f"  practical size: pregame pressure spans {P_PRE.min():.2f}-{P_PRE.max():.2f} "
      f"(range {spread2:.2f}); pooled beta implies {beta2 * spread2:+.3f} turnovers/100 end-to-end.")

# ===========================================================================
# RUNG 3 -- PLACEBO: permute opponent identity within season
# ===========================================================================
print("\n" + "=" * 78)
print(f"RUNG 3 -- PLACEBO noise floor ({N_PERM} permutations of opponent identity within season)")
print("=" * 78)
pp = PregamePressure(tg[["team_id", "season", "game_date", "def_poss", "def_tov", "def_pts_allowed"]])

# Precompute, for every (season, date) actually played and every team in that season,
# that team's pregame pressure as of that date. Fake opponents go through the IDENTICAL
# construction as the real one -- only the identity changes.
teams_by_season = {s: np.array(pp.teams_by_season[s]) for s in SEASONS}
uniq = df[["season", "game_date"]].drop_duplicates().reset_index(drop=True)
key_to_row = {(r.season, r.game_date): i for i, r in uniq.iterrows()}
max_teams = max(len(v) for v in teams_by_season.values())
PMAT = np.full((len(uniq), max_teams), np.nan)
for i, r in uniq.iterrows():
    for j, t in enumerate(teams_by_season[r.season]):
        PMAT[i, j], _ = pp.lookup(t, r.season, r.game_date)

row_key = np.array([key_to_row[(s, d)] for s, d in zip(df["season"], df["game_date"])])
team_pos = {s: {t: j for j, t in enumerate(teams_by_season[s])} for s in SEASONS}
actual_col = np.array([team_pos[s][t] for s, t in zip(df["season"], df["opponent_team_id"])])
n_teams_row = np.array([len(teams_by_season[s]) for s in df["season"]])

# sanity: the precomputed matrix must reproduce the real pregame pressure exactly
recon = PMAT[row_key, actual_col]
assert np.allclose(recon, P_PRE, equal_nan=True), "placebo lookup does not reproduce real pressure"
print("sanity: precomputed lookup reproduces real pregame pressure exactly -> placebo uses same construction")

rng = np.random.default_rng(SEED)
null_pooled = np.empty(N_PERM)
null_season = {int(s): np.empty(N_PERM) for s in SEASONS}
for i in range(N_PERM):
    # random DIFFERENT team from the same season
    off = rng.integers(1, n_teams_row)           # 1..n_teams-1, never 0 -> never the real opponent
    fake_col = (actual_col + off) % n_teams_row
    P_FAKE = PMAT[row_key, fake_col]
    _, _, dperm, _ = delta_r2([X1], P_FAKE)
    null_pooled[i] = dperm
    for s in SEASONS:
        m = S == s
        _, _, ds, _ = delta_r2([X1], P_FAKE, m)
        null_season[int(s)][i] = ds

q = np.percentile(null_pooled, [50, 90, 95, 99, 100])
print(f"placebo pooled dR2: mean={null_pooled.mean():.6f} sd={null_pooled.std():.6f} "
      f"median={q[0]:.6f} p90={q[1]:.6f} p95={q[2]:.6f} p99={q[3]:.6f} max={q[4]:.6f}")
print(f"REAL rung-2 pooled dR2 = {d2:.6f}")
p_emp = float(np.mean(null_pooled >= d2))
print(f"fraction of placebo draws >= real: {p_emp:.4f}  ({int((null_pooled >= d2).sum())}/{N_PERM})")
results["rung3_placebo_pooled"] = {
    "n_perm": N_PERM, "mean": float(null_pooled.mean()), "sd": float(null_pooled.std()),
    "median": float(q[0]), "p90": float(q[1]), "p95": float(q[2]), "p99": float(q[3]),
    "max": float(q[4]), "real_dR2": d2, "frac_placebo_ge_real": p_emp}
results["rung3_placebo_per_season"] = {}
for s in SEASONS:
    ns = null_season[int(s)]
    real_s = results["rung2_per_season"][int(s)]["dR2"]
    fr = float(np.mean(ns >= real_s))
    print(f"  season {s}: placebo mean={ns.mean():.6f} p95={np.percentile(ns,95):.6f} "
          f"max={ns.max():.6f} | real={real_s:.6f} | frac>=real={fr:.3f}")
    results["rung3_placebo_per_season"][int(s)] = {
        "mean": float(ns.mean()), "p95": float(np.percentile(ns, 95)),
        "max": float(ns.max()), "real_dR2": real_s, "frac_placebo_ge_real": fr}

# also run the placebo against RUNG 1 (LOO) so the idealised number has a floor too
null_loo = np.empty(N_PERM)
rng2 = np.random.default_rng(SEED + 1)
loo_map = tg.set_index(["team_id", "season", "game_date"])["pressure_loo"].to_dict()
LMAT = np.full((len(uniq), max_teams), np.nan)
for i, r in uniq.iterrows():
    for j, t in enumerate(teams_by_season[r.season]):
        # a fake opponent has no game on this date; use their season LOO rate excluding
        # their own nearest game is not defined -- use their full-season rate as the
        # idealised analogue (the LOO adjustment only matters for the real opponent)
        LMAT[i, j] = pp.season_rate.get((t, r.season), np.nan)
for i in range(N_PERM):
    off = rng2.integers(1, n_teams_row)
    fake_col = (actual_col + off) % n_teams_row
    _, _, dperm, _ = delta_r2([X1], LMAT[row_key, fake_col])
    null_loo[i] = dperm
print(f"placebo floor for the RUNG-1 (idealised season-rate) measure: mean={null_loo.mean():.6f} "
      f"p95={np.percentile(null_loo,95):.6f} max={null_loo.max():.6f} | real rung1={d:.6f} | "
      f"frac>=real={float(np.mean(null_loo >= d)):.4f}")
results["rung3_placebo_rung1"] = {
    "mean": float(null_loo.mean()), "p95": float(np.percentile(null_loo, 95)),
    "max": float(null_loo.max()), "real_dR2": d,
    "frac_placebo_ge_real": float(np.mean(null_loo >= d))}

# ===========================================================================
# RUNG 4 -- is the predictor itself forecastable?
# ===========================================================================
print("\n" + "=" * 78)
print("RUNG 4 -- persistence of the predictor itself (team forced-TO rate)")
print("=" * 78)
season_rate = (tg.groupby(["team_id", "season"], as_index=False)
                 .agg(p=("def_poss", "sum"), t=("def_tov", "sum")))
season_rate["rate"] = 100.0 * season_rate["t"] / season_rate["p"]
piv = season_rate.pivot(index="team_id", columns="season", values="rate")
print("\n(a) season-over-season correlation of team forced-TO rate per 100 def poss:")
results["rung4_season_over_season"] = {}
sos = []
for s in SEASONS[:-1]:
    if s + 1 not in piv.columns:
        continue
    pair = piv[[s, s + 1]].dropna()
    r = float(pair.corr().iloc[0, 1])
    sos.append(r)
    print(f"    {s} -> {s+1}: r = {r:+.3f}  (n_teams = {len(pair)})")
    results["rung4_season_over_season"][f"{s}->{s+1}"] = {"r": r, "n_teams": int(len(pair))}
# pooled: stack all consecutive pairs
stack = []
for s in SEASONS[:-1]:
    if s + 1 in piv.columns:
        pair = piv[[s, s + 1]].dropna()
        stack.append(np.column_stack([pair[s].to_numpy(), pair[s + 1].to_numpy()]))
stack = np.vstack(stack)
r_pooled = float(np.corrcoef(stack[:, 0], stack[:, 1])[0, 1])
print(f"    pooled across all consecutive pairs: r = {r_pooled:+.3f} (n = {len(stack)} team-season pairs)")
results["rung4_season_over_season_pooled"] = {"r": r_pooled, "n": int(len(stack))}

print("\n(b) within-season split-half (first half vs second half of each team's schedule):")
tg_sorted = tg.sort_values(["team_id", "season", "game_date"]).copy()
tg_sorted["gnum"] = tg_sorted.groupby(["team_id", "season"]).cumcount()
tg_sorted["ngames"] = tg_sorted.groupby(["team_id", "season"])["gnum"].transform("size")
tg_sorted["half"] = np.where(tg_sorted["gnum"] < tg_sorted["ngames"] / 2, 1, 2)
half = (tg_sorted.groupby(["team_id", "season", "half"], as_index=False)
                  .agg(p=("def_poss", "sum"), t=("def_tov", "sum")))
half["rate"] = 100.0 * half["t"] / half["p"]
hp = half.pivot(index=["team_id", "season"], columns="half", values="rate").dropna()
results["rung4_split_half"] = {}
for s in SEASONS:
    sub = hp[hp.index.get_level_values("season") == s]
    r = float(np.corrcoef(sub[1], sub[2])[0, 1])
    print(f"    season {s}: r(H1,H2) = {r:+.3f}  (n_teams = {len(sub)})")
    results["rung4_split_half"][int(s)] = {"r": r, "n_teams": int(len(sub))}
r_sh_pooled = float(np.corrcoef(hp[1], hp[2])[0, 1])
print(f"    pooled: r(H1,H2) = {r_sh_pooled:+.3f}  (n = {len(hp)} team-seasons)")
results["rung4_split_half_pooled"] = {"r": r_sh_pooled, "n": int(len(hp))}

# ===========================================================================
# CONFOUND -- is pressure just opponent quality (points allowed per 100)?
# ===========================================================================
print("\n" + "=" * 78)
print("CONFOUND CHECK -- add opponent points-allowed-per-100-def-poss as a control")
print("=" * 78)
print(f"corr(pressure_LOO, defrtg_LOO)       = {np.corrcoef(P_LOO, D_LOO)[0,1]:+.4f}")
print(f"corr(pressure_pregame, defrtg_pregame) = {np.corrcoef(P_PRE, D_PRE)[0,1]:+.4f}")

_, _, d1c, b1c = delta_r2([X1, D_LOO], P_LOO)
print(f"\nRUNG 1 with opponent-quality control: dR2(pressure | tendency, defrtg) = {d1c:.6f} "
      f"(uncontrolled {d:.6f})  beta = {b1c:+.4f}")
_, _, d2c, b2c = delta_r2([X1, D_PRE], P_PRE)
print(f"RUNG 2 with opponent-quality control: dR2(pressure | tendency, defrtg) = {d2c:.6f} "
      f"(uncontrolled {d2:.6f})  beta = {b2c:+.4f}")
results["confound"] = {
    "corr_pressure_defrtg_loo": float(np.corrcoef(P_LOO, D_LOO)[0, 1]),
    "corr_pressure_defrtg_pregame": float(np.corrcoef(P_PRE, D_PRE)[0, 1]),
    "rung1_dR2_controlled": d1c, "rung2_dR2_controlled": d2c}
results["confound_per_season"] = {}
for s in SEASONS:
    m = S == s
    _, _, dsc, _ = delta_r2([X1, D_PRE], P_PRE, m)
    print(f"  season {s} rung-2 controlled dR2 = {dsc:.6f}")
    results["confound_per_season"][int(s)] = dsc

# ===========================================================================
# PARTITION VERIFICATION ON OUTPUT BYTES
# ===========================================================================
print("\n" + "=" * 78)
print("PARTITION VERIFICATION -- re-read the written files and scan their bytes")
print("=" * 78)
import re
import os
for fn in ["player_game_analysis.csv", "team_game_defense.csv"]:
    path = os.path.join(OUT, fn)
    raw = open(path, "r", encoding="utf-8").read()
    years = set(re.findall(r"\b(20\d\d)\b", raw))
    d_ = pd.read_csv(path)
    seasons_in_file = sorted(d_["season"].unique().tolist())
    bad = sorted(y for y in years if y not in {"2021", "2022", "2023", "2024"})
    print(f"{fn}: rows={len(d_)}  season column values={seasons_in_file}  "
          f"4-digit-year tokens anywhere in file bytes={sorted(years)}  "
          f"out-of-partition tokens={bad if bad else 'NONE'}")
    assert set(seasons_in_file).issubset({2021, 2022, 2023, 2024}), "PARTITION VIOLATION"
    assert not bad, f"PARTITION VIOLATION: out-of-partition year token(s) {bad} in {fn}"
print("PARTITION VERIFIED on output bytes: only 2021-2024 appear anywhere in the written files.")

with open(f"{OUT}/summary.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nwrote summary.json")
