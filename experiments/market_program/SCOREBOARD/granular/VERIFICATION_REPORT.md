# VERIFICATION_REPORT.md -- legacy player-model verification (D037)

Date: 2026-08-21T15:33:44.985432+00:00. Verification node for the checklist in PROBE_LEGACY.md, executed against bytes at `experiments/cbs_v15_player_oof_v5/attempt_002/`.
Producer run: `cbs_v15_player_oof_v5/1`; verifier: `verify_legacy_player_model.py` (this directory).

## OVERALL VERDICT: RECEIPTED

| # | Check | Verdict |
|---|-------|---------|
| 1 | byte integrity | **PASS** |
| 2 | producer source-set digest | **PASS** |
| 3 | cutoff discipline | **PASS** |
| 4 | universe re-derivation | **PASS** |
| 5 | config/snapshot pinning | **PASS** |
| 6 | generation-only claim | **PASS** |
| 7 | tier policy | **PASS** |

### Check 1 -- byte integrity: PASS
37/37 manifests re-verified (expected 37: 6 folds x (4 prediction parquets + sidecar + fold receipt) + run_index). Recomputed sha256 and byte counts equal `content_sha256`/`content_bytes` in every `*.manifest.json`. Failures: none.

### Check 2 -- producer source-set digest: PASS
Recomputed digest over the 31-file `PRODUCER_SOURCES` set of `run_player_oof_v15.py` = `f3945feb9a15bf0a6476c9c8a781757590e651a4722e91dab078230d74a56891`; expected `f3945feb9a15bf0a6476c9c8a781757590e651a4722e91dab078230d74a56891` -- match: True. All 25 artifact manifests and all 6 fold receipts carry the expected digest. Producer source files drifted since the run: none.

### Check 3 -- cutoff discipline: PASS
Per-row violations across all 24 prediction parquets (forecast_cutoff >= game datetime, feature_asof >= game datetime, or feature_asof > forecast_cutoff): **0**. The game datetime is the contract's OBSERVED scheduled tip where captured (all 12,608 `exact_tip_T-90m` rows of 2025-2026), else midnight UTC of the game date, a lower bound on any same-day tip. Per fold: `max(train_seasons) < S` holds for every fitted fold (2021 is degenerate: no train seasons, fallback-only, `model_was_fitted=false`). Every row's forecast_cutoff is byte-equal to the contract's cutoff for its row_uid.

| fold | train_seasons | manifest fit_through_date | reproduces | train-bound | precedes S's first game |
|------|---------------|---------------------------|------------|-------------|-------------------------|
| 2021 | [] (degenerate) | 2021-10-16 12:00:00+00:00 | True | n/a | True |
| 2022 | [2021] | 2022-09-17 12:00:00+00:00 | True | 2021-10-18 12:00:00+00:00 | True |
| 2023 | [2021, 2022] | 2023-10-17 12:00:00+00:00 | True | 2022-09-19 12:00:00+00:00 | True |
| 2024 | [2021, 2022, 2023] | 2024-10-19 12:00:00+00:00 | True | 2023-10-19 12:00:00+00:00 | True |
| 2025 | [2021, 2022, 2023, 2024] | 2025-10-09 12:00:00+00:00 | True | 2024-10-21 12:00:00+00:00 | True |
| 2026 | [2021, 2022, 2023, 2024, 2025] | 2026-07-30 12:00:00+00:00 | True | 2025-10-11 12:00:00+00:00 | True |

PROBE_LEGACY.md's literal reading of the third assertion (`fit_through_date <= season S first game date`) does not apply to a walk-forward artifact and is replaced, per `asof_invariant.py`'s own manifest semantics, by the two assertions above: the artifact-level `fit_through_date` is max(train bound, max per-row `feature_asof`), and the per-row `feature_asof` lawfully includes within-season history strictly before each row's own cutoff. The recomputed value reproduces the manifest value exactly in every fold, and the TRAIN component precedes the predicted season's first game in every fitted fold.

### Check 4 -- universe re-derivation: PASS
`prediction_contract_v5.build_candidates()` re-run in memory from the pinned inputs (all pinned hashes match the fold receipts: True); 44851 obligation rows re-derived.

| season | n re-derived | n receipt | row_uid sets equal | tier counts match |
|--------|--------------|-----------|--------------------|-------------------|
| 2021 | 4997 | 4997 | True | True |
| 2022 | 6333 | 6333 | True | True |
| 2023 | 7418 | 7418 | True | True |
| 2024 | 7866 | 7866 | True | True |
| 2025 | 9729 | 9729 | True | True |
| 2026 | 8508 | 8508 | True | True |

Caveat (recorded, not blocking): the transaction wire and report capture feed S_TX/S3 candidacy but are NOT hash-pinned in the fold receipts; their bytes as verified today are recorded here. Exact row_uid set equality of the re-derivation makes the gap immaterial for THIS verification.

### Check 5 -- config/snapshot pinning: PASS
`config_hash` and `data_snapshot_hash` are single-valued in every prediction parquet and equal to the fold receipt's values; `fold_id` is `season:S` everywhere; the run-level `config_hash` (`e435d732...`) is constant across all six folds.

### Check 6 -- generation-only claim: PASS
`run_index.json.scores_computed=False`; all 25 manifests carry `generation_only: true, scores_computed: false`; all 6 fold receipts assert no forecast was scored and no evaluation metric calculated; no outcome or score column exists in any parquet (columns scanned against a forbidden-name set; hits: none). Every surfaced number below is computed fresh against owned gamelogs.

### Check 7 -- tier policy: PASS
DECISION (recorded): headline universe = **A_primary ONLY**; `B_s2_weak_fallback` and `B_transaction_sensitivity` are split out as separate labelled row sets; an all-tiers aggregate is published and labelled, never the headline. Authority: prediction_contract_v5 tier semantics: Tier B is cutoff-safe but roster membership is NOT verified and is 'reported SEPARATELY and never mixed silently into Tier A headline metrics'; D036 point 8 requires the universe named on every displayed number Per-fold, per-target tier counts in the parquets match every fold receipt.

## Verified legacy metrics (evidence class: PRELIMINARY, legacy-receiptable)

Computed by this node from `pred_point` vs owned-gamelog outcomes (sources + sha256 in `legacy_verified_metrics.json`), on appearance rows (minutes > 0) of the artifact universe; both targets are conditional-on-appearance by contract. 95% CIs: game-date-cluster bootstrap, seed 20260806, 1000 draws -- the same method as the naive-baseline scoreboard cells. Bias = mean(pred - actual). Headline = A_primary, pooled 2022-2026 (the naive-baseline window).

### points

| tier | season | N | MAE | MAE 95% CI | RMSE | bias |
|------|--------|---|-----|------------|------|------|
| A_primary | 2021 | 3407 | 5.8120 | [5.6846, 5.9515] | 7.2533 | -0.5335 |
| A_primary | 2022 | 3939 | 4.0380 | [3.9243, 4.1410] | 5.3409 | -0.0591 |
| A_primary | 2023 | 4394 | 4.0784 | [3.9934, 4.1725] | 5.4574 | -0.2753 |
| A_primary | 2024 | 4371 | 4.0800 | [3.9599, 4.2081] | 5.3703 | -0.1079 |
| A_primary | 2025 | 5213 | 4.1986 | [4.1037, 4.2968] | 5.4918 | -0.1502 |
| A_primary | 2026 | 4053 | 4.2451 | [4.1035, 4.3784] | 5.6118 | -0.2338 |
| A_primary | **pooled_2022_2026** | 21970 | **4.1308** | [4.0830, 4.1822] | 5.4566 | -0.1659 |
| A_primary | pooled_2021_2026 | 25377 | 4.3565 | [4.2876, 4.4298] | 5.7307 | -0.2152 |
| all_tiers | 2021 | 3479 | 5.7938 | [5.6730, 5.9274] | 7.2282 | -0.4919 |
| all_tiers | 2022 | 4065 | 4.0924 | [3.9690, 4.2095] | 5.4023 | -0.0630 |
| all_tiers | 2023 | 4520 | 4.1251 | [4.0238, 4.2474] | 5.4964 | -0.2312 |
| all_tiers | 2024 | 4502 | 4.1425 | [3.9987, 4.2914] | 5.4397 | -0.0930 |
| all_tiers | 2025 | 5357 | 4.2493 | [4.1399, 4.3629] | 5.5488 | -0.1158 |
| all_tiers | 2026 | 4221 | 4.3244 | [4.1824, 4.4861] | 5.6942 | -0.1972 |
| all_tiers | pooled_2022_2026 | 22665 | 4.1892 | [4.1322, 4.2504] | 5.5183 | -0.1400 |
| all_tiers | pooled_2021_2026 | 26144 | 4.4027 | [4.3349, 4.4732] | 5.7752 | -0.1868 |
| B_s2_weak_fallback | 2021 | 0 | -- | -- | -- | -- |
| B_s2_weak_fallback | 2022 | 24 | 6.9915 | [5.9134, 8.6284] | 8.4658 | -3.2162 |
| B_s2_weak_fallback | 2023 | 9 | 7.2141 | [3.6909, 9.1545] | 8.4226 | -2.7535 |
| B_s2_weak_fallback | 2024 | 6 | 7.6853 | [6.5279, 11.2779] | 8.5095 | -4.7779 |
| B_s2_weak_fallback | 2025 | 3 | 6.4361 | [6.2694, 6.7694] | 6.7562 | +6.4361 |
| B_s2_weak_fallback | 2026 | 2 | 6.7586 | [4.7586, 8.7586] | 7.0483 | +6.7586 |
| B_s2_weak_fallback | pooled_2022_2026 | 44 | 7.0832 | [6.4093, 8.0502] | 8.2975 | -2.2230 |
| B_s2_weak_fallback | pooled_2021_2026 | 44 | 7.0832 | [6.4093, 8.0502] | 8.2975 | -2.2230 |
| B_transaction_sensitivity | 2021 | 72 | 4.9333 | [3.1371, 5.3613] | 5.9227 | +1.4778 |
| B_transaction_sensitivity | 2022 | 102 | 5.5105 | [5.1176, 6.8063] | 6.6830 | +0.5308 |
| B_transaction_sensitivity | 2023 | 117 | 5.6418 | [3.5259, 6.2675] | 6.5652 | +1.6190 |
| B_transaction_sensitivity | 2024 | 125 | 6.1588 | [3.7847, 6.3910] | 7.3345 | +0.6499 |
| B_transaction_sensitivity | 2025 | 141 | 6.0753 | [4.7209, 6.3434] | 7.3315 | +1.0170 |
| B_transaction_sensitivity | 2026 | 166 | 6.2313 | [5.6492, 6.6635] | 7.4123 | +0.6117 |
| B_transaction_sensitivity | pooled_2022_2026 | 651 | 5.9647 | [5.6625, 6.1992] | 7.1221 | +0.8752 |
| B_transaction_sensitivity | pooled_2021_2026 | 723 | 5.8620 | [5.5464, 6.0925] | 7.0119 | +0.9352 |

Join audit (points): 44851 obligation rows; 18444 without a gamelog outcome row (candidate did not appear, or outcome outside the owned regular-season universe); 231 where the outcome's team differs from the obligation's team (dual obligations of traded players -- the other team's row scores); 32 zero-minute rows excluded (conditional target); 26144 scored.

### minutes

| tier | season | N | MAE | MAE 95% CI | RMSE | bias |
|------|--------|---|-----|------------|------|------|
| A_primary | 2021 | 3407 | 8.7658 | [8.5175, 9.0257] | 10.2943 | -1.8231 |
| A_primary | 2022 | 3939 | 4.8215 | [4.6437, 4.9959] | 6.1946 | +0.2783 |
| A_primary | 2023 | 4394 | 4.7349 | [4.5618, 4.8923] | 6.1824 | -0.0835 |
| A_primary | 2024 | 4371 | 4.7611 | [4.5746, 4.9931] | 6.2901 | +0.0322 |
| A_primary | 2025 | 5213 | 4.8123 | [4.6814, 4.9432] | 6.2161 | -0.0366 |
| A_primary | 2026 | 4053 | 4.4863 | [4.3021, 4.6600] | 5.8671 | +0.1245 |
| A_primary | **pooled_2022_2026** | 21970 | **4.7281** | [4.6544, 4.8127] | 6.1575 | +0.0539 |
| A_primary | pooled_2021_2026 | 25377 | 5.2702 | [5.1206, 5.4132] | 6.8594 | -0.1981 |
| all_tiers | 2021 | 3479 | 8.7600 | [8.5053, 8.9923] | 10.2841 | -1.7578 |
| all_tiers | 2022 | 4065 | 4.9367 | [4.7464, 5.1429] | 6.3653 | +0.2679 |
| all_tiers | 2023 | 4520 | 4.8450 | [4.6544, 5.0695] | 6.3366 | -0.0196 |
| all_tiers | 2024 | 4502 | 4.8947 | [4.6630, 5.1673] | 6.4636 | +0.0698 |
| all_tiers | 2025 | 5357 | 4.9225 | [4.7517, 5.1160] | 6.3734 | +0.0277 |
| all_tiers | 2026 | 4221 | 4.6320 | [4.4196, 4.8961] | 6.0707 | +0.2214 |
| all_tiers | pooled_2022_2026 | 22665 | 4.8500 | [4.7516, 4.9518] | 6.3275 | +0.1058 |
| all_tiers | pooled_2021_2026 | 26144 | 5.3703 | [5.2316, 5.5229] | 6.9845 | -0.1422 |
| B_s2_weak_fallback | 2021 | 0 | -- | -- | -- | -- |
| B_s2_weak_fallback | 2022 | 24 | 8.5525 | [7.4542, 12.5460] | 9.9652 | -2.9061 |
| B_s2_weak_fallback | 2023 | 9 | 9.7894 | [7.0958, 10.7480] | 10.5359 | -0.9635 |
| B_s2_weak_fallback | 2024 | 6 | 11.2633 | [9.0908, 19.7009] | 12.5242 | -4.6964 |
| B_s2_weak_fallback | 2025 | 3 | 11.5214 | [10.5214, 12.0214] | 12.1137 | +11.5214 |
| B_s2_weak_fallback | 2026 | 2 | 11.0057 | [6.5057, 15.5057] | 11.8901 | +11.0057 |
| B_s2_weak_fallback | pooled_2022_2026 | 44 | 9.4891 | [8.4620, 11.5741] | 10.7095 | -1.1368 |
| B_s2_weak_fallback | pooled_2021_2026 | 44 | 9.4891 | [8.4620, 11.5741] | 10.7095 | -1.1368 |
| B_transaction_sensitivity | 2021 | 72 | 8.4877 | [7.1720, 9.9716] | 9.7923 | +1.3317 |
| B_transaction_sensitivity | 2022 | 102 | 8.5347 | [7.5235, 11.7413] | 10.4626 | +0.6114 |
| B_transaction_sensitivity | 2023 | 117 | 8.5996 | [7.8428, 9.9862] | 10.3541 | +2.4516 |
| B_transaction_sensitivity | 2024 | 125 | 9.2608 | [6.8389, 9.9200] | 10.6607 | +1.6140 |
| B_transaction_sensitivity | 2025 | 141 | 8.8559 | [8.0675, 9.8616] | 10.5634 | +2.1635 |
| B_transaction_sensitivity | 2026 | 166 | 8.1134 | [7.1258, 11.5671] | 9.7442 | +2.4565 |
| B_transaction_sensitivity | pooled_2022_2026 | 651 | 8.6479 | [8.1636, 9.2473] | 10.3258 | +1.9413 |
| B_transaction_sensitivity | pooled_2021_2026 | 723 | 8.6320 | [8.1796, 9.1147] | 10.2739 | +1.8806 |

Join audit (minutes): 44851 obligation rows; 18444 without a gamelog outcome row (candidate did not appear, or outcome outside the owned regular-season universe); 231 where the outcome's team differs from the obligation's team (dual obligations of traded players -- the other team's row scores); 32 zero-minute rows excluded (conditional target); 26144 scored.

## Scope and caveats

- Stats covered: **points and minutes only.** The legacy lane never registered rebounds/assists/steals/blocks/threes/turnovers; those scoreboard rows remain ABSENT for the legacy column (PROBE_LEGACY.md).
- No `SEALED_RESULTS` path was read or written; no git command was run. The producer's own clean-tree receipt records commit `0108ef86e9c085e1d701e40e53c24dcde177ac97`; that identifier is reproduced from the receipt, not independently verified here -- the verified anchors are the manifest hashes and the producer source-set digest (checks 1-2).
- 2021 is an unfitted, fallback-only fold and 2021 outcome rows come from the pinned 2021 gamelog; 2021 cells are labelled and excluded from the headline pooled window.
- Evidence class PRELIMINARY per D036/D038: verified provenance, but a legacy artifact scored retrospectively by a different node -- not a program-registered, pre-declared evaluation (that would be VERIFIED).

