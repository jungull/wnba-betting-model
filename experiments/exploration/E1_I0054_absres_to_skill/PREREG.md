# PREREG — E1_I0054 · absolute residual → skill, or variance?

**Written and hashed before any statistic in this screen was computed.**
Anything added after the hash is marked `POST-HOC` in the body of every document that uses it.

---

## 0. THE QUESTION

`E1_I0050` reports that, with one structurally broken cell removed and a repaired conservative
null, **16 of 17 family-wise-significant cells survive on the 2023–24 decision stratum, ΔR²
0.0082–0.0274**. The response in every one of those cells is a **forecast-error magnitude**
(`|residual|` or `residual²`), not points.

This screen asks three separable things and refuses to merge them:

1. **R** — do the sixteen reproduce, independently, from source artifacts?
2. **S** — does forecasting `|residual|` improve a forecast of **POINTS**?
3. **C** — if not, what is the conditional-variance forecast worth **on its own terms**?

and one that must be excluded before any of the above is claimed:

4. **V** — how much of the association is just *"this player scores more"*?

---

## 1. PARTITION AND SCOPE GUARD

* Seasons **2021–2024 only**. `2025/26` is a **sealed confirmation holdout and is never opened**.
  Asserted in `_common.py` on `season` and on `gdate` and re-asserted by every caller.
* The source frame (`E0_I0014_residual_heterogeneity/analysis_frame.parquet`) contains
  **2022, 2023, 2024 only** (4,362 / 4,748 / 4,769). There is no 2021 in it, so the
  standing "2021 is degenerate" hazard cannot arise here; it is recorded, not relied on.
* Manifests: `row` / `season` usable, `artifact` **NOT**. MISSING = UNVERIFIABLE.
* **Write scope**: `experiments/exploration/E1_I0054_absres_to_skill/` only. No `git` write
  command is issued. The shared screen kit and every production file are read-only inputs.
* **Process isolation**: no blanket kill of any kind. Only PIDs this screen launches and records
  in `scripts/_pid_*.txt` may be signalled, and none is expected to need it.

---

## 2. ARMS (D101 — nothing is ever compared across arms)

| arm | rows | seasons | n | blocks |
|---|---|---|---|---|
| **A4_CLEAN_DEC** — **reported first** | `pl_games_prior>=8 & pl_min_mean5>=24` | 2023–24 | 3,549 | 174 player-season |
| A1_FULL — like-for-like with the published cell only | all | 2022–24 | 13,879 | 475 player-season |

The decision stratum is the standing programme predicate. Every headline in this screen is on
**A4_CLEAN_DEC**. A1_FULL exists to anchor the reproduction against the arm the published
verdict was formed on and is never differenced against A4.

---

## 3. PART R — REPRODUCTION (runs first; if it fails, that is the headline and the screen stops)

Independent re-implementation from **source artifacts**, not from `E1_I0050`'s tables:
`analysis_frame.parquet` and `screen_results.csv` (E0_I0014's own outputs). `E1_I0050`'s and
`E1_I0044`'s scripts are **read** for specification and **never executed or imported**.

**Anchors, in order. Each must pass before the next statistic is computed.**

| id | anchor | tolerance |
|---|---|---|
| R-A1 | my `t_classical` for all **348** cells on the full 13,879 rows vs `E0_I0014/screen_results.csv` | max abs rel. diff **< 1e-9** |
| R-A2 | my `delta_r2_plain_unweighted` for all 348 cells vs the same file | max abs diff **< 1e-12** |
| R-A3 | my A4 observed signed `t` and ΔR² for the 54 queue cells vs `E1_I0050/CORRECTED_VERDICTS.csv` | max abs diff **< 1e-9** |

**R-B — the null, rebuilt.** Composed-2 as specified in `E1_I0044/scripts/s07_remeasure_v2.py`
(receiving block filled by a uniform **resample of the whole donor block**; one shared gather
index per draw across all 58 candidates; PLAYER-scheme candidates on player-season blocks,
TEAM-scheme on team-season blocks). `R = 2000`. Family-wise bar = 95th percentile of
`max|t|` over the **348**-cell family. `p = (k+1)/(R+1)`.

**Seeds.** `SEED_MAIN = 20260808` (E1_I0044's, to allow an exact-path comparison) **plus two
independent seeds 20260809, 20260810**. The re-implementation consumes the RNG in its own order,
so an exact draw-for-draw match is **not** predicted; agreement is required on the **verdict set**.

**Verdict rule, copied verbatim from `E1_I0050/scripts/s04_verdicts.py` and applied numerically:**
a cell is `FAMILYWISE_SIGNIFICANT` iff `p_familywise_plus1 < 0.05` **and** its composed-2 null
validity (carried over from `E1_I0050/TYPEI_PER_CELL.csv`, which this screen does not re-measure
for all 54) starts with `ACCEPTABLE`. **No name-based selection anywhere**: the set is formed by
numeric predicate on the table, never by substring.

**Preregistered predictions**
* **P-R1**: the A4 `FAMILYWISE_SIGNIFICANT` set has **cardinality 16** at `SEED_MAIN`.
* **P-R2**: across the three seeds the set varies by **at most 2 cells** (symmetric difference).
* **P-R3**: the composed-2 family-wise bar q95 on A4 is within **±0.30** of the published 5.323.

**R-C — single-cell dominance of the bar (mandatory, was never looked at before).** For each of
the 2,000 draws record **which cell supplied `max|t|`**. Report the top cell's share and the
number of distinct cells that ever supply it. Reported for the composed-2 bar **and** for
E0_I0014's published bar rebuilt from `permutation_nulls.npz`.

---

## 4. PART V — THE DEGENERATE EXPLANATION (volume proxy), run BEFORE any skill claim

`|residual|` is mechanically related to the level of the response. The published base is **season
fixed effects and nothing else**. This part puts trailing level in the base **from the start** and
reports the increment over that base, not over nothing.

**Bases** (all include season fixed effects; all on the arm's own rows; SST = season-demeaned
response, unweighted):

| id | base |
|---|---|
| **B0** | season FE only — *the published base* |
| **B1** | B0 + **matched trailing level**: `pl_pts_mean5` for `pts_*`, `pl_min_mean5` for `minutes_*`, `pl_fga_mean5` for `fga_*` |
| **B2** | B1 + **matched forecast level**: `pts__pred_point` / `minutes__pred_point` / `fga__pred_point` |
| **B3** | B0 + **all eight level columns**, identical for every cell: `pl_pts_mean5, pl_min_mean5, pl_fga_mean5, pl_usg_mean5, pl_start_frac5, pts__pred_point, minutes__pred_point, fga__pred_point` — a mapping-free control for B1/B2, since B1/B2 use a response→column mapping and B3 does not |

For every base: recompute signed `t`, ΔR², a **fresh composed-2 null over the same 348-cell
family under that base** (R = 2000, `SEED_MAIN`), the bar, and `p_familywise_plus1`.
`retained_share = ΔR²(Bk) / ΔR²(B0)`.

**Preregistered predictions**
* **P-V1**: for `pts__pred_cv|pts_absres` (the largest cell, ΔR² 0.0274) `retained_share` under
  **B2 < 0.50**.
* **P-V2**: for the five `minutes_*` volatility candidates `retained_share` under **B2 > 0.50**
  on at least 3 of them.
* **P-V3**: at least **4** of the 16 lose family-wise significance under B3.

**A cell whose ΔR² does not survive B3 is reported as a volume proxy in plain words.**

---

## 5. PART C — WHAT THE VARIANCE FORECAST IS WORTH (run even if PART S is null)

**Out-of-fold construction, two independent schemes, both reported:**

* **WF** (primary) — expanding window ordered by `gdate`: fit on all A4 rows strictly earlier than
  the scored date, refit at every distinct date, minimum training rows **600**; rows before that
  are unscored.
* **GKF** (secondary) — 5-fold `GroupKFold` on `player_id` (no player appears in both sides).

**Variance models** (response = `absres_*` of that target; fitted by OLS with an intercept):

| id | features |
|---|---|
| **V0** | intercept only (constant) — the no-signal reference |
| **VSD** | the model's own emitted uncertainty `<target>__pred_sd` — **the incumbent** |
| **VSIG** | the family-wise-significant candidates for that target from PART R |
| **VALL** | all 58 candidates (a ridge with λ tuned on the training window, grid `10^{-3..3}`) |
| **VLEV** | matched trailing level alone (`pl_pts_mean5` etc.) — the volume-proxy reference |

**Metrics, per target ∈ {pts, minutes, fga} × scheme × model**, all on out-of-fold `v̂`:
decile reliability table (mean `v̂`, mean realised `absres`, n, per decile), top-vs-bottom decile
**spread** and **ratio**, Spearman ρ(`v̂`, realised `absres`), calibration slope and intercept from
`absres ~ 1 + v̂`, out-of-fold R² of `v̂` on `absres`, and mean |realised − v̂|.
Uncertainty: block bootstrap over the 174 player-season blocks, 2,000 resamples, percentile CI.

**Preregistered predictions**
* **P-C1**: `VSIG` top-decile mean realised `absres` exceeds bottom-decile by a factor **> 1.6**
  on `minutes`.
* **P-C2**: `VSIG` beats `V0` on out-of-fold R² for all three targets.
* **P-C3**: `VSIG` does **not** beat `VSD` by more than 0.02 out-of-fold R² on `pts`.

---

## 6. PART S — THE CENTRAL TEST: DOES IT MOVE **POINTS**?

**D101 block, fixed here and repeated on every number in `SKILL_OR_VARIANCE.md`:**

| | |
|---|---|
| response | **`y_pts` — total box points** |
| row set | A4_CLEAN_DEC **scored** rows (WF scheme drops the warm-up; exact n reported) |
| SST basis | `Σ(y_pts − ȳ)²` over the scored rows, about the **unweighted** mean |
| weighting | none in the metric (weighting appears only inside a channel's fit) |
| base | `B_PTS = [1, pts__pred_point, minutes__pred_point, pl_pts_mean5, pl_min_mean5, pl_fga_mean5, pl_usg_mean5, pl_start_frac5]` |
| fit kind | out-of-fold (WF primary, GKF secondary) |
| statistic | **paired** ΔR² = `(SSE_ref − SSE_treat)/SST` |
| reference | **tuned**: ridge on `B_PTS`, λ chosen by inner time-ordered CV on the training window over `10^{-4..4}` (13 points) |

**Channels** (each is a *use of the predicted error*, and each is preregistered here):

| id | channel |
|---|---|
| **S1** | **variance-weighted fitting** — same base, WLS with weights `1/max(v̂,c)^p`, `p ∈ {1,2}`, `c` = 10th pct of `v̂` on the training window |
| **S2** | **shrinkage proportional to predicted error** — `ŷ = ȳ_tr + κ(ŷ_ref − ȳ_tr)`, `κ = 1/(1+θ·(v̂/med_tr(v̂) − 1))`, θ tuned on the training window over `{0,0.05,…,1.0}` |
| **S3** | **mean augmentation** — base + `v̂`, and base + `v̂` + `v̂ × pts__pred_point` |
| **S4** | **two-stage mean/variance** — fit mean, fit variance on that mean's residuals, GLS refit of mean, one iteration |
| **S5** | **abstention** — drop the top `q ∈ {10,20,30}%` of rows by `v̂`. Reported as **loss reduction on retained rows**, against (a) the reference on the *same* retained rows and (b) the reference on 2,000 *random* subsets of equal size. **S5 is explicitly NOT a ΔR² skill claim** and is scored on MSE only. |

**Intercept.** Every channel is run **FROZEN** (the treatment inherits the reference's intercept;
no re-centring is permitted) and **UNFROZEN** (refit). **Both arms are reported for every channel.**

**Inference.** Cluster **sign-flip** on the paired per-row squared-error difference, at
**player-season** (174 clusters; primary) and at **team-season** (secondary). R = 5,000,
`p = (k+1)/(R+1)`, two-sided. Signed statistics and raw unstandardised draws with full stratum
keys are stored in `raw/*.npz`.

**Decision rule (preregistered, not revisable):** a channel **improves points** iff
`ΔR² > 0` **AND** cluster `p < 0.05` **AND** `ΔR² ≥ 0.00072`, the **points-scale** single-cell
detection floor from `E1_I0049/REFERENCE_CARD.md` §"THE RESPONSE MISMATCH, MEASURED"
(0.00102 on `y_ppm` × 0.704). All three quantities are reported for every channel whatever the
outcome. The K=132 points-scale figure 0.00181 is reported alongside as a family-scale reference.
**The published `y_ppm` floors 0.00102 / 0.00235 are never quoted against a points statistic.**

**Preregistered predictions**
* **P-S1**: **no channel** meets the decision rule. (This screen expects a variance model.)
* **P-S2**: S3's coefficient on `v̂` is not distinguishable from 0 at cluster `p < 0.05`.
* **P-S3**: S5 reduces MSE on retained rows relative to matched random subsets by **> 15%** at
  `q = 30%` — i.e. the abstention channel *works*, and it is a variance result, not a skill one.

---

## 7. PART T — CONTROLS

**T1 — the Type-I control must be CENTRED.** Effect-free responses are generated by
**EXCH** (block means reassigned within season; within-block deviations permuted within block) and
**CIRCSHIFT** (block means reassigned; deviations circularly rolled). Both leave the response
independent of any candidate conditional on the block structure.
**Requirement: mean SIGNED observed `t` over the B synthetic datasets satisfies `|mean| < 0.15` on
every cell tested.** Any cell failing this has its generator declared defective and its Type-I
number is reported as `UNVERIFIABLE`, exactly as `E1_I0050` F-2 requires. `B = 1000`.
The generator that transplants absolute within-block position (`BLOCKBOOT`) is run **only** as a
labelled diagnostic and **never** as an H0 generator.

**T2 — a Type-I control for the PART S statistic**, which is a different statistic and is not
covered by T1. A **placebo variance forecast** `v̂_placebo` is built by running the identical
PART C pipeline on a **composed-2 block-permuted candidate matrix**, then pushed through every
PART S channel. `B = 300` replicates. Report the rejection rate at 0.05 and the **mean signed
ΔR²**, which must satisfy `|mean| < 2e-4`.

**T3 — a blindness audit, which T1/T2 do not subsume.** For every cell and every null used, report
the null's **mean signed `t` on the real response**. A null whose `|mean signed t| > 0.20`
(`E1_I0044`'s functioning threshold) is declared **BLIND** and its p is void regardless of its
Type-I. Both instruments are run on everything.

**T4 — family-wise bar dominance** (see R-C). Any family-wise bar reported anywhere in this screen
carries the share of draws supplied by its single most frequent cell.

---

## 8. WHAT WOULD MAKE ME RETRACT

* R-A1/R-A2/R-A3 fail → `REPRODUCTION.md` is the headline and nothing else is claimed.
* The 16 do not reproduce within P-R2 → same.
* A PART S channel meets the decision rule but its T2 placebo rate exceeds 0.10 → the channel is
  reported as **UNVERIFIABLE**, not as a positive.
* A cell's ΔR² vanishes under B3 → it is reported as a **volume proxy**, in those words.
* If PART S is null I will write "**it is a variance model and does not improve points**" in the
  first three sentences of `SKILL_OR_VARIANCE.md` and will not soften it.

**I will not fit a champion. I will not enact a production change. I will report the result that
most weakens my own conclusion in the same document.**

---

## 9. FIXED CONSTANTS

```
R_NULL_COMPOSED2 = 2000
SEEDS            = [20260808, 20260809, 20260810]
R_SIGNFLIP       = 5000
B_TYPEI          = 1000        (PART T1)
B_PLACEBO        = 300         (PART T2)
N_BOOT           = 2000        (PART C block bootstrap)
TOL_TYPEI        = 0.075       (inherited from E1_I0050 PREREG §4)
TOL_BLIND        = 0.20        (inherited from E1_I0044's functioning test)
Z80              = 0.8416212335729143
FLOOR_POINTS_K1  = 0.00072     (E1_I0049 REFERENCE_CARD, points-scale)
FLOOR_POINTS_K132= 0.00181     (E1_I0049 REFERENCE_CARD, points-scale)
```

Thresholds, seeds, draw counts and sample sizes above are **not revised after seeing a result**.
