"""MINIMAL REPRODUCTION -- screenkit defect K4, found by the kit's SEVENTH real user (E1_I0020).

  `screenkit.assert_partition` RAISES `PartitionViolation` ON CLEAN, WHOLLY IN-PARTITION DATA
  whenever the frame carries a YEAR-VALUED PLAYER ATTRIBUTE -- `draft_year`, `birth_year`,
  `college_grad_year`, `franchise_founded_year` -- because such a year necessarily lies BEFORE the
  2021-2024 exploration partition.

  This is the FIFTH instance in this program of a guard firing on a column that is not what its
  name suggests, and the SECOND instance INSIDE `assert_partition` itself (K0 was the first).

  IT IS NOT A REPEAT OF K0.  K0 was a NAME match with NO value gate: `mae_with_candidate` contains
  "candi-DATE", got parsed as epoch nanoseconds and came back as 1970.  The K0 fix installed the
  invariant "a substring match on a column NAME may only ever nominate a column for a VALUE test;
  it may never, by itself, cause a violation."  **K4 satisfies that invariant and fails anyway.**
  `draft_year` is nominated by the token "year", the value gate `_is_season_valued` is then asked
  "are these values years?", the honest answer is YES, and the column is checked against the
  partition -- which it legitimately predates.

  THE REAL DEFECT IS THE QUESTION THE VALUE GATE ASKS.
      `_is_season_valued` answers   "are these values plausible YEARS?"
      the partition needs to know   "is this column the OBSERVATION SEASON of the row?"
  Those are different questions, and every year-valued attribute of a person or an organisation
  answers YES to the first and NO to the second.

  DIRECTION MATTERS, AND THE CURRENT CHECK IGNORES IT.  The partition guard exists to stop 2025 and
  2026 -- the HOLDOUT, the FUTURE -- from entering exploration work.  `draft_year = 2008` is not a
  holdout leak; it cannot be one, because it is fourteen years in the PAST.  The current code treats
  "outside `allowed`" as one undifferentiated category and so cannot tell a future leak from a
  historical attribute.

  Run:  python KIT_DEFECT_K4_REPRO.py
"""
import os
import sys

import numpy as np
import pandas as pd

KIT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program" \
      r"\experiments\exploration\_screen_kit"
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402


def line(s=""):
    print(s)


line("=" * 100)
line("K4 REPRODUCTION 1 -- a frame that is ENTIRELY inside 2021-2024 and is rejected anyway")
line("=" * 100)
clean = pd.DataFrame({
    "player_id":  [1, 2, 3, 4, 5, 6],
    "season":     [2022, 2022, 2023, 2023, 2024, 2024],      # observation season: ALL in partition
    "game_date":  pd.to_datetime(["2022-05-08", "2022-06-01", "2023-05-19",
                                  "2023-07-02", "2024-05-14", "2024-08-30"]),
    "draft_year": [2008, 2015, 2002, 2021, 2019, 2024],      # player attribute: legitimately PAST
    "y_pts":      [10.0, 4.0, 22.0, 7.0, 13.0, 2.0],
})
line("frame:")
line(clean.to_string(index=False))
line("\nEVERY observation is in 2021-2024.  There is no 2025 or 2026 value anywhere.")
try:
    sk.assert_partition(clean, verbose=True)
    line("\n  -> PASS  (defect is FIXED)")
except sk.PartitionViolation as e:
    line("\n  -> RAISED PartitionViolation: %s" % e)
    line("  *** THIS IS THE DEFECT: clean data rejected. ***")

line()
line("=" * 100)
line("K4 REPRODUCTION 2 -- the value gate answers the WRONG QUESTION, and answers it correctly")
line("=" * 100)
ok, vals = sk._is_season_valued(clean["draft_year"])
line("  _is_season_valued(draft_year) -> is_season=%s  values=%s" % (ok, sorted(vals)))
line("  It is not wrong about the values.  They ARE years.  They are simply not THIS ROW'S SEASON.")
line("  Contrast the K0 case, where the value gate correctly says NO:")
k0 = pd.Series([0.31, 4.02, 1.77])
line("  _is_season_valued(mae_floats)  -> is_season=%s" % (sk._is_season_valued(k0)[0],))

line()
line("=" * 100)
line("K4 REPRODUCTION 3 -- DIRECTION: the guard cannot tell a PAST attribute from a FUTURE leak")
line("=" * 100)
past = clean.copy()
future = clean.copy()
future["draft_year"] = [2008, 2015, 2002, 2021, 2019, 2026]   # one genuinely 2026 value
for name, fr in [("all draft years <= 2024 (harmless history)", past),
                 ("one draft year == 2026 (would be worth a look)", future)]:
    r = sk.assert_partition(fr, raise_on_violation=False)
    line("  %-46s ok=%-5s violations=%s" % (name, r["ok"], r["violations"]))
line("""
  Both are rejected, with violation strings of the same shape.  A caller cannot distinguish them
  programmatically without re-parsing the message text -- and parsing the guard's own prose is the
  textual check this whole module exists to forbid.""")

line()
line("=" * 100)
line("K4 REPRODUCTION 4 -- the OBVIOUS WORKAROUND IS A FALSE-PASS DOOR (the K0 lesson, again)")
line("=" * 100)
leaky = pd.DataFrame({
    "season":       [2022, 2023, 2024],
    "game_date":    pd.to_datetime(["2022-05-08", "2023-05-19", "2024-05-14"]),
    "draft_year":   [2008, 2015, 2019],
    "source_season": [2022, 2023, 2026],     # A REAL LEAK, in a column the caller did not name
    "y_pts":        [10.0, 22.0, 13.0],
})
r = sk.assert_partition(leaky, raise_on_violation=False)
line("  default auto-detection      -> violations=%s" % r["violations"])
r2 = sk.assert_partition(leaky, season_cols=["season"], raise_on_violation=False)
line("  season_cols=['season']      -> violations=%s" % r2["violations"])
line("""
  `season_cols=['season']` silences the draft_year false alarm AND SILENCES THE REAL 2026 LEAK in
  `source_season`.  That is precisely the shape K0 named a "false-pass door": the workaround that
  makes the guard quiet is the workaround that makes the guard useless.  So the fix cannot be
  "callers should pass season_cols".

  (Note the numeric catch-all sweep at the end of assert_partition does NOT rescue this case: it
   only fires when a column's values lie ENTIRELY inside [2020, 2030], and `source_season` here
   does, so it is caught -- but a leak column also holding a 2019 value would escape it. The sweep
   is a backstop, not the check.)""")
r3 = sk.assert_partition(leaky, season_cols=["season", "source_season"], raise_on_violation=False)
line("  season_cols=['season','source_season'] -> violations=%s" % r3["violations"])

line()
line("=" * 100)
line("SUGGESTED FIX -- reported, NOT applied.  screenkit.py is shared and is not in this screen's")
line("write scope; two other agents are running against it.")
line("=" * 100)
line("""
  The repair that matches the module's existing style is to make the value gate answer the question
  the partition actually asks, and to make DIRECTION explicit:

  1. Split the season branch's verdict into two categories instead of one:
         VIOLATION_FUTURE   any flagged value >  max(allowed)   -- the holdout direction. FATAL.
         OUT_OF_RANGE_PAST  all flagged values <  min(allowed)  -- historical. NOT fatal by default
                            for an AUTO-DETECTED column; recorded in a new `historical_year_cols`
                            field with its values, so it is visible and auditable.
     A column the caller NAMES in `season_cols` stays STRICT IN BOTH DIRECTIONS -- naming it is an
     assertion that it is an observation season, and that assertion should be honoured loudly, which
     is exactly the asymmetry B2 already established for `date_cols`.

  2. Return the violations as STRUCTURED records -- {col, kind, values, direction} -- not only as
     formatted strings, so a caller can adjudicate without parsing prose.  (Reproduction 3 shows
     that today there is no non-textual way to tell the two cases apart.)

  3. Add `_ATTRIBUTE_YEAR_TOKENS = {"draft_year", "birth_year", "founded", "grad_year", "rookie_
     year", "debut_year"}` as a NOMINATION-ONLY hint that routes a column to category (1)'s
     historical branch by default.  Keep it nomination-only: per the K0 invariant, a name must never
     by itself decide anything, and here it would only choose which REPORT the value test writes to.

  A regression test that FAILS against the current module: `assert_partition` on REPRODUCTION 1 must
  return ok=True, while REPRODUCTION 4's `source_season` 2026 must still raise, and a `draft_year`
  of 2026 must still surface (as a flagged future value) rather than being waved through.

  WHAT E1_I0020 DID INSTEAD, so no result in this screen depends on the defect:
  `ct_base.assert_partition_adjudicated` calls the kit with raise_on_violation=False and applies the
  direction rule above in the SCREEN, with an explicit allowlist of adjudicated attribute columns;
  any flagged value >= 2025, and any flagged column not on the allowlist, is still FATAL.  The
  strict unmodified `sk.assert_partition` is ALSO run on the frame with the allowlisted attribute
  columns dropped, so the guard still runs at full strength over everything else.
""")
line("K4 REPRO COMPLETE.")
