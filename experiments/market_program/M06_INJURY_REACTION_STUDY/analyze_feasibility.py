"""
M06_INJURY_REACTION_STUDY -- feasibility measurement only (no reaction-time
estimate is computed anywhere in this script, per the node's scope limit).

Reads real tape on disk from BOTH worktrees (read-only in both cases -- this
node's write scope is experiments/market_program/M06_INJURY_REACTION_STUDY/
in the PROGRAM worktree only):

  DATA worktree  (C:/Users/jgallagher/wnba-betting-model) -- where the
    scheduled tasks actually write:
      data/injury_official_live/{capture_log,injury_snapshots,status_transitions}.csv
      data/market_snapshots/{snapshots,poll_log,vendor_timing_log}.csv

  PROGRAM worktree (this session's cwd) -- the frozen seed committed
    alongside the capture_injury_live.py code, for contrast only:
      experiments/market_program/INJURY_OFFICIAL/live/*.csv

No network calls. No vendor credits spent. Run as:
    python analyze_feasibility.py
from this directory.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from datetime import datetime

DATA_ROOT = Path("C:/Users/jgallagher/wnba-betting-model")
PROGRAM_ROOT = Path(__file__).resolve().parents[3]  # .../player-model-program worktree root

INJURY_LIVE = DATA_ROOT / "data" / "injury_official_live"
MARKET_SNAP = DATA_ROOT / "data" / "market_snapshots"
INJURY_SEED = PROGRAM_ROOT / "experiments" / "market_program" / "INJURY_OFFICIAL" / "live"


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def minmax(vals):
    vals = sorted(v for v in vals if v)
    return (vals[0], vals[-1]) if vals else (None, None)


def main():
    out = {}

    # ---- Injury tape: DATA worktree (the real, growing, scheduler-written tape)
    cap = read_csv(INJURY_LIVE / "capture_log.csv")
    snap = read_csv(INJURY_LIVE / "injury_snapshots.csv")
    trans = read_csv(INJURY_LIVE / "status_transitions.csv")

    cap_outcomes = {}
    for r in cap:
        cap_outcomes[r["outcome"]] = cap_outcomes.get(r["outcome"], 0) + 1
    cap_min, cap_max = minmax(r["attempted_ts_utc"] for r in cap)
    snap_min, snap_max = minmax(r["retrieval_ts_utc"] for r in snap)
    novel_ids = sorted({r["capture_id"] for r in cap if r["outcome"].startswith("NOVEL")})

    real_transitions = [r for r in trans
                         if r["status_after"] != "REMOVED_FROM_REPORT"
                         and r["status_before"] != ""]

    out["injury_tape_data_worktree"] = {
        "path": str(INJURY_LIVE),
        "capture_log_rows": len(cap),
        "capture_log_outcome_distribution": cap_outcomes,
        "capture_log_attempted_ts_range": [cap_min, cap_max],
        "snapshot_rows": len(snap),
        "snapshot_retrieval_ts_range": [snap_min, snap_max],
        "distinct_novel_capture_ids": len(novel_ids),
        "status_transition_rows_total": len(trans),
        "status_transition_rows_genuine_before_after": len(real_transitions),
        "genuine_transitions": [
            {
                "team": r["team_raw"], "player": r["player_raw"],
                "status_before": r["status_before"], "status_after": r["status_after"],
                "t_lower_utc_bound": r["t_lower_utc_bound"],
                "t_upper_utc_bound": r["t_upper_utc_bound"],
            } for r in real_transitions
        ],
    }

    # ---- Injury tape: PROGRAM worktree committed seed, for contrast only
    seed_cap = read_csv(INJURY_SEED / "capture_log.csv")
    seed_snap = read_csv(INJURY_SEED / "injury_snapshots.csv")
    seed_trans = read_csv(INJURY_SEED / "status_transitions.csv")
    out["injury_tape_program_worktree_seed"] = {
        "path": str(INJURY_SEED),
        "note": "This is the frozen seed committed with capture_injury_live.py "
                "(28 docs / 552 rows per injury_live_tick.cmd's own comment). "
                "injury_live_tick.cmd sets INJURY_LIVE_DATA_ROOT so the scheduled "
                "task writes ONLY to the DATA worktree; this program-worktree copy "
                "does not grow.",
        "capture_log_rows": len(seed_cap),
        "snapshot_rows": len(seed_snap),
        "status_transition_rows": len(seed_trans),
    }

    # ---- Odds tape: DATA worktree
    mkt = read_csv(MARKET_SNAP / "snapshots.csv")
    props = [r for r in mkt if r["market"].startswith("player_")]
    gamelines = [r for r in mkt if r["market"] in ("h2h", "spreads", "totals")]

    all_min, all_max = minmax(r["retrieval_ts"] for r in mkt)
    props_min, props_max = minmax(r["retrieval_ts"] for r in props)
    gl_min, gl_max = minmax(r["retrieval_ts"] for r in gamelines)

    games = {}
    for r in mkt:
        games.setdefault(r["game_id"], {"props": 0, "gamelines": 0, "players": set()})
        if r["market"].startswith("player_"):
            games[r["game_id"]]["props"] += 1
            games[r["game_id"]]["players"].add(r["outcome"])
        else:
            games[r["game_id"]]["gamelines"] += 1

    game_summary = {}
    for gid, d in games.items():
        poll_times = sorted({r["retrieval_ts"] for r in mkt if r["game_id"] == gid})
        game_summary[gid] = {
            "props_rows": d["props"], "gameline_rows": d["gamelines"],
            "n_distinct_players_tracked": len(d["players"]),
            "n_poll_instants": len(poll_times),
            "poll_instants_range": [poll_times[0], poll_times[-1]] if poll_times else [None, None],
        }

    out["odds_tape_data_worktree"] = {
        "path": str(MARKET_SNAP / "snapshots.csv"),
        "total_rows": len(mkt),
        "props_rows": len(props),
        "gameline_rows": len(gamelines),
        "all_retrieval_ts_range": [all_min, all_max],
        "props_retrieval_ts_range": [props_min, props_max],
        "gameline_retrieval_ts_range": [gl_min, gl_max],
        "n_distinct_games": len(games),
        "per_game": game_summary,
    }

    vt = read_csv(MARKET_SNAP / "vendor_timing_log.csv")
    out["odds_tape_vendor_timing_log"] = {
        "path": str(MARKET_SNAP / "vendor_timing_log.csv"),
        "rows": len(vt),
        "note": "Populated only by this-session's ad hoc M26/M27 live-verification "
                "calls (game_id values prefixed M26-VERIFY-/M27-VERIFY-), not by "
                "the regular scheduled capture loop, as of the bytes read for this "
                "node. vendor_latency_bound/clock_skew_bound therefore remain "
                "effectively unmeasured for the ordinary scheduled poll stream.",
    }

    # ---- Cross-reference: for each genuine injury transition, does the
    # matched game (by player name appearing in that game's tracked outcome
    # set) have BOTH a before-event AND an after-event odds snapshot for
    # that exact player? This is a coverage measurement, not a reaction
    # estimate -- no reaction time, direction, or magnitude is computed.
    player_game_index = {}  # player_name -> game_id (only for player-prop rows)
    for r in props:
        player_game_index.setdefault(r["outcome"], set()).add(r["game_id"])

    linkage_rows = []
    for r in real_transitions:
        player = r["player_raw"]
        t_event_upper = r["t_upper_utc_bound"]
        candidate_games = player_game_index.get(player, set())
        row = {
            "player": player, "team": r["team_raw"],
            "status_before": r["status_before"], "status_after": r["status_after"],
            "event_t_lower": r["t_lower_utc_bound"], "event_t_upper": t_event_upper,
            "matched_game_ids": sorted(candidate_games),
        }
        if not candidate_games:
            row["coverage"] = "NO_MATCHING_GAME_IN_ODDS_TAPE"
            row["before_price_ts"] = None
            row["after_price_ts"] = None
        else:
            # use the first (only, in every observed case) matched game
            gid = sorted(candidate_games)[0]
            player_times = sorted({p["retrieval_ts"] for p in props
                                    if p["game_id"] == gid and p["outcome"] == player})
            before = [t for t in player_times if t < t_event_upper]
            after = [t for t in player_times if t > t_event_upper]
            row["before_price_ts"] = before[-1] if before else None
            row["after_price_ts"] = after[0] if after else None
            if before and after:
                row["coverage"] = "BEFORE_AND_AFTER"
            elif before:
                row["coverage"] = "BEFORE_ONLY_NO_AFTER"
            elif after:
                row["coverage"] = "AFTER_ONLY_NO_BEFORE"
            else:
                row["coverage"] = "NEITHER"
        linkage_rows.append(row)

    n_usable = sum(1 for r in linkage_rows if r["coverage"] == "BEFORE_AND_AFTER")

    out["linkage_coverage_check"] = {
        "description": "For every genuine (status_before != '') injury status "
                        "transition witnessed in the DATA-worktree injury tape, "
                        "checked whether the player-prop odds tape for the same "
                        "player+game carries at least one price snapshot BEFORE "
                        "the event's t_upper bound AND at least one AFTER it. "
                        "This is a coverage/feasibility count only -- no price "
                        "delta, direction, or timing figure is computed here.",
        "n_genuine_transitions_checked": len(linkage_rows),
        "n_with_before_and_after_coverage": n_usable,
        "rows": linkage_rows,
    }

    out_path = Path(__file__).resolve().parent / "feasibility_measurement.json"
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"n_usable_linked_events (before AND after coverage) = {n_usable}")
    print(f"n_genuine_injury_transitions_checked = {len(linkage_rows)}")
    print(f"injury snapshot tape span: {snap_min} .. {snap_max}")
    print(f"odds props tape span: {props_min} .. {props_max}")
    print(f"odds gameline tape span: {gl_min} .. {gl_max}")


if __name__ == "__main__":
    main()
