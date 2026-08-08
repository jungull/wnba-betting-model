# Can this programme detect the effects it has been hunting?

**Short answer: partly, and it has never known which part.**

It can see effects of about **0.002 and larger**. It can *just* see **0.001** if it stops
screening and tests one or two things at a time. It has **never once** been able to see anything
near **0.0001**, and no realistic amount of WNBA data would change that.

Of the **1,349 recorded cells whose design can still be checked** — every cell across seven
completed screens that published a null width — **56% were tested by a design that could not have
found the programme's own best result** even if that result had been sitting right there in the
data. Those nulls are not findings. They are silence. (The remaining screens publish no
machine-readable null width at all, so their power is not unknown-but-probably-fine; it is simply
unknown.)

---

## The number

Plant an effect of known size into the real data, using a real feature with its real structure
intact, and see how often the programme's own machinery finds it. Repeat 2,000 times per effect
size. The smallest effect found **80% of the time** is the detection floor.

**On the decision stratum (n = 5,673) under the programme's own correct-level null:**

| what you are doing | smallest effect found 80% of the time |
|---|---|
| testing **one** pre-registered thing | **0.00102** |
| testing **18** things at once | **0.00190** |
| testing **44** things at once | **0.00209** |
| testing **132+** things at once | **0.00235** |

Now put the programme's own numbers next to that:

| | |
|---|---|
| Best lead ever measured (D089, teammate volume, walk-forward points) | **0.0023** |
| Ceiling that killed the shot-mix lead (D079) | **0.001127** |
| Ceiling that killed the conversion lead (D084) | **0.000129** |

**The best result this programme has ever produced sits exactly on the floor of the design that
produced it.** Inside a screen of 132 cells — a perfectly ordinary size here; the ledger has
screens of 132, 154, 250, 318 and 348 — the floor is 0.00235 and the best-ever lead is 0.0023.
It would have been missed. It was found because it was tested on the pooled sample as well, where
the floor is lower.

**D079's killing ceiling of 0.001127 is at the very edge of what a single pre-registered test can
resolve, and well below what any screen can resolve.** **D084's ceiling of 0.000129 is roughly
eight times below the best floor measured anywhere in this study.** That kill was correct in
substance — a channel whose maximum possible contribution is below the detection floor can never
be confirmed here — but it was never a measurement, and it should not be cited as one.

---

## The screens whose nulls do not mean what they look like

For every recorded cell across seven completed screens (1,349 of them with a published null
width), we asked one question using **only the design** — sample size, grouping level, family
size — and never the result: *could this test have found an effect the size of 0.0023?*

| screen | decision | cells | could NOT have seen 0.0023 | median floor |
|---|---|---|---|---|
| **E0_I0019_availability_forecast** | D090 | 318 | **315 (99%)** | 0.0059 |
| **E1_I0023_usage_defence_interaction** | D098/D099 | 30 | **24 (80%)** | 0.0044 |
| **E0_I0014_residual_heterogeneity** | D078/D082 era | 348 | **203 (58%)** | 0.0028 |
| **E0_I0024_reb_ast_characterisation** | D097 | 250 | **103 (41%)** | 0.0021 |
| **E0_I0016_efficiency_predictors** | D085 | 132 | **53 (40%)** | 0.0018 |
| **E1_I0018_teammate_volume_channel** | D089 | 154 | **59 (38%)** | 0.0017 |
| **E0_I0017_shot_quality_efficiency** | D087 | 117 | **3 (2.6%)** | 0.0015 |

**628 of those cells were both blind and reported as nulls.** Those 628 recorded negatives carry
no information about whether the thing tested was real.

Named, by screen:

* **E0_I0019 (D090, availability forecast) — 232 uninformative nulls.** The worst in the
  programme. Its `skill_vs_R1` and `skill_vs_R2` families have floors of 0.015–0.029. Its
  conclusion that the availability forecast "adds nothing" rests on tests that could not have
  seen an effect **ten times** the best thing the programme has ever found.
* **E0_I0014 (residual heterogeneity) — 181 uninformative nulls** out of 348 cells.
* **E0_I0024 (D097, rebounds and assists) — 99 uninformative nulls.** D097 concluded rebounds and
  assists have "less room than points". Two fifths of the cells behind that could not have
  resolved 0.0023 in the first place.
* **E0_I0016 (D085, efficiency predictors) — 53 uninformative nulls.** D085's "0 of 330 rate
  cells" and D084's "generic pre-game state does not predict efficiency" inherit this.
* **E1_I0018 (D089, the best-lead screen itself) — 36 uninformative nulls.**
* **E1_I0023 (D098/D099, usage × defence) — 24 uninformative nulls** out of 30 tercile cells. The
  paired-forecast statistic on small strata has a floor of 0.0044; D099's careful adjudication of
  a "+0.005 on the decision stratum" effect was arguing about a number the design could barely
  resolve.
* **E0_I0017 (D087, shot quality) — 3 uninformative nulls.** Essentially clean.

**90% of all 1,349 cells could not have resolved D079's 0.001127. 98.7% could not have resolved
D084's 0.000129.**

---

## Where the power actually goes

Four levers were measured separately. They are not equally sized, and the two that were expected
to matter most are not the ones that do.

**1. Multiplicity — real, but it saturates almost immediately.**
Going from one pre-registered test to eighteen costs **1.9x** on the floor. Going from eighteen
to three hundred and eighteen costs only a further **1.24x**. *A screen of 318 and a screen of 18
have very nearly the same floor.* The expensive step is the first one — the decision to screen at
all rather than to test one thing. The ledger's habit of treating a 318-cell p-value and an
18-cell p-value as comparable is roughly right; the mistake is treating either as comparable to a
single pre-registered test.

**2. Sample size — the reliable lever, and it is slow.**
The floor falls as about **n^-0.65**. Going from the decision stratum (5,673) to the pooled
sample (14,852) — 2.6x the rows — buys **1.8x** on the floor. Halving the floor again would take
another 2.9x the rows.

**3. Cluster count — NOT the constraint, which is the surprise.**
The team-season null has 48 clusters, an absolute ceiling set by 12 teams × 4 seasons that no
number of extra rows inside these seasons can raise. That looked like the binding problem. It is
not. Swapping whole **player-seasons** instead — 600 clusters instead of 48, a one-line change,
already a kit function — gives a floor of **0.00056 against the team-season null's 0.00050**.
Twelve times the clusters, **no improvement at all**. Meanwhile the within-date opponent swap
(1,632 clusters) gives 0.00031 and the within-player cyclic shift (600 clusters) gives 0.00148 —
a 4.8x spread that cluster count does not order. **What sets the floor is how much of the
feature's structure the null has to leave standing, which is a property of the question being
asked, not of the sample.**

**4. Reference quality — the cheapest lever, and much bigger than expected in one specific place.**
D094 measured an 8.12-point swing from the reference alone and called it a bias problem. It is
also a power problem — but only where the null leaves structure standing. Completing the
reference is worth between **−9% and +16%** under the entity-swap and opponent-level nulls, which
is to say nothing at all. Under the **within-player cyclic shift**, the honest null for this
programme's modal `.shift(1).expanding()` feature, it moves the pooled floor from **0.0049 to
0.0015 — a factor of 3.3** (and 0.0034 to 0.0027 on the decision stratum, a factor of 1.26).
That is the single largest improvement available without acquiring any data at all, and it costs
four extra columns in the base. The lesson is narrower than "a better reference is a power
lever": it is a power lever exactly when the null is one that preserves the entity's level, and
it is worthless when the null destroys it.

---

## What would actually work

**Detectable today, with the data already on disk:**

* **0.002 or larger** — yes, on the pooled sample at any screen size up to 318 cells
  (floor 0.00112), and on the decision stratum if the screen is kept to **18 cells** (0.00190;
  at 44 cells it is 0.00209 and already marginal).
* **0.001** — yes, but only as a **pooled** test with **44 cells or fewer** (floor 0.00100), or
  as a single pre-registered test on the decision stratum (floor 0.00102). Not inside a
  132-cell screen anywhere.
* **0.0005** — only pooled, under the within-date opponent swap, testing **one** thing
  (floor 0.00031). At 18 cells that null is already at 0.00075.
* **0.0001** — **no.** The best floor measured anywhere in this study, under the most favourable
  null, on the largest sample, testing one thing, is **0.000285**. D084's 0.000129 is below it.

**The design that would detect 0.001–0.002 reliably:**

> Pooled sample (n ≈ 14,852). Complete reference — every prior measurement of the target
> quantity in the base, not one. **At most 18 pre-registered cells**, ideally fewer. Entity swap
> at team-season *or* the within-date opponent swap, whichever matches the feature's level. This
> design has a floor of **0.0009–0.0010** and needs no new data.

**And the honest sentence:**

> **Effects smaller than about 0.0003 are not detectable at the correct grouping level from
> 2021–2024 WNBA data, under any family size, with any reference, using any of this programme's
> nulls.** Reaching 0.000129 at a realistic screen size would take roughly **27 times** the
> current sample — on the order of a hundred WNBA seasons. It is not a question of being cleverer.
> There is no design.

That redirects the programme. Screening for small effects in this data is not a research
strategy, it is a way of generating silence and recording it as knowledge. The two things that
are worth doing instead are (a) **stop screening and start pre-registering one or two cells at a
time**, which is worth a factor of 1.9–2.3 immediately and free, and (b) **go after larger
targets or more data** — which is precisely the acquisition question D089 already raised about a
genuine pre-game injury feed.

---

## What could have been wrong here, and what was

The design was written down and hashed **before any statistic was computed**
(`PREREGISTRATION.md`, SHA-256 `9260f7db…42ea7c`). One thing was added afterwards and it is
counted: the player-season swap null, added because the first results made "is cluster count the
constraint?" answerable, and its answer went **against** the reason it was added.

The preregistration also committed to a check that could fail, and **it failed**. The plan was to
compute each null once and reuse it. Measured drift when an effect is planted ran from **−73%**
(the null narrows, under the within-player cyclic shift) to **+269%** (the null widens, under the
within-date opponent swap), and reached +506% on a single cell in the first, coarser probe. Far
past the 10% threshold. So every headline
number above was recomputed with the null measured on the planted response, as the
preregistration said to do. The uncorrected numbers are kept on disk beside the corrected ones
rather than deleted. Had they been reported instead, the within-player cyclic floor would have
been overstated 3x and the within-date opponent floor understated 2x.

Three machinery checks passed before any of this was believed: the fast statistic reproduces
`screenkit.delta_r2_plain` to 8e-17; the closed-form power calculation reproduces a literal
refit to 1e-16; and at a planted effect of exactly zero the rejection rate across all 24 design
cells lands between **0.040 and 0.069** against a nominal 0.05.

The power curves are measured on **one** frame — D089's, the programme's best-instrumented and
most favourable. The floors here are therefore, if anything, optimistic for the rest of the
programme. The retrospective across seven screens is the check on that, and it agrees.
