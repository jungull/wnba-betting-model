# `contract_baseline_suite_v4` — frozen, split-bound, and implemented

*Registered 2026-08-01, before any output on real data. **No historical OOF, fitted suite
artifact, accuracy figure or coverage score exists or was inspected.** The registry record is
append-only and carries `computed_nothing: true`. The implementation runs on **synthetic data
only** and has no file I/O at all.*

**Supersedes `contract_baseline_suite_v3`.** v1, v2 and v3 records are unmutated and their
documents unedited; supersession is recorded in `project_docs/SPEC_ERRATA.md` and the ledger.

v3 froze the right ideas, but its helpers were **useful primitives, not the registered
pipeline**, and five points let contamination back in through the side door.

---

## 0. What v4 changes

| # | v3 defect | v4 |
|---|---|---|
| 1 | team T1/T2/T3 cut on **team-game rows**, so one game's two rows — and two games on a date — could land in different segments | §1 cut on **distinct dates**, frozen rounding, minimums, degenerate fallback |
| 2 | selection took bare frames; returning disjoint arrays does not make leakage *unrepresentable* | §2 every selection API takes a `SplitContext` and **rejects** non-tuning indices |
| 3 | obligation order unpinned, so tie-breaking depended on input row order | §3 ordered by `(forecast_cutoff, game_id)` within player-season, **fail-closed on ties** |
| 4 | a **constant** residual pool gives `sd = 0` — finite, but the contract requires `> 0` | §4 nonfinite *or* nonpositive sd is **insufficient**, routed to the declared fallback |
| 5 | base rates and fallback means not restricted to the prefix | §5 computed from tuning indices only, through the same guard |

One further defect surfaced while implementing, and is fixed here rather than left latent:

| 6 | conditional-target history ran the EWMA over **all obligations**, so a DNP row's recorded outcome moved the selected conditional α | §6 conditional history is the **active subsequence only** |

**Carried from v3 unchanged:** the common contract layer; the disjoint-calibration principle and
the player 75/25 date split; target-specific masks; candidate-obligation history with
`n_prior_candidate_games` and `n_prior_appearances` recorded separately; the canonical positional
`p_active` feature order; the ordered minutes → attempts → points tuning with the minutes leg held
fixed; both α = 0.30 legacies sensitivity-only and weight-ineligible with the points legacy's
provenance **UNKNOWN**; the 11-point α grid with boundary-reporting; the 13-point λ grid; the
`season:2021` declared constants; and the `1e-6` team-points floor.

---

## 1. Team split on distinct dates

Cutting on **dates**, not rows, is what keeps **both rows of a game** and **every game on a date**
inside exactly one segment. A row-based cut could put one team's outcome in the segment that fits
the other team's calibration map.

| segment | share of distinct training dates | used for |
|---|---|---|
| **T1** | first **50 %** | channel α selection |
| **T2** | next **25 %** | fitting the `str_home` / `str_away` calibration maps |
| **T3** | last **25 %** | dispersion residuals |

**Rounding, frozen:** `n_t3 = floor(n * 0.25)`, `n_t2 = floor(n * 0.25)`,
`n_t1 = n - n_t2 - n_t3` — T1 absorbs the remainder.

**Minimums, frozen:** T1 >= **8** distinct dates, T2 >= **4**, T3 >= **4**.

**Degenerate fallback, frozen:** if any minimum fails, the split is reported `degenerate`, **T2 and
T3 are empty**, and the fold emits the declared constants. It may not borrow segments from
elsewhere or silently proceed.

Player targets keep v3's two-segment date cut: tuning prefix **75 %**, calibration tail **25 %**,
`n_tail = floor(n_dates * 0.25)`, minimums **8** and **4**.

---

## 2. Split-bound selection — leakage is unrepresentable, not merely discouraged

Every selection API takes a `SplitContext` carrying named `tuning_idx`, `calibration_idx` and
`test_idx`, and calls `require_tuning`, which raises `SelectionLeakage` when handed **any** index
outside the tuning segment. A `SplitContext` whose segments overlap **cannot be constructed**.

> **Tuning masks must be a subset of tuning indices.** A mask spanning the whole training frame is
> rejected, not silently intersected.

This is not theoretical tidiness: the guard rejected the **first run of this very pipeline**, which
passed whole-frame masks for the `p_active` base rate and again for team channel-α selection. Under
v3's contract both would have returned a plausible number computed partly on calibration rows.

The team runner exposes two contexts so each stage sees only its own segment: `context_for_alpha()`
(tuning = T1; T2 and T3 forbidden) and `context_for_calibration_map()` (tuning = T2; T1 and T3
forbidden).

---

## 3. Deterministic obligation ordering, fail-closed

Candidate obligations are ordered by **`(player_id, season, forecast_cutoff, game_id)`**, stable
sort. Every shifted feature depends on this order; leaving it to however the frame arrived would
make the pipeline reproducible only by accident.

If two obligations in a player-season share **both** `forecast_cutoff` and `game_id` they are
**indistinguishable**, and `ObligationOrderError` is raised. A missing ordering key raises the
same. Neither is repaired by guessing.

---

## 4. Dispersion fails closed on a degenerate pool

`pred_sd` is the sample sd (`ddof = 1`) of the calibration-segment residuals. It is **insufficient**
— routed to the declared fallback, never emitted — when the pool has fewer than 2 finite residuals,
**or** when the sd is nonfinite, **or** when it is **`<= 0`**.

The last case is the one v3 missed: a **constant** residual pool is perfectly finite and yields
`sd = 0`, which the contract forbids (`pred_sd > 0` on every distribution target). The emitted
contract still requires `pred_sd > 0`; the fallback is what guarantees it.

Empirical quantiles (`numpy.quantile`, `method="linear"`) at >= **200** player / >= **30** team
residuals; Gaussian `z * sd` below that. Truncate to support, **then** monotone-sort.

---

## 5. Prefix-only base rates and fallback means

The `p_active` activity base rate and every target's fallback mean are computed by `prefix_mean`,
which runs the mask through `require_tuning` first. Calibration-tail and outer-test outcomes
therefore **cannot** reach them — enforced, not asserted in prose.

Masks, frozen: `p_active` over **all** candidate obligations in the tuning segment; the three
conditional targets over **active** rows of the tuning segment; team points over **resolved**
team-games.

---

## 6. Conditional history is the active subsequence

The conditional targets are conditional **on activity**, so their history must be the history of
*active* games. v3 ran the EWMA over every obligation, which let a DNP row's recorded outcome (a
zero) move the estimate — and therefore move the selected conditional α. That defeats the
target-specific masks of §5 by a different route.

`active_shifted_ewma` computes the EWMA over the active subsequence only, shifts inside that
subsequence, then carries the value forward to intervening inactive rows. It is strictly as-of — no
row reads its own outcome or any later one — and **inactive outcomes are never read at all**. The
ratio form (`active_shifted_ratio_ewma`) sends a zero denominator to `NaN`, which routes the row to
the declared fallback rather than a silent zero.

`p_active` is unaffected: inactive rows are exactly what it exists to predict, and they do move its
base rate.

---

## 7. The implementation

| file | role |
|---|---|
| `cbs_generator.py` | guarded primitives: `SplitContext`, `player_split`, `team_split`, `order_obligations`, `prefix_mean`, `dispersion`, `active_shifted_ewma`, Stage-A features, standardiser, IRLS logistic, λ and α selection, row emission, exclusion cross-tab |
| `cbs_pipeline.py` | `run_player_fold` and `run_team_fold` — the registered end-to-end pipeline |
| `tests/test_cbs_generator.py` | **123 assertions**, synthetic data only |

**Neither module opens a file.** There is no path argument anywhere; frames arrive from the caller.
The pipeline therefore cannot reach the real contract even by mistake, which is what makes it safe
to run inside the repository gate.

The suite drives every stage — Stage-A features, standardisation, logistic fitting and λ tuning,
target masks and fallback means, ordered α tuning with the minutes leg fixed, team-channel tuning
with T2 map fitting and T3 dispersion, `season:2021` emission, full obligation-row output,
provenance, exclusion cross-tabs — and checks the output with the **real**
`prediction_contract_v2.validate_predictions()`, not a stand-in.

Required negative and invariance tests, all passing:

| id | property |
|---|---|
| N1 | perturbing calibration or outer-test outcomes changes no selected parameter, base rate, fallback mean, or fitted-prefix feature |
| N2 | contaminated selection calls are rejected (α, `prefix_mean`, `require_tuning`, overlapping context construction) |
| N3 | inactive rows move the `p_active` base rate but cannot move conditional tuning or fallbacks |
| N4 | both team rows of a game, and every game on a date, stay in exactly one segment; segments are chronologically ordered and disjoint; the floor rounding holds; short windows are degenerate |
| N5 | zero-candidate and excluded obligations stay visible, every required row is emitted, and an exclusion that perfectly predicts non-appearance raises the outcome-selection alarm |
| N6 | constant, empty, single-value and all-NaN residual pools are insufficient and fall back; a constant-outcome fold still emits `pred_sd > 0` and validates |
| N7 | duplicate and tied obligations fail closed; a missing ordering key fails closed; ordering is invariant to row shuffling |
| N8 | missing obligation rows, `feature_asof == forecast_cutoff`, `pred_sd == 0`, missing provenance and non-monotone quantiles are all **rejected** before any scoring path runs |

---

## 8. Identity

| field | value |
|---|---|
| `arm_id` | `contract_baseline_suite_v4` |
| components | `cbs4_pactive_logistic_histonly`, `cbs4_eminutes_ewma_tuned`, `cbs4_attempts_ratio_ewma_x_minutes`, `cbs4_points_pts36_x_minutes`, `cbs4_teampoints_structural_cal` |
| comparators | `cbs4_pactive_rulegate_comparator`, `cbs4_margin_gaussian_comparator` |
| legacy sensitivities (none weight-eligible) | `cbs4_eminutes_ewma_a030_legacy`, `cbs4_points_a030_legacy` (provenance UNKNOWN), `cbs4_teampoints_frozen2123_legacy` |
| `config_hash` | **`190b9e26c0de3ccdecce87297a762bc57367792eb9314e7ded3d14763e59bcef`** — SHA-256 over the canonical (`sort_keys=True`, compact separators) JSON of `extra.frozen_config` with `hashes.config_hash_value` removed, the v1-v3 self-referential convention |

---

## 9. What this registration is not

- **Not** a promotion candidate — thresholds are sentinels.
- **Not** evidence. It is a specification frozen before results on real data exist.
- **Not** a previously promoted incumbent arm.
- `arm_incumbent` remains **rejected and unconsumed**.
- The dynamic hierarchical arm is **not** begun.

**No real contract row has been read by this pipeline, and no historical OOF, accuracy or coverage
figure exists.** Generation into a new v4 artifact directory awaits supervisory review; validation,
provenance, obligation coverage and the exclusion cross-tabs must all pass **before any accuracy
metric is inspected**.
