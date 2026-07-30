# MINUTES MODEL SPEC — Predicting Per-Player Minutes Before Tip

*Drafted 2026-07-30. Design document only — no model has been trained. Every file path, column name, and data quirk below was verified against the repo on 2026-07-30 (inspection scripts run against the actual parquets; reference numbers in §7/§8 were computed then). Complies with the constitution in `project_docs/HANDOFF.md` §3; deviations would need John's sign-off.*

**Why this build first (HANDOFF §4/§6):** the channel model loses to books by ≈0.6 MAE on odds-covered games, and the diagnosed gap is tonight-specific lineup/minutes information. Every player-layer component (per-player channel rates, RAPM aggregation, props pricing) multiplies through expected minutes. Availability × minutes is the sportsbooks' information edge; this model is how we buy it back.

---

## Table of contents

1. Problem definition
2. Data inventory — what actually exists, with quirks
3. Core design decisions (D1–D8)
4. Target variable
5. Prediction universe, DNP labels, and roster churn
6. Feature table (the feature dictionary seed)
7. Baselines to beat
8. Evaluation protocol
9. Phased build plan
10. Missing-data ledger
11. External research synthesis (what drives accuracy elsewhere; what transfers to a 40-minute game)
12. Constitution compliance checklist
13. Open questions for John

---

## 1. Problem definition

For every **target game** and every **rostered player** on both teams, predict **before tip**:

- `p_plays` — probability the player logs any minutes (>0);
- `exp_min_played` — expected minutes **conditional on playing**;
- `exp_min` = `p_plays × exp_min_played` — unconditional expected minutes, the quantity the roster-aggregation layer consumes (HANDOFF §4: each channel decomposes into Σ(player rate × expected minutes)).

Scope for v1: a **point estimate** plus a calibrated play probability. Full minute *distributions* (needed to price props directly) are Phase 4 (§9) — the team-aggregation consumer needs only expectations, and complexity must earn its place (constitution rule 4).

"Before tip" means the feature set may only use information knowable before the target game starts: prior games' box scores (published postgame, including prior games' DNP reasons), schedule/rest/venue (known in advance), and — forward from 2026-07-30 only — captured pregame injury designations. Market odds are never features (rule 7).

---

## 2. Data inventory — what actually exists, with quirks

Everything below was verified by direct inspection on 2026-07-30. This section is normative: features in §6 may only cite these sources.

### 2.1 Player box gamelogs, "old style" (traditional box, per season)

`data/wnba_gamelog_2021.parquet` … `wnba_gamelog_2025.parquet` — 30 cols: `GAME_ID, TEAM_ID, TEAM_ABBREVIATION, TEAM_CITY, PLAYER_ID, PLAYER_NAME, NICKNAME, START_POSITION, COMMENT, MIN, FGM…PTS, PLUS_MINUS, SEASON`.

| Season | Rows | Games | Coverage |
|---|---|---|---|
| 2021 | 3,565 | 192 | full regular season |
| 2022 | 4,096 | 216 | full regular season |
| 2023 | 4,544 | 240 | full regular season |
| 2024 | 4,515 | 240 | full regular season |
| 2025 | 2,072 | 108 | regular season through 2025-07-03 only (refresh covers the rest) |

**Quirks (all verified):**
- **Regular season only.** Every `GAME_ID` in all five files is prefix `102` (regular season) — **no playoff rows** (verified). Playoff player boxes live in §2.2 (2021, 2025) and §2.3 misc files (2023, 2025 today; 2022/2024 arrive with the backfill). v1 trains and scores on regular-season rows; playoff rotations tighten (starters stretch toward 40), so playoff rows, when used, are scored as a separate split, never blended silently.
- **Played-only rows.** `COMMENT` is empty on *every* row in all five files; there are no 0:00 or DNP rows. Median 9 players per team-game (min 7, max 12). Absent/DNP players are simply missing. These files **cannot** define the "did not play" universe.
- **`MIN` is a string in two formats:** 2021–2023 use a corrupted `"35.000000:36"` (= 35:36); 2024 and 2025 use `"33:02"`. Sub-minute stints appear as `"0:33"` / `"0.000000:42"` — those are *played* rows (33s), not DNPs. Regex `^(\d+)(?:\.0+)?:(\d{1,2})$` → `mm + ss/60` parses **100% of non-empty values across all five seasons** (0 failures, verified).
- **`START_POSITION`** is `F/G/C` for exactly 5 players per team-game (verified 2024: min=max=5) and blank for bench. This is the starter flag for 2021–2025(-Jul 3). **No position exists for bench players anywhere in the repo** — position-based features are starter-only or "unknown".
- **No `GAME_DATE`, no `MATCHUP`.** Dates/home-away must be joined via `GAME_ID` from §2.4 bridges.
- `wnba_gamelog_*_with_misc_stats.parquet` are **mislabeled** — column-identical to the base files, zero misc columns (confirmed both by inspection and by the docstring of `collect_misc_backfill.py`). Ignore them.

### 2.2 Fresh player gamelogs (refresh, "LeagueGameLog style")

`data/refresh_2026/gamelog_player_2025_regular_season.parquet` (5,407 rows, 286 games, 2025-05-16 → 2025-09-11), `gamelog_player_2025_playoffs.parquet` (446 rows, 24 games), `gamelog_player_2026_regular_season.parquet` (4,143 rows, 209 games, 2026-05-08 → **2026-07-29**, still being appended), `gamelog_player_2021_playoffs.parquet` (320 rows, 17 games). 33 cols including `GAME_DATE, MATCHUP, WL, FANTASY_PTS`.

**Quirks:** `MIN` is **int64 rounded minutes** (11 rows of `MIN == 0` in 2026 — rounded-down sub-minute stints, not DNPs). **No `START_POSITION`, no `COMMENT`** — starter flags and DNP rows for 2025/2026 come from §2.3. Played-only rows again (median 10 per team-game). Convenient for dates and as a completeness cross-check; **not** the canonical minutes source where §2.3 exists.

### 2.3 V3 per-game misc/advanced boxscores — the DNP goldmine

`data/refresh_2026/misc/misc_<GAME_ID>.parquet` — 796 files: **2023 full** (240 reg + 20 PO), **2025 full** (286 reg + 24 PO), **2026 all games to date** (209), **2021 playoffs** (17). ~27 cols: `gameId, teamId, teamTricode, personId, firstName, familyName, position, comment, jerseyNum, minutes, pointsPaint, pointsFastBreak, …, foulsPersonal, foulsDrawn`.

- **Full dressed roster per game** — 8–15 rows per team (median 12), i.e. *includes players who did not play*.
- **`comment` carries the DNP reason** on exactly the no-minutes rows: observed taxonomy `DNP - Coach's Decision` (healthy scratch), `DND - Injury/Illness` (did not dress), `NWT - Injury/Illness` (not with team), `DND-Return to Competition Reconditioning`. In a 28-game sample: 18.2% of dressed-roster rows are DNPs; reason prefix counts DNP 163 / DND 163 / NWT 28.
- **`minutes` is a `"MM:SS"` string; empty string `""` for DNP rows** (never "0:00"). Same parser as §2.1 works.
- **`position` is populated for starters only** (F/G/C, exactly 5 set per team; blank for bench) → starter flag for 2023/2025/2026.
- `data/refresh_2026/advanced/advanced_<GAME_ID>.parquet` — 356 files at inspection (collector appending), same layout plus `usagePercentage, pace, possessions, offensiveRating…`. Coverage: 2025 reg **from game 109 only** (178), 2025 PO 24, 2021 PO 17, **2026: 137 of 209 (collection in flight)**. Use for per-minute context features later; not required for v1.
- **Coverage hole:** no misc for 2021 regular, 2022, 2024 — **`collect_misc_backfill.py` (repo root, already written, ~75–90 min resumable run) fills exactly this** and closes advanced too. Until it runs, DNP labels exist only for 2023 / 2025 / 2026 / 2021-PO.

### 2.4 GAME_ID → date/venue bridges (player files have no dates)

- `data/drive_masters/master_team_cleaned.csv` — 2,132 team-rows, **all 1,066 games 2021-05-14 → 2025-07-03** with `GAME_DATE, MATCHUP, WL`. The date bridge for 2021–2024 and early 2025.
- `data/refresh_2026/gamelog_team_2025_regular_season.parquet`, `..._2025_playoffs.parquet`, `..._2026_regular_season.parquet` (+ `wnba_team_gamelog_2024.parquet`, `gamelog_team_2021_playoffs.parquet`) — dates/matchups for everything after. 2026 file: 209 games, 15 teams, `GSV/TOR/PDX` present (expansion: Golden State 2025; Toronto, Portland 2026).
- `data/drive_masters/master_player.csv` — **do not use as a source.** Verified: played-only (median 9/team-game), 2023 regular season entirely absent, `MIN` null on 15,744 of 20,288 rows, mixed dtypes. The per-game parquets in §2.1–2.3 supersede it.

### 2.5 Play-by-play (upstream input to a parallel task)

- `data/playbyplay/pbp_<GAME_ID>.parquet` — 996 games, 2021 → 2025-07-03, **V2 schema**: substitutions are `EVENTMSGTYPE == 8`, `PLAYER1` = out, `PLAYER2` = in (~43 sub events/game).
- `data/refresh_2026/pbp/pbp_<GAME_ID>.parquet` — 428 files (2025 reg from game 109: 178; 2025 PO: 24; 2026: all 209 to date; 2021 PO: 17), **V3 schema**: `actionType == "Substitution"`, `playerName` = out, incoming player parsed from `description` (`"SUB: X FOR Y"`).
- A **parallel task** is deriving stints/rotations/starter-verification from these. This spec treats its outputs (§6 group F) as a Phase-2 upstream, not something this build re-implements. The two schemas + the 2025 game-109 seam are that task's problem; noted here so nobody double-builds.

### 2.6 Injury capture (forward-only, starts today)

`data/injury_capture/` — **does not exist yet** (verified); the live capture of official WNBA injury/availability reports starts 2026-07-30, alongside the odds capture (`data/odds_capture/` began 2026-07-30T15:01Z). **No historical pregame designations exist anywhere** — league injury reports are ephemeral; what was "Questionable at 4pm" before a 2024 game is unrecoverable. Everything derived from this source is marked **[FWD]** in §6 and gated to Phase 3.

---

## 3. Core design decisions

**D1 — Two-stage: `P(plays) × E[minutes | played]`, not single-stage.**
18.2% of dressed-roster player-games are exact zeros (§2.3) — a point mass, not a tail. A single regression over the mixture drags played-minute estimates toward zero and can't express "healthy scratch vs 24-minute role" as two different questions with two different feature sets. The two stages also have **different label coverage** (zeros only exist where misc files exist), and the split quarantines that problem cleanly: Stage B (minutes|played) trains on *all* seasons from played-only files; Stage A (P(plays)) trains only on misc-covered seasons — no imputation, no pretending. Finally, the aggregation and props layers need the components separately (availability scenarios: "if X is out, re-run with p=0").

**D2 — Point estimate + calibrated probability in v1; distributions deferred.**
The consumer this week is Σ(rate × exp_min). Distributions (props pricing, foul-out/blowout tails) are Phase 4, built as quantile regression or residual simulation *on top of* the v1 mean model. Rule 4: complexity earns its place on the leaderboard first.

**D3 — DNP/roster churn handled by explicit universes, never imputation.**
Three nested player sets per team-game (§5): **dressed roster** (misc rows; label universe for Stage A), **recency roster** (pregame-buildable scoring universe), **cold-start residue** (new signings/rookie debuts with <3 prior appearances — no model forecast in v1; flagged `cold_start`, given a clearly-labeled fallback tier, excluded from headline metrics and reported separately). Missing DNP labels for 2021-reg/2022/2024 are treated as *missing data to go collect* (`collect_misc_backfill.py`), per rule 8 — not reconstructed, not imputed.

**D4 — Canonical minutes source order: misc V3 → old gamelog → refresh gamelog.**
Misc `minutes` ("MM:SS", exact, includes zeros-as-blank) where it exists (2023/2025/2026, all seasons post-backfill); old-file `MIN` (exact, played-only) for 2021/2022/2024; refresh int-`MIN` (rounded) only as a gap-day stopgap and cross-check. One parser (§2.1 regex), 0 verified failures. Where sources overlap (2025 games 1–108) assert agreement to ±0.5 min in the build script.

**D5 — Walk-forward and shift discipline exactly per constitution.**
Train 2021–2023, test 2024+ (2026 as second test season). Every rolling/trend feature is computed within player-season (or team-season) and **`.shift(1)` before any window/EWM** — the §6 table states the rule per feature. EWMA alphas tuned on train years only. Team eligibility: ≥5 prior same-season team games (rule 2); player analog: ≥3 prior same-season appearances for a scored Stage-B row (below that → `cold_start` tier). Features reset per season.

**D6 — The 200-minute pool is a structural constraint, tested like a composite.**
Verified: player minutes sum to 199–201 in 95.5% of team-games (the rest are OTs, +25/OT max observed 250). After per-player predictions, optionally rescale each team's predicted vector to sum to 200 × P(regulation) — the WNBA analog of DFS's sum-to-240 discipline and of HANDOFF's box-identity thinking. It ships only if it beats the unscaled version on the leaderboard (rule 4), and it replaces nothing (rule 6 doesn't apply — it's a post-transform, not a stacked feature).

**D7 — Odds are never features (rule 7), so blowout risk uses an internal proxy.**
The DFS literature's blowout adjustment keys off the market spread. Here, expected-competitiveness = |own team net-rating EWMA − opponent net-rating EWMA| (both shifted, train-tuned) — our own information, no market circularity. When the channel model matures, its own predicted margin can replace the proxy (still model-internal).

**D8 — Charter-flight regime break is acknowledged in schedule features.**
WNBA flew commercial through 2023 and full charter from 2024. Back-to-back/travel coefficients learned on 2021–2023 may not transfer to the test years — exactly the years we test on. Mitigation: keep schedule features few and simple (rest days, B2B flag, 3-in-4), and check their marginal contribution separately per era in the feature-importance CSV before trusting them.

---

## 4. Target variable

- **Stage B target:** `minutes_played` (float) = parsed MM:SS from the canonical source (D4), for rows with minutes > 0. Includes OT minutes as played (raw truth; props settle on raw). Sub-minute stints (e.g. 0:33 → 0.55) are legitimate small targets, not noise to drop.
- **Stage A target:** `played` ∈ {0,1} over the **dressed roster** universe (misc-covered games only). `DNP/DND/NWT` rows are 0 with a `reason` category retained for analysis (not as a same-game feature — that's the label side).
- Diagnostic alternate target (not v1): `min_share` = minutes / team total (handles OT smoothly); revisit in Phase 4 if OT noise shows up in residuals.

---

## 5. Prediction universe, DNP labels, and roster churn

**Label universes (backtest):**
- Stage A rows: every player on the misc dressed roster for that game (2023, 2025, 2026, 2021-PO today; + 2021-reg/2022/2024 after `collect_misc_backfill.py`).
- Stage B rows: every played row (all seasons, §2.1 + §2.3).

**Scoring universe (pregame, live or backtest):** the **recency roster** = players who appeared on the team's dressed roster (misc era) or box (pre-misc era) within the team's **last 3 games**, plus [FWD] anyone named on the captured injury report. This is buildable strictly from prior-game information. Known limitations, accepted rather than papered over:
- A player cut/traded yesterday still appears until 3 team-games pass → Stage A learns to zero them out via `days_since_last_appearance`; transaction-log capture is a ledger item (§10).
- A debutant (rookie's first game, new hardship signing) is invisible → `cold_start` tier: no model forecast; fallback = team's shifted bench-median minutes, **labeled as fallback, reported separately, never mixed into headline MAE**. This is a documented prior for a genuinely new entity, not imputation of missing raw data.
- 2026 expansion teams (TOR, PDX; GSV in 2025) hit the ≥5-team-games rule early each season — same treatment HANDOFF §6 prescribes for the channel model (rows before eligibility aren't scored).

**Roster churn safety rule:** every feature in §6 is a function of (player, team, date) history *up to and excluding* the target game. Trades mid-season: player-level trends follow the player across teams **within season** (minutes history is a property of the player-coach pairing, so team-change resets are tested as a variant: `same_team_flag` interaction rather than a hard reset — bake-off decides on train years).

---

## 6. Feature table

Feature dictionary seed per constitution rule 10 (source + derivation per feature; exported as `feature_dictionary_minutes.csv` when built). **Shift rule notation:** "S1-EWM" = `groupby(player, season).shift(1)` then `.ewm(alpha).mean()`; "S1-roll-k" = shift(1) then rolling window k; "S1-exp" = shift(1) then expanding. All EWMA alphas tuned on 2021–2023 only, grid {0.05…0.50} (constitution favors 0.05–0.15 for team stats; minutes are role-driven and may want faster alphas — the grid, not habit, decides; tuned per stat).

**[FWD]** = forward-only (injury capture, exists from 2026-07-30). **[P2]** = gated on the parallel PBP-stint task. Unmarked = buildable today from files in this repo.

### A. Player minutes trend (Stage B core)

| Feature | Source file(s) | Derivation | Shift/leakage rule |
|---|---|---|---|
| `min_ewma` | §2.1 gamelogs + §2.3 misc `minutes` (D4 order) | parsed minutes, played rows, within player-season EWM | S1-EWM, alpha train-tuned |
| `min_last1` | same | previous game's minutes | shift(1) |
| `min_mean_l5` | same | mean of last 5 played games | S1-roll-5 |
| `min_expmean` | same | season-to-date mean | S1-exp |
| `min_std_l10` | same | volatility of role | S1-roll-10 std |
| `min_share_ewma` | same + team sum | minutes ÷ team total that game, then EWM | S1-EWM |
| `player_gp_season` | same | # prior appearances this season | count of rows strictly before target |
| `min_trend_delta` | derived | `min_mean_l5 − min_expmean` (role rising/falling) | both inputs already shifted |

### B. Starter/role status

| Feature | Source | Derivation | Shift rule |
|---|---|---|---|
| `started_last` | §2.1 `START_POSITION` (2021–2025/07); §2.3 misc `position` (2023/25/26) | non-blank = started, previous game | shift(1) |
| `start_share_l5` | same | share of last 5 appearances started | S1-roll-5 |
| `listed_pos_hist` | same | mode of historical non-blank start positions; `"UNK"` if never started (bench position is structurally unknowable, §2.1) | uses prior games only |
| `starts_streak` | same | consecutive games started entering target | shift(1) cumulative |

### C. Availability / return-from-absence (Stage A core; also Stage B inputs)

| Feature | Source | Derivation | Shift rule |
|---|---|---|---|
| `played_last_team_game` | played rows vs team schedule (§2.4 bridges) | did player appear in team's most recent game | prior games only |
| `played_share_l10_team_games` | same | appearances ÷ team's last 10 games | S1 over team-game index |
| `days_since_last_appearance` | same + `GAME_DATE` | calendar days since player's last played game | prior games only |
| `games_missed_streak` | same | consecutive team games missed entering target | prior games only |
| `prev_dnp_reason` | §2.3 misc `comment` (misc-covered seasons) | category of player's most recent DNP reason (CD / injury-DND / NWT / recondition), from *prior* games' postgame boxes — knowable pregame | strictly prior games; **target-game `comment` is label, never feature** |
| `returning_flag` | derived | played_last==0 and prior reason = injury class (restriction/ramp proxy: external evidence shows 25–28-min caps for 5–10 games on return, §11) | prior games only |
| `inj_designation` **[FWD]** | `data/injury_capture/` | latest pregame designation (Out/Doubtful/Questionable/Probable/Available) + listed reason; `Out` ⇒ hard `p_plays=0` gate (rule-based, usable in production immediately — no training history needed) | capture timestamp must precede tip; stored raw with timestamps |
| `days_on_report` **[FWD]** | same | consecutive days player has appeared on captured reports | capture history only |

### D. Team context / schedule

| Feature | Source | Derivation | Shift rule |
|---|---|---|---|
| `days_rest_team` | §2.4 team files `GAME_DATE` | days since team's previous game | schedule known pregame |
| `b2b_flag`, `three_in_four` | same | schedule density (see D8 charter caveat) | schedule known pregame |
| `home_flag` | §2.4 `MATCHUP` (`@` = away) | venue | known pregame |
| `team_gp_season` | same | team games played (rotation stabilization clock; gate ≥5) | prior games only |
| `blowout_proxy` | §2.4 team `PLUS_MINUS` | \|own net EWMA − opp net EWMA\| (D7: **not** the market spread) | S1-EWM per team-season, both sides |
| `team_bench_share_ewma` | §2.1/2.3 player minutes | share of team minutes to non-starters, EWM (coach rotation-tightness trait) | S1-EWM team-season |
| `team_n_rotation_ewma` | same | # players ≥10 min per game, EWM | S1-EWM team-season |

### E. Teammate interaction (minutes redistribute — the #1 driver in DFS practice, §11)

| Feature | Source | Derivation | Shift rule |
|---|---|---|---|
| `vacated_min` | player trend table + recency roster | Σ `min_ewma` of teammates who missed the team's last game and have not since reappeared (pregame-knowable absence proxy; [FWD] upgrade: teammates currently listed Out) | built from prior-game rosters only |
| `vacated_min_samepos` | same + `listed_pos_hist` | the subset of `vacated_min` from same historical position (UNK excluded, D3) | same |
| `returned_teammate_min` | same | Σ `min_ewma` of teammates who *returned* in the last game after ≥2 missed (role squeeze on fill-ins) | prior games only |
| `pf_per_min_ewma` | §2.1 `PF` / minutes; §2.3 `foulsPersonal` | foul-trouble propensity (6 fouls in 40 min — WNBA foul-out risk per minute exceeds NBA's 6-in-48) | S1-EWM |

### F. PBP-derived (Phase 2 — consumed from the parallel stint task, not rebuilt here) [P2]

| Feature | Upstream | Note |
|---|---|---|
| `closing_lineup_share` | stints from `data/playbyplay/` (V2, `EVENTMSGTYPE==8`) + `data/refresh_2026/pbp/` (V3, `actionType=="Substitution"`) | share of last-5-minute close-game stints player was on floor; shift(1) at consumption |
| `garbage_min_share_ewma` | same + `SCOREMARGIN` | share of player's recent minutes in ≥15-pt margin situations — cleans the trend inputs (a bench player's 12 garbage minutes ≠ 12 rotation minutes) | S1-EWM |
| `stint_len_mean`, `stints_per_game` | same | coach usage pattern per player | S1-EWM |
| `true_starters_check` | same | QA cross-check of §B starter flags | n/a (audit) |

---

## 7. Baselines to beat (simplest first)

All evaluated on played rows, walk-forward test 2024+, per §8. Reference numbers below were **measured on 2024** (played rows with ≥1 prior appearance, n=4,344) during spec prep — zero-parameter baselines only, no tuning:

| # | Baseline | Definition | Measured reference (2024) |
|---|---|---|---|
| B1 | Last-game carry-forward | `min_last1` | **MAE 5.42** (starters 5.33 / bench 5.52) |
| B2 | Shifted season-to-date mean | `min_expmean` | **MAE 5.12** (starters 4.93 / bench 5.35) |
| B3 | Shifted EWMA | `min_ewma`, alpha tuned on 2021–2023 only | to be measured; expected ≈4.6–5.0 (HANDOFF rule 3: EWMA wins bake-offs) |
| B4 | **EWMA × active-flag** | B3 × (played in team's last game) — the project's stated starting point (HANDOFF §6.2a) | to be measured on expected-minutes metric (§8 M3) |
| B5 (optional) | DFS folk blend | 0.75 × season mean + 0.25 × last-5 mean (industry heuristic, §11) | sanity anchor only |

Context for targets: minutes std on played rows is 10.9, so B2 already explains a lot; the NBA DFS practitioner target is MAE < 3 **with same-day lineup news** (§11) — not comparable to a news-blind backtest, but it bounds what Phase 3 (injury capture) should chase. A public NBA LightGBM (UBC-MDS) reports R² 0.65 vs 0.55 for a 5-game-average baseline — beating trend baselines by a real margin is achievable, not guaranteed.

Model v1 to challenge the baselines: **ridge on §6 groups A–E** (small, shifted, hand-inspectable), with a GBM challenger only if ridge beats B3/B4 first (rule 4: complexity queue). Leaderboard file: `project_docs/MINUTES_LEADERBOARD.md`, baselines and DFS-anchor rows included (rule 10).

---

## 8. Evaluation protocol

**Splits (constitution rule 2):** train 2021–2023, test 2024 + 2025 + 2026-to-date, walk-forward (features computed only from history at prediction time; no refit inside test unless the refit itself is walk-forward and pre-declared). Features reset per season. Scored rows require team ≥5 prior same-season games and player ≥3 prior same-season appearances (D5); coverage (% of player-games scored) is reported alongside every metric so the gates can't hide.

**Metrics:**
- **M1 — Minutes MAE on players who played** (primary, comparable to B1–B3). Reported overall and **split by prior-game starter vs bench** (`started_last`, not target-game starter status — conditioning on the target game's lineup would leak).
- **M2 — Brier score and log-loss for `p_plays`** over the dressed-roster universe (misc-covered test games: 2025/2026 now; 2024 joins after backfill). Plus a decile calibration table — the aggregation layer consumes probabilities, so calibration matters as much as rank.
- **M3 — Expected-minutes MAE** = MAE of `p_plays × exp_min_played` against actual minutes (zeros included) over the dressed roster. This is the number the roster-aggregation layer actually feels, and the metric on which B4 (EWMA × active-flag) is the incumbent.
- **M4 — Team-sum diagnostic:** distribution of Σ predicted minutes per team-game vs 200 (and vs 200+25×OT). Systematic bias here means miscalibrated availability, even if M1 looks fine.

**Audit battery before believing any result (rule 1; every prior sub-9.5 team MAE was leakage):**
1. Shift audit — recompute any feature with all rows ≥ target date deleted; values must be identical.
2. Target-permutation probe — shuffle targets within season; a "good" model must collapse to ~baseline.
3. Same-game canary — correlate each feature against *teammate* target-game outcomes; anything suspiciously informative gets traced.
4. `prev_dnp_reason` timestamp check — reason must come from a game strictly before the target game (the target game's own `comment` is the label's sibling, never a feature).
5. Reuse/adapt `verify_walk_forward.py` / `verify_target_leakage.py` patterns from the Drive mirror (HANDOFF rule 1).

**Reporting conventions (rule 10):** single leaderboard MD ranked by M1 with B1–B5 rows pinned; `feature_importance_minutes_<model>.csv` per model; `feature_dictionary_minutes.csv` kept current; outputs as CSVs John can open.

---

## 9. Phased build plan

**Phase 0 — Minutes master table (this week, all inputs exist).**
One script → `data/minutes_master.csv` (+ parquet twin): one row per player-game with parsed minutes (D4 source order + the two-format parser), `GAME_DATE`/`MATCHUP` joined via §2.4 bridges, starter flag (§6B sources), dressed-roster/DNP rows with reasons for misc-covered games, dedupe rule for the 2025 overlap (games 1–108 appear in both §2.1 and §2.3 — assert minute agreement ±0.5, prefer misc). QA gates: team sums ≈200/OT (§P check), 5 starters per team-game, 0 parse failures, row counts vs §2 tables.

**Phase 1 — Baselines + v1 two-stage (this week).**
B1–B4 on the leaderboard; Stage B ridge on groups A/B/C/D/E (existing-data features only); Stage A logistic on misc-covered seasons (train on 2023 only until backfill lands — thin but honest; 2021-PO too small to matter). Ship `exp_min = p × m` per D1; run the audit battery; publish leaderboard + feature importance + dictionary.

**Phase 1.5 — DNP label backfill (queued; ~75–90 min of collection).**
Run `collect_misc_backfill.py` (2021-reg/2022/2024 misc + advanced). Stage A retrains on 2021–2023, tests on 2024+ — the full constitutional split becomes available for availability modeling. No spec change, just more label rows (rule 9: more rows always helped).

**Phase 2 — Rotation-structure features (gated on the parallel PBP stint task).**
Consume §6F (closing-lineup share, garbage-time-cleaned trends, stint patterns). Each addition must beat the Phase-1 leaderboard entry to stay (rule 4). Also use stint-derived starters as a QA cross-check on §6B.

**Phase 3 — Injury capture goes live in the loop (gated on accumulation).**
Immediately (no training needed): captured `Out` designations gate `p_plays = 0` and drop players from the scoring universe in daily production runs; captured rosters refresh the recency roster. After ~6+ weeks of capture: designation categories become Stage-A features **for live prediction only** — they can never enter the 2021–2025 backtest (no historical reports exist; §10). Evaluation of capture-era features = forward-only paper-trail on 2026 games, reported separately from the historical leaderboard.

**Phase 4 — Distributions and structure (gated on Phase 1–2 results and props needs).**
Quantile regression or residual simulation for props pricing; 200-minute-pool renormalization test (D6); foul-out/blowout conditional tails; min_share target variant; coach-change and restriction-ramp modeling if residuals demand it.

---

## 10. Missing-data ledger

Honest accounting per rule 8 — three columns: can't ever know, accumulating from today, being derived elsewhere.

| Item | Status | Plan |
|---|---|---|
| **Pregame injury designations, 2021–2025** (Questionable/Out lists as they stood before tip) | **Unknowable historically** — league reports are ephemeral, never archived in usable pregame form | Accept: backtests are news-blind (that's the honest baseline for measuring what news is worth); capture forward |
| **Pregame injury designations, 2026-07-30 →** | Accumulates in `data/injury_capture/` starting today | Phase 3: production gates immediately, features after ~6 weeks; store raw snapshots with capture timestamps so "as-of" reconstruction is provable |
| **Announced starting lineups pregame** | Not captured historically; actual starters known only postgame | §6B uses prior-game starter flags (knowable); consider adding lineup announcements to the capture later |
| **DNP labels 2021-reg / 2022 / 2024** | Missing today; misc V3 endpoint has them | `collect_misc_backfill.py` is written and queued (Phase 1.5) — collect, don't reconstruct |
| **Transaction/waiver timestamps** (cuts, signings, trades) | Not in repo | Proxy: `days_since_last_appearance` + recency-roster decay; candidate future capture (public transaction log) — ledger'd, not blocking |
| **Bench player positions** | Structurally absent in every box source (starter-only `position`/`START_POSITION`) | `listed_pos_hist` with honest `UNK`; no position imputation (D3) |
| **Stints / true starters / garbage-time flags** | Being derived by the **parallel PBP task** from §2.5 (996 V2 games + 428 V3 files, two schemas, seam at 2025 game 109) | Consume in Phase 2; don't double-build |
| **Advanced V3 2026** | In flight: 137/209 games at inspection | Not needed for v1; collector still running |
| **Refresh gamelog `MIN` precision** | int-rounded by the endpoint | Never canonical where misc exists (D4) |
| **2026 daily refresh lag** | `gamelog_player_2026_*` / misc current through 2026-07-29 at inspection | Daily production run pulls latest before predicting |
| **Odds snapshots** | `data/odds_capture/` live since 2026-07-30T15:01Z | Benchmarks/CLV only — never features (rule 7) |

---

## 11. External research synthesis

What the best public practitioners say drives minutes-projection accuracy, and what transfers from a 48-minute NBA game to a 40-minute WNBA game. (DFS shops treat minutes as the single most important projection input; their methods are editorial + heuristic, so the transferable content is *which factors matter and roughly how much*, not fitted coefficients.)

**Consensus drivers, ranked roughly as the industry ranks them:**
1. **Availability news and redistribution** — "the #1 factor." When a 30-minute player sits, the direct backup gains ~+12–15 and adjacent rotation players +2–5 (LandYourBets). Encoded here as §6C/E (`vacated_min`, returns), upgraded by capture in Phase 3. Sources: [LandYourBets guide](https://landyourbets.com/how-to-make-nba-minutes-projections), [RotoWire projected minutes](https://www.rotowire.com/basketball/article/nba-projected-minutes-explained-fantasy-basketball-97473).
2. **Recent role vs season role** — baseline blends of season mean and last-5/last-10 (0.75/0.25 in the folk formula) ≈ our B5; a tuned EWMA is the same idea done properly (B3). Sources: RotoGrinders lessons ([Projecting Minutes](https://rotogrinders.com/lessons/projecting-minutes-1149307), [Most Critical Opportunity Stat](https://rotogrinders.com/lessons/projected-minutes-the-most-critical-opportunity-stat-in-nba-dfs-3147006)).
3. **The fixed minute pool** — 240 NBA / **200 WNBA**; redistribution is zero-sum, so team-level renormalization is principled (D6, M4).
4. **Rotation-change taxonomy** — injuries/rest, role changes, matchups, blowouts (RotoGrinders). Blowout adjustments scale with expected margin (−2…−5 for starters at double-digit spreads); we proxy internally (D7).
5. **Coach rotation archetypes** — tight 7–8-player benches vs 10–11 deep; captured as team-level EWMA traits (§6D) rather than coach fixed effects (coach IDs aren't in the repo; team-season traits are the buildable version).
6. **Returns from injury / minute restrictions** — documented ramp caps ~25–28 min for 5–10 games in the NBA ([Grokipedia: minutes restriction](https://grokipedia.com/page/Minutes_restriction), [FantasyLabs monitoring minutes](https://www.fantasylabs.com/articles/nba-dfs-monitoring-the-minutes-volume-1/)); historically we only see the *footprint* (absence then reduced minutes — `returning_flag`); capture makes it explicit going forward.
7. **Schedule** — B2Bs cut veteran minutes; WNBA-specific caveat: charter flights since 2024 (D8), and the 2026 44-game calendar is denser than the 40-game 2024 one — schedule features stay in, but era-checked.
8. **Quantitative anchors** — public NBA LightGBM: R² 0.65 / MSE 38.2 vs 5-game-avg baseline R² 0.55 / MSE 50.2 ([UBC-MDS NBA-Minutes-Predictor](https://github.com/UBC-MDS/NBA-Minutes-Predictor)); practitioner target MAE <3 *with news* (LandYourBets); an academic position-specific NN claims ~1.4–1.6 avg error ([BCP FHSS paper](https://bcpublication.org/index.php/FHSS/article/view/6718)) — treat that last one with heavy skepticism (venue quality, likely favorable filtering).

**WNBA vs NBA transfer honesty:**
- **Tighter and more stable.** 8–9 player rotations (median 9–10 playing per team-game in our data), 11–12 player rosters, stars at 35+/40 — WNBA DFS practitioners explicitly call minutes *more* projectable than NBA ([DFSBuild WNBA guide](https://dfsbuild.com/dfs-guide/wnba-dfs-guide/)). Our measured starter share: median starter plays 29.6/40 = 74% of the game.
- **Less load management** — short season, small rosters, no NBA-style rest culture; DNP-CD is concentrated in end-of-bench players (18.2% of dressed rosters DNP at all).
- **Foul-out risk is higher per minute** (6 PF in 40 vs 48) — `pf_per_min_ewma` earns its slot more than in NBA models.
- **Garbage time is shorter in absolute minutes** (40-min game) but the WNBA's 2025–26 blowout rate isn't lower; the blowout proxy stays, expectations modest (team-level venue/complexity lessons in HANDOFF rule 4 warn against overweighting situational adjustments).
- **Roster churn is *worse* than NBA** — hardship contracts and mid-season cuts are routine under the tight salary cap; that's why §5 spends so much design on the recency roster and cold-start tier.

---

## 12. Constitution compliance checklist

| Rule (HANDOFF §3) | Where honored |
|---|---|
| 1. Leakage kills; audit before believing | §8 audit battery; shift notation on every §6 row; `prev_dnp_reason` timestamp rule |
| 2. Walk-forward; 2021–23/2024+; ≥5 prior games; per-season reset | §8 splits; D5; expansion-team handling §5 |
| 3. Shifted EWMA, alpha tuned on train | B3/B4; §6 group A; alpha grid stated |
| 4. Complexity must earn its place | D2 (no distributions in v1), D6 (renorm must win), §7 ridge-before-GBM, Phase gates |
| 5. Granular beats aggregate | per-player two-stage rather than team minutes top-down; misc per-game files as source |
| 6. Composites replace ingredients | `min_trend_delta` replaces neither input by default — bake-off decides; renorm is a post-transform not a stacked feature |
| 7. Odds never features | D7 blowout proxy; odds_capture ledger'd as benchmark-only |
| 8. No imputation — go get the real data | D3; Phase 1.5 backfill instead of roster reconstruction; §10 ledger |
| 9. More rows help | Phase 1.5 motivation; dressed-roster labels ×6 seasons post-backfill |
| 10. Leaderboards, feature dictionaries, CSVs | §7 leaderboard, §8 reporting conventions, §6 as dictionary seed |

---

## 13. Open questions for John

1. **Backfill green light:** OK to run `collect_misc_backfill.py` now (~75–90 min, resumable, stats.wnba.com)? It converts Stage A from a one-season (2023) trainee into the full constitutional split, and it's the cheapest row-multiplier available.
2. **Injury capture contents:** confirm what the capture stores (designation, reason, report timestamp, roster/lineup announcements?) so §6C [FWD] rows match reality; request raw-snapshot retention with timestamps for provable as-of reconstruction.
3. **Blowout proxy vs market spread:** rule 7 is applied strictly here (no spread as feature). If John ever wants a "books-informed" variant for production only, that's a deliberate constitutional amendment, not a default.
4. **Cold-start fallback level:** team shifted bench-median is proposed; alternative is no number at all (aggregation layer handles the hole). John's no-imputation instinct may prefer the latter — decide before Phase 1 ships.
5. **`min_share` vs raw minutes** as the Phase-4 target for props (OT treatment) — flag now, decide later.
