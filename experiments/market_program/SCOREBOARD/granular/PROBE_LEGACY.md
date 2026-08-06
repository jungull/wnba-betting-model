# PROBE_LEGACY.md -- legacy player-model provenance probe (D037)

Date: 2026-08-06 (UTC). Probe only; **nothing was fitted, re-run, or scored**.
Per D037, no legacy number appears in `player_granular_metrics.json` this
session regardless of this verdict; legacy numbers may only surface after a
verification node executes the checklist below.

All paths are relative to the worktree root
`C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`.
None of the artifacts below sit under any `SEALED_RESULTS` directory or under
`experiments/player_program/stage2b` (the sealed possession-lane challenger
area); verified by directory enumeration -- the only `stage2b` directory in
the repo is `experiments/player_program/stage2b`, and the artifacts here live
at repo-root `experiments/`.

## VERDICT: RECEIPTABLE

Committed OOF prediction artifacts exist on disk, their cutoff discipline is
receipted per fold and per artifact, and every artifact carries a sha256
manifest. A verification node can check them without refitting anything.

## What exists

### 1. `experiments/cbs_v15_player_oof_v5/attempt_001/` (primary)
Producer: `run_player_oof_v15.py` (repo root; run id `cbs_v15_player_oof_v5/1`,
generation-only by design -- its docstring and manifests state "No forecast
was scored against its outcome").

- Prediction parquets: `predictions__<target>__<season>.parquet` for seasons
  2021-2026 and four registered targets:
  - `p_active` (activity probability)
  - `e_minutes_given_active` (**minutes**)
  - `attempts_usage` (attempt/usage volume)
  - `player_scoring_distribution` (**points**: `pred_point`, `pred_sd`,
    `pred_q05/q25/q50/q75/q95`)
  Row schema includes, per row: `row_uid`, `target_key`, `fold_id`,
  `forecast_cutoff`, `feature_asof`, `is_fallback`, `fallback_level`,
  `is_cold_start`, `n_prior_games`, `model_hash`, `config_hash`,
  `data_snapshot_hash`, `exclusion_reason`.
- Fold receipts: `fold_receipt__<season>.json`
  (`cbs_v15_player_oof_fold_receipt/1`). E.g. the 2024 fold records
  `train_seasons=[2021,2022,2023]`, `train_is_tier_a_only=true`,
  `row_universe="prediction_contract_v5"`, history policy
  `tier_a_target_fit_with_observed_history/1`, per-target obligation
  completeness (7866/7866), cold-start and fallback counts, `config_hash`,
  `snapshot_hash`, `producer_source_set_digest`.
- Per-artifact manifests (`*.manifest.json`): `content_sha256`,
  `fit_seasons`, `fit_through_date` (e.g. 2024 file: fit seasons
  [2021,2022,2023], `fit_through_date=2024-10-19T12:00:00+00:00`,
  `generation_only: true`), producer name and source-set digest.
- `provenance_sidecar__<season>.parquet`, `run_index.json` (row universe,
  scope receipt, implementation bytes, `scores_computed` field),
  `runtime_log__coordinator.jsonl`.

**Universe:** `prediction_contract_v5` obligation rows (contract code at repo
root `prediction_contract_v5.py`; obligation keys via `cbs_obligation_key.py`).
**Stats covered:** minutes and points directly; attempts/usage and activity
as auxiliary targets. **NOT covered:** rebounds, assists, steals, blocks,
threes made, turnovers -- the legacy lane never registered those targets, so
even a fully receipted surface fills only the minutes and points rows of the
granular scoreboard's "our model" column.

### 2. `experiments/cbs_v14_player_oof/attempt_001/` (the v14/v4 control)
Same four targets, `cbs_player_oof_fold_receipt/1` receipts (2024 fold:
`train_seasons=[2021,2022,2023]`), same manifest convention. Fold receipts
predate the v15 schema (no `row_universe` field in the receipt itself).

### 3. `experiments/oof_backfill/predictions_oof_2022_2023.csv`
Older scoring-channel backfill (`base_predictions_oof_2022_2023_v1`);
`run_summary.json` records per-season `train_seasons` strictly prior,
`fit_through` dates, and leakage audits with
`removal_mismatch_rows=0, perturbation_mismatch_rows=0`; has a manifest.
Seasons 2022-2023 only; channel-level scoring predictions.

### Producer/discipline code present at repo root
`run_player_oof_v14.py` (producer gate: `require_clean_producer`,
`producer_digest`, immutable attempts, fail-closed resume),
`run_player_oof_v15.py`, `cbs_player_runner_v13/14/15.py`,
`asof_invariant.py` (as-of invariant machinery), `prediction_contract_v5.py`.

## What a verification node must check (exactly)

1. **Byte integrity:** recompute sha256 of every
   `predictions__*.parquet` and compare to `content_sha256` in its
   `*.manifest.json`; same for fold receipts and sidecars.
2. **Producer digest:** recompute the producer source-set digest over the
   `PRODUCER_SOURCES` tuple named in `run_player_oof_v15.py` and compare to
   `producer_source_set_digest` in every manifest and fold receipt
   (`768f8139d72439adcae59b2dcf57390356b435ce8082f9a0aa0acdcb4925b7b9`).
3. **Cutoff discipline, per fold:** for every season S receipt, assert
   `max(train_seasons) < S`; assert every prediction row's `forecast_cutoff`
   and `feature_asof` strictly precede the row's game datetime (join
   `row_uid` -> game via `prediction_contract_v5` obligation keys); assert
   manifest `fit_through_date` <= season S first game date.
4. **Universe:** re-derive the `prediction_contract_v5` obligation row set
   for each season and confirm `n_universe_rows == n_emitted` per target
   (obligation completeness blocks) with `n_excluded=0` or itemized
   exclusions.
5. **Config/snapshot pinning:** `config_hash` and `data_snapshot_hash`
   constant within a fold and equal to the fold receipt values.
6. **Generation-only claim:** confirm no score/accuracy fields exist in any
   artifact (`run_index.json` `scores_computed`), so any surfaced number is
   computed fresh by the scoreboard pipeline from `pred_point` (or quantiles)
   vs owned-gamelog outcomes -- never copied from legacy output.
7. **Tier semantics:** decide and record whether `B_s2_weak_fallback` /
   `B_transaction_sensitivity` rows are admitted to the displayed universe
   or split out; the fold receipts give exact per-tier counts.

## Explicitly not receiptable today

- No git commit SHA can be attached from this worktree (no git available per
  task constraints); manifests' `content_sha256` + producer digests are the
  provenance anchor until a commit SHA is recorded by a git-capable node.
- The six stats never targeted by the legacy lane (rebounds, assists, steals,
  blocks, threes, turnovers) have **no** legacy artifacts: for those rows the
  legacy column is ABSENT, not unreceipted.
