#!/usr/bin/env python3
"""SC06_SCHED_FATIGUE_DIFF -- pinned rest/travel index differential and its charter-era
interaction. 2 elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/5, arm_block_sha256 2ffce99e...):

  F = 1.0*1[B2B] + 0.5*1[3rd in 4 days] + 0.25*min(tz_crossed, 3)
      (all weights PINNED a priori, ZERO fitted parameters inside)
  E2: y = a + b*C_margin + g*era + beta*(F_H - F_A) + beta_era*(F_H - F_A)*era
  E3: identical features through bernoulli-logit
  era = 1[season >= 2024];  beta SIGN-PINNED NEGATIVE
  Era terms active only in folds train_lt_2025 / train_lt_2026 (declared structural deactivation
  elsewhere: zero training variance).

CUTOFF STATUS IS NOT UNCONDITIONAL. This arm's game_date lineage is frozen at
CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS -- never at unconditional CUTOFF_VALID (obligation O6).
The exception set (10 release-order displaced clusters + 6 clusters with no second-endpoint
witness) is a mandatory non-gating sensitivity receipt on every element, and on THIS arm it
additionally carries an arm-killing A1-SENSITIVITY kill.

C2 POWER STATEMENT (obligation O3 / S34 note C2). The era-instability kill is essentially
UNPOWERED, and the obligation makes printing that fact adjacent to any verdict the kill produces
MANDATORY. `era_split_receipt()` below is the ONLY way this module will emit an era-split table,
and it refuses to return one without the verbatim statement attached -- see
`runner/obligations.py`, `stamp_sc06_power_statement` and
`assert_sc06_era_verdict_carries_power_statement`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

import runner_constants as K  # noqa: E402
from _head import linear_head  # noqa: E402
from obligations import (assert_sc06_era_verdict_carries_power_statement,  # noqa: E402
                         stamp_sc06_power_statement)
from runner_interface import ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC06_SCHED_FATIGUE_DIFF"
FORMULA = ("pinned rest/travel index F = 1.0*B2B + 0.5*third-in-four + 0.25*min(tz_crossed, 3), "
           "differenced across sides, plus its 2024+ charter-era interaction")
W_B2B, W_3IN4, W_TZ = 1.0, 0.5, 0.25
TZ_CAP = 3
ERA_BOUNDARY = 2024
ERA_ACTIVE_FOLDS = ("train_lt_2025", "train_lt_2026")
SIGN_PIN = "beta_fatigue NEGATIVE"
#: Standard UTC offsets for the tz map. The card pins a "standard-offset map", so daylight saving
#: is deliberately NOT applied -- applying it would make the feature date-dependent in a way the
#: pin does not describe, and would make two games in the same city cross a different number of
#: zones depending on the month.
#:
#: The map covers EXACTLY the six IANA zones present in the byte-pinned team_cities.csv
#: (sha256 10a544fd...), enumerated rather than defaulted so that a new franchise in a seventh
#: zone fails closed instead of being silently assigned an offset:
#:   America/New_York -5, America/Toronto -5, America/Indiana/Indianapolis -5,
#:   America/Chicago -6, America/Phoenix -7, America/Los_Angeles -8.
#: Indianapolis and Toronto are Eastern (-5) at standard time; Phoenix is -7 year-round, which is
#: another reason the standard-offset reading is the coherent one.
STANDARD_OFFSETS = {"America/New_York": -5, "America/Toronto": -5,
                    "America/Indiana/Indianapolis": -5, "America/Chicago": -6,
                    "America/Denver": -7, "America/Phoenix": -7, "America/Los_Angeles": -8}


def _team_timezone_offsets() -> dict[int, int]:
    tc = pd.read_csv(K.artifact_path("data/reference/team_cities.csv"))
    out = {}
    for _, r in tc.iterrows():
        tz = str(r["timezone"])
        if tz not in STANDARD_OFFSETS:
            raise ValueError(f"timezone {tz!r} is not in the pinned standard-offset map")
        out[int(r["team_id"])] = STANDARD_OFFSETS[tz]
    return out


def fatigue_index(universe) -> pd.DataFrame:
    """F per (game_id, team_id). Zero fitted parameters; every weight is carded."""
    tz = _team_timezone_offsets()
    tr = universe.team_rows.sort_values(["team_id", "game_date", "game_id"],
                                        kind="mergesort").copy()
    d = pd.to_datetime(tr["game_date"])
    tr["_d"] = d
    prev1 = tr.groupby("team_id", sort=False)["_d"].shift(1)
    prev2 = tr.groupby("team_id", sort=False)["_d"].shift(2)

    gap1 = (tr["_d"] - prev1).dt.days
    gap2 = (tr["_d"] - prev2).dt.days
    b2b = (gap1 == 1).astype(float)
    third_in_4 = (gap2 <= 3).astype(float)

    # travel: the team's OWN venue timezone this game vs the previous game's venue timezone.
    venue = np.where(tr["is_home"].to_numpy() == 1, tr["team_id"].to_numpy(),
                     tr["opp_team_id"].to_numpy())
    tr["_venue_tz"] = [tz[int(v)] for v in venue]
    prev_tz = tr.groupby("team_id", sort=False)["_venue_tz"].shift(1)
    tz_crossed = (tr["_venue_tz"] - prev_tz).abs().fillna(0.0)
    tz_crossed = np.minimum(tz_crossed.to_numpy(dtype=float), TZ_CAP)

    # "previous game undefined -> F = 0 (max rest, card-declared convention)"
    first = prev1.isna().to_numpy()
    F = W_B2B * b2b.to_numpy() + W_3IN4 * third_in_4.to_numpy() + W_TZ * tz_crossed
    F = np.where(first, 0.0, F)
    F_rest_only = np.where(first, 0.0,
                           W_B2B * b2b.to_numpy() + W_3IN4 * third_in_4.to_numpy())
    return pd.DataFrame({"game_id": tr["game_id"].to_numpy(), "team_id": tr["team_id"].to_numpy(),
                         "season": tr["season"].to_numpy(), "F": F, "F_rest_only": F_rest_only})


def fatigue_terms(universe) -> dict[str, np.ndarray]:
    fi = fatigue_index(universe)
    g = attach_side(universe.games, fi, "F", "F_H", "F_A", fill=0.0)
    g = attach_side(g, fi, "F_rest_only", "Fr_H", "Fr_A", fill=0.0)
    diff = g["F_H"].to_numpy(float) - g["F_A"].to_numpy(float)
    era = universe.games["era_2024"].to_numpy(dtype=float)
    return {"fatigue_diff": diff, "ERA2024": era, "ERA2024:fatigue_diff": diff * era,
            "fatigue_diff_rest_only": g["Fr_H"].to_numpy(float) - g["Fr_A"].to_numpy(float)}


def _build(estimand: str):
    def build(universe, fold, cache=None):
        cache = {} if cache is None else cache
        t = cache.setdefault("terms", fatigue_terms(universe))
        fc = {"index_weights": {"B2B": W_B2B, "third_in_four_days": W_3IN4,
                                "tz_crossed_per_zone": W_TZ},
              "tz_cap": TZ_CAP, "era_boundary": ERA_BOUNDARY, "sign_pin": SIGN_PIN,
              "zero_fitted_parameters_inside_the_index": True,
              "standard_offset_map": STANDARD_OFFSETS,
              "dst_not_applied": ("the card pins a STANDARD-offset map; applying daylight saving "
                                  "would make the feature date-dependent in a way the pin does "
                                  "not describe"),
              "cutoff_status": "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS",
              "previous_game_undefined": "F = 0 (max rest, card-declared convention)"}
        era_on = fold["fold_id"] in ERA_ACTIVE_FOLDS
        fc["era_terms_active"] = era_on
        if era_on:
            return linear_head(universe, estimand,
                               {"fatigue_diff": t["fatigue_diff"],
                                "ERA2024:fatigue_diff": t["ERA2024:fatigue_diff"]},
                               extra_structural={"ERA2024": t["ERA2024"]},
                               indicator_cols=("ERA2024",), fold_constants=fc)
        fc["era_deactivation_reason"] = (
            "declared fold_local_fallback (registered before results): the era_2024 indicator has "
            "zero variance in this fold's training rows, so the era main effect AND the era "
            "interaction are dropped for this fold on BOTH sides; no row is dropped")
        return linear_head(universe, estimand, {"fatigue_diff": t["fatigue_diff"]},
                           fold_constants=fc)
    return build


def era_split_receipt(table: dict, element_id: str) -> dict:
    """THE ONLY sanctioned way to emit SC06's era-split table / era-kill verdict.

    Obligation O3 (S34 note C2): the power statement is MANDATORY and prints adjacent to any
    verdict this kill produces. A table without it is, in the obligation's own words, a reporting
    defect -- so this function attaches the verbatim statement and then re-checks that it is
    there before returning."""
    out = stamp_sc06_power_statement(
        {"schema": "s36_sc06_era_split/1", "element_id": element_id,
         "kill": "era instability", "era_split_table": table,
         "kill_scope": "kills the arm"}, element_id)
    assert_sc06_era_verdict_carries_power_statement(out)
    return out


KILLS = (
    "fitted beta wrong sign (positive) pooled, or wrong sign in >= 3 of 5 folds",
    "affected-subset failure: Delta <= 0 on the |F_H - F_A| >= 1 subset",
    "era instability: subset-Delta sign differs between pre-2024 and 2024+ AND the pooled Delta "
    "depends on the pre-2024 split alone (POWER STATEMENT MANDATORY, see era_split_receipt)",
    "A1-SENSITIVITY: removing the enumerated game_date exception clusters (10 release-order "
    "displaced + 6 without a second-endpoint witness) flips the SIGN of the affected-subset Delta",
)
RECEIPTS = ("per_fold_coefficient_table", "affected_subset_delta_table_with_subset_count",
            "era_split_table_WITH_POWER_STATEMENT", "R-A1-EXCEPTIONS")

ELEMENTS = [
    ElementSpec(
        element_id="SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_SCHEDULE_FATIGUE",
        card_sha256="24abe6f2864d2678cf680d9c0776f8eca87baf8d5ae772c4392e82470e7c1acc",
        build=_build("E2_FINAL_MARGIN_HOME"), kill_conditions=KILLS,
        mandatory_receipts=RECEIPTS, sign_pin=SIGN_PIN),
    ElementSpec(
        element_id="SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB", arm_id=ARM_ID,
        estimand="E3_HOME_WIN_PROB", primary_metric="brier_raw_model_probability",
        arm_kind="substantive_feature", family_primary="FAM_S2_SCHEDULE_FATIGUE",
        card_sha256="77aab51b32f4de4f868fd4c9d9c42f56d524e76a648d6ba96a9957421b515f20",
        build=_build("E3_HOME_WIN_PROB"), kill_conditions=KILLS,
        mandatory_receipts=RECEIPTS + ("R_SC08_FLOOR",), sign_pin=SIGN_PIN,
        notes=("R_SC08_FLOOR is registered here as a NON-GATING agreement receipt (O5)",)),
]
