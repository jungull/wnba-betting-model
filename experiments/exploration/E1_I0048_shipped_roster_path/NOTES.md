# NOTES — E1_I0048_shipped_roster_path

**Question asked:** characterise and quantify the roster-currency defect at
`daily_forecast.py:647-665` — the only defect found in the preceding twenty-four hours that sits
on the shipped, scheduled path.

**Answer in one line:** it was real, it was repaired in production on 2026-08-06 (one day before
this screen ran and one day after it was reported), the 40 shipped records emitted before the
repair contain **zero** phantom pairings, **zero** duplicates and **zero** drops, and nothing
reads those fields anyway.

**Nothing was enacted. No production file was modified.**

---

## 1. Partition boundary — declared before anything else

**Every record in `forecasts/forecast_log.jsonl` falls in 2026.** The log opens 2026-07-31T14:28Z
and its latest record is 2026-08-08T23:45Z. 2025/26 is the **SEALED confirmation holdout**.

This screen therefore did exactly one of the two activities the brief distinguishes:

* **Done:** counted rows and names emitted by a production code path, and re-executed that code
  path to check the counts. These are descriptions of the code's output.
* **Not done, and refused by construction:** any skill statistic on sealed output. No Brier,
  log-loss, AUC, MAE, calibration, hit rate, CLV, or realised-vs-predicted comparison. No game
  outcome column was ever loaded — the analysis frame is an eight-column allowlist
  (`game_id, season, game_date, team_id, team_abbreviation, player_id, player_name, minutes`) and
  every script asserts that `pts, fgm, fga, reb, ast, plus_minus, appeared` are absent. The
  assertion is printed in `run_log_s02/s03/s05.txt`.

`minutes` is on the allowlist because it is a **model input** — the promoted
`minutes_ewma_vs_carryforward_v1` component — and reproducing the shipped `sum_min_ewma_available`
was the fidelity test. It is never used as an outcome.

The 2021–2024 exploration partition was used for the anchors and for the key-comparison
denominator (§5). The 2026 counts are labelled `SEALED-PARTITION / DESCRIPTIVE ONLY` throughout.

---

## 2. Anchors — 24 of 24, every one at exactly 0.000e+00

No new statistic was computed until these passed. Each was **recomputed** from the prior screen's
stored frame, never transcribed. Full table in `ANCHOR_REPRODUCTION.csv`.

| id | quantity | published | mine | diff |
|---|---|---:|---:|---:|
| A1 | RS1P champion rows | 20,084 | 20,084 | 0 |
| A2 | tier-B admitted by S2 | 3,266 | 3,266 | 0 |
| A3 | tier-B admitted by S_TX only | 506 | 506 | 0 |
| A4 | S2 by seasons-since-club | 1,765 / 991 / 432 / 78 | identical | 0 |
| A5 | S2 departed / not departed | 1,489 / 1,777 | identical | 0 |
| A6 | RS1P rows in the decision stratum | 4,964 | 4,964 | 0 |
| A7 | `p_active` refs across 9 production files + 5 production trees | 0 each | 0 each | 0 |

A7 is the direct analogue of this screen's consumer question and was recounted rather than
assumed — 14 separate counts, all zero.

---

## 3. The finding that reframes the task

E1_I0045 read `.claude/worktrees/player-model-program/daily_forecast.py`. Production runs
`C:\Users\jgallagher\wnba-betting-model\daily_forecast.py`. **They are different files** — 1,300
vs 1,523 lines — and the roster block is where they diverge.

Dating it from the `source_version` git sha recorded inside each shipped record, then `git show`
on each sha (read-only):

| sha | date | naive name-keyed roster | `entity_resolution` | records |
|---|---|---:|---:|---|
| `f7f9a189` | 2026-07-31 | 1 | 0 | 0–2 |
| `6fc79daf` | — | 1 | 0 | 3–5 |
| `b3026fc5` | — | 1 | 0 | 6–7 |
| `735b63bc` | 2026-08-01 | 1 | 0 | 8–39 |
| **`55d84f1e`** | **2026-08-06 15:47 −0400** | **0** | **2** | 40–44 |
| `9cfe22e6` | — | 0 | 2 | 45–47 |
| `5943846f` | 2026-08-07 | 0 | 2 | 48–63 |

The worktree copy matches `735b63bc`, which **was** production when E1_I0045 was written. The
screen was correct about the code in front of it; the worktree did not move when production did.
Logged as **D-3** with the convention that would have prevented it.

---

## 4. Fidelity — the gate that makes the damage numbers mean anything

The shipped log records five aggregates and the `Out` names. **The roster name list is never
written**, so the defect could only be quantified by re-executing the rule and proving the
re-execution *is* the shipped code.

| era | team-slots | reproduced exactly | by |
|---|---:|---:|---|
| pre-repair (records 0–39) | 76 | **76 / 76** | my re-implementation of the naive rule |
| post-repair (records 40–63) | 44 | **41 / 44** | production `entity_resolution.player_layer_resolved`, imported read-only |

"Exactly" means: `n_roster` integer-equal, `n_out` integer-equal, the `out_home`/`out_away` name
sets set-equal, and `sum_min_ewma_available` / `vacated_min_ewma` equal to 1e-9.

**76/76 is the load-bearing number.** The rosters in `SHIPPED_DAMAGE.csv` are not a plausible
reconstruction — they are the shipped rosters.

The reproduction pattern is also independent evidence for the era boundary: the naive rule
reproduces records 0–39 and fails on ≥40; the repaired module reproduces ≥40. Neither was told
where the boundary was.

The 3 failures are one player (Phoenix, `Kara Dunn`) whose only master row is dated on the slate
date and is excluded by the code's own date filter. Input drift; those slots back no number.

---

## 5. The measured damage

**On the 76 fidelity-passed pre-repair team-slots:**

| | count |
|---|---:|
| **stale phantom pairings** (appeared for this club, has since appeared elsewhere) | **0** |
| name→multiple-id collisions (a player silently dropped/merged) | **0** |
| id→multiple-name variants (a player silently duplicated) | **0** |
| slots where the name key and the `player_id` key give different rosters | **0 of 76** |
| **affected emissions reaching the DECISION STRATUM** (≥8 prior appearances AND ≥24 trailing-5 minutes) | **0** |

E1_I0045's `departed` predicate ported verbatim flags **9** emissions. All nine are
`ARRIVAL_NOT_YET_DEBUTED` — newly acquired players who had not yet debuted for the acquiring club
— and all nine are **correct** rostering. See **D-1**: this was my own error, caught by opening
the named cases rather than reporting the count.

Named, since named cases are worth more than rates:

| player | `player_id` | club emitted | reality at the cutoff |
|---|---:|---|---|
| Haley Jones | 1641650 | DAL (5 records) | acquired by DAL, 6 DNP rows, 0 DAL appearances — correct |
| Aneesah Morrow | 1642800 | TOR (3 records) | acquired from CON 2026-08-02, debuted 08-04 — correct |
| Chloe Bibby | 1631064 | MIN (1 record) | acquired from CHI, not yet debuted — correct |

**Why zero stale pairings, mechanistically:** a mid-season move appears in the *acquiring* club's
box score immediately, as a DNP row, so the acquiring side is always right. The failure mode is on
the *losing* side and needs that club to play a shipped slate within three games of the move.
Connecticut lost Morrow on 2026-08-02 and would have carried her for three more games — but
Connecticut's only shipped records (45/48/51, 2026-08-07) are **post-repair**. The defect's one
real opportunity in the logged window fell on the far side of the fix by one day.

---

## 6. The name key

`player_id` is present in the very frame line 647 reads, with **0 nulls in 34,199 rows**, 18 lines
above the call that used `player_name` instead. Full treatment in `NAME_KEY.md`.

Simulating the roster at **every** team-game index — 3,030 windows, same frame, one line changed:

| partition | windows | keys differ | rate |
|---|---:|---:|---:|
| 2021–2024 (exploration) | 1,940 | **196** | **10.10 %** |
| 2025 (SEALED) | 620 | 0 | 0 % |
| 2026 (SEALED) | 470 | 8 | 1.70 % |

Every difference is +1 or +2 — the **duplication** mode. The drop mode has zero instances: no
`player_name` maps to more than one `player_id` anywhere in the master.

13 identities carry more than one spelling: seven diacritic pairs (absorbed by `_norm_name`, so
harmless to the designation gate), one hyphenated surname (`Skylar Diggins` → `Diggins-Smith`),
two maiden/married pairs (`Megan DiLeo` → `Gustafson`; `Eliska Hamzova` → `Joklova`), and one
name-order transliteration (`Han Xu` / `Xu Han`). The last three categories are the ones
`_norm_name` cannot absorb, and they are exactly where the `Out` gate could fail to fire.

---

## 7. The result that most weakens this screen's conclusion

**The shipped zero is timing, not safety.**

The only 2026 identity with two spellings is Minnesota's `player_id` 1643490, `Eliska Hamzova` /
`Eliska Joklova`. Her name alternated through May and early July and settled on `Joklova` from
2026-07-06; the last box score carrying `Hamzova` is 2026-07-03. The eight differing 2026 windows
end at Minnesota's slate index 22 — in effect around **2026-07-09**.

**The shipped log opens 2026-07-31 — 22 days later.**

Had regime D started three weeks earlier, Minnesota would have shipped a 15-name roster containing
one player twice, with her minutes history split across the two entries and
`sum_min_ewma_available` correspondingly wrong. The correct reading of the zeros in §5 is *"this
defect did not fire during the window that happened to be logged"*, not *"this defect was
harmless"*.

Two further weakeners, in `CONSUMERS.md` §6: "reaches nothing" is a snapshot of today's
repository, not a property of the design — the layer is labelled `v0` and `informational`, and the
obvious v1 is one that feeds the forecast; and a token-count consumer trace cannot prove the
absence of a dynamic JSON-walk access path, only that none of the eight readers uses one.

---

## 8. Anti-substring discipline

This screen audits a name-keyed join and did not commit one.

* Every column resolved by **explicit allowlist**, printed at the head of each run log, asserted
  present, with the outcome-column blocklist asserted absent.
* Every player identity comparison on `player_id`. No `str.contains`, no `startswith`, no fuzzy
  match, no casefold anywhere in a selector.
* Name-collision analysis groups by the **exact** `player_name` value — `groupby(...).nunique()`,
  never a pattern.
* The one place a normalised name appears (`_norm_name`) is a **verbatim copy of the production
  function**, reproduced to re-execute the shipped code, never used to select rows for analysis.
* The consumer trace counts literal tokens and then **opens every hit**; the single non-writer
  match (`cbs_v6.py:466`) is quoted and dismissed on inspection rather than counted.

---

## 9. Provenance and manifest status

| artifact | manifest | used for |
|---|---|---|
| live `data/masters/master_player.parquet` | **NONE** (D-4) | reconstruction of shipped rosters; labelled UNVERIFIABLE |
| worktree `data/masters/master_player.parquet` | present, `asof_granularity: "row"` | cross-check on the 2026-07-31 slate — **16/16** team-slots |
| `data/injury_capture/injury_log.csv` (both) | **NONE** | reproducing `n_out` only, inside the fidelity gate |
| `E1_I0045/_PF.parquet` | (screen artifact) | anchors A1–A6 |
| `forecasts/forecast_log.jsonl` (live) | — | the shipped artifact under study |

Source files are identified by absolute path and git sha throughout, per the convention proposed
in D-3.

---

## 10. Process

Six scripts, `s01`–`s06`, run logs alongside. One background task launched by me
(`bvfqtp4qz`, a slow whole-repo scan) was superseded by a targeted equivalent and stopped **by its
own task id**. No blanket process kill of any kind was issued; no other process was touched. No
`git` write command was run — `git show` and `git log -s` are reads. All writes are inside
`experiments/exploration/E1_I0048_shipped_roster_path/`.
