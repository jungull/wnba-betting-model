# WNBA Prediction Engine — Recovery Report & Rebuild Assessment

*Prepared July 29, 2026 · Sources: Google Drive mirror of `wnba-betting-model` (snapshot July 15, 2025), planning docs (WNBA V4, v3, Master Plan, "ball"), 4 Cursor session transcripts, legacy odds-system repos*

---

## 1. The original vision (unchanged, still sound)

The core hypothesis across every version of the plan (ball → Master Plan v2 → WNBA v3 → **WNBA V4**): a **bottom-up, player-level model** will beat top-down team-average models. The V4 blueprint specified:

1. Per-player, pace-adjusted performance rates (per-100-possessions), forecast with a per-player/per-stat "champion model bake-off" (EWMA vs AR vs rolling windows, walk-forward validated)
2. **RAPM** (regularized adjusted plus-minus) to isolate each player's true impact, adjusted for teammates and opponents — this is the "player Elo" you described
3. K-means player archetypes (offensive K=6, defensive K=4, general K=7) for synergy/matchup modeling
4. Team profiles built by **minute-weighted aggregation** of player features, driven by health/availability and expected minutes
5. Contextual layers per player (road performance, rest, post-loss response, volatility scores)
6. Probabilistic score-differential forecasts → calibration (isotonic) → edge detection vs market → fractional Kelly sizing → Monte Carlo risk

**Key gap: the player-level core (steps 1–5) was never fully built.** The project got consumed by team-level modeling tiers and data-hygiene battles. RAPM, archetypes, minute-weighted aggregation, and the player bake-off exist only as plans (T1.1–T1.3 folders are scaffolded READMEs with empty results files).

## 2. What was actually built

### The modeling tiers (wnba-betting-model repo, `github.com/jungull/wnba-betting-model`)

| Tier | What it is | Honest result (MAE, score differential) |
|------|-----------|------------------------------------------|
| 0 | Bookmaker baseline (23 books, 2021–25 odds) | Best 8.82 (Circa) · Avg 9.28 · Worst 10.78; recomputed for 2025-active books: 9.26 / 9.67 / 11.21 |
| 1 | Four Factors only, per-team/stat/season tuned EWMA | LR 10.87 · rebuilt 3-factor RF **10.16** (dropping oreb_pct helped) |
| 1.5 | All team stats (~213 features), shifted EWMA | MLP 10.22 · LR 10.23 · RF 10.26 |
| 1.7 | "Normalize First, Then Trend" + battle differentials (47 features) | RF 10.71 — *worse* than 1.5; over-engineering post-mortem written |
| 1.8 | Forensic leakage audit ("Great Reset") | Certified-clean benchmark: LR **10.353** |
| 2 | Granular component stats (~31 features), two-stage bake-off | RF **9.81** — best legitimate model, beats worst bookie, approaches average bookie |

**Bottom line when abandoned: best honest model ≈ 9.8 vs average bookie ≈ 9.3–9.7 and best bookie ≈ 8.8–9.3. Close, but no edge yet — and the part of the plan most likely to create the edge (player-level modeling) was still on the shelf.**

### The data assets (the real treasure)

All in Drive under `wnba-betting-model/data/` (not downloaded to this workspace; too large, but intact):

- `master_all.csv` (86 MB) — unified player-game rows, 2021–2025, 91+ columns incl. advanced ratings
- `master_playbyplay.csv` (64 MB) — play-by-play (the RAPM prerequisite you never got to use)
- `master_player.csv` (5.5 MB), `master_team_cleaned.csv`
- `master_odds.csv` (5.3 MB, **328 columns** — per-bookmaker odds with hourly snapshots 1h–24h before tip) plus 23 raw historical-odds JSON snapshots from The Odds API
- `data_columns_inventory.txt` — full schema documentation
- Tuned EWMA alpha tables (per team/stat/season) for tiers 1, 1.5, 2

This is 4+ seasons of collected, cleaned, schema-documented data **including the paid odds history**. Even with the Odds API subscription lapsed, the history is preserved.

### Legacy subprojects

- **wnba-odds-aggregator** — production-grade live-odds collector (SQLAlchemy, scheduler, systemd, Docker) built around The Odds API
- **wnba_odds_system / scrapers** — the "free odds" scraping campaign: OddsPortal, VegasInsider, BetInf, OddsShark. **Verdict from your own logs: 0 records collected, ever.** Scraping failed on rate limits and 404s; the paid API was what worked.
- **wnba-prediction-engine** (earlier repo, `gallagjj/wnba-prediction-engine`) — the V4-era acquisition/processing/modeling pipeline
- **astro-sports** — Gemini AI Studio experiment scoring player zodiac signs + daily horoscope sentiment against performance (prototype code saved; the repo itself wasn't in Drive)
- **Ball2 / "a"** — earlier NBA-focused incarnation (the 2024 Gemini era); the NBA session transcript is saved in `docs/untitled_doc_2.md`

## 3. The hard-won lessons (do not re-learn these)

1. **Data leakage was the recurring project-killer.** Every "breakthrough" (MAE 5.28, 7.35, 7.91) was leakage: `is_blowout_win`, `team_plus_minus` containing the current game's result, and pandas `.ewm()` without `.shift(1)`. Tier 1.8's audit scripts (`audit_plus_minus_feature.py`, `verify_target_leakage.py`, `verify_walk_forward.py`) are reusable and should gate every future experiment.
2. **Simple, shifted EWMA with low alpha (≈0.1) beat everything** in the forecasting bake-offs — AR never won once. Per-player alpha tuning is cheap and already coded.
3. **Complexity subtracted value at the team level.** Pace normalization hurt in all three controlled tests; venue adjustment gained ~0.02 MAE; 8-step feature pipelines lost to 3-step ones. "More sophisticated is not better" is written in your own post-mortem.
4. **Granular component stats (points in paint, 2nd-chance, pts off TOV, fastbreak) carried real signal** — Tier 2's 9.81 came from decomposing broad stats, not from fancier math.
5. **Shooting efficiency differentials (3P%, FT%) dominate feature importance** in clean models.
6. **Walk-forward discipline works.** Train 2021–23, test 2024–25, never let the current game touch its own features. The infrastructure for this exists and is debugged.
7. **Odds belong in benchmarks, never in features** (your explicit design rule — it kept the model honest).

## 4. Data source status today (July 2026)

- **WNBA stats (via `nba_api`, stats.nba.com / stats.wnba.com backend):** free, no key, still actively maintained. Your fetch scripts should still work with minor endpoint-drift fixes (the API silently renamed fields before — e.g. OPP_FOULS→PFD — and your scripts already have sanity checks for that). Note: blocked from this particular cloud sandbox's network, so collection runs need to happen on your machine (or any normal environment).
- **The Odds API:** your paid key lapsed, but there's a free tier — 500 credits/month, no card. That's enough for a few live-odds snapshots per day during the season on one sport with 1–2 markets, but historical backfill costs 10× credits (≈8 historical snapshots/month) — not viable for backfill. The good news: **you don't need backfill for 2021–2025; you already own that data.** The gap to fill is only late-2025 → today.
- **Free scraping for odds:** conclusively failed last time; not worth revisiting.
- **Security note:** two Odds API keys are hardcoded in the repo (`fetch_historical_wnba_spreads.py`, `.env`, `historical_odds_api_fetcher.py`). Lapsed or not, rotate/remove them before any repo goes public.

## 5. Rebuild recommendation — aimed at the end goal, not at recycling

The end goal: **beat the average bookmaker (≈9.3–9.7 MAE), then the best (≈8.8–9.3), and find calibrated edges worth betting.** The gap to close from the best honest model is ~0.5–1.5 points of MAE — real but plausible, and the academic literature you cited (RF ≈9.2 vs market ≈8.8) suggests the ceiling is near the market, meaning the win probably comes from *player-availability information speed* rather than better curve-fitting on team stats.

**Keep (high value, already paid for):**
- The master datasets + schema inventory (2021–2025, incl. odds history)
- Tier 0 bookmaker benchmark methodology and the leakage-audit scripts as a permanent test gate
- The walk-forward harness and the shifted-EWMA feature code
- Tier 2's granular-stat feature set (current best: RF 9.81)
- The V4 blueprint as the north star — it was never disproven, just never finished

**Discard / don't rebuild:**
- All odds-scraping code (proven dead end)
- Tier 1.7's normalization pipeline (proven net-negative)
- The tangle of duplicate folders (T1.x vs Modeling/tier1.x vs modeling_v2) — start one clean repo, port only the keepers

**Build next (the unfinished 20% that carries the thesis):**
1. **Player expected-minutes model + availability ingestion** — this is where books are beatable: WNBA injury/rotation news moves lines slowly compared to NBA. Your own plan flagged it; it was never built.
2. **Player-level per-100-possession forecasts** (the bake-off machinery already exists — point it at `master_player.csv`)
3. **RAPM from the play-by-play you already collected** (64 MB sitting unused — the "player Elo" core)
4. **Minute-weighted team aggregation** replacing team-stat EWMAs as model input, with Tier 2 features as the fallback/ensemble partner
5. **Then and only then**: calibration, edge model vs market, fractional Kelly — using your preserved hourly odds snapshots to backtest edge detection realistically (CLV measurement was in the plan and the 1h–24h snapshot data supports it)
6. **Resume live odds capture** on the free Odds API tier (1 snapshot/day fits comfortably in 500 credits) so the benchmark stays current for 2026.

A practical sequencing note: the 2026 WNBA season is underway — a rebuilt pipeline can be validated walk-forward on 2024–2026 with three test seasons instead of two, and paper-traded live before any real sizing.

---

*Local mirror: 373 files under `/home/claude/wnba/` (Modeling tiers, T-folders, legacy subprojects, planning docs, cursor transcripts, manifests listing every skipped binary). The full git repo (.git included) remains intact in Drive if the GitHub copy is ever lost.*
