"""
derive_lineups.py
=================
Derive per-game starters, substitution stints, and per-player minutes from the
locally stored WNBA play-by-play parquet files. Precursor to the RAPM build
(possession stints) and the minutes-prediction model (rotation patterns).

LOCAL DATA ONLY - no network access, no nba_api calls.

Inputs
------
- data/playbyplay/pbp_*.parquet           NBA stats V2 schema (EVENTMSGTYPE, ...)
- data/refresh_2026/pbp/pbp_*.parquet     V3 camelCase schema (actionType, ...)
                                          NOTE: contains some V2-schema strays;
                                          schema is detected per file, not per dir.

Boxscore minutes truth (priority order):
- data/refresh_2026/advanced/advanced_*.parquet  ('minutes' as "MM:SS", position=starter)
- data/refresh_2026/misc/misc_*.parquet          (same shape)
- data/wnba_gamelog_<year>.parquet               (MIN "35.000000:36" or "MM:SS", START_POSITION)
- data/refresh_2026/gamelog_player_*.parquet     (MIN integer minutes - least precise)

Outputs
-------
- data/derived/starters.csv           GAME_ID, TEAM_ID, PLAYER_ID, PLAYER_NAME, period1_starter
- data/derived/stints.parquet         one row per on-court stint (+ per-player game totals)
- data/derived/lineup_validation.csv  derived vs boxscore minutes per player-game
- data/derived/failed_games.csv       games not processed, with reason

Substitution encodings (feed for the future pbp normalizer module):
- V2: one row per sub, EVENTMSGTYPE 8, PLAYER1 = outgoing, PLAYER2 = incoming,
  both with ids and team ids. Clock "MM:SS".
- V3: one row per sub, actionType 'Substitution', personId = OUTGOING player only.
  The incoming player exists ONLY in the description text "SUB: <IN> FOR <OUT>"
  and must be name-resolved against the game roster. Clock "PT09M45.00S".
  Steals/blocks are separate rows with blank actionType. Timeout rows carry the
  TEAM id in personId. Team rebounds/turnovers carry the team id in personId.
"""

from __future__ import annotations

import glob
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PBP_V2_DIR = os.path.join(DATA, "playbyplay")
PBP_REFRESH_DIR = os.path.join(DATA, "refresh_2026", "pbp")
ADV_DIR = os.path.join(DATA, "refresh_2026", "advanced")
MISC_DIR = os.path.join(DATA, "refresh_2026", "misc")
OUT_DIR = os.path.join(DATA, "derived")

TEAM_ID_FLOOR = 1_000_000_000  # ids >= this are team ids, not players

# V2 event types
V2_SUB = 8
# V2 foul EVENTMSGACTIONTYPEs where the listed person can be off the floor
# (technicals on bench players / coaches / team). Def-3-sec (17), flagrants
# (14, 15) and double personal (10) are committed by on-court players and kept.
V2_TECH_FOUL_ACTIONS = {11, 12, 13, 16, 18, 19, 25, 30}
V2_FT_TECHNICAL_ACTION = 16  # "Free Throw Technical"

# V2: (event_type) -> list of (id_col, ptype_col, team_col) that are ON-COURT evidence
V2_EVIDENCE_SLOTS = {
    1: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID"),  # shooter
        ("PLAYER2_ID", "PERSON2TYPE", "PLAYER2_TEAM_ID")],  # assister
    2: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID"),  # shooter
        ("PLAYER3_ID", "PERSON3TYPE", "PLAYER3_TEAM_ID")],  # blocker
    3: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID")],  # FT shooter (non-technical)
    4: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID")],  # rebounder (player only)
    5: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID"),  # turnover
        ("PLAYER2_ID", "PERSON2TYPE", "PLAYER2_TEAM_ID")],  # stealer
    6: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID"),  # fouler (non-technical)
        ("PLAYER2_ID", "PERSON2TYPE", "PLAYER2_TEAM_ID")],  # drawn-by
    7: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID")],  # violation
    10: [("PLAYER1_ID", "PERSON1TYPE", "PLAYER1_TEAM_ID"),  # jump ball home
         ("PLAYER2_ID", "PERSON2TYPE", "PLAYER2_TEAM_ID"),  # jump ball away
         ("PLAYER3_ID", "PERSON3TYPE", "PLAYER3_TEAM_ID")],  # tip-to
}
# Excluded V2 types entirely: 9 timeout (team-level), 11 ejection (can be bench),
# 12/13 period boundaries, 18 instant replay.

# V3 actionTypes usable as on-court evidence (with per-row filters applied below)
V3_EVIDENCE_TYPES = {
    "Made Shot", "Missed Shot", "Free Throw", "Rebound", "Turnover",
    "Violation", "Jump Ball", "Foul", "",  # '' rows are STEAL/BLOCK annotations
}
# Excluded V3 actionTypes: Timeout (team id in personId), Instant Replay
# (garbage personIds), period, Ejection.

SUB_DESC_RE = re.compile(r"^SUB:\s*(?P<inp>.+?)\s+FOR\s+(?P<outp>.+?)\s*$")
V3_CLOCK_RE = re.compile(r"^PT(\d+)M([\d.]+)S$")
V2_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def period_len_sec(p: int) -> float:
    return 600.0 if p <= 4 else 300.0


def period_start_abs(p: int) -> float:
    return 600.0 * (p - 1) if p <= 4 else 2400.0 + 300.0 * (p - 5)


def parse_clock_v2(s: str):
    m = V2_CLOCK_RE.match(s or "")
    if not m:
        return None
    return int(m.group(1)) * 60.0 + int(m.group(2))


def parse_clock_v3(s: str):
    m = V3_CLOCK_RE.match(s or "")
    if not m:
        return None
    return int(m.group(1)) * 60.0 + float(m.group(2))


def norm_name(s: str) -> str:
    """Casefold, strip accents/periods/extra spaces for tolerant name matching."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.replace(".", " ")).strip().casefold()


# ----------------------------------------------------------------------------
# Boxscore minutes truth
# ----------------------------------------------------------------------------
def parse_min_string(v) -> float:
    """Return seconds from any of the boxscore minute formats, NaN if unusable.
    Formats seen: '25:07' | '35.000000:36' | 28 (int minutes) | '' | None."""
    if v is None:
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return np.nan if pd.isna(v) else float(v) * 60.0
    s = str(v).strip()
    if not s:
        return np.nan
    if ":" in s:
        a, b = s.rsplit(":", 1)
        try:
            return float(a) * 60.0 + float(b)
        except ValueError:
            return np.nan
    try:
        return float(s) * 60.0
    except ValueError:
        return np.nan


def load_boxscore_truth() -> pd.DataFrame:
    """One row per (GAME_ID, PLAYER_ID): box seconds, team, name, starter flag,
    source. Priority: advanced > misc > root gamelog > refresh gamelog."""
    frames = []

    def v3_boxdir(dirpath, source, prio):
        rows = []
        for f in sorted(glob.glob(os.path.join(dirpath, "*.parquet"))):
            try:
                d = pd.read_parquet(f, columns=[
                    "gameId", "teamId", "personId", "firstName", "familyName",
                    "nameI", "position", "minutes"])
            except Exception:
                continue
            rows.append(d)
        if not rows:
            return None
        d = pd.concat(rows, ignore_index=True)
        out = pd.DataFrame({
            "GAME_ID": d["gameId"].astype(str),
            "TEAM_ID": d["teamId"].astype("int64"),
            "PLAYER_ID": d["personId"].astype("int64"),
            "PLAYER_NAME": (d["firstName"].fillna("") + " " + d["familyName"].fillna("")).str.strip(),
            "FAMILY_NAME": d["familyName"].fillna(""),
            "FIRST_NAME": d["firstName"].fillna(""),
            "NAME_I": d["nameI"].fillna(""),
            "BOX_SEC": d["minutes"].map(parse_min_string),
            "BOX_STARTER": (d["position"].fillna("") != "").astype(int),
            "HAS_STARTER_FLAG": True,
            "BOX_SOURCE": source,
            "PRIO": prio,
        })
        return out

    a = v3_boxdir(ADV_DIR, "advanced", 4)
    if a is not None:
        frames.append(a)
    m = v3_boxdir(MISC_DIR, "misc", 3)
    if m is not None:
        frames.append(m)

    for y in (2021, 2022, 2023, 2024, 2025):
        f = os.path.join(DATA, f"wnba_gamelog_{y}.parquet")
        if not os.path.exists(f):
            continue
        g = pd.read_parquet(f, columns=[
            "GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "START_POSITION", "MIN"])
        out = pd.DataFrame({
            "GAME_ID": g["GAME_ID"].astype(str),
            "TEAM_ID": g["TEAM_ID"].astype("int64"),
            "PLAYER_ID": g["PLAYER_ID"].astype("int64"),
            "PLAYER_NAME": g["PLAYER_NAME"].fillna(""),
            "FAMILY_NAME": g["PLAYER_NAME"].fillna("").str.split().str[-1],
            "FIRST_NAME": g["PLAYER_NAME"].fillna("").str.split().str[0],
            "NAME_I": "",
            "BOX_SEC": g["MIN"].map(parse_min_string),
            "BOX_STARTER": (g["START_POSITION"].fillna("") != "").astype(int),
            "HAS_STARTER_FLAG": True,
            "BOX_SOURCE": f"gamelog_{y}",
            "PRIO": 2,
        })
        frames.append(out)

    for name in ("gamelog_player_2021_playoffs", "gamelog_player_2025_playoffs",
                 "gamelog_player_2025_regular_season", "gamelog_player_2026_regular_season"):
        f = os.path.join(DATA, "refresh_2026", f"{name}.parquet")
        if not os.path.exists(f):
            continue
        g = pd.read_parquet(f, columns=["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "MIN"])
        out = pd.DataFrame({
            "GAME_ID": g["GAME_ID"].astype(str),
            "TEAM_ID": g["TEAM_ID"].astype("int64"),
            "PLAYER_ID": g["PLAYER_ID"].astype("int64"),
            "PLAYER_NAME": g["PLAYER_NAME"].fillna(""),
            "FAMILY_NAME": g["PLAYER_NAME"].fillna("").str.split().str[-1],
            "FIRST_NAME": g["PLAYER_NAME"].fillna("").str.split().str[0],
            "NAME_I": "",
            "BOX_SEC": g["MIN"].map(parse_min_string),
            "BOX_STARTER": 0,
            "HAS_STARTER_FLAG": False,  # leaguegamelog has no starter flag
            "BOX_SOURCE": name,
            "PRIO": 1,
        })
        frames.append(out)

    box = pd.concat(frames, ignore_index=True)
    # Prefer rows that actually carry minutes over source priority: some misc
    # rows have empty minutes for players who played (seen: renamed players).
    box["_has_min"] = np.isfinite(box["BOX_SEC"]).astype(int)
    box = box.sort_values(["_has_min", "PRIO"], ascending=False)
    box = box.drop_duplicates(subset=["GAME_ID", "PLAYER_ID"], keep="first")
    return box.drop(columns=["_has_min"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Normalized event model
#   ('sub', pos, period, t_abs, team_id, out_pid, in_pid)   in_pid may be None
#   ('ev',  pos, period, t_abs, team_id, pid)
# One downstream engine consumes this for both schemas.
# ----------------------------------------------------------------------------
class GameParse:
    __slots__ = ("game_id", "schema", "events", "periods", "player_team",
                 "player_name", "anoms", "clock_bad", "order_bad")

    def __init__(self, game_id, schema):
        self.game_id = game_id
        self.schema = schema
        self.events = []
        self.periods = set()
        self.player_team = {}
        self.player_name = {}
        self.anoms = Counter()
        self.clock_bad = 0
        self.order_bad = 0


def _register(gp: GameParse, pid, team, name):
    if pid and 0 < pid < TEAM_ID_FLOOR:
        if team and team > 0 and pid not in gp.player_team:
            gp.player_team[pid] = int(team)
        if name and pid not in gp.player_name:
            gp.player_name[pid] = name


def parse_game_v2(game_id: str, df: pd.DataFrame) -> GameParse:
    gp = GameParse(game_id, "V2")
    pos = 0
    last_clock = {}
    for row in df.itertuples(index=False):
        et = row.EVENTMSGTYPE
        period = int(row.PERIOD)
        clock = parse_clock_v2(row.PCTIMESTRING)
        if clock is None:
            gp.clock_bad += 1
            continue
        plen = period_len_sec(period)
        if clock > plen + 1e-9:
            gp.clock_bad += 1
            clock = plen
        if period in last_clock and clock > last_clock[period] + 1e-9:
            gp.order_bad += 1
        last_clock[period] = clock
        t_abs = period_start_abs(period) + (plen - clock)
        gp.periods.add(period)

        if et == V2_SUB:
            out_pid, in_pid = int(row.PLAYER1_ID), int(row.PLAYER2_ID)
            team = row.PLAYER1_TEAM_ID if pd.notna(row.PLAYER1_TEAM_ID) else row.PLAYER2_TEAM_ID
            team = int(team) if pd.notna(team) else 0
            if not (0 < out_pid < TEAM_ID_FLOOR and 0 < in_pid < TEAM_ID_FLOOR):
                gp.anoms["sub_malformed"] += 1
                continue
            _register(gp, out_pid, team, row.PLAYER1_NAME)
            _register(gp, in_pid, team, row.PLAYER2_NAME)
            gp.events.append(("sub", pos, period, t_abs, team, out_pid, in_pid))
            pos += 1
            continue

        slots = V2_EVIDENCE_SLOTS.get(et)
        if not slots:
            continue
        action = row.EVENTMSGACTIONTYPE
        if et == 3 and action == V2_FT_TECHNICAL_ACTION:
            continue
        if et == 6 and action in V2_TECH_FOUL_ACTIONS:
            continue
        names = {"PLAYER1_ID": row.PLAYER1_NAME, "PLAYER2_ID": row.PLAYER2_NAME,
                 "PLAYER3_ID": row.PLAYER3_NAME}
        for id_col, ptype_col, team_col in slots:
            pid = int(getattr(row, id_col))
            ptype = getattr(row, ptype_col)
            if ptype not in (4, 5) or not (0 < pid < TEAM_ID_FLOOR):
                continue
            team = getattr(row, team_col)
            team = int(team) if pd.notna(team) else 0
            _register(gp, pid, team, names[id_col])
            gp.events.append(("ev", pos, period, t_abs, team, pid))
            pos += 1
    return gp


def parse_game_v3(game_id: str, df: pd.DataFrame, roster_maps) -> GameParse:
    """roster_maps: ordered list of {(team_id, norm_name) -> {pid}} dicts built
    from the boxscore for this game (nameI, familyName, firstName, full name).
    Used to resolve the sub-IN player, which V3 encodes only as description
    text. Descriptions usually use familyName but sometimes the FIRST name
    (e.g. 'Xu' for Xu Han while playerName/familyName/nameI all say 'Han')."""
    gp = GameParse(game_id, "V3")

    # per-team name maps observed in the pbp itself
    obs = defaultdict(lambda: defaultdict(set))  # team -> norm name -> {pid}
    for row in df.itertuples(index=False):
        pid = int(row.personId)
        team = int(row.teamId)
        if 0 < pid < TEAM_ID_FLOOR and team > 0:
            if row.playerName:
                obs[team][norm_name(row.playerName)].add(pid)
            if row.playerNameI:
                obs[team][norm_name(row.playerNameI)].add(pid)

    def resolve_in(name: str, team: int):
        key = (team, norm_name(name))
        cands = obs[team].get(norm_name(name), set())
        if len(cands) == 1:
            return next(iter(cands))
        for mp in roster_maps:
            hit = mp.get(key)
            if hit is not None and len(hit) == 1:
                return next(iter(hit))
        return None  # unknown or ambiguous

    pos = 0
    last_clock = {}
    for row in df.itertuples(index=False):
        at = row.actionType
        period = int(row.period)
        clock = parse_clock_v3(row.clock)
        if clock is None:
            gp.clock_bad += 1
            continue
        plen = period_len_sec(period)
        if clock > plen + 1e-9:
            gp.clock_bad += 1
            clock = plen
        if period in last_clock and clock > last_clock[period] + 1e-9:
            gp.order_bad += 1
        last_clock[period] = clock
        t_abs = period_start_abs(period) + (plen - clock)
        gp.periods.add(period)

        if at == "Substitution":
            out_pid = int(row.personId)
            team = int(row.teamId)
            if not (0 < out_pid < TEAM_ID_FLOOR):
                gp.anoms["sub_malformed"] += 1
                continue
            _register(gp, out_pid, team, row.playerName)
            m = SUB_DESC_RE.match(str(row.description or ""))
            in_pid = None
            if m:
                in_pid = resolve_in(m.group("inp"), team)
            if in_pid is None:
                gp.anoms["sub_in_unresolved"] += 1
            else:
                _register(gp, in_pid, team, None)
            gp.events.append(("sub", pos, period, t_abs, team, out_pid, in_pid))
            pos += 1
            continue

        if at not in V3_EVIDENCE_TYPES:
            continue
        st = str(row.subType or "")
        if at == "Foul" and "Technical" in st:
            continue
        if at == "Free Throw" and st == "Free Throw Technical":
            continue
        if at == "":
            d = str(row.description or "")
            if ("STEAL" not in d) and ("BLOCK" not in d):
                continue
        pid = int(row.personId)
        if not (0 < pid < TEAM_ID_FLOOR):
            continue
        team = int(row.teamId)
        _register(gp, pid, team, row.playerName)
        gp.events.append(("ev", pos, period, t_abs, team, pid))
        pos += 1
    return gp


# ----------------------------------------------------------------------------
# Starters + stints from normalized events (shared engine)
# ----------------------------------------------------------------------------
def derive_game(gp: GameParse, box_roster: dict):
    """box_roster: pid -> (box_sec, team_id) for this game (may be empty).
    Returns (starters_by_period_team, stints, anoms).
    stints: list of [team, pid, period, start_abs, end_abs, filled_flag]"""
    anoms = gp.anoms

    # resolve each player's team: pbp first, boxscore fallback
    def team_of(pid):
        t = gp.player_team.get(pid, 0)
        if t <= 0 and pid in box_roster:
            t = box_roster[pid][1]
        return t

    # bucket events by (period, team)
    per = defaultdict(list)  # (period, team) -> [(pos, t_abs, kind, pid)]
    for e in gp.events:
        if e[0] == "sub":
            _, pos, period, t_abs, team, out_pid, in_pid = e
            team = team if team > 0 else team_of(out_pid)
            per[(period, team)].append((pos, t_abs, "out", out_pid))
            if in_pid is not None:
                per[(period, team)].append((pos, t_abs, "in", in_pid))
        else:
            _, pos, period, t_abs, team, pid = e
            team = team if team > 0 else team_of(pid)
            per[(period, team)].append((pos, t_abs, "ev", pid))

    per.pop((0, 0), None)
    teams = sorted({t for (_, t) in per if t > 0})
    if len(teams) != 2:
        anoms["teams_not_2"] += 1

    starters = {}      # (period, team) -> set(pid)
    raw_counts = {}    # (period, team) -> n starters pre-fill
    stints = []
    open_periods = sorted(gp.periods)

    for period in open_periods:
        p_start = period_start_abs(period)
        p_end = p_start + period_len_sec(period)
        for team in teams:
            evs = sorted(per.get((period, team), []), key=lambda x: x[0])
            # Starter rule, ordering-glitch safe: pbp sometimes logs an event
            # for a player just BEFORE their own sub-in row at the SAME clock
            # (dead-ball sequences). So plain 'ev' evidence only proves the
            # player was on the floor if it is strictly earlier on the clock
            # than their first sub-in. A sub-OUT is proof regardless (you can
            # only be subbed out if you are on the floor).
            first_in = {}
            for pos, t_abs, kind, pid in evs:
                if kind == "in" and pid not in first_in:
                    first_in[pid] = (pos, t_abs)
            first_signal = {}
            for pos, t_abs, kind, pid in evs:
                if kind == "in" or pid in first_signal:
                    continue
                fi = first_in.get(pid)
                if fi is None or (pos < fi[0] and (kind == "out" or t_abs < fi[1] - 1e-9)):
                    first_signal[pid] = pos
            cand = sorted(first_signal, key=lambda p: first_signal[p])
            raw_counts[(period, team)] = len(cand)
            if len(cand) > 5:
                anoms["over5_raw"] += 1
                cand = cand[:5]
            start_set = set(cand)
            starters[(period, team)] = start_set

            # replay subs to build stints
            on = dict.fromkeys(start_set, p_start)  # pid -> stint start
            for pos, t_abs, kind, pid in evs:
                if kind == "out":
                    if pid in on:
                        stints.append([team, pid, period, on.pop(pid), t_abs, 0])
                    else:
                        anoms["sub_out_not_on"] += 1
                elif kind == "in":
                    if pid in on:
                        anoms["sub_in_already_on"] += 1
                    else:
                        on[pid] = t_abs
                else:
                    if pid not in on:
                        anoms["evidence_while_off"] += 1
            for pid, t0 in on.items():
                stints.append([team, pid, period, t0, p_end, 0])

    # ---- boxscore-deficit fill for team-periods that resolved < 5 ----
    derived_sec = Counter()
    for team, pid, period, t0, t1, _ in stints:
        derived_sec[pid] += t1 - t0

    for period in open_periods:
        p_start = period_start_abs(period)
        plen = period_len_sec(period)
        p_end = p_start + plen
        for team in teams:
            k = len(starters.get((period, team), ()))
            if k >= 5:
                continue
            anoms["under5_raw"] += 1
            need = 5 - k
            appeared = {pid for t, pid, pp, *_ in stints if pp == period and t == team}
            appeared |= {pid for pos, t_abs, kind, pid in per.get((period, team), [])}
            cands = []
            for pid, (bsec, bteam) in box_roster.items():
                if bteam != team or pid in appeared or not np.isfinite(bsec):
                    continue
                deficit = bsec - derived_sec.get(pid, 0.0)
                if deficit >= 0.5 * plen:
                    cands.append((deficit, pid))
            cands.sort(reverse=True)
            took = cands[:need]
            if len(cands) > need and took and (cands[need][0] >= took[-1][0] - 60):
                anoms["fill_ambiguous"] += 1
            for deficit, pid in took:
                stints.append([team, pid, period, p_start, p_end, 1])
                starters[(period, team)].add(pid)
                derived_sec[pid] += plen
                anoms["filled_from_box"] += 1
            if len(starters[(period, team)]) < 5:
                anoms["still_under5"] += 1

    return starters, raw_counts, stints


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Loading boxscore minute truth (advanced/misc/gamelogs)...")
    box = load_boxscore_truth()
    print(f"  {len(box):,} boxscore player-game rows, "
          f"{box['GAME_ID'].nunique():,} games, {time.time()-t0:.1f}s")

    box_by_game = {g: d for g, d in box.groupby("GAME_ID")}

    # discover pbp files, detect schema per file
    files = []
    for f in sorted(glob.glob(os.path.join(PBP_V2_DIR, "pbp_*.parquet"))):
        files.append(f)
    for f in sorted(glob.glob(os.path.join(PBP_REFRESH_DIR, "pbp_*.parquet"))):
        files.append(f)
    print(f"{len(files)} pbp files discovered")

    starters_rows, stint_rows, failed = [], [], []
    global_anoms = Counter()
    n_by_schema = Counter()
    raw5 = Counter()      # raw team-period resolution histogram
    final5 = Counter()
    order_bad_games = 0
    seen_games = set()

    for i, f in enumerate(files):
        if i and i % 100 == 0:
            print(f"  ... {i}/{len(files)} games, {time.time()-t0:.1f}s elapsed")
        game_id = os.path.basename(f).split("_")[1].split(".")[0]
        if game_id in seen_games:
            failed.append((game_id, "?", "duplicate game id across dirs"))
            continue
        try:
            cols = pq.read_schema(f).names
            schema = "V2" if "EVENTMSGTYPE" in cols else ("V3" if "actionType" in cols else "UNKNOWN")
            if schema == "UNKNOWN":
                failed.append((game_id, "?", "unrecognized schema"))
                continue
            df = pd.read_parquet(f)
        except Exception as ex:
            failed.append((game_id, "?", f"read error: {type(ex).__name__}"))
            continue
        if df.empty:
            failed.append((game_id, schema, "empty pbp"))
            continue

        gb = box_by_game.get(game_id)
        box_roster = {}
        nameI2pid, fam2pid, first2pid, full2pid = (defaultdict(set) for _ in range(4))
        if gb is not None:
            for r in gb.itertuples(index=False):
                if np.isfinite(r.BOX_SEC):
                    box_roster[r.PLAYER_ID] = (r.BOX_SEC, r.TEAM_ID)
                fam2pid[(r.TEAM_ID, norm_name(r.FAMILY_NAME))].add(r.PLAYER_ID)
                if r.NAME_I:
                    nameI2pid[(r.TEAM_ID, norm_name(r.NAME_I))].add(r.PLAYER_ID)
                if r.FIRST_NAME:
                    first2pid[(r.TEAM_ID, norm_name(r.FIRST_NAME))].add(r.PLAYER_ID)
                if r.PLAYER_NAME:
                    full2pid[(r.TEAM_ID, norm_name(r.PLAYER_NAME))].add(r.PLAYER_ID)

        try:
            if schema == "V2":
                gp = parse_game_v2(game_id, df)
            else:
                gp = parse_game_v3(game_id, df, [nameI2pid, fam2pid, first2pid, full2pid])
            if not gp.events:
                failed.append((game_id, schema, "no usable events"))
                continue
            if not any(e[0] == "sub" for e in gp.events):
                global_anoms["game_no_subs"] += 1
            starters, raw_counts, stints = derive_game(gp, box_roster)
        except Exception as ex:
            failed.append((game_id, schema, f"derive error: {type(ex).__name__}: {ex}"))
            continue

        seen_games.add(game_id)
        n_by_schema[schema] += 1
        global_anoms.update(gp.anoms)
        if gp.clock_bad:
            global_anoms["clock_bad_rows"] += gp.clock_bad
        if gp.order_bad:
            order_bad_games += 1

        for (period, team), n in raw_counts.items():
            raw5[min(n, 6)] += 1
        for (period, team), s in starters.items():
            final5[min(len(s), 6)] += 1

        def name_of(pid):
            if gb is not None:
                hit = gb.loc[gb.PLAYER_ID == pid, "PLAYER_NAME"]
                if len(hit) and hit.iloc[0]:
                    return hit.iloc[0]
            return gp.player_name.get(pid, "")

        p1 = {(t): s for (p, t), s in starters.items() if p == 1}
        for team, pids in sorted(p1.items()):
            for pid in sorted(pids):
                starters_rows.append((game_id, team, pid, name_of(pid), 1))
            if len(pids) != 5:
                global_anoms["p1_not_5_starters"] += 1

        tot = Counter()
        for team, pid, period, s, e, filled in stints:
            tot[pid] += e - s
        for team, pid, period, s, e, filled in sorted(stints, key=lambda r: (r[0], r[2], r[3], r[1])):
            stint_rows.append((game_id, gp.schema, team, pid, name_of(pid), period,
                               round(s, 1), round(e, 1), round(e - s, 1),
                               round(tot[pid], 1), filled))

    print(f"  ... {len(files)}/{len(files)} games, {time.time()-t0:.1f}s elapsed")

    # ------------------------------------------------------------------ outputs
    starters_df = pd.DataFrame(starters_rows, columns=[
        "GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "period1_starter"])
    starters_csv = os.path.join(OUT_DIR, "starters.csv")
    starters_df.to_csv(starters_csv, index=False, encoding="utf-8")

    stints_df = pd.DataFrame(stint_rows, columns=[
        "GAME_ID", "SCHEMA", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "period",
        "stint_start_sec", "stint_end_sec", "stint_sec", "player_game_sec", "box_filled"])
    stints_path = os.path.join(OUT_DIR, "stints.parquet")
    stints_df.to_parquet(stints_path, index=False)

    derived_min = (stints_df.groupby(["GAME_ID", "TEAM_ID", "PLAYER_ID"], as_index=False)
                   .agg(PLAYER_NAME=("PLAYER_NAME", "first"), SCHEMA=("SCHEMA", "first"),
                        derived_sec=("stint_sec", "sum")))
    val = derived_min.merge(
        box[["GAME_ID", "PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "BOX_SEC",
             "BOX_SOURCE", "BOX_STARTER", "HAS_STARTER_FLAG"]],
        on=["GAME_ID", "PLAYER_ID"], how="outer", suffixes=("", "_box"), indicator=True)
    val["TEAM_ID"] = val["TEAM_ID"].fillna(val["TEAM_ID_box"]).astype("Int64")
    val["PLAYER_NAME"] = val["PLAYER_NAME"].fillna(val["PLAYER_NAME_box"])
    # keep boxscore-only rows only for games we actually processed (played but never derived)
    val = val[(val["_merge"] != "right_only") | (val["GAME_ID"].isin(seen_games))]
    val.loc[val["_merge"] == "right_only", "derived_sec"] = \
        val.loc[val["_merge"] == "right_only", "derived_sec"].fillna(0.0)
    val = val[~((val["_merge"] == "right_only") & (~np.isfinite(val["BOX_SEC"]) | (val["BOX_SEC"] <= 0)))]
    val["derived_min"] = (val["derived_sec"] / 60).round(2)
    val["box_min"] = (val["BOX_SEC"] / 60).round(2)
    val["diff_min"] = (val["derived_min"] - val["box_min"]).round(2)
    val_out = val[["GAME_ID", "TEAM_ID", "PLAYER_ID", "PLAYER_NAME", "SCHEMA",
                   "derived_min", "box_min", "diff_min", "BOX_SOURCE"]].copy()
    val_csv = os.path.join(OUT_DIR, "lineup_validation.csv")
    val_out.to_csv(val_csv, index=False, encoding="utf-8")

    failed_df = pd.DataFrame(failed, columns=["GAME_ID", "SCHEMA", "REASON"])
    failed_csv = os.path.join(OUT_DIR, "failed_games.csv")
    failed_df.to_csv(failed_csv, index=False, encoding="utf-8")

    # ------------------------------------------------------------------ metrics
    print("\n================ REPORT ================")
    print(f"Games processed: {dict(n_by_schema)}  |  failed: {len(failed)}")
    if len(failed):
        print(failed_df.groupby("REASON").size().to_string())

    tp_raw_total = sum(raw5.values())
    tp_final_total = sum(final5.values())
    raw_exact = raw5[5] / tp_raw_total * 100 if tp_raw_total else 0
    fin_exact = final5[5] / tp_final_total * 100 if tp_final_total else 0
    print(f"\nTeam-periods: {tp_raw_total:,}")
    print(f"  exactly 5 at period start (raw event inference): {raw_exact:.2f}%  "
          f"histogram {dict(sorted(raw5.items()))}")
    print(f"  exactly 5 after boxscore-deficit fill:           {fin_exact:.2f}%  "
          f"histogram {dict(sorted(final5.items()))}  (target >= 95%)")

    both = val.dropna(subset=["diff_min"])
    both = both[np.isfinite(both["box_min"])]
    ad = both["diff_min"].abs()
    med, p95 = ad.median(), ad.quantile(0.95)
    print(f"\nMinutes validation on {len(both):,} player-games "
          f"({both['GAME_ID'].nunique():,} games covered):")
    print(f"  median |derived-box| = {med:.3f} min (target <= 0.5)")
    print(f"  95th pct |derived-box| = {p95:.3f} min (target <= 2.0)")
    print(f"  within 0.5 min: {(ad <= 0.5).mean()*100:.1f}%   within 2 min: {(ad <= 2.0).mean()*100:.1f}%")
    for src, grp in both.groupby("BOX_SOURCE"):
        print(f"    {src:38s} n={len(grp):6,}  median={grp['diff_min'].abs().median():.3f}  "
              f"p95={grp['diff_min'].abs().quantile(0.95):.3f}")

    # starter cross-check vs boxscore flags
    flg = val[(val["HAS_STARTER_FLAG"] == True) & np.isfinite(val["box_min"])]
    if len(flg):
        p1s = starters_df.set_index(["GAME_ID", "PLAYER_ID"]).index
        flg = flg.assign(derived_starter=flg.set_index(["GAME_ID", "PLAYER_ID"]).index.isin(p1s).astype(int))
        gmatch = (flg.groupby("GAME_ID")
                  .apply(lambda d: (d["derived_starter"] == d["BOX_STARTER"]).all(), include_groups=False))
        agree = (flg["derived_starter"] == flg["BOX_STARTER"]).mean() * 100
        print(f"\nStarter cross-check vs boxscore flags: {agree:.2f}% player-row agreement, "
              f"{gmatch.mean()*100:.2f}% of {len(gmatch):,} games with perfect 10/10 starter match")

    print(f"\nAnomaly counters: {dict(sorted(global_anoms.items()))}")
    print(f"Games with clock-order inversions: {order_bad_games}")

    print("\nSample rows -- starters.csv:")
    print(starters_df.head(3).to_string(index=False))
    print("\nSample rows -- stints.parquet:")
    print(stints_df.head(3).to_string(index=False))
    print("\nSample rows -- lineup_validation.csv:")
    print(val_out.head(3).to_string(index=False))

    print(f"\nWrote:\n  {starters_csv}\n  {stints_path}\n  {val_csv}\n  {failed_csv}")
    print(f"Total runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
