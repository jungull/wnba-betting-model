# E1_I0037 — PREREGISTRATION
## Audit of the programme's analytic MDE80 construction

Written and hashed BEFORE any statistic in this screen was computed.
Date: 2026-08-08. Partition: 2021–2024 exploration only. 2025/26 never opened.

---

## 0. THE CLAIM UNDER TEST

E1_I0035 `DEFECTS.md` D-3 states:

> `MDE80 = 2.802 × null_sd` is computed from the **observed** difference vector, which carries the
> effect. A block sign-flip on a vector with a large mean shift has an inflated null sd, so the
> analytic floor moves with the effect it is supposed to be independent of.
> … player tier-A Brier: analytic 0.00038 vs injection 0.0025 → **anti-conservative 6.6×**.

Two separable assertions:

* **C1 (construction)** — `null_sd` is computed from an effect-carrying vector.
* **C2 (consequence)** — the resulting analytic MDE80 is anti-conservative, by ~6.6× on the
  player cell, and this generalises.

I preregister that these may dissociate. Note that E1_I0035's own `s05` docstring says the
inflation makes the floor **conservative**, while its `DEFECTS.md` D-3 says **anti-conservative**.
Those cannot both be right. Resolving that contradiction is deliverable 1.

---

## 1. PRE-COMMITTED ANALYTIC PREDICTION (recorded before simulating)

Under a block sign-flip null with `nb` blocks of size `m`, per-row noise sd `σ`, planted mean
effect `e`, and `n = nb·m`:

* true no-effect sd of the mean difference: `SE = σ / sqrt(n)`
* sd of the sign-flip draws computed **from the effect-carrying vector**:
  `sd(e) ≈ sqrt(e² / nb + SE²)`

The test rejects when `|mean(d)| ≥ z·sd(e)`. Solving for 80 % power in `u = e/SE` gives

```
u² (1 − z²/nb) − 2·z80·u + (z80² − z²) ≥ 0      z = 1.9600, z80 = 0.8416
```

**Pre-committed predictions, to be confirmed or refuted:**

* **P1.** The true MDE exceeds `2.802 × SE`, i.e. the analytic form IS anti-conservative — so
  D-3's *direction* is right and `s05`'s docstring is wrong. The two effects (inflated `sd`
  raising the quoted floor; inflated critical value raising the true floor) do not cancel; the
  second dominates.
* **P2.** The bias ratio depends on `nb` **only**, to first order — not on `n`, not on `σ`, not on
  the raw effect size. Predicted ratio `true_MDE / (2.802·SE)`:
  `nb = 400 → 1.007`, `nb = 100 → 1.028`, `nb = 20 → 1.167`, `nb = 10 → 1.429`,
  `nb = 5 → 3.14`, `nb = 4 → 15.8`, `nb ≤ 3.85 → ∞` (the test can never reject).
* **P3.** Because the quoted `2.802 × null_sd` uses the **inflated** `sd(e)` rather than `SE`, the
  ratio *as a screen would actually observe it* is
  `true_MDE / (2.802 · sd(e))`, which is SMALLER than the P2 ratio and can fall below 1
  (apparently conservative) when the observed effect is large. **This predicts the team/player
  split E1_I0035 saw**: the team cell had a huge effect (≈9.5 MAE) and looked conservative 2.3×;
  the player cell had a near-zero effect (−0.000148) and looked anti-conservative.
* **P4.** With `nb` in the hundreds — which the tier-A player cell has — P2 gives ~1.01–1.03, **far
  short of 6.6×**. So if 6.6× is real it CANNOT be explained by the effect-carrying `null_sd`
  mechanism alone. I pre-commit to naming the residual mechanism rather than assuming the
  diagnosis. Candidate residuals, ranked before looking: (a) **effective** block count ≪ nominal
  block count under heavy-tailed block sums (Kish `neff = (ΣB²)² / ΣB⁴`); (b) the injection floor
  is itself inflated because `injection_power`'s inner test uses the same effect-carrying null;
  (c) a genuinely non-Gaussian sign-flip null whose 97.5 % quantile / sd ratio departs from 1.96;
  (d) grid coarseness — `floor80` returns the first GRID POINT at which detection ≥ 0.80, not an
  interpolated crossing, so it is biased UP by up to one grid step.

If P1–P4 are contradicted I report the contradiction in VERDICT.md, in the first three sentences.

---

## 2. SCOPE RESOLUTION — HOW THE CALL GRAPH IS RESOLVED (no name-based searching)

Five findings in this programme died to substring matching. Therefore:

1. Every candidate module is parsed with `ast`, not grepped. For each `.py` file under
   `experiments\exploration\`, I extract (i) every `FunctionDef` and (ii) every `Call` node,
   resolving `Attribute` calls back to the module alias bound by the file's `Import` /
   `ImportFrom` nodes.
2. A function is classified **MDE-producing** iff its body multiplies a quantity by a constant in
   the interval [2.0, 3.5] or contains the closed form `(sqrt(T) + z·sqrt(mu))²` — that is, by
   what it *computes*, not what it is called.
3. A call site is **affected** iff it passes an sd that is traceable to a null run on an
   **observed** loss/difference vector.
4. The resolved list, and the count, are printed and asserted. Any file that fails to parse is
   reported as UNRESOLVED, never silently skipped.

Pre-committed: I will state the total number of `.py` files parsed, the number of MDE-producing
functions found, and the number of call sites resolved. If any number is zero I say so.

---

## 3. SIMULATION DESIGN (pre-committed grid, fixed before running)

Synthetic paired loss-difference vectors. Nothing real is required; the real cells are used only
as a **reproduction anchor**, not as evidence.

Factors (full factorial):

| factor | levels |
|---|---|
| `nb` (blocks) | 4, 8, 16, 32, 64, 128, 256, 512 |
| `m` (rows per block) | 4, 16, 64 |
| per-row noise dist | `gauss`, `t3` (heavy-tailed), `brier` (squared-error-difference-like: skewed, sparse) |
| within-block ICC | 0.0, 0.3, 0.7 |
| planted effect | located by bisection; 7 fixed multiples of SE also swept for the power curve |

Response variance `σ` is held at 1.0 and rescaled; the design tests **P2's claim that σ does not
matter** by including a `σ = 25` arm on a subset.

For each condition I compute FOUR quantities:

* **A_obs** = `2.802 × sd` where `sd` is the sign-flip sd of the **observed** effect-carrying
  vector — the programme's construction as actually used.
* **A_null** = `2.802 × sd0` where `sd0` is the sign-flip sd of a **genuine no-effect** vector —
  the corrected construction.
* **E_inj** = the empirical 80 %-power point found by injection, using the programme's own test
  (the effect-carrying inner null) — i.e. what `floor80` measures.
* **E_true** = the empirical 80 %-power point found by injection using a test whose critical value
  comes from a **pre-computed no-effect null** — i.e. what the floor SHOULD be if the test were
  fixed as well as the formula.

Reported ratios: `E_inj/A_obs` (the D-3 comparison), `E_true/A_null` (is the corrected form
calibrated?), `E_inj/E_true` (how much of the gap is the test rather than the formula),
`A_obs/A_null` (the inflation itself).

**Bisection, not a grid.** `floor80` in `av_base` returns the first grid point clearing 0.80,
which is biased upward. I use bisection on the planted effect to 2 % relative tolerance, and I
ALSO report the grid-point version so the grid-coarseness contribution is separable (P4d).

Replication: 400 injection replicates per evaluation, 2,000 sign-flip draws per replicate,
seeds derived from a single declared root seed 20260808.

---

## 4. MY OWN MACHINERY MUST BE VERIFIED — PRE-COMMITTED SELF-CHECKS

E1_I0035's first injection check measured nothing and its first Type-I check returned p ≡ 1.0.
I assume mine are broken until proven otherwise. Before any ratio is reported:

* **S1 — Type-I rate.** Every test construction I use is run at planted effect exactly 0 over
  ≥ 2,000 replicates. Pre-committed acceptance band at nominal 0.05 and R = 2000:
  0.0404–0.0596 (± 3 SE). **A rate of exactly 0.0000, or exactly 1.0000, or a p-value quartile
  vector of (1.000, 1.000, 1.000), is declared a DEGENERATE CHECK and the arm is discarded, not
  reported.** The Type-I rate of every check is printed in VERDICT.md whether or not it passes.
* **S2 — discrimination.** The detection rate must be strictly monotone increasing in the planted
  effect and must span < 0.15 to > 0.90 across the swept grid. A flat curve (E1_I0035's D-1
  failure mode) fails S2 and the arm is discarded.
* **S3 — degenerate-plant guard.** I assert that the planted vector's per-row differences are NOT
  constant: `sd(d) / |mean(d)| > 0.1`. This is the exact assertion that would have caught
  E1_I0035's D-1 at the moment it happened.
* **S4 — analytic recovery.** In the large-`nb` limit (`nb = 512`, gauss, ICC 0) the corrected
  construction must recover `E_true / A_null ∈ [0.95, 1.05]`. If it does not, my simulator is
  wrong, not the programme.

## 5. REPRODUCTION ANCHOR (declared before computing)

Before generating any new statistic I reproduce, exactly, from
`E1_I0026_detection_floor\out\retrospective_power.csv`:

* total unique cells = **1349**
* cells blind to 0.0023 family-wise = **760**
* share = **0.5633802816901409**

If any of these three fails to reproduce to the digit, this screen stops and reports that instead.

## 6. WHAT WOULD REFUTE THE CLAIM

* C1 refuted if the sd fed to the MDE formula is traceable to a permuted/null-resampled quantity
  rather than an observed one, at every affected call site.
* C2 refuted if `E_true / A_null ≈ 1` **and** `E_inj / A_obs ≈ 1` across the grid — i.e. the
  construction is calibrated and the 6.6× was a property of one cell.
* The **generality** of C2 is refuted if the median `E_inj/A_obs` across the grid is within
  [0.8, 1.25] and 6.6× sits beyond the 95th percentile.

I commit to reporting whichever of these obtains.

## 6b. ADDENDUM — added before hashing, before any computation

The coordinator reports E1_I0036 found a Severity-A defect in D108's injection protocol: planting
onto **shuffled residuals** destroys response structure the null fails to destroy in the carrier,
so an injection check can certify a null that is blind to the real candidate (N_CYCLIC: injection
power 0.95, real power 0.00). My brief told me to verify my own machinery by that protocol. So:

* **S5 — my own machinery must not depend on the defective construction.** My simulator is
  fully synthetic: I know the data-generating process, so I can draw **fresh component-wise
  noise** each replicate rather than resampling one fixed residual vector. I pre-commit to
  running every injection arm **twice**:
  * **arm FRESH** — new noise drawn from the declared DGP each replicate (component-wise; the
    amended protocol),
  * **arm FLIP** — one fixed noise vector resampled by block sign-flip (E1_I0035's construction,
    the one now under suspicion).
  Both are reported. If they disagree by more than 10 % on any headline ratio, **the FRESH arm is
  the authority and the disagreement is the finding**.
* **S6 — the `null_mean > observed` diagnostic** is computed for every null I construct and added
  to the census as a column wherever the recorded data supports it. I pre-record the expectation
  that for a **paired block sign-flip null this diagnostic is structurally vacuous**, because the
  draws are `±` a fixed set of block sums and therefore have expectation exactly 0 by
  construction — it cannot fire on the family I am auditing. If that is so I report it as a
  **gap in the diagnostic's coverage**, not as a clean bill of health, and say which cells it
  can and cannot police.

I am not auditing the 550 exposed cells and not implementing the amended protocol for the
programme; E1_I0038 has that. I report only where my results bear on it.

## 7. HARD LIMITS

* No file outside `experiments\exploration\E1_I0037_mde_audit\` is written, staged or committed.
* The shared kit is **not modified**. The fix is written to `PROPOSED_FIX\` only.
* No `git` write command is run. No process not launched by me is killed.
* D103's numbers are not revised here. A correction factor plus evidence is produced; the
  coordinator rules.
