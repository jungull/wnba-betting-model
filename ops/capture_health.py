# -*- coding: utf-8 -*-
"""Capture health check -- does the tape actually have a pulse?

WHY THIS EXISTS. On 2026-08-23 the `player-model-program` worktree was removed. Every capture
task invokes `wscript.exe` on `.claude/worktrees/player-model-program/scripts/run_hidden.vbs`,
that file exists nowhere else, and six tasks began failing. **Nothing noticed for roughly 1.6
hours**, inside a game window, on irreplaceable in-season data. Every task still displayed
`Ready`; the failure lived only in `LastTaskResult`.

So this checks the three things that were each individually sufficient to catch it, and one
more the incident taught:

  1. THE SINGLE POINT OF FAILURE. `run_hidden.vbs` exists at the exact path the tasks invoke.
     One missing file kills every capture at once.

  2. TASK RESULTS. `LastTaskResult` per WNBA task. `Ready` means "scheduled", not "working" --
     reading state instead of result is what let this run unnoticed.

  3. TAPE FRESHNESS, against the CORRECT cadence tier. The odds capture runs PT15M over
     14:00-19:00 UTC and PT5M over 19:00-03:00, and is IDLE 03:00-14:00 by design. A single
     staleness threshold would either scream every night or miss a daytime outage, so the
     tolerance is tier-aware.

  4. A ZERO EXIT IS NOT PROOF DATA LANDED. During the repair the first restored run returned
     LastTaskResult 0 while writing nothing; only the capture log proved the fix. Result codes
     and tape freshness are therefore checked SEPARATELY, and both must pass.

Exits non-zero when anything is wrong, so it is usable as a scheduled watchdog. Scheduling it
is a persistent-configuration decision and is deliberately NOT done here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VBS = os.path.join(ROOT, ".claude", "worktrees", "player-model-program",
                   "scripts", "run_hidden.vbs")
ODDS_LOG = os.path.join(ROOT, "data", "odds_capture", "capture_log.csv")

#: UTC hour ranges -> expected interval in minutes. Outside these the capture is idle.
TIERS = [((14, 19), 15), ((19, 24), 5), ((0, 3), 5)]
TOLERANCE = 3.0          # allow three missed ticks before calling it dead

problems, notes = [], []


def tier_for(hour_utc):
    for (lo, hi), mins in TIERS:
        if lo <= hour_utc < hi:
            return mins
    return None          # idle by design


def check_vbs():
    if os.path.exists(VBS):
        notes.append("run_hidden.vbs present")
        return
    problems.append(
        "MISSING: %s -- every capture task invokes this and it exists nowhere else. "
        "Repair: git worktree add .claude/worktrees/player-model-program "
        "player-model-program" % VBS)


def check_tasks():
    ps = (
        "Get-ScheduledTask -TaskName 'WNBA_*' -ErrorAction SilentlyContinue | "
        "ForEach-Object { $i = Get-ScheduledTaskInfo -TaskName $_.TaskName "
        "-ErrorAction SilentlyContinue; "
        "'{0}|{1}|{2}|{3}' -f $_.TaskName, $_.State, $i.LastTaskResult, $i.LastRunTime }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                              "-Command", ps],
                             capture_output=True, text=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError) as e:
        problems.append("could not query scheduled tasks: %s" % e)
        return
    seen = 0
    for line in out.splitlines():
        if "|" not in line:
            continue
        parts = [x.strip() for x in line.split("|", 3)]
        name, state, result = parts[0], parts[1], parts[2]
        lastrun = parts[3] if len(parts) > 3 else ""
        seen += 1
        if result not in ("0", ""):
            # 267009/267014 are "already running", not failures
            if result in ("267009", "267014"):
                continue
            # A failure code is STALE if the task has not run since. Reporting a stale
            # failure exactly like a live one is how a repaired task keeps looking broken:
            # DailyForecast_PM held a pre-repair code for a full day with no retry due.
            problems.append(
                "TASK FAILING: %-26s state=%s LastTaskResult=%s lastRun=%s "
                "(if lastRun predates your last repair, this is a STALE code and the task "
                "has not retried yet)" % (name, state, result, lastrun or "unknown"))
    if not seen:
        problems.append("no WNBA_* scheduled tasks found at all")
    else:
        notes.append("%d WNBA tasks queried" % seen)


def check_freshness():
    if not os.path.exists(ODDS_LOG):
        problems.append("odds capture log missing: %s" % ODDS_LOG)
        return
    last = None
    with open(ODDS_LOG, encoding="utf-8", errors="ignore") as f:
        head = f.readline().rstrip("\n").split(",")
        try:
            idx = head.index("snapshot_utc")
        except ValueError:
            problems.append("odds capture log has no snapshot_utc column")
            return
        for line in f:                       # the file is append-only; last line wins
            parts = line.split(",")
            if len(parts) > idx and parts[idx].strip():
                last = parts[idx].strip()
    if not last:
        problems.append("odds capture log has no rows")
        return
    try:
        t = dt.datetime.strptime(last, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        problems.append("unparseable last snapshot stamp: %r" % last)
        return
    now = dt.datetime.now(dt.timezone.utc)
    age_min = (now - t).total_seconds() / 60.0
    expected = tier_for(now.hour)
    if expected is None:
        notes.append("capture idle by design at %02dZ; last tape %.0f min ago"
                     % (now.hour, age_min))
        return
    limit = expected * TOLERANCE
    if age_min > limit:
        problems.append(
            "TAPE STALE: last capture %.0f min ago, but the %02dZ tier expects one every "
            "%d min (limit %.0f). A task exiting 0 is NOT proof data landed."
            % (age_min, now.hour, expected, limit))
    else:
        notes.append("tape fresh: %.0f min old, %d-min tier" % (age_min, expected))


def main():
    print("=" * 78)
    print("CAPTURE HEALTH CHECK  %s" % dt.datetime.now(dt.timezone.utc).isoformat())
    print("=" * 78)
    check_vbs()
    check_tasks()
    check_freshness()

    for n in notes:
        print("  ok    %s" % n)
    for p in problems:
        print("  PROBLEM  %s" % p)

    print("-" * 78)
    if problems:
        print("UNHEALTHY -- %d problem(s)" % len(problems))
    else:
        print("HEALTHY")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "capture_health.json"), "w", encoding="utf-8") as f:
        json.dump({"checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "healthy": not problems, "problems": problems, "notes": notes},
                  f, indent=1)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
