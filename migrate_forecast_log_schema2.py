#!/usr/bin/env python3
"""migrate_forecast_log_schema2.py — SCHEMA/2 migration tool. SHIPPED, NOT RUN.

Decision D-4 (PROJECT_UPDATE_2026-08-04, §7 item 1 and Appendix F), adopted
under D022: ``evalharness/forecast_log.py`` gains the additive OPTIONAL field
``alt_model_predictions`` and the writer schema moves ``evalharness/
forecast_log/1`` -> ``/2``. The amendment is explicit that **/1 records
stand**.

Why this "migration" rewrites nothing
-------------------------------------
The forecast log is an append-only, hash-chained, tamper-evident ledger
(``evalharness/forecast_log.py``). Rewriting any historical line — e.g. to
stamp ``schema: /2`` and ``alt_model_predictions: null`` onto old records —
would:

  * break every successor's ``prev_record_sha256`` (the chain is the point);
  * invalidate the externally anchored ``n_records`` / ``tip_sha256``;
  * violate the amendment's own "/1 records stand" clause and the ledger
    discipline ("nothing here ever rewrites, reorders, or deletes a line").

The correct migration for a hash-chained ledger is therefore READER
TOLERANCE, which ships in ``evalharness/forecast_log.py`` (``verify_chain``
and ``read_forecasts`` accept mixed /1 + /2 chains), plus this tool, which:

  1. verifies the chain end-to-end (``verify_chain``);
  2. produces a per-schema census (how many /1, how many /2, any unknown);
  3. confirms every record parses through the tolerant reader;
  4. optionally writes a census report — atomically (temp file +
     ``os.replace``) and NEVER to the log itself.

Idempotent by construction: the log is opened read-only; running the tool
twice produces byte-identical censuses for an unchanged log.

Exit codes: 0 = chain verifies and every record is a known schema;
            1 = verification failed or an unknown schema is present.

Usage (against a fixture or a copy — per the standing live-data rule this
tool is shipped with the D-4 bundle but is NOT to be run against the live
``forecasts/forecast_log.jsonl`` until the coordinator directs it):

  python migrate_forecast_log_schema2.py --log path/to/forecast_log.jsonl
  python migrate_forecast_log_schema2.py --log chain.jsonl --report out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from evalharness.forecast_log import (  # noqa: E402
    DEFAULT_FORECAST_LOG,
    KNOWN_SCHEMAS,
    SCHEMA_V1,
    SCHEMA_V2,
    read_forecasts,
    verify_chain,
)


def census(log_path: Path) -> dict:
    """Read-only census of a forecast-log chain. Never writes the log."""
    report = verify_chain(log_path)
    counts: Counter = Counter()
    unknown: list = []
    n_v2_null_alt = n_v2_with_alt = 0
    if report.n_records:
        for rec in read_forecasts(log_path):
            schema = rec.get("schema")
            counts[str(schema)] += 1
            if schema not in KNOWN_SCHEMAS:
                unknown.append({"record_idx": rec.get("record_idx"),
                                "schema": schema})
            elif schema == SCHEMA_V2:
                if rec.get("alt_model_predictions") is None:
                    n_v2_null_alt += 1
                else:
                    n_v2_with_alt += 1
    ok = report.ok and not unknown
    return {
        "tool": "migrate_forecast_log_schema2",
        "migration_semantics": (
            "additive only: /1 records stand (D-4); reader tolerance is the "
            "migration; no line of the ledger is ever rewritten"
        ),
        "log_path": str(log_path),
        "chain_ok": report.ok,
        "chain_first_bad_index": report.first_bad_index,
        "chain_reason": report.reason,
        "n_records": report.n_records,
        "tip_sha256": report.tip_sha256,
        "schema_counts": dict(counts),
        "n_schema_v1": counts.get(SCHEMA_V1, 0),
        "n_schema_v2": counts.get(SCHEMA_V2, 0),
        "n_v2_alt_model_predictions_null": n_v2_null_alt,
        "n_v2_alt_model_predictions_present": n_v2_with_alt,
        "unknown_schema_records": unknown,
        "ok": ok,
    }


def write_report_atomic(report: dict, out_path: Path) -> None:
    """Atomic report write: temp file in the destination directory, fsync,
    then os.replace. The log itself is never opened for writing."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True)
    fd, tmp = tempfile.mkstemp(dir=str(out_path.parent),
                               prefix=out_path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--log", default=str(DEFAULT_FORECAST_LOG),
                    help="forecast-log chain to census (default: the official "
                         "log path — but per the live-data rule, do not run "
                         "this against live data until directed)")
    ap.add_argument("--report", default=None,
                    help="optional path for the JSON census report "
                         "(written atomically; the log is never written)")
    args = ap.parse_args()

    rep = census(Path(args.log))
    print(json.dumps(rep, indent=2, sort_keys=True))
    if args.report:
        write_report_atomic(rep, Path(args.report))
        print(f"report written atomically to {args.report}", file=sys.stderr)
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
