# WITHIN-ENTITY NULL AUDIT -- VERDICT

Screen `E1_I0038_within_entity_null_audit` · preregistration `PREREG.md`
sha256 `09ccb1faa88582a70fb71aa48621d2fb66ed3bc23bda1391efa1963b2fe2d5d3`
Commissioned by **D115**. Partition: 2021-2024 exploration only. 2025/26 never opened.

---

## HEADLINE (first three sentences, as required)

**Of the 1,580 killed cells in the programme's census, 83 are structurally EXPOSED to the
within-entity null failure — 5.3% of the killed record, not the 550 D115 feared — and 0 are
undeterminable.** The `null_mean > observed` flag can be computed on 1,756 cells and trips on
632 of them, but as a detector of real exposure it has a **positive predictive value of 0.146**:
403 of the 472 flagged cells are structurally fine, so D115's proposed universal diagnostic is
a screen, not a verdict. **The negative record survives this third challenge in bulk but not
intact: the matched null was already on disk for all 83 exposed cells, 52 of them flip
per-cell, and 11 clear the family-wise bar under it — all 11 inside D085, whose published
"nothing clears" headline is the one conclusion this audit does materially weaken.**

---

## THE COUNTERWEIGHT, IN THE SAME BREATH

D115 said "550 killed cells sit at entity levels exposed to this failure". That number is
reproduced here exactly (213 at `player_season` + 337 at `opp_team_season`, and 299/427 with
survivors included — both anchors reproduce to the unit). **But sitting at an exposed LEVEL is
not the same as having been DECIDED by an exposed NULL.** Of the 550:

* **560 of the cells at those levels come from D108's own screen `E0_I0029`, which computed the
  cyclic null and then explicitly excluded it** (`p_N_CYCLIC_EXCLUDED_no_power`, 284 cells).
  Every one of its 560 cells was decided by `N_PSWAP`, `N_ENTITY` or `N_ROW`. **D108 already
  fixed its own screen. Zero exposed.**
* D097's 250 cells contribute 16 exposed, all of them the `R08_player_ra_share` family already
  discharged by `E1_I0036`.
* D085's 132 cells contribute 65 — **the real, previously unexamined population.**

So the exposure is 6.6x smaller than the level-based estimate, and it is concentrated in one
screen that D115 did not name.

---

## WHAT WAS ACTUALLY MEASURED

`AUDIT_TABLE.csv` — **1,999 cells, 41 columns**, one row per recorded cell, each carrying the
null scheme used, the level the null permutes at, the level the candidate varies at, the null
mean, the observed statistic, p, the recorded verdict, and the exposure classification **with
its evidence source**. Positional join to `E1_I0036/CENSUS.csv` verified exact on candidate AND
target for all 1,999 rows.

### The decision null, per killed cell

| decision null class | all kills | non-ceiling kills |
|---|---|---|
| BETWEEN_ENTITY (entity swap, block reassignment, cluster sign-flip) | 1,051 | 962 |
| **WITHIN_ENTITY (within-shuffle, cyclic shift)** | **424** | **340** |
| ROW (free shuffle) | 105 | 65 |
| UNDETERMINABLE | 0 | 0 |

### Exposure (frozen rule, PREREG 3: within-entity null AND between-entity share >= 0.50)

| | cells |
|---|---|
| **EXPOSED** | **83** |
| NOT_EXPOSED | 1,284 |
| CEILING_EXCLUDED (excluded by rule, not re-measured) | 213 |
| **UNDETERMINABLE** | **0** |
| (surviving cells, not counted) | 419 |

**Of the 340 non-ceiling kills decided by a within-entity null, 257 had a between-entity share
BELOW 0.50 — the null was the right instrument and the kill stands.** Only 83 were decided by
a null that provably could not see where the candidate varies.

Sensitivity to the threshold, preregistered: **143 exposed at 0.30, 83 at 0.50, 35 at 0.80.**

### By screen

| screen (decision) | exposed | not exposed | why |
|---|---|---|---|
| `E0_I0014` (D078/D082) | **0** | 320 | **immune by design** — its code sets `use_between = var_share > 0.5` and runs the matching null. The kit's own rule, applied. |
| `E0_I0016` (D085) | **65** | 59 | `p_correct = max(p_within, p_swap)` — the conjunction |
| `E0_I0017` (D087) | 0 | 86 | entity swap only |
| `E0_I0019` (D090) | 0 | 235 | **repaired to between-only** before publication ("two schemes, two questions, no max()") |
| `E0_I0024` (D097) | **16** | 4 | `p_correct = max(p_swap, p_cyclic)` — the conjunction |
| `E0_I0029` (D108) | **0** | 381 | **cyclic computed and explicitly excluded** |
| `E1_I0018` (D089) | **2** | 88 | conjunction, but its candidates' between-team-season share is low (median 0.15) |
| `E1_I0023` (D098/D099) | 0 | 111 | whole-cluster sign-flip only |

## THE ACTUAL MECHANISM, AND IT IS NOT "THE WRONG NULL WAS CHOSEN"

**No screen in this census pointed a within-entity null at a between-entity candidate by
mistake.** Every screen that used a within-entity null also ran the correctly matched
between-entity null in the same pass. The failure is the *combination rule*:

> **Three screens (D085, D089, D097) took `p_correct = max(p_within, p_between)` — "a candidate
> is credited only if it beats BOTH nulls". A blind null cannot be beaten. For a between-entity
> candidate that conjunction makes the verdict unfalsifiable.**

D085's family-wise p compounds it: `p_familywise_maxt = max(p_familywise_N1, p_familywise_N2)`,
so the blind arm vetoes at the headline level too.

The conjunction was adopted as *conservatism*. It is conservatism only when both nulls are
valid; when one is blind it is not a higher bar, it is an unreachable one. **This is the third
time in this ledger that a rule generalised from a well-measured case turned out to carry an
unstated scope condition (D108's preserved disagreement predicted exactly this).**

## THE MATCHED NULL WAS ALREADY ON DISK — D115 RULING 1 IS ANSWERED WITHOUT A SINGLE REFIT

Because the conjunction screens ran both arms, the correctly matched between-entity p is
**recorded for all 83 exposed cells**. `MATCHED_NULL_RECHECK.csv`:

| | cells |
|---|---|
| exposed | 83 |
| ... actually vetoed by the within-entity null (its own p >= 0.05) | **80** |
| ... matched between-entity p already recorded | **83 of 83** |
| ... matched null clears **per-cell** p<0.05 | 55 |
| ... **VERDICT FLIPS** (vetoed by the blind null, cleared by the matched one) | **52** |
| ... matched null clears **family-wise** p<0.05 | **11** (of 67 with a recorded family-wise p) |

**All 11 family-wise clears are in D085.** D085 published **8** family-wise survivors under
`max(N1, N2)`; under the matched entity-swap arm alone its structurally-exposed cells add
**11 more**. Named, largest first, with their published verdict and their matched-null p:

| candidate → outcome | n | dR2 | share between | p (blind null used for the kill) | p (matched, already on disk) | p family-wise (matched) |
|---|---|---|---|---|---|---|
| `B03_pl_fouls_drawn_per36` → ts | 14,079 | 0.002471 | 0.900 | 0.9983 | 0.001664 | **0.001664** |
| `E02_pl_paintpts_share` → efg | 13,950 | 0.001862 | 0.909 | 0.0948 | 0.001664 | **0.003328** |
| `B06_pl_ftpts_per36` → ts | 14,079 | 0.001794 | 0.874 | 1.0000 | 0.001664 | **0.003328** |
| `A10_opp_defrtg` → ppm | 14,852 | 0.001443 | 0.771 | 0.8702 | 0.001664 | **0.009983** |
| `E01_pl_fg3a_share` → ts | 14,073 | 0.001221 | 0.963 | 0.2596 | 0.001664 | **0.009983** |
| `B03_pl_fouls_drawn_per36` → ppm | 14,852 | 0.001172 | 0.896 | 1.0000 | 0.001664 | **0.003328** |
| `C02_tm_ast_per_game` → efg | 13,989 | 0.001012 | 0.850 | 0.9917 | 0.001664 | **0.033278** |
| `C03_tm_ast_rate` → efg | 13,989 | 0.000958 | 0.883 | 0.7454 | 0.001664 | **0.036606** |
| (+ 3 more that the within null did not veto but `p_familywise_maxt` did) | | | | | | |

**`A10_opp_defrtg → ppm` is the fourth independent sighting of the opponent-defence signal**
after D098, D099 and D103's incidental observation — and the first from a cell the programme
had recorded as dead.

### What this does NOT say

* **D089 is untouched.** 2 exposed cells, 0 clearing anything.
* **D097 is unchanged from `E1_I0036`.** Its 16 exposed cells are the `R08` family already
  discharged, and D097 recorded no family-wise p under the swap arm, so 0 of 16 can be said to
  clear family-wise here.
* **D090, D087, D078/D082, D098/D099 and D108 are entirely unaffected.** That is 1,133 of the
  1,367 auditable kills — 82.9% — with zero exposed cells.

## THE `null_mean > observed` FLAG — D115 RULING 1's CHEAP DIAGNOSTIC, MEASURED

| | cells |
|---|---|
| statistic scale permits the flag at all (dR2 or `\|t\|`) | 1,762 / 1,999 |
| ... null mean **recorded by the screen itself** | 846 |
| ... null mean **recovered by this audit from raw `.npz` draw archives** | 916 |
| ... no null mean available anywhere | **0** |
| flag **vacuous by construction** (sign-flip null, symmetric about zero) | 120 |
| flag **destroyed by standardisation** (draws stored as z-scores) | 117 |
| flag computable | 1,756 |
| **flag TRIPS** | **632** |

**Answering D103 ruling 2 directly: only 846 of 1,999 cells (42.3%) had a null mean written
beside their p. But the raw draws survive for every screen that lacked one, so the diagnostic
is recoverable for 1,756 of 1,999 (87.8%) and is permanently lost for 237** — 120 because a
sign-flip null is symmetric by construction (nothing was lost; the diagnostic simply does not
apply) and **117 because `E0_I0017` stored its draws standardised to mean zero, which erases
the null mean irrecoverably.**

### As a detector, it is weak (n = 1,170 determinate killed cells)

| | EXPOSED | NOT_EXPOSED |
|---|---|---|
| flag trips | 69 | **403** |
| flag silent | 14 | 684 |

**sensitivity 0.831 · specificity 0.629 · positive predictive value 0.146.**

The reason is structural and was foreseeable: `null_mean > observed` fires in two different
situations — (i) the null contains the effect (the D-04 failure) and (ii) *there is no effect*,
which describes most of a negative record. It fires on `G01_noise`, D097's own designated noise
placebo (null mean 4.82e-05 vs observed 1.67e-05), where the cyclic null is provably valid.
`E1_I0036` reported it "fired on 2 of 2 affected cells here" — a sample of two. On 1,170 cells
it is a screen, not a verdict.

**A magnitude-aware form is much better** (post-hoc, disclosed, `FLAG_REFINEMENT_Z.csv`,
computable on the 234 cells whose screen recorded a null *sd* as well as a mean):

| rule | sensitivity | specificity |
|---|---|---|
| `null_mean > observed` (D115's proposal) | 0.831 | 0.510 |
| `z = (observed - null_mean)/null_sd < -0.5` | 0.699 | 0.722 |
| **`z < -1.0`** | **0.446** | **0.980** |
| `z < -1.5` | 0.277 | **1.000** |

D097's `R08` sits at z = -2.4. **Recommendation: publish the flag, act on z < -1.0.**

---

## D-04: THE INJECTION PROTOCOL. VERDICT: THE DEFECT IS REAL, ITS STATED CAUSE IS WRONG

`INJECTION_PROTOCOL_D04.md` · working code `scripts/d04_protocol.py` · results
`D04_SCORECARD.csv`, `D04_MECHANISM.csv`, `D04_CONFIRM_NREP250.csv`.

**Two anchors reproduced before anything was computed:**

* **A1** `dR2 = 0.0064881160` on exactly **13,784** rows (D097 recorded 0.006488; diff 1.2e-07).
* **A2, new and never quoted before:** the mean of **D097's own on-disk cyclic null draws**
  (`E0_I0024/permutation_draws.npz`, key `POOLED|y_oreb|B_COMPLETE|R08_player_ra_share`) is
  **0.0078802401**, which is **1.2146x the observed statistic**. *The flag was sitting inside
  D097's own permutation archive from the day it was written.* Nobody had opened it.

### The preregistered scorecard — 4 of 5, and the one that failed matters

| run | result |
|---|---|
| **R1** ORIGINAL D108 protocol on `N_CYCLIC` | **CERTIFIED** — power 0.93 @ 0.002057, type-I 0.07, MDE80 1.62e-03. (`E1_I0036` reported 0.95 at 100 replicates; reproduces.) |
| **R2** D-04's stated mechanism: shuffling residuals destroys the response's between-entity structure | **FAILED.** The residual's between-player-season variance share moves only **0.0396 → 0.0337, a factor of 1.17.** It is not destroyed. |
| **R3** AMENDED protocol on `N_CYCLIC` | **VOID_FOR_THIS_CANDIDATE** — power **0.00** on the BETWEEN component at *every* delta tested, while that component carries **95.3%** of the measured effect. |
| **R4** AMENDED protocol on `N_PSWAP` (positive control) | **USABLE** — power 1.00 on the dominant component, type-I 0.067, MDE80 4.23e-04. The amendment does not reject valid nulls. |
| **R5** AMENDED protocol on `N_CYCLIC` against a genuinely within-varying candidate (specificity control) | **USABLE** — `G01_noise`, 96.6% of its variance within player-season, dominant component WITHIN, power 1.00. The amendment does not condemn cyclic nulls as a class. |

**R2 is kept as FAILED and is not rewritten.** D-04 named the wrong quantity. The defect is
real — R1 certifies and R3 voids the same null on the same cell — but the cause is not a
marginal, it is a joint:

| quantity | real response | synthetic response | collapse |
|---|---|---|---|
| residual's between-entity variance **share** (what D-04 named) | 0.0396 | 0.0337 | **1.17x** |
| corr(entity-mean carrier, entity-mean residual) — the **alignment** | **+0.4407** | −0.0059 | **74x** |
| **the `N_CYCLIC` null's own mean** | **7.882e-03** | 4.731e-05 | **167x** |

A cyclic shift preserves each entity's carrier mean exactly, so the one thing it can never
destroy is the alignment between entity-mean carrier and entity-mean residual. Shuffling the
residual destroys that alignment even though it barely touches the variance share.

> **The injection test was grading a completely different null distribution from the one that
> decided the cell.** That is the defect, in the currency that decides a permutation test.

### The consequence is a cheaper fix than the one proposed

Because the defect is a mismatch between two null distributions, it is detectable **without any
component decomposition at all**: compare the null mean the injection generates against the null
mean the real verdict was taken from.

| null | verdict null mean | injection null mean | ratio | drop-in check |
|---|---|---|---|---|
| `N_CYCLIC` | 7.882e-03 | 4.731e-05 | **167x** | **FAIL** |
| `N_PSWAP` | 7.551e-05 | 5.492e-05 | 1.37x | PASS |

This costs one line, needs no entity decomposition, and requires nothing the injection loop was
not already computing. It is recommended **in addition to** component-wise injection, not
instead of it: component-wise injection tells you *which* component is blind, the centre-ratio
check tells you *that* the certification is meaningless.

### The demonstration that matters, at a replicate count that can carry it

The 60-replicate runs cannot carry a hard 0.80 threshold (se 0.052; see DEFECTS D-03), so the
**shipped module `scripts/d04_protocol.py::verify_null` was re-run end to end at nrep = 250**
(se 0.025) on the same cell — `D04_CONFIRM_NREP250.csv`:

| check | result |
|---|---|
| ORIGINAL D108 protocol still CERTIFIES `N_CYCLIC` | **PASS** — power 0.908, type-I 0.040 |
| AMENDED protocol REJECTS `N_CYCLIC` | **PASS** — `INJECTION_TESTED_A_DIFFERENT_NULL`; power on dominant component **0.012**, null-centre ratio **155.4x** |
| AMENDED protocol ACCEPTS `N_PSWAP` | **PASS** — power 1.000, type-I 0.044, null-centre ratio **1.47x** |

**3 of 3 at a replicate count that can carry the threshold.** The `z` form separates the two
nulls by 60 standard deviations (`N_CYCLIC` z = −2.41, `N_PSWAP` z = +58.6) where the raw flag is
a single bit. At 250 replicates the blind null's power on the dominant component reads 0.012
rather than 0.000 — 3 detections in 250, consistent with a fraction of the type-I rate. The
verdict is unchanged and the number is more honest than the 60-replicate zero.

---

## RE-MEASUREMENT: 4 CELLS, ALL ANCHORS EXACT, ALL LEADS NOT FINDINGS

The frozen triage rule (PREREG 5.1/5.2) left **27 of 83 exposed cells** eligible — the rest sit
below D103's single-cell floor of 0.00102, where no null can produce a lead. Top 5, max 2 per
screen, yielded **4** because only two screens contribute eligible cells.

**The 213 arithmetic-ceiling kills were EXCLUDED BY RULE AND NOT RE-MEASURED.** They are named
in `CEILING_EXCLUSIONS.csv` (16 distinct candidates). A ceiling kill is arithmetic and survives
every methodological revision, including this one.

| cell | n | dR2 (reproduced to <1e-16 of recorded) | p, blind null | **p, matched `N_ESWAP`** | amended verdict on the matched null | MDE80 (injection-verified) | obs / 132-cell floor |
|---|---|---|---|---|---|---|---|
| `R08_player_ra_share → y_oreb`, `B_COMPLETE_PLUS_R10` | 13,784 | 0.006540 | 0.9950 | **0.001661** | USABLE | 4.22e-04 | **2.78x** |
| `R08_player_ra_share → y_oreb`, `B_COMPLETE` | 13,784 | 0.006488 | 0.9967 | **0.001661** | USABLE | 4.22e-04 | 2.76x |
| `B03_pl_fouls_drawn_per36 → ts` | 14,079 | 0.002471 | 0.9983 | **0.001661** | USABLE | 4.23e-04 | **1.05x** |
| `E02_pl_paintpts_share → ts` | 14,036 | 0.002320 | 0.0033 | **0.001661** | USABLE | 4.26e-04 | **0.99x** |

`p = 0.001661` is the minimum attainable at R = 601 draws. **Every MDE80 above is
injection-verified, not analytic** — no analytic MDE80 appears anywhere in this screen, per
D113.

**The counterweight, stated with the result:**

1. `E02_pl_paintpts_share → ts` is at **0.99x the 132-cell floor** — *below* it. It is not a
   lead. `B03_pl_fouls_drawn_per36 → ts` is at 1.05x, which is not a margin.
2. The `R08` result **adds one cell to `E1_I0036`'s finding and changes nothing about it**. The
   `B_COMPLETE_PLUS_R10` variant is the more D087-complete reference and it does not shrink
   (0.006540 vs 0.006488) — the only genuinely new number, and it is a lead in-sample only.
3. Everything here is **in-sample**. No walk-forward, no season stability, no out-of-sample
   propagation.
4. **Every reinstated cell is labelled E0 LEAD. None is a finding, none is a champion, none is
   proposed for production.**
5. D085's own D103 record says **53 of its 132 cells were blind to the programme's best live
   effect**. Correcting the null does not correct the power. Several of the 11 flips are
   probably still uninformative for that separate reason, and this screen did not re-run D103's
   power audit on them.

---

## DOES THE NEGATIVE RECORD SURVIVE ITS THIRD CHALLENGE?

**In bulk, yes.** 1,284 of 1,367 auditable kills (94.0%) are not exposed. Five of eight screens
have **zero** exposed cells, and three of those five were immune *by design* — `E0_I0014`
selected its null by the variance share exactly as the kit prescribes, `E0_I0029` computed the
cyclic null and threw it away, `E0_I0019` repaired its own conjunction out before publishing.
**The programme's null machinery was mostly right, and where it was right it was right on
purpose.**

**In one place, no.** D085's conclusion — "defensive matchup does not predict efficiency,
0 of 330 rate cells" — rests on a rule that required candidates to beat a null which, for 65 of
its cells, could not be beaten. Eleven of them clear the family-wise bar under the matched null
that D085 itself computed and then discarded by taking a maximum. **That is a real correction
to a real ledger verdict, and it was recoverable by reading a column.**

**And the verification machinery is worse than D115 thought, not better.** D115 proposed
`null_mean > observed` as the cheap universal diagnostic; measured on 1,170 cells its positive
predictive value is 0.146. D-04's stated mechanism does not hold; the real one is 74x larger and
sits in a different quantity. The injection protocol's own CERTIFY/VOID decision is unstable at
the replicate counts the programme has been using. **Three of the programme's guarantees have now
been checked by someone who did not build them, and all three needed correcting — which is
exactly the posture D115 recommended and the reason it was right to commission this.**

## WHAT WOULD CHANGE THIS VERDICT

* **The 30 screens outside the census are not audited.** 47 `FINDINGS.json` across 38 screens
  exist; the census covers 8. Ten out-of-census screens mention a within-entity scheme and four
  carry within-entity p columns in cell tables (`E1_I0021`, `E1_I0022`, `E1_I0027`, `E1_I0030`,
  ~188 cell rows). **Their exposure is UNKNOWN, not zero.** See `CENSUS_COVERAGE.csv`.
* **D090's counterfactual.** Its published rule is between-only and it is clean. Under the
  *superseded* pre-repair `max()` rule the within arm would have decided 117 of 318 cells and
  **70 would have been exposed** — nearly doubling this audit's total. D090 also self-flagged
  `within_null_degenerate` on 144 of 318 cells in its own repair, long before D115. **The
  programme had this diagnostic and did not generalise it.**
* **The 11 D085 flips need a power check, a family recomputation and a walk-forward** before any
  of them is more than a lead.
* **The exposure threshold.** At 0.30 the count is 143, at 0.80 it is 35. The headline uses
  0.50 because that is the threshold `E0_I0014`'s own code already used; it was not chosen to
  flatter this screen.
