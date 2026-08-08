# DEFECTS -- E1_I0038_within_entity_null_audit

Defects in this screen's own work, in the programme's recorded evidence, and in the methodology
this screen was directed to apply. Severity A = would change a verdict.

---

## D-01 (A) -- **D115's PROPOSED UNIVERSAL DIAGNOSTIC HAS A POSITIVE PREDICTIVE VALUE OF 0.146**

D115 ruling 1 and `E1_I0036` D-04 both propose `null_mean > observed` as the cheap universal
detector of the within-entity null failure, on the evidence that "it fired on 2 of 2 affected
cells here". Measured on **1,170 determinate killed cells** of this programme's own census:

| | EXPOSED | NOT_EXPOSED |
|---|---|---|
| flag trips | 69 | **403** |
| flag silent | 14 | 684 |

sensitivity 0.831 · specificity 0.629 · **PPV 0.146**.

The cause is structural, not a data accident: `null_mean > observed` fires both when the null
contains the effect (the failure mode) **and when there is simply no effect**, which describes
most of a negative record. It fires on `G01_noise` — D097's own designated noise placebo — where
the cyclic null is provably valid (this screen's R5).

**Consequence if uncorrected:** a programme that acts on this flag would re-open 632 cells, 403
of which are fine, and would treat the flag's silence as reassurance on 14 genuinely exposed
cells.

**Remedy (measured, not proposed):** publish the flag always, act on
`z = (observed − null_mean)/null_sd < −1.0`, which has specificity 0.980 on the same population
(`FLAG_REFINEMENT_Z.csv`). This requires the null **sd** beside the mean — which D103 ruling 2
already mandates and which only 234 of 1,999 census cells actually carry in a form joinable to
their p.

---

## D-02 (A) -- **THE FAILURE IS THE CONJUNCTION RULE, NOT THE CHOICE OF NULL, AND NOBODY HAS NAMED IT**

Every screen in the census that used a within-entity null **also ran the correctly matched
between-entity null in the same pass**. No screen pointed the wrong instrument at a candidate by
mistake. Three screens then combined them as

```
p_correct_level = max(p_within_entity, p_between_entity)      # "credited only if it beats BOTH"
```

`E0_I0016` (D085), `E1_I0018` (D089), `E0_I0024` (D097). `E0_I0016` compounds it at the headline:
`p_familywise_maxt = max(p_familywise_N1, p_familywise_N2)`.

**A blind null cannot be beaten.** For a between-entity candidate the conjunction is not a
higher bar, it is an unreachable one, and it converts "conservative" into "unfalsifiable".

This is the fourth instance of the pattern D108's own preserved disagreement named — *"a real
finding in one regime becomes a blanket rule without anyone asking where the regime ends"*. The
conjunction is sound whenever both arms are valid, and it is exactly the screens that were most
careful (they ran two nulls instead of one) that were bitten.

**Remedy:** a conjunction over nulls is legitimate only over nulls that have each passed
component-wise injection **for that candidate**. `max()` over a validated and an unvalidated arm
must be forbidden; the unvalidated arm must be dropped, as `E0_I0029` did explicitly and
`E0_I0019` did in its own repair.

---

## D-03 (A) -- **THE INJECTION PROTOCOL'S OWN CERTIFY/VOID DECISION IS UNSTABLE AT THE REPLICATE COUNTS IN USE**

Both `E1_I0036` (100 replicates) and this screen's preregistered runs (60, adopted for
comparability) decide at a hard threshold of power 0.80. The Monte-Carlo standard error of a
power estimate at 0.80 is 0.052 at nrep=60 and 0.040 at nrep=100, so **a null whose true power is
exactly 0.80 is misclassified roughly half the time.**

Observed live in this screen: `N_CYCLIC` on the D097 cell scored **0.933** in R1 and **0.800** on
the FULL arm of R3 — same null, same cell, same delta, different seed. R1 CERTIFIES; R3's FULL
arm does not. **Neither number is wrong; the threshold is being read at a resolution the
estimator does not have.**

This matters more than it looks: D108 made injection verification mandatory and four subsequent
screens were briefed on it. Any of them that ran 60-100 replicates has a certify/void decision
with a ±0.10 confidence interval on the quantity being thresholded.

**Remedy:** nrep >= 250 for any injection whose verdict can change a cell (se 0.025);
`scripts/d04_protocol.py` defaults to 250 and warns below 150. Report the power estimate's own
standard error beside it. This screen's confirmatory run at nrep=250 is
`D04_CONFIRM_NREP250.csv`.

---

## D-04 (B) -- **`E0_I0017` STORED ITS NULL DRAWS STANDARDISED, DESTROYING THE DIAGNOSTIC PERMANENTLY**

`E0_I0017/permutation_draws.npz` contains `standardised_draws` (mean 0 by construction) rather
than the raw statistic. For its **117 cells** the null mean is irrecoverable — not merely
unrecorded. Every other census screen's raw draws survive, which is why this audit could recover
a null mean for 916 cells the screens themselves never wrote one for.

Direction of harm is limited here: `E0_I0017`'s only null is an entity swap, so none of its cells
is structurally exposed and the missing diagnostic changes no verdict. **But the lesson
generalises:** a screen that standardises before writing has thrown away a check that had not
been invented yet.

**Remedy:** write raw draws, always. Standardise at read time.

---

## D-05 (B) -- 42.3% OF CENSUS CELLS NEVER HAD A NULL MEAN WRITTEN BESIDE THEIR p, AND D103 RULING 2 IS NOT BEING FOLLOWED RETROSPECTIVELY

Of 1,999 census cells, **846 (42.3%)** carry a null mean recorded by their own screen. This
screen recovered 916 more from raw `.npz` archives; 237 can never have one (120 because a
sign-flip null is symmetric about zero and the diagnostic does not apply — no loss; 117 because
of D-04 above).

D103 ruling 2 ("every screen must publish `null_mean` AND `null_sd` beside every p") was issued
after most of these screens ran and has not been applied retrospectively. The retrospective
application is cheap — the draws are on disk — and this screen has now done it for the census.

**Remedy:** a one-off pass writing `null_mean` / `null_sd` back into the eight census
`screen_results.csv` files from their own `.npz` archives. **NOT DONE HERE — that would be a
write outside this screen's scope.** Recorded as available work.

---

## D-06 (B) -- **THIS SCREEN'S 0 UNDETERMINABLE IS NOT THE SAME LINE `E1_I0036` HELD, AND THE DIFFERENCE MUST NOT BE MISREAD AS PROGRESS**

`E1_I0036` ruled **436 cells ineligible** because they carried `level_recorded = NOT_RECORDED`.
This screen reports **0 UNDETERMINABLE**. That is not because the record improved.

It is because the two screens need different things. `E1_I0036` needed a **level name** to build
a team-level frame; this screen needs a **between-entity variance share over the null's own
entity**, and 1,069 census cells carry one even where no level string was written. A recorded
variance share is a *measurement* of where a candidate varies; a level string is a *declaration*.
The measurement is the stronger record and more screens happen to have it.

Two further departures, both disclosed rather than buried:

* **`level_source = CODE`** was admitted for `E1_I0018` and `E1_I0023` (their entity is fixed
  unconditionally in their own source — `E1_I0018/s03_screen.py:170 ent = ENTITY_TEAM`;
  `E1_I0023/s02_interaction_forecast.py:68-71`). `E1_I0036` called `E1_I0018`'s level "implied
  but not recorded". **It is recorded — in the code.** Reasonable people can differ; every count
  in `AUDIT_TABLE.csv` carries `null_level_source` so a reader can discard the CODE rows (they
  contribute 2 of 83 exposed cells, so the headline does not depend on this).
* **`var_share_source = COMPUTED`** for 210 D097 cells, measured directly on D097's own frame,
  own regressor column and own row set. No fitting, no new data. These carry
  `exposure_confidence = 0.50` and contribute 16 of 83 exposed cells.

**If both concessions are refused, the headline becomes 65 exposed (all from `E0_I0016`, all
`TABLE`/`RECORDED`) and every conclusion in `VERDICT.md` still holds, because all 11
family-wise flips are in that 65.**

---

## D-07 (B) -- THE CENSUS COVERS 8 OF 38 SCREENS AND THIS AUDIT INHERITS THAT BOUNDARY

47 `FINDINGS.json` files exist across 38 screens under `experiments/exploration/`. The census
this audit extends covers **8**. Ten out-of-census screens mention a within-entity permutation
scheme, and four carry within-entity p columns in actual cell tables — `E1_I0021`
(heterogeneity diagnostic), `E1_I0022`, `E1_I0027` (reference ladder), `E1_I0030` (home
advantage), roughly 188 cell rows once permutation-draw dumps are excluded
(`OUT_OF_CENSUS_WITHIN_NULL_TABLES.csv`).

**Their exposure is UNKNOWN, not zero.** The 5.3% exposure rate reported in `VERDICT.md` is a
rate over the census, not over the programme. Direction of the error is unknown: `E1_I0021` is
specifically a heterogeneity screen and is therefore more likely than average to have pointed a
cyclic null at a between-entity quantity.

---

## D-08 (C) -- THE PREREGISTERED TRIAGE RULE YIELDED 4 CELLS, NOT 5, AND THE RULE WAS APPLIED AS FROZEN

PREREG 5.2 specified "top 5, at most 2 per screen". Only two screens contribute eligible cells
(`E0_I0024` and `E0_I0016`), so the cap binds at 4. The rule was **not** relaxed to reach 5.

A related awkwardness, disclosed: the frozen EV formula ranks purely on recorded effect size and
exposure confidence, and it therefore selected `E02_pl_paintpts_share → ts`, whose within-entity
null gave `p = 0.0033` — it was killed by family-wise multiplicity, not by the blind null. It
was re-measured anyway because the rule said so. Its result (0.99x the 132-cell floor) is
reported and is not a lead.

---

## D-09 (C) -- THE 0.50 EXPOSURE THRESHOLD IS A CONVENTION AND THE ANSWER MOVES WITH IT

143 exposed at 0.30, **83 at 0.50**, 35 at 0.80. The headline uses 0.50 because that is the
threshold `E0_I0014/s04_screen.py:229` already used (`use_between = vsb > 0.5`) to choose its
own nulls; adopting the programme's existing operational number was the only choice that could
not be accused of being tuned. Disclosed in PREREG section 0 before the rule was frozen.

---

## NOT A DEFECT, RECORDED SO IT IS NOT RE-LITIGATED

* **`E0_I0014`'s zero exposed cells are not an accident and not a coincidence.** Its code selects
  the null from the variance share (`use_between = vsb > 0.5`) and reports `correct_null_level`
  accordingly, so a within-block decision cell has `vsb <= 0.5` *by construction*. It is
  structurally immune. This is the kit's own documented rule, applied. It should be the
  programme's default.
* **`E0_I0029` (D108's own screen) has zero exposed cells** because it computed the cyclic null
  and then excluded it by name (`p_N_CYCLIC_EXCLUDED_no_power`, 284 cells). D108 fixed its own
  screen at the same time it raised the alarm. That deserves recording, since D115's framing
  ("550 cells nobody has looked at") implies otherwise and 560 of those 550-level cells are
  D108's.
* **`E0_I0019` (D090) is clean on its published rule and dirty on its superseded one.** Its
  repair (`s05_spreads_and_decomposition.py`, DEF-4) explicitly removed a `max()` over schemes —
  "two schemes, two questions, no max()" — which is exactly the fix D-02 above proposes, arrived
  at independently and months earlier. Under the superseded rule 117 of 318 cells would have
  been decided by the within arm and **70 would have been exposed**. D090 also self-flagged
  `within_null_degenerate` on 144 of 318 cells using `|null_mean|/null_sd > 5`. **The programme
  had both the fix and the diagnostic and did not generalise either.**
* **No process was killed.** Three python processes were launched by this screen and their PIDs
  recorded in `scripts/_s06_pid.txt`, `_s07_pid.txt`, `_s10_pid.txt`. All ran to completion. No
  blanket `Stop-Process` / `taskkill` was ever issued.
* **The shared screen kit was opened read-only and never modified.** Nothing outside
  `experiments/exploration/E1_I0038_within_entity_null_audit/` was written, staged or committed.
  `scripts/lab38.py` and `scripts/d04_protocol.py` are this screen's own copies precisely so the
  kit did not have to be touched.
