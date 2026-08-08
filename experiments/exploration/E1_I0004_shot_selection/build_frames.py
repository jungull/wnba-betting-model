"""E1 I0004b -- SHOT SELECTION channel + role concentration + five-zone multiplicity.

E1 IS NON-CLAIMING. Nothing here is a RESULT. It is a LEAD or it is dead.

WHAT THIS SCREEN ASKS (three things the conversion-channel screen left untested)
-------------------------------------------------------------------------------
(1) SELECTION: does opponent identity shift WHERE a player shoots -- the
    distribution of their field-goal ATTEMPTS across the five zones -- as distinct
    from how well they convert?
(2) ROLE / VOLUME CONCENTRATION: is any effect uniform, or concentrated in a
    definable high-usage subgroup?
(3) MULTIPLICITY: the family is FIVE zones. Family-wise correction by max-t
    permutation.

PARTITION (GRAPH_POLICY 13.2): seasons 2021, 2022, 2023, 2024 ONLY. 2025/2026 is
never read, joined, filtered against, counted, described or plotted. Every load is
followed by a `# FILTER-POINT` and a printed sorted(season.unique()).

ARTIFACT POLICY: the ONLY files read are data/shotcharts/shots_{2021..2024}_*.parquet
(raw, per-season, no manifests exist -- the season IS the filename) and the frozen
baseline module experiments/exploration/E1_I0011_split_alpha/baseline/corrected_baseline.py
(code, not data). data/zone_maps/* are FORBIDDEN (asof_granularity == "artifact",
verified by reading the manifest COLUMN VALUE, not by a text scan) and are not read.
Zone assignment is taken from the raw per-shot SHOT_ZONE_BASIC label inside each
per-season shot file, which is a property of the shot itself and reads no other row.

R-SQUARED CONVENTION (D069): plain UNWEIGHTED OLS R2 = 1 - SSE/SST with SST about
the UNWEIGHTED mean of the response. No weighting anywhere. The defective
sqrt-weight form is never used.

PRESELECTED CONSTANTS -- fixed in this file BEFORE any selection-channel statistic
was computed (see NOTES.md "where I could have cheated"):
    MIN_FGA_GAME    = 5     player must have >= 5 FGA in the game to have a share
    MIN_PRE_TOTAL   = 200   opponent must have faced >= 200 attempts in PRIOR games
    SHRINK_K        = 50    pseudo-attempts for the shrunk prior-share variant
    ROLE_CUTS       = (6.0, 11.0)  absolute FGA/game cut points for role tertiles
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
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]

MIN_LOO = 20            # E0's opponent gate, reused ONLY for the reproduction step
MIN_PRE = 20            # E1's pregame opponent gate, reused for the reproduction step
MIN_FGA_GAME = 5        # PRESELECTED
MIN_PRE_TOTAL = 200     # PRESELECTED
SHRINK_K = 50.0         # PRESELECTED
ROLE_CUTS = (6.0, 11.0)  # PRESELECTED

pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ============================================================================ 0 LOAD
hdr("0. LOAD -- exploration partition only (2021-2024)")
dfs = []
for ssn in PARTITION:
    for t in TYPES:
        f = f"data/shotcharts/shots_{ssn}_{t}.parquet"
        d = pd.read_parquet(os.path.join(REPO, f))
        d["season"] = ssn
        # FILTER-POINT 1: per-file restriction to the exploration partition.
        d = d[d["season"].isin(PARTITION)]
        print(f"  {f:<48} rows={len(d):>7}  seasons={sorted(d['season'].unique())}")
        dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)
# FILTER-POINT 2: re-assert on the concatenated frame.
shots = shots[shots["season"].isin(PARTITION)].copy()
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
print("\n  zone counts (from raw per-shot SHOT_ZONE_BASIC; zone_maps NOT read):")
print(shots["zone"].value_counts().to_string())

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
print(f"\n  shots with resolved opponent = {len(shots)}  games = {shots['GAME_ID'].nunique()}")
BACKCOURT = int((shots["zone"] == "Backcourt").sum())
shots5 = shots[shots["zone"].isin(ZONES)].copy()
print(f"  Backcourt shots dropped from the 5-zone family: {BACKCOURT} "
      f"({100 * BACKCOURT / len(shots):.2f}%)  -- E0 also excluded it (n < 200 gate)")


# =========================== 1 REPRODUCE THE CORRECTED E1 CONVERSION HEADLINE ======
hdr("1. REPRODUCE BEFORE CHANGING -- corrected E1 conversion headline (beta +0.373)")
print("""  Target (E1_I0004_rim_finishing/measure_results.json, cell
  B1_own_rate_v2_split_alpha | O2_pregame_prior_games_only):
      n = 30764   corr = +0.02881718   diff = +0.01757440   beta = +0.37315357
  Rebuilt here from the raw shot files by an independent transcription of the same
  construction. Any later difference is then attributable to MY CHANGE, not my harness.""")

# --- E0's O1: leave-one-GAME-out FULL-SEASON opponent zone rate.
# TIME WINDOW: the opponent's WHOLE SEASON minus the current game -> READS THE FUTURE.
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
s = s[ok].copy()
s["O1"] = s["loo_mk"] / s["loo_att"] - s["loo_pool_mk"] / s["loo_pool_att"]

# --- E0's B0: leave-one-SEASON-out player x zone rate. TIME WINDOW: LATER SEASONS.
pz = (s.groupby(["PLAYER_ID", "season", "zone"])
      .agg(att=("made", "size"), mk=("made", "sum")).reset_index())
recs = []
for (pid, zone), g in pz.groupby(["PLAYER_ID", "zone"]):
    for _, row in g.iterrows():
        other = g[g["season"] != row["season"]]
        if other["att"].sum() >= 10:
            recs.append((pid, row["season"], zone, other["mk"].sum() / other["att"].sum()))
b0 = pd.DataFrame(recs, columns=["PLAYER_ID", "season", "zone", "B0_loso_zone_rate"])

# --- E0 zone table reproduction (used later as the conversion-family comparator)
sB = s.merge(b0, on=["PLAYER_ID", "season", "zone"], how="inner")
sB["resid_B0"] = sB["made"] - sB["B0_loso_zone_rate"]


def e0_stat(g, ycol, xcol):
    corr = g[ycol].corr(g[xcol])
    med = g[xcol].median()
    hi_m = g[xcol] > med
    v = g[ycol].var()
    return dict(n=int(len(g)), corr=float(corr),
                diff=float(g.loc[hi_m, ycol].mean() - g.loc[~hi_m, ycol].mean()),
                se_diff=float(np.sqrt(v / hi_m.sum() + v / (~hi_m).sum())))


print(f"\n  E0 zone table reproduction ({'zone':<22}{'n':>8}{'corr':>10}{'diff':>10}):")
E0_PUB = {"Above the Break 3": (34961, 0.0027, 0.0033),
          "Corner 3": (3872, -0.0153, -0.0147),
          "In The Paint (Non-RA)": (25436, -0.0027, -0.0021),
          "Mid-Range": (22461, 0.0110, 0.0197),
          "Restricted Area": (34681, 0.0444, 0.0392)}
e0_repro = {}
for zone in ZONES:
    g = sB[sB["zone"] == zone]
    st = e0_stat(g, "resid_B0", "O1")
    e0_repro[zone] = st
    p = E0_PUB[zone]
    match = (st["n"] == p[0] and abs(st["corr"] - p[1]) < 5e-5
             and abs(st["diff"] - p[2]) < 5e-5)
    print(f"    {zone:<22}{st['n']:>8}{st['corr']:>+10.4f}{st['diff']:>+10.4f}   "
          f"E0 published ({p[0]}, {p[1]:+.4f}, {p[2]:+.4f})  {'MATCH' if match else 'MISMATCH'}")

# --- O2: strictly PRIOR GAMES opponent RA allowance (E1's corrected form).
og = (shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date"])
      .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
ogz = (shots[shots["zone"] == RA].groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
       .agg(z_att=("made", "size"), z_mk=("made", "sum")).reset_index())
og = og.merge(ogz, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
og[["z_att", "z_mk"]] = og[["z_att", "z_mk"]].fillna(0.0)
og = og.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                    kind="stable").reset_index(drop=True)
k = [og["OPP_TEAM_ID"], og["season"]]
for c in ["pool_att", "pool_mk", "z_att", "z_mk"]:
    og["pre_" + c] = og.groupby(k, sort=False)[c].cumsum() - og[c]
og["O2"] = og["pre_z_mk"] / og["pre_z_att"] - og["pre_pool_mk"] / og["pre_pool_att"]
og.loc[~((og["pre_z_att"] >= MIN_PRE) & (og["pre_pool_att"] >= MIN_PRE)), "O2"] = np.nan

# --- B1: frozen split-alpha own-rate on RA makes/attempts. STRICTLY PRIOR.
pg = (shots[shots["zone"] == RA]
      .groupby(["PLAYER_ID", "season", "GAME_ID", "game_date"])
      .agg(ra_att=("made", "size"), ra_mk=("made", "sum")).reset_index()
      .rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}))
pg["minutes"] = pg["ra_att"].astype(float)
pg["ra_att_copy"] = pg["ra_att"].astype(float)
BASE = CorrectedOwnRateBaseline()
pg["proj_mk"] = BASE.project(pg, "ra_mk")
pg["exp_att"] = BASE.project(pg, "ra_att_copy")
pg["n_prior"] = BASE.n_prior(pg, "ra_mk")
pg["B1"] = pg["proj_mk"] / pg["exp_att"]

# --- B2: shrunk expanding prior-games RA rate. STRICTLY PRIOR.
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
pg["B2"] = (pg["pre_mk"] + SHRINK_K * pg["lg_prior"]) / (pg["pre_att"] + SHRINK_K)
pg.loc[pg["n_prior"] < MIN_PRIOR, "B2"] = np.nan

ras = shots[shots["zone"] == RA].copy()
ras = ras.merge(s[["GAME_ID", "GAME_EVENT_ID", "O1"]], on=["GAME_ID", "GAME_EVENT_ID"],
                how="left")
ras = ras.merge(og[["OPP_TEAM_ID", "season", "GAME_ID", "O2"]],
                on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
ras = ras.merge(b0[b0["zone"] == RA][["PLAYER_ID", "season", "B0_loso_zone_rate"]]
                .rename(columns={"B0_loso_zone_rate": "B0"}),
                on=["PLAYER_ID", "season"], how="left")
ras = ras.merge(pg[["player_id", "season", "game_id", "B1", "B2", "n_prior", "exp_att"]]
                .rename(columns={"player_id": "PLAYER_ID", "game_id": "GAME_ID"}),
                on=["PLAYER_ID", "season", "GAME_ID"], how="left")
# FILTER-POINT 3
ras = ras[ras["season"].isin(PARTITION)].copy()
COMMON = ras[ras[["O1", "O2", "B0", "B1", "B2"]].notna().all(axis=1)].copy()
COMMON["resid_B1"] = COMMON["made"] - COMMON["B1"]
COMMON["resid_B0"] = COMMON["made"] - COMMON["B0"]


def ols_cluster(y, x, cluster):
    """Plain unweighted OLS y ~ 1 + x. R2 = 1 - SSE/SST, SST about the UNWEIGHTED
    mean of y (decision D069). CR0 cluster-robust SE on `cluster`."""
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(x, float)])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    sse = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    n, kp = X.shape
    cl = pd.Series(list(cluster), dtype=object)
    meat = np.zeros((kp, kp))
    for _, idx in cl.groupby(cl.values, sort=False).indices.items():
        u = X[idx].T @ e[idx]
        meat += np.outer(u, u)
    G = cl.nunique()
    adj = (G / max(G - 1, 1)) * ((n - 1) / (n - kp))
    V = XtX_inv @ (adj * meat) @ XtX_inv
    return dict(beta=float(b[1]), se_naive=float(np.sqrt(sse / (n - kp) * XtX_inv[1, 1])),
                se_cluster=float(np.sqrt(V[1, 1])), n_clusters=int(G),
                r2_unweighted_about_unweighted_mean=float(1 - sse / sst), n=int(n))


def cell(df, ycol, xcol):
    g = df[[ycol, xcol, "OPP_TEAM_ID", "season"]].dropna()
    out = e0_stat(g, ycol, xcol)
    out.update(ols_cluster(g[ycol], g[xcol],
                           (g["OPP_TEAM_ID"].astype(str) + "_" + g["season"].astype(str)).tolist()))
    out["t_cluster"] = out["beta"] / out["se_cluster"]
    out["t_naive"] = out["beta"] / out["se_naive"]
    return out


repro = cell(COMMON, "resid_B1", "O2")
E1_TARGET = dict(n=30764, corr=0.02881718165669519, diff=0.01757439922911997,
                 beta=0.3731535713274873)
print(f"\n  reproduced: n={repro['n']}  corr={repro['corr']:+.8f}  "
      f"diff={repro['diff']:+.8f}  beta={repro['beta']:+.8f}")
print(f"  E1 target : n={E1_TARGET['n']}  corr={E1_TARGET['corr']:+.8f}  "
      f"diff={E1_TARGET['diff']:+.8f}  beta={E1_TARGET['beta']:+.8f}")
repro_delta = {k: float(repro[k] - E1_TARGET[k]) for k in ("corr", "diff", "beta")}
repro_delta["n"] = int(repro["n"] - E1_TARGET["n"])
print(f"  ABSOLUTE DIFFERENCE: dn={repro_delta['n']}  |dcorr|={abs(repro_delta['corr']):.3e}  "
      f"|ddiff|={abs(repro_delta['diff']):.3e}  |dbeta|={abs(repro_delta['beta']):.3e}")
REPRO_OK = (repro_delta["n"] == 0 and abs(repro_delta["beta"]) < 1e-9)
print(f"  REPRODUCTION: {'EXACT' if REPRO_OK else '*** NOT EXACT -- investigate ***'}")


# ================= 2 CONVERSION FAMILY, ALL FIVE ZONES, FULLY PREGAME-OBSERVABLE ===
hdr("2. CONVERSION FAMILY -- all five zones on the corrected (B1 x O2) construction")
print("""  The surviving lead must be assessed against its whole family, so the corrected
  construction is extended to all five zones: own-rate = frozen split-alpha EWMA of
  the player's PRIOR-GAMES-IN-SEASON zone conversion rate; opponent = the zone rate
  allowed in the opponent's STRICTLY PRIOR games in season, minus its prior pooled rate.""")

conv_rows = []
for zone in ZONES:
    zsh = shots[shots["zone"] == zone]
    # opponent side, strictly prior games in season
    o = (shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "game_date"])
         .agg(pool_att=("made", "size"), pool_mk=("made", "sum")).reset_index())
    oz = (zsh.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
          .agg(z_att=("made", "size"), z_mk=("made", "sum")).reset_index())
    o = o.merge(oz, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
    o[["z_att", "z_mk"]] = o[["z_att", "z_mk"]].fillna(0.0)
    o = o.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                      kind="stable").reset_index(drop=True)
    kz = [o["OPP_TEAM_ID"], o["season"]]
    for c in ["pool_att", "pool_mk", "z_att", "z_mk"]:
        o["pre_" + c] = o.groupby(kz, sort=False)[c].cumsum() - o[c]
    o["OC"] = o["pre_z_mk"] / o["pre_z_att"] - o["pre_pool_mk"] / o["pre_pool_att"]
    o.loc[~((o["pre_z_att"] >= MIN_PRE) & (o["pre_pool_att"] >= MIN_PRE)), "OC"] = np.nan

    # own side, frozen split-alpha on the zone's makes/attempts, strictly prior
    p = (zsh.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date"])
         .agg(z_att=("made", "size"), z_mk=("made", "sum")).reset_index()
         .rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"}))
    p["minutes"] = p["z_att"].astype(float)
    p["z_att_copy"] = p["z_att"].astype(float)
    p["proj_mk"] = BASE.project(p, "z_mk")
    p["exp_att"] = BASE.project(p, "z_att_copy")
    p["Bz"] = p["proj_mk"] / p["exp_att"]

    z = zsh.merge(o[["OPP_TEAM_ID", "season", "GAME_ID", "OC"]],
                  on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")
    z = z.merge(p[["player_id", "season", "game_id", "Bz"]]
                .rename(columns={"player_id": "PLAYER_ID", "game_id": "GAME_ID"}),
                on=["PLAYER_ID", "season", "GAME_ID"], how="left")
    # FILTER-POINT 4
    z = z[z["season"].isin(PARTITION)].copy()
    z["resid"] = z["made"] - z["Bz"]
    z = z[z[["resid", "OC"]].notna().all(axis=1)].copy()
    z["zone_name"] = zone
    conv_rows.append(z[["zone_name", "season", "OPP_TEAM_ID", "PLAYER_ID", "GAME_ID",
                        "resid", "OC"]])
CONV = pd.concat(conv_rows, ignore_index=True)
# FILTER-POINT 5
CONV = CONV[CONV["season"].isin(PARTITION)].copy()
print(f"\n  {'zone':<24}{'n':>8}{'corr':>10}{'diff':>10}{'beta':>10}{'SE(cl)':>10}{'t(cl)':>9}{'R2':>11}")
for zone in ZONES:
    g = CONV[CONV["zone_name"] == zone].rename(columns={"resid": "y", "OC": "x"})
    st = cell(g, "y", "x")
    print(f"  {zone:<24}{st['n']:>8}{st['corr']:>+10.4f}{st['diff']:>+10.4f}"
          f"{st['beta']:>+10.4f}{st['se_cluster']:>10.4f}{st['t_cluster']:>+9.2f}"
          f"{st['r2_unweighted_about_unweighted_mean']:>11.6f}")


# ============================================= 3 THE SELECTION CHANNEL (the target) =
hdr("3. SELECTION CHANNEL -- build the player-game x zone attempt-share panel")
print(f"""  RESPONSE   share_z = (player's attempts in zone z this game) / (player's total
             attempts this game, over the five zones). Zones with zero attempts are
             PRESENT as share = 0 -- otherwise the test would condition on shooting there.
  OWN BASE   S1 = frozen own_rate_v2_split_alpha with minutes := total FGA in the game
             and target := zone attempts, so the efficiency channel IS
             EWMA_{ALPHA_EFF}(zone share) over the player's STRICTLY PRIOR games in season,
             gated at n_prior >= {MIN_PRIOR}. Reads: PRIOR GAMES OF THIS PLAYER, THIS SEASON.
             S2 (robustness) = expanding attempt-weighted prior-games share shrunk toward
             the expanding prior LEAGUE share, K = {SHRINK_K:.0f}. Same window.
  OPPONENT   OS_z = (attempts in zone z faced by the opponent in its STRICTLY PRIOR games
             this season / total attempts faced in those games) - (LEAGUE share in zone z
             over all games played STRICTLY BEFORE this calendar date this season).
             Gate: >= {MIN_PRE_TOTAL} prior attempts faced. Reads: PRIOR GAMES ONLY.
  GATE       player must have >= {MIN_FGA_GAME} FGA in the game.""")

# ---- player-game totals over the five zones
pgt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "game_date", "TEAM_ID",
                       "OPP_TEAM_ID"]).size().rename("fga").reset_index())
pzt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "zone"]).size()
       .rename("z_att").reset_index())
panel = (pgt.assign(key=1).merge(pd.DataFrame({"zone": ZONES, "key": 1}), on="key")
         .drop(columns="key"))
panel = panel.merge(pzt, on=["PLAYER_ID", "season", "GAME_ID", "zone"], how="left")
panel["z_att"] = panel["z_att"].fillna(0.0)
panel["share"] = panel["z_att"] / panel["fga"]
panel = panel.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"})
panel["minutes"] = panel["fga"].astype(float)
panel["fga_copy"] = panel["fga"].astype(float)
print(f"\n  panel rows = {len(panel)}  ({panel['game_id'].nunique()} games, "
      f"{len(pgt)} player-games x {len(ZONES)} zones)")
print(f"  sorted(season.unique()) = {sorted(panel['season'].unique())}")

# ---- S1 via the frozen module, per zone
parts = []
for zone in ZONES:
    q = panel[panel["zone"] == zone].copy()
    q["proj_z"] = BASE.project(q, "z_att")
    q["exp_fga"] = BASE.project(q, "fga_copy")
    q["n_prior"] = BASE.n_prior(q, "z_att")
    q["S1"] = q["proj_z"] / q["exp_fga"]
    parts.append(q)
panel = pd.concat(parts, ignore_index=True)

# identity check: S1 must equal EWMA_ALPHA_EFF(share)[strictly prior]
_v = panel.sort_values(["zone", "player_id", "season", "game_date", "game_id"],
                       kind="stable").copy()
_kk = [_v["zone"], _v["player_id"], _v["season"]]
_e = _v["share"].groupby(_kk, sort=False).transform(
    lambda x: x.ewm(alpha=ALPHA_EFF, adjust=True, ignore_na=True).mean())
_v["_chk"] = _e.groupby(_kk, sort=False).shift(1)
_w = _v[_v["n_prior"] >= MIN_PRIOR]
_d = float((_w["S1"] - _w["_chk"]).abs().max())
print(f"  identity check  S1 == EWMA_{ALPHA_EFF}(zone share)[strictly prior]: "
      f"max|diff| = {_d:.3e}  {'OK' if _d < 1e-12 else '*** FAILED ***'}")
assert _d < 1e-12

# ---- S2: expanding prior-games share shrunk to expanding prior LEAGUE share
panel = panel.sort_values(["zone", "player_id", "season", "game_date", "game_id"],
                          kind="stable").reset_index(drop=True)
gk = [panel["zone"], panel["player_id"], panel["season"]]
panel["pre_zatt"] = panel.groupby(gk, sort=False)["z_att"].cumsum() - panel["z_att"]
panel["pre_fga"] = panel.groupby(gk, sort=False)["fga"].cumsum() - panel["fga"]

# league prior share, STRICTLY BEFORE the current calendar date (not just before the
# current row) -- avoids same-day leakage entirely.
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

# ---- opponent selection allowance OS, strictly prior games
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
for z in ZONES:
    tgw["pre_" + z] = tgw.groupby(tk, sort=False)[z].cumsum() - tgw[z]
    tgw["oppshare_" + z] = tgw["pre_" + z] / tgw["pre_tot"]
tgw["OS_ok"] = tgw["pre_tot"] >= MIN_PRE_TOTAL
print(f"\n  opponent-game rows = {len(tgw)}; usable prior-share allowance "
      f"(>= {MIN_PRE_TOTAL} prior attempts faced): {int(tgw['OS_ok'].sum())} "
      f"({100 * tgw['OS_ok'].mean():.1f}%)")

oslong = tgw.melt(id_vars=["OPP_TEAM_ID", "season", "GAME_ID", "game_date", "OS_ok",
                           "pre_tot"],
                  value_vars=["oppshare_" + z for z in ZONES],
                  var_name="zone", value_name="opp_share_prior")
oslong["zone"] = oslong["zone"].str.replace("oppshare_", "", regex=False)
oslong = oslong.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                      on=["season", "game_date", "zone"], how="left")
oslong["OS"] = oslong["opp_share_prior"] - oslong["lg_share_prior"]
oslong.loc[~oslong["OS_ok"], ["OS", "opp_share_prior"]] = np.nan

panel = panel.merge(oslong[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "OS",
                            "opp_share_prior"]]
                    .rename(columns={"GAME_ID": "game_id"}),
                    on=["OPP_TEAM_ID", "season", "game_id", "zone"], how="left")

# ---- role / volume feature, STRICTLY PRIOR: EWMA_0.30 of the player's FGA per game
role = (panel[panel["zone"] == RA][["player_id", "season", "game_id", "exp_fga"]]
        .rename(columns={"exp_fga": "role_prior_fga"}))
panel = panel.merge(role, on=["player_id", "season", "game_id"], how="left")

# FILTER-POINT 6
panel = panel[panel["season"].isin(PARTITION)].copy()
SEL = panel[(panel["fga"] >= MIN_FGA_GAME)
            & panel[["share", "S1", "S2", "OS", "role_prior_fga"]].notna().all(axis=1)].copy()
SEL["resid_S1"] = SEL["share"] - SEL["S1"]
SEL["resid_S2"] = SEL["share"] - SEL["S2"]
print(f"\n  selection analysis rows = {len(SEL)}  "
      f"({SEL[['player_id', 'season', 'game_id']].drop_duplicates().shape[0]} player-games "
      f"x {len(ZONES)} zones)")
print(f"  sorted(season.unique()) = {sorted(SEL['season'].unique())}")
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"

print(f"\n  {'zone':<24}{'n':>8}{'mean share':>12}{'sd OS':>10}{'corr':>10}{'diff':>10}"
      f"{'beta':>10}{'SE(cl)':>10}{'t(cl)':>9}{'R2':>11}")
for zone in ZONES:
    g = SEL[SEL["zone"] == zone]
    st = cell(g, "resid_S1", "OS")
    print(f"  {zone:<24}{st['n']:>8}{g['share'].mean():>12.4f}{g['OS'].std():>10.5f}"
          f"{st['corr']:>+10.4f}{st['diff']:>+10.4f}{st['beta']:>+10.4f}"
          f"{st['se_cluster']:>10.4f}{st['t_cluster']:>+9.2f}"
          f"{st['r2_unweighted_about_unweighted_mean']:>11.6f}")

# ======================================================================= 4 WRITE ====
hdr("4. WRITE FRAMES")
assert set(SEL["season"].unique()) <= set(PARTITION)
assert set(CONV["season"].unique()) <= set(PARTITION)
assert set(COMMON["season"].unique()) <= set(PARTITION)
SEL_OUT = SEL[["zone", "player_id", "season", "game_id", "TEAM_ID", "OPP_TEAM_ID",
               "game_date", "fga", "z_att", "share", "S1", "S2", "resid_S1", "resid_S2",
               "OS", "opp_share_prior", "lg_share_prior", "role_prior_fga", "n_prior"]]
SEL_OUT.to_parquet(os.path.join(HERE, "selection_frame.parquet"), index=False)
CONV.to_parquet(os.path.join(HERE, "conversion_frame.parquet"), index=False)
COMMON[["season", "OPP_TEAM_ID", "PLAYER_ID", "GAME_ID", "resid_B1", "resid_B0",
        "O1", "O2", "exp_att"]].to_parquet(
    os.path.join(HERE, "repro_ra_common.parquet"), index=False)

json.dump(dict(reproduction=dict(target=E1_TARGET, reproduced=repro,
                                 delta=repro_delta, exact=bool(REPRO_OK)),
               e0_zone_reproduction=e0_repro,
               backcourt_dropped=BACKCOURT,
               n_selection_rows=int(len(SEL)),
               n_conversion_rows=int(len(CONV)),
               constants=dict(MIN_FGA_GAME=MIN_FGA_GAME, MIN_PRE_TOTAL=MIN_PRE_TOTAL,
                              MIN_PRE=MIN_PRE, MIN_LOO=MIN_LOO, SHRINK_K=SHRINK_K,
                              ROLE_CUTS=list(ROLE_CUTS), ALPHA_EFF=ALPHA_EFF,
                              ALPHA_EXP=ALPHA_EXP, MIN_PRIOR=MIN_PRIOR,
                              BASELINE_ID=BASELINE_ID),
               seasons_used=sorted(int(x) for x in SEL["season"].unique())),
          open(os.path.join(HERE, "build_results.json"), "w", encoding="utf-8"), indent=2)
print(f"  wrote selection_frame.parquet ({len(SEL_OUT)} rows), "
      f"conversion_frame.parquet ({len(CONV)} rows), repro_ra_common.parquet, "
      f"build_results.json")
print(f"  FINAL PARTITION RE-ASSERT: SEL={sorted(SEL['season'].unique())} "
      f"CONV={sorted(CONV['season'].unique())} COMMON={sorted(COMMON['season'].unique())}")
print("\nDone.")
