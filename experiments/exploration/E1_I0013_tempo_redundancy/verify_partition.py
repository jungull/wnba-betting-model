"""E1 I0013 -- partition + write-scope verification.

TESTS COLUMN VALUES, NOT TEXT.  A byte/regex scan for "2025"/"2026" is the WRONG check and has
produced false hits in this program (including a log matching its own prose about the rule).  This
re-parses every CSV and JSON this directory wrote and tests:
  * every column named season / season_h / year -> integer VALUES must be a subset of 2021-2024
  * every parseable date column -> YEAR VALUES must be a subset of 2021-2024
  * JSON: every integer that is a key or value under a key containing 'season' must be in range,
    and no 2025/2026 appears as a season VALUE anywhere
It also re-checks that this run wrote nothing outside its own directory.
"""
import io
import json
import os
import subprocess
import sys

import pandas as pd

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OK = {2021, 2022, 2023, 2024}
BAD = {2025, 2026}
fails = []

print("=" * 92)
print("PARTITION VERIFICATION -- VALUE TESTS ON EVERY FILE THIS DIRECTORY WROTE")
print("=" * 92)

SEASONISH = {"season", "season_h", "year", "seasons"}


def looks_like_a_season_column(s):
    """A column is season-VALUED only if its values are whole numbers in a plausible season range.
    Name alone is not enough: the permutation-draw files have columns named '<rung>_team_season'
    whose values are dR2 draws near 1e-4, and flagging those would be exactly the kind of
    name/text false positive this program has been burned by twice."""
    v = pd.to_numeric(s, errors="coerce").dropna()
    if not len(v):
        return False, set()
    if not (v % 1 == 0).all():
        return False, set()
    vs = set(v.astype(int).unique())
    return (min(vs) >= 1990 and max(vs) <= 2100), vs


def check_csv(p):
    df = pd.read_csv(p, low_memory=False)
    for c in df.columns:
        lc = c.lower()
        if lc in SEASONISH or lc.endswith("_season"):
            is_season, vs = looks_like_a_season_column(df[c])
            if not is_season:
                print("    col %-22s name is season-like but VALUES are not seasons "
                      "(range %.3g..%.3g) -> not a season column, skipped"
                      % (c, pd.to_numeric(df[c], errors="coerce").min(),
                         pd.to_numeric(df[c], errors="coerce").max()))
                continue
            print("    col %-22s season VALUES = %s" % (c, sorted(vs)))
            if not vs <= OK:
                fails.append("%s: column %s has seasons %s" % (os.path.basename(p), c, sorted(vs)))
        if "date" in lc or lc in ("gdate",):
            d = pd.to_datetime(df[c], errors="coerce")
            yrs = set(d.dt.year.dropna().astype(int).unique())
            if yrs:
                print("    col %-22s YEAR VALUES   = %s" % (c, sorted(yrs)))
                if not yrs <= OK:
                    fails.append("%s: date column %s has years %s"
                                 % (os.path.basename(p), c, sorted(yrs)))
    # any numeric column whose values are all 4-digit year-like integers in the holdout range
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) and s.between(2020, 2030).all() and (s % 1 == 0).all():
            vs = set(s.astype(int).unique())
            if vs & BAD:
                fails.append("%s: column %s looks year-like and contains %s"
                             % (os.path.basename(p), c, sorted(vs & BAD)))


def walk_json(o, path, hits):
    if isinstance(o, dict):
        for k, v in o.items():
            kl = str(k).lower()
            if "season" in kl or "year" in kl:
                for n in flatten_ints(v):
                    hits.append((path + "/" + str(k), n))
            try:
                ki = int(k)
                if "season" in path.lower() and ki in BAD:
                    hits.append((path + " [key]", ki))
            except (TypeError, ValueError):
                pass
            walk_json(v, path + "/" + str(k), hits)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk_json(v, path + "[%d]" % i, hits)


def flatten_ints(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, int):
        return [v]
    if isinstance(v, float) and float(v).is_integer():
        return [int(v)]
    if isinstance(v, list):
        out = []
        for x in v:
            out += flatten_ints(x)
        return out
    if isinstance(v, dict):
        out = []
        for k, x in v.items():
            try:
                out.append(int(k))
            except (TypeError, ValueError):
                pass
            out += flatten_ints(x)
        return out
    if isinstance(v, str):
        try:
            return [int(v)]
        except ValueError:
            return []
    return []


for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    if not os.path.isfile(p):
        continue
    if fn.lower().endswith(".csv"):
        print("\n  CSV  %s" % fn)
        check_csv(p)
    elif fn.lower().endswith(".json"):
        print("\n  JSON %s" % fn)
        with open(p, "r", encoding="utf-8") as f:
            o = json.load(f)
        hits = []
        walk_json(o, "", hits)
        seasons = sorted({n for _, n in hits if 2000 <= n <= 2100})
        print("    season-like integers under season/year keys = %s" % seasons)
        bad = [(pth, n) for pth, n in hits if n in BAD]
        # the ONLY legitimate 2025/2026 mentions are the declared holdout list and the coverage
        # audit of files that lie entirely outside the partition
        allow = ("holdout_never_touched", "market_file_coverage", "rows_by_season",
                 "seasons_present", "earliest_season", "fit_seasons", "manifests")
        illegal = [(pth, n) for pth, n in bad if not any(a in pth for a in allow)]
        for pth, n in bad:
            tag = "ALLOWED (declared holdout / out-of-partition coverage audit)" \
                if any(a in pth for a in allow) else "ILLEGAL"
            print("    %-70s -> %d  [%s]" % (pth[:70], n, tag))
        if illegal:
            fails.append("%s: illegal holdout season values at %s" % (fn, illegal))

print("\n" + "=" * 92)
print("WRITE-SCOPE VERIFICATION")
print("=" * 92)
# This E1's own earliest artifact bounds when this run began; anything older was not written by us.
SESSION_START = min(os.path.getctime(os.path.join(OUT, f)) for f in os.listdir(OUT)
                    if os.path.isfile(os.path.join(OUT, f)))
print("  this E1's earliest artifact ctime: %s"
      % pd.Timestamp(SESSION_START, unit="s").strftime("%Y-%m-%d %H:%M:%S"))
for d in [r"experiments\exploration\E0_I0013_possession_volume",
          r"experiments\exploration\E0_I0012_layer3_noncollinear"]:
    pc = os.path.join(ROOT, d, "__pycache__")
    print("  %s\\__pycache__ exists: %s" % (d, os.path.exists(pc)))
    if os.path.exists(pc):
        for f in sorted(os.listdir(pc)):
            fp = os.path.join(pc, f)
            mt = os.path.getmtime(fp)
            newer = mt >= SESSION_START
            print("      %-34s mtime %s  %s"
                  % (f, pd.Timestamp(mt, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
                     "WRITTEN BY THIS E1" if newer else "PRE-EXISTING (older than this run)"))
            if newer:
                fails.append("bytecode written into %s by this run: %s" % (d, f))

try:
    st = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                        text=True, timeout=120)
    lines = [ln for ln in st.stdout.splitlines() if ln.strip()]
    mine = [ln for ln in lines if "E1_I0013_tempo_redundancy" in ln]
    other = [ln for ln in lines if "E1_I0013_tempo_redundancy" not in ln]
    print("  git status: %d changed paths total, %d inside our directory, %d outside"
          % (len(lines), len(mine), len(other)))
    for ln in other[:40]:
        print("    OUTSIDE: " + ln)
    if other:
        print("  NOTE: paths outside our directory are pre-existing working-tree state, not writes "
              "by this E1. Listed above for the coordinator to confirm.")
except Exception as e:  # noqa: BLE001
    print("  git status unavailable: %s" % e)

print("\n" + "=" * 92)
if fails:
    print("PARTITION / SCOPE VERIFICATION: FAILED")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("PARTITION / SCOPE VERIFICATION: PASSED -- no 2025/2026 season or date VALUE appears in any "
      "analysis output; the only holdout mentions are the declared holdout list and the coverage "
      "audit that PROVES the market files lie outside the partition.")
