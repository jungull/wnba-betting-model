# Components preselected, frozen and hashed BEFORE any statistic

**Preregistration SHA-256: `7f784133085fffc3ef9ce93086b6c64045e5190e875f302c682547aafde0206d`**
(`_prereg.json`, written by `scripts/s03_prereg.py`, which reads no data at all.)

**Amendment 1 SHA-256: `b33ff1e4e779dbec7ea1ebf11872b3fc873e3378d4d85908da7007dd2ab6d26f`**
(`_prereg_amendment.json`. Trigger: a row count. See "The amendment" below.)

**Reference ladder SHA-256: `8079f632ea1bc159bdb993e1e1efdf49d6f73c11e5ade1b5398bdffb8dac24db`** —
imported unchanged from D101 / `E1_I0027_reference_ladder/refladder.py` and re-hashed at run time;
every script refuses to run on a mismatch.

## Counts

| | |
|---|---|
| components in the continuous stack | **6** |
| components on a separate response | **1** (C2, availability — see below) |
| placebo components | **6** |
| pending hooks declared | **2** (C8 free-throw hurdle, C9 RAPM-as-prior) |
| **added after hashing** | **0** |
| **dropped after hashing** | **0** |
| preregistered HEADLINE cells | **8** (4 targets × 2 strata) — inside D103's ≤18 recommendation |

## The components

| id | ledger | published claim | ablation = |
|---|---|---|---|
| `C1_FALLBACK_ROUTE` | D092, D094, **D102** | route `fallback_level == 2` (947 rows) to the tuned prior-history estimator: points +2.8169%, minutes +4.9885%, attempts +4.0358% MAE skill. `fallback_level == 3` (pure cold start) is **not** routed — it is 2.7% of the value. | the champion's own forecast stands |
| `C2_AVAIL_LONGABSENCE_RECAL` | D090 | the model is 11.5 points too pessimistic about returns from long absence (top decile predicted 0.5091, observed 0.6239) and **mis-shapes the duration curve** | measured on its own |
| `C3_PER_TARGET_HALFLIFE` | D094 | half-lives differ 20× across targets: minutes 2, attempts 5, points 8, ppm 40 | one common half-life of 5.0, mode `equal` |
| `C4_SHRINK_OWN_PRIOR_SEASON` | D094, D092 | shrink weakly toward the player's **own prior season, never the league**; k = 0.5 / 0 / 0.5 / 2; **no history minutes-floor** | k = 0 everywhere |
| `C6_OPP_DEFENCE_SELECTIVE` | D099 (D085, D098) | dR2 +0.003335 (points) / +0.005028 (ppm) on the decision stratum. **RAISED NOT ACCEPTED.** 70% is a pooled coefficient; it **hurts** low-volume players. Applied **only** to the top prior-usage tercile. | drop the defence correction |
| `C5_TEAMMATE_VOLUME_PRIOR_ONLY` | D089, **D101** | walk-forward points dR2 0.0023492 at cluster p 0.0345. **D101 downgraded the evidence**: it does not clear a correct-level null against a strong reference (p 0.2067). Strictly-prior variant only; the tip-time variant is a post-game observation and is never used. | drop the teammate correction |
| `C7_HOME_AWAY` | D104 | real and exactly bounded: a perfect home term can add at most dR2 **4.63e-05**, and it is 97.6% free throws. D104 ruling 2 says do not ship it. Included **as the test of whether effects this size aggregate at all.** | drop the home correction |

## Stack order (STEP 4), by PUBLISHED claim size — hashed in advance

1. `C1_FALLBACK_ROUTE` — routing to a **deliberately naive** estimator (one half-life 5.0, no shrinkage)
2. `C3_PER_TARGET_HALFLIFE` — upgrade the routed-to estimator's memory
3. `C4_SHRINK_OWN_PRIOR_SEASON` — upgrade its shrinkage
4. `C6_OPP_DEFENCE_SELECTIVE`
5. `C5_TEAMMATE_VOLUME_PRIOR_ONLY`
6. `C7_HOME_AWAY`

**The nesting was declared in advance.** C3 and C4 configure the estimator C1 routes to, so they can
only exist after C1 and ablating C1 also removes them. That shows up in the sum-of-parts arithmetic
and is not reported as a surprise.

## Why C2 is not in the stack

`p_active` is a **binary** response scored by Brier. Under D101's rule **D1 (same response)** it is
not commensurable with any dR2 on points, minutes, attempts or points-per-minute, and no denominator
convention repairs a response mismatch. It is measured as its own single preregistered test and its
number is reported beside the stack, never inside it. **This was written down before any statistic
existed, not after seeing one.** A second, structural reason emerged at build time and is recorded
in NOTES.md: every scored row is a row where the player appeared, so an availability correction has
no route into the continuous forecast on this row set at all.

## Placebo design (STEP 5), hashed in advance

Same count, same functional forms, same pipeline, same nulls, same row set, same denominator; only
the information content destroyed. Seed 424242.

| id | mirrors | design |
|---|---|---|
| `P1_PLACEBO_ROUTE` | C1 | route a **random** equal-sized subset of NON-fallback rows to the same estimator |
| `P3_PLACEBO_HALFLIFE` | C3 | per-target half-lives drawn at random from D094's own grid |
| `P4_PLACEBO_SHRINK` | C4 | per-target k drawn at random from {0, 0.5, 1, 2} |
| `P6_PLACEBO_DEFENCE` | C6 | opponent defensive rating reassigned **across opponents** within season, then applied through the identical selective rule |
| `P5_PLACEBO_TEAMMATE` | C5 | `G01_noise`, a pre-existing negative-control column written by an earlier screen |
| `P7_PLACEBO_HOME` | C7 | a random one-team-per-game home relabel preserving the exact per-game marginal (D104's third control, the one that passed at p 0.982) |

**Preregistered decision rule:** if the placebo stack's headline dR2 is the same order as the real
stack's on any target, the real stack's gain on that target is reported as UNINTERPRETABLE.

## The amendment

`s04_build.py` printed **zero** `fallback_level == 2` rows inside the preregistered common row set.
The trigger was that row count and nothing else; **no outcome statistic had been computed**. The
failed log is kept at `run_log_s04_FAILED_zero_routed_rows.txt` and the coverage accounting that
diagnosed it is `attrition_by_feature.csv`.

Cause: the preregistered common row set required **every** component's feature to be finite. C1's
target population is by construction the population with almost no prior history — exactly where the
prior-history features do not reach. Of 947 routed rows, 62 survived into the E1_I0018 universe and
**zero** had a finite `prior5_minutes`.

The amendment moves the base universe to `E0_I0024_reb_ast_characterisation/screen_frame.parquet`
(18,212 rows, 2021–2024), which **strictly contains** the champion's universe (tier ∩ rebast =
13,879, tier-only = 0), and replaces the all-features-finite requirement with a **zero-correction
rule**: a feature component corrects where its feature exists and applies exactly zero where it does
not, identically in the real stack, every ablation and every placebo. The DECISION stratum
definition is unchanged and was re-expressed on the champion frame's own columns — **verified
identical** on the 11,706-row overlap (4,513 rows either way, agreement 1.0000).

Zero components were added. Zero were dropped.
