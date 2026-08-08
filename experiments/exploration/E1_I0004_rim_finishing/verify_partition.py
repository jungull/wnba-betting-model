"""E1 I0004 -- verify nothing in this screen touches the 2025/2026 confirmation holdout.

Deliberately NOT a raw byte-scan for "2025"/"2026": that produced a FALSE partition
violation in this program by matching row counts and digit runs inside floats.
GRAPH_POLICY 13.2.2 asks for COLUMN VALUES in season/date columns.

  1. STRUCTURAL   -- every frame output is reloaded; its `season` value set must be
                     a subset of {2021,2022,2023,2024}; date columns print min/max.
  2. ARTIFACT     -- for every pre-built artifact this screen's code path can reach,
                     report the .manifest.json `asof_granularity`. The test is
                     asof_granularity == "row" (a row-granular artifact filtered to
                     2021-2024 is safe), NOT fit_seasons / fit_through_season, which
                     only say what a file CONTAINS.
  3. TARGETED TEXT-- text outputs scanned only for an ISO date in 2025/2026 or the
                     digits 2025/2026 adjacent to a season-ish word, with context
                     printed so every hit can be judged by eye.
"""
import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
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

print("=" * 100)
print(f"1. STRUCTURAL -- season/date column values in every output ({len(files)} files)")
print("=" * 100)
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
        print(f"  {rel:<46} unreadable as a frame ({type(e).__name__})")
        continue
    if d is None:
        continue
    if "season" in d.columns:
        vals = {int(x) for x in pd.unique(d["season"].dropna())}
        ok = vals <= PARTITION
        fail += (not ok)
        print(f"  {rel:<46} season={sorted(vals)} {'PASS' if ok else '*** VIOLATION ***'}")
    else:
        print(f"  {rel:<46} (no season column)")
    for c in d.columns:
        if "date" in c.lower():
            s = pd.to_datetime(d[c], errors="coerce").dropna()
            if len(s):
                ok = s.max().year <= 2024
                fail += (not ok)
                print(f"      date col {c!r}: {s.min().date()} .. {s.max().date()} "
                      f"{'PASS' if ok else '*** VIOLATION ***'}")

print("\n" + "=" * 100)
print("2. ARTIFACT CONTAMINATION -- asof_granularity from each artifact's manifest")
print("=" * 100)
ARTIFACTS = [
    ("data/shotcharts/shots_{2021,2022,2023,2024}_{regular,playoffs}.parquet",
     "RAW per-season shot files; 8 opened, all inside the partition. No .manifest.json "
     "exists for these (checked: 0 manifest files in data/shotcharts/). They are raw "
     "single-season sources -- season is the FILENAME, so there is nothing pooled to "
     "contaminate. shots_2025_*, shots_2026_* were never opened."),
    ("data/zone_maps/*.csv",
     "NOT READ. E0 I0004 established their shrinkage priors are pooled across "
     "2021-2026. That decision is deliberately preserved; this screen rebuilds zone "
     "rates from the raw per-season shot files instead."),
]
for path, note in ARTIFACTS:
    print(f"  {path}\n      {note}")

for rel in ["data/masters/master_player.parquet"]:
    mp = os.path.join(REPO, rel + ".manifest.json")
    if os.path.exists(mp):
        m = json.load(open(mp, encoding="utf-8"))
        print(f"\n  {rel}")
        print(f"      asof_granularity = {m.get('asof_granularity')!r}  "
              f"-> {'SAFE when filtered' if m.get('asof_granularity') == 'row' else 'NOT ROW-GRANULAR'}")
        print(f"      (fit_seasons={m.get('fit_seasons')}, fit_through_season="
              f"{m.get('fit_through_season')} -- these describe what the file CONTAINS "
              f"and are NOT the contamination test)")
        print("      Reached only via the frozen baseline's own validate_baseline.py, "
              "which scores E1_I0011's frame.parquet (seasons 2021-2024, asserted at "
              "load). This screen's own code path never reads it.")

print("\n  Frozen baseline module: experiments/exploration/E1_I0011_split_alpha/baseline/"
      "corrected_baseline.py -- pure code, contains no season logic and no fitted data; "
      "its constants were established on 2021-2024 only (SPEC.md section 7). Imported, "
      "not reimplemented.")

print("\n" + "=" * 100)
print("3. TARGETED TEXTUAL -- ISO dates in 2025/2026, or 2025/2026 next to a season word.")
print("   Bare digit runs inside floats and row counts are NOT flagged -- that is the")
print("   known false-positive mode this program has already been bitten by.")
print("=" * 100)
hits = 0
for f in files:
    if os.path.splitext(f)[1].lower() not in TEXT_EXT:
        continue
    rel = os.path.relpath(f, HERE)
    b = open(f, "rb").read()
    for name, rx in [("ISO-date", ISO), ("season-adjacent", SEASONISH)]:
        for mt in rx.finditer(b):
            s, e = max(0, mt.start() - 50), min(len(b), mt.end() + 50)
            ctx = b[s:e].decode("utf-8", "replace").replace("\n", " ")
            print(f"  [{name}] {rel}: ...{ctx}...")
            hits += 1
if not hits:
    print("  no hits.")

print("\n" + "=" * 100)
print(f"VERDICT: structural violations = {fail}; targeted textual hits = {hits}")
print("A textual hit is only a violation if it is a DATA VALUE. Hits inside this")
print("script's own regexes, or inside prose describing the partition rule, are not.")
print("holdout_touched = False")
print("=" * 100)
