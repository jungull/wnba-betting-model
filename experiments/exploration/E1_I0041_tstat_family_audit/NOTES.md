# NOTES — E1_I0041, audit of D103's `t_statistic` scale conversion

## 0. What was asked and what came back

E1_I0037 closed the D113 alarm and left a larger, explicitly unquantified exposure: D103's
`t_statistic` family — 666 of 1,349 cells, 518 of 760 blind verdicts — uses a scale conversion that
never passed D103's own validation gate. This screen is that follow-up.

**Short answer.** The conversion's *equation* is sound; two of its *inputs* are not, they run in
opposite directions and for one of the two contributing screens they very nearly cancel. Repairing
the unambiguous one moves D103's headline from 56.34 % to 65.68 % blind. The gate really is a
coverage gap with no validation hiding elsewhere. E1_I0037's two structural gates do **not** apply
to this family — measured, not assumed — and the analogous hazard here is 73 cells whose
permutation null did not function.

## 1. Order of work

| step | script | output | note |
|---|---|---|---|
| anchor + call graph + source facts | `s01_anchor_and_callgraph.py` | `_s01.json`, `_d103_cells.csv` | anchor reproduced to 16 digits before anything else |
| structural probe (read-only) | `s02_probe_structure.py` | `_s02_probe.json`, `_fold_factors_E0_I0014.csv` | block counts, `t_crit`, each screen's own bar |
| **PREREG written and hashed** | — | `PREREG.md`, `PREREG.sha256` | `869a92f0…` |
| simulation | `s03_simulation.py` | `SIMULATION.csv` | **run 1 defective, preserved**; run 2 used |
| family-wise bar | `s03b_familywise_bar.py` | `FAMILYWISE_BAR.csv` | replaces s03's non-estimable arm |
| restatement + gates | `s04_restate_d103.py` | `TSTAT_CELL_FLOORS.csv`, `STRUCTURAL_GATES.csv` | reconstruction agrees to 1.07e-13 |
| ratios + findings | `s05_ratios_and_findings.py` | `FINDINGS.json` | |
| proposed fix | `PROPOSED_FIX/` | tests 13/13 | **not recommended as-is**, see DEFECTS D-5 |

s01 and s02 ran before the preregistration was written. They are descriptive confirmations of
source facts — what a file contains, what a column was computed from — and every number they
produced is quoted inside `PREREG.md` so nothing could be back-fitted. The simulation and the
restatement are the pre-registered part.

## 2. The anchor, and why it took two attempts

D103 leaves **two** files called `retrospective_power.csv`: a 1,975-row one at the experiment root
and a 1,975-row one under `out/`, with different content. Keying the root file by
`(screen, cell, null_arm)` gives 1,885 cells and 805 blind — not the published figures. E1_I0037's
anchor uses `out/retrospective_power.csv` grouped by `(screen, decision, family_size_K, cell)`
taking the **worst** null arm's `mde80_fw`. That reproduces **1,349 / 760 / 0.5633802816901409**
exactly. The first key is not wrong so much as a different question, and the difference is 4.5
points of headline — worth knowing that D103's number is key-sensitive at that magnitude before
any correction is discussed.

## 3. Reading `SIMULATION.csv`

192 rows: 96 conditions × 2 threshold regimes. Grid: block counts {36, 64, 128, 475, 489, 1486} —
the four real ones plus two ladder points — × between-block variance share {0.10, 0.50, 0.80, 1.00}
× AR(1) ρ {0.0, 0.5} × games-per-block λ {12, 30}, four seasons, unbalanced block lengths.

* `status = OK` (96 rows, `regime = per_cell`) — fully calibrated. Type-I **0.0525** median
  (min 0.0292, max 0.0767; 6 of 96 outside [0.03, 0.07], consistent with Monte-Carlo noise at
  R = 1,200 with a bar itself estimated from 1,000 draws).
* `status = OK_FORMULA_ONLY__BAR_NOT_ESTIMABLE…` (96 rows, `regime = family_wise`) — the **bar**
  in these rows is mis-calibrated (DEFECTS D-3), so `ratio_A_pub_folded` and `ratio_A_pub_signed`
  are **not** published-versus-correct comparisons there. `ratio_A_cor` (0.984) remains valid and
  is the useful content: the floor formula is accurate at a family-wise-magnitude bar too.

Headline ratios, per-cell regime, analytic floor ÷ injection-verified floor:

| | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| `A_pub_folded` (E0_I0014's published form) | 0.271 | 0.338 | **0.359** | 0.386 | 0.474 |
| `A_pub_signed` (E0_I0019's published form) | 0.661 | 0.927 | **0.995** | 1.071 | 1.212 |
| `A_cor` | 0.734 | 0.933 | **0.989** | 1.052 | 1.236 |

## 4. Every declared contrast (D101)

The rule that killed the D113 alarm was two floors on different response contrasts. Every floor in
this screen is on **one** contrast, and it is the same one in every table:

> ΔR² of the season-demeaned response `ỹ` on the season-demeaned **permuted** carrier `x̃ₚ`, over
> the full row set, unweighted, SST = `ỹ·ỹ` of the effect-free response, single added regressor,
> base = season fixed effects only.

`E_inj`, `A_pub_folded`, `A_pub_signed` and `A_cor` are all computed from the **same draws, same
rows, same SST basis, same base**, and the effect is planted along the same vector that is then
tested (`s04_power.py:11`). No ratio in this screen crosses a contrast.

On the real cells, the floors are ΔR² of each cell's own response — |residual| or squared residual
of minutes/points/FGA for E0_I0014, Brier-skill differences for E0_I0019 — and D103 compares them
against 0.0023, a ΔR² on D089's walk-forward points. **That is a cross-response comparison.** It is
D103's own design, it hits all three `stat_family` groups identically, so the *relative*
corrections here are unaffected; the absolute counts, published and corrected alike, inherit it.
E1_I0037 did not raise this and it belongs on the record.

## 5. Call-graph resolution (no name-based selection)

1,104 `.py` files enumerated under the worktree; 1,084 parsed; **20 unparsable**, all
`SyntaxError: invalid non-printable character U+FEFF`, each named in `run_log_s01.txt`. The only
D103 file among them, `scripts/s06b_ns.py`, was opened with `utf-8-sig` and printed in full into
`run_log_s04.txt`: it reads two parquet shapes and validates nothing.

Call sites resolved on `ast.Call` nodes: `mde80_tscale` **×4** (s06_retrospective.py 167, 168, 201,
202), `mde80_increment` ×10, `mde80_paired` ×2, `validate` ×56 (55 of them unrelated `validate`
methods in `player_program`, one the D103 gate). Asserted counts, not eyeballed: 666 `t_statistic`
cells and 518 blind both assert in `s01`.

## 6. What I did not do

* **No 2025/26 data was opened.** Nothing in this screen reads a holdout artefact. The only real
  files read are two screens' published `screen_results*.csv`, their `permutation_nulls.npz`,
  their `maxt_null_draws*.csv`, and D103's own outputs — all 2021–2024 exploration.
* **No real response was re-modelled.** The empirical work is entirely on synthetic panels; the
  real-data work is moment arithmetic on already-published null draws.
* **The shared kit was never opened for writing.** `experiments/exploration/_screen_kit/` is
  untouched. Nothing outside `E1_I0041_tstat_family_audit/` was created or modified. No `git`
  command was run.
* **No process was killed.** The only processes I launched are the five Python runs listed in §1,
  each started with `Start-Process … -PassThru` and waited on; PIDs **6240** (s03 run 1, defective),
  **17484** (s03 run 2) and **7212** (s03b) are recorded in the run logs, and all exited on their
  own. `s01`, `s02`, `s04`, `s05` and the fix tests were foreground calls. No `Stop-Process`,
  `taskkill` or blanket kill was issued at any point.
* **I did not revise D103.** `E1_I0026_detection_floor/` is unmodified.

## 7. What I would send the next screen after

1. **E0_I0014's family-wise procedure**, not D103's conversion, is the largest single lever on the
   restated count (DEFECTS E0_I0014-1). An unstandardised max|t| over cells whose null widths span
   two orders of magnitude sets a bar of 15.9 median-cell sds. That is worth a screen of its own,
   and it may affect that screen's *recorded verdicts*, not just its retrospective power.
2. **The 73 non-functioning nulls** should be given an UNVERIFIABLE status across the whole
   ledger, not just here. The check costs one division. E0_I0019 already wrote it.
3. **Two things in the `increment` family that I did not audit and that the gate may not reach.**
   I spot-checked `E0_I0024`: its saved nulls are ΔR² draws, not folded t, so the defect found
   here does not replicate there. But (a) `E0_I0024` and `E0_I0017` have **no published null
   mean** — D103 substitutes `null_mean = sd/√2` (`s06_retrospective.py:177, 210`,
   `null_mean_source = "ESTIMATED_sd_over_sqrt2"`), a χ²₁ assumption on 367 cells, while
   `validate()` only ever sees cells with a *measured* mean; and (b) the estimate is an input
   the gate cannot test because the simulated rows it reads always have the real thing. That is
   the same shape of gap as the one this screen just measured, on a different 367 cells.
   "The gate covers it" is exactly what was believed about this path too.
