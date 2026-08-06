#!/usr/bin/env python3
"""
Append-only market-snapshot row schema (M03_CAPTURE_UPGRADE / D023 amendment 4).

One row per (snapshot poll event, book, market, outcome). This module owns the
column contract and the small pure functions (hashing, snapshot id, implied
probability, no-vig probability) that every writer path must go through so the
contract-6.3 mandatory fields are enforced at write time, not bolted on later
as annotations.

LIVE-DATA RULE (matches every existing capture script in this repo):
    this table is APPEND-ONLY. A correction is a new row with a new
    snapshot_id and prev_snapshot_ref pointing at what it corrects. Nothing in
    this module or in market_snapshot_writer.py opens the CSV in "w" mode or
    performs an UPDATE/rewrite of an existing row.

D023 amendment 4: every reaction-time / timing claim must carry its explicit
timestamp-uncertainty and vendor-latency terms. That is enforced here by
`REQUIRED_COLUMNS` (validate_row refuses to write a row missing any of them)
and by `vendor_ts_semantics` defaulting to the conservative
`unknown_unverified` value rather than silently assuming vendor `last_update`
means "when the book moved the line".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------- columns --
# Row-identity + market-content columns (design doc section (d)).
CONTENT_COLUMNS = [
    "snapshot_id",       # primary identity of this poll event for this row
    "game_id",            # official league game_id, else PROV-<date>-<away>@<home>
    "book",                # bookmaker key, verbatim from vendor
    "market",              # market key, verbatim from vendor
    "outcome",             # outcome name/description
    "line",                # point/line, nullable
    "price",               # American odds, two-way game markets (h2h/spreads/totals)
    "price_over",          # American odds, props over side
    "price_under",         # American odds, props under side
    "implied_prob",        # computed at write time from American odds, no vig removal
    "novig_prob",          # nullable; only when both sides present in the SAME snapshot
    "market_status",       # active / suspended / missing
]

# Amendment-4 timestamp-uncertainty fields. MANDATORY on every row per the
# M00 contract 6.3 schema mandate -- not optional, not added later.
TIMESTAMP_COLUMNS = [
    "vendor_ts",
    "vendor_ts_semantics",
    "retrieval_ts",
    "ingestion_ts",
    "max_staleness_bound",
    "poll_interval_at_capture",
    "vendor_latency_note",
]

# Chain-integrity fields.
CHAIN_COLUMNS = [
    "payload_hash",
    "prev_snapshot_ref",
]

COLUMNS = CONTENT_COLUMNS + TIMESTAMP_COLUMNS + CHAIN_COLUMNS

# Mandatory-at-write-time fields. `vendor_latency_note`, `line`, `novig_prob`,
# `prev_snapshot_ref`, `price`/`price_over`/`price_under` are legitimately
# nullable in specific rows (see NULLABLE_OK below) -- but the *column* must
# always be present with an explicit value (None/"" is fine, a MISSING KEY is
# not). REQUIRED_PRESENT is the amendment-4 mandate: these must never be
# null/blank -- a row that cannot populate them is not a capturable row.
REQUIRED_PRESENT = [
    "snapshot_id", "game_id", "book", "market", "outcome", "market_status",
    "vendor_ts_semantics", "retrieval_ts", "ingestion_ts",
    "max_staleness_bound", "poll_interval_at_capture", "payload_hash",
]

NULLABLE_OK = {
    "line", "price", "price_over", "price_under", "implied_prob",
    "novig_prob", "vendor_ts", "vendor_latency_note", "prev_snapshot_ref",
}

VENDOR_TS_SEMANTICS_DEFAULT = "unknown_unverified"
VENDOR_TS_SEMANTICS_VALUES = {
    "book_last_change", "vendor_ingest_time", "unknown_unverified",
}
MARKET_STATUS_VALUES = {"active", "suspended", "missing"}


class SchemaViolation(ValueError):
    """A row cannot be written because it fails the contract-6.3 mandate."""


def validate_row(row: dict) -> None:
    """Raise SchemaViolation if `row` cannot be written as a contract-6.3
    compliant snapshot row. Called by every writer path before append --
    this is the mechanism that makes the amendment-4 fields MANDATES rather
    than annotations: a row that cannot populate them does not get written,
    it gets refused (and the caller must surface that as an UNSUPPORTABLE
    claim per the node's stop conditions, never write it anyway)."""
    missing_cols = [c for c in COLUMNS if c not in row]
    if missing_cols:
        raise SchemaViolation(f"row missing column(s): {missing_cols}")
    for f in REQUIRED_PRESENT:
        v = row.get(f)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise SchemaViolation(f"required field '{f}' is null/blank")
    sem = row["vendor_ts_semantics"]
    if sem not in VENDOR_TS_SEMANTICS_VALUES:
        raise SchemaViolation(
            f"vendor_ts_semantics={sem!r} not in {VENDOR_TS_SEMANTICS_VALUES}")
    status = row["market_status"]
    if status not in MARKET_STATUS_VALUES:
        raise SchemaViolation(
            f"market_status={status!r} not in {MARKET_STATUS_VALUES}")
    has_price = row.get("price") not in (None, "")
    has_pair = (row.get("price_over") not in (None, "")
                or row.get("price_under") not in (None, ""))
    if not has_price and not has_pair and status == "active":
        raise SchemaViolation(
            "active row carries neither 'price' nor a price_over/price_under pair")


def payload_hash(raw_bytes: bytes) -> str:
    """sha256 of the raw response bytes this row's data came from. Used to
    detect silent overwrites (design section (e)): two rows that claim to
    come from different polls but hash identically indicate the vendor
    response was replayed/cached rather than freshly fetched, or that a
    writer bug re-derived the same payload twice."""
    return hashlib.sha256(raw_bytes).hexdigest()


def snapshot_id(a_payload_hash: str, key: tuple, retrieval_ts: str) -> str:
    """Deterministic-from-inputs id for one (poll event, book, market,
    outcome) row. Not the payload hash itself -- two different outcome rows
    from the SAME poll share a payload_hash but must have distinct
    snapshot_ids, and re-running validate/audit code must be able to
    recompute the same id from the row's own fields (no random uuid)."""
    key_str = "|".join(str(k) for k in key)
    basis = f"{a_payload_hash}|{key_str}|{retrieval_ts}".encode("utf-8")
    return hashlib.sha256(basis).hexdigest()[:24]


def implied_prob(american_price) -> Optional[float]:
    """American odds -> implied probability, no vig removal. None if the
    price is missing (e.g. a 'missing' market_status row)."""
    if american_price in (None, ""):
        return None
    p = float(american_price)
    if p > 0:
        return 100.0 / (p + 100.0)
    return -p / (-p + 100.0)


def novig_prob_pair(price_a, price_b) -> tuple:
    """Two-way no-vig probabilities for a pair of American-odds prices
    present in the SAME snapshot. Returns (prob_a, prob_b) or (None, None)
    if either side is missing -- per design (d), novig_prob is NEVER
    interpolated across snapshots, only computed when both sides of the
    same poll are present."""
    ia, ib = implied_prob(price_a), implied_prob(price_b)
    if ia is None or ib is None:
        return None, None
    total = ia + ib
    if total <= 0:
        return None, None
    return ia / total, ib / total


@dataclass(frozen=True)
class ChainKey:
    """The identity a snapshot row's history chains on: everything except
    the poll event itself. Two rows with the same ChainKey from different
    polls are the same market quote observed at different times."""
    game_id: str
    book: str
    market: str
    outcome: str

    def as_tuple(self) -> tuple:
        return (self.game_id, self.book, self.market, self.outcome)
