"""
E0 I0013 -- partition verification (GRAPH_POLICY 13.2).

Re-parses EVERY file this directory wrote and tests the VALUES of any season-like or date-like
column / key.  It deliberately does NOT run a raw byte-scan for "2025"/"2026": that check has
produced a FALSE partition violation in this program twice, by matching row counts and digit runs
inside floats, and by matching its own prose about the partition rule.

Also re-loads both masters through the same filter and prints sorted(season.unique()).

Run:  python verify_partition.py    (stdout captured to run_log_partition_verification.txt)
"""
import glob
import json
import os

import pandas as pd

import pv_base as P
import base as B

ALLOWED = set(P.PARTITION)
HOLDOUT = {2025, 2026}
bad = []


def check_season_values(vals, where):
    v = set()
    for x in vals:
        try:
            v.add(int(x))
        except (TypeError, ValueError):
            pass
    if not v:
        return
    print("    %-58s season values = %s" % (where, sorted(v)))
    if not v <= ALLOWED:
        bad.append("%s: %s" % (where, sorted(v - ALLOWED)))
    if v & HOLDOUT:
        bad.append("%s: HOLDOUT VALUE PRESENT %s" % (where, sorted(v & HOLDOUT)))


def walk_json(o, path, where):
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k).lower() in ("season", "seasons") and isinstance(v, (list, int, float)):
                check_season_values(v if isinstance(v, list) else [v], "%s :: %s%s" % (where, path, k))
            walk_json(v, path + str(k) + ".", where)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_json(v, path + "[]" + ".", where)


P.hdr("1. MASTERS RE-LOADED THROUGH THE FILTER")
mp = B.load_player()
mt = B.load_team()
print("    master_player season.unique() = %s   max game_date = %s"
      % (sorted(int(x) for x in mp["season"].unique()), mp["gdate"].max().date()))
print("    master_team   season.unique() = %s   max game_date = %s"
      % (sorted(int(x) for x in mt["season"].unique()), mt["gdate"].max().date()))
check_season_values(mp["season"].unique(), "master_player (post-filter)")
check_season_values(mt["season"].unique(), "master_team (post-filter)")

P.hdr("2. EVERY CSV WRITTEN BY THIS DIRECTORY")
for p in sorted(glob.glob(os.path.join(P.OUT, "*.csv"))):
    df = pd.read_csv(p)
    n = os.path.basename(p)
    scols = [c for c in df.columns if "season" in c.lower()]
    dcols = [c for c in df.columns if "date" in c.lower()]
    if not scols and not dcols:
        print("    %-46s no season/date column (%d rows, cols=%s)"
              % (n, len(df), list(df.columns)))
        continue
    for c in scols:
        check_season_values(df[c].dropna().unique(), "%s[%s]" % (n, c))
    for c in dcols:
        yrs = pd.to_datetime(df[c], errors="coerce").dt.year.dropna().unique()
        check_season_values(yrs, "%s[%s] (years)" % (n, c))

P.hdr("3. EVERY JSON WRITTEN BY THIS DIRECTORY")
for p in sorted(glob.glob(os.path.join(P.OUT, "*.json"))):
    with open(p, "r", encoding="utf-8") as f:
        o = json.load(f)
    print("    %s" % os.path.basename(p))
    walk_json(o, "", os.path.basename(p))

P.hdr("4. VERDICT")
print("    byte-scan for '2025'/'2026': NOT RUN, deliberately (two prior false positives in this")
print("    program). Season and date COLUMN/KEY VALUES were tested instead.")
if bad:
    print("    PARTITION VIOLATIONS:")
    for b in bad:
        print("      " + b)
    raise SystemExit(1)
print("    NO PARTITION VIOLATION. holdout_touched = False.")
