# calibrated_prob_edge_v1 — RESULT: NEGATIVE

*Run 2026-08-01. Registered `calibrated_prob_edge_v1` (regime A, primary metric
`realised_roi_frozen_rule`, incumbent `bet_everything_at_best_price`), as amended by
`executability_fixed_notional_v1`. Design frozen and committed at `b5171de` **before** the
script had ever been executed, so the pre-registration is auditable in git history rather
than asserted here.*

## The headline

**The calibrated-probability successor does not beat the market.** The frozen policy loses
money out of sample, and the probability model has no out-of-sample skill.

| slice | log loss | Brier | calib. slope | OVER ROI | UNDER ROI |
|---|---|---|---|---|---|
| **2024 fitting** | 0.68760 | 0.24726 | **+1.144** | +0.1076 `[-0.174, +0.387]` | +0.0244 `[-0.068, +0.123]` |
| **2025 development** | 0.69259 | 0.24969 | **+0.445** | −0.1048 `[-0.260, +0.045]` | **−0.1078 `[-0.200, -0.014]`** |
| **2026 descriptive** | 0.70154 | 0.25410 | **−0.263** | **−0.1438** `[-0.281, +0.002]` | −0.1058 `[-0.241, +0.047]` |

Intervals are 90%, bootstrapped over **game dates**, not rows.

Three things in that table matter more than the ROI figures:

1. **`log(2) = 0.69315`.** The 2026 log loss of **0.70154 is worse than a constant 50%
   predictor**, and 2025 at 0.69259 is barely better. The model does not merely fail to beat
   the market — out of sample it fails to beat a coin.
2. **The calibration slope inverts**: +1.144 → +0.445 → **−0.263**. A negative slope means
   higher predicted probabilities are associated with *lower* realised rates. Whatever the
   model learned on 2024 does not merely decay; by 2026 it points the wrong way.
3. **Even in the fitting slice, ROI is inside its own interval.** The in-sample +0.1076 and
   +0.0244 both span zero. A strategy that cannot demonstrate an edge on the data it was fit
   to has nothing to decay from.

## Why it failed — the mechanism, not just the number

```
corr(p_over, disagree)         = +0.007
corr(p_over, market implied)   = +0.612
```

The `disagree` term — the model's own basketball opinion, `projection − line` — has
**essentially zero relationship** to the calibrated probability. The fitted probability is
mostly a noisy echo of the market's own implied price.

That is the diagnosis. The model contributes no independent information; it re-derives a
degraded version of the line and then pays vig to bet against the real one. Losing roughly
10% per unit staked is what that predicts.

## What this result is *not*

**It is not the predecessor's failure.** `conditional_edge_props_v1` optimised a target that
was maximised by *agreeing* with the line — it rewarded abstention, and 88.4% of its
predicted-edge variance was the disagreement term inverted. This design defused that: the
target is `P(points > line)`, a well-posed binary label; the minimum-disagreement band was
fixed in advance at 1.0 points; overs and unders were scored separately; the disagreement
term was included deliberately so its dominance could be measured. It *was* measured, and
it is +0.007.

So the objective was sound this time and the answer is simply **no edge**. That is a cleaner
and more informative null than the predecessor's, and it costs the registration honestly.

## A defect I found in my own null, and fixed

The first run reported MDEs of 0.003–0.007. That was wrong and **anti-conservative by roughly
20×**.

The permutation shuffled outcomes only among the *already-selected* bets. Within-date outcome
variance (0.148) is well below overall variance (0.249), so reshuffling inside a fixed
selection barely moved the mean and the null collapsed. The naive SE alone implies ≈0.074.
An MDE of 0.003 would have let ordinary noise read as a real effect — in the fitting slice it
would have made +0.1076 look like a discovery.

Per `screening_protocol_amendment_v2` P3 the permuted quantity must flow through the whole
downstream path. Outcomes are now shuffled within a date across **every eligible row**, with
the fixed bet selection scored against them. The null is strictly wider. Corrected MDEs are
0.056–0.249.

**The headline conclusion is unchanged** — the fix makes the test more conservative, and the
losses were negative either way. But had the result been positive, the original null would
have manufactured a discovery. Recorded because it is exactly the class of error the
project's discipline exists to catch, and it was mine.

## Sample and eligibility ladder

```
33610  rows in
33300  after void removed
28345  after two-sided price
28345  after simultaneity (last_update joined; 0 missing)
17857  after minimum disagreement band (>= 1.0 pts)
17857  eligible
```

Fitting slice 2024: 6,320 rows / 246 games / 94 dates / 74 players.
Independent player-game opportunities are reported alongside quoted rows in `results.json` —
the 1,517 UNDER bets in 2024 are only **432** independent opportunities.

Chosen `lambda` 300 by leave-one-date-out CV inside 2024 only; `trace(H)` 7.42, under the
cap of 10, no escalation needed. **One fit only** — 2025 and 2026 merely score the frozen
object.

## Executability

Simultaneity **is** enforced: `last_update` was joined back on a verified one-to-one key
(36,946 rows → 36,946 distinct keys, so the join cannot change which price row is used), and
stale quotes beyond 120 minutes are excluded. Zero rows were missing `last_update`.

**Book limits remain unobtainable** — no odds feed publishes them. Capacity is therefore
**UNMEASURED**, and per `executability_fixed_notional_v1` E3 the omission biases returns
**upward and systematically**, because books cut limits precisely where they judge a market
soft, so limits correlate with edge.

Here that cuts in our favour for admissibility: **the result is negative under assumptions
that flatter it.** A loss measured with free execution and unlimited size is robust — real
limits would only make it worse. This negative is fully admissible; a positive one would not
have been.

## Slice discipline

2024 fitting · 2025 development check, **not** confirmation · 2026 retrospective descriptive
only. **No number in this file is confirmatory.** The prospective log remains the only holdout
capable of supporting a promotion decision, and nothing here is promoted.

## What follows

Per the persistence requirement, a null is not a stopping point. The mechanism points
somewhere specific: the failure is not the decision layer, the calibration method or the EV
threshold — it is that **`projection − line` carries no information**. Tuning the policy on
top of a signal-free projection cannot help.

That makes the next action the **player-model bake-off under `council_design_v1`**: the
projection itself is the thing that must improve before any betting policy built on it can
work. This result is evidence for prioritising representation over decision policy, which is
what the bake-off tests.

Registered follow-ups that do **not** follow from this: re-tuning the EV threshold, widening
the disagreement band, or searching bookmaker subsets. Each would be specification-searching
against a signal-free input, and each is explicitly barred.
