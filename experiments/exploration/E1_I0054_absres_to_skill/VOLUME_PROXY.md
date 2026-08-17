# VOLUME_PROXY — how much of it is just "this player scores more"?

## **Twelve of the sixteen. Four survive.**

Put trailing scoring level in the base **from the start** and the median cell keeps
**24%** of its ΔR². Five of the sixteen keep **less than 1%**. The four that survive are all
about **minutes volatility**, and none of them is about points.

`VOLUME_PROXY.csv` · `_LEVEL_CORRELATIONS.csv` · `_PRED_COLUMN_DEGENERACY.csv` ·
`_PRED_CV_MECHANISM.csv` · `_PRED_CV_SUBSTITUTION.csv` · `_BAR_ANATOMY_BY_BASE.csv` ·
raw draws in `raw/composed2_A4_CLEAN_DEC_B*.npz`.

---

## 1. The bases

Every base carries season fixed effects. Every base gets its **own** composed-2 null over the
**same 348-cell family** (R = 2,000, seed 20260808), its **own** bar and its **own** p.
The only cross-base quantity is the ratio `ΔR²(Bk)/ΔR²(B0)`, reported as a retained share on
one arm, one response, one row set.

| id | base | bar q95 |
|---|---|---:|
| **B0** | season FE only — **the published base** | 5.2935 |
| **B1** | B0 + matched trailing level (`pl_pts_mean5` / `pl_min_mean5` / `pl_fga_mean5`) | 5.1362 |
| **B2** | B1 + matched forecast level (`<target>__pred_point`) | 5.0827 |
| **B3** | B0 + **all eight** level columns, identical for every cell — mapping-free control | 4.8881 |
| **B4** | POST-HOC: B3 + the three emitted `pred_sd` columns | 4.8881 |

---

## 2. Result

| | B0 | B1 | B2 | B3 | B4 (post-hoc) |
|---|---:|---:|---:|---:|---:|
| **of the 16, still family-wise significant** | **16** | **6** | **5** | **4** | **4** |
| median retained share of ΔR² | 1.000 | 0.475 | 0.398 | **0.238** | 0.238 |

### Per cell, retained share of ΔR² vs the published base

| cell | B1 | B2 | **B3** | verdict |
|---|---:|---:|---:|---|
| `pts__pred_cv \| fga_sqres` | 0.002 | 0.001 | **0.003** | **VOLUME PROXY** |
| `pts__pred_cv \| pts_absres` | 0.120 | 0.012 | **0.003** | **VOLUME PROXY** |
| `pts__pred_cv \| pts_sqres` | 0.051 | 0.000 | **0.004** | **VOLUME PROXY** |
| `pts__pred_cv \| fga_absres` | 0.007 | 0.004 | **0.007** | **VOLUME PROXY** |
| `pts__pred_cv \| minutes_sqres` | 0.603 | 0.365 | **0.013** | **VOLUME PROXY** |
| `pts__pred_width \| minutes_absres` | 0.421 | 0.241 | **0.036** | **VOLUME PROXY** |
| `pl_pts_sd5 \| pts_absres` | 0.060 | 0.084 | **0.056** | **VOLUME PROXY** |
| `pl_start_switch5 \| minutes_absres` | 0.479 | 0.342 | **0.108** | **VOLUME PROXY** |
| `pl_abs_min_trend5 \| minutes_absres` | 0.472 | 0.430 | **0.368** | survives on ΔR², loses the bar |
| `pl_abs_min_trend5 \| minutes_sqres` | 0.644 | 0.587 | **0.499** | survives on ΔR², loses the bar |
| `pl_min_sd5 \| minutes_sqres` | 0.602 | 0.606 | **0.491** | survives on ΔR², loses the bar |
| `pl_min_rng5 \| minutes_sqres` | 0.614 | 0.614 | **0.502** | survives on ΔR², loses the bar |
| **`pl_min_sd5 \| minutes_absres`** | 0.463 | 0.466 | **0.386** | **SURVIVES B3** (p_fw 0.0145) |
| **`pl_min_rng5 \| minutes_absres`** | 0.482 | 0.483 | **0.404** | **SURVIVES B3** (p_fw 0.0110) |
| **`pl_dnp_frac5 \| minutes_absres`** | 0.810 | 0.742 | **0.933** | **SURVIVES B3** (p_fw 0.0325) |
| **`pl_dnp_frac5 \| minutes_sqres`** | 0.909 | 0.853 | **1.001** | **SURVIVES B3** (p_fw 0.0085) |

**All four survivors have a `minutes` response.** Not one cell with a **points**-error
response survives the volume base. `pl_pts_sd5|pts_absres` — the cell whose broken null was the
whole of the published family-wise bar — retains **5.6%**. `pts__pred_cv|pts_absres` — the
largest cell in the programme at ΔR² 0.0274 — retains **0.3%**.

**Preregistered predictions.** P-V1 (`pts__pred_cv|pts_absres` retained under B2 < 0.50):
measured **0.012** ✅. P-V2 (≥ 3 minutes candidates retained > 0.50 under B2): 4 of 5 ✅.
P-V3 (≥ 4 of 16 lose family-wise significance under B3): **12** ✅.

---

## 3. The mechanism, and it is worse than "correlated with level"

**POST-HOC.** This measurement was not named in the PREREG. It was forced by a singular matrix
in `s03` and belongs to PART V, which was preregistered.

`<target>__pred_cv = <target>__pred_sd / <target>__pred_point` by construction.
On the decision stratum, `_PRED_COLUMN_DEGENERACY.csv`:

| column | distinct values on A4 (n=3,549) | by season |
|---|---:|---|
| `pts__pred_sd` | **2** | **2023: 1, 2024: 1** |
| `minutes__pred_sd` | **2** | **2023: 1, 2024: 1** |
| `fga__pred_sd` | **2** | **2023: 1, 2024: 1** |
| `pts__pred_point` | 3,451 | 1,752 / 1,699 |

**The shipped forecast emits exactly one uncertainty value per season on the decision
stratum.** Therefore, on that stratum,

> **`pts__pred_cv` IS `k(season) / pts__pred_point`.**

Measured, not argued. Within-season correlation of `pred_cv` with `1/pred_point` is
**1.000000** for all three targets on both arms (`_PRED_CV_MECHANISM.csv`), and the identity
residual `pred_cv·pred_point − pred_sd` is **exactly 0.0**. Substituting `1/pts__pred_point`
for `pts__pred_cv` reproduces the cell **to every printed digit** (`_PRED_CV_SUBSTITUTION.csv`):

| dependent | carrier `pts__pred_cv` | carrier `1 / pts__pred_point` |
|---|---|---|
| `pts_absres` | t = −10.000849, ΔR² = 0.027432 | t = **−10.000849**, ΔR² = **0.027432** |
| `pts_sqres` | t = −9.351004, ΔR² = 0.024066 | t = **−9.351004**, ΔR² = **0.024066** |
| `fga_absres` | t = −8.368797, ΔR² = 0.019368 | t = **−8.368797**, ΔR² = **0.019368** |
| `fga_sqres` | t = −8.184151, ΔR² = 0.018539 | t = **−8.184151**, ΔR² = **0.018539** |
| `minutes_sqres` | t = +7.489661, ΔR² = 0.015573 | t = **+7.489661**, ΔR² = **0.015573** |

**Five of the sixteen — including the single largest cell in roughly 1,400 — say: the
reciprocal of the forecast's own point prediction predicts the size of the forecast's own
error.** In plain words: **low-scoring players have smaller absolute errors.** That is
arithmetic, not a finding.

`pl_pts_sd5` is the same story less starkly: its correlation with `pl_pts_mean5` on A4 is
**+0.438**, the mean–variance relation of a count. `pts__pred_width` (q95 − q05) carries one
value on 43.8% of the arm.

---

## 4. What survives, stated at its real size

Four cells, all `minutes`, all trailing-minutes volatility:
`pl_min_sd5`, `pl_min_rng5`, `pl_dnp_frac5` (×2). ΔR² under B3 = **0.0094, 0.0101, 0.0076,
0.0113** on `minutes_absres`/`minutes_sqres`, family-wise p 0.0085–0.0325 against a bar of
4.888 whose Type-I I measured directly under B3 (`TYPEI_CENTRED.csv`: EXCH/CIRCSHIFT
Type-I 0.003–0.034, centred to |mean signed t| ≤ 0.095).

**The honest sentence is: how variable a player's minutes have been predicts how wrong the
minutes forecast will be, after scoring level is accounted for.** That is a plausible,
mechanically sensible, and entirely uninteresting-to-a-market fact about a *minutes* model.
It is not a points result and must never be quoted as one.

---

## 5. What most weakens this document

1. **B3 is a hard base and some of what it removes may be real.** `pl_min_sd5` correlates
   −0.414 with `pl_min_mean5`; a base containing level will absorb part of any genuine
   volatility effect that happens to be level-graded. The retained shares are therefore
   **lower bounds** on the non-level signal, not point estimates of it. Four survivors is the
   pessimistic count; the ΔR²-only count at B3 is eight.
2. **`pl_dnp_frac5|minutes_sqres` retains 1.001 — more than 100%.** Conditioning on level
   makes it slightly *stronger*. That is a suppression effect and it is a reminder that
   "retained share" is not a decomposition of a fixed quantity; the denominators differ.
3. **The bar moves with the base**, from 5.2935 to 4.8881, so B3 is judged against an easier
   bar than B0. That works *against* my conclusion — a harder bar would kill more cells, not
   fewer. I report the direction rather than adjusting.
4. **The `pred_sd` degeneracy is a property of the decision stratum, not of the model
   everywhere.** On A1_FULL `pts__pred_sd` still takes only 3 values (one per season), so the
   finding is not a stratum artefact — but it is a finding about *this* frame's forecast
   columns and I have not traced it back to the producing pipeline. That is out of my write
   scope and is filed in `DEFECTS.md` as F-2 for whoever owns it.
5. **Nothing here retracts `E1_I0050`.** Its statistics are exactly right and I reproduced
   every one. It said explicitly, in its own §5.5, that these ΔR² are on forecast-error
   magnitude and make no betting edge. This document supplies the measurement behind that
   sentence.
