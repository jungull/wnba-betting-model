"""E1 I0004 -- rim finishing x opponent rim-defence allowance: does it persist,
and how much of it survives a CORRECTED, PREGAME-OBSERVABLE baseline?

E1 is NON-CLAIMING. Nothing here is a RESULT.

PARTITION (GRAPH_POLICY 13.2): seasons 2021, 2022, 2023, 2024 ONLY. The 2025/2026
confirmation holdout is never read, joined, filtered against, counted or plotted.
Every load is followed immediately by a `# FILTER-POINT` and a printed
sorted(season.unique()).

ARTIFACT CONTAMINATION (13.2.2): the only pre-built artifact used is
data/masters/master_player.parquet -- ONLY inside the frozen baseline's own
validation, which was run separately. This script reads raw per-season shot
files only. It deliberately does NOT read data/zone_maps/*.csv (E0 I0004
established their shrinkage priors are pooled 2021-2026); that decision is
preserved. The contamination test used is asof_granularity == "row" from the
artifact's .manifest.json -- NOT fit_seasons / fit_through_season, and NOT a raw
byte scan for "2025"/"2026" (a known false-positive mode in this program).

R-SQUARED CONVENTION: plain unweighted OLS R2 = 1 - SSE/SST with SST taken about
the unweighted mean of the response. The shared E0 `wls_r2` helper is NOT used.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BASELINE_DIR = os.path.join(REPO, "experiments", "exploration",
                            "E1_I0011_split_alpha", "baseline")
sys.path.insert(0, BASELINE_DIR)
from corrected_baseline import (BASELINE_ID, ALPHA_EFF, ALPHA_EXP,  # noqa: E402
                                MIN_PRIOR, CorrectedOwnRateBaseline)

PARTITION = [2021, 2022, 2023, 2024]
TYPES = ["regular", "playoffs"]
RA = "Restricted Area"
MIN_LOO = 20          # E0's opponent-sample gate; kept identical for comparability
MIN_PRE = 20          # same gate for the pregame-observable opponent variant
SHRINK_K = 50.0       # pseudo-attempts for the shrunk pregame own-rate (B2)

pd.set_option("display.width", 200)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# =========================================================================== load
hdr("0. LOAD -- exploration partition only")
FILES = [f"data/shotcharts/shots_{s}_{t}.parquet" for s in PARTITION for t in TYPES]
dfs = []
for f in FILES:
    d = pd.read_parquet(os.path.join(REPO, f))
    d["season"] = int(f.split("shots_")[1][:4])
    # FILTER-POINT 1: per-file restriction to the exploration partition.
    d = d[d["season"].isin(PARTITION)]
    print(f"  {f:<50} rows={len(d):>7}  seasons={sorted(d['season'].unique())}")
    dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)
# FILTER-POINT 2: re-assert on the concatenated frame.
shots = shots[shots["season"].isin(PARTITION)].copy()
print(f"\n  concatenated rows = {len(shots)}")
print(f"  sorted(season.unique()) = {sorted(shots['season'].unique())}")
shots["game_date"] = pd.to_datetime(shots["GAME_DATE"], format="%Y%m%d")
print(f"  GAME_DATE range = {shots['game_date'].min().date()} .. {shots['game_date'].max().date()}")
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
print(f"  shots with resolved opponent = {len(shots)}  games = {shots['GAME_ID'].nunique()}")


# ============================================ 1. reproduce E0 robustness_loo.py
hdr("1. REPRODUCE E0 I0004's HEADLINE (robustness_loo.py) EXACTLY")
print("Target to hit: Restricted Area corr=+0.0444, diff(hi-lo)=+0.0392, SE~0.0052.")

s = shots.copy()
season_tot = (s.groupby(["OPP_TEAM_ID", "season", "zone"])
              .agg(season_att=("made", "size"), season_mk=("made", "sum")).reset_index())
season_pool = (s.groupby(["OPP_TEAM_ID", "season"])
               .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
game_zone = (s.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "zone"])
             .agg(game_att=("made", "size"), game_mk=("made", "sum")).reset_index())
game_pool = (s.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
             .agg(gpool_att=("made", "size"), gpool_mk=("made", "sum")).reset_index())
s = s.merge(season_tot, on=["OPP_TEAM_ID", "season", "zone"], how="left")
s = s.merge(season_pool, on=["OPP_TEAM_ID", "season"], how="left")
s = s.merge(game_zone, on=["OPP_TEAM_ID", "season", "GAME_ID", "zone"], how="left")
s = s.merge(game_pool, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
s["loo_att"] = s["season_att"] - s["game_att"]
s["loo_mk"] = s["season_mk"] - s["game_mk"]
s["loo_pool_att"] = s["pool_att"] - s["gpool_att"]
s["loo_pool_mk"] = s["pool_mk"] - s["gpool_mk"]
ok = (s["loo_att"] >= MIN_LOO) & (s["loo_pool_att"] >= MIN_LOO)
print(f"  usable LOO opponent sample: {int(ok.sum())} / {len(s)}")
s = s[ok].copy()
s["opp_loo"] = s["loo_mk"] / s["loo_att"] - s["loo_pool_mk"] / s["loo_pool_att"]
s["opp_pool_loo"] = s["loo_pool_mk"] / s["loo_pool_att"]   # carried for placebo control C1

pz = (s.groupby(["PLAYER_ID", "season", "zone"])
      .agg(att=("made", "size"), mk=("made", "sum")).reset_index())
recs = []
for (pid, zone), g in pz.groupby(["PLAYER_ID", "zone"]):
    for _, row in g.iterrows():
        other = g[g["season"] != row["season"]]
        if other["att"].sum() >= 10:
            recs.append((pid, row["season"], zone, other["mk"].sum() / other["att"].sum()))
b0 = pd.DataFrame(recs, columns=["PLAYER_ID", "season", "zone", "B0_loso_zone_rate"])
s = s.merge(b0, on=["PLAYER_ID", "season", "zone"], how="inner")
s["resid_B0"] = s["made"] - s["B0_loso_zone_rate"]
print(f"  shots with LOO opponent measure AND E0 baseline: {len(s)}")


def e0_stat(g, ycol, xcol):
    corr = g[ycol].corr(g[xcol])
    med = g[xcol].median()
    hi_m = g[xcol] > med
    hi = g.loc[hi_m, ycol].mean()
    lo = g.loc[~hi_m, ycol].mean()
    v = g[ycol].var()
    se = np.sqrt(v / hi_m.sum() + v / (~hi_m).sum())
    return dict(n=int(len(g)), corr=float(corr), diff=float(hi - lo), se_diff=float(se))


print(f"\n  {'zone':<24}{'n':>8}{'corr':>10}{'diff':>10}{'approx SE':>12}")
e0_repro = {}
for zone, g in s.groupby("zone"):
    if len(g) < 200:
        continue
    st = e0_stat(g, "resid_B0", "opp_loo")
    e0_repro[zone] = st
    print(f"  {zone:<24}{st['n']:>8}{st['corr']:>+10.4f}{st['diff']:>+10.4f}{st['se_diff']:>12.4f}")

E0_PUBLISHED = dict(corr=0.0444, diff=0.0392, se=0.0052, n=34681)
ra = e0_repro[RA]
print(f"\n  E0 published RA : n={E0_PUBLISHED['n']} corr={E0_PUBLISHED['corr']:+.4f} "
      f"diff={E0_PUBLISHED['diff']:+.4f} se={E0_PUBLISHED['se']:.4f}")
print(f"  reproduced RA   : n={ra['n']} corr={ra['corr']:+.4f} "
      f"diff={ra['diff']:+.4f} se={ra['se_diff']:.4f}")
repro_ok = (ra["n"] == E0_PUBLISHED["n"]
            and abs(ra["corr"] - E0_PUBLISHED["corr"]) < 5e-5
            and abs(ra["diff"] - E0_PUBLISHED["diff"]) < 5e-5)
print(f"  REPRODUCTION: {'EXACT MATCH' if repro_ok else '*** MISMATCH ***'}")


# ============================================ 2. what baseline was E0 stated over?
hdr("2. BASELINE IDENTIFICATION -- established from E0's CODE, not its prose")
print("""  build_and_test.py L180-188 and robustness_loo.py L91-102 both construct

      other = g[g['season'] != row['season']]              # g is per (PLAYER_ID, zone)
      if other['att'].sum() >= 10:
          base = other['mk'].sum() / other['att'].sum()

  => B0 = LEAVE-ONE-SEASON-OUT, attempt-weighted, player x zone conversion rate.

  It is NOT props_edge.py's shrunk/expanding own-rate, and it is NOT the
  within-season player_tendency_loo = (season_sum - y_t)/(n-1).

  BUT it shares the fatal property: for a 2021 shot it is computed from the
  player's 2022/2023/2024 attempts. It reads the player's LATER SEASONS. It is
  also CONSTANT within (player, season, zone) -- it has no within-season time
  variation at all, so it is not a "recent rate" in any sense. An increment
  measured over it is NOT a forecasting increment.

  Separately: robustness_loo.py's 'LOO' in zone_conv_residual_loo is
  leave-one-GAME-out over the OPPONENT-allowance construction (L75-88), i.e. the
  non-fatal kind. Distinguished, as required. BUT that opponent statistic is a
  leave-one-game-out FULL-SEASON team rate, so it too reads the opponent's LATER
  games and is likewise not pregame-observable. Both sides of E0's headline are
  retrospective. Hence variant O2 below.""")


# ================================================= 3. build pregame-observable inputs
hdr("3. BUILD PREGAME-OBSERVABLE OPPONENT ALLOWANCE (O2) AND OWN-RATE BASELINES")

# ---- opponent side, strictly prior games in season (expanding, shifted) ----
og = (shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date"])
      .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
ogz = (shots[shots["zone"] == RA]
       .groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
       .agg(z_att=("made", "size"), z_mk=("made", "sum")).reset_index())
og = og.merge(ogz, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
og[["z_att", "z_mk"]] = og[["z_att", "z_mk"]].fillna(0.0)
og = og.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                    kind="stable").reset_index(drop=True)
k = [og["OPP_TEAM_ID"], og["season"]]
for c in ["pool_att", "pool_mk", "z_att", "z_mk"]:
    og["pre_" + c] = og.groupby(k, sort=False)[c].cumsum() - og[c]
og["O2"] = og["pre_z_mk"] / og["pre_z_att"] - og["pre_pool_mk"] / og["pre_pool_att"]
og["O2_ok"] = (og["pre_z_att"] >= MIN_PRE) & (og["pre_pool_att"] >= MIN_PRE)
og.loc[~og["O2_ok"], "O2"] = np.nan
print(f"  opponent-game rows: {len(og)}; with a usable pregame allowance: "
      f"{int(og['O2_ok'].sum())} ({100 * og['O2_ok'].mean():.1f}%)")

# ---- own side: player-game Restricted-Area frame ----
pg = (shots[shots["zone"] == RA]
      .groupby(["PLAYER_ID", "season", "GAME_ID", "game_date"])
      .agg(ra_att=("made", "size"), ra_mk=("made", "sum")).reset_index())
pg = pg.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"})
# The frozen module's channel contract: efficiency = target/minutes*36,
# exposure = minutes. For a per-ATTEMPT conversion rate the exposure unit is the
# attempt, so `minutes` := RA attempts and `target` := RA makes.
pg["minutes"] = pg["ra_att"].astype(float)
pg["ra_att_copy"] = pg["ra_att"].astype(float)
print(f"  player-game RA rows (ra_att > 0): {len(pg)}  "
      f"seasons={sorted(pg['season'].unique())}")

BASE = CorrectedOwnRateBaseline()          # alpha_eff=0.03, alpha_exp=0.30, gate 3
print(f"  baseline module: {BASE!r}  id={BASELINE_ID}")
pg["proj_mk"] = BASE.project(pg, "ra_mk")           # EWMA_.03(mk/att*36)*EWMA_.30(att)/36
pg["exp_att"] = BASE.project(pg, "ra_att_copy")     # identically EWMA_.30(att) (eff==36)
pg["n_prior"] = BASE.n_prior(pg, "ra_mk")
pg["B1_split_alpha_rate"] = pg["proj_mk"] / pg["exp_att"]   # == EWMA_.03(mk/att)

# Verify the extraction identity rather than trusting the algebra.
_v = pg.sort_values(["player_id", "season", "game_date", "game_id"], kind="stable").copy()
_kk = [_v["player_id"], _v["season"]]
_eff = (_v["ra_mk"] / _v["ra_att"]).groupby(_kk, sort=False).transform(
    lambda x: x.ewm(alpha=ALPHA_EFF, adjust=True, ignore_na=True).mean())
_eff = _eff.groupby(_kk, sort=False).shift(1)
_v["_check"] = _eff
_v = _v[_v["n_prior"] >= MIN_PRIOR]
_d = (_v["B1_split_alpha_rate"] - _v["_check"]).abs().max()
print(f"  identity check  B1 == EWMA_{ALPHA_EFF}(makes/attempts)[strictly prior]: "
      f"max|diff| = {_d:.3e}  {'OK' if _d < 1e-12 else '*** FAILED ***'}")
assert _d < 1e-12

# B2: robustness variant -- attempt-weighted expanding prior-games RA rate,
# shrunk toward the expanding prior LEAGUE RA rate. Fully pregame-observable.
pg = pg.sort_values(["player_id", "season", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
kk = [pg["player_id"], pg["season"]]
pg["pre_att"] = pg.groupby(kk, sort=False)["ra_att"].cumsum() - pg["ra_att"]
pg["pre_mk"] = pg.groupby(kk, sort=False)["ra_mk"].cumsum() - pg["ra_mk"]
lg = pg.sort_values(["season", "game_date", "game_id"], kind="stable").copy()
lg["cum_att"] = lg.groupby("season", sort=False)["ra_att"].cumsum()
lg["cum_mk"] = lg.groupby("season", sort=False)["ra_mk"].cumsum()
lg["lg_prior"] = ((lg["cum_mk"] - lg["ra_mk"]) / (lg["cum_att"] - lg["ra_att"])).ffill()
pg = pg.merge(lg[["player_id", "season", "game_id", "lg_prior"]],
              on=["player_id", "season", "game_id"], how="left")
pg["lg_prior"] = pg.groupby("season")["lg_prior"].transform(lambda x: x.bfill().ffill())
pg["B2_shrunk_pregame_rate"] = ((pg["pre_mk"] + SHRINK_K * pg["lg_prior"])
                                / (pg["pre_att"] + SHRINK_K))
pg.loc[pg["n_prior"] < MIN_PRIOR, "B2_shrunk_pregame_rate"] = np.nan
print(f"  B1 coverage (n_prior>=3): {int(pg['B1_split_alpha_rate'].notna().sum())} "
      f"/ {len(pg)} player-games")
print(f"  B2 coverage             : {int(pg['B2_shrunk_pregame_rate'].notna().sum())} "
      f"/ {len(pg)} player-games")

# =========================================================== 4. assemble RA shot frame
hdr("4. ASSEMBLE THE RESTRICTED-AREA SHOT FRAME (all baselines on identical rows)")
ras = shots[shots["zone"] == RA].copy()
ras = ras.merge(s[["GAME_ID", "GAME_EVENT_ID", "opp_loo", "opp_pool_loo"]]
                .rename(columns={"opp_loo": "O1"}),
                on=["GAME_ID", "GAME_EVENT_ID"], how="left")
ras = ras.merge(og[["OPP_TEAM_ID", "season", "GAME_ID", "O2"]],
                on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
ras = ras.merge(b0[b0["zone"] == RA][["PLAYER_ID", "season", "B0_loso_zone_rate"]],
                on=["PLAYER_ID", "season"], how="left")
ras = ras.merge(pg[["player_id", "season", "game_id", "B1_split_alpha_rate",
                    "B2_shrunk_pregame_rate", "n_prior", "exp_att"]]
                .rename(columns={"player_id": "PLAYER_ID", "game_id": "GAME_ID"}),
                on=["PLAYER_ID", "season", "GAME_ID"], how="left")
# FILTER-POINT 3: re-assert partition on the assembled frame before any statistic.
ras = ras[ras["season"].isin(PARTITION)].copy()
print(f"  RA shots = {len(ras)}  sorted(season.unique()) = {sorted(ras['season'].unique())}")

BASES = {"B0_E0_leave_one_season_out": "B0_loso_zone_rate",
         "B1_own_rate_v2_split_alpha": "B1_split_alpha_rate",
         "B2_shrunk_expanding_pregame": "B2_shrunk_pregame_rate"}
OPPS = {"O1_E0_leave_one_game_out_full_season": "O1",
        "O2_pregame_prior_games_only": "O2"}
common = ras[["O1", "O2"] + list(BASES.values())].notna().all(axis=1)
COMMON = ras[common].copy()
print(f"  common row set (every baseline AND every opponent variant present): {len(COMMON)}")
print(f"  coverage vs E0's own row set ({ra['n']}): {100 * len(COMMON) / ra['n']:.1f}%")
for nm, col in BASES.items():
    print(f"    {nm:<32} available on {int(ras[col].notna().sum()):>6} RA shots")
for nm, col in OPPS.items():
    print(f"    {nm:<32} available on {int(ras[col].notna().sum()):>6} RA shots")


# ================================================================= 5. the re-measurement
def ols_with_cluster(y, x, cluster):
    """Plain unweighted OLS y ~ 1 + x. Returns slope, naive SE, cluster-robust
    (CR0) SE clustered on `cluster`, and plain unweighted R2 = 1 - SSE/SST with
    SST about the unweighted mean of y."""
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(x, float)])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    sse = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    n, kp = X.shape
    naive = float(np.sqrt(sse / (n - kp) * XtX_inv[1, 1]))
    cl = pd.Series(list(cluster), dtype=object)
    meat = np.zeros((kp, kp))
    for _, idx in cl.groupby(cl.values, sort=False).indices.items():
        Xg, eg = X[idx], e[idx]
        u = Xg.T @ eg
        meat += np.outer(u, u)
    G = cl.nunique()
    adj = (G / max(G - 1, 1)) * ((n - 1) / (n - kp))
    V = XtX_inv @ (adj * meat) @ XtX_inv
    return dict(beta=float(b[1]), se_naive=naive,
                se_cluster_opp_team_season=float(np.sqrt(V[1, 1])),
                n_clusters=int(G), r2=float(1 - sse / sst), n=int(n))


def cell(df, ycol, xcol):
    g = df[[ycol, xcol, "OPP_TEAM_ID", "season"]].dropna()
    out = e0_stat(g, ycol, xcol)
    out.update(ols_with_cluster(g[ycol], g[xcol],
                                (g["OPP_TEAM_ID"].astype(str) + "_"
                                 + g["season"].astype(str)).tolist()))
    out["t_cluster"] = out["beta"] / out["se_cluster_opp_team_season"]
    out["t_naive"] = out["beta"] / out["se_naive"]
    return out


hdr("5. RE-MEASUREMENT -- Restricted Area, baseline x opponent-variant, COMMON ROWS")
print("R2 convention: plain unweighted OLS, 1 - SSE/SST, SST about the unweighted mean.\n")
print(f"  {'baseline':<30}{'opponent':<38}{'n':>7}{'corr':>9}{'diff':>9}"
      f"{'beta':>9}{'SE(naive)':>11}{'SE(clust)':>11}{'t_clust':>9}")
grid = {}
for bn, bc in BASES.items():
    COMMON["resid_" + bn] = COMMON["made"] - COMMON[bc]
    for on, oc in OPPS.items():
        st = cell(COMMON, "resid_" + bn, oc)
        grid[f"{bn}|{on}"] = st
        print(f"  {bn:<30}{on:<38}{st['n']:>7}{st['corr']:>+9.4f}{st['diff']:>+9.4f}"
              f"{st['beta']:>+9.4f}{st['se_naive']:>11.4f}"
              f"{st['se_cluster_opp_team_season']:>11.4f}{st['t_cluster']:>+9.2f}")

hdr("5b. E0's OWN CELL ON E0's OWN ROW SET (for the headline comparison)")
e0_cell = cell(s[s["zone"] == RA].rename(columns={"opp_loo": "O1"}), "resid_B0", "O1")
print(f"  n={e0_cell['n']}  corr={e0_cell['corr']:+.4f}  diff={e0_cell['diff']:+.4f}  "
      f"beta={e0_cell['beta']:+.4f}  SE_naive={e0_cell['se_naive']:.4f}  "
      f"SE_cluster={e0_cell['se_cluster_opp_team_season']:.4f} "
      f"(G={e0_cell['n_clusters']})  t_cluster={e0_cell['t_cluster']:+.2f}")

hdr("5c. HOW MUCH OF THE E0 EFFECT SURVIVES")
hl = grid["B0_E0_leave_one_season_out|O1_E0_leave_one_game_out_full_season"]
survive = {}
for key in grid:
    survive[key] = dict(
        frac_of_E0_diff=grid[key]["diff"] / E0_PUBLISHED["diff"],
        frac_of_E0_corr=grid[key]["corr"] / E0_PUBLISHED["corr"])
print(f"  {'cell':<70}{'diff':>9}{'% of E0 diff':>15}{'% of E0 corr':>15}")
for key in grid:
    print(f"  {key:<70}{grid[key]['diff']:>+9.4f}"
          f"{100 * survive[key]['frac_of_E0_diff']:>15.1f}"
          f"{100 * survive[key]['frac_of_E0_corr']:>15.1f}")
print(f"\n  (E0 published: diff={E0_PUBLISHED['diff']:+.4f}, corr={E0_PUBLISHED['corr']:+.4f};"
      f" same-row-set E0 cell diff={hl['diff']:+.4f})")


# ================================================================ 6. persistence
hdr("6. PERSISTENCE -- season split and half split, INSIDE the exploration partition")
per_season, per_half = {}, {}
for bn in BASES:
    for on, oc in OPPS.items():
        key = f"{bn}|{on}"
        per_season[key], per_half[key] = {}, {}
        for ssn in PARTITION:
            g = COMMON[COMMON["season"] == ssn]
            per_season[key][str(ssn)] = cell(g, "resid_" + bn, oc)
        for hn, m in [("2021_2022", COMMON["season"] <= 2022),
                      ("2023_2024", COMMON["season"] >= 2023)]:
            per_half[key][hn] = cell(COMMON[m], "resid_" + bn, oc)

print(f"  {'cell':<70}" + "".join(f"{y:>11}" for y in PARTITION)
      + f"{'signs':>8}{'H1':>10}{'H2':>10}")
for key in per_season:
    bs = [per_season[key][str(y)]["beta"] for y in PARTITION]
    npos = sum(b > 0 for b in bs)
    h1 = per_half[key]["2021_2022"]["beta"]
    h2 = per_half[key]["2023_2024"]["beta"]
    print(f"  {key:<70}" + "".join(f"{b:>+11.4f}" for b in bs)
          + f"{npos:>6}/4{h1:>+10.4f}{h2:>+10.4f}")

hdr("6b. PERSISTENCE, corr metric (directly comparable to E0 NOTES.md section 4)")
print("  E0 reported RA corr +0.049 (2021-22) then +0.034 (2023-24).")
for key in per_half:
    print(f"  {key:<70}  H1 corr={per_half[key]['2021_2022']['corr']:+.4f} "
          f"(n={per_half[key]['2021_2022']['n']})  "
          f"H2 corr={per_half[key]['2023_2024']['corr']:+.4f} "
          f"(n={per_half[key]['2023_2024']['n']})")


# ================================== 7. player-game dR2, the module's native form
hdr("7. PLAYER-GAME dR2 -- opponent rim allowance ON TOP OF own_rate_v2_split_alpha")
print("""  This is the 'incremental value over the player's own recent rate' claim in the
  form the frozen baseline was actually built for: predict a player's RESTRICTED-AREA
  MAKES in a game from the split-alpha projection, then ask whether the opponent's
  rim-defence allowance adds anything.
    M0: ra_mk ~ 1 + proj
    M1: ra_mk ~ 1 + proj + exp_att * opp_allowance
  R2 = plain unweighted OLS, 1 - SSE/SST about the unweighted mean of ra_mk.""")

pgm = pg.merge(shots[["GAME_ID", "TEAM_ID", "PLAYER_ID", "OPP_TEAM_ID"]]
               .drop_duplicates(["GAME_ID", "PLAYER_ID"])
               .rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}),
               on=["player_id", "game_id"], how="left")
pgm = pgm.merge(og[["OPP_TEAM_ID", "season", "GAME_ID", "O2"]]
                .rename(columns={"GAME_ID": "game_id"}),
                on=["OPP_TEAM_ID", "season", "game_id"], how="left")
o1g = (ras.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])["O1"].first().reset_index()
       .rename(columns={"GAME_ID": "game_id"}))
pgm = pgm.merge(o1g, on=["OPP_TEAM_ID", "season", "game_id"], how="left")
# FILTER-POINT 4: re-assert partition before the dR2 statistics.
pgm = pgm[pgm["season"].isin(PARTITION)].copy()
print(f"\n  player-game rows = {len(pgm)}  sorted(season.unique()) = "
      f"{sorted(pgm['season'].unique())}")


def dr2(df, oppcol, seasons=None):
    d = df if seasons is None else df[df["season"].isin(seasons)]
    d = d[["ra_mk", "proj_mk", "exp_att", oppcol]].dropna()
    y = d["ra_mk"].to_numpy(float)
    sst = float(((y - y.mean()) ** 2).sum())
    X0 = np.column_stack([np.ones(len(y)), d["proj_mk"]])
    X1 = np.column_stack([X0, d["exp_att"] * d[oppcol]])
    r = {}
    for nm, X in [("m0", X0), ("m1", X1)]:
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        r[nm] = 1 - float(e @ e) / sst
        r[nm + "_coef"] = [float(v) for v in b]
    r["dR2"] = r["m1"] - r["m0"]
    r["n"] = int(len(y))
    return r


dr2_res = {}
print(f"\n  {'opponent variant':<40}{'scope':<12}{'n':>7}{'R2(M0)':>10}{'R2(M1)':>10}"
      f"{'dR2':>12}{'interaction coef':>19}")
for on, oc in OPPS.items():
    for scope, ss in [("2021-2024", None)] + [(str(y), [y]) for y in PARTITION] + \
                     [("2021-2022", [2021, 2022]), ("2023-2024", [2023, 2024])]:
        r = dr2(pgm, oc, ss)
        dr2_res[f"{on}|{scope}"] = r
        print(f"  {on:<40}{scope:<12}{r['n']:>7}{r['m0']:>10.4f}{r['m1']:>10.4f}"
              f"{r['dR2']:>+12.6f}{r['m1_coef'][2]:>+19.5f}")

out = dict(e0_reproduction=e0_repro, e0_reproduction_ok=bool(repro_ok),
           e0_published=E0_PUBLISHED, e0_cell_own_rowset=e0_cell,
           grid=grid, survive=survive, per_season=per_season, per_half=per_half,
           dr2=dr2_res,
           n_common=int(len(COMMON)),
           coverage=dict({k: int(ras[v].notna().sum()) for k, v in BASES.items()},
                         **{k: int(ras[v].notna().sum()) for k, v in OPPS.items()}),
           baseline_module=dict(id=BASELINE_ID, alpha_eff=ALPHA_EFF,
                                alpha_exp=ALPHA_EXP, min_prior=MIN_PRIOR),
           seasons_used=sorted(int(x) for x in COMMON["season"].unique()))
with open(os.path.join(HERE, "measure_results.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)

COMMON.to_parquet(os.path.join(HERE, "ra_common_frame.parquet"), index=False)
pgm.to_parquet(os.path.join(HERE, "player_game_ra_frame.parquet"), index=False)
print("\n  wrote measure_results.json, ra_common_frame.parquet, player_game_ra_frame.parquet")
print(f"  FINAL PARTITION RE-ASSERT before write: COMMON seasons="
      f"{sorted(COMMON['season'].unique())}, pgm seasons={sorted(pgm['season'].unique())}")
assert set(COMMON["season"].unique()) <= set(PARTITION)
assert set(pgm["season"].unique()) <= set(PARTITION)
print("\nDone.")
