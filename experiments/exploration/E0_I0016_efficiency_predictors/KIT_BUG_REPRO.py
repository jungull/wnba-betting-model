"""MINIMAL REPRODUCTION -- screenkit.assert_partition false-positives on a column named "candidate".

*** THIS IS TRAP 3 IN A NEW SHAPE, INSIDE THE FUNCTION BUILT TO PREVENT TRAP 3. ***

WHAT HAPPENS
    `assert_partition` auto-detects date columns by NAME:

        cand_date = [c for c in df.columns if "date" in str(c).lower()]

    The word "candi-DATE" contains "date".  Every column this program names `candidate`,
    `n_candidates`, `mae_with_candidate`, `candidate_id`, ... is therefore treated as a date column.
    It is then parsed with `pd.to_datetime(df[c], errors="coerce")`, which on a FLOAT column does
    not fail -- it silently interprets the floats as nanoseconds since the epoch, yielding year
    1970 -- and 1970 is outside the 2021-2024 partition, so `PartitionViolation` is raised.

WHY IT MATTERS, AND WHY IT IS NOT MERELY COSMETIC
    The failure direction is conservative (a false ALARM, not a false PASS), so it cannot let a
    2025/2026 row through.  But the remedy a hurried caller reaches for is
    `assert_partition(df, date_cols=[])`, which DISABLES THE DATE CHECK ENTIRELY -- and that is a
    false-pass door.  A guard that cries wolf on the program's single most common column name
    trains callers to switch it off.

    "candidate" is not an unlucky choice of word here.  It is the vocabulary of every exploration
    screen in this program: candidate lists, candidate columns, per-candidate p-values.  This will
    recur.

THE ASYMMETRY THAT IS THE ACTUAL DEFECT
    The SEASON branch already has a value-plausibility guard, `_is_season_valued`, added precisely
    because columns NAMED `_team_season_2025` held dR2 draws near 1e-4.  Its regression test is in
    TESTS.py and it passes.
    The DATE branch has NO EQUIVALENT GUARD.  Name-matched, parsed, flagged.  The hardening was
    applied to one branch and not the other, and `pd.to_datetime` on floats never raises, so
    nothing surfaces the mistake.

SUGGESTED FIX (mirrors what the season branch already does)
    Require a name-matched date column to be DATE-VALUED before checking it:
      * accept datetime64 dtype outright;
      * for object/string columns, require a high parse-success rate under `pd.to_datetime`;
      * for NUMERIC columns, refuse to interpret the values as epoch nanoseconds at all -- record
        them in `skipped_name_only` exactly as the season branch does, with the same wording
        ("name is date-like but VALUES are not dates").
    A caller who genuinely stores dates as epoch integers can pass `date_cols=[...]` explicitly,
    which is the same escape hatch the season branch offers.

RUN:  python KIT_BUG_REPRO.py     (exit 0 = defect reproduced as described)
"""
import os
import sys

import numpy as np
import pandas as pd

KIT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\_screen_kit"
sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

print("=" * 100)
print("REPRO 1 -- a clean 2021-2024 frame with a column named 'candidate' RAISES")
print("=" * 100)
df = pd.DataFrame({
    "season": [2021, 2022, 2023, 2024],
    "game_date": pd.to_datetime(["2021-06-01", "2022-06-01", "2023-06-01", "2024-06-01"]),
    "candidate": ["A01_opp_efg_allowed", "B05_matchup_fouldraw", "C07_pl_usage_rank", "G01_noise"],
    "mae_with_candidate": [0.1234, 0.2345, 0.3456, 0.4567],
    "n_candidates": [44, 44, 44, 44],
})
print("  frame:\n%s\n" % df.to_string(index=False))
try:
    sk.assert_partition(df, verbose=True)
    print("  -> NO EXCEPTION (defect not reproduced)")
    raised = False
except sk.PartitionViolation as exc:
    raised = True
    print("  -> RAISED PartitionViolation: %s" % exc)

print("\n  every value in this frame is inside 2021-2024. The only columns that failed are the ones")
print("  whose NAMES contain the substring 'date' by way of the word 'candi-DATE'.")
assert raised, "expected the false positive"

print("\n" + "=" * 100)
print("REPRO 2 -- the mechanism, step by step")
print("=" * 100)
for name in ["candidate", "mae_with_candidate", "n_candidates", "update_flag", "validated"]:
    print("  'date' in %-22r -> %s" % (name, "date" in name.lower()))
print()
floats = pd.Series([0.1234, 0.2345, 0.3456])
parsed = pd.to_datetime(floats, errors="coerce")
print("  pd.to_datetime(pd.Series([0.1234, 0.2345, 0.3456])) does NOT raise; it returns")
print("    %s" % list(parsed.astype(str)))
print("  year values -> %s   (1970, i.e. the epoch, which is outside every real partition)"
      % sorted(set(int(y) for y in parsed.dt.year.dropna().unique())))

print("\n" + "=" * 100)
print("REPRO 3 -- the SEASON branch already guards against exactly this; the DATE branch does not")
print("=" * 100)
df2 = pd.DataFrame({
    "season": [2021, 2022],
    # NAME is season-like, VALUES are dR2 draws.  The season branch SKIPS this (guarded).
    "_team_season_2025": [1.2e-4, 3.4e-4],
    # NAME is date-like (candi-DATE), VALUES are MAE numbers.  The date branch FLAGS it (unguarded).
    "candidate_mae": [0.11, 0.22],
})
rep = sk.assert_partition(df2, raise_on_violation=False, verbose=True)
print("\n  skipped_name_only (the GUARDED branch): %s" % list(rep["skipped_name_only"]))
print("  checked_date_cols (the UNGUARDED branch): %s" % list(rep["checked_date_cols"]))
print("  violations: %s" % rep["violations"])
assert "_team_season_2025" in rep["skipped_name_only"], "season guard should have skipped it"
assert "candidate_mae" in rep["checked_date_cols"], "date branch should have (wrongly) checked it"
assert rep["violations"], "date branch should have (wrongly) flagged it"
print("\n  -> ASYMMETRY CONFIRMED: the season branch skips a name-only match; the date branch does not.")

print("\n" + "=" * 100)
print("REPRO 4 -- the workaround is a FALSE-PASS DOOR, which is why this is worth fixing")
print("=" * 100)
bad = pd.DataFrame({
    "season": [2021, 2022],
    "game_date": pd.to_datetime(["2021-06-01", "2026-06-01"]),   # <-- a REAL 2026 violation
    "candidate": ["A01", "B05"],
})
rep_ok = sk.assert_partition(bad, raise_on_violation=False)
print("  with the default date detection, the real 2026 date IS caught: violations=%s"
      % rep_ok["violations"])
rep_off = sk.assert_partition(bad, date_cols=[], raise_on_violation=False)
print("  with the caller's natural workaround date_cols=[], the SAME frame passes: ok=%s violations=%s"
      % (rep_off["ok"], rep_off["violations"]))
assert rep_ok["violations"] and not rep_off["violations"]
print("\n  -> the obvious way to silence the false alarm silences the TRUE alarm as well.")
print("\nDEFECT REPRODUCED AS DESCRIBED.")
