r"""S33R / finding A1 - is there an admissible witness for master_team.game_date?

ROOT (stated explicitly; a prior agent measured the wrong tree):
  C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program
The program worktree's data/masters/master_team.parquet hashes to the S33 SPEC pin
ad79ce5c...8528.  The MAIN working tree's copy has drifted (e8e35b53...) because live
captures continue there.  Only the worktree is admissible.

Produces A1_DATE_WITNESS_RECEIPT.json.  No fit, no performance number.
"""
import hashlib
import json
import os

import pandas as pd
import pyarrow.parquet as pq

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
DATA = os.path.join(WORKTREE, "data")
HERE = os.path.dirname(os.path.abspath(__file__))
out = {"measurement": "A1_DATE_WITNESS", "root": WORKTREE, "reads": {}}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ universe
mt_path = os.path.join(DATA, "masters", "master_team.parquet")
out["reads"]["data/masters/master_team.parquet"] = sha256(mt_path)
mt = pd.read_parquet(mt_path)
home = mt[mt.is_home == 1].copy()
first_date = home[home.season == 2021].game_date.min()
uni = home[home.game_date > first_date].copy()
uni_ids = set(uni.game_id)
season_of = dict(zip(uni.game_id, uni.season))
date_of = dict(zip(uni.game_id, uni.game_date))
stype_of = dict(zip(uni.game_id, uni.season_type))
pooled_test = {g for g in uni_ids if season_of[g] >= 2022}
out["universe"] = {
    "full_schedule_clusters": int(home.game_id.nunique()),
    "full_schedule_rows": int(mt[mt.game_id.isin(set(home.game_id))].shape[0]),
    "excluded_first_2021_date": first_date,
    "universe_clusters": len(uni_ids),
    "universe_rows": int(mt[mt.game_id.isin(uni_ids)].shape[0]),
    "pooled_test_clusters": len(pooled_test),
    "per_season": {str(k): int(v) for k, v in uni.groupby("season").game_id.nunique().items()},
}


def census(ids):
    ids = set(ids) & uni_ids
    return {"n": len(ids),
            "per_season": {str(s): sum(1 for g in ids if season_of[g] == s)
                           for s in sorted(set(season_of.values()))},
            "pooled_test": len(ids & pooled_test)}


# ============================ 1. the S33-named measurement, re-derived ============
tt_path = os.path.join(DATA, "reference", "tip_times.csv")
out["reads"]["data/reference/tip_times.csv"] = sha256(tt_path)
tt = pd.read_csv(tt_path)
tt["game_id"] = tt.game_id.astype(str)
tt_uni = tt[tt.game_id.isin(uni_ids)]
tt_dev = tt_uni[[date_of[g] != str(d) for g, d in zip(tt_uni.game_id, tt_uni.game_date)]]
flagged = sorted(tt_uni[tt_uni.n_commence_variants > 1].game_id.tolist())
out["s33_named_measurement_as_written"] = {
    "witness_1": "data/reference/tip_times.csv",
    "witness_1_provenance": {k: int(v) for k, v in tt.source_table.value_counts().items()},
    "witness_1_is_market_archive_derived": True,
    "rows": int(tt.shape[0]),
    "seasons_present": sorted(int(s) for s in tt.season.unique()),
    "covers_2021": bool((tt.season == 2021).any()),
    "universe_clusters_witnessed": census(tt_uni.game_id),
    "universe_clusters_UNWITNESSED": census(uni_ids - set(tt_uni.game_id)),
    "unwitnessed_game_ids": sorted(uni_ids - set(tt_uni.game_id)),
    "date_deviations_found": int(tt_dev.shape[0]),
    "reschedule_column_never_consulted_by_S33": "n_commence_variants",
    "n_commence_variants_gt_1": {"n": len(flagged), "game_ids": flagged,
                                 "census": census(flagged)},
    "witness_2": "data/refresh_2026/gamelog_team_*.parquet (+ data/wnba_team_gamelog_2024.parquet)",
    "witness_2_independence": "NONE - master_team.source names these files as its own build inputs",
}

# ---- witness-2 coverage, and the hole S34 named
rf = os.path.join(DATA, "refresh_2026")
gl_names, gl_paths = [], []
for f in sorted(os.listdir(rf)):
    if f.startswith("gamelog_team_"):
        gl_names.append("data/refresh_2026/" + f)
        gl_paths.append(os.path.join(rf, f))
frames = []
for name, pth in zip(gl_names, gl_paths):
    g = pd.read_parquet(pth)
    c = {x.lower(): x for x in g.columns}
    frames.append(pd.DataFrame({"game_id": g[c["game_id"]].astype(str),
                                "game_date": g[c["game_date"]].astype(str).str.slice(0, 10),
                                "file": name}))
gl = pd.concat(frames, ignore_index=True).drop_duplicates("game_id")
gl_uni = gl[gl.game_id.isin(uni_ids)]
out["s33_named_measurement_as_written"]["witness_2_files_present"] = gl_names
out["s33_named_measurement_as_written"]["witness_2_expected_but_absent"] = [
    f"data/refresh_2026/gamelog_team_{s}_{t}.parquet"
    for s in sorted(set(season_of.values())) for t in ("regular_season", "playoffs")
    if f"data/refresh_2026/gamelog_team_{s}_{t}.parquet" not in gl_names]
out["s33_named_measurement_as_written"]["witness_2_coverage_from_refresh_dir_only"] = \
    census(gl_uni.game_id)
out["s33_named_measurement_as_written"]["witness_2_hole_from_refresh_dir_only"] = \
    census(uni_ids - set(gl_uni.game_id))

# ==================== 2. REPLACEMENT WITNESS A: independent NBA-Stats endpoint =====
# shotchartdetail pulls (data/shotcharts/shots_<season>_<type>.parquet) carry GAME_DATE
# per GAME_ID.  They are NOT in master_team's build chain (master_team.source names only
# gamelog_team_* / wnba_team_gamelog_2024) and they are NOT market-archive derived.
sc_dir = os.path.join(DATA, "shotcharts")
sc_frames, sc_reads = [], {}
for f in sorted(os.listdir(sc_dir)):
    if not f.endswith(".parquet"):
        continue
    p = os.path.join(sc_dir, f)
    names = [n.lower() for n in pq.ParquetFile(p).schema.names]
    if "game_id" not in names or "game_date" not in names:
        continue
    d = pd.read_parquet(p, columns=["GAME_ID", "GAME_DATE"]).drop_duplicates()
    d["game_id"] = d.GAME_ID.astype(str)
    d["wdate"] = (d.GAME_DATE.astype(str).str.slice(0, 4) + "-"
                  + d.GAME_DATE.astype(str).str.slice(4, 6) + "-"
                  + d.GAME_DATE.astype(str).str.slice(6, 8))
    sc_frames.append(d[["game_id", "wdate"]])
    sc_reads["data/shotcharts/" + f] = sha256(p)
sc = pd.concat(sc_frames, ignore_index=True).drop_duplicates()
multi = sc.groupby("game_id").wdate.nunique()
sc = sc.drop_duplicates("game_id")
sc_uni = sc[sc.game_id.isin(uni_ids)]
sc_dev = sc_uni[[date_of[g] != w for g, w in zip(sc_uni.game_id, sc_uni.wdate)]]
out["reads"].update(sc_reads)
out["replacement_witness_A_shotchart_endpoint"] = {
    "artifacts": sorted(sc_reads),
    "market_archive_derived": False,
    "in_master_team_build_chain": False,
    "covers_2021": bool(any(g.startswith("10221") or g.startswith("10421")
                            for g in sc.game_id)),
    "games_with_internally_conflicting_dates": int((multi > 1).sum()),
    "universe_clusters_witnessed": census(sc_uni.game_id),
    "universe_clusters_UNWITNESSED": census(uni_ids - set(sc_uni.game_id)),
    "unwitnessed_game_ids": sorted(uni_ids - set(sc_uni.game_id)),
    "date_deviations_vs_master_team": int(sc_dev.shape[0]),
    "deviation_detail": [{"game_id": g, "master_team": date_of[g], "shotchart": w}
                         for g, w in zip(sc_dev.game_id, sc_dev.wdate)],
    "what_it_can_and_cannot_show": (
        "CAN falsify: any disagreement between two independently pulled vendor endpoints "
        "about the date a game was played, including a rewrite that touched only the "
        "gamelog chain. CANNOT show: what the schedule said BEFORE tip - both endpoints "
        "are postgame records, so a postponement agreed by both is invisible to this test."),
}

# =============== 3. REPLACEMENT WITNESS B: schedule-release ordinal (reschedule-direct)
# The trailing 5 digits of a WNBA regular-season game_id are the league's schedule-release
# sequence number, fixed when the schedule is published and never reissued.  A game moved
# to a later date keeps its number, so it lands out of date order against its neighbours.
# Playoff ids encode round/series/game instead of a linear counter and are reported
# separately as STRUCTURAL, never as reschedule evidence.
seq = uni[["game_id", "season", "season_type", "game_date"]].drop_duplicates("game_id").copy()
seq["ordinal"] = seq.game_id.str.slice(-5).astype(int)
reg_anoms, playoff_note = [], {}
for (s, st), grp in seq.groupby(["season", "season_type"]):
    g2 = grp.sort_values("ordinal")
    dates = g2.game_date.tolist()
    ids = g2.game_id.tolist()
    ords = g2.ordinal.tolist()
    dec = [i for i in range(1, len(dates)) if dates[i] < dates[i - 1]]
    if st == "Regular Season":
        for i in dec:
            reg_anoms.append({
                "game_id": ids[i], "season": int(s), "ordinal": ords[i],
                "game_date": dates[i],
                "previous_ordinal_game_id": ids[i - 1],
                "previous_ordinal_date": dates[i - 1],
                "days_out_of_order": int(
                    (pd.Timestamp(dates[i - 1]) - pd.Timestamp(dates[i])).days)})
    else:
        playoff_note[f"{s}"] = {"games": len(ids), "adjacent_date_decreases": len(dec)}
out["replacement_witness_B_release_ordinal"] = {
    "market_archive_derived": False,
    "second_source_required": False,
    "covers_2021": True,
    "universe_clusters_witnessed": census(uni_ids),
    "universe_clusters_UNWITNESSED": census(set()),
    "regular_season_out_of_order_games": len(reg_anoms),
    "regular_season_anomalies": sorted(reg_anoms, key=lambda r: (r["season"], r["ordinal"])),
    "playoffs_excluded_structural": playoff_note,
    "what_it_can_and_cannot_show": (
        "CAN falsify: a game played out of its schedule-release order is the direct "
        "signature of a postponement/reschedule, and the test runs on every cluster "
        "including 2021.  CANNOT show: a reschedule that preserved the release ordering "
        "(moved a game inside its own gap), and it cannot by itself distinguish a "
        "postponement from a league-published out-of-order fixture."),
}

# --- 3b. attribute each adjacent decrease to the DISPLACED game, not its neighbour ---
# A game displaced by a reschedule is later (or earlier) than BOTH of its release-order
# neighbours.  This localises the mover instead of flagging whoever follows it.
movers = []
for (s, st), grp in seq.groupby(["season", "season_type"]):
    if st != "Regular Season":
        continue
    g2 = grp.sort_values("ordinal").reset_index(drop=True)
    for i in range(len(g2)):
        d = pd.Timestamp(g2.game_date[i])
        prev = pd.Timestamp(g2.game_date[i - 1]) if i > 0 else None
        nxt = pd.Timestamp(g2.game_date[i + 1]) if i + 1 < len(g2) else None
        if prev is None or nxt is None:
            continue
        if d > prev and d > nxt:
            movers.append({"game_id": g2.game_id[i], "season": int(s),
                           "ordinal": int(g2.ordinal[i]), "game_date": g2.game_date[i],
                           "direction": "played_LATE_relative_to_release_order",
                           "days_after_next_ordinal_game": int((d - nxt).days),
                           "neighbours": [g2.game_id[i - 1], g2.game_id[i + 1]]})
        elif d < prev and d < nxt:
            movers.append({"game_id": g2.game_id[i], "season": int(s),
                           "ordinal": int(g2.ordinal[i]), "game_date": g2.game_date[i],
                           "direction": "played_EARLY_relative_to_release_order",
                           "days_before_previous_ordinal_game": int((prev - d).days),
                           "neighbours": [g2.game_id[i - 1], g2.game_id[i + 1]]})
out["replacement_witness_B_release_ordinal"]["displaced_games_localised"] = sorted(
    movers, key=lambda r: (r["season"], r["ordinal"]))
out["replacement_witness_B_release_ordinal"]["n_displaced_games"] = len(movers)

# ============ 4. cross-check: does the barred archive's reschedule flag agree? =====
anom_ids = {a["game_id"] for a in reg_anoms} | {m["game_id"] for m in movers}
out["cross_check_alarm_probe_only"] = {
    "status": "ALARM_ONLY - the market archive may raise a flag, never clear one, and "
              "never contributes to promoting the field (S30 section 8 / P2B)",
    "market_flagged_n_commence_variants_gt_1": len(flagged),
    "release_ordinal_flagged": sorted(anom_ids),
    "intersection": sorted(anom_ids & set(flagged)),
    "market_flagged_not_ordinal_flagged": sorted(set(flagged) - anom_ids),
    "ordinal_flagged_not_market_flagged": sorted(anom_ids - set(flagged)),
}

# ============ 5. consequence measure: does an out-of-order game change lag sets? ===
# For each anomalous game, count universe games played between the two dates - those are
# the games a date rewrite would move in or out of a "strictly prior" filter.
all_dates = sorted(uni.game_date.tolist())
cons = []
for a in reg_anoms:
    lo, hi = sorted([a["game_date"], a["previous_ordinal_date"]])
    between = sum(1 for d in all_dates if lo < d < hi)
    cons.append({"game_id": a["game_id"], "window": [lo, hi],
                 "universe_games_inside_window": int(between)})
out["consequence_if_a_flagged_date_were_rewritten"] = cons

# ============ 6. exhaustive inventory of committed (game_id, date) artifacts ========
inv = []
for root, _d, files in os.walk(DATA):
    for fn in files:
        if not fn.lower().endswith((".parquet", ".csv")):
            continue
        p = os.path.join(root, fn)
        try:
            if fn.lower().endswith(".parquet"):
                cols = [c.lower() for c in pq.ParquetFile(p).schema.names]
            else:
                if os.path.getsize(p) > 60_000_000:
                    continue
                cols = [c.lower() for c in pd.read_csv(p, nrows=0).columns]
        except Exception:
            continue
        if ("game_id" in cols or "gameid" in cols) and \
                any(c in ("game_date", "gamedate", "date") for c in cols):
            inv.append(os.path.relpath(p, WORKTREE).replace("\\", "/"))
out["committed_artifacts_carrying_game_id_and_a_date"] = sorted(inv)

with open(os.path.join(HERE, "A1_DATE_WITNESS_RECEIPT.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)

brief = json.loads(json.dumps(out))
brief["s33_named_measurement_as_written"].pop("unwitnessed_game_ids")
brief["replacement_witness_A_shotchart_endpoint"].pop("unwitnessed_game_ids")
brief["reads"] = {"n_artifacts_hashed": len(out["reads"])}
print(json.dumps(brief, indent=1))
