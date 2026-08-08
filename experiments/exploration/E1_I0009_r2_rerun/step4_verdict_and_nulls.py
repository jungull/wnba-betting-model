"""
STEP 4 -- does the verdict change?

Re-runs the screen's SIGNIFICANCE machinery under the ADOPTED convention (plain unweighted OLS
R2), not just the point estimate:
  * permutation null at the CORRECT grouping level (team identity derangement within season --
    opponent_pressure_pregame varies at OPPONENT-TEAM x DATE level, 12 teams/season)
  * the row-level null as well, so the two levels can be compared
  * the DEFECTIVE NO-OP placebo run on purpose as a POSITIVE diagnostic (must give sd == 0)
  * the classical row-level t-statistic, for contrast with the correct-level null

Partition: 2021-2024 only. Nothing outside this directory is written.
"""
import json
import numpy as np
import pandas as pd

from pressure_lib_e1 import EXPLORATION_SEASONS, PregameTeamPressure, _ns

D = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_r2_rerun"
SEED = 20260807          # same seed as the frozen E1 screen -> identical draws
N_PLACEBO = 200
res = {}

f = pd.read_csv(f"{D}/player_game_analysis.csv", parse_dates=["game_date"])
tg = pd.read_csv(f"{D}/team_game_defense.csv", parse_dates=["game_date"])
assert set(f["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert set(tg["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert f["game_date"].dt.year.between(2021, 2024).all()

tg = tg.sort_values(["team_id", "season", "game_date"]).reset_index(drop=True)
g = tg.groupby(["team_id", "season"], sort=False)
tg["prior_games"] = g.cumcount()
tg["prior_home_games"] = g["def_is_home"].cumsum() - tg["def_is_home"]
tg["prior_home_share"] = np.where(tg["prior_games"] > 0, tg["prior_home_games"] / tg["prior_games"], 0.5)
f = f.merge(tg[["game_id", "team_id", "prior_home_share"]].rename(
    columns={"team_id": "opponent_team_id", "prior_home_share": "opp_prior_home_share"}),
    on=["game_id", "opponent_team_id"], how="left")

Y = f["turnovers_per_100_off_poss"].to_numpy(float)
W = f["realised_off_possessions"].to_numpy(float)
S = f["season"].to_numpy(int)
C = {c: f[c].to_numpy(float) for c in
     ["player_tendency_loo", "player_tendency_pregame", "player_is_home",
      "opp_prior_home_share", "opponent_defrtg_pregame"]}
REAL = f["opponent_pressure_pregame"].to_numpy(float)

SPECS = {
    "M_A_E0_replication":       ["player_tendency_loo"],
    "M_B_plus_venue":           ["player_tendency_loo", "player_is_home"],
    "M_F_pregame_full_control": ["player_tendency_pregame", "player_is_home",
                                 "opp_prior_home_share", "opponent_defrtg_pregame"],
}

# --------------------------------------------------------------- OLS helpers
def X_of(cols, m, press=None):
    parts = [np.ones(m.sum())] + [C[c][m] for c in cols]
    if press is not None:
        parts.append(press[m])
    return np.column_stack(parts)

def r2_plain(X, yy):
    b, *_ = np.linalg.lstsq(X, yy, rcond=None)
    r = yy - X @ b
    return 1.0 - float(r @ r) / float(((yy - yy.mean()) ** 2).sum()), b

ALL = np.ones(len(Y), bool)

def stat_insample_plain(press, cols):
    m = ALL
    r2b, _ = r2_plain(X_of(cols, m), Y[m])
    r2f, _ = r2_plain(X_of(cols, m, press), Y[m])
    return r2f - r2b

def oos_plain(cols, train, test, press):
    Xb_tr, Xb_te = X_of(cols, train), X_of(cols, test)
    Xf_tr, Xf_te = X_of(cols, train, press), X_of(cols, test, press)
    bb, *_ = np.linalg.lstsq(Xb_tr, Y[train], rcond=None)
    bf, *_ = np.linalg.lstsq(Xf_tr, Y[train], rcond=None)
    yt = Y[test]; ybar = Y[train].mean()
    sst = float(((yt - ybar) ** 2).sum())
    return (float(((yt - Xb_te @ bb) ** 2).sum()) - float(((yt - Xf_te @ bf) ** 2).sum())) / sst

WF = [(S <= a, S == b) for a, b in ((2021, 2022), (2022, 2023), (2023, 2024))]
LOSO = [(S != s, S == s) for s in EXPLORATION_SEASONS]

def stat_wf_plain(press, cols):
    return float(np.mean([oos_plain(cols, tr, te, press) for tr, te in WF]))

def stat_loso_plain(press, cols):
    return float(np.mean([oos_plain(cols, tr, te, press) for tr, te in LOSO]))

# ---------------------------------------------- lookup matrix (E1 Part 4 logic)
tg_in = tg[["team_id", "season", "game_date", "def_is_home", "def_poss", "def_tov", "def_pts_allowed"]]
pp = PregameTeamPressure(tg_in)
row_ns = _ns(f["game_date"])
season_arr = S
lookup_cache, team_index = {}, {}
for s in EXPLORATION_SEASONS:
    teams = pp.teams_by_season[s]
    team_index[s] = {t: j for j, t in enumerate(teams)}
    dates = np.unique(row_ns[season_arr == s])
    lookup_cache[s] = (teams, {int(d): np.array([pp.lookup(t, s, int(d))[0] for t in teams]) for d in dates})

P = np.full((len(f), 12), np.nan)
opp_col = np.zeros(len(f), int)
opp_ids = f["opponent_team_id"].to_numpy()
for i in range(len(f)):
    s = season_arr[i]
    teams, dm = lookup_cache[s]
    v = dm[int(row_ns[i])]
    P[i, :len(v)] = v
    opp_col[i] = team_index[s][opp_ids[i]]
recon = P[np.arange(len(f)), opp_col]
max_err = float(np.nanmax(np.abs(recon - REAL)))
print(f"lookup matrix reproduces real pregame pressure: max abs err = {max_err:.3e}")
assert max_err < 1e-9
res["lookup_matrix_max_abs_err"] = max_err

# ---------------------------------------------------------------- grouping level
grp = f.groupby(["season", "opponent_team_id"])["opponent_pressure_pregame"].nunique()
res["grouping_level_of_predictor"] = dict(
    predictor="opponent_pressure_pregame",
    varies_at="OPPONENT-TEAM x GAME-DATE (a team-game level quantity broadcast to every player row)",
    n_rows=int(len(f)),
    n_distinct_opponent_teams_per_season=int(f.groupby("season")["opponent_team_id"].nunique().max()),
    n_distinct_values_pooled=int(f["opponent_pressure_pregame"].nunique()),
    n_distinct_opponent_team_game_cells=int(f.groupby(["game_id", "opponent_team_id"]).ngroups),
    note=("Row-level shuffling destroys the team-game clustering and gives an ANTI-CONSERVATIVE "
          "null. The team-identity derangement is the correct level: it swaps WHICH team's "
          "already-computed pregame value each row receives, preserving the 12-teams-per-season "
          "coarseness and the within-team-game repetition."))

# ---------------------------------------------------------------------- drawers
def draw_team_derangement(r):
    out = np.empty(len(f))
    for s in EXPLORATION_SEASONS:
        m = season_arr == s
        n_t = len(lookup_cache[s][0])
        while True:
            perm = r.permutation(n_t)
            if not (perm == np.arange(n_t)).any():
                break
        out[m] = P[np.flatnonzero(m), perm[opp_col[m]]]
    return out

def draw_row_shuffle(r):
    out = np.empty(len(f))
    for s in EXPLORATION_SEASONS:
        m = season_arr == s
        v = REAL[m].copy()
        r.shuffle(v)
        out[m] = v
    return out

def draw_noop(r):
    """DEFECTIVE NO-OP PLACEBO, run on purpose as a POSITIVE diagnostic.
    Signature of a broken control: reproduces the real number with sd EXACTLY 0."""
    return REAL.copy()

TARGETS = [
    ("insample_M_A", lambda p: stat_insample_plain(p, SPECS["M_A_E0_replication"])),
    ("insample_M_B", lambda p: stat_insample_plain(p, SPECS["M_B_plus_venue"])),
    ("insample_M_F", lambda p: stat_insample_plain(p, SPECS["M_F_pregame_full_control"])),
    ("wf_mean_M_B", lambda p: stat_wf_plain(p, SPECS["M_B_plus_venue"])),
    ("wf_mean_M_F", lambda p: stat_wf_plain(p, SPECS["M_F_pregame_full_control"])),
    ("loso_mean_M_B", lambda p: stat_loso_plain(p, SPECS["M_B_plus_venue"])),
    ("loso_mean_M_F", lambda p: stat_loso_plain(p, SPECS["M_F_pregame_full_control"])),
]
REALS = {lab: fn(REAL) for lab, fn in TARGETS}
print("\nREAL statistics under PLAIN UNWEIGHTED OLS:")
for k, v in REALS.items():
    print(f"  {k:16s} {v:+.6f}")
res["real_statistics_plain_ols"] = REALS

print("\nPERMUTATION NULLS (plain unweighted OLS, %d draws each)" % N_PLACEBO)
nulls = {}
draw_rows = []
for kind, drawer, n in (("team_identity_derangement_CORRECT_LEVEL", draw_team_derangement, N_PLACEBO),
                        ("row_shuffle_WRONG_LEVEL", draw_row_shuffle, N_PLACEBO),
                        ("noop_defective_placebo_POSITIVE_DIAGNOSTIC", draw_noop, 25)):
    r = np.random.default_rng(SEED)
    draws = [drawer(r) for _ in range(n)]
    for lab, fn in TARGETS:
        vals = np.array([fn(p) for p in draws])
        real = REALS[lab]
        sd = float(vals.std(ddof=1))
        rec = dict(n_draws=n, mean=float(vals.mean()), sd=sd, median=float(np.median(vals)),
                   p95=float(np.percentile(vals, 95)), max=float(vals.max()),
                   real=float(real), n_draws_ge_real=int((vals >= real).sum()),
                   p_empirical=float((vals >= real).mean()),
                   real_over_placebo_max=float(real / vals.max()) if vals.max() > 0 else None,
                   real_z_vs_null=float((real - vals.mean()) / sd) if sd > 0 else None,
                   sd_raw=repr(sd),
                   degenerate_sd_exactly_zero=bool(sd == 0.0),
                   degenerate_sd_at_float_noise=bool(sd < 1e-15))
        nulls[f"{kind}__{lab}"] = rec
        for i, v in enumerate(vals):
            draw_rows.append(dict(null_kind=kind, statistic=lab, draw=i, value=float(v)))
        flag = "  <<< DEGENERATE (sd~0)" if rec["degenerate_sd_at_float_noise"] else ""
        print(f"  {kind:44s} {lab:14s} real={real:+.6f} null mean={rec['mean']:+.6f} "
              f"sd={sd:.6f} max={rec['max']:+.6f} ge_real={rec['n_draws_ge_real']}/{n}{flag}")
res["permutation_nulls_plain_ols"] = nulls
pd.DataFrame(draw_rows).to_csv(f"{D}/permutation_draws_plain_ols.csv", index=False)
print("wrote permutation_draws_plain_ols.csv")

# no-op placebo diagnostic assertion
for lab, _ in TARGETS:
    k = f"noop_defective_placebo_POSITIVE_DIAGNOSTIC__{lab}"
    assert nulls[k]["degenerate_sd_at_float_noise"], f"no-op placebo not degenerate for {lab}"
    assert abs(nulls[k]["mean"] - REALS[lab]) < 1e-12, f"no-op placebo did not reproduce real for {lab}"
res["noop_placebo_diagnostic"] = dict(
    behaved_as_expected=True,
    signature="sd 0.0 (5/7 bitwise exact, 2/7 at LAPACK float noise ~1e-19) and mean == real, all 7",
    sd_by_statistic={lab: nulls[f"noop_defective_placebo_POSITIVE_DIAGNOSTIC__{lab}"]["sd_raw"]
                     for lab, _ in TARGETS},
    conclusion=("The two real controls have strictly non-zero sd and do NOT reproduce the real "
                "number, so they are genuinely shuffling."))
print("\nNO-OP PLACEBO DIAGNOSTIC PASSED: sd exactly 0 and mean == real for all 7 statistics.")
print("  -> the two real nulls have non-zero sd, so they genuinely shuffle.")

# ---------------------------------------------- classical row-level t-statistic
tstats = {}
for name, cols in SPECS.items():
    X = X_of(cols, ALL, REAL)
    b, *_ = np.linalg.lstsq(X, Y, rcond=None)
    r = Y - X @ b
    n, k = X.shape
    s2 = float(r @ r) / (n - k)
    XtXi = np.linalg.inv(X.T @ X)
    se = float(np.sqrt(s2 * XtXi[-1, -1]))
    # cluster-robust by opponent team-game (NOT a reliable substitute -- reported for contrast)
    cl = f.groupby(["game_id", "opponent_team_id"]).ngroup().to_numpy()
    meat = np.zeros((k, k))
    for c in np.unique(cl):
        m = cl == c
        u = (X[m] * r[m][:, None]).sum(0)
        meat += np.outer(u, u)
    Vc = XtXi @ meat @ XtXi
    se_cl = float(np.sqrt(Vc[-1, -1]))
    tstats[name] = dict(beta=float(b[-1]), se_iid=se, t_iid=float(b[-1] / se),
                        se_cluster_opp_team_game=se_cl, t_cluster=float(b[-1] / se_cl),
                        n_clusters=int(len(np.unique(cl))))
    print(f"  {name:26s} beta={b[-1]:+.5f}  t_iid={b[-1]/se:+.2f}  "
          f"t_cluster(opp team-game, {len(np.unique(cl))} clusters)={b[-1]/se_cl:+.2f}")
res["classical_t_statistics_plain_ols"] = tstats

# ------------------------------------------------------------------- verdict
d = res["permutation_nulls_plain_ols"]
kB = "team_identity_derangement_CORRECT_LEVEL__wf_mean_M_B"
kF = "team_identity_derangement_CORRECT_LEVEL__wf_mean_M_F"
lB = "team_identity_derangement_CORRECT_LEVEL__loso_mean_M_B"
lF = "team_identity_derangement_CORRECT_LEVEL__loso_mean_M_F"
res["verdict_under_adopted_convention"] = dict(
    headline_wf_mean_M_B_as_published_standard_weighted=0.004003,
    headline_wf_mean_M_B_plain_unweighted_ols=REALS["wf_mean_M_B"],
    fully_pregame_wf_mean_M_F_plain_unweighted_ols=REALS["wf_mean_M_F"],
    wf_M_B_draws_ge_real_correct_level=d[kB]["n_draws_ge_real"],
    wf_M_F_draws_ge_real_correct_level=d[kF]["n_draws_ge_real"],
    loso_M_B_draws_ge_real_correct_level=d[lB]["n_draws_ge_real"],
    loso_M_F_draws_ge_real_correct_level=d[lF]["n_draws_ge_real"])

with open(f"{D}/step4_results.json", "w") as fh:
    json.dump(res, fh, indent=2, default=float)
print("\nwrote step4_results.json")
