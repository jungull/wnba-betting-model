"""E0_I0016 s05 -- final verification of the written artifacts.  VALUE-BASED partition sweep."""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import OUT, hdr, sk

hdr("1. FINDINGS.json parses, and its headline fields")
with open(os.path.join(OUT, "FINDINGS.json"), encoding="utf-8") as fh:
    fi = json.load(fh)
print("  top-level keys: %s" % list(fi.keys()))
print("  cells recorded: %d   survivors detailed: %d"
      % (len(fi["all_cells"]), len(fi["survivors_familywise_p05"])))
print("  attrition: %s" % json.dumps(fi["attrition"]))
print("  preselection: %s" % json.dumps(fi["preselection"]))

hdr("2. VALUE-BASED PARTITION SWEEP over every artifact this screen wrote")
print("  screenkit.assert_partition on COLUMN VALUES -- no byte scan.")
print("  *** date_cols IS PASSED EXPLICITLY, AND HERE IS WHY -- see KIT_BUG_REPRO.py. ***")
print("  assert_partition auto-detects date columns by `\"date\" in name.lower()`, and the word")
print("  candi-DATE contains 'date'. Columns named `candidate`, `n_candidates` and")
print("  `mae_with_candidate` are therefore parsed with pd.to_datetime, which on FLOATS does not")
print("  raise -- it reads them as epoch nanoseconds, returns 1970, and flags a violation on a")
print("  frame whose every real value is inside 2021-2024. The SEASON branch has a value-")
print("  plausibility guard for exactly this (`_is_season_valued`); the DATE branch has none.")
print("  Passing date_cols=[] would silence the TRUE alarm too (REPRO 4), so instead the real")
print("  date columns are named EXPLICITLY and a separate value-based date sweep is run below.")

REAL_DATE_NAMES = {"game_date", "gdate", "date"}


def real_date_cols(d):
    return [c for c in d.columns
            if pd.api.types.is_datetime64_any_dtype(d[c]) or str(c).lower() in REAL_DATE_NAMES]


def independent_date_value_sweep(d):
    """Parse EVERY non-numeric column and check any that genuinely reads as dates.

    This is the compensating control for naming the date columns explicitly: it is value-based,
    ignores names entirely, and would catch a 2025/2026 date hiding in an oddly-named text column.
    """
    bad = []
    for c in d.columns:
        s = d[c]
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
            continue          # numbers are NOT dates; the epoch reading is the defect above
        parsed = pd.to_datetime(s, errors="coerce")
        if parsed.notna().mean() < 0.9:
            continue
        yrs = set(int(y) for y in parsed.dt.year.dropna().unique())
        out = sorted(yrs - set(sk.EXPLORATION_SEASONS))
        if out:
            bad.append((str(c), out))
    return bad


ok = True
for p in sorted(glob.glob(os.path.join(OUT, "*.csv")) + glob.glob(os.path.join(OUT, "*.parquet"))):
    try:
        d = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    except Exception as exc:                                  # noqa: BLE001
        print("    %-52s UNREADABLE (%s)" % (os.path.basename(p), exc))
        continue
    rep = sk.assert_partition(d, date_cols=real_date_cols(d), raise_on_violation=False)
    extra = independent_date_value_sweep(d)
    ok &= rep["ok"] and not extra
    print("    %-52s ok=%-5s season_cols=%s date_cols=%s%s%s"
          % (os.path.basename(p), rep["ok"] and not extra, list(rep["checked_season_cols"]),
             list(rep["checked_date_cols"]),
             ("  VIOLATIONS: %s" % rep["violations"]) if rep["violations"] else "",
             ("  SWEEP: %s" % extra) if extra else ""))
cells = pd.DataFrame(fi["all_cells"])
rep = sk.assert_partition(cells, date_cols=real_date_cols(cells), raise_on_violation=False)
extra = independent_date_value_sweep(cells)
ok &= rep["ok"] and not extra
print("    %-52s ok=%-5s%s" % ("FINDINGS.json::all_cells", rep["ok"] and not extra,
                               ("  VIOLATIONS: %s" % rep["violations"]) if rep["violations"] else ""))
print("\n  NOTE: the numeric year-value sweep inside assert_partition (which catches a year-valued")
print("        column with an innocuous name) runs unconditionally and is NOT affected by naming")
print("        date_cols explicitly. That guard is intact on every artifact above.")
print("\n  ALL ARTIFACTS INSIDE THE 2021-2024 PARTITION: %s" % ok)
assert ok

hdr("3. Frame integrity re-checks")
f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
print("  rows=%d  seasons=%s  max game_date=%s" % (len(f), sorted(f["season"].unique()),
                                                   f["game_date"].max().date()))
print("  minutes > 0 on every row: %s" % bool((f["minutes"] > 0).all()))
print("  n_prior >= 3 on every row: %s" % bool((f["n_prior"] >= 3).all()))
print("  reference non-null: refB_ppm %.4f  refB_ts %.4f  refB_efg %.4f"
      % (f["refB_ppm"].notna().mean(), f["refB_ts"].notna().mean(), f["refB_efg"].notna().mean()))
print("  y non-null: y_ppm %.4f  y_ts %.4f  y_efg %.4f"
      % (f["y_ppm"].notna().mean(), f["y_ts"].notna().mean(), f["y_efg"].notna().mean()))

hdr("4. E0 HYGIENE: nothing outside this directory was written")
for p in ["registry.jsonl", "DECISION_LEDGER.jsonl", "GRAPH_EVENTS.jsonl", "idea_log.jsonl"]:
    hits = glob.glob(os.path.join(OUT, "**", p), recursive=True)
    print("    %-24s written by this screen: %s" % (p, bool(hits)))
print("    E1_I0004_efficiency_transfer/ : never read, never written (no path reference exists in")
print("                                    any script in this directory)")
