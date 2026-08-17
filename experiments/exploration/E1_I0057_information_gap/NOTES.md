# NOTES — E1_I0057_information_gap

Audit commissioned by the owner, decision D137, 2026-08-17. Evidence level **E0/E1**.
**This is an audit, not a screen.** No effect is measured and none is claimed. Any predictive
number appearing anywhere in this directory is illustrative and is labelled as such at the point
of use.

Deliverables: `FINDINGS.json`, `CAPTURED_BUT_UNUSED.csv`, `DECISION_TIMELINE.md`,
`REGIME_BOUNDARY.md`, `RANKED_GAPS.md`. Reproduction scripts in `scripts/`.

---

## 0. The finding in one paragraph

The program's **production** forecaster reads three same-day information sources every day —
official injury designations, the live odds tape, and referee assignments. The program's
**research** lane has never read any of them. Not one of the 63 exploration screens, not the
feature library, not the OOF runners. Every conclusion this program has reached about its own
skill — including "single-game scoring efficiency is not forecastable from pre-game state" — was
measured on an information set strictly poorer than the one its own shipped code is handed at run
time. The owner asked what data analysts have that we do not. A large part of the answer is: data
we already have, in this repository, updated within the hour, that the research lane cannot see.

---

## 1. Why the research lane cannot see it — the mechanism, verified on bytes

The exploration screens run inside the worktree
`.claude/worktrees/player-model-program/`. Its `data/` directory is **missing six directories that
exist in the main repository**:

    drive_masters/        entity_resolution/     injury_official_live/
    market_snapshots/     odds_capture/          sxbet_capture/

All six are listed in `.gitignore`. A worktree checkout does not carry ignored paths, so the
research lane's view of `data/` is a strict subset of reality.

This is not a hypothesis. `experiments/exploration/E1_I0013_tempo_redundancy/step0_env_audit.json`
records `"master_odds_hits": []`. That screen went looking for the odds master, correctly found
nothing, and correctly concluded that a market comparison was impossible. The conclusion was true
of its environment and was recorded as though it were true of the repository.

`data/drive_masters/master_odds.csv` holds **20,004 rows of timestamped game spread odds spanning
2022-05-21 to 2025-07-04** — three of the four exploration seasons.

**This is the cheapest correctable defect the audit found, and it silently narrows the scope of at
least one recorded impossibility.**

## 2. Method, and the D086 discipline

For each candidate source I (a) profiled the file on bytes — row count, columns, timestamp span,
cadence — and (b) established consumption by grepping `data/...` path literals across `features/`,
all `experiments/exploration/E0_*` and `E1_*` screens, the OOF runners and `daily_forecast.py`.

Per D086, **every grep hit was opened and read before being counted.** Three hits nominated a
capture source inside an exploration screen; all three failed on inspection:

| hit | what it actually is |
|---|---|
| `E1_I0013/make_findings.py:69` — `master_props_historical.csv` | an entry in a findings-declaration dict |
| `E1_I0034/scripts/redist_base.py:15-16` — both injury sources | a docstring explaining why they are **not** used (`manifest_present:false` / `UNVERIFIABLE`) |
| `E1_I0048/scripts/s07_findings.py:149` — `alias_table.json` | an entry in an artifact list inside a findings JSON |

Net: **zero exploration screens read any capture source as data.**

The screens' actual read surface is: `data/masters`, `data/w1_truth`, `data/shotcharts`,
`data/reference`, `data/zone_maps`, `data/rapm`, `data/possessions`, `data/playbyplay`,
`data/derived`.

## 3. The asymmetry, stated precisely

`daily_forecast.py` reads `data/injury_capture/injury_log.csv` (line 104), and uses it at
lines 612–694. Read the construction: a designation of **`Out` at the cutoff excludes the player**,
and **every other designation annotates and feeds nothing** (`daily_forecast.py:35-36` —
"Other designations annotate, never exclude"). So even in production, `Questionable`, `Probable`,
`Doubtful` and `Available` reach no fitted quantity. They are printed in a report.

Meanwhile **22.5% of pre-tip designation series change status**, and those changes are
`Questionable → Out` (7), `Probable → Out` (1), `Doubtful → Out` (2), `Probable → Available` (16),
`Questionable → Available` (11) — the exact resolutions a professional waits for.

## 4. Reading the construction, not the label — three cases where it mattered

**`era` is not a measurement-quality label.** It is assigned by column sniffing
(`wnba_schema.py:320-334`). The separation across the partition is perfect, but the two harms the
schema doc predicts — no `starter_flag`/`dnp_reason`, endpoint-rounded minutes — **do not occur**,
because `minutes_source` is the V3 `misc` boxscore on 100% of played rows in all six seasons. The
V3 layer bridges the eras. Full working in `REGIME_BOUNDARY.md`.

**`status_transitions.csv` is not 15,145 designation changes.** 99.0% of its rows are
`X → REMOVED_FROM_REPORT`, which is the report rolling over to the next game day, not a player's
status changing. Only ~150 rows are genuine transitions. A row count taken at face value here would
overstate the source by two orders of magnitude.

**`master_props_historical.csv` is not a tape.** It is *one* snapshot per event. Median lead 1.16 h,
p10 = p90 = 1.16 h — the acquisition was a single scheduled pull, not a poll. It is a fine
benchmark and useless for line-movement work.

## 5. Point-in-time provenance, per source

The instruction was to distinguish "we have it" from "we have it point-in-time". Summary:

- **Point-in-time provable:** `master_props_historical.csv` (`snapshot_returned_utc` strictly
  precedes `commence_time` on 100% of rows), `injury_capture/injury_log.csv` (`capture_utc` is a
  witnessed retrieval), `injury_official_live/*` (the strongest in the repository — `retrieval_ts_utc`
  kept separate from `provider_publication_ts_et`, with interval-censored bounds),
  `odds_capture/*`, `market_snapshots/snapshots.csv` (the only market file carrying an explicit
  `max_staleness_bound`), `drive_masters/master_odds.csv`.
- **Retrospective, and a trap:** `data/lineups/*.parquet` — season-aggregate totals retrieved
  2026-08-06. Confirmed unread by every screen, so the trap has not been sprung.
- **Retrospective file, strictly-prior records:** `injury_history/injury_history.csv`. The file is a
  one-off scrape, but a player's own dated prior absence spells are strictly-prior facts.
- **Unverified:** `sxbet_capture/*.jsonl`. Sampled lines failed JSON parse. I did not establish
  record-level timestamp semantics and therefore assert nothing about it.
- **No provenance at all:** `master_player.parquet.observed_time` has **10 distinct values across all
  33,712 rows**, all within 2026-07-31T20:42 → 2026-08-01T13:01. It is the build time, not an
  observation time. The master carries no point-in-time information whatsoever, which is correct for
  a retrospective outcome table and worth stating so nobody mistakes it for one.

## 6. Freshness note

The main-repo master runs through **2026-08-07** (built 2026-08-08). The live captures run through
**2026-08-17**. The worktree master stops at **2026-07-31**. There is therefore a ten-day window of
captured pre-game information with no corresponding outcomes yet, and the overlap available for any
join today is nine game days.

## 7. Things I deliberately did not do

- Did not measure any effect, fit any model, or compute any skill delta.
- Did not open `DECISION_LEDGER.jsonl` or `GRAPH_EVENTS.jsonl`.
- Did not write outside this directory, did not commit, did not push.
- Did not spawn subagents.
- Did not read the large parquet/jsonl payloads in full — sampled columns and streamed line counts.

## 8. The honest size of what was found

The largest concrete thing is **a market benchmark that already exists on disk, covers 100% of 2024
and 2025 games, and has never been used**. That is a measurement opportunity, not a measurement. It
does not tell anyone whether this program forecasts well. It tells them the question is now cheaply
answerable, on 6,366 player-game rows, against the price a book actually charged 70 minutes before
tip — and that until now it has not been asked.

The second largest is a **~71-hour gap** between the program's feature cutoff and the moment the
information that decides availability lands. That gap is real and quantified. Whether closing it
buys anything is untested, and this audit does not license anyone to say otherwise.
