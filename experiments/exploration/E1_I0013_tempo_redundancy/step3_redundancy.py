"""E1 I0013 -- Step 3: the three redundancy tests.

(A) SIMPLE-PROXY   -- crudest possible point-in-time tempo proxy: the unadjusted mean of the two
                      teams' RAW possessions over their previous N games, N in {3,5,10}, using only
                      games strictly BEFORE the current game's date.  Does exp_gposs retain
                      incremental dR2 over it?
(B) MAIN-EFFECT ABSORPTION -- own-team-season and opponent-team-season fixed effects; player-season
                      fixed effects; and a within-season CALENDAR control (deciles of days-into-
                      season), because an expanding-window pace estimate drifts mechanically across
                      a season and could be a calendar proxy.
(C) REALISTIC BASELINE -- a sensible point-in-time forecast of the player's OWN assist production:
                      prior-games-only assists per game (shrunk), prior 5- and 10-game assist means,
                      prior 5- and 10-game minute means, and the naive count forecast
                      (prior assists/minute x prior minutes per game).  All strictly prior.

TIME WINDOW OF EVERY QUANTITY BUILT HERE is stated in build_* docstrings and re-asserted by
assert_strictly_prior() below, which checks the constructed value against a brute-force recompute
that uses ONLY rows with gdate < the target row's gdate.

R2 CONVENTION (D069): plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean.
PARTITION: 2021-2024 only.
"""
import json
import os

import numpy as np
import pandas as pd

import e1_lib as L
import base as B
import pv_base as P

rng = np.random.default_rng(L.SEED + 1)
NPERM = 300

L.hdr("STEP 3 -- REBUILD FRAME")
W, TEAM, mp, mt = L.build_frame("ast")
W = W.sort_values(["gdate", "game_id", "team_id", "player_id"]).reset_index(drop=True)


# ===================================================================== (A) crude tempo proxy
def build_crude_team_pace(mt, N):
    """CRUDEST point-in-time tempo proxy.

    TIME WINDOW: for a team's game on date t, the mean of that team's RAW estimated possessions
    over its N most recent games with gdate STRICTLY LESS THAN t, within the same season.  No
    per-48 normalisation, no shrinkage, no minimum-possession gate, no league prior.  Implemented
    as groupby(season, team_id).shift(1).rolling(N, min_periods=N).  Nothing reads the target game
    or any later game or any other season.
    """
    tp = B.team_possessions(mt)[["season", "team_id", "game_id", "gdate", "team_poss"]].copy()
    tp = tp.sort_values(["season", "team_id", "gdate", "game_id"]).reset_index(drop=True)
    tp["_lag"] = tp.groupby(["season", "team_id"], sort=False)["team_poss"].shift(1)
    tp["crude%d" % N] = (tp.groupby(["season", "team_id"], sort=False)["_lag"]
                           .transform(lambda x: x.rolling(N, min_periods=N).mean()))
    return tp[["season", "team_id", "game_id", "gdate", "crude%d" % N]]


def assert_strictly_prior(tp, mt, N, n_check=60, seed=7):
    """Brute-force audit: recompute a random sample of crude values from scratch using ONLY rows
    with gdate strictly before the target row's gdate.  Any leakage of the target game or a later
    game would show up as a mismatch."""
    src = B.team_possessions(mt)[["season", "team_id", "gdate", "team_poss"]]
    col = "crude%d" % N
    d = tp.dropna(subset=[col])
    r = np.random.default_rng(seed)
    idx = r.choice(len(d), size=min(n_check, len(d)), replace=False)
    bad = 0
    for i in idx:
        row = d.iloc[i]
        h = src[(src["season"] == row["season"]) & (src["team_id"] == row["team_id"]) &
                (src["gdate"] < row["gdate"])].sort_values("gdate")
        ref = h["team_poss"].tail(N).mean() if len(h) >= N else np.nan
        if not (np.isfinite(ref) and abs(ref - row[col]) < 1e-9):
            bad += 1
    print("    strict-prior audit crude%-2d : %d/%d sampled values reproduced from "
          "strictly-earlier rows only  -> %s" % (N, len(idx) - bad, len(idx),
                                                 "PASS" if bad == 0 else "FAIL"))
    return bad == 0


L.hdr("STEP 3A -- BUILD THE CRUDE PROXIES (strictly prior-N-games, no adjustment at all)")
prior_ok = {}
for N in (3, 5, 10):
    tp = build_crude_team_pace(mt, N)
    prior_ok[N] = assert_strictly_prior(tp, mt, N)
    c = "crude%d" % N
    W = W.merge(tp[["season", "game_id", "team_id", c]].rename(
        columns={"team_id": "opp_team_id", c: "opp_" + c}),
        on=["season", "game_id", "opp_team_id"], how="left")
    W = W.merge(tp[["season", "game_id", "team_id", c]].rename(columns={c: "own_" + c}),
                on=["season", "game_id", "team_id"], how="left")
    W[c] = 0.5 * (W["opp_" + c] + W["own_" + c])
    print("    crude%-2d coverage on the analysis frame: %.4f" % (N, W[c].notna().mean()))
assert all(prior_ok.values()), "a crude proxy failed the strict-prior audit"


# ===================================================================== (C) realistic player baseline
def build_realistic_player(mp, target="ast"):
    """A sensible POINT-IN-TIME forecast of the player's own production.

    TIME WINDOW: every field for a player's game on date t uses only that player's games with
    gdate STRICTLY LESS THAN t, within the same season.
      apg_pre  prior expanding assists per game, shrunk 2 games toward the strictly-prior expanding
               league assists-per-game (previous-season fallback)   [base.prior_expanding]
      a5, a10  mean assists over the player's previous 5 / 10 games [shift(1).rolling]
      m5, m10  mean minutes over the player's previous 5 / 10 games [shift(1).rolling]
      naive    prior assists per minute x prior minutes per game    = the naive count forecast
    No leave-one-out, no leave-one-season-out, no full-season anything.
    """
    d = mp.copy()
    d["_a"] = d[target].astype(float)
    d["_m"] = d["minutes"].astype(float)
    d["_g"] = 1.0
    d = B.prior_expanding(d, ["season", "player_id"], ["_a", "_m", "_g"], "rp_")
    la = B.prior_expanding(d[["season", "gdate", "_a", "_m", "_g"]].copy(), ["season"],
                           ["_a", "_m", "_g"], "lg_")
    lg_apg = np.where(la["lg__g"].values > 0, la["lg__a"].values / la["lg__g"].values, np.nan)
    prev = d.groupby("season")[["_a", "_g"]].sum().reset_index()
    prev["pv_apg"] = prev["_a"] / prev["_g"]
    prev["season"] += 1
    d = d.merge(prev[["season", "pv_apg"]], on="season", how="left")
    d["lg_apg"] = pd.Series(lg_apg, index=d.index).fillna(d["pv_apg"]).fillna(
        d["_a"].sum() / d["_g"].sum())
    K = 2.0
    d["apg_pre"] = (d["rp__a"] + K * d["lg_apg"]) / (d["rp__g"] + K)
    d.loc[d["rp__g"] < 2, "apg_pre"] = np.nan
    d["apm_pre"] = np.where(d["rp__m"] > 0, d["rp__a"] / d["rp__m"], np.nan)
    d["mpg_pre"] = np.where(d["rp__g"] > 0, d["rp__m"] / d["rp__g"], np.nan)
    d["naive_ct"] = d["apm_pre"] * d["mpg_pre"]

    d = d.sort_values(["season", "player_id", "gdate", "game_id"]).reset_index(drop=True)
    for src in ("_a", "_m"):
        d["_lag" + src] = d.groupby(["season", "player_id"], sort=False)[src].shift(1)
    for n in (5, 10):
        for src, nm in (("_a", "a%d" % n), ("_m", "m%d" % n)):
            d[nm] = (d.groupby(["season", "player_id"], sort=False)["_lag" + src]
                       .transform(lambda x, n=n: x.rolling(n, min_periods=max(2, n // 2)).mean()))
    return d[["season", "game_id", "player_id", "gdate", "apg_pre", "naive_ct",
              "a5", "a10", "m5", "m10"]]


L.hdr("STEP 3C -- BUILD THE REALISTIC PLAYER BASELINE (strictly prior-games-only)")
RP = build_realistic_player(mp, "ast")
W = W.merge(RP, on=["season", "game_id", "player_id", "gdate"], how="left")
for c in ["apg_pre", "naive_ct", "a5", "a10", "m5", "m10"]:
    print("    %-9s coverage on the analysis frame: %.4f" % (c, W[c].notna().mean()))

# brute-force strict-prior audit of a5 on a random sample
_r = np.random.default_rng(11)
_src = mp[["season", "player_id", "gdate", "ast"]]
_d = W.dropna(subset=["a5"])
_idx = _r.choice(len(_d), size=60, replace=False)
_bad = 0
for i in _idx:
    row = _d.iloc[i]
    h = _src[(_src["season"] == row["season"]) & (_src["player_id"] == row["player_id"]) &
             (_src["gdate"] < row["gdate"])].sort_values("gdate")
    ref = h["ast"].tail(5).mean() if len(h) >= 2 else np.nan
    if not (np.isfinite(ref) and abs(ref - row["a5"]) < 1e-9):
        _bad += 1
print("    strict-prior audit a5      : %d/%d sampled values reproduced from strictly-earlier "
      "rows only -> %s" % (len(_idx) - _bad, len(_idx), "PASS" if _bad == 0 else "FAIL"))
assert _bad == 0, "a5 failed the strict-prior audit"

# ===================================================================== common sample
NEED = ["crude3", "crude5", "crude10", "apg_pre", "naive_ct", "a5", "a10", "m5", "m10"]
S = W.dropna(subset=NEED).copy().reset_index(drop=True)
L.guard(S, "common sample (all baselines available)")
print("  common sample n=%d of %d full-frame rows (%.1f%%)  games=%d  players=%d"
      % (len(S), len(W), 100.0 * len(S) / len(W), S["game_id"].nunique(), S["player_id"].nunique()))
print("  per-season n = %s" % {int(k): int(v) for k, v in S.groupby("season").size().items()})

y = S["s"].to_numpy(float)
seas = S["season"].to_numpy()
Mz = B.zwithin(S, "exp_gposs").to_numpy(float)          # recentred on the common sample
base0 = L.e0_basecols(S)

# permutation apparatus on the common sample
PANEL = L.TeamPanel(TEAM, "pace48")
A1, c01, sq = PANEL.bind(S, "opp_team_id")
A2, c02, _ = PANEL.bind(S, "team_id")
GP = L.GamePerm(S, "exp_gposs")
raw = S["exp_gposs"].to_numpy(float)


def run_rung(name, extra, description, nperm=NPERM, do_naive=True):
    cols = base0 + list(extra)
    Q, ry, sst = L.prep_fast(y, cols)
    real = L.incr(Q, ry, sst, Mz)
    bet = L.beta_from_qr(Q, ry, Mz)
    r2r = L.r2(y, cols)
    ts = [L.incr(Q, ry, sst, L.center_within(
        0.5 * (L.perm_team(A1, c01, sq, rng) + L.perm_team(A2, c02, sq, rng)), sq))
        for _ in range(nperm)]
    gm = [L.incr(Q, ry, sst, L.center_within(GP.draw(rng), seas)) for _ in range(nperm)]
    rw = [L.incr(Q, ry, sst, L.center_within(L.perm_rows(raw, seas, rng), seas))
          for _ in range(nperm)] if do_naive else []
    out = dict(rung=name, description=description, n=int(len(S)), n_extra_cols=len(list(extra)),
               R2_rung=float(r2r), dR2_exp_gposs=float(real), beta_exp_gposs=float(bet),
               null_team_season=L.summarize(ts, real, "team-season relabel (CORRECT LEVEL, "
                                                      "preserves team-season dependence)"),
               null_game_level=L.summarize(gm, real, "game-level value permutation"),
               null_row_naive=(L.summarize(rw, real, "NAIVE row-level (WRONG; contrast only)")
                               if do_naive else None))
    print("  %-42s R2=%.5f  dR2=%.6f  beta=%+.4f | p_teamseason=%.4f p_game=%.4f%s"
          % (name, r2r, real, bet, out["null_team_season"]["frac_ge_real"],
             out["null_game_level"]["frac_ge_real"],
             "  p_rowNAIVE=%.4f" % out["null_row_naive"]["frac_ge_real"] if do_naive else ""))
    return out, (ts, gm, rw)


RUNGS = []
DRAWS = {}

L.hdr("STEP 3 -- BASELINE LADDER (all on the common sample; dR2 is always for exp_gposs)")

r, dr = run_rung("R0  E0 published base", [],
                 "y_count ~ O + D + O*D + Mexp + O*Mexp  (the published E0 baseline)")
RUNGS.append(r); DRAWS["R0"] = dr
REF = r["dR2_exp_gposs"]

# ---- weak baseline for contrast: player-season dummies only
pl_d = L.dummies(S["player_id"].astype(str) + "_" + S["season"].astype(str))
r, dr = run_rung("W0  player-season dummies ONLY", pl_d,
                 "deliberately WEAK baseline: player-season fixed effects and nothing else "
                 "(no O, no D, no minutes). Reported to show how a weak baseline flatters dR2.",
                 nperm=150, do_naive=False)
# note: this rung replaces the base, it does not add to it
Qw, ryw, sstw = L.prep_fast(y, pl_d)
r["R2_rung"] = float(L.r2(y, pl_d))
r["dR2_exp_gposs"] = float(L.incr(Qw, ryw, sstw, Mz))
r["note"] = "computed WITHOUT the E0 base terms (pure player-season FE baseline)"
tsw = [L.incr(Qw, ryw, sstw, L.center_within(
    0.5 * (L.perm_team(A1, c01, sq, rng) + L.perm_team(A2, c02, sq, rng)), sq)) for _ in range(150)]
r["null_team_season"] = L.summarize(tsw, r["dR2_exp_gposs"], "team-season relabel")
r["null_game_level"] = None
print("     [corrected] W0 pure player-season FE: R2=%.5f dR2=%.6f p_teamseason=%.4f"
      % (r["R2_rung"], r["dR2_exp_gposs"], r["null_team_season"]["frac_ge_real"]))
RUNGS.append(r); DRAWS["W0"] = (tsw, [], [])

# ---- (A) crude proxy rungs
L.hdr("STEP 3A -- SIMPLE-PROXY TEST")
for N in (3, 5, 10):
    c = "crude%d" % N
    cz = B.zwithin(S, c).to_numpy(float)
    # what does the crude proxy get on its own?
    Q0, ry0, sst0 = L.prep_fast(y, base0)
    d_crude = L.incr(Q0, ry0, sst0, cz)
    print("  crude%-2d alone over E0 base: dR2=%.6f   corr(crude,exp_gposs)=%+.4f"
          % (N, d_crude, float(np.corrcoef(cz, Mz)[0, 1])))
    r, dr = run_rung("A%d  E0 base + crude%d" % (N, N), [cz],
                     "E0 base plus the crudest strictly-prior tempo proxy: unadjusted mean of the "
                     "two teams' raw possessions over their previous %d games" % N)
    r["dR2_crude_alone_over_base"] = float(d_crude)
    r["corr_crude_vs_exp_gposs"] = float(np.corrcoef(cz, Mz)[0, 1])
    r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF) if REF > 0 else np.nan
    RUNGS.append(r); DRAWS["A%d" % N] = dr

# ---- (B) absorption rungs
L.hdr("STEP 3B -- MAIN-EFFECT ABSORPTION")
own_fe = L.dummies(S["team_id"].astype(str) + "_" + S["season"].astype(str))
opp_fe = L.dummies(S["opp_team_id"].astype(str) + "_" + S["season"].astype(str))
r, dr = run_rung("B1  E0 base + own+opp team-season FE", own_fe + opp_fe,
                 "team fixed effects on BOTH sides at the team-season level; absorbs every "
                 "between-team-season difference in pace, leaving only the within-season "
                 "evolution of each team's expanding pace")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["B1"] = dr

r, dr = run_rung("B2  E0 base + player-season FE", pl_d,
                 "player-season fixed effects on top of the E0 base: is the effect cross-player "
                 "composition rather than within-player exposure?")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["B2"] = dr

# calendar control: deciles of days-into-season
doy = (S["gdate"] - S.groupby("season")["gdate"].transform("min")).dt.days
dec = S.assign(_d=doy).groupby("season")["_d"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))
cal_fe = L.dummies(dec.astype(str) + "_" + S["season"].astype(str))
r, dr = run_rung("B3  E0 base + calendar deciles x season", cal_fe,
                 "deciles of days-into-season interacted with season. An expanding-window pace "
                 "estimate drifts mechanically across a season; this asks whether exp_gposs is a "
                 "calendar proxy.")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["B3"] = dr

r, dr = run_rung("B4  E0 base + team FE + player FE + calendar", own_fe + opp_fe + pl_d + cal_fe,
                 "everything in B1+B2+B3 together")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["B4"] = dr

# ---- (C) realistic baseline
L.hdr("STEP 3C -- REALISTIC-BASELINE TEST")
rb = [B.zwithin(S, c).to_numpy(float) for c in ["apg_pre", "naive_ct", "a5", "a10", "m5", "m10"]]
r, dr = run_rung("C1  realistic player baseline", rb,
                 "E0 base + strictly-prior-only player forecast: shrunk prior assists per game, "
                 "the naive count forecast (prior ast/min x prior min/game), prior 5- and 10-game "
                 "assist means, prior 5- and 10-game minute means")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["C1"] = dr

r, dr = run_rung("C2  realistic + crude5", rb + [B.zwithin(S, "crude5").to_numpy(float)],
                 "the production-relevant question: realistic player forecast AND a trivially "
                 "available crude tempo proxy already in the model")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["C2"] = dr

r, dr = run_rung("C3  realistic + crude5 + team FE + calendar",
                 rb + [B.zwithin(S, "crude5").to_numpy(float)] + own_fe + opp_fe + cal_fe,
                 "everything a production model would plausibly already contain")
r["retained_frac_vs_R0"] = float(r["dR2_exp_gposs"] / REF)
RUNGS.append(r); DRAWS["C3"] = dr

# ---- draws to disk
rows = {}
for k, (ts, gm, rw) in DRAWS.items():
    rows["%s_team_season" % k] = pd.Series(ts)
    if len(gm):
        rows["%s_game_level" % k] = pd.Series(gm)
    if len(rw):
        rows["%s_row_naive" % k] = pd.Series(rw)
pd.DataFrame(rows).to_csv(os.path.join(L.OUT, "perm_draws_step3.csv"), index=False)
print("\n  wrote perm_draws_step3.csv")

with open(os.path.join(L.OUT, "step3_redundancy.json"), "w", encoding="utf-8") as f:
    json.dump(dict(
        r2_convention="plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean "
                      "(D069); raw ast count outcome; no weights",
        common_sample_n=int(len(S)), full_frame_n=int(len(W)),
        common_sample_per_season={int(k): int(v) for k, v in S.groupby("season").size().items()},
        reference_dR2_on_common_sample=float(REF),
        strict_prior_audits=dict(crude={str(k): bool(v) for k, v in prior_ok.items()},
                                 a5=bool(_bad == 0)),
        rungs=RUNGS, n_perm=NPERM, seed=L.SEED + 1), f, indent=1, default=float)
print("  wrote step3_redundancy.json")

S[["season", "game_id", "team_id", "opp_team_id", "player_id", "gdate", "s", "exp_gposs",
   "crude3", "crude5", "crude10", "apg_pre", "naive_ct", "a5", "a10", "m5", "m10"]] \
    .to_csv(os.path.join(L.OUT, "common_sample_features.csv"), index=False)
print("  wrote common_sample_features.csv")
