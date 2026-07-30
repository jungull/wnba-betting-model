#!/usr/bin/env python3
"""
Targeted repair of the two games where the local old-era player season gamelogs
contradict their own play-by-play (REBUILD_VALIDATION.md 2026-07-30, category
'local_gamelog_pbp_disagreement'; per-row evidence in
data/masters/diff_drive_team_mismatches.csv):

  1022300092 (2023, LVA at CON): LVA player STL sums to 8 locally, pbp says 7;
      CON player-credited TO sums to 11 locally, pbp says 10 (game total 12
      including 2 TEAM turnovers).
  1022200107 (2022, DAL vs PHO): DAL player 1629497 (Marina Mabrey) has TO=3
      locally, pbp shows 4 (player-credited total 15, game total 16).

Constitution rule: go get the real data, never impute. This script refetches
each game's traditional boxscore (BoxScoreTraditionalV3 -- stats.nba.com
retired the V2 per-game endpoints in July 2026) and patches ONLY the cells
where the refetched box disagrees with the local row. Nothing is derived from
the pbp; the pbp is used strictly as the post-patch arbiter.

  raw refetches   -> data/refresh_2026/traditional/traditional_<gid>.parquet
  backups         -> data/backups/wnba_gamelog_<year>.pre_patch_<date>.parquet
  patch document  -> data/gamelog_patch_<date>.md (every changed cell)

Aborts loudly (nothing written) on any structural surprise: local player
missing from the refetched box, refetched PLAYED player missing locally, or
team mismatch. Resumable/idempotent: refetches are checkpointed, and a re-run
after a successful patch finds zero differing cells and rewrites nothing.

Run from the repo root:  python repair_gamelog_two_games.py
"""
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from nba_api.stats.endpoints import boxscoretraditionalv3
except ImportError:
    sys.exit("Run first:  pip install nba_api pandas pyarrow")

from collect_refresh import OUT, fetch
from wnba_schema import minutes_to_float, normalize_player_box

DATA = Path("data")
TRAD = OUT / "traditional"

REPAIRS = {"1022300092": 2023, "1022200107": 2022}  # game_id -> season file

# pbp arbiter values (data/masters/diff_drive_team_mismatches.csv). The patch
# does NOT write these; it writes refetched boxscore values and then checks
# whether the patched file now agrees with the pbp.
EXPECT = [
    ("1022300092", 2023, 1611661319, "LVA", "STL", 7,
     "pbp stl=7"),
    ("1022300092", 2023, 1611661323, "CON", "TO", 10,
     "pbp player-credited TO=10 (game total 12 incl. 2 TEAM turnovers)"),
    ("1022200107", 2022, 1611661321, "DAL", "TO", 15,
     "pbp player-credited TO=15 (game total 16 incl. 1 TEAM turnover)"),
]

# old-era file stat columns -> canonical names in the normalized refetch frame
STAT_COLS = {
    "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct", "FG3M": "fg3m",
    "FG3A": "fg3a", "FG3_PCT": "fg3_pct", "FTM": "ftm", "FTA": "fta",
    "FT_PCT": "ft_pct", "OREB": "oreb", "DREB": "dreb", "REB": "reb",
    "AST": "ast", "STL": "stl", "BLK": "blk", "TO": "tov", "PF": "pf",
    "PTS": "pts", "PLUS_MINUS": "plus_minus",
}
PCT_OF = {"FG_PCT": ("FGM", "FGA"), "FG3_PCT": ("FG3M", "FG3A"),
          "FT_PCT": ("FTM", "FTA")}
COUNT_COLS = [c for c in STAT_COLS if c not in PCT_OF]


def half_up3(x):
    """3dp HALF-UP -- the stats-API pct convention (matches build_masters)."""
    return x if pd.isna(x) else np.floor(float(x) * 1000 + 0.5) / 1000


def num_equal(a, b):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) != pd.isna(b):
        return False
    return float(a) == float(b)


def fetch_traditional(gid):
    """Checkpointed refetch of one game's traditional boxscore (player rows)."""
    path = TRAD / f"traditional_{gid}.parquet"
    if path.exists():
        print(f"  {gid}: refetched boxscore already on disk -- reusing")
        return pd.read_parquet(path)
    r = fetch(lambda: boxscoretraditionalv3.BoxScoreTraditionalV3(
        game_id=gid, timeout=60), f"traditional {gid}")
    if r is None:
        sys.exit(f"ABORT: could not fetch traditional boxscore for {gid}")
    raw = r.player_stats.get_data_frame()
    if raw is None or not len(raw):
        sys.exit(f"ABORT: empty traditional boxscore for {gid}")
    if "gameId" not in raw.columns:  # some nba_api versions omit it
        raw.insert(0, "gameId", gid)
    TRAD.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(path, index=False)
    print(f"  {gid}: fetched {len(raw)} roster rows -> {path.as_posix()}")
    return raw


def resolve_ref_dupes(gid, ref, notes):
    """Known ghost-row case (misc/advanced files carry personId 1629484 twice
    from a player rename): keep the finite-minutes row; two finite rows for one
    person would be a real conflict -> abort."""
    dup_pids = ref.loc[ref["player_id"].duplicated(keep=False), "player_id"].unique()
    for dpid in dup_pids:
        grp = ref[ref["player_id"] == dpid]
        finite = grp[grp["minutes"].notna()]
        if len(finite) > 1:
            sys.exit(f"ABORT {gid}: personId {int(dpid)} has {len(finite)} "
                     f"rows with real minutes in the refetched box")
        keep = finite.index[0] if len(finite) == 1 else grp.index[0]
        ref = ref.drop(index=[i for i in grp.index if i != keep])
        notes.append(f"{gid}: personId {int(dpid)} duplicated in refetch "
                     f"({len(grp)} rows) -> kept the finite-minutes row")
    return ref


def repair_game(gid, season_df, ref, changes, notes):
    """Patch season_df rows of game `gid` from canonical refetch frame `ref`
    (already filtered to the game). Appends one dict per changed cell."""
    loc_idx = season_df.index[season_df["GAME_ID"].astype(str).str.zfill(10) == gid]
    if not len(loc_idx):
        sys.exit(f"ABORT: game {gid} not found in local season file")
    ref = resolve_ref_dupes(gid, ref, notes)

    loc_pids = {int(season_df.at[i, "PLAYER_ID"]) for i in loc_idx}
    ref_pids = set(ref["player_id"].astype("int64"))
    missing = loc_pids - ref_pids
    if missing:
        sys.exit(f"ABORT {gid}: local players missing from refetched box: {missing}")
    extra_played = set(ref.loc[ref["minutes"].notna(), "player_id"].astype("int64")) - loc_pids
    if extra_played:
        # old-era season files hold played rows only; a refetched PLAYED player
        # absent locally would be a structural gap, not a cell patch
        sys.exit(f"ABORT {gid}: refetched box has played rows absent locally: {extra_played}")

    ref_by_pid = ref.set_index(ref["player_id"].astype("int64"))
    for i in loc_idx:
        pid = int(season_df.at[i, "PLAYER_ID"])
        rrow = ref_by_pid.loc[pid]
        if int(rrow["team_id"]) != int(season_df.at[i, "TEAM_ID"]):
            sys.exit(f"ABORT {gid}: team mismatch for player {pid}: "
                     f"local {int(season_df.at[i, 'TEAM_ID'])} vs refetch {int(rrow['team_id'])}")

        def record(col, old, new):
            changes.append({
                "file": f"wnba_gamelog_{REPAIRS[gid]}.parquet", "game_id": gid,
                "team": str(season_df.at[i, "TEAM_ABBREVIATION"]),
                "player_id": pid, "player": str(season_df.at[i, "PLAYER_NAME"]),
                "column": col, "old": old, "new": new,
            })

        # minutes: refetch says DNP for a locally-played row -> structural, abort
        new_min = rrow["minutes"]
        old_min_raw = season_df.at[i, "MIN"]
        if pd.isna(new_min):
            sys.exit(f"ABORT {gid}: refetched box has no minutes for locally-"
                     f"played player {pid} ({season_df.at[i, 'PLAYER_NAME']})")
        if abs(minutes_to_float(old_min_raw) - float(new_min)) > 1e-6:
            record("MIN", old_min_raw, str(rrow["minutes_raw"]))
            season_df.at[i, "MIN"] = str(rrow["minutes_raw"])

        changed_here = set()
        for col in COUNT_COLS:
            new_v = rrow[STAT_COLS[col]]
            old_v = season_df.at[i, col]
            if not num_equal(old_v, new_v):
                record(col, old_v, float(new_v))
                season_df.at[i, col] = float(new_v)
                changed_here.add(col)

        for pcol, (mcol, acol) in PCT_OF.items():
            new3 = half_up3(rrow[STAT_COLS[pcol]])
            old_p = season_df.at[i, pcol]
            if {mcol, acol} & changed_here:
                if not num_equal(old_p, new3):
                    record(pcol, old_p, new3)
                    season_df.at[i, pcol] = new3
            elif pd.notna(old_p) and pd.notna(new3) and abs(new3 - old_p) > 0.0011:
                # beyond the dual-rounding boundary with unchanged counts: a
                # real upstream pct revision
                record(pcol, old_p, new3)
                season_df.at[i, pcol] = new3
            elif pd.isna(old_p) != pd.isna(new3):
                notes.append(f"{gid} player {pid} {pcol}: NaN-vs-value convention "
                             f"difference (counts unchanged) -- NOT patched")


def main():
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print("== refetch traditional boxscores ==")
    refs = {}
    for gid in REPAIRS:
        raw = fetch_traditional(gid)
        ref = normalize_player_box(raw)
        refs[gid] = ref[ref["game_id"] == gid]

    print("\n== compare & patch ==")
    seasons = {y: pd.read_parquet(DATA / f"wnba_gamelog_{y}.parquet")
               for y in sorted(set(REPAIRS.values()))}
    changes, notes = [], []
    for gid, year in REPAIRS.items():
        repair_game(gid, seasons[year], refs[gid], changes, notes)
    for c in changes:
        print(f"  {c['file']} {c['game_id']} {c['team']} {c['player']} "
              f"{c['column']}: {c['old']} -> {c['new']}")
    for n in notes:
        print(f"  note: {n}")
    if not changes:
        print("  no differing cells -- local files already match the refetched boxscores")

    print("\n== verify vs pbp (arbiter only, never a source) ==")
    verdicts = []
    for gid, year, team_id, abbr, col, want, basis in EXPECT:
        df = seasons[year]
        got = df.loc[(df["GAME_ID"].astype(str).str.zfill(10) == gid)
                     & (df["TEAM_ID"] == team_id), col].sum()
        ok = int(got) == want
        verdicts.append((gid, abbr, col, want, int(got), ok, basis))
        print(f"  {gid} {abbr} sum({col}) = {int(got)} vs pbp {want}: "
              f"{'PASS' if ok else 'STILL DISAGREES (upstream vs pbp)'}  [{basis}]")

    if not changes:
        print("\nnothing to write; disagreements above (if any) are upstream, "
              "not repairable from the boxscore endpoint")
        return

    print("\n== back up & write ==")
    stamp = date.today().isoformat()
    changed_years = sorted({REPAIRS[c["game_id"]] for c in changes})
    for year in changed_years:
        src = DATA / f"wnba_gamelog_{year}.parquet"
        bdir = DATA / "backups"
        bdir.mkdir(exist_ok=True)
        bak = bdir / f"wnba_gamelog_{year}.pre_patch_{stamp}.parquet"
        if not bak.exists():
            shutil.copy2(src, bak)
            print(f"  backup: {bak.as_posix()}")
        seasons[year].to_parquet(src, index=False)
        print(f"  patched: {src.as_posix()} "
              f"({sum(1 for c in changes if REPAIRS[c['game_id']] == year)} cells)")

    doc = DATA / f"gamelog_patch_{stamp}.md"
    lines = [
        f"# Gamelog patch {stamp} -- two pbp-contradicted games",
        "",
        f"Source: BoxScoreTraditionalV3 refetched {fetched_at} into "
        f"`data/refresh_2026/traditional/` by `repair_gamelog_two_games.py`.",
        "Cause: REBUILD_VALIDATION.md category `local_gamelog_pbp_disagreement` "
        "(local old-era season gamelogs contradicted the raw play-by-play; "
        "evidence in `data/masters/diff_drive_team_mismatches.csv`).",
        "Rule: every patched value is the refetched boxscore value -- nothing "
        "derived from pbp, nothing imputed. pbp is the post-patch arbiter only.",
        "",
        "## Patched cells",
        "",
        "| file | game | team | player | column | old | new |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in changes:
        lines.append(f"| {c['file']} | {c['game_id']} | {c['team']} | "
                     f"{c['player']} ({c['player_id']}) | {c['column']} | "
                     f"{c['old']} | {c['new']} |")
    lines += ["", "## Post-patch verification vs pbp", ""]
    for gid, abbr, col, want, got, ok, basis in verdicts:
        lines.append(f"- {gid} {abbr} sum({col}) = {got}, pbp {want}: "
                     f"{'PASS' if ok else 'STILL DISAGREES -- upstream boxscore vs pbp'} ({basis})")
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    lines += ["", "## Backups", ""]
    lines += [f"- data/backups/wnba_gamelog_{y}.pre_patch_{stamp}.parquet"
              for y in changed_years]
    lines.append("")
    doc.write_text("\n".join(lines), encoding="utf-8")
    print(f"  documented: {doc.as_posix()}")


if __name__ == "__main__":
    main()
