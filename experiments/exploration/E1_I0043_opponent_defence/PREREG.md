# E1_I0043 — OPPONENT DEFENCE: PREREGISTRATION

Screen `E1_I0043_opponent_defence`. Commissioned to give the opponent-defence channel its first
dedicated preregistered screen after four recorded sightings (D098, D099, D103-incidental, D117).

**This file is hashed before any statistic produced by this screen exists.** Numbers quoted below
are ANCHORS read from other screens' artifacts on disk, and are labelled as such. Every number this
screen produces itself comes after the hash.

---

## 0. PARTITION AND WINDOW — DECLARED FIRST

* **Seasons 2021–2024 only.** 2025/26 is a sealed confirmation holdout. It is never read, joined,
  merged, described or counted. Enforced on VALUES by `assert_partition` in `scripts/od_base.py`,
  which refuses to coerce non-datetime columns (the K0 trap).
* **ONE CLEAN WINDOW: walk-forward evaluation on 2023 and 2024 ONLY.** E1_I0042 verified from fold
  receipts that 2021 is degenerate (all forecasts at fallback level 4, a constant with no usable
  residual) and that 2022 depends only on 2021. A second window is NOT manufactured.
  2021 and 2022 appear as TRAINING rows only. A 2022-eval arm is computed and reported as a
  disclosed contrast, explicitly labelled as resting one step from the degenerate fold, and is
  never a headline.
* Manifests: `row`/`season` granularity usable, `artifact` not, MISSING = UNVERIFIABLE. Both source
  frames are frozen artifacts of screens whose manifests were already cleared (D085 records both
  `master_player` and `master_team` at `asof_granularity 'row'`).

## 1. QUESTION

Does the opponent's prior defensive rating add forecasting information about a player's scoring,
on the rows anyone would bet on, over a base that already carries the plausible incumbents?

And, logically prior to that: **are the four recorded sightings four measurements or one?**

## 2. THE FOUR SIGHTINGS TO BE RECONSTRUCTED (anchors, read from disk before this hash)

| # | ledger | screen | statistic as recorded |
|---|---|---|---|
| 1 | D098 | `E1_I0023_usage_defence_interaction` | dR² +0.023862917871899685 (ppm), +0.018703 (pts), n=1,687, top usage tercile, decision stratum, walk-forward |
| 2 | D099 | `E1_I0025_threshold_vs_refit` | dR² +0.005028 (ppm), +0.003335 (pts), n=4,514, decision stratum, common denominator |
| 3 | D103 | `E1_I0026_detection_floor` | in-sample screening dR² 0.0082–0.0086 vs `y_ppm`, decision stratum, p 0.0017 on both opponent-level nulls |
| 4 | D117 | `E1_I0038_within_entity_null_audit` | dR² 0.001443, n=14,852, p matched `N_ESWAP` 0.001664, family-wise 0.009983 |

## 3. THE INDEPENDENCE TEST — PREREGISTERED, RUN FIRST, AND DECISIVE

Four arrivals at one channel corroborate only if they are four measurements. The following audit is
run BEFORE any new effect size is computed, and its result governs what else this screen does.

Preregistered checks, each a pass/fail assertion written to `INDEPENDENCE.csv`:

* **I1 COLUMN IDENTITY.** For each sighting, resolve the defence column to a physical file and byte
  range. Assert on values whether the four are the same vector. Reported as max |difference| on the
  joined rows, not as a claim about names.
* **I2 ROW SET.** Pairwise intersection and containment of the four row sets, on `(player_id, game_id)`.
  Reported as counts, and as Jaccard.
* **I3 RESPONSE.** Which response each sighting used; count of distinct responses across the four.
* **I4 REFERENCE / BASE.** Which base each sighting scored against.
* **I5 SHARED UPSTREAM.** The provenance chain from each sighting back to a source file. A shared
  source file at the root of all four is the shared-upstream-defect signature the brief names.
* **I6 REDUNDANCY WITHIN THE FAMILY.** Correlation of `A10_opp_defrtg` with the other eleven
  A-family opponent columns, and the rank of the A-family correlation matrix at 99% variance.
  This tests whether D085's "twelve constructions" were twelve tests.

**PREREGISTERED RULE.** If I1 returns the same vector, I2 returns nested row sets, and I5 returns a
single shared source file, **the four sightings are declared ONE sighting, that is recorded as the
finding, and this screen does not escalate.** It still computes the ceiling and the decision-stratum
effect (items 4–7) because those are cheap and because a single sighting still has to be either
alive or dead — but no corroboration credit is taken from the count of four, and no champion,
production change or promotion is proposed under any outcome.

## 4. THE ARITHMETIC CEILING — COMPUTED BEFORE ANY FIT

Computed in D084/D089/E1_I0023's exact form, on the decision stratum, walk-forward, clean window:

* `points_moved_by_1sd = |beta| x sd(centred defence) x mean(minutes estimate)`
* `ceiling_1sd = (points_moved_by_1sd / sd(y_points))^2`
* `ceiling_D084 = (d·d)/SST` where `d` is the forecast shift in points
* ORACLE `(d·e)^2/((d·d)·SST)` is DIAGNOSTIC ONLY and never a headline.

**A matched pure-noise negative control is run through the identical path and its ceiling is
reported beside every real ceiling.** The ceiling statistic has a noise floor and it is not
negligible on small strata; it is quoted, not assumed.

Benchmarks, frozen here before this screen's ceiling exists:

| benchmark | value |
|---|---|
| largest live effect the programme has measured (D089) | **0.002057** |
| single-cell injection-verified detection floor (D103) | **0.00102** |
| 132-cell floor (D103) | **0.00235** |

**PREREGISTERED GATE.** If the ceiling on the decision stratum falls below the single-cell floor of
0.00102, this screen reports that and **does not fit**. If it falls below the 132-cell floor but
above the single-cell floor, that is reported as a bound and the fit proceeds as a one-cell
preregistered test only.

## 5. THE DECISION STRATUM INTERSECTION — REPORTED BEFORE ANY EFFECT SIZE

`DECISION = n_prior >= 8 AND prior5_minutes >= 24` (D081's stratum, the definition
`E1_I0023/s00_prereg.py` used).

`VERDICT.md` will state, before any effect size appears in the document:
the count of rows in the decision stratum; the count in the clean 2023–2024 eval window; the count
of distinct players, opponent-team-seasons and blocks; and the intersection of the decision stratum
with each of the four sightings' row sets. A gain on rows that are not decision-relevant is not a
gain, and D119's `+3.51%` on zero bettable rows is the reason this clause exists.

## 6. THE BASE — INCUMBENTS IN FROM THE START (D108's lesson)

Three nested bases. Every one of them is an EXPLICIT ALLOWLIST. No substring, prefix or regex
selection of columns occurs anywhere in this screen; every resolved list is printed and its length
asserted against a literal.

| id | columns | n | purpose |
|---|---|---|---|
| `B0_COMPLETE` | `refB_ppm`, `refB_spm`, `refB_pps`, `refB_mpg`, `refB_own_usg_pg` | 5 | E1_I0023's complete player reference. The floor. |
| `B1_HONEST` | `B0` + `D01_tm_poss_per40`, `D02_opp_poss_per40` | 7 | adds the pace incumbents. Opponent defensive rating is points allowed per possession; a base with no possession term hands it a free ride. |
| `B2_FAMILY` | `B1` + `A01_opp_efg_allowed`, `A02_opp_ts_allowed` | 9 | **is it already in the model?** The increment of `A10` over the rest of its own family. |

**The headline increment is over `B1_HONEST`.** `B0` is reported as the reference-sensitivity
contrast and is never the headline. `B2` answers item 5 of the brief directly.

D087 REFERENCE INCOMPLETENESS: coverage counts are asserted for every base column — non-null count,
finite count, and the count of rows dropped by complete-casing — and printed. A reference silently
covering part of the rows is the failure mode; the assertion is the guard.

## 7. THE EFFECT, FROZEN AND UNFROZEN (E1_I0042's lesson)

For each fold, fit the base on the training rows. Then two augmented arms on identical rows:

* **UNFROZEN** — refit the whole augmented model (base + defence) on the training rows. Every
  coefficient including the intercept is free. This is the conventional dR².
* **FROZEN** — hold the intercept AND every base coefficient at the base model's fitted values and
  estimate ONLY the defence coefficient, on the training residual. The base's prediction is
  untouched; the defence term may only move rows away from it.

**Both are reported side by side in the first three sentences of `VERDICT.md`.** If the effect
vanishes when the intercept is frozen, that is the headline: the channel is shared-intercept
movement, not opponent information. E1_I0042 found a component scoring +0.0287 at p 0.00005 on rows
where it substitutes nothing at all; this is the check that would have caught it.

A third arm, **INTERCEPT_ONLY**, adds a free intercept shift and NO defence column, so the
intercept's own contribution is measured rather than inferred.

## 8. STATISTIC AND DENOMINATOR (D101)

`dR2 = (SSE_base - SSE_aug) / SST` with, across both arms of every contrast and every null draw:
identical response, identical row set, identical SST basis, identical (unit) weighting, identical
base. SST is computed once per cell on the eval rows and reused. Signed statistics are stored;
absolute values are never stored. Every critical value is derived on the scale it is applied to —
a dR² bar is never applied to a t, and no bar is imported from another cell.

## 9. NULLS — MATCHED TO THE LEVEL THE CANDIDATE VARIES AT

`A10_opp_defrtg` is a **team-season quantity** measured at `opp_team_game`. A within-player null is
structurally blind to it (measured p=1.0000 in 0/15 planted configurations; it killed a real rebound
signal that way). Both nulls here are BETWEEN-entity:

| id | scheme | permuting unit |
|---|---|---|
| `N_ESWAP` | relabel opponent-team-season identities, within season | opponent-team-season |
| `N_DATE` | swap opponent assignment within game date | opponent-team-game within date |

* `N_WITHIN` (within-player cyclic) is computed as a **CONTRAST ONLY** and is never a verdict, so
  the blindness is demonstrated in this screen rather than asserted from another one.
* **The candidate is a single column, not a composite**, so D120's every-component invariant is
  satisfied trivially — and that is asserted, not assumed, by checking the candidate list has
  length 1.
* **Validity is established by COMPONENT-WISE INJECTION, not by shuffled residuals.** A known effect
  of size δ is planted on the between-opponent-entity component of the response and the null's power
  to detect it is measured. The null-centre ratio check (E1_I0038's cheap drop-in) is reported
  beside it: `injection null mean / verdict null mean`. A ratio far from 1 means the injection
  graded a different null from the one that decided the cell.
* **Block counts are reported for every cell.** `p_min = 2^(1-nb)` is printed for any sign-flip
  arm; below six blocks a two-sided sign-flip cannot reject and any such cell is reported as
  ARITHMETICALLY INCAPABLE rather than as a null result. `t_crit` is checked against `sqrt(nb)`.
* **Every floor quoted is labelled INJECTION-VERIFIED or ANALYTIC.** The analytic rule is
  anti-conservative by up to 1.27x at 8 blocks and no analytic MDE is used as a bar.
* **Every stratum arm of every null is saved** to `nulls/*.npz`, RAW and UNSTANDARDISED, with the
  observed statistic, the block count, the scheme and the stratum key in the archive. Standardising
  draws destroys the null mean irrecoverably (E0_I0017 lost 117 cells that way).

`N_DRAWS = 2000`. `SEED = 20260808`.

## 10. CELL COUNT AND FAMILY

Preregistered cells: **2 responses (`y_ppm`, `y_pts`) x 3 bases x 2 arms (frozen/unfrozen) = 12**,
on ONE stratum and ONE window. Plus 2 negative-control cells and 1 intercept-only cell per response.
D103 ruling 1 says narrow, preregistered screens are worth 1.9–2.3x for free; this screen is 12
cells, not 132. The primary cell is declared:

> **PRIMARY: `A10_opp_defrtg` -> `y_ppm`, decision stratum, base `B1_HONEST`, UNFROZEN,
> walk-forward eval 2023–2024, null `N_ESWAP`.**
> **CO-PRIMARY: the same cell with the intercept FROZEN.**

`y_ppm` is primary because it is the response all four sightings share; making it primary is what
lets this screen speak to them.

## 11. ANCHOR REPRODUCTION BEFORE ANY NEW STATISTIC

At least one prior anchor must reproduce EXACTLY before this screen generates a statistic. The
anchor set, all read from other screens' artifacts:

| id | anchor | source |
|---|---|---|
| A1 | dR² 0.001443 for `A10_opp_defrtg -> ppm`, n 14,852 | `E0_I0016/screen_results.csv` |
| A2 | p_N2_entity_swap 0.001664, p_familywise_N2 0.009983 | same |
| A3 | var_share_between_entity 0.771356 | same |
| A4 | ceiling 0.012808, points_moved_by_1sd 0.739198 (D098's headline lever) | `E1_I0023/arithmetic_ceiling.csv` |
| A5 | realised paired dR² 0.003335 (pts) on n 4,514 (D099's corrected headline) | same |
| A6 | D093 Spearman 0.3200431235648813 | `E1_I0023/_prereg.json` |
| A7 | frame row count 14,852 on both source frames | both parquets |

Failure of any anchor halts the screen and is reported as the result.

## 12. WHAT THIS SCREEN WILL NOT DO

* No champion is fitted. No production change is enacted. No promotion is proposed.
* Nothing outside `experiments/exploration/E1_I0043_opponent_defence/` is written, staged or
  committed. The shared screen kit is not imported and not modified.
* No process is killed that this screen did not launch, and any PID it launches is recorded.
* No retrospective baseline: every reference column is verified strictly prior by construction in
  the source frames, and the eval-fold statistic never sees its own fold's coefficients.
* The result that most weakens this screen's own conclusion is reported in the same document as the
  conclusion.

## 13. DECISION RULE

The channel is called ALIVE only if ALL of:

1. the decision-stratum intersection is non-trivial (>= 500 eval rows on the clean window), AND
2. the ceiling on the decision stratum exceeds the single-cell floor 0.00102, AND
3. the PRIMARY cell's dR² over `B1_HONEST` exceeds the injection-verified single-cell floor, AND
4. the CO-PRIMARY (frozen intercept) retains at least half the unfrozen effect, AND
5. `N_ESWAP` p < 0.05 with a reported block count >= 6, AND
6. the increment over `B2_FAMILY` is not zero — i.e. it is not already in the model.

Any failure is recorded as the verdict. **Killing this channel is an acceptable and expected
outcome.** A lead, if one survives, is an E0 LEAD and nothing more.
