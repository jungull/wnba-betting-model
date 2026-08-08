"""
E1 I0009 -- home/away control, collinearity diagnostics, genuine out-of-sample protocol,
and a non-degenerate placebo.

Non-claiming (GRAPH_POLICY 13.1): no registry entry, no preregistration, no leaderboard row,
no bootstrap, no promotion threshold. Output is a LEAD verdict only.

Partition: 2021-2024 ONLY. Verified on season/date COLUMN VALUES (not raw bytes).
"""
import json

import numpy as np
import pandas as pd

from pressure_lib_e1 import EXPLORATION_SEASONS, PregameTeamPressure, _ns

OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_additive_pressure"
SEED = 20260807
N_PLACEBO = 200

rng = np.random.default_rng(SEED)
res = {"idea": "I0009", "family": "F_TURNOVER_PRESSURE", "stage": "E1",
       "status": "NON-CLAIMING EXPLORATION -- lead, not result",
       "partition": {"seasons": EXPLORATION_SEASONS}}

# ---------------------------------------------------------------------------
# Load + partition verification on COLUMN VALUES
# ---------------------------------------------------------------------------
f = pd.read_csv(f"{OUT}/player_game_analysis.csv", parse_dates=["game_date"])
tg = pd.read_csv(f"{OUT}/team_game_defense.csv", parse_dates=["game_date"])
for name, d in (("player_game_analysis", f), ("team_game_defense", tg)):
    assert set(d["season"].unique()).issubset(set(EXPLORATION_SEASONS)), f"PARTITION VIOLATION {name}"
    assert d["game_date"].dt.year.between(2021, 2024).all(), f"PARTITION VIOLATION {name} date"
    assert "observed_time" not in d.columns
    print(f"{name}: rows={len(d)} season values={sorted(d['season'].unique())} "
          f"date years={sorted(d['game_date'].dt.year.unique())}")
print("PARTITION VERIFIED on season/date COLUMN VALUES (no byte scan; column values only).\n")
res["partition"]["verified_on"] = "season column values and game_date.dt.year (NOT raw bytes)"
res["partition"]["incident"] = "none"

# ---------------------------------------------------------------------------
# Prior-schedule home share for the opponent (the schedule-imbalance channel by which a
# team-level pressure average could encode VENUE rather than opponent quality)
# ---------------------------------------------------------------------------
tg = tg.sort_values(["team_id", "season", "game_date"]).reset_index(drop=True)
g = tg.groupby(["team_id", "season"], sort=False)
tg["prior_games"] = g.cumcount()
tg["prior_home_games"] = g["def_is_home"].cumsum() - tg["def_is_home"]
tg["prior_home_share"] = np.where(tg["prior_games"] > 0,
                                  tg["prior_home_games"] / tg["prior_games"], 0.5)
f = f.merge(tg[["game_id", "team_id", "prior_home_share"]].rename(
    columns={"team_id": "opponent_team_id", "prior_home_share": "opp_prior_home_share"}),
    on=["game_id", "opponent_team_id"], how="left")
assert f["opp_prior_home_share"].notna().all()

y = f["turnovers_per_100_off_poss"].to_numpy(float)
w = f["realised_off_possessions"].to_numpy(float)
season = f["season"].to_numpy(int)

# ---------------------------------------------------------------------------
# WLS helpers
# ---------------------------------------------------------------------------
def fit(X, yy, ww):
    s = np.sqrt(ww)
    beta, *_ = np.linalg.lstsq(X * s[:, None], yy * s, rcond=None)
    return beta

def r2_in(X, yy, ww):
    b = fit(X, yy, ww)
    r = yy - X @ b
    ybar = np.average(yy, weights=ww)
    return 1.0 - np.sum(ww * r ** 2) / np.sum(ww * (yy - ybar) ** 2), b

def design(cols, mask=None):
    m = np.ones(len(f), bool) if mask is None else mask
    return np.column_stack([np.ones(m.sum())] + [f[c].to_numpy(float)[m] for c in cols])

def delta_r2(base_cols, add_col, mask=None):
    m = np.ones(len(f), bool) if mask is None else mask
    Xb = design(base_cols, m)
    Xf = np.column_stack([Xb, f[add_col].to_numpy(float)[m]])
    r2b, _ = r2_in(Xb, y[m], w[m])
    r2f, bf = r2_in(Xf, y[m], w[m])
    return dict(n=int(m.sum()), r2_base=r2b, r2_full=r2f,
                dr2=r2f - r2b, beta_add=float(bf[-1]))

# ===========================================================================
# PART 1 -- THE UNCONTROLLED CONFOUND: HOME/AWAY
# ===========================================================================
print("=" * 78)
print("PART 1  HOME/AWAY -- is the pressure measure venue in disguise?")
print("=" * 78)

# 1a. Do teams actually force more turnovers at home?
venue = {}
tgw = tg["def_poss"].to_numpy(float)
for s in EXPLORATION_SEASONS + ["pooled"]:
    m = np.ones(len(tg), bool) if s == "pooled" else (tg["season"].to_numpy() == s)
    h = m & (tg["def_is_home"].to_numpy() == 1)
    a = m & (tg["def_is_home"].to_numpy() == 0)
    rh = 100 * tg["def_tov"].to_numpy()[h].sum() / tg["def_poss"].to_numpy()[h].sum()
    ra = 100 * tg["def_tov"].to_numpy()[a].sum() / tg["def_poss"].to_numpy()[a].sum()
    venue[str(s)] = dict(home_forced_to_rate=rh, away_forced_to_rate=ra, home_minus_away=rh - ra)
    print(f"  forced-TO/100 def poss  {s}: home={rh:.3f}  away={ra:.3f}  diff={rh-ra:+.3f}")
res["venue_effect_on_forced_to_rate"] = venue

# 1b. Variance decomposition of the team-game forced-TO rate: venue vs team identity
tgy = tg["def_tov_rate"].to_numpy(float)
def tg_r2(X):
    b = fit(X, tgy, tgw)
    r = tgy - X @ b
    ybar = np.average(tgy, weights=tgw)
    return 1.0 - np.sum(tgw * r ** 2) / np.sum(tgw * (tgy - ybar) ** 2)

season_d = pd.get_dummies(tg["season"], drop_first=True).to_numpy(float)
teamseason_d = pd.get_dummies(tg["team_id"].astype(str) + "_" + tg["season"].astype(str),
                              drop_first=True).to_numpy(float)
one = np.ones((len(tg), 1))
r2_season = tg_r2(np.hstack([one, season_d]))
r2_venue = tg_r2(np.hstack([one, season_d, tg["def_is_home"].to_numpy(float)[:, None]]))
r2_team = tg_r2(np.hstack([one, teamseason_d]))
r2_team_venue = tg_r2(np.hstack([one, teamseason_d, tg["def_is_home"].to_numpy(float)[:, None]]))
print(f"\n  team-game forced-TO rate, weighted R^2 (n={len(tg)} team-games):")
print(f"    season FE only            : {r2_season:.5f}")
print(f"    season FE + venue         : {r2_venue:.5f}   (venue adds {r2_venue-r2_season:.5f})")
print(f"    team-season FE            : {r2_team:.5f}   (team identity adds {r2_team-r2_season:.5f})")
print(f"    team-season FE + venue    : {r2_team_venue:.5f}")
res["variance_decomposition_team_game_forced_to_rate"] = dict(
    n_team_games=int(len(tg)), r2_season_fe=r2_season, r2_season_fe_plus_venue=r2_venue,
    venue_increment=r2_venue - r2_season, r2_team_season_fe=r2_team,
    team_identity_increment=r2_team - r2_season, r2_team_season_fe_plus_venue=r2_team_venue,
    venue_increment_over_team_fe=r2_team_venue - r2_team)

# 1c. COLLINEARITY of the pressure measure with (a) venue and (b) opponent defensive strength
print("\n  COLLINEARITY of opponent_pressure_pregame, within season:")
coll = {}
for s in EXPLORATION_SEASONS + ["pooled"]:
    m = np.ones(len(f), bool) if s == "pooled" else (season == s)
    p = f["opponent_pressure_pregame"].to_numpy(float)[m]
    row = dict(
        n=int(m.sum()),
        corr_with_player_is_home=float(np.corrcoef(p, f["player_is_home"].to_numpy(float)[m])[0, 1]),
        corr_with_opp_prior_home_share=float(np.corrcoef(p, f["opp_prior_home_share"].to_numpy(float)[m])[0, 1]),
        corr_with_opponent_defrtg_pregame=float(np.corrcoef(p, f["opponent_defrtg_pregame"].to_numpy(float)[m])[0, 1]),
    )
    # share of the pressure measure's variance explained by the obvious main effects
    Xc = np.column_stack([np.ones(m.sum()), f["player_is_home"].to_numpy(float)[m],
                          f["opp_prior_home_share"].to_numpy(float)[m],
                          f["opponent_defrtg_pregame"].to_numpy(float)[m]])
    bb = fit(Xc, p, w[m])
    rr = p - Xc @ bb
    pbar = np.average(p, weights=w[m])
    row["r2_pressure_on_venue_and_defrtg"] = float(
        1 - np.sum(w[m] * rr ** 2) / np.sum(w[m] * (p - pbar) ** 2))
    Xv = np.column_stack([np.ones(m.sum()), f["player_is_home"].to_numpy(float)[m],
                          f["opp_prior_home_share"].to_numpy(float)[m]])
    bv = fit(Xv, p, w[m])
    rv = p - Xv @ bv
    row["r2_pressure_on_venue_only"] = float(
        1 - np.sum(w[m] * rv ** 2) / np.sum(w[m] * (p - pbar) ** 2))
    coll[str(s)] = row
    print(f"    {s}: r(is_home)={row['corr_with_player_is_home']:+.4f}  "
          f"r(opp prior home share)={row['corr_with_opp_prior_home_share']:+.4f}  "
          f"r(opp defrtg)={row['corr_with_opponent_defrtg_pregame']:+.4f}  "
          f"R2(pressure~venue)={row['r2_pressure_on_venue_only']:.5f}  "
          f"R2(pressure~venue+defrtg)={row['r2_pressure_on_venue_and_defrtg']:.5f}")
res["collinearity"] = coll

# 1d. Home/away main effect on the OUTCOME
hm = delta_r2(["player_tendency_loo"], "player_is_home")
print(f"\n  home/away main effect on player turnover rate: beta={hm['beta_add']:+.4f} "
      f"dR2={hm['dr2']:.6f}")
res["home_main_effect_on_outcome"] = hm

# ===========================================================================
# PART 2 -- IN-SAMPLE EFFECT UNDER PROGRESSIVE CONTROL
# ===========================================================================
print("\n" + "=" * 78)
print("PART 2  IN-SAMPLE dR2 UNDER PROGRESSIVE CONTROL (E0-comparable, hindsight baseline)")
print("=" * 78)

SPECS = {
    "M_A_E0_replication":        ["player_tendency_loo"],
    "M_B_plus_venue":            ["player_tendency_loo", "player_is_home"],
    "M_C_plus_schedule_balance": ["player_tendency_loo", "player_is_home", "opp_prior_home_share"],
    "M_D_plus_opp_defrtg":       ["player_tendency_loo", "player_is_home", "opp_prior_home_share",
                                  "opponent_defrtg_pregame"],
    "M_E_pregame_baseline":      ["player_tendency_pregame", "player_is_home"],
    "M_F_pregame_full_control":  ["player_tendency_pregame", "player_is_home",
                                  "opp_prior_home_share", "opponent_defrtg_pregame"],
}
insample = {}
for name, cols in SPECS.items():
    pooled = delta_r2(cols, "opponent_pressure_pregame")
    per = {}
    for s in EXPLORATION_SEASONS:
        per[str(s)] = delta_r2(cols, "opponent_pressure_pregame", mask=(season == s))
    d = np.array([per[str(s)]["dr2"] for s in EXPLORATION_SEASONS])
    insample[name] = dict(baseline_cols=cols, pooled=pooled, per_season=per,
                          per_season_dr2_mean=float(d.mean()), per_season_dr2_sd=float(d.std(ddof=1)),
                          per_season_dr2_min=float(d.min()), per_season_dr2_max=float(d.max()),
                          all_same_sign=bool((d > 0).all()))
    print(f"  {name:28s} pooled dR2={pooled['dr2']:.6f}  beta={pooled['beta_add']:+.4f}  "
          f"per-season=[{', '.join(f'{x:.6f}' for x in d)}]")
res["in_sample_progressive_control"] = insample

base_dr2 = insample["M_A_E0_replication"]["pooled"]["dr2"]
for name in SPECS:
    insample[name]["retained_vs_M_A"] = insample[name]["pooled"]["dr2"] / base_dr2
print(f"\n  retained vs M_A (E0 replication, dR2={base_dr2:.6f}):")
for name in SPECS:
    print(f"    {name:28s} {100*insample[name]['retained_vs_M_A']:6.1f}%")

# 2a-bis. RECONCILIATION WITH E0's PUBLISHED NUMBERS.
# E0 computed weighted R^2 as 1 - SSE_w / sum((y*sqrt(w) - mean(y*sqrt(w)))^2), i.e. the SST of
# the sqrt-weight-TRANSFORMED response around ITS OWN mean, not the weighted SST of y around the
# weighted mean of y. The SSE numerators are identical; only the denominator differs, so every E0
# dR2 is the same quantity divided by a larger number. Recomputing under E0's convention must
# reproduce E0's published figures exactly -- that is the check that this E1 rebuilt the same frame.
def delta_r2_e0convention(base_cols, add_col, mask=None):
    m = np.ones(len(f), bool) if mask is None else mask
    def r2(X):
        s = np.sqrt(w[m]); Xw = X * s[:, None]; yw = y[m] * s
        b, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        r = yw - Xw @ b
        return 1 - float(r @ r) / float(((yw - yw.mean()) ** 2).sum())
    Xb = design(base_cols, m)
    return r2(np.column_stack([Xb, f[add_col].to_numpy(float)[m]])) - r2(Xb)

e0_pooled = delta_r2_e0convention(["player_tendency_loo"], "opponent_pressure_pregame")
e0_per = {str(s): delta_r2_e0convention(["player_tendency_loo"], "opponent_pressure_pregame",
                                        mask=(season == s)) for s in EXPLORATION_SEASONS}
e0_loo = delta_r2_e0convention(["player_tendency_loo"], "opponent_pressure_loo")
print(f"\n  E0 reconciliation (E0's own R^2 denominator convention):")
print(f"    rung-2 pooled dR2 = {e0_pooled:.6f}  (E0 published 0.006505)")
print(f"    rung-1 pooled dR2 = {e0_loo:.6f}  (E0 published 0.008424)")
print(f"    rung-2 per season = {[round(v,6) for v in e0_per.values()]}")
print(f"    (E0 published       [0.015038, 0.005329, 0.002279, 0.006121])")
res["e0_reconciliation"] = dict(
    note=("E0's weighted R^2 used SST of the sqrt-weight-transformed response around its own mean; "
          "this E1 uses the standard weighted SST of y around the weighted mean of y. SSE numerators "
          "are identical. Under E0's convention this E1's frame reproduces E0's published numbers "
          "exactly, confirming the frame and predictor were rebuilt identically. All E1 headline "
          "numbers below use the STANDARD weighted R^2, which is ~8% larger than E0's."),
    rung2_pooled_e0_convention=e0_pooled, e0_published_rung2_pooled=0.006505,
    rung1_pooled_e0_convention=e0_loo, e0_published_rung1_pooled=0.008424,
    rung2_per_season_e0_convention=e0_per,
    e0_published_rung2_per_season=[0.015038, 0.005329, 0.002279, 0.006121])
assert abs(e0_pooled - 0.006505) < 5e-6, "failed to reproduce E0 under E0's own convention"

# 2b. venue-STRATIFIED (fit inside home games only, and away games only)
print("\n  venue-STRATIFIED (effect must be present inside each venue stratum):")
strat = {}
for lab, hv in (("home_games", 1), ("away_games", 0)):
    m = f["player_is_home"].to_numpy() == hv
    r = delta_r2(["player_tendency_loo"], "opponent_pressure_pregame", mask=m)
    per = {str(s): delta_r2(["player_tendency_loo"], "opponent_pressure_pregame",
                            mask=m & (season == s)) for s in EXPLORATION_SEASONS}
    strat[lab] = dict(pooled=r, per_season=per)
    print(f"    {lab:11s} n={r['n']:5d}  dR2={r['dr2']:.6f}  beta={r['beta_add']:+.4f}")
res["venue_stratified"] = strat

# 2c. does the VENUE-SPLIT pressure measure beat the venue-blind one?
print("\n  venue-split vs venue-blind pressure measure (M_B baseline):")
vb = delta_r2(SPECS["M_B_plus_venue"], "opponent_pressure_pregame")
vs = delta_r2(SPECS["M_B_plus_venue"], "opponent_pressure_pregame_venue")
both = delta_r2(SPECS["M_B_plus_venue"] + ["opponent_pressure_pregame"],
                "opponent_pressure_pregame_venue")
print(f"    venue-blind dR2={vb['dr2']:.6f} | venue-matched dR2={vs['dr2']:.6f} | "
      f"venue-matched ON TOP of venue-blind dR2={both['dr2']:.6f}")
res["venue_split_measure"] = dict(venue_blind=vb, venue_matched=vs,
                                  venue_matched_incremental_over_blind=both)

# ===========================================================================
# PART 3 -- GENUINE OUT-OF-SAMPLE PROTOCOL
# ===========================================================================
print("\n" + "=" * 78)
print("PART 3  OUT-OF-SAMPLE (leave-one-season-out and walk-forward, inside 2021-2024)")
print("=" * 78)

def oos_delta(base_cols, add_col, train_mask, test_mask, press=None):
    """Out-of-sample dR2 = (SSE_base - SSE_full)/SST, SST around the TRAIN weighted mean."""
    def mat(cols, m):
        parts = [np.ones(m.sum())]
        for c in cols:
            parts.append(press[m] if c == "__PRESS__" else f[c].to_numpy(float)[m])
        return np.column_stack(parts)
    add = "__PRESS__" if add_col == "__PRESS__" else add_col
    Xb_tr, Xb_te = mat(base_cols, train_mask), mat(base_cols, test_mask)
    Xf_tr = np.column_stack([Xb_tr, mat([add], train_mask)[:, 1]])
    Xf_te = np.column_stack([Xb_te, mat([add], test_mask)[:, 1]])
    bb = fit(Xb_tr, y[train_mask], w[train_mask])
    bf = fit(Xf_tr, y[train_mask], w[train_mask])
    yt, wt = y[test_mask], w[test_mask]
    ybar_tr = np.average(y[train_mask], weights=w[train_mask])
    sst = np.sum(wt * (yt - ybar_tr) ** 2)
    sse_b = np.sum(wt * (yt - Xb_te @ bb) ** 2)
    sse_f = np.sum(wt * (yt - Xf_te @ bf) ** 2)
    return dict(n_train=int(train_mask.sum()), n_test=int(test_mask.sum()),
                r2_oos_base=1 - sse_b / sst, r2_oos_full=1 - sse_f / sst,
                dr2_oos=(sse_b - sse_f) / sst, beta_add=float(bf[-1]))

def run_protocol(base_cols, press=None, tag=""):
    if press is None:
        press = f["opponent_pressure_pregame"].to_numpy(float)
    out = {"loso": {}, "walk_forward": {}}
    for s in EXPLORATION_SEASONS:
        te = season == s
        out["loso"][str(s)] = oos_delta(base_cols, "__PRESS__", ~te, te, press)
    for tr_end, s in ((2021, 2022), (2022, 2023), (2023, 2024)):
        tr = season <= tr_end
        te = season == s
        out["walk_forward"][f"train<= {tr_end} -> test {s}"] = oos_delta(base_cols, "__PRESS__", tr, te, press)
    for k in ("loso", "walk_forward"):
        d = np.array([v["dr2_oos"] for v in out[k].values()])
        out[k + "_summary"] = dict(mean=float(d.mean()), sd=float(d.std(ddof=1)),
                                   min=float(d.min()), max=float(d.max()),
                                   n_folds=len(d), all_positive=bool((d > 0).all()))
    return out

oos = {}
for name in ("M_B_plus_venue", "M_D_plus_opp_defrtg", "M_E_pregame_baseline", "M_F_pregame_full_control"):
    oos[name] = run_protocol(SPECS[name])
    lo, wf = oos[name]["loso_summary"], oos[name]["walk_forward_summary"]
    print(f"\n  {name}  (baseline = {SPECS[name]})")
    for s in EXPLORATION_SEASONS:
        v = oos[name]["loso"][str(s)]
        print(f"    LOSO hold-out {s}: dR2_oos={v['dr2_oos']:+.6f}  beta={v['beta_add']:+.4f}  n_test={v['n_test']}")
    print(f"    LOSO   mean={lo['mean']:+.6f} sd={lo['sd']:.6f} min={lo['min']:+.6f} "
          f"max={lo['max']:+.6f} all_positive={lo['all_positive']}")
    for k, v in oos[name]["walk_forward"].items():
        print(f"    WF {k}: dR2_oos={v['dr2_oos']:+.6f}  beta={v['beta_add']:+.4f}")
    print(f"    WF     mean={wf['mean']:+.6f} sd={wf['sd']:.6f} all_positive={wf['all_positive']}")
res["out_of_sample"] = oos

# 3b. is the whole thing carried by 2021? LOSO restricted to 2022-2024.
print("\n  ROBUSTNESS -- drop 2021 entirely (E0 flagged 2021 as the strongest season):")
drop21 = {}
for name in ("M_B_plus_venue", "M_F_pregame_full_control"):
    folds = {}
    for s in (2022, 2023, 2024):
        te = season == s
        tr = (season != s) & (season != 2021)
        folds[str(s)] = oos_delta(SPECS[name], "__PRESS__", tr, te,
                                  f["opponent_pressure_pregame"].to_numpy(float))
    d = np.array([v["dr2_oos"] for v in folds.values()])
    ins = delta_r2(SPECS[name], "opponent_pressure_pregame", mask=(season != 2021))
    drop21[name] = dict(loso_2022_2024=folds, loso_mean=float(d.mean()),
                        loso_sd=float(d.std(ddof=1)), all_positive=bool((d > 0).all()),
                        in_sample_pooled_2022_2024=ins)
    print(f"    {name:26s} LOSO(2022-24) mean={d.mean():+.6f} sd={d.std(ddof=1):.6f} "
          f"all_positive={bool((d>0).all())} | in-sample pooled(2022-24) dR2={ins['dr2']:.6f}")
res["robustness_drop_2021"] = drop21

# 3c. practical size
sp = f["opponent_pressure_pregame"]
beta = insample["M_F_pregame_full_control"]["pooled"]["beta_add"]
rng_pressure = float(sp.max() - sp.min())
p10p90 = float(sp.quantile(0.9) - sp.quantile(0.1))
ymean = float(np.average(y, weights=w))
res["practical_size"] = dict(
    beta_per_unit_pressure=beta, pressure_full_range=rng_pressure, pressure_p10_p90=p10p90,
    effect_over_full_range=beta * rng_pressure, effect_over_p10_p90=beta * p10p90,
    outcome_weighted_mean=ymean,
    effect_p10_p90_as_pct_of_mean=100 * beta * p10p90 / ymean)
print(f"\n  practical size (fully-controlled beta={beta:+.4f}): p10-p90 pressure spread="
      f"{p10p90:.2f} -> {beta*p10p90:+.3f} TO/100 off poss "
      f"({100*beta*p10p90/ymean:.1f}% of the {ymean:.2f} weighted mean)")

# ===========================================================================
# PART 4 -- PLACEBO (must be NON-DEGENERATE; sd reported explicitly)
# ===========================================================================
print("\n" + "=" * 78)
print("PART 4  PLACEBO -- reassignment of ALREADY-COMPUTED values (not key permutation)")
print("=" * 78)

tg_in = tg[["team_id", "season", "game_date", "def_is_home", "def_poss", "def_tov",
            "def_pts_allowed"]]
pp = PregameTeamPressure(tg_in)
# every team's already-computed pregame pressure at every (season, date) appearing in the frame
row_ns = _ns(f["game_date"])
lookup_cache, team_index = {}, {}
for s in EXPLORATION_SEASONS:
    teams = pp.teams_by_season[s]
    team_index[s] = {t: j for j, t in enumerate(teams)}
    dates = np.unique(row_ns[season == s])
    lookup_cache[s] = (teams, {int(d): np.array([pp.lookup(t, s, int(d))[0] for t in teams])
                              for d in dates})

P = np.full((len(f), 12), np.nan)
opp_col = np.zeros(len(f), int)
for i in range(len(f)):
    s = season[i]
    teams, dm = lookup_cache[s]
    v = dm[int(row_ns[i])]
    P[i, :len(v)] = v
    opp_col[i] = team_index[s][f["opponent_team_id"].iloc[i]]

real_press = f["opponent_pressure_pregame"].to_numpy(float)
recon = P[np.arange(len(f)), opp_col]
max_err = float(np.nanmax(np.abs(recon - real_press)))
print(f"  lookup matrix reproduces the real pregame pressure exactly: max abs err = {max_err:.3e}")
assert max_err < 1e-9, "placebo lookup matrix does not reproduce the real measure"

def draw_team_permutation(r):
    """Derangement of team identity within season: every row gets ANOTHER team's
    already-computed pregame value at its own date. Not a key permutation."""
    out = np.empty(len(f))
    for s in EXPLORATION_SEASONS:
        m = season == s
        n_t = len(lookup_cache[s][0])
        while True:
            perm = r.permutation(n_t)
            if not (perm == np.arange(n_t)).any():
                break
        out[m] = P[np.flatnonzero(m), perm[opp_col[m]]]
    return out

def draw_row_shuffle(r):
    """Blunter control: shuffle the already-computed value vector across rows within season."""
    out = np.empty(len(f))
    for s in EXPLORATION_SEASONS:
        m = season == s
        v = real_press[m].copy()
        r.shuffle(v)
        out[m] = v
    return out

def stat_insample(press, base_cols):
    Xb = design(base_cols)
    Xf = np.column_stack([Xb, press])
    return r2_in(Xf, y, w)[0] - r2_in(Xb, y, w)[0]

def stat_loso(press, base_cols):
    return float(np.mean([oos_delta(base_cols, "__PRESS__", season != s, season == s, press)["dr2_oos"]
                          for s in EXPLORATION_SEASONS]))

placebo = {}
targets = [
    ("insample_M_A_E0_replication", lambda p: stat_insample(p, SPECS["M_A_E0_replication"]),
     insample["M_A_E0_replication"]["pooled"]["dr2"]),
    ("insample_M_B_venue_controlled", lambda p: stat_insample(p, SPECS["M_B_plus_venue"]),
     insample["M_B_plus_venue"]["pooled"]["dr2"]),
    ("insample_M_F_pregame_full_control", lambda p: stat_insample(p, SPECS["M_F_pregame_full_control"]),
     insample["M_F_pregame_full_control"]["pooled"]["dr2"]),
    ("loso_mean_M_B_venue_controlled", lambda p: stat_loso(p, SPECS["M_B_plus_venue"]),
     oos["M_B_plus_venue"]["loso_summary"]["mean"]),
    ("loso_mean_M_F_pregame_full_control", lambda p: stat_loso(p, SPECS["M_F_pregame_full_control"]),
     oos["M_F_pregame_full_control"]["loso_summary"]["mean"]),
]
for kind, drawer in (("team_identity_derangement", draw_team_permutation),
                     ("row_shuffle", draw_row_shuffle)):
    r = np.random.default_rng(SEED)
    draws = [drawer(r) for _ in range(N_PLACEBO)]
    for label, statfn, real in targets:
        vals = np.array([statfn(p) for p in draws])
        sd = float(vals.std(ddof=1))
        rec = dict(n_draws=N_PLACEBO, mean=float(vals.mean()), sd=sd,
                   median=float(np.median(vals)), p95=float(np.percentile(vals, 95)),
                   max=float(vals.max()), real=float(real),
                   n_draws_ge_real=int((vals >= real).sum()),
                   real_over_placebo_max=float(real / vals.max()) if vals.max() > 0 else None,
                   degenerate=bool(sd < 1e-12))
        placebo[f"{kind}__{label}"] = rec
        print(f"  {kind:26s} {label:36s} real={real:+.6f} placebo mean={rec['mean']:+.6f} "
              f"sd={sd:.6f} max={rec['max']:+.6f} draws>=real={rec['n_draws_ge_real']}/{N_PLACEBO}"
              f"{'  *** DEGENERATE ***' if rec['degenerate'] else ''}")
        assert not rec["degenerate"], f"DEGENERATE PLACEBO (sd=0) for {kind}/{label} -- no-op control"
res["placebo"] = placebo
print("\n  All placebo sds are non-zero -> the negative control is NOT the no-op form.")

# ===========================================================================
# PART 5 -- RELIABILITY OF THE INSTRUMENT (ambiguous-null guard)
# ===========================================================================
print("\n" + "=" * 78)
print("PART 5  RELIABILITY OF THE PRESSURE MEASURE")
print("=" * 78)
rel = {}
sh = []
for s in EXPLORATION_SEASONS:
    d = tg[tg["season"] == s].sort_values("game_date")
    a, b = [], []
    for t, gg in d.groupby("team_id"):
        gg = gg.sort_values("game_date")
        h = len(gg) // 2
        a.append(100 * gg["def_tov"].iloc[:h].sum() / gg["def_poss"].iloc[:h].sum())
        b.append(100 * gg["def_tov"].iloc[h:].sum() / gg["def_poss"].iloc[h:].sum())
    r_ = float(np.corrcoef(a, b)[0, 1])
    rel[f"split_half_{s}"] = dict(r=r_, n_teams=len(a))
    sh.append(r_)
    print(f"  split-half {s}: r={r_:+.3f}  (n={len(a)} teams)")
ts = tg.groupby(["team_id", "season"]).apply(
    lambda d: 100 * d["def_tov"].sum() / d["def_poss"].sum(), include_groups=False)
pairs = [(ts.get((t, s)), ts.get((t, s + 1))) for (t, s) in ts.index if (t, s + 1) in ts.index]
pairs = [(x, z) for x, z in pairs if x is not None and z is not None]
r_soso = float(np.corrcoef([p[0] for p in pairs], [p[1] for p in pairs])[0, 1])
rel["season_over_season_r"] = dict(r=r_soso, n_pairs=len(pairs))
rel["split_half_mean_r"] = float(np.mean(sh))
print(f"  season-over-season r={r_soso:+.3f} (n={len(pairs)} team-season pairs)")
print(f"  NOTE: 12 teams per season -- these correlations are individually imprecise.")
res["instrument_reliability"] = rel

# ===========================================================================
# VERDICT
# ===========================================================================
retained_venue = insample["M_B_plus_venue"]["retained_vs_M_A"]
loso_B = oos["M_B_plus_venue"]["loso_summary"]
loso_F = oos["M_F_pregame_full_control"]["loso_summary"]
plac_B = placebo["team_identity_derangement__loso_mean_M_B_venue_controlled"]
plac_F = placebo["team_identity_derangement__loso_mean_M_F_pregame_full_control"]

keep = (retained_venue > 0.5 and loso_B["all_positive"] and loso_F["all_positive"]
        and plac_B["n_draws_ge_real"] == 0 and plac_F["n_draws_ge_real"] == 0
        and rel["split_half_mean_r"] > 0.3)
res["verdict"] = "keep-as-lead" if keep else "kill"
res["verdict_inputs"] = dict(
    retained_after_home_away_control=retained_venue,
    loso_all_positive_venue_controlled=loso_B["all_positive"],
    loso_all_positive_full_pregame_control=loso_F["all_positive"],
    placebo_draws_ge_real_venue_controlled=plac_B["n_draws_ge_real"],
    placebo_draws_ge_real_full_control=plac_F["n_draws_ge_real"],
    instrument_split_half_mean_r=rel["split_half_mean_r"])
print("\n" + "=" * 78)
print(f"E1 VERDICT: {res['verdict']}")
print(f"  effect retained after home/away control: {100*retained_venue:.1f}% of E0's dR2")
print(f"  LOSO out-of-sample (venue-controlled):   mean={loso_B['mean']:+.6f} sd={loso_B['sd']:.6f} "
      f"all_positive={loso_B['all_positive']}")
print(f"  LOSO out-of-sample (full pregame ctrl):  mean={loso_F['mean']:+.6f} sd={loso_F['sd']:.6f} "
      f"all_positive={loso_F['all_positive']}")
print("=" * 78)

with open(f"{OUT}/FINDINGS.json", "w") as fh:
    json.dump(res, fh, indent=2, default=float)
print("wrote FINDINGS.json")
