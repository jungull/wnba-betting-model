"""E1_I0018 s01 -- build the screening frame and REPRODUCE D085's frozen C04 column exactly.

Order of operations, deliberately:
    manifest check -> load -> partition assert -> build -> partition re-assert ->
    EXACT REPRODUCTION CHECK against the frozen D085 column -> leakage probes ->
    fast-dR2 identity check against the kit -> write.

EVERY availability quantity here is rebuilt from BOX MEMBERSHIP (minutes > 0), the D076 method.
data/w1_truth/player_game_availability.csv and roster_asof.csv are artifact-granular with
fit_through_season 2026 and are NEVER OPENED.  Their manifests are read (a manifest is not the
artifact) purely to record the verdict on disk at call time rather than citing it from notes.
"""
import json
import os
import sys
from collections import deque

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import (D085_FRAME, MIN_PRIOR_APPEARANCES, MP_PATH, MT_PATH, OUT, ROOT, SEASONS,
                     BaseFit, hdr, league_prior_mean, prior_count, prior_mean, prior_sum,
                     safe_div, sk)

TIP_TIME_COLS = ["T01_c04_tiptime", "T02_teamgame_present_usg", "T03_absent_usg", "T04_n_present",
                 "N01_news_vs_prevgame", "N02_news_vs_avail",
                 "M01_dev_pos", "M02_dev_neg", "M03_dev_pos_playernorm", "M04_dev_neg_playernorm"]
PRIOR_ONLY_COLS = ["O01_own_usg_pg", "P01_c04_prevgame", "P02_c04_availweighted",
                   "P03_c04_avail5", "P04_absent_usg_prevgame", "P05_n_present_prevgame",
                   "P06_c04_rotstab"]

# =====================================================================================
hdr("1. MANIFEST CHECKS -- read from disk at call time, not cited from notes")
# =====================================================================================
manifests = {}
for p in [MP_PATH, MT_PATH,
          os.path.join(ROOT, r"data\w1_truth\player_game_availability.csv"),
          os.path.join(ROOT, r"data\w1_truth\roster_asof.csv")]:
    r = sk.check_manifest(p, verbose=True)
    manifests[os.path.basename(p)] = {k: v for k, v in r.items() if k != "note"}
    print("     -> usable_at_e0_e1=%s  fit_through_season=%s" % (r["usable_at_e0_e1"],
                                                                r["fit_through_season"]))
print("\n  USED:       master_player.parquet, master_team.parquet (both asof_granularity='row').")
print("  NOT OPENED: w1_truth/player_game_availability.csv, w1_truth/roster_asof.csv")
print("              -- artifact-granular, fit_through_season 2026, FILTERING DOES NOT HELP.")
print("              Availability is rebuilt from box membership (minutes>0), the D076 method.")
print("  READ-ONLY REPRODUCTION TARGET: E0_I0016/screen_frame.parquet (frozen).")

# =====================================================================================
hdr("2. LOAD + PARTITION FILTER (VALUE-BASED, never a byte scan)")
# =====================================================================================
mp = pd.read_parquet(MP_PATH)
print("  raw master_player %s" % (mp.shape,))
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
mp = mp[mp["season"].isin(SEASONS)].copy()
print("  after season filter: master_player %s" % (mp.shape,))
rep = sk.assert_partition(mp, verbose=True)
print("  master_player partition ok=%s" % rep["ok"])

PNUM = ["minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "ast", "stl", "blk",
        "tov", "pf", "pts", "points_paint", "points_fast_break", "points_second_chance",
        "fouls_drawn", "blocks_against"]
for c in PNUM:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)
mp["player_id"] = pd.to_numeric(mp["player_id"], errors="coerce").astype("int64")
mp["team_id"] = pd.to_numeric(mp["team_id"], errors="coerce").astype("int64")
mp["opp_team_id"] = pd.to_numeric(mp["opp_team_id"], errors="coerce").astype("int64")

pl = mp[mp["minutes"] > 0].copy()                       # APPEARED rows only -- D085's filter
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
print("  appeared player-game rows 2021-2024: %d  (players=%d, games=%d)"
      % (len(pl), pl["player_id"].nunique(), pl["game_id"].nunique()))

pl["used"] = pl["fga"] + 0.44 * pl["fta"] + pl["tov"]   # possessions used -- D085's definition
pl["TSA"] = pl["fga"] + 0.44 * pl["fta"]                # true-shot attempts

# =====================================================================================
hdr("3. STRICTLY-PRIOR PLAYER AGGREGATES.  .shift(1) ALWAYS PRECEDES .expanding().")
# =====================================================================================
PK = ["season", "player_id"]
QS = {}
for c in PNUM + ["used", "TSA"]:
    QS[c] = prior_sum(pl, PK, c)
pl["n_prior"] = prior_count(pl, PK, "pts")

# =====================================================================================
hdr("4. TEAMMATE CONTEXT -- availability REBUILT FROM BOX MEMBERSHIP (D076 method)")
# =====================================================================================
# The TIP-TIME columns read TODAY's box membership.  The PRIOR-ONLY columns read only the team's
# strictly earlier games.  Both are produced in ONE pass so the row alignment is identical.
n = len(pl)
NA = lambda: np.full(n, np.nan)                                                      # noqa: E731
T01 = NA(); T02 = NA(); T03 = NA(); T04 = NA(); O01 = NA()
P01 = NA(); P02 = NA(); P03 = NA(); P04 = NA(); P05 = NA(); P06 = NA()

pl_idx_by_teamgame = pl.groupby(["season", "team_id", "game_id"], sort=False).indices
tg = (pl[["season", "team_id", "game_id", "game_date"]]
      .drop_duplicates().sort_values(["season", "team_id", "game_date", "game_id"], kind="stable"))
pid = pl["player_id"].to_numpy()
used_row = pl["used"].to_numpy()

for (season, team_id), sub in tg.groupby(["season", "team_id"], sort=False):
    roster = {}                       # player_id -> [cum_used, cum_appearances]   STRICTLY PRIOR
    n_team_games = 0                  # team games seen so far                     STRICTLY PRIOR
    prev_present = None               # previous game's box membership             STRICTLY PRIOR
    last5 = deque(maxlen=5)           # last 5 prior games' box membership         STRICTLY PRIOR
    last3 = deque(maxlen=3)           # last 3 prior games' box membership         STRICTLY PRIOR
    for _, r in sub.iterrows():
        key = (season, team_id, r["game_id"])
        rows = np.sort(pl_idx_by_teamgame[key])
        present = set(int(p) for p in pid[rows])                    # <-- TIP-TIME: TODAY's box
        prior_pg = {p: v[0] / v[1] for p, v in roster.items() if v[1] > 0}

        # strictly-prior availability weights
        if n_team_games > 0:
            avail = {p: v[1] / n_team_games for p, v in roster.items()}
        else:
            avail = {}
        if len(last5):
            a5 = {p: float(np.mean([p in s for s in last5])) for p in roster}
        else:
            a5 = {}
        if len(last3):
            a3 = {p: float(np.mean([p in s for s in last3])) for p in roster}
        else:
            a3 = {}

        t02 = float(sum(prior_pg.get(q, 0.0) for q in present)) if prior_pg else np.nan
        absent_usg = (float(sum(v for p, v in prior_pg.items() if p not in present))
                      if prior_pg else np.nan)
        if prev_present is not None and prior_pg:
            absent_prev = float(sum(v for p, v in prior_pg.items() if p not in prev_present))
        else:
            absent_prev = np.nan

        for i in rows:
            p = int(pid[i])
            own = prior_pg.get(p, np.nan) if prior_pg else np.nan
            O01[i] = own
            T04[i] = float(len(present))
            if prior_pg:
                T01[i] = float(sum(prior_pg.get(q, 0.0) for q in present if q != p))
                T02[i] = t02
                T03[i] = absent_usg
                P02[i] = float(sum(prior_pg[q] * avail.get(q, 0.0)
                                   for q in prior_pg if q != p)) if avail else np.nan
                P03[i] = float(sum(prior_pg[q] * a5.get(q, 0.0)
                                   for q in prior_pg if q != p)) if a5 else np.nan
                P06[i] = float(sum(prior_pg[q] * a5.get(q, 0.0) * a3.get(q, 0.0)
                                   for q in prior_pg if q != p)) if (a5 and a3) else np.nan
                if prev_present is not None:
                    P01[i] = float(sum(prior_pg.get(q, 0.0) for q in prev_present if q != p))
                    P04[i] = absent_prev
            if prev_present is not None:
                P05[i] = float(len(prev_present))

        # ---- advance the strictly-prior state AFTER every row of this game is written ----
        for i in rows:
            roster.setdefault(int(pid[i]), [0.0, 0])
            roster[int(pid[i])][0] += float(used_row[i])
            roster[int(pid[i])][1] += 1
        n_team_games += 1
        prev_present = present
        last5.append(present)
        last3.append(present)

pl["T01_c04_tiptime"] = T01
pl["T02_teamgame_present_usg"] = T02
pl["T03_absent_usg"] = T03
pl["T04_n_present"] = T04
pl["O01_own_usg_pg"] = O01
pl["P01_c04_prevgame"] = P01
pl["P02_c04_availweighted"] = P02
pl["P03_c04_avail5"] = P03
pl["P04_absent_usg_prevgame"] = P04
pl["P05_n_present_prevgame"] = P05
pl["P06_c04_rotstab"] = P06

# --- N: the same-day NEWS increment (tip-time by construction) ---
pl["N01_news_vs_prevgame"] = pl["T01_c04_tiptime"] - pl["P01_c04_prevgame"]
pl["N02_news_vs_avail"] = pl["T01_c04_tiptime"] - pl["P02_c04_availweighted"]

# --- M: deviation from a STRICTLY-PRIOR running norm.  Both norms are .shift(1).expanding(). ---
pl = pl.sort_values(["season", "team_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
norm_team = pl.groupby(["season", "team_id"], sort=False)["T01_c04_tiptime"].transform(
    lambda x: x.shift(1).expanding().mean())
pl = pl.sort_values(["season", "player_id", "game_date", "game_id"],
                    kind="stable").reset_index(drop=True)
norm_team = norm_team.reindex(pl.index)   # index was reset; recompute cleanly below instead
pl["_norm_team"] = (pl.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable")
                    .groupby(["season", "team_id"], sort=False)["T01_c04_tiptime"]
                    .transform(lambda x: x.shift(1).expanding().mean()))
pl["_norm_player"] = pl.groupby(["season", "player_id"], sort=False)["T01_c04_tiptime"].transform(
    lambda x: x.shift(1).expanding().mean())
dev_t = pl["T01_c04_tiptime"] - pl["_norm_team"]
dev_p = pl["T01_c04_tiptime"] - pl["_norm_player"]
pl["M01_dev_pos"] = dev_t.clip(lower=0)
pl["M02_dev_neg"] = dev_t.clip(upper=0)
pl["M03_dev_pos_playernorm"] = dev_p.clip(lower=0)
pl["M04_dev_neg_playernorm"] = dev_p.clip(upper=0)

# --- G01 negative control ---
rng = np.random.default_rng(20260808)
pl["G01_noise"] = rng.standard_normal(len(pl))

# =====================================================================================
hdr("5. OUTCOMES + STRICTLY-PRIOR REFERENCES (D085 REF-B construction, extended)")
# =====================================================================================
pl["y_ppm"] = safe_div(pl["pts"], pl["minutes"])
pl["y_spm"] = safe_div(pl["TSA"], pl["minutes"])
pl["y_pps"] = safe_div(pl["pts"], pl["TSA"])
pl["y_ts"] = safe_div(pl["pts"], 2.0 * pl["TSA"])
pl["y_efg"] = safe_div(pl["fgm"] + 0.5 * pl["fg3m"], pl["fga"])
pl["y_fgapm"] = safe_div(pl["fga"], pl["minutes"])
pl["y_ppfga"] = safe_div(pl["pts"], pl["fga"])
pl["y_pts"] = pl["pts"].astype(float)

RATE_SPEC = {
    "ppm": (QS["pts"], QS["minutes"]),
    "spm": (QS["TSA"], QS["minutes"]),
    "pps": (QS["pts"], QS["TSA"]),
    "ts":  (QS["pts"], 2.0 * QS["TSA"]),
    "efg": (QS["fgm"] + 0.5 * QS["fg3m"], QS["fga"]),
    "fgapm": (QS["fga"], QS["minutes"]),
    "ppfga": (QS["pts"], QS["fga"]),
    "mpg": (QS["minutes"], pl["n_prior"]),
    "own_usg_pg": (QS["used"], pl["n_prior"]),
}
ref_fallback_counts = {}
for rt, (num, den) in RATE_SPEC.items():
    ycol = "y_" + rt
    b = pd.Series(safe_div(num, den), index=pl.index)
    if ycol in pl.columns:
        lg = league_prior_mean(pl, "season", "game_date", ycol)
        a = pl.groupby(PK, sort=False)[ycol].transform(lambda x: x.shift(1).expanding().mean())
        pl["refA_" + rt] = a.fillna(lg)
    else:
        lg = league_prior_mean(pl, "season", "game_date", "y_ppm") * np.nan
        lg = pd.Series(np.where(np.isfinite(b), np.nan, np.nan), index=pl.index)
        # mpg / own_usg_pg have no matching realised-outcome column; cold-start fallback is the
        # same-season strictly-earlier league expanding mean of the SAME prior ratio.
        tmp = pd.Series(safe_div(num, den), index=pl.index)
        pl["_tmp_lg"] = tmp
        lg = league_prior_mean(pl, "season", "game_date", "_tmp_lg")
        pl.drop(columns=["_tmp_lg"], inplace=True)
    pl["refB_" + rt] = b.fillna(lg)
    ref_fallback_counts[rt] = {
        "n_from_player_prior_B": int(b.notna().sum()),
        "n_still_nan_B": int(pl["refB_" + rt].isna().sum()),
    }
print("  reference fallback accounting:\n%s" % json.dumps(ref_fallback_counts, indent=2))

# EXACT ALGEBRAIC IDENTITIES, asserted rather than assumed:
_m = np.isfinite(pl["y_ts"]) & np.isfinite(pl["y_pps"])
print("\n  IDENTITY  max|y_pps - 2*y_ts|            = %.3e"
      % float(np.nanmax(np.abs(pl.loc[_m, "y_pps"] - 2 * pl.loc[_m, "y_ts"]))))
_m2 = np.isfinite(pl["refB_ts"]) & np.isfinite(pl["refB_pps"])
print("  IDENTITY  max|refB_pps - 2*refB_ts|      = %.3e"
      % float(np.nanmax(np.abs(pl.loc[_m2, "refB_pps"] - 2 * pl.loc[_m2, "refB_ts"]))))
_m3 = np.isfinite(pl["y_ppm"]) & np.isfinite(pl["y_spm"]) & np.isfinite(pl["y_pps"])
print("  IDENTITY  max|y_ppm - y_spm*y_pps|       = %.3e"
      % float(np.nanmax(np.abs(pl.loc[_m3, "y_ppm"] - pl.loc[_m3, "y_spm"] * pl.loc[_m3, "y_pps"]))))
_m4 = np.isfinite(pl["T01_c04_tiptime"]) & np.isfinite(pl["T02_teamgame_present_usg"]) & np.isfinite(pl["O01_own_usg_pg"])
print("  IDENTITY  max|T01 - (T02 - O01)|         = %.3e   <-- the reference-incompleteness vector"
      % float(np.nanmax(np.abs(pl.loc[_m4, "T01_c04_tiptime"]
                               - (pl.loc[_m4, "T02_teamgame_present_usg"]
                                  - pl.loc[_m4, "O01_own_usg_pg"])))))

# =====================================================================================
hdr("6. SCREEN FRAME: Regular Season, >= %d prior appearances (D085's filter)"
    % MIN_PRIOR_APPEARANCES)
# =====================================================================================
f = pl[(pl["season_type"] == "Regular Season") & (pl["n_prior"] >= MIN_PRIOR_APPEARANCES)].copy()
f = f.sort_values(["season", "player_id", "game_date", "game_id"],
                  kind="stable").reset_index(drop=True)
f["prior5_minutes"] = f.groupby(["season", "player_id"], sort=False)["minutes"].transform(
    lambda x: x.shift(1).rolling(5).mean())
print("  screen frame: %d rows, %d players, %d games, seasons %s"
      % (len(f), f["player_id"].nunique(), f["game_id"].nunique(), sorted(f["season"].unique())))
sk.assert_partition(f, verbose=True)
assert f["game_date"].max() < pd.Timestamp("2025-01-01"), "partition breach"
assert set(f["season"].unique()) <= set(SEASONS)

# =====================================================================================
hdr("7. EXACT REPRODUCTION CHECK against D085's FROZEN screen_frame.parquet")
# =====================================================================================
d085 = pd.read_parquet(D085_FRAME)
sk.assert_partition(d085, verbose=True)
key = ["season", "player_id", "game_id"]
j = f[key + ["T01_c04_tiptime", "T03_absent_usg", "y_ppm", "y_ts", "y_efg",
             "refB_ppm", "refB_ts", "refB_efg", "n_prior"]].merge(
    d085[key + ["C04_teammate_usg_present", "C08_vacated_usg", "y_ppm", "y_ts", "y_efg",
                "refB_ppm", "refB_ts", "refB_efg", "n_prior"]],
    on=key, how="inner", suffixes=("_new", "_frozen"))
repro = {"n_rows_this_frame": int(len(f)), "n_rows_d085_frame": int(len(d085)),
         "n_rows_joined": int(len(j))}
for a, b, nm in [("T01_c04_tiptime", "C04_teammate_usg_present", "C04"),
                 ("T03_absent_usg", "C08_vacated_usg", "C08"),
                 ("y_ppm_new", "y_ppm_frozen", "y_ppm"),
                 ("y_ts_new", "y_ts_frozen", "y_ts"),
                 ("y_efg_new", "y_efg_frozen", "y_efg"),
                 ("refB_ppm_new", "refB_ppm_frozen", "refB_ppm"),
                 ("refB_ts_new", "refB_ts_frozen", "refB_ts"),
                 ("refB_efg_new", "refB_efg_frozen", "refB_efg"),
                 ("n_prior_new", "n_prior_frozen", "n_prior")]:
    m = np.isfinite(j[a]) & np.isfinite(j[b])
    md = float(np.max(np.abs(j.loc[m, a] - j.loc[m, b]))) if m.sum() else float("nan")
    nan_mismatch = int((j[a].isna() != j[b].isna()).sum())
    repro["max_abs_diff_" + nm] = md
    repro["nan_pattern_mismatch_" + nm] = nan_mismatch
    print("  %-10s max|new - frozen| = %.6e     NaN-pattern mismatches = %d" % (nm, md, nan_mismatch))
assert repro["n_rows_joined"] == repro["n_rows_d085_frame"] == repro["n_rows_this_frame"], \
    "row sets differ -- reproduction is not like-for-like"
assert repro["max_abs_diff_C04"] < 1e-12, "C04 NOT reproduced"
print("\n  -> D085's C04 column is REPRODUCED EXACTLY from master_player.  Row set identical.")

# =====================================================================================
hdr("8. LEAKAGE PROBES (trap 2).  A FLAG IS A SCREENING FLAG, NOT A VERDICT (kit K1).")
# =====================================================================================
probes = {}
f["_LEAKY_control_ppm"] = f.groupby(PK, sort=False)["y_ppm"].transform("mean")   # POSITIVE CONTROL
for suspect, clean, label in [("refB_ppm", "refA_ppm", "refB_vs_refA"),
                              ("refB_spm", "refA_spm", "refB_spm_vs_refA_spm"),
                              ("_LEAKY_control_ppm", "refB_ppm", "POSITIVE_CONTROL_leaky_vs_refB")]:
    d = f[np.isfinite(f[suspect]) & np.isfinite(f[clean]) & np.isfinite(f["y_ppm"])]
    r = sk.future_leakage_probe(d, suspect, clean, ["season", "player_id"], "game_date", "y_ppm",
                                verbose=True)
    probes[label] = {k: v for k, v in r.items()}
f = f.drop(columns=["_LEAKY_control_ppm"])

CANDS = sorted([c for c in f.columns
                if c[0] in "TOPNMG" and c[1:3].isdigit() and "_" in c])
print("\n  candidates found in frame: %d\n  %s" % (len(CANDS), CANDS))
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
                           screening_flag=r.get("screening_flag", r.get("reads_future")),
                           status=r.get("status"), skipped=False))
probe_df = pd.DataFrame(probe_rows)
probe_df.to_csv(os.path.join(OUT, "leakage_probes.csv"), index=False)
fl = probe_df[probe_df.get("screening_flag", False) == True]  # noqa: E712
print("\n  candidates the probe FLAGS (screening flag, NOT a verdict): %d" % len(fl))
if len(fl):
    print(fl.to_string(index=False))

# =====================================================================================
hdr("9. FAST-dR2 IDENTITY CHECK against screenkit.delta_r2_plain (kit is ground truth)")
# =====================================================================================
chk = f[np.isfinite(f["y_ppm"]) & np.isfinite(f["refB_ppm"]) & np.isfinite(f["refB_spm"])].copy()
worst = 0.0
for c in CANDS:
    x = pd.to_numeric(chk[c], errors="coerce").to_numpy(float)
    m = np.isfinite(x)
    if m.sum() < 500:
        continue
    y2 = chk["y_ppm"].to_numpy(float)[m]
    for basecols in (["refB_ppm"], ["refB_ppm", "refB_spm"]):
        B = chk[basecols].to_numpy(float)[m]
        kit = sk.delta_r2_plain(y2, B, np.column_stack([B, x[m]]))
        fast = BaseFit(y2, B).dr2(x[m])
        worst = max(worst, abs(kit - fast))
print("  max |fast dR2 - screenkit.delta_r2_plain| over %d candidates x 2 bases = %.3e"
      % (len(CANDS), worst))
assert worst < 1e-10, "fast dR2 does not reproduce the kit"
print("  -> fast path VERIFIED against the kit; used for the permutation loops only.")

# =====================================================================================
hdr("10. WRITE")
# =====================================================================================
keep = (["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date", "n_prior",
         "minutes", "fga", "fta", "fgm", "fg3m", "pts", "TSA", "used", "starter_flag",
         "prior5_minutes"]
        + [c for c in f.columns if c.startswith("y_")]
        + [c for c in f.columns if c.startswith("refA_") or c.startswith("refB_")]
        + CANDS)
keep = [c for c in dict.fromkeys(keep) if c in f.columns]
out = f[keep].copy()
out.to_parquet(os.path.join(OUT, "screen_frame.parquet"), index=False)
with open(os.path.join(OUT, "_s01.json"), "w", encoding="utf-8") as fh:
    json.dump({"manifests": manifests, "n_rows": int(len(out)),
               "n_players": int(out["player_id"].nunique()),
               "n_games": int(out["game_id"].nunique()),
               "seasons": sorted(int(s) for s in out["season"].unique()),
               "candidates": CANDS,
               "tip_time_columns": TIP_TIME_COLS,
               "strictly_prior_only_columns": PRIOR_ONLY_COLS,
               "reference_fallbacks": ref_fallback_counts,
               "reproduction_vs_D085": repro,
               "leakage_probes_headline": probes,
               "fast_dr2_max_abs_err_vs_kit": worst}, fh, indent=2, default=str)
print("  wrote screen_frame.parquet %s" % (out.shape,))
print("\n  candidate non-null coverage (fraction of frame rows):")
for c in CANDS:
    print("    %-30s %.4f   sd=%.5f" % (c, float(out[c].notna().mean()),
                                        float(pd.to_numeric(out[c], errors='coerce').std())))
