#!/usr/bin/env python3
"""feature_construction.py -- A24_rest_level_symmetric feature construction.

Implements EXACTLY the pinned clock/window/constant the frozen P35 task card names for A24
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A24_rest_level_
symmetric], carrying P33_PREREGISTRATION_DRAFT/SPEC.json sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093 by hash reference):

  model: eta = log_exposure + coef * x
  rest(t, g)  = min(days since team t's MAX PRIOR CONTRACT GAME DATE, cap_days=10)
  x(t, g)     = (rest(t, g) + rest(opp(g, t), g)) / 2
  mu          = exp(eta); no global intercept.

  hyperparameters (P33/P35, verbatim): {"fixed": {"cap_days": 10}, "enumerated": {},
  "handling": "cap frozen by source; differs from A23's caps - D6 preserved"}. Single enumeration
  element -- one module instance IS the whole arm (RUNNER_INTERFACE.md section 1: "{} for
  single-element arms").

CLOCK READING (inferred from the card's own wording, flagged explicitly -- NOT invented from
nothing): the model formula says "days since max prior CONTRACT game date of t" -- the word
CONTRACT is the same word P35 shared_frozen_amendments.construction_pins.n_clock_pin uses to name
the 2,990-row team_possession_prior_v1 CONTRACT SCHEDULE ("n_i / n_t / n_cur / m_prev and every
other prior-game COUNT are computed on the CONTRACT SCHEDULE ... INCLUDING the four
universe-excluded 2021 opening-day games"). A24's own "rest" quantity is not literally one of the
named COUNT variables the pin enumerates, but the card's deliberate choice of the word "contract"
(rather than "prior game" or "prior universe row") is read here as the SAME pin extended to this
arm's own clock: rest(t, g) is computed against the full CONTRACT-SCHEDULE history of team t
(including the four otherwise-excluded 2021 opening-day rows), not against the smaller in-fold
UNIVERSE. This is exactly what makes the card's own claim "fallback: none needed (cross-season
prior game covers openers)" literally true for every SEASON-opener row: a team's first game of a
new season still has a strictly-earlier CONTRACT-SCHEDULE row (last season's finale, or the 2021
opening-day slate itself for 2021's early rows). Flagged for P37 as a card-silent-but-well-
supported clock choice, in the same spirit as A08's Lbar_train reading and A23's opener-rule
reading -- both disclosed, neither invented from nothing.

GENUINE GAP DISCLOSED, NOT SILENTLY RESOLVED: the card's "fallback: none needed" claim does NOT
cover a true FRANCHISE DEBUT (a team's first game in the entire archive, as opposed to a season
opener) -- P35 task_cards.A14's own card names exactly three such teams and games (team_id
1611661331's 2025 debut; 1611661327 and 1611661332's 2026 debuts). For those specific rows,
rest(t, g) on the debuting team's OWN side is structurally undefined (no contract-schedule row of
that team exists at all before it). The card is silent on this exact edge case. Per the standing
instruction ("anything the card leaves ambiguous: mark BLOCKED and report, never improvise"), this
module does NOT invent a numeric substitution (neither A23-bundle_OM's "assign cap value" nor
A23-bundle_AI's "contrast := 0" is authorized anywhere in A24's own frozen text): `compute_rest_
days` returns NaN for a structurally-undefined row, and `build_design` FAILS CLOSED (raises
A24ConstructionFailure) if any row's x is undefined, rather than silently picking a fallback the
card never pinned. This mirrors the program's own established fail-closed precedent (A21's
"an all-false train_mask must fail closed, never silently fill with 0"). Flagged in the module
report for P37 disposition (a small, decidable, testable gap -- three known rows -- not a change
to the primary target, K0 structure, inference structure, candidate universe, cutoff-valid feature
set or leakage status, so it is NOT raised here as a HALT-worthy stop condition).

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness, no
same-row (current-game) dependency. STRICT LAGGING (a row's rest_own/rest_opp depend only on
OTHER, strictly-earlier contract-schedule rows of the SAME team, never on the row's own game
outcome and never on any later game) is verified directly by tests/TESTS.py.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CAP_DAYS = 10.0          # P33/P35 A24 hyperparameters.fixed.cap_days (frozen)


class A24ConstructionFailure(RuntimeError):
    """Fail-closed: raised whenever this module cannot honestly produce the card's construction
    (an undefined rest value with no frozen fallback rule, a non-superset history frame, or a
    duplicate (team_id, game_rank) / (game_id, team_id) key) -- never silently substituted."""


# --------------------------------------------------------------------------------- game ranking

def _game_rank_map(game_date, game_id) -> pd.DataFrame:
    """Deterministic dense rank of DISTINCT (game_date, game_id) pairs, ascending, 0-indexed.
    Matches the program's one canonical ordering (construction_pins.a08_window_tie_break /
    possession_features.load_universe's own sort; ties broken by game_id, never by row order)."""
    df = pd.DataFrame({"game_date": pd.to_datetime(pd.Series(np.asarray(game_date))),
                       "game_id": np.asarray(game_id)}).drop_duplicates()
    df = df.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)
    df["game_rank"] = np.arange(len(df))
    return df


# --------------------------------------------------------------------------------- rest(t, g)

def compute_rest_days(target_team_id, target_game_date, target_game_id, *,
                      history_team_id, history_game_date, history_game_id) -> np.ndarray:
    """rest_days[i] = days between target row i's own game_date and team_id[i]'s most recent
    STRICTLY EARLIER row of the supplied CONTRACT-SCHEDULE history (by (game_date, game_id)
    ascending), cross-season, no season restriction of any kind.

    `history_*` must be a SUPERSET of every target row's own (game_date, game_id) (a team's own
    current-game row is itself a legitimate contract-schedule row; it never contributes to that
    row's OWN feature, only to strictly-later rows'). Raises A24ConstructionFailure if that
    superset invariant does not hold, or if (team_id, game_rank) is not unique in `history_*`.

    NaN when no strictly-earlier contract-schedule row exists for that team (a genuine franchise
    debut -- see module docstring's GENUINE GAP DISCLOSED note); never silently substituted here.
    """
    hist = pd.DataFrame({
        "team_id": np.asarray(history_team_id),
        "game_date": pd.to_datetime(pd.Series(np.asarray(history_game_date))),
        "game_id": np.asarray(history_game_id),
    })
    rank_map = _game_rank_map(hist["game_date"], hist["game_id"])

    hist_r = hist.merge(rank_map, on=["game_date", "game_id"], how="left")
    if hist_r["game_rank"].isna().any():
        raise A24ConstructionFailure("internal: every history row must map to a game_rank")
    hist_r = hist_r.sort_values(["team_id", "game_rank"], kind="mergesort")
    if hist_r.duplicated(["team_id", "game_rank"]).any():
        raise A24ConstructionFailure(
            "A24: (team_id, game_rank) is not unique in the supplied contract-schedule history "
            "-- a team appears more than once at the same (game_date, game_id)")
    prior_date = hist_r.groupby("team_id", sort=False)["game_date"].shift(1)
    lookup = pd.Series(
        prior_date.to_numpy(),
        index=pd.MultiIndex.from_arrays([hist_r["team_id"].to_numpy(),
                                         hist_r["game_rank"].to_numpy()]))

    target = pd.DataFrame({
        "team_id": np.asarray(target_team_id),
        "game_date": pd.to_datetime(pd.Series(np.asarray(target_game_date))),
        "game_id": np.asarray(target_game_id),
        "_orig_idx": np.arange(len(np.asarray(target_team_id))),
    })
    tgt_r = target.merge(rank_map, on=["game_date", "game_id"], how="left")
    if tgt_r["game_rank"].isna().any():
        bad = tgt_r.loc[tgt_r["game_rank"].isna(), ["game_date", "game_id"]]
        raise A24ConstructionFailure(
            f"A24: target rows absent from the contract-schedule history (history must be a "
            f"superset of every target row's own game): {bad.head(5).to_dict('records')}")

    key = pd.MultiIndex.from_arrays([tgt_r["team_id"].to_numpy(), tgt_r["game_rank"].to_numpy()])
    prior = lookup.reindex(key).to_numpy()

    out = np.full(len(target), np.nan, dtype=float)
    defined = ~pd.isna(prior)
    own_date = tgt_r["game_date"].to_numpy()[defined]
    prior_date_defined = prior[defined]
    days = (own_date - prior_date_defined) / np.timedelta64(1, "D")
    out[tgt_r["_orig_idx"].to_numpy()[defined]] = days.astype(float)
    return out


def rest_level(rest_days, cap: float = CAP_DAYS) -> np.ndarray:
    """f(rest) = min(rest, cap). NaN passes through as NaN -- kept a pure, honest min-cap
    transform with no fallback baked in (mirrors A23's f_cap for the identical reason)."""
    return np.minimum(np.asarray(rest_days, dtype=float), float(cap))


def _lookup_by_opponent(game_id, team_id, opp_team_id, value) -> np.ndarray:
    """value computed per (game_id, team_id) row, looked up at the SAME game_id's opponent row.
    Mirrors A16/A23's opponent-lookup pattern (two-sided game universe invariant). NaN values
    (a debut on the opponent's own side) pass through -- legitimate, not an error."""
    lut = pd.Series(np.asarray(value, dtype=float),
                    index=pd.MultiIndex.from_arrays([np.asarray(game_id), np.asarray(team_id)]))
    if lut.index.has_duplicates:
        raise A24ConstructionFailure(
            "A24: (game_id, team_id) is not unique in the supplied frame; opponent lookup "
            "requires exactly one row per team per game")
    opp_key = pd.MultiIndex.from_arrays([np.asarray(game_id), np.asarray(opp_team_id)])
    if not opp_key.isin(lut.index).all():
        raise A24ConstructionFailure(
            "A24: opponent lookup failed for one or more rows -- every row's opp_team_id must "
            "have its own row in the same frame at the same game_id (two-sided game universe "
            "invariant); this is a schema failure, distinct from a legitimate NaN rest value")
    return lut.reindex(opp_key).to_numpy(dtype=float)


def rest_level_symmetric(team_id, opp_team_id, game_id, game_date, *,
                         history_team_id, history_game_date, history_game_id,
                         cap: float = CAP_DAYS) -> dict:
    """The complete A24 construction: rest_own, rest_opp (raw, uncapped), f_own, f_opp (capped),
    and the symmetric mean treatment x = (f_own + f_opp) / 2, aligned to the input row order.

    Returns NaN in x wherever either side's rest is structurally undefined (a franchise debut on
    that row's own or opponent side); build_design (arm_a24.py) is the fail-closed policy point,
    not this pure function.
    """
    rest_days_own = compute_rest_days(
        team_id, game_date, game_id,
        history_team_id=history_team_id, history_game_date=history_game_date,
        history_game_id=history_game_id)
    f_own = rest_level(rest_days_own, cap=cap)
    f_opp = _lookup_by_opponent(game_id, team_id, opp_team_id, f_own)
    x = (f_own + f_opp) / 2.0
    return {
        "rest_days_own": rest_days_own,
        "f_own": f_own, "f_opp": f_opp, "x": x,
        "undefined_own": np.isnan(f_own),
        "undefined_opp": np.isnan(f_opp),
        "n_undefined": int(np.isnan(x).sum()),
    }
