# WNBA Prediction Engine — Full Project Handoff

> **Note (2026-07-30):** this is the historical handoff snapshot. The living plan — including
> the six AI-era workstreams (news/availability engine, zone maps, NBA transfer quarantine,
> ref model, closing-line model, playing-through-it detector) — is **[../ROADMAP.md](../ROADMAP.md)**.
> The §3 constitution below remains binding.

*Written July 29, 2026, by the Claude (Cowork) session that recovered and restarted this project. Audience: the Claude Code session (and John) picking it up. Everything below is verified against primary sources, not recalled.*

---

## 1. What this project is

Build a bottom-up WNBA game-outcome prediction engine that eventually **beats the betting market**, per the "WNBA V4" blueprint (Google Doc, John's Drive): player-level pace-adjusted forecasts → RAPM player impact ("player Elo") → minute-weighted roster aggregation driven by availability → probabilistic score-differential forecasts → calibration → edge detection vs market → fractional Kelly sizing. The player-level core was never built; that is the destination. The immediate goals are (in order): complete the datasets, re-validate the new channel architecture on full data, then build the player layer.

**End-goal metrics:** average bookie ≈ 8.5–9.7 MAE on score differential (sample-dependent); best bookie ≈ 8.8–9.3. Best honest team-level model to date: **9.54** (channel-structural, see §4). Success = beating average bookie out-of-sample, then positive CLV paper-trading. Long-term, the realistic money target is player props/totals, not spreads — the model's player-level outputs price those directly.

## 2. Where everything lives

- **GitHub (now public):** `github.com/jungull/wnba-betting-model` — working repo. Last substantive push Jul 2 2025; one Aug 28 2025 commit (tier-0 CSV). Contains: per-season player gamelogs 2021–2025-partial (parquet), **complete play-by-play for all 996 games** (`data/playbyplay/`), possession features, legacy odds subprojects, scripts.
- **Google Drive:** full mirror of the July 15 2025 project state (folder `wnba-betting-model`), including files never pushed: `Modeling/` tiers 1–1.8 with results, and `data/` master exports — `master_all.csv` (86MB), `master_player.csv`, `master_team_cleaned.csv`, `master_playbyplay.csv` (64MB), `master_odds.csv` (328-col hourly odds snapshots). Also planning docs: **WNBA V4** (the blueprint), WNBA v3, Master Plan, "ball", and 4 Cursor session transcripts (the project's lab notebook).
- **Missing everywhere:** `modeling_v2/` (the Tier-1 rebuild + Tier 2 RF 9.81 champion + repaired-2023 granular data) exists at best on John's machine — search for it (`modeling_v2` with `tier_0_baseline`, `tier_1_four_factors`, `tier_2_expanded_stats` subfolders). If found: commit it. If not: nothing blocking — the channel architecture (§4) supersedes it and recipes are re-derivable.
- **Other repos:** `jungull/a`, `jungull/astro-sports` (zodiac/horoscope-sentiment experiment), `jungull/Ball2` (earlier NBA incarnation). Historical interest only.
- **This handoff bundle** also contains: the recovery report, data audit, channel-experiment report + code, and `collect_refresh.py`. Suggest committing the docs to `project_docs/` and the experiment to `experiments/channels/`.

## 3. The constitution — hard-won rules, do not re-learn these

1. **Leakage is the project-killer.** Three "breakthroughs" (MAE 5.28, 7.35, 7.91) were all leakage: `is_blowout_win`, `team_plus_minus` containing the current game's result, and pandas `.ewm()` without `.shift(1)`. **Every trend feature must be shifted; every good result gets audited before it gets believed.** Reusable audit scripts: `Modeling/tier1.8/scripts/audit_*.py`, `verify_walk_forward.py`, `verify_target_leakage.py` (in Drive mirror).
2. **Walk-forward always.** Train 2021–2023, test 2024+; ≥5 prior same-season games per team for any prediction row; features reset per season.
3. **Shifted EWMA with low alpha (0.05–0.15) wins the forecasting bake-offs.** AR never won once across hundreds of team-stat combos. Tune alpha per channel (or per team-stat) on train years only.
4. **Complexity subtracted value at the team level.** Pace normalization hurt in 3 controlled tests. Venue adjustment ≈ ±0.02. Tier 1.7's 8-step pipeline lost to Tier 1.5's 3-step. Speculative interaction features hurt (10.24 vs 9.53 baseline). Only composites encoding accounting identities or matchup structure have ever helped.
5. **Granular beats aggregate:** decomposing points into components (paint/fastbreak/2nd-chance/FT/3pt) produced the two biggest legitimate gains in project history.
6. **Composites replace their ingredients, never stack alongside them** (collinearity: see the -705 coefficient on `fg_pct` in `feature_importance_1.8.1.csv`).
7. **Odds are benchmarks, never features.**
8. **No imputation of missing raw data — go get the real data.** (John's standing rule.)
9. **More rows always helped; more columns only when genuinely new information.**
10. Documentation conventions: single leaderboard MD ranked by MAE with bookie rows included; feature-importance CSV per model; feature dictionary with source + derivation per feature; CSVs preferred over parquet for hand-inspectable outputs.

## 4. Current architecture decision (July 2026 experiment — adopted)

**Channel decomposition with structural chains** beat everything (full report + code in bundle):

- Score = sum of 4 channels per team: FT points, 3pt points, paint points, non-paint 2s. Box-identity verified.
- Each channel predicted by a **structural chain**: own-tendency trend × (opponent-allowed trend ÷ league avg) × conversion trend — all shifted EWMA, within-season.
- Test (308 walk-forward games, 2024–25): structural sum **9.54 MAE** vs raw-trend sum 10.53, monolithic ridge 9.60–10.86. P>99.99% paired bootstrap. Passed shift audit, perturbation probe, strict league-mean rebuild.
- Channel calls: FT & 3pt structural (confident), paint structural (provisional — retest after 2023 repair), non-paint-2s raw. Final calibration stage: train-years-only linear (slope ≈ 0.78 shrinkage + home-court intercept ≈ +1.5).
- Same-games bookie comparison: avg bookie 8.46 vs model 9.04 on the 178 odds-covered test games. Gap ≈ tonight-specific info (lineups/minutes) the model doesn't have.
- **Why this architecture matters:** each channel decomposes naturally into Σ(player rate × expected minutes) — it is the scaffold the player layer bolts onto.

## 5. Data state and the immediate task

Verified inventory (see DATA_COMPLETENESS_AUDIT.md for the full table): gamelogs+PBP complete 2021 → Jul 3 2025 (996 games, incl. 2022–24 postseasons); odds full 2023–24, 76% of 2022, none for 2021, none after Jul 4 2025.

**Gaps to fill — `collect_refresh.py` (in bundle) does all of this in one resumable run (~60–120 min):**
- 2023 misc/advanced stats repair (broken in every surviving copy: 480/520 team-games zero paint/PFD — blocks paint channels for a train season)
- 2021 postseason (~15 games)
- 2025 after Jul 3 (regular + playoffs, ~190 games)
- 2026 season to date (15 teams — **Toronto Tempo and Portland Fire are new; team-ID mappings need updating** in any script with a hardcoded team list)

Run it from the repo root on John's machine (needs open internet — stats.wnba.com; `pip install nba_api pandas pyarrow`), validate `data/refresh_2026/collection_report.json` (`2023_misc_sample_nonzero_paint` should be ~50/50), push branch `data-refresh-2026`.

**Odds going forward (decision pending with John):** free Odds API tier (500 credits/mo) supports ~1 snapshot/day live capture but cannot backfill (10× credit cost). One paid month would backfill Jul 2025→now in a sweep. Keys currently in the repo are John's (he's fine with them being there); The Odds API endpoint quirk: don't double the `/v4` in `historical_odds_api_fetcher.py`'s BASE_URL.

## 6. Roadmap after the data run

1. **Rebuild masters** with repaired 2023 + new seasons; regenerate `channel_base` (builder script in bundle); re-run channel experiment with 2026 as third test season. Watch the expansion teams — thin history will stress the ≥5-games rule; consider league-prior fallback for their first games.
2. **Player layer, in this order** (the V4 thesis, finally):
   a. **Expected minutes model** + availability ingestion — the books' edge is lineup news; this is the highest-leverage build. WNBA injury reports + rotation trends; even a simple minutes-EWMA × active-flag beats nothing.
   b. **Per-player per-100 channel rates** (3PA rate, 3P%, FTr, paint rate…) with the existing bake-off machinery pointed at `master_player.csv`. First test: 3pt channel as Σ(player 3PA×3P%×exp minutes) vs team-level chain — the first true test of bottom-up vs top-down.
   c. **RAPM** from the 996+ PBP files (offense/defense, ridge on possession stints) — the "player Elo."
   d. Minute-weighted aggregation replacing/ensembling team chains.
3. **Then** calibration (isotonic), edge model vs the hourly odds snapshots in `master_odds.csv` (supports CLV backtesting), fractional Kelly, paper-trade 2026.

## 7. Key numbers reference (honest results only)

| Model | MAE | Sample |
|---|---|---|
| Best bookie (Circa) | 8.82 | 2021–25 odds-covered |
| Avg bookie | 9.28 / 9.67 / 8.46 | three samples: all-books / 2025-active / channel-test-178 |
| **Channel structural sum (current champion)** | **9.54** | 308 games 2024–25 |
| Tier 2 RF (granular stats, lost code) | 9.81 | 2024–25 |
| Rebuilt Tier 1 3-factor RF | 10.16 | 2024–25 |
| Tier 1.5 MLP/LR | 10.22/10.23 | 2024–25 |
| Tier 1.8.1 LR (certified-clean floor) | 10.35 | 2024–25 |
| Raw-trend channel sum | 10.53 | 308 games |
| Naive home-advantage only | 11.22 | 308 games |

Never trust a new result below ~9.5 without running the full audit battery. Every prior sub-9.5 was leakage.

## 8. Context on John's preferences (from transcripts + this session)

Goal-oriented — cares about reaching the end goal, not preserving old code. Instinct-driven and usually right (called the is_blowout_win leak himself; predicted the composite-features result). Wants maximal granularity ("no totals — give me the pieces"), refuses imputation, rejects streak features as superstition, prefers CSVs he can open, wants a running leaderboard with bookies in it, and wants feature dictionaries kept current. Push back with evidence, run isolated experiments, keep the leaderboard honest.
