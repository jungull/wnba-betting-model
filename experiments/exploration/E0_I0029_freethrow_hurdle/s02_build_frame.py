"""E0_I0029 s02 -- BUILD THE SCREEN FRAME.

EVERY constructed column is declared in TIME_WINDOW_TABLE below, covering FEATURES AND INFERENCE,
and every prior-only claim is then verified BY BRUTE-FORCE RECOMPUTATION on a random sample rather
than by inspection.  The retrospective-baseline trap has six instances in this programme, one of
which entered through the INFERENCE machinery, so the probes deliberately include a
DISCRIMINATION arm: a probe that only shows "my column equals a prior recomputation" is vacuous if
the prior and contemporaneous recomputations happen to agree.  Each probe therefore also checks
that the column DOES NOT equal the contemporaneous recomputation.

THE CONDITIONAL-STAGE REFERENCES ARE MATCHED.  For stages B and C the reference is built on the
player's PRIOR GAMES WITH fta>0 -- not on all prior games -- because that is the matched
prior-history reference for a conditional target.  Building it on all prior games would make the
reference artificially weak and manufacture a finding.  D087: reference incompleteness is the
top-ranked source of false results in this programme.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (EWMA_HALFLIFE, HEADLINE_SEASONS, HISTORY_FLOOR, MP_PATH, OUT, SEASONS, SEED,
                     TARGETS, TARGET_ORDER, TARGET_PCT, assert_partition, hdr, jsonable,
                     prior_ewma, prior_mean, prior_sum, prior_trail, safe_div)

rep = {}

# =====================================================================================
# 0. TIME-WINDOW TABLE -- MANDATORY, covering FEATURES AND INFERENCE
# =====================================================================================
TIME_WINDOW_TABLE = [
    dict(column="y_any_fta / y_fta_given / y_ftm_given / y_fta / y_ftm / y_pts",
         construction="THIS GAME's box score",
         window="[game]", reads_future=True, role="RESPONSE ONLY",
         evidence="never appears on the right-hand side of any fit in this screen"),
    dict(column="minutes (contemporaneous)",
         construction="THIS GAME's minutes",
         window="[game]", reads_future=True, role="ORACLE RUNG EXPOSURE ONLY (O2/O3/O4)",
         evidence="s03 uses d['minutes'] exclusively inside rungs LABELLED ORACLE; no honest rung "
                  "and no candidate touches it"),
    dict(column="fta (contemporaneous)",
         construction="THIS GAME's free-throw attempts",
         window="[game]", reads_future=True,
         role="STAGE-C ORACLE EXPOSURE ONLY, and the row-selector for the CONDITIONAL subset",
         evidence="stage C conditions on fta>0 BY DEFINITION -- that is what 'given attempts' "
                  "means.  Its dR2 is therefore reported on the conditional subset's own SST and "
                  "is re-expressed on the common denominator in s04 before any cross-stage claim."),
    dict(column="ref_mean__<t> / ref_ewma__<t> / ref_trail5__<t>",
         construction="shift(1) then expanding().mean() / ewm(hl=5) / rolling(5) of the target, "
                      "inside (season, player_id), rows sorted by (game_date, game_id).  For the "
                      "CONDITIONAL targets these are built on the player's PRIOR fta>0 GAMES ONLY.",
         window="(-inf, game_date) within season", reads_future=False,
         role="BASE (B_SINGLE / B_COMPLETE)",
         evidence="probe P1 recomputes from raw bytes; probe P1c shows it differs from the "
                  "contemporaneous-inclusive version"),
    dict(column="ref_rate_x_min__<t> / ref_rate_floored__<t>",
         construction="(prior sum of target over prior games with minutes>=FLOOR) / (prior sum of "
                      "EXPOSURE over those games), times the prior mean exposure",
         window="(-inf, game_date) within season", reads_future=False, role="BASE / honest rung H3",
         evidence="probe P2; the floor is applied to the HISTORY only, never to the response"),
    dict(column="ref_mean_minutes / ref_trail5_minutes / ref_mean_pace / n_prior",
         construction="shift(1) then expanding/rolling over the player's own prior games",
         window="(-inf, game_date) within season", reads_future=False, role="BASE",
         evidence="probe P1 machinery, same prefix"),
    dict(column="ref_pct__<t>",
         construction="shift(1) then expanding().mean() of the advanced-box percentage companion "
                      "(usage_percentage / true_shooting_percentage)",
         window="(-inf, game_date) within season", reads_future=False, role="BASE",
         evidence="probe P1 machinery"),
    dict(column="is_home",
         construction="schedule attribute, known before tip",
         window="[game, pregame]", reads_future=False, role="BASE",
         evidence="fixture attribute, not an outcome"),
    dict(column="F01..F10",
         construction="ratios and per-minute rates of the player's OWN strictly-prior box "
                      "quantities; every one is (prior sum)/(prior sum), never a mean of ratios",
         window="(-inf, game_date) within season", reads_future=False, role="CANDIDATE",
         evidence="probes P2 (F01), P3 (F02); F09 aggregates starter_flag over PRIOR games only -- "
                  "the CONTEMPORANEOUS starter_flag is a TIP-TIME observation and is never used"),
    dict(column="M01..M06",
         construction="the OPPONENT team's strictly-prior per-game means, over the OPPONENT's own "
                      "earlier games in the same season, built from the opposing box totals",
         window="(-inf, game_date) within season, opponent's own games", reads_future=False,
         role="CANDIDATE (opp_team_season level)",
         evidence="probe P5 recomputes M01/M02 from raw bytes; probe P5c shows they differ from "
                  "the version that includes TONIGHT's game"),
    dict(column="X01 / X02",
         construction="centred product of two columns already declared above",
         window="(-inf, game_date)", reads_future=False, role="CANDIDATE (interaction)",
         evidence="algebraic function of clean inputs; centring uses PRIOR-ONLY season-to-date "
                  "league means (probe P6)"),
    dict(column="ORACLE_seasonmean__<t> / ORACLE_seasonrate__<t>",
         construction="the player's WHOLE-SEASON mean of the target / whole-season per-exposure "
                      "rate, INCLUDING games after this one",
         window="ENTIRE SEASON", reads_future=True, role="ORACLE LADDER RUNG -- LABELLED",
         evidence="deliberately retrospective.  NO dR2 IS EVER PUBLISHED OVER A BASE CONTAINING "
                  "THESE.  They appear only as ladder rungs O1/O2/O5, always in the ORACLE column."),
    dict(column="DECISION",
         construction="n_prior>=8 AND trailing-5 prior mean minutes>=24 -- both strictly prior",
         window="(-inf, game_date)", reads_future=False, role="STRATUM SELECTOR",
         evidence="composed of two prior-only columns; selecting on them does not condition on "
                  "this game's outcome"),
    dict(column="G01_noise / G02_placebo_noop / G03_placebo_perturbed",
         construction="seed-fixed RNG / affine copy of ref_mean / ref_mean with 30% of values "
                      "swapped pairwise",
         window="n/a", reads_future=False, role="CONTROL",
         evidence="G02 must give dR2~0 by collinearity; G03 must MOVE the statistic (verified s04)"),
]
rep["time_window_table"] = TIME_WINDOW_TABLE

hdr("0. TIME-WINDOW TABLE (features AND inference)")
for r in TIME_WINDOW_TABLE:
    print("  %-58s reads_future=%-5s  %s" % (r["column"][:58], r["reads_future"], r["role"]))

# =====================================================================================
# 1. LOAD
# =====================================================================================
hdr("1. LOAD + PARTITION ASSERT")
mp = pd.read_parquet(MP_PATH)
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()                                    # FILTER-POINT
assert_partition(mp)
NUM = ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "tov",
       "pf", "pts", "fouls_drawn", "points_paint", "pace", "possessions", "usage_percentage",
       "true_shooting_percentage", "starter_flag"]
for c in NUM:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp["team_id"] = pd.to_numeric(mp["team_id"], errors="coerce").astype("int64")
mp["opp_team_id"] = pd.to_numeric(mp["opp_team_id"], errors="coerce").astype("int64")
mp["game_id"] = mp["game_id"].astype(str)

app = mp[mp["minutes"] > 0].copy()                                           # FILTER-POINT
assert_partition(app)
app = app.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable")
app = app.reset_index(drop=True)
print("  appeared player-games: %d" % len(app))

# =====================================================================================
# 2. RESPONSES
# =====================================================================================
hdr("2. RESPONSES -- THE THREE HURDLE STAGES")
app["y_any_fta"] = (app["fta"] > 0).astype(float)
app["y_fta"] = app["fta"]
app["y_ftm"] = app["ftm"]
app["y_pts"] = app["pts"]
app["y_fta_given"] = np.where(app["fta"] > 0, app["fta"], np.nan)
app["y_ftm_given"] = np.where(app["fta"] > 0, app["ftm"], np.nan)
app["ft_pct_given"] = safe_div(app["ftm"], app["fta"])
app["COND"] = (app["fta"] > 0).astype(int)
for t in TARGET_ORDER:
    v = app[t]
    print("  %-14s n=%-6d mean=%8.4f sd=%8.4f   rowset=%s"
          % (t, int(v.notna().sum()), v.mean(), v.std(), TARGETS[t]["rowset"]))

# IDENTITY ASSERTIONS -- ftm <= fta always, and the composition must hold exactly
assert (app.loc[app["COND"] == 1, "ftm"] <= app.loc[app["COND"] == 1, "fta"]).all()
comp = app["y_any_fta"] * np.nan_to_num(app["y_ftm_given"], nan=0.0)
assert float(np.abs(comp - app["y_ftm"]).max()) == 0.0, "hurdle composition identity violated"
print("  IDENTITY OK: ftm == 1{fta>0} * (ftm | fta>0), max abs deviation 0.000000")
rep["identity_ok"] = True

# =====================================================================================
# 3. PLAYER-SIDE PRIOR-ONLY REFERENCES
# =====================================================================================
hdr("3. PLAYER-SIDE PRIOR-ONLY REFERENCES (shift(1) ALWAYS precedes the accumulator)")
K = ["season", "player_id"]
app["n_prior"] = app.groupby(K, sort=False)["minutes"].transform(
    lambda x: x.shift(1).expanding().count())
app["ref_mean_minutes"] = prior_mean(app, K, "minutes")
app["ref_trail5_minutes"] = prior_trail(app, K, "minutes", 5)
app["ref_mean_pace"] = prior_mean(app, K, "pace")
app["is_home"] = pd.to_numeric(app["is_home"], errors="coerce").astype(float)

# history floor: which PRIOR GAMES contribute to a per-exposure rate.  HISTORY ONLY (D091 r3).
app["_flr"] = (app["minutes"] >= HISTORY_FLOOR).astype(float)


def floored_prior_rate(d, keys, ycol, expcol):
    """(prior sum of y over prior games passing the floor) / (prior sum of exposure over those)."""
    num = d[ycol].to_numpy(float) * d["_flr"].to_numpy(float)
    den = d[expcol].to_numpy(float) * d["_flr"].to_numpy(float)
    tmp = d[list(keys)].copy()
    tmp["_n"], tmp["_d"] = num, den
    ps_n = prior_sum(tmp, keys, "_n")
    ps_d = prior_sum(tmp, keys, "_d")
    return pd.Series(safe_div(ps_n, ps_d), index=d.index)


# --- FULL-rowset targets: references over ALL prior games
for t in [k for k in TARGET_ORDER if TARGETS[k]["rowset"] == "FULL"]:
    app["ref_mean__" + t] = prior_mean(app, K, t)
    app["ref_ewma__" + t] = prior_ewma(app, K, t)
    app["ref_trail5__" + t] = prior_trail(app, K, t, 5)
    app["ref_pct__" + t] = prior_mean(app, K, TARGET_PCT[t])
    rate = floored_prior_rate(app, K, t, "minutes")
    app["ref_rate_floored__" + t] = rate
    app["ref_rate_x_min__" + t] = rate * app["ref_mean_minutes"]

# --- CONDITIONAL targets: references over the player's PRIOR fta>0 GAMES ONLY (matched reference)
#
# DEFECT CAUGHT AND FIXED HERE (see DEFECTS.md D-01).  The first implementation computed these on
# the fta>0 SUBFRAME and joined them back, which left them NULL ON EVERY fta==0 ROW.  That is a
# RESPONSE-CONDITIONED FEATURE: any screen row on which the column existed was, by construction, a
# row where the player had gone to the line tonight.  It made the column a perfect predictor of
# stage A and it silently degraded s04's honest stage-B forecast to the league value on 46% of
# rows.  It was caught by an SST=0 crash rather than by inspection, which is the point of running
# the guards.
#
# THE FIX.  Compute the INCLUSIVE running value on the conditional subframe (it is defined only
# there), place it on the full frame at the conditional rows, then within (season, player) take
# .shift(1).ffill().  Row i receives the value accumulated over the player's conditional games
# STRICTLY BEFORE row i -- defined on EVERY row, and still strictly prior.  On conditional rows
# this is algebraically identical to the subframe's shifted expanding value; probe P1c asserts it.
sub = app[app["COND"] == 1].copy()
for t in [k for k in TARGET_ORDER if TARGETS[k]["rowset"] == "CONDITIONAL"]:
    expcol = TARGETS[t]["exposure"]                     # 'minutes' for B, 'fta' for C
    s = sub.copy()
    s["_flr"] = (s["minutes"] >= HISTORY_FLOOR).astype(float) if expcol == "minutes" else 1.0
    incl = {}
    incl["ref_mean__" + t] = s.groupby(K, sort=False)[t].transform(
        lambda x: x.expanding().mean())
    incl["ref_ewma__" + t] = s.groupby(K, sort=False)[t].transform(
        lambda x: x.ewm(halflife=EWMA_HALFLIFE, min_periods=1).mean())
    incl["ref_trail5__" + t] = s.groupby(K, sort=False)[t].transform(
        lambda x: x.rolling(5, min_periods=1).mean())
    incl["ref_pct__" + t] = s.groupby(K, sort=False)[TARGET_PCT[t]].transform(
        lambda x: x.expanding().mean())
    _n = s.groupby(K, sort=False).apply(
        lambda g: pd.Series((g[t] * g["_flr"]).cumsum().to_numpy(), index=g.index),
        include_groups=False).reset_index(level=list(range(len(K))), drop=True)
    _d = s.groupby(K, sort=False).apply(
        lambda g: pd.Series((g[expcol] * g["_flr"]).cumsum().to_numpy(), index=g.index),
        include_groups=False).reset_index(level=list(range(len(K))), drop=True)
    incl["ref_rate_floored__" + t] = pd.Series(safe_div(_n, _d), index=s.index)
    incl["ref_mean_exposure__" + t] = s.groupby(K, sort=False)[expcol].transform(
        lambda x: x.expanding().mean())

    for cname, vals in incl.items():
        tmp = pd.Series(np.nan, index=app.index)
        tmp.loc[s.index] = vals.to_numpy(float)
        app[cname] = app.assign(_t=tmp).groupby(K, sort=False)["_t"].transform(
            lambda x: x.shift(1).ffill())
    app["ref_rate_x_min__" + t] = app["ref_rate_floored__" + t] * app["ref_mean_exposure__" + t]
    cov_all = float(app["ref_mean__" + t].notna().mean())
    cov_cond = float(app.loc[app["COND"] == 1, "ref_mean__" + t].notna().mean())
    print("  %-14s conditional refs from %d fta>0 rows -> defined on %.4f of ALL rows "
          "(%.4f of conditional rows)" % (t, len(s), cov_all, cov_cond))

# FULL targets need an exposure column too, for the ladder's H3/O5
for t in [k for k in TARGET_ORDER if TARGETS[k]["rowset"] == "FULL"]:
    app["ref_mean_exposure__" + t] = app["ref_mean_minutes"]

# --- ORACLE columns (LABELLED; read the WHOLE SEASON, deliberately)
for t in TARGET_ORDER:
    expcol = TARGETS[t]["exposure"]
    app["ORACLE_seasonmean__" + t] = app.groupby(K, sort=False)[t].transform("mean")
    gs = app.groupby(K, sort=False)
    num = gs[t].transform("sum")
    den = gs[expcol].transform("sum") if TARGETS[t]["rowset"] == "FULL" else \
        app.assign(_e=np.where(app["COND"] == 1, app[expcol], np.nan)).groupby(K, sort=False)["_e"].transform("sum")
    app["ORACLE_seasonrate__" + t] = safe_div(num, den)
print("  ORACLE columns built (season-wide; LABELLED, never in any base)")

# =====================================================================================
# 4. OPPONENT-SIDE PRIOR-ONLY AGGREGATES  (vary at opp_team_season)
# =====================================================================================
hdr("4. OPPONENT-SIDE PRIOR-ONLY AGGREGATES")
tg = (app.groupby(["season", "game_id", "game_date", "team_id", "opp_team_id"], as_index=False)
         .agg(t_fta=("fta", "sum"), t_ftm=("ftm", "sum"), t_fga=("fga", "sum"),
              t_pf=("pf", "sum"), t_pts=("pts", "sum"), t_pace=("pace", "mean"),
              n_players=("player_id", "size"), n_any_fta=("y_any_fta", "sum")))
print("  team-games: %d" % len(tg))

# what a team ALLOWED = the opposing team's offensive line in the same game
opp = tg.rename(columns={"team_id": "_o", "opp_team_id": "team_id",
                         "t_fta": "a_fta", "t_ftm": "a_ftm", "t_fga": "a_fga",
                         "t_pf": "a_pf", "t_pts": "a_pts", "t_pace": "a_pace",
                         "n_players": "a_nplayers", "n_any_fta": "a_nany"})
tg = tg.merge(opp[["season", "game_id", "team_id", "a_fta", "a_ftm", "a_fga", "a_nplayers",
                   "a_nany"]],
              on=["season", "game_id", "team_id"], how="left")
miss = int(tg["a_fta"].isna().sum())
print("  team-games with no opposing line found: %d (%.3f%%)" % (miss, 100 * miss / len(tg)))
rep["team_games_unmatched"] = miss

tg = tg.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
TK = ["season", "team_id"]
tg["M01_opp_pf_pg"] = prior_mean(tg, TK, "t_pf")
tg["M02_opp_allowed_fta_pg"] = prior_mean(tg, TK, "a_fta")
tg["M03_opp_allowed_ftm_pg"] = prior_mean(tg, TK, "a_ftm")
tg["M04_opp_allowed_ft_rate"] = safe_div(prior_sum(tg, TK, "a_fta"), prior_sum(tg, TK, "a_fga"))
tg["M05_opp_allowed_hurdle_rate"] = safe_div(prior_sum(tg, TK, "a_nany"),
                                             prior_sum(tg, TK, "a_nplayers"))
tg["M06_opp_pace"] = prior_mean(tg, TK, "t_pace")
tg["opp_n_prior_games"] = tg.groupby(TK, sort=False)["t_pf"].transform(
    lambda x: x.shift(1).expanding().count())

MCOLS = ["M01_opp_pf_pg", "M02_opp_allowed_fta_pg", "M03_opp_allowed_ftm_pg",
         "M04_opp_allowed_ft_rate", "M05_opp_allowed_hurdle_rate", "M06_opp_pace",
         "opp_n_prior_games"]
# attach to the player row by the OPPONENT's identity
app = app.merge(tg[["season", "game_id", "team_id"] + MCOLS]
                .rename(columns={"team_id": "opp_team_id"}),
                on=["season", "game_id", "opp_team_id"], how="left")
app = app.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable")
app = app.reset_index(drop=True)
for c in MCOLS:
    print("  %-30s non-null %.4f  mean %.4f" % (c, app[c].notna().mean(), app[c].mean()))

# =====================================================================================
# 5. OWN-SIDE CANDIDATES F01..F10
# =====================================================================================
hdr("5. OWN-SIDE CANDIDATES -- every one is (prior sum)/(prior sum), never a mean of ratios")
app["_paint"] = app["points_paint"]
app["F01_prior_ftr"] = safe_div(prior_sum(app, K, "fta"), prior_sum(app, K, "fga"))
app["F02_prior_fd_pm"] = safe_div(prior_sum(app, K, "fouls_drawn"), prior_sum(app, K, "minutes"))
app["F03_prior_ft_pct"] = safe_div(prior_sum(app, K, "ftm"), prior_sum(app, K, "fta"))
app["F04_prior_paint_share"] = safe_div(prior_sum(app, K, "_paint"), prior_sum(app, K, "pts"))
app["F05_prior_fga_pm"] = safe_div(prior_sum(app, K, "fga"), prior_sum(app, K, "minutes"))
app["F06_prior_fg3a_share"] = safe_div(prior_sum(app, K, "fg3a"), prior_sum(app, K, "fga"))
app["F07_prior_hurdle_rate"] = prior_mean(app, K, "y_any_fta")
app["F09_prior_starter_rate"] = prior_mean(app, K, "starter_flag")
app["F10_prior_pf_pm"] = safe_div(prior_sum(app, K, "pf"), prior_sum(app, K, "minutes"))
# F08: prior mean fta over the player's prior fta>0 games -- already computed as the conditional ref
app["F08_prior_fta_given"] = app["ref_mean__y_fta_given"]
FCOLS = ["F01_prior_ftr", "F02_prior_fd_pm", "F03_prior_ft_pct", "F04_prior_paint_share",
         "F05_prior_fga_pm", "F06_prior_fg3a_share", "F07_prior_hurdle_rate",
         "F08_prior_fta_given", "F09_prior_starter_rate", "F10_prior_pf_pm"]
for c in FCOLS:
    print("  %-26s non-null %.4f  mean %9.4f  sd %8.4f"
          % (c, app[c].notna().mean(), app[c].mean(), app[c].std()))

# =====================================================================================
# 6. INTERACTIONS -- centred on PRIOR-ONLY season-to-date league means
# =====================================================================================
hdr("6. INTERACTIONS (D085 GUARD: both main effects go in the base, built in s04)")


def prior_league_centre(d, col):
    """Centre on the expanding league mean over rows strictly EARLIER IN THE SAME SEASON.
    Centring on the FULL-SAMPLE mean would import a whole-season quantity into a pregame feature."""
    f = d.sort_values(["season", "game_date", "game_id"], kind="stable")
    m = f.groupby("season", sort=False)[col].transform(lambda x: x.shift(1).expanding().mean())
    m = m.reindex(d.index)
    return d[col] - m


app["_c_F02"] = prior_league_centre(app, "F02_prior_fd_pm")
app["_c_M01"] = prior_league_centre(app, "M01_opp_pf_pg")
app["_c_F01"] = prior_league_centre(app, "F01_prior_ftr")
app["_c_M04"] = prior_league_centre(app, "M04_opp_allowed_ft_rate")
app["X01_fd_x_oppfoul"] = app["_c_F02"] * app["_c_M01"]
app["X02_ftr_x_oppftrate"] = app["_c_F01"] * app["_c_M04"]
print("  X01 non-null %.4f  sd %.6f" % (app["X01_fd_x_oppfoul"].notna().mean(),
                                        app["X01_fd_x_oppfoul"].std()))
print("  X02 non-null %.4f  sd %.6f" % (app["X02_ftr_x_oppftrate"].notna().mean(),
                                        app["X02_ftr_x_oppftrate"].std()))

# =====================================================================================
# 7. CONTROLS
# =====================================================================================
hdr("7. CONTROLS")
# DEFECT CAUGHT AND FIXED HERE (see DEFECTS.md D-02).  The first implementation built ONE placebo
# pair from ref_mean__y_ftm and reused it on every target.  The prereg says the no-op placebo is
# "an exact affine copy of THE BASE'S FIRST column" -- and the base's first column is
# ref_mean__<target>, which differs per target.  The single-column version was therefore a GENUINE
# PREDICTOR on the five targets it was not built from (observed max |dR2| 2.591e-02), so it tested
# nothing and the perturbation check it fed was meaningless.  This is a bug fix that brings the
# code into line with the preregistered text; the prereg hash is unchanged.
rng = np.random.default_rng(SEED)
app["G01_noise"] = rng.normal(size=len(app))
pl_rows = []
for t in TARGET_ORDER:
    src = app["ref_mean__" + t].to_numpy(float)
    app["G02_placebo_noop__" + t] = 2.5 * src + 7.0            # COLLINEAR with the base by design
    pert = src.copy()
    fin = np.flatnonzero(np.isfinite(pert))
    idx = rng.choice(fin, size=int(0.30 * len(fin)), replace=False)
    half = len(idx) // 2
    a, b = idx[:half], idx[half:2 * half]
    pert[a], pert[b] = pert[b].copy(), pert[a].copy()
    app["G03_placebo_perturbed__" + t] = pert
    n_moved = int(np.nansum(pert[fin] != src[fin]))
    cc = float(np.corrcoef(pert[fin], src[fin])[0, 1])
    pl_rows.append(dict(target=t, rows_changed=n_moved, frac_changed=n_moved / max(len(fin), 1),
                        corr_with_source=cc))
    print("  %-13s G02 affine copy of ref_mean__%-13s | G03 perturbed %5d/%5d rows (%.1f%%), "
          "corr %.4f" % (t, t, n_moved, len(fin), 100 * n_moved / max(len(fin), 1), cc))
    assert n_moved > 0, "G03 DID NOT PERTURB ANYTHING on %s -- placebo machinery inert" % t
print("  G01 iid gaussian, seed %d" % SEED)
rep["placebo_perturbation"] = pl_rows

# =====================================================================================
# 8. STRATA
# =====================================================================================
hdr("8. STRATA")
app["DECISION"] = ((app["n_prior"] >= 8) & (app["ref_trail5_minutes"] >= 24)).astype(int)
for s, m in [("POOLED (headline 2022-24)", app["season"].isin(HEADLINE_SEASONS)),
             ("DECISION (headline)", app["season"].isin(HEADLINE_SEASONS) & (app["DECISION"] == 1))]:
    d = app[m]
    print("  %-28s n=%-6d  of which fta>0: %-6d (%.1f%%)"
          % (s, len(d), int(d["COND"].sum()), 100 * d["COND"].mean()))
    rep["stratum_" + s.split()[0]] = dict(n=int(len(d)), n_cond=int(d["COND"].sum()),
                                          frac_cond=float(d["COND"].mean()))

# =====================================================================================
# 9. BRUTE-FORCE LEAKAGE PROBES -- with a DISCRIMINATION ARM on every one
# =====================================================================================
hdr("9. BRUTE-FORCE LEAKAGE PROBES (recomputed from raw bytes, not inspected)")
prng = np.random.default_rng(SEED + 11)
probes = []


def probe(name, col, prior_fn, contemp_fn, n=300, need_discrim=True):
    """prior_fn/contemp_fn take (raw rows for this player/team, this row) and return a scalar."""
    cand = app.index[app[col].notna() & (app["n_prior"] >= 3)].to_numpy()
    if len(cand) == 0:
        probes.append(dict(probe=name, passed=False, n_checked=0, detail="no eligible rows"))
        return
    samp = prng.choice(cand, size=min(n, len(cand)), replace=False)
    bad_prior = bad_contemp = ok = 0
    for i in samp:
        r = app.loc[i]
        pv = prior_fn(r)
        cv = contemp_fn(r) if contemp_fn is not None else None
        if pv is None or not np.isfinite(pv):
            continue
        ok += 1
        if abs(pv - float(r[col])) > 1e-8:
            bad_prior += 1
        if cv is not None and np.isfinite(cv) and abs(cv - float(r[col])) > 1e-8:
            bad_contemp += 1
    p1 = (bad_prior == 0)
    p2 = (bad_contemp > 0) if (need_discrim and contemp_fn is not None) else True
    probes.append(dict(probe=name, passed=bool(p1 and p2), n_checked=ok,
                       detail="mismatch_vs_PRIOR=%d ; mismatch_vs_CONTEMPORANEOUS=%d (must be >0)"
                              % (bad_prior, bad_contemp)))
    print("  [%s] %-46s n=%-4d  prior_mismatch=%-4d contemp_mismatch=%d"
          % ("PASS" if (p1 and p2) else "FAIL", name, ok, bad_prior, bad_contemp))
    assert p1, "%s: column does NOT reproduce from a strictly-prior recomputation" % name
    assert p2, "%s: column is INDISTINGUISHABLE from a contemporaneous recomputation" % name


PL = app.set_index(["season", "player_id"]).sort_index()


def _plr(r):
    d = PL.loc[(r["season"], r["player_id"])]
    if isinstance(d, pd.Series):
        d = d.to_frame().T
    return d.sort_values(["game_date", "game_id"], kind="stable")


def _split(r):
    d = _plr(r)
    before = d[(d["game_date"] < r["game_date"]) |
               ((d["game_date"] == r["game_date"]) & (d["game_id"] < r["game_id"]))]
    upto = d[(d["game_date"] < r["game_date"]) |
             ((d["game_date"] == r["game_date"]) & (d["game_id"] <= r["game_id"]))]
    return before, upto


probe("P1  ref_mean__y_ftm == prior expanding mean", "ref_mean__y_ftm",
      lambda r: _split(r)[0]["ftm"].mean() if len(_split(r)[0]) else None,
      lambda r: _split(r)[1]["ftm"].mean())

probe("P1b ref_mean__y_fta_given == prior COND mean", "ref_mean__y_fta_given",
      lambda r: (lambda b: b.loc[b["fta"] > 0, "fta"].mean() if (b["fta"] > 0).any() else None)(_split(r)[0]),
      lambda r: (lambda u: u.loc[u["fta"] > 0, "fta"].mean())(_split(r)[1]))

# P1c: the D-01 FIX must not have changed the values on conditional rows.  The old (defective)
# construction was correct WHERE IT WAS DEFINED; the fix only extends it to the fta==0 rows.  If
# the two disagree anywhere on a conditional row, the fix changed the measurement rather than its
# domain, and s03's ladder would no longer be the quantity it claims to be.
_sc = app[app["COND"] == 1].copy()
_old = prior_mean(_sc, K, "y_fta_given")
_new = _sc["ref_mean__y_fta_given"]
_cmp = np.abs(_old.to_numpy(float) - _new.to_numpy(float))
_both = np.isfinite(_old.to_numpy(float)) & np.isfinite(_new.to_numpy(float))
p1c_max = float(np.max(_cmp[_both])) if _both.any() else np.nan
p1c_dom = float(_new.notna().mean()) - float(_old.notna().mean())
p1c = bool(p1c_max < 1e-9)
probes.append(dict(probe="P1c D-01 fix changed the DOMAIN, not the VALUES", passed=p1c,
                   n_checked=int(_both.sum()),
                   detail="max abs diff on conditional rows=%.3e ; domain change on conditional "
                          "rows=%+.6f ; defined on %.4f of ALL rows now vs %.4f before"
                          % (p1c_max, p1c_dom, float(app["ref_mean__y_fta_given"].notna().mean()),
                             float(app.loc[app["COND"] == 1, "ref_mean__y_fta_given"].notna().mean()
                                   * app["COND"].mean()))))
print("  [%s] P1c D-01 fix changed the DOMAIN not the VALUES  max abs diff on conditional "
      "rows = %.3e" % ("PASS" if p1c else "FAIL", p1c_max))
assert p1c, "the D-01 fix altered the reference VALUES, not merely its domain"

# P1d: the extended column must NOT be a response-conditioned indicator any more.  Before the fix,
# notna(ref_mean__y_fta_given) predicted y_any_fta PERFECTLY.  Now it must not.
_ind = app["ref_mean__y_fta_given"].notna().to_numpy(float)
_auc_like = float(np.corrcoef(_ind, app["y_any_fta"].to_numpy(float))[0, 1])
p1d = bool(abs(_auc_like) < 0.30)
probes.append(dict(probe="P1d conditional-ref AVAILABILITY no longer encodes the response",
                   passed=p1d, n_checked=int(len(app)),
                   detail="corr(notna(ref_mean__y_fta_given), y_any_fta) = %+.4f (was +1.0 by "
                          "construction before the D-01 fix)" % _auc_like))
print("  [%s] P1d availability no longer encodes the response: corr = %+.4f"
      % ("PASS" if p1d else "FAIL", _auc_like))
assert p1d

probe("P2  F01_prior_ftr == sum(fta)/sum(fga) prior", "F01_prior_ftr",
      lambda r: (lambda b: b["fta"].sum() / b["fga"].sum() if b["fga"].sum() > 0 else None)(_split(r)[0]),
      lambda r: (lambda u: u["fta"].sum() / u["fga"].sum() if u["fga"].sum() > 0 else None)(_split(r)[1]))

probe("P3  F02_prior_fd_pm == sum(fd)/sum(min) prior", "F02_prior_fd_pm",
      lambda r: (lambda b: b["fouls_drawn"].sum() / b["minutes"].sum() if b["minutes"].sum() > 0 else None)(_split(r)[0]),
      lambda r: (lambda u: u["fouls_drawn"].sum() / u["minutes"].sum())(_split(r)[1]))

probe("P4  F09_prior_starter_rate (TIP-TIME guard)", "F09_prior_starter_rate",
      lambda r: _split(r)[0]["starter_flag"].mean() if len(_split(r)[0]) else None,
      lambda r: _split(r)[1]["starter_flag"].mean())

TGI = tg.set_index(["season", "team_id"]).sort_index()


def _tsplit(r):
    d = TGI.loc[(r["season"], r["opp_team_id"])]
    if isinstance(d, pd.Series):
        d = d.to_frame().T
    d = d.sort_values(["game_date", "game_id"], kind="stable")
    before = d[(d["game_date"] < r["game_date"]) |
               ((d["game_date"] == r["game_date"]) & (d["game_id"] < r["game_id"]))]
    upto = d[(d["game_date"] < r["game_date"]) |
             ((d["game_date"] == r["game_date"]) & (d["game_id"] <= r["game_id"]))]
    return before, upto


probe("P5  M01_opp_pf_pg == opp prior mean team pf", "M01_opp_pf_pg",
      lambda r: _tsplit(r)[0]["t_pf"].mean() if len(_tsplit(r)[0]) else None,
      lambda r: _tsplit(r)[1]["t_pf"].mean(), n=200)

probe("P5b M02_opp_allowed_fta_pg == opp prior mean", "M02_opp_allowed_fta_pg",
      lambda r: _tsplit(r)[0]["a_fta"].mean() if len(_tsplit(r)[0]) else None,
      lambda r: _tsplit(r)[1]["a_fta"].mean(), n=200)

# P6: the centring used for the interactions must itself be prior-only
_lg = app.sort_values(["season", "game_date", "game_id"], kind="stable")
_chk = _lg.groupby("season", sort=False)["F02_prior_fd_pm"].transform(
    lambda x: x.shift(1).expanding().mean()).reindex(app.index)
p6 = bool(np.nanmax(np.abs((app["F02_prior_fd_pm"] - _chk) - app["_c_F02"]).to_numpy(float)) < 1e-12)
p6b = bool(np.nanstd((app["F02_prior_fd_pm"] - app["F02_prior_fd_pm"].mean()) - app["_c_F02"]) > 1e-9)
probes.append(dict(probe="P6  interaction centring is PRIOR-ONLY, not full-sample", passed=p6 and p6b,
                   n_checked=int(app["_c_F02"].notna().sum()),
                   detail="matches prior-expanding league mean=%s ; differs from full-sample "
                          "centring=%s" % (p6, p6b)))
print("  [%s] P6  interaction centring is PRIOR-ONLY (differs from full-sample: %s)"
      % ("PASS" if (p6 and p6b) else "FAIL", p6b))
assert p6 and p6b

pd.DataFrame(probes).to_csv(os.path.join(OUT, "leakage_probes.csv"), index=False)
rep["leakage_probes"] = probes

# =====================================================================================
# 10. WRITE
# =====================================================================================
hdr("10. WRITE FRAME")
drop = [c for c in app.columns if c.startswith("_") and c not in ("_c_F02", "_c_M01", "_c_F01",
                                                                  "_c_M04")]
F = app.drop(columns=drop)
assert_partition(F)
F.to_parquet(os.path.join(OUT, "screen_frame.parquet"), index=False)
print("  wrote screen_frame.parquet %s" % (F.shape,))
rep["frame_shape"] = list(F.shape)
json.dump(jsonable(rep), open(os.path.join(OUT, "_s02.json"), "w"), indent=2)
print("  WROTE _s02.json")
