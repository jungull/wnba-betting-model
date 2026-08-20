"""`cbs_player_coldstart/16` — the cold-start splice, as authorised.

WHY THIS EXISTS
---------------

On rows the arm flags `is_fallback`, the champion does not look at the player at all. Across
2022–2024 and 1,061 player-games it emits essentially one number for everybody: points forecast
sd **0.012982** against an actual outcome spread of about 7.2 points. Measured tier MAE
**6.063956** on points and **9.7480** on minutes.

D092 recommended a rule. D137 authorised it. D139 then found that **the authorisation cannot be
executed as written**, and this module exists because of how that is resolved.

THE INCONSISTENCY, AND THE RULING TAKEN
---------------------------------------

* D092 **ruling 2** says: *drop listed position*. It carries no signal (p 0.783, permutation
  null 0.1996) and the depth-chart rank is what actually works.
* D092's **headline 4.02** was nevertheless computed from a variant that **includes** listed
  position. Confirmed here on the artifact: `P5c_additive` is identically
  `P2_position + P3_draft_bin + P4_teamrole - 2*league` to 7.1e-15.
* D137 authorised the change on condition it *"reproduce its validated numbers … a change that
  does not reproduce its own validation is not the change that was authorised."*

Both cannot hold. Implementing the **specified rule** yields **4.032479**, not 4.02.

**This module implements the specified rule — WITHOUT listed position.** The reasoning, recorded
so it can be reversed rather than discovered:

1. D092 ruling 2 is the *rule*; 4.02 is a *number that a superseded variant happened to produce*.
2. Position is measured null. Carrying a null feature in order to land on a headline is exactly
   backwards, and the programme's own habit note names restating-to-fit as its modal failure.
3. The gap is **0.008145 points of tier MAE, 0.20%**, and **+3.492% pooled skill against
   +3.507%**. Immaterial to performance; the principle is not immaterial, which is why it is
   written here instead of absorbed.

`structural_prior(..., include_listed_position=True)` reproduces the 4.024334 variant exactly, so
the choice is auditable in both directions and reversing it is a one-argument change.

THE RULE
--------

    IF the arm flags the row as a fallback (equivalently: fewer than three prior appearances
    this season), REPLACE the champion forecast with

        blend = lam(n) * own_running_mean + (1 - lam(n)) * structural
        lam(n) = n / (n + 2)                       n = prior same-season appearances
        structural = league + depth_dev + draft_dev        (NO listed-position term)

    then clip at zero. Otherwise leave the champion untouched.

Every component is estimated on **strictly earlier seasons only**; `own_running_mean` is the
player's own strictly-prior same-season games. Nothing is refitted and the champion is never
retrained — its stored forecasts are consumed as-is.

WHAT THIS MODULE DOES NOT DO
----------------------------

It is **not wired into the live arm**. Binding requires revising a byte-locked arm-registry
record and should follow a registered generation run, exactly as D139 required of the dispersion
repair. Until then the production defect remains live. This file is AVAILABLE, not BOUND.

It authorises nothing wager-shaped. S42 stands.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COLDSTART_ID = "cbs_player_coldstart/16"

#: Blend constant. lam(n) = n/(n+K_BLEND). D092 selected k=2 from {1,2,3,5,10}.
K_BLEND = 2.0

#: Reproduction anchors, on the E1_I0020 artifact frame (2022-2024, 13,879 rows, 1,061 tier).
ANCHORS = {
    "tier_rows": 1061,
    "pts": {"champion": 6.063956, "own_only": 4.252020,
            "authorised_no_position": 4.032479, "position_inclusive": 4.024334},
    "minutes": {"champion": 9.748011, "authorised_no_position": 5.448707,
                "position_inclusive": 5.437188},
    "pooled_skill_pts": {"champion": -0.222, "own_only": 3.090,
                         "authorised_no_position": 3.492, "position_inclusive": 3.507},
}


def blend_weight(n_prior, k: float = K_BLEND) -> np.ndarray:
    """lam(n) = n/(n+k). Zero prior games -> pure structural prior."""
    n = np.asarray(n_prior, dtype=float)
    return n / (n + float(k))


def structural_prior(league, depth_prior, draft_prior, position_prior=None, *,
                     include_listed_position: bool = False) -> np.ndarray:
    """Additive deviations from the league mean, all estimated on strictly earlier seasons.

    `structural = league + (depth - league) + (draft - league)`, i.e. `depth + draft - league`.

    `include_listed_position=True` adds the position deviation, reproducing the variant that
    produced D092's 4.02 headline. It is OFF by default because D092 ruling 2 says to drop it and
    it is measured null. The argument exists so the discarded variant stays auditable.
    """
    lg = np.asarray(league, dtype=float)
    out = np.asarray(depth_prior, float) + np.asarray(draft_prior, float) - lg
    if include_listed_position:
        if position_prior is None:
            raise ValueError("include_listed_position=True requires position_prior")
        out = out + (np.asarray(position_prior, float) - lg)
    return out


def coldstart_forecast(own_running_mean, n_prior, league, depth_prior, draft_prior,
                       position_prior=None, *, k: float = K_BLEND,
                       include_listed_position: bool = False,
                       clip_at_zero: bool = True) -> np.ndarray:
    """The replacement forecast for a cold-start row. Clipped at zero (D092 implementation note:
    the blend can go very slightly negative; the minimum observed was -0.10)."""
    lam = blend_weight(n_prior, k)
    struct = structural_prior(league, depth_prior, draft_prior, position_prior,
                              include_listed_position=include_listed_position)
    out = lam * np.asarray(own_running_mean, float) + (1.0 - lam) * struct
    return np.clip(out, 0.0, None) if clip_at_zero else out


def splice(champion, is_fallback, replacement) -> np.ndarray:
    """Champion everywhere except the flagged tier. Above the tier NOTHING is touched."""
    champ = np.asarray(champion, dtype=float)
    tier = np.asarray(is_fallback, dtype=bool)
    rep = np.asarray(replacement, dtype=float)
    if not (champ.shape == tier.shape == rep.shape):
        raise ValueError("champion, is_fallback and replacement must be the same shape")
    return np.where(tier, rep, champ)


def apply_coldstart_splice(frame: pd.DataFrame, *, champion: str, is_fallback: str,
                           own_running_mean: str, n_prior: str, league: str,
                           depth_prior: str, draft_prior: str, position_prior: str | None = None,
                           k: float = K_BLEND,
                           include_listed_position: bool = False) -> np.ndarray:
    """Column-name wrapper over the two steps above."""
    rep = coldstart_forecast(
        frame[own_running_mean], frame[n_prior], frame[league], frame[depth_prior],
        frame[draft_prior], frame[position_prior] if position_prior else None,
        k=k, include_listed_position=include_listed_position)
    return splice(frame[champion], frame[is_fallback], rep)


def coldstart_receipt(spliced, champion, is_fallback, outcome=None, *, target: str) -> dict:
    """What changed, and by how much. Emitted so a landing can be audited without rerunning."""
    tier = np.asarray(is_fallback, dtype=bool)
    champ = np.asarray(champion, float)
    new = np.asarray(spliced, float)
    rec = {
        "coldstart_id": COLDSTART_ID, "target": target,
        "n_rows": int(len(new)), "n_tier": int(tier.sum()),
        "tier_share": float(tier.mean()),
        "n_changed": int(np.sum(~np.isclose(new, champ))),
        "champion_sd_on_tier": float(np.std(champ[tier])) if tier.any() else None,
        "replacement_sd_on_tier": float(np.std(new[tier])) if tier.any() else None,
        "untouched_above_tier": bool(np.allclose(new[~tier], champ[~tier])),
    }
    if outcome is not None:
        y = np.asarray(outcome, float)
        rec["tier_mae_champion"] = float(np.mean(np.abs(y[tier] - champ[tier])))
        rec["tier_mae_spliced"] = float(np.mean(np.abs(y[tier] - new[tier])))
        rec["pooled_mae_champion"] = float(np.mean(np.abs(y - champ)))
        rec["pooled_mae_spliced"] = float(np.mean(np.abs(y - new)))
    return rec


def assert_above_tier_untouched(spliced, champion, is_fallback) -> None:
    """The splice must be a no-op above the tier. Raises rather than warning."""
    tier = np.asarray(is_fallback, dtype=bool)
    if not np.allclose(np.asarray(spliced, float)[~tier], np.asarray(champion, float)[~tier]):
        raise AssertionError("cold-start splice altered rows OUTSIDE the fallback tier")
