# VERDICT — E1_I0043_opponent_defence

`PREREG.md` sha256 `629fe4aa2d757d393ec7db5861feba28e431f25cb89562ac1e61e05cf9b73add`,
hashed before any statistic this screen produced existed. 0 cells added, 0 dropped.
Partition 2021–2024 exploration only; **2025/26 was never read.** 16 anchors reproduced first,
four of them at exactly 0.000e+00.

---

## HEADLINE (first three sentences, as required)

**The four sightings are ONE sighting: all four read the same 14,852 values of `A10_opp_defrtg` out
of the same file (`E0_I0016/screen_frame.parquet`, max\|diff\| 0.000e+00), against the same response
`y_ppm`, on four strictly nested row sets — so the corroboration pattern is the shared-upstream
signature, not four independent arrivals, and no credit may be taken from the count of four.**
On the decision stratum (`n_prior ≥ 8` AND `prior5_minutes ≥ 24`) — **5,673 rows, 38.2% of the
frame, 149 players, 48 opponent-team-seasons; 3,167 of them in the one clean 2023–2024 walk-forward
eval window, 24 blocks** — the opponent-defence increment over an honest base is **signed
ΔR² = +0.00939778 with the walk-forward intercept UNFROZEN and +0.00890794 with it FROZEN (94.8%
retained), and the intercept-only arm returns exactly +0.00000000**, so this is not the E1_I0042
shared-intercept failure. **The channel is therefore alive as a measurement and dead as a
corroboration story: it is D099's already-recorded finding reproduced on a cleaner window, it sits
at only 1.50× this screen's own injection-verified detection floor of 0.006256, half of it is
already reachable from two columns the programme already holds, and on 2023 alone — one of the two
seasons in the only clean window — it falls below that floor.**

---

## THE DECISION-STRATUM INTERSECTION, BEFORE ANY EFFECT SIZE

Reported first, as the standing requirement adopted after a screen headlined +3.51% on zero
bettable rows.

| population | rows | % of frame | players | opp-team-seasons | games |
|---|---|---|---|---|---|
| whole frame (sighting 4's row set) | 14,852 | 100.0% | 247 | 48 | 827 |
| **DECISION stratum** | **5,673** | **38.2%** | 149 | 48 | 708 |
| DECISION ∩ complete-case | 5,673 | 38.2% | 149 | 48 | 708 |
| **DECISION ∩ clean eval window 2023–24** | **3,167** | **21.3%** | 113 | **24** | 390 |
| DECISION ∩ 2022 (disclosed contrast only) | 1,350 | 9.1% | 83 | 12 | 170 |

* Complete-casing drops **0 rows**; every base column's coverage is asserted at exactly 1.000000
  (D087 guard, `REFERENCE_COVERAGE.csv`).
* **61.8% of the rows behind sighting 4 (D117/D085) are rows nobody would bet on.** Sightings 1–3
  are already inside the decision stratum.
* Block count on the headline cell: **24 opponent-team-seasons in the eval window, 48 in the
  permuted frame.** A two-sided sign-flip at 24 blocks has `p_min = 2^(1−24) = 1.19e-07`; this
  screen uses permutation nulls, `p_min = 1/2001 = 4.998e-04`, and quotes no block `t` — `sqrt(24)`
  = 4.899 would be the ceiling if it did.

---

## THE EFFECT, FROZEN AND UNFROZEN

Decision stratum, walk-forward eval 2023–2024, `A10_opp_defrtg`, signed ΔR², 2,000 draws.

| response | base | UNFROZEN | **FROZEN** | frozen / unfrozen | INTERCEPT_ONLY |
|---|---|---|---|---|---|
| `y_ppm` | `B0_COMPLETE` | +0.01033791 | +0.01016239 | **0.983** | +0.00000000 |
| **`y_ppm`** | **`B1_HONEST` (PRIMARY)** | **+0.00939778** | **+0.00890794** | **0.948** | **+0.00000000** |
| `y_ppm` | `B2_FAMILY` | +0.00442427 | +0.00270346 | 0.611 | +0.00000000 |
| `y_pts` | `B0_COMPLETE` | +0.00532344 | +0.00526012 | 0.988 | +0.00000000 |
| `y_pts` | `B1_HONEST` | +0.00452075 | +0.00461568 | **1.021** | −0.00000000 |
| `y_pts` | `B2_FAMILY` | +0.00238383 | +0.00166445 | 0.698 | +0.00000000 |

**The effect does not vanish when the intercept is frozen.** Holding the intercept and every base
coefficient at their base-model values and letting only the defence coefficient move keeps 94.8% of
the primary cell and 102.1% of the points cell. The intercept's own contribution, measured directly
rather than inferred, is **exactly zero on all twelve cells**. E1_I0042's failure mode is absent
here, and it was looked for with the instrument that would have found it.

Negative control `G01_noise` through the identical path: **+0.00019978, p = 0.111444 (`N_ESWAP`),
p = 0.082959 (`N_DATE`)** — not significant, and 0.2× the single-cell floor.

## NULLS AND THE FAMILY BAR

| cell | `N_ESWAP` p | `N_DATE` p | p family-wise (K=12, coupled max) |
|---|---|---|---|
| `y_ppm` `B1_HONEST` UNFROZEN | **0.000500** | 0.000500 | **0.000500** |
| `y_ppm` `B1_HONEST` FROZEN | 0.000500 | 0.000500 | 0.000500 |
| `y_ppm` `B2_FAMILY` FROZEN | 0.001000 | 0.000500 | 0.008996 |
| `y_pts` `B2_FAMILY` FROZEN | — | — | 0.039980 |

**12 of 12 preregistered cells clear the family-wise bar at 0.05**, using draws shared across cells
so the maximum is coupled rather than a stack of independent maxima.

---

## THE NULL IS VALID, AND THE BLIND ONE IS DEMONSTRATED BESIDE IT

`INJECTION_POWER.csv`, `INJECTION_MDE.csv`, `BLIND_NULL_DEMO.csv`. nrep = 250, ndraw = 250 (se on a
power estimate 0.025 — 60 replicates cannot carry an 0.80 threshold, E1_I0038 D-03).

| null | type-I @0.05 | **null-centre ratio** | power on the BETWEEN component at δ=0.008 | verdict |
|---|---|---|---|---|
| **`N_ESWAP`** (relabel opponent-team-seasons) | **0.048** | **+1.030** | **0.868** | **USABLE** |
| `N_BLIND` (shuffle within opponent-team-season) | 0.008 | **−0.040** | 0.144 | **VOID** |

E1_I0038's one-line drop-in check separates them cleanly on a fresh cell: the valid null's injection
centre matches its verdict centre to 3%, the blind null's is 25× off **and of the opposite sign**.
And the blind null's own centre on the real data is **+8.322e-03 against an observed +9.398e-03** —
the null distribution sits at 88.5% of the statistic it is judging.

Measured directly on this screen's own cell, 1,000 draws each, identical rows:

| scheme | permutes within | corr(drawn, real) | z | **p** |
|---|---|---|---|---|
| `N_ESWAP` | — (between opponents) | **−0.0231** | +9.016 | **0.000999** |
| `N_BLIND` | opponent-team-season | **+0.8221** | +0.908 | **0.186813** |
| `N_WITHIN_PLAYER` cyclic | player-season | +0.0301 | +18.820 | **0.000999** |

**The same effect that the matched null calls p = 0.000999, the blind null calls p = 0.187.** That
is the D115/D117 failure, demonstrated first-hand on a live cell rather than cited.

**And it corrects the framing this screen was given.** A *within-player* null is not blind to
opponent defence — it rejects at the draw floor. The blind null is the *within-opponent* one, which
changes 97.0% of the values and still preserves 82.2% of the correlation because it preserves each
opponent-team-season's mean, and 77.1% of this candidate's variance is that mean. Blindness is a
property of the match between the permuting entity and the entity the candidate is constant in —
not of "within" versus "between" in the abstract (`DEFECTS.md` D-05).

### The floor this screen actually has

**MDE80 on the BETWEEN component under `N_ESWAP`, injection-verified: 0.006256** (≈0.00525 on the
realised rather than the target scale). That is **6.1× D103's single-cell floor of 0.00102 and 2.7×
its 132-cell floor of 0.00235** — because D103 measured a pooled 14,852-row design and this is a
3,167-row walk-forward with 24 eval blocks. **Every floor quoted in this screen is
injection-verified; no analytic MDE80 appears anywhere.**

The observed primary effect is **1.50× its own measured floor.** That is a margin, not a comfortable
one.

---

## WHAT THE CHANNEL IS, EXACTLY

| probe | signed ΔR² | share of observed |
|---|---|---|
| no-op (identical column) | +0.00939778 | 1.000, \|diff\| **0.000e+00** |
| league mean on date | −0.00024048 | **−2.6%** |
| within-date demeaned | +0.01013469 | +107.8% |
| **opponent-season MEAN only** | **+0.01103633** | **+117.4%** |
| within-opponent-season deviation only | −0.00025220 | **−2.7%** |
| **opponent's PREVIOUS-season mean** | **+0.00094229** | **+10.0%** |

**It is entirely the opponent's current-season defensive level.** Not a calendar effect
(−2.6%), not form (−2.7%), and not durable team quality (the previous-season construction returns
+0.00094, *below* D103's single-cell floor). Whatever this is, it is in-season accumulation of one
season-level number.

The gain lives on the rows the candidate moves: **75.1% of it on the extreme-deviation tercile,
1.6% on the tercile nearest an average defence.** Not a vacuous control.

Not a leak: the future-reading full-season column beats the strictly-prior one by 1.174× (`y_ppm`)
and 1.264× (`y_pts`). Equality would have been the leak signature.

---

## IS IT ALREADY IN THE MODEL?

Partly, and the arithmetic said so before the fit did. Adding `A01_opp_efg_allowed` and
`A02_opp_ts_allowed` — two columns the programme already holds, correlated with the candidate at
+0.815 and +0.829 — **halves the ORACLE ceiling from 0.01094 to 0.00582 and cuts the realised effect
from +0.00940 to +0.00442 (47% retained), and from +0.00891 to +0.00270 frozen (30% retained).**
D085's twelve "separate constructions" have an effective dimension of **8 at 95% of variance**;
this is one channel with several names.

---

## THE PREREGISTERED DECISION RULE, MECHANICALLY APPLIED

| clause | required | measured | |
|---|---|---|---|
| 1 | ≥500 decision-stratum eval rows | 3,167 | PASS |
| 2 | ceiling > 0.00102 | 0.00344 (D084 form) / 0.01094 (oracle) | PASS |
| 3 | primary ΔR² > injection-verified floor | 0.00940 > 0.006256 (1.50×) | PASS |
| 4 | frozen retains ≥ half of unfrozen | 0.948 | PASS |
| 5 | `N_ESWAP` p < 0.05, blocks ≥ 6 | p 0.000500, 24/48 blocks | PASS |
| 6 | increment over `B2_FAMILY` non-zero | +0.00442, p_cell 0.000500 | PASS |

**Six of six. By its own rule this screen cannot kill the channel, and it does not.**

It is an **E0 LEAD and nothing more**: one stratum, one window, one column, in-partition only, no
confirmation-holdout evidence, no champion fitted, no production change enacted, nothing proposed
for promotion. **And it is not a new lead** — D099 already ruled "there is a real opponent-defence
effect worth about ΔR² +0.005 stratum-wide", and +0.00940 on `y_ppm` / +0.00452 on `y_pts` over a
harder base on a cleaner window is that finding, not a fifth one.

---

## THE RESULTS THAT MOST WEAKEN THIS PAGE

Three, and the first is the one that matters.

**1. On 2023 alone, the effect is below this screen's own detection floor.** One eval season at a
time, `y_ppm`, `B1_HONEST`, trained strictly on earlier seasons:

| eval season | ΔR² unfrozen | vs MDE80 0.006256 | between-team sd of the candidate | corr(defence, ppm) | noise control |
|---|---|---|---|---|---|
| 2022 *(not the clean window)* | +0.00444926 | 0.71× | 4.39 | +0.0685 | −0.00058 |
| **2023** | **+0.00405016** | **0.65×** | **3.49** | **+0.0426** | −0.00031 |
| **2024** | **+0.01548220** | **2.47×** | **5.37** | **+0.1467** | +0.00078 |

**2024 carries the headline.** It has 54% more between-team dispersion in defensive rating than 2023
and a 3.4× larger raw correlation with the response. The two-season pooled figure of +0.00940 is not
a stable per-season effect; it is one strong season averaged with one that does not clear the floor.
On `y_pts` the 2023 cell is +0.00139660 — **1.37× D103's single-cell floor and below its 132-cell
floor**, on the first genuinely clean season the programme has.

**2. The one construction that is even partly independent of the in-season column returns nothing.**
The opponent's previous-season mean defensive rating — strictly prior, a different row-to-value
mapping, available on 79.0% of rows — gives **+0.00094229** on `y_ppm`, below the single-cell floor.
If this channel were durable team defensive quality it should survive that construction. It does
not. Everything here rests on one in-season estimator whose four "sightings" are one measurement.

**3. This screen made the D101 error on itself.** `s02` computed the ceiling on a
rate-times-minutes points forecast and applied it to cells that fit points directly; the `y_pts`
cell then returned +0.00452 against a "ceiling" of 0.00344. Caught, corrected in `s04`, uncorrected
table kept on disk, and generalised in `DEFECTS.md` D-02 — where it turns out that `(d·d)/SST`, the
statistic D084 and D089 both call "the ceiling", **is not an upper bound on ΔR²** at all. Neither
kill is thereby wrong; the word is.

---

## WHAT WOULD CHANGE THIS VERDICT

* **A genuinely independent sighting, which does not exist.** It needs a *different estimator* of
  opponent defensive strength (points allowed per game, a RAPM-derived defensive rating, an
  opponent-adjusted rating), on a *different row set*, against a *different response*. D098's
  leakage rebuild matched the frozen column to 1.42e-14, which proves fidelity and is not
  independence. Until someone builds one, the count of independent arrivals at this channel is
  **one**.
* **A third clean season.** The whole result turns on 2024 versus 2023 and there is no way to break
  that tie inside 2021–2024. The tie-breaker is in the sealed 2025/26 holdout and this screen did not
  open it and must not.
* **A power re-run at a larger family.** MDE80 0.006256 is measured for K=1. This screen's family is
  12 and the coupled-max bar was computed, but the *floor* under K=12 was not re-injected; it will be
  higher than 0.006256, which would push the 1.50× margin down further.
* **D085's kill is untouched and reproduces exactly.** Its pooled ΔR² of 0.001443 on 14,852 rows
  reproduces here at |diff| 9.324e-18, and its own matched entity-swap arm already recorded
  p = 0.001664 / family-wise 0.009983. **D085 measured a diluted pooled average correctly and its
  blind `max(p_within, p_between)` conjunction is what buried it** — exactly as D117 concluded. This
  screen adds no new challenge to D085 and removes none.
