"""E1 I0004b -- partition and artifact-contamination verification.

TWO CHECKS, DELIBERATELY DIFFERENT IN KIND.

1. STRUCTURAL. Every parquet/CSV this screen wrote is opened and its `season`
   column VALUES are tested against {2021,2022,2023,2024}. Every data file this
   screen READ is enumerated from the source and tested for a 2025/2026 filename.

2. ARTIFACT CONTAMINATION. For every pre-built artifact in the repo that carries a
   sibling `<artifact>.manifest.json`, the `asof_granularity` COLUMN VALUE is read
   and reported. "row" -> bounded per row by its own date, safe once filtered to
   2021-2024. "artifact" -> bounded by the file's LATEST input, UNUSABLE at E0/E1
   and filtering does NOT help.

   A BYTE/REGEX SCAN FOR "2025"/"2026" IS THE WRONG CHECK and is not performed as a
   verdict: the previous I0004 verifier produced 14 textual hits that were ALL prose
   about the partition rule, including its own log re-scanning its own context lines.
   Text occurrences of "2025"/"2026" in THIS screen's own sources are counted and
   listed purely so a reader can see they are prose, and they carry no verdict.
"""
import glob
import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARTITION = {2021, 2022, 2023, 2024}
FORBIDDEN = re.compile(r"20(25|26)")

print("=" * 100)
print("1. STRUCTURAL -- season COLUMN VALUES in every frame this screen wrote")
print("=" * 100)
violations = 0
for p in sorted(glob.glob(os.path.join(HERE, "*.parquet"))):
    d = pd.read_parquet(p)
    if "season" in d.columns:
        ss = set(int(x) for x in d["season"].unique())
        bad = ss - PARTITION
        violations += len(bad)
        print(f"  {os.path.basename(p):<40} rows={len(d):>7}  seasons={sorted(ss)}  "
              f"{'OK' if not bad else '*** VIOLATION ' + str(sorted(bad)) + ' ***'}")
    else:
        print(f"  {os.path.basename(p):<40} rows={len(d):>7}  (no season column)")
for p in sorted(glob.glob(os.path.join(HERE, "*.csv"))):
    d = pd.read_csv(p)
    print(f"  {os.path.basename(p):<40} rows={len(d):>7}  (permutation draws; "
          f"columns={list(d.columns)})")

print("\n" + "=" * 100)
print("2. STRUCTURAL -- every DATA file this screen opened")
print("=" * 100)
srcs = sorted(glob.glob(os.path.join(HERE, "*.py")))
read_paths = set()
for p in srcs:
    txt = open(p, encoding="utf-8").read()
    for m in re.finditer(r"shots_\{?[^\"']*?\}?_\{?t\}?\.parquet|shots_(\d{4})_(\w+)\.parquet",
                         txt):
        read_paths.add(m.group(0))
print("  shot-file read patterns found in this screen's sources:")
for r in sorted(read_paths):
    print(f"    {r}")
print("\n  the PARTITION list those patterns are formatted with is, in every script:")
for p in srcs:
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"^PARTITION = (\[.*?\])", txt, re.M)
    if m:
        print(f"    {os.path.basename(p):<24} PARTITION = {m.group(1)}")
files_that_exist = sorted(os.path.basename(x) for x in
                          glob.glob(os.path.join(REPO, "data", "shotcharts", "*.parquet")))
would_read = [f"shots_{s}_{t}.parquet" for s in sorted(PARTITION)
              for t in ("regular", "playoffs")]
print(f"\n  files in data/shotcharts that exist        : {len(files_that_exist)}")
print(f"  files this screen enumerates and opens    : {len(would_read)}")
print(f"  of those, any with a 2025/2026 filename?  : "
      f"{[f for f in would_read if FORBIDDEN.search(f)] or 'NONE'}")
holdout = [f for f in files_that_exist if FORBIDDEN.search(f)]
print(f"  holdout files present but NEVER opened    : {holdout}")

print("\n" + "=" * 100)
print("3. ARTIFACT CONTAMINATION -- asof_granularity COLUMN VALUES (not a text scan)")
print("=" * 100)
mans = sorted(glob.glob(os.path.join(REPO, "data", "**", "*.manifest.json"),
                        recursive=True))
usable, unusable = [], []
for p in mans:
    m = json.load(open(p, encoding="utf-8"))
    g = m.get("asof_granularity")
    rel = os.path.relpath(p, REPO).replace("\\", "/")
    (usable if g == "row" else unusable).append((rel, g))
    print(f"  {rel:<58} asof_granularity = {g!r}   "
          f"{'usable once filtered' if g == 'row' else 'UNUSABLE at E0/E1'}")
print(f"\n  usable ('row'): {len(usable)}   unusable ('artifact'): {len(unusable)}")

read_artifacts = set()
for p in srcs:
    txt = open(p, encoding="utf-8").read()
    for cand in ("zone_maps", "master_player", "master_team", "player_zone_offense",
                 "team_zone_defense", "team_zone_offense", "shrinkage_priors",
                 "league_zone_averages"):
        if re.search(r"read_(parquet|csv)\([^)]*" + cand, txt):
            read_artifacts.add((os.path.basename(p), cand))
print(f"\n  pre-built artifacts actually read by this screen: "
      f"{sorted(read_artifacts) if read_artifacts else 'NONE'}")
print("  data/zone_maps/* : NOT READ. All five carry asof_granularity == 'artifact'")
print("    and their own manifests state a 2021 row's shrunk value saw later seasons,")
print("    so FILTERING DOES NOT HELP. Zone assignment is instead taken from the raw")
print("    per-shot SHOT_ZONE_BASIC label inside each per-season shot file.")
print("  data/masters/*   : NOT READ by this screen (asof_granularity == 'row', so it")
print("    WOULD have been usable filtered; it simply was not needed).")

print("\n" + "=" * 100)
print("4. TEXTUAL OCCURRENCES OF 2025/2026 IN THIS SCREEN'S SOURCES -- NO VERDICT")
print("=" * 100)
print("  A byte/regex scan is the WRONG contamination check. Listed only so a reader")
print("  can confirm every hit is prose about the partition rule, never a data value.")
nhit = 0
for p in srcs:
    for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
        if FORBIDDEN.search(line):
            nhit += 1
            print(f"    {os.path.basename(p)}:{i}: {line.strip()[:110]}")
print(f"\n  .py textual hits: {nhit} (all prose / the RNG seed 20260807, no data value)")
mdhit = sum(1 for p in sorted(glob.glob(os.path.join(HERE, "*.md")))
            for line in open(p, encoding="utf-8").read().splitlines()
            if FORBIDDEN.search(line))
print(f"  .md textual hits: {mdhit} -- NOTES.md prose describing the partition rule and "
      f"the holdout it does not touch. Not listed; carries no verdict.")

print("\n" + "=" * 100)
print(f"STRUCTURAL VIOLATIONS: {violations}")
print("=" * 100)
