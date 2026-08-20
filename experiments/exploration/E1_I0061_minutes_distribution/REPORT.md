# E1_I0061 — minutes as a distribution

**Prereg** `e44c46a5f2b83da6f3834ddcb7b7816b8abe0419bad74c4d74c2478c0f99244a`, frozen after the
response's shape was printed and before any score existed. Exploration 2021–2024 only.
12,281 scored played rows over 450 player-seasons; 14,342 dressed rows including DNPs.

**Every arm uses the identical point forecast.** Only the distribution around it varies, so
every number below is attributable to the distribution and to nothing else.

---

## The answer in three lines

**The distribution work is real but small. The DNP branch is the whole story.** Modelling the
*shape* of the minutes distribution improves calibration threefold (PIT χ² 90.1 → 30.7) but
moves the primary score by **+0.83%**, against the 3% I predicted.

**Four of six predictions failed, including the one this screen was built on.**

**What actually pays is including the probability the player does not play at all: Brier on
"will they play more than 15 minutes" improves 11.5%, and improves at every threshold.** No
amount of distributional shape achieved anything close to that.

## Predictions, scored

| | prediction | result |
|---|---|---|
| **P1** | the constant-sd arm is miscalibrated, 80% coverage < 0.75 | **FAIL** — coverage 0.8056. See DEFECT 1; this is my labelling error, not a refutation of E1_I0056 |
| **P2** | shape gain ≥ 2× scale gain | **PASS**, but degenerately — see below |
| **P3** | shape improves CRPS over constant-sd by > 3% | **FAIL** — +0.83% |
| **P4** | constant-sd PIT shows excess mass in the OUTER bins | **FAIL** — outer mass 0.1905, slightly *under* 0.20. It is badly non-uniform (χ² 90.1) but in the interior, not the tails |
| **P5** | shape arm ≥ 5% narrower at matched coverage | **FAIL** — 1.7% |
| **P6** | the DNP mixture beats the played-only model at every threshold, > 10% at t=15 | **PASS** — +11.5% at t>15, positive at all five |

## The primary table

| arm | CRPS | vs. baseline | 80% coverage | width | PIT χ² |
|---|---|---|---|---|---|
| `A0` constant-sd Gaussian | 3.35921 | — | 0.8056 | 15.47 | 90.1 |
| `A1` per-row-sd Gaussian | 3.36945 | **−0.30%** | 0.7729 | 14.62 | 91.5 |
| `A2` pooled empirical quantiles | 3.35754 | +0.05% | 0.8183 | 15.33 | 59.7 |
| `A3` conditional empirical quantiles | **3.33129** | **+0.83%** | 0.8031 | 15.20 | **30.7** |

Conditional-bin fallback rate 0.0008 — the conditioning almost never ran out of training rows.

**On the thesis (P2).** It holds in direction and the ratio is meaningless: modelling the
*scale* per row made things **worse** (−0.30%), while modelling the *shape* helped (+0.83%).
A ratio against a negative denominator is not a quantity, so P2 is recorded as passing on
direction only. That scale-only modelling actively hurts is consistent with E1_I0056, which
found the per-row variance increment's confidence interval straddling zero.

**The calibration gain is the real distributional result.** PIT χ² falls from 90.1 to 30.7, a
threefold improvement, and that is worth having even though CRPS barely moves — CRPS is
dominated by the bulk, and the bulk was already roughly right.

## What actually matters: the branch where they do not play

Brier score for `P(minutes > t)`, on all dressed rows, DNPs included as zeros.

| arm | t>15 | t>20 | t>25 | t>30 | t>35 |
|---|---|---|---|---|---|
| `A0` constant-sd Gaussian | 0.1277 | 0.1183 | 0.1131 | 0.1056 | 0.0609 |
| `A3` conditional quantiles | 0.1279 | 0.1193 | 0.1135 | 0.1058 | 0.0597 |
| **`A4` = A3 × P(play), with a point mass at 0** | **0.1132** | **0.1101** | **0.1080** | **0.1031** | **0.0592** |
| **A4 vs A3** | **+11.5%** | **+7.7%** | **+4.8%** | **+2.5%** | **+0.8%** |

Read the first two rows against each other: **all of the distributional shape work is worth
essentially nothing for a threshold question** — A3 is a hair *worse* than A0 at three of five
thresholds. Then the DNP branch arrives and takes 11.5% off the low threshold.

The gradient is exactly what it should be. A player who does not dress cannot clear 15
minutes, and the low thresholds are where that branch does the most work; by t>35 the question
is about rotation size rather than availability and the branch stops mattering.

**And A4 used a deliberately crude availability estimate** — an EWMA of the player's own prior
appearance rate. The programme already has a far better one: E0_I0019 characterised the
shipped `p_active` at AUC 0.902 and Brier 0.092, against 0.841 / 0.122 for exactly the
prior-rate estimator used here. The 11.5% is therefore a **floor**, obtained with the worse of
the two availability models we hold.

## What this settles

- **Stop trying to fix minutes uncertainty by rescaling it.** Per-row scale modelling has now
  failed twice: E1_I0056's increment straddled zero, and here it is outright negative.
- **The shape work is worth doing for calibration, not for accuracy.** A threefold PIT
  improvement for free is worth keeping; it will not move a point forecast.
- **The unexploited thing in minutes is availability, not minutes.** It is the one branch
  nobody's minutes model contains, it is worth more than every distributional refinement
  combined, and the good version of it already exists and is not wired in.
- This is consistent with the ladder: minutes reach R² 0.668 against points' 0.523 — minutes
  are *already* the better-predicted quantity. The room was never in predicting them more
  precisely. It is in the branch where there are none.

## What this does NOT establish

- **No wager-shaped claim.** S42 stands. Threshold Brier is prop-shaped; that is not
  permission to price a prop.
- **Exploration only.** 2025–26 untouched.
- **A4 is not a validated availability model.** It is `A3 × a crude prior-rate`. That the crude
  version already wins by 11.5% is the finding; wiring in the good one is a separate screen and
  would need its own preregistration.
