"""
STEP 2 -- reproduce the PUBLISHED numbers using each screen's helper AS-IS.
STEP 3 -- re-run every dR2 under (i) standard weighted R2 and (ii) plain unweighted OLS R2.

Helpers are copied VERBATIM from the frozen screens. Nothing outside this directory is written.
Partition: 2021-2024 only (asserted).
"""
import json
import numpy as np
import pandas as pd

D = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_r2_rerun"
EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]
res = {}

# ===========================================================================
# THREE R2 CONVENTIONS
# ===========================================================================
def r2_defective(y, X, w):
    """VERBATIM from E0_I0009_additive_pressure/analyze.py lines 40-48 (wls_r2)."""
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    yw = y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    sse = float(resid @ resid)
    sst = float(((yw - yw.mean()) ** 2).sum())          # <-- THE DEFECT
    return beta, (1 - sse / sst if sst > 0 else np.nan)

def r2_standard_weighted(y, X, w):
    """VERBATIM logic from E1_I0009_additive_pressure/analyze.py lines 63-72 (fit + r2_in)."""
    s = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * s[:, None], y * s, rcond=None)
    r = y - X @ beta
    ybar = np.average(y, weights=w)
    return beta, 1.0 - np.sum(w * r ** 2) / np.sum(w * (y - ybar) ** 2)

def r2_plain_ols(y, X, w=None):
    """ADOPTED CONVENTION: unweighted OLS fit, SSE/SST both unweighted, SST about y.mean()."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return beta, 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())

CONV = {"defective_weighted": r2_defective,
        "standard_weighted": r2_standard_weighted,
        "plain_unweighted_ols": r2_plain_ols}

# ===========================================================================
# E0 FRAME  -- the screen whose PUBLISHED numbers really are defective
# ===========================================================================
df0 = pd.read_csv(f"{D}/E0_player_game_analysis.csv", parse_dates=["game_date"])
assert set(df0["season"].unique()).issubset(set(EXPLORATION_SEASONS))
Y0 = df0["turnovers_per_100_off_poss"].to_numpy(float)
W0 = df0["realised_off_possessions"].to_numpy(float)
S0 = df0["season"].to_numpy(int)
COL0 = {c: df0[c].to_numpy(float) for c in
        ["player_tendency_loo", "opponent_pressure_loo", "opponent_pressure_pregame",
         "opponent_defrtg_loo", "opponent_defrtg_pregame"]}

def design(*cols):
    return np.column_stack([np.ones(len(cols[0]))] + list(cols))

def d_r2(conv, Y, W, base, add, mask):
    fn = CONV[conv]
    bc = [c[mask] for c in base]
    _, r2b = fn(Y[mask], design(*bc), W[mask])
    beta, r2f = fn(Y[mask], design(*bc, add[mask]), W[mask])
    return float(r2f - r2b), float(beta[-1])

ALL0 = np.ones(len(Y0), bool)

E0_PUBLISHED = {
    "E0_rung1_pooled_dR2":            (0.008424, [COL0["player_tendency_loo"]], COL0["opponent_pressure_loo"], ALL0),
    "E0_rung2_pooled_dR2":            (0.006505, [COL0["player_tendency_loo"]], COL0["opponent_pressure_pregame"], ALL0),
    "E0_rung2_2021_dR2":              (0.015038, [COL0["player_tendency_loo"]], COL0["opponent_pressure_pregame"], S0 == 2021),
    "E0_rung2_2022_dR2":              (0.005329, [COL0["player_tendency_loo"]], COL0["opponent_pressure_pregame"], S0 == 2022),
    "E0_rung2_2023_dR2":              (0.002279, [COL0["player_tendency_loo"]], COL0["opponent_pressure_pregame"], S0 == 2023),
    "E0_rung2_2024_dR2":              (0.006121, [COL0["player_tendency_loo"]], COL0["opponent_pressure_pregame"], S0 == 2024),
}
# published rung-1/2 with opponent-quality control (from E0 summary.json)
with open(f"{D}/E0_summary_published.json") as fh:
    e0_pub = json.load(fh)
E0_PUBLISHED["E0_rung1_dR2_defrtg_controlled"] = (
    e0_pub["confound"]["rung1_dR2_controlled"],
    [COL0["player_tendency_loo"], COL0["opponent_defrtg_loo"]], COL0["opponent_pressure_loo"], ALL0)
E0_PUBLISHED["E0_rung2_dR2_defrtg_controlled"] = (
    e0_pub["confound"]["rung2_dR2_controlled"],
    [COL0["player_tendency_loo"], COL0["opponent_defrtg_pregame"]], COL0["opponent_pressure_pregame"], ALL0)

print("=" * 100)
print("STEP 2/3  E0 SCREEN  (published numbers ARE defective-convention)")
print("=" * 100)
print(f"{'quantity':38s} {'published':>11s} {'repro(def)':>11s} {'|delta|':>10s} "
      f"{'std wtd':>11s} {'plain OLS':>11s} {'bias%':>8s}")
e0_tab = {}
for name, (pub, base, add, mask) in E0_PUBLISHED.items():
    dd, _ = d_r2("defective_weighted", Y0, W0, base, add, mask)
    ds, _ = d_r2("standard_weighted", Y0, W0, base, add, mask)
    dp, bp = d_r2("plain_unweighted_ols", Y0, W0, base, add, mask)
    bias = 100.0 * (dd / ds - 1.0)
    e0_tab[name] = dict(published=pub, reproduced_defective=dd, abs_repro_delta=abs(dd - pub),
                        standard_weighted=ds, plain_unweighted_ols=dp,
                        realised_bias_pct_vs_standard=bias,
                        ratio_defective_over_standard=dd / ds, beta_plain_ols=bp,
                        n=int(mask.sum()))
    print(f"{name:38s} {pub:11.6f} {dd:11.6f} {abs(dd-pub):10.2e} {ds:11.6f} {dp:11.6f} {bias:+7.2f}%")
res["E0_table"] = e0_tab
max_delta0 = max(v["abs_repro_delta"] for v in e0_tab.values())
print(f"\n  MAX |reproduction delta| over E0 published figures = {max_delta0:.3e}")
res["E0_reproduction_max_abs_delta"] = max_delta0
res["E0_reproduction_ok"] = bool(max_delta0 < 1e-6)

# ===========================================================================
# E1 FRAME
# ===========================================================================
f = pd.read_csv(f"{D}/player_game_analysis.csv", parse_dates=["game_date"])
tg = pd.read_csv(f"{D}/team_game_defense.csv", parse_dates=["game_date"])
assert set(f["season"].unique()).issubset(set(EXPLORATION_SEASONS))
assert set(tg["season"].unique()).issubset(set(EXPLORATION_SEASONS))

# rebuild opp_prior_home_share exactly as E1 analyze.py lines 45-54
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

Y = f["turnovers_per_100_off_poss"].to_numpy(float)
W = f["realised_off_possessions"].to_numpy(float)
S = f["season"].to_numpy(int)
PRESS = f["opponent_pressure_pregame"].to_numpy(float)
ALL = np.ones(len(Y), bool)
C = {c: f[c].to_numpy(float) for c in
     ["player_tendency_loo", "player_tendency_pregame", "player_is_home",
      "opp_prior_home_share", "opponent_defrtg_pregame", "opponent_pressure_pregame",
      "opponent_pressure_pregame_venue"]}

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
# published in-sample pooled dR2 (E1 run_log.txt lines 32-37) -- STANDARD WEIGHTED convention
E1_PUB_INSAMPLE = {"M_A_E0_replication": 0.007035, "M_B_plus_venue": 0.007045,
                   "M_C_plus_schedule_balance": 0.007013, "M_D_plus_opp_defrtg": 0.005999,
                   "M_E_pregame_baseline": 0.006765, "M_F_pregame_full_control": 0.005649}

print("\n" + "=" * 100)
print("STEP 2/3  E1 SCREEN IN-SAMPLE  (published numbers are ALREADY standard weighted)")
print("=" * 100)
print(f"{'quantity':34s} {'published':>11s} {'repro(std)':>11s} {'|delta|':>10s} "
      f"{'defective':>11s} {'plain OLS':>11s} {'bias%':>8s}")
e1_tab = {}
for name, cols in SPECS.items():
    base = [C[c] for c in cols]
    dd, _ = d_r2("defective_weighted", Y, W, base, PRESS, ALL)
    ds, _ = d_r2("standard_weighted", Y, W, base, PRESS, ALL)
    dp, bp = d_r2("plain_unweighted_ols", Y, W, base, PRESS, ALL)
    pub = E1_PUB_INSAMPLE[name]
    e1_tab[f"E1_insample_{name}_pooled_dR2"] = dict(
        published=pub, published_convention="standard_weighted",
        reproduced_published_convention=ds, abs_repro_delta=abs(ds - pub),
        defective_weighted=dd, standard_weighted=ds, plain_unweighted_ols=dp,
        realised_bias_pct_defective_vs_standard=100.0 * (dd / ds - 1.0),
        change_pct_plain_vs_standard=100.0 * (dp / ds - 1.0), beta_plain_ols=bp, n=int(len(Y)))
    print(f"{name:34s} {pub:11.6f} {ds:11.6f} {abs(ds-pub):10.2e} {dd:11.6f} {dp:11.6f} "
          f"{100*(dd/ds-1):+7.2f}%")
res["E1_insample_table"] = e1_tab

# per-season in-sample for M_A (the E0-comparable rung)
per_season = {}
for s in EXPLORATION_SEASONS:
    m = S == s
    base = [C["player_tendency_loo"]]
    dd, _ = d_r2("defective_weighted", Y, W, base, PRESS, m)
    ds, _ = d_r2("standard_weighted", Y, W, base, PRESS, m)
    dp, _ = d_r2("plain_unweighted_ols", Y, W, base, PRESS, m)
    per_season[str(s)] = dict(defective_weighted=dd, standard_weighted=ds, plain_unweighted_ols=dp,
                              realised_bias_pct=100.0 * (dd / ds - 1.0), n=int(m.sum()))
res["E1_insample_M_A_per_season"] = per_season

# ===========================================================================
# OUT-OF-SAMPLE (the headline +0.004003 lives here)
# ===========================================================================
def oos(conv, base_cols, train, test, press):
    def mat(cols, m):
        return np.column_stack([np.ones(m.sum())] + [C[c][m] for c in cols])
    Xb_tr, Xb_te = mat(base_cols, train), mat(base_cols, test)
    Xf_tr = np.column_stack([Xb_tr, press[train]])
    Xf_te = np.column_stack([Xb_te, press[test]])
    yt = Y[test]
    if conv == "plain_unweighted_ols":
        bb, *_ = np.linalg.lstsq(Xb_tr, Y[train], rcond=None)
        bf, *_ = np.linalg.lstsq(Xf_tr, Y[train], rcond=None)
        ybar = Y[train].mean()
        sst = float(((yt - ybar) ** 2).sum())
        sse_b = float(((yt - Xb_te @ bb) ** 2).sum())
        sse_f = float(((yt - Xf_te @ bf) ** 2).sum())
    else:
        s_tr = np.sqrt(W[train]); wt = W[test]
        bb, *_ = np.linalg.lstsq(Xb_tr * s_tr[:, None], Y[train] * s_tr, rcond=None)
        bf, *_ = np.linalg.lstsq(Xf_tr * s_tr[:, None], Y[train] * s_tr, rcond=None)
        if conv == "standard_weighted":
            ybar = np.average(Y[train], weights=W[train])
            sst = float(np.sum(wt * (yt - ybar) ** 2))
            sse_b = float(np.sum(wt * (yt - Xb_te @ bb) ** 2))
            sse_f = float(np.sum(wt * (yt - Xf_te @ bf) ** 2))
        else:  # defective analogue: sqrt-w transformed space, SST about the TRAIN transformed mean
            s_te = np.sqrt(wt)
            ywt = yt * s_te
            ybar_tr_t = float((Y[train] * s_tr).mean())
            sst = float(((ywt - ybar_tr_t) ** 2).sum())
            sse_b = float(np.sum(wt * (yt - Xb_te @ bb) ** 2))
            sse_f = float(np.sum(wt * (yt - Xf_te @ bf) ** 2))
    return dict(dr2_oos=(sse_b - sse_f) / sst, beta_add=float(bf[-1]),
                n_train=int(train.sum()), n_test=int(test.sum()))

FOLDS_LOSO = [(f"loso_{s}", S != s, S == s) for s in EXPLORATION_SEASONS]
FOLDS_WF = [(f"wf_train<={a}_test_{b}", S <= a, S == b) for a, b in ((2021, 2022), (2022, 2023), (2023, 2024))]

E1_PUB_OOS = {  # from run_log.txt
    ("M_B_plus_venue", "loso"): 0.007071, ("M_B_plus_venue", "wf"): 0.004003,
    ("M_D_plus_opp_defrtg", "loso"): 0.006297, ("M_D_plus_opp_defrtg", "wf"): 0.003270,
    ("M_E_pregame_baseline", "loso"): 0.006731, ("M_E_pregame_baseline", "wf"): 0.003479,
    ("M_F_pregame_full_control", "loso"): 0.005908, ("M_F_pregame_full_control", "wf"): 0.002795,
}

print("\n" + "=" * 100)
print("STEP 2/3  E1 OUT-OF-SAMPLE  (HEADLINE +0.004003 = M_B walk-forward mean)")
print("=" * 100)
print(f"{'quantity':44s} {'published':>11s} {'repro(std)':>11s} {'|delta|':>10s} "
      f"{'defective':>11s} {'plain OLS':>11s} {'bias%':>8s}")
oos_tab = {}
for name in ("M_B_plus_venue", "M_D_plus_opp_defrtg", "M_E_pregame_baseline", "M_F_pregame_full_control"):
    cols = SPECS[name]
    for tag, folds in (("loso", FOLDS_LOSO), ("wf", FOLDS_WF)):
        vals = {}
        for conv in CONV:
            v = np.array([oos(conv, cols, tr, te, PRESS)["dr2_oos"] for _, tr, te in folds])
            vals[conv] = v
        pub = E1_PUB_OOS[(name, tag)]
        ds = float(vals["standard_weighted"].mean())
        dd = float(vals["defective_weighted"].mean())
        dp = float(vals["plain_unweighted_ols"].mean())
        key = f"E1_oos_{tag}_mean_{name}"
        oos_tab[key] = dict(
            published=pub, published_convention="standard_weighted",
            reproduced_published_convention=ds, abs_repro_delta=abs(ds - pub),
            defective_weighted=dd, standard_weighted=ds, plain_unweighted_ols=dp,
            realised_bias_pct_defective_vs_standard=100.0 * (dd / ds - 1.0),
            change_pct_plain_vs_standard=100.0 * (dp / ds - 1.0),
            folds_standard_weighted={fl[0]: float(x) for fl, x in zip(folds, vals["standard_weighted"])},
            folds_plain_unweighted_ols={fl[0]: float(x) for fl, x in zip(folds, vals["plain_unweighted_ols"])},
            folds_defective={fl[0]: float(x) for fl, x in zip(folds, vals["defective_weighted"])},
            sd_standard_weighted=float(vals["standard_weighted"].std(ddof=1)),
            sd_plain_unweighted_ols=float(vals["plain_unweighted_ols"].std(ddof=1)),
            all_positive_standard=bool((vals["standard_weighted"] > 0).all()),
            all_positive_plain=bool((vals["plain_unweighted_ols"] > 0).all()))
        print(f"{key:44s} {pub:11.6f} {ds:11.6f} {abs(ds-pub):10.2e} {dd:11.6f} {dp:11.6f} "
              f"{100*(dd/ds-1):+7.2f}%")
res["E1_oos_table"] = oos_tab

deltas = ([v["abs_repro_delta"] for v in e1_tab.values()]
          + [v["abs_repro_delta"] for v in oos_tab.values()])
res["E1_reproduction_max_abs_delta"] = float(max(deltas))
res["E1_reproduction_ok"] = bool(max(deltas) < 1e-6)
print(f"\n  MAX |reproduction delta| over E1 published figures = {max(deltas):.3e}")

with open(f"{D}/step23_results.json", "w") as fh:
    json.dump(res, fh, indent=2, default=float)
print("wrote step23_results.json")
