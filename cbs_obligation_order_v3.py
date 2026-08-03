"""`cbs_obligation_order/3` — the same total order, with two accounting claims made true.

WHY THIS EXISTS
---------------

`cbs_obligation_order/2` produces the right order and the supervisor accepted it. Two things it
*said* about itself were not true, and both were caught in review rather than by its own tests:

1. **It validated the wrong frame.** `order_obligations_v2` called `assert_total_order(df)` on the
   INPUT and then returned `df.sort_values(...)`. The docstring and the v13 suite both described
   this as re-asserting totality *after* sorting — "the property the modelling core relies on is a
   property of the ordered frame" — and the test that was supposed to prove it only searched the
   docstring for the word "after". The verdict happens to be identical either way, because sorting
   permutes rows and cannot create or remove a duplicate key. That makes the claim harmless and
   still false, and a check that reads a docstring is not a check.
2. **`row_set_unchanged` compared lengths.** `bool(len(before) == len(after))` is a row-COUNT
   equality wearing the name of a row-SET proof. Two frames of equal length with different
   canonical keys would have satisfied it.

`/2` is registered under `contract_baseline_suite_v13` and is left **byte-untouched**. This is a
new id, so `/2` documents remain valid `/2` documents; they are simply not `/3`.

WHAT `/3` CHANGES, AND WHAT IT DOES NOT
----------------------------------------

The ORDER is `/2`'s, unchanged: same key, same stable sort, same terminal tie-breaker. What
changes is when the assertion runs and what the receipt actually proves:

* `order_obligations_v3` sorts FIRST and validates the RETURNED frame. A caller now gets a frame
  that has itself been checked, not a frame whose pre-image was.
* `order_receipt_v3.row_set_unchanged` is a canonical-key SET comparison, and reports the
  symmetric difference when it fails rather than a bare `False`.

Everything else — the key, the discriminator, the tie-breaker, the history-grouping guard, the
inherited-refusal probe — is imported from `/2` rather than restated, so the two cannot drift.
"""

from __future__ import annotations

import pandas as pd

import cbs_obligation_order as _v2
from cbs_obligation_order import (DISCRIMINATOR, HISTORY_GROUP_COLS, INHERITED_KEY,  # noqa: F401
                                  ORDER_KEY, OrderNotTotal, TIE_BREAKER,
                                  assert_total_order, inherited_would_refuse,
                                  require_history_grouping_unchanged)

ORDER_ID = "cbs_obligation_order/3"
SUPERSEDES = _v2.ORDER_ID
INHERITED_SUPERSEDES = _v2.SUPERSEDES

#: `/2` remains valid; it is simply not `/3`.
REJECTED_ORDER_IDS: tuple[str, ...] = ()


def order_obligations_v3(df: pd.DataFrame, *, where: str = "frame") -> pd.DataFrame:
    """Sort by `ORDER_KEY`, then prove the RETURNED frame is totally ordered.

    The order is `/2`'s and the sort is `/2`'s stable mergesort. The difference is that the frame
    handed back is the frame that was checked. `/2` checked its input and returned its output;
    the two agree, but only the second is the object the modelling core consumes, and only the
    second is what the claim was about.
    """
    missing = [c for c in ORDER_KEY if c not in df.columns]
    if missing:
        raise _v2.ObligationOrderError(
            f"{where}: cannot order obligations, missing {missing}")
    out = df.sort_values(list(ORDER_KEY), kind="mergesort")
    assert_total_order(out, where=f"{where} (AFTER ordering)")
    return out


def order_receipt_v3(before: pd.DataFrame, after: pd.DataFrame, *, role: str) -> dict:
    """`/2`'s receipt, with `row_set_unchanged` actually comparing the row SET.

    `/2` compared lengths. A frame that lost one obligation and gained another would have passed.
    Here the canonical keys are compared as sets, and a failure reports what moved in each
    direction rather than a bare False that a reader has to go and investigate.
    """
    rec = dict(_v2.order_receipt(before, after, role=role))
    rec["order_id"] = ORDER_ID
    rec["supersedes"] = SUPERSEDES

    if TIE_BREAKER in before.columns and TIE_BREAKER in after.columns:
        b, a = set(before[TIE_BREAKER]), set(after[TIE_BREAKER])
        only_before, only_after = sorted(b - a), sorted(a - b)
        rec["row_set_unchanged"] = not only_before and not only_after
        rec["row_set_comparison"] = {
            "compared_on": TIE_BREAKER,
            "n_before": len(b), "n_after": len(a),
            "n_only_before": len(only_before), "n_only_after": len(only_after),
            "only_before": only_before[:16], "only_after": only_after[:16],
        }
    else:
        rec["row_set_unchanged"] = None
        rec["row_set_comparison"] = {
            "compared_on": None,
            "not_measurable": f"one of the frames has no {TIE_BREAKER!r} column",
        }
    rec["row_count_unchanged"] = bool(len(before) == len(after))
    rec["what_v2_actually_checked"] = (
        "row COUNT equality, reported under the name row_set_unchanged. Corrected here to a "
        "canonical-key SET comparison; the count is still reported, separately and under its own "
        "name.")
    return rec
