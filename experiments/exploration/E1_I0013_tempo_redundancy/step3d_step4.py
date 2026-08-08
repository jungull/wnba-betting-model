"""E1 I0013 -- Step 3D (what is actually inside exp_gposs) and Step 4 (the 2023 anomaly).

STEP 3D runs on the FULL E0 analysis frame (n = 10,167) so every number is directly comparable to
the published dR2 = 0.001133, not to the step-3 common sample.

  * which half carries it: dR2(own_pace48 | base) vs dR2(opp_pace48 | base)
  * absorption by own-team-season FE alone, opponent-team-season FE alone, and both
  * the competing-mechanism test the E0 confound ladder never ran: the player's OWN TEAM's
    strictly-prior assists per 100 possessions.  A fast team that also passes a lot would produce
    exactly this survivor without any possession-volume channel.

STEP 4 investigates the negative 2023 beta: per-season dR2 and beta each against ITS OWN
correct-level null, plus instrument-validity, dispersion, coverage and schedule diagnostics, plus
a permutation test of whether the four betas are more spread out than chance.

TIME WINDOWS: every constructed quantity is base.prior_expanding (aggregate to date, then strict
cumulative-minus-self within season+key) -> strictly earlier games, same season, only.
R2 CONVENTION (D069): plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean.
PARTITION: 2021-2024 only.
"""
import json
import os

import numpy as np
import pandas as pd

import e1_lib as L
import base as B

rng = np.random.default_rng(L.SEED + 2)
NPERM = 300

L.hdr("REBUILD FULL FRAME (n should be 10,167)")
W, TEAM, mp, mt = L.build_frame("ast")
y = W["s"].to_numpy(float)
seas = W["season"].to_numpy()
base0 = L.e0_basecols(W)
Mz = B.zwithin(W, "exp_gposs").to_numpy(float)
Q0, ry0, sst0 = L.prep_fast(y, base0)
REF = L.incr(Q0, ry0, sst0, Mz)
print("  reference dR2(exp_gposs | E0 base) on the full frame = %.9f" % REF)

PANEL = L.TeamPanel(TEAM, "pace48")
A1, c01, sq = PANEL.bind(W, "opp_team_id")
A2, c02, _ = PANEL.bind(W, "team_id")
GP = L.GamePerm(W, "exp_gposs")
raw = W["exp_gposs"].to_numpy(float)


def rung(name, extra, desc, nperm=NPERM):
    cols = base0 + list(extra)
    Q, ry, sst = L.prep_fast(y, cols)
    real = L.incr(Q, ry, sst, Mz)
    bet = L.beta_from_qr(Q, ry, Mz)
    ts = [L.incr(Q, ry, sst, L.center_within(
        0.5 * (L.perm_team(A1, c01, sq, rng) + L.perm_team(A2, c02, sq, rng)), sq))
        for _ in range(nperm)]
    gm = [L.incr(Q, ry, sst, L.center_within(GP.draw(rng), seas)) for _ in range(nperm)]
    rw = [L.incr(Q, ry, sst, L.center_within(L.perm_rows(raw, seas, rng), seas))
          for _ in range(nperm)]
    o = dict(rung=name, description=desc, n=int(len(W)), n_extra_cols=len(list(extra)),
             R2_rung=float(L.r2(y, cols)), dR2_exp_gposs=float(real), beta_exp_gposs=float(bet),
             retained_frac_vs_base=float(real / REF),
             null_team_season=L.summarize(ts, real, "team-season relabel (CORRECT LEVEL)"),
             null_game_level=L.summarize(gm, real, "game-level value permutation"),
             null_row_naive=L.summarize(rw, real, "NAIVE row-level (WRONG; contrast only)"))
    print("  %-46s dR2=%.6f (%.0f%% of base) beta=%+.4f | p_ts=%.4f p_game=%.4f p_rowNAIVE=%.4f"
          % (name, real, 100 * real / REF, bet, o["null_team_season"]["frac_ge_real"],
             o["null_game_level"]["frac_ge_real"], o["null_row_naive"]["frac_ge_real"]))
    return o, (ts, gm, rw)


# ==================================================================== 3D-1 which half carries it
L.hdr("STEP 3D-1 -- WHICH HALF OF exp_gposs CARRIES THE INCREMENT?")
halves = {}
for nm in ["own_pace48", "opp_pace48", "exp_gposs"]:
    v = B.zwithin(W, nm).to_numpy(float)
    d = L.incr(Q0, ry0, sst0, v)
    b = L.beta_from_qr(Q0, ry0, v)
    halves[nm] = dict(dR2=float(d), beta=float(b))
    print("  %-12s dR2=%.6f  beta=%+.4f" % (nm, d, b))
print("  corr(own_pace48, opp_pace48) within season = %+.4f"
      % float(np.corrcoef(B.zwithin(W, "own_pace48"), B.zwithin(W, "opp_pace48"))[0, 1]))

# ==================================================================== 3D-2 team FE absorption
L.hdr("STEP 3D-2 -- TEAM FIXED-EFFECT ABSORPTION (full frame)")
own_fe = L.dummies(W["team_id"].astype(str) + "_" + W["season"].astype(str))
opp_fe = L.dummies(W["opp_team_id"].astype(str) + "_" + W["season"].astype(str))
RUNGS, DRAWS = [], {}
for nm, ex, ds in [
    ("F1  base + OWN team-season FE", own_fe,
     "absorbs every fixed difference between the player's own team-seasons"),
    ("F2  base + OPP team-season FE", opp_fe,
     "absorbs every fixed difference between opponent team-seasons"),
    ("F3  base + OWN + OPP team-season FE", own_fe + opp_fe,
     "absorbs all between-team-season variation on both sides; only the within-season evolution "
     "of each team's expanding pace estimate survives")]:
    r, dr = rung(nm, ex, ds)
    RUNGS.append(r); DRAWS[nm.split()[0]] = dr

# ==================================================================== 3D-3 own-team assist rate
L.hdr("STEP 3D-3 -- THE COMPETING MECHANISM: OWN-TEAM PASSING RATE (strictly prior)")
tp = B.team_possessions(mt)
t = mt.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"], how="left")
for c in ["ast", "opp_ast", "pts", "opp_pts"]:
    t[c] = pd.to_numeric(t[c], errors="coerce").astype("float64")
t["n_ast"] = t["ast"]
t["n_oast"] = t["opp_ast"]
t["n_pts"] = t["pts"]
t["n_poss"] = t["team_poss"]
pe = B.prior_expanding(t, ["season", "team_id"], ["n_ast", "n_oast", "n_pts", "n_poss"], "pr_")
u = pe["pr_n_poss"] / 100.0
TA = pe[["season", "team_id", "game_id"]].copy()
TA["ast100"] = np.where(u > 0, pe["pr_n_ast"] / u, np.nan)      # team's OWN assists per 100
TA["astA100"] = np.where(u > 0, pe["pr_n_oast"] / u, np.nan)    # assists the team ALLOWS per 100
TA["ortg"] = np.where(u > 0, pe["pr_n_pts"] / u, np.nan)        # team's OWN points per 100
TA.loc[pe["pr_n_poss"] < 300, ["ast100", "astA100", "ortg"]] = np.nan
L.guard(TA, "team pregame passing table")

W2 = W.merge(TA.rename(columns={"ast100": "own_ast100", "astA100": "own_astA100",
                                "ortg": "own_ortg"}),
             on=["season", "game_id", "team_id"], how="left")
W2 = W2.merge(TA.rename(columns={"team_id": "opp_team_id", "ast100": "opp_ast100",
                                 "astA100": "opp_astA100", "ortg": "opp_ortg"}),
              on=["season", "game_id", "opp_team_id"], how="left")
assert len(W2) == len(W)
cov = {c: float(W2[c].notna().mean()) for c in ["own_ast100", "opp_astA100", "own_ortg"]}
print("  coverage: %s" % cov)
for c in ["own_ast100", "opp_astA100", "own_ortg", "opp_ortg"]:
    W2[c] = W2[c].fillna(W2.groupby("season")[c].transform("mean"))
oa = B.zwithin(W2, "own_ast100").to_numpy(float)
oaA = B.zwithin(W2, "opp_astA100").to_numpy(float)
oo = B.zwithin(W2, "own_ortg").to_numpy(float)
po = B.zwithin(W2, "opp_ortg").to_numpy(float)
print("  corr(own_ast100, exp_gposs) within season = %+.4f" % float(np.corrcoef(oa, Mz)[0, 1])
      + "   corr(own_ast100, own_pace48) = %+.4f"
      % float(np.corrcoef(oa, B.zwithin(W2, "own_pace48"))[0, 1]))
print("  dR2(own_ast100 | E0 base) = %.6f   beta=%+.4f"
      % (L.incr(Q0, ry0, sst0, oa), L.beta_from_qr(Q0, ry0, oa)))

for nm, ex, ds in [
    ("G1  base + own-team prior ast/100", [oa],
     "the player's OWN team's strictly-prior assists per 100 possessions -- a pass-heavy offensive "
     "system, which is the obvious competing explanation for a positive tempo-to-assists link"),
    ("G2  base + own ast/100 + opp ast-allowed/100", [oa, oaA],
     "both sides' strictly-prior assist rates"),
    ("G3  base + own/opp ast rates + own/opp ortg", [oa, oaA, oo, po],
     "both sides' assist rates and offensive ratings")]:
    r, dr = rung(nm, ex, ds)
    RUNGS.append(r); DRAWS[nm.split()[0]] = dr

pd.DataFrame({("%s_%s" % (k, w)): pd.Series(v)
              for k, (a, b_, c_) in DRAWS.items()
              for w, v in (("team_season", a), ("game_level", b_), ("row_naive", c_))}).to_csv(
    os.path.join(L.OUT, "perm_draws_step3d.csv"), index=False)
print("  wrote perm_draws_step3d.csv")

# ==================================================================== STEP 4 -- the 2023 anomaly
L.hdr("STEP 4 -- THE 2023 ANOMALY: per-season effect against ITS OWN correct-level null")
per_season = []
season_draws = {}
for s in L.PARTITION:
    m = seas == s
    Ws = W[m].reset_index(drop=True)
    ys = y[m]
    bs = [c[m] for c in base0]
    qs, rys, ssts = L.prep_fast(ys, bs)
    v = Ws["exp_gposs"].to_numpy(float)
    vz = (v - v.mean()) / v.std()
    real_d = L.incr(qs, rys, ssts, vz)
    real_b = L.beta_from_qr(qs, rys, vz)
    a1, k1, s1 = PANEL.bind(Ws, "opp_team_id")
    a2, k2, _ = PANEL.bind(Ws, "team_id")
    gps = L.GamePerm(Ws, "exp_gposs")
    dts, bts, dgm = [], [], []
    for _ in range(NPERM):
        pv = 0.5 * (L.perm_team(a1, k1, s1, rng) + L.perm_team(a2, k2, s1, rng))
        pv = L.center_within(pv, s1)
        dts.append(L.incr(qs, rys, ssts, pv))
        bts.append(L.beta_from_qr(qs, rys, pv))
        dgm.append(L.incr(qs, rys, ssts, L.center_within(gps.draw(rng), s1)))
    bts = np.asarray(bts)
    rec = dict(
        season=int(s), n=int(m.sum()), n_games=int(Ws["game_id"].nunique()),
        n_teams=int(Ws["team_id"].nunique()),
        dR2=float(real_d), beta=float(real_b),
        null_team_season_dR2=L.summarize(dts, real_d, "team-season relabel within this season"),
        null_game_level_dR2=L.summarize(dgm, real_d, "game-level permutation within this season"),
        beta_null_mean=float(bts.mean()), beta_null_sd=float(bts.std(ddof=1)),
        beta_null_p2_5=float(np.percentile(bts, 2.5)),
        beta_null_p97_5=float(np.percentile(bts, 97.5)),
        beta_two_sided_frac_ge_abs=float((np.abs(bts) >= abs(real_b)).mean()),
        beta_z_vs_null=float((real_b - bts.mean()) / bts.std(ddof=1)))
    per_season.append(rec)
    season_draws["%d_dR2_teamseason" % s] = pd.Series(dts)
    season_draws["%d_beta_teamseason" % s] = pd.Series(bts)
    print("  %d n=%5d games=%3d | dR2=%.6f p_ts=%.4f p_game=%.4f | beta=%+.4f "
          "(null mean %+.4f sd %.4f, 95%% [%+.4f,%+.4f], two-sided p=%.3f, z=%+.2f)"
          % (s, rec["n"], rec["n_games"], rec["dR2"],
             rec["null_team_season_dR2"]["frac_ge_real"],
             rec["null_game_level_dR2"]["frac_ge_real"], rec["beta"],
             rec["beta_null_mean"], rec["beta_null_sd"], rec["beta_null_p2_5"],
             rec["beta_null_p97_5"], rec["beta_two_sided_frac_ge_abs"], rec["beta_z_vs_null"]))
pd.DataFrame(season_draws).to_csv(os.path.join(L.OUT, "perm_draws_per_season.csv"), index=False)

# ---- is the season-to-season spread of betas bigger than chance?
L.hdr("STEP 4 -- IS THE FOUR-SEASON BETA SPREAD LARGER THAN CHANCE?")
real_betas = np.array([r["beta"] for r in per_season])
real_spread = float(real_betas.max() - real_betas.min())
real_sd = float(real_betas.std(ddof=1))
sp, sd_ = [], []
for i in range(NPERM):
    bb = [season_draws["%d_beta_teamseason" % s].iloc[i] for s in L.PARTITION]
    bb = np.asarray(bb)
    sp.append(bb.max() - bb.min())
    sd_.append(bb.std(ddof=1))
sp, sd_ = np.asarray(sp), np.asarray(sd_)
het = dict(real_betas={int(r["season"]): r["beta"] for r in per_season},
           real_range=real_spread, real_sd=real_sd,
           null_range_mean=float(sp.mean()), null_range_sd=float(sp.std(ddof=1)),
           frac_null_range_ge_real=float((sp >= real_spread).mean()),
           null_sd_mean=float(sd_.mean()), frac_null_sd_ge_real=float((sd_ >= real_sd).mean()),
           n_seasons_positive=int((real_betas > 0).sum()))
print("  real per-season betas: %s" % np.round(real_betas, 4).tolist())
print("  real range = %.4f ; null range mean = %.4f sd = %.4f ; frac(null >= real) = %.3f"
      % (real_spread, sp.mean(), sp.std(ddof=1), het["frac_null_range_ge_real"]))
print("  real sd    = %.4f ; frac(null sd >= real sd) = %.3f" % (real_sd, het["frac_null_sd_ge_real"]))
print("  -> the four-season spread is %s than the null produces by chance."
      % ("NO LARGER" if het["frac_null_range_ge_real"] > 0.10 else "LARGER"))

# ==================================================================== 2023 forensics
L.hdr("STEP 4 -- 2023 FORENSICS: coverage, dispersion, instrument validity, schedule")
tp_all = B.team_possessions(mt)
tg = tp_all.merge(TEAM[["season", "game_id", "team_id", "pace48", "prior_poss"]],
                  on=["season", "game_id", "team_id"], how="left")
gposs = tp_all.groupby(["season", "game_id"])["team_poss"].sum().rename("game_poss").reset_index()
Wg = W.merge(gposs, on=["season", "game_id"], how="left")

forensics = []
for s in L.PARTITION:
    tgs = tg[tg["season"] == s]
    ws = Wg[Wg["season"] == s]
    gp = gposs[gposs["season"] == s]
    seasmean = tgs.groupby("team_id")["team_poss"].mean()
    dates = pd.to_datetime(tgs["gdate"]).dt.date
    gaps = pd.Series(sorted(set(dates)))
    gapd = gaps.diff().dt.days.dropna() if len(gaps) > 1 else pd.Series(dtype=float)
    rec = dict(
        season=int(s),
        n_team_games=int(len(tgs)), n_games=int(tgs["game_id"].nunique()),
        games_per_team=float(tgs.groupby("team_id").size().mean()),
        pace48_nonnull_frac=float(tgs["pace48"].notna().mean()),
        analysis_rows=int(len(ws)),
        # dispersion of the FEATURE
        exp_gposs_mean=float(ws["exp_gposs"].mean()), exp_gposs_sd=float(ws["exp_gposs"].std()),
        exp_gposs_min=float(ws["exp_gposs"].min()), exp_gposs_max=float(ws["exp_gposs"].max()),
        # dispersion of TRUE team pace across teams (the thing the feature tries to measure)
        true_team_pace_sd_across_teams=float(seasmean.std()),
        true_team_pace_mean=float(seasmean.mean()),
        realized_game_poss_mean=float(gp["game_poss"].mean()),
        realized_game_poss_sd=float(gp["game_poss"].std()),
        # instrument validity: does the pregame estimate still predict the realised game?
        corr_expgposs_vs_realized_gameposs=float(
            ws[["exp_gposs", "game_poss"]].corr().iloc[0, 1]),
        # outcome link: does a faster realised game actually produce more assists?
        corr_realized_gameposs_vs_ast=float(ws[["game_poss", "s"]].corr().iloc[0, 1]),
        corr_expgposs_vs_ast=float(ws[["exp_gposs", "s"]].corr().iloc[0, 1]),
        league_ast_per_game=float(ws["s"].mean()),
        # schedule / coverage breaks
        first_date=str(pd.to_datetime(tgs["gdate"]).min().date()),
        last_date=str(pd.to_datetime(tgs["gdate"]).max().date()),
        n_distinct_dates=int(len(gaps)),
        max_gap_days=float(gapd.max()) if len(gapd) else np.nan,
        n_gaps_ge_7_days=int((gapd >= 7).sum()) if len(gapd) else 0)
    forensics.append(rec)

print("  %-6s %6s %6s %7s %9s %9s %11s %11s %10s %9s %9s"
      % ("season", "rows", "games", "g/team", "expg_sd", "truepc_sd", "r(exp,real)",
         "r(real,ast)", "r(exp,ast)", "maxgap", "gaps>=7"))
for r in forensics:
    print("  %-6d %6d %6d %7.1f %9.3f %9.3f %11.4f %11.4f %10.4f %9.0f %9d"
          % (r["season"], r["analysis_rows"], r["n_games"], r["games_per_team"],
             r["exp_gposs_sd"], r["true_team_pace_sd_across_teams"],
             r["corr_expgposs_vs_realized_gameposs"], r["corr_realized_gameposs_vs_ast"],
             r["corr_expgposs_vs_ast"], r["max_gap_days"], r["n_gaps_ge_7_days"]))

# split-half reliability of the pace instrument, per season
L.hdr("STEP 4 -- SPLIT-HALF RELIABILITY OF TEAM PACE, PER SEASON")
rel = []
for s in L.PARTITION:
    d = tp_all[tp_all["season"] == s].sort_values(["team_id", "gdate"]).copy()
    d["_rk"] = d.groupby("team_id", sort=False).cumcount()
    d["_h"] = d["_rk"] % 2
    piv = d.pivot_table(index="team_id", columns="_h", values="team_poss", aggfunc="mean").dropna()
    r_ = float(np.corrcoef(piv[0].values, piv[1].values)[0, 1])
    sb = 2 * r_ / (1 + r_)
    rel.append(dict(season=int(s), r_half=r_, spearman_brown=sb, n_teams=int(len(piv))))
    print("  %d  odd/even split-half r=%.4f  Spearman-Brown=%.4f  (n=%d teams)"
          % (s, r_, sb, len(piv)))

out = dict(
    r2_convention="plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean (D069); "
                  "raw ast count outcome; no weights anywhere",
    n=int(len(W)), reference_dR2=float(REF),
    halves=halves, own_team_control_coverage=cov,
    dR2_own_ast100_over_base=float(L.incr(Q0, ry0, sst0, oa)),
    rungs=RUNGS, per_season=per_season, beta_heterogeneity=het,
    forensics_2021_2024=forensics, split_half_reliability=rel,
    n_perm=NPERM, seed=L.SEED + 2)
with open(os.path.join(L.OUT, "step3d_step4.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=float)
print("\n  wrote step3d_step4.json")
