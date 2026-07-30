"""
build_possessions.py
====================
Possession attribution from the canonical pbp event stream (ROADMAP Phase 2b
prerequisite: "RAPM waits on possession reconciliation"). LOCAL DATA ONLY.

Inputs
------
- data/playbyplay/pbp_*.parquet + data/refresh_2026/pbp/pbp_*.parquet
  (era detected per file by wnba_schema.normalize_pbp; duplicate game ids
  across dirs resolved first-dir-wins, matching derive_lineups.py)
- data/derived/stints.parquet      on-court intervals (derive_lineups.py)
- data/masters/master_team.parquet final scores + is_home (reconciliation truth)
- data/refresh_2026/advanced|misc  optional V3 roster (name resolution only)

Output: data/possessions/possessions.parquet — one row per possession:
  game_id, season, season_type, era, possession_idx, period,
  start_sec, end_sec, duration_sec       absolute game seconds (period-local
                                         boundaries per wnba_schema conventions)
  offense_team_id, defense_team_id, points_scored, end_reason,
  is_home_offense, home_pts_before, away_pts_before   (cumulative, model-internal)
  off_p1..off_p5, def_p1..def_p5         the five on-court player ids per side
                                         (sorted ascending; NA when underfull)
  n_off_oncourt, n_def_oncourt           how many the lineup join actually found

Possession rules (standard, applied via ball-run segmentation)
--------------------------------------------------------------
The stream of BALL-INDICATOR events (shot_made / shot_missed / ft_made /
ft_missed [non-technical] / turnover / rebound) is segmented into maximal runs
of the same team; each run is one possession. This makes the standard rules
fall out without lookahead:
  * made FG ends the possession — unless the same team's and-one FT follows
    (same run -> one possession, end_reason from the FT);
  * final FT of a trip ends it ('made_ft_final'); flagrant / clear-path FTs
    where the shooting team retains the ball simply continue the run;
  * offensive rebounds (player or team) continue the run; a rebound by the
    other team closes it ('defensive_rebound');
  * turnover closes it at the turnover time;
  * period end closes any open possession ('period_end'); each period's first
    indicator defines that period's opening offense (no possession-arrow model);
  * dead-ball team rebounds after missed NON-final FTs are credited to the
    shooting team in both eras (verified) -> they continue the run, harmless;
  * technical FTs never flip possession and are excluded from runs. Made
    technical FT points are folded into the current possession when the
    shooter's team is on offense; otherwise they land in a zero-duration
    synthetic row with end_reason='technical_ft' (so per-team score
    reconciliation stays exact). Rebound rows that trail a missed technical FT
    (dead ball) are skipped.
Rare flips with no classifiable ending event (held-ball jump balls, away-from-
play FT quirks, missing rebound rows) are kept but labeled 'inferred_flip' /
'miss_flip_no_rebound' and counted per game.

Source-defect guard: six V2 games (2021/2023) double-log a made shot — same
clock, identical description, and the source's own running-score column does
not advance on the copy. Such rows are dropped only under that two-part proof
(_drop_duplicate_scoring_rows) and counted as 'dup_scoring_row_dropped'.

Lineup rule (documented, uniform): a possession is NOT split at substitutions.
Each side gets the five players with the LARGEST time overlap with
[start_sec, end_sec) from stints.parquet (majority-time rule; ties broken by
player id). Zero-duration possessions use on-court membership at the instant
(half-open intervals [s, e), so a sub at the boundary credits the incoming
player). Underfull sides are back-filled by midpoint membership, then counted
in n_off_oncourt / n_def_oncourt if still short — never guessed.

Reconciliation (the gate): per game, possession points summed per offense team
must equal master_team pts for both teams. The full run prints the exact-match
rate, lists every non-exact game with residuals + dominant anomaly, reports the
possessions-per-team-per-40 distribution, and cross-checks a 100-game sample
against V3 advanced boxscore possessions (sum of player possessions / 5).
Artifacts: data/possessions/reconciliation.csv (per game) and
data/possessions/possessions.parquet.

daily_certify.py hook: reconcile_sample(n) re-derives the n most recent games
from raw pbp and returns per-game exactness — wired into the standing
'lineup possession reconciliation' check.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PBP_DIRS = [os.path.join(DATA, "playbyplay"),
            os.path.join(DATA, "refresh_2026", "pbp")]
ADV_DIR = os.path.join(DATA, "refresh_2026", "advanced")
MISC_DIR = os.path.join(DATA, "refresh_2026", "misc")
STINTS_PATH = os.path.join(DATA, "derived", "stints.parquet")
MASTER_TEAM_PATH = os.path.join(DATA, "masters", "master_team.parquet")
OUT_DIR = os.path.join(DATA, "possessions")
OUT_PARQUET = os.path.join(OUT_DIR, "possessions.parquet")
OUT_RECON = os.path.join(OUT_DIR, "reconciliation.csv")

sys.path.insert(0, ROOT)
from wnba_schema import (  # noqa: E402
    normalize_pbp, period_length_sec, period_start_sec)

INDICATOR_TYPES = frozenset(
    {"shot_made", "shot_missed", "ft_made", "ft_missed", "turnover", "rebound"})
FT_TRIP_RE = re.compile(r"(\d) of (\d)")

# priority order when naming a game's dominant failure mode
FAILURE_PRIORITY = [
    "tech_ft_no_team", "indicator_no_team", "points_na_on_scoring_row",
    "miss_flip_no_rebound", "made_ft_nonfinal_flip", "inferred_flip",
    "rebound_after_tech_ft_skipped", "clock_ffilled",
]


def season_of_game_id(gid: str) -> str:
    gid = str(gid)
    return "20" + gid[3:5] if len(gid) == 10 and gid[0] == "1" else "unknown"


def season_type_of_game_id(gid: str) -> str:
    return {"02": "Regular Season", "04": "Playoffs"}.get(str(gid)[1:3], "other")


def _ft_is_final(subtype: str) -> bool:
    m = FT_TRIP_RE.search(subtype or "")
    return bool(m and m.group(1) == m.group(2))


# ---------------------------------------------------------------------------
# possession state machine (one game)
# ---------------------------------------------------------------------------
def build_game_possessions(ev: pd.DataFrame, home_id: int, away_id: int,
                           anoms: Counter) -> list[dict]:
    """ev: canonical normalize_pbp rows for ONE game, event_idx order.
    Returns possession dicts (no lineups yet)."""
    teams = (home_id, away_id)

    # timeline: forward-fill unparseable clocks within the game
    t = ev["game_seconds_elapsed"].to_numpy(dtype=float, copy=True)
    bad = np.isnan(t)
    if bad.any():
        anoms["clock_ffilled"] += int(bad.sum())
        s = pd.Series(t).ffill()
        t = s.to_numpy()
    per = ev["period"].to_numpy(dtype=int)
    etype = ev["event_type"].to_numpy(dtype=object)
    esub = ev["event_subtype"].to_numpy(dtype=object)
    tech = ev["technical_flag"].to_numpy(dtype=bool)
    team = ev["team_id"].to_numpy(dtype=object)
    pts = ev["points"].to_numpy(dtype=object)

    out: list[dict] = []

    def other(tm):
        return away_id if tm == home_id else home_id

    def emit(period, t0, t1, off, points, reason):
        if off not in teams:
            anoms["offense_team_unknown"] += 1
            return
        out.append({
            "period": int(period),
            "start_sec": float(t0),
            "end_sec": float(max(t1, t0)),
            "offense_team_id": int(off),
            "defense_team_id": int(other(off)),
            "points_scored": int(points),
            "end_reason": reason,
        })

    for p in sorted(set(per.tolist())):
        mask = per == p
        idxs = np.nonzero(mask)[0]
        p_start = period_start_sec(p)
        p_end = p_start + period_length_sec(p)
        cur_off = None
        cur_start = p_start
        cur_points = 0
        last_ind = None  # (etype, esub, t, team)

        for i in idxs:
            et = etype[i]
            if et not in INDICATOR_TYPES:
                continue
            ti = t[i] if not np.isnan(t[i]) else (
                last_ind[2] if last_ind else p_start)
            ti = min(max(ti, p_start), p_end)

            # technical FTs: never flip possession, points still must land
            if et in ("ft_made", "ft_missed") and tech[i]:
                if et == "ft_made":
                    tm = team[i]
                    if pd.isna(tm) or int(tm) not in teams:
                        anoms["tech_ft_no_team"] += 1
                    elif cur_off is not None and int(tm) == cur_off:
                        cur_points += 1
                        anoms["tech_ft_folded"] += 1
                    else:
                        emit(p, ti, ti, int(tm), 1, "technical_ft")
                        anoms["tech_ft_synthetic"] += 1
                continue

            # (rebounds trailing a missed technical FT were dropped upstream
            # by _mask_rebounds_after_missed_tech_ft)
            tm = team[i]
            if pd.isna(tm) or int(tm) not in teams:
                anoms["indicator_no_team"] += 1
                continue
            tm = int(tm)
            pt = pts[i]
            if et in ("shot_made", "ft_made") and pd.isna(pt):
                anoms["points_na_on_scoring_row"] += 1
            pt = int(pt) if pd.notna(pt) else 0

            if cur_off is None:                    # period's opening offense
                if et == "rebound":
                    anoms["period_opens_with_rebound"] += 1
                cur_off = tm
                cur_start = p_start
                cur_points = pt
                last_ind = (et, esub[i], ti, tm)
                continue

            if tm == cur_off:                      # run continues
                cur_points += pt
                last_ind = (et, esub[i], ti, tm)
                continue

            # ---- flip: close the current possession -------------------------
            let, lsub, lt, _ = last_ind
            if et == "rebound":
                reason, t_close = "defensive_rebound", ti
            elif let == "turnover":
                reason, t_close = "turnover", lt
            elif let == "ft_made":
                if _ft_is_final(lsub):
                    reason = "made_ft_final"
                else:
                    reason = "made_ft_nonfinal_flip"
                    anoms["made_ft_nonfinal_flip"] += 1
                t_close = lt
            elif let == "shot_made":
                reason, t_close = "made_shot", lt
            elif let in ("shot_missed", "ft_missed"):
                reason, t_close = "miss_flip_no_rebound", ti
                anoms["miss_flip_no_rebound"] += 1
            else:
                reason, t_close = "inferred_flip", ti
                anoms["inferred_flip"] += 1
            t_close = min(max(t_close, cur_start), p_end)
            emit(p, cur_start, t_close, cur_off, cur_points, reason)
            cur_off = tm
            cur_start = t_close
            cur_points = pt
            last_ind = (et, esub[i], ti, tm)

        if cur_off is not None:                    # close at the period horn
            emit(p, cur_start, p_end, cur_off, cur_points, "period_end")
    return out


def _drop_duplicate_scoring_rows(ev: pd.DataFrame, anoms: Counter) -> pd.DataFrame:
    """Drop provably duplicated scoring rows (upstream feed defect, seen in 6
    V2 games 2021/2023: the same made shot logged twice at the same clock with
    identical description). A row is dropped ONLY when BOTH hold:
      (a) an identical earlier scoring row exists in the same game
          (period, clock, team, person, event_type, points, detail), and
      (b) the forward-filled running score total does NOT advance on this row
          (the source's own score column proves the points were not counted).
    Never touches rows the running score confirms. Counted, never silent."""
    pts = ev["points"].fillna(0).astype("int64")
    scoring = (pts > 0).to_numpy()
    if not scoring.any():
        return ev
    tot = (ev["home_score"].astype("Float64").ffill() +
           ev["away_score"].astype("Float64").ffill())
    tot_prev = tot.shift(1)
    keys = list(zip(ev["period"], ev["game_seconds_elapsed"], ev["team_id"],
                    ev["person_id"], ev["event_type"], pts, ev["detail"]))
    seen: set = set()
    drop = []
    for i in range(len(ev)):
        if not scoring[i]:
            continue
        k = keys[i]
        if (k in seen and pd.notna(tot.iat[i]) and pd.notna(tot_prev.iat[i])
                and float(tot.iat[i]) == float(tot_prev.iat[i])):
            drop.append(i)
            anoms["dup_scoring_row_dropped"] += 1
        else:
            seen.add(k)
    if drop:
        ev = ev.drop(ev.index[drop]).reset_index(drop=True)
    return ev


def _mask_rebounds_after_missed_tech_ft(ev: pd.DataFrame, anoms: Counter) -> pd.DataFrame:
    """Drop rebound rows whose nearest preceding indicator-ish row is a missed
    technical FT (dead ball; both eras occasionally log a team rebound)."""
    drop = []
    prev_missed_tech = False
    for i, (et, tech) in enumerate(zip(ev["event_type"], ev["technical_flag"])):
        if et in ("ft_made", "ft_missed"):
            prev_missed_tech = bool(tech) and et == "ft_missed"
        elif et == "rebound":
            if prev_missed_tech:
                drop.append(i)
                anoms["rebound_after_tech_ft_skipped"] += 1
            prev_missed_tech = False
        elif et in ("shot_made", "shot_missed", "turnover"):
            prev_missed_tech = False
    if drop:
        ev = ev.drop(ev.index[drop]).reset_index(drop=True)
    return ev


# ---------------------------------------------------------------------------
# lineup join (majority-time rule)
# ---------------------------------------------------------------------------
def _team_intervals(stints_g: pd.DataFrame) -> dict:
    """team_id -> (pid array, start array, end array) for one game."""
    res = {}
    for tid, grp in stints_g.groupby("TEAM_ID"):
        res[int(tid)] = (grp["PLAYER_ID"].to_numpy(dtype=np.int64),
                         grp["stint_start_sec"].to_numpy(dtype=float),
                         grp["stint_end_sec"].to_numpy(dtype=float))
    return res


def _lineup_for(intervals, tid, t0, t1, anoms):
    """Five player ids on court for team `tid` over [t0, t1) by majority time."""
    if tid not in intervals:
        anoms["lineup_team_missing"] += 1
        return [pd.NA] * 5, 0
    pids, s, e = intervals[tid]
    if t1 > t0:
        ov = np.minimum(e, t1) - np.maximum(s, t0)
        ov[ov < 0] = 0.0
    else:  # zero-duration: membership at the instant, half-open [s, e)
        ov = ((s <= t0) & (t0 < e)).astype(float)
    per_pid: dict[int, float] = {}
    for pid, o in zip(pids, ov):
        if o > 0:
            per_pid[int(pid)] = per_pid.get(int(pid), 0.0) + float(o)
    chosen = sorted(per_pid.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    ids = [pid for pid, _ in chosen]
    if len(ids) < 5:                      # back-fill by midpoint membership
        mid = 0.5 * (t0 + t1)
        member = (s <= mid) & (mid < e)
        for pid in pids[member]:
            if int(pid) not in ids:
                ids.append(int(pid))
                if len(ids) == 5:
                    break
    n = len(ids)
    if n < 5:
        anoms["lineup_underfull"] += 1
    ids = sorted(ids)[:5] + [pd.NA] * (5 - min(n, 5))
    return ids, n


def attach_lineups(poss: list[dict], stints_g: pd.DataFrame, anoms: Counter):
    intervals = _team_intervals(stints_g) if stints_g is not None else {}
    for row in poss:
        for side, tid_key in (("off", "offense_team_id"), ("def", "defense_team_id")):
            ids, n = _lineup_for(intervals, row[tid_key],
                                 row["start_sec"], row["end_sec"], anoms)
            for k in range(5):
                row[f"{side}_p{k + 1}"] = ids[k]
            row[f"n_{side}_oncourt"] = n
    return poss


# ---------------------------------------------------------------------------
# per-game driver
# ---------------------------------------------------------------------------
def discover_games() -> "dict[str, str]":
    """game_id -> pbp path; first dir wins on duplicates (as derive_lineups)."""
    games: dict[str, str] = {}
    for d in PBP_DIRS:
        for f in sorted(glob.glob(os.path.join(d, "pbp_*.parquet"))):
            gid = os.path.basename(f).split("_")[1].split(".")[0]
            games.setdefault(gid, f)
    return games


def load_master_lookup() -> "dict[str, dict]":
    mt = pd.read_parquet(MASTER_TEAM_PATH,
                         columns=["game_id", "team_id", "pts", "is_home"])
    mt["game_id"] = mt["game_id"].astype(str).str.zfill(10)
    look: dict[str, dict] = {}
    for gid, grp in mt.groupby("game_id"):
        h = grp[grp["is_home"] == 1]
        a = grp[grp["is_home"] == 0]
        if len(h) == 1 and len(a) == 1:
            look[gid] = {"home_id": int(h["team_id"].iloc[0]),
                         "away_id": int(a["team_id"].iloc[0]),
                         "home_pts": int(h["pts"].iloc[0]),
                         "away_pts": int(a["pts"].iloc[0])}
    return look


def load_roster_for(gid: str) -> "pd.DataFrame | None":
    for d in (ADV_DIR, MISC_DIR):
        f = os.path.join(d, f"{'advanced' if d == ADV_DIR else 'misc'}_{gid}.parquet")
        if os.path.exists(f):
            try:
                return pd.read_parquet(f, columns=[
                    "gameId", "teamId", "personId", "firstName", "familyName", "nameI"])
            except Exception:
                return None
    return None


def process_game(gid: str, path: str, master: dict,
                 stints_g: "pd.DataFrame | None",
                 want_roster: bool = True) -> "tuple[pd.DataFrame | None, dict]":
    """Returns (possession frame or None, per-game report)."""
    report = {"game_id": gid, "season": season_of_game_id(gid),
              "season_type": season_type_of_game_id(gid)}
    anoms: Counter = Counter()
    try:
        raw = pd.read_parquet(path)
    except Exception as ex:
        report.update(status=f"read_error:{type(ex).__name__}")
        return None, report
    if raw.empty:
        report.update(status="empty_pbp")
        return None, report
    is_v3 = "actionType" in raw.columns
    roster = load_roster_for(gid) if (is_v3 and want_roster) else None
    try:
        ev = normalize_pbp(raw, roster=roster)
    except Exception as ex:
        report.update(status=f"normalize_error:{type(ex).__name__}")
        return None, report
    norm_anoms = dict(ev.attrs.get("anomalies", {}))
    era = ev["era"].iloc[0] if len(ev) else "?"

    ev = _drop_duplicate_scoring_rows(ev, anoms)
    ev = _mask_rebounds_after_missed_tech_ft(ev, anoms)
    poss = build_game_possessions(ev, master["home_id"], master["away_id"], anoms)
    if not poss:
        report.update(status="no_possessions")
        return None, report
    if stints_g is not None and not stints_g.empty:
        attach_lineups(poss, stints_g, anoms)
    else:
        anoms["no_stints_for_game"] += 1
        attach_lineups(poss, pd.DataFrame(columns=["TEAM_ID", "PLAYER_ID",
                       "stint_start_sec", "stint_end_sec"]), anoms)

    df = pd.DataFrame(poss)
    df.insert(0, "game_id", gid)
    df.insert(1, "season", report["season"])
    df.insert(2, "season_type", report["season_type"])
    df.insert(3, "era", era)
    df["possession_idx"] = np.arange(len(df))
    df["is_home_offense"] = (df["offense_team_id"] == master["home_id"]).astype("int64")
    # cumulative model-internal score BEFORE each possession
    hp = np.where(df["is_home_offense"] == 1, df["points_scored"], 0).cumsum()
    ap = np.where(df["is_home_offense"] == 0, df["points_scored"], 0).cumsum()
    df["home_pts_before"] = np.concatenate([[0], hp[:-1]]).astype("int64")
    df["away_pts_before"] = np.concatenate([[0], ap[:-1]]).astype("int64")
    df["duration_sec"] = (df["end_sec"] - df["start_sec"]).round(2)

    model_home = int(hp[-1])
    model_away = int(ap[-1])
    exact = (model_home == master["home_pts"]) and (model_away == master["away_pts"])
    dominant = ""
    if not exact:
        for k in FAILURE_PRIORITY:
            if anoms.get(k):
                dominant = f"{k}({anoms[k]})"
                break
        if not dominant and anoms:
            k = max(anoms, key=anoms.get)
            dominant = f"{k}({anoms[k]})"
    n_real = int((df["end_reason"] != "technical_ft").sum())
    report.update(
        status="ok", era=era,
        n_possessions=len(df), n_real_possessions=n_real,
        model_home_pts=model_home, model_away_pts=model_away,
        master_home_pts=master["home_pts"], master_away_pts=master["away_pts"],
        resid_home=model_home - master["home_pts"],
        resid_away=model_away - master["away_pts"],
        exact=bool(exact), dominant_failure=dominant,
        game_seconds=float(df["end_sec"].max()),
        anomalies={k: int(v) for k, v in sorted(anoms.items())},
        norm_anomalies={k: int(v) for k, v in sorted(norm_anoms.items())},
    )
    col_order = [
        "game_id", "season", "season_type", "era", "possession_idx", "period",
        "start_sec", "end_sec", "duration_sec", "offense_team_id",
        "defense_team_id", "points_scored", "end_reason", "is_home_offense",
        "home_pts_before", "away_pts_before",
        "off_p1", "off_p2", "off_p3", "off_p4", "off_p5",
        "def_p1", "def_p2", "def_p3", "def_p4", "def_p5",
        "n_off_oncourt", "n_def_oncourt",
    ]
    for c in col_order:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[col_order]
    for c in [f"{s}_p{k}" for s in ("off", "def") for k in range(1, 6)]:
        df[c] = df[c].astype("Int64")
    return df, report


# ---------------------------------------------------------------------------
# daily_certify hook — re-derive the n most recent games and reconcile
# ---------------------------------------------------------------------------
def reconcile_sample(n: int = 8) -> "list[dict]":
    """Fast standing check: re-derive the n most recent games from raw pbp and
    compare possession point sums to master_team. Returns per-game dicts with
    at least game_id/status/exact/resid_home/resid_away."""
    games = discover_games()
    master = load_master_lookup()
    gids = sorted((g for g in games if g in master),
                  key=lambda g: (season_of_game_id(g), g))[-n:]
    stints = pd.read_parquet(STINTS_PATH, columns=[
        "GAME_ID", "TEAM_ID", "PLAYER_ID", "stint_start_sec", "stint_end_sec"])
    stints_by_game = {g: d for g, d in stints.groupby("GAME_ID") if g in set(gids)}
    out = []
    for gid in gids:
        _, rep = process_game(gid, games[gid], master[gid],
                              stints_by_game.get(gid), want_roster=True)
        out.append(rep)
    return out


# ---------------------------------------------------------------------------
# pace / advanced cross-check helpers
# ---------------------------------------------------------------------------
def advanced_team_possessions(gid: str) -> "dict[int, float] | None":
    f = os.path.join(ADV_DIR, f"advanced_{gid}.parquet")
    if not os.path.exists(f):
        return None
    try:
        d = pd.read_parquet(f, columns=["teamId", "possessions"])
    except Exception:
        return None
    agg = d.groupby("teamId")["possessions"].sum() / 5.0
    return {int(t): float(v) for t, v in agg.items()}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="build possessions.parquet")
    ap.add_argument("--limit", type=int, default=0,
                    help="process only the first N games (smoke runs)")
    ap.add_argument("--no-roster", action="store_true",
                    help="skip V3 roster loading (faster, more unresolved names)")
    args = ap.parse_args(argv)

    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    games = discover_games()
    master = load_master_lookup()
    print(f"{len(games)} pbp games discovered; master coverage "
          f"{sum(g in master for g in games)}")
    stints = pd.read_parquet(STINTS_PATH, columns=[
        "GAME_ID", "TEAM_ID", "PLAYER_ID", "stint_start_sec", "stint_end_sec"])
    stints_by_game = dict(tuple(stints.groupby("GAME_ID")))

    gids = sorted(games)
    if args.limit:
        gids = gids[:args.limit]

    frames, reports, skipped = [], [], []
    glob_anoms: Counter = Counter()
    for i, gid in enumerate(gids):
        if i and i % 200 == 0:
            print(f"  ... {i}/{len(gids)} games, {time.time() - t0:.0f}s")
        if gid not in master:
            skipped.append((gid, "no_master_row"))
            continue
        df, rep = process_game(gid, games[gid], master[gid],
                               stints_by_game.get(gid),
                               want_roster=not args.no_roster)
        if df is None:
            skipped.append((gid, rep.get("status", "?")))
            continue
        frames.append(df)
        reports.append(rep)
        glob_anoms.update(rep["anomalies"])
    print(f"  ... {len(gids)}/{len(gids)} games, {time.time() - t0:.0f}s")

    poss = pd.concat(frames, ignore_index=True)
    poss.to_parquet(OUT_PARQUET, index=False)
    rep_df = pd.DataFrame([{k: v for k, v in r.items()
                            if k not in ("anomalies", "norm_anomalies")} |
                           {"anomalies": str(r["anomalies"]),}
                           for r in reports])
    rep_df.to_csv(OUT_RECON, index=False, encoding="utf-8")

    # ------------------------------------------------------------ report
    print("\n================ POSSESSION RECONCILIATION ================")
    n_ok = int(rep_df["exact"].sum())
    n_all = len(rep_df)
    print(f"games processed: {n_all}  |  skipped: {len(skipped)} {skipped[:6]}")
    print(f"EXACT per-team score match: {n_ok}/{n_all} = {n_ok / n_all * 100:.2f}%"
          f"   (gate target >= 99.5%)")
    bad = rep_df[~rep_df["exact"]]
    if len(bad):
        print(f"\nnon-exact games ({len(bad)}):")
        cols = ["game_id", "season", "era", "resid_home", "resid_away",
                "dominant_failure", "anomalies"]
        with pd.option_context("display.max_colwidth", 90, "display.width", 200):
            print(bad[cols].to_string(index=False))
    by_season = rep_df.groupby("season")["exact"].agg(["mean", "size"])
    print("\nexact rate by season:")
    for s, r in by_season.iterrows():
        print(f"  {s}: {r['mean'] * 100:6.2f}%  ({int(r['size'])} games)")
    print(f"\nglobal anomaly counters: {dict(sorted(glob_anoms.items()))}")

    # possessions per team per 40 min
    real = poss[poss["end_reason"] != "technical_ft"]
    per_team = (real.groupby(["game_id", "offense_team_id"]).size()
                .rename("n_poss").reset_index())
    gsec = poss.groupby("game_id")["end_sec"].max().rename("game_sec")
    per_team = per_team.merge(gsec, on="game_id")
    per_team["poss_40"] = per_team["n_poss"] * 2400.0 / per_team["game_sec"]
    d = per_team["poss_40"]
    print("\npossessions per team per 40 min (technical_ft rows excluded):")
    print(f"  mean {d.mean():.2f}  sd {d.std():.2f}  "
          f"p5 {d.quantile(.05):.1f}  p50 {d.quantile(.50):.1f}  "
          f"p95 {d.quantile(.95):.1f}  min {d.min():.1f}  max {d.max():.1f}")
    in_band = ((d >= 70) & (d <= 90)).mean() * 100
    print(f"  within [70, 90]: {in_band:.1f}%   "
          f"(known WNBA range ~75-85; alarm only outside 70-90)")

    # advanced cross-check on a 100-game sample
    rng = np.random.default_rng(20260730)
    with_adv = [g for g in rep_df["game_id"] if
                os.path.exists(os.path.join(ADV_DIR, f"advanced_{g}.parquet"))]
    sample = list(rng.choice(with_adv, size=min(100, len(with_adv)), replace=False))
    rows = []
    pt_idx = per_team.set_index(["game_id", "offense_team_id"])["n_poss"]
    for g in sample:
        adv = advanced_team_possessions(g)
        if not adv:
            continue
        for tid, apos in adv.items():
            key = (g, tid)
            if key in pt_idx.index and apos > 0:
                rows.append((g, tid, float(pt_idx.loc[key]), apos))
    cmp_df = pd.DataFrame(rows, columns=["game_id", "team_id", "mine", "advanced"])
    if len(cmp_df) > 3:
        corr = float(np.corrcoef(cmp_df["mine"], cmp_df["advanced"])[0, 1])
        mad = float((cmp_df["mine"] - cmp_df["advanced"]).abs().mean())
        bias = float((cmp_df["mine"] - cmp_df["advanced"]).mean())
        print(f"\nadvanced-boxscore cross-check ({len(cmp_df)} team-games from "
              f"{len(sample)} sampled games; advanced possessions = sum(player)/5):")
        print(f"  corr {corr:.4f}   mean |diff| {mad:.2f}   mean bias {bias:+.2f} "
              f"(mine - advanced)")
    else:
        print("\nadvanced-boxscore cross-check: no advanced files in sample")

    # lineup completeness
    full = ((poss["n_off_oncourt"] == 5) & (poss["n_def_oncourt"] == 5)).mean() * 100
    print(f"\nlineup join: {full:.2f}% of possessions with full 5v5 lineups "
          f"({len(poss):,} possessions total)")
    print(f"end_reason distribution:\n"
          f"{poss['end_reason'].value_counts().to_string()}")
    print(f"\nwrote {OUT_PARQUET} ({len(poss):,} rows) and {OUT_RECON}")
    print(f"runtime {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
