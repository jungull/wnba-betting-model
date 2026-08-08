# DEFECTS — E1_I0034_redistribution

Every defect found in **this screen's own work**, written as it was found, before the affected
result was used. Nothing here was deleted; the failed runs are on disk in `run_log_s03*.txt`.

Eight are recorded. Three of them change a headline.

---

## D-1 The first concentration statistic divided by a near-zero denominator and returned 2.98e9

**Where.** `s03_probe.py` §5. The statistic was "share of the freed minutes taken by the top-1
beneficiary" = `Δ_i / FREED_g`. In team-games where `FREED_g` was a fraction of a minute the ratio
exploded; the mean top-1 share printed as **2,978,273,065.94** against a uniform expectation of
0.12.

**Consequence if it had stood.** It would have supported a headline of "the redistribution is
overwhelmingly concentrated", which is the opposite of what this screen concludes.

**Repair.** Discarded before use; `s03b` recomputes concentration on an absolute basis and `s08` §4
replaces it entirely with **predictable** concentration — the within-team-game correlation between
the realised gain and each pre-game predictor — which is the quantity that actually bears on a
props market. Found before any cell was preregistered.

**Direction.** Toward a false positive. Caught.

---

## D-2 The champion's pre-game expected-minutes ranking is contaminated by phantom players, and my first two probe designs were built on it

**Where.** `s03c_probe3.py` §1. E1_I0033 ranked the pre-game roster by
`p_active_hat × min_hat` and took the top 3. Extending that to a top-8 rotation, **6.12% of the
rows have fewer than three prior same-season appearances**, and they carry the champion's
declared-constant `p_active_hat` of **0.816** against a prefix-mean `min_hat` of **21.63** — an
expected 17.6 minutes for a player who has never played. That ranks fifth to eighth on many teams.

**How bad.** At K=8, **only 293 of 676 "absence" team-games (43%) had an absentee with a usable
trailing-5 baseline at all.** In the majority of them the "absent starter" was a roster entry that
was never going to play, so nothing was freed and nothing could redistribute.

This is D111 ruling 3 — the availability forecast that sums to 10.34 players where 9.40 play —
seen from a different direction. It is a defect in the champion, but it became a defect in **this
screen** the moment I inherited the ranking.

**Repair.** The rotation is defined by the player's **own strictly-prior trailing-5 minutes**, not
by the champion's forecast. Phantom-free by construction, pre-game knowable, and every member has
a baseline. Probes 1 and 2 are kept on disk and their numbers are not used.

**Direction.** Toward a **false negative** — phantom absentees free no minutes, so the contaminated
definition dilutes the treatment and biases the whole screen toward null. Both discarded designs
would have made this screen look emptier than it is.

---

## D-3 The `FREED = 0` stratum is NOT a clean placebo, and P03_fga's entire pooled gain comes from it

**Where.** `s08_secondary.py` §2. M1's coefficients are fitted **jointly** — the intercept and the
`base5` and `z` slopes are re-estimated in the presence of the `u` and `u·z` terms. On rows where
`u = 0` the redistribution terms contribute exactly nothing, but the *rest* of M1 has still moved.
So `FREED = 0` rows do not reproduce M0 and the stratum is not a placebo.

**What it exposes.** For shot attempts:

| P03_fga stratum | n | ΔMAE | p |
|---|---:|---:|---:|
| ALL | 8,118 | **+0.00736** | 0.0235 |
| FREED > 0 (treatment ON) | 5,593 | +0.00356 | 0.4126 |
| FREED ≥ 25 min-equivalent | 2,475 | **−0.00387** | 0.6815 |
| FREED = 0 (treatment OFF) | 2,525 | **+0.01579** | 0.00055 |

**The pooled P03_fga "gain" is produced on the rows where the treatment is switched off, and
reverses sign on the rows where it is strongest.** It is a coefficient-refitting artefact, not
attempt redistribution. The same pattern holds for `P04_fga` and, more starkly, for both points
cells.

**Consequence if it had stood.** A headline of "absence knowledge improves the shot-attempt
forecast, p = 0.023" that is false.

**Repair.** P03_fga and P04_fga are reported as **NOT ESTABLISHED** and the stratification is
published beside every pooled number. The clean placebo is **P06**, which uses a **disjoint** row
set with its own pseudo-treatment and returns null (−0.00067, p = 0.8175, MDE80 0.00796).

**Direction.** Toward a false positive. Caught, and it kills one preregistered cell's apparent result.

---

## D-4 `FREED` overstates the volume actually available, so every "fraction recovered" is biased downward

**Where.** `s10_findings.py`, `baseline_sum_diagnostic.csv`. A player's trailing-5 is computed over
games she **played**, which are systematically her higher-minute games. Summed over a team's
established players these baselines exceed the 200-minute budget, **and by more when the team has
had absences** — the very games the treatment selects.

**Consequence.** The pooled OLS slope of established-player gain on `FREED` is **0.2822**, and
reading that as "only 28% of the absent player's minutes come back" would be wrong: part of the
shortfall is that `FREED` was never 200-minutes-worth of anything. This is why P01 was rewritten as
a **leakage** cell rather than a **closure** cell — see D-5.

**Direction.** Toward a false negative on any "is it absorbed?" statement. Disclosed, quantified,
and no headline rests on a recovery fraction.

---

## D-5 The preregistered team-level closure question is an identity, and I only noticed at probe 4

**Where.** `s03d_probe4.py` §1. For minutes, the remaining established players' total is
`200 − (minutes of players with no established baseline)`. Conditional on the remaining players'
own baselines it has **nothing to do with FREED at all**; a "closure β" can be made to come out at
1.0 or at 0.28 purely by choosing which term to condition on.

**Repair.** P01 was written as a **leakage** cell — does the freed volume leave the established
roster to call-ups? — which is not an identity. The change was made **before** PREREG.md was hashed
and is disclosed in PREREG.md §9.4.

**Direction.** Neutral, but it is recorded because a preregistered cell that is arithmetically
forced is worse than no cell.

---

## D-6 P02's null also destroys the base's mean-reversion main effect, and its null mean absorbs two-thirds of the observed statistic

**Where.** `s06_cells.py` P02, `null_absorption_tell.csv`. N1 permutes `base5` and `z` together
within the team-game — the coherent "reassign the pre-game player profile" null. But `base5` also
carries the mean-reversion main effect that sits in the base, so the permutation moves the base as
well as the candidate.

**The tell fires.** For `P02_TILT_minutes`:

| | value |
|---|---:|
| observed γ | −0.03487 |
| null mean | **−0.02320** |
| ratio \|null mean\| / \|observed\| | **0.666** |
| same sign as observed | **YES** |

This is the coordinator's absorption signature at two-thirds strength: the null has partly
reproduced the effect instead of destroying it. It is the **only** one of the fourteen cells that
fires the warning — no cell has a null mean *exceeding* its observed statistic — but it is the cell
whose verdict is "diffuse", so it matters.

**Consequence.** `P02_TILT_minutes`'s p = 0.6732 is **weaker evidence of a diffuse allocation than
it appears**, because a null that absorbs part of the effect inflates p. It is reported as
**NOT ESTABLISHED**, never as "the allocation is uniform".

**Direction.** Toward a false null on the cell it affects. Disclosed rather than repaired, because
every alternative construction I could specify either leaves an unpermuted collinear twin of the
candidate in the model (anticonservative) or removes the mean-reversion main effect from the base,
which D108's main-effects rule forbids.

---

## D-7 The analytic MDE80 is anti-conservative here by 1.2×–2.6×, and the headline cell sits below its injection-verified floor

**Where.** `s09_null_audit.py` §E2, `power_simulated_curve.csv`. Added after the hash, in response
to the coordinator's D113 note.

D113 says the programme's analytic `MDE80 = 2.80 × null_sd` may be anti-conservative by ~6.6×. On
this screen the **block-bootstrap sampling sd matches the analytic null sd almost exactly** (ratio
0.963–1.013 over six cells), so the *variance* estimate is sound. But the *power rule* is not:

| cell | observed ΔMAE | analytic MDE80 | empirical power AT the observed effect | injection-verified MDE80 | ratio | in null sds |
|---|---:|---:|---:|---:|---:|---:|
| P03_minutes | 0.02950 | 0.02529 | **0.783** | **0.03079** | **1.22×** | 3.41 |
| P03_fga | 0.00736 | 0.00919 | **0.300** | **0.01480** | **1.61×** | 4.51 |
| P03_pts | 0.00225 | 0.00886 | **0.033** | **0.03011** *(extrapolated — the simulated curve tops out at power 0.467)* | **3.40×** | 9.50 |

**Consequence, and it hits my own headline.** Under the analytic rule `P03_minutes` clears its
floor (0.0295 > 0.0253) and is DECIDED. Under the injection-verified floor it sits **just below**
it (0.0295 < 0.0308, empirical power 78.3%). The honest statement is that the pooled minutes cell
is **at its 80%-power boundary, not comfortably past it.**

**What survives, and what does not.** Rescaling every verdict to the injection-verified threshold
in null-sd units (3.41 for minutes, 4.51 for attempts, 9.50 for points):

| stratified cell (FREED ≥ 25, n = 2,475) | effect / null sd | injection-verified threshold | survives? |
|---|---:|---:|---|
| P03_minutes | **4.68** | 3.41 | **YES — decided** |
| P04_minutes | **3.44** | 3.41 | **marginally — just over** |
| P03_pts | −4.01 | 9.50 | **NO — falls to NOT ESTABLISHED** |
| P04_pts | −3.28 | 9.50 | **NO — falls to NOT ESTABLISHED** |
| P03_fga / P04_fga | −0.41 / −0.01 | 4.51 | no (and no under the analytic floor either) |

So the *positive* minutes result survives the correction and the *negative* points result does not.
The points floor is an extrapolation and should be treated as an upper bound on the floor, not a
measurement of it; the direction of the points effect is negative in all four treated cells, which
is the honest thing to carry.

**Direction.** Toward a false positive on the pooled headline. Caught, and the headline is
downgraded accordingly.

---

## D-8 P01's response is zero-floored and zero-inflated, so an OLS slope is a crude summary of it

**Where.** `s06_cells.py` P01. "Minutes played by players with no established baseline" cannot go
below zero and is exactly zero in a large share of team-games. A least-squares slope on it is not
wrong, but the fitted θ = −0.030 should **not** be read as "call-ups play *less* when a starter
sits". What the cell supports is the negative claim it was written for: **θ = 1 (full leakage) sits
59.6 null sds away and is decisively rejected**, while θ = 0 is 1.74 null sds away and
|θ| = 0.030 is below the cell's own MDE80 of 0.048, so **no leakage is established in either
direction**. Both statements are in FINDINGS.json; only the first carries weight.

---

## Two things that are conditioning, not defects, but are declared here so they are not missed

* **The absence indicator is realised.** Every forecast cell in this screen is an ORACLE CEILING.
  Both pre-game injury sources (`data/injury_capture/injury_log.csv`,
  `data/injury_history/injury_history.csv`) return `manifest_present: false` / UNVERIFIABLE from
  `screenkit.check_manifest`, and UNVERIFIABLE is not a pass. Nothing here is an achievable live
  increment.
* **The scored row set conditions on appearance.** ABSENT and REM partition ESTABLISHED, so a
  player is in the scored rows only if she played. M0 and M1 are scored on identical rows so the
  comparison is fair under D101, but the MAE **levels** here are not comparable to any screen that
  scores all candidate rows.
