"""E1_I0039 s08 -- assemble FINDINGS.json from the artefacts on disk.  Computes nothing new."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402

O = B.OUT
lat = pd.read_csv(os.path.join(O, "STACK_LATTICE.csv"))
ov = pd.read_csv(os.path.join(O, "ROW_OVERLAP.csv"))
add = pd.read_csv(os.path.join(O, "additivity.csv"))
vac = pd.read_csv(os.path.join(O, "vacuous_split.csv"))
neg = pd.read_csv(os.path.join(O, "negative_and_threshold_strata.csv"))
frz = pd.read_csv(os.path.join(O, "intercept_frozen_attribution.csv"))
rec = pd.read_csv(os.path.join(O, "recalibration_share.csv"))
own = pd.read_csv(os.path.join(O, "C_on_own_rows.csv"))
rnd = pd.read_csv(os.path.join(O, "control_random_target.csv"))
t1 = pd.read_csv(os.path.join(O, "power_type_I.csv"))
w1 = pd.read_csv(os.path.join(O, "secondary_W1.csv"))
w1m = pd.read_csv(os.path.join(O, "secondary_W1_movement.csv"))
ordr = pd.read_csv(os.path.join(O, "order_sensitivity.csv"))
s02 = json.load(open(os.path.join(O, "_s02.json"), encoding="utf-8"))


def verdict(row):
    """DR1, using the INJECTION-VERIFIED floor carried from D116 -- labelled as CARRIED."""
    d, p, fl = row["dMAE"], row["p"], row["MDE80_injection_D116carried"]
    if p < 0.05 and abs(d) > fl:
        return "DECIDED_POSITIVE" if d > 0 else "DECIDED_NEGATIVE"
    return "NOT_ESTABLISHED"


lat = lat.copy()
lat["verdict_DR1_injection_floor_CARRIED"] = lat.apply(verdict, axis=1)
lat["verdict_if_analytic_floor_only"] = lat.apply(
    lambda r: ("DECIDED_POSITIVE" if (r["p"] < 0.05 and r["dMAE"] > r["MDE80_analytic"])
               else ("DECIDED_NEGATIVE" if (r["p"] < 0.05 and r["dMAE"] < -r["MDE80_analytic"])
                     else "NOT_ESTABLISHED")), axis=1)
lat.to_csv(os.path.join(O, "STACK_LATTICE.csv"), index=False)

F = {
 "screen": "E1_I0039_stacking",
 "question": ("Three separately validated improvements -- cold-start tiering (D092/D102), "
              "fallback routing to a tuned simple estimator (D094) and minutes redistribution "
              "above a threshold (D116) -- have never been measured together.  Do they compose, "
              "and how much of the result reaches the decision stratum?"),
 "prereg": {"file": "PREREG.md",
            "sha256": hashlib.sha256(open(os.path.join(O, "PREREG.md"), "rb").read()).hexdigest(),
            "added_after_hashing": [
                "s07 section 1 INTERCEPT-FROZEN ATTRIBUTION -- added after the vacuous split "
                "showed every component moving rows it does not treat.  Direction: it REDUCES "
                "the A and B decision-stratum numbers to EXACTLY ZERO and INCREASES C's minutes "
                "decision-stratum number from +0.0150 to +0.0253.  It weakened two headlines and "
                "strengthened one.",
                "s07 section 2 corrected injections -- added because the preregistered injection "
                "construction failed (see DEFECTS.md DEF-3/DEF-5).  Direction: it did NOT "
                "produce a usable self-derived floor, so every verdict still leans on D116's "
                "CARRIED factors, which is a WEAKER evidential position than preregistered.",
                "s06 section 2 threshold strata at freed>=30 and 0<freed<25 -- added to test "
                "D116's 30-minute threshold on this row set.  Direction: it CORROBORATED D116."],
            "dropped_after_hashing": []},
 "partition": {"exploration_seasons_used": [2021, 2022, 2023, 2024],
               "scored_window_primary": list(B.SCORED_W2),
               "sealed_never_opened": [2025, 2026],
               "regular_season_only": True,
               "guard": "value-level assert_partition after every load and every filter"},
 "conditioning": ("EVERY CELL CONTAINING COMPONENT C IS AN ORACLE-ON-ABSENCE CEILING.  Both "
                  "pre-game injury sources return UNVERIFIABLE from check_manifest and back no "
                  "number, so the absence indicator is REALISED, exactly as E1_I0034 declared."),
 "anchors_reproduced_before_any_new_statistic": {
     "count": 17, "all_exact_or_within_1e-6": True,
     "list": s02["anchors"],
     "A8_E1_I0034_P04_minutes": {"MAE_M0_published": 5.101386713527127,
                                 "MAE_M0_reproduced": 5.101386713527127,
                                 "dMAE_published": 0.09269264623364977,
                                 "dMAE_reproduced": 0.09269264623364926,
                                 "abs_delta": 5.135e-16}},
 "ROW_OVERLAP": {
     "universe_U": s02["universe"],
     "table": ov.to_dict("records"),
     "headline": ("A IS A STRICT SUBSET OF B (632 of 945, Jaccard 0.669) -- they are two "
                  "different replacements proposed for overlapping rows, so their composition "
                  "is a REDUNDANCY question and had to be measured.  A and C intersect on 48 "
                  "rows (0.53% of U) and B and C on 63 (0.70%) -- NEAR-EMPTY BY CONSTRUCTION, "
                  "because E1_I0034's REM requires >=3 strictly-prior same-season appearances "
                  "and the champion's fallback flag fires BELOW 3.  For those pairs the "
                  "stacking question is ARITHMETIC, and the lattice confirms it: "
                  "sum-of-parts / whole is 1.019 (AC) and 1.016 (BC).  "
                  "ZERO A rows and ZERO B rows are in the decision stratum; 1,051 C rows are.")},
 "LATTICE": lat.to_dict("records"),
 "additivity": add.to_dict("records"),
 "THE_HONEST_TOTAL": {
     "definition": ("the full three-component stack ABC, measured against the champion-plus-"
                    "walk-forward-intercept base on ONE common row set, both responses, both "
                    "strata, with the shared-recalibration share separated out"),
     "pooled_U_n": 9022,
     "decision_stratum_n": 3158,
     "minutes_pooled_dMAE": 0.381702, "minutes_pooled_pct": 7.280002,
     "minutes_decision_dMAE": 0.021781, "minutes_decision_pct": 0.501471,
     "minutes_decision_p": 0.026899,
     "minutes_decision_MDE80_injection_CARRIED": 0.033967,
     "minutes_decision_verdict": "NOT_ESTABLISHED -- below the carried injection floor",
     "pts_pooled_dMAE": 0.208909, "pts_pooled_pct": 4.869041,
     "pts_decision_dMAE": 0.000672, "pts_decision_pct": 0.013284, "pts_decision_p": 0.900605,
     "pts_decision_verdict": "NOT_ESTABLISHED -- nil",
     "minutes_decision_dMAE_intercept_frozen": 0.025822,
     "minutes_decision_pct_intercept_frozen": 0.594502,
     "pts_decision_dMAE_intercept_frozen": -0.005424,
     "on_C_own_treated_rows_in_decision_stratum": {
         "n": 1051, "minutes_dMAE": 0.077589, "minutes_pct": 1.729240, "minutes_p": 0.005499,
         "pts_dMAE": -0.016299, "pts_pct": -0.323586, "pts_p": 0.298175}},
 "DOES_IT_AGGREGATE": {
     "A_and_B": ("NO -- they are redundant by construction.  AB (+0.3660 minutes pooled) is "
                 "WORSE than B alone (+0.3828).  sum-of-parts/whole = 2.01.  A is a strict "
                 "subset of B, so stacking them adds nothing and the precedence rule costs "
                 "0.0168 minutes MAE against simply using B."),
     "A_or_B_with_C": ("YES, ARITHMETICALLY, AND ONLY ARITHMETICALLY.  AC and BC recover 98.1% "
                       "and 98.4% of the sum of their parts.  They do not interact because "
                       "they barely share rows."),
     "all_three": ("ABC (+0.3817 minutes pooled) is WORSE than the best single component "
                   "B (+0.3828).  The whole stack does not beat its best part on the pooled "
                   "minutes response."),
     "on_the_decision_stratum": ("NOTHING AGGREGATES.  A and B contribute EXACTLY ZERO there "
                                 "once the shared recalibration is frozen out, because they "
                                 "treat zero decision-stratum rows.  ABC frozen (+0.02582) is "
                                 "0.0005 above C frozen (+0.02529) -- the entire remainder is C.")},
 "controls": {
     "no_op_placebo": "dMAE EXACTLY 0.0, one distinct draw value, on both responses",
     "random_target": rnd.to_dict("records"),
     "negative_and_threshold_strata": neg.to_dict("records"),
     "vacuous_split": vac.to_dict("records"),
     "intercept_frozen_attribution": frz.to_dict("records"),
     "recalibration_share": rec.to_dict("records"),
     "C_on_own_rows": own.to_dict("records"),
     "type_I": t1.to_dict("records"),
     "order_sensitivity": ordr.to_dict("records")},
 "secondary_W1": {"note": ("The declared W1 secondary CANNOT be run under the primary training "
                           "rule: with MIN_TRAIN 2022 the 2022 season has no valid training "
                           "season and a W1 run returns W2 verbatim.  The version below trains "
                           "on 2021 -- THE FOLD THE CHAMPION'S RECEIPT DECLARES DEGENERATE -- "
                           "and is labelled accordingly.  Sign agreement with W2 is only "
                           "0.6429 of 28 cells and C REVERSES to -12.56% on decision-stratum "
                           "minutes.  This is the strongest counterweight in the screen."),
                  "sign_agreement": float(w1m["sign_agrees"].mean()),
                  "table": w1.to_dict("records"),
                  "movement": w1m.to_dict("records")},
 "power": {"analytic_rule": "MDE80 = 2.80 x null_sd -- UNDER ACTIVE SUSPICION (D113/D116)",
           "floor_used_for_every_verdict": ("MDE80_injection_D116carried = 2.80 x null_sd x "
                                            "D116's measured anti-conservatism factor "
                                            "(minutes 1.22, pts 3.40).  CARRIED FROM D116, "
                                            "NOT SELF-DERIVED -- see DEFECTS.md DEF-3/DEF-5."),
           "type_I_measured": t1.to_dict("records")},
 "no_production_change": ("NOTHING IS ENACTED.  All three components remain unauthorised and "
                          "this screen requests no authorisation.  The champion was scored, "
                          "never refitted."),
}
json.dump(B.jsonable(F), open(os.path.join(O, "FINDINGS.json"), "w", encoding="utf-8"),
          indent=1, sort_keys=False)
print("wrote FINDINGS.json (%d bytes)" % os.path.getsize(os.path.join(O, "FINDINGS.json")))
print("\nverdict counts under the CARRIED injection floor:")
print(lat.groupby(["response", "stratum", "verdict_DR1_injection_floor_CARRIED"]).size().to_string())
