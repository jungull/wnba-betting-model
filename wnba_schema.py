"""
wnba_schema.py
==============
THE single V2/V3 schema-normalization module for the WNBA prediction engine.
Everything downstream (master rebuild, RAPM stints, channel features, minutes
model) imports from this file. Design: TWO THIN PARSERS (one per schema era)
feeding ONE canonical model. No file IO, no network, no side effects on import,
no cross-game state — each call sees exactly the frame(s) it is given
(HANDOFF.md §3 constitution: nothing here may peek across games/time).

Dependencies: pandas, numpy, stdlib only.

Eras (`detect_era`)
-------------------
- 'v2'          NBA-stats V2: pbp (EVENTMSGTYPE, PCTIMESTRING "MM:SS", PLAYERx
                slots) — data/playbyplay/pbp_*.parquet and the V2 strays inside
                data/refresh_2026/pbp/.
- 'v3'          camelCase V3: pbp (actionType, clock "PT09M45.00S", personId)
                and per-game boxscores (misc/advanced: gameId/personId/minutes).
- 'gamelog_old' uppercase per-game traditional box rows concatenated per season
                (data/wnba_gamelog_<year>.parquet: START_POSITION, COMMENT,
                MIN "35.000000:36" or "33:02", stat col TO).
- 'gamelog_new' LeagueGameLog-style refresh frames (SEASON_ID, GAME_DATE,
                MIN int64 rounded, stat col TOV).

Canonical play-by-play frame (`normalize_pbp`)
----------------------------------------------
One row per person/team reference, source row order preserved (row order is the
chronological truth in BOTH eras — EVENTNUM/actionNumber are non-monotonic in
~97% of games). Columns:

  game_id              str
  event_idx            int64    0..n-1 chronological within game
  period               int64
  game_seconds_elapsed float64  absolute seconds from tip (periods 1-4 are 600s,
                                OTs 300s); NaN if the clock string was unparseable
  team_id              Int64    NA when unknown / neutral (e.g. official timeout)
  person_id            Int64    NA for team events (team rebound/turnover/timeout),
                                coach/official references, junk ids (Instant
                                Replay carries garbage person ids in BOTH eras),
                                and unresolved V3 name references
  player_name          object   '' when unknown
  event_type           object   canonical enum: shot_made / shot_missed / ft_made /
                                ft_missed / rebound / turnover / foul / sub_in /
                                sub_out / timeout / period_start / period_end / other
  event_subtype        object   for enum'd types: era-native flavor text except
                                where canonicalized across eras (free throws
                                "Free Throw 1 of 2"...; timeouts "Regular"/
                                "Official"/...; periods "start"/"end").
                                For event_type 'other' the subtype IS the
                                canonical classifier: 'Assist', 'Steal', 'Block',
                                'Foul Drawn', 'Jump Ball', 'Jump Ball Tip',
                                'Ejection[:kind]', 'Violation:<kind>',
                                'Instant Replay', or the raw source label.
  technical_flag       bool     True on technical fouls / technical FTs — the rows
                                where the listed person may legally be OFF the
                                floor (bench player / coach / team technicals).
                                Lineup engines must filter on this, not re-learn it.
  points               Int64    points scored by this event: 3/2 for shot_made,
                                1 for ft_made, 0 for shot_missed/ft_missed,
                                NA otherwise
  home_score           Int64    running score where the source row carries one
  away_score           Int64    (V2 SCORE is "AWAY - HOME"; V3 scoreHome/scoreAway);
                                NA elsewhere — forward-fill downstream if needed
  detail               object   raw description text (V2: HOME|NEUTRAL|VISITOR
                                joined with ' | ')
  era                  object   'v2' | 'v3'

Substitutions emit TWO rows in both eras: sub_out then sub_in at the same
timestamp. V2 encodes both ids structurally (PLAYER1=out, PLAYER2=in). V3 only
structures the OUTGOING personId; the incoming player exists solely in the
description "SUB: <IN> FOR <OUT>" and is name-resolved against (a) names
observed in the pbp itself, then (b) the optional `roster` frame via the chain
nameI -> familyName -> firstName -> full name (descriptions sometimes use the
FIRST name, e.g. 'Xu' for Xu Han). Unresolved sub_in rows keep person_id=NA and
are counted in attrs['anomalies'].

Companion rows unify the eras' side-channel encodings: V2 structured slots
(assist=PLAYER2 on made shots, steal=PLAYER2 on turnovers, block=PLAYER3 on
missed shots, foul-drawn=PLAYER2 on fouls, jump-ball slots) and V3's separate
blank-actionType STEAL/BLOCK rows plus description-parsed assists and jump-ball
participants all land as event_type='other' rows with the canonical subtypes
listed above.

Ported era traps (do NOT re-learn these):
- V2: PERSONxTYPE {4,5}=player, {2,3}=team (id lives in PLAYERx_ID), else
  coach/official/none -> person_id NA. Technical foul EVENTMSGACTIONTYPEs
  {11,12,13,16,18,19,25,30} (+ 'tech' description fallback) can name off-floor
  people. FT made/missed = absence/presence of MISS in the description (agrees
  100% with SCORE presence). EVENTNUM is non-monotonic; row order is truth.
- V3: timeouts put the TEAM id in personId (teamId=0); team rebounds/turnovers
  put the team id in personId with teamId=0; steal/block are separate rows with
  BLANK actionType; Instant Replay rows carry junk person ids (and sometimes a
  real-looking playerName — never trust them); FT shotResult is EMPTY, made/miss
  comes from the MISS token; the sub-IN player is description-text only.

`normalize_pbp(df).attrs['anomalies']` carries per-call counters (unresolved
names, malformed subs, clamped/unparseable clocks, order inversions, ...).
pandas may drop .attrs on further operations — read it right after the call.

Canonical player-box frame (`normalize_player_box`)
---------------------------------------------------
Guaranteed identity block (always present, same dtypes, all eras):
  game_id, team_id, player_id, player_name, first_name, family_name, name_i,
  position (F/G/C for starters, '' bench, NA where source lacks it),
  starter_flag (Int64 1/0; NA where not derivable — LeagueGameLog era),
  dnp_reason (comment text on no-minutes rows: "DNP - Coach's Decision", ...;
  NA where absent), minutes (float minutes via the canonical parser),
  minutes_raw (untouched source value), era.
Stat columns follow under canonical snake_case names — one name per concept
regardless of source spelling (TO/TOV/turnovers -> tov, PF/foulsPersonal -> pf,
BLK/blocks -> blk, pointsPaint -> points_paint, ...). Mapping lives in the
column-map tables below (not if-soup); unmapped source columns fall through a
deterministic camelCase/UPPERCASE -> snake_case rename so V3 advanced columns
arrive automatically.

Minutes strings (`minutes_to_float`): ONE regex handles every observed format —
"33:02", corrupted "35.000000:36" (2021-2023), sub-minute "0.000000:42",
int/float minutes (refresh gamelogs), and ''/None/NaN for DNP (-> NaN).

Known semantic gaps this module can NOT bridge (be explicit downstream):
- V3 pbp has NO foul-drawn attribution (V2 PLAYER2 slot -> 'Foul Drawn'
  companion rows exist only in v2; V3 foul descriptions carry no drawn-by;
  use misc box `fouls_drawn` for V3-era games).
- V3 sub-in / assist / jump-ball participants are name-resolved text, so a
  small unresolved residue is possible (counted, never guessed).
- Shot-location/subtype vocabularies stay era-native in event_subtype for
  shots/rebounds/turnovers/fouls (V2 int action codes vs V3 labels); only the
  technical distinction, FT labels, timeout kinds, violation kinds and period
  start/end are canonicalized across eras.
- gamelog_new frames cannot yield starter_flag or dnp_reason (structurally
  absent); minutes there are endpoint-rounded ints.
- V2 coach technicals null the person (PERSONxTYPE 6/7); V3 coach technicals
  are indistinguishable from player technicals without a roster — pass
  `roster` to normalize_pbp to null non-roster persons on technical rows.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

__all__ = [
    "detect_era",
    "parse_clock",
    "minutes_to_float",
    "minutes_parse_report",
    "normalize_pbp",
    "normalize_player_box",
    "period_length_sec",
    "period_start_sec",
    "norm_name",
    "TEAM_ID_FLOOR",
    "PBP_COLUMNS",
    "EVENT_TYPES",
    "V2_TECH_FOUL_ACTIONS",
    "MIN_RE",
]

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
TEAM_ID_FLOOR = 1_000_000_000  # ids >= this are team ids, never players

EVENT_TYPES = (
    "shot_made", "shot_missed", "ft_made", "ft_missed", "rebound", "turnover",
    "foul", "sub_in", "sub_out", "timeout", "period_start", "period_end", "other",
)

PBP_COLUMNS = [
    "game_id", "event_idx", "period", "game_seconds_elapsed", "team_id",
    "person_id", "player_name", "event_type", "event_subtype", "technical_flag",
    "points", "home_score", "away_score", "detail", "era",
]

# V2 EVENTMSGTYPE -> canonical event_type (types needing per-row logic handled
# in the parser: 3 free throws, 8 substitutions)
V2_SUB = 8
V2_FT = 3

# V2 foul EVENTMSGACTIONTYPEs where the listed person can be OFF the floor
# (technicals on bench players / coaches / team). Def-3-sec (17), flagrants
# (14, 15) and double personal (10) are committed by on-court players and are
# NOT technicals. (Battle-tested set from derive_lineups.py.)
V2_TECH_FOUL_ACTIONS = frozenset({11, 12, 13, 16, 18, 19, 25, 30})
V2_FT_TECHNICAL_ACTION = 16

# V2 FT EVENTMSGACTIONTYPE -> canonical label (verified against description
# text across a 60-game sample; identical vocabulary to V3 subType).
V2_FT_ACTION_LABELS = {
    10: "Free Throw 1 of 1", 11: "Free Throw 1 of 2", 12: "Free Throw 2 of 2",
    13: "Free Throw 1 of 3", 14: "Free Throw 2 of 3", 15: "Free Throw 3 of 3",
    16: "Free Throw Technical", 18: "Free Throw Flagrant 1 of 2",
    19: "Free Throw Flagrant 2 of 2", 20: "Free Throw Flagrant 1 of 1",
    25: "Free Throw Clear Path 1 of 2", 26: "Free Throw Clear Path 2 of 2",
}

# V2 PLAYERx slot companions: EVENTMSGTYPE -> [(slot, canonical subtype), ...]
V2_COMPANION_SLOTS = {
    1: [("2", "Assist")],
    2: [("3", "Block")],
    5: [("2", "Steal")],
    6: [("2", "Foul Drawn")],
    10: [("2", "Jump Ball"), ("3", "Jump Ball Tip")],
}

# ----------------------------------------------------------------------------
# Regexes
# ----------------------------------------------------------------------------
# The canonical minutes regex (MINUTES_MODEL_SPEC §2.1): parses "33:02",
# "35.000000:36", "0.000000:42" — verified 0 failures across all season files.
MIN_RE = re.compile(r"^(\d+)(?:\.0+)?:(\d{1,2})$")

V2_CLOCK_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
V3_CLOCK_RE = re.compile(r"^PT(\d+)M([\d.]+)S$")

SUB_DESC_RE = re.compile(r"^SUB:\s*(?P<inp>.+?)\s+FOR\s+(?P<outp>.+?)\s*$")
MISS_RE = re.compile(r"\bMISS\b")
THREE_PT_RE = re.compile(r"\b3PT\b")
AST_DESC_RE = re.compile(r"\((?P<name>[^()]+?)\s+\d+\s+AST\)")
FT_PHRASE_RE = re.compile(r"(Free Throw[^()]*?)(?:\s*\(|\s*$)")
TIMEOUT_KIND_RE = re.compile(r"Timeout:\s*([^(]+?)(?:\s*\(|\s*$)")
VIOLATION_KIND_RE = re.compile(r"Violation:\s*([A-Za-z ]+)")
EJECTION_KIND_RE = re.compile(r"Ejection:\s*([A-Za-z ]+)")
JUMP_BALL_RE = re.compile(
    r"Jump Ball(?:\s*\([A-Z]+\))?\s+(?P<a>.+?)\s+vs\.\s+(?P<b>.+?)"
    r"(?::\s*Tip to\s+(?P<tip>.+?))?\s*$")
SCORE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
TECH_TOKEN_RE = re.compile(r"tech", re.IGNORECASE)


# ----------------------------------------------------------------------------
# Small shared helpers
# ----------------------------------------------------------------------------
def period_length_sec(period: int) -> float:
    """Regulation periods are 600s; every OT is 300s."""
    return 600.0 if period <= 4 else 300.0


def period_start_sec(period: int) -> float:
    """Absolute game-seconds at which `period` begins."""
    return 600.0 * (period - 1) if period <= 4 else 2400.0 + 300.0 * (period - 5)


def parse_clock(clock_str, era: str) -> float:
    """Seconds REMAINING in the period from an era-native clock string.

    era='v2': "MM:SS"; era='v3': ISO-ish duration "PT09M45.00S".
    Returns float seconds, or NaN if unparseable.
    """
    e = str(era).lower()
    s = "" if clock_str is None else str(clock_str)
    if e == "v2":
        m = V2_CLOCK_RE.match(s)
        return float(int(m.group(1)) * 60 + int(m.group(2))) if m else float("nan")
    if e == "v3":
        m = V3_CLOCK_RE.match(s)
        return int(m.group(1)) * 60.0 + float(m.group(2)) if m else float("nan")
    raise ValueError(f"parse_clock: unknown era {era!r} (expected 'v2' or 'v3')")


def minutes_to_float(x) -> float:
    """Float MINUTES from any boxscore minutes representation.

    Handles: "33:02" | "35.000000:36" (= 35:36) | "0.000000:42" | int/float
    minutes (refresh gamelogs) | '' / None / NaN (DNP rows) -> NaN.
    One regex (MIN_RE), numeric passthrough, NaN otherwise.
    """
    if x is None:
        return float("nan")
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float("nan") if pd.isna(x) else float(x)
    s = str(x).strip()
    if not s:
        return float("nan")
    m = MIN_RE.match(s)
    if m:
        return float(m.group(1)) + float(m.group(2)) / 60.0
    try:
        return float(s)
    except ValueError:
        return float("nan")


def minutes_parse_report(values) -> dict:
    """Parse-coverage report for a minutes column.

    Returns {'n', 'n_blank', 'n_parsed', 'n_failed', 'failed_values'} where a
    FAILURE is a non-blank source value that minutes_to_float cannot parse
    (blank/None/NaN are legitimate DNP encodings, not failures).
    """
    ser = pd.Series(list(values))
    blank = ser.isna() | ser.astype(str).str.strip().eq("")
    parsed = ser.map(minutes_to_float)
    failed = (~blank) & parsed.isna()
    return {
        "n": int(len(ser)),
        "n_blank": int(blank.sum()),
        "n_parsed": int(((~blank) & parsed.notna()).sum()),
        "n_failed": int(failed.sum()),
        "failed_values": ser[failed].astype(str).unique()[:20].tolist(),
    }


def norm_name(s) -> str:
    """Casefold, strip accents/periods/extra spaces for tolerant name matching."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.replace(".", " ")).strip().casefold()


# ----------------------------------------------------------------------------
# Era detection
# ----------------------------------------------------------------------------
def detect_era(obj) -> str:
    """'v2' | 'v3' | 'gamelog_old' | 'gamelog_new' from a DataFrame (or any
    iterable of column names). Detection is per-frame — the refresh pbp
    directory contains V2 strays, so never assume era from a file's location.
    """
    cols = set(obj.columns) if hasattr(obj, "columns") else set(obj)
    if "EVENTMSGTYPE" in cols:
        return "v2"
    if "actionType" in cols:
        return "v3"
    if "personId" in cols and "gameId" in cols:
        return "v3"  # camelCase boxscore (misc / advanced / traditional)
    if "START_POSITION" in cols:
        return "gamelog_old"
    if "SEASON_ID" in cols and "GAME_ID" in cols and "MIN" in cols:
        return "gamelog_new"
    raise ValueError(
        "detect_era: unrecognized schema. Expected V2 pbp (EVENTMSGTYPE), V3 pbp "
        "(actionType), V3 boxscore (gameId/personId), old gamelog (START_POSITION) "
        f"or LeagueGameLog (SEASON_ID/GAME_ID/MIN). Got columns: {sorted(cols)[:12]}...")


# ----------------------------------------------------------------------------
# Roster index — powers V3 name resolution (sub-ins, assists, jump balls)
# ----------------------------------------------------------------------------
def _first_col(df, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return None


class _RosterIndex:
    """Per-game name -> player_id lookups.

    Built from (a) names observed in the pbp itself and (b) an optional
    boxscore roster frame (canonical normalize_player_box output or raw
    V3/uppercase box columns). Resolution priority mirrors the battle-tested
    derive_lineups chain: pbp-observed -> nameI -> familyName -> firstName ->
    full name; a hit must be UNIQUE to count (never guess between two Smiths).
    """

    def __init__(self):
        self.obs = defaultdict(lambda: defaultdict(set))   # team -> norm name -> {pid}
        self.maps = [defaultdict(set) for _ in range(4)]   # (team, norm) -> {pid}: nameI, family, first, full
        self.pid_team = {}
        self.pid_name = {}

    def observe(self, team, pid, name):
        if pid and 0 < pid < TEAM_ID_FLOOR and team and team > 0 and name:
            self.obs[team][norm_name(name)].add(pid)
            self.pid_team.setdefault(pid, team)
            if len(str(name)) > len(self.pid_name.get(pid, "")):
                self.pid_name[pid] = str(name)

    def add_roster(self, roster: pd.DataFrame):
        pid_s = _first_col(roster, "player_id", "personId", "PLAYER_ID")
        team_s = _first_col(roster, "team_id", "teamId", "TEAM_ID")
        if pid_s is None or team_s is None:
            raise ValueError("roster frame needs player_id/personId and team_id/teamId columns")
        name_i = _first_col(roster, "name_i", "nameI")
        family = _first_col(roster, "family_name", "familyName")
        first = _first_col(roster, "first_name", "firstName")
        full = _first_col(roster, "player_name", "PLAYER_NAME")
        if full is None and first is not None and family is not None:
            full = first.fillna("").astype(str) + " " + family.fillna("").astype(str)
        for i in range(len(roster)):
            pid, team = pid_s.iat[i], team_s.iat[i]
            if pd.isna(pid) or pd.isna(team):
                continue
            pid, team = int(pid), int(team)
            if not (0 < pid < TEAM_ID_FLOOR) or team <= 0:
                continue
            self.pid_team.setdefault(pid, team)
            fullname = str(full.iat[i]) if full is not None and pd.notna(full.iat[i]) else ""
            if fullname and len(fullname) > len(self.pid_name.get(pid, "")):
                self.pid_name[pid] = fullname
            fam = str(family.iat[i]) if family is not None and pd.notna(family.iat[i]) else ""
            fst = str(first.iat[i]) if first is not None and pd.notna(first.iat[i]) else ""
            if not fam and fullname:
                fam = fullname.split()[-1]
            if not fst and fullname:
                fst = fullname.split()[0]
            for mp, nm in zip(self.maps, (
                    str(name_i.iat[i]) if name_i is not None and pd.notna(name_i.iat[i]) else "",
                    fam, fst, fullname)):
                if nm:
                    mp[(team, norm_name(nm))].add(pid)

    def known_player(self, pid) -> bool:
        return pid in self.pid_team

    def name_of(self, pid) -> str:
        return self.pid_name.get(pid, "")

    def resolve(self, name, team):
        """Unique pid for `name` on `team`, else None."""
        key = norm_name(name)
        if not key:
            return None
        cands = self.obs[team].get(key, set())
        if len(cands) == 1:
            return next(iter(cands))
        for mp in self.maps:
            hit = mp.get((team, key), set())
            if len(hit) == 1:
                return next(iter(hit))
        return None

    def resolve_gamewide(self, name):
        """(team, pid) if `name` is unique across BOTH teams, else (None, None)."""
        key = norm_name(name)
        if not key:
            return None, None
        cands = set()
        for team, names in self.obs.items():
            for pid in names.get(key, ()):  # pragma: no branch
                cands.add((team, pid))
        for mp in self.maps:
            for (team, nm), pids in mp.items():
                if nm == key:
                    cands.update((team, p) for p in pids)
        if len(cands) == 1:
            return next(iter(cands))
        return None, None


# ----------------------------------------------------------------------------
# normalize_pbp
# ----------------------------------------------------------------------------
def normalize_pbp(df: pd.DataFrame, roster: pd.DataFrame | None = None) -> pd.DataFrame:
    """Era-detect a raw pbp frame and return the canonical event frame.

    `df` may hold one game or several concatenated games OF THE SAME ERA;
    parsing state never crosses game boundaries. `roster` (optional) is a
    boxscore frame — canonical normalize_player_box output or raw V3/uppercase
    box rows — used ONLY to strengthen V3 name resolution and to null coach
    person ids on technical rows; it may span many games (filtered per game by
    game id). Result column contract: PBP_COLUMNS. Per-call anomaly counters
    land in result.attrs['anomalies'] — read them immediately (pandas may drop
    attrs on later operations).
    """
    era = detect_era(df)
    if era not in ("v2", "v3"):
        raise ValueError(f"normalize_pbp expects a pbp frame, got era {era!r}")
    anoms = Counter()
    gid_col = "GAME_ID" if era == "v2" else "gameId"
    roster_gid = None
    if roster is not None:
        rg = _first_col(roster, "game_id", "gameId", "GAME_ID")
        roster_gid = rg.astype(str) if rg is not None else None

    out_rows = []  # one tuple per canonical row
    for gid, g in df.groupby(df[gid_col].astype(str), sort=False):
        r = roster
        if roster is not None and roster_gid is not None:
            r = roster[(roster_gid == gid).values]
            if r.empty:
                r = None
        if era == "v2":
            _parse_game_v2(gid, g, r, out_rows, anoms)
        else:
            _parse_game_v3(gid, g, r, out_rows, anoms)

    res = pd.DataFrame(out_rows, columns=[
        "game_id", "period", "game_seconds_elapsed", "team_id", "person_id",
        "player_name", "event_type", "event_subtype", "technical_flag",
        "points", "home_score", "away_score", "detail"])
    res["era"] = era
    res["event_idx"] = res.groupby("game_id", sort=False).cumcount()
    for c in ("team_id", "person_id", "points", "home_score", "away_score"):
        res[c] = res[c].astype("Int64")
    res["period"] = res["period"].astype("int64")
    res["game_seconds_elapsed"] = res["game_seconds_elapsed"].astype("float64")
    res["technical_flag"] = res["technical_flag"].astype(bool)
    res = res[PBP_COLUMNS]
    res.attrs["anomalies"] = dict(anoms)
    return res


def _elapsed(period: int, clock_sec: float, anoms: Counter):
    """Absolute game seconds from a period + seconds-remaining clock."""
    plen = period_length_sec(period)
    if np.isnan(clock_sec):
        anoms["clock_unparseable"] += 1
        return float("nan")
    if clock_sec > plen + 1e-9:
        anoms["clock_over_period_clamped"] += 1
        clock_sec = plen
    return period_start_sec(period) + (plen - clock_sec)


# ------------------------------- V2 parser ----------------------------------
def _v2_slot(row, slot: str):
    """Classify a V2 PLAYERx slot.

    Returns (kind, team_id_or_None, pid_or_None, name):
      kind 'person' — PERSONxTYPE 4/5 with a player-range id
      kind 'team'   — PERSONxTYPE 2/3 (team id lives in PLAYERx_ID) or id >= floor
      kind 'none'   — empty / official / coach (PERSONxTYPE 0,1,6,7) -> person NA
    """
    pid = getattr(row, f"PLAYER{slot}_ID")
    ptype = getattr(row, f"PERSON{slot}TYPE")
    team = getattr(row, f"PLAYER{slot}_TEAM_ID")
    name = getattr(row, f"PLAYER{slot}_NAME")
    pid = int(pid) if pd.notna(pid) else 0
    ptype = int(ptype) if pd.notna(ptype) else 0
    team = int(team) if pd.notna(team) and team > 0 else None
    name = str(name) if pd.notna(name) else ""
    if ptype in (4, 5) and 0 < pid < TEAM_ID_FLOOR:
        return "person", team, pid, name
    if ptype in (2, 3) or pid >= TEAM_ID_FLOOR:
        return "team", (pid if pid >= TEAM_ID_FLOOR else team), None, ""
    return "none", team, None, name


def _parse_game_v2(gid, g, roster, out, anoms):
    emit = out.append
    last_clock = {}
    for row in g.itertuples(index=False):
        et = int(row.EVENTMSGTYPE)
        action = int(row.EVENTMSGACTIONTYPE) if pd.notna(row.EVENTMSGACTIONTYPE) else 0
        period = int(row.PERIOD)
        clock = parse_clock(row.PCTIMESTRING, "v2")
        if not np.isnan(clock):
            if period in last_clock and clock > last_clock[period] + 1e-9:
                anoms["order_inversion"] += 1
            last_clock[period] = clock
        t = _elapsed(period, clock, anoms)
        parts = [str(x) for x in (row.HOMEDESCRIPTION, row.NEUTRALDESCRIPTION,
                                  row.VISITORDESCRIPTION) if pd.notna(x) and str(x)]
        detail = " | ".join(parts)
        hs = aw = None
        if pd.notna(row.SCORE):
            m = SCORE_RE.match(str(row.SCORE))
            if m:  # V2 SCORE is "AWAY - HOME" (verified vs team gamelogs)
                aw, hs = int(m.group(1)), int(m.group(2))

        if et == V2_SUB:
            k1, team1, out_pid, name1 = _v2_slot(row, "1")
            k2, team2, in_pid, name2 = _v2_slot(row, "2")
            if k1 != "person" or k2 != "person":
                anoms["sub_malformed"] += 1
                continue
            team = team1 if team1 else team2
            emit((gid, period, t, team, out_pid, name1, "sub_out", "", False,
                  None, hs, aw, detail))
            emit((gid, period, t, team2 if team2 else team, in_pid, name2,
                  "sub_in", "", False, None, hs, aw, detail))
            continue

        if et == V2_FT:
            k, team, pid, name = _v2_slot(row, "1")
            made = MISS_RE.search(detail) is None
            subtype = V2_FT_ACTION_LABELS.get(action)
            if subtype is None:
                m = FT_PHRASE_RE.search(detail)
                subtype = m.group(1).strip() if m else f"Free Throw action {action}"
            tech = action == V2_FT_TECHNICAL_ACTION or "Technical" in subtype
            emit((gid, period, t, team, pid, name, "ft_made" if made else "ft_missed",
                  subtype, tech, 1 if made else 0, hs, aw, detail))
            continue

        if et in (1, 2):  # made / missed shot
            k, team, pid, name = _v2_slot(row, "1")
            made = et == 1
            pts = (3 if THREE_PT_RE.search(detail) else 2) if made else 0
            emit((gid, period, t, team, pid, name,
                  "shot_made" if made else "shot_missed", str(action), False,
                  pts, hs, aw, detail))
        elif et == 4:  # rebound (player or team)
            k, team, pid, name = _v2_slot(row, "1")
            emit((gid, period, t, team, pid, name, "rebound", str(action), False,
                  None, hs, aw, detail))
        elif et == 5:  # turnover (player or team)
            k, team, pid, name = _v2_slot(row, "1")
            emit((gid, period, t, team, pid, name, "turnover", str(action), False,
                  None, hs, aw, detail))
        elif et == 6:  # foul
            k, team, pid, name = _v2_slot(row, "1")
            tech = action in V2_TECH_FOUL_ACTIONS or bool(TECH_TOKEN_RE.search(detail))
            emit((gid, period, t, team, pid, name, "foul", str(action), tech,
                  None, hs, aw, detail))
        elif et == 7:  # violation
            k, team, pid, name = _v2_slot(row, "1")
            m = VIOLATION_KIND_RE.search(detail)
            sub = f"Violation:{m.group(1).strip()}" if m else "Violation"
            emit((gid, period, t, team, pid, name, "other", sub, False,
                  None, hs, aw, detail))
        elif et == 9:  # timeout — team id lives in PLAYER1_ID for team timeouts
            k, team, pid, name = _v2_slot(row, "1")
            m = TIMEOUT_KIND_RE.search(detail)
            sub = m.group(1).strip() if m else ""
            emit((gid, period, t, team, None, "", "timeout", sub, False,
                  None, hs, aw, detail))
        elif et == 10:  # jump ball — slots emitted as companions below
            k, team, pid, name = _v2_slot(row, "1")
            emit((gid, period, t, team, pid, name, "other", "Jump Ball", False,
                  None, hs, aw, detail))
        elif et == 11:  # ejection
            k, team, pid, name = _v2_slot(row, "1")
            m = EJECTION_KIND_RE.search(detail)
            sub = f"Ejection:{m.group(1).strip()}" if m else "Ejection"
            emit((gid, period, t, team, pid, name, "other", sub, True,
                  None, hs, aw, detail))
        elif et == 12:
            emit((gid, period, t, None, None, "", "period_start", "start", False,
                  None, hs, aw, detail))
        elif et == 13:
            emit((gid, period, t, None, None, "", "period_end", "end", False,
                  None, hs, aw, detail))
        elif et == 18:  # instant replay: person ids are junk in BOTH eras
            if row.PLAYER1_ID and int(row.PLAYER1_ID) != 0:
                anoms["instant_replay_person_nulled"] += 1
            emit((gid, period, t, None, None, "", "other", "Instant Replay", False,
                  None, hs, aw, detail))
        else:
            anoms[f"v2_unknown_type_{et}"] += 1
            k, team, pid, name = _v2_slot(row, "1")
            emit((gid, period, t, team, pid, name, "other", f"v2_type_{et}", False,
                  None, hs, aw, detail))

        # structured companion slots (assist / steal / block / foul drawn / jump ball)
        for slot, subtype in V2_COMPANION_SLOTS.get(et, ()):
            kind, s_team, s_pid, s_name = _v2_slot(row, slot)
            if kind == "none":
                continue
            tech = False
            if et == 6:  # foul-drawn companion inherits the technical flag
                tech = action in V2_TECH_FOUL_ACTIONS or bool(TECH_TOKEN_RE.search(detail))
            emit((gid, period, t, s_team, s_pid, s_name, "other", subtype, tech,
                  None, hs, aw, detail))


# ------------------------------- V3 parser ----------------------------------
def _v3_ids(pid, team):
    """Classify a V3 personId/teamId pair (team events smuggle the team id in
    personId with teamId=0 — rebounds, turnovers, timeouts)."""
    pid = int(pid) if pd.notna(pid) else 0
    team = int(team) if pd.notna(team) else 0
    if pid >= TEAM_ID_FLOOR:
        return "team", pid, None
    if pid > 0:
        return "person", (team if team > 0 else None), pid
    return "none", (team if team > 0 else None), None


def _parse_game_v3(gid, g, roster, out, anoms):
    idx = _RosterIndex()
    # pass 1: observe names from the pbp itself (NEVER from Instant Replay rows —
    # they carry junk personIds under real-looking playerNames)
    for row in g.itertuples(index=False):
        if str(row.actionType) == "Instant Replay":
            continue
        pid = int(row.personId)
        team = int(row.teamId)
        if 0 < pid < TEAM_ID_FLOOR and team > 0:
            idx.observe(team, pid, str(row.playerName) if pd.notna(row.playerName) else "")
            idx.observe(team, pid, str(row.playerNameI) if pd.notna(row.playerNameI) else "")
    if roster is not None:
        idx.add_roster(roster)
    teams = sorted({int(t) for t in g.teamId.unique() if int(t) > 0} |
                   {t for t in idx.pid_team.values()})

    def other_team(team):
        if team and len(teams) == 2:
            rest = [t for t in teams if t != team]
            return rest[0] if rest else None
        return None

    emit = out.append
    last_clock = {}
    for row in g.itertuples(index=False):
        at = str(row.actionType) if pd.notna(row.actionType) else ""
        sub_t = str(row.subType) if pd.notna(row.subType) else ""
        period = int(row.period)
        clock = parse_clock(row.clock, "v3")
        if not np.isnan(clock):
            if period in last_clock and clock > last_clock[period] + 1e-9:
                anoms["order_inversion"] += 1
            last_clock[period] = clock
        t = _elapsed(period, clock, anoms)
        detail = str(row.description) if pd.notna(row.description) else ""
        hs = aw = None
        sh, sa = str(row.scoreHome or ""), str(row.scoreAway or "")
        if sh.isdigit() and sa.isdigit():
            hs, aw = int(sh), int(sa)
        kind, team, pid, name = *_v3_ids(row.personId, row.teamId), ""
        if pid is not None:
            name = idx.name_of(pid) or (str(row.playerName) if pd.notna(row.playerName) else "")

        if at == "Substitution":
            if kind != "person":
                anoms["sub_malformed"] += 1
                continue
            emit((gid, period, t, team, pid, name, "sub_out", "", False,
                  None, hs, aw, detail))
            in_pid, in_name = None, ""
            m = SUB_DESC_RE.match(detail)
            if m:
                in_name = m.group("inp")
                in_pid = idx.resolve(in_name, team)
            if in_pid is None:
                anoms["v3_sub_in_unresolved"] += 1
            else:
                in_name = idx.name_of(in_pid) or in_name
            emit((gid, period, t, team, in_pid, in_name, "sub_in", "", False,
                  None, hs, aw, detail))
            continue

        if at == "Free Throw":
            made = MISS_RE.search(detail) is None
            tech = "Technical" in sub_t
            emit((gid, period, t, team, pid, name,
                  "ft_made" if made else "ft_missed", sub_t or "Free Throw",
                  tech, 1 if made else 0, hs, aw, detail))
        elif at in ("Made Shot", "Missed Shot"):
            made = at == "Made Shot"
            sv = int(row.shotValue) if pd.notna(row.shotValue) else 0
            pts3 = sv == 3 or (sv not in (2, 3) and bool(THREE_PT_RE.search(detail)))
            emit((gid, period, t, team, pid, name,
                  "shot_made" if made else "shot_missed", sub_t, False,
                  (3 if pts3 else 2) if made else 0, hs, aw, detail))
            if made:  # assist exists only as "(<name> N AST)" description text
                m = AST_DESC_RE.search(detail)
                if m:
                    a_pid = idx.resolve(m.group("name"), team) if team else None
                    if a_pid is None:
                        anoms["v3_assist_unresolved"] += 1
                    emit((gid, period, t, team, a_pid,
                          idx.name_of(a_pid) if a_pid else m.group("name"),
                          "other", "Assist", False, None, hs, aw, detail))
        elif at == "Rebound":
            emit((gid, period, t, team, pid, name, "rebound", sub_t, False,
                  None, hs, aw, detail))
        elif at == "Turnover":
            emit((gid, period, t, team, pid, name, "turnover", sub_t, False,
                  None, hs, aw, detail))
        elif at == "Foul":
            tech = "Technical" in sub_t
            if tech and pid is not None and roster is not None and not idx.known_player(pid):
                # V3 coach technicals put the coach's person id in personId;
                # only a roster can tell them from bench players — null them.
                anoms["v3_tech_nonroster_person_nulled"] += 1
                pid, name = None, name
            emit((gid, period, t, team, pid, name, "foul", sub_t, tech,
                  None, hs, aw, detail))
        elif at == "Violation":
            emit((gid, period, t, team, pid, name, "other",
                  f"Violation:{sub_t}" if sub_t else "Violation", False,
                  None, hs, aw, detail))
        elif at == "Timeout":
            emit((gid, period, t, team, None, "", "timeout", sub_t, False,
                  None, hs, aw, detail))
        elif at == "Jump Ball":
            emit((gid, period, t, team, pid, name, "other", "Jump Ball", False,
                  None, hs, aw, detail))
            m = JUMP_BALL_RE.search(detail)
            if m:
                vs_team = other_team(team)
                vs_pid = idx.resolve(m.group("b"), vs_team) if vs_team else None
                if vs_pid is None and m.group("b"):
                    vs_team2, vs_pid = idx.resolve_gamewide(m.group("b"))
                    vs_team = vs_team if vs_pid is None else vs_team2
                if vs_pid is None:
                    anoms["v3_jumpball_unresolved"] += 1
                emit((gid, period, t, vs_team, vs_pid,
                      idx.name_of(vs_pid) if vs_pid else (m.group("b") or ""),
                      "other", "Jump Ball", False, None, hs, aw, detail))
                if m.group("tip"):
                    tip_team, tip_pid = idx.resolve_gamewide(m.group("tip"))
                    if tip_pid is None:
                        anoms["v3_jumpball_unresolved"] += 1
                    emit((gid, period, t, tip_team, tip_pid,
                          idx.name_of(tip_pid) if tip_pid else m.group("tip"),
                          "other", "Jump Ball Tip", False, None, hs, aw, detail))
        elif at == "period":
            emit((gid, period, t, None, None, "",
                  "period_start" if sub_t == "start" else "period_end",
                  sub_t, False, None, hs, aw, detail))
        elif at == "Ejection":
            emit((gid, period, t, team, pid, name, "other",
                  f"Ejection:{sub_t}" if sub_t else "Ejection", True,
                  None, hs, aw, detail))
        elif at == "Instant Replay":
            if pid is not None:
                anoms["instant_replay_person_nulled"] += 1
            emit((gid, period, t, None, None, "", "other", "Instant Replay", False,
                  None, hs, aw, detail))
        elif at == "":
            # steal/block companion rows arrive with BLANK actionType
            if "STEAL" in detail:
                emit((gid, period, t, team, pid, name, "other", "Steal", False,
                      None, hs, aw, detail))
            elif "BLOCK" in detail:
                emit((gid, period, t, team, pid, name, "other", "Block", False,
                      None, hs, aw, detail))
            else:
                anoms["v3_blank_action_unclassified"] += 1
                emit((gid, period, t, team, pid, name, "other", "", False,
                      None, hs, aw, detail))
        else:
            anoms[f"v3_unknown_action_{at}"] += 1
            emit((gid, period, t, team, pid, name, "other", at, False,
                  None, hs, aw, detail))


# ----------------------------------------------------------------------------
# normalize_player_box — column-map tables, not if-soup
# ----------------------------------------------------------------------------
# V3 camelCase identity columns -> canonical
V3_BOX_IDENTITY_MAP = {
    "gameId": "game_id", "teamId": "team_id", "personId": "player_id",
    "firstName": "first_name", "familyName": "family_name", "nameI": "name_i",
    "position": "position", "comment": "dnp_reason",
    "teamCity": "team_city", "teamName": "team_name",
    "teamTricode": "team_tricode", "teamSlug": "team_slug",
    "playerSlug": "player_slug", "jerseyNum": "jersey_num",
}

# V3 camelCase stats -> canonical snake_case. Where V2 already named the
# concept, the V3 spelling maps onto the SAME canonical name (one name per
# concept: blocks->blk, foulsPersonal->pf, turnovers->tov, ...).
V3_BOX_STAT_MAP = {
    # misc boxscore (verified in repo)
    "pointsOffTurnovers": "points_off_turnovers",
    "pointsSecondChance": "points_second_chance",
    "pointsFastBreak": "points_fast_break",
    "pointsPaint": "points_paint",
    "oppPointsOffTurnovers": "opp_points_off_turnovers",
    "oppPointsSecondChance": "opp_points_second_chance",
    "oppPointsFastBreak": "opp_points_fast_break",
    "oppPointsPaint": "opp_points_paint",
    "blocks": "blk", "blocksAgainst": "blocks_against",
    "foulsPersonal": "pf", "foulsDrawn": "fouls_drawn",
    # traditional V3 spellings (standard nba_api naming; future-proofing —
    # no traditional V3 files exist in the repo yet)
    "fieldGoalsMade": "fgm", "fieldGoalsAttempted": "fga",
    "fieldGoalsPercentage": "fg_pct",
    "threePointersMade": "fg3m", "threePointersAttempted": "fg3a",
    "threePointersPercentage": "fg3_pct",
    "freeThrowsMade": "ftm", "freeThrowsAttempted": "fta",
    "freeThrowsPercentage": "ft_pct",
    "reboundsOffensive": "oreb", "reboundsDefensive": "dreb",
    "reboundsTotal": "reb", "assists": "ast", "steals": "stl",
    "turnovers": "tov", "points": "pts", "plusMinusPoints": "plus_minus",
    "PIE": "pie",
}

# Uppercase identity columns (old per-game boxes AND LeagueGameLog refresh)
UPPER_BOX_IDENTITY_MAP = {
    "GAME_ID": "game_id", "TEAM_ID": "team_id", "PLAYER_ID": "player_id",
    "PLAYER_NAME": "player_name", "NICKNAME": "nickname",
    "TEAM_ABBREVIATION": "team_abbreviation", "TEAM_CITY": "team_city",
    "TEAM_NAME": "team_name", "START_POSITION": "position",
    "COMMENT": "dnp_reason", "SEASON": "season", "SEASON_ID": "season_id",
    "GAME_DATE": "game_date", "MATCHUP": "matchup", "WL": "wl",
    "season_type": "season_type",
}

# Uppercase stats -> canonical (note the TO/TOV split across gamelog eras)
UPPER_BOX_STAT_MAP = {
    "FGM": "fgm", "FGA": "fga", "FG_PCT": "fg_pct",
    "FG3M": "fg3m", "FG3A": "fg3a", "FG3_PCT": "fg3_pct",
    "FTM": "ftm", "FTA": "fta", "FT_PCT": "ft_pct",
    "OREB": "oreb", "DREB": "dreb", "REB": "reb",
    "AST": "ast", "STL": "stl", "BLK": "blk",
    "TO": "tov", "TOV": "tov", "PF": "pf", "PTS": "pts",
    "PLUS_MINUS": "plus_minus", "FANTASY_PTS": "fantasy_pts",
    "VIDEO_AVAILABLE": "video_available",
}

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

BOX_IDENTITY_COLUMNS = [
    "game_id", "team_id", "player_id", "player_name", "first_name",
    "family_name", "name_i", "position", "starter_flag", "dnp_reason",
    "minutes", "minutes_raw", "era",
]


def _snake(col: str) -> str:
    """Deterministic fallback rename for unmapped source columns."""
    return _CAMEL_RE.sub("_", col).lower()


def _zfill_game_id(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.strip()
    return out.where(~out.str.fullmatch(r"\d{1,9}"), out.str.zfill(10))


def normalize_player_box(df: pd.DataFrame) -> pd.DataFrame:
    """Canonical per-player boxscore rows from any supported box frame:
    V3 misc/advanced (camelCase), V2-style uppercase per-game boxes / old
    season gamelogs, and LeagueGameLog refresh gamelogs.

    Guaranteed identity block: BOX_IDENTITY_COLUMNS (same dtypes every era;
    starter_flag/dnp_reason are NA where the source structurally lacks them —
    LeagueGameLog frames). Stats follow under canonical snake_case names via
    the column-map tables above. attrs['era'] and
    attrs['minutes_parse_failures'] are set on the result.
    """
    era = detect_era(df)
    if era == "v2":
        raise ValueError("normalize_player_box got a V2 pbp frame; use normalize_pbp")
    if era == "v3" and "actionType" in df.columns:
        raise ValueError("normalize_player_box got a V3 pbp frame; use normalize_pbp")

    if era == "v3":
        id_map, stat_map = V3_BOX_IDENTITY_MAP, V3_BOX_STAT_MAP
    else:
        id_map, stat_map = UPPER_BOX_IDENTITY_MAP, UPPER_BOX_STAT_MAP
    if "PLAYER_ID" not in df.columns and era != "v3":
        raise ValueError(
            f"normalize_player_box: frame detected as {era!r} but has no PLAYER_ID "
            "column (team-level gamelog?) — this normalizer is for player rows")

    rename = {}
    for c in df.columns:
        if c == "MIN" or c == "minutes":
            rename[c] = "minutes_raw"
        elif c in id_map:
            rename[c] = id_map[c]
        elif c in stat_map:
            rename[c] = stat_map[c]
        else:
            rename[c] = _snake(c)
    out = df.rename(columns=rename).copy()

    # identity block ---------------------------------------------------------
    out["game_id"] = _zfill_game_id(out["game_id"])
    out["team_id"] = out["team_id"].astype("Int64")
    out["player_id"] = out["player_id"].astype("Int64")
    out["era"] = era

    if era == "v3":
        for c in ("first_name", "family_name", "name_i"):
            if c not in out.columns:
                out[c] = ""
        first = out["first_name"].fillna("").astype(str)
        family = out["family_name"].fillna("").astype(str)
        out["player_name"] = (first + " " + family).str.strip()
    else:
        pn = out["player_name"].fillna("").astype(str)
        out["first_name"] = pn.str.split().str[0].fillna("")
        out["family_name"] = pn.str.split().str[-1].fillna("")
        out["name_i"] = pd.NA

    if "position" in out.columns:
        pos = out["position"].fillna("").astype(str).str.strip()
        out["position"] = pos
        out["starter_flag"] = pos.ne("").astype("Int64")
    else:  # LeagueGameLog frames: starters are structurally unknowable
        out["position"] = pd.NA
        out["starter_flag"] = pd.Series(pd.NA, index=out.index, dtype="Int64")

    if "dnp_reason" in out.columns:
        cm = out["dnp_reason"].fillna("").astype(str).str.strip()
        out["dnp_reason"] = cm.where(cm.ne(""), pd.NA)
    else:
        out["dnp_reason"] = pd.NA

    if "minutes_raw" in out.columns:
        out["minutes"] = out["minutes_raw"].map(minutes_to_float).astype("float64")
        raw = out["minutes_raw"]
        blank = raw.isna() | raw.astype(str).str.strip().eq("")
        n_failed = int(((~blank) & out["minutes"].isna()).sum())
    else:
        out["minutes_raw"] = pd.NA
        out["minutes"] = np.nan
        n_failed = 0

    rest = [c for c in out.columns if c not in BOX_IDENTITY_COLUMNS]
    out = out[BOX_IDENTITY_COLUMNS + rest]
    out.attrs["era"] = era
    out.attrs["minutes_parse_failures"] = n_failed
    return out
