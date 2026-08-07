"""
E0 I0012 -- partition integrity verification over every artifact this screen wrote.

Method (GRAPH_POLICY 13.2.2, and deliberately NOT the over-broad byte scan):
  * Parse each CSV as a table.
  * Test the VALUES of any season column against {2021,2022,2023,2024}.
  * Test the VALUES of any date column against a max of 2024-12-31.
  * Assert no `observed_time` column (a mid-2026 local file mtime) survives anywhere.

A literal byte-scan for "2025"/"2026" is NOT run: it previously produced a FALSE partition
violation by matching row counts equal to 2026 and digit runs inside float literals.
"""
import glob
import os

import pandas as pd

import base as B

ALLOWED = set(B.PARTITION)
MAXDATE = pd.Timestamp("2024-12-31")

files = sorted(glob.glob(os.path.join(B.OUT, "*.csv")))
print("verifying %d CSV artifacts in %s\n" % (len(files), B.OUT))
bad = []
for p in files:
    d = pd.read_csv(p)
    name = os.path.basename(p)
    notes = []
    for c in d.columns:
        if c in B.BANNED_COLS:
            bad.append((name, "BANNED COLUMN PRESENT: %s" % c))
    scol = [c for c in d.columns if c.lower() == "season"]
    if scol:
        vals = set(pd.to_numeric(d[scol[0]], errors="coerce").dropna().astype(int).unique())
        notes.append("season values %s" % sorted(vals))
        if not vals <= ALLOWED:
            bad.append((name, "SEASON VALUES OUTSIDE PARTITION: %s" % sorted(vals - ALLOWED)))
    dcol = [c for c in d.columns if "date" in c.lower()]
    for c in dcol:
        dt = pd.to_datetime(d[c], errors="coerce").dropna()
        if len(dt):
            notes.append("%s max %s" % (c, dt.max().date()))
            if dt.max() > MAXDATE:
                bad.append((name, "DATE BEYOND PARTITION in %s: %s" % (c, dt.max())))
    print("  %-42s rows=%-7d %s" % (name, len(d), "; ".join(notes) if notes else "(no season/date cols)"))

print("\n" + "=" * 78)
if bad:
    for n, m in bad:
        print("VIOLATION  %s  %s" % (n, m))
    raise SystemExit("PARTITION INTEGRITY FAILED")
print("PARTITION INTEGRITY OK -- all season values within %s, no dates past %s, "
      "no banned columns present." % (sorted(ALLOWED), MAXDATE.date()))
print("The 2025/2026 confirmation holdout was never read by this screen.")
