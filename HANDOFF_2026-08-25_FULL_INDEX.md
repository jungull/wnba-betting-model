# WNBA Prediction Engine — Full Handoff & File Index

**Written 2026-08-25 for a successor with no prior context.** Read §1–§4 before touching
anything. §5 onward is the reference index.

---

## 1. What this project is, and what "done" means

Three systems sharing one data foundation:

1. a **basketball forecasting model** — game and player outcomes from basketball information only;
2. a **market model** — how betting lines behave;
3. a **betting decision system** — the first two, sized under risk control.

**The goal is to beat the betting market on a preregistered, forward-looking sample — or to
prove honestly that we cannot.** Both are acceptable outcomes. A backtest that looks
profitable but was found by searching is *not* an acceptable outcome, and most of this
project's discipline exists to prevent one.

### The honest bottom line as of 2026-08-25

**No profitable strategy has been found.** Eight routes have been measured and closed:

| Route | Result | Where |
|---|---|---|
| Beat the de-vigged consensus of other books | **−7.2%**, CI excludes zero | M32 |
| Model vs market, player props | falsified; residual slope **negative** | M14 |
| Model vs market, team margin vs spread | flat at every threshold, open and close | M44 |
| Middle bets | negative at observed windows | M10 |
| Line shopping | −2.05% (saves money, makes none) | M21 |
| True arbitrage | exists, pays single-digit dollars a season | M09 |
| Stale lines between books | not measurable at our capture speed | M08 |
| News latency (injury → line move) | window real, **direction is a coin flip** | M42 |

**One lead is open but unproven:** large-spread (>8 pt) underdogs against the spread, at the
best available price, returned +7.75% over 384 games (2022–2026). It is **not an edge**. The
result sits 1.61 standard errors from zero, and the *expected best* of the ~15 comparisons run
in M43 is 1.57 SE from pure noise. The only clean number is the out-of-sample replication on
2022–2024 (+4.03%, 201 games, 0.60 SE, ~73% chance positive). See **M43 s06** and **D209**.

**One route has never been tested:** bookmaker promotions/bonuses. It is recorded as the
highest-value opportunity identified, and it is untested only because no real offer has ever
been entered into the system. This requires a human — see §7 USER_REQUIRED.

---

## 2. Machine, paths, and how to run anything

| Thing | Value |
|---|---|
| Working directory | `C:\Users\jgallagher\wnba-betting-model` |
| GitHub | `https://github.com/jungull/wnba-betting-model` |
| Python | `C:\Users\jgallagher\AppData\Local\Programs\Python\Python313\python.exe` |
| OS | Windows 11. PowerShell and Git Bash both available. |
| Admin rights | **Not available.** Scheduled tasks are created with `schtasks /Create /XML`, never `Register-ScheduledTask` (which needs elevation). |

### The two-branch / worktree layout — read this or you will be confused

The repo has **two active branches checked out simultaneously**:

| Branch | Path | Contains |
|---|---|---|
| `data-refresh-2026` | `C:\Users\jgallagher\wnba-betting-model` (main checkout) | **data**, `ops/`, capture scripts, daily jobs |
| `player-model-program` | `...\.claude\worktrees\player-model-program` | **experiments**, orchestration, decision ledger, handoffs |

Both push to the same GitHub remote. Committing to the wrong one is the most common mistake.
A rough rule: *data and things that run on a schedule* → main checkout; *analysis, findings,
and the ledger* → worktree.

**The worktree has a pre-push hook** (`verify_all.py --repository-gate`) that runs a full test
suite. Pushes take **10–20 minutes** and will appear to hang. They are not hanging. Do not
`--no-verify`. Do not launch several pushes at once — concurrent pushes race and one will be
rejected as non-fast-forward.

---

## 3. The evidence system — how this project records what it knows

This is the part that makes the project worth inheriting. Everything is append-only.

| File | What it is |
|---|---|
| `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` | **208 decisions (D001–D209).** Every ruling, its question, its authority, and its limits. The single most valuable file here. |
| `.../GRAPH_EVENTS.jsonl` | 613 events. The append-only event log; **derived** status, not the declared status in `PROGRAM_GRAPH.json`. |
| `.../PROGRAM_GRAPH.json` | 108 nodes. **Its `status` field is stale — do not trust it.** Derive state from `GRAPH_EVENTS.jsonl`. |
| `.../scripts/graphctl.py` | The tool. `graphctl.py status | event | decision | show`. Record decisions with this, not by hand. |
| `experiments/registry.jsonl` | Every registered experiment, result, and erratum. |
| `DEFECTS.md` | Known defects, recorded rather than repaired. |

**To record a decision:**
```bash
python experiments/player_program/orchestration/scripts/graphctl.py decision --decision-id "D210_..." --question "..." --ruling "..." --authority "..." --made-by "coordinator"
```

---

## 4. What runs automatically

**19 Windows scheduled tasks**, all named `WNBA_*`. Inspect with
`Get-ScheduledTask -TaskName "WNBA_*"`.

| Task | Cadence | Does |
|---|---|---|
| `WNBA_OddsCapture` | tiered: 15 min 14:00–19:00Z, 5 min 19:00–03:00Z, **idle 03:00–14:00Z** | game-level odds (h2h/spreads/totals), 11 books |
| `WNBA_PropsCapture_1..4` | a few times daily | player props — **too sparse to time anything, see §8** |
| `WNBA_InjuryLive` | 15 min | official injury report, point-in-time |
| `WNBA_InjuryCapture` | hourly | secondary injury source |
| `WNBA_LineupCapture` | 15 min | RotoWire projected lineups (new 2026-08-24) |
| `WNBA_NewsCapture`, `WNBA_RefAssignments`, `WNBA_SxBetCapture`, `WNBA_MarketLadder` | various | supporting tapes |
| `WNBA_DailyRefresh` | 08:30 ET | **the data chain**: collect → build masters → channel base → certify |
| `WNBA_DailyCycle` | 09:15 ET | health check, gated studies, shadow scoring, writes the daily brief |
| `WNBA_DailyForecast_AM/PM` | 10:20 / 18:45 ET | official forecasts; **PM writes the live regime-D chain** |
| `WNBA_CaptureHealth` | hourly | watchdog |
| `WNBA_OpportunityBoard`, `WNBA_ReplyDeliveryWatchdog` | various | supporting |

### Operational lessons learned the hard way (2026-08-24/25)

- **Tasks must not be battery-gated.** 14 of 19 carried `DisallowStartIfOnBatteries=true` (a
  Windows default) and the entire capture fleet died for 4.5 hours when the laptop unplugged.
  All are now ungated; originals backed up in `logs/task_xml_backup_20260824/`.
- **A task with no `NextRunTime` will never run again and reports as healthy.** The watchdog
  itself died this way (bounded `Duration=PT13H` + `StopAtDurationEnd`). `capture_health.py`
  now flags any task with no next run.
- **Wake timers are disabled on this machine**, so a sleeping laptop still stops everything.
  That is the remaining barrier to true 24/7 and needs a human decision.
- `267011` = "task has not run yet", not a failure.

---

## 5. File index — the main checkout (`data-refresh-2026`)

### Entry documents (read in this order)
| File | What |
|---|---|
| `START_HERE.md` | entry point; points at the constitution and roadmap |
| `ROADMAP.md` | the plan, the four evaluation regimes, promotion gates |
| `DATA_AND_OPERATIONS.md` | data sources and operational layout |
| `MISSION_LEDGER.md` | mission-level history |
| `DEFECTS.md` | known defects |

### Daily jobs (root)
| File | What |
|---|---|
| `daily_refresh.py` | 4-step chain: `collect_refresh` → `build_masters` → `build_channel_base_v2` → `daily_certify`. Aborts loudly; no imputation. |
| `daily_forecast.py` | team + player forecasts. **`--live` writes the OFFICIAL regime-D chain**; without it, a scratch chain. Tees output to `logs/daily_forecast/`. |
| `daily_certify.py` | standing Phase-0 certification |
| `build_masters.py` | rebuilds `data/masters/` (atomic writes via `.tmp` + `os.replace`) |
| `collect_refresh.py` | the **only** stats.nba.com crawler |
| `backfill_market_history.py` | historical odds backfill (D028), 2022-05-21 → 2026-07-30 |

### Operations (`ops/`)
| File | What |
|---|---|
| `ops/capture_health.py` | watchdog: run_hidden.vbs present, task result codes, **no-next-run detection**, odds tape freshness by tier, lineup tape freshness |
| `ops/daily_cycle.py` | writes `reports/DAILY_BRIEF.md` in plain language for a non-technical reader |
| `ops/lineup_capture.py` | RotoWire scraper. Append-only, gzipped raw pages, `--reparse` rebuild, content-hash dedup, self-reporting parse failures |
| `ops/build_stints.py` | **fails on 994/996 games by design** — kept because the failure is worth inheriting (period-boundary subs are not recorded) |

### Model core (root)
`cbs_v5.py … cbs_v7.py`, `cbs_v15.py`, `cbs_player_runner_v13/14/15.py`,
`cbs_player_history_v14.py`, `cbs_player_coldstart_v16.py` — the player model lineage.
`cbs_v7.py` defines the **fallback ladder** (`player_fallback_level`): level 0 normal,
2 short history, 3 no history this season, 4 declared-constant seasons.

`arm_incumbent.py` — **REJECTED at commit ac2e2f0, do not consume its output.** Retained for
audit. The live arm is `experiments/cbs_v15_player_oof_v5/attempt_002`.

`prediction_contract_v2.py` — the cutoff/candidacy machinery (`apply_cutoff_policy`,
`resolve_tip_times`, `load_tip_observations`). v3/v4/v5 live in the worktree.

### Data (`data/`)
| Directory | Contents |
|---|---|
| `masters/` | `master_player.parquet`, `master_team.parquet` — **the outcome truth**, 2021–2026 |
| `odds_capture/` | `capture_log.csv` (242k rows, 760 snapshots, 11 books), `live_*.json` raw, `historical/`, `master_odds_extension.csv` (27.7k rows, 406 games, game_id-linked), **`KNOWN_GAPS.md`** |
| `market_snapshots/historical/` | **`featured_backfill.jsonl`** — 1,415 snapshots, 2022→2026, h2h/spreads/totals. The richest odds asset; 1,245 settled games. |
| `props_capture/` | `master_props.csv` — 36k rows but only **68 snapshots over 25 days** |
| `injury_official_live/` | `injury_snapshots.csv` — 14.8k rows, 2026-08-07→, point-in-time with retrieval timestamps |
| `lineup_capture/` | `lineups.csv`, `capture_log.csv`, `raw/` (gzipped, gitignored), `TEAM_ALIASES.json` |
| `playbyplay/`, `possessions/`, `shotcharts/`, `rapm/`, `officials/` | supporting basketball data |

---

## 6. File index — the worktree (`player-model-program`)

Path: `.claude\worktrees\player-model-program\`

### Handoffs and state
| File | What |
|---|---|
| `HANDOFF_2026-08-25_FULL_INDEX.md` | **this document** |
| `HANDOFF_2026-08-22.md` | previous handoff + appended updates through 08-25 |
| `HANDOFF_PLAYER_MODEL_PROGRAM.md`, `HANDOFF_ADDENDUM_INTEGRITY_WORK.md` | earlier context |
| `experiments/player_program/orchestration/` | the ledgers and graph (see §3) |

### The market program — `experiments/market_program/`

Each `M*` directory holds scripts, `FINDINGS*.json`, and usually `REPORT.md`.

| Node | What it established |
|---|---|
| `M00_MARKET_PROGRAM_CONTRACT` | the rules. **M00-U4: the final-state odds archive is never a feature, never a benchmark.** |
| `M08_STALE_WINDOW` | stale lines not measurable at our speed |
| `M09_TRUE_ARB_SCANNER` | arbitrage exists, pays cents |
| `M10_MIDDLES` | middles negative |
| `M13/M14` | player value translation; **model-vs-market falsified, slope negative** |
| `M21/M22` | execution realism, capacity |
| `M23_SHADOW_TRADING` | logs paper decisions before outcomes; `s02_score.py` settles them |
| `M24_STAKING` | frozen staking policy — stakes **$0.00** by arithmetic |
| `M31/M08` | gated studies that refuse to answer until enough games accrue |
| `M32_DOES_IT_ACTUALLY_WIN` | **the −7.2% that closed the main route** |
| `M33_WHERE_THE_GAP_IS` | the model-market gap is entirely **minutes** |
| `M38_FALLBACK_DEFICIT` | 8.8% of priced rows carry 42% of the deficit |
| `M39_MINUTES_REDISTRIBUTION` | who absorbs an absent player's minutes; **half of Out news breaks inside 90 min of tip** |
| `M40_WHO_GETS_PROMOTED` | promotion prediction ~40% flat; the vendor-feed pricing argument withdrawn (**D201**) |
| `M41_ARM_LEGAL_FALLBACK_REPAIR` | **the best model-side lead.** See below. |
| `M42_NEWS_LATENCY` | latency real, direction a coin flip |
| `M43_SIDE_BIAS` | the underdog candidate, s01–s06 |
| `M44_TEAM_MODEL_VS_SPREAD` | team margin model does not beat the spread |

### The two live threads a successor should care about

**M41 — the minutes repair (ready to implement).**
`s01_arm_legal.py` found that M38's recorded 21.3% gap-closure reads a constant computed on
the **priced population**, which the arm may not see (market data is outside its file
boundary, and the priced population is selected on the very quantity being predicted).
Arm-legal, it is 6.2%. But using **the player's own prior-season minutes** (level 3) and
**own prior-season rate** (level 2) closes **28.3%** — better than the leaky version and
fully legal. `s03_prereg_arm_revision.py` **hash-freezes the implementation criterion**
(sha256 `8b454e7e…`): the revision must land in [−0.26, −0.21] on priced 2026 rows, a smaller
improvement is a *failed reproduction*, and exactly one rule gets built. **This is the
best-specified next build.** Note it still leaves the model losing to the market.

**M43 — the underdog lead (needs forward data).** s01 flat sides → s02 stability/shopping →
s03 totals + concentration → s04 the same test on 1,245 games → s05 totals and moneylines
(both dead) → **s06 the decision analysis**, which is the file to read.

---

## 7. Rules that must not be broken

These are load-bearing. Most were written after something went wrong.

- **Execution mode is SHADOW.** The system places nothing, holds no credentials, contacts no
  venue. `M24` stakes $0.00.
- **S42 is CLOSED** — no fitted scoring model for anything wager-shaped.
- **USER_REQUIRED** (a human must do these, not an agent): purchases and data licences;
  accounts, KYC, deposits, withdrawals; credentials; any non-SHADOW order; staking changes;
  deployment transitions; legal and risk acceptance.
- **Partition rule:** 2025/2026 are the confirmation holdout for E0/E1 exploration.
- **2026 is now SPENT as a holdout** for the M41 line — roughly a dozen confirmations have
  been run against it. Do not select further variants on it (M41 `REPORT.md`).
- **A diagnostic may read the priced frame; an ARM may not.** Any diagnostic finding destined
  to become a model change must be re-derived using only what the arm may read. (**D206**)
- **Never write to a worktree while a gate or test suite is running in it** (D105/D140).
- **Do not run `daily_forecast.py --live` off-cycle to test it.** `nearest_label()` has no
  proximity bound (O12-1, proposal P3, not adopted), so an off-cycle run claims a decision
  label and the obligation guard will refuse the later, correctly-timed serving. Reproduce
  on the scratch chain (omit `--live`).
- **Defects are recorded, not repaired**, unless repairing them is the task.

---

## 8. Known gotchas that will cost you a day each

1. **`PROGRAM_GRAPH.json`'s status field is stale.** Derive from `GRAPH_EVENTS.jsonl`.
2. **The props tape is 3 snapshots/day.** No prop *timing* analysis is possible from history.
   Props are the softest market in basketball, so this is arguably the single biggest
   data-collection gap in the project.
3. **The odds capture is idle 03:00–14:00Z by design.** A quiet tape in that window is not an
   outage.
4. **In-play prices are in the odds tape** (~6% of rows) and move enormously. **Always filter
   `snap < commence_time`.** Failing to do so produced two "significant" results in M42 that
   were pure artifact.
5. **Team names differ between sources.** The injury tape uses full names ("Las Vegas Aces");
   odds use full names; masters use abbreviations; RotoWire uses `POR`/`PHO` where masters use
   `PDX`/`PHX`. See `data/lineup_capture/TEAM_ALIASES.json`. A broken join looks exactly like
   an absent market.
6. **UTC vs ET dates.** An evening ET game carries the *next* UTC date. Joins usually need to
   try both.
7. **Bootstrap by GAME, not by row.** Eleven books quoting one game are one bet; resampling
   rows shrinks intervals by ~√11 and manufactures significance.
8. **Count your comparisons.** The expected best of 15 pure-noise tests is 1.57 SE. Any
   "finding" near that is the search, not a signal.

---

## 9. What I would do next, in order

1. **Implement the M41 arm revision.** It is preregistered, hash-frozen, criterion fixed in
   advance, and it is the best-specified piece of work available. It closes 28.3% of the
   model-market gap. It does **not** produce an edge.
2. **Fix the props capture cadence.** Three snapshots a day makes the softest market in
   basketball untestable. This is a data problem with a known fix and it unlocks a whole
   class of analysis.
3. **Run the M43 underdog lead forward** — ~76 qualifying bets a season, logged before tip at
   the best available price, unbettable after the fact. It is the only thing that converts
   0.60 SE into knowledge. Kill it if the running ROI is below −11.5% after 100 bets.
4. **Let the lineup archive accumulate** and score it with
   `M40/s02_score_vendor_vs_us.py`, which already runs in the daily cycle.
5. **Decide about promotions** — the one route never tested, and the one that needs a human.

---

## 10. One-paragraph summary for whoever reads only this

A well-instrumented WNBA forecasting and market-analysis system with about four years of
data, 19 automated capture jobs, and a 208-entry decision ledger recording every ruling and
retraction. It has **not** found a way to beat the betting market, and it has measured eight
distinct routes closing off. Its real asset is the discipline: preregistration, walk-forward
selection, game-clustered inference, and a written record of every number that failed to
reproduce — including several of its own former headline findings. The best open lead is a
minutes-model repair worth 28.3% of the model-market gap (specified and ready to build, but
still losing to the market), and a large-underdog spread candidate that is suggestive and
statistically unresolved. Trust the ledger over any summary, including this one.
