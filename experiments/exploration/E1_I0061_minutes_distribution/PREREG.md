# E1_I0061 — minutes as a DISTRIBUTION, not a point plus a constant

Frozen before any score, loss, coverage or calibration statistic existed. What was known at
freezing is the **shape of the response only**, printed from the frame: 21,462 dressed rows
across 2021–2024, of which 18,212 played and 3,250 did not; played minutes mean 21.45, sd
10.67, **skew −0.207, kurtosis −1.026**, quantiles 0.98 / 3.20 / 5.65 / 12.93 / 22.40 / 30.55
/ 34.82 / 36.85 / 40.00 at q01…q99, 2.73% under two minutes and 9.53% at or above 35.

No forecast, no arm and no comparison had been run.

**Partition: exploration 2021–2024 only. 2025 and 2026 are never read, joined, plotted or
described.**

---

## Why this screen exists

Two facts from the programme's own record put it here.

1. **The shipped per-row minutes uncertainty is a per-season scalar.** E1_I0056 confirmed it
   on the emitted bytes: `pred_sd` takes exactly one value per season, and the quantiles are
   the point forecast plus a constant offset. It cannot have positive out-of-fold R² by
   construction.
2. **Its nominal 80% interval covers 68.5%.** And every alternative tested so far — L1, L4,
   C5 — is still `point ± k × sd` with a Gaussian shape. At matched 80% coverage those give
   mean widths of 13.02 / 13.21 / 13.38 against the shipped 13.39: **a 2.8% improvement at
   best from modelling the scale.**

Everything tried so far has varied the **scale**. Nobody has questioned the **shape**. With
kurtosis −1.03 on a support bounded at [0, 48], a Gaussian is visibly the wrong family, and a
mis-shaped distribution cannot be fixed by rescaling it.

**This screen's thesis: for minutes, SHAPE matters more than SCALE.**

## Universe, frozen

- **U_PLAYED**: rows with `appeared = 1` and at least 5 prior same-season appearances.
- **U_DRESSED**: all rows with at least 5 prior appearances, DNP rows included, minutes 0.
  Carried because a prop is a question about a *dressed* player, and a forecast that
  conditions on playing has silently dropped the branch where the bet loses badly.

## Point forecast, frozen and shared by every arm

`m_hat` = EWMA of the player's own prior same-season minutes, **half-life 2**, the setting the
reference ladder selected for minutes. Every arm below uses the **identical** point forecast,
so the only thing varying is the distribution placed around it.

## Arms, frozen

| id | distribution |
|---|---|
| `A0_SHIPPED_STYLE` | Gaussian, sd = one constant per season (fitted on earlier seasons), clipped to [0, 48] |
| `A1_PERROW_GAUSS` | Gaussian, sd = per-row, from the player's own prior residual dispersion, clipped |
| `A2_EMPIRICAL_GLOBAL` | `m_hat` + the **empirical residual quantiles** pooled over training seasons |
| `A3_EMPIRICAL_COND` | `m_hat` + empirical residual quantiles conditional on **predicted-level decile × prior-volatility tercile** |
| `A4_MIXTURE` | `A3` for the played branch, times `P(play)`, with an explicit **point mass at 0** — evaluated on U_DRESSED |

`A2`/`A3` are deliberately non-parametric: they impose no family at all and are cheap. If the
thesis is right, they should beat both Gaussians without any extra information — the same
point forecast, only a better-shaped distribution around it.

## Metrics, frozen. PRIMARY is CRPS.

CRPS is computed **identically for every arm** by numerical integration of
`(F(x) − 1{y ≤ x})²` over a fixed grid `x = 0, 0.25, …, 48`, so no arm is advantaged by its
parameterisation. Also reported:

- pinball loss at deciles 0.1…0.9
- PIT calibration: histogram of `F(y)` in 10 bins, and its chi-square distance from uniform
- 80% interval coverage, and **mean width at scale-matched 80% coverage** (the comparison
  E1_I0056 used, so this screen's numbers are commensurable with its)
- **threshold Brier** for `P(minutes > t)` at `t ∈ {15, 20, 25, 30, 35}` — the prop-shaped
  question, and the one a point forecast cannot answer at all

## Validation, frozen

Walk-forward by season: every quantity fitted on seasons **strictly earlier** than the season
scored. 2021 is unscored and reported as such. Intervals from a **cluster bootstrap by
player-season, 2,000 draws, seed 20260820**.

## Predictions, committed before computing

- **P1** `A0` is miscalibrated: 80% interval coverage below 0.75. *(E1_I0056 measured 0.685 on
  a different stratum; this restates it on this one and would fail if that does not carry.)*
- **P2** **SHAPE beats SCALE**: the CRPS gain of `A3` over `A0` is at least twice the CRPS
  gain of `A1` over `A0`. **This is the thesis and the screen's reason to exist.**
- **P3** `A3` improves CRPS over `A0` by more than 3%.
- **P4** `A0`'s PIT histogram is non-uniform with **excess mass in the outer bins** — the
  signature of a distribution that is too narrow in the tails.
- **P5** At scale-matched 80% coverage, `A3`'s mean interval width is more than 5% narrower
  than `A0`'s. *(The scale-only arms managed 2.8%.)*
- **P6** On U_DRESSED, `A4` beats `A3` on threshold Brier at every `t`, by more than 10%
  relative at `t = 15`. Ignoring the DNP branch should hurt most at the low thresholds.

## What would make this screen worthless

- **The point forecast is not re-tuned and is not the contribution.** Any CRPS difference here
  is attributable to the distribution alone, by construction. If a reader wants a better point
  forecast, that is E1_I0053's territory and it reported seven of eight candidates null.
- **CRPS on a grid is an approximation.** Grid 0.25 minutes over [0, 48]; the same grid for
  every arm, so comparisons are fair even where the absolute value is not exact.
- **`A3`'s conditioning bins can be sparse.** Any bin with fewer than 50 training rows falls
  back to the pooled `A2` quantiles; the fallback rate is reported, never hidden.
- **Nothing here is a wager-shaped claim.** S42 stands. This is a distributional forecast of
  minutes on exploration data, and it authorises no use of any model against any market.
