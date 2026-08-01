# `contract_baseline_suite_v5` — frozen estimator, corrected implementation

*Registered 2026-08-01. **No real contract row has been read, no historical OOF, fitted suite
artifact, accuracy figure or coverage score exists or was inspected.** The registry record is
append-only. The implementation runs on synthetic data only and has no file I/O.*

**Supersedes `contract_baseline_suite_v4`.** v1-v4 records and documents are unchanged; v4's
implementation files (`cbs_generator.py`, `cbs_pipeline.py`) are **left exactly as registered** and
this module set is the corrected one. Supersession is recorded here, in the ledger and in
`project_docs/SPEC_ERRATA.md`.

v4's *specification* was sound. Its **implementation differed materially from it**, in ways that
would have produced confidently wrong numbers rather than errors. Each defect below was confirmed
by direct reproduction before being fixed.

---

## 0. What was actually wrong, and what v5 freezes

| # | v4 implementation | reproduction | v5 |
|---|---|---|---|
| 1 | λ tuning sliced tuning **row indices** 75/25 | obligations are ordered by player, so the fit side held **P0-P5** and validation **P6-P7**, with **all 36 dates on both sides** | §1 inner cut on **distinct chronological dates** |
| 2 | the team runner never ordered its rows | shuffling identical frames moved team predictions by **up to 5.9 points** here (16.1 in the supervisor's reproduction) and moved dispersion **8.38 → 8.27** | §2 frozen chronological keys everywhere |
| 3 | one **pooled** calibration map, no side indicator required | the fixture had no home/away field at all | §3 separate home/away T2 maps, side required |
| 4 | residual = `prediction - outcome`, offsets **added** to the point | every asymmetric empirical quantile came out **mirrored** | §4 residual = `outcome - prediction` |
| 5 | missing channels silently dropped | a 3-channel frame became a different model without saying so | §3 four channels **required**, fail closed |
| 6 | `model_hash` covered only the coefficients | two fits differing in scaler, λ or feature order could share a hash | §5 complete fitted state |
| 7 | cold-start ignored the target; team prior games always 0 | a player with 4 obligations and 0 appearances was marked **non-cold** for conditional targets | §6 target-specific accounting |
| 8 | Stage-A silently zero-filled; `feature_asof` trusted | a frame missing half the vector still produced confident probabilities | §7 fail closed |

---

## 1. λ inner split — distinct chronological dates

Cut the **tuning segment** into fit / validation on **distinct dates**:

- `n_val = floor(n_tuning_dates * 0.25)`; validation is the **latest** dates;
- minimums **6** fit dates and **2** validation dates;
- below either minimum the inner split is **degenerate**, yields **no validation rows**, and λ
  takes the declared default **1.0**;
- fit and validation dates are asserted disjoint; overlap raises `SelectionLeakage`.

Ties → smallest λ, grid ascending. The grid is unchanged from v3/v4.

---

## 2. Team history — explicit chronological keys, frozen reset

Taken from the registered `run_reval` family after inspection, so the baseline matches the
promoted artifact rather than approximating it:

| element | frozen value | source |
|---|---|---|
| sort keys | `(team_id, game_date, game_id)` | `run_reval.py:86` |
| history grouping | `(team_id, season)` | `run_reval.py:102` |
| season boundary | **history resets; nothing carries across a season** | same |
| `prior_games` | `cumcount()` within `(team_id, season)` | `run_reval.py:89` |
| minimum prior | **5** | `run_reval.MIN_PRIOR` |
| channels | `ft`, `3pt`, `paint`, `np2` | `run_reval.CHANNELS` |

Every team history operation sorts explicitly before grouping, so **input order cannot make a
later game part of an earlier row's history**. Row-shuffle invariance is a registered property and
is tested.

Because folds are seasons and history is grouped by `(team_id, season)`, the train→test boundary
carries **no** team history: a test season starts from its own openers. Season openers are
identified (`prior_games == 0`), not hidden.

---

## 3. Separate home/away maps; required inputs

- A **`side`** column is **required**, with values exactly `home` / `away`.
- All **four** channels are **required**. A missing channel raises `MissingRequiredInput`; the
  registered estimator may not silently become a different model.
- **Two** two-parameter linear maps are fitted on **T2 only**, one per side:
  `calibrated = a_side + b_side · structural`. They are applied only to their own side.

---

## 4. Residual sign

**`residual = outcome - prediction`**, because the offsets are **added** to the point prediction.

v4 used `prediction - outcome` with additive offsets, so a long *upper* tail in the outcomes was
emitted as a long *lower* tail. The direction is now tested explicitly, including a reproduction of
the inverted convention to show the test would have caught it.

Dispersion is otherwise unchanged: sd with `ddof = 1`; nonfinite **or** nonpositive sd (including
a constant pool) is **insufficient** and routes to the declared fallback; empirical quantiles via
`numpy.quantile(method="linear")` at >= 200 player / >= 30 team residuals, Gaussian `z·sd` below;
truncate to support, then monotone-sort.

---

## 5. Complete fitted-state hashing, and a fail-closed adapter boundary

`model_hash` is a SHA-256 over the **complete fitted state** — feature order, scaler means and
standard deviations, dropped-column set, λ, coefficients, selected αs, calibration maps, fallback
means, and dispersion state (sd, method, offsets). Anything that changes a prediction is in the
hash; floats are canonicalised to 12 decimal places so it is stable across platforms.

`require_identity(config_hash, snapshot_hash, synthetic=False)` **fails closed** on the real-data
boundary: both must be explicit 64-hex digests, and placeholders (`"synthetic"`, all-zero) are
rejected. Synthetic runs must opt in with `synthetic=True`.

---

## 6. Target-specific cold starts and prior-history accounting

`n_prior_candidate_games` and `n_prior_appearances` are recorded **separately** on every row, and
cold-start is target-specific:

| target | cold when | reason |
|---|---|---|
| `p_active` | **no prior obligation** | 0-of-k is evidence, not absence |
| `e_minutes_given_active`, `attempts_usage`, `player_scoring_distribution` | **no prior appearance** | their history is the active subsequence, so a player with obligations but no appearances has *no conditional history at all* — those rows are cold **and** fallback |
| `team_game_distribution` | `prior_games == 0` (a season opener) | team history resets each season |

`n_prior_games` in the emitted contract is strictly-prior **appearances**.

---

## 7. Stage-A features and `feature_asof` fail closed

`stage_a_features_strict` raises `MissingRequiredInput` when a canonical feature is absent, unless
the caller explicitly passes `allow_declared_defaults=True` (permitted for synthetic tests, never
for real data). `resolve_feature_asof` derives the row's **maximum actual source timestamp** from
the columns actually read, and raises on absent or unparseable sources, or when any derived
timestamp is `>= forecast_cutoff`.

---

## 8. A strict validator, alongside the historical one

`contract_validator_v2_strict.py` (`contract_v2_strict/1`) validates the **unchanged** v2 row
universe. The historical `prediction_contract_v2.validate_predictions()` is **not rewritten** —
other registered artifacts were checked against it, and tightening it retroactively would change
what those checks meant.

**Passing the historical validator is necessary but not sufficient.** The strict validator joins
predictions to the universe and additionally enforces: exact `target_key` / `arm_id` / `fold_id`;
`forecast_cutoff` equal to the universe's; per-target support bounds on the point **and** the
quantiles; sd required-and-positive or required-null by target; quantiles required-or-forbidden by
target; boolean `is_fallback` / `is_cold_start`; non-negative integer `n_prior_games`; 64-hex hash
format and expected `config_hash` / `data_snapshot_hash`; and strict `feature_asof < forecast_cutoff`.

Of nine mutations that the strict validator rejects, the historical validator accepts most —
measured in the suite, not asserted.

---

## 9. Identity and status

| field | value |
|---|---|
| `arm_id` | `contract_baseline_suite_v5` |
| implementation | `cbs_v5.py`, `contract_validator_v2_strict.py` |
| tests | `tests/test_cbs_v5.py` — **75 assertions**, synthetic only |
| `config_hash` | **`ea701817e5f87caf3fe1041037cd8bec430df95d9c25e6128fa4db4f9ec5afda`** — the v1-v4 self-referential convention |

Carried unchanged from v4: the common contract layer; the disjoint player tuning/calibration date
split and the team T1/T2/T3 date split with its rounding, minimums and degenerate fallback;
`SplitContext`-bound selection; obligation ordering with fail-closed duplicate detection;
prefix-only base rates and fallback means; active-subsequence conditional history; the α and λ
grids with boundary reporting; the `season:2021` declared constants; both α = 0.30 legacies
sensitivity-only and weight-ineligible with the points legacy's provenance **UNKNOWN**; and the
`1e-6` team-points floor.

**Not** a promotion candidate; **not** evidence; `arm_incumbent` remains rejected and unconsumed;
the dynamic hierarchical arm is **not** begun. Generation into a v5 artifact directory awaits
supervisory review, and validation, provenance, obligation coverage and exclusion cross-tabs must
pass **before any accuracy metric is inspected**.
