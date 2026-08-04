# Stage 2A hypotheses — source: CLAUDE COORDINATOR

**Generation order: FIRST.** Written and frozen before any specialized reasoning agent was
launched, and before any agent output existed. No agent has seen this file.

Evidence packet: `EVIDENCE_PACKET.json`, sha256
`f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`.
Nothing fitted. No accuracy opened.

---

## The observation that drives most of what follows

Aggregate bias is negligible — squared bias is **0.19%** of MSE, so at the whole-sample level the
incumbent looks unbiased and its error looks purely dispersive.

**That aggregate is misleading.** Within strata the incumbent carries large, opposite-signed
biases that cancel:

| stratum | n | MAE | bias |
|---|---|---|---|
| `team_window_prior_season` (level 2) | 183 | 3.693 | **−2.845** |
| games 1–3 of a season | 228 | 3.778 | **−2.175** |
| 7+ days rest | 162 | 3.527 | −1.435 |
| support 3–4 games | 156 | 3.144 | **+1.342** |
| support 5–9 games | 390 | 3.065 | **+1.147** |
| support 10 (full window) | 2413 | 2.846 | −0.065 |

A −2.8 bias on 183 rows and a +1.3 bias on 156 rows are both real and point in opposite
directions. "The error is all variance" is true of the pooled number and false of the parts.
This is the same pooled-versus-stratum blindness the wave already paid for once, at fold level.

Variance explained versus the target is **0.116** — the incumbent captures about a ninth of
possession variance.

---

## Category A — immediately testable (cutoff-valid, available, reproducible)

### A1. Season-level league drift correction for the prior-season fallback
* **Mechanism.** League pace is not stationary across seasons. Level 2 reuses last season's
  window at last season's level, so if the league has sped up, every level-2 row under-projects
  by roughly the league's year-over-year shift.
* **Expected direction.** Removes most of the −2.845 bias on level-2 rows. Strictly a level
  correction, so it should not help level-1 rows at all.
* **Stratum.** `team_window_prior_season` (183), and by extension games 1–3.
* **Inputs.** League mean `game_pace` to date this season and over the prior season, both from
  strictly earlier dates. **Exists.**
* **Leakage risk.** Low, if the current-season league mean uses only earlier dates.
* **Overlap.** High with A2 and A6 — probably one latent mechanism.
* **Information gain.** High per row, small in aggregate (183 of 2,982 rows).
* **Falsifier.** Level-2 bias does not move toward zero, or level-1 MAE degrades.
* **Changes.** The total.

### A2. Continuous support-weighted blend replacing the discrete fallback ladder
* **Mechanism.** The incumbent switches hard at `MIN_HISTORY_M=3` between same-season,
  prior-season and league prior. A discrete switch is a step change in a quantity that varies
  smoothly with evidence. A blend weighted by support would remove the step.
* **Expected direction.** Fixes both tails at once — the under-projection at 1–3 games and the
  over-projection at 3–9 games are opposite-signed errors of the same switching rule.
* **Stratum.** Everything below full support: 156 + 390 + 228 rows.
* **Inputs.** Same as the incumbent plus a support count. **Exists.**
* **Leakage risk.** Low.
* **Overlap.** High with A1 and A5.
* **Information gain.** Moderate-to-high; touches ~20% of rows.
* **Falsifier.** No improvement over the discrete ladder once A5 shrinkage is present.
* **Changes.** The total and the calibration at low support.

### A3. Recency weighting inside the window (EWMA family)
* **Mechanism.** The unweighted 10-game mean gives the 10th-most-recent game the same weight as
  the most recent. If a team's pace drifts within a season, recent games are more informative.
* **Expected direction.** Small variance reduction at full support; possibly harmful if pace is
  genuinely stationary within a season and recency merely adds noise.
* **Stratum.** Full-support rows (2,413) — the bulk.
* **Inputs.** The existing window. **Exists.**
* **Leakage risk.** None beyond the incumbent's.
* **Overlap.** Low with A1/A2; competes with A5.
* **Information gain.** Uncertain. WS4 falsified faster adaptation *in the opposite direction*
  for player turnover rates — error was monotone in memory length. That is a different quantity,
  but it is a genuine prior against this hypothesis and must be stated.
* **Falsifier.** No half-life beats the flat window out of fold.
* **Changes.** The total.
* **Multiplicity note.** Half-life is a hyperparameter. All half-lives nest inside this ONE
  family and count once.

### A4. Opponent pace interaction
* **Mechanism.** The incumbent projects a game as the unweighted mean of the two sides' own-pace
  estimates — an assumption that tempo combines symmetrically and additively. Basketball says
  otherwise: a team that walks the ball up can impose tempo more than a fast team can force it,
  because the slow team controls its own offensive possession length while the fast team cannot
  shorten the opponent's.
* **Expected direction.** Improves games with a large pace gap between the two sides; null where
  the sides are similar. Asymmetric weighting, not a symmetric mean.
* **Stratum.** Not visible in the current strata — needs a pace-gap stratum. That is itself a
  reason to test it.
* **Inputs.** Opponent's own lagged pace history. **Exists**, and the incumbent already computes
  it for the other side of the same game.
* **Leakage risk.** Low.
* **Overlap.** Low — genuinely distinct from every window-shape hypothesis.
* **Information gain.** Potentially the highest of the A set, because it is the only one that
  changes the *functional form* rather than the *estimator of the same quantity*.
* **Falsifier.** Asymmetric weighting does not beat the symmetric mean, or gains appear only in
  one season.
* **Changes.** The total, and within-game differentiation (currently zero: both sides get an
  identical projection).

### A5. Support-scaled shrinkage toward a current-season league mean
* **Mechanism.** A 3-game mean and a 10-game mean are treated identically. Classic
  James–Stein/empirical-Bayes: shrink toward the league mean in inverse proportion to support.
* **Expected direction.** Removes the +1.34 / +1.15 over-projection at low support and reduces
  dispersion there. Near-null at full support.
* **Stratum.** Support 3–4 and 5–9 (546 rows).
* **Inputs.** Support count and current-season league mean to date. **Exists.**
* **Leakage risk.** Low.
* **Overlap.** High with A2 — A2 is the blend, A5 is the shrinkage; they may be the same family
  expressed two ways.
* **Information gain.** Moderate, and it is the most standard statistical fix available.
* **Falsifier.** Shrinkage does not beat the raw window at any support level.
* **Changes.** The total and low-support calibration.

### A6. Schedule-gap staleness term
* **Mechanism.** After a long layoff the window is stale relative to league drift, and the team
  itself may return at a different tempo.
* **Expected direction.** Removes part of the −1.435 bias on 7+ days rest.
* **Stratum.** 7+ days rest (162 rows).
* **Inputs.** Schedule dates only. **Exists.**
* **Leakage risk.** None.
* **Overlap.** **HIGH with A1** — long gaps often span league breaks, so this may be league drift
  wearing a schedule costume. Must be tested against A1, not merely alongside it.
* **Information gain.** Low-to-moderate; small stratum.
* **Falsifier.** The gap term is null once A1's drift correction is present.
* **Changes.** The total.

### A7. Home/away tempo asymmetry
* **Mechanism.** Home teams may play marginally faster. `is_home` is genuinely pregame and fully
  covered.
* **Expected direction.** Small and symmetric — it cannot change the game total under the
  incumbent's symmetric mean unless the functional form also changes, so it is really a
  sub-hypothesis of A4.
* **Inputs.** `is_home`. **Exists**, 2990/2990.
* **Information gain.** Low. I record it mainly to be explicit that I considered and nearly
  rejected it.
* **Falsifier.** No home effect after conditioning on the pace gap.
* **Changes.** Within-game allocation only, unless combined with A4.

---

## Category B — high-value but currently UNAVAILABLE (roadmap only, not arms)

### B1. Coaching identity and coaching change
* **Missing input.** No coaching source exists anywhere in the repository.
* **Why it may matter.** Pace is among the most coach-determined team properties. A coaching
  change is a structural break that a trailing window cannot see and will absorb slowly and
  wrongly.
* **Minimum viable collection.** A hand-maintained coach-by-team-season table — 12 teams × 6
  seasons is a small, one-time effort.
* **Prospective-only validation.** No — a historical table would be immediately usable.
* **Expected value of closing.** High relative to cost. This is the cheapest genuinely new
  information channel identified.

### B2. Pregame injury and availability
* **Missing input.** Injury capture spans 2026-07-30 to 2026-08-04 — six days of a five-season
  span.
* **Why it may matter.** Losing a primary ball-handler plausibly changes possession rate.
* **Prospective-only validation.** Yes.

### B3. Announced starting lineup / expected rotation
* **Prospective-only validation.** Yes.

### B4. Travel distance and time-zone change
* **Missing input.** No venue table with coordinates.
* **Minimum viable collection.** A static 12-team venue table. Cheap.
* **Prospective-only validation.** No.

### B5. Market total as an external consensus pace signal
* **Caution.** This changes what the model *is*. It would no longer be a pace projection but a
  market-anchored forecast, with different failure modes and different questions about what is
  being learned. Recorded, but I would not prioritise it.

---

## What I expect to be wrong about

* A3 (recency) is the hypothesis I would most expect to fail, because WS4 found error monotone in
  memory *length* for a related quantity. I am including it because that was a different target
  and the prior should be tested, not assumed to transfer.
* A1, A2, A5 and A6 are probably **not four mechanisms**. They are plausibly two — a league-drift
  level correction and a support-dependent shrinkage — and the deduplication step should be
  sceptical of my own list here.
* A4 is the one I would defend hardest as genuinely distinct, and the one I would most regret
  omitting.
