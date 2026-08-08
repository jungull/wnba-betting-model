# DEFECTS — defects in E1_I0037's own work

Self-reported. Five found, four by me during the run and corrected, one standing. Worst first.

---

## D-1 — MY SIMULATOR'S FIRST RUN WAS DEGENERATE, IN E1_I0035's D-2 WAY. Corrected.

**Severity: would have invalidated everything.** `draw_noise` ended with

```python
z = z - z.mean()          # centre the realisation
```

The statistic under test **is** the mean of the difference vector. Centring every realisation made
it identically zero, so `|draws| >= |real| = 0` held for every draw, `p = 1.0000` always, and
`se_true` was exactly 0 — which then made every planted effect `u * se_true = 0`. Result: **Type-I
rate 0.0000 and power 0.000 at every effect size in all 648 FRESH conditions.** This is E1_I0035's
D-2 degeneracy, committed inside the audit of it.

**Caught by my own preregistered S1 check**, which is the only reason it is not in the results.
The defective output is kept at `SIMULATION_DEFECTIVE_s02run1.csv` and
`run_log_s02_DEFECTIVE.txt` rather than overwritten — E1_I0035's D-1 notes that it failed to do
this and I am not repeating that.

**Fixed** by standardising with constants from a 400,000-row pilot draw, never with the
realisation's own moments.

**Two things about this are worse than the bug itself.** First, **the FLIP arm did not fail** —
resampling one fixed vector by sign-flip gives a non-zero mean, so 567 conditions returned
plausible-looking finite ratios. Had I run only E1_I0035's construction I would have published
numbers from a simulator whose other half was measuring nothing. Second, the corrected grid still
shows **162 conditions with Type-I exactly 0.0000** — but those are the genuine `nb <= 5` cells
where the test provably cannot reject (D-1 of the *findings*, not a bug), and I only know the
difference because I went and checked. A degenerate-looking number and a true zero are
indistinguishable from the summary table.

---

## D-2 — MY FIRST CALL-GRAPH CLASSIFIER RETURNED 300 FALSE POSITIVES. Corrected.

The first version accepted any numeric constant in `[2.0, 3.5]` anywhere in a function body. It
matched `** 2`, `/ 2.0`, `* 3`, `haversine`, `r2`, `split_half_reliability` — **300 "MDE-producing
functions" across 47 screens**, which is not a resolution, it is noise wearing a resolution's
clothes. It would have made the census meaningless while looking exhaustive.

**Fixed** by testing the *value*: a constant within 0.01 of `z_alpha + Phi^-1(0.80)` for one of
three standard alphas, or `Phi^-1(0.80)` itself, or a `Mult` whose folded constant factor lands
on one of those. That is still a value test, not a name test. It yields **13** producers.

**The risk this leaves:** a screen that computes an MDE by some fourth route — a hard-coded
literal, a table lookup, a constant imported from elsewhere — is invisible to this classifier. I
mitigated it by cross-checking against the ratio fingerprint in the census (`value / null_sd` in
the same JSON record), which found the same four screens by a completely different route. Two
independent methods agreeing is the best evidence I have; it is not proof.

---

## D-3 — MY PROPOSED CLOSED-FORM FIX IS WORSE THAN THE INCUMBENT AT 8 BLOCKS. Standing, documented.

Test T6 measures all three against a simulated power crossing:

| blocks | empirical | my exact solver | my closed form | **incumbent** |
|---|---:|---:|---:|---:|
| 8 | 0.19231 | 0.27133 (**+41 %**) | 0.26323 (**+37 %**) | 0.16173 (−16 %) |
| 16 | 0.11898 | 0.16318 (+37 %) | 0.13378 (+12 %) | 0.10958 (−8 %) |
| 32 | 0.08424 | 0.07821 (−7 %) | 0.08455 (0 %) | 0.07711 (−9 %) |
| 64 | 0.05586 | 0.05865 (+5 %) | 0.05779 (+4 %) | 0.05528 (−1 %) |
| 256 | 0.02744 | 0.02758 (+1 %) | 0.02713 (−1 %) | 0.02683 (−2 %) |

**At 8 and 16 blocks the thing I built to fix the defect is further from the truth than the defect
was.** The closed form assumes a Gaussian null; the sign-flip null at small block counts is
sub-Gaussian, so the correction overshoots. The exact solver is worse still there, because it
conditions on one realisation's set of `|B_j|` and at 8 blocks that set is itself wildly variable.

I could not engineer this away and I have not hidden it behind a looser tolerance. The module now
**emits a warning below 32 blocks saying no data-driven MDE is stable there**, and T6d asserts
that the warning fires below 32 and not above. That is the honest output. A coordinator adopting
this fix should know it improves nothing below 32 blocks — it only stops the number being quoted
as if it meant something.

---

## D-4 — SEVEN FILES WOULD NOT PARSE AND I CANNOT PROVE THEY ARE CLEAN.

`E0_I0029\s05_screen.py`, `E1_I0004_shot_selection\analyze.py`, `E1_I0026\scripts\s06b_ns.py`,
`E1_I0032\scripts\{s08_stack,s11_findings,s12_verify}.py`, `E1_I0035\scripts\s07_tier_crosscheck.py`
— all `SyntaxError: invalid non-printable character U+FEFF` (a UTF-8 BOM). They are **named in
`run_log_s01.txt` and counted as UNRESOLVED**, not silently skipped. But 7 of 417 files were not
searched, and one of them is inside D103 itself. I could have stripped the BOM and reparsed;
I chose not to modify or even re-read files outside my scope under a transformation, and the cost
is this gap. It is small and it is real.

---

## D-5 — MY TYPE-I ACCEPTANCE BAND WAS WRONG FOR THE R I ACTUALLY RAN.

PREREG S1 committed to a band of 0.0404–0.0596, which is ±3 SE **at R = 2,000**. The grid in `s02`
ran at **R = 400**, for which the correct ±3 SE band is 0.0173–0.0827. So the reported "622 of
1,304 conditions inside the band (47.7 %)" **understates calibration** — it is measuring against a
band five times too tight. Against the correct R = 400 band the pass rate is far higher.

Rather than quietly widen the band I ran a **dedicated R = 2,000 Type-I check** in `s03` at the
committed replication: nb = 6 → 0.0275, nb = 7 → 0.0470, nb = 8 → 0.0485, nb = 9 → 0.0435,
nb = 10 → 0.0445, nb = 11 → 0.0505, nb = 12 → 0.0465, nb = 13 → 0.0495. Median 0.047, mildly
conservative, as a discrete randomisation test should be. **That, not the grid figure, is this
screen's Type-I evidence.**

---

## Limitations that are not defects but carry the same weight

* **I did not recompute E1_I0023's cells.** The whole D103 exposure calculation turns on that
  screen's 30 paired cells, and I bounded H_A on them from *other* screens' contamination rather
  than measuring it. I do not hold its loss vectors and writing there is outside my scope. The
  H_A bound [1.00, 2.44] is therefore an extrapolation, and it is the weakest link in
  `D103_EXPOSURE.md`.
* **The 6.6× refutation rests on reading `s05_power_and_exposure.py` lines 45–50 and 72.** I
  recomputed both contrasts from E1_I0035's own frame and the analytic figures reproduce its
  published values to 3 significant figures (Xa 0.000372 vs published 0.000382; Xb 0.003051 vs
  0.003042 — the small gaps are Monte-Carlo, different seeds on 2,000 draws). But I am inferring
  intent from code, and the author may have meant something I have not reconstructed.
* **`null_mean > observed` is structurally vacuous here.** The coordinator's cheap universal
  diagnostic cannot fire on this family: sign-flip draws are `±` a fixed set of block sums, so
  `E[draws] = 0` exactly, independent of the effect. It polices permutation nulls, where an
  effect can be absorbed into the null mean. **It cannot police the family this audit is about,**
  and reporting "the flag did not fire" for these cells would be a clean bill of health that the
  diagnostic is incapable of issuing. That is a coverage gap in the diagnostic, not a result.
* **FRESH vs FLIP agreed here, which does not clear the FLIP construction generally.** Median
  `E_inj/A_oracle` 1.034 (FRESH) vs 1.043 (FLIP), agreeing within 1 % at every block count. But my
  quantity is a *power calibration ratio*, and E1_I0034's measured attenuation (0.024 → −0.001 at
  2 null sd) is about *effect recovery*, which my simulation never performs. **My agreement is not
  evidence that the shuffled-residual construction is safe for E1_I0038's purposes.**
* **Everything is 2022–2024.** 2025/26 never opened; `assert_partition` runs on both E1_I0035
  frames I read and both are `[2022, 2023, 2024]`.
