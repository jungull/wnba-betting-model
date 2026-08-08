"""E1_I0042 s01 -- THE WINDOW CENSUS.

Applies PREREG s1's admissibility rule (R1)+(R2) to the champion's OWN fold receipts and counts
the clean windows the partition allows.  The 2021 degeneracy is VERIFIED HERE FROM THE RECEIPT,
not inherited from E1_I0034 or E1_I0039.

The sealed seasons' receipts exist on disk and are DELIBERATELY NOT OPENED.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_base as R  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 60)

R.check_prereg()

R.hdr("1. CHAMPION FOLD RECEIPTS -- 2021-2024 ONLY.  2025/2026 receipts are NOT opened.")
present = sorted(fn for fn in os.listdir(R.SRC_CHAMP)
                 if fn.startswith("fold_receipt__") and fn.endswith(".json"))
print("  receipt files on disk: %s" % present)
for s in R.SEALED:
    fn = "fold_receipt__%d.json" % s
    print("  SEALED, NOT OPENED: %s  (exists=%s)" % (fn, fn in present))

rows = []
for s in R.EXPLORATION_SEASONS:
    p = os.path.join(R.SRC_CHAMP, "fold_receipt__%d.json" % s)
    d = json.load(open(p, encoding="utf-8"))
    assert int(d["season"]) == s, "receipt season mismatch"
    ts = [int(x) for x in d.get("train_seasons", [])]
    assert not (set(ts) & set(R.SEALED)), "PARTITION: receipt %d trains on a sealed season" % s
    rows.append(dict(season=s,
                     degenerate=bool(d["degenerate"]),
                     model_was_fitted=bool(d["model_was_fitted"]),
                     n_train_rows=int(d["n_train_rows"]),
                     n_test_rows=int(d["n_test_rows"]),
                     train_seasons=ts,
                     cold_start_declared_constant_only=bool(
                         d.get("cold_start_declared_constant_only", False)),
                     n_fallback_rows=int(d["n_fallback_rows"]),
                     minutes_fallback_levels=json.dumps(
                         d["obligation_completeness"]["e_minutes_given_active"]["fallback_levels"]),
                     minutes_n_fallback=int(
                         d["obligation_completeness"]["e_minutes_given_active"]["n_fallback"]),
                     fit_through_date=d["fit_through_date"]))
rec = pd.DataFrame(rows)
print()
print(rec.to_string(index=False))

R.hdr("2. ANCHORS A1-A4 -- the 2021 degeneracy verified FIRST-HAND from the receipt")
r21 = rec[rec.season == 2021].iloc[0]
R.anchor("A1  2021 degenerate", bool(r21.degenerate), True)
R.anchor("A2  2021 model_was_fitted", bool(r21.model_was_fitted), False)
R.anchor("A3  2021 n_train_rows", int(r21.n_train_rows), 0)
R.anchor("A4  2022 train_seasons", rec[rec.season == 2022].iloc[0].train_seasons, [2021])
# the decisive detail: EVERY 2021 minutes forecast is a level-4 constant fallback
lv21 = json.loads(r21.minutes_fallback_levels)
R.anchor("A1b 2021 minutes fallback levels", sorted(lv21.keys()), ["4"])
R.anchor("A1c 2021 minutes n_fallback == n_test", int(r21.minutes_n_fallback), int(r21.n_test_rows))
print("\n  2021 is degenerate on its own receipt: no model was fitted, no training rows existed,")
print("  and all %d minutes forecasts are level-4 constant fallbacks.  INHERITED FROM NOBODY."
      % int(r21.n_test_rows))

R.hdr("3. ADMISSIBILITY -- PREREG s1 (R1) and (R2), applied mechanically")
adm_r1 = {}
for _, r in rec.iterrows():
    adm_r1[int(r.season)] = bool((not r.degenerate) and r.model_was_fitted and r.n_train_rows > 0)
print("  (R1) champion fold not degenerate:")
for s in R.EXPLORATION_SEASONS:
    print("       %d  %s" % (s, "PASS" if adm_r1[s] else "FAIL"))

out = []
for s in R.EXPLORATION_SEASONS:
    pool = [t for t in R.EXPLORATION_SEASONS if t < s and adm_r1[t]]
    r2 = len(pool) > 0
    out.append(dict(scored_season=s, R1_champion_not_degenerate=adm_r1[s],
                    overlay_training_pool=pool, R2_has_admissible_prior=r2,
                    SCORABLE=bool(adm_r1[s] and r2),
                    reason=("champion fold degenerate" if not adm_r1[s]
                            else ("no admissible strictly-prior season for the overlay fit"
                                  if not r2 else "admissible"))))
adm = pd.DataFrame(out)
print()
print(adm.to_string(index=False))
adm.to_csv(os.path.join(R.OUT, "WINDOW_CENSUS.csv"), index=False)

scorable = [int(r.scored_season) for _, r in adm.iterrows() if r.SCORABLE]
print("\n  SCORABLE SEASONS: %s" % scorable)
assert scorable == list(R.ADMISSIBLE_SCORED), \
    "the receipts disagree with rr_base.ADMISSIBLE_SCORED (%s vs %s)" % (scorable,
                                                                         R.ADMISSIBLE_SCORED)

# maximal contiguous runs
windows, cur = [], []
for s in R.EXPLORATION_SEASONS:
    if s in scorable:
        cur.append(s)
    elif cur:
        windows.append(tuple(cur)); cur = []
if cur:
    windows.append(tuple(cur))
print("  MAXIMAL CONTIGUOUS CLEAN WINDOWS: %d  ->  %s" % (len(windows), windows))

R.hdr("4. WHAT A SECOND WINDOW WOULD HAVE REQUIRED, AND WHY IT DOES NOT EXIST")
print("""  2022 is the only candidate for a second window and it fails (R2), not (R1): its champion
  fold IS fitted, but the ONLY strictly-prior season is 2021, whose champion emitted a constant.
  Forcing 2022 through means fitting the redistribution overlay on residuals about a constant.
  E1_I0039 did exactly that and reported C at -12.56% on decision-stratum minutes with cross-window
  sign agreement of 0.64.  PREREG s1 forbids relaxing (R2), so that window is NOT run here as a
  replication; it is reported in WINDOWS.md as the known-bad alternative it is.

  A THIRD OBSERVATION, which weakens even the one window that survives: 2023's overlay training
  pool is the single season 2022, and 2022's OWN champion was trained on nothing but the degenerate
  2021 fold (train_seasons == [2021]).  The degeneracy is therefore not fully quarantined -- it is
  one step removed from the 2023 fold and two steps from the 2024 fold.  Stated in WINDOWS.md.""")

R.hdr("5. THE SPLIT THAT IS AVAILABLE -- and it is a SPLIT, not a second window")
print("""  The one clean window contains TWO DISJOINT SCORED FOLDS, 2023 and 2024, each with its own
  admissible training pool.  Scoring them separately is the strongest honest second test the
  partition allows, and this screen runs it.  It is NOT a second window and is never reported as
  one: 2024's overlay training pool CONTAINS 2023, so the two folds share fitted information in
  one direction.  Every table labels it PRIMARY_WINDOW_SPLIT.""")

R.dump({"receipts": rec.to_dict("records"), "admissibility": adm.to_dict("records"),
        "scorable_seasons": scorable, "n_clean_windows": len(windows),
        "windows": [list(w) for w in windows],
        "sealed_receipts_not_opened": ["fold_receipt__%d.json" % s for s in R.SEALED]}, "_s01.json")
print("\n  wrote WINDOW_CENSUS.csv, _s01.json")
