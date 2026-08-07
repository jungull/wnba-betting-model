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

from market_capture_config import (  # noqa: E402
    is_enabled, is_per_book_polling_enabled, PER_BOOK_DECLARED_BOOKS,
    PER_BOOK_POLL_INTERVAL_SECONDS,
)
import market_ladder_scheduler as ladder  # noqa: E402
import market_burst_trigger as burst  # noqa: E402
import market_per_book_scheduler as per_book  # noqa: E402
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

    # M27_PER_BOOK_POLLING: which games are due for a scoped per-book poll
    # cycle right now (kill switch gated -- see market_capture_config.
    # is_per_book_polling_enabled). Computed BEFORE the /events lookup so a
    # per-book-only run (no ladder rung, no burst) still triggers the free
    # /events call it needs to resolve event ids.
    per_book_cursor = None
    per_book_due = []
    if is_per_book_polling_enabled():
        per_book_cursor = per_book.PerBookCursor(out_dir / per_book.PER_BOOK_CURSOR_JSON)
        for g in games:
            last = per_book_cursor.last_polled(g["game_id"])
            if per_book.due_per_book(g, now, last):
                per_book_due.append(g)

    events_by_teams = {}
    if due_games or watch_res["bursts_scheduled"] or per_book_due:
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

    n_per_book_calls = 0
    for game in per_book_due:
        event_id = events_by_teams.get((game["home"], game["away"]))
        if event_id is None:
            continue
        n_rows_g, n_rej_g, n_calls_g = _poll_per_book(
            session, key, game, event_id, out_dir, now)
        n_rows += n_rows_g
        n_rejected += n_rej_g
        n_per_book_calls += n_calls_g
        n_polls += n_calls_g
        per_book_cursor.mark_polled(game["game_id"], now)
    if per_book_cursor is not None:
        per_book_cursor.save()

    print(f"[{now.isoformat()}] polls={n_polls} rows_written={n_rows} "
          f"rows_rejected={n_rejected} bursts_triggered={len(watch_res['bursts_scheduled'])} "
          f"per_book_games_polled={len(per_book_due)} per_book_calls={n_per_book_calls}")
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
    existing capture script's per-item try/except discipline).

    M26_CAPTURE_MICROSTRUCTURE_REMEDIATION fixes applied here (see that
    node's REPORT.md for the full audit trail):

    DEFECT 1 (game-odds endpoint wrote zero rows on all 21 measured polls):
    root cause was this function filtering the slate-wide odds response by
    OUR internal `game_id` (a league id / PROV-id, e.g. "1022600230"), while
    every row `flatten_odds_payload` produces carries the VENDOR's own event
    id (a hex uuid, e.g. "58beff9061f15ff3f416542cb51f4751") as `game_id` --
    the two id spaces never intersect, so the filter silently zeroed every
    poll's rows before validation even ran (HTTP 200, 0 written, 0 rejected,
    no error -- exactly the symptom M16/coordinator measured). The fix:
    resolve this game's vendor event id via `events_by_teams` (the same
    lookup the props branch already used) BEFORE filtering, and filter on
    THAT id instead. If no vendor event id resolves for this game, the
    slate-wide odds response cannot be honestly attributed to this game at
    all (the endpoint is not scopeable to one game) -- record that as an
    explicit reason in the poll log rather than another silent zero.

    DEFECT 2 (all books/markets shared one byte-identical retrieval_ts per
    poll): partially fixed -- retrieval_ts is now witnessed fresh at the
    instant EACH HTTP response is actually received (inside
    fetch_odds_snapshot/fetch_event_props_snapshot's timing dict), not
    computed once before both calls and reused. The odds call and the props
    call now carry genuinely different, real retrieval_ts values. What this
    does NOT fix, and cannot be fixed from this vendor without a poll-rate/
    quota-ceiling decision this node is not authorized to make unilaterally:
    within ONE HTTP response, all books/bookmakers arrive in a single JSON
    payload with no per-book timing signal -- see REPORT.md defect-2 section
    for the full reasoning and the decision packet this raises.
    """
    game_id = game["game_id"]
    n_written_total = n_rejected_total = 0
    event_id = events_by_teams.get((game["home"], game["away"]))

    poll_ts_for_log = datetime.now(timezone.utc).isoformat()
    entry = {"poll_ts": poll_ts_for_log, "game_id": game_id,
              "obligation_type": obligation_type, "label": label,
              "endpoint": writer.ODDS_URL, "n_rows_written": 0,
              "n_rows_rejected": 0}
    if event_id is None:
        entry["error"] = ("SKIPPED: no vendor event_id resolved for this game "
                          "via /events team-name lookup; the game-odds "
                          "endpoint returns the whole slate and is not "
                          "scopeable to one game, so its rows cannot be "
                          "honestly attributed to this game_id without an "
                          "event_id to filter on (DEFECT 1 fix -- see "
                          "M26_CAPTURE_MICROSTRUCTURE_REMEDIATION/REPORT.md)")
        writer.append_poll_log(entry, out_dir)
    else:
        try:
            games_json, raw, resp, timing = writer.fetch_odds_snapshot(session, key)
            retrieval_ts = timing["response_received_ts"]
            entry["poll_ts"] = retrieval_ts
            entry["http_status"] = resp.status_code
            entry["credits_used"] = resp.headers.get("x-requests-used")
            entry["credits_remaining"] = resp.headers.get("x-requests-remaining")
            entry["credits_last"] = resp.headers.get("x-requests-last")
            a_payload_hash = writer.payload_hash(raw)
            rows = writer.flatten_odds_payload(
                games_json, retrieval_ts, poll_interval_seconds=poll_interval_seconds,
                a_payload_hash=a_payload_hash)
            # DEFECT 1 fix: filter on the vendor's own event id (what
            # flatten_odds_payload actually stamped as row["game_id"]), not
            # our internal game_id.
            rows = [r for r in rows if r["game_id"] == str(event_id)]

            ingestion_ts = datetime.now(timezone.utc).isoformat()
            roster = writer.RosterIndex(out_dir / writer.ROSTER_INDEX_JSON)
            vanish_rows = writer.detect_vanished_chains(
                rows, roster, roster_key=f"{game_id}:odds", game_id=game_id,
                retrieval_ts=retrieval_ts, ingestion_ts=ingestion_ts,
                poll_interval_seconds=poll_interval_seconds,
                a_payload_hash=a_payload_hash)
            rows = rows + vanish_rows

            chain = writer.ChainIndex(out_dir / writer.CHAIN_INDEX_JSON)
            writer.attach_chain_fields(rows, chain, retrieval_ts)
            n_written, rejected = writer.append_snapshot_rows(rows, out_dir)
            chain.save()
            roster.save()
            entry["n_rows_written"], entry["n_rows_rejected"] = n_written, len(rejected)
            entry["n_rows_vanished_witnessed"] = len(vanish_rows)
            entry["error"] = None
            n_written_total += n_written
            n_rejected_total += len(rejected)
            writer.append_vendor_timing_log({**timing, "poll_ts": retrieval_ts,
                                             "game_id": game_id,
                                             "endpoint": writer.ODDS_URL}, out_dir)
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            print(f"WARNING: odds poll failed for {game_id} {obligation_type}/{label}: "
                  f"{entry['error']}", file=sys.stderr)
        writer.append_poll_log(entry, out_dir)

    if event_id is None:
        return n_written_total, n_rejected_total

    p_entry = {"poll_ts": datetime.now(timezone.utc).isoformat(), "game_id": game_id,
               "obligation_type": obligation_type, "label": label,
               "endpoint": writer.EVENT_ODDS_URL.format(event_id=event_id),
               "n_rows_written": 0, "n_rows_rejected": 0}
    try:
        ev_json, raw, resp, timing = writer.fetch_event_props_snapshot(session, key, event_id)
        retrieval_ts = timing["response_received_ts"]
        p_entry["poll_ts"] = retrieval_ts
        p_entry["http_status"] = resp.status_code
        p_entry["credits_used"] = resp.headers.get("x-requests-used")
        p_entry["credits_remaining"] = resp.headers.get("x-requests-remaining")
        p_entry["credits_last"] = resp.headers.get("x-requests-last")
        a_payload_hash = writer.payload_hash(raw)
        rows = writer.flatten_props_payload(
            ev_json, retrieval_ts, poll_interval_seconds=poll_interval_seconds,
            a_payload_hash=a_payload_hash)

        ingestion_ts = datetime.now(timezone.utc).isoformat()
        vanish_rows = []
        if ev_json is not None:
            # Guard: a 422 (ev_json is None -> flatten_props_payload
            # returns []) means we-failed-to-get-a-normal-response, not "the
            # vendor's active markets legitimately became empty". Running
            # roster-diff on an empty `rows` here would falsely mark every
            # previously-active chain as vanished and wipe the roster memory
            # -- exactly the book-suspended vs. we-failed-to-poll conflation
            # M17 flagged as unacceptable. Only diff the roster on a normal,
            # well-formed response.
            roster = writer.RosterIndex(out_dir / writer.ROSTER_INDEX_JSON)
            vanish_rows = writer.detect_vanished_chains(
                rows, roster, roster_key=f"{game_id}:props", game_id=game_id,
                retrieval_ts=retrieval_ts, ingestion_ts=ingestion_ts,
                poll_interval_seconds=poll_interval_seconds,
                a_payload_hash=a_payload_hash)
            roster.save()
        rows = rows + vanish_rows

        chain = writer.ChainIndex(out_dir / writer.CHAIN_INDEX_JSON)
        writer.attach_chain_fields(rows, chain, retrieval_ts)
        n_written, rejected = writer.append_snapshot_rows(rows, out_dir)
        chain.save()
        p_entry["n_rows_written"], p_entry["n_rows_rejected"] = n_written, len(rejected)
        p_entry["n_rows_vanished_witnessed"] = len(vanish_rows)
        p_entry["error"] = None
        n_written_total += n_written
        n_rejected_total += len(rejected)
        writer.append_vendor_timing_log({**timing, "poll_ts": retrieval_ts,
                                         "game_id": game_id,
                                         "endpoint": p_entry["endpoint"]}, out_dir)
    except Exception as e:
        p_entry["error"] = f"{type(e).__name__}: {e}"
        print(f"WARNING: props poll failed for {game_id} {obligation_type}/{label}: "
              f"{p_entry['error']}", file=sys.stderr)
    writer.append_poll_log(p_entry, out_dir)
    return n_written_total, n_rejected_total


def _poll_per_book(session, key, game, event_id, out_dir, now):
    """M27_PER_BOOK_POLLING (D052/D053, bounded scope -- see
    market_capture_config.py for the declared books/window/interval and
    M27_PER_BOOK_POLLING/M27_REPORT_BODY.md for the tape evidence behind
    them). Issues one SEPARATE props HTTP call per book in
    PER_BOOK_DECLARED_BOOKS, scoped via `bookmakers=<book>` instead of the
    bundled `regions=us` call -- each call is a genuinely independent round
    trip with its own witnessed `retrieval_ts`, closing the M26 defect-2(b)
    gap (all books sharing one byte-identical timestamp) for exactly the
    declared subset, without touching the bundled odds/props polls' own
    behavior at all (the M26 anti-faking test
    `test_defect2_within_one_payload_books_still_share_one_timestamp_documented`
    exercises the UNCHANGED bundled path and must keep passing).

    Politeness: >=1s spacing between successive per-book calls, matching
    the polite-client discipline used elsewhere in this program (no
    documented Odds API rate ceiling exists to size against more precisely
    -- see M27_REPORT_BODY.md Section 4).

    Roster/vanish-detection uses a per-book roster_key
    (f"{game_id}:props:perbook:{book}") distinct from the bundled props
    roster key, so a single book's per-book poll never mistakes "this book
    wasn't in THIS call" (every other call, by construction, since each
    call is scoped to one book) for "this chain vanished from the vendor".
    Chain-history (`prev_snapshot_ref`) uses the SAME ChainIndex as every
    other poll path, so a per-book row correctly links into the same
    continuous price history as bundled-poll rows for that
    (game, book, market, outcome).

    Returns (n_written_total, n_rejected_total, n_calls_made).
    """
    import time
    game_id = game["game_id"]
    n_written_total = n_rejected_total = n_calls_made = 0
    for i, book in enumerate(PER_BOOK_DECLARED_BOOKS):
        if i > 0:
            time.sleep(1.0)  # polite-client spacing between separate HTTP calls
        entry = {"poll_ts": datetime.now(timezone.utc).isoformat(), "game_id": game_id,
                 "obligation_type": "per_book", "label": f"PER_BOOK:{book}",
                 "endpoint": writer.EVENT_ODDS_URL.format(event_id=event_id) + f"?bookmakers={book}",
                 "n_rows_written": 0, "n_rows_rejected": 0}
        try:
            ev_json, raw, resp, timing = writer.fetch_event_props_snapshot(
                session, key, event_id, bookmakers=book)
            n_calls_made += 1
            retrieval_ts = timing["response_received_ts"]
            entry["poll_ts"] = retrieval_ts
            entry["http_status"] = resp.status_code
            entry["credits_used"] = resp.headers.get("x-requests-used")
            entry["credits_remaining"] = resp.headers.get("x-requests-remaining")
            entry["credits_last"] = resp.headers.get("x-requests-last")
            a_payload_hash = writer.payload_hash(raw)
            rows = writer.flatten_props_payload(
                ev_json, retrieval_ts,
                poll_interval_seconds=int(PER_BOOK_POLL_INTERVAL_SECONDS),
                a_payload_hash=a_payload_hash)

            ingestion_ts = datetime.now(timezone.utc).isoformat()
            vanish_rows = []
            if ev_json is not None:
                roster = writer.RosterIndex(out_dir / writer.ROSTER_INDEX_JSON)
                vanish_rows = writer.detect_vanished_chains(
                    rows, roster, roster_key=f"{game_id}:props:perbook:{book}",
                    game_id=game_id, retrieval_ts=retrieval_ts, ingestion_ts=ingestion_ts,
                    poll_interval_seconds=int(PER_BOOK_POLL_INTERVAL_SECONDS),
                    a_payload_hash=a_payload_hash)
                roster.save()
            rows = rows + vanish_rows

            chain = writer.ChainIndex(out_dir / writer.CHAIN_INDEX_JSON)
            writer.attach_chain_fields(rows, chain, retrieval_ts)
            n_written, rejected = writer.append_snapshot_rows(rows, out_dir)
            chain.save()
            entry["n_rows_written"], entry["n_rows_rejected"] = n_written, len(rejected)
            entry["n_rows_vanished_witnessed"] = len(vanish_rows)
            entry["error"] = None
            n_written_total += n_written
            n_rejected_total += len(rejected)
            writer.append_vendor_timing_log({**timing, "poll_ts": retrieval_ts,
                                             "game_id": game_id,
                                             "endpoint": entry["endpoint"]}, out_dir)
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            print(f"WARNING: per-book poll failed for {game_id} book={book}: "
                  f"{entry['error']}", file=sys.stderr)
        writer.append_poll_log(entry, out_dir)
    return n_written_total, n_rejected_total, n_calls_made


if __name__ == "__main__":
    raise SystemExit(main())
