# REJECTED ARTIFACT — do not consume

`experiments/arm_incumbent/predictions.parquet`, produced at commit **`ac2e2f0`**, is
**REJECTED**. It must not be used in any comparison, council, weight fit, or report.
Rejection raised by the Codex supervisor 2026-08-01 and **verified against the committed
parquet files before being accepted**.

## The blocking defect: target-box membership controlled arm coverage

`arm_incumbent.py` built its feature frame from `master_player` and joined it to contract
candidates on `(game_id, player_id)`. A feature row therefore existed **only when the player
also had a row in the target game's boxscore**. Dropping label columns after reading the
contract did not remove that channel — it removed the *values*, not the *membership*.

So the arm reintroduced, after contract construction, exactly the v1 selection channel that
`prediction_contract_v2` was built to eliminate.

## Verified figures (recomputed here, all matched the supervisor's)

| claim | verified |
|---|---|
| exclusions that are `in_target_box == False` | **3,154 of 3,154** |
| target-box rows excluded | **0** |
| excluded rows with ≥1 strictly prior **appearance** | **2,697** |
| remaining excluded rows (prior roster/DNP observations, fallback-eligible) | **457** |
| excluded rows that later appeared | **0 of 3,154** |
| `n_prior_games` ≠ strictly-prior appearances | **16,102 of 32,461** |

`no_strictly_prior_observation` is therefore **false for all 3,154 rows**. Every one of them
had strictly prior observations — that is how they became contract candidates at all.

## The reading error that matters most

I reported conditional `scoreable_coverage = 1.0000` as "exactly as the contract intends."
It was the opposite. Coverage was 1.0 **because every excluded row was one that never
appeared** — 0 of 3,154 excluded candidates later played. Exclusion perfectly predicted
non-appearance. That is an outcome-selection alarm, and I read it as a success.

## Further blockers in the same artifact

1. **`feature_asof` was repaired, not enforced.** It used the prior `game_date` localised to
   00:00 UTC — timestamping an outcome *before* the game that produced it — and then clamped
   any late value to `forecast_cutoff − 1s` instead of discarding the observation. Timestamp
   repair is not fail-closed as-of enforcement.
2. **`n_prior_games` emitted the wrong quantity** — prior box rows including DNPs, not the
   schema's strictly-prior *appearances*. Differs on 16,102 rows.
3. **It is not the registered incumbent.** The registered control is the *current EWMA/ridge
   player layer, unchanged*. This file contains no ridge and introduced new alphas, a 0.70
   active prior, and points-SD-derived uncertainty heuristics.
4. **C3 provenance not met.** Manifest lacks dependency hashes, producer commit and a real
   data-snapshot hash; `data_snapshot_hash` was row-count + max-date, so content can change
   without moving it; `model_hash` is constant per target across folds.
5. **No arm-level test suite.** The generic validator lets any *declared* exclusion pass by
   design, so a green gate could never establish the reason was true.

## Status of dependent claims

**No accuracy result from this artifact was ever computed or inspected.** The run reported
contract compliance only. No comparison, ranking or council weight used it. Evidence labels
elsewhere are unaffected: `calibrated_prob_edge_v1` NEGATIVE, mechanism label A,
harmful-controls an uncorrected diagnostic lead, `freeze-v0` untouched.
