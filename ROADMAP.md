# ROADMAP — WNBA Prediction Engine

*Created 2026-07-30. This is the living plan; it supersedes the phase outline in
`project_docs/HANDOFF.md` §6 (kept unchanged as the historical record). The constitution in
HANDOFF.md §3 governs every item below: walk-forward always, every trend feature shifted,
leakage audit before believing any result, isolated experiments, composites replace their
ingredients, odds are benchmarks never features, no imputation — go get the real data.*

**Status stamps reflect 2026-07-30.** Six AI-era workstreams (W1–W6) are integrated into the
standing phase plan. Statuses: **build-in** (on the critical path, ships into the model after
passing its gate) vs **quarantined experiment** (isolated; must beat the incumbent baseline on
walk-forward error before promotion; result reported on the leaderboard either way).

---

## Phase 0 — Dataset completion & certification — ✅ effectively DONE (tonight)

| Item | Status 2026-07-30 |
|---|---|
| 2021 postseason + 2023 misc repair + 2025 completion + 2026 to date (`collect_refresh.py`, V3 endpoints) | ✅ done — 0 permanent failures; 2023 paint 50/50 nonzero |
| Per-game misc/advanced for 2021R/2022/2024 + 2023 advanced (`collect_misc_backfill.py`) | 🔄 running tonight |
| Odds: July 2025→now backfilled (292 snapshots), live capture 2×/day (`WNBA_OddsCapture`) | ✅ done / live |
| Injury report capture 2×/day, official PDF + ESPN fallback (`WNBA_InjuryCapture`) | ✅ live since today |
| Historical injury/absence archive 2021→now (`scrape_injury_history.py`) | 🔄 finishing tonight |
| Starters / stints / minutes from all 1,424 PBP games (`derive_lineups.py`) | ✅ done — median error 0.00 min vs box |
| Playoff player-gamelog season files (2022–24) + V3 refetch of 17 stray files | queued behind backfill |
| Full certification (`audit_completeness.py` → AUDIT_REPORT.md) | queued last |

## Phase 1 — Foundation rebuild & channel re-validation (next session)

1. **V2/V3 normalizer module** — shape already decided by the stint work: two thin schema
   parsers feeding one shared event/column model. One module, tested on games in both eras.
2. **Master rebuild from raw** (all seasons uniform) + row-level diff vs the July-15 Drive
   masters on the overlap span. Unexplained mismatch stops the line.
3. **Channel re-validation**: regenerate `channel_base.csv`; re-run the structural-chain
   experiment with repaired 2023; walk-forward test on 2024, 2025, 2026 separately;
   league-prior fallback for expansion teams' first games (GSV '25, TOR/PDX '26).
   - **Gate:** structural sum ≤ raw-trend sum and ≤ monolithic on all three test seasons;
     paint channel promoted from provisional (or demoted, with the evidence written down).
   - Deliverable: refreshed leaderboard MD with bookie rows on the enlarged odds sample.

## Phase 2 — Player layer

### 2a. W1 — News → Availability Engine (build-in; highest priority)
- **Purpose:** close the documented ~0.8 MAE gap vs average bookie, which is tonight-specific
  lineup/minutes information. Feeds the two-stage minutes model (`project_docs/MINUTES_MODEL_SPEC.md`).
- **Data:** `data/injury_capture/` (live since today — official designations 2×/day with
  designation-progression history), plus daily news text: beat-reporter feeds, team sites,
  coach pressers. Every raw text and every extraction logged for audit.
- **Build sketch:** daily LLM extraction job → structured per-player rows: `P(plays)`,
  expected-minutes delta, rotation-change flags, confidence, source citations. Backfill-test
  on the historical injury archive where dates allow.
- **Validation gate:** extracted signals must improve walk-forward minutes MAE over the
  shifted minutes-EWMA × active-flag baseline. Measured floors to beat (2024, played rows):
  carry-forward 5.42, expanding-mean 5.12. No gate pass → no entry into the main model.
- **Slot / status:** Phase 2a / build-in.

### 2b. W2 — Zone Capability Maps (build-in)
- **Purpose:** upgrade each channel chain to zone-tendency × opponent-zone-defense ×
  conversion; matchup overlays (our O-map minus their D-allowed map) become channel inputs.
- **Data:** `shotchartdetail` (stats API, LeagueID 10), all seasons — one more per-game/per-season
  crawl to add to the collection scripts (endpoint unaffected by the V2 boxscore retirement;
  verify on one game before the full pull, per today's V3 lesson).
- **Build sketch:** per-team and per-player zone efficiency (O and D-allowed); overlay
  differentials per matchup; split player scoring into shot-quality-created vs shot-making
  (xP model) — quality persists, making regresses.
- **Validation gate:** per-channel walk-forward MAE vs the current structural chains; swap in
  only the channels that improve. Composites replace ingredients — never stack.
- **Slot / status:** Phase 2b / build-in.

### 2c. RAPM — the player Elo (build-in)
- **Data: ready today** — `data/derived/stints.parquet` (116,317 stints, all 1,424 games,
  exact to the boxscore) awaits possession attribution from the normalizer.
- Ridge regression on possession stints, offense/defense split, within-era priors.
- **Gates:** face validity (known stars rank sensibly), year-over-year stability, and the
  minute-weighted aggregation must beat/tie team chains before replacing them.

### W3 — NBA Transfer Learning (QUARANTINED experiment; after 2c exists)
- **Hypothesis:** pretrain player/lineup embeddings or possession-sequence models on NBA PBP,
  fine-tune on WNBA to beat small-sample limits.
- **Documented concern (John):** playstyle divergence (e.g., dunking changes interior
  dynamics) may import drift, not signal. Hence quarantine.
- **Validation gate:** must beat the WNBA-only equivalent (classic RAPM / WNBA-only
  embeddings) on walk-forward MAE. Comparison reported on the leaderboard **either way**.
- **Slot / status:** experiment queue, low priority until RAPM baseline exists / quarantined.

### W4 — Referee Model (Phase 2 sidecar; build-in)
- **Purpose:** refs have persistent foul/FTA-rate tendencies and assignments publish pre-game;
  the FT chain already reserves the slot (drawn-rate × committed-rate × **ref adjustment**).
- **Data:** officials per game from the boxscore-summary endpoint (verify V3-era health on one
  game first; ~1,500-game crawl, same checkpoint pattern) + daily assignments page going forward.
- **Build sketch:** per-ref shrunken foul/FTA priors (league-mean prior, games-reffed weight).
- **Validation gate:** FT-channel walk-forward MAE improves vs current FT chain.
- **Slot / status:** Phase 2 sidecar / build-in (small, cheap, bounded).

### W6 — Playing-Through-It Detector (experiment queue)
- **Purpose:** flag degraded-but-active players before official news.
- **Data: inputs exist today** — rolling FT%, stint-length trends (`stints.parquet`),
  rim-attempt share (W2 zones once pulled), vs the historical injury archive as ground truth.
- **Validation gate (retroactive first):** historical flags must precede documented injury
  news at better-than-chance rates. Promote to a live minutes-model input only if yes.
- **Slot / status:** experiment queue / worth a try, after W1's plumbing exists.

## Phase 3 — Betting & sizing engine

### W5 — Closing-Line Model (build-in; the Phase 3 foundation)
- **Purpose:** the engine bets only when the game model disagrees with the **predicted close**
  — a CLV filter, not just a vs-current-line edge.
- **Data: trainable now** — snapshot sequences in `data/drive_masters/master_odds.csv`
  (2022–Jul 2025, ~5-min cadence) + `data/odds_capture/historical/` (Jul 2025–now, 2/day)
  + live 2×/day capture forward.
- **Build sketch:** predict close from open + line path + elapsed news flow (W1 outputs);
  evaluate close-prediction error by book; then edge = model line vs predicted close.
- **Validation gate:** beats "close = current line" and "close = open" naive baselines on
  held-out seasons; then positive simulated CLV on walk-forward bets.
- Then: calibration (isotonic) → fractional Kelly → **paper-trade the rest of 2026**.
- **Gate to real money (John's call):** beat avg-bookie MAE out-of-sample AND sustained
  positive paper CLV.

---

## Leaderboard conventions (extended)

Single `LEADERBOARD.md` ranked by MAE with bookie rows always present (existing rule), plus:
- **Minutes section:** baselines pinned (carry-forward 5.42, expanding-mean 5.12 on 2024);
  every W1 variant posts here before touching the main model.
- **Per-channel section:** current structural chains are the incumbents; W2/W4 variants post
  per-channel MAE next to them.
- **Quarantine section:** W3 and W6 results reported win or lose — negative results are
  results (the astrology rule).
- **W5 section:** close-prediction error vs the two naive baselines + simulated CLV.
- Per model: feature-importance CSV + feature-dictionary entries (existing rules).

## Explicitly rejected (do not add)
- Social sentiment features
- Streak/momentum narrative features
- Broadcast-video CV tracking — parked as moonshot; revisit only if the engine consistently
  beats the close
- Astrology (the `astro-sports` experiment stays retired)

## Critical path
**Data refresh ✅ (2026-07-30) → channel re-validation → W1 + expected-minutes model → W2
zones → RAPM (then W3 quarantine test) → W4 refs → W5 closing-line → Kelly sizing engine →
paper-trade 2026.**
