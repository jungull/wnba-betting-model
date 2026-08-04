"""O14_OPS_ENTITY_RESOLUTION -- reproduction harness.

Measures the entity-resolution behaviour of the PROSPECTIVE capture/forecast
path as it is actually implemented in ``daily_forecast.py`` (the player layer,
lines 606-760).  Nothing here modifies any shared artifact; it only reads.

Two data snapshots are addressed, and every number is labelled with which one
produced it:

  SNAP_PROGRAM   the copy of data/ inside THIS worktree (player-model-program).
                 master_player.parquet manifest fit_through 2026-08-01T12:00Z;
                 injury_log.csv captures 20260730T154950Z .. 20260801T150005Z.
  SNAP_LIVE      the copy of data/ in the repository root worktree, read-only.
                 This is the snapshot PROJECT_UPDATE_2026-08-04.md was written
                 against.  It is READ ONLY.  Nothing is written there.

Run:  python repro_entity_resolution.py            (writes MEASUREMENTS.json)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM_REPO = HERE.parents[3]          # ...\worktrees\player-model-program
LIVE_REPO = Path(r"C:\Users\jgallagher\wnba-betting-model")

# --- constants copied verbatim from daily_forecast.py -----------------------
# daily_forecast.py:112  MINUTES_ALPHA = 0.30
# daily_forecast.py:120  RECENCY_GAMES = 3
MINUTES_ALPHA = 0.30
RECENCY_GAMES = 3

# daily_forecast.py:606-609 -- the ONLY name-resolution primitive in the path.
def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load(repo: Path):
    p = pd.read_parquet(repo / "data" / "masters" / "master_player.parquet")
    i = pd.read_csv(repo / "data" / "injury_capture" / "injury_log.csv")
    return p, i


def team_name_to_abbr(master: pd.DataFrame, injury: pd.DataFrame) -> dict:
    """daily_forecast.py:651 inverts its own TEAMS dict.  We rebuild the same
    mapping from the data so the harness does not depend on importing the
    frozen forecaster (which would execute its slate/odds path)."""
    # last token of the franchise name is enough to disambiguate all 15 except
    # the two LA teams and the two 'Sun/Storm' style names -- do it explicitly.
    known = {
        "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
        "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
        "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
        "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
        "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
        "Portland Fire": "PDX", "Seattle Storm": "SEA",
        "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
    }
    missing = sorted(set(injury.team.unique()) - set(known))
    if missing:
        raise SystemExit(f"unmapped franchise names in injury feed: {missing}")
    unknown_abbr = sorted(set(known.values()) - set(master.team_abbreviation.unique()))
    if unknown_abbr:
        raise SystemExit(f"abbreviations absent from master: {unknown_abbr}")
    return known


def ewma_last(minutes: pd.Series) -> float | None:
    if not len(minutes):
        return None
    return float(minutes.ewm(alpha=MINUTES_ALPHA, adjust=True).mean().iloc[-1])


# ---------------------------------------------------------------------------
# M1  per-team truncation of a transferred player's minutes history
# ---------------------------------------------------------------------------
def m1_transfer_history_truncation(p: pd.DataFrame, season: int) -> dict:
    """daily_forecast.py:654 filters the whole player frame to ONE team
    (`tp = p[p.team_abbreviation == team_ab]`) and every later per-player
    computation -- history, min_ewma, games_played, cold_start (line 674-683) --
    is taken from that team-filtered frame.  A player who changed teams
    mid-season therefore has her prior-team rows in the SAME season silently
    discarded.  Measure the size of that discard."""
    s = p[p.season == season]
    n_team = s.groupby("player_id").team_abbreviation.nunique()
    movers = sorted(n_team[n_team > 1].index)
    rows = []
    for pid in movers:
        sub = s[s.player_id == pid].sort_values(["game_date", "game_id"])
        name = sub.player_name.iloc[-1]
        # the team the player is CURRENTLY on = team of her most recent row
        cur = sub.team_abbreviation.iloc[-1]
        played_all = sub[sub.minutes.notna() & (sub.minutes > 0)]
        played_cur = played_all[played_all.team_abbreviation == cur]
        rows.append({
            "player_id": int(pid),
            "player_name": str(name),
            "current_team": str(cur),
            "teams_this_season": {str(k): int(v) for k, v in
                                  sub.groupby("team_abbreviation").size().items()},
            "games_played_identity": int(len(played_all)),
            "games_played_as_seen_by_forecaster": int(len(played_cur)),
            "games_discarded": int(len(played_all) - len(played_cur)),
            "min_ewma_identity": ewma_last(played_all.minutes),
            "min_ewma_as_seen_by_forecaster": ewma_last(played_cur.minutes),
        })
    for r in rows:
        a, b = r["min_ewma_identity"], r["min_ewma_as_seen_by_forecaster"]
        r["min_ewma_abs_error"] = None if (a is None or b is None) else abs(a - b)
    errs = [r["min_ewma_abs_error"] for r in rows if r["min_ewma_abs_error"] is not None]
    return {
        "n_movers": len(rows),
        "n_movers_with_single_game_at_new_team":
            sum(1 for r in rows if r["games_played_as_seen_by_forecaster"] <= 1),
        "min_ewma_abs_error_mean": float(np.mean(errs)) if errs else None,
        "min_ewma_abs_error_max": float(np.max(errs)) if errs else None,
        "movers": rows,
    }


# ---------------------------------------------------------------------------
# M2  can one player_id be on two teams' recency rosters at once?
# ---------------------------------------------------------------------------
def m2_double_rostering(p: pd.DataFrame, season: int, slate_date) -> dict:
    """daily_forecast.py:662-665 builds each team's recency roster from that
    team's own last RECENCY_GAMES games.  There is no cross-team exclusivity
    check anywhere in the function, so a player who changed teams inside the
    window appears on BOTH rosters and her min_ewma is added to BOTH teams'
    `sum_min_ewma_available` (line 743)."""
    s = p[(p.season == season) & (pd.to_datetime(p.game_date).dt.date < slate_date)].copy()
    s["game_date"] = pd.to_datetime(s.game_date)
    roster_of = {}
    for ab, tp in s.groupby("team_abbreviation"):
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        roster_of[ab] = set(tp[tp.game_id.isin(recent)].player_id.unique())
    dup = {}
    for ab, ids in roster_of.items():
        for pid in ids:
            dup.setdefault(pid, []).append(ab)
    doubles = {int(k): sorted(v) for k, v in dup.items() if len(v) > 1}
    named = []
    for pid, teams in doubles.items():
        named.append({"player_id": pid,
                      "player_name": str(s[s.player_id == pid].player_name.iloc[0]),
                      "on_recency_rosters_of": teams})
    return {"slate_date": str(slate_date),
            "n_players_on_two_rosters": len(named), "players": named}


# ---------------------------------------------------------------------------
# M3  injury row team-keying: can the Out gate fire on a transferred player?
# ---------------------------------------------------------------------------
def m3_injury_team_keying(p: pd.DataFrame, inj: pd.DataFrame, season: int,
                          name2ab: dict) -> dict:
    """daily_forecast.py:667-668 selects a team's injury rows by FRANCHISE NAME
    equality (`inj[inj.team == abbr_to_name[team_ab]]`) and then matches by
    normalized player name (line 685) inside that team only.  Consequence: a
    designation published under a player's FORMER franchise can never reach her
    current team's roster entry.  Measure how many captured designations name a
    player whose master-of-record team for the season is a different team."""
    s = p[p.season == season]
    norm2ids = {}
    for pid, nm in s[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
        norm2ids.setdefault(_norm_name(nm), set()).add(int(pid))
    # team-of-record = team of the player's latest row this season
    latest_team = (s.sort_values(["game_date", "game_id"])
                    .groupby("player_id").team_abbreviation.last().to_dict())
    teams_ever = s.groupby("player_id").team_abbreviation.apply(
        lambda x: sorted(set(x))).to_dict()

    latest = (inj.sort_values("capture_utc")
                 .drop_duplicates(subset=["team", "player"], keep="last"))
    cross, unknown, ok = [], [], 0
    for r in latest.itertuples(index=False):
        ab = name2ab[r.team]
        ids = norm2ids.get(_norm_name(r.player), set())
        if not ids:
            unknown.append({"team": r.team, "player": r.player, "status": r.status})
            continue
        pid = sorted(ids)[0]
        if ab in teams_ever.get(pid, []):
            ok += 1
        else:
            cross.append({"injury_row_team": r.team, "injury_row_abbr": ab,
                          "player": r.player, "status": r.status,
                          "player_id": pid,
                          "master_team_of_record": latest_team.get(pid),
                          "master_teams_this_season": teams_ever.get(pid)})
    return {
        "n_latest_designations": int(len(latest)),
        "n_resolved_to_the_same_team": ok,
        "n_resolved_to_a_DIFFERENT_team": len(cross),
        "n_unresolvable_to_any_master_player": len(unknown),
        "cross_team_rows": cross,
        "unresolvable_rows": unknown,
    }


# ---------------------------------------------------------------------------
# M4  does normalized-exact matching lose anything on the real feed?
# ---------------------------------------------------------------------------
def m4_name_normalisation(p: pd.DataFrame, inj: pd.DataFrame, season: int) -> dict:
    """Two questions the OPERATIONAL_GAPS note (line 182-185) leaves open:
    (a) does _norm_name COLLIDE two distinct master players (a false match);
    (b) do any captured names fail normalized-exact but resolve under a
        strictly weaker rule (first-initial + surname), i.e. is the missing
        alias table actually costing matches TODAY."""
    s = p[p.season == season]
    ids = s[["player_id", "player_name"]].drop_duplicates()
    coll = {}
    for pid, nm in ids.itertuples(index=False):
        coll.setdefault(_norm_name(nm), set()).add(int(pid))
    collisions = {k: sorted(v) for k, v in coll.items() if len(v) > 1}

    master_norms = set(coll)

    def weak(nm: str) -> str:
        parts = re.split(r"\s+", str(nm).strip())
        if len(parts) < 2:
            return _norm_name(nm)
        return _norm_name(parts[0][:1] + parts[-1])

    weak_index = {}
    for pid, nm in ids.itertuples(index=False):
        weak_index.setdefault(weak(nm), set()).add(int(pid))

    unmatched_exact, recovered_by_weak = [], []
    for nm in sorted(inj.player.unique()):
        if _norm_name(nm) in master_norms:
            continue
        unmatched_exact.append(nm)
        cand = weak_index.get(weak(nm), set())
        if len(cand) == 1:
            pid = sorted(cand)[0]
            recovered_by_weak.append(
                {"capture_name": nm, "player_id": pid,
                 "master_name": str(ids[ids.player_id == pid].player_name.iloc[0])})
    return {
        "n_distinct_capture_names": int(inj.player.nunique()),
        "n_norm_collisions_between_distinct_master_players": len(collisions),
        "norm_collisions": collisions,
        "n_capture_names_unmatched_by_normalized_exact": len(unmatched_exact),
        "unmatched_capture_names": unmatched_exact,
        "n_recovered_by_first_initial_plus_surname": len(recovered_by_weak),
        "recovered": recovered_by_weak,
    }


# ---------------------------------------------------------------------------
# M5  the specific D-e claim: Kelsey Plum
# ---------------------------------------------------------------------------
def m5_plum(p: pd.DataFrame, season: int) -> dict:
    """PROJECT_UPDATE_2026-08-04.md:214-216 states Plum shows
    'LAS 2026 (17 g) + PHX 2026 (1 g); one appearance falls below the matcher's
    season-history threshold'.  Check the counts against the bytes, and check
    whether the mechanism named ('season-history threshold') exists."""
    pl = p[p.player_name.str.contains("Plum", na=False)]
    by = {f"{int(r.season)}/{r.team_abbreviation}": int(n)
          for (r, n) in [(row, cnt) for row, cnt in
                         zip(pl.groupby(["season", "team_abbreviation"]).size().reset_index()
                             .itertuples(index=False),
                             pl.groupby(["season", "team_abbreviation"]).size().values)]}
    cur = pl[pl.season == season]
    detail = {}
    for ab, sub in cur.groupby("team_abbreviation"):
        detail[str(ab)] = {"rows": int(len(sub)),
                           "dates": sorted(str(pd.Timestamp(d).date()) for d in sub.game_date)}
        # is that appearance inside PHX's last RECENCY_GAMES games?
        tp = p[(p.season == season) & (p.team_abbreviation == ab)].copy()
        tp["game_date"] = pd.to_datetime(tp.game_date)
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        detail[str(ab)]["on_recency_roster_as_of_end_of_snapshot"] = bool(
            set(sub.game_id) & recent)
    return {"season_team_counts": by, "current_season_detail": detail}


# ---------------------------------------------------------------------------
# M6  AS-OF resolution.  M3 asks the question against the FINAL master and so
#     cannot see a transfer that the master had not yet ingested at capture
#     time.  This asks it the way the forecaster actually asks it: at each
#     capture timestamp, against only the games that had been played before it.
# ---------------------------------------------------------------------------
def m6_asof_resolution(p: pd.DataFrame, inj: pd.DataFrame, season: int,
                       name2ab: dict) -> dict:
    s = p[p.season == season].copy()
    s["gd"] = pd.to_datetime(s.game_date).dt.tz_localize("UTC")
    s["norm"] = s.player_name.map(_norm_name)
    # EVERY captured row, not the latest per (team, player): the defect is a
    # transient window, and collapsing to the latest state hides exactly the
    # interval in which the forecaster would have run.
    i = inj.copy()
    i["cap_dt"] = pd.to_datetime(i.capture_utc, format="%Y%m%dT%H%M%SZ", utc=True)
    i = i.sort_values("cap_dt")

    same, cross, cold = 0, [], []
    for r in i.itertuples(index=False):
        ab = name2ab[r.team]
        # the master the forecaster would hold: games strictly before the
        # capture date (build_masters runs the following morning at 08:30).
        vis = s[s.gd < r.cap_dt.normalize()]
        nm = _norm_name(r.player)
        mine = vis[(vis.norm == nm) & (vis.team_abbreviation == ab)]
        if len(mine):
            same += 1
            continue
        elsewhere = vis[vis.norm == nm]
        if len(elsewhere):
            cross.append({
                "capture_utc": str(r.capture_utc), "injury_row_team": r.team,
                "injury_row_abbr": ab, "player": r.player, "status": r.status,
                "visible_teams_at_capture": sorted(set(elsewhere.team_abbreviation)),
                "last_visible_game": str(elsewhere.gd.max().date()),
            })
        else:
            cold.append({"capture_utc": str(r.capture_utc), "team": r.team,
                         "player": r.player, "status": r.status,
                         "in_any_earlier_season": bool(
                             len(p[(p.season < season)
                                   & (p.player_name.map(_norm_name) == nm)]))})
    cross_players = sorted({c["player"] for c in cross})
    cold_players = sorted({c["player"] for c in cold})
    windows = {}
    for c in cross:
        w = windows.setdefault(c["player"], {"first": c["capture_utc"],
                                             "last": c["capture_utc"], "n": 0,
                                             "team": c["injury_row_team"],
                                             "statuses": set()})
        w["last"] = c["capture_utc"]
        w["n"] += 1
        w["statuses"].add(c["status"])
    for w in windows.values():
        w["statuses"] = sorted(w["statuses"])
    return {
        "n_capture_rows_examined": int(len(i)),
        "n_bind_to_the_named_team": same,
        "distinct_players_unbindable_to_named_team": cross_players,
        "distinct_players_absent_from_season": cold_players,
        "unbindable_windows": windows,
        "n_player_known_but_ONLY_under_a_different_team": len(cross),
        "n_player_not_in_this_season_at_all": len(cold),
        "cross_team_asof_rows": cross,
        "cold_rows": cold,
    }


# ---------------------------------------------------------------------------
# M7  minutes double-counted by M2's double-rostered players
# ---------------------------------------------------------------------------
def m7_double_counted_minutes(p: pd.DataFrame, season: int, slate_date,
                              doubles: list) -> dict:
    s = p[(p.season == season) & (pd.to_datetime(p.game_date).dt.date < slate_date)].copy()
    rows = []
    for d in doubles:
        pid = d["player_id"]
        for ab in d["on_recency_rosters_of"]:
            tp = s[s.team_abbreviation == ab]
            hist = tp[(tp.player_id == pid) & tp.minutes.notna() & (tp.minutes > 0)] \
                .sort_values(["game_date", "game_id"])
            rows.append({"player_id": pid, "player_name": d["player_name"],
                         "team": ab, "games_at_this_team": int(len(hist)),
                         "min_ewma_attributed_to_this_team": ewma_last(hist.minutes)})
    tot = sum(r["min_ewma_attributed_to_this_team"] or 0.0 for r in rows)
    return {"per_team_attribution": rows,
            "total_minutes_attributed_across_teams": float(tot)}


# ---------------------------------------------------------------------------
# M8  the props capture path carries no identity at all
# ---------------------------------------------------------------------------
def m8_props_identity(repo: Path, p: pd.DataFrame, season: int) -> dict:
    f = repo / "data" / "props_capture" / "master_props.csv"
    if not f.exists():
        return {"present": False}
    d = pd.read_csv(f)
    names = sorted(set(d.player_name.dropna())) if "player_name" in d else []
    m_season = set(p[p.season == season].player_name.map(_norm_name))
    m_all = set(p.player_name.map(_norm_name))
    u_season = [x for x in names if _norm_name(x) not in m_season]
    u_all = [x for x in names if _norm_name(x) not in m_all]
    return {
        "present": True, "rows": int(len(d)),
        "has_player_id_column": bool("player_id" in d.columns),
        "distinct_player_names": len(names),
        "unmatched_against_current_season_master": u_season,
        "unmatched_against_all_seasons_master": u_all,
    }


def run(repo: Path, label: str) -> dict:
    p, inj = load(repo)
    season = int(p.season.max())
    name2ab = team_name_to_abbr(p, inj)
    slate_date = (pd.to_datetime(p[p.season == season].game_date).max()
                  + pd.Timedelta(days=1)).date()
    m2 = m2_double_rostering(p, season, slate_date)
    return {
        "snapshot": label,
        "repo": str(repo),
        "season": season,
        "master_rows": int(len(p)),
        "master_last_game_date": str(pd.to_datetime(p.game_date).max().date()),
        "injury_rows": int(len(inj)),
        "injury_capture_span": [str(inj.capture_utc.min()), str(inj.capture_utc.max())],
        "assumed_slate_date": str(slate_date),
        "M1_transfer_history_truncation": m1_transfer_history_truncation(p, season),
        "M2_double_rostering": m2,
        "M3_injury_team_keying": m3_injury_team_keying(p, inj, season, name2ab),
        "M4_name_normalisation": m4_name_normalisation(p, inj, season),
        "M5_plum": m5_plum(p, season),
        "M6_asof_resolution": m6_asof_resolution(p, inj, season, name2ab),
        "M7_double_counted_minutes": m7_double_counted_minutes(
            p, season, slate_date, m2["players"]),
        "M8_props_identity": m8_props_identity(repo, p, season),
    }


def main() -> int:
    out = {"generated_by": "experiments/player_program/ops_lane/"
                           "O14_OPS_ENTITY_RESOLUTION/repro_entity_resolution.py",
           "snapshots": []}
    out["snapshots"].append(run(PROGRAM_REPO, "SNAP_PROGRAM"))
    if (LIVE_REPO / "data" / "masters" / "master_player.parquet").exists():
        out["snapshots"].append(run(LIVE_REPO, "SNAP_LIVE_readonly"))
    else:
        out["snapshots"].append({"snapshot": "SNAP_LIVE_readonly",
                                 "error": "not present"})
    dest = HERE / "MEASUREMENTS.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {dest}")
    for s in out["snapshots"]:
        if "error" in s:
            print(s)
            continue
        print(f"\n--- {s['snapshot']} (master through {s['master_last_game_date']}, "
              f"{s['injury_rows']} injury rows) ---")
        m1 = s["M1_transfer_history_truncation"]
        print(f"M1 movers={m1['n_movers']} "
              f"with<=1 game at new team={m1['n_movers_with_single_game_at_new_team']} "
              f"mean|dEWMA|={m1['min_ewma_abs_error_mean']}")
        print(f"M2 double-rostered players={s['M2_double_rostering']['n_players_on_two_rosters']}")
        m3 = s["M3_injury_team_keying"]
        print(f"M3 designations={m3['n_latest_designations']} same-team={m3['n_resolved_to_the_same_team']} "
              f"cross-team={m3['n_resolved_to_a_DIFFERENT_team']} "
              f"unresolvable={m3['n_unresolvable_to_any_master_player']}")
        m4 = s["M4_name_normalisation"]
        print(f"M4 collisions={m4['n_norm_collisions_between_distinct_master_players']} "
              f"unmatched-exact={m4['n_capture_names_unmatched_by_normalized_exact']} "
              f"recovered-by-weak={m4['n_recovered_by_first_initial_plus_surname']}")
        print(f"M5 plum={s['M5_plum']['current_season_detail']}")
        m6 = s["M6_asof_resolution"]
        print(f"M6 as-of: bind-to-named-team={m6['n_bind_to_the_named_team']} "
              f"known-only-under-another-team={m6['n_player_known_but_ONLY_under_a_different_team']} "
              f"not-in-season={m6['n_player_not_in_this_season_at_all']}")
        for c in m6["cross_team_asof_rows"]:
            print("   CROSS:", c)
        print(f"M7 {s['M7_double_counted_minutes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
