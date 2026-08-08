# DEFECTS -- E1_I0033_aggregation_level

Written as each was found, before the affected results were used. Nothing here was deleted; the
failed runs are on disk.

---

## D-1  The first injection-power construction was UNINFORMATIVE (found in s06, repaired in s07)

**What I did.** `s06_topdown_vs_bottomup.py` verified null power by taking the P01 loss-difference
series, re-centring it so the mean gap equalled a planted `delta`, and asking whether N1 detected
`delta`.

**Why it is wrong, in two ways.**

1. It measured power *against P01's loss-difference variance* and then reported the answer as if
   it were the screen's power in general. P01 compares two forecasts that are enormously
   different (MAE 8.69 against 18.26), so its per-row loss difference has null sd 1.77. P02
   compares two similar forecasts and has null sd 0.0898 -- **twenty times smaller**. A single
   power curve computed on P01's variance says nothing about P02's floor, and the run log
   presented it as though it did.
2. At `delta = 0` it returned `p = 1.0000` and I nearly read that as a type-I pass. It is not a
   test at all: a two-sided permutation p at an observed statistic of *exactly* zero counts every
   draw as a hit by construction, so `p = 1.0000` is mechanically forced and carries no
   information about calibration.

**Consequence if it had stood.** The screen would have reported "N1 cannot detect a gap of 1.00
MAE point" as a property of the screen. That is false for five of the six primary cells. It would
also have reported a fabricated type-I pass.

**Repair (s07).** Two separate things, both per cell:
* a **per-cell minimum detectable effect**, planted as multiples of *that cell's own* null sd and
  recovered through the same code path; and
* a **genuine type-I check**: 400 synthetic no-effect datasets built by randomly sign-flipping
  whole blocks of the real loss difference, each pushed through the full null, and the resulting
  p-value distribution checked for uniformity and for a rejection rate near 0.05.

The defective s06 numbers are **kept on disk** in `injection_power.csv` and `run_log_s06.txt`,
renamed in FINDINGS as `injection_power_DEFECTIVE_SUPERSEDED`, and the corrected file is
`injection_power_per_cell.csv`.

**Direction of the error.** This one did not flatter the headline; it would have made the
screen look *less* able to see things than it is. It is recorded because a power claim that is
wrong in the conservative direction is still a wrong power claim, and D103 exists because nobody
checked.

---

## D-2  `B1_BOTTOMUP_AVAIL` as preregistered is a fair statement of the literal construction and
an unfair strawman for the *level* question (found in s06, addressed in s07/s08)

**What the numbers show.** The champion's obligation universe averages **14.43 rows per
team-game** on RS1 against a realised roster of **9.40**, and the availability forecast sums to
**10.34**. Multiplying a ~1-player roster-size excess by a ~8.7-point conditional scoring
forecast produces a **+8.14 point level bias**, which is essentially the whole of B1's MAE
disadvantage.

**Why this is not simply my error.** B1 is exactly what "sum the champion's player forecasts over
a team-game" means, using the champion's own availability forecast as the weight, over the
champion's own obligation set. It is the literal bottom-up arm and it is reported as the headline
bottom-up arm because that is what the question asked.

**Why it would nonetheless be a strawman if left alone.** The excess is concentrated in the
universe's **tier-B fallback rows**, which receive a *declared-constant* `p_active` of 0.8. A
reader could reasonably say the comparison is against a roster-construction artefact rather than
against the player level as such.

**Repair.** Three additional constructions, all labelled, and the two that make bottom-up look
*better* are additions after the hash and are counted as such:
* `B1A_TIER_A_ONLY` -- the same sum restricted to the tier-A obligation set (ADDED AFTER HASHING).
* `B1N_ROSTER_NORMALISED` -- weights rescaled so they sum to the team's own prior-games mean
  realised roster size, which is pre-game knowable (ADDED AFTER HASHING).
* The preregistered `B4_BOTTOMUP_CAL`, which removes the level bias by walk-forward affine
  recalibration and was in the hashed list from the start.

Both additions move the result **toward** bottom-up and **against** this screen's headline.

---

## D-3  `DR4`'s gap attribution shares are not a partition (found in s06, anticipated in the prereg)

The preregistered shares came out roster **79.5%**, level-bias **98.6%**, residual **-78.1%**.
They sum past 100% because the ORACLE roster arm repairs the level bias *as well as* the roster,
so the two shares overlap almost completely rather than partitioning the gap. The preregistration
said the shares would not be clipped and that a negative residual would be reported as measured,
so this is a disclosed limitation of the rule rather than a violation of it. s07 replaces it with
a **sequential** decomposition in which each step is applied on top of the previous one, so the
pieces do sum to the total by construction, and both versions are published.
