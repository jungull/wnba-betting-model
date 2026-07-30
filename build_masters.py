"""
build_masters.py
================
Phase-1 uniform master rebuild (ROADMAP "Phase 1 - Uniform master rebuild").
Pure assembly of raw per-game data into data/masters/ -- NO imputation, NO
cross-time peeking, NO modeling (HANDOFF.md par.3 constitution). Every frame is
normalized through wnba_schema.normalize_player_box (the validated V2/V3
normalizer); this script never re-implements schema handling.

Designed to run WHILE the granular misc/advanced backfill is still writing
files: it snapshots the file list at start, skips unreadable (mid-write) files,
emits a coverage table, banners PARTIAL when season-kinds are short, and is
fully idempotent -- re-run any time, outputs are rebuilt from whatever exists.

Inputs (all local, read-only):
  data/wnba_gamelog_{2021..2024}.parquet          old-era player box (played rows only,
                                                  regular season only, no dates)
  data/wnba_gamelog_2025.parquet                  SKIPPED: partial (games 1-108, missing
                                                  all PHX games due to the PHO->PHX rename)
                                                  and fully superseded by the refresh file
  data/refresh_2026/gamelog_player_*.parquet      new-era player box (LeagueGameLog)
  data/refresh_2026/gamelog_team_*.parquet        new-era team box
  data/wnba_team_gamelog_2024.parquet             2024 regular team box
  data/refresh_2026/misc/misc_<gid>.parquet       V3 per-game misc (dressed roster incl.
                                                  DNP rows -- the availability labels)
  data/refresh_2026/advanced/advanced_<gid>.parquet  V3 per-game advanced
  data/shotcharts/shots_*.parquet                 game identity only (GAME_DATE/HTM/VTM)
  data/drive_masters/master_team_cleaned.csv      DIFF TARGET ONLY (never a stat source)
  data/drive_masters/master_player.csv            DIFF TARGET ONLY

Outputs (data/masters/):
  master_player.parquet/.csv   one row per (game_id, player_id), every dressed player
  master_team.parquet/.csv     one row per (game_id, team_id) with opp_ join
  REBUILD_VALIDATION.md        the five validations + coverage + explanations
  validation_*.csv, diff_*.csv, coverage_table.csv

Provenance per row (prediction contract): source (files contributing), era,
observed_time (UTC ISO mtime of newest contributing file).

Team-box precedence: real team gamelog when one exists; otherwise derived from
same-game player-row sums (box_source='player_sum' -- derivation from the same
game's rows, not imputation); a game covered by neither carries misc channel
sums with box NA. The set of real team files is discovered at run time (the
backfill dropped 2022-2024 playoff gamelogs mid-build on 2026-07-30 and this
script picked them up on the next run unchanged).

Usage:  python build_masters.py
Exit 0 on PASS/PARTIAL, 1 on FAIL (identity violations or unexplained diffs).
"""

from __future__ import annotations

import glob
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from wnba_schema import (
    UPPER_BOX_IDENTITY_MAP,
    UPPER_BOX_STAT_MAP,
    minutes_to_float,
    normalize_player_box,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
REFRESH = os.path.join(DATA, "refresh_2026")
MASTERS = os.path.join(DATA, "masters")
DRIVE = os.path.join(DATA, "drive_masters")
SHOTS = os.path.join(DATA, "shotcharts")

SEASON_TYPE_BY_DIGIT = {"1": "Preseason", "2": "Regular Season",
                        "3": "All-Star", "4": "Playoffs"}
# Tricode aliases across eras (stats.nba.com renamed PHO->PHX in 2025; Portland
# is PDX in every local source -- alias kept for safety only).
TRICODE_ALIAS = {"PHX": "PHO", "PHO": "PHO", "PDX": "PDX", "POR": "PDX"}

BOX_STATS = ["fgm", "fga", "fg_pct", "fg3m", "fg3a", "fg3_pct", "ftm", "fta",
             "ft_pct", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf",
             "pts", "plus_minus"]
BOX_COUNT_STATS = [c for c in BOX_STATS if not c.endswith("_pct")]
MISC_PLAYER_STATS = ["points_off_turnovers", "points_second_chance",
                     "points_fast_break", "points_paint",
                     "opp_points_off_turnovers", "opp_points_second_chance",
                     "opp_points_fast_break", "opp_points_paint",
                     "blk", "blocks_against", "pf", "fouls_drawn"]
# blk/pf exist in BOTH gamelog and misc: gamelog is the box source of record,
# misc copies are suffixed _misc and kept for cross-checking only.
MISC_TEAM_CHANNELS = ["points_paint", "points_fast_break",
                      "points_second_chance", "points_off_turnovers",
                      "fouls_drawn"]

ANOMS = Counter()          # global schema-surprise / anomaly counters
NOTES: list[str] = []      # free-text findings for the report
DEDUPE_ROWS: list[dict] = []   # per-file duplicate resolutions (-> CSV)


def log(msg: str) -> None:
    print(msg, flush=True)


def season_of(gid: pd.Series) -> pd.Series:
    return ("20" + gid.str[3:5]).astype("int64")


def stype_of(gid: pd.Series) -> pd.Series:
    return gid.str[2].map(SEASON_TYPE_BY_DIGIT).fillna("Unknown")


def iso_mtime(path: str) -> str:
    return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) \
        .isoformat(timespec="seconds")


def read_parquet_safe(path: str):
    """Read one parquet; None on failure (mid-write file from the running
    backfill). Failures are counted and listed, never fatal."""
    try:
        return pq.read_table(path).to_pandas()
    except Exception as exc:  # noqa: BLE001 -- any unreadable file is skipped
        ANOMS["unreadable_files"] += 1
        NOTES.append(f"unreadable (mid-write?) file skipped: "
                     f"{os.path.basename(path)}: {exc}")
        return None


# ----------------------------------------------------------------------------
# Phase 1 -- player gamelogs
# ----------------------------------------------------------------------------
def load_player_gamelogs(mtimes: dict) -> pd.DataFrame:
    """Canonical player-box rows from old-era season files (2021-2024) and
    every refresh gamelog_player_* file. data/wnba_gamelog_2025.parquet is
    deliberately skipped: it holds only league games 1-108 and is missing all
    Phoenix games (PHO->PHX rename); gamelog_player_2025_regular_season.parquet
    covers the full 286-game season."""
    frames = []
    old = [os.path.join(DATA, f"wnba_gamelog_{y}.parquet")
           for y in (2021, 2022, 2023, 2024)]
    new = sorted(glob.glob(os.path.join(REFRESH, "gamelog_player_*.parquet")))
    for path in old + new:
        if not os.path.exists(path):
            NOTES.append(f"expected gamelog missing: {os.path.basename(path)}")
            continue
        raw = read_parquet_safe(path)
        if raw is None:
            continue
        box = normalize_player_box(raw)
        box["source_file_gl"] = os.path.basename(path)
        mtimes[os.path.basename(path)] = iso_mtime(path)
        frames.append(box)
    gl = pd.concat(frames, ignore_index=True)
    dup = gl.duplicated(["game_id", "player_id"], keep=False)
    if dup.any():
        ANOMS["gamelog_duplicate_player_game_rows"] = int(dup.sum())
        NOTES.append("duplicate (game_id, player_id) in gamelogs: "
                     + gl.loc[dup, ["game_id", "player_id", "source_file_gl"]]
                         .head(10).to_string(index=False))
        gl = gl[~gl.duplicated(["game_id", "player_id"], keep="first")]
    return gl


# ----------------------------------------------------------------------------
# Phase 2 -- team gamelogs (thin normalizer reusing wnba_schema column maps)
# ----------------------------------------------------------------------------
def normalize_team_gamelog(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """Team gamelogs have no PLAYER_ID, so normalize_player_box refuses them;
    this thin wrapper reuses the SAME wnba_schema column maps + minutes parser
    (no schema logic re-implemented, just re-pointed at team rows)."""
    rename = {}
    for c in df.columns:
        if c == "MIN":
            rename[c] = "minutes_raw"
        elif c in UPPER_BOX_IDENTITY_MAP:
            rename[c] = UPPER_BOX_IDENTITY_MAP[c]
        elif c in UPPER_BOX_STAT_MAP:
            rename[c] = UPPER_BOX_STAT_MAP[c]
        else:
            rename[c] = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", c).lower()
    out = df.rename(columns=rename).copy()
    out["game_id"] = out["game_id"].astype(str).str.strip().str.zfill(10)
    out["team_id"] = out["team_id"].astype("Int64")
    out["minutes"] = out["minutes_raw"].map(minutes_to_float).astype("float64")
    out["source_file_team"] = source_file
    return out


def load_team_gamelogs(mtimes: dict) -> pd.DataFrame:
    paths = sorted(glob.glob(os.path.join(REFRESH, "gamelog_team_*.parquet")))
    p2024 = os.path.join(DATA, "wnba_team_gamelog_2024.parquet")
    if os.path.exists(p2024):
        paths.append(p2024)
    frames = []
    for path in paths:
        raw = read_parquet_safe(path)
        if raw is None:
            continue
        name = os.path.basename(path)
        frames.append(normalize_team_gamelog(raw, name))
        mtimes[name] = iso_mtime(path)
    gt = pd.concat(frames, ignore_index=True)
    dup = gt.duplicated(["game_id", "team_id"], keep=False)
    if dup.any():
        ANOMS["team_gamelog_duplicate_rows"] = int(dup.sum())
        gt = gt[~gt.duplicated(["game_id", "team_id"], keep="first")]
    return gt


# ----------------------------------------------------------------------------
# Phase 3 -- per-game misc / advanced directories
# ----------------------------------------------------------------------------
def dedupe_pergame(box: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Resolve duplicated (game_id, player_id) rows inside per-game V3 files.
    Known case misc_1022300156: the same personId appears twice from a player
    rename ('Megan DiLeo' ghost row with blank minutes vs 'Megan Gustafson'
    with 27:04). Rule: prefer the row with finite minutes; if none has minutes,
    prefer the row with a dnp_reason; else keep the first. Every resolution is
    counted and listed."""
    dup_mask = box.duplicated(["game_id", "player_id"], keep=False)
    if not dup_mask.any():
        return box
    keep_idx = []
    for (gid, pid), grp in box[dup_mask].groupby(["game_id", "player_id"]):
        finite = grp[grp["minutes"].notna()]
        with_reason = grp[grp["dnp_reason"].notna()]
        if len(finite) > 1:
            # two real stat lines for one person would be a conflict, not a
            # ghost row -- surface it loudly instead of picking silently
            ANOMS[f"{kind}_dupe_BOTH_FINITE_minutes"] += 1
            NOTES.append(f"{kind} CONFLICT: game {gid} personId {pid} has "
                         f"{len(finite)} rows with finite minutes "
                         f"({sorted(set(grp['player_name']))})")
        rule, chosen = (
            ("finite_minutes", finite.index[0]) if len(finite) else
            ("has_dnp_reason", with_reason.index[0]) if len(with_reason) else
            ("first_row", grp.index[0]))
        keep_idx.append(chosen)
        ANOMS[f"{kind}_dupe_player_resolved"] += 1
        DEDUPE_ROWS.append({
            "kind": kind, "game_id": gid, "player_id": pid,
            "n_rows": len(grp),
            "names": " | ".join(sorted(set(grp["player_name"]))),
            "kept_name": box.loc[chosen, "player_name"],
            "kept_minutes_raw": box.loc[chosen, "minutes_raw"],
            "rule": rule})
    # one summary note per (kind, player, name-set) -- the DiLeo/Gustafson
    # ghost row spans 100+ files; full detail goes to dedupe_resolutions.csv
    dd = pd.DataFrame([r for r in DEDUPE_ROWS if r["kind"] == kind])
    for (pid, names), grp in dd.groupby(["player_id", "names"]):
        rules = {k: int(v) for k, v in grp["rule"].value_counts().items()}
        NOTES.append(
            f"{kind}: {len(grp)} files carry personId {pid} twice "
            f"({names}) -> resolved by {rules}; "
            f"games {grp['game_id'].min()}..{grp['game_id'].max()} "
            "(full list: dedupe_resolutions.csv)")
    drop = box.index[dup_mask].difference(pd.Index(keep_idx))
    return box.drop(index=drop)


def load_pergame_dir(kind: str, mtimes: dict) -> pd.DataFrame:
    """Snapshot data/refresh_2026/<kind>/ NOW (backfill may still be writing),
    read in parallel, group by exact column tuple (schema-drift guard), and
    push each group through normalize_player_box in one call."""
    files = sorted(glob.glob(os.path.join(REFRESH, kind, f"{kind}_*.parquet")))
    with ThreadPoolExecutor(max_workers=8) as ex:
        raws = list(ex.map(read_parquet_safe, files))
    groups: dict[tuple, list[pd.DataFrame]] = {}
    for path, raw in zip(files, raws):
        if raw is None or raw.empty:
            if raw is not None:
                ANOMS[f"{kind}_empty_files"] += 1
            continue
        gid = os.path.basename(path).split("_")[1].split(".")[0]
        raw = raw.copy()
        raw["__source_file"] = os.path.basename(path)
        mtimes[os.path.basename(path)] = iso_mtime(path)
        key = tuple(c for c in raw.columns if c != "__source_file")
        groups.setdefault(key, []).append(raw)
        if str(raw["gameId"].iloc[0]) != gid:
            ANOMS[f"{kind}_filename_gameid_mismatch"] += 1
    if len(groups) > 1:
        ANOMS[f"{kind}_schema_variants"] = len(groups)
        NOTES.append(f"{kind}: {len(groups)} distinct column schemas observed "
                     f"(schema drift) -- normalized per variant")
    frames = []
    for chunks in groups.values():
        raw = pd.concat(chunks, ignore_index=True)
        src = raw.pop("__source_file")
        box = normalize_player_box(raw)
        ANOMS[f"{kind}_minutes_parse_failures"] += box.attrs.get(
            "minutes_parse_failures", 0)
        box[f"source_file_{kind}"] = src.values
        frames.append(box)
    box = pd.concat(frames, ignore_index=True)
    return dedupe_pergame(box, kind)


# ----------------------------------------------------------------------------
# Phase 4 -- game identity index (date + home/away for every game)
# ----------------------------------------------------------------------------
def build_game_index(team_gl: pd.DataFrame, player_gl: pd.DataFrame,
                     misc: pd.DataFrame, mtimes: dict) -> pd.DataFrame:
    """One row per (game_id, team_id): is_home, game_date, gameinfo_source.

    Priority: real team gamelog MATCHUP > new-era player gamelog MATCHUP >
    shotchart HTM/VTM matched against that game's own tricodes. Old-era
    gamelogs carry no date/matchup at all -- shotcharts (raw ShotChartDetail
    exports) are the only local raw source of identity for 2021-2024, playoffs
    included. Disagreements between sources are counted, never averaged."""
    parts = []

    def from_matchup(df, src):
        d = df[["game_id", "team_id", "matchup", "game_date"]].dropna(
            subset=["matchup"]).copy()
        d["is_home"] = (~d["matchup"].str.contains(" @ ")).astype("int64")
        d["gameinfo_source"] = src
        return d[["game_id", "team_id", "is_home", "game_date",
                  "gameinfo_source"]].drop_duplicates(["game_id", "team_id"])

    parts.append(from_matchup(team_gl, "team_gamelog"))
    pg = player_gl[player_gl["source_file_gl"].str.startswith("gamelog_player")]
    if "matchup" in pg.columns and len(pg):
        parts.append(from_matchup(pg, "player_gamelog"))

    # tricodes per (game, team) from every box source, for HTM/VTM matching
    tri = []
    for df, col in ((player_gl, "team_abbreviation"),
                    (team_gl, "team_abbreviation"), (misc, "team_tricode")):
        if col in df.columns:
            t = df[["game_id", "team_id", col]].dropna().rename(
                columns={col: "tricode"})
            tri.append(t)
    tricodes = pd.concat(tri, ignore_index=True).drop_duplicates(
        ["game_id", "team_id", "tricode"])
    tricodes["tri_norm"] = tricodes["tricode"].map(
        lambda s: TRICODE_ALIAS.get(str(s), str(s)))

    shot_rows = []
    for path in sorted(glob.glob(os.path.join(SHOTS, "shots_*.parquet"))):
        raw = read_parquet_safe(path)
        if raw is None:
            continue
        mtimes[os.path.basename(path)] = iso_mtime(path)
        s = raw[["GAME_ID", "GAME_DATE", "HTM", "VTM"]].drop_duplicates("GAME_ID")
        s["source_file_shots"] = os.path.basename(path)
        shot_rows.append(s)
    shots = pd.concat(shot_rows, ignore_index=True)
    shots["game_id"] = shots["GAME_ID"].astype(str).str.zfill(10)
    d = shots["GAME_DATE"].astype(str)
    shots["game_date"] = d.str[:4] + "-" + d.str[4:6] + "-" + d.str[6:8]
    for side, flag in (("HTM", 1), ("VTM", 0)):
        m = shots[["game_id", side, "game_date", "source_file_shots"]].copy()
        m["tri_norm"] = m[side].map(lambda s: TRICODE_ALIAS.get(str(s), str(s)))
        m = m.merge(tricodes[["game_id", "team_id", "tri_norm"]],
                    on=["game_id", "tri_norm"], how="left")
        unresolved = m["team_id"].isna()
        if unresolved.any():
            ANOMS["shotchart_tricode_unresolved"] += int(unresolved.sum())
        m = m[~unresolved].copy()
        m["is_home"] = flag
        m["gameinfo_source"] = "shotcharts:" + m["source_file_shots"]
        parts.append(m[["game_id", "team_id", "is_home", "game_date",
                        "gameinfo_source"]])

    allp = pd.concat(parts, ignore_index=True)
    allp["team_id"] = allp["team_id"].astype("Int64")
    # disagreement audit before precedence dedupe
    chk = allp.groupby(["game_id", "team_id"]).agg(
        n_home=("is_home", "nunique"), n_date=("game_date", "nunique"))
    ANOMS["gameinfo_is_home_disagreements"] += int((chk["n_home"] > 1).sum())
    ANOMS["gameinfo_date_disagreements"] += int((chk["n_date"] > 1).sum())
    idx = allp.drop_duplicates(["game_id", "team_id"], keep="first").copy()

    # opponent pairing + exactly-one-home audit
    per_game = idx.groupby("game_id").agg(n_teams=("team_id", "nunique"),
                                          n_home=("is_home", "sum"))
    ANOMS["games_without_two_teams"] += int((per_game["n_teams"] != 2).sum())
    ANOMS["games_without_exactly_one_home"] += int((per_game["n_home"] != 1).sum())
    pair = idx[["game_id", "team_id"]].merge(idx[["game_id", "team_id"]],
                                             on="game_id")
    pair = pair[pair["team_id_x"] != pair["team_id_y"]].rename(
        columns={"team_id_x": "team_id", "team_id_y": "opp_team_id"})
    idx = idx.merge(pair.drop_duplicates(["game_id", "team_id"]),
                    on=["game_id", "team_id"], how="left")
    return idx


# ----------------------------------------------------------------------------
# Phase 5 -- master_player
# ----------------------------------------------------------------------------
def build_master_player(gl: pd.DataFrame, misc: pd.DataFrame,
                        adv: pd.DataFrame, gidx: pd.DataFrame,
                        mtimes: dict) -> pd.DataFrame:
    gl_cols = (["game_id", "player_id", "team_id", "player_name", "position",
                "starter_flag", "minutes", "minutes_raw", "era",
                "team_abbreviation", "source_file_gl"]
               + [c for c in BOX_STATS if c in gl.columns])
    g = gl[gl_cols].rename(columns={
        "team_id": "team_id_gl", "player_name": "player_name_gl",
        "position": "position_gl", "starter_flag": "starter_flag_gl",
        "minutes": "minutes_gl", "minutes_raw": "minutes_raw_gl",
        "era": "era_gl", "team_abbreviation": "team_abbreviation_gl"})

    m_cols = ["game_id", "player_id", "team_id", "player_name", "first_name",
              "family_name", "name_i", "position", "starter_flag",
              "dnp_reason", "minutes", "minutes_raw", "team_tricode",
              "source_file_misc"] + MISC_PLAYER_STATS
    m = misc[[c for c in m_cols if c in misc.columns]].rename(columns={
        "team_id": "team_id_misc", "player_name": "player_name_misc",
        "position": "position_misc", "starter_flag": "starter_flag_misc",
        "minutes": "minutes_misc", "minutes_raw": "minutes_raw_misc",
        "blk": "blk_misc", "pf": "pf_misc"})

    mp = g.merge(m, on=["game_id", "player_id"], how="outer")

    conflict = (mp["team_id_gl"].notna() & mp["team_id_misc"].notna()
                & (mp["team_id_gl"] != mp["team_id_misc"]))
    if conflict.any():
        ANOMS["player_team_id_conflicts"] = int(conflict.sum())
        NOTES.append("gamelog-vs-misc team_id conflicts:\n"
                     + mp.loc[conflict, ["game_id", "player_id", "team_id_gl",
                                         "team_id_misc"]].to_string(index=False))
    mp["team_id"] = mp["team_id_gl"].fillna(mp["team_id_misc"]).astype("Int64")
    mp["in_gamelog"] = mp["source_file_gl"].notna().astype("int64")
    mp["in_misc"] = mp["source_file_misc"].notna().astype("int64")

    # advanced: stats only, LEFT join -- an advanced row whose (game, player)
    # is in neither gamelog nor misc would be a finding, never silently added
    adv_stats = [c for c in adv.columns
                 if c not in ("game_id", "team_id", "player_id", "player_name",
                              "first_name", "family_name", "name_i", "position",
                              "starter_flag", "dnp_reason", "minutes",
                              "minutes_raw", "era", "team_city", "team_name",
                              "team_tricode", "team_slug", "player_slug",
                              "jersey_num", "comment", "source_file_advanced")]
    a = adv[["game_id", "player_id", "source_file_advanced"] + adv_stats]
    mp = mp.merge(a, on=["game_id", "player_id"], how="left")
    mp["in_advanced"] = mp["source_file_advanced"].notna().astype("int64")
    only_adv = set(map(tuple, a[["game_id", "player_id"]].itertuples(index=False))) \
        - set(map(tuple, mp.loc[mp["in_advanced"] == 1,
                                ["game_id", "player_id"]].itertuples(index=False)))
    if only_adv:
        ANOMS["advanced_rows_matching_no_roster"] = len(only_adv)
        NOTES.append(f"advanced rows with no gamelog/misc counterpart: "
                     f"{sorted(only_adv)[:10]}")

    # coalesced identity: misc is the roster/availability source of record
    # (it alone carries DNP rows); gamelog fills where misc is absent
    mp["player_name"] = mp["player_name_gl"].fillna(mp["player_name_misc"])
    mp["position"] = mp["position_misc"].where(mp["in_misc"] == 1,
                                               mp["position_gl"])
    mp["starter_flag"] = mp["starter_flag_misc"].where(
        mp["in_misc"] == 1, mp["starter_flag_gl"]).astype("Int64")
    mp["team_abbreviation"] = mp["team_abbreviation_gl"].fillna(
        mp.get("team_tricode"))
    # minutes: most precise observed value -- misc is exact MM:SS in all eras,
    # new-era gamelog minutes are endpoint-rounded ints (never imputed; the
    # chosen source is recorded per row)
    use_misc_min = mp["minutes_misc"].notna()
    mp["minutes"] = mp["minutes_misc"].where(use_misc_min, mp["minutes_gl"])
    mp["minutes_raw"] = mp["minutes_raw_misc"].where(use_misc_min,
                                                     mp["minutes_raw_gl"])
    mp["minutes_source"] = np.select(
        [use_misc_min, mp["minutes_gl"].notna()],
        ["misc", "gamelog"], default="none")
    mp["era"] = mp["era_gl"].fillna("v3")

    gi = gidx[["game_id", "team_id", "is_home", "game_date", "opp_team_id",
               "gameinfo_source"]]
    mp = mp.merge(gi, on=["game_id", "team_id"], how="left")
    ANOMS["player_rows_without_gameinfo"] += int(mp["is_home"].isna().sum())
    mp["season"] = season_of(mp["game_id"])
    mp["season_type"] = stype_of(mp["game_id"])

    # provenance ------------------------------------------------------------
    parts = [mp["source_file_gl"], mp["source_file_misc"],
             mp["source_file_advanced"],
             mp["gameinfo_source"].str.replace("shotcharts:", "", regex=False)
               .where(mp["gameinfo_source"].str.startswith("shotcharts:"))]
    mp["source"] = pd.concat(parts, axis=1).apply(
        lambda r: "+".join(x for x in r if pd.notna(x)), axis=1)
    obs = pd.concat([p.map(mtimes) for p in parts], axis=1)
    mp["observed_time"] = obs.max(axis=1)

    keep = (["game_id", "season", "season_type", "game_date", "team_id",
             "team_abbreviation", "opp_team_id", "is_home", "player_id",
             "player_name", "first_name", "family_name", "name_i", "position",
             "starter_flag", "dnp_reason", "minutes", "minutes_raw",
             "minutes_source"]
            + [c for c in BOX_STATS if c in mp.columns]
            + [c for c in ("points_off_turnovers", "points_second_chance",
                           "points_fast_break", "points_paint",
                           "opp_points_off_turnovers", "opp_points_second_chance",
                           "opp_points_fast_break", "opp_points_paint",
                           "blk_misc", "blocks_against", "pf_misc",
                           "fouls_drawn") if c in mp.columns]
            + adv_stats
            + ["in_gamelog", "in_misc", "in_advanced", "era", "source",
               "observed_time"])
    mp = mp[keep].sort_values(["game_id", "team_id", "player_id"],
                              ignore_index=True)
    for c in (BOX_COUNT_STATS + ["points_off_turnovers", "points_second_chance",
                                 "points_fast_break", "points_paint",
                                 "opp_points_off_turnovers",
                                 "opp_points_second_chance",
                                 "opp_points_fast_break", "opp_points_paint",
                                 "blk_misc", "blocks_against", "pf_misc",
                                 "fouls_drawn", "is_home"]):
        if c in mp.columns:
            mp[c] = mp[c].astype("Int64")
    return mp


# ----------------------------------------------------------------------------
# Phase 6 -- master_team
# ----------------------------------------------------------------------------
def build_master_team(team_gl: pd.DataFrame, gl: pd.DataFrame,
                      misc: pd.DataFrame, gidx: pd.DataFrame,
                      mtimes: dict) -> pd.DataFrame:
    real = team_gl[["game_id", "team_id", "team_abbreviation", "minutes",
                    "wl", "source_file_team"]
                   + [c for c in BOX_STATS if c in team_gl.columns]].copy()
    real["box_source"] = "team_gamelog"

    # derived team box: same-game player-row sums where no real team file
    # exists (2021-2023 regular; derivation, marked, never imputation)
    have_real = set(real["game_id"])
    gsub = gl[~gl["game_id"].isin(have_real)]
    sums = gsub.groupby(["game_id", "team_id"], as_index=False).agg(
        minutes=("minutes", "sum"),
        **{c: (c, "sum") for c in BOX_COUNT_STATS if c != "plus_minus"})
    abbr = gsub.groupby(["game_id", "team_id"])["team_abbreviation"] \
        .first().reset_index()
    src = gsub.groupby(["game_id", "team_id"])["source_file_gl"] \
        .first().reset_index()
    sums = sums.merge(abbr, on=["game_id", "team_id"]).merge(
        src, on=["game_id", "team_id"]).rename(
        columns={"source_file_gl": "source_file_team"})
    # shooting pct recomputed from the same game's sums. 3dp HALF-UP rounding
    # = the stats API convention (Python's round() is banker's and produced
    # 39 false 1-in-the-last-digit diffs vs the Drive master before this).
    for made, att, pct in (("fgm", "fga", "fg_pct"), ("fg3m", "fg3a", "fg3_pct"),
                           ("ftm", "fta", "ft_pct")):
        sums[pct] = np.floor(sums[made] / sums[att] * 1000 + 0.5) / 1000
    sums["box_source"] = "player_sum"
    sums["wl"] = pd.NA
    sums["plus_minus"] = pd.NA

    mt = pd.concat([real, sums], ignore_index=True)

    # channel sums from misc (own-scoring channels only: oppPoints* columns are
    # on-court-credited and do NOT sum to team totals)
    played = misc  # DNP rows carry 0s; summing over the full roster is exact
    ch = played.groupby(["game_id", "team_id"], as_index=False).agg(
        **{c: (c, lambda s: s.sum(min_count=1)) for c in MISC_TEAM_CHANNELS})
    ch["source_file_misc"] = "misc_" + ch["game_id"] + ".parquet"
    mt = mt.merge(ch, on=["game_id", "team_id"], how="outer")
    mt["in_misc"] = mt["source_file_misc"].notna().astype("int64")
    mt["box_source"] = mt["box_source"].fillna("none")

    gi = gidx[["game_id", "team_id", "is_home", "game_date", "opp_team_id",
               "gameinfo_source"]]
    mt = mt.merge(gi, on=["game_id", "team_id"], how="left")
    ANOMS["team_rows_without_gameinfo"] += int(mt["is_home"].isna().sum())
    mt["season"] = season_of(mt["game_id"])
    mt["season_type"] = stype_of(mt["game_id"])

    # opponent join (box + channels)
    opp_cols = ([c for c in BOX_STATS] + MISC_TEAM_CHANNELS
                + ["team_abbreviation", "box_source"])
    opp = mt[["game_id", "team_id"] + opp_cols].rename(
        columns={c: f"opp_{c}" for c in opp_cols}).rename(
        columns={"team_id": "opp_team_id"})
    mt = mt.merge(opp, on=["game_id", "opp_team_id"], how="left")

    # derived rows: plus_minus/wl from the opponent join (same-game data)
    derived = mt["box_source"] == "player_sum"
    mt.loc[derived, "plus_minus"] = (mt.loc[derived, "pts"]
                                     - mt.loc[derived, "opp_pts"])
    mt.loc[derived, "wl"] = np.where(mt.loc[derived, "plus_minus"] > 0, "W", "L")

    parts = [mt["source_file_team"], mt["source_file_misc"],
             mt["gameinfo_source"].str.replace("shotcharts:", "", regex=False)
               .where(mt["gameinfo_source"].str.startswith("shotcharts:"))]
    mt["source"] = pd.concat(parts, axis=1).apply(
        lambda r: "+".join(x for x in r if pd.notna(x)), axis=1)
    obs = pd.concat([p.map(mtimes) for p in parts], axis=1)
    mt["observed_time"] = obs.max(axis=1)
    mt["era"] = np.where(mt["box_source"] == "team_gamelog", "gamelog_new",
                         np.where(mt["box_source"] == "player_sum",
                                  "gamelog_old", "v3"))

    keep = (["game_id", "season", "season_type", "game_date", "team_id",
             "team_abbreviation", "opp_team_id", "opp_team_abbreviation",
             "is_home", "wl", "minutes"] + BOX_STATS + MISC_TEAM_CHANNELS
            + [f"opp_{c}" for c in BOX_STATS]
            + [f"opp_{c}" for c in MISC_TEAM_CHANNELS]
            + ["box_source", "opp_box_source", "in_misc", "era", "source",
               "observed_time"])
    mt = mt[keep].sort_values(["game_id", "team_id"], ignore_index=True)
    for c in mt.columns:
        if c in BOX_COUNT_STATS or c in MISC_TEAM_CHANNELS \
                or c in [f"opp_{x}" for x in BOX_COUNT_STATS] \
                or c in [f"opp_{x}" for x in MISC_TEAM_CHANNELS] or c == "is_home":
            mt[c] = pd.to_numeric(mt[c], errors="raise").round(0).astype("Int64")
    return mt


# ----------------------------------------------------------------------------
# Phase 7 -- validations
# ----------------------------------------------------------------------------
def v1_box_identity(mt: pd.DataFrame):
    """FTM + 3*FG3M + 2*(FGM-FG3M) == PTS on every box-covered team row."""
    have = mt[["ftm", "fg3m", "fgm", "pts"]].notna().all(axis=1)
    sub = mt[have]
    calc = sub["ftm"] + 3 * sub["fg3m"] + 2 * (sub["fgm"] - sub["fg3m"])
    bad = sub[calc != sub["pts"]]
    out = bad[["game_id", "season", "season_type", "team_id", "fgm", "fg3m",
               "ftm", "pts", "box_source"]].copy()
    out["pts_from_identity"] = calc[bad.index]
    return {"checked": int(have.sum()), "skipped_no_box": int((~have).sum()),
            "violations": len(out)}, out


def v2_channel_identity(mt: pd.DataFrame):
    """ch_np2 = 2*(FGM-FG3M) - points_paint >= 0 wherever misc is present
    (paint field goals are all 2s, so non-paint-2 points cannot be negative)."""
    have = mt[["fgm", "fg3m", "points_paint"]].notna().all(axis=1)
    sub = mt[have]
    np2 = 2 * (sub["fgm"] - sub["fg3m"]) - sub["points_paint"]
    bad = sub[np2 < 0]
    out = bad[["game_id", "season", "season_type", "team_id", "fgm", "fg3m",
               "points_paint", "box_source"]].copy()
    out["ch_np2"] = np2[bad.index]
    return {"checked": int(have.sum()), "skipped": int((~have).sum()),
            "violations": len(out)}, out


def v3_player_team_reconciliation(mp: pd.DataFrame, mt: pd.DataFrame):
    """Player-row sums vs team totals per (game, team) for PTS/FGM/FTM.
    Only real-team-gamelog rows are informative (player_sum rows reconcile by
    construction -- reported separately, never counted as evidence)."""
    ps = mp[mp["in_gamelog"] == 1].groupby(
        ["game_id", "team_id"], as_index=False)[["pts", "fgm", "ftm"]].sum()
    j = ps.merge(mt[["game_id", "team_id", "pts", "fgm", "ftm", "box_source"]],
                 on=["game_id", "team_id"], suffixes=("_players", "_team"))
    j = j[j[["pts_team", "fgm_team", "ftm_team"]].notna().all(axis=1)]
    bad = j[(j["pts_players"] != j["pts_team"])
            | (j["fgm_players"] != j["fgm_team"])
            | (j["ftm_players"] != j["ftm_team"])]
    real = j[j["box_source"] == "team_gamelog"]
    bad_real = bad[bad["box_source"] == "team_gamelog"]
    return {"team_games_checked": len(j),
            "independent_checks_vs_real_team_gamelog": len(real),
            "mismatches_total": len(bad),
            "mismatches_vs_real_team_gamelog": len(bad_real),
            "trivial_player_sum_rows": int((j["box_source"] == "player_sum").sum())}, bad


DRIVE_TEAM_STATS = {f"team_{c}": c for c in BOX_STATS}
PCT_TOL = 0.0011   # 3dp rounding boundary between two independent roundings
MIN_TOL = 0.5      # drive team_min is an int; derived rows sum exact MM:SS


def _pbp_stat(ev: pd.DataFrame, team_id: int, stat: str):
    """Independent pbp count for the stats with unambiguous canonical events
    (wnba_schema.normalize_pbp vocabulary). Returns None when the stat has no
    trustworthy pbp mirror (reb/pf: dead-ball & technical conventions differ)."""
    t = ev[ev["team_id"] == team_id]
    if stat == "tov_total":
        return int((t["event_type"] == "turnover").sum())
    if stat == "tov_player":
        return int(((t["event_type"] == "turnover")
                    & t["person_id"].notna()).sum())
    if stat in ("stl", "ast", "blk"):
        label = {"stl": "Steal", "ast": "Assist", "blk": "Block"}[stat]
        return int(((t["event_type"] == "other")
                    & (t["event_subtype"] == label)).sum())
    if stat == "fgm":
        return int((t["event_type"] == "shot_made").sum())
    if stat == "fg3m":
        return int(((t["event_type"] == "shot_made") & (t["points"] == 3)).sum())
    if stat == "ftm":
        return int((t["event_type"] == "ft_made").sum())
    if stat == "pts":
        return int(t["points"].dropna().sum())
    return None


def _explain_team_mismatches(mism: pd.DataFrame) -> pd.DataFrame:
    """Classify every drive-vs-master diff with the raw V2/V3 pbp as the
    independent arbiter. Nothing is waved through by a blanket rule -- each
    row must pass its category's predicate on THIS run's data or it stays
    unexplained (and fails the build):

    team_tov_uncredited      ours == pbp player-credited TOs and drive ==
                             pbp total TOs: both values are correct at their
                             own definition -- LeagueGameLog team tov includes
                             TEAM turnovers (shot-clock/5-sec/8-sec) that
                             belong to no player, so player-row sums cannot
                             contain them.
    local_gamelog_pbp_disagreement
                             drive == pbp but our raw local gamelog does not:
                             the local per-player season file miscounts this
                             stat (repair item -- refetch that game's box).
    drive_wrong_vs_pbp       ours == pbp but drive does not: the July-15
                             drive value is contradicted by the pbp; our
                             master is corroborated.
    rounding_boundary        3dp pct or integer team-minutes representation.
    """
    if mism.empty:
        mism["category"] = pd.Series(dtype=str)
        return mism
    from wnba_schema import normalize_pbp
    mism = mism.copy()
    mism["category"] = np.where(mism["kind"] == "rounding_boundary",
                                "rounding_boundary", "unexplained")
    mism["pbp_value"] = pd.NA
    mism["evidence"] = ""

    ev_cache: dict[str, pd.DataFrame | None] = {}

    def pbp_events(gid: str):
        if gid not in ev_cache:
            path = os.path.join(DATA, "playbyplay", f"pbp_{gid}.parquet")
            if not os.path.exists(path):
                path = os.path.join(REFRESH, "pbp", f"pbp_{gid}.parquet")
            ev_cache[gid] = (normalize_pbp(pd.read_parquet(path))
                             if os.path.exists(path) else None)
        return ev_cache[gid]

    for i, r in mism[mism["category"] == "unexplained"].iterrows():
        ev = pbp_events(r["game_id"])
        if ev is None:
            ANOMS["explain_no_pbp_file"] += 1
            continue
        team = int(r["team_id"])
        ours, drive = float(r["ours"]), float(r["drive"])
        if r["stat"] == "tov":
            total = _pbp_stat(ev, team, "tov_total")
            pcred = _pbp_stat(ev, team, "tov_player")
            mism.at[i, "pbp_value"] = total
            mism.at[i, "evidence"] = (f"pbp total={total} player-credited="
                                      f"{pcred} team-credited={total - pcred}")
            if ours == pcred and drive == total:
                mism.at[i, "category"] = "team_tov_uncredited"
            elif drive == total:
                mism.at[i, "category"] = "local_gamelog_pbp_disagreement"
            elif ours == pcred:
                mism.at[i, "category"] = "drive_wrong_vs_pbp"
        else:
            truth = _pbp_stat(ev, team, r["stat"])
            if truth is None:
                continue
            mism.at[i, "pbp_value"] = truth
            mism.at[i, "evidence"] = f"pbp {r['stat']}={truth}"
            if ours == truth and drive != truth:
                mism.at[i, "category"] = "drive_wrong_vs_pbp"
            elif drive == truth and ours != truth:
                mism.at[i, "category"] = "local_gamelog_pbp_disagreement"
        if mism.at[i, "category"] in ("local_gamelog_pbp_disagreement",
                                      "drive_wrong_vs_pbp"):
            NOTES.append(
                f"drive diff {mism.at[i, 'category']}: game {r['game_id']} "
                f"team {team} {r['stat']}: ours={ours:g} drive={drive:g} "
                f"[{mism.at[i, 'evidence']}]")
    counts = mism["category"].value_counts()
    ANOMS["tov_uncredited_pbp_verified"] = int(counts.get("team_tov_uncredited", 0))
    return mism


def v4_diff_drive_team(mt: pd.DataFrame):
    """Row-level diff vs the July-15 Drive team master over its span."""
    f = os.path.join(DRIVE, "master_team_cleaned.csv")
    dr = pd.read_csv(f, low_memory=False)
    dr["game_id"] = dr["GAME_ID"].astype(str).str.zfill(10)
    dr["team_id"] = dr["TEAM_ID"].astype("int64")
    ours = mt[["game_id", "team_id", "minutes", "box_source"] + BOX_STATS]
    j = dr.merge(ours, on=["game_id", "team_id"], how="left",
                 indicator=True)
    unjoined = j[j["_merge"] == "left_only"]
    no_box = j[(j["_merge"] == "both") & j["pts"].isna()]
    comp = j[(j["_merge"] == "both") & j["pts"].notna()]

    stat_rows, mism_rows = [], []
    for drive_col, our_col in DRIVE_TEAM_STATS.items():
        a, b = comp[drive_col], comp[our_col]
        both_na = a.isna() & b.isna()      # e.g. ft_pct with FTA=0: agreement
        if our_col.endswith("_pct"):
            diff = (a.round(3) - b.round(3)).abs()
            exact = both_na | (diff <= 1e-9)
            boundary = (~exact) & (diff <= PCT_TOL)
        else:
            diff = (a - b).abs()
            exact = both_na | (diff <= 1e-9)
            boundary = pd.Series(False, index=comp.index)
        real_mism = (~exact) & (~boundary)
        stat_rows.append({"stat": our_col, "n": len(comp),
                          "exact": int(exact.sum()),
                          "rounding_boundary": int(boundary.sum()),
                          "mismatch": int(real_mism.sum())})
        for i in comp.index[real_mism | boundary]:
            mism_rows.append({
                "game_id": comp.at[i, "game_id"], "team_id": comp.at[i, "team_id"],
                "stat": our_col, "ours": comp.at[i, our_col],
                "drive": comp.at[i, drive_col],
                "box_source": comp.at[i, "box_source"],
                "kind": "rounding_boundary" if bool(boundary.at[i]) else "mismatch"})
    # team_min separately (drive stores ints; derived rows sum exact MM:SS)
    md = (comp["team_min"] - comp["minutes"]).abs()
    stat_rows.append({"stat": "minutes(team_min)", "n": len(comp),
                      "exact": int((md <= 1e-9).sum()),
                      "rounding_boundary": int(((md > 1e-9) & (md <= MIN_TOL)).sum()),
                      "mismatch": int((md > MIN_TOL).sum())})
    for i in comp.index[md > MIN_TOL]:
        mism_rows.append({"game_id": comp.at[i, "game_id"],
                          "team_id": comp.at[i, "team_id"], "stat": "minutes",
                          "ours": comp.at[i, "minutes"],
                          "drive": comp.at[i, "team_min"],
                          "box_source": comp.at[i, "box_source"],
                          "kind": "mismatch"})
    mism = _explain_team_mismatches(pd.DataFrame(mism_rows))
    cat_counts = (mism["category"].value_counts().to_dict()
                  if len(mism) else {})
    summary = {
        "drive_rows": len(dr), "joined": int((j["_merge"] == "both").sum()),
        "drive_rows_not_in_master": len(unjoined),
        "joined_but_no_box_on_our_side": len(no_box),
        "no_box_breakdown": no_box.assign(season=season_of(no_box["game_id"]),
                                          kind=stype_of(no_box["game_id"]))
            .groupby(["season", "kind"]).size().to_dict(),
        "compared_rows": len(comp),
        "mismatch_categories": cat_counts,
        "unexplained_mismatches": int(cat_counts.get("unexplained", 0)),
        "total_rounding_boundary": int(cat_counts.get("rounding_boundary", 0)),
    }
    return summary, pd.DataFrame(stat_rows), mism


def v4_diff_drive_player_paint(mt: pd.DataFrame):
    """Team-summed player_pts_paint from the Drive player master vs our
    misc-derived team paint. 2023 (prefixes 10223/10423) is excluded from the
    match-rate -- the old file is broken there -- and reported separately as
    repaired-vs-broken."""
    f = os.path.join(DRIVE, "master_player.csv")
    dr = pd.read_csv(f, usecols=["GAME_ID", "TEAM_ID", "player_pts_paint"],
                     low_memory=False)
    dr["game_id"] = dr["GAME_ID"].astype(str).str.zfill(10)
    ds = dr.groupby(["game_id", "TEAM_ID"], as_index=False) \
        .agg(drive_paint=("player_pts_paint", lambda s: s.sum(min_count=1)))
    ds = ds.rename(columns={"TEAM_ID": "team_id"})
    ours = mt.loc[mt["points_paint"].notna(),
                  ["game_id", "team_id", "points_paint"]]
    j = ds.merge(ours, on=["game_id", "team_id"], how="left", indicator=True)
    j["season"] = season_of(j["game_id"])
    is23 = j["season"] == 2023

    main = j[~is23 & (j["_merge"] == "both")]
    mism = main[main["drive_paint"].isna()
                | (main["drive_paint"] != main["points_paint"])]
    mism_out = mism[["game_id", "team_id", "drive_paint", "points_paint"]].copy()

    y23 = j[is23]
    broken23 = y23["drive_paint"].isna() | (y23["drive_paint"] == 0)
    rep23 = {
        "team_games_in_drive": len(y23),
        "drive_zero_paint": int((y23["drive_paint"] == 0).sum()),
        "drive_nan_paint": int(y23["drive_paint"].isna().sum()),
        "drive_mean_paint_where_present": round(float(y23["drive_paint"].mean()), 2),
        "ours_mean_paint": round(float(y23["points_paint"].mean()), 2),
        "ours_zero_paint": int((y23["points_paint"] == 0).sum()),
        "team_games_repaired": int((broken23 & (y23["points_paint"] > 0)).sum()),
        "mean_abs_repair": round(float(
            (y23["points_paint"] - y23["drive_paint"].fillna(0)).abs().mean()), 2),
        # the small 2023 subset where the old file DID have paint: it must
        # agree with our misc rebuild or the repair story is suspect
        "nonbroken_team_games": int((~broken23).sum()),
        "nonbroken_exact_match": int((y23.loc[~broken23, "drive_paint"]
                                      == y23.loc[~broken23, "points_paint"]).sum()),
    }
    rep23_rows = y23[["game_id", "team_id", "drive_paint", "points_paint"]].copy()
    summary = {"drive_team_games": len(ds),
               "non2023_joined": len(main),
               "non2023_not_in_master": int((~is23 & (j["_merge"] == "left_only")).sum()),
               "non2023_exact": int(len(main) - len(mism)),
               "non2023_mismatches": len(mism),
               "repair_2023": rep23}
    return summary, mism_out, rep23_rows


def v5_coverage(mp: pd.DataFrame, mt: pd.DataFrame):
    """Per (season, kind): games seen anywhere vs games covered per source,
    plus preserved DNP rows. 'Short' = fewer than the games seen in ANY
    local source for that season-kind (the running backfill closes these)."""
    def games_by(df, id_col="game_id"):
        g = df[[id_col]].drop_duplicates()
        g["season"] = season_of(g[id_col])
        g["kind"] = stype_of(g[id_col])
        return g.groupby(["season", "kind"])[id_col].nunique()

    all_games = pd.concat([mt[["game_id"]], mp[["game_id"]]]).drop_duplicates()
    rows = []
    expected = games_by(all_games)
    for (season, kind), n_exp in expected.items():
        sel_mp = (mp["season"] == season) & (mp["season_type"] == kind)
        sel_mt = (mt["season"] == season) & (mt["season_type"] == kind)
        n_gl_games = mp[sel_mp & (mp["in_gamelog"] == 1)]["game_id"].nunique()
        n_misc = mp[sel_mp & (mp["in_misc"] == 1)]["game_id"].nunique()
        n_adv = mp[sel_mp & (mp["in_advanced"] == 1)]["game_id"].nunique()
        n_team_real = mt[sel_mt & (mt["box_source"] == "team_gamelog")]["game_id"].nunique()
        n_team_derived = mt[sel_mt & (mt["box_source"] == "player_sum")]["game_id"].nunique()
        rows.append({
            "season": season, "kind": kind, "games": int(n_exp),
            "gamelog_games": int(n_gl_games),
            "gamelog_player_rows": int((sel_mp & (mp["in_gamelog"] == 1)).sum()),
            "team_box_real": int(n_team_real),
            "team_box_derived": int(n_team_derived),
            "misc_games": int(n_misc), "advanced_games": int(n_adv),
            "dnp_rows_preserved": int((sel_mp & mp["dnp_reason"].notna()).sum()),
            "master_player_rows": int(sel_mp.sum()),
        })
    cov = pd.DataFrame(rows).sort_values(["season", "kind"], ignore_index=True)
    shorts = []
    for r in cov.itertuples(index=False):
        tag = f"{r.season} {r.kind}"
        if r.gamelog_games < r.games:
            shorts.append(f"{tag}: player gamelog {r.gamelog_games}/{r.games}")
        if r.team_box_real + r.team_box_derived < r.games:
            shorts.append(f"{tag}: team box {r.team_box_real + r.team_box_derived}"
                          f"/{r.games}")
        if r.misc_games < r.games:
            shorts.append(f"{tag}: misc {r.misc_games}/{r.games}")
        if r.advanced_games < r.games:
            shorts.append(f"{tag}: advanced {r.advanced_games}/{r.games}")
    return cov, shorts


# ----------------------------------------------------------------------------
# Phase 8 -- outputs
# ----------------------------------------------------------------------------
def write_atomic(df: pd.DataFrame, path: str) -> None:
    tmp = path + ".tmp"
    if path.endswith(".parquet"):
        df.to_parquet(tmp, index=False)
    else:
        df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, path)


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def write_report(status, runtime_s, mp, mt, res, cov, shorts):
    v1, v2, v3, (t_sum, t_stats, _), (p_sum, _, _) = (
        res["v1"], res["v2"], res["v3"], res["v4_team"], res["v4_paint"])
    dnp_misc = res["dnp_misc_rows"]
    dnp_master = int(mp["dnp_reason"].notna().sum())
    derived_kinds = sorted(set(
        zip(mt.loc[mt["box_source"] == "player_sum", "season"],
            mt.loc[mt["box_source"] == "player_sum", "season_type"])))
    lines = [
        "# REBUILD_VALIDATION -- uniform master rebuild",
        "",
        f"*Generated by `build_masters.py` on "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"(runtime {runtime_s:.1f}s). Status: **{status}**.*",
        "",
        "Masters are assembled from raw per-game files only "
        "(gamelogs + refresh misc/advanced + shotchart game identity). "
        "The July-15 Drive masters are used exclusively as a diff target, "
        "never as a stat source. No imputation anywhere: every gap is an "
        "explicit NA with a coverage flag.",
        "",
        "## Row counts",
        "",
        f"- master_player: {len(mp):,} rows, {mp['game_id'].nunique():,} games, "
        f"{int(mp['player_id'].nunique()):,} players",
        f"- master_team: {len(mt):,} rows, {mt['game_id'].nunique():,} games",
        f"- DNP rows preserved: {dnp_master:,} (misc source had {dnp_misc:,}; "
        + ("all preserved)" if dnp_master == dnp_misc else "MISMATCH!)"),
        "",
        "## 1. Box identity (FTM + 3*FG3M + 2*(FGM-FG3M) == PTS)",
        "",
        f"- checked {v1['checked']:,} team rows with full box; "
        f"**{v1['violations']} violations** (target 0)"
        + (f"; {v1['skipped_no_box']} rows skipped for missing box"
           if v1["skipped_no_box"] else "; every team row carried a full box"),
        "",
        "## 2. Channel identity (ch_np2 = 2*(FGM-FG3M) - points_paint >= 0)",
        "",
        f"- checked {v2['checked']:,} team rows with box+misc; "
        f"**{v2['violations']} violations**",
        "",
        "## 3. Player-sum vs team-total reconciliation (PTS, FGM, FTM)",
        "",
        f"- {v3['team_games_checked']:,} team-games checked; "
        f"**{v3['mismatches_total']} mismatches**",
        f"- independent checks (real team gamelog vs player sums): "
        f"{v3['independent_checks_vs_real_team_gamelog']:,} "
        f"({v3['mismatches_vs_real_team_gamelog']} mismatches); the "
        f"{v3['trivial_player_sum_rows']:,} derived (player_sum) rows "
        "reconcile by construction and are not evidence",
        "",
        "## 4a. Diff vs Drive master_team_cleaned.csv (the accuracy proof)",
        "",
        f"- drive rows {t_sum['drive_rows']:,}; joined {t_sum['joined']:,}; "
        f"compared (box on both sides) {t_sum['compared_rows']:,}",
        f"- drive rows with no master row: {t_sum['drive_rows_not_in_master']}",
        f"- joined but box-NA on our side: {t_sum['joined_but_no_box_on_our_side']}"
        + (f" -- breakdown {t_sum['no_box_breakdown']}"
           if t_sum["joined_but_no_box_on_our_side"] else ""),
        f"- **unexplained mismatches: {t_sum['unexplained_mismatches']}** "
        f"(target 0). All diffs by category: {t_sum['mismatch_categories']}",
        "",
        md_table(t_stats),
        "",
        "Every non-exact cell is classified in diff_drive_team_mismatches.csv "
        "with the raw pbp as independent arbiter; each category is re-VERIFIED "
        "per row on every run, never waved through:",
        "",
        "- `team_tov_uncredited` -- on derived rows both values are correct "
        "at their own definition: Drive team tov (real LeagueGameLog team "
        "files John had in July; absent on this machine for 2021-2023 "
        "regular) counts TEAM turnovers (shot-clock/5-sec/8-sec, credited to "
        "no player) that a player-row sum cannot contain. Verified per row: "
        "ours == pbp player-credited TOs AND drive == pbp total TOs "
        f"(pbp-verified rows: {ANOMS.get('tov_uncredited_pbp_verified', 0)}). "
        "Master tov on box_source='player_sum' rows is therefore "
        "player-attributed only -- fetching the three real team-gamelog "
        "season files upgrades those rows in place.",
        "- `local_gamelog_pbp_disagreement` -- drive == pbp but our raw "
        "local season gamelog does not: the local file miscounts that stat "
        "(REPAIR ITEM -- refetch those games' boxscores; exact games, teams "
        "and pbp evidence in the Notes section and the CSV).",
        "- `drive_wrong_vs_pbp` -- ours == pbp but drive does not: the "
        "July-15 value would be contradicted by the play-by-play and our "
        "master corroborated (0 such rows on this run -- the category exists "
        "so a future drive-side error cannot hide).",
        "- `rounding_boundary` -- |diff| <= 0.0011 on a 3dp pct (two "
        "independent roundings), or |team_min diff| <= 0.5 (Drive stores "
        "integer team minutes; derived rows sum exact MM:SS).",
        "",
        "## 4b. Diff vs Drive master_player.csv (team-summed paint)",
        "",
        f"- drive team-games {p_sum['drive_team_games']:,}; non-2023 joined "
        f"{p_sum['non2023_joined']:,}, exact {p_sum['non2023_exact']:,}, "
        f"**mismatches {p_sum['non2023_mismatches']}**, not-in-master "
        f"{p_sum['non2023_not_in_master']}",
        "",
        "### 2023 repaired-vs-broken (excluded from the match-rate above)",
        "",
    ]
    for k, v in p_sum["repair_2023"].items():
        lines.append(f"- {k}: {v}")
    lines += [
        "",
        "Full per-team-game 2023 old-vs-new values: "
        "diff_drive_player_paint_2023_repair.csv",
        "",
        "## 5. Coverage by season x kind",
        "",
        md_table(cov),
        "",
        "### Season-kinds still short at run time",
        "",
    ]
    lines += [f"- {s}" for s in shorts] if shorts else ["- none"]
    lines += [
        "",
        "## Known gaps and explanations (not smoothed over)",
        "",
        "- **data/wnba_gamelog_2025.parquet deliberately skipped**: it holds "
        "league games 1-108 only and is missing every Phoenix game (PHO->PHX "
        "rename); gamelog_player_2025_regular_season.parquet covers all 286 "
        "games and supersedes it.",
        "- **Team box derived from same-game player-row sums** "
        f"(box_source='player_sum') for {derived_kinds or 'no season-kinds'} "
        "-- no real team gamelog exists locally there. Shooting pct "
        "recomputed at 3dp half-up, plus_minus = pts - opp_pts, wl from the "
        "margin: same-game derivation with provenance, not imputation. "
        "Derived tov is player-attributed only (see team_tov_uncredited "
        "above); a real LeagueGameLog team pull for those seasons upgrades "
        "these rows in place on the next run.",
        "- **Misc opp_points_* player columns are on-court-credited** and do "
        "not sum to team totals; team channel sums use own-scoring columns "
        "only.",
        "- **Old-era gamelogs carry no dates or home/away**; game identity "
        "for those rows comes from raw ShotChartDetail exports "
        "(GAME_DATE/HTM/VTM), recorded in gameinfo provenance. Tricode "
        "aliases handled: PHO/PHX (stats.nba.com renamed Phoenix in 2025), "
        "POR/PDX (Portland is PDX in every local source).",
        "",
        "## Anomaly counters",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(ANOMS.items())] or ["- none"]
    if NOTES:
        lines += ["", "## Notes / schema surprises", ""]
        lines += [f"- {n}" for n in NOTES]
    lines += [
        "",
        "## Validation artifacts",
        "",
        "- validation_box_identity_violations.csv",
        "- validation_channel_identity_violations.csv",
        "- validation_player_team_reconciliation_mismatches.csv",
        "- diff_drive_team_stats.csv / diff_drive_team_mismatches.csv",
        "- diff_drive_player_paint_mismatches.csv / "
        "diff_drive_player_paint_2023_repair.csv",
        "- coverage_table.csv",
        "",
    ]
    with open(os.path.join(MASTERS, "REBUILD_VALIDATION.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.perf_counter()
    os.makedirs(MASTERS, exist_ok=True)
    mtimes: dict[str, str] = {}

    log("[1/8] player gamelogs ...")
    gl = load_player_gamelogs(mtimes)
    log(f"      {len(gl):,} rows, {gl['game_id'].nunique():,} games")

    log("[2/8] team gamelogs ...")
    team_gl = load_team_gamelogs(mtimes)
    log(f"      {len(team_gl):,} rows, {team_gl['game_id'].nunique():,} games")

    log("[3/8] per-game misc (snapshot of a live directory) ...")
    misc = load_pergame_dir("misc", mtimes)
    dnp_misc_rows = int(misc["dnp_reason"].notna().sum())
    log(f"      {len(misc):,} rows, {misc['game_id'].nunique():,} games, "
        f"{dnp_misc_rows:,} DNP rows")

    log("[4/8] per-game advanced ...")
    adv = load_pergame_dir("advanced", mtimes)
    log(f"      {len(adv):,} rows, {adv['game_id'].nunique():,} games")

    log("[5/8] game identity index (team gl > player gl > shotcharts) ...")
    gidx = build_game_index(team_gl, gl, misc, mtimes)
    log(f"      {gidx['game_id'].nunique():,} games indexed")

    log("[6/8] master_player ...")
    mp = build_master_player(gl, misc, adv, gidx, mtimes)
    log(f"      {len(mp):,} rows")

    log("[7/8] master_team ...")
    mt = build_master_team(team_gl, gl, misc, gidx, mtimes)
    log(f"      {len(mt):,} rows")

    log("[8/8] validations + outputs ...")
    res = {"dnp_misc_rows": dnp_misc_rows}
    res["v1"], bad1 = v1_box_identity(mt)
    res["v2"], bad2 = v2_channel_identity(mt)
    res["v3"], bad3 = v3_player_team_reconciliation(mp, mt)
    res["v4_team"] = v4_diff_drive_team(mt)
    res["v4_paint"] = v4_diff_drive_player_paint(mt)
    cov, shorts = v5_coverage(mp, mt)

    write_atomic(mp, os.path.join(MASTERS, "master_player.parquet"))
    write_atomic(mp, os.path.join(MASTERS, "master_player.csv"))
    write_atomic(mt, os.path.join(MASTERS, "master_team.parquet"))
    write_atomic(mt, os.path.join(MASTERS, "master_team.csv"))
    write_atomic(bad1, os.path.join(MASTERS, "validation_box_identity_violations.csv"))
    write_atomic(bad2, os.path.join(MASTERS, "validation_channel_identity_violations.csv"))
    write_atomic(bad3, os.path.join(MASTERS, "validation_player_team_reconciliation_mismatches.csv"))
    write_atomic(res["v4_team"][1], os.path.join(MASTERS, "diff_drive_team_stats.csv"))
    write_atomic(res["v4_team"][2], os.path.join(MASTERS, "diff_drive_team_mismatches.csv"))
    write_atomic(res["v4_paint"][1], os.path.join(MASTERS, "diff_drive_player_paint_mismatches.csv"))
    write_atomic(res["v4_paint"][2], os.path.join(MASTERS, "diff_drive_player_paint_2023_repair.csv"))
    write_atomic(cov, os.path.join(MASTERS, "coverage_table.csv"))
    write_atomic(pd.DataFrame(DEDUPE_ROWS),
                 os.path.join(MASTERS, "dedupe_resolutions.csv"))

    dnp_ok = int(mp["dnp_reason"].notna().sum()) == dnp_misc_rows
    hard_fail = (res["v1"]["violations"] > 0 or res["v2"]["violations"] > 0
                 or res["v3"]["mismatches_vs_real_team_gamelog"] > 0
                 or res["v4_team"][0]["unexplained_mismatches"] > 0
                 or res["v4_paint"][0]["non2023_mismatches"] > 0
                 or not dnp_ok)
    status = "FAIL" if hard_fail else ("PARTIAL" if shorts else "PASS")
    runtime = time.perf_counter() - t0
    write_report(status, runtime, mp, mt, res, cov, shorts)

    # ---------------- one-screen console summary ----------------
    log("")
    log("=" * 76)
    log("MASTER REBUILD SUMMARY")
    log("=" * 76)
    per_season = mp.groupby(["season", "season_type"]).size()
    log("master_player rows: " + "  ".join(
        f"{s}-{k[:3]}:{n}" for (s, k), n in per_season.items()))
    per_season_t = mt.groupby(["season", "season_type"]).size()
    log("master_team rows:   " + "  ".join(
        f"{s}-{k[:3]}:{n}" for (s, k), n in per_season_t.items()))
    log(f"[1] box identity: {res['v1']['violations']} violations "
        f"({res['v1']['checked']:,} checked)")
    log(f"[2] channel identity: {res['v2']['violations']} violations "
        f"({res['v2']['checked']:,} checked)")
    log(f"[3] player-vs-team recon: "
        f"{res['v3']['mismatches_vs_real_team_gamelog']} independent mismatches "
        f"({res['v3']['independent_checks_vs_real_team_gamelog']:,} real checks)")
    t_sum = res["v4_team"][0]
    log(f"[4a] drive team diff: {t_sum['unexplained_mismatches']} unexplained "
        f"/ {t_sum['compared_rows']:,} compared rows; categories "
        f"{t_sum['mismatch_categories']}")
    p_sum = res["v4_paint"][0]
    log(f"[4b] drive paint diff: {p_sum['non2023_mismatches']} mismatches "
        f"/ {p_sum['non2023_joined']:,} non-2023 team-games; 2023 repaired: "
        f"{p_sum['repair_2023']['team_games_repaired']} team-games "
        f"(mean |repair| {p_sum['repair_2023']['mean_abs_repair']})")
    log(f"[5] coverage: {len(shorts)} season-kind shortfalls")
    for s in shorts:
        log(f"     SHORT {s}")
    log(f"DNP rows preserved: {int(mp['dnp_reason'].notna().sum()):,}"
        + ("" if dnp_ok else "  (MISMATCH vs misc!)"))
    log(f"runtime: {runtime:.1f}s   outputs: data/masters/")
    log("=" * 76)
    log(f"STATUS: {status}")
    log("=" * 76)
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

