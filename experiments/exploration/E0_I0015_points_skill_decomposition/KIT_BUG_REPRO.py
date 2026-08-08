"""MINIMAL REPRODUCTION of a defect in the shared screen kit, found by its first real user.

*** THIS SCRIPT DOES NOT MODIFY THE KIT.  It only demonstrates the failure. ***

DEFECT: `screenkit.detect_grouping_level` raises TypeError on any BOOLEAN feature column.

WHERE: screenkit._constant_within, line ~302.
    if pd.api.types.is_numeric_dtype(s):            # <-- bool IS numeric in pandas
        spread = g.transform("max") - g.transform("min")   # <-- numpy bool subtract -> TypeError

    TypeError: numpy boolean subtract, the `-` operator, is not supported, use the bitwise_xor,
               the `^` operator, or the logical_xor function instead.

WHY IT MATTERS: binary pre-game flags are among the most common candidates in this program.  D076
    (E0_I0014) screened `is_fallback` / `is_cold_start` / `tm_b2b` / `tm_3in4` / `tm_first_meeting`
    / `tm_is_home` and TWO of its four surviving leads were the boolean `is_fallback` and
    `fallback_level`.  A new screen that follows the kit's own documented quick-start order --
    check_manifest, assert_partition, detect_grouping_level, permutation_null -- CRASHES on the
    third call the moment a boolean candidate is reached.  The kit's TESTS.py passes 49/49 because
    it only ever exercises float features.

    `permutation_null` inherits the same failure through the same helper whenever it is given a
    boolean feature and a non-row grouping level, so the crash is not confined to the detector.

WORKAROUND USED BY THIS SCREEN (E0_I0015): cast boolean candidates to float before the call.
    That is a caller-side patch, not a fix; the kit is outside this screen's write scope and was
    not touched.

SUGGESTED FIX (for whoever owns the kit -- NOT applied here): in `_constant_within`, branch on
    `pd.api.types.is_bool_dtype(s)` BEFORE the numeric branch and use the nunique path, or simply
    cast with `s = s.astype(float)` when the dtype is bool.  Then add a boolean-feature case to
    TESTS.py, which currently has none.
"""
import os
import sys

import numpy as np
import pandas as pd

KIT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\_screen_kit"
sys.path.insert(0, KIT)
import screenkit as sk

df = pd.DataFrame({
    "season": [2022] * 8,
    "game_id": ["g1", "g1", "g2", "g2", "g3", "g3", "g4", "g4"],
    "team_id": [1, 2, 1, 2, 1, 2, 1, 2],
    "player_id": [10, 20, 10, 20, 10, 20, 10, 20],
    "flag_bool": np.array([True, True, False, False, True, True, False, False]),
})
df["flag_float"] = df["flag_bool"].astype(float)

print("frame dtypes:")
print(df[["flag_bool", "flag_float"]].dtypes.to_string())
print("  pd.api.types.is_numeric_dtype(flag_bool) =",
      pd.api.types.is_numeric_dtype(df["flag_bool"]),
      "  <-- bool counts as NUMERIC, so the numeric branch is taken")

print("\n1) IDENTICAL data as float -- works:")
r = sk.detect_grouping_level(df, "flag_float", verbose=True)
print("   -> recommended level:", r["recommended_permutation_level"])

print("\n2) SAME data as bool -- raises:")
try:
    sk.detect_grouping_level(df, "flag_bool", verbose=True)
    print("   -> NO ERROR (defect not reproduced in this pandas version)")
except TypeError as exc:
    print("   TypeError: %s" % exc)
    print("   -> DEFECT REPRODUCED")

print("\n3) permutation_null inherits it through the same helper:")
def stat(d):
    return float(d["flag_bool"].astype(float).mean())
try:
    sk.permutation_null(stat, df, ["game_id"], 5, 1, feature_col="flag_bool", block_col="season")
    print("   -> NO ERROR")
except TypeError as exc:
    print("   TypeError: %s" % exc)
    print("   -> DEFECT REPRODUCED in permutation_null as well")

print("\n4) The caller-side workaround this screen used (cast to float) -- works:")
df["flag_bool_cast"] = df["flag_bool"].astype(float)
r = sk.detect_grouping_level(df, "flag_bool_cast")
print("   -> recommended level:", r["recommended_permutation_level"], " (no crash)")
