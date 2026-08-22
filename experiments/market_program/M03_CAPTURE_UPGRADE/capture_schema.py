# -*- coding: utf-8 -*-
"""M03 -- the additive capture schema and a reference implementation of it.

Acceptance criterion 3: every captured quote must carry a capture first-seen
timestamp, a source fetch timestamp and a vendor-latency bound field, and these
are mandatory AT THE SCHEMA LEVEL rather than annotations added later.

WHY THIS IS NEEDED, measured rather than asserted (M36 s02). The props capture
takes one `snapshot_utc` at the top of main(), BEFORE the events list is fetched
and before any event request is issued, and writes it identically to every row of
the cycle. So `snapshot_utc <= true retrieval time`, and for a point-in-time
cutoff question that runs in the OPTIMISTIC direction: it can admit a quote whose
true retrieval fell after the cutoff. The odds capture has the same shape. The
INJURY capture already does it correctly, carrying attempted_ts_utc alongside
retrieval_ts_utc -- so the pattern to adopt already exists in this repository and
does not need inventing.

Measured exposure of the defect today is ZERO (M36 s02: 0 of 10,285 quotes
wrongly admitted at T-90m) because the cadence is too coarse to put anything near
the boundary. That is exactly why it should be fixed NOW rather than after the
cadence is tightened -- criterion 2 of this node proposes tightening it, which is
the change that would make the defect bite.

THE FIELDS.

    fetch_requested_utc   stamped immediately BEFORE the HTTP request
    fetch_returned_utc    stamped immediately AFTER the response is received
    vendor_reported_utc   the vendor's own timestamp for the quote (last_update)
    vendor_latency_bound_s   fetch_returned_utc - vendor_reported_utc
    first_seen_utc        the earliest fetch_returned_utc at which this exact
                          (key, payload) was observed; NEVER revised downward

`fetch_requested_utc` and `fetch_returned_utc` BRACKET the true retrieval instant,
which is what makes a cutoff decision fail-closed: use `fetch_returned_utc` and a
quote is admitted only if it was demonstrably in hand by then.

ADDITIVE AND REVERSIBLE (criterion 7). The existing `snapshot_utc` and
`last_update` columns are RETAINED unchanged, so every current consumer keeps
working and the change can be reverted by ignoring the new columns. Nothing here
modifies a running capture script; this module is the specification plus a
reference implementation that the capture would import.

NO BACKDATING (criterion 4). `first_seen_utc` is monotone per key: re-observing an
unchanged payload leaves it alone; a CHANGED payload is a new record with its own
first_seen, never an edit of the old one.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

#: Columns the current captures already write. Never removed, never redefined.
LEGACY_COLUMNS = ("snapshot_utc", "last_update")

#: The D023 amendment-4 mandatory fields, in schema order.
REQUIRED_TIMING_FIELDS = (
    "fetch_requested_utc",
    "fetch_returned_utc",
    "vendor_reported_utc",
    "vendor_latency_bound_s",
    "first_seen_utc",
)

STAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def stamp(t):
    return t.strftime(STAMP_FMT)


def parse(s):
    return dt.datetime.strptime(s, STAMP_FMT).replace(tzinfo=dt.timezone.utc)


def payload_digest(payload) -> str:
    """Stable digest of a quote's economically meaningful content.

    Timing fields are excluded deliberately: re-observing the SAME price at a
    later time must not count as a change, or every capture cycle would append a
    spurious record and `first_seen_utc` would lose its meaning.
    """
    body = {k: payload[k] for k in sorted(payload)
            if k not in set(REQUIRED_TIMING_FIELDS) | set(LEGACY_COLUMNS)}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class FetchWindow:
    """Brackets one HTTP call so the true retrieval instant is bounded.

    Usage mirrors how the capture would adopt it, one request at a time rather
    than one stamp per cycle:

        with FetchWindow() as w:
            resp = requests.get(url, ...)
        row.update(w.fields(vendor_reported_utc=mk["last_update"]))
    """

    def __init__(self):
        self.requested = None
        self.returned = None

    def __enter__(self):
        self.requested = utcnow()
        return self

    def __exit__(self, *exc):
        self.returned = utcnow()
        return False

    def fields(self, vendor_reported_utc=None):
        if self.requested is None or self.returned is None:
            raise RuntimeError("FetchWindow used outside its context manager")
        out = {
            "fetch_requested_utc": stamp(self.requested),
            "fetch_returned_utc": stamp(self.returned),
            "vendor_reported_utc": vendor_reported_utc or "",
            "vendor_latency_bound_s": "",
        }
        if vendor_reported_utc:
            try:
                v = dt.datetime.fromisoformat(
                    str(vendor_reported_utc).replace("Z", "+00:00"))
                if v.tzinfo is None:
                    v = v.replace(tzinfo=dt.timezone.utc)
                out["vendor_latency_bound_s"] = round(
                    (self.returned - v).total_seconds(), 3)
            except (ValueError, TypeError):
                out["vendor_latency_bound_s"] = ""
        return out


def apply_first_seen(row, known):
    """Set `first_seen_utc`, never moving it backwards.

    `known` maps (record key, payload digest) -> first_seen stamp and is updated
    in place. An unchanged payload keeps its original first_seen no matter how
    many times it is re-observed; a changed payload gets a NEW key and therefore
    a new first_seen, leaving the previous record untouched.
    """
    key = (row.get("record_key", ""), payload_digest(row))
    if key in known:
        row["first_seen_utc"] = known[key]
    else:
        known[key] = row["fetch_returned_utc"]
        row["first_seen_utc"] = row["fetch_returned_utc"]
    return row


def schema_for(existing_columns):
    """The upgraded column list: every existing column, then the new ones.

    Additive by construction -- existing columns keep their positions so a naive
    positional reader is unaffected, and the check is mechanical rather than a
    promise in prose.
    """
    cols = list(existing_columns)
    for f in REQUIRED_TIMING_FIELDS:
        if f not in cols:
            cols.append(f)
    return cols
