"""E1 I0004c -- DOES THE SHOT-MIX SIGNAL SURVIVE WHEN ATTEMPTS MUST ALSO BE FORECAST?

E1 IS NON-CLAIMING. Nothing here is a RESULT. It is a LEAD or it is dead.

WHAT THIS SCREEN ASKS
---------------------
E1_I0004_shot_selection (D074) established a real shot-MIX effect and disclosed, itself,
that its player-game increment (dR2 = +0.019138861495123338 on Restricted-Area attempt
counts) is measured CONDITIONAL ON REALISED FGA -- which is why its base R2 is already
0.510. Given a player's actual total attempts, predicting their rim share is easy. In
live use nobody knows realised FGA before the game.

    Q: does the mix signal survive when TOTAL ATTEMPTS must also be forecast from
       strictly prior-games information?

STAGE 1 (this file): reproduce the conditional +0.019138861495123338 exactly, from the
predecessor's frame AND from an independent raw-file rebuild.
STAGE 2 (this file): build two honest point-in-time FGA forecasts and measure their own
accuracy.
STAGE 3-5 (end_to_end.py): forecast zone attempt COUNTS and PLAYER POINTS with no
realised-game information anywhere.

PARTITION (GRAPH_POLICY 13.2): seasons 2021, 2022, 2023, 2024 ONLY. 2025/2026 is never
read, joined, filtered against, counted, described or plotted. Every load is followed by
a `# FILTER-POINT` and a printed sorted(season.unique()).

ARTIFACT POLICY
---------------
Files read:
  data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet  -- raw per-shot events.
      NO MANIFEST. Admitted on STRUCTURAL grounds, stated explicitly: the season IS the
      filename, and every column is a property of that single shot event (coordinates,
      zone label, made flag, its own game's id/date). No column is an aggregate, a
      shrunk value, or a cross-row derivation, so no row can embed another season.
  data/wnba_gamelog_{2021..2024}.parquet  -- raw per-player-per-game box score.
      NO MANIFEST -> formally UNVERIFIABLE, NOT A PASS. Admitted on the SAME structural
      grounds and audited column by column in this script: every column is a raw
      counting stat of that one game, plus three within-row ratios (FG_PCT, FG3_PCT,
      FT_PCT) which this script re-derives and checks equal FGM/FGA etc. Used for ONE
      thing: the player's MINUTES in games strictly before the game being forecast.
      Everything is also re-run without minutes (forecast A / A2) so no headline
      depends on this source alone.
  experiments/exploration/E1_I0004_shot_selection/selection_frame.parquet -- frozen
      predecessor frame, read-only.
  experiments/exploration/E1_I0011_split_alpha/baseline/corrected_baseline.py -- code.

data/zone_maps/* are FORBIDDEN (asof_granularity == "artifact"). Not read. Zone
assignment comes from the raw per-shot SHOT_ZONE_BASIC label.

R-SQUARED CONVENTION (D069): plain UNWEIGHTED OLS R2 = 1 - SSE/SST with SST about the
UNWEIGHTED mean of the response. The defective sqrt-weight form is never used.

PRESELECTED CONSTANTS -- fixed in this file BEFORE any forecast accuracy number or any
end-to-end statistic was computed. None was tuned; no alternative was searched.
    K_A        = 3.0    pseudo-GAMES of shrinkage for crude forecast A
    K_R        = 40.0   pseudo-MINUTES of shrinkage for the FGA-per-minute rate in B
    PACE_CLIP  = (0.85, 1.15)   clip on the opponent prior-pace multiplier in B
    K_Q        = 20.0   pseudo-ATTEMPTS of shrinkage for prior zone conversion rates
    MIN_FGA_GAME  = 5   inherited unchanged from the predecessor (sample definition)
    MIN_PRE_TOTAL = 200 inherited unchanged from the predecessor
Everything else (alpha_eff 0.03, alpha_exp 0.30, min_prior 3) is the FROZEN program
baseline own_rate_v2_split_alpha and was not touched.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PRED = os.path.join(REPO, "experiments", "exploration", "E1_I0004_shot_selection")
BASELINE_DIR = os.path.join(REPO, "experiments", "exploration",
                            "E1_I0011_split_alpha", "baseline")
sys.path.insert(0, BASELINE_DIR)
from corrected_baseline import (BASELINE_ID, ALPHA_EFF, ALPHA_EXP,  # noqa: E402
                                MIN_PRIOR, CorrectedOwnRateBaseline)

PARTITION = [2021, 2022, 2023, 2024]
TYPES = ["regular", "playoffs"]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
ZONE_PTS = {RA: 2.0, "In The Paint (Non-RA)": 2.0, "Mid-Range": 2.0,
            "Corner 3": 3.0, "Above the Break 3": 3.0}

MIN_FGA_GAME = 5        # inherited, unchanged
MIN_PRE_TOTAL = 200     # inherited, unchanged
SHRINK_K = 50.0         # inherited, unchanged (S2 only)
K_A = 3.0               # PRESELECTED
K_R = 40.0              # PRESELECTED
PACE_CLIP = (0.85, 1.15)  # PRESELECTED
K_Q = 20.0              # PRESELECTED

PRED_DR2_TARGET = 0.019138861495123338   # predecessor dr2_results.json, RA, 2021-2024
PRED_M0_TARGET = 0.5103262851681518
PRED_M1_TARGET = 0.5294651466632752

pd.set_option("display.width", 240)
RESULTS = {}


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ================================================================== 0 LOAD RAW SHOTS =
hdr("0. LOAD RAW SHOTS -- exploration partition only (2021-2024)")
dfs = []
for ssn in PARTITION:
    for t in TYPES:
        f = f"data/shotcharts/shots_{ssn}_{t}.parquet"
        d = pd.read_parquet(os.path.join(REPO, f))
        d["season"] = ssn
        d = d[d["season"].isin(PARTITION)]           # FILTER-POINT 1
        print(f"  {f:<48} rows={len(d):>7}  seasons={sorted(d['season'].unique())}")
        dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)
shots = shots[shots["season"].isin(PARTITION)].copy()  # FILTER-POINT 2
shots["game_date"] = pd.to_datetime(shots["GAME_DATE"], format="%Y%m%d")
print(f"\n  concatenated rows = {len(shots)}")
print(f"  sorted(season.unique()) = {sorted(shots['season'].unique())}")
print(f"  GAME_DATE range = {shots['game_date'].min().date()} .. "
      f"{shots['game_date'].max().date()}")
assert set(shots["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION (season)"
assert shots["game_date"].dt.year.max() <= 2024, "PARTITION VIOLATION (date)"
print("  PARTITION CHECK PASSED.")

shots["zone"] = shots["SHOT_ZONE_BASIC"].map(
    lambda z: "Corner 3" if z in ("Left Corner 3", "Right Corner 3") else z)
shots["made"] = shots["SHOT_MADE_FLAG"].astype(int)

game_teams = shots.groupby("GAME_ID")["TEAM_ID"].unique()
opp_lookup = {}
for gid, teams in game_teams.items():
    if len(teams) == 2:
        opp_lookup[(gid, teams[0])] = teams[1]
        opp_lookup[(gid, teams[1])] = teams[0]
shots["OPP_TEAM_ID"] = [opp_lookup.get((g, t), np.nan)
                        for g, t in zip(shots["GAME_ID"], shots["TEAM_ID"])]
shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)
shots5 = shots[shots["zone"].isin(ZONES)].copy()
print(f"  5-zone shots = {len(shots5)}  games = {shots5['GAME_ID'].nunique()}")

# ============================================ 1 REBUILD THE PREDECESSOR PANEL (RAW) ==
hdr("1. STEP 1 -- REBUILD THE PREDECESSOR'S SELECTION PANEL FROM RAW FILES")
print("""  Independent transcription of E1_I0004_shot_selection/build_frames.py section 3.
  Checked column-by-column against the frozen selection_frame.parquet. Any later
  difference is then attributable to introducing the FGA FORECAST, not to my harness.""")

pgt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date", "TEAM_ID",
                       "OPP_TEAM_ID"]).size().rename("fga").reset_index())
pzt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "zone"]).size()
       .rename("z_att").reset_index())
pzm = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "zone"])["made"].sum()
       .rename("z_mk").reset_index())
panel = (pgt.assign(key=1).merge(pd.DataFrame({"zone": ZONES, "key": 1}), on="key")
         .drop(columns="key"))
panel = panel.merge(pzt, on=["PLAYER_ID", "season", "GAME_ID", "zone"], how="left")
panel = panel.merge(pzm, on=["PLAYER_ID", "season", "GAME_ID", "zone"], how="left")
panel[["z_att", "z_mk"]] = panel[["z_att", "z_mk"]].fillna(0.0)
panel["share"] = panel["z_att"] / panel["fga"]
panel = panel.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"})
panel["minutes"] = panel["fga"].astype(float)      # predecessor's S1 trick
panel["fga_copy"] = panel["fga"].astype(float)
print(f"  panel rows = {len(panel)}   player-games = {len(pgt)}")

BASE = CorrectedOwnRateBaseline()
parts = []
for zone in ZONES:
    q = panel[panel["zone"] == zone].copy()
    q["proj_z"] = BASE.project(q, "z_att")
    q["exp_fga"] = BASE.project(q, "fga_copy")
    q["n_prior"] = BASE.n_prior(q, "z_att")
    q["S1"] = q["proj_z"] / q["exp_fga"]
    parts.append(q)
panel = pd.concat(parts, ignore_index=True)

# S2
panel = panel.sort_values(["zone", "player_id", "season", "game_date", "game_id"],
                          kind="stable").reset_index(drop=True)
gk = [panel["zone"], panel["player_id"], panel["season"]]
panel["pre_zatt"] = panel.groupby(gk, sort=False)["z_att"].cumsum() - panel["z_att"]
panel["pre_fga"] = panel.groupby(gk, sort=False)["fga"].cumsum() - panel["fga"]
panel["pre_zmk"] = panel.groupby(gk, sort=False)["z_mk"].cumsum() - panel["z_mk"]

lgd = (shots5.groupby(["season", "game_date", "zone"]).size().rename("a").reset_index())
lgd = lgd.sort_values(["season", "zone", "game_date"], kind="stable")
lgd["cum"] = lgd.groupby(["season", "zone"], sort=False)["a"].cumsum() - lgd["a"]
lgt = (shots5.groupby(["season", "game_date"]).size().rename("t").reset_index()
       .sort_values(["season", "game_date"], kind="stable"))
lgt["cumt"] = lgt.groupby("season", sort=False)["t"].cumsum() - lgt["t"]
lgd = lgd.merge(lgt[["season", "game_date", "cumt"]], on=["season", "game_date"])
lgd["lg_share_prior"] = lgd["cum"] / lgd["cumt"]
panel = panel.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                    on=["season", "game_date", "zone"], how="left")
panel["lg_share_prior"] = panel.groupby(["season", "zone"])["lg_share_prior"].transform(
    lambda x: x.bfill().ffill())
panel["S2"] = ((panel["pre_zatt"] + SHRINK_K * panel["lg_share_prior"])
               / (panel["pre_fga"] + SHRINK_K))
panel.loc[panel["n_prior"] < MIN_PRIOR, "S2"] = np.nan

# OS
tg = (shots5.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "zone"]).size()
      .rename("a").reset_index())
tgw = tg.pivot_table(index=["OPP_TEAM_ID", "season", "GAME_ID", "game_date"],
                     columns="zone", values="a", fill_value=0).reset_index()
for z in ZONES:
    if z not in tgw.columns:
        tgw[z] = 0
tgw = tgw.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                      kind="stable").reset_index(drop=True)
tk = [tgw["OPP_TEAM_ID"], tgw["season"]]
tgw["tot"] = tgw[ZONES].sum(axis=1)
tgw["pre_tot"] = tgw.groupby(tk, sort=False)["tot"].cumsum() - tgw["tot"]
tgw["pre_ngames"] = tgw.groupby(tk, sort=False).cumcount()
for z in ZONES:
    tgw["pre_" + z] = tgw.groupby(tk, sort=False)[z].cumsum() - tgw[z]
    tgw["oppshare_" + z] = tgw["pre_" + z] / tgw["pre_tot"]
tgw["OS_ok"] = tgw["pre_tot"] >= MIN_PRE_TOTAL

oslong = tgw.melt(id_vars=["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "OS_ok"],
                  value_vars=["oppshare_" + z for z in ZONES],
                  var_name="zone", value_name="opp_share_prior")
oslong["zone"] = oslong["zone"].str.replace("oppshare_", "", regex=False)
oslong = oslong.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                      on=["season", "game_date", "zone"], how="left")
oslong["OS"] = oslong["opp_share_prior"] - oslong["lg_share_prior"]
oslong.loc[~oslong["OS_ok"], ["OS", "opp_share_prior"]] = np.nan
panel = panel.merge(oslong[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "OS"]]
                    .rename(columns={"GAME_ID": "game_id"}),
                    on=["OPP_TEAM_ID", "season", "game_id", "zone"], how="left")

role = (panel[panel["zone"] == RA][["player_id", "season", "game_id", "exp_fga"]]
        .rename(columns={"exp_fga": "role_prior_fga"}))
panel = panel.merge(role, on=["player_id", "season", "game_id"], how="left")

panel = panel[panel["season"].isin(PARTITION)].copy()   # FILTER-POINT 3
MINE = panel[(panel["fga"] >= MIN_FGA_GAME)
             & panel[["share", "S1", "S2", "OS", "role_prior_fga"]]
             .notna().all(axis=1)].copy()
print(f"  my rebuilt analysis rows = {len(MINE)}   "
      f"player-games = {MINE[['player_id','season','game_id']].drop_duplicates().shape[0]}")

# ---- compare to the frozen frame, column by column
SF = pd.read_parquet(os.path.join(PRED, "selection_frame.parquet"))
SF = SF[SF["season"].isin(PARTITION)].copy()            # FILTER-POINT 4
key = ["zone", "player_id", "season", "game_id"]
cmp = SF.merge(MINE[key + ["fga", "z_att", "share", "S1", "S2", "OS", "role_prior_fga",
                           "n_prior"]],
               on=key, how="outer", suffixes=("_pred", "_mine"), indicator=True)
print(f"\n  row-set match: {cmp['_merge'].value_counts().to_dict()}")
FRAME_DELTAS = {}
for c in ["fga", "z_att", "share", "S1", "S2", "OS", "role_prior_fga", "n_prior"]:
    d = (cmp[c + "_pred"].astype(float) - cmp[c + "_mine"].astype(float)).abs().max()
    FRAME_DELTAS[c] = float(d)
    print(f"    max|delta| {c:<18} = {d:.3e}")
FRAME_EXACT = bool(cmp["_merge"].eq("both").all()
                   and max(FRAME_DELTAS.values()) < 1e-12)
print(f"  RAW-REBUILD OF THE FRAME: {'EXACT' if FRAME_EXACT else '*** MISMATCH ***'}")


def dr2_conditional(d, fga_col):
    """Predecessor's spec: z_att ~ 1 + S1*fga  vs  + fga*OS.
    Plain unweighted OLS, R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean (D069)."""
    y = d["z_att"].to_numpy(float)
    sst = float(((y - y.mean()) ** 2).sum())
    f = d[fga_col].to_numpy(float)
    X0 = np.column_stack([np.ones(len(y)), d["S1"].to_numpy(float) * f])
    X1 = np.column_stack([X0, f * d["OS"].to_numpy(float)])
    out = {}
    for nm, X in (("m0", X0), ("m1", X1)):
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        out[nm] = float(1 - (e @ e) / sst)
    out["dR2"] = out["m1"] - out["m0"]
    out["n"] = int(len(y))
    return out


hdr("1b. STEP 1 -- REPRODUCE THE CONDITIONAL dR2 (+0.019138861495123338)")
ra_pred = SF[SF["zone"] == RA].dropna(subset=["z_att", "S1", "fga", "OS"])
ra_mine = MINE[MINE["zone"] == RA].dropna(subset=["z_att", "S1", "fga", "OS"])
r_pred = dr2_conditional(ra_pred, "fga")
r_mine = dr2_conditional(ra_mine, "fga")
print(f"  predecessor published : m0={PRED_M0_TARGET:.16f}  m1={PRED_M1_TARGET:.16f}  "
      f"dR2={PRED_DR2_TARGET:.16f}  n=10307")
print(f"  from THEIR frame      : m0={r_pred['m0']:.16f}  m1={r_pred['m1']:.16f}  "
      f"dR2={r_pred['dR2']:.16f}  n={r_pred['n']}")
print(f"  from MY raw rebuild   : m0={r_mine['m0']:.16f}  m1={r_mine['m1']:.16f}  "
      f"dR2={r_mine['dR2']:.16f}  n={r_mine['n']}")
d_pred = abs(r_pred["dR2"] - PRED_DR2_TARGET)
d_mine = abs(r_mine["dR2"] - PRED_DR2_TARGET)
print(f"\n  ABSOLUTE DIFFERENCE vs +0.019138861495123338")
print(f"    their frame -> {d_pred:.3e}   (dn = {r_pred['n'] - 10307})")
print(f"    raw rebuild -> {d_mine:.3e}   (dn = {r_mine['n'] - 10307})")
REPRO_OK = (d_pred < 1e-12 and d_mine < 1e-12
            and r_pred["n"] == 10307 and r_mine["n"] == 10307)
print(f"  REPRODUCTION: {'EXACT -- proceeding' if REPRO_OK else '*** NOT EXACT -- STOP ***'}")
RESULTS["step1_reproduction"] = dict(
    target_dR2=PRED_DR2_TARGET, target_m0=PRED_M0_TARGET, target_m1=PRED_M1_TARGET,
    from_predecessor_frame=r_pred, from_raw_rebuild=r_mine,
    abs_diff_from_predecessor_frame=float(d_pred),
    abs_diff_from_raw_rebuild=float(d_mine),
    frame_column_max_abs_deltas=FRAME_DELTAS, frame_rebuild_exact=FRAME_EXACT,
    exact=bool(REPRO_OK))
if not REPRO_OK:
    json.dump(RESULTS, open(os.path.join(HERE, "build_results.json"), "w",
                            encoding="utf-8"), indent=2, default=float)
    raise SystemExit("STOP: could not reproduce the predecessor's conditional dR2.")

# also reproduce the other four zones for completeness
cond_all = {}
for z in ZONES:
    g = SF[SF["zone"] == z].dropna(subset=["z_att", "S1", "fga", "OS"])
    cond_all[z] = dr2_conditional(g, "fga")
    print(f"    conditional dR2  {z:<24} = {cond_all[z]['dR2']:+.6f}  "
          f"(base R2 {cond_all[z]['m0']:.6f}, n={cond_all[z]['n']})")
RESULTS["step1_conditional_all_zones"] = cond_all

# ==================================================== 2 MINUTES FROM THE GAMELOG =====
hdr("2. GAMELOG -- structural audit, then MINUTES for strictly-prior games only")
gl = []
for ssn in PARTITION:
    d = pd.read_parquet(os.path.join(REPO, f"data/wnba_gamelog_{ssn}.parquet"))
    d["season"] = ssn
    d = d[d["season"].isin(PARTITION)]                  # FILTER-POINT 5
    gl.append(d)
GL = pd.concat(gl, ignore_index=True)
GL = GL[GL["season"].isin(PARTITION)].copy()            # FILTER-POINT 6
print(f"  gamelog rows = {len(GL)}  seasons={sorted(GL['season'].unique())}")
print(f"  SEASON column values = {sorted(GL['SEASON'].unique())}")

# structural audit: the three ratio columns must be within-row identities.
for num, den, pct in [("FGM", "FGA", "FG_PCT"), ("FG3M", "FG3A", "FG3_PCT"),
                      ("FTM", "FTA", "FT_PCT")]:
    m = GL[GL[den] > 0]
    dd = float((m[num] / m[den] - m[pct]).abs().max())
    print(f"  within-row identity {pct} == {num}/{den}: max|diff| = {dd:.3e}  "
          f"{'OK' if dd < 1e-3 else '*** NOT A WITHIN-ROW RATIO ***'}")
print("  every remaining column is a raw counting stat of that single game, an id, or a "
      "name. No aggregate, no shrunk value, no cross-row derivation -> structurally "
      "cannot embed another season. NO MANIFEST: formally UNVERIFIABLE, admitted on "
      "these grounds and used ONLY for prior-game minutes.")


def parse_min(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return np.nan
    if ":" in s:
        a, b = s.split(":", 1)
        try:
            return float(a) + float(b) / 60.0
        except ValueError:
            return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


GL["min_played"] = GL["MIN"].map(parse_min)
print(f"  parsed minutes: non-null {GL['min_played'].notna().sum()} / {len(GL)}  "
      f"range {GL['min_played'].min():.2f} .. {GL['min_played'].max():.2f}")
GLK = GL[["GAME_ID", "PLAYER_ID", "season", "min_played", "PTS", "FGA", "FTA"]].rename(
    columns={"GAME_ID": "game_id", "PLAYER_ID": "player_id", "PTS": "pts_total_box",
             "FGA": "fga_box", "FTA": "fta_box"})

# ============================================ 3 PLAYER-GAME FRAME + FGA FORECASTS ====
hdr("3. STEP 2 -- POINT-IN-TIME FGA FORECASTS (strictly prior games only)")
pg = pgt.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}).copy()
pg["fg_pts"] = (shots5.assign(v=shots5["zone"].map(ZONE_PTS) * shots5["made"])
                .groupby(["PLAYER_ID", "season", "GAME_ID"])["v"].sum()
                .reindex(pd.MultiIndex.from_frame(
                    pg[["player_id", "season", "game_id"]])).to_numpy())
pg = pg.merge(GLK, on=["game_id", "player_id", "season"], how="left")
cov = pg["min_played"].notna().mean()
print(f"  player-game rows = {len(pg)}   minutes joined for {100 * cov:.1f}% "
      f"(gamelog files contain REGULAR SEASON only -- playoff rows get NaN minutes, "
      f"which means they do not UPDATE the minutes state; their own forecast is still "
      f"built from prior regular-season games)")
print(f"  box FGA vs 5-zone shot count: corr={pg['fga_box'].corr(pg['fga']):.6f}  "
      f"mean|diff|={float((pg['fga_box'] - pg['fga']).abs().mean()):.4f} "
      f"(diff = Backcourt shots + any collection gap; DIAGNOSTIC ONLY)")

pg = pg.sort_values(["player_id", "season", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
pk = [pg["player_id"], pg["season"]]

# ---- expanding strictly-prior totals of the player's own FGA / minutes
pg["pre_n"] = pg.groupby(pk, sort=False).cumcount().astype(float)
pg["pre_fga_sum"] = pg.groupby(pk, sort=False)["fga"].cumsum() - pg["fga"]
_m = pg["min_played"].fillna(0.0)
pg["pre_min_sum"] = _m.groupby(pk, sort=False).cumsum() - _m
pg["pre_min_n"] = (pg["min_played"].notna().astype(float).groupby(pk, sort=False).cumsum()
                   - pg["min_played"].notna().astype(float))
# FGA accumulated only over games whose minutes are known (matching denominator)
_fm = pg["fga"].where(pg["min_played"].notna(), 0.0)
pg["pre_fga_sum_m"] = _fm.groupby(pk, sort=False).cumsum() - _fm

# ---- league priors, strictly BEFORE the current calendar date, same season
lgp = (pg.groupby(["season", "game_date"])
       .agg(a=("fga", "sum"), n=("fga", "size")).reset_index()
       .sort_values(["season", "game_date"], kind="stable"))
lgp["cum_a"] = lgp.groupby("season", sort=False)["a"].cumsum() - lgp["a"]
lgp["cum_n"] = lgp.groupby("season", sort=False)["n"].cumsum() - lgp["n"]
lgp["lg_mean_fga_prior"] = lgp["cum_a"] / lgp["cum_n"]
lgm = (pg.dropna(subset=["min_played"]).groupby(["season", "game_date"])
       .agg(a=("fga", "sum"), m=("min_played", "sum")).reset_index()
       .sort_values(["season", "game_date"], kind="stable"))
lgm["cum_a"] = lgm.groupby("season", sort=False)["a"].cumsum() - lgm["a"]
lgm["cum_m"] = lgm.groupby("season", sort=False)["m"].cumsum() - lgm["m"]
lgm["lg_fga_per_min_prior"] = lgm["cum_a"] / lgm["cum_m"]
pg = pg.merge(lgp[["season", "game_date", "lg_mean_fga_prior"]],
              on=["season", "game_date"], how="left")
pg = pg.merge(lgm[["season", "game_date", "lg_fga_per_min_prior"]],
              on=["season", "game_date"], how="left")
for c in ("lg_mean_fga_prior", "lg_fga_per_min_prior"):
    pg[c] = pg.groupby("season")[c].transform(lambda x: x.bfill().ffill())

# ---- FORECAST A (CRUDE): shrunk expanding mean of the player's own prior FGA
pg["F_A"] = (pg["pre_fga_sum"] + K_A * pg["lg_mean_fga_prior"]) / (pg["pre_n"] + K_A)

# ---- FORECAST A2 (reference): EWMA_0.30 of the player's prior FGA
#      == the predecessor's own role_prior_fga feature.
pg["minutes"] = pg["fga"].astype(float)
pg["fga_copy"] = pg["fga"].astype(float)
pg["F_A2"] = BASE.project(pg, "fga_copy")

# ---- FORECAST B (BETTER): frozen own_rate_v2_split_alpha with REAL prior minutes,
#      i.e. EWMA_0.03(FGA per 36 min)[prior] * EWMA_0.30(minutes)[prior] / 36,
#      shrunk-rate fallback, times an opponent prior-pace multiplier.
pgB = pg.copy()
pgB["minutes"] = pgB["min_played"]
pgB["fga_copy2"] = pgB["fga"].astype(float)
pg["F_B_core"] = BASE.project(pgB, "fga_copy2").to_numpy()
# fallback for rows with too little minutes history: shrunk rate x shrunk minutes
pg["rate_shr"] = ((pg["pre_fga_sum_m"] + K_R * pg["lg_fga_per_min_prior"])
                  / (pg["pre_min_sum"] + K_R))
pg["min_shr"] = pg["pre_min_sum"] / pg["pre_min_n"].replace(0, np.nan)
pg["F_B_fallback"] = pg["rate_shr"] * pg["min_shr"]
pg["F_B_core"] = pg["F_B_core"].fillna(pg["F_B_fallback"]).fillna(pg["F_A"])

# opponent prior pace multiplier: attempts FACED per game in the opponent's strictly
# prior games this season / league prior mean team attempts-faced per game.
tp = (tgw[["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "tot", "pre_tot",
           "pre_ngames"]].copy())
tp["opp_faced_pg"] = tp["pre_tot"] / tp["pre_ngames"].replace(0, np.nan)
lgt2 = (tgw.groupby(["season", "game_date"]).agg(a=("tot", "sum"), n=("tot", "size"))
        .reset_index().sort_values(["season", "game_date"], kind="stable"))
lgt2["cum_a"] = lgt2.groupby("season", sort=False)["a"].cumsum() - lgt2["a"]
lgt2["cum_n"] = lgt2.groupby("season", sort=False)["n"].cumsum() - lgt2["n"]
lgt2["lg_faced_pg_prior"] = lgt2["cum_a"] / lgt2["cum_n"]
tp = tp.merge(lgt2[["season", "game_date", "lg_faced_pg_prior"]],
              on=["season", "game_date"], how="left")
tp["lg_faced_pg_prior"] = tp.groupby("season")["lg_faced_pg_prior"].transform(
    lambda x: x.bfill().ffill())
tp["opp_pace"] = (tp["opp_faced_pg"] / tp["lg_faced_pg_prior"]).clip(*PACE_CLIP)
tp["opp_pace"] = tp["opp_pace"].fillna(1.0)
pg = pg.merge(tp[["OPP_TEAM_ID", "season", "GAME_ID", "opp_pace"]]
              .rename(columns={"GAME_ID": "game_id"}),
              on=["OPP_TEAM_ID", "season", "game_id"], how="left")
pg["opp_pace"] = pg["opp_pace"].fillna(1.0)
pg["F_B"] = pg["F_B_core"] * pg["opp_pace"]
pg["F_B_nopace"] = pg["F_B_core"]

# ---- FORECAST LG (floor reference): the league prior mean, no player information
pg["F_LG"] = pg["lg_mean_fga_prior"]

FCAST = ["F_LG", "F_A", "F_A2", "F_B_nopace", "F_B"]


def acc(y, yhat):
    y = np.asarray(y, float)
    yh = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yh)
    y, yh = y[m], yh[m]
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - yh) ** 2).sum())
    return dict(n=int(len(y)), mae=float(np.abs(y - yh).mean()),
                rmse=float(np.sqrt(((y - yh) ** 2).mean())),
                r2_unweighted_about_unweighted_mean=float(1 - sse / sst),
                bias=float((yh - y).mean()), corr=float(np.corrcoef(y, yh)[0, 1]))


# evaluation sets
EVAL_ALL = pg[(pg["pre_n"] >= MIN_PRIOR)].copy()
hdr("3b. FGA FORECAST ACCURACY -- its own accuracy, before it is used for anything")
print("  Target: the player's realised total field-goal attempts over the five zones.")
print("  R2 convention: plain unweighted, 1 - SSE/SST, SST about the UNWEIGHTED mean.")
print(f"\n  (i) ALL player-games with >= {MIN_PRIOR} prior games in season  n={len(EVAL_ALL)}")
print(f"  {'forecast':<14}{'n':>7}{'MAE':>9}{'RMSE':>9}{'R2':>10}{'bias':>9}{'corr':>9}")
ACC = {"all_player_games": {}, "analysis_set": {}}
for f in FCAST:
    a = acc(EVAL_ALL["fga"], EVAL_ALL[f])
    ACC["all_player_games"][f] = a
    print(f"  {f:<14}{a['n']:>7}{a['mae']:>9.4f}{a['rmse']:>9.4f}"
          f"{a['r2_unweighted_about_unweighted_mean']:>10.5f}{a['bias']:>+9.4f}"
          f"{a['corr']:>9.4f}")

# the headline analysis set = exactly the predecessor's 10,307 player-games
AN = SF[SF["zone"] == RA][["player_id", "season", "game_id"]].drop_duplicates()
EVAL_AN = pg.merge(AN, on=["player_id", "season", "game_id"], how="inner")
print(f"\n  (ii) THE PREDECESSOR'S ANALYSIS SET (fga>=5, n_prior>=3, OS available)  "
      f"n={len(EVAL_AN)}")
print(f"  {'forecast':<14}{'n':>7}{'MAE':>9}{'RMSE':>9}{'R2':>10}{'bias':>9}{'corr':>9}")
for f in FCAST:
    a = acc(EVAL_AN["fga"], EVAL_AN[f])
    ACC["analysis_set"][f] = a
    print(f"  {f:<14}{a['n']:>7}{a['mae']:>9.4f}{a['rmse']:>9.4f}"
          f"{a['r2_unweighted_about_unweighted_mean']:>10.5f}{a['bias']:>+9.4f}"
          f"{a['corr']:>9.4f}")
print(f"\n  realised FGA on the analysis set: mean={EVAL_AN['fga'].mean():.4f}  "
      f"sd={EVAL_AN['fga'].std():.4f}  var={EVAL_AN['fga'].var():.4f}")
ACC["by_season"] = {}
print(f"\n  by season (analysis set), MAE:")
for ssn in PARTITION:
    e = EVAL_AN[EVAL_AN["season"] == ssn]
    row = {f: acc(e["fga"], e[f]) for f in FCAST}
    ACC["by_season"][str(ssn)] = row
    print(f"    {ssn}  n={len(e):<6} " + "  ".join(
        f"{f}={row[f]['mae']:.3f}" for f in FCAST))
RESULTS["step2_fga_forecast_accuracy"] = ACC
RESULTS["step2_realised_fga_moments"] = dict(
    mean=float(EVAL_AN["fga"].mean()), sd=float(EVAL_AN["fga"].std()),
    var=float(EVAL_AN["fga"].var()))

# ============================================ 4 PRIOR-ONLY ZONE CONVERSION RATES =====
hdr("4. PRIOR-ONLY ZONE CONVERSION RATES (for the points target, step 4)")
lgz = (shots5.groupby(["season", "game_date", "zone"])
       .agg(a=("made", "size"), m=("made", "sum")).reset_index()
       .sort_values(["season", "zone", "game_date"], kind="stable"))
lgz["cum_a"] = lgz.groupby(["season", "zone"], sort=False)["a"].cumsum() - lgz["a"]
lgz["cum_m"] = lgz.groupby(["season", "zone"], sort=False)["m"].cumsum() - lgz["m"]
lgz["lg_zone_rate_prior"] = lgz["cum_m"] / lgz["cum_a"]
panel = panel.merge(lgz[["season", "game_date", "zone", "lg_zone_rate_prior"]],
                    on=["season", "game_date", "zone"], how="left")
panel["lg_zone_rate_prior"] = panel.groupby(["season", "zone"])[
    "lg_zone_rate_prior"].transform(lambda x: x.bfill().ffill())
panel["q_prior"] = ((panel["pre_zmk"] + K_Q * panel["lg_zone_rate_prior"])
                    / (panel["pre_zatt"] + K_Q))
print(f"  q_prior built from the player's STRICTLY PRIOR games in season, shrunk "
      f"(K_Q={K_Q:.0f} attempts) toward the league zone rate over games played "
      f"STRICTLY BEFORE this calendar date.")
print(panel.groupby("zone").agg(q=("q_prior", "mean"),
                                realised=("z_mk", "sum")).to_string())

# ============================================================== 5 WRITE THE FRAME ====
hdr("5. WRITE forecast_frame.parquet")
OUT = panel.merge(pg[["player_id", "season", "game_id", "min_played", "pts_total_box",
                      "fg_pts", "opp_pace", "pre_n", "pre_min_n"] + FCAST],
                  on=["player_id", "season", "game_id"], how="left")
OUT = OUT[(OUT["fga"] >= MIN_FGA_GAME)
          & OUT[["share", "S1", "S2", "OS", "role_prior_fga"]].notna().all(axis=1)].copy()
OUT["zone_pts"] = OUT["zone"].map(ZONE_PTS)
# strictly-prior minutes volatility (a PRE-GAME observable, for step 5)
mv = pg.copy()
mv["_m"] = mv["min_played"]
mv["prior_min_sd"] = mv.groupby(["player_id", "season"], sort=False)["_m"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).std())
mv["prior_min_mean"] = mv.groupby(["player_id", "season"], sort=False)["_m"].transform(
    lambda x: x.shift(1).expanding(min_periods=3).mean())
OUT = OUT.merge(mv[["player_id", "season", "game_id", "prior_min_sd", "prior_min_mean"]],
                on=["player_id", "season", "game_id"], how="left")
OUT = OUT[OUT["season"].isin(PARTITION)].copy()          # FILTER-POINT 7
assert set(OUT["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
COLS = ["zone", "player_id", "season", "game_id", "TEAM_ID", "OPP_TEAM_ID", "game_date",
        "fga", "z_att", "z_mk", "share", "S1", "S2", "OS", "lg_share_prior",
        "role_prior_fga", "n_prior", "q_prior", "lg_zone_rate_prior", "zone_pts",
        "min_played", "pts_total_box", "fg_pts", "opp_pace", "pre_n", "pre_min_n",
        "prior_min_sd", "prior_min_mean"] + FCAST
OUT[COLS].to_parquet(os.path.join(HERE, "forecast_frame.parquet"), index=False)
print(f"  wrote forecast_frame.parquet  rows={len(OUT)}  "
      f"player-games={OUT[['player_id','season','game_id']].drop_duplicates().shape[0]}")
print(f"  sorted(season.unique()) = {sorted(OUT['season'].unique())}")

# ---- ROBUSTNESS FRAME: the sample gate itself made pregame-observable.
# The headline row set inherits the predecessor's `realised FGA >= 5` gate, which is a
# SAMPLE DEFINITION reading a realised quantity (disclosed; it is not a feature). This
# second frame gates on the FORECAST instead, so nothing anywhere reads the game.
PG2 = panel.merge(pg[["player_id", "season", "game_id", "min_played", "pts_total_box",
                      "fg_pts", "opp_pace", "pre_n", "pre_min_n"] + FCAST],
                  on=["player_id", "season", "game_id"], how="left")
PG2 = PG2[(PG2["F_B"] >= MIN_FGA_GAME)
          & PG2[["share", "S1", "S2", "OS", "role_prior_fga"]].notna().all(axis=1)].copy()
PG2["zone_pts"] = PG2["zone"].map(ZONE_PTS)
PG2 = PG2.merge(mv[["player_id", "season", "game_id", "prior_min_sd", "prior_min_mean"]],
                on=["player_id", "season", "game_id"], how="left")
PG2 = PG2[PG2["season"].isin(PARTITION)].copy()          # FILTER-POINT 8
assert set(PG2["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
PG2[COLS].to_parquet(os.path.join(HERE, "forecast_frame_pregame_gate.parquet"),
                     index=False)
print(f"  wrote forecast_frame_pregame_gate.parquet  rows={len(PG2)}  "
      f"player-games={PG2[['player_id','season','game_id']].drop_duplicates().shape[0]}"
      f"  (gate: F_B >= {MIN_FGA_GAME}, fully pregame)")
RESULTS["pregame_gate_frame"] = dict(
    rows=int(len(PG2)),
    player_games=int(PG2[["player_id", "season", "game_id"]].drop_duplicates().shape[0]))

RESULTS["constants"] = dict(K_A=K_A, K_R=K_R, PACE_CLIP=list(PACE_CLIP), K_Q=K_Q,
                            MIN_FGA_GAME=MIN_FGA_GAME, MIN_PRE_TOTAL=MIN_PRE_TOTAL,
                            SHRINK_K=SHRINK_K, ALPHA_EFF=ALPHA_EFF, ALPHA_EXP=ALPHA_EXP,
                            MIN_PRIOR=MIN_PRIOR, BASELINE_ID=BASELINE_ID)
RESULTS["minutes_coverage_fraction"] = float(cov)
RESULTS["seasons_used"] = sorted(int(x) for x in OUT["season"].unique())
RESULTS["r2_convention"] = ("plain unweighted OLS, R2 = 1 - SSE/SST with SST about the "
                            "UNWEIGHTED mean of the response (D069)")
json.dump(RESULTS, open(os.path.join(HERE, "build_results.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("  wrote build_results.json")
print(f"\nFINAL PARTITION RE-ASSERT: {sorted(OUT['season'].unique())}")
print("Done.")
