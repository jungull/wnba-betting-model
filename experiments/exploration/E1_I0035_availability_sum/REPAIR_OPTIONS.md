# Repair options — each with its TEAM-level and PLAYER-level effect

**E1_I0035_availability_sum.** Preregistered before any repair statistic was computed;
hash `7cd32656f3f7a96e869bf649f2ce1034a1c9cc3670f5dbc7605350fba6664205`.

> **NO REPAIR HAS BEEN ENACTED.** Nothing here writes to any arm, contract, registry or
> production path. Every one of these is a model change and therefore the user's decision.
> This document measures; it does not recommend enactment.

Every repair is fitted **walk-forward on strictly earlier seasons only** — the 2022 fold sees
2021 alone, and where a training stratum is empty the row is left unrepaired and that is
printed. Realised appearance rates are used freely to **judge** calibration and never to
**build** a repair scored on the same rows. One in-sample variant (`Xa-O`) is carried purely as
the ceiling and is labelled **ORACLE**; it carries no verdict.

---

## The table that decides it

Team level: RS1, n = 1,392 team-games, response `master_team.pts`, SST 168 710.4073, no
weighting, no base. Player level: RS1P n = 20,084 / RS1P-A n = 16,312 / RS1P-B n = 3,772,
responses `appeared` and `pts`. **These are different responses and no skill ratio is carried
across them.**

| | **Xa** recalibrate per tier | **Xb** normalise the sum | **Xc** prune the universe | **Xd** correct downstream |
|---|---|---|---|---|
| **Team MAE** (from 18.263) | 10.957 | **9.453** | 16.014 | **8.794** |
| Δ team MAE | +7.306 | +8.810 | +2.249 | **+9.469** |
| p / null sd | <0.0001 / 1.432 | <0.0001 / 1.640 | <0.0001 / 0.539 | <0.0001 / 1.763 |
| vs injection floor 2.00 | ✅ 3.7× | ✅ 4.4× | ✅ 1.1× | ✅ 4.7× |
| Team bias (from +8.139) | +1.127 | +0.072 | +2.606 | +0.054 |
| Corr. with response (from +0.001) | +0.056 | **+0.163** | +0.006 | **−0.021** |
| Fitted slope | — | — | — | **0.000 / −0.016 / −0.021** |
| **Player Brier, all** (from 0.1302) | **0.0947** | 0.1076 | 0.1322 | 0.1302 *(unchanged)* |
| **Player Brier, tier A** (from 0.0932) | 0.0933 | **0.1074** | **0.1058** | 0.0932 *(unchanged)* |
| Δ tier-A Brier | −0.000148 | **−0.014239** | **−0.012558** | 0 |
| vs injection floor 0.0025 | 0.06× → **NOT ESTABLISHED** | 5.7× → **ESTABLISHED HARM** | 5.0× → **ESTABLISHED HARM** | — |
| Player Brier, tier B (from 0.2905) | **0.1004** | 0.1084 | 0.2467 | 0.2905 |
| Player AUC (from 0.9026) | **0.9285** | 0.9153 | 0.9001 | 0.9026 |
| Player log-loss (from 0.4056) | **0.3141** | 0.3876 | **0.7754** | 0.4056 |
| Tier-A calibration slope (from 1.059) | **1.005** | **0.710** | **0.213** | 1.059 |
| Uncond. E[pts] MAE (from 3.907) | **3.455** | 3.583 | 3.594 | 3.907 |
| Conditional `pts_hat` MAE (4.2553) | identical | identical | 4.2972 on survivors | identical |
| **Appeared player-games left with NO forecast** | 0 | 0 | **684 (5.23 %)** | 0 |
| **Exposure misallocation** (from 8.91 min) | **4.01** | **8.91 — no change at all** | 5.52 | 8.91 |
| **PASSES BOTH LEVELS** | **YES** | NO | NO | NO |

*ORACLE ceiling, no verdict:* `Xa-O`, the same recalibration fitted in-sample, reaches team MAE
10.414, player Brier 0.0910 and misallocation 1.76 min. The walk-forward version captures most
of the achievable gain.

---

## (a) Xa — recalibrate `p_active` per tier so realised rates are matched

**Construction.** Four strata, enumerated not pattern-matched: (tier A / tier B) × (declared
constant / fitted). Within each, a logistic recalibration `σ(α + β·logit p)` fitted on **strictly
earlier seasons**. Where the training stratum is empty the row is left alone and it is reported —
in 2022 both *fitted* strata are empty, because 2021 emits nothing but declared constants, so
5,135 of the 2022 rows go through unrepaired. That is visible in `Xa_walkforward_fits.csv`, not
hidden, and it makes the walk-forward result **worse** than it would otherwise be.

**Team effect.** MAE 18.263 → **10.957**, an improvement of **+7.306** (p < 0.0001, null mean
+0.011, null sd 1.432, 36 team-season blocks; injection-derived 80 %-power floor 2.00 MAE, so the
effect sits 3.7× above it). Bias falls from +8.139 to +1.127. Σ`p_active` falls from 10.338 to
9.561 against a realised 9.402.

**Player effect — the part that matters.** Brier 0.1302 → **0.0947** and AUC 0.9026 → **0.9285**,
both ESTABLISHED. On tier B specifically, Brier 0.2905 → **0.1004**. On tier A — the 16,312 rows
where the product actually lives — the effect is **−0.000148**, which is **0.06× the 0.0025
injection floor**, so the correct verdict is **NOT ESTABLISHED**: no harm was detected, and none
could have been detected at that magnitude. That is a failure to reject, not a demonstration of
safety, and it must be quoted that way. The tier-A calibration slope moves from 1.059 to 1.005 —
towards perfect, not away. Unconditional E[pts] MAE 3.907 → **3.455**. Conditional `pts_hat` is
untouched by construction.

**Downstream.** Minutes misallocated to tier-B rows falls from **8.91 to 4.01** per team-game.

**Verdict — DR3 SATISFIED. The only candidate that improves the team sum without an established
cost to individual forecasts.** It also has the honest property that it *targets the actual
mechanism*: it repairs the constant and the population mismatch in the same operation, because
the strata separate them.

**What it does not do.** It does not fix the team sum as well as Xb or Xd. It leaves residual bias
of +1.13 points. And it does not stop the universe manufacturing pairings that do not exist — it
only stops the model asserting they will play.

---

## (b) Xb — normalise `p_active` to sum to a realistic roster size

**Construction.** `w = p_active × (R̂ / Σ p_active)`, where `R̂` is the team's **strictly prior
same-season** mean realised roster size, backing off to the earlier seasons' league mean on the
36 season-opener rows. The target is accurate: mean `R̂` 9.4104 against a realised 9.4016.

**Team effect.** MAE 18.263 → **9.453**, an improvement of **+8.810** — the best of the three
honest repairs. Bias +0.072. Correlation with the response rises from +0.001 to **+0.163**, the
highest of any arm here. On the team level alone this is the winner.

**Player effect — and this is why it is not the answer.** Tier-A Brier degrades by **−0.014239**,
which is **5.7× the injection floor**: **ESTABLISHED HARM**, p < 0.0001. The tier-A calibration
slope collapses from 1.059 to **0.710**. The mechanism is plain — the scale factor averages 0.894
and is applied *uniformly across the roster*, so it shrinks the ~13,600 tier-A probabilities that
were already well calibrated in order to absorb an error that lives in 3,772 tier-B rows. Overall
Brier still improves (0.1076 vs 0.1302) because the tier-B gain is larger, but **a repair that
buys a pooled improvement by damaging the rows the product is sold on is not a repair.**

**Downstream — the decisive detail.** The exposure producer allocates a fixed 200 team-minutes in
proportion to `p_active × e_min`. A per-team-game uniform rescaling **cancels exactly in that
normalisation.** Xb's measured misallocation is **8.912455 minutes — identical to the unrepaired
champion to the last digit.** Xb changes the team sum and changes nothing at all downstream.

**Verdict — FAILS DR2.** This is precisely the case the brief warned about: it fixes the team sum
and degrades the individual forecasts.

---

## (c) Xc — prune the universe to plausible-active players

**Construction.** Drop rows with `p_active < τ`, τ chosen on **strictly earlier seasons** by the
preregistered rule (equate the kept Σ`p_active` to the training pool's realised appearances). The
full τ curve is published in `Xc_tau_curve.csv` so the choice is auditable. Fitted τ: 0.00 (2022,
no usable pool), 0.68 (2023), 0.57 (2024).

**Team effect.** MAE 18.263 → **16.014**, +2.249 — the weakest of the four, and only 1.1× the
injection floor. Bias still +2.606.

**Player effect.** Tier-A Brier degrades by **−0.012558**, 5.0× the floor: **ESTABLISHED HARM**.
Log-loss explodes from 0.4056 to **0.7754** — pruning turns probabilities into a step function,
and the tier-A calibration slope collapses to **0.213**. Overall Brier is *worse* than doing
nothing (0.1322 vs 0.1302).

**And the cost the other options do not have: coverage.** 4,197 of 20,084 rows are deleted,
including **684 player-games in which the player actually played and scored** — **5.23 % of all
appeared player-games are left with no forecast at all.** A props market cannot price a player
who has been erased from the list, and those 684 are disproportionately the interesting cases:
returns, call-ups, sudden starts.

**Verdict — FAILS EVERYTHING.** Dominated on the team side, harmful on the player side, and
uniquely it destroys product coverage.

---

## (d) Xd — leave `p_active` alone and correct the level downstream

**Construction.** A walk-forward affine `a + b·B1` on the team total, fitted on strictly earlier
seasons.

**Team effect.** MAE 18.263 → **8.794**, +9.469 — the best number in the whole table, and
essentially the top-down team arm's 8.686.

**And it is worthless.** The fitted slopes are **0.000 / −0.016 / −0.021** and the arm's
correlation with the response is **−0.021**. A slope of zero means the recalibration has learned
to emit `a` — a constant — and ignore the player forecast entirely. This sharpens E1_I0033's
counterweight: they reported slopes of 0.07–0.15 for their normalised variant, but for the
*unnormalised* bottom-up sum the slope is not merely small, it is **negative**. Xd reaches parity
by ceasing to be a bottom-up forecast.

**Player effect: none, by construction.** `p_active`, `pts_hat`, the Brier score, the AUC, the
exposure allocation — all bit-identical to doing nothing. Xd is a team-total cosmetic.

**Verdict — FAILS DR2 by vacuity.** If the goal is a team total, E1_I0033 already showed the
top-down arm is better and a tuned team EWMA better still. If the goal is the player product,
Xd contributes exactly zero.

---

## What is NOT established

* **That Xa is safe for tier-A forecasts.** −0.000148 sits below the 0.0025 injection floor. No
  harm detected; none could have been. **NOT ESTABLISHED, not absent** (D103).
* **That any of these is the right repair.** Four points in a larger space were measured on a
  fixed row set.
* **The repair the population analysis actually points at — not manufacturing the tier-B
  obligation in the first place — was not measurable here.** It needs a roster source the
  contract explicitly declines to trust, and no manifest-verified artifact in this partition
  supplies one. This is the largest gap in the screen and it is the one worth closing next.
* **That the exposure-shape numbers transfer to the real producer.** They faithfully reproduce
  the proportional-allocation step but omit the 40-minute cap and the water-filling loop.
* **Anything about 2025 or 2026.** Never opened.

---

## If the user wants a recommendation

**Xa is the only option that survives the test the brief set.** It is also the only one that
targets the mechanism rather than its symptom, and the only one whose benefit survives the
downstream normalisation.

Two caveats belong with it, not after it:

1. Xa is a **recalibration**, and the arm's registration carries an explicit clause forbidding
   the retuning of declared constants after seeing outcomes. Enacting Xa is a re-registration,
   not an edit. **It is the user's call and it is not a small one.**
2. Xa treats the *probability*. The population analysis says the deeper fault is that 83.8 % of
   tier-B rows describe player-club pairings that never happen. Xa makes the model correctly
   uncertain about a question it should not be asked. **Repairing the universe would be better
   than repairing the answer**, and that option could not be measured from these artifacts.
