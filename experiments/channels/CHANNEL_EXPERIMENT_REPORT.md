# Channel Decomposition Experiment — Raw Trends vs Structural Chains

*July 29, 2026 · data: master_team_cleaned.csv + master_player.csv (2021 – Jul 2025) · code: `run_experiment.py` in this folder*

## The question

Should scoring be predicted as raw stat trends, or as structural "chains" (own tendency × opponent tendency × conversion rate) per scoring channel — with final score differential as the **sum of validated sub-predictions** instead of one monolithic regression?

## Setup (inherits the project's hygiene rules)

- Four channels per team-game: **FT points** (FTM), **3pt points** (3 × FG3M), **paint points** (player-agg), **non-paint 2s** (2·(FGM−FG3M) − paint). Box-score identity verified on all 2,132 rows: 0 violations.
- All trends are shifted EWMA, within-season, alpha tuned per channel on train years only (winners: 0.05–0.10, consistent with the old bake-offs).
- Structural chains: e.g. expected FT pts = FTA-trend × (opponent's fouls-committed trend ÷ league avg) × FT%-trend. Same smoothing as raw, so the test isolates *structure*, not tuning.
- Walk-forward: train 2021–23 (2021–22 for paint channels), test **2024–25, n = 308 games**, ≥5 prior games per team.
- **Known data flaw handled:** 2023 paint/fouls-drawn data is corrupted in this export (480/520 rows zero — the documented 2023 granular gap). 2023 excluded from paint-channel streams.
- **Leakage audits passed:** (1) 30-sample manual recomputation of shifted EWMAs — 0 mismatches; (2) perturbing a game's own stats leaves its feature row unchanged; (3) league averages rebuilt to use strictly-earlier dates only (result unchanged: 9.51 → 9.54).

## Channel-level results (test MAE, points in that channel)

| Channel | Raw trend | Structural chain | Δ | P(structural better) | Call |
|---|---|---|---|---|---|
| 3pt points | 7.05 | **6.78** | −0.27 | 99.8% | **swap to structural** |
| FT points | 4.14 | **4.06** | −0.08 | 95.8% | **swap to structural** |
| Paint points | 6.67 | **6.60** | −0.07 | 76.0% | swap (weak evidence) |
| Non-paint 2s | **3.40** | 3.56 | +0.16 | 0.2% | **keep raw** |

Pattern: structure helps most where opponent defense is a real filter (3-point volume/quality allowed, foul discipline). It hurts on non-paint 2s — the noisiest, lowest-volume channel, where the opponent adjustment multiplies noise into a thin signal.

## Game-level results (score differential, test MAE, n=308)

| Model | Test MAE |
|---|---|
| **STRUCTURAL sum of channels** | **9.54** |
| MONOLITHIC ridge (raw + structural features) | 9.60 |
| HYBRID sum (per-channel winners) | 9.66 |
| RAW sum of channels | 10.53 |
| MONOLITHIC ridge (raw trends only) | 10.86 |
| Naive (home advantage only) | 11.22 |

Paired bootstrap, structural vs raw sum: **P(better) > 99.99%, mean improvement −0.99 points of MAE.** Holds in both test seasons (2024: 8.97 vs 10.02; 2025-partial: 11.19 vs 11.99).

Benchmarks on the 178 test games with odds coverage (identical games, apples-to-apples): average bookie **8.46**, structural sum **9.04**. Reference: the project's previous best honest model was Tier 2 RF at 9.81 (different sample — indicative, not strictly comparable).

## The call

1. **Adopt the structural-chain architecture.** Sum-of-channels with opponent-adjusted chains beats every raw and monolithic variant tested, including a ridge given *both* feature sets — the structure itself, not extra data, carries the gain. This vindicates the "correct composites beat discovered correlations" principle: all three chains encode accounting identities and matchup logic, not speculative interactions.
2. **Swap channels: FT and 3pt to structural definitively; paint to structural provisionally** (re-test when the repaired 2023 granular data is recovered from the repo/API).
3. **Keep non-paint 2s raw** at the channel level; at the game level the full-structural sum still won, so carry both variants until the next re-test on a bigger sample.
4. **Replace ingredients, don't stack them** — the chains go into the model *instead of* their raw components, per the established anti-collinearity rule.
5. Calibration slope on the sum is 0.78 — trend sums overstate spread and want shrinkage; keep the train-years-only linear calibration as a permanent final stage.

## Caveats

- 308 test games is one split; the 2025 season is partial (through July 12, 2025) and includes an expansion team (GSV) with thin history.
- The old tiers' 9.81 was computed on a different sample and feature set; the clean claim is the *internal* comparison: structure beat raw by ~1 MAE point on identical games.
- Books remain ahead (8.46 vs 9.04 on covered games). The remaining gap is tonight-specific information — lineups and minutes — which no trailing-trend feature can close. The chains decompose naturally into player terms (channel = Σ player rate × expected minutes), which is the designed next step.
