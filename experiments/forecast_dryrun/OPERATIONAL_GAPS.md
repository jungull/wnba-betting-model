# OPERATIONAL GAPS — what a real production daily forecast run still needs

*Written 2026-07-30 by the daily-forecast build agent, alongside the v0 dry-run
(`daily_forecast.py` → `experiments/forecast_dryrun/`). This is the honest gap
ledger between "the dry-run worked today" and "a frozen model issues immutable
regime-D predictions every game day unattended." Constitution references:
ROADMAP prediction contract + regime D; HANDOFF §3; the no-imputation rule
(degrade explicitly, never silently).*

---

## 0. The regime-D start ceremony (the one thing this job must NOT do itself)

- The dry-run writes ONLY `experiments/forecast_dryrun/scratch_chain.jsonl` and
  hard-refuses any other path (`_guard_scratch_path`). The official clock
  starts with record 0 of `forecasts/forecast_log.jsonl` — a deliberate act by
  the orchestrator and John, never a side effect of running a script.
- Before that first real record:
  1. **Pin a frozen config file** (see §1) and record its
     `hash_model_config` value in the session log / commit message.
  2. Decide the cutoff policy for day one (which of T-24h/T-8h/T-90m/T-30m
     actually run; v0 produces one cutoff per invocation).
  3. Decide the duplicate/re-freeze policy: a re-log at the same
     (game, cutoff) is only legal under a NEW frozen hash (the logger already
     enforces this).
  4. Anchor discipline: after every logging session, commit the log to git
     and record `n_records` + `tip_sha256` out of band (`verify_chain` report;
     the module docstring's tail-truncation caveat). Decide WHERE out of band
     (JOURNAL.md line, or the commit message itself).
- The scratch chain is disposable evidence of this build. It must never be
  migrated, concatenated, or replayed into the real log.

## 1. Freeze mechanics — v0 reads a live experiment artifact (not acceptable for real runs)

- v0 loads alphas + train-years-only calibrations from
  `experiments/channel_reval/run_summary.json` at runtime. That file is an
  EXPERIMENT OUTPUT: re-running `run_reval.py` would silently change the
  "frozen" model under the same script. Production needs a dedicated
  `forecasts/frozen_config_v<N>.json` (or similar) written once at freeze
  time, blessed by John, and read-only thereafter; the model hash covers it.
  (The v0 hash embeds the calibration VALUES + git HEAD, so any drift does
  change the hash — the gap is procedural, not cryptographic.)
- Code version: v0 reads `.git/HEAD` by file (never a git command). Fine, but
  a dirty working tree is invisible — the freeze ceremony should require a
  clean committed tree so the hash means what it claims.

## 2. Daily stats refresh — the biggest missing piece

The forecast consumes `data/masters/master_team.parquet` +
`master_player.parquet` "through yesterday." Nothing currently *schedules*
that. Today the masters were current through 2026-07-29 because the refresh
was run by hand this session.

- **Mechanics needed, in order, before the first forecast cutoff of the day**
  (a new scheduled task, suggested name `WNBA_DailyStatsRefresh`):
  1. `collect_refresh.py` — pull yesterday's gamelogs (team + player) and the
     per-game V3 misc/advanced boxscores for yesterday's finals
     (stats.wnba.com, V3 endpoints only — V2 per-game is dead).
  2. PBP for yesterday's games (feeds derive_lineups/possessions downstream;
     not needed by the v0 forecast itself).
  3. `build_masters.py` — rebuild/append the masters; its own verification
     gates (identity checks, provenance columns) must pass.
  4. Optionally `daily_certify.py` — the Phase-0 standing certification;
     failures ALERT, never auto-fix.
- **One-stats-crawler rule (HANDOFF §6):** exactly one stats.nba.com/
  stats.wnba.com crawler at a time. The refresh task must be sequenced so it
  never overlaps `collect_misc_backfill.py`, shotchart pulls, or the officials
  crawl (single task with sequential actions, or a lock file all stats
  crawlers respect). Odds / injury / news / official.nba.com captures are
  independent hosts and may run in parallel with it.
- **Timing relative to the existing capture tasks** (all times local machine):
  - `WNBA_OddsCapture` hourly 10:00–23:00; `WNBA_InjuryCapture` hourly
    10:00–23:00; `WNBA_NewsCapture` 08:00/11:45/17:00/21:30 (+W1 extraction);
    `WNBA_RefAssignments` 10:00 + 18:30.
  - Suggested slot: refresh at ~08:30–09:30 local — after any overnight West
    Coast finals are posted, before the 10:00 capture window opens and before
    any T-8h/T-90m/T-30m cutoffs for evening games. A T-24h run for tomorrow's
    games needs yesterday-complete masters only, so it can share the same
    morning slot.
  - The forecast job must run AFTER the refresh completes (task dependency or
    one task with chained actions gated on exit codes — remember the handoff
    burn: never chain commits/steps unconditionally).
- **Failure / staleness behavior (no-imputation rule):**
  - If the refresh fails, the job currently WARNs when the newest master game
    is > 3 days old and stamps every output with the masters' max game date +
    observed_time. Production should adopt a hard rule: **masters older than
    2 calendar days ⇒ NO chain logging** (report-only mode) unless John
    overrides explicitly. Missing-yesterday is a real information loss —
    trends silently one game behind is exactly the "silent degradation" the
    rule forbids... so the run must either say it loudly or not log.
  - Distinguish schedule gaps from data failures: v0 already cross-checks
    per-team last-played vs the league (CHI's 8-day All-Star-style gap today
    was INFO'd, not treated as staleness). A real run should reconcile
    against the schedule (odds events by date) to prove "no games were
    missed" vs "yesterday's games are absent."
  - A partial refresh (gamelog present, misc missing) leaves player-layer DNP
    labels incomplete for the newest game. The dressed-roster estimate then
    quietly loses one game of recency — the job must detect misc-vs-gamelog
    coverage mismatch for the latest date and WARN.

## 3. Cutoff scheduling — contract cutoffs are per-game, tasks are fixed-time

- The contract's T-24h/T-8h/T-90m/T-30m are relative to EACH game's tip.
  Windows scheduled tasks fire at fixed clock times. Options:
  a) a dispatcher run each morning that reads tips from the latest odds
     snapshot and registers one-shot scheduled runs per (game, cutoff); or
  b) an hourly (or finer) runner that computes which (game, cutoff) pairs
     were crossed since its last invocation and logs exactly those.
- v0 labels its single "now" cutoff with the NEAREST contract label and
  records true `hours_to_tip_at_cutoff` in every record, so labels can never
  overstate precision. Keep that honesty rule whatever the scheduler becomes.
- Late games: tips at 22:10 ET mean a T-30m cutoff at ~21:40 ET — inside the
  capture window (captures run to 23:00 local) but any capture failure that
  evening leaves the T-30m run consuming ≥1h-old lines; the job already
  flags snapshots > 75 min old. Weekend/machine-off days (documented pending
  decision): no captures ⇒ no cutoffs are servable that day — that must be an
  explicit "no forecasts today" entry, not a silent absence.
- Multiple same-day cutoffs per game are already safe in the log (key =
  game_id + cutoff + model hash), but the job needs an idempotent "which
  cutoffs already logged" query so a re-fired task does not spam duplicates
  (they'd be refused anyway — refusal is the backstop, not the plan).

## 4. Game identity & schedule truth

- Official stats `game_id`s pre-tip come ONLY from the ref-assignments
  capture today. When refs are not yet posted (v0 test at a 15:05Z cutoff:
  none were), the job degrades to provisional ids
  (`PROV-<date>-<AWAY>@<HOME>`). Provisional ids in the REAL log would
  fracture the (game, cutoff) key across the day — production rule needed:
  **hold chain logging until the official id resolves**, or adopt a
  deterministic pre-game id convention (ET-date + franchise pair) that a
  later reconciliation step maps to stats ids. Decide before regime D.
- Postponements / tip changes: the odds feed relists games (the 51f9e00b
  case in `build_odds_master_extension.py`); tip-time-known-at-capture is
  stored with every snapshot. The daily job should diff commence_time across
  snapshots and (a) re-derive cutoff schedules, (b) annotate any forecast
  whose tip moved after logging (the logged record is immutable; the
  annotation lives outside the chain).
- Non-gamelog games (Commissioner's Cup final): they appear in odds with no
  stats game_id ever. Policy needed: forecast-and-log under a special id, or
  skip explicitly.
- Slate definition is ET-date of commence (WNBA convention). DST transitions
  are handled by zoneinfo; keep it that way (never fixed UTC offsets).

## 5. Market fields — what the log can and cannot carry yet

- The log schema has ONE market_line/price/book triple; v0 logs the
  consensus (median across books) HOME SPREAD at the cutoff, with the sign
  convention documented in the record's market_source, and keeps totals /
  moneyline / per-book range in `forecast_today.csv` + inside the prediction
  object (`market_total_median_at_cutoff`). When W5/betting come online they
  will want best-executable price and book-level lines — either extra log
  fields (schema version bump) or a companion market snapshot file keyed by
  (game, cutoff). Decide before the betting layer, not after.
- Suspended markets (game in odds with no spread outcomes) degrade to null
  market fields with a WARN — already implemented; keep.
- Book staleness INSIDE a snapshot (a book's last_update hours old while
  others are fresh) is not yet filtered; median-of-11 dampens it, but the
  W5-era job should drop books staler than a threshold and record which.
- Odds cadence decision at paid-month end (~Aug 30, John pending): free tier
  = 2-hourly on game days ⇒ the "nearest prior snapshot" for a T-30m cutoff
  could be ~2h old. The staleness WARN threshold must follow the cadence.

## 6. Player layer — from informational to load-bearing

- v0 is INFORMATIONAL by design: dressed recency roster (last 3 team games),
  minutes EWMA α=0.30, Phase-3 rule gate (captured `Out` ⇒ excluded). It does
  not modify the team forecast. Promoting it into the forecast (the V4
  bottom-up thesis: per-player channel rates × Stage-A availability ×
  conditional minutes) is a MODEL CHANGE ⇒ new frozen config + registered
  experiment ⇒ new hash. Never patch it into a running frozen version.
- Known blind spots surfaced by today's real slate, all logged as notes:
  - **Returns are invisible**: Marine Johannes listed `Available` today but
    absent from NYL's last-3 dressed rosters — the recency roster cannot see
    a return until it happens (WARN emitted). Fix path: injury-report
    `Available`/`Probable` listings re-ADD players to the scoring universe
    (spec §5 [FWD] upgrade), with their season EWMA and a return flag.
  - Long-term absentees (Fiebich, Sabally, Westbeld, R. Jackson, Barker
    today) are correctly absent from rosters; their vacated minutes are
    NOT in `vacated_min_ewma` (which counts only currently-rostered Outs).
    Fine for v0; a real vacated-minutes feature needs the full-season view.
  - Name matching is normalized-exact only (accent/punctuation-insensitive),
    with two-way explicit failure notes; no fuzzy matching by policy. A
    persistent alias table (capture-name → master player_id) should
    accumulate as mismatches appear. None appeared today.
  - `Questionable`/`Doubtful` are annotations only. Any probabilistic use is
    Stage-A's job (after ~6 weeks of capture accumulation per the spec).
  - Transaction/waiver capture (cuts, signings) still missing — the recency
    roster carries cut players for up to 3 team games (documented spec
    limitation).
  - Injury log data quirk: 38 rows with null game_date in today's capture
    file; v0 keys on capture_utc + team + player so it is unaffected, but
    the capture script should be hardened.
- Roster-sum sanity: available min-EWMA sums today ranged 170 (CHI, 3 out)
  to 258 (TOR, 14 dressed) vs the 200-minute pool — expected for a roster
  (not a rotation) estimate; do not "fix" by renormalizing (D6 says test it,
  and only in the model phase).

## 7. Not yet wired (by design, v0)

- `w1_extraction` / `core_plus_w1_prediction`: null. W1 extraction runs
  4×/day after news capture but is not consumed here. Regime D's core-vs-
  core+W1 simultaneous logging starts when the W1-informed variant freezes.
- `predicted_close`: null until W5 has a promoted close model.
- `intended_bet_decision`/`paper_stake`: `not_applicable`/0 until system #3
  exists. The enum distinction matters: `no_bet` = the layer ran and chose to
  abstain; v0 must keep `not_applicable`.
- Playoffs: channel trends in the promoted pipeline run through playoff rows
  within a season (masters include them); the calibrations were fit on
  regular-season-dominated train years. First 2026 playoff slate needs an
  explicit decision (forecast with a flag vs hold).
- Ref crews are attached as provenance only (W4 sidecar not promoted).

## 8. Runbook summary of a compliant production day (target state)

1. 08:30 `WNBA_DailyStatsRefresh`: collect yesterday (one stats crawler at a
   time) → rebuild masters → certify. Failure ⇒ alert; forecast runs degrade
   per §2 policy.
2. Morning dispatcher: read tips (latest odds snapshot), emit today's
   (game, cutoff) schedule.
3. Per cutoff: verify captures fresh (odds ≤75 min at hourly cadence,
   injuries ≤2h on game days) → run the frozen forecast → `log_forecast` to
   `forecasts/forecast_log.jsonl` (real, only after the §0 ceremony) →
   `verify_chain` → append anchor (n_records, tip_sha256) out of band.
4. End of day: git commit the log (orchestrator/John — agents never git);
   reconcile provisional anything; record open questions in the journal.
