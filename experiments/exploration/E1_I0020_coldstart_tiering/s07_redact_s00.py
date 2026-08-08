"""E1_I0020 STEP 9 -- redact holdout-season row counts from the s00 INSPECTION artifacts.

  DISCLOSURE, not a cleanup.  s00 was an inspection of player_bios.csv run BEFORE the load filter
  existed, and it printed the file's season row counts -- which include 2025 and 2026.  No 2025/2026
  VALUE ever entered any analysis, table, model or result: every loader filters at the filter-point
  and assert_partition runs on every frame.  But a row COUNT for a holdout season is a description of
  the holdout, and the partition rule says not to produce one.

  This script REDACTS those counts in place, leaving an explicit marker so the redaction is visible
  rather than silent, and re-verifies that nothing else in the screen's artifacts mentions a
  holdout-season VALUE.  The original inspection is superseded by s02, which redoes the same
  verification restricted to 2021-2024; every result in the screen uses the s02 version.
"""
import json
import os
import re

import pandas as pd

import ct_base as B

MARK = "REDACTED__HOLDOUT_SEASON_ROW_COUNT__see_NOTES.md_section_3_item_8"

p = os.path.join(B.OUT, "_s00.json")
with open(p) as fh:
    d = json.load(fh)
before = dict(d.get("bios_season_counts", {}))
if "bios_season_counts" in d:
    d["bios_season_counts"] = {k: (MARK if int(k) in B.HOLDOUT else v)
                               for k, v in d["bios_season_counts"].items()}
d["_redaction_note"] = (
    "s00 was an INSPECTION step that ran before the season filter and printed player_bios.csv row "
    "counts for every season present in the file, including the 2025/2026 holdout.  Those two counts "
    "are redacted here.  No holdout VALUE entered any analysis; s02 redoes this verification "
    "restricted to 2021-2024 and every result uses that version.  Recorded rather than deleted.")
with open(p, "w") as fh:
    json.dump(d, fh, indent=2)
print("redacted _s00.json  (holdout keys present before: %s)"
      % sorted(k for k in before if int(k) in B.HOLDOUT))

# same for the s00 run log
lp = os.path.join(B.OUT, "run_log_s00.txt")
with open(lp, encoding="utf-8", errors="replace") as fh:
    lines = fh.readlines()
out, n = [], 0
for ln in lines:
    if re.match(r"^\s*(2025|2026)\s+\d+\s*$", ln):
        out.append("    %s\n" % MARK)
        n += 1
    else:
        out.append(ln)
with open(lp, "w", encoding="utf-8") as fh:
    fh.writelines(out)
print("redacted %d holdout count lines in run_log_s00.txt" % n)

B.hdr("FINAL SWEEP -- do any RESULT artifacts contain a holdout-season VALUE?")
print("""
  VALUE test, not a text scan: every CSV this screen wrote is re-read and every column that is
  season-VALUED is checked against the partition.  (A text scan for '2025' would hit this screen's
  own prose about the partition rule -- the trap-3 false positive, three times over.)
""")
bad = []
for f in sorted(os.listdir(B.OUT)):
    if not f.endswith(".csv"):
        continue
    try:
        df = pd.read_csv(os.path.join(B.OUT, f))
    except Exception as e:
        print("  %-42s SKIPPED (%s)" % (f, type(e).__name__))
        continue
    hits = []
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) and bool((s % 1 == 0).all()) and bool(s.between(1990, 2100).all()):
            vs = set(int(x) for x in s.unique())
            if vs & B.HOLDOUT:
                hits.append((c, sorted(vs & B.HOLDOUT)))
    print("  %-42s %s" % (f, "OK" if not hits else "*** HOLDOUT VALUES %s ***" % hits))
    if hits:
        bad.append((f, hits))
for f in ["tier_frame.parquet", "prior_pool.parquet", "placeholder_frame.parquet"]:
    df = pd.read_parquet(os.path.join(B.OUT, f))
    B.assert_partition_adjudicated(df, where=f)
if bad:
    raise SystemExit("HOLDOUT VALUES FOUND IN RESULT ARTIFACTS: %s" % bad)
print("\n  SWEEP CLEAN: no result artifact contains a holdout-season value.")
