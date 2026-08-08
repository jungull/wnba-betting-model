"""SCREEN_TEMPLATE.py -- runnable skeleton for a new E0/E1 exploration screen.

COPY THIS FILE into your own screen directory and replace the DEMO DATA block with real loads.
Everything else is the ORDER OF OPERATIONS, and the order is the point:

    0. TIME-WINDOW TABLE      -- declare, for EVERY constructed feature, what window it reads
    1. check_manifest         -- per input artifact, BEFORE loading anything
    2. assert_partition       -- on COLUMN VALUES, immediately after every load/filter
    3. detect_grouping_level  -- find the level at which the feature actually varies
    4. reproduce published    -- if you are re-running a frozen screen, reproduce its number FIRST
    5. real statistic         -- under the adopted convention (plain unweighted OLS R2, D069)
    6. correct-level null     -- the verdict-carrying null
    7. row-level null         -- CONTRAST ONLY; publishes the inflation factor
    8. no-op placebo          -- prove your control is not the identity
    9. FINDINGS.json          -- emit, with every guard's output recorded

As shipped this runs end-to-end on SYNTHETIC demo data and writes to ./_demo_out/, so you can see
the whole pipeline work before you touch real data.

Run:  python SCREEN_TEMPLATE.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # <-- point at _screen_kit

import screenkit as sk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_demo_out")            # <-- REPLACE with your own screen directory
os.makedirs(OUT, exist_ok=True)

SCREEN_ID = "TEMPLATE_DEMO"                       # <-- REPLACE
SEED = 20260807
N_DRAWS = 300                                     # raise for a real screen


def hdr(s):
    print("\n" + "=" * 96)
    print(s)
    print("=" * 96)


# ===========================================================================================
# 0. TIME-WINDOW TABLE  -- MANDATORY. Fill this in BEFORE writing any feature code.
# ===========================================================================================
# For EVERY constructed column, declare exactly what window it reads.  Trap 2 exists because names
# lie: "leave-one-out", "expected", "pregame", "prior" and "baseline" have ALL appeared in this
# program on quantities that read the future.  A row here is a claim you must be able to defend by
# pointing at the construction code, and `future_leakage_probe` must agree with it.
#
#   reads_future=True is not automatically fatal -- but a dR2 measured OVER such a baseline is NOT
#   a forecasting increment and must never be published as one.
TIME_WINDOW_TABLE = [
    dict(column="own_pre",
         construction="expanding mean over the player's games STRICTLY BEFORE this game_date",
         window="(-inf, game_date)",
         reads_future=False,
         evidence="np.searchsorted(dates, date, side='left') -> strictly-before prefix"),
    dict(column="opp_strength",
         construction="opponent team rate over the opponent's games strictly before this date",
         window="(-inf, game_date)",
         reads_future=False,
         evidence="same strictly-before prefix machinery, keyed on opp_team_id"),
    # EXAMPLE OF A ROW YOU MUST NOT PUBLISH AN INCREMENT OVER:
    # dict(column="player_tendency_loo",
    #      construction="season total over ALL games minus this game",
    #      window="ENTIRE SEASON, including games after game_date",
    #      reads_future=True,
    #      evidence="full-season leave-one-out; confirmed by future_leakage_probe"),
]

FINDINGS = {
    "screen_id": SCREEN_ID,
    "r2_convention": ("plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean "
                      "(D069 adopted default)"),
    "partition": list(sk.EXPLORATION_SEASONS),
    "holdout_never_touched": list(sk.HOLDOUT_SEASONS),
    "screenkit_version": "1.0",
    "time_window_table": TIME_WINDOW_TABLE,
}


# ===========================================================================================
# DEMO DATA  -- REPLACE THIS WHOLE BLOCK with your real loads.
# ===========================================================================================
def build_demo_frame():
    rng = np.random.default_rng(SEED)
    n_games, per_game = 60, 18
    rows = []
    for gi in range(n_games):
        season = 2021 + gi % 4
        gval = rng.normal()                      # a GAME-level feature: one value per game
        for k in range(per_game):
            rows.append(dict(
                season=season,
                game_id=10_000 + gi,
                game_date=pd.Timestamp("%d-06-01" % season) + pd.Timedelta(days=int(gi / 4)),
                team_id=gi % 12 if k < per_game // 2 else (gi + 5) % 12,
                player_id=1000 + (k % (per_game // 2)),
                opp_strength=gval,               # <-- the feature under test (per GAME)
                own_pre=rng.normal(),            # <-- a legitimate pregame baseline covariate
            ))
    df = pd.DataFrame(rows)
    # outcome: driven by the baseline plus a GAME random effect; opp_strength has NO true effect
    game_effect = rng.normal(0.0, 1.5, n_games)
    df["y"] = (0.6 * df["own_pre"]
               + game_effect[df["game_id"] - 10_000]
               + rng.normal(0.0, 1.0, len(df)))
    return df


# ===========================================================================================
# 1. MANIFEST CHECK -- per input artifact, BEFORE you trust it (GRAPH_POLICY 13.2.2)
# ===========================================================================================
hdr("1. MANIFEST CHECK -- read from bytes this session, never cited from NOTES")
INPUT_ARTIFACTS = [
    # REPLACE with your real inputs, e.g.:
    #   os.path.join(REPO, "data", "masters", "master_player.parquet"),
    os.path.join(OUT, "demo_input.parquet"),      # deliberately has no manifest -> UNVERIFIABLE
]
manifest_records = {}
for path in INPUT_ARTIFACTS:
    rec = sk.check_manifest(path, verbose=True)
    manifest_records[os.path.basename(path)] = {k: v for k, v in rec.items() if k != "draws"}
    if rec["status"] == "UNUSABLE":
        sys.exit("13.2.2 FAIL: %s is artifact-granular. FILTERING DOES NOT HELP. Cannot use at "
                 "E0/E1." % path)
    if rec["status"] == "UNVERIFIABLE":
        print("    !! UNVERIFIABLE -- this is NOT a pass. Recording the status in FINDINGS.json; "
              "the coordinator must decide whether the screen may proceed.")
FINDINGS["manifest_checks"] = manifest_records


# ===========================================================================================
# 2. PARTITION ASSERT -- on COLUMN VALUES, right after every load and every filter
# ===========================================================================================
hdr("2. PARTITION ASSERT -- VALUE-based (a text/regex scan is the WRONG check)")
df = build_demo_frame()
df = df[df["season"].isin(sk.EXPLORATION_SEASONS)].copy()          # FILTER-POINT
partition_report = sk.assert_partition(df, verbose=True)           # raises on violation
FINDINGS["partition_check"] = {k: v for k, v in partition_report.items() if k != "draws"}


# ===========================================================================================
# 3. GROUPING-LEVEL DETECTION -- BEFORE you choose a null (trap 1)
# ===========================================================================================
hdr("3. GROUPING-LEVEL DETECTION -- where does the feature actually vary?")
FEATURE = "opp_strength"
BASELINE = ["own_pre"]
level_report = sk.detect_grouping_level(df, FEATURE, verbose=True)
GROUP_KEY = level_report["recommended_key_cols"] or sk.ROW_LEVEL
FINDINGS["grouping_level"] = {k: v for k, v in level_report.items() if k != "draws"}
print("    -> this screen will permute at: %s" % GROUP_KEY)


# ===========================================================================================
# 4. REPRODUCE THE PUBLISHED NUMBER  (only when re-running a frozen screen)
# ===========================================================================================
hdr("4. REPRODUCE-PUBLISHED-NUMBER STEP")
# If you are re-running a frozen screen, reproduce its published figure FIRST, under ITS
# convention, so that any later difference is attributable to your change and not to your harness.
# The frozen screens used the defective weighted R2; `wls_r2_DEFECTIVE` exists solely for this.
#   published = 0.004003                                   # from the frozen screen's run_log.txt
#   repro = sk.wls_r2_DEFECTIVE(y, X_full, w) - sk.wls_r2_DEFECTIVE(y, X_base, w)
#   assert abs(repro - published) < 1e-6, "harness does not reproduce the published number"
print("    (no frozen screen is being re-run by this template; step recorded as not-applicable)")
FINDINGS["reproduction"] = {"applicable": False,
                            "note": "new screen; nothing published to reproduce"}


# ===========================================================================================
# 5. REAL STATISTIC -- adopted convention (D069)
# ===========================================================================================
hdr("5. REAL STATISTIC -- plain unweighted OLS dR2")


def stat_fn(d):
    """dR2 of FEATURE over BASELINE. Must depend on the frame ONLY through its columns, and must
    NOT mutate `d` (permutation_null reuses one working copy across draws)."""
    y = d["y"].to_numpy(float)
    Xb = d[BASELINE].to_numpy(float)
    Xf = d[BASELINE + [FEATURE]].to_numpy(float)
    return sk.delta_r2_plain(y, Xb, Xf)


real = stat_fn(df)
r2_base = sk.r2_plain(df["y"].to_numpy(float), df[BASELINE].to_numpy(float))
print("    n = %d rows" % len(df))
print("    R2(baseline)      = %.6f" % r2_base)
print("    dR2(%s)  = %.6f" % (FEATURE, real))
FINDINGS["real"] = {"n": int(len(df)), "r2_base": float(r2_base), "dR2": float(real),
                    "baseline_cols": BASELINE, "feature_col": FEATURE}


# ===========================================================================================
# 6 + 7. CORRECT-LEVEL NULL, AND THE ROW-LEVEL NULL FOR CONTRAST
# ===========================================================================================
hdr("6+7. PERMUTATION NULLS -- correct level carries the verdict; row level is contrast only")
cmp = sk.null_width_comparison(stat_fn, df, GROUP_KEY, N_DRAWS, SEED,
                               feature_col=FEATURE, block_col="season", verbose=True)
FINDINGS["null"] = {
    "correct_level": {k: v for k, v in cmp["correct"].items() if k != "draws"},
    "row_level_NAIVE": {k: v for k, v in cmp["row_level"].items() if k != "draws"},
    "sd_inflation_correct_over_row": cmp["inflation"],
    "p_correct": cmp["p_correct"],
    "p_row_level_NAIVE": cmp["p_row_level_NAIVE"],
    "note": ("The row-level p is reported ONLY to expose the inflation factor and never carries a "
             "verdict. Cluster-robust standard errors are NOT an alternative to this: they moved t "
             "the WRONG way in two screens in this program."),
}
pd.DataFrame({"correct_level_draws": cmp["correct"]["draws"],
              "row_level_naive_draws": cmp["row_level"]["draws"]}) \
    .to_csv(os.path.join(OUT, "permutation_draws.csv"), index=False)


# ===========================================================================================
# 8. NO-OP PLACEBO -- prove your control actually does something
# ===========================================================================================
hdr("8. NO-OP PLACEBO DIAGNOSTIC")
noop = sk.noop_placebo(stat_fn, df, 25, verbose=True)
FINDINGS["noop_placebo"] = {k: v for k, v in noop.items() if k != "draws"}
if noop["is_noop"]:
    print("    (expected here: the identity transform IS a no-op. If you pass your own placebo "
          "transform and it comes back CONFIRMED NO-OP, your control tests nothing.)")


# ===========================================================================================
# 8b. FUTURE-LEAKAGE PROBE -- run on every baseline you publish an increment over (trap 2)
# ===========================================================================================
hdr("8b. FUTURE-LEAKAGE PROBE")
# Requires a suspect baseline AND a believed-clean one to contrast against. Example:
#   probe = sk.future_leakage_probe(df, "player_tendency_loo", "player_tendency_pregame",
#                                   ["player_id", "season"], "game_date", "y", verbose=True)
#   FINDINGS["leakage_probe"] = probe
print("    (this template's demo frame carries only one baseline, so there is nothing to")
print("     contrast. A REAL screen must run this on every baseline in TIME_WINDOW_TABLE.)")
FINDINGS["leakage_probe"] = {"applicable": False,
                             "note": "demo frame has a single pregame baseline"}


# ===========================================================================================
# 9. FINDINGS.json
# ===========================================================================================
hdr("9. FINDINGS.json")


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return [_jsonable(v) for v in o.tolist()]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


path = os.path.join(OUT, "FINDINGS.json")
with open(path, "w", encoding="utf-8") as fh:
    json.dump(_jsonable(FINDINGS), fh, indent=2)
print("    wrote %s" % path)
print("\nTEMPLATE RUN COMPLETE.")
