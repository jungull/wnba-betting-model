"""O13_LEAD_WINDOW_LATENCY -- tip-revision probe (READ ONLY).

The gate's own log line at 2026-08-03T22:45:06Z printed T-30m cutoffs of
22:30:00 (NYL v SEA) and 23:00:00 (ATL v LVA). The auditor, run later, computes
22:34:00 and 22:44:00 for the same two obligations. Both derive the cutoff from
the tip. So the tip was revised between the two evaluations.

This probe reads every data/odds_capture/live_*.json in capture order and prints
the commence_time each capture asserted for the two 2026-08-03 games, so the
revision is visible as data rather than inferred.

Usage:  python tip_drift_probe.py <path-to-live-repo-root>
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PAIRS = {("Seattle Storm", "New York Liberty"), ("New York Liberty", "Seattle Storm"),
         ("Las Vegas Aces", "Atlanta Dream"), ("Atlanta Dream", "Las Vegas Aces")}


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    rows = []
    for f in sorted(glob.glob(str(repo / "data" / "odds_capture" / "live_*.json"))):
        cap = datetime.strptime(Path(f).stem.replace("live_", ""), "%Y%m%dT%H%M%SZ") \
            .replace(tzinfo=timezone.utc)
        try:
            games = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for g in games:
            key = (g.get("home_team"), g.get("away_team"))
            if key not in PAIRS:
                continue
            tip = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
            if tip.date().isoformat() not in ("2026-08-03", "2026-08-04"):
                continue
            rows.append((cap, key, tip))

    print("%-22s %-46s %-26s %s" % ("capture", "matchup", "commence_time", "implied T-30m cutoff"))
    last = {}
    for cap, key, tip in rows:
        if last.get(key) == tip:
            continue                       # only print revisions
        last[key] = tip
        print("%-22s %-46s %-26s %s"
              % (cap.isoformat(), "%s v %s" % key, tip.isoformat(),
                 (tip - timedelta(minutes=30)).isoformat()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
