"""E0_I0016 s01 -- build the screening frame.  ALL FEATURES STRICTLY PRIOR unless flagged TIP-TIME.

Order of operations, deliberately: manifest check -> load -> partition assert -> build -> partition
re-assert -> leakage probes -> fast-dR2 identity check against the kit -> write.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import (KIT, MP_PATH, MT_PATH, MIN_PRIOR_APPEARANCES, OUT, ROOT, SEASONS, BaseFit,
                     decompose, hdr, league_prior_mean, prior_count, prior_mean, prior_sum,
                     safe_div, sk)

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 100)

TIP_TIME_COLS = ["C04_teammate_usg_present", "C05_top_usg_teammate_out", "C08_vacated_usg"]

# =====================================================================================
hdr("1. MANIFEST CHECKS -- read from disk at call time, not cited from notes")
# =====================================================================================
manifests = {}
for p in [MP_PATH, MT_PATH,
          os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity\analysis_frame.parquet"),
          os.path.join(ROOT, r"data\shotcharts\shots_2023_regular.parquet"),
          os.path.join(ROOT, r"data\w1_truth\player_game_availability.csv"),
          os.path.join(ROOT, r"data\w1_truth\roster_asof.csv")]:
    r = sk.check_manifest(p, verbose=True)
    manifests[os.path.basename(p)] = {k: v for k, v in r.items() if k != "note"}
    print("     -> usable_at_e0_e1=%s  fit_through_season=%s" % (r["usable_at_e0_e1"],
                                                                r["fit_through_season"]))
print("\n  USED: master_player.parquet, master_team.parquet (both asof_granularity='row').")
print("  NOT USED: analysis_frame.parquet (UNVERIFIABLE), shotcharts/* (UNVERIFIABLE).")
print("  NOT OPENED: w1_truth availability/roster (artifact-granular, fit_through_season 2026),")
print("              data/zone_maps/* (forbidden).  Availability is rebuilt from box membership.")

# =====================================================================================
hdr("2. LOAD + PARTITION FILTER (VALUE-BASED)")
# =====================================================================================
mp = pd.read_parquet(MP_PATH)
mt = pd.read_parquet(MT_PATH)
print("  raw master_player %s   raw master_team %s" % (mp.shape, mt.shape))

for d in (mp, mt):
    d["game_date"] = pd.to_datetime(d["game_date"], errors="coerce")

mp = mp[mp["season"].isin(SEASONS)].copy()
mt = mt[mt["season"].isin(SEASONS)].copy()
print("  after season filter: master_player %s  master_team %s" % (mp.shape, mt.shape))

# `observed_time` and `source` are LOCAL FILE MTIMES / filenames carrying 2026 strings.  The
# manifest says explicitly they are NOT an as-of bound.  They are kept in the frame for the
# partition assert to see rather than dropped -- dropping columns to make a check pass would be a
# place to cheat.  assert_partition is VALUE-based and does not parse them as dates.
for d, nm in ((mp, "master_player"), (mt, "master_team")):
    rep = sk.assert_partition(d, verbose=True)
    print("  %s partition: ok=%s" % (nm, rep["ok"]))

# =====================================================================================
hdr("3. TEAM-LEVEL STRICTLY-PRIOR AGGREGATES (from master_team)")
# =====================================================================================
TEAMNUM = ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "ast", "stl",
           "blk", "tov", "pf", "pts", "points_paint", "points_fast_break",
           "points_second_chance", "points_off_turnovers", "fouls_drawn",
           "opp_fgm", "opp_fga", "opp_fg3m", "opp_fg3a", "opp_ftm", "opp_fta", "opp_oreb",
           "opp_tov", "opp_pf", "opp_pts", "opp_blk", "opp_stl",
           "opp_points_paint", "opp_points_fast_break", "opp_points_second_chance"]
for c in TEAMNUM:
    mt[c] = pd.to_numeric(mt[c], errors="coerce").astype(float)

mt["poss"] = mt["fga"] - mt["oreb"] + mt["tov"] + 0.44 * mt["fta"]
mt["opp_poss"] = mt["opp_fga"] - mt["opp_oreb"] + mt["opp_tov"] + 0.44 * mt["opp_fta"]
mt = mt.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)

TK = ["season", "team_id"]
PS = {}
for c in TEAMNUM + ["poss", "opp_poss"]:
    PS[c] = prior_sum(mt, TK, c)
mt["_tm_prior_games"] = prior_count(mt, TK, "pts")

tprior = pd.DataFrame({"season": mt["season"], "team_id": mt["team_id"], "game_id": mt["game_id"],
                       "game_date": mt["game_date"], "tm_prior_games": mt["_tm_prior_games"]})

# --- what this team ALLOWED, strictly prior (these become the OPPONENT features when merged) ---
tprior["A01_opp_efg_allowed"] = safe_div(PS["opp_fgm"] + 0.5 * PS["opp_fg3m"], PS["opp_fga"])
tprior["A02_opp_ts_allowed"] = safe_div(PS["opp_pts"], 2.0 * (PS["opp_fga"] + 0.44 * PS["opp_fta"]))
tprior["A03_opp_paintpts_allowed"] = safe_div(PS["opp_points_paint"], mt["_tm_prior_games"])
tprior["A04_opp_blk"] = safe_div(PS["blk"], mt["_tm_prior_games"])
tprior["A05_opp_fg3pct_allowed"] = safe_div(PS["opp_fg3m"], PS["opp_fg3a"])
tprior["A06_opp_fg3a_share_allowed"] = safe_div(PS["opp_fg3a"], PS["opp_fga"])
tprior["A07_opp_ftrate_allowed"] = safe_div(PS["opp_fta"], PS["opp_fga"])
tprior["A08_opp_pf"] = safe_div(PS["pf"], mt["_tm_prior_games"])
tprior["A09_opp_stl"] = safe_div(PS["stl"], mt["_tm_prior_games"])
tprior["A10_opp_defrtg"] = 100.0 * safe_div(PS["opp_pts"], PS["opp_poss"])
tprior["A11_opp_fastbreak_allowed"] = safe_div(PS["opp_points_fast_break"], mt["_tm_prior_games"])
tprior["A12_opp_2ndchance_allowed"] = safe_div(PS["opp_points_second_chance"], mt["_tm_prior_games"])

# --- own-team offensive/tempo context, strictly prior ---
tprior["C02_tm_ast_per_game"] = safe_div(PS["ast"], mt["_tm_prior_games"])
tprior["C03_tm_ast_rate"] = safe_div(PS["ast"], PS["fgm"])
tprior["D01_tm_poss_per40"] = 200.0 * safe_div(PS["poss"], PS["minutes"])
tprior["D06_tm_fastbreak_pts"] = safe_div(PS["points_fast_break"], mt["_tm_prior_games"])
tprior["_tm_poss_per40"] = tprior["D01_tm_poss_per40"]

# team back-to-back: previous team game was exactly 1 day earlier (strictly prior)
prevdate = mt.groupby(TK, sort=False)["game_date"].shift(1)
tprior["_tm_b2b"] = ((mt["game_date"] - prevdate).dt.days == 1).astype(float)

print("  team prior table: %s rows, %d columns" % (tprior.shape, tprior.shape[1]))

# =====================================================================================
hdr("4. PLAYER FRAME + STRICTLY-PRIOR PLAYER AGGREGATES (from master_player)")
# =====================================================================================
PNUM = ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk",
        "tov", "pf", "pts", "points_paint", "points_fast_break", "points_second_chance",
        "fouls_drawn", "blocks_against"]
for c in PNUM:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp["team_id"] = pd.to_numeric(mp["team_id"], errors="coerce").astype("int64")
mp["opp_team_id"] = pd.to_numeric(mp["opp_team_id"], errors="coerce").astype("int64")

pl = mp[mp["minutes"] > 0].copy()                      # APPEARED rows only
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
print("  appeared player-game rows 2021-2024: %d  (players=%d, games=%d)"
      % (len(pl), pl["player_id"].nunique(), pl["game_id"].nunique()))
print("  season_type counts: %s" % pl["season_type"].value_counts().to_dict())

pl["used"] = pl["fga"] + 0.44 * pl["fta"] + pl["tov"]  # possessions used

PK = ["season", "player_id"]
QS = {}
for c in PNUM + ["used"]:
    QS[c] = prior_sum(pl, PK, c)
pl["n_prior"] = prior_count(pl, PK, "pts")

pl["B01_pl_ftrate"] = safe_div(QS["fta"], QS["fga"])
pl["B02_pl_ftpct"] = safe_div(QS["ftm"], QS["fta"])
pl["B03_pl_fouls_drawn_per36"] = 36.0 * safe_div(QS["fouls_drawn"], QS["minutes"])
pl["B06_pl_ftpts_per36"] = 36.0 * safe_div(QS["ftm"], QS["minutes"])
pl["D04_pl_fastbreak_share"] = safe_div(QS["points_fast_break"], QS["pts"])
pl["E01_pl_fg3a_share"] = safe_div(QS["fg3a"], QS["fga"])
pl["E02_pl_paintpts_share"] = safe_div(QS["points_paint"], QS["pts"])
pl["E03_pl_blocked_rate"] = safe_div(QS["blocks_against"], QS["fga"])
pl["E06_pl_efg_prior"] = safe_div(QS["fgm"] + 0.5 * QS["fg3m"], QS["fga"])
pl["E07_pl_2ndchance_share"] = safe_div(QS["points_second_chance"], QS["pts"])
pl["_pl_used_pg_prior"] = safe_div(QS["used"], pl["n_prior"])

# --- F03: minutes played in the trailing 7 days, STRICTLY PRIOR (accumulated load, not rest) ---
load = np.full(len(pl), np.nan)
for _, idx in pl.groupby(PK, sort=False).indices.items():
    idx = np.sort(idx)
    dts = pl["game_date"].to_numpy()[idx].astype("datetime64[D]").astype(np.int64)
    mins = pl["minutes"].to_numpy()[idx]
    cum = np.concatenate([[0.0], np.cumsum(mins)])
    for i in range(len(idx)):
        lo = int(np.searchsorted(dts, dts[i] - 7, side="left"))
        load[idx[i]] = cum[i] - cum[lo]                 # strictly prior rows within 7 days
pl["F03_minutes_load_7d"] = load

# =====================================================================================
hdr("5. TEAMMATE CONTEXT -- availability REBUILT FROM BOX MEMBERSHIP (D076 method)")
# =====================================================================================
# w1_truth/player_game_availability.csv and roster_asof.csv are artifact-granular, bound at 2026.
# They are NOT OPENED.  Presence in the box (minutes > 0) is the availability signal, exactly as
# D076 rebuilt it.  Three of these columns read TODAY's box and are flagged TIP-TIME everywhere.
c01 = np.full(len(pl), np.nan); c04 = np.full(len(pl), np.nan)
c05 = np.full(len(pl), np.nan); c07 = np.full(len(pl), np.nan); c08 = np.full(len(pl), np.nan)
c05_by_teamgame = {}

pl_idx_by_teamgame = pl.groupby(["season", "team_id", "game_id"], sort=False).indices
tg = (pl[["season", "team_id", "game_id", "game_date"]]
      .drop_duplicates().sort_values(["season", "team_id", "game_date", "game_id"], kind="stable"))
pid = pl["player_id"].to_numpy()
used_row = pl["used"].to_numpy()

for (season, team_id), sub in tg.groupby(["season", "team_id"], sort=False):
    roster = {}                                        # player_id -> [cum_used, cum_games]
    for _, r in sub.iterrows():
        key = (season, team_id, r["game_id"])
        rows = np.sort(pl_idx_by_teamgame[key])
        present = set(int(p) for p in pid[rows])
        prior_pg = {p: v[0] / v[1] for p, v in roster.items() if v[1] > 0}
        tot = sum(prior_pg.values())
        if prior_pg and tot > 0:
            shares = np.array([v / tot for v in prior_pg.values()])
            hhi = float((shares ** 2).sum())
            order = sorted(prior_pg.items(), key=lambda kv: -kv[1])
            ranks = {p: i + 1 for i, (p, _) in enumerate(order)}
            absent_usg = float(sum(v for p, v in prior_pg.items() if p not in present))
        else:
            hhi = np.nan; order = []; ranks = {}; absent_usg = np.nan
        for i in rows:
            p = int(pid[i])
            c01[i] = hhi
            c04[i] = float(sum(prior_pg.get(q, 0.0) for q in present if q != p))
            c07[i] = float(ranks.get(p, np.nan)) if ranks else np.nan
            c08[i] = absent_usg
            top_other = next((q for q, _ in order if q != p), None)
            c05[i] = np.nan if top_other is None else float(top_other not in present)
        # team-level version of C05 (top prior-usage player overall, for the C06 lag)
        top_any = order[0][0] if order else None
        c05_by_teamgame[key] = np.nan if top_any is None else float(top_any not in present)
        for i in rows:
            roster.setdefault(int(pid[i]), [0.0, 0])
            roster[int(pid[i])][0] += float(used_row[i])
            roster[int(pid[i])][1] += 1

pl["C01_tm_usage_hhi"] = c01
pl["C04_teammate_usg_present"] = c04
pl["C05_top_usg_teammate_out"] = c05
pl["C07_pl_usage_rank"] = c07
pl["C08_vacated_usg"] = c08

# C06: the SAME quantity measured on the team's PREVIOUS game -> strictly prior
tgl = tg.copy()
tgl["_c05_team"] = [c05_by_teamgame[(s, t, g)] for s, t, g
                    in zip(tgl["season"], tgl["team_id"], tgl["game_id"])]
tgl["C06_top_usg_teammate_out_lastgame"] = tgl.groupby(["season", "team_id"], sort=False)["_c05_team"].shift(1)
pl = pl.merge(tgl[["season", "team_id", "game_id", "C06_top_usg_teammate_out_lastgame"]],
              on=["season", "team_id", "game_id"], how="left")

# =====================================================================================
hdr("6. MERGE TEAM + OPPONENT PRIOR CONTEXT")
# =====================================================================================
own_cols = ["C02_tm_ast_per_game", "C03_tm_ast_rate", "D01_tm_poss_per40", "D06_tm_fastbreak_pts",
            "_tm_b2b", "tm_prior_games"]
opp_cols = [c for c in tprior.columns if c.startswith("A")] + ["_tm_poss_per40", "tm_prior_games"]

pl = pl.merge(tprior[["season", "team_id", "game_id"] + own_cols],
              on=["season", "team_id", "game_id"], how="left")
opp = tprior[["season", "team_id", "game_id"] + opp_cols].rename(
    columns={"team_id": "opp_team_id", "_tm_poss_per40": "D02_opp_poss_per40",
             "tm_prior_games": "opp_prior_games"})
pl = pl.merge(opp, on=["season", "opp_team_id", "game_id"], how="left")

pl["D03_pace_sum"] = pl["D01_tm_poss_per40"] + pl["D02_opp_poss_per40"]

# --- interactions (all components strictly prior) ---
pl["B04_matchup_ftrate"] = pl["B01_pl_ftrate"] * pl["A07_opp_ftrate_allowed"]
pl["B05_matchup_fouldraw"] = pl["B03_pl_fouls_drawn_per36"] * pl["A08_opp_pf"]
pl["D05_transition_x_pace"] = pl["D04_pl_fastbreak_share"] * pl["D03_pace_sum"]
pl["E04_3pt_vs_opp_perim"] = pl["E01_pl_fg3a_share"] * pl["A05_opp_fg3pct_allowed"]
pl["E05_paint_vs_opp_rim"] = pl["E02_pl_paintpts_share"] * pl["A04_opp_blk"]
pl["F01_b2b_x_fg3a_share"] = pl["_tm_b2b"] * pl["E01_pl_fg3a_share"]
pl["F02_b2b_x_ftrate"] = pl["_tm_b2b"] * pl["B01_pl_ftrate"]
pl["F04_load_x_fg3a_share"] = pl["F03_minutes_load_7d"] * pl["E01_pl_fg3a_share"]

# --- G01 negative control: deterministic pseudo-random, carries no information by construction ---
rng = np.random.default_rng(20260807)
pl["G01_noise"] = rng.standard_normal(len(pl))

# =====================================================================================
hdr("7. OUTCOMES + STRICTLY-PRIOR REFERENCES")
# =====================================================================================
pl["y_ppm"] = safe_div(pl["pts"], pl["minutes"])
pl["y_ts"] = safe_div(pl["pts"], 2.0 * (pl["fga"] + 0.44 * pl["fta"]))
pl["y_efg"] = safe_div(pl["fgm"] + 0.5 * pl["fg3m"], pl["fga"])

RATE_SPEC = {                       # outcome -> (numerator sum, denominator sum) for REF-B
    "ppm": (QS["pts"], QS["minutes"]),
    "ts": (QS["pts"], 2.0 * (QS["fga"] + 0.44 * QS["fta"])),
    "efg": (QS["fgm"] + 0.5 * QS["fg3m"], QS["fga"]),
}
ref_fallback_counts = {}
for rt, (num, den) in RATE_SPEC.items():
    ycol = "y_" + rt
    b = pd.Series(safe_div(num, den), index=pl.index)          # REF-B ratio of prior sums
    a = pl.groupby(PK, sort=False)[ycol].transform(            # REF-A mean of prior ratios
        lambda x: x.shift(1).expanding().mean())
    lg = league_prior_mean(pl, "season", "game_date", ycol)
    pl["refB_" + rt] = b.fillna(lg)
    pl["refA_" + rt] = a.fillna(lg)
    ref_fallback_counts[rt] = {
        "n_from_player_prior_B": int(b.notna().sum()),
        "n_from_league_prior_B": int(b.isna().sum() - (b.isna() & lg.isna()).sum()),
        "n_still_nan_B": int(pl["refB_" + rt].isna().sum()),
        "n_from_player_prior_A": int(a.notna().sum()),
        "n_still_nan_A": int(pl["refA_" + rt].isna().sum()),
    }
print("  reference fallback accounting: %s" % json.dumps(ref_fallback_counts, indent=2))

# =====================================================================================
hdr("8. SCREEN FRAME: Regular Season, >= %d prior appearances" % MIN_PRIOR_APPEARANCES)
# =====================================================================================
f = pl[(pl["season_type"] == "Regular Season") & (pl["n_prior"] >= MIN_PRIOR_APPEARANCES)].copy()
f = f.reset_index(drop=True)
print("  screen frame: %d rows, %d players, %d games, seasons %s"
      % (len(f), f["player_id"].nunique(), f["game_id"].nunique(), sorted(f["season"].unique())))
sk.assert_partition(f, verbose=True)
assert f["game_date"].max() < pd.Timestamp("2025-01-01"), "partition breach"
assert set(f["season"].unique()) <= set(SEASONS)

# =====================================================================================
hdr("9. LEAKAGE PROBES (trap 2).  Names lie in BOTH directions -- probe, do not trust labels.")
# =====================================================================================
probes = {}
# The reference is the object every candidate is measured against, so it is probed first.
# A deliberately RETROSPECTIVE control is built ONLY as the probe's positive control and is never
# used anywhere else in this screen.
f["_LEAKY_control_ppm"] = f.groupby(PK, sort=False)["y_ppm"].transform("mean")   # full-season mean
for suspect, clean, label in [("refB_ppm", "refA_ppm", "refB_vs_refA"),
                              ("_LEAKY_control_ppm", "refB_ppm", "POSITIVE_CONTROL_leaky_vs_refB")]:
    d = f[np.isfinite(f[suspect]) & np.isfinite(f[clean]) & np.isfinite(f["y_ppm"])]
    r = sk.future_leakage_probe(d, suspect, clean, ["season", "player_id"], "game_date", "y_ppm",
                                verbose=True)
    probes[label] = {k: v for k, v in r.items() if k != "verdict"}
    probes[label]["verdict"] = r["verdict"]
f = f.drop(columns=["_LEAKY_control_ppm"])

CANDS = sorted([c for c in f.columns if c[0] in "ABCDEFG" and c[1:3].isdigit() and "_" in c])
print("\n  candidates found in frame: %d" % len(CANDS))
print("  %s" % CANDS)

# probe every candidate against the clean reference, target = the player's own unplayed future rate
probe_rows = []
for c in CANDS:
    d = f[np.isfinite(f[c]) & np.isfinite(f["refB_ppm"]) & np.isfinite(f["y_ppm"])]
    if len(d) < 200:
        probe_rows.append(dict(candidate=c, n=len(d), skipped=True))
        continue
    r = sk.future_leakage_probe(d, c, "refB_ppm", ["season", "player_id"], "game_date", "y_ppm")
    probe_rows.append(dict(candidate=c, n=r["n_rows_with_future"],
                           corr_cand_future=r["corr_suspect_with_future"],
                           corr_ref_future=r["corr_clean_with_future"],
                           dr2_over_ref_predicting_future=r["dr2_suspect_over_clean_predicting_future"],
                           reads_future_flag=r["reads_future"], skipped=False))
probe_df = pd.DataFrame(probe_rows)
probe_df.to_csv(os.path.join(OUT, "leakage_probes.csv"), index=False)
flagged = probe_df[probe_df.get("reads_future_flag", False) == True]  # noqa: E712
print("\n  candidates the probe FLAGS as out-predicting the reference on the unplayed future: %d"
      % len(flagged))
if len(flagged):
    print(flagged.to_string(index=False))
print("  NOTE: this probe is a positive detector, NOT a certificate.  Constructions were read too;")
print("        see the TIME-WINDOW TABLE in NOTES.md, which names every column and its window.")

# =====================================================================================
hdr("10. FAST-dR2 IDENTITY CHECK against screenkit.delta_r2_plain (kit is ground truth)")
# =====================================================================================
chk = f[np.isfinite(f["y_ppm"]) & np.isfinite(f["refB_ppm"])].copy()
bf = BaseFit(chk["y_ppm"].to_numpy(float), chk["refB_ppm"].to_numpy(float))
worst = 0.0
for c in CANDS[:12]:
    x = pd.to_numeric(chk[c], errors="coerce").to_numpy(float)
    m = np.isfinite(x)
    if m.sum() < 500:
        continue
    y2 = chk["y_ppm"].to_numpy(float)[m]
    r2 = chk["refB_ppm"].to_numpy(float)[m]
    x2 = x[m]
    kit = sk.delta_r2_plain(y2, r2[:, None], np.column_stack([r2, x2]))
    fast = BaseFit(y2, r2).dr2(x2)
    worst = max(worst, abs(kit - fast))
print("  max |fast dR2 - screenkit.delta_r2_plain| over 12 candidates = %.3e" % worst)
assert worst < 1e-10, "fast dR2 does not reproduce the kit"
print("  -> fast path VERIFIED against the kit; used for the permutation loops only.")

# =====================================================================================
hdr("11. WRITE")
# =====================================================================================
keep = (["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date", "n_prior",
         "minutes", "fga", "fta", "pts", "starter_flag", "tm_prior_games", "opp_prior_games"]
        + ["y_ppm", "y_ts", "y_efg", "refA_ppm", "refA_ts", "refA_efg",
           "refB_ppm", "refB_ts", "refB_efg"] + CANDS)
out = f[keep].copy()
out.to_parquet(os.path.join(OUT, "screen_frame.parquet"), index=False)
with open(os.path.join(OUT, "_s01.json"), "w", encoding="utf-8") as fh:
    json.dump({"manifests": manifests, "n_rows": int(len(out)),
               "n_players": int(out["player_id"].nunique()),
               "n_games": int(out["game_id"].nunique()),
               "seasons": sorted(int(s) for s in out["season"].unique()),
               "candidates": CANDS, "tip_time_columns": TIP_TIME_COLS,
               "reference_fallbacks": ref_fallback_counts,
               "leakage_probes_headline": probes,
               "fast_dr2_max_abs_err_vs_kit": worst,
               "min_prior_appearances": MIN_PRIOR_APPEARANCES}, fh, indent=2, default=str)
print("  wrote screen_frame.parquet %s" % (out.shape,))
print("  candidate non-null coverage (fraction of rows):")
for c in CANDS:
    print("    %-34s %.4f" % (c, float(pd.to_numeric(out[c], errors="coerce").notna().mean())))
