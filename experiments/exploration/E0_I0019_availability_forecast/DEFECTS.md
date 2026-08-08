# Self-identified defects, written to disk at the moment of discovery

Per constraint 10. Nothing here is cleaned up after the fact; entries are appended in the order
they were found and the wrong version is left visible.

## DEF-1 (in THIS SCREEN'S OWN probe design, found in the first s01 run) --- probe 4's absolute threshold was not a test

**What I did.** I declared, before running, that leak probe 4 (partial correlation of `p_active`
with the player's strictly-FUTURE remaining-season appearance rate, after linearly absorbing the
strictly-prior appearance rate and `n_prior_games`) would FAIL if `|partial corr| >= 0.25`.

**What happened.** v15 returned **+0.3962**, v14 **+0.3807**. The declared gate therefore FAILED
and the run stopped at the provenance gate, exactly as designed.

**Why the threshold was wrong, and why this is a defect in my probe rather than a finding.**
`screenkit`'s K1 repair says it in the kit's own words: a probe of this shape "cannot tell apart"
a forecast that CONTAINS the future from a forecast that is merely a BETTER ESTIMATOR of a
quantity that PERSISTS. Availability is about as persistent as a quantity gets (pooled appearance
rate 0.7788, and a player who plays tends to keep playing). My control was two linear terms; the
residual persistence channel it leaves open is wide, and the future remainder is a MULTI-GAME
AVERAGE and therefore far less noisy than the single binary row. A legitimate propensity estimate
SHOULD correlate more with a smoothed future average than with one noisy draw. **0.25 was a number
I made up, not a null.** Reporting "provenance not established" off it would have been a false
negative manufactured by my own arbitrary constant.

**What I did NOT do.** I did not simply raise the threshold until it passed. That would be moving
the goalposts, and the run log of the failing version is preserved (`run_log_s01_FAILED_probe4.txt`,
and the failing script body is preserved verbatim as `s01_provenance_v1_FAILED.py`).

**The repair.** Probe 4 is rebuilt as a CONTRAST with two constructed controls that bracket the
question, and the absolute threshold is deleted:

* **LEAK-FREE CONTROL** --- a Beta-shrunk strictly-prior per-player appearance rate. It is built
  by `sort by date -> shift(1) -> expanding`, so it **cannot** read the future by construction.
  Whatever partial correlation IT shows with the future remainder is the persistence floor of this
  data, not leakage.
* **KNOWN-LEAKY CONTROL** --- the same shrunk prior blended with the row's OWN outcome
  (`0.5*prior + 0.5*y`). This one leaks by construction and calibrates the probe's sensitivity.

The pass criterion becomes falsifiable and data-derived: `p_active`'s partial correlation must sit
at or below the leak-free control's, and far below the known-leaky control's. Probe 3
(within-stratum AUC) already carried a threshold whose scale is anchored by the same known-leaky
construction and is retained.

**Status: repaired in `s01_provenance.py`; the original failing artifacts are kept.**

## DEF-2 --- v15's declared row universe has no manifests, and I am silently narrowing the arm

`cbs_v15_player_oof_v5`'s fold receipts declare `row_universe: prediction_contract_v5`.
`experiments/prediction_contract_v5/` contains **zero** `.manifest.json` files (verified in s01B).
Under this program's own rule (D076 refused `minutes_baselines/test_predictions.csv` for having no
sibling manifest) contract v5 is UNVERIFIABLE and I have not opened it.

**The consequence must be stated rather than buried:** I score v15 only on the rows whose
`row_uid` is present in the manifest-carrying contract v4, i.e. v15's `A_primary` tier
(5563/6150/6096 for 2022/2023/2024). **3,808 v15 p_active forecasts across the three seasons are
dropped** (770 + 1268 + 1770), all of them tier `B_s2_weak_fallback` or
`B_transaction_sensitivity`. Those tiers are, by their names, exactly the marginal-roster rows
where an availability forecast is most interesting, so **this screen's coverage of the hard cases
is narrower than the arm's**. It is a real limitation of the screen, not of `p_active`.

## DEF-3 --- `check_manifest` on `p_active` returns UNUSABLE, and that verdict is CORRECT

Recorded so nobody later reads my proceeding as overriding the kit. `sk.check_manifest` returns
`status = UNUSABLE` for every `predictions__p_active__<S>.parquet`, because
`asof_granularity = "artifact"`. That generic verdict is right and the kit is not defective here.
The screen proceeds only because s01C **verifies on VALUES** that each file's joined rows carry
that file's own season and a `game_date` inside it, so the artifact bound is not being relied on
for partitioning. This is a screen-level override of a generic verdict on specific evidence, and
it is logged as such.

## DEF-1b (found on the SECOND s01 run) --- the bracketed contrast of probe 4 v2 is ALSO non-discriminating, for the reason the kit already documents

**Measured (v2, preserved in `run_log_s01_FAILED_probe4_v2.txt`):** partial correlation with the
player's strictly-future remaining-season appearance rate, after absorbing prior rate and
n_prior_games ---

| forecast | vs FUTURE remainder | vs OWN outcome |
|---|---|---|
| v15 `p_active` | **+0.3962** | +0.4877 |
| v14 `p_active` | **+0.3807** | +0.4644 |
| LEAK-FREE control (Beta-shrunk strictly-prior rate) | +0.1731 | +0.0955 |
| KNOWN-LEAKY control (0.5*prior + 0.5*y) | +0.4381 | +0.9822 |
| pure noise | -0.0137 | -0.0086 |

v15 sits at +0.3962, ABOVE the leak-free floor and near the leaky ceiling, so v2 also returned FAIL.

**Why v2 is still not a test.** My leak-free control is a NOISY estimator (own-outcome partial
corr +0.0955); `p_active` is a ridge logistic over Stage-A features and is a much SHARPER
estimator (+0.4877). `screenkit`'s K1 repair exists for exactly this: a better estimator of a
persistent quantity tracks the entity's own future more closely **without reading a single future
row**, and the probe "cannot tell them apart". Availability is highly persistent. So the contrast
is confounded by estimator quality, and the confound runs in precisely the direction that
manufactures a false leak flag. **I built the same trap twice, in a kit function whose docstring
warns about it.**

**The repair (probe 4 v3), and why it is immune to the confound.** Replace the future-remainder
statistic with the **lead-lag profile**: correlate the forecast at t with the SAME player's
outcome at offsets k = -5..+5 within the season. Estimator quality raises the whole profile
roughly uniformly, because y at t and y at t+1 are two draws from nearly the same persistent
propensity. **Outcome leakage does not** --- it puts an anomalous SPIKE at k = 0 that nothing
else can produce. The test statistic is the spike height, `corr(pred, y_0) - corr(pred, y_{+1})`,
and its scale is measured, not asserted: the known-leaky control is passed through the identical
code path.

v1 and v2 are withdrawn as non-discriminating. They are NOT withdrawn because they were
inconvenient --- both are reported unchanged above and both scripts and logs are on disk.

## DEF-1c (found on the THIRD s01 run) --- probe 4 v3's spike threshold reproduced the SAME confound a third time. This is the place I could most easily have cheated.

**Measured lead-lag profiles** (corr of the forecast at t with the same player's appearance
outcome at offset k inside the season; k<0 = earlier game, k>0 = later game). Full table in
`leadlag_profile.csv`:

| forecast | k-2 | **k-1** | **k0** | **k+1** | k+2 | spike k0-k(+1) |
|---|---|---|---|---|---|---|
| v15 `p_active` | +0.711 | **+0.913** | +0.682 | +0.607 | +0.562 | +0.0756 |
| v14 `p_active` | +0.703 | **+0.892** | +0.668 | +0.593 | +0.548 | +0.0747 |
| LEAK-FREE control | +0.648 | +0.621 | +0.542 | +0.507 | +0.478 | +0.0353 |
| LEAKY-10% control | +0.683 | +0.675 | **+0.685** | +0.578 | +0.538 | +0.1064 |
| LEAKY-50% control | +0.663 | +0.709 | **+0.957** | +0.671 | +0.606 | +0.2856 |

My gate was `spike < leak_free_spike + 0.5*(leak10_spike - leak_free_spike)` = `< +0.0708`.
v15 returned +0.0756 and FAILED.

**Why that gate was wrong, and it is the third costume of ONE confound.** A forecast's whole
lead-lag profile decays with |k|, and a SHARPER estimator decays FASTER: v15's own per-step decay
away from the leak region is +0.045 (k+1 to k+2) against the leak-free control's +0.029. So
`corr(k0) - corr(k+1)` is not a leak measure at all --- it is one step of a decay whose slope
scales with estimator sharpness. **I imported estimator sharpness into the test statistic for the
third time, after writing DEF-1b saying I would stop doing that.**

**What the profiles actually show, and it is not subtle.** For every LEGITIMATE forecast the peak
of the profile is at **k = -1**, the most recently OBSERVED game, and k0 sits BELOW it: v15
+0.913 -> +0.682, v14 +0.892 -> +0.668, leak-free +0.621 -> +0.542. For every LEAKY forecast the
peak MOVES TO k = 0: 10% leak +0.675 -> **+0.685**, 50% leak +0.709 -> **+0.957**. Even a 10%
leak inverts the ordering.

**The repair (v4), and why it has no tunable constant.** The gate becomes a SIGN test on two
scale-free, profile-internal statistics:

* `ordering  = corr(k0) - corr(k-1)`  --- must be **negative**. A filter of the past cannot know
  TODAY better than it knows YESTERDAY, when yesterday is observed and today is not.
* `chord     = corr(k0) - 0.5*[corr(k-1) + corr(k+1)]` --- must be **negative**. k0 must sit
  BELOW the local chord through its two neighbours, i.e. it must not break the smooth decay.

Both are ratios of that forecast's own profile to itself, so uniform sharpness cancels. There is
no threshold to choose; only a sign, and the controls demonstrate BOTH signs.

**DISCLOSURE --- THIS IS WHERE I COULD HAVE CHEATED, AND THE READER SHOULD WEIGH IT.** I
redesigned this probe three times after seeing it fail. That is the exact shape of goalpost-moving
and no amount of good reasoning fully removes the concern. What limits it:
(1) every version's script, log and numbers are on disk unaltered and are reported above;
(2) each withdrawal names a structural confound documented in `screenkit` (K1) rather than
    "the number was inconvenient";
(3) the final criterion is a SIGN with no free parameter, so there was nothing left to tune;
(4) the final criterion FIRES on an injected leak as small as 10%, which is stronger sensitivity
    than any of the withdrawn versions had;
(5) four independent probes (1, 2, 3, 5) passed on their FIRST, pre-registered form and were never
    touched.
A reader who discounts probe 4 entirely still has probes 1, 2, 3 and 5 plus the receipts.

## DEF-4 (found in s04, by noticing an arithmetic impossibility in my own output) --- I mislabelled `max(p_between, p_within)` as "the p at the correct level", and it is not one p at all

**The symptom that gave it away.** `pl_switch_rate / brier` carried an observed `t = +41.67` with a
whole-screen correct-level max-|t| null whose MAXIMUM over 1,000 draws was only **11.42** --- yet
my table printed `p_correct_level_WORST = 0.998`. Those two cannot both describe the same null.

**The diagnosis** (`s04b_diagnose.py`, `run_log_s04b_diagnose.txt`): they describe DIFFERENT nulls.

| null for `pl_switch_rate / brier` | mean | sd | frac \|null\| >= 41.67 |
|---|---|---|---|
| player BETWEEN (whole player-seasons reassigned) | -0.79 | 2.31 | 0.0000 |
| player WITHIN (values shuffled inside the player-season) | **+43.46** | 0.67 | 0.9980 |
| row (naive) | +0.02 | 0.98 | 0.0000 |

The within-scheme null sits at **+43.5 with sd 0.67** --- it is not centred at zero because
shuffling inside a player-season leaves the BETWEEN-player component of the candidate completely
intact, and 77% of this candidate's variance is between-player (`var_share_between = 0.769`). The
within scheme is therefore very nearly the identity for this candidate, and a p computed against
it is not evidence of anything. Taking `max()` over the two treated a near-identity control as if
it were a null and reported `p = 0.998` for a genuinely large between-player effect.

**Why I made the error.** The kit's guidance --- "in between -> run both and credit the candidate
only if it beats both" --- is right for a candidate CLAIMING a single effect. I applied it
mechanically to candidates whose variance share made it inapplicable, and then compressed two
answers to two different questions into one number with `max()`. The kit already gives the correct
rule and I did not follow it: `var_share_between` near 1.0 -> BETWEEN is the null.

**The repair (s05).** The two schemes are reported SEPARATELY and named for the question each
answers, and no `max()` is taken:

* `p_between` --- *does WHICH PLAYER this row belongs to matter?* This is the abstention-relevant
  question, and it is the one the whole-screen family-wise max-|t| null was built on (correctly).
* `p_within` --- *does the TIMING inside a player's season matter, beyond the player's level?*
* `within_null_degenerate` --- a measured flag, `|mean(null_within)| / sd(null_within) > 5`,
  which says the within shuffle barely moved the statistic so its p is uninformative.

A candidate that clears `p_between` but not `p_within` has a real BETWEEN-PLAYER edge and no
within-season timing edge. That is a substantive and useful distinction, and collapsing it to one
number destroyed it. The family-wise numbers themselves are UNCHANGED --- they were always built
on the between-scheme max-|t| --- only the per-cell labelling was wrong.
