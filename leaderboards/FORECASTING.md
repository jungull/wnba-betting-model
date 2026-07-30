# Forecasting leaderboard — score/margin/total point error, by decision time

*Rendered 2026-07-30T21:41:45+00:00 from `C:\Users\jgallagher\wnba-betting-model\experiments\registry.jsonl` by evalharness.leaderboards (ROADMAP §Leaderboards). Every registered evaluation posts here — win or lose, every run. Unregistered results are void and cannot appear.*

## Frozen reference baselines (pinned permanently — never re-run, never removed)

| model | metric | value | sample | provenance |
|---|---|---|---|---|
| Naive home-advantage only | margin_mae | **11.22** | 308-game 2024-25 walk-forward test | experiments/channels/CHANNEL_EXPERIMENT_REPORT.md (game-level results table); HANDOFF.md §7 |
| RAW sum of channels (shifted-EWMA trends) | margin_mae | **10.53** | 308-game 2024-25 walk-forward test | experiments/channels/CHANNEL_EXPERIMENT_REPORT.md (game-level results table); HANDOFF.md §7 |
| Channel STRUCTURAL sum (incumbent champion) | margin_mae | **9.54** | 308-game 2024-25 walk-forward test | experiments/channels/CHANNEL_EXPERIMENT_REPORT.md (game-level results table); HANDOFF.md §4/§7 |
| Minutes B1: last-game carry-forward | minutes_mae | **5.42** | 2024 played rows with >=1 prior appearance, n=4,344 | project_docs/MINUTES_MODEL_SPEC.md §7 (baselines table) |
| Minutes B2: shifted season-to-date expanding mean | minutes_mae | **5.12** | 2024 played rows with >=1 prior appearance, n=4,344 | project_docs/MINUTES_MODEL_SPEC.md §7 (baselines table) |
| Market: average bookie (same-games comparison) *(market benchmark)* | margin_mae | **8.46** | 178 odds-covered games of the 308-game 2024-25 test | experiments/channels/CHANNEL_EXPERIMENT_REPORT.md; HANDOFF.md §7 |
| Market: best bookie (Circa) *(market benchmark)* | margin_mae | **8.82** | 2021-25 odds-covered games | HANDOFF.md §7 (key numbers reference) |
| Market: average bookie (all books) *(market benchmark)* | margin_mae | **9.28** | 2021-25 odds-covered games (all-books sample) | HANDOFF.md §7 (key numbers reference) |

## Registered experiment evaluations (FORECASTING)

| rank | experiment (run) | regime | decision time | primary metric | challenger | incumbent | Δ pooled | 90% CI (date-cluster) | gates 1-5 | verdict | n | evaluated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `w4_ref_fta_priors_v1` (run 1) | A | T-24h | ft_channel_mae | 4.3053 | 4.3044 | -0.0009 | [-0.0039, 0.0018] | 1:F 2:P 3:P 4:P 5:P | FAIL | 1346 | 2026-07-30 |
| 2 | `minutes_twostage_availability_v1` (run 1) | B | T-24h | minutes_mae | 4.6057 | 4.6428 | 0.0370 | [0.0116, 0.0613] | 1:F 2:P 3:P 4:· 5:P | FAIL | 13501 | 2026-07-30 |
| 3 | `minutes_ewma_vs_carryforward_v1` (run 1) | A | T-24h | minutes_mae | 4.6428 | 5.3913 | 0.7485 | [0.6899, 0.8029] | 1:P 2:P 3:P 4:· 5:P | **PASS** | 13501 | 2026-07-30 |
| 4 | `bottomup_3pt_channel_v1` (run 1) | B | T-24h | threep_channel_mae | 7.0614 | 7.1142 | 0.0528 | [-0.0425, 0.1471] | 1:F 2:P 3:F 4:F 5:P | FAIL | 1270 | 2026-07-30 |
| 5 | `chanreval_2026_structural_repaired` (run 1) | A | T-24h | margin_mae | 10.0860 | 10.7159 | 0.6299 | [0.3939, 0.8661] | 1:P 2:P 3:P 4:P 5:P | **PASS** | 673 | 2026-07-30 |
| 6 | `oracle_availability_bracket_v2` (run 1) | C | T-24h | margin_mae | 10.1555 | 10.1753 | 0.0198 | [-0.0241, 0.0625] | 1:F 2:P 3:P 4:· 5:P | FAIL | 627 | 2026-07-30 |
| 7 | `w2_zone_channel_integration_v1` (run 1) | A | T-24h | margin_mae | 10.2233 | 10.0860 | -0.1373 | [-0.2886, 0.0093] | 1:F 2:F 3:F 4:F 5:P | FAIL | 673 | 2026-07-30 |
| 8 | `w6_microsignal_retrospective_v1` **[QUARANTINED]** (run 1) | B | T-24h | absence_auc | — | — | 0.0278 | [0.0036, 0.0520] | 1:P 2:P 3:P 4:· 5:P | **PASS** | — | 2026-07-30 |
| 9 | `minutes_twostage_availability_v1` (run 2) | B | T-24h | minutes_mae | — | — | — | — | 1:· 2:· 3:· 4:· 5:· | — | — | 2026-07-30 |
| 10 | `oracle_availability_bracket_v2` (run 2) | C | T-24h | margin_mae | — | — | — | — | 1:· 2:· 3:· 4:· 5:· | — | — | 2026-07-30 |

Gate legend (ROADMAP §Standard promotion gate): 1 pooled improvement ≥ registered minimum · 2 90% clustered-bootstrap CI excludes harm beyond bound · 3 per-season non-inferiority · 4 joint forecast non-degradation · 5 coverage maintained. P=pass F=fail ·=not provided (visible, not hidden).
