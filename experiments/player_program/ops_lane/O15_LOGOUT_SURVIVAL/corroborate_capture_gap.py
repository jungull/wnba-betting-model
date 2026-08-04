"""
O15_LOGOUT_SURVIVAL -- corroboration: does the artifact record agree with the
Task Scheduler log?

The scheduler log says 23 WNBA launches were suppressed on 2026-08-02 between
08:00 and 16:00 local. If that is true and not a logging artifact, the capture
outputs must carry a hole in exactly that window. This script checks, from the
artifacts rather than from the log.

READ-ONLY, and deliberately reads the LIVE capture tree at the repository root
(C:/Users/jgallagher/wnba-betting-model), not this program worktree: the
worktree is pinned to an older commit whose data/ stops on 2026-08-01, so it
cannot see the window at issue. The live tree is another worktree on another
branch with ~160 uncommitted files; it is read here purely as operational
evidence and nothing is written to it.

Writes EVIDENCE_capture_gap.json next to this script.

    python experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/corroborate_capture_gap.py
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
LIVE_ROOT = pathlib.Path("C:/Users/jgallagher/wnba-betting-model")

# Task Scheduler timestamps are local; capture filenames are UTC. This machine
# reported UTC-04:00 in its event records on 2026-08-02 (EDT).
UTC_OFFSET_HOURS = -4

STAMP = re.compile(r"^wnba_official_(\d{8}T\d{6})Z\.pdf$")


def parse_stamps(d: pathlib.Path) -> list[dt.datetime]:
    out = []
    for p in sorted(d.glob("wnba_official_*.pdf")):
        m = STAMP.match(p.name)
        if m:
            out.append(dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S"))
    return sorted(out)


def main() -> int:
    result: dict = {"live_root": str(LIVE_ROOT)}

    inj = LIVE_ROOT / "data" / "injury_capture" / "raw"
    if not inj.is_dir():
        print(f"MISSING: {inj}")
        return 1

    stamps = parse_stamps(inj)
    result["injury_pdf_count"] = len(stamps)
    result["injury_first_utc"] = stamps[0].isoformat() + "Z"
    result["injury_last_utc"] = stamps[-1].isoformat() + "Z"

    # largest gap anywhere in the captured series
    gaps = [(stamps[i + 1] - stamps[i], stamps[i], stamps[i + 1]) for i in range(len(stamps) - 1)]
    gaps.sort(key=lambda g: g[0], reverse=True)
    top = []
    for g, a, b in gaps[:5]:
        top.append(
            {
                "hours": round(g.total_seconds() / 3600.0, 3),
                "after_utc": a.isoformat() + "Z",
                "before_utc": b.isoformat() + "Z",
                "after_local": (a + dt.timedelta(hours=UTC_OFFSET_HOURS)).isoformat(),
                "before_local": (b + dt.timedelta(hours=UTC_OFFSET_HOURS)).isoformat(),
            }
        )
    result["largest_gaps"] = top

    # hourly slots the injury task should have produced on 2026-08-02 local,
    # per START_HERE.md:50 ("odds and injury capture hourly (10:00-23:00)")
    have_local = {(s + dt.timedelta(hours=UTC_OFFSET_HOURS)) for s in stamps}
    have_hours = {t.hour for t in have_local if t.date() == dt.date(2026, 8, 2)}
    expected = set(range(10, 24))
    result["aug02_local_hours_present"] = sorted(have_hours)
    result["aug02_local_hours_missing"] = sorted(expected - have_hours)
    result["aug02_n_missing_slots"] = len(expected - have_hours)

    # the prospective forecast chain on the same day
    log = LIVE_ROOT / "forecasts" / "forecast_log.jsonl"
    if log.exists():
        cutoffs: dict[str, int] = {}
        n = 0
        for line in log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            n += 1
            rec = json.loads(line)
            c = (rec.get("forecast_cutoff") or "")[:10]
            cutoffs[c] = cutoffs.get(c, 0) + 1
        result["forecast_log_records"] = n
        result["forecast_records_by_cutoff_date_utc"] = dict(sorted(cutoffs.items()))
        result["forecast_records_2026_08_02"] = cutoffs.get("2026-08-02", 0)
    else:
        result["forecast_log_records"] = None

    out = HERE / "EVIDENCE_capture_gap.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
