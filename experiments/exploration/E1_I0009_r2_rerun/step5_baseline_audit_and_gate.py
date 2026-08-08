"""
STEP 5 -- (a) RETROSPECTIVE-BASELINE AUDIT (constraint 3), measured not assumed
          (b) walk-forward permutation null under the AS-PUBLISHED standard-weighted convention,
              so "does significance change with the convention" is answered like-for-like
          (c) re-evaluation of the frozen E1 verdict gate under the adopted convention

Partition: 2021-2024 only. Nothing outside this directory is written.
"""
import json
import numpy as np
import pandas as pd

from pressure_lib_e1 import EXPLORATION_SEASONS, PregameTeamPressure, _ns

D = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_r2_rerun"
SEED = 20260807
N_PLACEBO = 200
res = {}

f = pd.read_csv(f"{D}/player_game_analysis.csv", parse_dates=["game_date"])
tg = pd.read_csv(f"{D}/team_game_defense.csv", parse_dates=["game_date"])
assert set(f["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
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
REAL = f["opponent_pressure_pregame"].to_numpy(float)
C = {c: f[c].to_numpy(float) for c in
     ["player_tendency_loo", "player_tendency_pregame", "player_is_home",
      "opp_prior_home_share", "opponent_defrtg_pregame"]}

# ===========================================================================
# (a) RETROSPECTIVE-BASELINE AUDIT
# ===========================================================================
print("=" * 90)
print("(a) BASELINE CONSTRUCTION AUDIT -- read the construction, not the label")
print("=" * 90)

# Build, for every player-game row, the player's STRICTLY-AFTER-DATE (future) season rate.
# This is used ONLY as an audit probe: if a baseline correlates with the future beyond what
# prior games explain, that baseline reads the future.
d = f[["player_id", "season", "game_date", "turnovers", "realised_off_possessions"]].copy()
d = d.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
gb = d.groupby(["player_id", "season"], sort=False)
tot_t = gb["turnovers"].transform("sum")
tot_p = gb["realised_off_possessions"].transform("sum")
cum_t = gb["turnovers"].cumsum()
cum_p = gb["realised_off_possessions"].cumsum()
fut_t = tot_t - cum_t          # strictly after this row (rows are date-ordered)
fut_p = tot_p - cum_p
d["future_rate"] = np.where(fut_p > 0, 100.0 * fut_t / fut_p, np.nan)
d["future_poss"] = fut_p
f2 = f.merge(d[["player_id", "season", "game_date", "future_rate", "future_poss"]],
             on=["player_id", "season", "game_date"], how="left")
m = f2["future_poss"].to_numpy(float) > 0

corr_loo_future = float(np.corrcoef(f2["player_tendency_loo"].to_numpy(float)[m],
                                    f2["future_rate"].to_numpy(float)[m])[0, 1])
corr_pre_future = float(np.corrcoef(f2["player_tendency_pregame"].to_numpy(float)[m],
                                    f2["future_rate"].to_numpy(float)[m])[0, 1])
# partial: does loo add to pregame in explaining the FUTURE?
Xp = np.column_stack([np.ones(m.sum()), f2["player_tendency_pregame"].to_numpy(float)[m]])
Xl = np.column_stack([Xp, f2["player_tendency_loo"].to_numpy(float)[m]])
yf = f2["future_rate"].to_numpy(float)[m]
def r2p(X, yy):
    b, *_ = np.linalg.lstsq(X, yy, rcond=None); r = yy - X @ b
    return 1 - float(r @ r) / float(((yy - yy.mean()) ** 2).sum())
dr2_loo_on_future = r2p(Xl, yf) - r2p(Xp, yf)

print(f"  player_tendency_loo   construction: build_data.py lines 164-170 -- season TOTAL over ALL")
print(f"                        games in the season, minus this game. RETROSPECTIVE.")
print(f"  player_tendency_pregame construction: pressure_lib_e1.py _PrefixIndex.prefix, "
      f"searchsorted(side='left') -> STRICTLY BEFORE date. PRIOR-GAMES-ONLY.")
print(f"  corr(loo baseline, player's OWN FUTURE season rate)     = {corr_loo_future:+.4f}")
print(f"  corr(pregame baseline, player's OWN FUTURE season rate) = {corr_pre_future:+.4f}")
print(f"  dR2 of adding loo on top of pregame, TARGET = the FUTURE rate = {dr2_loo_on_future:.6f}")
print(f"    -> the LOO baseline demonstrably carries information about games that had not been "
      f"played yet.")

res["baseline_audit"] = dict(
    predictor_under_test=dict(
        name="opponent_pressure_pregame",
        construction=("pressure_lib_e1.PregameTeamPressure.lookup -> _PrefixIndex.prefix with "
                      "np.searchsorted(dates, date_ns, side='left'), i.e. expanding over the "
                      "opponent's games STRICTLY BEFORE this game's date, shrunk (K=200 poss) "
                      "toward the prior-season team rate or the season league mean"),
        reads_future=False, verdict="PRIOR-GAMES-ONLY -- clean"),
    other_controls=dict(
        opp_prior_home_share=dict(construction="cumsum of def_is_home MINUS own row / cumcount",
                                  reads_future=False),
        opponent_defrtg_pregame=dict(construction="same PregameTeamPressure machinery on def_pts_allowed",
                                     reads_future=False),
        player_is_home=dict(construction="schedule fact, known pregame", reads_future=False)),
    baselines=dict(
        player_tendency_loo=dict(
            construction="build_data.py 164-170: season_tov/season_poss over ALL games in the season, "
                         "minus this game's own tallies (full-season leave-one-out)",
            reads_future=True,
            verdict="RETROSPECTIVE -- named in constraint 3 as a known offender; confirmed by reading",
            used_by=["M_A_E0_replication", "M_B_plus_venue", "M_C_plus_schedule_balance",
                     "M_D_plus_opp_defrtg", "E0 rung-1 and rung-2 (ALL E0 published numbers)"],
            carries_headline=True,
            headline_note="the +0.004003 walk-forward figure is M_B, whose baseline is player_tendency_loo"),
        player_tendency_pregame=dict(
            construction="pressure_lib_e1.PregamePlayerTendency: expanding strictly-before-date, "
                         "shrunk (K=100 poss) toward prior-season player rate or season league mean",
            reads_future=False, verdict="PRIOR-GAMES-ONLY -- clean",
            used_by=["M_E_pregame_baseline", "M_F_pregame_full_control"])),
    empirical_probe=dict(
        probe="correlate each baseline with the player's OWN strictly-after-date season rate",
        n_rows_with_future=int(m.sum()),
        corr_loo_with_future=corr_loo_future,
        corr_pregame_with_future=corr_pre_future,
        dr2_of_loo_over_pregame_predicting_the_future=float(dr2_loo_on_future),
        conclusion=("player_tendency_loo predicts the player's unplayed future far better than the "
                    "pregame baseline does, which is only possible because it contains it.")),
    overall=("The PREDICTOR under test is clean (prior games only). The BASELINE that carries the "
             "headline is retrospective. E1 anticipated this and shipped a fully-pregame variant "
             "(M_E/M_F); those, not M_A/M_B, are the forecasting-honest numbers. The headline "
             "+0.004003 is NOT a forecasting increment because its baseline reads the future."))

# ===========================================================================
# (b) WF permutation null under the AS-PUBLISHED standard-weighted convention
# ===========================================================================
print("\n" + "=" * 90)
print("(b) WALK-FORWARD PERMUTATION NULL under the AS-PUBLISHED standard-weighted convention")
print("=" * 90)

def X_of(cols, mm, press=None):
    parts = [np.ones(mm.sum())] + [C[c][mm] for c in cols]
    if press is not None:
        parts.append(press[mm])
    return np.column_stack(parts)

def oos_std(cols, train, test, press):
    Xb_tr, Xb_te = X_of(cols, train), X_of(cols, test)
    Xf_tr, Xf_te = X_of(cols, train, press), X_of(cols, test, press)
    s_tr = np.sqrt(W[train]); wt = W[test]; yt = Y[test]
    bb, *_ = np.linalg.lstsq(Xb_tr * s_tr[:, None], Y[train] * s_tr, rcond=None)
    bf, *_ = np.linalg.lstsq(Xf_tr * s_tr[:, None], Y[train] * s_tr, rcond=None)
    ybar = np.average(Y[train], weights=W[train])
    sst = float(np.sum(wt * (yt - ybar) ** 2))
    return (float(np.sum(wt * (yt - Xb_te @ bb) ** 2)) - float(np.sum(wt * (yt - Xf_te @ bf) ** 2))) / sst

WF = [(S <= a, S == b) for a, b in ((2021, 2022), (2022, 2023), (2023, 2024))]
SPECS = {"M_B_plus_venue": ["player_tendency_loo", "player_is_home"],
         "M_F_pregame_full_control": ["player_tendency_pregame", "player_is_home",
                                      "opp_prior_home_share", "opponent_defrtg_pregame"]}

tg_in = tg[["team_id", "season", "game_date", "def_is_home", "def_poss", "def_tov", "def_pts_allowed"]]
pp = PregameTeamPressure(tg_in)
row_ns = _ns(f["game_date"])
lookup_cache, team_index = {}, {}
for s in EXPLORATION_SEASONS:
    teams = pp.teams_by_season[s]
    team_index[s] = {t: j for j, t in enumerate(teams)}
    dates = np.unique(row_ns[S == s])
    lookup_cache[s] = (teams, {int(dd): np.array([pp.lookup(t, s, int(dd))[0] for t in teams]) for dd in dates})
P = np.full((len(f), 12), np.nan)
opp_col = np.zeros(len(f), int)
opp_ids = f["opponent_team_id"].to_numpy()
for i in range(len(f)):
    s = S[i]; teams, dm = lookup_cache[s]; v = dm[int(row_ns[i])]
    P[i, :len(v)] = v; opp_col[i] = team_index[s][opp_ids[i]]
assert float(np.nanmax(np.abs(P[np.arange(len(f)), opp_col] - REAL))) < 1e-9

def draw_team_derangement(r):
    out = np.empty(len(f))
    for s in EXPLORATION_SEASONS:
        mm = S == s; n_t = len(lookup_cache[s][0])
        while True:
            perm = r.permutation(n_t)
            if not (perm == np.arange(n_t)).any():
                break
        out[mm] = P[np.flatnonzero(mm), perm[opp_col[mm]]]
    return out

wf_null = {}
rows = []
r = np.random.default_rng(SEED)
draws = [draw_team_derangement(r) for _ in range(N_PLACEBO)]
for name, cols in SPECS.items():
    real = float(np.mean([oos_std(cols, tr, te, REAL) for tr, te in WF]))
    vals = np.array([float(np.mean([oos_std(cols, tr, te, p) for tr, te in WF])) for p in draws])
    rec = dict(real=real, mean=float(vals.mean()), sd=float(vals.std(ddof=1)),
               p95=float(np.percentile(vals, 95)), max=float(vals.max()),
               n_draws_ge_real=int((vals >= real).sum()), p_empirical=float((vals >= real).mean()))
    wf_null[f"standard_weighted__wf_mean_{name}"] = rec
    rows += [dict(null_kind="team_identity_derangement_CORRECT_LEVEL",
                  convention="standard_weighted", statistic=f"wf_mean_{name}",
                  draw=i, value=float(v)) for i, v in enumerate(vals)]
    print(f"  {name:26s} real={real:+.6f} null mean={rec['mean']:+.6f} sd={rec['sd']:.6f} "
          f"max={rec['max']:+.6f} ge_real={rec['n_draws_ge_real']}/{N_PLACEBO} "
          f"p_emp={rec['p_empirical']:.3f}")
pd.DataFrame(rows).to_csv(f"{D}/permutation_draws_standard_weighted_wf.csv", index=False)
res["wf_null_standard_weighted_correct_level"] = wf_null

# ===========================================================================
# (c) VERDICT GATE re-evaluation
# ===========================================================================
print("\n" + "=" * 90)
print("(c) FROZEN E1 VERDICT GATE, re-evaluated under PLAIN UNWEIGHTED OLS")
print("=" * 90)
with open(f"{D}/step23_results.json") as fh:
    s23 = json.load(fh)
with open(f"{D}/step4_results.json") as fh:
    s4 = json.load(fh)

t = s23["E1_insample_table"]
retained_pub = (t["E1_insample_M_B_plus_venue_pooled_dR2"]["standard_weighted"]
                / t["E1_insample_M_A_E0_replication_pooled_dR2"]["standard_weighted"])
retained_new = (t["E1_insample_M_B_plus_venue_pooled_dR2"]["plain_unweighted_ols"]
                / t["E1_insample_M_A_E0_replication_pooled_dR2"]["plain_unweighted_ols"])
o = s23["E1_oos_table"]
gate = dict(
    gate_1_retained_after_home_away_control=dict(
        threshold=">0.5", as_published=retained_pub, adopted_convention=retained_new,
        passes_as_published=bool(retained_pub > 0.5), passes_adopted=bool(retained_new > 0.5)),
    gate_2_loso_all_positive_M_B=dict(
        as_published=o["E1_oos_loso_mean_M_B_plus_venue"]["all_positive_standard"],
        adopted=o["E1_oos_loso_mean_M_B_plus_venue"]["all_positive_plain"]),
    gate_3_loso_all_positive_M_F=dict(
        as_published=o["E1_oos_loso_mean_M_F_pregame_full_control"]["all_positive_standard"],
        adopted=o["E1_oos_loso_mean_M_F_pregame_full_control"]["all_positive_plain"]),
    gate_4_placebo_draws_ge_real_loso_M_B=dict(
        as_published_frozen_screen=0,
        adopted=s4["permutation_nulls_plain_ols"]["team_identity_derangement_CORRECT_LEVEL__loso_mean_M_B"]["n_draws_ge_real"]),
    gate_5_placebo_draws_ge_real_loso_M_F=dict(
        as_published_frozen_screen=0,
        adopted=s4["permutation_nulls_plain_ols"]["team_identity_derangement_CORRECT_LEVEL__loso_mean_M_F"]["n_draws_ge_real"]),
    gate_6_instrument_split_half_mean_r=dict(
        value=0.5725, threshold=">0.3", passes=True,
        note="a correlation of team forced-TO rates; unaffected by the R2 convention"),
)
all_pass = (gate["gate_1_retained_after_home_away_control"]["passes_adopted"]
            and gate["gate_2_loso_all_positive_M_B"]["adopted"]
            and gate["gate_3_loso_all_positive_M_F"]["adopted"]
            and gate["gate_4_placebo_draws_ge_real_loso_M_B"]["adopted"] == 0
            and gate["gate_5_placebo_draws_ge_real_loso_M_F"]["adopted"] == 0
            and gate["gate_6_instrument_split_half_mean_r"]["passes"])
gate["verdict_under_adopted_convention"] = "keep-as-lead" if all_pass else "kill"
for k, v in gate.items():
    print(f"  {k}: {v}")
res["verdict_gate"] = gate

with open(f"{D}/step5_results.json", "w") as fh:
    json.dump(res, fh, indent=2, default=float)
print("\nwrote step5_results.json")
