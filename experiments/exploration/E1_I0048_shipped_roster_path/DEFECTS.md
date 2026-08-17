# Defects found by, and in, E1_I0048_shipped_roster_path

---

## D-1 — MY OWN: I ported E1_I0045's `departed` predicate verbatim and it inverted its meaning

**Where.** `scripts/s03_damage.py`, first run.

**What happened.** I ported the departure signal from E1_I0045
`scripts/s01_build_and_anchor.py:277-278` unchanged:

```python
pf["departed"] = (lad.notna() & (pf["last_any_team"] != pf["team_id"])
                  & (lcd.isna() | (lad > lcd)))
```

It reported **9 phantom player-club pairings** in shipped output, with named cases — Haley Jones
on Dallas, Aneesah Morrow on Toronto, Chloe Bibby on Minnesota. That is a publishable-looking
finding on the shipped critical path, and it is wrong.

**Why it is wrong.** The `lcd.isna()` disjunct means *"she has never appeared for this club"*. In
E1_I0045's setting that is the defect: those rows are admitted by **S2, prior-season affiliation**,
so a player who never appeared for the club is a stale ghost. On the **shipped** roster the
predicate inverts, because the shipped roster already requires membership of the club's box score
in its last three games (DNP rows included). A player who is in this week's box score but has
never *appeared* for the club is not a ghost — she is a **new signing who has not yet debuted**.
All three named players had just been acquired; all three were correctly rostered.

**How it was caught.** By printing the named cases and opening the box-score trail for each,
rather than reporting the count. Haley Jones has six consecutive Dallas DNP rows and zero Dallas
appearances — visibly an arrival, not a departure.

**Fixed** by splitting the predicate into `STALE_PHANTOM_PAIRING` (has appeared for this club, has
since appeared elsewhere — the actual defect) and `ARRIVAL_NOT_YET_DEBUTED` (has never appeared
for this club — correct rostering). Corrected result: **0 stale, 9 arrivals.** Both are reported
in `SHIPPED_DAMAGE.csv`; the verbatim-predicate count of 9 is reported alongside so the
discrepancy with E1_I0045's definition is visible rather than hidden.

**Generalisable lesson.** A predicate carries the assumptions of the row set it was written for.
E1_I0045's rows were candidacies admitted *without* current box-score membership; the shipped
rows are admitted *by* it. Porting the predicate across that boundary flipped its sign. **A ported
definition needs its admission criterion checked, not just its column names.** This is the same
class of error as D-1 in E1_I0045 and D-1 in E1_I0035 — a function that does not say what it
actually measures — and it is the third consecutive screen to log one.

---

## D-2 — MY OWN, caught within the turn: I nearly concluded the shipped log has no player fields

On first inspection I enumerated the **top-level** keys of `forecasts/forecast_log.jsonl` and found
no player-layer field, and briefly recorded that the log carries none. The player layer is nested
inside `core_only_prediction.player_layer_informational`. Had that stood, this screen would have
reported "the defect reaches nothing because nothing is emitted", which is the right conclusion
reached by a false route — and it would have contradicted E1_I0045's REACH.md §4, which quoted the
`out_away` values correctly. Corrected before any statistic was computed. **Recorded because a
right answer via a wrong mechanism is not detectable from the answer.**

---

## D-3 — E1_I0045's D-2 cites a worktree file as production without recording which worktree

**Where.** `E1_I0045_roster_currency/DEFECTS.md` D-2, `REACH.md` §4, `UNIVERSE_CONSTRUCTION.md` §6.

All three cite `daily_forecast.py:647-665` as being "on the critical scheduled path
(`WNBA_DailyForecast_AM` / `_PM`)". The file read was
`.claude/worktrees/player-model-program/daily_forecast.py` (1,300 lines). The file that runs is
`C:\Users\jgallagher\wnba-betting-model\daily_forecast.py` (1,523 lines). They are not the same
file and their roster construction differs completely.

**At the time E1_I0045 was written the claim was true**: the worktree copy matches commit
`735b63bc` (2026-08-01), which was production. The repair landed the next day in `55d84f1e`
(2026-08-06 19:47 Z). So this is not an error of fact at the time of writing — it is a **missing
provenance stamp** that made the claim un-ageable. A reader today, following D-2 to the cited
lines in the cited file, sees the defect and concludes it is live. It is not.

**Cheapest possible remedy, and it is a convention rather than a change:** a screen citing a
production file should record the **absolute path and the git sha** it read, exactly as this
programme already requires for data artifacts. Every conclusion about "the shipped path" in this
programme is a claim about a specific blob. `MISSING = UNVERIFIABLE` is enforced for parquet
manifests; the same discipline is not being applied to source files.

**Not enacted.** Nothing in E1_I0045 was modified — it is outside my write scope and its
conclusions were correct when written.

---

## D-4 — The master that feeds production has NO MANIFEST; the one that does is the research copy

**Where.**

| file | manifest |
|---|---|
| `C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet` (**what production reads**) | **NONE** |
| `.claude/worktrees/player-model-program/data/masters/master_player.parquet` (research copy) | present — `asof_granularity: "row"`, `fit_through_date 2026-08-01T12:00Z` |

The programme's standing rule is `MISSING = UNVERIFIABLE and may back no number`. Applied
literally, **no number about production can be backed by production's own input**, because the
manifest lives on the copy that production does not read.

This is not a leakage or correctness defect — the two files agree, and the shipped aggregates
reproduce from the live copy at 76/76 — but it is a governance gap that will bite any screen
trying to make a verifiable claim about the shipped path. The same is true of
`data/injury_capture/injury_log.csv`, which has no manifest in either location and is a direct
input to the shipped availability gate.

**Consequence honoured in this screen:** every number computed from the live master is labelled as
resting on an unmanifested artifact, and the manifest-verified worktree copy was used to
cross-check the subset it covers (16/16 team-slots on the 2026-07-31 slate). **Not repaired —
writing a manifest is a production act.**

---

## D-5 — A document the brief cites does not exist

`experiments/exploration/E1_I0035_availability_sum/REACH.md` is named in the task brief as
required reading. That directory contains `DEFECT_ANATOMY.md`, `REPAIR_OPTIONS.md`, `DEFECTS.md`
and `NOTES.md`, but **no `REACH.md`**. The zero-reference finding attributed to it is real and is
recorded in `E1_I0045_roster_currency/REACH.md` §1, which is where I read it and which I
independently recounted as anchor A7 (14 files/directories, all at exactly 0). Recorded so the
citation does not propagate a third time.

---

## Not defects, recorded so a later reader does not re-derive them

* **The worktree's `forecasts/forecast_log.jsonl` is stale** — 8 records vs the live 64. The
  market program's `M01_MARKET_DATA_INVENTORY` already flagged an 8-vs-40 discrepancy on
  2026-08-06; it is now 8 vs 64. The worktree copy is not a truncation, it is a snapshot: its 8
  records are byte-identical to live records 0–7.
* **4 of the 64 shipped records carry no player layer at all.** They are `no_forecast` records
  (`status` / `no_forecast_reason` present, `player_layer_informational` absent) emitted by the
  completeness rule for skipped games. Not a defect — a skipped game has no roster to report — but
  it means the player-layer denominator is 60 records / 120 team-slots, not 64 / 128.
* **`cbs_v6.py:466` matches the token `n_cold_start`** and is not a consumer; it is an unrelated
  local dict key. Opened and dismissed in `CONSUMERS.md` §4.
* **3 post-repair team-slots (Phoenix, records 45/48/51) do not reproduce.** One player,
  `Kara Dunn`, whose only master row is dated on the slate date itself and is therefore excluded
  by the `game_date < slate_date` filter; she entered at run time via a designation transfer whose
  feed row has since changed. Input drift, not a code difference. Those slots back no number.
