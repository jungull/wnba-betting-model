# P22_POSTGAME_SURROGATE_GUARD — S1: enforced invariant against current-game outcome-derived columns

**Node:** `P22_POSTGAME_SURROGATE_GUARD`  ·  **Lane:** possession  ·  **Type:** implementation
**Spec version:** `P22_POSTGAME_SURROGATE_GUARD_v1`
**Status:** `LANDED` — not `VERIFIED`. A separate verifier context validates this; I do not mark my own work accepted.

## Epistemic status of this output

> INFRASTRUCTURE + task-specific INVARIANT. Establishes that a prohibited column cannot silently enter a prediction frame. Establishes nothing about any candidate's accuracy.

---

## 1. What S1 asked for, and what this node delivers

`stage2a/V2_STOP_CONDITION.json` -> `findings.S1_master_team_minutes_is_an_exact_overtime_indicator`
states the consequence in one sentence:

> "A convention is not enough; this needs an enforced invariant."

This node is that invariant, implemented as a **Stage 2 call-site wrapper**:

| file | role |
|---|---|
| `postgame_surrogate_guard.py` | the enforced invariant — declaration layer, empirical lag re-derivation, dependency battery, receipt emission, receipt verification |
| `TESTS.py` | 73 checks, all passing, exit 0. Every number in this report is produced by it |
| `MEASUREMENTS.json` | machine-readable output of the test run |
| `receipts/EXEMPLAR_LAGGED_DURATION_RECEIPT.json` | a real `construction_receipt/1` whose transformation block IS the lag record |

`feature_gate.py` is **not modified**. Nothing outside this node's directory is written.

**Runner:** `python experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/TESTS.py` -> `ALL CHECKS PASSED`, exit `0`, 73 `[PASS]`, 0 `[FAIL]`.

---

## 2. Measurements — every number, with the command that produced it

All measurements come from one run of `TESTS.py` against the frozen artifacts
(`data/masters/master_team.parquet`, `experiments/player_program/possessions_v2/possessions_raw_v2.parquet`,
`experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet`) and are
written to `MEASUREMENTS.json`. Section names below are the section headings `TESTS.py` prints.

### 2.1 Re-derivation of S1 — AGREES on every figure

`TESTS.py::section_m1`, key `MEASURED["S1"]`.

| S1 packet claim | packet value | re-derived | verdict |
|---|---|---|---|
| `rows` | 2990 | **2990** | AGREES |
| `nulls` | 0 | **0** | AGREES |
| `minutes_over_game_minutes.mean` | 5.0 | **5.0** | AGREES |
| `minutes_over_game_minutes.sd` | 0.0 | **0.0** | AGREES |
| `minutes_over_game_minutes.min / max` | 5.0 / 5.0 | **5.0 / 5.0** | AGREES |
| `exactly_5x_game_minutes` | 2990/2990 | **2990/2990** | AGREES |
| `game_minutes_recoverable_by_division` | 2990/2990 | **2990/2990** | AGREES |

Not in the packet, measured here: `master_team.minutes` takes exactly four values
`{200.0, 225.0, 250.0, 300.0}`; `game_minutes` takes exactly `{40.0, 45.0, 50.0, 60.0}`. The
identity is a bijection on four levels, not an approximate relation.

`game_minutes` is defined here exactly as the pipeline defines it —
`40 + 5 * max(0, max_period - 4)`, mirrored from
`possession_features._realised_offensive_possessions` (line 210). A guard that used a different
definition of the prohibited quantity than the pipeline uses would be guarding a different thing.

### 2.2 Universe — AGREES with the brief

`TESTS.py::section_m1`, key `MEASURED["universe"]`.

* **2,982** team-game rows over **1,491** game clusters (`possession_features.load_universe`, after
  the `pace_resolved` restriction).
* `master_team.minutes` joins 1:1 onto **2,982 of 2,982** rows.
* The 5x identity holds on **2,982 of 2,982** audited rows, not only on master_team's own 2,990.
* Chronological folds (`possession_features.chronological_folds`): `train_lt_2022` 410,
  `train_lt_2023` 888, `train_lt_2024` 1408, `train_lt_2025` 1932, `train_lt_2026` 2552 training rows.

### 2.3 Period structure — a packet nit confirmed, and a corroboration

`TESTS.py::section_m1`, key `MEASURED["period_structure"]`.

* Games in `possessions_raw_v2`: **1,495**. Games in the audited universe: **1,491**. This is
  precisely the four-game gap the frozen packet already records under
  `packet_nits_flagged_not_corrected`. AGREES — no new discrepancy.
* `max_period` distribution: `{4: 1429, 5: 60, 6: 5, 8: 1}`. There is **no 7-period game**: the
  distribution jumps from 6 to 8. The single 8-period (four-overtime) game is
  `game_id 1022600142`, season 2026.
* That game is **independently corroborated**: `master_team` records 300.0 minutes on exactly the
  two rows of that game, and 300 = 5 x 60. Two artifacts, built by different producers, agree the
  game had eight periods. This strengthens S1's identity claim rather than qualifying it.

### 2.4 The gap — feature_gate.audit passes every prohibited form

`TESTS.py::section_m2`, key `MEASURED["feature_gate_blindness"]`. Each row is
`feature_gate.audit(F, FEATURE_NAMES + [col], offset=..., target=..., test_df=...)` — every
optional argument that section 3.1 of `GATE_INVOCATION_CONTRACT.md` makes mandatory was supplied.

| candidate column | gate verdict | findings | corr w/ target | corr w/ offset | std | nulls |
|---|---|---|---|---|---|---|
| `master_team.minutes` (raw) | **passed** | `[]` | -0.020350 | -0.002952 | 6.222130 | 0 |
| `minutes / 5` | **passed** | `[]` | -0.020350 | -0.002952 | 1.244426 | 0 |
| `minutes` renamed `team_tempo_index` | **passed** | `[]` | -0.020350 | -0.002952 | 6.222130 | 0 |
| `3 * minutes - 17.5` | **passed** | `[]` | -0.020350 | -0.002952 | 18.666390 | 0 |
| `exp(minutes / 100)` | **passed** | `[]` | -0.019632 | -0.004234 | 0.592146 | 0 |
| raw `game_minutes` | **passed** | `[]` | -0.020350 | -0.002952 | 1.244426 | 0 |

Gate thresholds are `target_corr_threshold = 0.98` and `corr_threshold = 0.999`. The observed
correlations are **two orders of magnitude** below them. The design is full rank (5 of 5,
condition 3.23). There are no nulls, so no missingness branch can fire.

**This is not a defect in `feature_gate.py`.** Section 7.3 of `GATE_INVOCATION_CONTRACT.md` states
the limitation in advance: a post-cutoff-derived column whose values do not correlate above
threshold with the target *passes*, and cutoff validity "remains a registration obligation and a
producer obligation". The gate has two comparands — target and offset. It has no third. The
wrapper supplies one: the **prohibited basis**.

### 2.5 The prohibited basis

Four mutually-determining parameterisations of one quantity, built per row from the frozen
possessions artifact (`postgame_surrogate_guard.realised_duration_basis`):

| quantity | level supports on the 2,982 audited rows |
|---|---|
| `game_minutes` | 40 -> 2850, 45 -> 120, 50 -> 10, 60 -> 2 |
| `overtime_periods` | 0 -> 2850, 1 -> 120, 2 -> 10, 4 -> 2 |
| `is_overtime` | 0 -> 2850, 1 -> 132 |
| `team_minutes` (= `master_team.minutes`) | 200 -> 2850, 225 -> 120, 250 -> 10, 300 -> 2 |

A basis quantity with fewer than two levels on the audited rows is recorded as
`prohibited_basis_degenerate` (blocking) and **no verdict is issued against it**. Measured: every
one of the five chronological training folds carries overtime variation (32 / 56 / 78 / 98 / 114
overtime rows), so no fold is degenerate in this program's actual data.

### 2.6 Acceptance criteria — all seven discharged

`TESTS.py`, sections `A1`-`A7`. `->` lists the guard's blocking finding kinds.

| # | criterion | section | result |
|---|---|---|---|
| 1 | unlagged `master_team.minutes` FAILS | `A1` | **BLOCKED** -> `same_game_join`, `function_of_prohibited`, `prohibited_recoverable`, `exact_affine_of_prohibited`, `prohibited_exact_affine_of_column` |
| 2 | `minutes/5` FAILS | `A2` | **BLOCKED** -> `lag_alignment_violated`, `function_of_prohibited`, `prohibited_recoverable`, both affine kinds. Recovery of `game_minutes` is affine with slope **1.0** and relative max residual **0.0** |
| 3 | a renamed or linearly transformed current-game duration FAILS | `A3` | **BLOCKED** for `team_tempo_index` (rename), `3*minutes-17.5` (affine, recovered at slope 2.9999999999999973, intercept -17.49999999999943), `exp(minutes/100)` (nonlinear injective) and raw `game_minutes` |
| 4 | a correctly lagged prior-game duration PASSES when every cutoff check passes | `A4` | **PASSES** on the final assembled design and in all five training folds |
| 5 | same-game joins fail closed | `A5` | **8 independent routes, all block** |
| 6 | construction receipts record the lag transformation and the source keys | `A6` | **recorded, digest-bound, re-verified** — with one measured defect, section 4.1 |
| 7 | `feature_gate.py` byte-unchanged | `A7` | sha256 `b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7`, unchanged |

**Criterion 3 in detail.** The strongest check is `function_of_prohibited`: the column is constant
within every level of a prohibited quantity. This is invariant to **any injective
reparameterisation** of the column, so a rename, a rescale, a unit change, a nonlinear monotone map
and an arbitrary relabelling all fail identically. The affine tests are cardinality-free and catch
a continuous linear transform without a partition argument. Measured contrast, on `exp(minutes/100)`:
`column_exact_affine_of_prohibited = false` (the nonlinear map defeats affine recovery) while
`column_is_function_of_prohibited = true` and `prohibited_is_function_of_column = true` (the
partition test is untouched). Neither check alone is sufficient; both are implemented.

**Criterion 4 in detail.** `prior_game_minutes` = the club's most recent **strictly earlier**
game's duration, keyed on `team_id`, ordered by `game_date`, `n_back = 1`.

* The `PRIOR_GAME` claim was **re-derived from the declared source** and compared value-for-value:
  2,982 rows, 15 expected nulls, 15 presented nulls, **0 rows disagreeing**.
* It is **not** a function of the current game's duration: only **2 of 4** prohibited levels carry
  a varying column — which by itself would not clear the test — and **3 of 4** column levels carry
  a varying prohibited value, so the partition does not refine in either direction.
* `pearson_r = -0.001806` against `game_minutes`.
* `guarded_audit` (guard **then** `feature_gate.audit`) passes end to end on the **2,967**
  complete-case rows. The 15 first-appearance rows are **dropped, not imputed**: imputing them
  would be an undeclared transformation, which `GATE_INVOCATION_CONTRACT.md` section 8a forbids,
  and would break the lag re-derivation — the correct behaviour, exercised by route A5(c).
* Per fold: `train_lt_2022` (410 rows, 32 OT), `train_lt_2023` (888, 56), `train_lt_2024`
  (1408, 78), `train_lt_2025` (1932, 98), `train_lt_2026` (2552, 114) — the lagged column passes
  in every one and `master_team.minutes` is blocked in every one, per
  `GATE_INVOCATION_CONTRACT.md` section 1.

**Criterion 5 in detail — the eight routes, all blocking.**

| route | scenario | blocking kind |
|---|---|---|
| a | column declared with **no** `LagSpec` | `lag_specification_absent` |
| b | honestly declared `SAME_GAME` | `same_game_join` |
| c | same-game values **mislabelled** `PRIOR_GAME` | `lag_alignment_violated` (2,982 of 2,982 rows disagree with the re-derivation) |
| d | `PRIOR_GAME` with `strict_inequality = False` | `same_game_join` — a non-strict window admits the row's own game, so it blocks at the declaration layer before any bytes are read |
| e | `PRIOR_GAME` with no source to re-derive from | `lag_unverifiable` |
| f | `prohibited = None` | `prohibited_basis_absent` |
| g | basis not aligned row-for-row with the frame | `prohibited_basis_misaligned` |
| h | `guarded_audit` on a prohibited frame | raises **before** `feature_gate` sees the design, so no clean gate record is ever produced for a prohibited frame |

Route (c) is the load-bearing one. A caller who declares a clean lag and supplies dirty values is
caught by the bytes, not by the declaration.

### 2.7 Negative results — preserved, not manufactured into positives

`TESTS.py::section_no_false_positive` (`N1`) and `::section_scan` (`N2`).

* **The guard does not fire on the frozen incumbent-equivalent feature set.** `pace_gap`,
  `pace_evidence_depth`, `opp_pace_evidence_depth`, `is_playoff_game`: `passed = true`, zero
  blocking findings. Largest |r| against any prohibited quantity across all four features:
  **0.060192** (`is_playoff_game` vs `game_minutes`; 0.067350 vs `is_overtime`).
* **`pace_gap` has r = exactly 0.0 against every prohibited quantity.** This is a structural
  artifact, not evidence of independence: the two rows of a game carry exactly negated `pace_gap`
  and identical `game_minutes`, so the covariance cancels by antisymmetry. Stated so that the zero
  is not later cited as an independence result.
* **Sweep of the frozen prior artifact:** 5 numeric columns checked (1 constant, `pace_resolved`);
  **0 block**. There is no duration surrogate in the current feature source.
* **Sweep of `master_team`:** 51 numeric columns checked on the audited universe (1 constant,
  `in_misc`); **exactly one blocks — `minutes`**. Within `master_team`, S1's naming of `minutes` is
  **complete**: there is no second, unnamed duration surrogate in that artifact. This is a
  strengthening of S1, not a correction of it.

---

## 3. What I could NOT establish, and why

1. **That the guard catches a non-exact, nonlinear near-surrogate.** The battery is an **exact**
   dependency guard plus one correlation threshold at |r| >= 0.999. A column of the form
   `f(game_minutes) + noise` with a nonlinear `f` and enough noise to break both the partition
   tests and the linear correlation would pass. I did not construct one and did not measure the
   boundary. This is the same open gap `GATE_INVOCATION_CONTRACT.md` section 7.1 records for
   `feature_gate.py`, one comparand over. It is not closed here and must not be reported as closed.

2. **That `prior_game_minutes` is cutoff-valid in the operational sense.** The re-derivation proves
   the column equals the club's previous game **within the audited universe**. The eight team-games
   dropped by the `pace_resolved` restriction, and the four games in `possessions_raw_v2` that are
   not in the universe, are not in that history. A team whose true previous game is one of those
   rows carries the game before it instead. I measured that the re-derivation is internally exact
   (0 disagreements); I did **not** establish that the universe-restricted history equals the true
   schedule history. Any arm using this column must state which of the two it means.

3. **That the 8-period game is a real four-overtime game rather than a period-coding artifact.**
   Two independent artifacts agree on eight periods, which is strong, but no play-by-play
   inspection was performed. It affects only the support of the `game_minutes = 60` level (2 rows).

4. **Anything about the other prohibited-outcome surfaces.** S3's `missed_game_*` injury regime
   (5,373 rows), S8's 32 unadjudicated possession columns, S2's join hazards: **not audited here**.
   `is_overtime` happens to be in this guard's basis and is therefore blocked as a feature by
   construction, but `score_diff_offense_start`, `abs_score_diff_start`,
   `non_competitive_conservative` and the rest are `P2A_POSSESSION_COLUMN_ADJUDICATION`'s mandate,
   not this node's. A pass from this guard is **not** a cutoff-validity certificate.

5. **Any comparative performance figure.** None was computed, none was read. Nothing under
   `stage2b/SEALED_RESULTS/` was opened; the directory does not exist in this worktree.

---

## 4. Contradictions found

### 4.1 MEASURED DEFECT — construction_receipt.py records the lag transformation but does not BIND it

`TESTS.py::section_a6`, key `MEASURED["A6_transformation_binding_defect"]`.

`construction_receipt.binding_fields` binds `transformation_digest` — the **stored scalar** — and
`verify_construction_receipt` **never recomputes** `sha256(canonical(transformation))` from the
transformation **body**. Measured, by emitting the exemplar receipt and then editing one field:

```
edit: produced_frame_provenance.transformation.columns.prior_game_minutes.strict_inequality
      true -> false
cr.verify_construction_receipt(...).verified        = True     blocking = []
stored     transformation digest = transformation:sha256=a49c2f53860b16a2...702fd05d
recomputed transformation digest = transformation:sha256=b85904db4d3c6627...6462a1c
```

The two digests differ, and the frozen verifier does not compare them. So the lag declaration
inside an emitted receipt — including the strict-inequality flag that separates a lawful lag from
a same-game join — can be edited in place and the receipt still verifies clean.

**This does not trip a stop condition.** It changes neither the primary target, the K0 structure,
the inference structure, the candidate universe, the cutoff-valid feature set, nor the leakage
status of anything. Under `RESEARCH_CONTRACT_V1` severity rules it is Severity C — "stronger
digest binding" — explicitly listed there as a next-contract-version item.

**I did not edit the frozen module.** The fix is at the call site:
`postgame_surrogate_guard.verify_guard_receipt` delegates to `cr.verify_construction_receipt` and
then recomputes the transformation digest, raising `transformation_body_edited`. Measured:
`guard_verify_verdict = False`, `guard_blocking_kinds = ["transformation_body_edited"]`.
**Acceptance criterion 6 is discharged against `verify_guard_receipt`, not against the unmodified
verifier**, and any consumer of this node's receipts must use it.

### 4.2 Document vs bytes — no contradiction found

* `GATE_INVOCATION_CONTRACT.md` states it was prepared against `feature_gate.py` "as of `55f4500`
  (rank / conditioning) and `42af2cd` (informative missingness)".
  `git log -1 -- experiments/player_program/feature_gate.py` returns
  `42af2cd57effd2d0d46713eb6a1715d9528ef653`, and
  `git status --porcelain -- experiments/player_program/feature_gate.py` returns empty. The
  document and the bytes agree, and the file is unmodified relative to HEAD.
* `feature_gate.BLOCKING` contains exactly the 12 kinds section 3 of the contract enumerates, and
  `RANK_TOL = 1e-8`, `COND_MAX = 1e6` match. No drift.
* The packet's `game_clusters 1491` / `games_with_one_shared_projection 1495` nit reproduces
  exactly. Already recorded in the frozen packet; not a new contradiction.

### 4.3 A wording caveat on S1, not a correction

S1's `consequence` says `master_team.minutes` "must be named an explicitly PROHIBITED column on the
target-game row, and any lagged use must be audited rather than assumed safe." The measured N2
sweep supports a stronger and more useful statement: within `master_team`, `minutes` is the **only**
column of the 51 numeric ones that behaves as a duration surrogate. Naming `minutes` is therefore
*sufficient* for that artifact — but only for that artifact, and only against *this* prohibited
basis. Every one of the other 50 columns remains a realised target-game box-score outcome and is
prohibited for reasons this guard does not test. `possession_features.py` already excludes all of
`master_team` on those grounds (module docstring, lines 68-71). Nothing here weakens that exclusion.

---

## 5. Stop conditions

**None tripped.** Stated plainly:

* No finding here changes the primary target, the K0 structure, the inference structure, the
  candidate universe, the cutoff-valid feature set, or the leakage status.
* S1's leakage status was already declared by the frozen V2 halt packet. This node **implements the
  enforcement S1 asked for**; it does not re-adjudicate S1 and does not extend the prohibition to
  any column S1 did not already cover.
* The one defect found (section 4.1) is Severity C in a shared artifact and is closed at the call
  site without touching the artifact.

---

## 6. Scope compliance

* Wrote only inside `experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/`.
* No git command other than read-only `status` / `log` was run. No `add`, `commit`, `checkout`,
  `stash`.
* No frozen artifact modified. `feature_gate.py` sha256 verified byte-identical by `TESTS.py::A7`
  and re-verified inside `postgame_surrogate_guard.audit` on **every invocation** — a run against a
  changed gate raises `gate_bytes_changed`.
* `stage2b/SEALED_RESULTS/` was not read; it does not exist in this worktree.
* No comparative historical performance of any challenger was inspected or computed.
