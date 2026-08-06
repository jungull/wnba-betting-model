# VERIFICATION_REPORT.md -- legacy player-model verification (D037)

Date: 2026-08-06T21:01:49.633112+00:00. Verification node for the checklist in PROBE_LEGACY.md, executed against bytes at `experiments/cbs_v15_player_oof_v5/attempt_001/`.
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
Recomputed digest over the 31-file `PRODUCER_SOURCES` set of `run_player_oof_v15.py` = `768f8139d72439adcae59b2dcf57390356b435ce8082f9a0aa0acdcb4925b7b9`; expected `768f8139d72439adcae59b2dcf57390356b435ce8082f9a0aa0acdcb4925b7b9` -- match: True. All 25 artifact manifests and all 6 fold receipts carry the expected digest. Producer source files drifted since the run: none.

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
| A_primary | 2022 | 3939 | 4.1386 | [4.0142, 4.2547] | 5.4070 | -0.0125 |
| A_primary | 2023 | 4394 | 4.2199 | [4.0937, 4.3601] | 5.6080 | -0.1681 |
| A_primary | 2024 | 4371 | 4.2499 | [4.0984, 4.4211] | 5.5764 | -0.0188 |
| A_primary | 2025 | 5213 | 4.3317 | [4.2095, 4.4576] | 5.6105 | -0.0418 |
| A_primary | 2026 | 4053 | 4.3785 | [4.1977, 4.5396] | 5.7389 | -0.1159 |
| A_primary | **pooled_2022_2026** | 21970 | **4.2671** | [4.2044, 4.3320] | 5.5914 | -0.0709 |
| A_primary | pooled_2021_2026 | 25377 | 4.4745 | [4.4017, 4.5519] | 5.8420 | -0.1330 |
| all_tiers | 2021 | 3479 | 5.7938 | [5.6730, 5.9274] | 7.2282 | -0.4919 |
| all_tiers | 2022 | 4065 | 4.1875 | [4.0546, 4.3176] | 5.4604 | -0.0158 |
| all_tiers | 2023 | 4520 | 4.2642 | [4.1236, 4.4154] | 5.6427 | -0.1255 |
| all_tiers | 2024 | 4502 | 4.3075 | [4.1447, 4.4775] | 5.6375 | -0.0066 |
| all_tiers | 2025 | 5357 | 4.3788 | [4.2390, 4.5148] | 5.6632 | -0.0089 |
| all_tiers | 2026 | 4221 | 4.4545 | [4.2861, 4.6446] | 5.8161 | -0.0820 |
| all_tiers | pooled_2022_2026 | 22665 | 4.3215 | [4.2492, 4.3948] | 5.6471 | -0.0466 |
| all_tiers | pooled_2021_2026 | 26144 | 4.5175 | [4.4436, 4.5913] | 5.8821 | -0.1058 |
| B_s2_weak_fallback | 2021 | 0 | -- | -- | -- | -- |
| B_s2_weak_fallback | 2022 | 24 | 6.9915 | [5.9134, 8.6284] | 8.4658 | -3.2162 |
| B_s2_weak_fallback | 2023 | 9 | 7.2141 | [3.6909, 9.1545] | 8.4226 | -2.7535 |
| B_s2_weak_fallback | 2024 | 6 | 7.6853 | [6.5279, 11.2779] | 8.5095 | -4.7779 |
| B_s2_weak_fallback | 2025 | 3 | 6.4361 | [6.2694, 6.7694] | 6.7562 | +6.4361 |
| B_s2_weak_fallback | 2026 | 2 | 6.7586 | [4.7586, 8.7586] | 7.0483 | +6.7586 |
| B_s2_weak_fallback | pooled_2022_2026 | 44 | 7.0832 | [6.4093, 8.0502] | 8.2975 | -2.2230 |
| B_s2_weak_fallback | pooled_2021_2026 | 44 | 7.0832 | [6.4093, 8.0502] | 8.2975 | -2.2230 |
| B_transaction_sensitivity | 2021 | 72 | 4.9333 | [3.1371, 5.3613] | 5.9227 | +1.4778 |
| B_transaction_sensitivity | 2022 | 102 | 5.4176 | [5.0655, 6.3995] | 6.5102 | +0.6085 |
| B_transaction_sensitivity | 2023 | 117 | 5.6990 | [4.0646, 6.3315] | 6.5943 | +1.6762 |
| B_transaction_sensitivity | 2024 | 125 | 6.1588 | [3.7847, 6.3910] | 7.3345 | +0.6499 |
| B_transaction_sensitivity | 2025 | 141 | 6.0727 | [4.7119, 6.3415] | 7.3301 | +1.0731 |
| B_transaction_sensitivity | 2026 | 166 | 6.2828 | [5.8866, 6.9407] | 7.4433 | +0.6631 |
| B_transaction_sensitivity | pooled_2022_2026 | 651 | 5.9730 | [5.6542, 6.2024] | 7.1098 | +0.9229 |
| B_transaction_sensitivity | pooled_2021_2026 | 723 | 5.8695 | [5.5510, 6.0973] | 7.0007 | +0.9782 |

Join audit (points): 44851 obligation rows; 18444 without a gamelog outcome row (candidate did not appear, or outcome outside the owned regular-season universe); 231 where the outcome's team differs from the obligation's team (dual obligations of traded players -- the other team's row scores); 32 zero-minute rows excluded (conditional target); 26144 scored.

### minutes

| tier | season | N | MAE | MAE 95% CI | RMSE | bias |
|------|--------|---|-----|------------|------|------|
| A_primary | 2021 | 3407 | 8.7658 | [8.5175, 9.0257] | 10.2943 | -1.8231 |
| A_primary | 2022 | 3939 | 5.0822 | [4.8445, 5.3095] | 6.5660 | +0.4114 |
| A_primary | 2023 | 4394 | 5.0638 | [4.8300, 5.3263] | 6.6184 | +0.1202 |
| A_primary | 2024 | 4371 | 5.1815 | [4.9090, 5.4956] | 6.8885 | +0.2319 |
| A_primary | 2025 | 5213 | 5.1044 | [4.9051, 5.3157] | 6.6226 | +0.1913 |
| A_primary | 2026 | 4053 | 4.9124 | [4.6264, 5.2050] | 6.4608 | +0.4680 |
| A_primary | **pooled_2022_2026** | 21970 | **5.0722** | [4.9646, 5.2006] | 6.6361 | +0.2757 |
| A_primary | pooled_2021_2026 | 25377 | 5.5681 | [5.4123, 5.7186] | 7.2355 | -0.0061 |
| all_tiers | 2021 | 3479 | 8.7600 | [8.5053, 8.9923] | 10.2841 | -1.7578 |
| all_tiers | 2022 | 4065 | 5.1854 | [4.9592, 5.4544] | 6.7017 | +0.4023 |
| all_tiers | 2023 | 4520 | 5.1671 | [4.9229, 5.4645] | 6.7543 | +0.1824 |
| all_tiers | 2024 | 4502 | 5.3029 | [4.9716, 5.6217] | 7.0310 | +0.2637 |
| all_tiers | 2025 | 5357 | 5.2048 | [4.9841, 5.4361] | 6.7574 | +0.2529 |
| all_tiers | 2026 | 4221 | 5.0416 | [4.7449, 5.3780] | 6.6250 | +0.5557 |
| all_tiers | pooled_2022_2026 | 22665 | 5.1829 | [5.0557, 5.3199] | 6.7779 | +0.3242 |
| all_tiers | pooled_2021_2026 | 26144 | 5.6589 | [5.5145, 5.8061] | 7.3417 | +0.0471 |
| B_s2_weak_fallback | 2021 | 0 | -- | -- | -- | -- |
| B_s2_weak_fallback | 2022 | 24 | 8.5525 | [7.4542, 12.5460] | 9.9652 | -2.9061 |
| B_s2_weak_fallback | 2023 | 9 | 9.7894 | [7.0958, 10.7480] | 10.5359 | -0.9635 |
| B_s2_weak_fallback | 2024 | 6 | 11.2633 | [9.0908, 19.7009] | 12.5242 | -4.6964 |
| B_s2_weak_fallback | 2025 | 3 | 11.5214 | [10.5214, 12.0214] | 12.1137 | +11.5214 |
| B_s2_weak_fallback | 2026 | 2 | 11.0057 | [6.5057, 15.5057] | 11.8901 | +11.0057 |
| B_s2_weak_fallback | pooled_2022_2026 | 44 | 9.4891 | [8.4620, 11.5741] | 10.7095 | -1.1368 |
| B_s2_weak_fallback | pooled_2021_2026 | 44 | 9.4891 | [8.4620, 11.5741] | 10.7095 | -1.1368 |
| B_transaction_sensitivity | 2021 | 72 | 8.4877 | [7.1720, 9.9716] | 9.7923 | +1.3317 |
| B_transaction_sensitivity | 2022 | 102 | 8.3796 | [7.5084, 10.9711] | 10.0813 | +0.8292 |
| B_transaction_sensitivity | 2023 | 117 | 8.6920 | [8.0625, 10.9555] | 10.4347 | +2.6064 |
| B_transaction_sensitivity | 2024 | 125 | 9.2608 | [6.8389, 9.9200] | 10.6607 | +1.6140 |
| B_transaction_sensitivity | 2025 | 141 | 8.7791 | [7.9255, 9.6788] | 10.4983 | +2.2903 |
| B_transaction_sensitivity | 2026 | 166 | 8.1259 | [7.1425, 11.6335] | 9.7563 | +2.5707 |
| B_transaction_sensitivity | pooled_2022_2026 | 651 | 8.6268 | [8.1403, 9.1988] | 10.2693 | +2.0598 |
| B_transaction_sensitivity | pooled_2021_2026 | 723 | 8.6129 | [8.1576, 9.0649] | 10.2228 | +1.9873 |

Join audit (minutes): 44851 obligation rows; 18444 without a gamelog outcome row (candidate did not appear, or outcome outside the owned regular-season universe); 231 where the outcome's team differs from the obligation's team (dual obligations of traded players -- the other team's row scores); 32 zero-minute rows excluded (conditional target); 26144 scored.

## Scope and caveats

- Stats covered: **points and minutes only.** The legacy lane never registered rebounds/assists/steals/blocks/threes/turnovers; those scoreboard rows remain ABSENT for the legacy column (PROBE_LEGACY.md).
- No `SEALED_RESULTS` path was read or written; no git command was run. The producer's own clean-tree receipt records commit `0108ef86e9c085e1d701e40e53c24dcde177ac97`; that identifier is reproduced from the receipt, not independently verified here -- the verified anchors are the manifest hashes and the producer source-set digest (checks 1-2).
- 2021 is an unfitted, fallback-only fold and 2021 outcome rows come from the pinned 2021 gamelog; 2021 cells are labelled and excluded from the headline pooled window.
- Evidence class PRELIMINARY per D036/D038: verified provenance, but a legacy artifact scored retrospectively by a different node -- not a program-registered, pre-declared evaluation (that would be VERIFIED).

