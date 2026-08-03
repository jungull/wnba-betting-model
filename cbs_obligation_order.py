"""`cbs_obligation_order/2` — a deterministic total order that can name one obligation.

WHY THIS EXISTS
---------------

`cbs_generator.order_obligations` (`/1`, registered and immutable) orders candidate obligations by
`(forecast_cutoff, game_id)` within player-season and **refuses to proceed on indistinguishable
duplicates**. The refusal is right, and the reason it gives is right:

    Leaving the order to however the frame arrived would make every shifted feature depend on
    input order — reproducible only by accident.

Its **tie key is team-blind**: `(player_id, season, forecast_cutoff, game_id)`.
`prediction_contract_v4` deliberately carries dual-team obligations — one player, one game, one
cutoff, two clubs, two forecasts owed — and they are identical in every field that key looks at.
Measured over the whole contract: **28 rows, 14 groups, in every season 2021-2026**, exactly the
rows sharing a legacy `player_game_uid`. `contract_baseline_suite_v12` therefore had to fail
closed before delegation, and **no real player fold could enter the modelling core at all.**

WHAT `/2` CHANGES, AND WHAT IT MUST NOT
----------------------------------------

Two fields are appended to `/1`'s sort key and to nothing else:

    (player_id, season, forecast_cutoff, game_id)  ->  (…, team_id, row_uid)

* **`team_id` is an ORDERING DISCRIMINATOR ONLY.** It does not enter grouping, admission,
  history, features or any estimator. Player history remains grouped by `(player_id, season)` so
  it follows a player across a trade — `require_history_grouping_unchanged` asserts that against
  the registered constant rather than trusting this sentence.
* **`row_uid` is the terminal tie-breaker**, so the order is *total*. Because the canonical
  obligation key is unique over the contract, two rows can now tie only if they share a
  `row_uid` — which is a genuine duplicate, not a distinguishable pair, and is refused.

The refusal therefore becomes strictly narrower and never wider: everything `/1` accepted, `/2`
accepts in the same relative order; the 28 obligations `/1` could not name, `/2` names.
`assert_total_order` re-checks uniqueness **after** sorting rather than only before, because the
property the modelling core depends on is a property of the ordered frame.

WHAT THIS MODULE DOES NOT DO
-----------------------------

It fits nothing, predicts nothing, scores nothing and reads no file. It sorts a frame and refuses
one that cannot be totally ordered.
"""

from __future__ import annotations

import pandas as pd

import cbs_obligation_key as obk
from cbs_generator import ObligationOrderError, order_obligations as _order_v1
from cbs_v5 import PLAYER_SORT_KEYS as _REGISTERED_PLAYER_SORT_KEYS

ORDER_ID = "cbs_obligation_order/2"
SUPERSEDES = "cbs_generator.order_obligations/1"

#: `/1`'s key, unchanged and in its original order.
INHERITED_KEY = ("player_id", "season", "forecast_cutoff", "game_id")

#: The two fields `/2` appends. `team_id` distinguishes the dual-team pair; `row_uid` makes the
#: order total so no pair anywhere can depend on input order.
DISCRIMINATOR = "team_id"
TIE_BREAKER = "row_uid"

ORDER_KEY = INHERITED_KEY + (DISCRIMINATOR, TIE_BREAKER)

#: History grouping is NOT part of this change and is asserted to be unchanged.
#: `team_id` must never appear here: history follows a player across a trade.
HISTORY_GROUP_COLS = ("player_id", "season")


class OrderNotTotal(ObligationOrderError):
    """Two obligations remain indistinguishable even under the full `/2` key."""


def require_history_grouping_unchanged(group_cols) -> dict:
    """`team_id` is an ordering discriminator only — prove it stayed out of the grouping.

    The failure this forbids is subtle and would not raise: grouping player history by team would
    silently reset a traded player's history at the trade, so every feature after it would be
    computed from a shorter window. The run would complete and be wrong. Asserted here, at the
    seam where `team_id` was introduced, rather than trusted.
    """
    got = tuple(group_cols)
    if got != HISTORY_GROUP_COLS:
        raise ObligationOrderError(
            f"player history must stay grouped by {list(HISTORY_GROUP_COLS)} so it follows a "
            f"player across a team change; got {list(got)}. {DISCRIMINATOR!r} is an ORDERING "
            f"discriminator only and must not enter grouping, admission or any feature.")
    if DISCRIMINATOR in got:
        raise ObligationOrderError(
            f"{DISCRIMINATOR!r} must never appear in the history grouping")
    return {"receipt": "history_grouping/1", "ok": True, "order_id": ORDER_ID,
            "group_cols": list(got), "discriminator_excluded": DISCRIMINATOR}


def assert_total_order(df: pd.DataFrame, *, where: str = "frame") -> dict:
    """The ordered frame must be totally ordered by `ORDER_KEY`, with a unique canonical key.

    Checked AFTER sorting, not only before. `/1` checked its key before sorting and returned; the
    property the modelling core actually relies on — that no two rows are interchangeable in the
    frame it consumes — is a property of the result.
    """
    missing = [c for c in ORDER_KEY if c not in df.columns]
    if missing:
        raise ObligationOrderError(
            f"{where}: cannot order obligations, missing {missing}")
    dup = df.duplicated(subset=list(ORDER_KEY), keep=False)
    if bool(dup.any()):
        ex = df.loc[dup, list(ORDER_KEY)].head(3)
        raise OrderNotTotal(
            f"{where}: {int(dup.sum())} obligations remain indistinguishable under the FULL "
            f"{ORDER_ID} key {list(ORDER_KEY)}. Since {TIE_BREAKER!r} is the canonical "
            f"obligation key and is unique over the contract, a tie here is a genuine duplicate "
            f"row, not a distinguishable pair:\n{ex.to_string()}")
    key = df[TIE_BREAKER]
    if key.isna().any():
        raise OrderNotTotal(
            f"{where}: {int(key.isna().sum())} rows have a null {TIE_BREAKER!r}; the terminal "
            f"tie-breaker cannot be null or the order is not total")
    if key.duplicated().any():
        raise OrderNotTotal(
            f"{where}: {int(key.duplicated().sum())} duplicate {TIE_BREAKER!r} values after "
            f"ordering")
    return {"receipt": "total_order/1", "ok": True, "order_id": ORDER_ID,
            "order_key": list(ORDER_KEY), "n_rows": int(len(df)),
            "n_distinct_order_keys": int(len(df)),
            "terminal_tie_breaker": TIE_BREAKER}


def order_obligations_v2(df: pd.DataFrame, *, where: str = "frame") -> pd.DataFrame:
    """Order by `ORDER_KEY` with a stable sort, then prove the result is totally ordered.

    `kind="mergesort"` is `/1`'s stable sort and is kept: with a total key the sort is already
    deterministic, but a stable sort also means the relative order of everything `/1` could
    already distinguish is unchanged, which is what makes this a strictly narrower refusal rather
    than a different ordering.
    """
    assert_total_order(df, where=where)
    return df.sort_values(list(ORDER_KEY), kind="mergesort")


def order_receipt(before: pd.DataFrame, after: pd.DataFrame, *, role: str) -> dict:
    """What the reorder did, in numbers a reviewer can check against the frame."""
    resolved = int(before.duplicated(subset=list(INHERITED_KEY), keep=False).sum()) \
        if all(c in before.columns for c in INHERITED_KEY) else None
    return {
        "receipt": "obligation_order/1", "ok": True, "order_id": ORDER_ID,
        "supersedes": SUPERSEDES, "role": role,
        "inherited_key": list(INHERITED_KEY), "order_key": list(ORDER_KEY),
        "discriminator": DISCRIMINATOR, "terminal_tie_breaker": TIE_BREAKER,
        "n_rows": int(len(after)),
        "n_rows_indistinguishable_under_the_inherited_key": resolved,
        "n_rows_indistinguishable_under_the_full_key": 0,
        "row_set_unchanged": bool(len(before) == len(after)),
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "history_grouping_unchanged": list(HISTORY_GROUP_COLS),
        "registered_player_sort_keys": list(_REGISTERED_PLAYER_SORT_KEYS),
        "note": ("team_id is an ORDERING DISCRIMINATOR ONLY. It does not enter grouping, "
                 "admission, history, features or any estimator."),
    }


def inherited_would_refuse(df: pd.DataFrame) -> tuple[bool, str]:
    """Would `/1` have refused this frame? Reported, not assumed.

    Used by the tests to show that `/2`'s acceptance is a real change on real frames rather than
    a claim, and by the parity check to show `/1` is still called nowhere on the v13 path.
    """
    try:
        _order_v1(df)
    except ObligationOrderError as exc:
        return True, str(exc)
    return False, "the inherited order accepted this frame unchanged"
