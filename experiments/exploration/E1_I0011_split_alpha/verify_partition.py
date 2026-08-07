"""E1 I0011 -- verify no output touches the 2025/2026 confirmation holdout.

TWO CHECKS, deliberately NOT a bare byte-scan.

A previous coordinator in this program produced a FALSE partition violation by
scanning raw bytes for the literals "2025"/"2026": it matched digit runs inside
floats (e.g. ...5.5282656202558...) and row counts that happen to equal 2026.
GRAPH_POLICY 13.2.2 asks for COLUMN VALUES in season/date columns, so:

  1. STRUCTURAL -- every output with a `season` column is reloaded and its value
     set is required to be a subset of {2021,2022,2023,2024}; every output with a
     date column has its min/max printed.
  2. TARGETED TEXTUAL -- text outputs are scanned only for tokens that could
     actually denote a holdout season: an ISO date beginning 2025-/2026-, or the
     digits 2025/2026 adjacent to a season-ish word. Bare digit runs are NOT
     flagged, and every hit is printed with context so it can be judged by eye.
"""
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = {2021, 2022, 2023, 2024}
TEXT_EXT = {".py", ".md", ".txt", ".csv", ".json"}

ISO = re.compile(rb"202[56]-[01]\d-[0-3]\d")
SEASONISH = re.compile(rb"(?i)(season|year|fit_seasons|partition)[^\n]{0,40}?202[56]")

files = []
for root, _, names in os.walk(HERE):
    if "__pycache__" in root:
        continue
    for n in sorted(names):
        files.append(os.path.join(root, n))

print("=" * 96)
print(f"1. STRUCTURAL -- season/date column values in every output ({len(files)} files)")
print("=" * 96)
fail = 0
for f in files:
    ext = os.path.splitext(f)[1].lower()
    rel = os.path.relpath(f, HERE)
    d = None
    try:
        if ext == ".parquet":
            d = pd.read_parquet(f)
        elif ext == ".csv":
            d = pd.read_csv(f)
    except Exception as e:
        print(f"  {rel:<44} unreadable as a frame ({type(e).__name__})")
        continue
    if d is None:
        continue
    if "season" in d.columns:
        vals = set(int(x) for x in pd.unique(d["season"].dropna()))
        ok = vals <= PARTITION
        fail += (not ok)
        print(f"  {rel:<44} season={sorted(vals)} {'PASS' if ok else '*** VIOLATION ***'}")
    else:
        print(f"  {rel:<44} (no season column)")
    for c in d.columns:
        if "date" in c.lower():
            s = pd.to_datetime(d[c], errors="coerce").dropna()
            if len(s):
                ok = s.max().year <= 2024
                fail += (not ok)
                print(f"      date col {c!r}: {s.min().date()} .. {s.max().date()} "
                      f"{'PASS' if ok else '*** VIOLATION ***'}")

print("\n" + "=" * 96)
print("2. TARGETED TEXTUAL -- ISO dates in 2025/2026, or 2025/2026 next to a season word.")
print("   (bare digit runs inside floats and row counts are NOT flagged -- that is the")
print("    known false-positive mode this program has already been bitten by)")
print("=" * 96)
hits = 0
for f in files:
    if os.path.splitext(f)[1].lower() not in TEXT_EXT:
        continue
    rel = os.path.relpath(f, HERE)
    b = open(f, "rb").read()
    for name, rx in [("ISO-date", ISO), ("season-adjacent", SEASONISH)]:
        for mt in rx.finditer(b):
            s, e = max(0, mt.start() - 45), min(len(b), mt.end() + 45)
            ctx = b[s:e].decode("utf-8", "replace").replace("\n", " ")
            print(f"  [{name}] {rel}: ...{ctx}...")
            hits += 1
if not hits:
    print("  no hits.")

print("\n" + "=" * 96)
print(f"VERDICT: structural violations = {fail}; targeted textual hits = {hits}")
print("A textual hit is only a violation if it is a DATA VALUE. Hits inside this")
print("script's own patterns, or inside prose describing the partition rule, are not.")
print("=" * 96)
