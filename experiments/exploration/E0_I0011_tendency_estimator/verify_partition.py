"""E0 I0011 -- partition verification performed on the ACTUAL OUTPUT BYTES.

Two independent checks on every file this experiment wrote:
  (1) structural -- if the file has a `season` column, its value set must be a
      subset of {2021,2022,2023,2024};
  (2) byte-level -- scan the raw bytes for the literal tokens "2025" and "2026"
      and print every hit with surrounding context, so any match can be judged
      by eye rather than waved away.
"""
import os
import re
import pandas as pd

PARTITION = {2021, 2022, 2023, 2024}
HERE = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
        r"\player-model-program\experiments\exploration\E0_I0011_tendency_estimator")

files = sorted(os.listdir(HERE))
print("files written by this experiment:", len(files))

print("\n--- (1) structural check on `season` columns ---")
for f in files:
    p = os.path.join(HERE, f)
    if f.endswith(".parquet"):
        d = pd.read_parquet(p)
    elif f.endswith(".csv"):
        d = pd.read_csv(p)
    else:
        continue
    if "season" in d.columns:
        vals = set(int(x) for x in pd.unique(d["season"].dropna()))
        ok = vals <= PARTITION
        print(f"  {f:<34} season values = {sorted(vals)}  -> {'PASS' if ok else 'FAIL'}")
        assert ok, f"PARTITION VIOLATION in {f}: {vals}"
    else:
        print(f"  {f:<34} (no season column)")

print("\n--- (2) byte-level scan for the literals '2025' and '2026' ---")
total_hits = 0
for f in files:
    p = os.path.join(HERE, f)
    if not os.path.isfile(p):
        continue
    raw = open(p, "rb").read()
    hits = []
    for tok in (b"2025", b"2026"):
        for m in re.finditer(re.escape(tok), raw):
            s = max(0, m.start() - 45)
            ctx = raw[s:m.end() + 45].decode("utf-8", "replace").replace("\r", " ")
            ctx = ctx.replace("\n", " ")
            hits.append((tok.decode(), m.start(), ctx))
    total_hits += len(hits)
    print(f"  {f:<34} {len(hits)} hit(s)")
    for tok, off, ctx in hits[:12]:
        print(f"      {tok} @ {off}: ...{ctx}...")
    if len(hits) > 12:
        print(f"      (+{len(hits)-12} more, same character)")
print(f"\ntotal literal hits across all output files: {total_hits}")
print("Any hit above must be a coincidental digit run inside a float "
      "(e.g. '0.20250') or a path/date string, NOT a season value. "
      "The structural check in (1) is the binding one for season identity.")
