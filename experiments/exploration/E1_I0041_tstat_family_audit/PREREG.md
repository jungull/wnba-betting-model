# PREREG — E1_I0041, audit of D103's `t_statistic` scale conversion

Written and hashed **before** any simulation is run. Steps s01 (anchor + call graph) and s02
(read-only structural probe) had already run at the time of writing and are **descriptive
confirmations of source facts, not tests**; every number they produced is quoted here so that
nothing in this document can be back-fitted to a simulation result. The simulation in s03 and the
restatement in s04–s05 are the pre-registered part.

Partition: **2021–2024 exploration artefacts only.** Nothing under 2025/26 is opened. No real
response is re-modelled; the only real quantities used are already-published null draws and
already-published summary columns.

Write scope: `experiments/exploration/E1_I0041_tstat_family_audit/` only. The shared screen kit is
not touched.

---

## 0. The anchor, reproduced before anything else (s01, already run)

From `E1_I0026_detection_floor/out/retrospective_power.csv`, keyed exactly as E1_I0037 keyed it
(`screen, decision, family_size_K, cell`, worst null arm, blind iff `mde80_fw > 0.0023`):

* unique cells **1349**
* blind **760**
* share **0.5633802816901409** — identical to the published value at all 16 digits.

Family split, asserted not eyeballed: `increment` 653 / 218 blind, `paired` 30 / 24, **`t_statistic`
666 / 518**. Within `t_statistic`: **E0_I0014 348 cells / 203 blind**, **E0_I0019 318 cells /
315 blind**.

---

## 1. What the conversion is, and the four candidate defects

`E1_I0026_detection_floor/scripts/s06_retrospective.py:66-77`

```python
def mde80_tscale(sd_null_t, t_crit, n):
    return float(((t_crit + Z80) * sd_null_t) ** 2 / n)
```

Called at exactly four sites (AST-resolved, s01 §B: lines 167, 168, 201, 202 of that one file;
nowhere else in 1,104 `.py` files, 20 of which are unparsable BOM files and are named in
`run_log_s01.txt`).

Its derivation assumes, in order: (a) ΔR² = t²/(t²+df) ≈ t²/n; (b) planting δ shifts the
statistic by √(δn); (c) the statistic is **signed** and its null mean cancels between threshold and
shift; (d) the null is close enough to normal that "mean + `t_crit` sds" is the right
(1−α) family-wise quantile; (e) `t_crit` is a valid multiplier of a **t-scale** null sd.

| id | candidate defect | which cells | direction if real |
|---|---|---|---|
| **C1** | `sd_null_t` for E0_I0014 is `null_correct_sd` = sd(**\|t\|**), a FOLDED variable, not sd(t). `s04_screen.py:211` stores `v = np.abs(tvec(...)[1])`; all 18 saved null arrays have `frac_negative = 0.0000` and `min = 0.0` (s01 §D). Assumption (c) is violated. | 348 (E0_I0014 only) | sd(\|t\|) < sd(t) ⇒ floor **too low** ⇒ **anti-conservative**, cells wrongly counted powered |
| **C2** | `t_crit` is `q95` of the max of a **standardised ΔR²** statistic over K cells, taken from D089's null matrix (`s04_power.py:70-72`). It is applied as a multiplier of a **t-scale** sd. A right-skewed squared statistic's standardised quantile is not a signed statistic's. Assumption (e). | 666 | unknown a priori — measure it |
| **C3** | Both screens' actual family-wise rule is an **unstandardised** max\|t\| bar (`E0_I0014 s04_screen.py:238`, `E0_I0019 s04_screen.py:184`), q95 = **29.13** and **8.68** on their own saved draws. D103 substitutes a standardised bar. Assumption (d)+(e). | 666 | unknown a priori — measure it |
| **C4** | Cells whose permutation null is **degenerate** (the shuffle barely moves the statistic, so the null \|t\| is a tight cloud far from 0) get a tiny `sd_null_t` and therefore a tiny MDE — they are recorded as the *best*-powered cells when their null is not a null at all. E0_I0019 flags this concept explicitly (`s05:56-58`, criterion \|mean\|/sd > 5); E0_I0014 publishes no such flag. | unknown | floor **too low** ⇒ **anti-conservative** |

**Already refuted before the simulation, and recorded as such:** assumption (a) holds on the real
cells. On E0_I0014's 330 cells with both `t_classical` and `delta_r2_plain_unweighted` finite and
positive, `(t²/n)/ΔR²_published` has median **1.0034** (p10 0.9997, p90 1.0484); with the exact
form `t²/(t²+df)`, `df = n−4`, the median ratio is **1.0000**. The scale identity is **sound** and
is not a defect. This is the single most likely way for this screen to have been wrong and it is
not wrong.

**Also confirmed sound before the simulation:** E0_I0019 stores **signed** t
(`s04_screen.py:181`; `frac_negative` 0.14–0.50 across schemes), so **C1 does not apply to its 318
cells**. No `mde80_fw` is NaN in either screen (0 of 348, 0 of 318), and the one all-NaN null array
(`null_teamseason_between`) is never a primary scheme, so there is no silent-NaN defect.

---

## 2. The gate — what is claimed and what will be checked

E1_I0037 asserted that `validate()` never exercises the `t_statistic` path. s01 §C confirms it at
source: `validate()` reads `out/s04_mde_table.csv` (216 rows), which has **no `stat_family`
column** and contains only the six simulated nulls of `s04_power.py`, whose statistic is
`dR2 = (a*a/b)/sst` (`s04_power.py:118`) — never a t. `validate()` calls only `mde80_increment`.
The AST sweep found **no other call site of `mde80_tscale` and no other validation of it anywhere
in the worktree**. This is a coverage gap in the gate, not a case of validation living elsewhere.

Pre-registered residual risk: 20 files failed to parse (all `U+FEFF` BOM), one of which
(`E1_I0026_detection_floor/scripts/s06b_ns.py`) is a D103 script. **s03 will read that file
literally and record whether it validates anything.** If it does, C1–C4 must be re-scoped.

---

## 3. THE SIMULATION — design, fixed in advance

### 3.1 Generating process (matches this programme's actual structure)

Synthetic panel, no real data:

* `P` player blocks per season, `S = 4` seasons (2021–2024 shape), games per player drawn
  **unbalanced** from a right-skewed distribution (`1 + Poisson(λ)` clipped to [5, 44]), so block
  lengths differ — which is what makes `block_index`'s cycling (`rh_base.py:398-409`) bite.
* Response `y = α_player + γ_teamgame + ε`, with `ε` **AR(1)** within player at ρ ∈ {0.0, 0.5},
  then demeaned **within season** (the FWL construction both screens use).
* Carrier `x = √w · b_block + √(1−w) · u_row`, `w` = target between-block variance share ∈
  {0.10, 0.50, 0.80, 1.00}; the real screens' observed range is 0.00–1.00, median 0.80.
* Statistic: the screens' own classical FWL slope t (`rh_base.py:357-370`), `df = n − 4`.
* Null: **between-block reassignment**, a literal re-implementation of `rh_base.block_index`
  (permute block order within season; gather donor rows cycling modulo donor length).

### 3.2 Effect planting and the D101 contrast declaration

**Every floor in this screen is quoted on one and only one contrast, stated here:**
> ΔR² of the season-demeaned response `ỹ` on the season-demeaned carrier `x̃`, over the full
> simulated row set, unweighted, with SST = `ỹ·ỹ` of the **effect-free** response, single added
> regressor, base = season fixed effects only.

Effect planted exactly as `s04_power.py:11` does it: `y(δ) = y + c·x̃_real`,
`c = √(δ·SST₀/(x̃_real·x̃_real))`. All three floors below are computed from the same draws, the
same rows, the same SST basis and the same base. Any floor that cannot be put on this contrast is
not reported as a ratio.

Closed form asserted against a literal recompute before the sweep runs (tolerance 1e-10), the same
guard `s04_power.py:175-189` uses.

### 3.3 The three floors compared

| symbol | definition | contrast |
|---|---|---|
| `E_inj` | injection-verified: the δ at which measured rejection rate first crosses 0.80, log-linearly interpolated exactly as `s04_power.py:146-161` | as §3.2 |
| `A_pub_folded` | `((t_crit + z₈₀)·sd(\|t\|))²/n` — **E0_I0014's actual published form** | as §3.2 |
| `A_pub_signed` | `((t_crit + z₈₀)·sd(t))²/n` — **E0_I0019's actual published form** | as §3.2 |
| `A_cor` | `(q + z₈₀·sd(t))²/n`, `q` = the empirical (1−α) quantile of the null's own \|t\| at the same α the threshold represents | as §3.2 |

Two threshold regimes, both reported: **per-cell** (α = 0.05 two-sided) and **family-wise**
(K = 348 / 318, max\|t\| over K independent cells).

### 3.4 Machinery checks — pre-committed, reported whether they pass or fail

* **S1 (Type-I).** At δ = 0, rejection under the null's own empirical q95(|t|) must be
  **0.05 ± 0.02**. Three sibling screens have shipped degenerate power checks; I assume mine is
  broken until this passes. If it fails in any condition, the defective output is **preserved**
  under a `_DEFECTIVE` name and the cause is diagnosed in `DEFECTS.md` before anything is reported.
* **S2 (non-degeneracy).** Power must be monotone in δ and must reach ≥ 0.99 at the top of the
  grid in at least 80 % of conditions. A condition with detection 1.000 everywhere, or 0.000
  everywhere, is a defect, not a result.
* **S3 (fold recovery).** In simulation both signed and folded draws are available, so
  `sd(t) = √(sd(|t|)² + mean(|t|)²)` — exact iff `E[t] = 0` — is checked against the true signed
  sd. Median relative error must be < 1 % where the null is symmetric. **This validates the
  recovery I will apply to E0_I0014's real cells, where only folded draws survive.**
* **S4 (closed form).** |closed-form ΔR²(δ) − literal recompute| < 1e-10 over 75 spot checks.
* **S5 (does the effect contaminate the null?).** The permutation null's sd is re-measured at each
  δ. E1_I0037's two structural gates were derived for a sign-flip null whose sd carries the effect.
  If the permutation null's sd is flat in δ, **both gates are inapplicable to this family and I
  will say so**; if it moves, the gates must be re-derived for it.

### 3.5 Pre-registered predictions (falsifiable, with the outcome that would refute me)

* **P1** `A_cor / E_inj` median ∈ [0.85, 1.20]. *Refuted if outside.*
* **P2** `A_pub_folded / E_inj` median ≈ 0.36 (= 1/2.75, the half-normal fold factor squared) in
  the per-cell regime, i.e. **anti-conservative**. *Refuted if the median is ≥ 0.85.*
* **P3** `A_pub_signed / E_inj` median ∈ [0.85, 1.20] in the regime where `t_crit·sd(t)` happens to
  land near the true family-wise bar — i.e. **E0_I0019's conversion is sound**. *Refuted if not.*
* **P4** The ratios depend on the **fold factor and the threshold scale only**, not on `n`, ρ, or
  block-length imbalance, which enter solely through the measured sd. *Refuted if `n` or ρ arms
  disagree by more than 10 % at matched fold factor.*
* **P5 — the outcome that would clear the conversion.** If both `A_pub_folded/E_inj` and
  `A_pub_signed/E_inj` have medians in [0.85, 1.20] across the whole grid, **the conversion is
  sound, 68 % of the programme's blind verdicts rest on solid ground, and that is the verdict I
  report.** This is a real possible outcome and it is stated before the run.

No condition may be dropped after the fact. `SIMULATION.csv` carries every condition attempted,
including failures, with a status column.

---

## 4. Restating D103 (s04–s05)

Two corrections will be computed and reported **separately**, never blended:

* **R-A (fold only, E0_I0014's 348 cells).** Replace sd(|t|) with the exactly-recovered sd(t),
  keep D103's own `t_crit`, keep everything else. Recovery validated by S3.
* **R-B (screen's own family-wise bar, all 666 cells).** Replace the borrowed standardised
  `t_crit·sd` threshold with each screen's **own** published family-wise max|t| q95 — 29.13 for
  E0_I0014 (`maxt_null_draws_whole_screen.csv`), 8.68 for E0_I0019 (`maxt_null_draws.csv`). This
  is the bar the screen actually applied to declare its own verdicts.

For each, the corrected blind count over all 1,349 cells at the unchanged 0.0023 benchmark, using
D103's own key and its own comparison. **I do not revise D103.** I produce the corrected figure
and the evidence; the coordinator rules.

**Standing D101 caveat, to be restated in the verdict rather than buried:** D103 compares every
cell's MDE, expressed as ΔR² **of that cell's own response**, against 0.0023, a ΔR² on D089's
walk-forward points. E0_I0014's responses are |residual| and squared residual of minutes/points/FGA;
E0_I0019's are Brier-skill differences. These are different SST bases. That is D103's own design
choice and it applies to all three families equally, so it does not affect the *relative*
correction — but it is a cross-response comparison and E1_I0037 did not raise it.

---

## 5. Structural gates (s04)

E1_I0037's two gates are **derived for a two-sided sign-flip null on an effect-carrying paired
loss difference**. The `t_statistic` family is on **permutation-of-carrier** nulls. I will report,
for all 666 cells:

* count with fewer than six permutation blocks;
* count with `t_crit ≥ √nb`;

and, in the same table, **whether each gate's derivation is applicable to a permutation null** —
decided by S5's measurement, not by assertion. If they do not apply, the count is reported as
zero-by-construction with the reason, and the applicable analogue (null resolution `1/(R+1)`;
degenerate-null count from C4) is reported instead. Reporting an inapplicable gate's count as if it
were a finding would be a name-based, not a mechanism-based, result.

---

## 6. Standard held

A proposed fix, if any, will be measured against the incumbent in every regime, and if it is worse
anywhere that will be reported and the fix will not be recommended. It will not be applied to the
shared kit. "The conversion is sound" is an acceptable and useful outcome (P5). The result that
most weakens this screen's own conclusion will appear in `VERDICT.md`, not only in `DEFECTS.md`.

Seeds: base seed **20410807**; the null-calibration pass and the power-replicate pass use
**different** seeds (`+0` and `+101`), as `s04_power.py` does, so replicates are never standardised
by their own draws.
