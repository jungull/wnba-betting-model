# Forecasting leaderboard — score/margin/total point error, by decision time

*Rendered 2026-07-30T18:06:28+00:00 from `C:\Users\jgallagher\wnba-betting-model\experiments\registry.jsonl` by evalharness.leaderboards (ROADMAP §Leaderboards). Every registered evaluation posts here — win or lose, every run. Unregistered results are void and cannot appear.*

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
| 1 | `minutes_ewma_vs_carryforward_v1` (run 1) | A | T-24h | minutes_mae | 4.6428 | 5.3913 | 0.7485 | [0.6899, 0.8029] | 1:P 2:P 3:P 4:· 5:P | **PASS** | 13501 | 2026-07-30 |

Gate legend (ROADMAP §Standard promotion gate): 1 pooled improvement ≥ registered minimum · 2 90% clustered-bootstrap CI excludes harm beyond bound · 3 per-season non-inferiority · 4 joint forecast non-degradation · 5 coverage maintained. P=pass F=fail ·=not provided (visible, not hidden).
