"""daily_refresh.py — daily data refresh chain for the WNBA prediction engine.

Runs the four-step chain, aborting loudly on any failure (no-imputation rule:
downstream consumers degrade explicitly on stale data — daily_forecast.py's
staleness guards check master ages):

  1. collect_refresh.py          resumable collection (skips completed work;
                                 pulls new 2026 games: gamelogs, pbp, misc,
                                 advanced). The ONLY stats.nba.com crawler —
                                 scheduled at 08:30 local, before the capture
                                 windows (odds/injury 10:00-23:00, different
                                 hosts) and colliding with nothing.
  2. build_masters.py            rebuild data/masters/ (~41s; PASS required).
  3. build_channel_base_v2.py    rebuild channel_base_v2.csv from the masters
                                 (daily_forecast.py trends read this file).
  4. daily_certify.py            standing Phase-0 certification (exit code is
                                 the chain's exit code).

Each step's stdout/stderr is appended to logs/daily_refresh/refresh_<date>.log.
Exit codes: 0 = full chain green; 1 = a step failed (the log names it).

Scheduled task: WNBA_DailyRefresh, daily 08:30 (created 2026-07-30; delete with
``schtasks /delete /tn WNBA_DailyRefresh``).

Run manually:  python daily_refresh.py [--skip-collect]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
LOGDIR = REPO / "logs" / "daily_refresh"

STEPS = [
    ("collect", [sys.executable, str(REPO / "collect_refresh.py")]),
    ("masters", [sys.executable, str(REPO / "build_masters.py")]),
    ("channel_base", [sys.executable,
                      str(REPO / "experiments" / "channel_reval" / "build_channel_base_v2.py")]),
    ("certify", [sys.executable, str(REPO / "daily_certify.py")]),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip-collect", action="store_true",
                    help="skip the stats.nba.com collection step (offline rebuild)")
    args = ap.parse_args(argv)

    LOGDIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGDIR / f"refresh_{datetime.now():%Y-%m-%d}.log"
    steps = [s for s in STEPS if not (args.skip_collect and s[0] == "collect")]

    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n===== daily_refresh {datetime.now().isoformat(timespec='seconds')} =====\n")
        for name, cmd in steps:
            log.write(f"\n----- step: {name} ({' '.join(cmd[1:])}) -----\n")
            log.flush()
            t0 = datetime.now()
            proc = subprocess.run(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
            dt = (datetime.now() - t0).total_seconds()
            log.write(f"----- step {name}: exit {proc.returncode} in {dt:.0f}s -----\n")
            log.flush()
            print(f"[daily_refresh] {name}: exit {proc.returncode} ({dt:.0f}s)")
            if proc.returncode != 0:
                log.write(f"CHAIN ABORTED at step {name}\n")
                print(f"[daily_refresh] CHAIN ABORTED at {name} — see {log_path}")
                return 1
        log.write("CHAIN GREEN\n")
    print(f"[daily_refresh] chain green — log {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
