# RANKED_GAPS — what to ingest next, ranked

E1_I0057, 2026-08-17. Ranked by (a) is the raw data obtainable, (b) does this program's own record
already suggest it matters, (c) cost to ingest.

Every entry carries its closed-surfaces check. `CLOSED_SURFACES.md` was read first. **Nothing here
resurrects rest, travel, pace, foul history or starter transitions** — those are `REAL_NULL` under
D076/D085/D090 and the schedule family is closed by D090 ruling 5.

The ranking is deliberately front-loaded with things **already sitting on disk**. The owner's thesis
is "find what data they have that we don't". The first four rows are data *we* have and have never
opened.

---

## Rank 1 — The T-1.16h player-points line as a scored benchmark (2024 + 2025 + 2026)
**File:** `data/props_capture/historical/master_props_historical.csv` — already captured.

- **Obtainable:** already on disk. 36,946 rows, 100% of 2024 games, 100% of 2025, 90% of 2026.
- **Does the record say it matters:** this is the single question D137 asks. The program has never
  once scored a player forecast against a posted price. Everything it knows about its own skill is
  measured against internal references (D094: a tuned simple estimator beats the champion — but
  against *what a book would have charged*, unknown).
- **Cost:** ~1 day. The join is done and reproducible (`scripts/s15`, `s16`); 1,972 / 2,410 / 1,984
  played rows land by `(game_id, normalised player name)` with no fuzzy matching required.
- **Closed-surfaces check:** §7 records "Market comparison on the exploration partition — SCOPE:
  **impossible**, not refuted", citing `bookie_totals_per_game.csv` (0 in-partition rows) and
  `game_level_totals.csv` (229 rows, market column 100% NULL). Both statements are about **game
  totals** and both are correct. E1_I0013's own env audit **did see** these 11,237 rows of 2024
  player props and ruled: *"PLAYER PROPS, not game totals; covers only the tail of one of four
  exploration seasons and extends into the forbidden holdout"* — the right verdict **for a
  game-tempo question**. Under D137 the object of study is the player, so "player props, not game
  totals" stops being a disqualification and becomes the point; and "extends into the holdout" stops
  being a defect and becomes the property that makes it a cross-partition yardstick (see
  `REGIME_BOUNDARY.md` §5). **This is not a resurrection — it is the same file read against a
  different question.**
- **What it would settle:** whether this program forecasts player points better or worse than the
  market did 70 minutes before tip, on 6,366 player-game rows across three seasons. That is the
  owner's question, answerable with zero acquisition.
- **Honest limit:** one snapshot per event, points only, 79–130 players per season, ~34% of rows.
  It benchmarks; it does not support line-movement work.

## Rank 2 — Wire the research lane to the data the production lane already reads
**Not an ingest. A path fix.**

- **Obtainable:** the files exist; the screens simply cannot see them.
- **The mechanism, verified:** the `data/` directory inside the worktree the screens run in is
  **missing six directories that exist in the main repo** — `drive_masters`, `entity_resolution`,
  `injury_official_live`, `market_snapshots`, `odds_capture`, `sxbet_capture`. All six are named in
  `.gitignore`. E1_I0013's `step0_env_audit.json` records `"master_odds_hits": []` — the screen
  looked for the odds master, correctly found nothing, and correctly concluded market comparison was
  impossible **in that worktree**. The conclusion was true and the premise was an artefact of where
  it ran.
- **Cost:** hours. Point the screens' `DATA` root at the main repository, or un-ignore the capture
  directories, or add a manifest that resolves them.
- **Closed-surfaces check:** not a surface. This is the *cause* of a closed surface.
- **Why it ranks this high:** it is the cheapest item on the list and it silently invalidates the
  scope of at least one recorded impossibility. Until it is fixed, every future screen will re-derive
  the same wrong environment.

## Rank 3 — Official injury designations as a *feature*, not just an exclusion rule
**Files:** `data/injury_capture/injury_log.csv` (2026-07-30 →, hourly),
`data/injury_official_live/` (2026-08-07 →, PT15M, interval-censored transitions).

- **Obtainable:** captured, running, updated within the hour of this audit.
- **Does the record say it matters:** D089 named the teammate-volume tip-time variant the program's
  largest positive and then correctly refused to quote it, because **~49.2% of the channel is
  same-day news**. That number is the program's own estimate of the size of this gap. `p_active`
  (D090) is separately recorded as carrying an **11.5 pp** over-pessimism on returns from long
  absence and a **7.7 pp** void-risk under-estimate in the 0.50–0.80 band — "the most directly
  monetisable finding of the session". A designation feed speaks directly to both.
- **Cost:** low to build, **high to wait**. The join is trivial (`scripts/s08`). The binding
  constraint is history: designations start 2026-07-30, outcomes stop 2026-08-07 in the current
  master, so **only 9 game days / 636 rows / 130 DNPs overlap today**, and only 1 game day overlaps
  the higher-provenance PT15M feed. It accrues ~1 game day per day.
- **Closed-surfaces check:** §8 lists the tip-time teammate-volume variant as **"NEVER QUOTE AS A
  RESULT"** because it is computed from a post-game observation. This proposal is the *opposite*
  construction — a witnessed pre-tip designation with `capture_utc` strictly before tip — and it is
  the thing that would let that channel be rebuilt honestly. `p_active` "should not be rebuilt"
  (D090) as an availability model; this does not rebuild it, it supplies an input it never had.
- **Honest limit:** the report covers the **injury** channel of unavailability essentially
  completely and the **coach's-decision** channel not at all (63.8% of observed DNPs, all Coach's
  Decision, carried no designation). Do not sell it as an availability solution.
- **Recommendation:** do not screen it yet. **Freeze the capture, let it accumulate**, and revisit at
  ≥60 game days. Meanwhile use the window that exists only to validate the join and the entity
  resolution.

## Rank 4 — Free throws, using the fouls-drawn channel that is already 100% covered
**Files:** `data/masters/master_player.parquet` — `ftm`, `fta`, `fouls_drawn`, all present.

- **Obtainable:** on disk, all six seasons.
- **Does the record say it matters:** `CLOSED_SURFACES.md` §9.11 — free throws are **17.4% of
  points**, `ftm` correlates **+0.6595** with points (a perfect `ftm` forecast bounds at R² 0.435 of
  points variance), `fouls_drawn` correlates **+0.6749** and is 100% covered. D084's own
  recommendation names the free-throw route as an untested channel. It is queued as Q5 and described
  as "the largest untested points channel in the repository".
- **Cost:** near zero — no new data.
- **Closed-surfaces check:** §5 kills shot-mix → **points** by `CEILING` and the conversion channel
  by `CEILING`. Neither ceiling was computed on the FT channel; D084 explicitly carved it out. §2's
  foul-draw *matchup* is dead as `REDUNDANT` (a repackaged main effect) — this is the **main effect's
  own volume channel**, not a matchup overlay, and a proposer must say so and carry the ceiling
  estimate. §9.11 also warns it is a **hurdle process** (`fta == 0` on 46.4% of played rows), so a
  continuous-rate construction is the wrong shape and would fail for the same reason
  `E0_I0029_freethrow_hurdle` was scoped that way.
- **Caution:** §9.10 records every count target is over-dispersed and zero-inflated, and that a
  Gaussian/OLS treatment has never been justified. The FT channel is the worst offender.

## Rank 5 — Reconcile the null-encoding of `fg_pct` / `fg3_pct` / `ft_pct`
- **Obtainable:** on disk. **Cost:** hours, in `build_masters.py`.
- **Why:** it is the only genuine cross-partition discontinuity found in the master
  (`ft_pct` shifts **+0.805 sd** across the boundary, entirely from a 0/0 encoding change).
  It does not currently reach `features/`, so this is preventive, not corrective.
- **Closed-surfaces check:** not a surface; a data-integrity repair.

## Rank 6 — Lineup / rotation intentions (coach pressers, projected starters)
- **Obtainable:** **NO** — verified. D11's `SOURCE_BINDING.json` records **0 of 8** domains bound and
  the frozen evidence packet returns `UNAVAILABLE` for a pre-game lineup or starter feed, source
  *"no captured pregame feed"*. `data/lineups/*.parquet` are **season-aggregate totals retrieved
  2026-08-06** and using them on an exploration row is a retrospective-baseline violation
  (`CLOSED_SURFACES.md` §9.6) — a trap, not a source.
- **Closed-surfaces check:** §3 kills **starting-five stability and roster churn** as `REAL_NULL`
  (D076). That is a kill of *realised* churn as a between-game state variable. A *pre-announced
  intention* is a different object. But since no feed exists, this cannot be screened, only acquired.
- **Cost:** high — new scraping, entity resolution, and no history. **Recommend: do not start.**

## Rank 7 — Minute restrictions ("on a minutes limit tonight")
- **Obtainable:** **NO.** D11 grepped 284 files for
  `minute[s]?[ _-]?(restriction|cap|limit)` and found 5 lines, **none naming a source** (3 restate
  D11's own criterion, 2 are a 40-minute exposure validation cap).
- **Does the record say it matters:** minutes is the one place the program has real skill
  (D081: minutes skill +3.55%) and D133 records minutes as a **powered null** against further
  pre-game state — a minutes restriction is not pre-game *state*, it is same-day *news*, and is
  therefore outside what D133 tested.
- **Cost:** high — the information lives in beat-reporter text, and `news_capture/news_items.csv`
  carries `players_mentioned_raw` as unresolved free text.
- **Recommend:** park behind Rank 3. If designations prove joinable, the same NLP lane could target
  restrictions.

## Rank 8 — The exchange tape (`data/sxbet_capture/`, ~403 MB)
- **Obtainable:** on disk, live, large (114,912 trades; 57,017 order-book lines).
- **Why it ranks last despite its size:** **its provenance is unverified by this audit.** Sampled
  lines failed JSON parse (truncated at the head of the file), so I could not establish record-level
  timestamp semantics, and I will not assert point-in-time status I did not check. It is also a
  market-microstructure object, not a player-outcome object.
- **Recommend:** a 2-hour provenance probe before anything else. If the timestamps are witnessed, it
  becomes a candidate closing-line source with far better resolution than Rank 1 — but that is a
  market-lane question, not a player-model one.

---

## Explicitly NOT proposed

Rest, travel, back-to-backs, 3-in-4, cumulative schedule state, home/away, pace, transition,
opponent unfamiliarity, height/reach mismatch, assisted share, average shot distance, early-clock
share, roster churn, starting-five stability, `p_active` as an abstention variable, per-player
coefficient fitting, realised-minutes floors, listed position in the cold-start rule, and the
usage × opponent-defence interaction (currently running as `E1_I0023`).

Each is closed by a named mechanism in `CLOSED_SURFACES.md` §§1–7, or is already in flight.

## What I could NOT determine about this ranking

- Whether any item would actually improve a forecast. **Nothing here has been screened.** The ranking
  is by obtainability, record support and cost — not by measured effect.
- Whether the props line's ~34% row coverage biases a model-vs-market comparison toward the players
  a model handles best. It certainly conditions on book-priced players; the comparison must be
  reported on that population and never extrapolated to the full frame.
