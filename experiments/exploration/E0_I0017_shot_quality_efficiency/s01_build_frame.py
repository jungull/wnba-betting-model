"""
E0_I0017 S01 -- build the screen frame.

ORDER OF OPERATIONS, DELIBERATELY:
    manifest check -> load -> partition assert -> build REALISED per-game aggregates (intermediate
    only) -> convert to STRICTLY-PRIOR forecasts -> partition assert again -> leakage probes ->
    first-appearance NaN assertion -> save.

NOTHING here reads the current game or any later game.  There are ZERO tip-time exceptions in this
screen: every candidate is a function of games strictly before the row's own game_date.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sq_base import (  # noqa: E402
    ROOT, OUT, SHOTDIR, PBPDIR, MP_PATH, sk, SEED, SEASONS, MIN_PRIOR_APPEARANCES, TRAIL,
    CANDIDATES, CANDIDATES_SHA256, ZONES, CATCH_ACTIONS_PREFIX, CATCH_ACTIONS_EXACT,
    SELFCREATE_PREFIX, INTERACTION_MAINS, hdr, safe_div, prior_sum_many, trail_sum_many,
    league_prior_mean, BaseFit,
)

pd.set_option("display.width", 220)
rng = np.random.default_rng(SEED)
info = {"candidates_sha256": CANDIDATES_SHA256, "n_candidates_preselected": len(CANDIDATES)}

# =====================================================================================
hdr("0. INPUT MANIFEST VERDICTS -- recorded verbatim, never papered over")
# =====================================================================================
manifests = {}
for lbl, p in [("master_player", MP_PATH),
               ("shots_2023_regular", os.path.join(SHOTDIR, "shots_2023_regular.parquet")),
               ("pbp_1022300001", os.path.join(PBPDIR, "pbp_1022300001.parquet"))]:
    mv = sk.check_manifest(p, verbose=True)
    manifests[lbl] = {k: str(v) for k, v in mv.items()}
info["manifests"] = manifests
print("  data/shotcharts/* and data/playbyplay/* remain UNVERIFIABLE by manifest.")
print("  s00 established VERDICT=ROW on column VALUES; see NOTES.md Step 0.")

# =====================================================================================
hdr("1. LOAD master_player, FILTER TO PARTITION ON VALUES")
# =====================================================================================
mp = pd.read_parquet(MP_PATH)
print("  raw master_player: %d rows" % len(mp))
mp = mp[mp["season"].isin(SEASONS)].copy()
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp["game_id"] = mp["game_id"].astype(str)
mp["player_id"] = mp["player_id"].astype("int64")
mp["team_id"] = mp["team_id"].astype("int64")
mp["opp_team_id"] = mp["opp_team_id"].astype("int64")
sk.assert_partition(mp, verbose=True)
assert mp["game_date"].max() < pd.Timestamp("2025-01-01"), "partition breach"
print("  partition rows=%d games=%d players=%d" % (len(mp), mp["game_id"].nunique(),
                                                   mp["player_id"].nunique()))

for c in ["minutes", "fga", "fgm", "fg3m", "fg3a", "fta", "ftm", "pts", "ast"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce")

# appearances only
pl = mp[(mp["minutes"] > 0) & mp["pts"].notna()].copy()
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  appearances (minutes>0): %d" % len(pl))

PK = ["season", "player_id"]
TK = ["season", "team_id"]
OK = ["season", "opp_team_id"]
pl["n_prior"] = pl.groupby(PK, sort=False)["game_id"].transform(lambda x: np.arange(len(x)))

# =====================================================================================
hdr("2. LOAD SHOT EVENTS (2021-2024 regular + playoffs ONLY)")
# =====================================================================================
shot_files = []
for s in SEASONS:
    for st in ("regular", "playoffs"):
        p = os.path.join(SHOTDIR, "shots_%d_%s.parquet" % (s, st))
        if os.path.exists(p):
            shot_files.append((s, st, p))
print("  files opened: %d  (2025/2026 and league_avg_* NEVER opened)" % len(shot_files))
frames = []
for s, st, p in shot_files:
    d = pd.read_parquet(p)
    d["season"] = s
    frames.append(d)
sh = pd.concat(frames, ignore_index=True)
sh["game_date"] = pd.to_datetime(sh["GAME_DATE"], format="%Y%m%d", errors="coerce")
sh["game_id"] = sh["GAME_ID"].astype(str)
sh["player_id"] = sh["PLAYER_ID"].astype("int64")
sh["team_id"] = sh["TEAM_ID"].astype("int64")
sk.assert_partition(sh, verbose=True)
assert sh["game_date"].max() < pd.Timestamp("2025-01-01"), "partition breach"
print("  shot events: %d  games=%d" % (len(sh), sh["game_id"].nunique()))

# =====================================================================================
hdr("3. LOAD PLAY-BY-PLAY ASSIST FLAGS (2021-2024 regular only; 2025 files NEVER opened)")
# =====================================================================================
allowed_prefix = tuple("102%d" % (s % 100) for s in SEASONS)   # 10221,10222,10223,10224
pbp_files = []
for f in sorted(glob.glob(os.path.join(PBPDIR, "*.parquet"))):
    gid = os.path.basename(f)[4:-8]
    if gid[:5] in allowed_prefix:
        pbp_files.append(f)
print("  pbp files in partition: %d  (skipped %d outside)"
      % (len(pbp_files), len(glob.glob(os.path.join(PBPDIR, "*.parquet"))) - len(pbp_files)))
COLS = ["GAME_ID", "EVENTNUM", "EVENTMSGTYPE", "PLAYER1_ID", "PLAYER2_ID"]
pparts = []
for f in pbp_files:
    d = pd.read_parquet(f, columns=COLS)
    d = d[d["EVENTMSGTYPE"] == 1]
    pparts.append(d)
pbp = pd.concat(pparts, ignore_index=True)
pbp["game_id"] = pbp["GAME_ID"].astype(str)
pbp["_assisted"] = (pd.to_numeric(pbp["PLAYER2_ID"], errors="coerce").fillna(0) != 0).astype(float)
print("  made-FG pbp events: %d  assisted: %.4f" % (len(pbp), pbp["_assisted"].mean()))
# join on event identity: (GAME_ID, GAME_EVENT_ID) == (GAME_ID, EVENTNUM).  Within-row join.
pbp_k = pbp[["game_id", "EVENTNUM", "_assisted"]].rename(columns={"EVENTNUM": "GAME_EVENT_ID"})
pbp_k = pbp_k.drop_duplicates(subset=["game_id", "GAME_EVENT_ID"])
sh = sh.merge(pbp_k, on=["game_id", "GAME_EVENT_ID"], how="left")
made = sh["SHOT_MADE_FLAG"] == 1
print("  made shots matched to a pbp assist record: %.4f"
      % float(sh.loc[made, "_assisted"].notna().mean()))
info["pbp_assist_match_rate_on_made_shots"] = float(sh.loc[made, "_assisted"].notna().mean())

# =====================================================================================
hdr("4. REALISED per-shot indicators -> per-player-game COUNTS  (INTERMEDIATE ONLY)")
# =====================================================================================
# Every column built here is measured FROM the game itself.  NONE of them is ever used as a
# feature.  They exist only to be shifted into a strictly-prior forecast in section 6.
sh["_att"] = 1.0
sh["_dist"] = sh["SHOT_DISTANCE"].astype(float)
sh["_lt5"] = (sh["SHOT_DISTANCE"].astype(float) < 5).astype(float)
sh["_is3"] = (sh["SHOT_TYPE"] == "3PT Field Goal").astype(float)
sh["_made"] = sh["SHOT_MADE_FLAG"].astype(float)
sh["_made3"] = sh["_made"] * sh["_is3"]
sh["_efgnum"] = sh["_made"] + 0.5 * sh["_made3"]
sh["_pts"] = sh["_made"] * (2.0 + sh["_is3"])
at = sh["ACTION_TYPE"].astype(str)
sh["_catch"] = (at.str.startswith(CATCH_ACTIONS_PREFIX) | at.isin(CATCH_ACTIONS_EXACT)).astype(float)
sh["_self"] = at.str.startswith(SELFCREATE_PREFIX).astype(float)
sh["_layup"] = at.str.contains("Layup|Dunk|Finger Roll", regex=True).astype(float)
sh["_plainjs"] = (at == "Jump Shot").astype(float)
for z in ZONES:
    sh["_z_" + z.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "")] = \
        (sh["SHOT_ZONE_BASIC"] == z).astype(float)
ZCOLS = [c for c in sh.columns if c.startswith("_z_")]
sh["_asst"] = sh["_assisted"].fillna(0.0) * sh["_made"]                 # assisted MAKES
sh["_asst_den"] = sh["_made"] * sh["_assisted"].notna().astype(float)   # makes WITH a pbp record
sh["_asst3"] = sh["_asst"] * sh["_is3"]
sh["_asst3_den"] = sh["_asst_den"] * sh["_is3"]
sh["_asst2"] = sh["_asst"] * (1 - sh["_is3"])
sh["_asst2_den"] = sh["_asst_den"] * (1 - sh["_is3"])
sh["_distsum"] = sh["_dist"]

# ---- ACTION_TYPE one-hot (family D03) --------------------------------------------------------
act_levels = sorted(sh["ACTION_TYPE"].astype(str).unique())
print("  distinct ACTION_TYPE labels: %d" % len(act_levels))
ACOLS = []
for i, a in enumerate(act_levels):
    c = "_a%02d" % i
    sh[c] = (at == a).astype(float)
    ACOLS.append(c)

COUNTCOLS = (["_att", "_distsum", "_lt5", "_is3", "_made", "_made3", "_efgnum", "_pts",
              "_catch", "_self", "_layup", "_plainjs", "_asst", "_asst_den", "_asst3",
              "_asst3_den", "_asst2", "_asst2_den"] + ZCOLS + ACOLS)

pg = sh.groupby(["season", "game_id", "player_id", "team_id"], sort=False)[COUNTCOLS].sum().reset_index()
print("  realised player-game shot rows: %d" % len(pg))

# =====================================================================================
hdr("5. LEAGUE PRIOR ZONE / ACTION RATES  (strictly earlier dates in the SAME season)")
# =====================================================================================
# For each (season, zone) accumulate attempts, eFG numerator and points over GAME DATES, then
# .shift(1) at the DATE level so a row's league rate uses only games on strictly earlier dates.
def league_prior_rate(sh, keycol, levels, out_prefix):
    g = sh.groupby(["season", "game_date", keycol], sort=True)[["_att", "_efgnum", "_pts"]].sum().reset_index()
    piv_att = g.pivot_table(index=["season", "game_date"], columns=keycol, values="_att",
                            aggfunc="sum", fill_value=0.0).sort_index()
    piv_num = g.pivot_table(index=["season", "game_date"], columns=keycol, values="_efgnum",
                            aggfunc="sum", fill_value=0.0).sort_index()
    piv_pts = g.pivot_table(index=["season", "game_date"], columns=keycol, values="_pts",
                            aggfunc="sum", fill_value=0.0).sort_index()
    for p in (piv_att, piv_num, piv_pts):
        for lv in levels:
            if lv not in p.columns:
                p[lv] = 0.0
    piv_att, piv_num, piv_pts = (p[levels] for p in (piv_att, piv_num, piv_pts))
    # cumulative over strictly earlier dates, within season
    ca = piv_att.groupby(level=0).transform(lambda x: x.shift(1).expanding().sum())
    cn = piv_num.groupby(level=0).transform(lambda x: x.shift(1).expanding().sum())
    cp = piv_pts.groupby(level=0).transform(lambda x: x.shift(1).expanding().sum())
    efg = cn / ca.replace(0.0, np.nan)
    pps = cp / ca.replace(0.0, np.nan)
    # season-to-date overall league rate as the cold-start fill for a zone not yet attempted
    tot_a = ca.sum(axis=1); tot_n = cn.sum(axis=1); tot_p = cp.sum(axis=1)
    efg = efg.apply(lambda col: col.fillna(tot_n / tot_a.replace(0.0, np.nan)))
    pps = pps.apply(lambda col: col.fillna(tot_p / tot_a.replace(0.0, np.nan)))
    efg.columns = ["%s_efg_%s" % (out_prefix, str(c)) for c in efg.columns]
    pps.columns = ["%s_pps_%s" % (out_prefix, str(c)) for c in pps.columns]
    return efg.reset_index(), pps.reset_index()

lg_z_efg, lg_z_pps = league_prior_rate(sh, "SHOT_ZONE_BASIC", ZONES, "lgz")
lg_a_efg, lg_a_pps = league_prior_rate(sh, "ACTION_TYPE", act_levels, "lga")
print("  league prior zone table: %d (season, date) rows" % len(lg_z_efg))
print("  first-date NaN check (must be all-NaN on each season's first date):")
_fd = lg_z_efg.groupby("season").head(1)
print("    %s" % _fd.set_index(["season", "game_date"]).isna().all(axis=1).to_dict())

# =====================================================================================
hdr("6. ATTACH TO PLAYER-GAME ROWS AND CONVERT TO STRICTLY-PRIOR FORECASTS")
# =====================================================================================
pl = pl.merge(pg.drop(columns=["team_id"]), on=["season", "game_id", "player_id"], how="left")
for c in COUNTCOLS:
    pl[c] = pl[c].fillna(0.0)
print("  player-game rows with >=1 shot event: %d of %d"
      % (int((pl["_att"] > 0).sum()), len(pl)))

pl = pl.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
P = prior_sum_many(pl, PK, COUNTCOLS)        # strictly-prior expanding sums, per player-season
T5 = trail_sum_many(pl, PK, COUNTCOLS, TRAIL)  # strictly-prior trailing-5 sums

# ---- FAMILY A -------------------------------------------------------------------------------
pl["A01_dist_mean"] = safe_div(P["_distsum"], P["_att"])
pl["A02_share_lt5ft"] = safe_div(P["_lt5"], P["_att"])
zc = {z: "_z_" + z.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "") for z in ZONES}
pl["A03_share_restricted"] = safe_div(P[zc["Restricted Area"]], P["_att"])
pl["A04_share_paint"] = safe_div(P[zc["Restricted Area"]] + P[zc["In The Paint (Non-RA)"]], P["_att"])
pl["A05_share_midrange"] = safe_div(P[zc["Mid-Range"]], P["_att"])
pl["A06_share_corner3"] = safe_div(P[zc["Left Corner 3"]] + P[zc["Right Corner 3"]], P["_att"])
pl["A07_share_abovebreak3"] = safe_div(P[zc["Above the Break 3"]], P["_att"])
pl["A08_share_3pa"] = safe_div(P["_is3"], P["_att"])
pl["A09_share_catch_action"] = safe_div(P["_catch"], P["_att"])
pl["A10_share_selfcreate_action"] = safe_div(P["_self"], P["_att"])
pl["A11_share_layup_action"] = safe_div(P["_layup"], P["_att"])
pl["A12_share_plain_jumpshot"] = safe_div(P["_plainjs"], P["_att"])

# ---- FAMILY B -------------------------------------------------------------------------------
pl["B01_dist_t5"] = safe_div(T5["_distsum"], T5["_att"])
pl["B02_lt5ft_t5"] = safe_div(T5["_lt5"], T5["_att"])
pl["B03_restricted_t5"] = safe_div(T5[zc["Restricted Area"]], T5["_att"])
pl["B04_dist_trend"] = pl["B01_dist_t5"] - pl["A01_dist_mean"]
pl["B05_lt5ft_trend"] = pl["B02_lt5ft_t5"] - pl["A02_share_lt5ft"]
pl["B06_3pa_trend"] = safe_div(T5["_is3"], T5["_att"]) - pl["A08_share_3pa"]

# ---- FAMILY C -------------------------------------------------------------------------------
pl["C01_assisted_share"] = safe_div(P["_asst"], P["_asst_den"])
pl["C02_assisted_share_3pt"] = safe_div(P["_asst3"], P["_asst3_den"])
pl["C03_assisted_share_2pt"] = safe_div(P["_asst2"], P["_asst2_den"])
pl["C04_assisted_share_t5"] = safe_div(T5["_asst"], T5["_asst_den"])
pl["C05_assisted_trend"] = pl["C04_assisted_share_t5"] - pl["C01_assisted_share"]

# ---- FAMILY D: shot-quality index = prior mix x STRICTLY PRIOR league rates -------------------
pl = pl.merge(lg_z_efg, on=["season", "game_date"], how="left")
pl = pl.merge(lg_z_pps, on=["season", "game_date"], how="left")
pl = pl.merge(lg_a_efg, on=["season", "game_date"], how="left")
xefg = np.zeros(len(pl)); xpps = np.zeros(len(pl))
for z in ZONES:
    share = safe_div(P[zc[z]], P["_att"])
    xefg += np.nan_to_num(share, nan=0.0) * np.nan_to_num(pl["lgz_efg_%s" % z].to_numpy(float), nan=0.0)
    xpps += np.nan_to_num(share, nan=0.0) * np.nan_to_num(pl["lgz_pps_%s" % z].to_numpy(float), nan=0.0)
novalid = ~np.isfinite(safe_div(P["_att"], P["_att"]))
pl["D01_xefg_zone"] = np.where(novalid, np.nan, xefg)
pl["D02_xpps_zone"] = np.where(novalid, np.nan, xpps)
xefga = np.zeros(len(pl))
for i, a in enumerate(act_levels):
    share = safe_div(P["_a%02d" % i], P["_att"])
    xefga += np.nan_to_num(share, nan=0.0) * np.nan_to_num(pl["lga_efg_%s" % a].to_numpy(float), nan=0.0)
pl["D03_xefg_action"] = np.where(novalid, np.nan, xefga)

# =====================================================================================
hdr("7. OPPONENT SHOT QUALITY CONCEDED  (family E)")
# =====================================================================================
# team-game ALLOWED counts = the shots the OTHER team took in that game.
tg_taken = sh.groupby(["season", "game_id", "team_id"], sort=False)[COUNTCOLS].sum().reset_index()
g_tot = sh.groupby(["season", "game_id"], sort=False)[COUNTCOLS].sum().reset_index()
tg = tg_taken.merge(g_tot, on=["season", "game_id"], suffixes=("_tk", "_tot"))
for c in COUNTCOLS:
    tg[c] = tg[c + "_tot"] - tg[c + "_tk"]           # ALLOWED
tg = tg[["season", "game_id", "team_id"] + COUNTCOLS]
dates = pl[["season", "game_id", "game_date"]].drop_duplicates()
tg = tg.merge(dates, on=["season", "game_id"], how="left")
tg = tg.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
TP = prior_sum_many(tg, ["season", "team_id"], COUNTCOLS)
tg["E01_opp_dist_conceded"] = safe_div(TP["_distsum"], TP["_att"])
tg["E02_opp_lt5ft_conceded"] = safe_div(TP["_lt5"], TP["_att"])
tg["E03_opp_restricted_conceded"] = safe_div(TP[zc["Restricted Area"]], TP["_att"])
tg["E05_opp_3pa_conceded"] = safe_div(TP["_is3"], TP["_att"])
tg["E06_opp_assisted_conceded"] = safe_div(TP["_asst"], TP["_asst_den"])
tg = tg.merge(lg_z_efg, on=["season", "game_date"], how="left")
xo = np.zeros(len(tg))
for z in ZONES:
    share = safe_div(TP[zc[z]], TP["_att"])
    xo += np.nan_to_num(share, nan=0.0) * np.nan_to_num(tg["lgz_efg_%s" % z].to_numpy(float), nan=0.0)
tg["E04_opp_xefg_conceded"] = np.where(~np.isfinite(safe_div(TP["_att"], TP["_att"])), np.nan, xo)
ECOLS = ["E01_opp_dist_conceded", "E02_opp_lt5ft_conceded", "E03_opp_restricted_conceded",
         "E04_opp_xefg_conceded", "E05_opp_3pa_conceded", "E06_opp_assisted_conceded"]
opp = tg[["season", "game_id", "team_id"] + ECOLS].rename(columns={"team_id": "opp_team_id"})
pl = pl.merge(opp, on=["season", "game_id", "opp_team_id"], how="left")
print("  rows with a finite opponent-conceded prior: %d of %d"
      % (int(pl["E04_opp_xefg_conceded"].notna().sum()), len(pl)))

# =====================================================================================
hdr("8. OUTCOMES + STRICTLY-PRIOR REFERENCES  (identical construction to D085)")
# =====================================================================================
pl["y_ppm"] = safe_div(pl["pts"], pl["minutes"])
pl["y_ts"] = safe_div(pl["pts"], 2.0 * (pl["fga"] + 0.44 * pl["fta"]))
pl["y_efg"] = safe_div(pl["fgm"] + 0.5 * pl["fg3m"], pl["fga"])

QS = prior_sum_many(pl, PK, ["pts", "minutes", "fga", "fta", "fgm", "fg3m"])
RATE_SPEC = {
    "ppm": (QS["pts"], QS["minutes"]),
    "ts": (QS["pts"], 2.0 * (QS["fga"] + 0.44 * QS["fta"])),
    "efg": (QS["fgm"] + 0.5 * QS["fg3m"], QS["fga"]),
}
ref_fallback = {}
for rt, (num, den) in RATE_SPEC.items():
    ycol = "y_" + rt
    b = pd.Series(safe_div(num, den), index=pl.index)
    a = pl.groupby(PK, sort=False)[ycol].transform(lambda x: x.shift(1).expanding().mean())
    lg = league_prior_mean(pl, "season", "game_date", ycol)
    pl["refB_" + rt] = b.fillna(lg)
    pl["refA_" + rt] = a.fillna(lg)
    ref_fallback[rt] = {"n_from_player_prior": int(b.notna().sum()),
                        "n_from_league_prior": int((b.isna() & lg.notna()).sum()),
                        "n_still_nan": int(pl["refB_" + rt].isna().sum())}
print("  reference fallback accounting: %s" % json.dumps(ref_fallback, indent=2))
info["ref_fallback"] = ref_fallback

# ---- D04 and family F and G, which need the reference / each other ----------------------------
pl["D04_xefg_minus_own"] = pl["D01_xefg_zone"] - pl["refB_efg"]
pl["F01_dist_x_oppdist"] = pl["A01_dist_mean"] * pl["E01_opp_dist_conceded"]
pl["F02_lt5ft_x_opplt5ft"] = pl["A02_share_lt5ft"] * pl["E02_opp_lt5ft_conceded"]
pl["F03_xefg_x_oppxefg"] = pl["D01_xefg_zone"] * pl["E04_opp_xefg_conceded"]
pl["F04_3pa_x_opp3pa"] = pl["A08_share_3pa"] * pl["E05_opp_3pa_conceded"]
pl["G01_noise"] = rng.standard_normal(len(pl))
pl["G02_ref_echo"] = pl["refB_ppm"]           # per-outcome echo is re-pointed in s02

# =====================================================================================
hdr("9. SCREEN FRAME: Regular Season, >= %d prior appearances" % MIN_PRIOR_APPEARANCES)
# =====================================================================================
f = pl[(pl["season_type"] == "Regular Season") & (pl["n_prior"] >= MIN_PRIOR_APPEARANCES)].copy()
f = f[f["fga"] >= 1].reset_index(drop=True)
print("  screen frame: %d rows, %d players, %d games, seasons %s"
      % (len(f), f["player_id"].nunique(), f["game_id"].nunique(), sorted(f["season"].unique())))
sk.assert_partition(f, verbose=True)
assert f["game_date"].max() < pd.Timestamp("2025-01-01"), "partition breach"
assert set(f["season"].unique()) <= set(SEASONS)
info["frame"] = {"n_rows": int(len(f)), "n_players": int(f["player_id"].nunique()),
                 "n_games": int(f["game_id"].nunique()),
                 "seasons": sorted(int(s) for s in f["season"].unique())}

# =====================================================================================
hdr("10. FIRST-APPEARANCE NaN ASSERTION -- proof by construction that nothing reads its own game")
# =====================================================================================
# On a player's FIRST appearance of a season there are no prior games, so every player-entity
# candidate MUST be NaN.  A candidate that is finite there is reading the current game.
first = pl[pl["n_prior"] == 0]
fa = {}
viol = []
#
# EXEMPTIONS, both declared rather than silently skipped:
#   G01_noise      -- a seeded draw, unrelated to any game, finite everywhere by design.
#   G02_ref_echo   -- IS the reference refB_ppm.  refB falls back to the strictly-earlier-in-season
#                     LEAGUE mean on a player's cold start, so it is legitimately finite on a
#                     player's first appearance (630 rows).  That fallback reads other players'
#                     earlier games, never this player's current game.  It is probed directly in
#                     section 11 (refB_vs_refA) rather than by this construction check, and its
#                     same-day granularity is disclosed in NOTES.md.
for c in CANDIDATES:
    if c in ("G01_noise", "G02_ref_echo"):
        continue
    ent = "player" if c[0] in "ABCD" else ("opp" if c[0] == "E" else "inter")
    n_fin = int(np.isfinite(pd.to_numeric(first[c], errors="coerce")).sum())
    fa[c] = {"entity": ent, "n_finite_on_player_first_appearance": n_fin,
             "n_rows_checked": int(len(first))}
    if ent in ("player", "inter") and n_fin > 0:
        viol.append(c)
print("  player-entity candidates finite on a player's first appearance (must be 0):")
for c in CANDIDATES:
    if c in fa and fa[c]["entity"] in ("player", "inter"):
        print("    %-32s %d" % (c, fa[c]["n_finite_on_player_first_appearance"]))
print("  (family E is an OPPONENT prior and is legitimately finite on a player's first game --")
print("   it is NaN on the OPPONENT's first game of the season, checked separately below)")
oppfirst_viol = []
_tgf = tg.groupby(["season", "team_id"], sort=False).head(1)
for c in ECOLS:
    n_fin = int(np.isfinite(pd.to_numeric(_tgf[c], errors="coerce")).sum())
    fa[c] = {"entity": "opp", "n_finite_on_opp_first_game": n_fin, "n_rows_checked": int(len(_tgf))}
    print("    %-32s finite on opponent's FIRST game of season: %d (must be 0)" % (c, n_fin))
    if n_fin > 0:
        oppfirst_viol.append(c)
info["first_appearance_assertion"] = fa
assert not viol, "CANDIDATE READS ITS OWN GAME: %s" % viol
assert not oppfirst_viol, "OPPONENT CANDIDATE READS ITS OWN GAME: %s" % oppfirst_viol
print("  ALL PASS -- no candidate is finite before it has any prior data.")

# =====================================================================================
hdr("11. LEAKAGE PROBES (trap 2).  Names lie in BOTH directions -- probe, do not trust labels.")
# =====================================================================================
probes = {}
f["_LEAKY_control_ppm"] = f.groupby(PK, sort=False)["y_ppm"].transform("mean")   # full-season mean
for suspect, clean, label in [("refB_ppm", "refA_ppm", "refB_vs_refA"),
                              ("_LEAKY_control_ppm", "refB_ppm", "POSITIVE_CONTROL_leaky_vs_refB")]:
    d = f[np.isfinite(f[suspect]) & np.isfinite(f[clean]) & np.isfinite(f["y_ppm"])]
    r = sk.future_leakage_probe(d, suspect, clean, ["season", "player_id"], "game_date", "y_ppm",
                                verbose=True)
    probes[label] = {k: (str(v) if not isinstance(v, (int, float, bool, type(None))) else v)
                     for k, v in r.items()}
f = f.drop(columns=["_LEAKY_control_ppm"])

print("\n  every candidate probed against the clean reference:")
prob_rows = []
for c in CANDIDATES:
    d = f[np.isfinite(f[c]) & np.isfinite(f["refB_ppm"]) & np.isfinite(f["y_ppm"])]
    if len(d) < 200:
        prob_rows.append({"candidate": c, "n": int(len(d)), "status": "TOO_FEW_ROWS"})
        continue
    r = sk.future_leakage_probe(d, c, "refB_ppm", ["season", "player_id"], "game_date", "y_ppm")
    prob_rows.append({"candidate": c, "n": int(len(d)),
                      "corr_candidate_with_future": r["corr_suspect_with_future"],
                      "corr_ref_with_future": r["corr_clean_with_future"],
                      "dr2_over_ref_predicting_future": r["dr2_suspect_over_clean_predicting_future"],
                      "status": r["status"], "verdict": str(r["verdict"])})
pr = pd.DataFrame(prob_rows)
pr.to_csv(os.path.join(OUT, "leakage_probes.csv"), index=False)
print(pr.to_string(index=False))
info["leakage_probe_reference"] = probes

# =====================================================================================
hdr("12. VERIFY BaseFit AGAINST screenkit.delta_r2_plain BEFORE ANY RESULT IS PRODUCED")
# =====================================================================================
chk = f[np.isfinite(f["y_ppm"]) & np.isfinite(f["refB_ppm"]) & np.isfinite(f["A01_dist_mean"])].copy()
y = chk["y_ppm"].to_numpy(float); rf = chk["refB_ppm"].to_numpy(float)
x = chk["A01_dist_mean"].to_numpy(float)
bf = BaseFit(y, rf)
fast = bf.dr2(x)
slow = sk.delta_r2_plain(y, rf.reshape(-1, 1), np.column_stack([rf, x]))
print("  BaseFit.dr2   = %.12e" % fast)
print("  kit delta_r2  = %.12e" % slow)
print("  abs diff      = %.3e" % abs(fast - slow))
assert abs(fast - slow) < 1e-10, "BaseFit disagrees with screenkit"
info["basefit_vs_kit_absdiff"] = float(abs(fast - slow))

# =====================================================================================
hdr("13. COVERAGE PER CANDIDATE + SAVE")
# =====================================================================================
cov = []
for c in CANDIDATES:
    v = pd.to_numeric(f[c], errors="coerce")
    cov.append({"candidate": c, "n_finite": int(np.isfinite(v).sum()),
                "frac_finite": float(np.isfinite(v).mean()),
                "mean": float(np.nanmean(v)), "sd": float(np.nanstd(v, ddof=1)),
                "p10": float(np.nanpercentile(v, 10)), "p90": float(np.nanpercentile(v, 90))})
cvd = pd.DataFrame(cov)
print(cvd.to_string(index=False))
cvd.to_csv(os.path.join(OUT, "candidate_coverage.csv"), index=False)

keep = (["season", "game_id", "game_date", "player_id", "team_id", "opp_team_id", "player_name",
         "season_type", "minutes", "fga", "fta", "fgm", "fg3m", "pts", "n_prior"]
        + ["y_" + r for r in ("ppm", "ts", "efg")]
        + ["refB_" + r for r in ("ppm", "ts", "efg")]
        + ["refA_" + r for r in ("ppm", "ts", "efg")]
        + CANDIDATES)
f[keep].to_parquet(os.path.join(OUT, "screen_frame.parquet"), index=False)
with open(os.path.join(OUT, "_s01.json"), "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2, default=str)
print("\nwrote screen_frame.parquet (%d rows, %d cols) and _s01.json" % (len(f), len(keep)))
