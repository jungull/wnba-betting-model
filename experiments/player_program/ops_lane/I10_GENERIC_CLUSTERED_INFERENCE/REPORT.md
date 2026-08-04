# I10_GENERIC_CLUSTERED_INFERENCE — game-clustered bootstrap and interval utilities

**Node:** I10_GENERIC_CLUSTERED_INFERENCE | **Lane:** operations | **Type:** implementation
**Date:** 2026-08-04 | **Worktree:** player-model-program

## Epistemic status

> INFRASTRUCTURE. Utilities in an isolated namespace. Shared adoption requires a separate review node; nothing here amends a shared contract.

That line bounds what this node may be cited for. Nothing below authorises the use of these
utilities in a gate invocation, a Stage 2B result, or a promotion decision. Adoption is a separate
review.

---

## What was built

Five files, all inside this node's directory and nowhere else:

| file | role |
|---|---|
| `clustered_inference.py` | the library. sha256 `860f85769db6eccb8bee6c83173007b46309c1807f51cad886abcb611c81d6ed` |
| `measure.py` | binds the library to the real universe and to a synthetic ground truth; writes MEASUREMENTS.json |
| `MEASUREMENTS.json` | every number in this report, machine-readable |
| `TESTS.py` | 85 checks across 17 tests; `main()` returns 1 on failure |
| `REPORT.md` | this file |

The library provides: `build_cluster_index`, `assert_clusters_not_split`, `draw_cluster_ids`,
`rows_for_cluster_draw`, `cluster_bootstrap`, `cluster_jackknife`, `cluster_robust_se_mean`,
`mean_of`, `paired_mean_difference`, percentile / basic / normal / BCa intervals,
`uncertainty_slot` and `bootstrap_receipt`.

**The design decision that matters.** A `ClusterIndex` stores rows as contiguous per-cluster
blocks and every resampling routine addresses clusters BY BLOCK. There is no index arithmetic
anywhere in the module that can express half a game. "Never split a game" is therefore structural
here, not a convention someone has to remember.

---

## What was measured

Every number below was produced by:

    cd experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE
    python measure.py          # writes MEASUREMENTS.json
    python TESTS.py            # 85 checks, PASS

Environment measured at run time: Python 3.13.14, numpy 2.5.1, pandas 3.0.5
(MEASUREMENTS.json -> real.real_bootstrap.library_versions).

### 1. The 2,982 / 1,491 distinction — honoured and reported

`possession_features.load_universe()` was read READ-ONLY; `sys.dont_write_bytecode` is set in both
scripts so importing shared modules leaves no .pyc outside this node.

| quantity | value | key in MEASUREMENTS.json |
|---|---|---|
| team-game rows | **2,982** | `real.rows_vs_clusters.team_game_rows` |
| game clusters | **1,491** | `real.rows_vs_clusters.game_clusters` |
| rows per cluster | `{2: 1491}` — every game has exactly two rows, none has one or three | `real.cluster_index.rows_per_cluster` |
| row-universe digest | `raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371` | `real.row_universe_digest` |
| cluster-membership digest | `de0f8e5a2575dc7920e6358553861323281c9b8b9a3b3f5a72fc1aa2b5ca4545` | `real.cluster_index.membership_digest` |

`ClusterIndex.describe()` always emits BOTH counts; `TESTS.py::test_A2_real_universe` fails if
either drifts from 2,982 / 1,491, if any game stops having exactly two rows, or if the frozen
row-universe digest moves.

The 2,982 is 8 rows / 4 games short of the 2,990 / 1,495 in
projected_exposure_v1/team_possession_prior_v1.parquet. Measured directly with a one-liner that
reads that parquet and filters `pace_resolved == False`:

    -> 2990 rows, 1495 games total; 8 unresolved rows over 4 games:
       1022100001, 1022100002, 1022100003, 1022100004

Those four are the FIRST FOUR GAMES OF 2021 — contiguous season openers, not a scatter. That
matches the D10 ledger note. Recorded because the exclusion is therefore not neutral with respect
to the cold-start stratum; see Contradictions.

### 2. Games are never split across a bootstrap draw — measured, not asserted

The check is an equality, run over every drawn cluster of every draw:

> for every draw b and every game g:  rows(g) present in draw b  ==  (times g was drawn) * size(g)

| what | value | key |
|---|---|---|
| draws checked on the real universe | 500 | `real.whole_cluster_integrity.draws_checked` |
| violations | **0** | `real.whole_cluster_integrity.violations` |
| distinct clusters per draw (min / mean / max) | 907 / 942.82 / 984 | `real.whole_cluster_integrity.distinct_clusters_per_draw` |
| theoretical (1 - 1/e) * 1491 | 942.49 | same key |

`TESTS.py::test_A1_whole_clusters_only` repeats this on a deliberately RAGGED fixture (cluster
sizes 3, 1, 2, 2 — a uniform size-2 fixture would hide off-by-one bugs) over 400 draws, and adds
two independent forms of the same check: every non-zero per-cluster count is an exact multiple of
that cluster's size, and the drawn row multiset is reconstructible from cluster multiplicities
alone. `test_A1_jackknife_deletes_whole_clusters` proves the same for the jackknife: the deletion
unit is the cluster, so BCa acceleration and the resampling unit agree. A delete-one-ROW jackknife
is not offered by this module at all.

### 3. No partition splits a game

`assert_clusters_not_split` was run against every partition the program actually uses.

| partition | clusters split | key |
|---|---|---|
| season | 0 | `real.partitions.season` |
| season_type | 0 | `real.partitions.season_type` |
| game_date | 0 | `real.partitions.game_date` |
| each of the 5 chronological folds, train vs test | 0 | `real.partitions.chronological_folds` |
| pace_level | **37** — guard RAISED | `real.partitions.pace_level` |
| pace_source | **37** — guard RAISED | `real.partitions.pace_source` |

Fold structure, with cluster counts alongside the row counts (the program's own documents report
these folds in rows only):

| fold | test season | cutoff | train rows / clusters | test rows / clusters |
|---|---|---|---|---|
| train_lt_2022 | 2022 | 2022-05-06 | 410 / 205 | 478 / 239 |
| train_lt_2023 | 2023 | 2023-05-19 | 888 / 444 | 520 / 260 |
| train_lt_2024 | 2024 | 2024-05-14 | 1408 / 704 | 524 / 262 |
| train_lt_2025 | 2025 | 2025-05-16 | 1932 / 966 | 620 / 310 |
| train_lt_2026 | 2026 | 2026-05-08 | 2552 / 1276 | 430 / 215 |

Train/test row overlap is 0 in every fold. The five test folds cover 2,572 of the 2,982 rows;
**410 rows over 205 game clusters (all of 2021) are in no test fold**, because the earliest season
can never be a test season under an expanding window
(`real.partitions.rows_never_in_any_test_fold`). Reported so a reader who sums the test folds and
gets 2,572 does not read the shortfall as missing data.

### 4. The price of clustering, measured on the real universe

Intraclass correlation across the two rows of a game (one-way ANOVA; for size-2 clusters the
design effect of a mean is 1 + icc). Key: `real.within_game_structure.columns`.

| column | icc | implied design effect |
|---|---|---|
| realised_team_off_possessions_reg_equiv (the primary target) | **0.9547** | 1.9547 |
| projected_team_off_possessions (the frozen incumbent offset) | **1.0000** | 2.0000 |
| log_projected_team_off_possessions | 1.0000 | 2.0000 |
| pace_evidence_depth | 0.8182 | 1.8182 |
| team_pace_estimate | 0.1980 | 1.1980 |
| pace_gap | **-1.0000** | 0.0000 |

Analytic CR1 cluster-robust SE of the mean against the naive row-iid SE
(`real.design_effect_on_target_column`, `real.design_effect_on_pace_gap`):

| column | mean | CR1 clustered SE | naive iid SE | variance design effect | SE inflation |
|---|---|---|---|---|---|
| target | 79.28758 | 0.100073 | 0.071566 | **1.9553** | **1.3983x** |
| pace_gap | 0.0 exactly | **0.0 exactly** | 0.046464 | 0.0 | 0.0 |

Two readings, both consequential, both directions of the same point:

* On the PRIMARY POSSESSION TARGET, a row-level iid interval is too narrow by a factor of
  **1.398**. The effective sample size for a mean is essentially the 1,491 games, not the 2,982
  rows. "2,982 vs 1,491" is not bookkeeping; it is a ~40% understatement of every row-iid width.
* On pace_gap the failure runs the other way and is worse in kind. pace_gap is exactly
  antisymmetric within a game (team A's value is the negative of team B's), so its within-game
  sum is exactly zero for all 1,491 games, its mean is exactly 0, and its clustered SE is exactly
  0. The naive iid SE of 0.046464 is ENTIRELY an artefact of treating the two halves of one game
  as independent. A row-iid test on an antisymmetric column of this universe tests nothing.

projected_team_off_possessions has icc exactly 1.0 — the frozen incumbent projection is identical
for both teams of a game. Consistent with the packet's "games_with_one_shared_projection"
framing; I verified it as an icc rather than reading it.

### 5. The bootstrap on the real cluster structure

Statistic: mean(realised_team_off_possessions_reg_equiv). This is a DESCRIPTIVE statistic of an
observed outcome column. No prediction column is contrasted with an outcome anywhere in this node;
no arm is fitted, scored or compared. Key: `real.real_bootstrap`.

| quantity | value |
|---|---|
| estimate | 79.287577 |
| bootstrap SE (2,000 draws, seed 20260804) | 0.100179 |
| analytic CR1 SE | 0.100073 |
| ratio bootstrap / analytic | **1.00105** |
| bootstrap bias | -0.001318 |
| 95% percentile CI | [79.09854, 79.48313] |
| 95% basic CI | [79.09203, 79.47662] |
| 95% normal CI | [79.09123, 79.48392] |
| 95% BCa CI (cluster jackknife) | [79.10147, 79.48726] |

The bootstrap SE and the analytic sandwich SE are two independent routes to the same number and
agree to 0.1%. Neither is trusted alone.

Season-stratified variant (clusters resampled within season; 205/239/260/262/310/215 clusters per
season, 500 draws): SE 0.094742, 95% percentile CI [79.10885, 79.47651] (`real.season_stratified`).

Draw-count sensitivity (`real.draw_count_sensitivity`, seed 20260804): SE at
250/500/1000/2000/4000 draws = 0.09808 / 0.10121 / 0.10308 / 0.10018 / 0.09917; interval width =
0.3740 / 0.3751 / 0.3900 / 0.3846 / 0.3808. The SE settles to within ~3% by 500 draws; the
percentile ENDPOINTS are still moving in the third decimal at 4,000. Consequence for any consumer:
do not quote a bootstrap endpoint to more digits than the draw count supports.

### 6. Coverage — synthetic only, because it cannot be done on real data

The true value of a real quantity is unobservable, so coverage is measured against a KNOWN
parameter on data shaped like the real universe: y[g,i] = 0 + u[g] + e[g,i], 1,491 clusters x 2
rows = 2,982 rows, 400 simulations x 400 bootstrap draws, seed 424242
(`synthetic_coverage_icc_0p6`). Monte-Carlo SE of a coverage estimate: 0.0109.

| interval, nominal 95% | coverage | mean width |
|---|---|---|
| game-clustered percentile bootstrap | **0.9350** | 0.08957 |
| row-level iid bootstrap | 0.8525 | 0.07081 |
| row-level iid normal | 0.8725 | 0.07177 |

Negative control at icc ~ 0 (600 clusters x 2, 300 sims, seed 99001, `synthetic_coverage_icc_0`):

| interval | coverage | mean width |
|---|---|---|
| game-clustered percentile | 0.9367 | 0.11178 |
| row-level iid bootstrap | 0.9400 | 0.11211 |
| row-level iid normal | 0.9433 | 0.11317 |

The control is what makes the first table mean something: the clustered interval is NOT merely
wider by construction. With no intra-cluster correlation it is indistinguishable from the iid
interval (widths 0.11178 vs 0.11211). The 8-10 point coverage deficit in the first table is
therefore attributable to clustering, not to conservatism.

Stated against myself: the clustered interval covers at **0.935, not 0.950** — 1.4 Monte-Carlo SEs
low. A 400-draw percentile bootstrap is mildly liberal. I did not chase this to nominal, and a
consumer should not present 0.935 as if it were 0.950.

### 7. Reproducibility

Replicate b comes from numpy.random.SeedSequence(seed).spawn(n_draws)[b], so it is a function of
(seed, b) and nothing else. Measured (`real.reproducibility`):

| claim | result |
|---|---|
| same seed -> identical draw digest | true |
| same seed -> bitwise-identical replicates | true (max abs difference **0.0**) |
| prefix stability: first 250 of a 2,000-draw run == a 250-draw run | true, bitwise |
| different seed -> different draws | true (SE 0.09866 vs 0.10018) |

Draw digest for the headline run:
`e8f67420ecd8898bca623844f28e812ae14bb537e90b40383f54569970272b3b` (sha256 over the drawn
cluster-id matrix). A reproduction claim is checkable against that byte string rather than against
a promise. `bootstrap_receipt` carries the seed, draw count, row and cluster counts, both digests,
the module sha256 and the library versions.

`seed` is a REQUIRED KEYWORD-ONLY argument — `TESTS.py::test_A3_seed_is_required` fails if a
default ever appears. An inference utility with a default seed invites a silently irreproducible
number.

`TESTS.py::test_measurements_are_current` fails if MEASUREMENTS.json was produced by a different
version of clustered_inference.py than the one on disk, so the numbers in this report cannot
silently go stale relative to the code.

### 8. Task isolation, and the one place this touches a shared object

* clustered_inference.py imports NOTHING from the program — only stdlib, numpy, pandas.
  `TESTS.py::test_A4_isolated_namespace` greps the module source and fails if
  possession_features, comparison_gate, feature_gate, gate_invocation, receipt_integrity,
  construction_receipt or PROGRAM_STATE is ever imported into it, and fails if either script so
  much as names the forbidden sealed-results directory.
* Only measure.py and TESTS.py touch program modules, read-only, with
  `sys.dont_write_bytecode = True` so no .pyc is written outside this node. Verified: no file in
  experiments/player_program/__pycache__/ has a modification time from this session.
* `uncertainty_slot()` emits {"se", "ci", "ci_level", "method"} — the input shape
  `comparison_gate.uncertainty_block` ALREADY PUBLISHES.
  `TESTS.py::test_A4_slot_fits_the_published_gate_shape` feeds a slot into the real frozen
  comparison_gate.uncertainty_block, asserts it is parsed with supplied == True and identical
  numbers, asserts the two unsupplied contrasts are still reported as "unknown, not zero", and
  RE-HASHES comparison_gate.py before and after to prove the frozen bytes did not change.
  Conforming to a published input shape is not amending it. No gate dimension, threshold or
  decision rule is added, removed or altered.
* Writes: exactly five files, all under
  experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE/. No mutating git command
  was run.

---

## What I could NOT establish

1. **Real-data coverage.** The true value of any real quantity is unobservable, so the
   0.935 / 0.8525 comparison is synthetic. It transfers to the real universe only to the extent
   the DGP shape (1,491 clusters x 2 rows, icc 0.6) resembles it — and the real target icc is
   0.9547, HIGHER than the simulated 0.6, so the real penalty for row-iid inference is plausibly
   larger than the synthetic table shows. I did not simulate at icc 0.95, so that is a direction,
   not a measurement.
2. **Coverage for anything other than a mean.** Every coverage number here is for a sample mean
   (and by extension a paired mean difference — a mean of per-row differences). I did NOT measure
   coverage for a quantile, a fitted coefficient, a refit-per-replicate metric, or any non-smooth
   statistic. cluster_bootstrap accepts an arbitrary row-position callable, so it RUNS for those;
   nothing here says its interval is calibrated for them.
3. **Whether the game is the right cluster level.** I measured game-level clustering only. Whether
   a further shared shock exists at the date level (all games on one night), the team-season level,
   or the referee-crew level is unmeasured. If any exists, game-level clustering is still too
   narrow. A real open question, not a formality.
4. **The draw count needed for a stable percentile endpoint.** The SE stabilises by ~500 draws;
   the endpoints had not stabilised to the third decimal by 4,000. I did not determine where they
   do.
5. **BCa behaviour under a degenerate bias-correction.** bca_ci raises rather than returning a
   number when the proportion of replicates below the estimate is 0 or 1. I constructed no real
   case that triggers it and cannot say how often it would fire in practice.
6. **Anything about performance.** No arm, challenger, incumbent metric or comparative result was
   computed, read, or inferred. The sealed Stage 2B results directory was never opened.
7. **Whether these utilities should be adopted.** Out of scope by the epistemic status. This node
   builds and validates; it does not admit.

---

## Contradictions found

1. **1,491 vs 1,495 game clusters, again.** The possession inference universe is 1,491 games /
   2,982 rows; team_possession_prior_v1.parquet, EVENT_SOURCE_INVENTORY.json (universe.games =
   1495) and master_team all carry 1,495 games / 2,990 rows. Already recorded by D10 and by
   V2_STOP_CONDITION.json -> not_stop_conditions_but_recorded ->
   packet_nits_flagged_not_corrected. I re-measured rather than cited: the gap is exactly 8 rows
   / 4 games, all pace_resolved == False, game_ids 1022100001-1022100004. NEW DETAIL: those four
   are the contiguous first four games of 2021, so the exclusion is concentrated on precisely the
   cold-start stratum S6 identifies as carrying 42% bias-share of MSE. I did not resolve this and
   it is not mine to resolve.
2. **No contradiction found between the frozen bytes and any document I checked.** The digest
   raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371 reproduces exactly from the
   artifacts as they stand today.

---

## Things I believe touch a stop condition — raised, not resolved

The node stop condition is: a finding that would change the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set or the leakage status —
HALT and raise, do not resolve it inside the node. Three findings plausibly bear on INFERENCE
STRUCTURE and K0_MATCHED. I implemented nothing in response to any of them and changed no shared
object.

**R1 — pace_level and pace_source are ROW-level, not game-level: 37 games disagree with
themselves.** assert_clusters_not_split raised on both, naming 37 of 1,491 games whose two team
rows carry different tier values (e.g. game 1022100015 -> pace_level 1 and 3; 1022200015 -> 1 and
2). Consequence for inference: THE PACE TIER IS NOT A LEGAL STRATIFICATION VARIABLE FOR A
GAME-CLUSTERED BOOTSTRAP, because stratifying on it would require splitting those 37 games. This
bears directly on S6 (whether K0_MATCHED carries the tier structure) and S7 (per-fold tier
degeneracy on the control): if the authoritative control is tier-structured, any game-clustered
interval around it must decide what to do with 37 self-inconsistent games, and the existing
documents do not say. Measured, reported, not resolved.
Keys: `real.partitions.pace_level`, `real.partitions.pace_source`.

**R2 — the incumbent offset has intraclass correlation exactly 1.0.** Both team rows of every game
carry an identical projected_team_off_possessions. Any statistic that is a function of the offset
alone has an effective sample size of 1,491, not 2,982 — exactly, not approximately. This is the
same structural fact S5 records as own_est + opp_est == 2 * projected with max absolute deviation
0.0 over 2,982 rows, seen from the variance side. A fact about the inference structure; raised,
not acted on.

**R3 — antisymmetric columns have an exactly-zero clustered SE.** pace_gap has icc -1.0, mean
exactly 0.0 and CR1 SE exactly 0.0, against a naive iid SE of 0.046464. Any existing or future
row-iid uncertainty statement about an own-minus-opponent quantity on this universe is not merely
too narrow — it is measuring a quantity with no variation at the resampling unit. I do not know
whether any such statement exists in the program; I did not audit for one, because auditing
challenger-side statements would be performance peeking.

None of R1-R3 changes the primary target, the candidate universe, the cutoff-valid feature set or
the leakage status as far as I can determine.

## Escalation to the possession lane

R1 and R2 should be routed to whichever node owns K0_MATCHED construction (the S6/S9 thread) and
to the fold-level fallback required by GATE_INVOCATION_CONTRACT section 4 (the S7 thread). They
are raised here as measurements only. R3 and the cold-start concentration of the four excluded
games (contradiction 1) belong in the same packet.

## Validation

    python experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE/TESTS.py
    -> clustered inference: 85 checks across 17 tests
    -> PASS
