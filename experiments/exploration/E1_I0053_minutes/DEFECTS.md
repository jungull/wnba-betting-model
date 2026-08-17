# DEFECTS — E1_I0053_minutes' own

`PREREG.md` sha256 `ac373cc884166e263ddfae43466932de430d0f046966c5d918dc3c3853a1168d`.
Every defect below is this screen's, found by this screen, and recorded whether or not it changed a
number. Two of the eight would have changed a published figure.

---

## D-01 — the PROJ arms are oracles twice over. **Declared, not fixed.**

`PROJ` renormalises the forecast inside the team-game onto the **realised** `T_min`, summed over the
**realised appeared roster**. Neither is available before tip-off, and the frame's rows *are* the
realised roster, so there is no version of a within-team-game renormalisation in this frame that is
free of it. **No PROJ number in this screen is an achievable live increment.** The primary arm is
`RAW` precisely for this reason, and `s06`'s decomposition exists to quantify how much of the PROJ
gain the oracle is responsible for (answer: all of it — see D-08's companion result in `VERDICT.md`
§3).

## D-02 — the first projected-oracle implementation returned clip-driven ceilings. **FIXED BEFORE PUBLICATION.**

`s03_ceiling.py::proj_oracle` originally searched `g` over `±20·sd(y)/sd(d)`, an unanchored range.
At large `|g|` the non-negativity clip inside `project_to_total` turns the search into an arbitrary
monotone reallocation of the candidate, and the "ceiling" it returns is a property of the clip. It
produced `R1_min/PROJ/C3_blowout_adj = 0.032978` against an unconstrained linear oracle of 0.002388,
and `C2_foul_rate = 0.023574` against 0.000087.

**Fix:** the grid is now anchored on the linear frozen coefficient, `g0·linspace(−6, 10, 321)`,
following `E1_I0046/s02::oracle_proj` (read-only). `clip_frac_at_gstar` is now published per row and
is 0.0000 for all but two component cells (max 0.0025), so the *remaining* excess of the projected
oracle over the linear one is genuine nonlinearity of the renormalisation, not clipping.
**A companion column `ORACLE_projected_g_within_2g0` is published beside it, and no verdict in this
screen uses the projected oracle at all.**

## D-03 — the fully-pre-game rescale arm scored R² = −10.34. **FIXED. WOULD HAVE CHANGED A PUBLISHED NUMBER.**

`s06`'s `A1_GLOBAL` arm computes one scalar `c = 200·n_tg / Σ forecast` on training rows. The first
version summed the forecast over **decision-stratum training rows only** — about 4 players of a
9.41-player roster — so `c ≈ 1.67` and every forecast was inflated 67 %. The arm scored
**R² = −10.344142** and the contrast `A1_GLOBAL − A0_RAW` read **−10.573581**.

**Caught because the number was impossible**, not by inspection — the same signature as
`E1_I0046`'s D-01 (an impossible ΔR² of 2.43). **Fix:** the team-game sum runs over the full
appeared roster of the training seasons. Post-fix the arm scores +0.159056 and the contrast is
−0.070383. **Every `A1_GLOBAL` number published anywhere in this screen is post-fix.**

## D-04 — the PROJ arm's FROZEN and UNFROZEN values are not comparable to each other.

The PROJ arm fits its coefficients on the **unprojected** response and scores the **projected**
forecast. The two fit arms therefore optimise different objectives, and the difference between them
on that arm is not the substitute-versus-addition diagnostic it is on the `RAW` arm. It shows up
loudly: `R2_smin / C3_blowout_adj` is **+0.019254 FROZEN and +0.001507 UNFROZEN**, and
`R1_min/PROJ / C3_blowout_adj` is **+0.015115 FROZEN and +0.001946 UNFROZEN**.

**Not fixed** — fixing it means fitting on the projected response, which changes what the base is.
**Consequence: the freeze diagnostic in `VERDICT.md` is taken from the `RAW` arm only**, and the
largest number anywhere in `PRIMARY_CELLS.csv` (+0.019254) is quoted nowhere except here and in
`VERDICT.md`'s weakening section, flagged as this artefact.

## D-05 — the base column is not built with one consistent `(h, k)` across train and eval rows.

`s02` assembles the walk-forward base by writing each eval season's own tuned allocator into that
season's rows, so 2022 rows carry the allocator tuned for **eval 2022** (`h = 2, k = 2` on `R1_min`
RAW) while serving as *training* rows for eval 2023, whose own allocator is `h = 3, k = 1`. **This
is not leakage** — the 2022 allocator is selected on 2021 data only — but it is an inconsistency,
and it is inherited from `E1_I0046/s02`, which does the same.

**Measured cost:** `s05` rebuilds the base with a single `(h = 3, k = 1)` everywhere and gets
`C1_player_rest` FROZEN at **+0.006553** against `s04`'s **+0.006644** — a **1.4 %** difference that
changes no verdict, no floor comparison and no p-value. The eval-row base columns agree at
**max|Δ| = 0.000e+00**; the discrepancy is entirely in the training rows.

## D-06 — the injection recovery curve is not monotone in recovered units.

`INJECTION_POWER.csv`, `C1_player_rest`: planting θ = 0.20, 0.35, 0.50 returns mean recovered ΔR² of
**−0.000604, −0.001196, −0.000528** — negative recoveries from positive plants — before turning
positive at θ = 0.70 (+0.002311) and θ = 1.00 (+0.010653). **Power is monotone** (0.000, 0.050,
0.400, 0.875, 1.000), so `θ80 = 0.6684` minutes per sd is trustworthy; the conversion into ΔR² units
is not. Linear interpolation of the recovered column crosses a sign change and gives **0.001863**;
quadratic scaling from the θ = 1 anchor gives **0.004760**.

**Consequence:** the injection floor is published as the **interval 0.001863–0.004760** and every
verdict uses the conservative end (1.40×, not 3.57×). This is `E1_I0046`'s D-06 recurring, with 40
replicates and 200 draws — **the replicate count is the binding constraint and it is too small to
resolve the low-θ region**. `E1_I0038` D-03 established that 60 replicates cannot carry an 0.80
threshold; 40 is worse, and the honest reading is that only θ80 is resolved.

## D-07 — the statistic is biased upward under a null draw for this candidate, and the `z` on the vacuous control is meaningless.

**(a)** At θ = 0 the injection returns a mean recovered ΔR² of **+0.002140** rather than 0. The
frozen arm's `g·(d − d̄_train)` term acts as an accidental intercept correction whenever the
candidate's eval-season mean differs from its training mean, and `C1_player_rest` has such a shift.
**The null prices it correctly** — its centre is +0.002190, ratio +1.0232, type-I 0.060 — but any
reader comparing +0.006644 against zero rather than against +0.002190 overstates the effect by 3×.
`VERDICT.md` says so in its weakening section.

**(b)** `N_TGSWAP` is the **literal identity** for a team-game-constant column, so its null sd on
those cells is 0 to within LAPACK noise (**5.4e-20, 2.2e-19, 2.2e-19, and exactly 0.000000e+00**).
`(real − mean)/sd` is then ±1.00 or `nan` and carries no information. **The published tables report
the observed sd and suppress the `z`**; the numbers are not rounded to `0.000000`.

## D-08 — three grids were added after the prereg hash, and one of them overturned the headline.

Listed with direction, per `NOTES.md`:

| added | why | direction |
|---|---|---|
| `s06_budget.py` | the coordinator asked for the pre-game-available portion of the projection gain | **new question**, and its answer (zero) weakens a result this screen did not own |
| `s07_robustness.py` | to test whether the only survivor lives in a thin tail | **can only weaken**, and it did — it is the reason `VERDICT.md` says the survivor is not what it was preregistered as |
| `s08_findings.py` | floor assembly and concentration counts | bookkeeping; the floor it computes is **more conservative** than the one the prereg named |

**None of the three can strengthen a headline and two of them weakened one.** No preregistered cell
was dropped, no null was changed, no candidate was added, and `V5_binary_rest_ge_8` — the variant
that reproduces the whole effect — is **explicitly not treated as a survivor** because it was chosen
after seeing the result and its p-value is uncorrected for the eight variants tried.

---

## THINGS CHECKED THAT WERE **NOT** DEFECTS

* **Imputation.** Ten candidates impute non-finite values to the whole-frame column mean. **Zero
  decision-stratum rows are imputed** for `C1_player_rest` (verified in `s07`), because
  `n_prior ≥ 8` guarantees a previous appearance exists.
* **Same-channel contamination.** `corr(candidate, base)` on the scored rows peaks at −0.397
  (`C4_min_volatility`); nothing approaches the ≥ 0.9 that made `E1_I0046`'s largest number
  unquotable.
* **Leakage.** Every candidate is a `.shift(1)` construction. The probe puts the survivor at
  **−0.0697** correlation with the player's own strictly-after-date future minutes, against the
  base's +0.5816. Nothing flagged.
* **Partition.** Value-level, datetime-dtype-gated, asserted after every load and every filter.
  2025 and 2026 were never read, joined, merged, described or counted.
