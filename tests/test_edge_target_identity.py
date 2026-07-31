"""The comparative-error trap — a permanent guard.

Discovered 2026-07-31 by conditional_edge_props_v1 and formalised at John's
request (review 7, point 5).

THE IDENTITY.  For a model prediction p, a market line m and an outcome y, the
comparative-advantage target

    edge = |m - y| - |p - y|

is bounded by the reverse triangle inequality:

    |edge| <= |p - m|          (the model-market DISAGREEMENT)

So an agreeing model (p ~ m) is mechanically pinned to edge ~ 0.  Whenever the
unconditional mean edge is NEGATIVE — i.e. the model is worse than the market on
average, which is our situation in every market we have measured — a selector
can maximise this target by simply finding rows where it has NOTHING TO SAY.
Agreement wins.  The objective rewards abstention, not forecasting.

These tests construct a selector with PROVABLY ZERO forecasting skill and show
it "wins" the target anyway, so the trap can never be rediscovered the
expensive way.  Any future experiment targeting comparative error must show it
has defused this — by targeting realised return, by fixing a minimum
disagreement band before ranking, or by an equivalent argument.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_edge_target_identity.py
"""

from __future__ import annotations

import sys
import traceback

import numpy as np

RNG_SEED = 20260731


def _world(n=20000, seed=RNG_SEED):
    """A world where the model has ZERO skill beyond the market.

    y      truth
    m      market line: truth plus market noise
    p      model: the market line plus a disagreement that is INDEPENDENT of y
           (so the model carries no information the market lacks)
    """
    rng = np.random.default_rng(seed)
    y = rng.normal(0, 10, n)
    m = y + rng.normal(0, 9, n)                 # market: decent
    d = rng.normal(0, 4, n)                     # disagreement, independent of y
    p = m + d                                   # model: market plus pure noise
    return y, m, p, d


def _edge(y, m, p):
    return np.abs(m - y) - np.abs(p - y)


def test_identity_bound_holds():
    """|edge| <= |p - m| on every row — the inequality the trap rests on."""
    y, m, p, d = _world()
    e = _edge(y, m, p)
    assert np.all(np.abs(e) <= np.abs(p - m) + 1e-9), "reverse triangle inequality violated"


def test_model_has_provably_zero_skill():
    """The model adds nothing: its deviation from the line is uncorrelated with
    the line's own error. Any 'win' below is therefore not forecasting."""
    y, m, p, d = _world()
    skill = np.corrcoef(p - m, y - m)[0, 1]
    assert abs(skill) < 0.03, f"world is misconstructed; model has skill {skill:.3f}"
    assert _edge(y, m, p).mean() < 0, "unconditional edge should be negative"


def test_agreement_wins_the_comparative_error_target():
    """THE TRAP. Ranking by -|disagreement| — using NO information about the
    outcome — produces a large positive edge in the selected bucket."""
    y, m, p, d = _world()
    e = _edge(y, m, p)
    score = -np.abs(p - m)                     # "bet where we agree with the line"
    top = np.argsort(-score)[: len(y) // 10]   # top decile by agreement
    assert e[top].mean() > e.mean() + 0.5, (
        f"selected {e[top].mean():.3f} vs overall {e.mean():.3f} — the trap "
        "should be dramatic")
    assert e[top].mean() > -0.2, "agreement should pin edge near zero"


def test_the_winning_selector_makes_no_money():
    """And the same bucket is worthless to bet: near-zero disagreement means
    near-coin-flip sides, which lose to the vig."""
    y, m, p, d = _world()
    score = -np.abs(p - m)
    top = np.argsort(-score)[: len(y) // 10]
    # bet the side our model favours against the line; win if truth agrees
    side = np.sign(p - m)
    won = (np.sign(y - m) == side) & (side != 0)
    hit = won[top].mean()
    roi = hit * (100 / 110) - (1 - hit)        # -110 pricing
    assert abs(hit - 0.5) < 0.05, f"hit rate should be ~coin flip, got {hit:.3f}"
    assert roi < 0, f"a coin flip at -110 must lose; got ROI {roi:+.3%}"


def test_disagreement_band_defuses_it():
    """The prescribed fix: require a MINIMUM disagreement before ranking, so the
    selector must choose among rows where the model actually has an opinion."""
    y, m, p, d = _world()
    e = _edge(y, m, p)
    band = np.abs(p - m) >= 3.0                # fixed BEFORE looking at outcomes
    score = -np.abs(p - m)
    idx = np.where(band)[0]
    top = idx[np.argsort(-score[idx])[: max(1, len(idx) // 10)]]
    # inside the band the agreement trick no longer pins edge near zero
    assert e[top].mean() < -0.2, (
        f"inside the band the free lunch should be gone; got {e[top].mean():.3f}")


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception:
            failures.append(fn.__name__)
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed")
    if failures:
        print("FAILED:", *failures, sep="\n  - ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
