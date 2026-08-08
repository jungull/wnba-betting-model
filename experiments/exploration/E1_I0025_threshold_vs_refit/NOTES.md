# E1_I0025 — THRESHOLD vs REFIT ARTEFACT — NOTES

Confirmation of the lead raised by **E1_I0023 / D098** and **raised-and-not-accepted** by the
coordinator.

Preregistration SHA-256: `0daa5165d4469cab26db68ccace4cd4cf54af3ad117ed59815fc699fabe2dc4b`
Specifications added after preregistration: **0**. Dropped: **0**.

---

## 0. THE DECISION RULE, STATED BEFORE ANY NUMBER WAS COMPUTED

Written into `c00_prereg.py` and hashed before the first statistic. Let

- **G_refit** = D098's statistic: the defence increment inside a tier-restricted refit, ppm,
  decision stratum, top usage tercile (+0.023863);
- **G_step** = the same increment from a **pooled** model carrying a tier-dummy × defence term,
  scored on the identical rows;
- **F** = G_step / G_refit;
- **R_nodef** = the refit's own contribution, with **no defence column in either arm**;
- **Q95_rand** = 95th percentile of G_refit over size-matched **random** tiers.

**THRESHOLD** required *all* of: F ≥ 0.60; G_step > 0 at swap p < 0.05; R_nodef < 0.50·G_refit;
Q95_rand < 0.50·G_refit; the negative control clean; max(|T1|, T2) < 0.50·G_refit.

**REFIT ARTEFACT** on *any* of: R_nodef ≥ G_refit; Q95_rand ≥ 0.60·G_refit; the random-tier
one-sided p ≥ 0.05; (F ≤ 0.15 and Q95_rand ≥ 0.30·G_refit); the negative control ≥ 0.50·G_refit.

**UNRESOLVED** otherwise, stating exactly which criterion failed.

**Reproduction gate:** |reproduced − published| < 1e-9 on both of D098's anchors, or the screen
stops.

---

## 1. VERDICT: UNRESOLVED

**REFIT ARTEFACT is refuted. THRESHOLD as framed is not supported. The lead survives as a real
effect and is substantially smaller and substantially less exotic than its headline.**

The preregistered rule, applied mechanically and without adjustment, returns **REFIT ARTEFACT** on
both responses. **Two of its clauses fired and both are wrong proxies for the hypothesis they were
written to test.** That is a defect in *this screen's own preregistration* and it is published in
full in §5 rather than quietly repaired. The direct measurements that settle the question are
reported here and the disagreement is left visible.

---

## 2. THE NUMBER THAT WAS ASKED FOR

Everything below is walk-forward, decision stratum, **COMPLETE** prior reference, scored on the
**identical 1,687 top-tercile rows** D098 scored, with SST taken on those rows — D098's dR2
definition exactly.

| rung | what it is | ppm | points |
|---|---|---|---|
| **L1** | pooled, **one** defence coefficient, no tiers, no interaction | **+0.016772** | +0.013553 |
| **L2** | pooled, defence + **linear** usage × defence | +0.021237 | +0.018835 |
| **L3** | **pooled, tier-dummy × defence — THE TEST D098 NAMED AND DID NOT RUN** | **+0.021986** | **+0.017707** |
| **L4** | tier-restricted refit + defence — **D098's +0.023863** | +0.023863 | +0.018703 |

**Recovery fraction F = 0.921 (ppm) and 0.947 (points).** A pooled model with **no tier-specific
baseline coefficients anywhere** recovers 92–95% of the gain. Against D098's anchors: the answer is
`+0.024`, not `+0.0002`.

Every rung clears the within-date opponent-swap null at the 500-draw floor (p 0.0020); L3's z is
+10.45 and L4's is +12.80.

### The decomposition of D098's +0.023863

| component | share |
|---|---|
| a **single pooled defence coefficient**, no volume heterogeneity of any kind | **70%** |
| adding a **linear** usage × defence interaction | +19% |
| making the slope a **step** rather than a line | **+3%** |
| the **full tier-restricted refit** on top of that | +8% |

**Seventy per cent of the headline is a pooled main effect scored on high-volume rows.** The
non-linearity that the word "threshold" refers to is worth three per cent.

### Why the +0.024 / +0.0002 tension was never a tension

They are different contrasts on different row sets. `+0.0002` is a *linear interaction's increment
over a model that already carries defence*, scored on all **4,514** decision rows. `+0.024` is *the
whole defence family's increment over a no-defence model*, scored on **1,687** top-tercile rows.
Put on the same footing, the linear interaction on those 1,687 rows is **+0.004466**, not +0.0002.

**But the step genuinely does beat the line.** On the full decision stratum the tier step adds
**+0.003317** over one pooled coefficient where the linear interaction adds **+0.000203** — a factor
of 16. That increment clears the opponent-swap null at **z = +3.55, p = 0.0020**
(`concentration_increment_null.csv`, labelled post-hoc).

---

## 3. SEPARATING THE REFIT FROM THE SIGNAL

| measurement | ppm | reading |
|---|---|---|
| **refit WITHOUT defence** (no defence column in either arm) | **+0.033319** | the top tercile *does* have different baseline relationships, and that is worth **more than the defence term** |
| the same on the **middle** tercile | +0.033762 | **the refit gain is generic — it is not about high-volume players** |
| the same on the **bottom** tercile | −0.004837 | |
| **transplant**: freeze the **pooled** non-defence coefficients, add only a defence term | **+0.023659 (99%)** | **the defence gain needs no refit at all** |
| **transplant**: freeze the **tier** non-defence coefficients, add only a defence term | +0.023295 (98%) | |
| defence gain on the **middle** tercile | +0.005179 | **the defence gain is specific to the top tercile** |
| defence gain on the **bottom** tercile | −0.004077 | |

The two effects are **additive and orthogonal**: D098's statistic already carries the refit in
*both* arms, so the refit cannot flow through the defence column. The refit is generic across
terciles; the defence gain is not. And adding defence to a model that *already* has tier-specific
baselines (L4, +0.023863) buys **more** than adding it to one that does not (L3, +0.021986) — if
defence were proxying for the missing tier baseline structure the ordering would be reversed.

### The concentration is real in absolute units, not a denominator effect

The **identical** pooled coefficient, the **same** fitted model, only the scored rows changing:

| | total | T1 | T2 | **T3** |
|---|---|---|---|---|
| SSE reduction, ppm | +1.1378 | −0.0472 | −0.1656 | **+1.3506** |
| SSE reduction, points | +864.59 | −81.06 | −326.96 | **+1272.61** |

The top tercile accounts for **119%** (ppm) and **147%** (points) of a reduction that is **negative**
in the other two terciles. sd(T3)/sd(all) = 0.976, so the subset is not simply a lower-variance
target. **The defence term helps high-volume rows and actively hurts everyone else.**

### The random-tier null — and this is the thin part

Refitting a **size-matched random subset** and adding a defence column, 500 draws each, the whole
walk-forward redone inside every draw:

| variant | null mean | null sd | null p95 | observed | one-sided p |
|---|---|---|---|---|---|
| within-season row shuffle | +0.005339 | 0.010056 | +0.016327 | +0.023863 | **0.0180** |
| player-season blocks, size-matched | +0.008385 | 0.051602 | +0.019806 | +0.023863 | **0.0459** |

The null is **correctly centred on the genuine pooled effect** (+0.0053 against the pooled
all-tiers dR2 of +0.0050), which is what it should be. The observed value clears, but **only just**.
This is the honest measure of "is the top tercile special relative to any equally sized subset", and
it is far weaker than the z = +12.80 the headline rests on. **The opponent-swap null holds the
subset fixed and permutes the defence column; it cannot address whether the subset is special.** The
coordinator's stated reading — that the swap null argues for THRESHOLD — is therefore not supported
by that null, exactly as the coordinator warned it might not be.

---

## 4. WHERE THE HEADLINE OVERSTATES ITSELF

D098 quotes a ceiling of **0.01280821**, "6.23× D089's 0.002057, the largest the programme had
measured". **That comparison was not verified here and should not be relied on.** The ceiling was
computed on the same 1,687-row subset, whose SST is **36%** of the decision stratum's. The dR2 on
that subset is inflated roughly **2.8×** relative to a common-denominator reading: the pooled
coefficient's gain is **+0.016772** against the subset's own SST and **+0.005968** against the whole
stratum's. **I did not recompute the ceiling** — that is named in §6 as what would resolve it.

---

## 5. DISCLOSURE — WHERE THIS SCREEN COULD HAVE CHEATED, AND WHERE IT DID

**Every item is a real fork where a more flattering or a more decisive number was available.**

1. **MY OWN PREREGISTERED RULE RETURNED A VERDICT I DID NOT ADOPT, AND THAT IS THE MOST IMPORTANT
   THING ON THIS PAGE.** The rule mechanically returns **REFIT ARTEFACT**. I report **UNRESOLVED**.
   Two clauses fired:
   - **`R_nodef ≥ G_refit`** (+0.033319 ≥ +0.023863). I wrote this to test "the defence term is
     along for the ride". **It cannot test that**, because D098's statistic carries the refit in
     *both* arms, making the refit's contribution additive and orthogonal by construction. What the
     clause actually measures — "the top tercile has different baselines" — is **true and large**,
     and is reported as such. The question it was meant to ask is answered directly by the
     transplant (99% with everything frozen at pooled values).
   - **`Q95_rand ≥ 0.60·G_refit`** (+0.019806 ≥ +0.014318). The random-tier null is centred on the
     genuine pooled effect, not on zero, so comparing its 95th percentile to a *fraction of the
     observed* is not a test of anything. The calibrated statistic is its p-value (0.0180 / 0.0459),
     which is reported and which is the real residual uncertainty here.
   **A confirmation that swaps its criterion after seeing the numbers confirms nothing.** Both the
   mechanical verdict and the adjudication are in `FINDINGS.json`; a reader who rejects my
   adjudication has the mechanical answer in front of them.
2. **THE FLATTERING READING WAS AVAILABLE AND IS NOT THE HEADLINE.** F = 0.921 with swap p 0.0020
   would have supported a clean "THRESHOLD CONFIRMED, the lead is real and is the programme's
   largest". I did not report that, because 70% of the gain is a pooled main effect with no volume
   heterogeneity at all and the "largest" claim rests on an unverified subset-scored ceiling.
3. **THE UNFLATTERING READING WAS ALSO AVAILABLE AND IS ALSO NOT THE HEADLINE.** R_nodef = +0.033319
   at 140% of G_refit would have supported "REFIT ARTEFACT, the lead dies". I did not report that
   either, for the reason in item 1.
4. **ONE QUANTITY WAS NULLED AFTER SEEING A RESULT.** The swap null for the concentration increment
   (L3 over L1) was computed **after** c04's random-tier null came back marginal. The quantity is a
   preregistered ladder increment and the null is the preregistered headline null; only the decision
   to null *that* increment is post-hoc. It is labelled post-hoc in `c05_axis.py`, in
   `concentration_increment_null.csv` and in `FINDINGS.json`, and it is **not** a verdict input.
5. **THE NEGATIVE CONTROL IS CLEAN AND THE PLACEBO WAS VERIFIED TO PERTURB, BY MEASUREMENT.** Noise
   in place of defence: max dR2 +0.001536, 3–8% of the real gain, negative at rung L3. The
   within-date swap changes **80.7%** of the 1,632 team-game defence values, corr(original, swapped)
   = +0.192. The no-op placebo — the null code path run with the **unpermuted** column — returns the
   observed dR2 to **0.000e+00**. A vacuous control has bitten this programme twice; here it is
   excluded by measurement rather than by assertion.
6. **THE RANDOM-TIER NULL HAS A KNOWN DEFECT AND I DID NOT REPAIR IT.** The player-block variant's
   null has sd 0.0516 and a maximum of **0.6485**, driven by draws whose training folds are
   near-collinear. That fattens the tail and makes the concentration test *conservative*. Trimming
   it would have improved my p-value from 0.0459; I left it untrimmed and named the repair in §6.
7. **I DID NOT RECOMPUTE THE ARITHMETIC CEILING.** The "6.2× the programme's largest" claim is the
   single most quotable number in D098 and it is the one I checked least. I measured that the dR2 on
   that subset is inflated ~2.8× on a common denominator and inferred the ceiling is subject to the
   same concern. **That is an inference, not a measurement**, and it is flagged as such.
8. **I IMPORTED D098's CODE RATHER THAN REIMPLEMENTING IT.** That guarantees comparability and
   removes any possibility of a favourable reimplementation, but it also means a defect in D098's
   loader or design would be inherited silently. The reproduction to 0.000e+00 through *two*
   independent routes (D098's `s05.score` and this screen's ladder) is the check that my new code is
   faithful; it is **not** a check on D098's frames, which were taken as frozen.
9. **NO MARKET OR ODDS TEST EXISTS FOR THESE SEASONS.** Neither D098's lead nor this screen's
   reframing has been shown to beat a price.
10. **PLAYER POSITION IS NOT CARRIED BY EITHER FROZEN FRAME**, so "high-volume" still could not be
    separated from a positional story. Inherited limit, disclosed by D098, unchanged here.

---

## 6. WHAT WOULD RESOLVE THE REMAINDER

1. **Recompute the arithmetic ceiling and the headline dR2 on the full decision stratum's SST**, so
   they are comparable to D079 (0.001127), D084 (0.000129) and D089 (0.002057).
   `absolute_accounting.csv` already supplies the common-denominator dR2s: **+0.005968** (ppm),
   **+0.004909** (points).
2. **Re-run the random-tier null with degenerate draws screened out and more than 500 draws**, so
   the concentration claim gets a fair test rather than a fat-tailed one.
3. **Promote the pooled tier-step model (L3), not the tier-restricted refit.** It is 92–95% of the
   gain, it is **one deployable model rather than three**, it needs no tier-specific baselines, and
   it is the specification that would actually ship.
4. **An out-of-partition or market confirmation.** Neither exists inside 2021–2024 and this screen
   may not read 2025/2026.

---

## 7. AXIS RESOLUTION — "usage" is a proxy, and it is only half separable

Reproduced exactly (|Δ| = 0.000e+00 on all three axes): prior usage **+0.023863**, prior minutes
**+0.019177**, prior points-per-minute **+0.026204**.

| pair | Pearson | Spearman | top-tercile Jaccard | disagreement rows |
|---|---|---|---|---|
| usage vs minutes | +0.758 | +0.765 | 0.525 | 691 / 561 |
| **usage vs prior points-per-minute** | **+0.864** | **+0.864** | **0.696** | 359 / 391 |
| minutes vs prior points-per-minute | +0.493 | +0.514 | 0.413 | 759 / 921 |

- **Minutes is separably weaker.** On rows that are top-tercile on usage but **not** on minutes
  (n = 352) the gain is **+0.013579**; on rows top-tercile on minutes but **not** on usage (n = 169)
  it is **+0.003954** — a ratio of 0.29, just inside the preregistered 0.30 bar. The joint pooled
  model agrees: usage adds **+0.004014** given minutes, minutes adds **−0.000863** given usage.
  n = 169 is thin and the bar was cleared by 0.009, so this is a *direction*, not a settled fact.
- **Usage and prior points-per-minute are NOT separable.** Jaccard 0.696, and **both disagreement
  sets are too small to run the walk-forward at all** (359 and 391 frame rows, fold gating fails).
  In the joint model the two increments are tiny and opposite-signed (usage −0.001695 given ppm;
  ppm +0.002610 given usage), which at this power says nothing.

**Conclusion, and it is a legitimate answer rather than a failure: the axis is "this player scores a
lot", not "this player plays a lot". Prior usage and prior scoring rate cannot be told apart on
2021–2024 and this screen does not claim to.** D098's reading is confirmed and sharpened by one
notch.

---

## 8. TIME-WINDOW TABLE

| Quantity | Window it reads | Notes |
|---|---|---|
| `y_ppm` = pts/minutes, `y_pts` | the scored game itself | responses |
| `refB_ppm`, `refB_spm`, `refB_pps`, `refB_mpg`, `refB_own_usg_pg` | the player's strictly-prior same-season sums, league expanding-prior cold fallback | the COMPLETE reference, in **both** arms of **every** rung |
| `O01_own_usg_pg` | the player's strictly earlier games | D089 frozen frame |
| `A10_opp_defrtg` | the opponent's strictly earlier games | D085 frozen frame; verified on bytes by D098's `s06` against an independent shift-then-expanding rebuild to 1.42e-14 |
| `_m_hat` | `prior5_minutes` (strictly-prior trailing-5 mean) with a `refB_mpg` fallback | **no realised minutes anywhere in this screen** |
| tier labels | tercile cut points computed on the **2021 training fold only**, applied forward | a tier label could genuinely have been attached before tip-off |
| `n_prior ≥ 8`, `prior5_minutes ≥ 24` | strictly prior | D081's decision stratum |
| walk-forward coefficients | seasons **strictly before** the scored season | 2021 is a training fold and is never scored |
| within-date swap null | the whole walk-forward is redone inside every draw | the null is of the estimator, not of a fixed coefficient |
| random-tier null | the whole walk-forward is redone inside every draw | same |
| season / partition | n/a | 2021–2024 by value; every scored row is 2022–2024; **2025/2026 never read, joined, plotted or described** |

---

## 9. SCOPE COMPLIANCE

- Wrote **only** inside `experiments\exploration\E1_I0025_threshold_vs_refit\`.
- `E1_I0023_usage_defence_interaction` was **read only**. Its modules were imported to guarantee
  comparability; every script runs under `python -B` with `sys.dont_write_bytecode` set before the
  first import, and **no `__pycache__` was created there** (verified). No `main()` of any D098 module
  was called.
- `registry.jsonl`, `DECISION_LEDGER.jsonl`, `GRAPH_EVENTS.jsonl`, `idea_log.jsonl` — **never read
  and never written** by this screen.
- `_screen_kit` was **not** imported. D098's machinery was used instead, because a reimplementation
  would introduce exactly the class of discrepancy this comparison cannot tolerate.
- All frozen exploration frames read read-only.
- **The champion was never loaded, scored, retrained or modified.** Fitting comparison models is
  authorised by D091 ruling 1.

---

## 10. FILES

| File | What |
|---|---|
| `SPECS_PRESELECTED.md`, `_prereg.json` | preregistration with SHA-256 and the decision rule |
| `FINDINGS.json` | every headline number, the mechanical verdict, and the adjudication |
| `reproduction.csv`, `reproduction_anchors.csv` | the gate: D098 published vs reproduced, two routes |
| `pooled_tier_dummy.csv` | **the decisive test** — the full ladder, both strata, both evaluation sets |
| `ladder_increments.csv` | the increments *between* rungs, which is where the +0.024 / +0.0002 confusion lives |
| `ladder_swap_null.csv` | within-date opponent-swap null on every rung |
| `refit_decomposition.csv` | refit-without-defence and both transplants, all three tiers |
| `absolute_accounting.csv` | where the pooled coefficient's SSE reduction actually lands |
| `placebo_tiers.csv` | the identical machinery on the middle and bottom terciles |
| `random_tier_null.csv` | the null for "refitting any 1,687 rows", two variants |
| `negative_control.csv` | pure noise through the whole ladder |
| `axis_resolution.csv` | collinearity, per-axis gains, disagreement rows, joint model |
| `concentration_increment_null.csv` | swap null for L3-over-L1 (**post-hoc**, not a verdict input) |
| `permutation_draws_c02.csv`, `permutation_draws_c04.csv` | null draws |
| `run_log.txt`, `run_log_c00..c06.txt` | full logs |
| `cbase.py`, `c00`–`c06` | scripts |
