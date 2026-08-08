# E1_I0023 — USAGE × OPPONENT-DEFENCE INTERACTION — NOTES

Preregistration SHA-256: `b8777375c40e500d97e2e79a3516d663a7a7665127e5c11bb8030bd20cac69d4`
Cells added after preregistration: **0**. Dropped: **0**.

**VERDICT: SPLIT.** Kill the preregistered interaction term. Raise, as a new lead, the thing the
interaction test uncovered on its way to failing.

---

## 1. The three answers, in the order they were asked

**Does D093 reproduce?** Yes, exactly. Max |Δ Spearman| over all eight relationships
**6.939e-17**, max |Δ p| **1.110e-16**; family-wise p 0.003498 against a published 0.0035.
D093's `hd_base.py` imports the shared screen kit, which this screen was directed not to import,
so `group_slopes_fast` and `cyclic_shift_within_groups` were **reimplemented from D093's source**
(credited in `uid_base.py`). The exact reproduction is the evidence that the reimplementation is
faithful, which is why it was run first and in full.

**Does the interaction improve a forecast against a COMPLETE reference?** **No, not where it
matters.** The preregistered primary cell — points, D081's decision stratum, complete prior
reference, walk-forward coefficients — is **dR2 +0.001005 at correct-level p 0.4123**. The
co-primary on points-per-minute is +0.000203 at p 0.8461. Under the stronger within-date
opponent-swap null those become p 0.0679 and p 0.3174. It clears only POOLED (+0.001873 on points,
p 0.0275), and the family-wise p over the 18 hashed cells is 0.0435 — marginal, and its argmax is a
pooled cell, not the decision stratum. **The interaction is dead on the stratum anyone would bet
on.**

**Does the arithmetic ceiling close it?** **No — and that matters, because it means the interaction
died on its forecast rather than on its arithmetic.** On the decision stratum the ceiling is
**0.00124234**: 1.10× D079's shot-mix ceiling, 9.63× D084's conversion ceiling, 0.60× D089's
teammate-volume ceiling. One sd of the centred interaction moves a points forecast by 0.1118 points
against a 7.5787-point response sd — 1.475%. That is a real if modest lever, and the forecast
simply does not realise it.

---

## 2. What the interaction test uncovered, which is larger than the interaction

Step 5 asked whether the dead opponent-defence main effect (D085: twelve constructions, 0 of 36
cells, best dR2 0.00144) is explained by cancellation. It is not sign cancellation. The slope is
**positive in all three usage tiers and monotone increasing**:

| tier | mean prior usage/game | β on points-per-minute | cluster-robust t | walk-forward dR2 (ppm, DECISION) |
|---|---|---|---|---|
| T1 low | 8.69 | +2.494e-03 | +2.89 | −0.004077 |
| T2 mid | 13.53 | +3.697e-03 | +4.10 | +0.005179 |
| T3 high | 18.74 | +6.804e-03 | +6.08 | **+0.023863** |

Pooled across tiers the same contrast is dR2 **+0.001556 at p 0.1069** — which is essentially
D085's own best figure. **The mechanism is dilution, not sign cancellation:** one pooled slope is a
compromise that under-fits the top tercile and buys nothing in the other two.

Everything thrown at the top-tier result:

| test | result |
|---|---|
| within-date opponent-swap null (500 draws, whole walk-forward redone per draw) | p 0.0020 (the floor); z **+12.80** (ppm, DECISION), **+23.15** (ppm, POOLED) |
| family-wise over the 12 main-effect tier cells | **p 0.0020** |
| negative control (pure noise in place of defence, same tier machinery) | **clean**, min p 0.0758, max z +1.03 |
| league-mean-on-date placebo (all time/level, zero opponent information) | reproduces **−2%** of the effect |
| within-date-demeaned defence (pure cross-section) | reproduces **94%** of the effect |
| season stability | positive in **all 12** season cells, β +3.07e-03 → +6.39e-03 |
| leave-one-opponent-season-out over 48 clusters | **all 48 positive**, min +0.019757, median +0.023997 |
| leakage: independent shift(1) rebuild from `master_team` | matches the frozen column to **1.421e-14** |
| leakage: lead-lag profile | frozen INTO +0.0245 / OUT +0.6095 — the strictly-prior signature |
| leakage: **planted leaky twin (positive control)** | INTO **+0.4719** / OUT −0.1613, and it inflates dR2 1.6–2.8× — **the probe detects a deliberate leak** |

Ceiling for this one: **0.01280821** on the decision stratum — 6.23× D089's, which was the largest
the programme had measured. One sd of opponent defensive rating (4.645) moves a high-volume
player's points forecast by **0.739 points per game**, 9.9% of a response sd.

**The axis is not specifically usage.** Splitting on prior minutes (+0.019177) or prior
points-per-minute (+0.026204) works as well as prior usage (+0.023863). "Usage" is a proxy for
"this player scores a lot". D093's usage axis is therefore **confirmed as an axis and refuted as
the mechanism**, and this screen does not claim to separate the three.

---

## 3. TIME-WINDOW TABLE — features AND inference

### 3a. Response and row filters

| Quantity | Window it reads | Notes |
|---|---|---|
| `y_ppm` = pts/minutes, `y_spm` = TSA/minutes | the scored game itself | responses |
| `y_pts`, `TSA` | the scored game itself | responses |
| `n_prior >= 8` | strictly prior appearances | D081's decision stratum |
| `prior5_minutes >= 24` | the player's **strictly prior** trailing-5 mean minutes (`.shift(1).rolling(5)`) | D081's decision stratum. **No realised minutes anywhere in this screen** — unlike D093, this is a forecasting question and may not condition on the game's own outcome. The one exception is §3d. |
| season / partition filter | n/a | 2021–2024 by value; every **scored** row is 2022–2024; 2025/2026 never read |

### 3b. Features

| Feature | Window | Source | Verified |
|---|---|---|---|
| `refB_ppm`, `refB_spm`, `refB_pps`, `refB_mpg`, `refB_own_usg_pg` | ratio of the player's strictly-prior same-season sums, league expanding-prior cold fallback | D089 frozen frame | `refB_ppm` cross-checked against D085's independent copy: max abs diff **0.000e+00** |
| `O01_own_usg_pg` | the player's own games strictly earlier; the running roster state is advanced **after** every row of a game is written | D089 frozen frame, `PRIOR_ONLY_COLS` | inherited from D089/D093 |
| `A10_opp_defrtg`, `A01_opp_efg_allowed`, `A02_opp_ts_allowed` | opponent's games **strictly earlier**, merged on `(season, opp_team_id, game_id)` | D085 frozen frame | **verified on bytes here**, not inherited — see §3e |
| `_m_hat` (minutes estimate for points/attempts) | `prior5_minutes` with a `refB_mpg` fallback, both strictly prior | built here | D089's construction, reused |
| `P1_leaguemean_on_date` | mean defensive rating over the team-games played **that date** | built here | a placebo, never a headline feature |
| `G01_noise`, `G01_noise_tvframe` | none — pure noise | D085 / D089 frozen frames | two independent draws, one per frame |

### 3c. Inference — the machinery itself (D085 entered its trap here)

| Step | Fit window | Applied to | Why it is not retrospective |
|---|---|---|---|
| s02/s04/s05/s07 walk-forward | coefficients fitted on seasons **strictly before** the scored season | that season only | 2021 is a training fold and is never scored. D089's `walkforward_points.csv` construction. |
| in-sample fits | whole partition | the same rows | **LABELLED DIAGNOSTIC ONLY** and excluded from every headline, because an in-sample coefficient reads the whole partition |
| usage tercile cut points | computed on the **training** rows only | applied forward to the scored season | so a tier label could genuinely have been attached before tip-off |
| cluster sign-flip null | acts on already-computed paired squared-error differences | — | no aggregate is recomputed from a permuted key |
| within-date opponent swap null | **the whole walk-forward fit is redone inside every draw** | — | the null is of the estimator, not of a fixed coefficient |
| cluster-robust standard errors | in-sample, within tier | reported as a descriptive t only | never used for a verdict; the swap null is |

### 3d. The one place a realised outcome is read, and it is quarantined

`s01`'s reproduction of D093 applies D093's **realised-minutes floor of 20**, which conditions on
the game's own outcome. That is legitimate for D093's measurement question and is not a forecasting
increment. **It is confined to step 1 and appears in no forecasting figure in this screen.**

### 3e. The opponent column was verified rather than inherited

D093's notes state the opponent terms are strictly prior and cite D085's frozen frame. Because a
t of +6.7 where D085 found nothing is exactly what a contemporaneous leak looks like — and would
scale with usage, because a high-usage player contributes more of the points inside their own
regressor — the column was rebuilt from `data/masters/master_team.parquet` with an explicit
`.shift(1)` before the expanding sums. It matches to **1.421e-14**. A deliberately leaky twin was
built as a positive control and is cleanly separated on every probe. `s06_leakage_probe.py`.

---

## 4. Nulls, and which one is the verdict

| Null | What it preserves | Status |
|---|---|---|
| row-level sign flip | nothing | **contrast only, known anticonservative.** 8 of 18 real cells clear it against 2 at the correct level; median width inflation **1.611**. Tenth confirmation of the wrong-null trap. |
| whole-cluster sign flip at opponent-team-season | the within-cluster correlation of the paired differences | the headline null for the preregistered interaction family. Cluster codes are **global** and the sign draws are **shared across cells**, so the max-statistic family-wise correction is coupled rather than a stack of independent maxima. |
| **within-date opponent swap** | the date's marginal distribution of defence values **exactly**, and therefore the entire time/level component; destroys only **which opponent** was faced | **THE STRONGEST NULL AND THE ONE THE NEW LEAD IS JUDGED ON.** The whole walk-forward fit is redone inside every draw. |
| within-player cyclic shift | each regressor's marginal **and its serial correlation** | used only in step 1, where it is D093's honest null (constraint 2). |

---

## 5. DISCLOSURE — where this screen could have cheated, and where it did

**Every item below is a real fork where a more flattering number was available.**

1. **A NEGATIVE CONTROL FIRED IN STEP 2 AND IT IS REPORTED.** `NC1_noise_x_defrtg|ppm|POOLED`
   returns p 0.0055 and `NC1|attempts|DECISION` p 0.0075 — both with **negative** dR2. The cause is
   understood and is not manufactured signal: adding any extra column to a walk-forward regression
   carries an estimation-variance penalty, so the true no-signal expectation is slightly negative
   while the sign-flip null is centred at zero. That mis-centring is **conservative** for the
   positive findings, so no reported p was adjusted. But the preregistered decision rule said "both
   negative controls fail", and **I did not preregister whether the control test was one-sided or
   two-sided.** Under a two-sided reading a control fired; under a one-sided (improvement) reading
   no control improved anything anywhere. Both readings are stated and the ambiguity is mine.

2. **THE HEADLINE FINDING IS POST-HOC RELATIVE TO THE HASHED CELL LIST.** The 18 hashed cells are
   all *interaction* contrasts. The surviving result is a *main effect inside a tier*. The tier
   decomposition (step 4) and the main-effect-by-tier test (step 5) were both directed, and the
   step-5 prediction was written into `s04` before its numbers were computed — but the surviving
   cell does not inherit the 18-cell family-wise correction, so it was given **its own**, over its
   own 12 cells, under the stronger null (p 0.0020). It is labelled post-hoc in `FINDINGS.json`,
   in `s07`'s docstring and here. **A reader should discount it accordingly.**

3. **`s05`, `s06` and `s07` WERE WRITTEN AFTER SEEING `s04`'s RESULT.** They exist precisely because
   the result looked too good. Every one of them was designed as an attempt to **kill** the finding
   — placebos, a swap null, a leak probe with a planted positive control, a jackknife, alternative
   axes — and each one's hypothesis is stated in its docstring **before** its numbers. Writing
   probes after seeing a result is indistinguishable from tuning them to pass unless the intent and
   the direction are declared first; they were, and none was discarded or rerun in a different form.

4. **THE FLATTERING REFERENCE WAS AVAILABLE AND IS NOT THE HEADLINE.** Against the incomplete
   single-column reference, `A10_opp_defrtg|ppm|DECISION` is +0.001351; against the complete
   reference it is +0.000203, a **6.66× collapse**. Reporting the incomplete-reference number would
   have turned a dead cell into a live one. The complete reference is the headline everywhere and
   `reference_sensitivity.csv` publishes both. This is D090/D091's top-ranked failure mode, caught
   prospectively.

5. **THE IN-SAMPLE FIT IS UNIFORMLY MORE FLATTERING FOR THE INTERACTION AND IS NOT THE HEADLINE.**
   In-sample, the primary cell is +0.001349 rather than +0.001005, and the DECISION ppm cell rises
   from +0.000203 to +0.001620. Every in-sample figure is published and labelled a diagnostic.

6. **THE 1-SD CEILING AND THE D084-FORM CEILING DISAGREE, AND BOTH ARE PUBLISHED.** For the
   preregistered interaction on the decision stratum they are 0.00021761 and 0.00124234. The
   difference is that the 1-sd form uses the mean coefficient and mean minutes while the D084 form
   uses the realised variance of the forecast shift across folds and rows. **The larger of the two
   is quoted as the ceiling**, which makes this screen's own kill of the interaction harder rather
   than easier.

7. **THE CEILING STATISTIC HAS A NOISE FLOOR AND IT IS DISCLOSED.** The pure-noise interaction
   control returns a walk-forward ceiling of up to 3.98e-04 purely from estimation noise in its own
   coefficient. Ceilings below roughly 4e-04 here are not distinguishable from that floor. Two of
   this screen's own interaction ceilings sit under it.

8. **A TENSION IS LEFT STANDING RATHER THAN ARGUED AWAY.** A tier-restricted model gains dR2 +0.024
   from the defence column while a pooled model with a usage × defence interaction — which also
   lets the defence slope vary with usage — gains +0.0002 on the same stratum. The difference is
   that the tier-restricted model refits **every** coefficient inside the tier. **The intermediate
   specification (pooled model, tier-dummy × defence) was not tested**, and it is the obvious next
   test. Recorded as UNRESOLVED in `FINDINGS.json` rather than explained away.

9. **THE SCALE TEST DOES NOT FULLY SETTLE ITS OWN QUESTION.** Making the response relative to the
   player's own prior rate leaves the tier gradient intact (+0.0247 in the top tier), which argues
   against a pure multiplicative scale effect — but the relative response is mechanically noisier
   for low-volume players, which deflates the low tiers for a reason that has nothing to do with
   the hypothesis. The test is reported with that caveat rather than as a clean refutation.

10. **2021 IS USED, AND ONLY AS A TRAINING FOLD.** D093 excluded it entirely; D089 trained on it.
    This screen follows D089 so that all three of 2022–2024 can be scored. No figure is reported on
    a 2021 row. Step 1 excludes 2021 completely, which is why it reproduces D093 exactly.

11. **NOT DONE, AND DISCLOSED AS A LIMIT.** No market or odds test exists for these seasons, so
    neither the killed interaction nor the new lead has been shown to beat a price. Player position
    is not carried by either frozen frame, so "high-volume" could not be separated from a positional
    story.

---

## 6. Scope compliance

- Wrote only inside `experiments\exploration\E1_I0023_usage_defence_interaction\`.
- `_screen_kit` was **never read, imported or written**. Everything it would have supplied — the
  partition gate, the permutation machinery, the paired forecast comparison — is reimplemented in
  `uid_base.py`, and the D093 reproduction to 6.9e-17 is the check that the reimplementation is
  right.
- `E1_I0022_optimal_simple_estimator`, `IDEATION_QUEUE` and `E0_I0024_reb_ast_characterisation`
  were **never read or written**.
- `registry.jsonl`, `DECISION_LEDGER.jsonl`, `GRAPH_EVENTS.jsonl`, `idea_log.jsonl` — the decision
  ledger was **read only** (D079/D081/D084/D085/D089/D090/D091 for context and for the three
  ceiling benchmarks). Nothing was written to any of them.
- All frozen exploration frames and `data\masters\master_team.parquet` read read-only.
- **The champion was never loaded, scored, retrained or modified.** Fitting pooled and
  tier-restricted screening models in the exploration lane is authorised by D091 ruling 1.

---

## 7. Files

| File | What |
|---|---|
| `SPECS_PRESELECTED.md`, `_prereg.json` | preregistration with SHA-256, 18 real + 12 control cells |
| `FINDINGS.json` | every headline number, assembled from the artefacts on disk by `s08` |
| `reproduction_d093.csv` | step 1, D093 published vs reproduced, absolute deltas |
| `interaction_forecast.csv` | step 2, 30 cells × 2 bases × 2 fit windows |
| `reference_sensitivity.csv` | complete vs incomplete reference, per cell |
| `arithmetic_ceiling.csv` | step 3, both contrasts × both strata × both tiers × both fit windows |
| `usage_tier_gain.csv` | step 4, where the interaction's gain lives |
| `usage_tier_maineffect.csv` | step 5, the main effect inside each usage tier |
| `placebo_diagnostics.csv` | league-mean placebo, cross-section, within-date swap null |
| `leakage_probes.csv`, `leadlag_profile.csv` | frozen vs clean rebuild vs planted leaky twin |
| `stress_family_wise.csv` | 12 tier cells + 12 negative-control cells under the swap null |
| `stress_season_stability.csv`, `stress_alternative_axes.csv`, `stress_scale_test.csv` | T3–T6 |
| `permutation_draws_s01.csv`, `permutation_draws_s02.csv`, `permutation_draws_s07.csv` | null draws |
| `run_log.txt`, `run_log_s00..s07.txt` | full logs |
| `uid_base.py`, `s00`–`s08` | scripts |
