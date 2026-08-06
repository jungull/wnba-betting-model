#!/usr/bin/env python3
"""
Ladder + burst poller entry point. OFF BY DEFAULT -- see market_capture_config.py.

Wires together, for production use only (no Task Scheduler entry created by
this deliverable -- see REPORT.md section (f)):
    slate            prospective_pair.coverage_audit.build_slate() + TEAMS
    ladder rungs      market_ladder_scheduler.due_rungs()
    burst triggers    market_burst_trigger.run_watch()
    fetch + write     market_snapshot_writer.*
    credentials       odds_capture_daily.api_key() (imported, not reimplemented)

Writes ONLY to data/market_snapshots/ (new, additive per design (f)); never
touches data/odds_capture/ or data/props_capture/, and never imports
odds_capture_daily/props_capture_daily for anything beyond the credential
loader, so it cannot accidentally re-trigger their behavior.

This module is intentionally the only place in the deliverable that imports
prospective_pair.coverage_audit (for build_slate()/TEAMS) -- every other
module here takes that data as a plain-Python argument instead, exactly so
those modules stay testable without the evalharness dependency chain
coverage_audit.py pulls in. See market_burst_trigger.py's docstring.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prospective_pair"))

from market_capture_config import is_enabled  # noqa: E402
import market_ladder_scheduler as ladder  # noqa: E402
import market_burst_trigger as burst  # noqa: E402
import market_snapshot_writer as writer  # noqa: E402
import capture_coverage_audit as audit  # noqa: E402
from odds_capture_daily import api_key  # noqa: E402  (credential loader, reused verbatim)

KNOWN_BOOKS_SEED = set()   # deliberately empty: first run seeds the allow-list
KNOWN_MARKETS_SEED = {"spreads", "totals", "h2h", "player_points",
                       "player_rebounds", "player_assists", "player_threes"}


def _slate_for_scheduler():
    """coverage_audit.build_slate()'s DataFrame -> the plain-dict shape
    market_ladder_scheduler / market_burst_trigger expect. Imported lazily
    inside the function (not at module top) so that importing
    market_capture_run.py for its constants/CLI wiring does not require the
    forecast-chain data files to exist (tests never call this)."""
    from coverage_audit import build_slate, TEAMS
    slate_df = build_slate()
    games = []
    for row in slate_df.itertuples():
        gid = str(row.game_id) if getattr(row, "game_id", None) is not None else \
            f"PROV-{row.game_date}-{row.away}@{row.home}"
        games.append({"game_id": gid, "home": row.home, "away": row.away,
                      "tip": row.tip, "tip_moved": bool(row.tip_moved)})
    return games, TEAMS


def main() -> int:
    if not is_enabled():
        print("[market_capture_run] MARKET_LADDER_ENABLED is not set -- "
              "the ladder/burst poller is OFF by default. Exiting 0 (no-op, "
              "no vendor credits spent). See market_capture_config.py.")
        return 0

    now = datetime.now(timezone.utc)
    out_dir = writer.DEFAULT_SNAPSHOT_DIR
    games, team_names = _slate_for_scheduler()
    if not games:
        print(f"[{now.isoformat()}] no slate available; nothing to do")
        return 0

    key = api_key()
    session = _session()

    obligations = ladder.ladder_obligations(games, now)
    due_games = [o for o in obligations if o["due"]]

    watch_res = burst.run_watch(
        injury_csv=ROOT / "data" / "injury_capture" / "injury_log.csv",
        news_csv=ROOT / "data" / "news_capture" / "news_items.csv",
        cursor_path=out_dir / "_burst_cursor.json",
        slate=games, team_lookup=None, now=now)

    events_by_teams = {}
    if due_games or watch_res["bursts_scheduled"]:
        try:
            events_by_teams = _events_lookup(session, key, team_names)
        except Exception as e:
            print(f"WARNING: /events lookup failed, props polls will be "
                  f"skipped this run: {type(e).__name__}: {e}", file=sys.stderr)

    n_polls = n_rows = n_rejected = 0
    for o in due_games:
        game_id = o["game_id"]
        game = next(g for g in games if g["game_id"] == game_id)
        for rung in o["due"]:
            n_polls += 1
            interval = ladder.RUNG_POLL_INTERVAL_SECONDS.get(rung["label"])
            n_rows_g, n_rej_g = _poll_and_write(
                session, key, game, "ladder", rung["label"], interval,
                events_by_teams, out_dir, now)
            n_rows += n_rows_g
            n_rejected += n_rej_g

    for b in watch_res["bursts_scheduled"]:
        n_polls += 1
        game = next((g for g in games if g["game_id"] == b.game_id), None)
        if game is None:
            continue
        n_rows_g, n_rej_g = _poll_and_write(
            session, key, game, "burst", b.leg_label,
            ladder.BURST_LEG_INTERVAL_SECONDS, events_by_teams, out_dir, now)
        n_rows += n_rows_g
        n_rejected += n_rej_g

    print(f"[{now.isoformat()}] polls={n_polls} rows_written={n_rows} "
          f"rows_rejected={n_rejected} bursts_triggered={len(watch_res['bursts_scheduled'])}")
    return 0


def _session():
    import requests
    return requests.Session()


def _events_lookup(session, key, team_names) -> dict:
    """Free /events call -> {(home_abbr, away_abbr): vendor_event_id}, so a
    ladder rung / burst leg for a game can scope its props pull to that
    game's single event id (design (b) step 4). `team_names` is
    coverage_audit.TEAMS (full name -> abbreviation)."""
    import requests
    r = session.get(f"https://api.the-odds-api.com/v4/sports/basketball_wnba/events",
                    params={"apiKey": key}, timeout=30)
    r.raise_for_status()
    out = {}
    for ev in r.json():
        h = team_names.get(ev.get("home_team"))
        a = team_names.get(ev.get("away_team"))
        if h and a:
            out[(h, a)] = ev["id"]
    return out


def _poll_and_write(session, key, game, obligation_type, label,
                     poll_interval_seconds, events_by_teams, out_dir, now):
    """Fetch the slate-wide odds snapshot (every ladder rung and burst leg
    polls it -- it is not scopeable to one game) plus, if this game's vendor
    event id resolved, its props scoped to that one event. Writes rows +
    one poll_log entry per endpoint hit. Never raises past this function: a
    failed poll is logged, not fatal to the rest of the run (matches every
    existing capture script's per-item try/except discipline)."""
    game_id = game["game_id"]
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    n_written_total = n_rejected_total = 0

    entry = {"poll_ts": retrieval_ts, "game_id": game_id,
              "obligation_type": obligation_type, "label": label,
              "endpoint": writer.ODDS_URL, "n_rows_written": 0,
              "n_rows_rejected": 0}
    try:
        games_json, raw, resp = writer.fetch_odds_snapshot(session, key)
        entry["http_status"] = resp.status_code
        entry["credits_used"] = resp.headers.get("x-requests-used")
        entry["credits_remaining"] = resp.headers.get("x-requests-remaining")
        entry["credits_last"] = resp.headers.get("x-requests-last")
        rows = writer.flatten_odds_payload(
            games_json, retrieval_ts, poll_interval_seconds=poll_interval_seconds,
            a_payload_hash=writer.payload_hash(raw))
        rows = [r for r in rows if r["game_id"] == game_id]
        chain = writer.ChainIndex(out_dir / writer.CHAIN_INDEX_JSON)
        writer.attach_chain_fields(rows, chain, retrieval_ts)
        n_written, rejected = writer.append_snapshot_rows(rows, out_dir)
        chain.save()
        entry["n_rows_written"], entry["n_rows_rejected"] = n_written, len(rejected)
        entry["error"] = None
        n_written_total += n_written
        n_rejected_total += len(rejected)
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
        print(f"WARNING: odds poll failed for {game_id} {obligation_type}/{label}: "
              f"{entry['error']}", file=sys.stderr)
    writer.append_poll_log(entry, out_dir)

    event_id = events_by_teams.get((game["home"], game["away"]))
    if event_id is None:
        return n_written_total, n_rejected_total

    p_entry = {"poll_ts": retrieval_ts, "game_id": game_id,
               "obligation_type": obligation_type, "label": label,
               "endpoint": writer.EVENT_ODDS_URL.format(event_id=event_id),
               "n_rows_written": 0, "n_rows_rejected": 0}
    try:
        ev_json, raw, resp = writer.fetch_event_props_snapshot(session, key, event_id)
        p_entry["http_status"] = resp.status_code
        p_entry["credits_used"] = resp.headers.get("x-requests-used")
        p_entry["credits_remaining"] = resp.headers.get("x-requests-remaining")
        p_entry["credits_last"] = resp.headers.get("x-requests-last")
        rows = writer.flatten_props_payload(
            ev_json, retrieval_ts, poll_interval_seconds=poll_interval_seconds,
            a_payload_hash=writer.payload_hash(raw))
        chain = writer.ChainIndex(out_dir / writer.CHAIN_INDEX_JSON)
        writer.attach_chain_fields(rows, chain, retrieval_ts)
        n_written, rejected = writer.append_snapshot_rows(rows, out_dir)
        chain.save()
        p_entry["n_rows_written"], p_entry["n_rows_rejected"] = n_written, len(rejected)
        p_entry["error"] = None
        n_written_total += n_written
        n_rejected_total += len(rejected)
    except Exception as e:
        p_entry["error"] = f"{type(e).__name__}: {e}"
        print(f"WARNING: props poll failed for {game_id} {obligation_type}/{label}: "
              f"{p_entry['error']}", file=sys.stderr)
    writer.append_poll_log(p_entry, out_dir)
    return n_written_total, n_rejected_total


if __name__ == "__main__":
    raise SystemExit(main())
