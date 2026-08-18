# NOTES — E1_I0058_market_benchmark

**Decision D141** (the frozen PREREG prints "D138" — that id was already taken; see `DEFECTS.md`
D4). Evidence level **E1**, and E1 is the ceiling by construction: this is a single-partition
screen and the confirmation partition may not be touched.

**Executed by Coordinator #07 on 2026-08-18**, resuming at `s02` under the hash frozen 2026-08-17
by an agent that died before it could run the scoring step.

---

## The question, and the answer

**Does this program's player-points forecast add anything to a real market price?**

**No. On this population the market encompasses the model, and the model is not close.**

This is the first time the program has scored its own player-points forecasts against an actual
book price rather than against a baseline of its own choosing.

---

## READ THIS BEFORE ANY NUMBER BELOW — the population is conditional

n = **1,972** player-game obligations, **78** players, **262** games, 2024-05-14 to 2024-10-20.

These are **40.2% of season-2024 played player-game rows.** A player-game enters only if a book
posted a `player_points` line on it. **Books price the players they choose to price** — high-minute,
high-usage, nationally visible players. Every figure in this document is conditional on that
selection.

Nothing here may be generalised to unpriced players, and no statement of the form "the model is
behind the market on player points" may be made without that clause attached.

---

## 1. Standalone accuracy — the market wins on reference-free metrics

Headline metrics are **MAE and RMSE**, chosen in advance precisely because they need no baseline
and so cannot move on a reference choice (D087/D136).

| arm | what it is | MAE | RMSE | bias (f−y) | corr |
|---|---|---|---|---|---|
| M1 | raw consensus line (median over books) | 4.9232 | 6.2030 | +0.1691 | 0.5450 |
| **M2** | **de-vigged central estimate — PRIMARY MARKET** | **4.9043** | **6.1873** | +0.0944 | 0.5476 |
| M3 | de-vigged, additive margin (sensitivity) | 4.9038 | 6.1870 | +0.0890 | 0.5476 |
| **F1** | **model E[pts\|active], `cbs_v15_player_oof_v5` — PRIMARY MODEL** | **5.3232** | **6.7573** | −0.2153 | 0.4474 |
| F2 | model E[pts\|active], `cbs_v14_player_oof` (robustness, n=1927) | 5.3635 | 6.8174 | −0.2744 | 0.4405 |

**The market is 0.4189 MAE points better than the model** — more than four times the preregistered
0.10 materiality floor. **P1 PASSES.**

### R², against a named ladder — because the reference is where this program has been wrong before

The same result has moved 6.5×, 4.6× and 8.12 points on reference choice alone in earlier work, so
the reference name travels with every number:

| arm | R0_grand_mean *(declared honest)* | R1_player_season_mean *(**RETROSPECTIVE**)* | R2_market_raw |
|---|---|---|---|
| M1 | 0.2951 | −0.0558 | 0.0000 |
| M2 | 0.2987 | −0.0505 | 0.0051 |
| F1 | **0.1635** | −0.2530 | **−0.1867** |
| F2 | 0.1544 | −0.2671 | −0.2032 |

`R0_grand_mean` is the honest denominator: it is the only reference defined on exactly the
population being scored and it is not itself a forecast anyone could have made better.
**`R1_player_season_mean` is RETROSPECTIVE** — it uses each player's own *realised* 2024 season mean
and is not a forecast; it is a yardstick only, and it is labelled as such at every occurrence.

**F1's R² moves from −0.2530 to +0.1635 across the ladder — a spread of 0.42.** That spread is
reported, not hidden, and it is exactly why the headline metrics are reference-free.

Against the raw line, the model's R² is **−0.1867**: the model is 18.7% *worse* than simply reading
the number off the board.

---

## 2. THE DECISIVE TEST — forecast encompassing

`pts ~ 1 + M2 + F1`, n = 1,972. No classical or cluster-robust SE is used anywhere in this screen;
this program has found classical t-statistics untrustworthy twice, independently.

| term | coefficient | headline 95% CI (wider of GAME/PLAYER) | cluster level | permutation p |
|---|---|---|---|---|
| **M2 (market)** | **+1.0978** | **[+0.9556, +1.2450]** | PLAYER | **0.0002** |
| **F1 (model)** | **−0.1604** | [−0.3012, −0.0248] | PLAYER | 0.7111 |

Under §5, "distinguishable from zero" requires **both** an interval excluding 0 **and** a
permutation p < 0.05.

* **bM: both hold → distinguishable. P3 PASSES.**
* **bF: the interval excludes 0 but p = 0.7111 → NOT distinguishable. P2 PASSES.**

**This is preregistered outcome #1: *market encompasses model — the program has no edge on this
population, and that is the answer.***

The market coefficient's interval **contains 1.0**, which is what a well-calibrated forecast looks
like. The model enters with a *negative* sign.

**Same conclusion three ways.** Swap the market arm for the raw line: bF = −0.1401, p = 0.8804.
Swap the model anchor to v14: bF2 = −0.1605, p = 0.6771. The result does not turn on the arm choice.

### Two things not to over-read

**(a) bF's interval excludes zero, on the negative side. That is not an anti-edge worth acting on.**
`corr(M2, F1) = 0.8643`; in the presence of that collinearity a small negative loading is what a
noisier copy of the same information earns. What matters is what it *buys*, and the answer is
nothing — see §3.

**(b) The permutation p-value does not mean what it looks like it means.** The cyclic null for bF is
centred at **+0.1882**, not at zero (95% null interval [+0.0926, +0.2885]), because the cyclic shift
preserves each player's mean level and player mean level genuinely predicts points. The observed
−0.1604 sits *entirely below* that null. So `p = 0.7111` is **not** evidence that bF is near zero —
it is the arithmetic of comparing |−0.16| against null mass sitting near +0.19. The preregistered
number is reported as frozen; **`DEFECTS.md` D2 carries the full account, and it must travel with
this p-value.** The conclusion does not depend on it.

---

## 3. What the combination actually buys — the number that settles it

The encompassing test's inference is contested (D2). The materiality arithmetic is not, and it needs
no null at all:

| comparison | MAE | change |
|---|---|---|
| market-only fitted regression, in-sample | 4.8964 | — |
| market + model blend, in-sample | 4.8885 | **−0.0079** |
| market-only fitted, leave-one-game-out *(POST-HOC)* | 4.9017 | — |
| market + model blend, leave-one-game-out *(POST-HOC)* | 4.8966 | **−0.0051** |

**Preregistered materiality floor: 0.10 MAE points.** The blend buys **0.008** in-sample and
**0.005** out-of-fold — **more than an order of magnitude below the floor**, and the in-sample figure
is the optimistic one because the weights are fitted on the rows they are scored on.

**By the PREREG's own rule this is a TIE. There is no usable combination on this population.**

---

## 4. Is the null informative? Yes — stated before it is interpreted (D136)

An underpowered null is not a finding, so the minimum detectable effect is fixed before any
interpretation:

```
bootstrap SD of bF (wider cluster level)  = 0.0709
MDE(bF) at 80% power, alpha 0.05 two-sided = 2.802 * 0.0709 = 0.1987   (coefficient units)
                                           = 0.0351                    (MAE points)
materiality floor                          = 0.10                      (MAE points)
```

**The smallest edge this screen could detect (0.0351 MAE points) is finer than the smallest edge
that would matter (0.10).** The screen was powered to find any edge large enough to be worth having.
**The null is informative, and it is a real null, not an absence of power.**

*(`s02_score.py` also prints an `UNDERPOWERED` flag against a 0.25 cutoff that is not in the PREREG.
That flag is POST-HOC and is not the argument here — see `DEFECTS.md` D3. The argument above uses
only the PREREG's own materiality floor.)*

---

## 5. The two predictions that failed — both informative, as expected

**P4 — de-vigging materially improves the market estimate: FAILS.**
`MAE(M1) − MAE(M2) = +0.0188`, 95% CI [+0.0007, +0.0365]. The direction is right and the interval
excludes zero, so de-vigging **reliably** helps — but by **0.019 points** against a preregistered
threshold of 0.05 and a materiality floor of 0.10. By the PREREG's own rule this is a **TIE**.
`corr(M1, M2) = 0.9964` says the same thing: the de-vig barely moves the estimate. The proportional
and additive methods are indistinguishable from each other (M3 MAE 4.9038 vs M2 4.9043).

**Useful consequence:** for this market, at this snapshot regime, **the raw line is an adequate
market estimate.** The de-vig machinery is not doing meaningful work and future screens need not
treat it as load-bearing.

**P5 — books shade the over: FAILS.**
`mean(M1) − mean(pts) = +0.1691`, 95% CI **[−0.1121, +0.4455]** — includes zero. The point estimate
points the predicted way and the data cannot distinguish it from no shading at all. **No claim of
over-shading is supported**, and none is made.

P4 and P5 were flagged in advance as genuinely uncertain and expected to be informative either way.
They were.

---

## 6. Subgroups: NOT RUN

§8 pre-specified four subgroups (minutes, cold start, volume, book disagreement) and gated them
behind a single condition: they are examined **only if bF is distinguishable from zero in (A)**. It
is not. **§8 was not run and no subgroup of any kind is reported** — not exploratorily, not "for
colour". The gate exists to stop exactly the search that a disappointing headline invites.

---

## 7. What this screen does NOT say

* It does not say the model is worthless. It says the model adds nothing **to a market price**, on
  **book-priced players**, at **this snapshot regime**, in **2024**.
* It says nothing about the ~60% of played player-games books do not price. That population is
  where a model could still be worth something, and this screen is silent on it **by construction**.
* It promotes nothing and it kills nothing outside its own scope. It is a screen: single partition,
  E1, one season.
* It does not test bet selection, staking, or any decision rule. Only forecast accuracy.

---

## 8. What it does say, plainly

**On the players books choose to price, the market's number is better than ours, and ours adds
nothing on top of it that is worth having.** The market's coefficient is ~1.0 and well calibrated;
ours enters negative and buys 0.005 MAE points out-of-fold against a 0.10 floor.

**One POST-HOC diagnostic worth carrying forward** (not preregistered, flagged as such): the model
is **more dispersed than the market yet less correlated with outcomes** — sd(F1) 4.706 vs sd(M1)
4.297, corr 0.4474 vs 0.5450 — and the univariate slope of `pts` on F1 is **0.7027**, 95% CI
[0.6031, 0.7819], excluding 1.0. **The model's forecasts want shrinking by roughly 30% toward the
mean.** That is the signature of a forecast treating noise as signal, and it is a concrete,
testable lead rather than a lament. It is a lead, not a result: it has not been preregistered or
tested and must not be reported as a finding.

---

## 9. Reproduction

```
python scripts/s00_probe.py     # structural probe (already run 2026-08-17)
python scripts/s01_frame.py     # frame + leak proof (already run 2026-08-17)
python scripts/s02_score.py     # scoring, bootstrap, permutation (run 2026-08-18)
python scripts/s03_report.py    # FINDINGS.json + PARTITION_PROOF.md
python scripts/verify.py        # re-derives every headline number; non-zero exit on any drift
python scripts/verify.py --full # additionally re-runs the seeded bootstrap and permutation null
```

Seeds and draw counts are read from the frozen PREREG and are not parameters of any script:
bootstrap seed 20240817, permutation seed 20240818, 5,000 draws each.
