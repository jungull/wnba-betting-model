# E1_I0036 -- LEVEL ARTEFACT SWEEP -- PREREGISTRATION

Screen id: `E1_I0036_level_artefact_sweep`
Programme: WNBA player-model research programme
Authority: D103 (power), D108 (null must match level, verify by injection), D111 (aggregation
level is a design variable), D101 (denominator/comparability), D087 (reference incompleteness).

This document is frozen and hashed BEFORE the triage rule is applied to the census and BEFORE
any new statistic is generated. `PREREG.sha256` accompanies it.

---

## 0. DISCLOSURE OF WHAT WAS SEEN BEFORE FREEZING

Honesty requires stating what had already been read when this was written, because a
preregistration written after looking is worth less than one written before.

BEFORE freezing I had read (read-only, no statistics generated):

- `E1_I0033_aggregation_level/which_level_wins.csv` (directed by the brief; used to reproduce
  the D111 anchor, see section 9).
- `DECISION_LEDGER.jsonl` entries D097, D103, D108, D111 in full.
- `E1_I0026_detection_floor/out/s08_cell_verdicts.csv`, `s08_screen_verdicts.csv`,
  `s06_retrospective_by_screen.csv`, `s01_result_file_inventory.csv` -- the D103 power census.
- `E0_I0024_reb_ast_characterisation/upstream_signals.csv`, `arithmetic_ceiling.csv`,
  `ladder_summary.csv` and the screen's build/prereg scripts -- the D097 record.
- `E0_I0029_freethrow_hurdle/injection_power.csv` -- the D108 degeneracy evidence.
- Column inventories and roster-completeness counts of the frames named in section 3.

CONSEQUENCE, stated plainly: **the D097 rebound cell is DIRECTED, not selected.** The brief
named it as an outstanding programme debt and I had located it before writing this. It is
therefore NOT counted as a hit of the triage rule and is reported in its own document. The
triage rule in section 4 governs only the OTHER re-runs, and I had not computed any
level-artefact ranking before freezing.

---

## 1. THE QUESTION

Roughly 1,349 recorded cells were measured at a fixed player-game level because nobody asked
whether that was the right level. D111 showed the level is worth up to 49.6%. D103 showed
56.3% of cells could not have detected the programme's own best finding.

HYPOTHESIS (H1): some recorded nulls are LEVEL ARTEFACTS -- an effect that is real at team or
matchup level, diluted across a roster, fails every player-level screen and would pass a
team-level screen that was never run.

NULL HYPOTHESIS (H0), which I expect to be the outcome: the nulls were real. Re-levelling
changes nothing that matters, and the negative record survives.

**I am not looking for a survivor. A clean H0 with power behind it is the deliverable I
expect to write, and it is a more valuable result than a manufactured lead.**

---

## 2. PARTITION -- HARD

- Exploration partition = seasons **2021, 2022, 2023, 2024 ONLY**.
- 2025 and 2026 are a SEALED HOLDOUT. No file under any 2025/2026 path is opened, and every
  frame is asserted to contain no season outside {2021,2022,2023,2024} before any fit.
- Manifest fields `row` and `season` are usable; `artifact` is NOT. MISSING = UNVERIFIABLE.
- Assertion `A_PARTITION`: `set(frame.season) <= {2021,2022,2023,2024}`, printed and asserted
  in every build step. A failure halts the screen.

---

## 3. DATA -- EXPLICIT ALLOWLIST, NO NAME-BASED SELECTION

Five findings in this programme died to name-based column selection. Therefore:

- Every regressor and every response is named in an **explicit python list literal** in the
  script. No `startswith`, no `filter`, no regex, no `[c for c in df.columns if ...]` is
  permitted to choose a modelling column.
- Each script PRINTS the resolved list and ASSERTS its length against a hard-coded integer.

### 3.1 Sources (read-only, both already inside the exploration partition)

| id | path | grain | rows |
|----|------|-------|------|
| `SRC_PLAYER` | `E0_I0024_reb_ast_characterisation/screen_frame.parquet` | player-game | 18,212 |
| `SRC_TEAM`   | `E1_I0033_aggregation_level/_team_frame.parquet` | team-game | 1,940 |

`SRC_PLAYER` is D097's own frame. Re-using it is deliberate: the D097 re-examination must be
measured on D097's exact rows or it is not a re-examination (D101).

### 3.2 D087 REFERENCE-INCOMPLETENESS GUARDS (asserted, not assumed)

- `A_ROSTER_COMPLETE`: for every team-game in `SRC_PLAYER`, summed player minutes must equal
  200 (regulation) or 200 + 25k for k overtimes, within 1.0 minute. Count printed.
- `A_TEAM_JOIN`: `SRC_TEAM` and the team-game aggregate of `SRC_PLAYER` must agree on the SET
  of (season, game_id, team_id) keys exactly -- no left-join silently covering a subset.
- `A_SUM_IDENTITY`: for reb / oreb / ast / pts / fga, the sum of player values must equal the
  team box value. The MATCH RATE is printed. If any response fails at >1% of team-games it is
  DROPPED from the team-level arm and the drop is recorded in DEFECTS.md.
- Any reference used in any cell must have its coverage count printed and asserted equal to
  the analysis row count.

### 3.3 NO RETROSPECTIVE BASELINE -- checked, not assumed

Six instances have been found in this programme, one via inference machinery rather than an
obvious lookup. For every column entering any model I will state and check its construction:

- `A_NO_RETRO_1`: every reference and every candidate must be a STRICTLY PRIOR quantity.
  Verified for the D097 candidates by reading `s02_build_frame.py` (already done: R08 is
  `prior_sum(p_ra)/prior_sum(p_att)`, an expanding strictly-prior ratio -- NOT a season
  aggregate). Verified for team-level references by construction below.
- `A_NO_RETRO_2` (empirical): delete all rows from the LAST 20% of each season, rebuild every
  reference, and assert the reference values on the surviving rows are bit-identical. A
  retrospective baseline changes; a prior one does not. Mismatch count printed.
- Team-level references are built ONLY as expanding strictly-prior means within season,
  computed with a shift so the current game is excluded. No season means, no oracle columns,
  no full-sample standardisation of any regressor (standardisation, where used, is
  within-fold/expanding or omitted entirely).

---

## 4. THE TRIAGE RULE -- FROZEN BEFORE APPLICATION

### 4.1 Census

`CENSUS.csv` = every killed candidate cell recoverable from the programme's recorded result
files, with columns: screen, decision, cell, candidate, target, stratum, base, **level**,
n, reported dr2, reported p at the screen's own "correct level" null, family size K,
D103 `mde80_fw` / `mde80_percell`, D103 blindness flags, recorded arithmetic ceiling where
present, and a KILL REASON assigned by the rules in 4.2.

Level is taken from the source screen's own recorded `level` / `entity_level` / `entity` /
`carrier_level` column where one exists. Where none exists the level is recorded as
`NOT_RECORDED` and the cell is **INELIGIBLE** for re-levelling -- I will not infer a level
from a candidate's name.

### 4.2 KILL REASON -- assigned mechanically

Applied in order; first match wins.

1. `CEILING` -- the screen recorded an arithmetic ceiling for the cell and that ceiling is
   below the single-cell detection floor 0.00102. **Arithmetic; survives re-levelling.**
2. `DEFECT` -- the cell is recorded in a screen's DEFECTS.md or was superseded.
3. `UNINFORMATIVE_NULL` -- D103 flags the cell blind to the programme's own best live effect
   (`blind_to_best_lead_fw == True`). Not evidence of absence.
4. `POWERED_NULL` -- the cell was not blind and did not survive. A real negative.
5. `SURVIVOR` -- cleared its family-wise threshold. Not a kill; retained for context.

### 4.3 ELIGIBILITY FOR RE-LEVELLING (all four must hold)

- **T1 NOT-A-CEILING-KILL.** `kill_reason != CEILING`. **Ceiling kills are arithmetic and
  survive re-levelling. They are NOT resurrected, and the verdict document will say so
  explicitly and name them.**
- **T2 MECHANISM IS CONSTANT ACROSS THE ROSTER.** The candidate's recorded level is in
  {`team_season`, `opp_team_season`, `team_game`, `matchup`}. This is the exact and only
  condition under which a player-level response DILUTES the effect: a regressor that is the
  same number for all ~9.4 teammates in a team-game contributes its whole effect to the team
  total but 1/9.4 of it, plus roster noise, to each player row.
  Candidates at `player_season` or `row` level are INELIGIBLE for re-levelling upward --
  their mechanism is a property of a player, and summing to team level destroys, not
  recovers, the variation. (The D097 debt is a `player_season` candidate and is therefore
  explicitly NOT a re-levelling candidate; see section 6.)
- **T3 A LEVEL-MATCHED RESPONSE EXISTS.** The player-level response is an additive box
  quantity whose team total is observed: one of pts, reb, oreb, dreb, ast, fga, fta, ftm.
- **T4 POWER IS RECORDED.** `mde80_fw` present. T4 is a recording requirement, not a filter.

### 4.4 RANKING -- frozen formula

Eligible cells are collapsed to unique (candidate, target) pairs, taking the largest recorded
`dr2` across strata/bases. Rank key, descending:

```
EV = log10(max(dr2, 1e-6)) + LEVELBONUS + PENALTY_D111
  LEVELBONUS    = +0.50 if level == opp_team_season (matchup mechanism, the strongest
                  a-priori case for dilution), +0.25 if team_season, else 0
  PENALTY_D111  = the D111 bottom-up penalty for the target quantity, expressed as a
                  fraction, added directly:  fga .496 | pts .273 | reb/oreb/dreb .157 |
                  ast .110 | fta .073 | ftm .066
                  (higher penalty = the quantity is more level-sensitive = higher EV)
```

Ties broken by larger `n`. **N_RERUN = 4** distinct (candidate, target) pairs, taken from the
top of this ranking. Four is chosen because each re-run carries a full injection-verified
null at two levels plus an MDE curve, and because a small preregistered set is what D103
directed ("AT MOST ~18 PREREGISTERED CELLS"); 4 pairs x 2 levels x 1 null each = 8 primary
cells, well inside that budget and leaving room for the injection grid.

If fewer than 4 pairs are eligible, all eligible pairs are run and the shortfall is reported.

---

## 5. STATISTICS

### 5.1 Estimator

Incremental variance explained from OLS, in-sample on the analysis rows unless the cell is
declared walk-forward:

`dr2 = R2(base + candidate) - R2(base)`

fitted by `numpy.linalg.lstsq` on a design with an explicit intercept. Base columns are
listed explicitly per cell in `PREREG` section 5.4 and asserted by count.

### 5.2 Nulls -- ONE PER LEVEL, NAMED IN ADVANCE

R = 601 permutation draws per null (giving a minimum attainable p of 1/601 = 0.001664, the
same granularity as the screens being re-examined). All draws are saved as `.npz`.

| null | construction | correct for |
|------|--------------|-------------|
| `N_ROW` | permute the candidate freely across all analysis rows | `row`-level candidates only |
| `N_CYCLIC` | within each player, cyclically shift the candidate series by a random offset | within-player time-varying candidates ONLY |
| `N_PSWAP` | swap each player's ENTIRE candidate series with another player's, preserving within-player serial structure | `player_season` candidates |
| `N_TSWAP` | reassign the team-season identity carrying the candidate among team-seasons within the same season, preserving the team's own series | `team_season` candidates |
| `N_OSWAP` | reassign the OPPONENT identity among team-games within the same season, preserving each opponent's own series | `opp_team_season` candidates |

The p-value is two-sided on the studentised statistic and one-sided on dr2 as recorded by the
source screens; both are reported. `null_mean` and `null_sd` are published beside EVERY p
(D103 ruling 2). Any p reported without them is void.

### 5.3 INJECTION VERIFICATION -- MANDATORY, D108

**No null is trusted until it detects a planted signal.** For every (cell, null) pair:

1. Take the analysis rows and the real base.
2. Construct `y_inject = y_base_residual + c * carrier_residualised`, with `c` solved so the
   INDUCED dr2 equals a target delta exactly.
3. Targets: `DELTAS = [0.002057, 0.001127, 0.000500, 0.000129, 0.000050, 0.0]`
   (0.002057 = largest live effect in the programme; 0.001127 = D079 shot mix; 0.000129 =
   D084 opp conversion; 0.0 = type-I check).
4. Run the null against the injected response. `DETECTED = (p < 0.05)`.

VERDICTS:

- A null that FAILS to detect **0.002057** is **DEGENERATE**. Every kill it produced is VOID
  and is reported as a false-negative risk, not as evidence of absence.
- A null whose type-I rate at delta = 0 exceeds 0.10 is **ANTICONSERVATIVE**; its survivals
  are void.
- MDE80 for the cell = the smallest delta in `DELTAS` at which detection probability reaches
  0.80 across 200 injection replicates. Reported as `> max(DELTAS)` if never reached.

### 5.4 POWER FIRST -- D103

MDE80 is computed and printed **BEFORE** any interpretation of any cell. If
`MDE80 > the effect the cell was meant to detect`, the cell is stamped **UNINFORMATIVE** and
**no further compute is spent fitting it.** The effect a cell was meant to detect is, in
order of availability: the cell's own recorded arithmetic ceiling; else the programme's
largest live effect 0.002057.

### 5.5 ARITHMETIC CEILING BEFORE FITTING

Benchmarks, fixed: largest live effect **0.002057**; single-cell floor **0.00102**; 132-cell
floor **0.00235**. For every new cell, the ceiling
`CEILING = (beta * sd_candidate_residualised / sd_y)^2` is computed FIRST. If
`CEILING < 0.00102` the verdict is **CEILING BELOW FLOOR -- NOT FIT**, recorded, and the fit
is skipped.

### 5.6 D101 -- COMPARABILITY DISCIPLINE

**A team-level number and a player-level number have DIFFERENT RESPONSES and are NEVER
directly comparable.** No cross-level dR2 is quoted, differenced, or ratioed anywhere in this
screen's outputs. The only cross-level statement permitted is a SURVIVAL statement:

> "Candidate X, killed at player level, does / does not clear its own level-matched,
> injection-verified null when measured at team level against a team-level reference."

Each level carries its own reference, its own SST, its own row set, its own weighting (none),
and its own null. Skill is expressed as a ratio to a level-matched reference within a level.
Any sentence comparing magnitudes across levels is a defect and is to be recorded as one.

---

## 6. THE D097 DEBT -- DIRECTED CELL (not a triage hit)

Candidate `R08_player_ra_share`; response `y_oreb`; stratum POOLED; base B_COMPLETE;
n = 13,784; recorded `dr2 = 0.006488` -- the largest raw increment anywhere in D097.
Killed at `p_cyclic_shift = 0.996672`, family-wise p = 1.0000, while `p_row_level = 0.001664`
and `p_entity_swap = 0.001664`.

D108 proved `N_CYCLIC` returns p = 1.0000 against a planted signal in 0/15 configurations
when the carrier is `player_season`. R08's carrier is `player_season`. **The kill is
therefore suspect.**

PREREGISTERED PROTOCOL, in this order:

1. **Reproduce** D097's `dr2 = 0.006488` on D097's exact rows and base. Exact reproduction is
   a gate: if it does not reproduce, the re-examination halts and the mismatch is a defect.
2. **Decompose R08's variance** into between-player and within-player-season components. This
   determines which null is correct and is a fact about the regressor, not about the outcome.
3. **Run all three candidate nulls** (`N_ROW`, `N_CYCLIC`, `N_PSWAP`) and **inject into every
   one of them** per 5.3.
4. Declare the matched null = the one that (a) detects 0.002057 and (b) has type-I <= 0.10 at
   delta = 0. If more than one qualifies, the most conservative (largest null_sd) wins.
5. Report the verdict under the matched null, WITH its MDE80.
6. **Separately** test whether re-levelling is the fix: D111 gives rebounds only a 15.7%
   bottom-up penalty, and offensive rebounds are an ALLOCATION OF A SHARED BUDGET (exactly
   one player collects each rebound), which D111's rule says does NOT survive aggregation
   from below. Both possibilities -- "the null was wrong" and "the level was wrong" -- are
   to be reported, including if they disagree.

PRE-COMMITTED READING OF THE OUTCOMES:

- If `N_CYCLIC` is degenerate AND R08 clears the matched null: the kill was a false negative.
  This does NOT make R08 a champion; it makes it a lead requiring season-stability and
  walk-forward tests before it is ranked. Say exactly that and no more.
- If `N_CYCLIC` is degenerate AND R08 fails the matched null: the kill was RIGHT FOR THE
  WRONG REASON. Report both halves.
- If `N_CYCLIC` detects the planted signal here: D108's degeneracy does not generalise to
  this cell, and the kill stands. Report that D108 is narrower than assumed.

---

## 7. STOP CONDITIONS

- Partition assertion fails -> HALT.
- D097 reproduction fails -> HALT the D097 arm, report as defect, continue the sweep.
- A team-level response fails `A_SUM_IDENTITY` at >1% -> that response is dropped.
- Every null used in a reported verdict must carry a passing injection result. A verdict
  without one is not published.

## 8. WHAT WOULD FALSIFY H1 (the level-artefact hypothesis)

If the eligible team/matchup-level candidates, re-measured at team-game level against a
level-matched reference and an injection-verified level-matched null, fail at team level too
-- and the team-level nulls demonstrably CAN detect effects of the relevant size -- then the
dilution story is refuted for those candidates and the negative record survives the D111
challenge. That is the outcome I expect and it will be reported as the headline if it occurs.

## 9. ANCHOR REPRODUCTION (required before new statistics)

From `E1_I0033_aggregation_level/which_level_wins.csv`, the D111 bottom-up penalties are
recomputed as `NORM_MAE_advantage_TEAM_over_PLAYER / MAE_LEVEL_TEAM_<q>` and must equal the
published D111 figures:

| quantity | cell | recomputed | published |
|---|---|---|---|
| fga | P10 | 2.327457668389231 / 4.697728525077772 = **0.4954** | 49.6% |
| pts | P09 | 2.311266851851397 / 8.480207422893590 = **0.2726** | 27.3% |
| reb | P13 | 0.691716188228001 / 4.399947628617945 = **0.1572** | 15.7% |
| ast | P14 | 0.354172081374060 / 3.232950478458267 = **0.1096** | 11.0% |
| fta | P11 | 0.354282250315851 / 4.867416090380144 = **0.0728** |  7.3% |
| ftm | P12 | 0.276936862413650 / 4.220232142762853 = **0.0656** |  6.6% |

All six reproduce. This is the anchor. A second anchor -- D097's `dr2 = 0.006488` -- is
reproduced from raw data in section 6 step 1.

## 10. WHAT THIS SCREEN WILL NOT DO

- Not fit a champion. Not propose a production change. Not enact one.
- Not resurrect a ceiling kill.
- Not quote a cross-level dR2 comparison.
- Not read 2025 or 2026 data.
- Not report a p without its null_mean and null_sd.
- Not report a verdict from a null that has not detected a planted signal.
