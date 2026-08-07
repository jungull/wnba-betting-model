#!/usr/bin/env python3
"""
D032/D033 primary injury track -- live capture module.

Owns one 15-minute capture cycle end to end: discover -> fetch -> archive
raw -> parse -> hash-dedup -> entity-resolve -> supersession-detect ->
append. NOT scheduled by this module (D033 mandate: "NOT scheduled --
coordinator schedules"); invoke `python capture_injury_live.py` once per
cycle, or `--backfill-today` to pull every not-yet-captured link the
discovery JSON currently lists for the ET calendar day.

Three timestamp classes, kept distinct on every snapshot row (D034):
  1. provider publication ts  -- the PDF's own embedded header line
     ("Injury Report: MM/DD/YY HH:MM AM/PM"), publisher-asserted (T1).
  2. document ts               -- the URL/label slot this document was
     published under (e.g. "3:15 p.m. ET report" -> 2026-08-06T15:15 ET),
     plus the HTTP Last-Modified header when the fetch returns one. This is
     the document's OWN identity, not necessarily identical to (1): a
     report can be filed a few minutes into or before its nominal slot.
  3. our capture ts            -- retrieval_ts_utc (when our GET was made)
     and ingestion_ts_utc (when this row was written), witnessed by us,
     T0 tier.
These are never collapsed into one "timestamp" column and never silently
promoted to a sharper tier than they are.

Absent-row-is-not-healthy, enforced structurally: this module never writes
a synthetic "Available" row for a player who is not printed in the report.
injury_snapshots.csv contains exactly the rows the PDF prints (Out /
Doubtful / Questionable / Probable / Available / Rest / Health and Safety
Protocols / Suspension), nothing cross-joined against a full roster. A
team-game the report marks "NOT YET SUBMITTED" is written to
report_coverage.csv as an explicit NOT_YET_SUBMITTED row -- so "we have no
row for this player" and "the team hasn't filed yet" are never
indistinguishable from "healthy": a consumer must join against
report_coverage.csv before treating any absence as informative at all.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parser import parse_official_pdf  # noqa: E402
from entity_resolution_bridge import try_load_index, resolve  # noqa: E402
from fetch_official_report import (  # noqa: E402
    fetch_discovery_json, fetch_pdf, BotBlockDetected, NetworkUnavailable,
)

import os as _os
# Data-store root. Default: this module's own directory (original behavior,
# used for the 2026-08-07 D048 recovery snapshot committed alongside the
# code). The scheduled tick sets INJURY_LIVE_DATA_ROOT to a directory in
# the DATA worktree so continuous 15-minute appends never dirty the program
# worktree (quiescent-tree push rule, D018/D044). Code stays here; only the
# CSV/raw store moves.
ROOT = Path(_os.environ.get("INJURY_LIVE_DATA_ROOT") or Path(__file__).resolve().parent)
ROOT.mkdir(parents=True, exist_ok=True)
RAWDIR = ROOT / "raw"
CAPTURE_LOG_CSV = ROOT / "capture_log.csv"
SNAPSHOTS_CSV = ROOT / "injury_snapshots.csv"
TRANSITIONS_CSV = ROOT / "status_transitions.csv"
COVERAGE_CSV = ROOT / "report_coverage.csv"
REJECTS_CSV = ROOT / "rejects.csv"

ET = ZoneInfo("America/New_York")

CAPTURE_LOG_HEADER = [
    "capture_id", "attempted_ts_utc", "source_url", "http_status",
    "outcome",  # NOVEL | DUPLICATE_OF_PRIOR | BOT_BLOCK | NETWORK_UNAVAILABLE
                # (+ _BROWSER_CLIENT suffix when the D048 real-Chromium
                #  fallback obtained the body; see fetch_browser.py)
    "payload_hash_sha256", "dedup_of_capture_id", "raw_path",
    "retrieval_ts_utc",
]
SNAPSHOT_HEADER = [
    "capture_id", "cycle_id",
    "url_slot_label", "url_slot_ts_et", "url_slot_ts_utc",
    "doc_last_modified_utc",
    "provider_publication_ts_raw", "provider_publication_ts_et",
    "retrieval_ts_utc", "ingestion_ts_utc",
    "poll_interval_at_capture", "max_staleness_bound_minutes",
    "vendor_latency_note",
    "source_url", "source_provenance_class",
    "payload_hash_sha256", "prev_snapshot_capture_id",
    "game_date", "game_time_et", "matchup", "team_raw", "team",
    "player_raw", "player_id", "status", "reason",
]
TRANSITION_HEADER = [
    "transition_id", "team_raw", "team", "player_raw", "player_id",
    "status_before", "status_after", "reason_after",
    "t_lower_utc_bound", "t_upper_utc_bound",
    "poll_interval_event", "censor_type", "tier",
    "prev_capture_id", "curr_capture_id",
]
COVERAGE_HEADER = [
    "capture_id", "cycle_id", "game_date", "game_time_et", "matchup",
    "team_raw", "coverage_status",  # NOT_YET_SUBMITTED (only value so far)
    "retrieval_ts_utc",
]
REJECTS_HEADER = [
    "capture_id", "cycle_id", "page", "kind", "reason", "raw_text",
    "retrieval_ts_utc",
]

POLL_INTERVAL_AT_CAPTURE = "PT15M"          # the report's own publish grid
MAX_STALENESS_BOUND_MINUTES = 15            # never sharper than the grid
VENDOR_LATENCY_NOTE = (
    "wnba.com/api/injury-reports discovery JSON and the ak-static.cms."
    "nba.com PDF CDN carry no documented vendor-latency SLA; "
    "poll_interval_at_capture=PT15M is the observed publish grid "
    "(confirmed by three consecutive real quarter-hour documents with "
    "Last-Modified values exactly 15 minutes apart), not a vendor-stated "
    "bound -- treat as UNBOUNDED for anything sharper than the 15-minute "
    "grid itself."
)
SOURCE_PROVENANCE_CLASS = (
    "T0 directly-witnessed capture of the official league quarter-hour "
    "injury report (D033 source-hierarchy rank 1); provider_publication_ts "
    "is T1 (publisher-asserted, unwitnessed by us); url_slot_ts is the "
    "document's own nominal slot identity, not a witnessed instant."
)


def _ensure_headers():
    RAWDIR.mkdir(parents=True, exist_ok=True)
    for path, header in (
        (CAPTURE_LOG_CSV, CAPTURE_LOG_HEADER),
        (SNAPSHOTS_CSV, SNAPSHOT_HEADER),
        (TRANSITIONS_CSV, TRANSITION_HEADER),
        (COVERAGE_CSV, COVERAGE_HEADER),
        (REJECTS_CSV, REJECTS_HEADER),
    ):
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(header)


def _append_rows(path, header, rows):
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        for r in rows:
            w.writerow(r)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_label_to_et(label, date_label_this_year_et_date):
    """'3:15 p.m. ET report' + a known ET calendar date -> ET datetime, or
    None if the label doesn't match the expected shape (never guessed)."""
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.)", label.strip(),
                 re.IGNORECASE)
    if not m or date_label_this_year_et_date is None:
        return None
    hour, minute, ampm = m.groups()
    hour = int(hour) % 12
    if ampm.lower() == "p.m.":
        hour += 12
    d = date_label_this_year_et_date
    return datetime(d.year, d.month, d.day, hour, int(minute),
                     tzinfo=ET)


def _load_prior_index():
    """capture_log.csv -> {payload_hash: capture_id of first occurrence},
    for hash-dedup across restarts (append-only discipline: we never
    forget a hash just because the process restarted)."""
    seen = {}
    if not CAPTURE_LOG_CSV.exists():
        return seen
    with CAPTURE_LOG_CSV.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            h = row.get("payload_hash_sha256")
            if h and h not in seen:
                seen[h] = row["capture_id"]
    return seen


def _load_last_snapshot_status():
    """injury_snapshots.csv -> {(team_raw, player_raw): (status, capture_id)}
    for the MOST RECENT distinct (post-dedup) snapshot, for supersession
    detection against the new cycle."""
    latest = {}
    if not SNAPSHOTS_CSV.exists():
        return latest
    with SNAPSHOTS_CSV.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["team_raw"], row["player_raw"])
            latest[key] = (row["status"], row["capture_id"],
                           row["retrieval_ts_utc"])
    return latest


def run_one_cycle(pdf_url, url_slot_label=None, capture_id=None):
    """Fetch, archive, parse and append exactly one report document.
    Raises BotBlockDetected / NetworkUnavailable to the caller -- this
    function never swallows either, per standing rules (report, don't
    bypass)."""
    _ensure_headers()
    capture_id = capture_id or f"cap_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}"
    cycle_id = f"cycle_{datetime.now(timezone.utc):%Y%m%d}"

    log_row = {
        "capture_id": capture_id, "attempted_ts_utc": _now_utc_iso(),
        "source_url": pdf_url, "http_status": "", "outcome": "",
        "payload_hash_sha256": "", "dedup_of_capture_id": "",
        "raw_path": "", "retrieval_ts_utc": "",
    }

    try:
        result = fetch_pdf(pdf_url)
    except BotBlockDetected as e:
        log_row.update(outcome="BOT_BLOCK", http_status=str(e.status_code))
        _append_rows(CAPTURE_LOG_CSV, CAPTURE_LOG_HEADER, [log_row])
        raise
    except NetworkUnavailable as e:
        log_row.update(outcome="NETWORK_UNAVAILABLE")
        _append_rows(CAPTURE_LOG_CSV, CAPTURE_LOG_HEADER, [log_row])
        raise

    retrieval_ts = result.retrieval_ts_utc
    payload_hash = _sha256(result.body)
    log_row.update(http_status=str(result.status_code),
                    payload_hash_sha256=payload_hash,
                    retrieval_ts_utc=retrieval_ts)

    prior_hashes = _load_prior_index()
    is_novel = payload_hash not in prior_hashes
    # D048: the browser-client fallback is surfaced in the outcome itself so
    # provenance never conflates the two fetch paths (client field on the
    # FetchResult; "urllib" is the honest script client this log has always
    # recorded, status 0 rows are browser downloads with no status line).
    _client_suffix = "" if getattr(result, "client", "urllib") == "urllib" else "_BROWSER_CLIENT"
    log_row["outcome"] = ("NOVEL" if is_novel else "DUPLICATE_OF_PRIOR") + _client_suffix
    log_row["dedup_of_capture_id"] = "" if is_novel else prior_hashes[payload_hash]

    raw_path = RAWDIR / f"{capture_id}.pdf"
    raw_path.write_bytes(result.body)  # archive raw verbatim, ALWAYS
    log_row["raw_path"] = str(raw_path.relative_to(ROOT))
    _append_rows(CAPTURE_LOG_CSV, CAPTURE_LOG_HEADER, [log_row])

    if not is_novel:
        # Report unchanged since the last distinct capture: proof-of-polling
        # is already recorded in capture_log.csv; no new snapshot rows
        # (append-only discipline means we never write a duplicate content
        # row, but we DO prove we checked).
        return {"capture_id": capture_id, "outcome": "DUPLICATE_OF_PRIOR",
                "snapshot_rows": 0, "transitions": 0, "rejects": 0}

    rows, meta, rejects = parse_official_pdf(result.body)

    idx, idx_note = try_load_index()
    last_status = _load_last_snapshot_status()

    doc_last_modified = result.headers.get("Last-Modified", "")
    provider_pub_raw = meta.get("report_publication_ts_raw") or ""
    provider_pub_et = meta.get("report_publication_ts_et") or ""

    snapshot_rows = []
    transition_rows = []
    for r in rows:
        team_raw = r["team_raw"]
        player_raw = r["player_raw"]
        pid = resolve(player_raw, idx)
        snap = {
            "capture_id": capture_id, "cycle_id": cycle_id,
            "url_slot_label": url_slot_label or "",
            "url_slot_ts_et": "", "url_slot_ts_utc": "",
            "doc_last_modified_utc": doc_last_modified,
            "provider_publication_ts_raw": provider_pub_raw,
            "provider_publication_ts_et": provider_pub_et,
            "retrieval_ts_utc": retrieval_ts,
            "ingestion_ts_utc": _now_utc_iso(),
            "poll_interval_at_capture": POLL_INTERVAL_AT_CAPTURE,
            "max_staleness_bound_minutes": MAX_STALENESS_BOUND_MINUTES,
            "vendor_latency_note": VENDOR_LATENCY_NOTE,
            "source_url": pdf_url,
            "source_provenance_class": SOURCE_PROVENANCE_CLASS,
            "payload_hash_sha256": payload_hash,
            "prev_snapshot_capture_id": "",
            "game_date": r["game_date"], "game_time_et": r["game_time_et"],
            "matchup": r["matchup"], "team_raw": team_raw,
            "team": team_raw,  # normalized in a later pass if/when a
                                # canonical team map is wired in; never
                                # guessed here
            "player_raw": player_raw,
            "player_id": pid if pid is not None else "",
            "status": r["status"], "reason": r["reason"],
        }
        snapshot_rows.append(snap)

        key = (team_raw, player_raw)
        prev = last_status.get(key)
        if prev is None or prev[0] != r["status"]:
            transition_rows.append({
                "transition_id": f"{capture_id}_{len(transition_rows)}",
                "team_raw": team_raw, "team": team_raw,
                "player_raw": player_raw, "player_id": pid if pid is not None else "",
                "status_before": prev[0] if prev else "",
                "status_after": r["status"], "reason_after": r["reason"],
                "t_lower_utc_bound": prev[2] if prev else "",
                "t_upper_utc_bound": retrieval_ts,
                "poll_interval_event": POLL_INTERVAL_AT_CAPTURE,
                "censor_type": "interval",
                "tier": "T0",
                "prev_capture_id": prev[1] if prev else "",
                "curr_capture_id": capture_id,
            })
        last_status[key] = (r["status"], capture_id, retrieval_ts)

    # Players who WERE in the last snapshot but are absent from this one:
    # never silently treated as healthy. Recorded as a transition to an
    # explicit "REMOVED_FROM_REPORT" state, distinct from "Available".
    current_keys = {(r["team_raw"], r["player_raw"]) for r in rows}
    for key, (prev_status, prev_capture_id, prev_ts) in list(
            last_status.items()):
        if key in current_keys:
            continue
        if prev_status == "REMOVED_FROM_REPORT":
            continue  # already recorded; don't re-fire every cycle
        team_raw, player_raw = key
        transition_rows.append({
            "transition_id": f"{capture_id}_rm_{len(transition_rows)}",
            "team_raw": team_raw, "team": team_raw,
            "player_raw": player_raw, "player_id": "",
            "status_before": prev_status,
            "status_after": "REMOVED_FROM_REPORT",
            "reason_after": (
                "absent from this report vs the immediately prior one -- "
                "this is NOT evidence of availability; it means only that "
                "no designation for this player was printed this cycle"
            ),
            "t_lower_utc_bound": prev_ts, "t_upper_utc_bound": retrieval_ts,
            "poll_interval_event": POLL_INTERVAL_AT_CAPTURE,
            "censor_type": "interval", "tier": "T0",
            "prev_capture_id": prev_capture_id, "curr_capture_id": capture_id,
        })
        last_status[key] = ("REMOVED_FROM_REPORT", capture_id, retrieval_ts)

    coverage_rows = [{
        "capture_id": capture_id, "cycle_id": cycle_id,
        "game_date": nys["game_date"], "game_time_et": nys["game_time_et"],
        "matchup": nys["matchup"], "team_raw": nys["team_raw"],
        "coverage_status": "NOT_YET_SUBMITTED",
        "retrieval_ts_utc": retrieval_ts,
    } for nys in meta.get("not_yet_submitted", [])]

    reject_rows = [{
        "capture_id": capture_id, "cycle_id": cycle_id,
        "page": rj.get("page", ""), "kind": rj.get("kind", ""),
        "reason": rj.get("reason", ""), "raw_text": rj.get("raw", ""),
        "retrieval_ts_utc": retrieval_ts,
    } for rj in rejects]

    _append_rows(SNAPSHOTS_CSV, SNAPSHOT_HEADER, snapshot_rows)
    _append_rows(TRANSITIONS_CSV, TRANSITION_HEADER, transition_rows)
    _append_rows(COVERAGE_CSV, COVERAGE_HEADER, coverage_rows)
    _append_rows(REJECTS_CSV, REJECTS_HEADER, reject_rows)

    return {
        "capture_id": capture_id, "outcome": "NOVEL",
        "snapshot_rows": len(snapshot_rows),
        "transitions": len(transition_rows),
        "coverage_rows": len(coverage_rows),
        "rejects": len(reject_rows),
        "entity_resolution_note": idx_note,
    }


def run_latest_cycle():
    """Discover today's links, fetch only the newest one not already in
    capture_log.csv by source_url. This is the normal 15-minute-cadence
    invocation."""
    _ensure_headers()
    try:
        disc_result, disc = fetch_discovery_json()
    except (BotBlockDetected, NetworkUnavailable) as e:
        print(f"DISCOVERY FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        raise

    already = set()
    if CAPTURE_LOG_CSV.exists():
        with CAPTURE_LOG_CSV.open("r", newline="", encoding="utf-8") as f:
            already = {row["source_url"] for row in csv.DictReader(f)}

    new_links = [l for l in disc["links"] if l["href"] not in already]
    if not new_links:
        print("No new report links since last capture_log.csv entry.")
        return []
    results = []
    for link in new_links:
        try:
            res = run_one_cycle(link["href"], url_slot_label=link["label"])
            res["source_url"] = link["href"]
            results.append(res)
            print(json.dumps(res))
        except (BotBlockDetected, NetworkUnavailable) as e:
            print(f"CYCLE FAILED for {link['href']}: "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
            # A network condition on one link does not abort the whole
            # run: later links (if any) still get a chance, and this one
            # is already logged NETWORK_UNAVAILABLE/BOT_BLOCK in
            # capture_log.csv by run_one_cycle before it raised.
            if isinstance(e, BotBlockDetected):
                raise  # a real bot-block signature: stop entirely
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backfill-today", action="store_true",
                     help="fetch every not-yet-captured link the "
                          "discovery JSON lists for today")
    args = ap.parse_args()
    try:
        out = run_latest_cycle()
        print(f"cycle complete: {len(out)} new document(s) processed")
    except BotBlockDetected as e:
        print(f"STOPPING -- bot-block-shaped response, not bypassed: {e}",
              file=sys.stderr)
        sys.exit(2)
    except NetworkUnavailable as e:
        print(f"cycle incomplete -- network unavailable, not a confirmed "
              f"block, will retry next scheduled cycle: {e}",
              file=sys.stderr)
        sys.exit(1)
