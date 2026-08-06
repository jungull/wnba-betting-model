#!/usr/bin/env python3
"""feature_construction.py -- A23_rest_differential_contrast feature construction.

Implements EXACTLY the pinned clocks/constructions the frozen P35 task card names for A23
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A23_rest_
differential_contrast]):

  model: eta = log_exposure + beta * (f(rest_own) - f(rest_opp)); f = min(rest, c); no global
  intercept; TWO bundle elements (AI, OM), each fitted end-to-end as its own module instance.

  rest(t, g): days between game g and team t's PREVIOUS COMPLETED SAME-SEASON game, strictly
  earlier by (game_date, game_id) ascending (the program's canonical row ordering). Per the P35
  amendment (LEAKAGE L2 / OPERATIONAL OP-4), bundle_AI's prior-game rule was REDEFINED from
  "previous SCHEDULED game" to "previous COMPLETED game" -- the same reading bundle_OM already
  used ("most recent COMPLETED same-season game"). After the redefinition BOTH bundles compute
  the identical rest_own/rest_opp base quantity; they differ ONLY in cap c and opener rule (P35
  A23 card, bundles_frozen.distinction_honest, verbatim):

    bundle_AI: cap c = 7; opener rule = S7 preregistered training-support-based symmetric
               fallback (fold-level; can change fold evaluability, arm AND null identically).
    bundle_OM: cap c = 4; opener rule = assign cap value (fully rested), deterministic, no
               active-set rule.

  AMBIGUITY DISCLOSED, NOT RESOLVED SILENTLY (flagged for P37, per this program's own established
  practice for card-silent numeric readings -- e.g. A03/A07/A12/A16's identically-flagged
  ambiguities): the card names bundle_AI's opener rule as an S7 "symmetric fallback" but does not
  spell out the row-level numeric substitution a design matrix requires for every row (including
  test rows). This module's reading, chosen because it is the SAME pattern every other S7/empty-
  window rule in this program uses (A08 L_t:=0, A09 d_t:=0, A16 dev_team:=0 -- deterministic
  zero-fill on the undefined side, symmetric between own/opp so it privileges neither):

    bundle_AI: if EITHER side of a row (own or opp) has no strictly-earlier same-season game
               (an "opener"), the row's treatment CONTRAST f(rest_own)-f(rest_opp) := 0
               (deterministic, symmetric -- "symmetric fallback"). Separately, an S7
               ActiveSetRule requires >= 10 TRAINING clusters with a nonzero (non-degenerate)
               contrast per fold ("training-support-based ... fold-level; can change fold
               evaluability"); a fold below that floor is prospectively UNEVALUABLE, identically
               for arm and null (p27_rule() in arm_a23.py).
    bundle_OM: EACH side is handled independently: a side with no strictly-earlier same-season
               game gets f(rest_side) := c (the cap value, "fully rested"), deterministic,
               row-level, no active-set rule. This is exactly what the card states ("assign cap
               value (fully rested), deterministic, no active-set rule").

  precondition = "P23-receipted game_date join" (P35 A23 card, k0_matched_frozen amendment; NOT
  the cross-season franchise-continuity precondition -- A23 is same-season-only by construction
  and is absent from P33 shared_arm_invariants.p23_franchise_continuity_precondition's arm list,
  unlike A24). requires_franchise_continuity() therefore returns False (arm_a23.py), matching the
  A02/A03 precedent for arms absent from that list.

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness, no
same-row (current-game) dependency. STRICT LAGGING (a row's rest_own/rest_opp depend only on
OTHER rows with a strictly earlier game_date, of the SAME team and SAME season, never on the
row's own game outcome and never on any later game) is verified directly by TESTS.py.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# frozen P35 A23 card elements (bundle cap, verbatim)
ENUMERATED_BUNDLES: tuple[str, ...] = ("AI", "OM")
BUNDLE_CAP = {"AI": 7.0, "OM": 4.0}


# --------------------------------------------------------------------------------- rest(t, g)

def _to_day_axis(values) -> np.ndarray:
    """Coerce `game_date` to something day-differences are meaningful on, WITHOUT ever routing a
    plain numeric day-ordinal through pd.to_datetime (which reinterprets an int/float as
    nanoseconds-since-epoch and corrupts every downstream day-difference by nine orders of
    magnitude -- caught by this module's own strict-lagging identity test before this fix).
    Real, already-numeric day-ordinals (synthetic tests; any contract-schedule column already in
    day units) pass through unchanged. genuine datetime64/date-like/string columns are parsed via
    pd.to_datetime, exactly once, here."""
    v = np.asarray(values)
    if np.issubdtype(v.dtype, np.number):
        return v.astype(float)
    return pd.to_datetime(pd.Series(v)).to_numpy()


def compute_rest_and_opener(team_id, season, game_date, game_id) -> tuple[np.ndarray, np.ndarray]:
    """rest_days[i] = days since team_id[i]'s previous COMPLETED SAME-SEASON game, strictly
    earlier by (game_date, game_id) ascending; NaN and is_opener[i]=True when no such game exists
    (the team's first game of that season in the supplied frame).

    Deterministic and row-order-invariant: grouping is by (team_id, season); ordering within a
    group is (game_date, game_id) ascending with a stable (mergesort) tie-break, matching the
    program's canonical row ordering (possession_features.load_universe /
    construction_pins.a08_window_tie_break, reused rather than inventing a second convention, per
    the identical A16 precedent).
    """
    n = len(team_id)
    gd = _to_day_axis(game_date)
    is_datetime = np.issubdtype(gd.dtype, np.datetime64)
    df = pd.DataFrame({
        "team_id": np.asarray(team_id),
        "season": np.asarray(season),
        "game_date": gd,
        "game_id": np.asarray(game_id),
        "_orig_idx": np.arange(n),
    })
    df = df.sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
    prev_date = df.groupby(["team_id", "season"], sort=False)["game_date"].shift(1)
    delta = df["game_date"] - prev_date
    rest_days = (delta / np.timedelta64(1, "D")) if is_datetime else delta.astype(float)
    is_opener = prev_date.isna()

    out_rest = np.full(n, np.nan, dtype=float)
    out_opener = np.zeros(n, dtype=bool)
    out_rest[df["_orig_idx"].to_numpy()] = rest_days.to_numpy(dtype=float)
    out_opener[df["_orig_idx"].to_numpy()] = is_opener.to_numpy()
    return out_rest, out_opener


def f_cap(rest_days: np.ndarray, cap: float) -> np.ndarray:
    """f(rest) = min(rest, c). NaN (undefined / opener) rows pass through as NaN -- callers apply
    the bundle's own opener rule before or after this, never inside it (kept a pure, honest
    min-cap transform with no bundle-specific fallback baked in)."""
    r = np.asarray(rest_days, dtype=float)
    return np.minimum(r, float(cap))


def _lookup_by_opponent(game_id: np.ndarray, team_id: np.ndarray, opp_team_id: np.ndarray,
                        value: np.ndarray) -> np.ndarray:
    """value computed per (game_id, team_id) row, looked up at the SAME game_id's opponent row.
    Mirrors A16's opponent-lookup pattern exactly (two-sided game universe invariant). `value`
    may legitimately be NaN (an opener's own undefined rest); the failure check below is on
    lookup-KEY membership, never on the looked-up VALUE, so a real NaN is never mistaken for a
    missing opponent row.
    """
    lut = pd.Series(np.asarray(value, dtype=float),
                    index=pd.MultiIndex.from_arrays([np.asarray(game_id), np.asarray(team_id)]))
    if lut.index.has_duplicates:
        raise ValueError("A23: (game_id, team_id) is not unique in the supplied frame; opponent "
                         "lookup requires exactly one row per team per game")
    opp_key = pd.MultiIndex.from_arrays([np.asarray(game_id), np.asarray(opp_team_id)])
    missing = ~opp_key.isin(lut.index)
    if missing.any():
        raise ValueError("A23: opponent lookup failed for one or more rows -- every row's "
                         "opp_team_id must have its own row at the same game_id")
    return lut.reindex(opp_key).to_numpy(dtype=float)


def bundle_contrast(team_id, season, game_date, game_id, opp_team_id, *, bundle: str
                    ) -> dict[str, np.ndarray]:
    """The complete per-bundle construction: rest_own, rest_opp, f_own, f_opp (post opener rule),
    and the treatment contrast f_own - f_opp, all aligned to the input row order.

    bundle == "AI": cap 7; opener -> contrast forced to 0 on the row (symmetric fallback; see
        module docstring). f_own/f_opp are reported RAW (NaN on that side's own opener) for
        diagnostic/test visibility -- only the CONTRAST column is guaranteed finite.
    bundle == "OM": cap 4; opener -> f(rest) := cap on the opener side only, independently per
        side (deterministic, "fully rested"); f_own/f_opp are therefore always finite.
    """
    if bundle not in ENUMERATED_BUNDLES:
        raise ValueError(f"bundle={bundle!r} is not one of the frozen P35 elements "
                         f"{ENUMERATED_BUNDLES}")
    cap = BUNDLE_CAP[bundle]
    rest_own, opener_own = compute_rest_and_opener(team_id, season, game_date, game_id)
    f_own_raw = f_cap(rest_own, cap)
    rest_opp = _lookup_by_opponent(game_id, team_id, opp_team_id, rest_own)
    opener_opp = _lookup_by_opponent(game_id, team_id, opp_team_id, opener_own.astype(float)) > 0.5
    f_opp_raw = f_cap(rest_opp, cap)

    if bundle == "OM":
        f_own = np.where(opener_own, cap, f_own_raw)
        f_opp = np.where(opener_opp, cap, f_opp_raw)
        contrast = f_own - f_opp
    else:  # "AI"
        f_own, f_opp = f_own_raw, f_opp_raw
        either_opener = opener_own | opener_opp
        raw_contrast = np.where(either_opener, 0.0, f_own_raw - f_opp_raw)
        contrast = raw_contrast

    return {
        "rest_own": rest_own, "rest_opp": rest_opp,
        "opener_own": opener_own, "opener_opp": opener_opp,
        "f_own": f_own, "f_opp": f_opp,
        "contrast": contrast,
    }
