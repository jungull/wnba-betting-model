# REPRODUCTION — do the sixteen reproduce?

## **Yes. Exactly, at three independent seeds, on both arms.**

Rebuilt from source artifacts by an independent re-implementation. `E1_I0044`'s and
`E1_I0050`'s scripts were **read for specification and never imported or executed**; the only
inputs are `E0_I0014/analysis_frame.parquet`, `E0_I0014/screen_results.csv` and
`E0_I0014/permutation_nulls.npz`.

PREREG sha256 `7054f16908c7a2360aab0e48cd932ae1979a88a85e449e74ac373b3600a4c36a`.
Partition **2021–2024**; the frame contains 2022–2024 only; **2025/26 was never opened.**

---

## 1. Anchors — every one passes before any new statistic

| id | anchor | result | tolerance |
|---|---|---:|---|
| **R-A1** | my `t_classical`, **348 cells**, 13,879 rows, vs `E0_I0014/screen_results.csv` | max relative `\|Δt\|` **3.94e-15**; **276 of 348 bitwise identical** | < 1e-9 ✅ |
| **R-A2** | my `delta_r2_plain_unweighted`, 348 cells, same file | max `\|ΔΔR²\|` **9.89e-17** (max `\|Δβ\|` 3.55e-15) | < 1e-12 ✅ |
| **R-A3** | my A4 observed signed `t` and ΔR², 50 estimable queue cells, vs `E1_I0050/CORRECTED_VERDICTS.csv` | max `\|Δt\|` **4.44e-16**, max `\|ΔΔR²\|` **9.85e-17** | < 1e-9 ✅ |

Arm shape reproduces on the nose: **A4_CLEAN_DEC n = 3,549 in 174 player-season blocks**
(and 24 team-season blocks), seasons 2023–24. A1_FULL n = 13,879 in 475 player-season blocks.

## 2. The sixteen

Composed-2 null rebuilt from spec (receiving block filled by a uniform resample of the whole
donor block; one shared gather index per draw across all 58 candidates; PLAYER-scheme on
player-season blocks, TEAM-scheme on team-season blocks). `R = 2,000`, bar = q95 of `max|t|`
over the **348**-cell family, `p = (k+1)/(R+1)`. Cell selection is by **numeric predicate**
(`p_familywise_plus1 < 0.05` **and** null validity `ACCEPTABLE*`) — **no substring matching
anywhere**.

| seed | A4 family-wise-significant cells | symmetric difference vs the published 16 |
|---|---:|---:|
| 20260808 | **16** | **0** |
| 20260809 | **16** | **0** |
| 20260810 | **16** | **0** |

**A1_FULL, seed 20260808: 36 cells, symmetric difference 0** against `E1_I0050`'s
24 `FAMILYWISE_SIGNIFICANT` + 12 `FAMILYWISE_SIGNIFICANT_BUT_CONFOUNDED_WITH_BLOCK_POSITION`.

Bars: A4 **5.2935 / 5.3342 / 5.2653** against `E1_I0050`'s published **5.3231** (P-R3 required
±0.30; the gap is 0.030). A1 **5.7034** against its **5.8346**.

**All three preregistered predictions hold: P-R1 (set size 16), P-R2 (symdiff ≤ 2), P-R3 (bar within 0.30).**

### The sixteen, on the published base B0 (season fixed effects only)

`p_fw (mine)` is from my own 2,000 composed-2 draws at seed 20260808; `p_fw (E1_I0050)` is the
published value. They agree to within draw noise on every cell and mine is uniformly the
slightly smaller of the two.

| cell | signed t | ΔR² | p_fw (mine) | p_fw (E1_I0050) |
|---|---:|---:|---:|---:|
| pts__pred_cv \| pts_absres | −10.001 | 0.02743 | 0.0010 | 0.0010 |
| pl_min_rng5 \| minutes_absres | +9.556 | 0.02511 | 0.0015 | 0.0015 |
| pl_min_sd5 \| minutes_absres | +9.382 | 0.02422 | 0.0015 | 0.0015 |
| pts__pred_cv \| pts_sqres | −9.351 | 0.02407 | 0.0015 | 0.0015 |
| pts__pred_cv \| fga_absres | −8.369 | 0.01937 | 0.0020 | 0.0020 |
| pts__pred_cv \| fga_sqres | −8.184 | 0.01854 | 0.0025 | 0.0025 |
| pts__pred_cv \| minutes_sqres | +7.490 | 0.01557 | 0.0055 | 0.0065 |
| pl_abs_min_trend5 \| minutes_absres | +7.048 | 0.01381 | 0.0055 | 0.0070 |
| pl_start_switch5 \| minutes_absres | +6.790 | 0.01283 | 0.0070 | 0.0090 |
| pl_min_rng5 \| minutes_sqres | +6.736 | 0.01264 | 0.0070 | 0.0090 |
| pl_min_sd5 \| minutes_sqres | +6.650 | 0.01232 | 0.0070 | 0.0100 |
| pl_dnp_frac5 \| minutes_sqres | +6.372 | 0.01132 | 0.0085 | 0.0125 |
| pts__pred_width \| minutes_absres | −6.267 | 0.01096 | 0.0095 | 0.0135 |
| pl_abs_min_trend5 \| minutes_sqres | +5.736 | 0.00919 | 0.0265 | 0.0280 |
| pl_pts_sd5 \| pts_absres | +5.520 | 0.00852 | 0.0365 | 0.0385 |
| pl_dnp_frac5 \| minutes_absres | +5.398 | 0.00815 | 0.0425 | 0.0460 |

ΔR² 0.0082–0.0274, exactly as published. **D101: every one of these is a ΔR² on
`|residual|` or `residual²` of a forecast**, on the A4 rows, season-FE base, season-demeaned
SST, unweighted. **Not on points. It is never comparable to a points number.**

**Only three of the sixteen have a points-error response at all** (`pts_absres` ×2,
`pts_sqres` ×1). **Eleven are minutes; two are fga.** The programme's largest apparent positive
result is mostly about **minutes**.

---

## 3. Single-cell dominance of the family-wise bar (T4 — mandatory, and the contrast is the point)

| bar | top supplier | share of draws | distinct suppliers |
|---|---|---:|---:|
| `E0_I0014` **as published**, rebuilt from its own `permutation_nulls.npz` | `pl_pts_sd5\|pts_absres` | **1000 / 1000 = 100%** | **1** |
| repaired composed-2, A4, seed 20260808 | `tm_poss_mean_prior\|minutes_absres` | 249 / 2000 = **12.5%** | **284** |
| repaired composed-2, A1 | same | 8.1% | 282 |

The published bar reproduces to `0.00e+00` against `familywise_summary.json`
(mean 27.5776, p95 29.1266). `E1_I0050`'s diagnosis is confirmed exactly and independently.
The repaired bar is a bar: no cell owns it.

**A finding of my own that nobody has flagged**: the repaired bar's most frequent supplier is
a **TEAM-scheme** candidate, and on the decision stratum there are only **24 team-season
blocks** against 174 player-season blocks. The family-wise bar for these 348 cells is set
mostly by the 17 team-level candidates whose nulls are the widest because they have the
fewest blocks. Every player-level cell in this family is therefore judged against a bar it
does not contribute to. That is conservative, not liberal, and it is recorded in `DEFECTS.md`.

---

## 4. Blindness (T3) — a Type-I audit does not subsume it

The composed-2 null's **mean signed `t` on the real response**, all 54 cells, A4:
**max |mean| = 0.0723**, threshold 0.20. On A1: same, none blind. **0 of 54 blind on either
arm.** The published within-block null sits at +27.6 on one of these cells; the repaired null
sits at 0.07 at worst. Both instruments were run; both pass.

## 5. Level (T1) — with a **centred** generator, checked before it was used

`TYPEI_CENTRED.csv`, B = 1,000 synthetic datasets per cell per generator, POOL = 1,000,
R_NULL = 500.

| | EXCH + CIRCSHIFT (H0 holds) |
|---|---|
| **centred?** `\|mean SIGNED observed t\| < 0.15` | **40 of 40 pairs pass**, max **0.0948** |
| composed-2 Type-I, nominal 0.05, tolerance 0.075 | median **0.0235**, max **0.0580**, **0 over tolerance** |

The defective `BLOCKBOOT` generator, run as a labelled diagnostic and **never used to accept
or reject anything**, fails the centring requirement on **7 of 20** cells, max |mean signed t|
**0.3595**. `E1_I0050`'s F-2 reproduces in my hands.

**Direction, stated plainly: the repaired null is conservative — median Type-I is under half
nominal. It cannot manufacture the sixteen. It can only suppress them.**

---

## 6. What most weakens this document

1. **This reproduces the statistic, not the frame.** Every number above rests on
   `E0_I0014/analysis_frame.parquet` being what it says it is. I rebuilt the screen from that
   file; I did not rebuild the file. If the forecasts in it are wrong, everything downstream
   is wrong in the same way — and §2 of `VOLUME_PROXY.md` shows one column in it
   (`<target>__pred_sd`) is degenerate on the decision stratum, which nobody had noticed.
2. **I inherited `E1_I0050`'s per-cell Type-I verdicts for the 54** rather than re-measuring
   all of them; I re-measured only the 16 (and the 4 that survive the volume base). The two
   cells `E1_I0050` marks `INVALID_ANTICONSERVATIVE` are excluded on its authority, not mine.
   Its own `D-5` notes a reader with a 0.10 tolerance would keep them.
3. **The bar is still contaminated** in exactly the way `E1_I0050` says: it is built over all
   348 cells including ones whose nulls nobody validated, and it is dominated by team-scheme
   candidates with 24 blocks. Conservative, but not the bar an exact null would give.
4. **A perfect reproduction of a statistic says nothing about what the statistic means.**
   The sixteen are real and they are reproducible. `VOLUME_PROXY.md` shows twelve of them are
   a restatement of *"this player scores more"*, and `SKILL_OR_VARIANCE.md` shows none of them
   moves a points forecast. Reproducibility was never the question.
