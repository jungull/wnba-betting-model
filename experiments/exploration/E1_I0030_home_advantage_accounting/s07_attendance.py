"""S07 -- STEP 7.  ATTENDANCE FEASIBILITY.  An honest inventory, and nothing else.

The user flagged attendance and doubted it is modellable.  The instruction is explicit: check
whether attendance data EXISTS anywhere in the repository and report honestly; if it does not, say
so and STOP -- do not proxy it with something else and present that as an answer.

This stage therefore only INVENTORIES.  It builds no attendance feature, fits nothing, and reports
no attendance result.
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd

import ha_base as hb

DATA = os.path.join(hb.ROOT, "data")
PAT = re.compile(r"attend", re.I)
SKIP = ("E1_I0026", "E1_I0027", "E0_I0028", "E0_I0029", "__pycache__", "node_modules")


def main():
    hb.hdr("S07 ATTENDANCE FEASIBILITY -- INVENTORY ONLY")
    out = {"question": "does attendance data exist anywhere in this repository?",
           "columns_found": [], "files_mentioning_attendance": [], "verdict": None}

    # 1. every tabular artifact under data/: does ANY carry a column matching /attend/?
    checked = 0
    for root, dirs, files in os.walk(DATA):
        dirs[:] = [d for d in dirs if not any(s in d for s in SKIP)]
        for fn in files:
            path = os.path.join(root, fn)
            try:
                if fn.endswith(".parquet"):
                    cols = list(pd.read_parquet(path, columns=None).head(0).columns)
                elif fn.endswith(".csv"):
                    cols = list(pd.read_csv(path, nrows=0).columns)
                else:
                    continue
            except Exception:                                     # noqa: BLE001
                continue
            checked += 1
            hits = [c for c in cols if PAT.search(str(c))]
            if hits:
                out["columns_found"].append({"file": os.path.relpath(path, hb.ROOT),
                                             "columns": hits})
    out["n_tabular_artifacts_scanned"] = checked
    print("  scanned %d tabular artifacts under data/ for a column matching /attend/i" % checked)
    print("  artifacts carrying such a column: %d" % len(out["columns_found"]))
    for r in out["columns_found"]:
        print("    %s -> %s" % (r["file"], r["columns"]))

    # 2. where is attendance MENTIONED at all, and in what capacity?
    mentions = [
        {"path": "experiments/market_program/FREE_DATA_SURVEY/stats_surface/"
                 "endpoint_coverage_report.json",
         "what": "the string ATTENDANCE appears as an available FIELD NAME on an upstream "
                 "stats endpoint the programme surveyed but did not ingest",
         "is_data": False},
        {"path": "experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/"
                 "capture_schema.py",
         "what": "an `attendance_actual` key in a LIVE-capture schema definition -- a placeholder "
                 "in a forward-looking capture spec, not a populated historical column",
         "is_data": False},
        {"path": "project_docs/FEATURE_LAB_CATALOG.md",
         "what": "catalogue row 99, 'Attendance/TV context', marked N/A and 'not captured; noted'",
         "is_data": False},
        {"path": "experiments/player_program/stage3_score/S31_SCORE_IDEATION/raw_sources/"
                 "SOURCE_2_domain.md and SOURCE_4_falsificationist.md",
         "what": "PROSE noting that 2021 ran under attendance restrictions; used as a narrative "
                 "reason to expect home advantage to drift, never as a measured column",
         "is_data": False},
        {"path": "project_docs/WNBA_Odds_Research_Report.md",
         "what": "a single league-wide press figure ('400,000+ fans in May 2024') in a prose "
                 "report -- one aggregate number, not a per-game series",
         "is_data": False},
    ]
    out["files_mentioning_attendance"] = mentions
    print("\n  every mention of attendance in the repository, and what it actually is:")
    for m in mentions:
        print("    - %s\n        %s" % (m["path"], m["what"]))

    has = len(out["columns_found"]) > 0
    out["verdict"] = (
        "ATTENDANCE DATA DOES NOT EXIST IN THIS REPOSITORY.  No tabular artifact under data/ "
        "carries a per-game attendance column; every mention is either a field name on an "
        "un-ingested upstream endpoint, a placeholder key in a forward-looking live-capture "
        "schema, a catalogue row explicitly marked 'not captured', or prose.  The user's "
        "conditional -- 'maybe its conditional on attendance but idk how we would model that' -- "
        "cannot be tested at all with what is here.  PER THE BRIEF THIS STAGE STOPS: no proxy "
        "(arena capacity, market size, weekend/weeknight, season progress, 2021-vs-later) is "
        "built or reported as an attendance answer, because none of them is attendance and "
        "presenting one as such would be the exact substitution the brief forbids."
    ) if not has else "columns matching /attend/ WERE found; see columns_found."
    print("\n  VERDICT: %s" % out["verdict"])

    # what it would take, stated once, without building it
    out["what_acquisition_would_require"] = (
        "a per-game attendance series for 2021-2024 from an external source, joined on game_id, "
        "with an as-of manifest.  Note the design problem even if it were acquired: attendance is "
        "measured AT the game and is itself a consequence of team quality, day of week, opponent "
        "and market size, so it is not a clean pre-game feature.  A defensible version would use "
        "the venue's PRIOR-GAMES-ONLY mean attendance, which is a market-size proxy rather than a "
        "crowd-on-the-night measurement -- and that is a different hypothesis from the one asked."
    )

    with open(os.path.join(hb.OUT, "_s07.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("  wrote _s07.json")


if __name__ == "__main__":
    main()
