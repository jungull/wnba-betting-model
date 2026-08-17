# SKILL OR VARIANCE — the central answer

## **It is a variance model, and it does not improve points.**

**Ninety-six channel arms — variance-weighted fitting, shrinkage proportional to predicted
error, mean augmentation, a two-stage mean/variance model, each frozen and unfrozen, on two
out-of-fold schemes and four variance models — produce a best ΔR² on points of +0.00047 at
cluster p = 0.41, against a points-scale detection floor of 0.00072.** Nothing meets the
preregistered decision rule; nothing comes close; and the one channel family whose sign is
systematic contributes about a fifth of the floor.

The conditional-variance forecast itself is **real, well calibrated, and worth having** — top
predicted-error decile realises **1.63×** the absolute points error of the bottom decile
(bootstrap CI 1.42–1.90), calibration slope 0.93 — but **most of that is scoring level**, and
the model the programme already ships emits **one uncertainty value per season** on this
stratum, so it has no competition.

---

## D101 — the denominator, on every number in this document

| | |
|---|---|
| **response** | **`y_pts` — total box points** |
| row set | `A4_CLEAN_DEC` scored rows: 2023–24, `pl_games_prior ≥ 8 & pl_min_mean5 ≥ 24`, date-sorted. **n = 2,945** scored (WF, 138 folds, 600-row warm-up) / **n = 3,549** (GKF) |
| SST basis | `Σ(y_pts − ȳ)²` over the scored rows, about the **unweighted** mean |
| weighting | **none in the metric**; weighting appears only inside a channel's fit |
| base | `B_PTS = [1, pts__pred_point, minutes__pred_point, pl_pts_mean5, pl_min_mean5, pl_fga_mean5, pl_usg_mean5, pl_start_frac5]` |
| fit kind | out-of-fold — WF expanding window by `gdate` (primary), GroupKFold on `player_id` (secondary) |
| statistic | **paired** ΔR² = `(SSE_ref − SSE_treat)/SST` |
| reference | **tuned**: ridge on `B_PTS`, λ by inner time-ordered CV over `10^{-4..4}` |
| inference | cluster **sign-flip** on the paired per-row squared-error difference, **174 player-season** clusters (primary) and 24 team-season (secondary), R = 5,000, `p = (k+1)/(R+1)` |
| floor | **0.00072** (K=1) and **0.00181** (K=132), **points-scale**, from `E1_I0049/REFERENCE_CARD.md`. The published `0.00102 / 0.00235` are `y_ppm` floors and are **not** quoted here |

The tuned reference reaches **out-of-fold R² 0.3183** on points. It beats the raw shipped
forecast `pts__pred_point` by **+0.0067** — the reference is genuinely tuned, not a straw man.

---

## 1. The channels (WF, VSIG — the preregistered primary)

| channel | intercept | ΔR² on points | sign-flip p (player-season) | (team-season) | clears floor? |
|---|---|---:|---:|---:|---|
| S3 add `v̂` | frozen / unfrozen | **+0.000470** | 0.408 | 0.409 | no |
| S3 add `v̂ × level` | frozen / unfrozen | +0.000235 | 0.854 | 0.827 | no |
| S1 WLS `1/v̂` | unfrozen | −0.000027 | 0.915 | 0.926 | no |
| S1 WLS `1/v̂` | frozen | −0.000109 | 0.648 | 0.690 | no |
| S1 WLS `1/v̂²` | unfrozen | −0.000172 | 0.731 | 0.752 | no |
| S2 shrinkage | unfrozen | −0.000047 | 0.835 | 0.830 | no |
| S2 shrinkage | frozen | −0.000213 | 0.234 | 0.292 | no |
| S4 two-stage | unfrozen | −0.000182 | 0.689 | 0.718 | no |
| S4 two-stage | frozen | −0.000318 | 0.468 | 0.536 | no |
| S1 WLS `1/v̂²` | frozen | −0.000322 | 0.500 | 0.563 | no |

**Best ΔR² anywhere across all 96 channel arms in `POINTS_TEST.csv`** (2 schemes × 4 variance
models × 6 channels × 2 intercept arms; 104 rows including the raw-incumbent reference row per
combination): **+0.000470**, WF / VSIG / S3-add-`v̂`, p = 0.408.
That is **0.65× the K=1 points floor** and **0.26× the K=132 floor**.
**Zero channel arms meet the preregistered decision rule** (`ΔR² > 0` and `p < 0.05` and
`ΔR² ≥ 0.00072`).

**P-S1 holds. P-S2 holds** — S3's `v̂` term is not distinguishable from zero.

**The only two channel arms in all 96 that reach cluster `p < 0.05` are harmful.** WF / **VSD** /
S2-shrinkage, frozen and unfrozen: ΔR² **−0.000741** and **−0.000740**, p = 0.020 and 0.020
(team-season 0.035). VSD's `v̂` is a per-season constant, so that channel shrinks every forecast
towards the mean by the same factor — and the *only* statistically significant effect on points
anywhere in this screen is that doing so **costs** about one detection floor. That is the shape
of a genuine null: the sole detectable signal is the one with the wrong sign.

### Frozen versus unfrozen, both arms as required

The pattern is consistent and mildly informative: **freezing the intercept helps the weighting
channels and hurts the shrinkage channel.** Variance weighting down-weights high-variance rows,
which on this stratum are the high-scoring rows, so it shifts the fitted level; forcing the
training-window mean back to the reference's removes that shift. On GKF the frozen arms are the
only positive ones at all (S1 `1/v̂²` frozen **+0.000251** vs unfrozen −0.000056). **The gain, such
as it is, lives in the level correction, not in the slopes.** It is still a fifth of the floor.

---

## 2. The one nuance, and why it is not a positive result

Under the T2 placebo, three channel arms sit far above what a **noise** `v̂` produces:

| channel (GKF, VSIG) | observed ΔR² | placebo mean | placebo sd | z | calibrated one-sided p |
|---|---:|---:|---:|---:|---:|
| S1 WLS `1/v̂` frozen | +0.000143 | +0.000001 | 0.000015 | **+9.2** | 0.0033 |
| S1 WLS `1/v̂²` frozen | +0.000251 | +0.000002 | 0.000031 | **+8.1** | 0.0033 |
| S4 two-stage frozen | +0.000234 | −0.000004 | 0.000031 | **+7.7** | 0.0033 |

**This is not evidence that the channel improves points, and I will not present it as such.**
The placebo varies `v̂` and holds the data fixed, so a placebo-calibrated p answers *"is this
what a noise `v̂` would give on THIS dataset"* — not *"is this distinguishable from zero across
resamples of the data"*. The second question is the one that matters and its answer is the
cluster sign-flip test: **p = 0.34, 0.39, 0.37**. Both numbers are in `FINDINGS.json` with this
warning attached.

What it does establish, honestly: **variance weighting has a systematic, correctly-signed,
non-zero effect on the points forecast — of magnitude ≈ 2×10⁻⁴ ΔR², i.e. roughly one third of
the single-cell detection floor and one eighth of the family floor.** It is real and it is too
small to matter. That is a different sentence from "there is nothing there", and it is the one
the data supports.

### The T2 placebo also condemns two of my own channels

| channel | mean signed ΔR² under H0 | required | Type-I at 0.05 |
|---|---:|---|---:|
| S1 (both powers), S2, S4 | +1e-6 … −4.9e-5 | \|mean\| < 2e-4 | 0.023 – 0.087 |
| **S3 add `v̂`** | **−2.91e-4** | ✗ | **0.160** |
| **S3 add `v̂ × level`** | **−2.18e-3** | ✗ | **0.117** |

**The S3 channels are not centred and their sign-flip test over-rejects at 3× nominal.** Their
nominal p-values are not usable, and the best-in-screen +0.00047 belongs to one of them. Read
against its own placebo (mean −2.9e-4, sd 5.1e-4) it is **+1.5 sd** — which is exactly nothing.
S2's placebo rate 0.087 also exceeds the 0.075 tolerance the programme inherited; S2's observed
result is negative, so it costs nothing here, but it is recorded.

---

## 3. What the variance model *is* worth (PART C — measured whatever PART S said)

`CALIBRATION.csv`, `CALIBRATION_DECILES.csv`. Out-of-fold, WF scheme, n = 2,945.
**D101: response is `absres_<target>` on the A4 scored rows, SST about its own unweighted mean.
None of this is comparable to a points ΔR².**

| target | model | decile-1 realised \|err\| | decile-10 | **ratio** | boot 95% CI | ρ | OOF R² | calib. slope |
|---|---|---:|---:|---:|---|---:|---:|---:|
| pts | **VSIG** | 3.781 | 6.160 | **1.629** | 1.422 – 1.902 | 0.141 | **+0.0255** | 0.932 |
| pts | VLEV (level only) | 3.841 | 6.311 | **1.643** | 1.420 – 1.912 | 0.122 | +0.0238 | 0.831 |
| pts | VALL (58 cands, ridge) | 3.928 | 5.721 | 1.457 | 1.263 – 1.755 | 0.119 | +0.0150 | 0.660 |
| pts | **VSD (the incumbent)** | 5.424 | 4.677 | **0.862** | 0.759 – 1.007 | −0.031 | **−0.0064** | −0.514 |
| pts | V0 (constant) | 5.283 | 4.916 | 0.931 | — | −0.033 | −0.0005 | — |
| minutes | **VSIG** | 3.004 | 5.735 | **1.909** | 1.645 – 2.253 | 0.205 | **+0.0429** | 1.012 |
| minutes | VLEV | 3.772 | 5.109 | 1.354 | 1.141 – 1.669 | 0.178 | +0.0184 | 0.836 |
| fga | **VSIG** | 2.345 | 3.355 | 1.431 | 1.265 – 1.665 | 0.129 | +0.0190 | 1.009 |
| fga | VLEV | 2.155 | 3.497 | **1.623** | 1.372 – 1.864 | 0.141 | +0.0277 | 0.994 |

Read this table three ways, all of which matter:

1. **The variance forecast works and is honestly calibrated.** Slopes 0.93 / 1.01 / 1.01 —
   a row it says will miss by 6 points misses by about 6 points. Top-vs-bottom decile spreads
   of **+2.38 points**, **+2.73 minutes**, **+1.01 FGA** of realised absolute error, all with
   bootstrap CIs clear of 1.0.
2. **On points and FGA it is a volume proxy.** `VLEV` — **trailing scoring level, one column,
   nothing else** — matches it on points (1.643 vs 1.629) and beats it on FGA (1.623 vs 1.431).
   **Only on minutes does the volatility feature set add anything real** (1.909 vs 1.354).
   That is the same four cells that survived the volume base, arrived at independently.
3. **The incumbent uncertainty is worse than useless.** `<target>__pred_sd` takes **exactly one
   value per season** on the decision stratum, so `VSD`'s decile ordering is noise, its ratio is
   **0.86**, and its OOF R² is **negative**. **P-C3 FAILS**: I predicted VSIG would not beat VSD
   by more than 0.02 OOF R² on points; the measured gap is **0.032**, because VSD is degenerate,
   not because VSIG is strong. P-C1 and P-C2 hold.

### Abstention — the one channel that "works", and what it actually is

`ABSTENTION.csv`: dropping the top **30%** of rows by predicted error cuts points MSE on the
retained rows by **13.2%** (WF/VSIG), p = 0.0005 against 2,000 matched random subsets.
**P-S3 FAILS** — I preregistered > 15% and measured 13.2%.

**POST-HOC decomposition (`_ABSTENTION_DECOMPOSED.csv`), and it is the check that stops this
becoming a skill claim:**

| rule (WF, drop top 30%) | MSE reduction | response-variance reduction | R² on retained rows | change in R² |
|---|---:|---:|---:|---:|
| predicted error `v̂` | 12.5% | 22.1% | 0.234 | **−0.084** |
| **forecast level alone** | **13.7%** | 25.0% | 0.215 | −0.103 |

**Abstention lowers MSE by removing high-variance rows, not by forecasting them better. R² on
the retained rows FALLS by 8.4 points. And a rule that abstains on the forecast's own point
prediction — "don't bet on high scorers" — does at least as well.** The abstention channel is
not a use of the variance model; it is a restatement of the level. It is genuinely useful for
stake sizing and it must be described in exactly those words.

---

## 4. The answer, in the form the programme asked for

* **Does forecasting `|residual|` improve a forecast of POINTS on the decision stratum against
  a tuned reference?** **No.** 96 channel arms, 2 schemes, 4 variance models, frozen and
  unfrozen. Best +0.00047 at p = 0.41, below a 0.00072 floor, and it belongs to the one channel
  family whose null is not centred.
* **Is it a variance model?** **Yes, and a well-calibrated one** — decile ratio 1.63 on points,
  1.91 on minutes, calibration slope ≈ 1.
* **Is the variance model itself a volume proxy?** **On points and FGA, essentially yes**
  (trailing level alone matches or beats it). **On minutes, no** — and that is the whole of the
  non-degenerate result.
* **Should anything be promoted?** **No.** I recommend no production change. The measurable
  deliverable here is a *minutes*-uncertainty forecast and a defensible abstention rule, both of
  which are variance objects, and the abstention rule is dominated by a one-column level rule.

---

## 5. What most weakens my own conclusion

1. **A null result is cheap to produce badly.** The strongest counter-evidence I have against
   myself is §2: three channel arms sit **7.7–9.2 sd** above their own placebo. If a future
   screen finds a test with real power against a 2×10⁻⁴ effect, the sign is already known and
   it is positive. I could not detect it and I say so; I did not prove it is zero.
2. **My reference may be too good.** A tuned ridge on eight columns including the shipped
   forecast reaches R² 0.3183. If the mean model were correctly specified, inverse-variance
   weighting is only an efficiency gain and a small one — which is precisely what I measured.
   Against a *worse* mean model the variance channel would look better, and that would be a
   statement about the mean model, not about the variance signal.
3. **The WF arm scores 2,945 of 3,549 rows.** The 604 warm-up rows are the earliest of 2023 and
   are dropped. The GKF arm scores all 3,549 but leaks time. Both are reported; neither is
   clean on both axes.
4. **S2's tuning is mildly self-serving.** θ is tuned on previously-scored out-of-fold rows,
   which is honest, but the grid was searched on the training window's own SSE. Any bias is
   **towards** the treatment, which makes the null stronger, not weaker.
5. **`E1_I0050` said this first.** Its §5.5 states plainly that none of this makes a betting
   edge because the response is forecast-error magnitude. It was right. This document is the
   measurement, not the discovery, and the credit belongs upstream.
6. **The four surviving minutes cells were never put through PART S.** I tested whether
   predicted *points* error improves *points*. I did not test whether predicted *minutes* error
   improves a *minutes* forecast, because minutes is not the decision variable and a positive
   there would still not be a points result. Someone may want it; it is not here.
