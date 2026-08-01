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

## Why it failed — the mechanism

> **Corrected twice after John's reviews.** Originally this argued from a marginal
> `corr(p_over, disagree) = +0.007`, which cannot measure *incremental* information
> conditional on market probability. The replacement ablation's market arm then turned out to
> use a **vig-inclusive, one-sided** price. Both are fixed: the claim now rests on
> `prob_edge_mechanism_ablation_v2`, which uses a genuine de-vigged market
> `p = q_over / (q_over + q_under)` from the same book and simultaneous snapshot.

**Primary result — no detectable incremental projection information.** Full model minus
de-vigged-market-plus-all-other-controls spans zero on every slice:

| PRIMARY (8) − (7) | 2024 fit | 2025 dev | 2026 desc |
|---|---|---|---|
| delta | −0.000053 | −0.000211 | +0.000207 |
| 90% CI | spans 0 | spans 0 | spans 0 |

The projection alone against a constant is likewise indistinguishable from zero
(−0.000000 `[−0.000041, +0.000040]`).

**The de-vig correction mattered.** `(3) − (2)` — de-vigged versus raw vig-inclusive, both
unfitted — is −0.0055 / −0.0045 / −0.0043 and **excludes zero on all three slices**. The raw
vig-inclusive one-sided probability is in fact **worse than a constant** out of sample (2025
0.69309 vs 0.69217; 2026 0.69659 vs 0.69316). And `(4) − (3)` spans zero everywhere: the
de-vigged market needs no fitted recalibration.

**Softened accordingly.** An earlier draft said "the market carries the only real signal."
Against the fairer representation that is too strong: `(3) − (1)`, de-vigged market over a
constant, excludes zero **only on 2025** (−0.0036 `[−0.0066, −0.0005]`) and spans zero on 2024
and 2026. The accurate statement is that the de-vigged market is the best available
representation and beats a constant detectably on 2025 only.

**A diagnostic lead, explicitly not a mechanism.** `(7) − (4)` is +0.0042 `[+0.0008, +0.0076]`
on 2025 and +0.0091 `[+0.0034, +0.0151]` on 2026 — i.e. **non-projection controls appear
harmful in the 2025 development and 2026 descriptive slices, consistent with 2024
noise-fitting.** These intervals are **not** corrected for the full registered comparison
family, and this contrast is one of several secondary lines across multiple specifications
and slices. It is a strong lead for why calibration degrades; it is **not** independent
evidence of a confirmed general anti-generalisation mechanism, and is not claimed as one.

## What this result is *not*

**It is not the predecessor's failure.** `conditional_edge_props_v1` optimised a target that
was maximised by *agreeing* with the line — it rewarded abstention, and 88.4% of its
predicted-edge variance was the disagreement term inverted. This design defused that: the
target is `P(points > line)`, a well-posed binary label; the minimum-disagreement band was
fixed in advance at 1.0 points; overs and unders were scored separately; the disagreement
term was included deliberately so its dominance could be measured. It *was* measured — and,
after two corrections, measured properly: the registered primary contrast in
`prob_edge_mechanism_ablation_v2` spans zero on every slice.

So the objective was sound this time and the answer is simply **no edge**. That is a cleaner
and more informative null than the predecessor's, and it costs the registration honestly.

## Two defects in my own null, both found and fixed

**First: the null was ~20× too narrow.** The original permutation shuffled outcomes only among
the *already-selected* bets. Within-date outcome variance (0.148) sits well below overall
variance (0.249), so reshuffling inside a fixed selection barely moved the mean and the null
collapsed — MDEs of 0.003–0.007 where the naive SE alone implies ≈0.074. That would have made
the fitting slice's +0.1076 look like a discovery. Outcomes are now shuffled within a date
across **every eligible row**. Corrected MDEs 0.056–0.249.

**Second: I described the fix inaccurately.** I wrote that the permuted label "flows through
the whole downstream path" per `screening_protocol_amendment_v2` P3. **It does not.** Lambda
selection, model fitting, probabilities and bet selection are all held fixed inside that
permutation. John flagged this on 2026-08-01 and was right. The two estimands are now named
and separated:

| estimand | what varies | status |
|---|---|---|
| **`frozen_policy_conditional`** | outcomes only; model and selection fixed | correct and sufficient for **2025, 2026**, where the policy genuinely *is* frozen |
| **`pipeline_refit_fixed_lambda_sensitivity`** | coefficients refit, bets re-selected; **lambda held fixed** | a **partial-refit SENSITIVITY** for 2024 — *not* a complete pipeline null and **not** amendment v2 P3 compliant |

The distinction matters, and running the correct one on 2024 changed the reading:

```
OVER   observed ROI +0.1076 | refit-null mean +0.1915  sd 0.1599 | MDE 0.4480 -> WITHIN NOISE
UNDER  observed ROI +0.0244 | refit-null mean +0.0628  sd 0.0188 | MDE 0.0526 -> WITHIN NOISE
```

The refit-null mean is higher than the observed ROI on both sides: a pipeline handed
*shuffled* labels achieves better in-sample ROI on average than the real one did.

**What that is, and is not.** It is an **overfitting diagnostic** on the fitting slice — it
says the 2024 return is not merely inside noise but below what label-free noise-fitting
produces. It is **not** additional out-of-sample evidence, and is not offered as any. The
out-of-sample case rests entirely on the 2025 and 2026 frozen-policy results.

**Labelling, corrected.** The real pipeline selected lambda *from the labels*; this null does
not. It refits coefficients and re-selects bets, but it does **not** reproduce the complete
registered fitting procedure, so it is named `pipeline_refit_fixed_lambda_sensitivity` and is
**not** described as a complete pipeline-refitting null nor as satisfying
`screening_protocol_amendment_v2` P3.

An earlier draft claimed the omission makes the null "only slightly narrower." **That is
withdrawn** — neither the direction nor the magnitude of holding lambda fixed has been
demonstrated. Accordingly this MDE is retained as a clearly labelled partial-refit
sensitivity and is **not used as a formally amendment-compliant inference result**. Since
2024 is the fitting slice and the out-of-sample results are already negative, no substantive
claim rests on it; a full nested permutation is therefore not run and is not blocking.

Both defects were mine, and both are the class of error this project's discipline exists to
catch. The headline conclusion is unchanged by either; the second fix strengthened it.

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
