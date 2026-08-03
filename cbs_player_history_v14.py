"""`cbs_player_history/14` — the prior-obligation count, defined by cutoff instead of by position.

WHY THIS EXISTS
---------------

`cbs_v8._prior_by_cutoff` is documented as *"Prior rows by CUTOFF — a scheduling fact, needing no
availability gate"* and is implemented as a **positional prefix**: within a `(player_id, season)`
group it counts every row the sort put earlier, whether or not that row's cutoff is strictly
earlier. For almost every obligation the two coincide, which is why it went unnoticed. For
`prediction_contract_v4`'s dual-team obligations — one player, one game, one cutoff, two clubs —
they do not: the sibling the sort puts second counts the first as prior.

v13 measured it and reported it. The supervisor ruled that measuring is not enough, because it
**changes an actual decision**: `n_prior_candidate_games` feeds `player_fallback_level` for
`p_active`, and two 2022 obligations land in a different band because of it.

THE DEFINITION, AS REGISTERED
------------------------------

    n_prior_candidate_games(row) = the number of candidate OBLIGATIONS in the same
                                   (player_id, season) whose forecast_cutoff is STRICTLY EARLIER
                                   than this row's forecast_cutoff.

Two things this is not:

* **It is not a count of distinct game ids.** Two obligations owed for the same earlier game —
  the dual-team case — contribute **two**. The quantity the fallback ladder reads is "how many
  forecasts has this player already owed this season", and a player who owed two forecasts for one
  contest owed two.
* **It is not availability-gated, and must not become one.** It is a scheduling fact, exactly as
  the inherited docstring says. The availability-gated quantities —
  `n_prior_available_obligations`, `n_prior_appearances`, `p_plays_prior` — are computed by
  `cbs_v8` and are correct; this module does not touch them.

WHAT THIS MODULE CHANGES, AND HOW NARROWLY
-------------------------------------------

`player_history_v14` **calls `cbs_v8.player_history_walk_forward`** and replaces exactly two of
its seven columns: `n_prior_candidate_games` and the flag derived from it,
`has_prior_obligation`. Every other column is passed through as the inherited function computed
it, untouched. `assert_only_the_count_moved` re-runs the inherited function and asserts,
column by column, that nothing else differs — so "one seam" is a checked property, not a promise.

Ties are the whole point, so they are handled explicitly: `searchsorted(..., side="left")` counts
strictly-earlier cutoffs only, which makes both members of an equal-cutoff group receive the same
count and neither count the other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import cbs_v8 as _core
from cbs_v7 import WalkForwardPlan

HISTORY_ID = "cbs_player_history/14"
SUPERSEDES = "cbs_v8._prior_by_cutoff (positional prefix)"

#: The only two columns this module recomputes. Everything else is the inherited function's.
REPLACED_COLUMNS = ("n_prior_candidate_games", "has_prior_obligation")

#: The grouping the count is taken within. Unchanged, and deliberately team-blind: a traded
#: player's obligations are still the same player's obligations.
GROUP_COLS = ("player_id", "season")

CUTOFF_COL = "forecast_cutoff"

COUNT_DEFINITION = (
    "the number of candidate OBLIGATIONS in the same (player_id, season) whose forecast_cutoff "
    "is STRICTLY EARLIER than this row's forecast_cutoff. Not a count of distinct game ids: two "
    "obligations owed for one earlier contest contribute two. Not availability-gated: it is a "
    "scheduling fact, and the availability-gated quantities are cbs_v8's and are untouched.")


class PriorCountError(RuntimeError):
    """The strict-cutoff prior count could not be computed, or the seam was not confined."""


def strict_prior_obligation_count(frame: pd.DataFrame, plan: WalkForwardPlan) -> np.ndarray:
    """Per row of `plan.order`, the count of strictly-earlier-cutoff obligations in its group.

    Computed over `plan.order` so it aligns with every other column the inherited history frame
    produces, and grouped on `plan.group_key`, which is the plan's own record of the grouping it
    was built with — not a constant restated here that could drift from the plan it is indexed
    against.
    """
    if CUTOFF_COL not in frame.columns:
        raise PriorCountError(f"cannot count prior obligations without {CUTOFF_COL!r}")
    cut = pd.to_datetime(frame[CUTOFF_COL], utc=True, errors="coerce").reindex(plan.order)
    if cut.isna().any():
        raise PriorCountError(
            f"{int(cut.isna().sum())} rows have an unparseable {CUTOFF_COL!r}; a prior count "
            f"over an undefined cutoff is undefined")
    values = cut.to_numpy()

    by_group: dict = {}
    for i, g in enumerate(plan.group_key):
        by_group.setdefault(g, []).append(i)

    out = np.zeros(len(plan.order), dtype=int)
    for members in by_group.values():
        idx = np.asarray(members, dtype=int)
        vals = values[idx]
        order = np.sort(vals)
        # side="left" counts only STRICTLY earlier cutoffs: an equal cutoff is not prior, so both
        # members of an equal-cutoff group get the same answer and neither counts the other.
        out[idx] = np.searchsorted(order, vals, side="left")
    return out


def player_history_v14(frame: pd.DataFrame, plan: WalkForwardPlan) -> pd.DataFrame:
    """The inherited history frame with exactly the prior-obligation count corrected."""
    hist = _core.player_history_walk_forward(frame, plan)
    counts = strict_prior_obligation_count(frame, plan)
    aligned = pd.Series(counts, index=plan.order).reindex(frame.index)
    out = hist.copy()
    out["n_prior_candidate_games"] = aligned.astype(int)
    out["has_prior_obligation"] = out["n_prior_candidate_games"] > 0
    return out


def assert_only_the_count_moved(frame: pd.DataFrame, plan: WalkForwardPlan) -> dict:
    """Prove the seam is confined: re-run the inherited function and diff column by column.

    "One seam" is worth nothing as an assurance. This recomputes the inherited history frame and
    the v14 one over the same inputs and asserts that every column outside `REPLACED_COLUMNS` is
    identical, so a future edit that quietly touched an availability-gated quantity would be
    caught here rather than in a forecast.
    """
    inherited = _core.player_history_walk_forward(frame, plan)
    corrected = player_history_v14(frame, plan)
    if list(inherited.columns) != list(corrected.columns):
        raise PriorCountError(
            f"the corrected history frame has different columns: "
            f"{sorted(set(corrected.columns) ^ set(inherited.columns))}")

    moved, unchanged = [], []
    for col in inherited.columns:
        same = inherited[col].astype(object).equals(corrected[col].astype(object))
        (unchanged if same else moved).append(col)
    unexpected = [c for c in moved if c not in REPLACED_COLUMNS]
    if unexpected:
        raise PriorCountError(
            f"the prior-count seam is not confined: {unexpected} also changed. Only "
            f"{list(REPLACED_COLUMNS)} may differ from the inherited history frame.")

    delta = (corrected["n_prior_candidate_games"].astype(int)
             - inherited["n_prior_candidate_games"].astype(int))
    if (delta > 0).any():
        raise PriorCountError(
            f"{int((delta > 0).sum())} rows count MORE prior obligations under the strict-cutoff "
            f"rule than under the positional prefix, which is impossible: a strictly-earlier "
            f"cutoff is a subset of an earlier position")
    return {
        "receipt": "prior_count_seam/1", "ok": True, "history_id": HISTORY_ID,
        "replaced_columns": list(REPLACED_COLUMNS),
        "columns_unchanged": unchanged,
        "n_rows": int(len(frame)),
        "n_rows_corrected": int((delta != 0).sum()),
        "n_rows_overcounted_by_the_positional_prefix": int((delta < 0).sum()),
        "max_overcount": int(-delta.min()) if len(delta) else 0,
        "count_definition": COUNT_DEFINITION,
        "grouping": list(GROUP_COLS),
        "availability_gated_columns_untouched": [
            c for c in ("n_prior_available_obligations", "n_prior_appearances",
                        "p_plays_prior", "has_prior_appearance",
                        "has_prior_available_obligation") if c in unchanged],
    }


def equal_cutoff_agreement(frame: pd.DataFrame, plan: WalkForwardPlan) -> dict:
    """Every equal-cutoff group must receive ONE prior count, shared by all its members.

    This is the property the whole correction exists for, so it is measured directly rather than
    inferred from the definition: group the frame on `(player_id, season, forecast_cutoff)` and
    assert the corrected count is constant within every group of size > 1.
    """
    corrected = player_history_v14(frame, plan)
    d = frame.assign(_n=corrected["n_prior_candidate_games"].to_numpy())
    key = [*GROUP_COLS, CUTOFF_COL]
    if any(c not in d.columns for c in key):
        return {"receipt": "equal_cutoff_agreement/1", "ok": True,
                "not_measurable": f"frame lacks {[c for c in key if c not in d.columns]}"}
    sizes = d.groupby(key)["_n"].agg(["size", "nunique"])
    ties = sizes[sizes["size"] > 1]
    disagreeing = ties[ties["nunique"] > 1]
    return {
        "receipt": "equal_cutoff_agreement/1", "ok": len(disagreeing) == 0,
        "history_id": HISTORY_ID,
        "n_equal_cutoff_groups": int(len(ties)),
        "n_rows_in_equal_cutoff_groups": int(ties["size"].sum()) if len(ties) else 0,
        "n_groups_whose_members_disagree": int(len(disagreeing)),
        "problems": ([f"{int(len(disagreeing))} equal-cutoff groups whose members received "
                      f"different prior counts"] if len(disagreeing) else []),
        "note": ("both members of an equal-cutoff pair must receive the same count, and neither "
                 "may count the other. side='left' on the sorted cutoffs is what makes that "
                 "true rather than nearly true."),
    }
