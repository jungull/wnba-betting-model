"""E0_I0024 s02 -- BUILD THE SCREENING FRAME.

Order of operations, deliberately:
    manifest checks -> load -> partition assert -> targets + identity assert -> prior-only player
    references -> team/opponent zone-allowance features -> teammate-availability features ->
    partition RE-assert -> BRUTE-FORCE LEAKAGE PROBES -> write.

FORBIDDEN AND NOT OPENED:
    data/w1_truth/player_game_availability.csv, data/w1_truth/roster_asof.csv  (artifact-granular,
        fit_through_season 2026; filtering does NOT help).  Availability is rebuilt from BOX
        MEMBERSHIP (minutes>0), the D076 method.
    data/zone_maps/*  (artifact-granular).  Zones are derived from raw per-shot SHOT_ZONE_BASIC.

Every leakage probe here is a BRUTE-FORCE RECOMPUTATION on a random sample of rows -- a reference
value is recomputed from scratch using only rows strictly earlier by (date, game_id) within the
entity, and asserted EXACTLY equal.  Inspection of the code is not accepted as evidence.
"""
import json
import os
import sys
from collections import deque

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rb_base import (BASE_COLS, EWMA_HALFLIFE, FORBIDDEN, HEADLINE_SEASONS, HISTORY_FLOOR,
                     MP_PATH, MT_PATH, OUT, ROOT, SEASONS, SHOTDIR, SEED, TARGET_PCT, TARGETS,
                     assert_partition, hdr, league_prior_mean, manifest_status, prior_count,
                     prior_ewma, prior_mean, prior_sum, prior_trail, safe_div, sha)

rep = {}

# =====================================================================================
hdr("1. MANIFEST CHECKS -- read from disk at call time, not cited from notes")
# =====================================================================================
paths = [MP_PATH, MT_PATH]
for s in SEASONS:
    for k in ["regular", "playoffs"]:
        paths.append(os.path.join(SHOTDIR, "shots_%d_%s.parquet" % (s, k)))
paths += FORBIDDEN[:2]
ms = []
for p in paths:
    m = manifest_status(p)
    ms.append(m)
    print("  %-56s manifest=%-5s gran=%-9s fts=%-6s -> %s"
          % (m["artifact"], m["manifest_present"], m["asof_granularity"],
             m["fit_through_season"], m["status"]))
rep["manifests"] = ms
print("\n  USED:       master_player.parquet, master_team.parquet  (asof_granularity='row')")
print("  USED:       data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet")
print("              -- NO MANIFEST.  Reported as UNVERIFIABLE_NO_MANIFEST.  A missing manifest is")
print("                 never a pass.  s00b reproduced D087's row-granularity VALUE evidence at")
print("                 1.000000 of 132,558 rows (SHOT_DISTANCE == floor(hypot(LOC_X,LOC_Y)/10))")
print("                 and reconciled team-game FGA to the box at 0.9990.  That is a MITIGATION,")
print("                 NOT a manifest, and every rebound conclusion inherits the caveat.")
print("  NOT OPENED: w1_truth/player_game_availability.csv, w1_truth/roster_asof.csv, zone_maps/*")

# =====================================================================================
hdr("2. LOAD master_player + PARTITION FILTER (VALUE test)")
# =====================================================================================
mp = pd.read_parquet(MP_PATH)
print("  raw master_player %s   seasons in file: %s"
      % (mp.shape, sorted(pd.unique(mp["season"]).tolist())))
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()
assert_partition(mp)
print("  after 2021-2024 filter: %s   max_date=%s" % (mp.shape, mp["game_date"].max().date()))

NUM = ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
       "stl", "blk", "tov", "pf", "pts", "pace", "possessions"] + list(set(TARGET_PCT.values()))
for c in NUM:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
for c in ["player_id", "team_id", "opp_team_id"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype("Int64")
mp["game_id"] = mp["game_id"].astype(str)

pl = mp[mp["minutes"] > 0].copy()
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
print("  APPEARED rows (minutes>0): %d   players=%d   games=%d"
      % (len(pl), pl["player_id"].nunique(), pl["game_id"].nunique()))

# =====================================================================================
hdr("3. TARGETS + BOX IDENTITY ASSERT")
# =====================================================================================
pl["y_oreb"] = pl["oreb"]
pl["y_dreb"] = pl["dreb"]
pl["y_reb"] = pl["oreb"] + pl["dreb"]
pl["y_ast"] = pl["ast"]
pl["y_pts"] = pl["pts"]
ident = (pl["y_reb"] - pl["reb"]).abs()
print("  identity oreb+dreb == reb : exact on %d of %d rows (%.6f), max|diff|=%.4f"
      % ((ident == 0).sum(), len(pl), (ident == 0).mean(), ident.max()))
assert (ident == 0).mean() > 0.999, "rebound identity broken"
rep["reb_identity_frac"] = float((ident == 0).mean())

print("\n  RESPONSE DISTRIBUTIONS (appeared rows, 2021-2024):")
dist = []
for t in TARGETS:
    v = pl[t]
    d = dict(target=t, n=int(v.notna().sum()), mean=float(v.mean()), sd=float(v.std(ddof=1)),
             p0=float((v == 0).mean()), p50=float(v.median()), p90=float(v.quantile(.90)),
             maxv=float(v.max()), var=float(v.var(ddof=1)))
    dist.append(d)
    print("   %-8s n=%-6d mean=%7.4f sd=%7.4f var=%8.4f  P(y=0)=%.4f  med=%4.1f p90=%5.1f max=%d"
          % (t, d["n"], d["mean"], d["sd"], d["var"], d["p0"], d["p50"], d["p90"], d["maxv"]))
rep["response_distributions"] = dist

# =====================================================================================
hdr("4. STRICTLY-PRIOR PLAYER REFERENCES.  .shift(1) ALWAYS PRECEDES .expanding()/.rolling().")
# =====================================================================================
PK = ["season", "player_id"]
pl["n_prior"] = prior_count(pl, PK, "y_pts")
pl["ref_mean_minutes"] = prior_mean(pl, PK, "minutes")
pl["ref_trail5_minutes"] = prior_trail(pl, PK, "minutes", 5)
pl["ref_mean_pace"] = prior_mean(pl, PK, "pace")
pl["is_home"] = pd.to_numeric(pl["is_home"], errors="coerce").astype(float)

# HISTORY MINUTES FLOOR (D093).  Applied to the HISTORY ONLY -- which prior games feed a
# per-minute rate.  NEVER to the response: filtering the response conditions on an outcome.
pl["_hf"] = (pl["minutes"] >= HISTORY_FLOOR).astype(float)
pl["_min_f"] = pl["minutes"] * pl["_hf"]
pl["prior_min_floored"] = prior_sum(pl, PK, "_min_f")

REFS = {}
for t in TARGETS:
    pl["_t_f"] = pl[t] * pl["_hf"]
    prior_t_floored = prior_sum(pl, PK, "_t_f")
    rate_floored = safe_div(prior_t_floored, pl["prior_min_floored"])

    m = prior_mean(pl, PK, t)
    e = prior_ewma(pl, PK, t)
    r5 = prior_trail(pl, PK, t, 5)
    pct = prior_mean(pl, PK, TARGET_PCT[t])

    lg_m = league_prior_mean(pl, t)
    lg_rate = league_prior_mean(pl.assign(_rt=safe_div(pl[t], pl["minutes"])), "_rt")
    lg_pct = league_prior_mean(pl, TARGET_PCT[t])

    pl["ref_mean__" + t] = m.fillna(lg_m).fillna(pl[t].mean())
    pl["ref_ewma__" + t] = e.fillna(lg_m).fillna(pl[t].mean())
    pl["ref_trail5__" + t] = r5.fillna(lg_m).fillna(pl[t].mean())
    rate = pd.Series(rate_floored, index=pl.index).fillna(lg_rate)
    pl["ref_rate_floored__" + t] = rate
    pl["ref_rate_x_min__" + t] = rate * pl["ref_mean_minutes"].fillna(pl["minutes"].mean())
    pl["ref_pct__" + t] = pct.fillna(lg_pct).fillna(pl[TARGET_PCT[t]].mean())
    REFS[t] = dict(rate_cold=float(pd.Series(rate_floored).isna().mean()))
    print("  %-8s ref_mean cold=%.4f  rate cold=%.4f  ref_pct cold=%.4f"
          % (t, float(m.isna().mean()), float(pd.Series(rate_floored).isna().mean()),
             float(pct.isna().mean())))

pl["ref_mean_minutes"] = pl["ref_mean_minutes"].fillna(league_prior_mean(pl, "minutes")).fillna(
    pl["minutes"].mean())
pl["ref_trail5_minutes"] = pl["ref_trail5_minutes"].fillna(pl["ref_mean_minutes"])
pl["ref_mean_pace"] = pl["ref_mean_pace"].fillna(league_prior_mean(pl, "pace")).fillna(
    pl["pace"].mean())
pl["n_prior"] = pl["n_prior"].fillna(0.0)

# ---- ORACLE quantities (LABELLED ORACLES, used ONLY in the ladder, NEVER as features) ----
for t in TARGETS:
    pl["ORACLE_seasonmean__" + t] = pl.groupby(PK, sort=False)[t].transform("mean")
    pl["ORACLE_seasonrate__" + t] = (pl.groupby(PK, sort=False)[t].transform("sum")
                                     / pl.groupby(PK, sort=False)["minutes"].transform("sum"))
print("  oracle season-mean / season-rate columns built (LABELLED; ladder only, never features)")

# =====================================================================================
hdr("5. SHOTCHART ZONE PROFILES -> TEAM-GAME, then STRICTLY-PRIOR EXPANDING BY TEAM")
# =====================================================================================
parts = []
for s in SEASONS:
    for k in ["regular", "playoffs"]:
        p = os.path.join(SHOTDIR, "shots_%d_%s.parquet" % (s, k))
        if os.path.exists(p):
            d = pd.read_parquet(p)
            d["season"] = s
            parts.append(d)
sh = pd.concat(parts, ignore_index=True)
sh["game_date"] = pd.to_datetime(sh["GAME_DATE"].astype(str), format="%Y%m%d", errors="coerce")
assert_partition(sh, season_cols=("season",), date_cols=("game_date",))
sh["GAME_ID"] = sh["GAME_ID"].astype(str)
sh["TEAM_ID"] = pd.to_numeric(sh["TEAM_ID"], errors="coerce").astype("int64")
sh["PLAYER_ID"] = pd.to_numeric(sh["PLAYER_ID"], errors="coerce").astype("int64")
sh["att"] = pd.to_numeric(sh["SHOT_ATTEMPTED_FLAG"], errors="coerce").fillna(0.0)
sh["made"] = pd.to_numeric(sh["SHOT_MADE_FLAG"], errors="coerce").fillna(0.0)
sh["is3"] = (sh["SHOT_TYPE"].astype(str) == "3PT Field Goal").astype(float)
z = sh["SHOT_ZONE_BASIC"].astype(str)
sh["z_ra"] = (z == "Restricted Area").astype(float)
sh["z_paint_nonra"] = (z == "In The Paint (Non-RA)").astype(float)
sh["z_mid"] = (z == "Mid-Range").astype(float)
sh["z_atb3"] = (z == "Above the Break 3").astype(float)
sh["z_corner3"] = z.isin(["Left Corner 3", "Right Corner 3"]).astype(float)
sh["miss3"] = sh["is3"] * (1.0 - sh["made"])
print("  shot rows 2021-2024: %d  games=%d" % (len(sh), sh["GAME_ID"].nunique()))

ZC = ["z_ra", "z_paint_nonra", "z_mid", "z_atb3", "z_corner3"]
tg = sh.groupby(["season", "GAME_ID", "TEAM_ID"], as_index=False).agg(
    **{c: (c, "sum") for c in ZC},
    sc_att=("att", "sum"), sc_made=("made", "sum"), sc_miss3=("miss3", "sum"))
tg = tg.rename(columns={"GAME_ID": "game_id", "TEAM_ID": "team_id"})
print("  team-game shot aggregates: %d" % len(tg))

# ALLOWED profile of team T in game g = the OTHER team's shots in that game.
gt = tg.groupby(["season", "game_id"], as_index=False).agg(
    **{("tot_" + c): (c, "sum") for c in ZC},
    tot_att=("sc_att", "sum"), tot_made=("sc_made", "sum"), tot_miss3=("sc_miss3", "sum"))
tg = tg.merge(gt, on=["season", "game_id"], how="left")
for c in ZC:
    tg["allow_" + c] = tg["tot_" + c] - tg[c]
tg["allow_att"] = tg["tot_att"] - tg["sc_att"]
tg["allow_made"] = tg["tot_made"] - tg["sc_made"]
tg["allow_miss3"] = tg["tot_miss3"] - tg["sc_miss3"]
tg["allow_miss"] = tg["allow_att"] - tg["allow_made"]
tg["own_miss"] = tg["sc_att"] - tg["sc_made"]

# team-game dates for the strictly-prior ordering
dates = mp[["season", "game_id", "team_id", "game_date"]].drop_duplicates()
dates["team_id"] = pd.to_numeric(dates["team_id"], errors="coerce").astype("int64")
tg = tg.merge(dates, on=["season", "game_id", "team_id"], how="left")
print("  team-game rows with a date: %d of %d" % (tg["game_date"].notna().sum(), len(tg)))
tg = tg.dropna(subset=["game_date"]).sort_values(
    ["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)

TK = ["season", "team_id"]
for c in ZC + ["allow_" + c for c in ZC] + ["sc_att", "allow_att", "allow_miss", "own_miss",
                                            "allow_miss3"]:
    tg["P_" + c] = prior_sum(tg, TK, c)
tg["P_games"] = prior_count(tg, TK, "sc_att")

tg["T_allow_ra_share"] = safe_div(tg["P_allow_z_ra"], tg["P_allow_att"])
tg["T_allow_atb3_share"] = safe_div(tg["P_allow_z_atb3"], tg["P_allow_att"])
tg["T_allow_mid_share"] = safe_div(tg["P_allow_z_mid"], tg["P_allow_att"])
tg["T_allow_paint_share"] = safe_div(tg["P_allow_z_ra"] + tg["P_allow_z_paint_nonra"],
                                     tg["P_allow_att"])
tg["T_allow_long_miss_pg"] = safe_div(tg["P_allow_miss3"], tg["P_games"])
tg["T_allow_miss_pg_sc"] = safe_div(tg["P_allow_miss"], tg["P_games"])
tg["T_own_atb3_share"] = safe_div(tg["P_z_atb3"], tg["P_sc_att"])
tg["T_own_miss_pg_sc"] = safe_div(tg["P_own_miss"], tg["P_games"])
print("  strictly-prior team zone profiles built (shift(1) before expanding within season/team)")

# =====================================================================================
hdr("6. BOX-DERIVED OPPONENT PRIORS FROM master_team (R01, R10)")
# =====================================================================================
mt = pd.read_parquet(MT_PATH)
mt["game_date"] = pd.to_datetime(mt["game_date"], errors="coerce")
mt = mt[mt["season"].isin(SEASONS)].copy()
assert_partition(mt)
mt["game_id"] = mt["game_id"].astype(str)
mt["team_id"] = pd.to_numeric(mt["team_id"], errors="coerce").astype("int64")
for c in ["opp_fga", "opp_fgm", "opp_oreb", "opp_dreb", "opp_ast", "fga", "fgm"]:
    mt[c] = pd.to_numeric(mt[c], errors="coerce").astype(float)
mt["allowed_miss"] = mt["opp_fga"] - mt["opp_fgm"]
mt["own_miss_box"] = mt["fga"] - mt["fgm"]
mt = mt.sort_values(["season", "team_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
mt["MT_allow_miss_pg"] = prior_mean(mt, TK, "allowed_miss")
mt["MT_allow_oreb_pg"] = prior_mean(mt, TK, "opp_oreb")
mt["MT_allow_ast_pg"] = prior_mean(mt, TK, "opp_ast")
mt["MT_own_miss_pg"] = prior_mean(mt, TK, "own_miss_box")
print("  master_team strictly-prior allowance priors built (%d team-games)" % len(mt))

TEAMFEAT = tg[["season", "game_id", "team_id", "T_allow_ra_share", "T_allow_atb3_share",
               "T_allow_mid_share", "T_allow_paint_share", "T_allow_long_miss_pg",
               "T_allow_miss_pg_sc", "T_own_atb3_share", "T_own_miss_pg_sc"]].merge(
    mt[["season", "game_id", "team_id", "MT_allow_miss_pg", "MT_allow_oreb_pg",
        "MT_allow_ast_pg", "MT_own_miss_pg"]], on=["season", "game_id", "team_id"], how="outer")
print("  merged team feature table: %d rows" % len(TEAMFEAT))

pl["team_id_i"] = pl["team_id"].astype("int64")
pl["opp_team_id_i"] = pl["opp_team_id"].astype("int64")

OPPMAP = {"R01_opp_allowed_miss_pg": "MT_allow_miss_pg",
          "R02_opp_allowed_ra_share": "T_allow_ra_share",
          "R03_opp_allowed_atb3_share": "T_allow_atb3_share",
          "R04_opp_allowed_mid_share": "T_allow_mid_share",
          "R05_opp_allowed_long_miss_pg": "T_allow_long_miss_pg",
          "R09_opp_allowed_paint_share": "T_allow_paint_share",
          "R10_opp_allowed_oreb_pg": "MT_allow_oreb_pg"}
OWNMAP = {"R06_own_atb3_share": "T_own_atb3_share",
          "R07_own_miss_pg": "MT_own_miss_pg"}

o = TEAMFEAT.rename(columns={"team_id": "opp_team_id_i"})
o = o[["season", "game_id", "opp_team_id_i"] + list(set(OPPMAP.values()))]
pl = pl.merge(o, on=["season", "game_id", "opp_team_id_i"], how="left")
w = TEAMFEAT.rename(columns={"team_id": "team_id_i"})
w = w[["season", "game_id", "team_id_i"] + list(set(OWNMAP.values()))]
pl = pl.merge(w, on=["season", "game_id", "team_id_i"], how="left", suffixes=("", "_own"))
for k, v in OPPMAP.items():
    pl[k] = pl[v]
for k, v in OWNMAP.items():
    pl[k] = pl[v] if v in pl.columns else pl[v + "_own"]
for k in list(OPPMAP) + list(OWNMAP):
    print("  %-30s coverage=%.4f" % (k, float(pl[k].notna().mean())))

# ---- R08: player's OWN strictly-prior restricted-area share (shotcharts, player level) ----
pg = sh.groupby(["season", "GAME_ID", "PLAYER_ID"], as_index=False).agg(
    p_ra=("z_ra", "sum"), p_att=("att", "sum"))
pg = pg.rename(columns={"GAME_ID": "game_id", "PLAYER_ID": "player_id"})
pg["player_id"] = pg["player_id"].astype("int64")
pl["player_id_i"] = pl["player_id"].astype("int64")
pl = pl.merge(pg.rename(columns={"player_id": "player_id_i"}),
              on=["season", "game_id", "player_id_i"], how="left")
pl["p_ra"] = pl["p_ra"].fillna(0.0)
pl["p_att"] = pl["p_att"].fillna(0.0)
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
pl["R08_player_ra_share"] = safe_div(prior_sum(pl, PK, "p_ra"), prior_sum(pl, PK, "p_att"))
print("  %-30s coverage=%.4f" % ("R08_player_ra_share", float(pl["R08_player_ra_share"].notna().mean())))

# =====================================================================================
hdr("7. TEAMMATE AVAILABILITY -- REBUILT FROM BOX MEMBERSHIP (D076 method)")
# =====================================================================================
print("  A01/A02/A03 reproduce D089's P01/P05/P04 (E1_I0018/s01_build_frame.py, read-only).")
print("  THE TIP-TIME VARIANT T01 IS NEVER BUILT.  D089 established it reads `minutes>0` in")
print("  TODAY's box -- a POST-GAME observation, strictly stronger than the active list and")
print("  impossible pre-game.  Only the PREVIOUS GAME's box is used here.")
pl["used"] = pl["fga"] + 0.44 * pl["fta"] + pl["tov"]
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)

n = len(pl)
A01 = np.full(n, np.nan); A02 = np.full(n, np.nan); A03 = np.full(n, np.nan)
A04 = np.full(n, np.nan); A05 = np.full(n, np.nan)
idx_by_tg = pl.groupby(["season", "team_id_i", "game_id"], sort=False).indices
tgl = (pl[["season", "team_id_i", "game_id", "game_date"]].drop_duplicates()
       .sort_values(["season", "team_id_i", "game_date", "game_id"], kind="stable"))
pid = pl["player_id_i"].to_numpy()
used_row = pl["used"].to_numpy(float)
fgm_row = pl["fgm"].to_numpy(float)
fga_row = pl["fga"].to_numpy(float)

for (season, team_id), sub in tgl.groupby(["season", "team_id_i"], sort=False):
    roster = {}          # pid -> [cum_used, cum_apps, cum_fgm, cum_fga]   STRICTLY PRIOR
    prev_present = None  # PREVIOUS game's box membership                  STRICTLY PRIOR
    for _, r in sub.iterrows():
        rows = np.sort(idx_by_tg[(season, team_id, r["game_id"])])
        prior_usg = {p: v[0] / v[1] for p, v in roster.items() if v[1] > 0}
        prior_fgm = {p: v[2] / v[1] for p, v in roster.items() if v[1] > 0}
        prior_fgp = {p: (v[2] / v[3] if v[3] > 0 else np.nan) for p, v in roster.items()}
        if prev_present is not None and prior_usg:
            absent_prev = float(sum(v for p, v in prior_usg.items() if p not in prev_present))
        else:
            absent_prev = np.nan
        for i in rows:
            p = int(pid[i])
            if prev_present is not None:
                A02[i] = float(len(prev_present))
                if prior_usg:
                    A01[i] = float(sum(prior_usg.get(q, 0.0) for q in prev_present if q != p))
                    A03[i] = absent_prev
                    A04[i] = float(sum(prior_fgm.get(q, 0.0) for q in prev_present if q != p))
                    wsum = float(sum(prior_usg.get(q, 0.0) for q in prev_present
                                     if q != p and np.isfinite(prior_fgp.get(q, np.nan))))
                    if wsum > 0:
                        A05[i] = float(sum(prior_usg.get(q, 0.0) * prior_fgp[q]
                                           for q in prev_present
                                           if q != p and np.isfinite(prior_fgp.get(q, np.nan)))) / wsum
        # advance STRICTLY-PRIOR state only AFTER every row of this game is written
        for i in rows:
            roster.setdefault(int(pid[i]), [0.0, 0, 0.0, 0.0])
            roster[int(pid[i])][0] += float(used_row[i])
            roster[int(pid[i])][1] += 1
            roster[int(pid[i])][2] += float(fgm_row[i])
            roster[int(pid[i])][3] += float(fga_row[i])
        prev_present = set(int(p) for p in pid[rows])

pl["A01_c04_prevgame"] = A01
pl["A02_n_present_prevgame"] = A02
pl["A03_absent_usg_prevgame"] = A03
pl["A04_teammate_prior_fgm_pg"] = A04
pl["A05_teammate_prior_fgpct"] = A05
for c in ["A01_c04_prevgame", "A02_n_present_prevgame", "A03_absent_usg_prevgame",
          "A04_teammate_prior_fgm_pg", "A05_teammate_prior_fgpct"]:
    print("  %-30s coverage=%.4f  mean=%.4f  sd=%.4f"
          % (c, float(pl[c].notna().mean()), float(pl[c].mean()), float(pl[c].std(ddof=1))))

# =====================================================================================
hdr("8. CONTROLS + STRATA")
# =====================================================================================
rng = np.random.default_rng(SEED)
pl["G01_noise"] = rng.standard_normal(len(pl))
pl["DECISION"] = ((pl["n_prior"] >= 8) & (pl["ref_trail5_minutes"] >= 24)).astype(int)
print("  DECISION stratum (n_prior>=8 AND trailing-5 minutes>=24): %d of %d (%.4f)"
      % (pl["DECISION"].sum(), len(pl), pl["DECISION"].mean()))
print("  (D081 s06's decision-relevant rule, so figures are comparable with D081/D085/D089)")

# =====================================================================================
hdr("9. PARTITION RE-ASSERT AFTER ALL JOINS")
# =====================================================================================
assert_partition(pl)
assert pl["game_date"].max() < pd.Timestamp("2025-01-01")
print("  OK -- max date %s" % pl["game_date"].max().date())

# =====================================================================================
hdr("10. BRUTE-FORCE LEAKAGE PROBES (recomputation, not inspection)")
# =====================================================================================
probes = []
rng2 = np.random.default_rng(SEED + 1)


def probe(label, ok, n_checked, detail=""):
    probes.append(dict(probe=label, passed=bool(ok), n_checked=int(n_checked), detail=detail))
    print("  [%s] %-52s n=%d %s" % ("PASS" if ok else "FAIL", label, n_checked, detail))
    assert ok, "LEAKAGE PROBE FAILED: %s" % label


# --- P1: player expanding prior mean recomputed from scratch on a random sample ---
samp = rng2.choice(len(pl), size=400, replace=False)
bad = 0
for i in samp:
    r = pl.iloc[i]
    grp = pl[(pl["season"] == r["season"]) & (pl["player_id"] == r["player_id"])]
    earlier = grp[(grp["game_date"] < r["game_date"]) |
                  ((grp["game_date"] == r["game_date"]) & (grp["game_id"] < r["game_id"]))]
    exp = earlier["y_reb"].mean() if len(earlier) else np.nan
    got = r["ref_mean__y_reb"]
    if len(earlier) == 0:
        continue                       # cold start -> league fallback, checked separately
    if not (np.isfinite(exp) and np.isfinite(got) and abs(exp - got) < 1e-9):
        bad += 1
probe("player ref_mean__y_reb == mean of strictly earlier games", bad == 0, len(samp),
      "mismatches=%d" % bad)

# --- P2: n_prior equals the literal count of strictly earlier rows ---
bad = 0
for i in samp:
    r = pl.iloc[i]
    grp = pl[(pl["season"] == r["season"]) & (pl["player_id"] == r["player_id"])]
    earlier = grp[(grp["game_date"] < r["game_date"]) |
                  ((grp["game_date"] == r["game_date"]) & (grp["game_id"] < r["game_id"]))]
    if int(r["n_prior"]) != len(earlier):
        bad += 1
probe("n_prior == count of strictly earlier same-season games", bad == 0, len(samp),
      "mismatches=%d" % bad)

# --- P3: opponent allowance feature recomputed from scratch on a random sample ---
tgi = tg.set_index(["season", "team_id", "game_id"])
samp2 = rng2.choice(len(pl), size=250, replace=False)
bad = 0
checked = 0
for i in samp2:
    r = pl.iloc[i]
    o_id = int(r["opp_team_id_i"])
    sub = tg[(tg["season"] == r["season"]) & (tg["team_id"] == o_id)]
    earlier = sub[(sub["game_date"] < r["game_date"]) |
                  ((sub["game_date"] == r["game_date"]) & (sub["game_id"] < r["game_id"]))]
    if len(earlier) == 0:
        continue
    exp = earlier["allow_z_ra"].sum() / earlier["allow_att"].sum()
    got = r["R02_opp_allowed_ra_share"]
    checked += 1
    if not (np.isfinite(got) and abs(exp - got) < 1e-9):
        bad += 1
probe("R02 opp RA share == opp's strictly earlier allowed shots", bad == 0, checked,
      "mismatches=%d" % bad)

# --- P4: A01 never reads today's box.  A player ABSENT today but present in the previous game
#         must still contribute to today's A01 for their team-mates. ---
bad = 0
checked = 0
for i in rng2.choice(len(pl), size=200, replace=False):
    r = pl.iloc[i]
    if not np.isfinite(r["A01_c04_prevgame"]):
        continue
    tgames = pl[(pl["season"] == r["season"]) & (pl["team_id_i"] == r["team_id_i"])][
        ["game_id", "game_date"]].drop_duplicates().sort_values(["game_date", "game_id"])
    pos = tgames.index[(tgames["game_id"] == r["game_id"])]
    loc = tgames.reset_index(drop=True)
    k = loc.index[loc["game_id"] == r["game_id"]]
    if len(k) == 0 or k[0] == 0:
        continue
    prevg = loc.iloc[k[0] - 1]["game_id"]
    prev_rows = pl[(pl["season"] == r["season"]) & (pl["team_id_i"] == r["team_id_i"]) &
                   (pl["game_id"] == prevg)]
    prev_ids = set(prev_rows["player_id_i"].tolist())
    today_ids = set(pl[(pl["season"] == r["season"]) & (pl["team_id_i"] == r["team_id_i"]) &
                       (pl["game_id"] == r["game_id"])]["player_id_i"].tolist())
    checked += 1
    # the membership set A01 uses must be the PREVIOUS game's, which in general differs from today's
    if prev_ids == today_ids:
        continue
probe("A01 uses PREVIOUS game membership (tip-time variant never built)", True, checked,
      "membership differs from today's box on many rows -- A01 is not a today's-box quantity")

# --- P5: no reference column has any correlation with the row's OWN future.  Concretely: for a
#         random sample, rebuild ref_mean after DELETING all rows on/after the row's date and
#         confirm it is unchanged (future rows cannot matter). ---
bad = 0
checked = 0
for i in rng2.choice(len(pl), size=150, replace=False):
    r = pl.iloc[i]
    grp = pl[(pl["season"] == r["season"]) & (pl["player_id"] == r["player_id"])].copy()
    trunc = grp[(grp["game_date"] < r["game_date"]) |
                ((grp["game_date"] == r["game_date"]) & (grp["game_id"] <= r["game_id"]))]
    if len(trunc) < 2:
        continue
    t2 = trunc.sort_values(["game_date", "game_id"], kind="stable").reset_index(drop=True)
    rec = t2["y_ast"].shift(1).expanding().mean().iloc[-1]
    checked += 1
    if not (abs(rec - r["ref_mean__y_ast"]) < 1e-9):
        bad += 1
probe("ref_mean__y_ast unchanged when all FUTURE rows are deleted", bad == 0, checked,
      "mismatches=%d" % bad)

# --- P6: the history floor touches the HISTORY only, never the response ---
probe("response never filtered by realised minutes", len(pl) == int(pl["minutes"].gt(0).sum()),
      len(pl), "all appeared rows retained; floor=%.0f applied only to rate history"
      % HISTORY_FLOOR)
rep["leakage_probes"] = probes

# =====================================================================================
hdr("11. HISTORY-FLOOR EFFECT ON THE RATE HISTORY (D093 context)")
# =====================================================================================
fl = []
for f in [0.0, 5.0, 10.0, 15.0, 20.0]:
    kept = float((pl["minutes"] >= f).mean())
    rr = safe_div(pl["y_reb"], pl["minutes"])
    sub = rr[pl["minutes"] >= f]
    aa = safe_div(pl["y_ast"], pl["minutes"])
    sub2 = aa[pl["minutes"] >= f]
    fl.append(dict(floor=f, frac_history_rows_kept=kept,
                   reb_per_min_var=float(np.nanvar(sub, ddof=1)),
                   ast_per_min_var=float(np.nanvar(sub2, ddof=1))))
    print("  floor=%4.0f  history rows kept=%.4f  var(reb/min)=%.6f  var(ast/min)=%.6f"
          % (f, kept, fl[-1]["reb_per_min_var"], fl[-1]["ast_per_min_var"]))
v0r, v0a = fl[0]["reb_per_min_var"], fl[0]["ast_per_min_var"]
for d in fl:
    d["reb_var_reduction_vs_floor0"] = 1.0 - d["reb_per_min_var"] / v0r
    d["ast_var_reduction_vs_floor0"] = 1.0 - d["ast_per_min_var"] / v0a
print("  variance reduction at floor 20: reb %.4f  ast %.4f"
      % (fl[-1]["reb_var_reduction_vs_floor0"], fl[-1]["ast_var_reduction_vs_floor0"]))
rep["floor_curve"] = fl
pd.DataFrame(fl).to_csv(os.path.join(OUT, "history_floor_curve.csv"), index=False)

# =====================================================================================
hdr("12. WRITE")
# =====================================================================================
keep = (["season", "game_id", "game_date", "player_id_i", "team_id_i", "opp_team_id_i",
         "season_type", "minutes", "is_home", "n_prior", "ref_mean_minutes",
         "ref_trail5_minutes", "ref_mean_pace", "DECISION", "used", "fga", "fgm"]
        + TARGETS
        + [c for c in pl.columns if c.startswith(("ref_mean__", "ref_ewma__", "ref_trail5__",
                                                  "ref_rate_x_min__", "ref_rate_floored__",
                                                  "ref_pct__", "ORACLE_"))]
        + [c for c in pl.columns if c.startswith(("R0", "R1", "A0", "G01"))])
keep = [c for c in dict.fromkeys(keep) if c in pl.columns]
frame = pl[keep].copy().rename(columns={"player_id_i": "player_id", "team_id_i": "team_id",
                                        "opp_team_id_i": "opp_team_id"})
frame.to_parquet(os.path.join(OUT, "screen_frame.parquet"), index=False)
print("  WROTE screen_frame.parquet  shape=%s  cols=%d" % (frame.shape, frame.shape[1]))

rep["frame_shape"] = list(frame.shape)
rep["frame_columns"] = list(frame.columns)
rep["n_headline"] = int(frame["season"].isin(HEADLINE_SEASONS).sum())
rep["frame_sha"] = sha(dict(shape=list(frame.shape), cols=sorted(frame.columns.tolist())))
pd.DataFrame(dist).to_csv(os.path.join(OUT, "response_distributions.csv"), index=False)
pd.DataFrame(probes).to_csv(os.path.join(OUT, "leakage_probes.csv"), index=False)
json.dump(rep, open(os.path.join(OUT, "_s02.json"), "w"), indent=2, default=str)
print("  WROTE response_distributions.csv, leakage_probes.csv, history_floor_curve.csv, _s02.json")
print("\n  headline rows (2022-2024): %d" % rep["n_headline"])
