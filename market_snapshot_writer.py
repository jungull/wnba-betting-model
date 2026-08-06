#!/usr/bin/env python3
"""
Append-only market-snapshot writer + poll log (design sections (c)/(d)).

Two layers, deliberately separated so the row-building logic is testable
without a network:
  * `flatten_odds_payload` / `flatten_props_payload` -- pure functions,
    vendor JSON (already fetched) -> list of contract-6.3 rows. No I/O.
  * `fetch_odds_snapshot` / `fetch_event_props_snapshot` -- the only
    functions in this module that call `requests`. Thin wrappers so tests
    can monkeypatch a fake session/response instead of hitting the network.

CREDENTIAL RULE: `api_key()` is imported, unmodified, from
odds_capture_daily.py (same .env / ODDS_API_KEY loading this repo's other
capture scripts already use) -- not reimplemented here. The key is never
logged, printed, written to a row, or included in any error message this
module raises (see `_scrub` below, applied to every exception message that
could contain a urllib/requests-formatted URL with the key querystring).

APPEND-ONLY: `append_snapshot_rows` and `append_poll_log` both open their
target file in "a" mode only (or create it with a header on first write).
Neither ever seeks, truncates, or rewrites an existing line.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from market_snapshot_schema import (
    COLUMNS, ChainKey, SchemaViolation, VENDOR_TS_SEMANTICS_DEFAULT,
    implied_prob, novig_prob_pair, payload_hash, snapshot_id, validate_row,
)

ODDS_URL = "https://api.the-odds-api.com/v4/sports/basketball_wnba/odds"
EVENT_ODDS_URL = ("https://api.the-odds-api.com/v4/sports/basketball_wnba/"
                   "events/{event_id}/odds")
GAME_MARKETS = "spreads,totals,h2h"
PROP_MARKETS = ["player_points", "player_rebounds", "player_assists",
                "player_threes"]

DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "market_snapshots"
SNAPSHOTS_CSV = "snapshots.csv"
POLL_LOG_CSV = "poll_log.csv"
CHAIN_INDEX_JSON = "_chain_index.json"

POLL_LOG_COLUMNS = [
    "poll_ts", "game_id", "obligation_type", "label", "endpoint",
    "http_status", "credits_used", "credits_remaining", "credits_last",
    "n_rows_written", "n_rows_rejected", "error",
]


def _scrub(msg: str, key: Optional[str]) -> str:
    """Remove a credential value from a string before it can be logged,
    printed, or returned. Defensive even though requests params (not URL
    string interpolation) are used everywhere in this module, because
    requests.RequestException messages sometimes embed the full prepared
    URL including the querystring."""
    if not key:
        return msg
    return msg.replace(key, "***REDACTED***")


# ------------------------------------------------------------- fetch ------
def fetch_odds_snapshot(session, key: str, timeout=30):
    """One slate-wide live-odds call. Returns (games_json, raw_bytes,
    response). Raises with the key scrubbed from any error text."""
    try:
        r = session.get(ODDS_URL, params={"apiKey": key, "regions": "us",
                                          "markets": GAME_MARKETS,
                                          "oddsFormat": "american"},
                        timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(_scrub(f"{type(e).__name__}: {e}", key)) from None
    return r.json(), r.content, r


def fetch_event_props_snapshot(session, key: str, event_id: str,
                                markets=None, timeout=30):
    """One per-event props call, scoped to a single event_id (used both by
    the regular props ladder rung, over all in-window events, and by a
    burst leg, scoped to the one triggering game's event)."""
    markets = markets or PROP_MARKETS
    url = EVENT_ODDS_URL.format(event_id=event_id)
    try:
        r = session.get(url, params={"apiKey": key, "regions": "us",
                                     "markets": ",".join(markets),
                                     "oddsFormat": "american"},
                        timeout=timeout)
        if r.status_code == 422:
            return None, r.content, r
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(_scrub(f"{type(e).__name__}: {e}", key)) from None
    return r.json(), r.content, r


# --------------------------------------------------------- row-building ---
def _base_fields(retrieval_ts: str, ingestion_ts: str, poll_interval_seconds,
                  a_payload_hash: str, latency_note: Optional[str]) -> dict:
    """Amendment-4 fields shared by every row from one poll event.
    vendor_ts_semantics is ALWAYS unknown_unverified here -- resolving it
    requires the vendor's own documentation/support channel confirmation
    (design open item #2), which is out of scope for this writer. A future
    writer that has obtained that confirmation would set it explicitly; this
    one must not guess."""
    return {
        "vendor_ts_semantics": VENDOR_TS_SEMANTICS_DEFAULT,
        "retrieval_ts": retrieval_ts,
        "ingestion_ts": ingestion_ts,
        "max_staleness_bound": poll_interval_seconds,
        "poll_interval_at_capture": poll_interval_seconds,
        "vendor_latency_note": latency_note,
        "payload_hash": a_payload_hash,
    }


def flatten_odds_payload(games_json: list, retrieval_ts: str,
                          poll_interval_seconds, a_payload_hash: str,
                          latency_note: Optional[str] = None) -> list:
    """games_json: the /v4/.../odds response (list of game objects). One row
    per (book, market, outcome). Two-way game markets use `price`."""
    ingestion_ts = datetime.now(timezone.utc).isoformat()
    base = _base_fields(retrieval_ts, ingestion_ts, poll_interval_seconds,
                        a_payload_hash, latency_note)
    rows = []
    for g in games_json:
        game_id = g.get("id") or g.get("game_id")
        for b in g.get("bookmakers", []):
            for mk in b.get("markets", []):
                outcomes = mk.get("outcomes", [])
                for o in outcomes:
                    price = o.get("price")
                    rows.append({
                        **base,
                        "game_id": str(game_id),
                        "book": b.get("key"),
                        "market": mk.get("key"),
                        "outcome": o.get("name"),
                        "line": o.get("point"),
                        "price": price,
                        "price_over": None,
                        "price_under": None,
                        "implied_prob": implied_prob(price),
                        "novig_prob": None,   # computed in a second pass below
                        "market_status": "active" if outcomes else "missing",
                        "vendor_ts": mk.get("last_update"),
                    })
    _fill_novig_two_way(rows)
    return rows


def _fill_novig_two_way(rows: list) -> None:
    """For two-way game markets (h2h/spreads/totals), pair opposing outcomes
    within the same (game_id, book, market, line) and compute novig_prob for
    both sides, in place. Never interpolates across snapshots -- operates
    only within the rows of a single flatten_* call (one poll)."""
    groups: dict = {}
    for r in rows:
        if r["price"] in (None, ""):
            continue
        k = (r["game_id"], r["book"], r["market"], r["line"])
        groups.setdefault(k, []).append(r)
    for k, grp in groups.items():
        if len(grp) == 2:
            a, b = grp
            pa, pb = novig_prob_pair(a["price"], b["price"])
            a["novig_prob"], b["novig_prob"] = pa, pb


def flatten_props_payload(event_json: dict, retrieval_ts: str,
                           poll_interval_seconds, a_payload_hash: str,
                           latency_note: Optional[str] = None) -> list:
    """event_json: one /events/{id}/odds response. Rows use
    price_over/price_under, matching props_capture_daily.py's existing
    over/under-pair row shape rather than forcing a single `price` column
    (per design (d), do not force both shapes into one column layout)."""
    if event_json is None:
        return []
    ingestion_ts = datetime.now(timezone.utc).isoformat()
    base = _base_fields(retrieval_ts, ingestion_ts, poll_interval_seconds,
                        a_payload_hash, latency_note)
    game_id = event_json.get("id")
    pairs: dict = {}
    for b in event_json.get("bookmakers", []):
        for mk in b.get("markets", []):
            for o in mk.get("outcomes", []):
                key = (game_id, b.get("key"), mk.get("key"),
                       o.get("description"), o.get("point"))
                row = pairs.setdefault(key, {
                    **base, "game_id": str(game_id), "book": b.get("key"),
                    "market": mk.get("key"), "outcome": o.get("description"),
                    "line": o.get("point"), "price": None,
                    "price_over": None, "price_under": None,
                    "implied_prob": None, "novig_prob": None,
                    "market_status": "active",
                    "vendor_ts": mk.get("last_update"),
                })
                if o.get("name") == "Over":
                    row["price_over"] = o.get("price")
                elif o.get("name") == "Under":
                    row["price_under"] = o.get("price")
    rows = list(pairs.values())
    for r in rows:
        pa, pb = novig_prob_pair(r["price_over"], r["price_under"])
        r["novig_prob"] = pa if pa is not None else r["novig_prob"]
        if r["price_over"] is not None and r["price_under"] is None:
            r["implied_prob"] = implied_prob(r["price_over"])
        elif r["price_under"] is not None and r["price_over"] is None:
            r["implied_prob"] = implied_prob(r["price_under"])
    if not rows:
        rows = [{
            **base, "game_id": str(game_id), "book": None, "market": None,
            "outcome": None, "line": None, "price": None, "price_over": None,
            "price_under": None, "implied_prob": None, "novig_prob": None,
            "market_status": "missing", "vendor_ts": None,
        }]
    return rows


# ---------------------------------------------------------- chain index ---
class ChainIndex:
    """Persisted map of ChainKey -> last-written snapshot_id, so
    prev_snapshot_ref can be set without rescanning the whole snapshots.csv
    on every poll. This is a performance cache, not the source of truth --
    capture_coverage_audit.py's silent-overwrite check re-derives the chain
    from snapshots.csv itself and would catch a corrupted/rebuilt index."""

    def __init__(self, path: Path):
        self.path = path
        self._data = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def prev_for(self, key: ChainKey) -> Optional[str]:
        return self._data.get("|".join(key.as_tuple()))

    def update(self, key: ChainKey, new_snapshot_id: str) -> None:
        self._data["|".join(key.as_tuple())] = new_snapshot_id

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=1), encoding="utf-8")


def attach_chain_fields(rows: list, chain: ChainIndex,
                        retrieval_ts: str) -> list:
    """Fill snapshot_id and prev_snapshot_ref on each row, in place, and
    advance the chain index. Must run AFTER all other fields are set (the
    snapshot_id basis includes the row's payload_hash)."""
    for r in rows:
        key = ChainKey(r["game_id"], r["book"] or "", r["market"] or "",
                       r["outcome"] or "")
        sid = snapshot_id(r["payload_hash"], key.as_tuple(), retrieval_ts)
        r["snapshot_id"] = sid
        r["prev_snapshot_ref"] = chain.prev_for(key)
        chain.update(key, sid)
    return rows


# --------------------------------------------------------------- writer ---
def _csv_header(path: Path):
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f), None)


def append_snapshot_rows(rows: list, out_dir: Path = DEFAULT_SNAPSHOT_DIR
                          ) -> tuple:
    """Validate every row against the contract-6.3 schema, then append the
    valid ones (append-only, header-on-first-write). Returns
    (n_written, rejected) where rejected is a list of (row, reason) for any
    row that failed validate_row -- these are NEVER written, and the caller
    (market_capture_run.py) surfaces them loudly rather than silently
    dropping them, per the node's stop-condition on unsupportable timing
    claims."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SNAPSHOTS_CSV
    hdr = _csv_header(path)
    valid, rejected = [], []
    for r in rows:
        try:
            validate_row(r)
            valid.append(r)
        except SchemaViolation as e:
            rejected.append((r, str(e)))
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if hdr is None:
            w.writeheader()
        for r in valid:
            w.writerow(r)
    return len(valid), rejected


def append_poll_log(entry: dict, out_dir: Path = DEFAULT_SNAPSHOT_DIR) -> None:
    """One row per poll ATTEMPT (success or failure) -- design section (c),
    "the poll log". Append-only, same discipline as snapshots.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / POLL_LOG_CSV
    hdr = _csv_header(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POLL_LOG_COLUMNS, extrasaction="ignore")
        if hdr is None:
            w.writeheader()
        w.writerow({c: entry.get(c) for c in POLL_LOG_COLUMNS})
