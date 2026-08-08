# TRAP CHECKLIST — the pre-screen gate

Every proposal in `QUEUE.md` / `QUEUE.json` carries a `trap_check` field answering all eight. Every
future screen must re-run this checklist against its own *construction* before it computes anything.

Each trap below has been **paid for at least once by this program**. The counts are from the ledger.

---

## T1. RETROSPECTIVE BASELINE — 6 confirmed instances

**The trap.** A baseline, control or normalisation is computed over data that includes the future of
the row being scored. The screen then reports the increment over a baseline no forecaster could have.

**The instance that matters most:** one entered through the **INFERENCE MACHINERY**, not the feature
set — a decomposition introduced purely to satisfy a permutation scheme read the future and cleared
**47 of 264 cells** (D075). `base.zwithin` within-season centering (F7) is classified RETROSPECTIVE
SAME+CROSS season and affects `E0_I0012`, `E0_I0013`, `E1_I0012` and `E0_I0010`; **its magnitude was
never measured**. `E0_I0005`'s `r2_gain_pressure_over_pooled = 0.008424` carries a **false leakage
attestation** and may not be cited as a forecasting increment (D075 ruling 3).

**The check.** Read the *construction*, not the label. Trace every baseline, control, normalisation,
standardisation and shrinkage prior to the rows it consumes and assert those rows predate the
forecast cutoff. Attestations in a NOTES.md are not evidence.

**Live example in the data directory:** `data/lineups/lineups_*.parquet` are **season-aggregate totals
retrieved 2026-08-06**. Any exploration-season use is an automatic T1 violation.

## T2. WRONG-NULL LEVEL — 9 confirmations

**The trap.** The permutation/null is applied at a finer grain than the effect. The naive row-level
null **passed 65 of 132 cells** in one screen.

**The check.** State the level at which the candidate varies (row, player, player-season, team-game,
team-season, game) and null at *that* level. If a regressor is constant within a cluster, a
row-level shuffle is meaningless. `detect_grouping_level` in the shared kit was correct on all eight
regressors in D093 — use it, and record the level in FINDINGS.

## T3. AUTOCORRELATION IN THE NULL — the D093 finding, and it is the newest

**The trap.** A within-player shuffle destroys serial structure while the response keeps its own slow
drift, so the null is too narrow and the observed statistic looks anomalous. **Anticonservative:
p 0.0015 under a plain within-player shuffle where an honest cyclic-shift null gives p 0.39.**

**Why it is systemic here:** the program's most common construction is `.shift(1).expanding()`, which
is **autocorrelated by design**. D093 verified the mechanism: the shuffle-minus-cyclic gap tracks the
regressor's lag-1 autocorrelation at correlation **+0.832 across 48 cells** — own-usage (acf 0.912)
shows a gap of 0.186 while both iid noise controls (acf −0.033, −0.025) show gaps of 0.004 and 0.013.

**The check.** Compute the within-group lag-1 autocorrelation of every regressor. If it is material,
use a serial-structure-preserving null (within-player **cyclic shift**), not a plain shuffle.
D093 ruling 4: any prior screen using a within-block scheme on a shift-expanding regressor may carry
an anticonservative p and **should be checked rather than assumed**. This has not been done — it is
QUEUE Q9.

## T4. REFERENCE INCOMPLETENESS — the newest, and it passes every other guard

**The trap.** The increment is measured against a reference that is weaker than the best available,
so the "skill" is the reference's deficit. **Two confirmed instances:**
- D090: the same forecast scored **+46.4% or +7.1% by reference alone**.
- D093: the same forecast on the same rows scored **+0.22% or +4.24% by reference choice alone**, and
  an apparent 7.6x rise with a minutes floor was **the reference degrading, not the signal emerging**
  (at floor 30 the refitted reference's MAE is 0.1499 against the frozen reference's 0.1439).

D093 ranks reference/increment dependence as the **#1 explanation for the program's nulls**.

**The check.** Only **decomposition** catches this. Name every reference you could have used, score
against the strongest one, and report the spread. A screen reporting one reference number has not
discharged this. Note also (D072 ruling 4) that **dR2 is not scale-free across screens** — it depends
on the response's variance decomposition and the weighting, so a cross-screen dR2 ordering is fragile
even after a convention is imposed.

## T5. NAME-BASED FALSE HITS — 5 instances

**The trap.** A substring match on a column name is treated as evidence. `assert_partition` in the
shared kit **raised on clean data because "candi-DATE" contains "date"** (D085/D086). The coordinator
itself committed this trap in throwaway code hours after adopting the invariant against it (D088).

**THE INVARIANT, adopted program-wide at D086 ruling 2 and extended to ad-hoc code at D088 ruling 3:**
> A substring match on a column name may only **NOMINATE** a column for a value test.
> It may **never by itself** convict.

**The check.** Every claim about a column is settled on its **values**. This binds throwaway scripts
exactly as much as shipped screens. (I applied it in this pass: I did not assert that
`master_player.position` is starter-only from its name — I cross-tabbed it against `starter_flag` and
got perfect separation, 14,950/14,950.)

## T6. VACUOUS CONTROLS

**The trap.** A control that **cannot fail** returns a clean bill of health while testing nothing.
The natural per-player control — relabelling the player key and refitting per-player coefficients —
is a **literal no-op**, observed sd **5.207e-17** (D093). This is the row-level trap one level down.

**The check.** Before trusting a control, ask what result would make it fire, and verify it *can*
fire on synthetic data where the effect is known to be present. Report the control's own null
distribution, not just its p-value. D093's first-pass precision-weighted correlation let noise
control NC1 through at p 0.0076 because the weights were the one player-attached quantity a covariate
permutation does not permute; the unweighted rank statistic returned p 0.194 on the same control.

## T7. ARITHMETIC CEILINGS — three leads died here, not on statistics

**The trap.** The signal is real, clean, out-of-sample and **too small to matter**. Shot mix died at
dR2 ≤ 0.001127 (D079); the conversion channel at dR2 ≤ 0.000129 (D084), a ceiling 8.7x smaller.
D079 ruling 2 is explicit that the coordinator's stated worry (the attempts forecast) was wrong and
the real limit was **the response variable's own scale**.

**THE RULE, and it is mandatory for every entry in this queue:**
> Every proposal carries a rough ceiling: **how much could this move the target if it were perfect?**
> **A proposal that cannot clear ~0.001 dR2 on points is not worth screening.**

**Reference ceiling inputs I measured on the exploration partition** (18,216 played rows, 265
players), `var(pts) = 56.2619`, as `cov(x,pts)^2 / (var(x)·var(pts))` — the R2 bound if `x` were
forecast perfectly and nothing else changed:

| component | var | corr with pts | **perfect-forecast R2 bound** |
|---|---|---|---|
| `fgm` | 7.871 | 0.9612 | 0.9240 |
| `fga` | 28.371 | 0.8758 | 0.7670 |
| `minutes` | 113.927 | 0.7366 | 0.5426 |
| `fouls_drawn` | 3.732 | 0.6749 | **0.4555** |
| `ftm` | 4.341 | 0.6595 | **0.4350** |
| `fta` | 6.041 | 0.6548 | 0.4287 |
| `fg3m` | 1.451 | 0.6084 | 0.3701 |
| `reb` | 10.753 | 0.4826 | 0.2329 |
| `dreb` | 6.844 | 0.4753 | 0.2259 |
| `ast` | 5.094 | 0.3943 | 0.1555 |
| `tov` | 1.959 | 0.3713 | 0.1379 |
| `oreb` | 1.506 | 0.2761 | 0.0763 |

These are **upper bounds on a perfect forecast of the component**, not achievable numbers. A realistic
ceiling is this bound times the forecastable fraction of the component's variance, and the program's
measured experience is that the forecastable fraction is small. Use them to *reject*, not to promise.

## T8. PREDICTING ERROR IS NOT PREDICTING DIFFERENTIAL SKILL

**The trap.** A variable predicts the absolute residual, so it looks like a conditional edge — but the
**naive reference degrades in the same place**, so there is no edge. Demonstrated twice in one screen
(D076): `tm_newfaces_prior` predicts absolute residual strongly with no edge; and `pts__pred_point`
**cut points MAE by 9.9% while moving skill by +0.00007**.

**The check.** The metric must be **skill against a reference that faces the same conditions**. Any
screen reporting an abstention rule on raw MAE alone is measuring the wrong thing. D079 applies the
same discipline to a real pocket: an abstention pocket may be valid *for abstention* while being
**partly mechanical** (extreme-|OS| opponents supply more regressor variance) and therefore **not** a
heterogeneity claim.

---

## Standing procedural requirements that ride along with the eight

- **HASHED PRESELECTION** (D085 ruling 4, D087): write `CANDIDATES_PRESELECTED.md` and hash it before
  screening. It converts a screen-count claim into a checkable fact.
- **DECOMPOSITION IS A REQUIRED STEP, not discretionary** (D087 ruling 4): decompose every surviving
  candidate against its own components and against every available prior measurement of the target.
- **EXPLORATION PARTITION** (D062, GRAPH_POLICY 13.2): E0/E1 read seasons **2021–2024 only**.
  Seasons 2025–2026 are the confirmation holdout and may not be read, joined, plotted or described.
- **MANIFEST GATE** (GRAPH_POLICY 13.2.1/13.2.2): an artifact with no manifest fails the gate. **68
  shared artifacts have no manifest at all**, including all of `data/shotcharts/`,
  `data/playbyplay/`, `data/possessions/`, `data/lineups/`, `data/injury_history/` and
  `data/reference/player_bios.csv`. Every proposal touching these must carry a provenance note and
  resolve the gate **on values** the way D087 did.
- **FORBIDDEN ARTIFACTS**: `data/w1_truth/player_game_availability.csv` and
  `data/w1_truth/roster_asof.csv` are artifact-granular with `fit_through_season 2026` and may not be
  used at E0/E1 at all.
- **REPORT DEFECTS IN SHARED CODE, do not work around them** (D081/D082/D086, ratified across six
  users and seven real defects).
- **PLAIN UNWEIGHTED OLS R2** is the convention (D069), meaning unweighted in **all three** places —
  fit, SSE and SST (D072 ruling 2). A screen needing weights must use the standard weighted SST about
  the weighted mean and say so. **Past weighted numbers cannot be rescaled** — they must be re-run.
