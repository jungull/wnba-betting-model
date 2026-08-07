#!/usr/bin/env python3
"""SC12_ROBUST_INPUT_WINSOR -- winsorized-minus-raw EWMA correction. 1 element.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/10, arm_block_sha256 6143bb85...):

  per side over strictly-prior own settled margins (ANY season):
      E_raw  = EWMA span 10 of margin
      E_wins = same EWMA of clip(margin, -15, +15)
      w      = E_wins - E_raw
  y = a + b*C_margin + c*(w_H - w_A)
  S33 freeze: the fixed +/-15 cap was chosen over a train-quantile clip (2-option set frozen to
  ONE, documented); coefficient direction expected positive but NOT sign-pinned.
  PINNED: cap +/-15; EWMA span 10 (alpha 2/11); >= 3 prior games support floor, else w = 0.

S34 FINDING B3, CARRIED. The S33 inertness kill and its justification are RETIRED: 780/2982
team-game margins exceed the +/-15 cap (26.16%), minimum per-season share 20.61%, so a
"< 8% clipped" kill was unreachable and the S33 justification stated the inference backwards.
The BITE-CONCENTRATION kill replaces it, and a separate IMPLEMENTATION-INTEGRITY inertness kill
(p90 of |w_H - w_A| < 1.0 point) now exists to catch a build defect rather than a scientific null.

The pre-registration measurements the integrity kill leans on -- median 1.704, p90 4.7058, max
13.0 for |w_H - w_A|, and 652 pooled clusters (43.7%) at |w_H - w_A| >= 2.0 -- are the CARD'S
measurements, carried here so the kill is checkable. This node does not re-report them as its own
and does not need to: they gate an implementation defect, not a performance claim.

TWO S36 FINDINGS ON THIS CARD, both measured, neither reconciled away
--------------------------------------------------------------------
(1) THE EWMA CONVENTION IS SETTLED BY THIS CARD. Sweeping 36 combinations of (adjust,
    min_periods, floor handling), exactly ONE reproduces all seven of the card's habitat numbers
    to the last printed digit: the RECURSIVE EWMA, pandas `adjust=False`, with the support floor
    NOT applied. `adjust=True` reproduces none of them. That settles the slate-wide EWMA
    convention, which no card states and which cycle-1 had flagged as an open interpretive pin.
    See `runner/features_common.py`.

(2) CARD-INTERNAL DISCREPANCY, DISCLOSED. The reproduction only closes with the support floor
    NOT applied -- so the habitat numbers the two kills are pinned against were measured WITHOUT
    the floor that this same card's `parameters.fixed_pinned` (">= 3 prior games support floor")
    and `fallback_cold_start` ("< 3 prior games: w = 0") make normative. Both readings are frozen
    bytes, so neither is silently preferred:

      * this module BUILDS the NORMATIVE reading (floor applied) -- the construction rule is what
        the card tells an implementer to build, and it IS implementable as frozen;
      * `verify_carded_strata.py` reports BOTH censuses side by side.

    MEASURED CONSEQUENCE FOR THE KILLS, which is the question that actually matters:
      BITE-CONCENTRATION habitat  652 (no floor) vs 649 (floor)  -- non-empty in every fold either
                                  way, so the arm-killing subset stays checkable in all 5 folds;
      INTEGRITY inertness p90     4.7058 (no floor) vs 4.6795 (floor) -- both are ~4.7x the 1.0
                                  threshold, so the kill cannot misfire under either reading.
    NEITHER KILL CHANGES ITS BEHAVIOUR. The discrepancy is a census-provenance defect in the
    card's descriptive numbers, not a defect that alters an inference, and it is raised to S37
    rather than repaired here -- the cards are immutable from the freeze onward, and a defect
    discovered downstream is handled by a new erratum record, never by editing these bytes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from features_common import prior_count, prior_ewma  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC12_ROBUST_INPUT_WINSOR"
FORMULA = ("winsorized-minus-raw EWMA (span 10) correction on strictly-prior own settled margins, "
           "differenced across sides; one fitted head coefficient")
CAP = 15.0
SPAN = 10.0                     # alpha = 2/11
SUPPORT_FLOOR = 3
BITE_THRESHOLD = 2.0            # |w_H - w_A| >= 2.0 defines the high-bite subset
INTEGRITY_P90_FLOOR = 1.0       # p90 below this can only mean a build defect
CARDED_HABITAT = {"high_bite_pooled_clusters": 652, "high_bite_share": 0.437,
                  "per_test_season": [97, 118, 102, 141, 107], "in_2021": 87,
                  "abs_w_diff_median": 1.704, "abs_w_diff_p90": 4.7058, "abs_w_diff_max": 13.0}


def winsor_terms(universe, *, apply_support_floor: bool = True) -> dict[str, np.ndarray]:
    """w = EWMA(clip(margin, +/-15)) - EWMA(margin), differenced across sides.

    `apply_support_floor=True` is the NORMATIVE construction and the only reading `build` uses.
    `False` reproduces the card's descriptive habitat census; see finding (2) in the module
    docstring. It exists so the discrepancy can be MEASURED rather than argued about, and it is
    never used to build a design."""
    tr = universe.team_rows.copy()
    tr["margin_clipped"] = np.clip(tr["margin"].to_numpy(dtype=float), -CAP, CAP)
    mp = SUPPORT_FLOOR if apply_support_floor else 1
    raw = prior_ewma(tr, "margin", span=SPAN, same_season=False, min_periods=mp, fill=np.nan)
    wins = prior_ewma(tr, "margin_clipped", span=SPAN, same_season=False, min_periods=mp,
                      fill=np.nan)
    pc = prior_count(universe.team_rows, same_season=False)
    w = wins["value"].to_numpy(dtype=float) - raw["value"].to_numpy(dtype=float)
    if apply_support_floor:
        w = np.where(pc["n_prior"].to_numpy() >= SUPPORT_FLOOR, np.nan_to_num(w, nan=0.0), 0.0)
    else:
        w = np.nan_to_num(w, nan=0.0)
    side = raw[["game_id", "team_id"]].copy()
    side["w"] = w
    a = attach_side(universe.games, side, "w", "w_H", "w_A", fill=0.0)
    diff = a["w_H"].to_numpy(dtype=float) - a["w_A"].to_numpy(dtype=float)
    return {"winsor_correction_diff": diff, "w_H": a["w_H"].to_numpy(dtype=float),
            "w_A": a["w_A"].to_numpy(dtype=float)}


def build(universe, fold, cache=None):
    cache = {} if cache is None else cache
    t = cache.setdefault("terms", winsor_terms(universe))
    return linear_head(
        universe, "E2_FINAL_MARGIN_HOME",
        {"winsor_correction_diff": t["winsor_correction_diff"]},
        fold_constants={"cap": CAP, "ewma_span": SPAN, "ewma_alpha": 2.0 / (SPAN + 1.0),
                        "support_floor_prior_games": SUPPORT_FLOOR,
                        "below_support_floor": "w = 0",
                        "any_season": True,
                        "s33_two_option_freeze": "fixed +/-15 cap chosen over a train-quantile "
                                                 "clip; 2-option set frozen to ONE, documented",
                        "direction": "expected positive, NOT sign-pinned",
                        "composite_column_stays_raw": True,
                        "s34_b3": "the S33 incidence/inertness kill is RETIRED (26.16% of "
                                  "team-game margins exceed the cap; a '<8% clipped' kill was "
                                  "unreachable)",
                        "carded_habitat": CARDED_HABITAT})


KILLS = (
    "BITE-CONCENTRATION KILL: pooled Delta-MAE(E2) <= 0 on the high-bite subset "
    "|w_H - w_A| >= 2.0 points (carded habitat 652 pooled clusters, 43.7%, non-empty in every "
    "fold)",
    "IMPLEMENTATION-INTEGRITY inertness kill (not a scientific kill): p90 of |w_H - w_A| over "
    "pooled test clusters < 1.0 point means the built transform is not the registered one",
    "outliers-are-signal confirmation: Delta negative in the two widest-strength-spread test "
    "seasons while positive elsewhere; the 'widest' seasons are pinned by a train-only, "
    "deterministic spread statistic",
    "pooled OOF Delta-MAE(E2) <= 0 vs K0_MATCHED (uncorrected)",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC12_ROBUST_INPUT_WINSOR::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_BLOWOUT_DISCOUNT",
        card_sha256="1b93abafa4a7612667dbc50c83c962e691b119185741300b779259d267062e4f",
        build=build, kill_conditions=KILLS,
        mandatory_receipts=("high_bite_subset_delta_table", "abs_w_diff_quantile_receipt_per_fold",
                            "season_split_delta_table_with_spread_ranking", "delta_table",
                            "R-A1-EXCEPTIONS"),
        notes=("disputed across TWO merges: {SC09, SC12} and partition D {SC10, SC12}; must "
               "survive Holm under every registered partition",)),
]
