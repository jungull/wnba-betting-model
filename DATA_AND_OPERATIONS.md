# Data and operations — what a successor needs, and where it is

> **MIRROR.** The canonical copy of this file lives on `data-refresh-2026`, next to the data
> and the operations layer it describes. It is duplicated here because a successor who starts
> on `player-model-program` would otherwise never see it — this worktree does not contain the
> capture directories at all. If the two ever disagree, the data branch is authoritative.

Written 2026-08-21 after an audit that asked: *if work stopped today, could someone continue
from GitHub plus this machine alone?* The answer was no, for four reasons. Three are fixed by
the commit that carries this file. The fourth is recorded below because it cannot be fixed by
committing anything.

---

## 1. The branch topology, which is the first thing to understand

This repository is not one line of work. Two branches matter:

| branch | what lives there |
|---|---|
| `data-refresh-2026` | **the live data and the operations layer.** The main checkout sits here. Every capture writes here. |
| `player-model-program` | **the analysis programme.** 108-node graph, decision ledger, every experiment and market node. |

They are deliberately separate and do **not** merge. A successor needs **both**.

The analysis branch is checked out as a git worktree at
`.claude/worktrees/player-model-program/`. **A gitignored path does not appear in a worktree**,
which is how the programme once lost sight of six data directories entirely (D138, D146). If a
script cannot find its input, check which branch you are standing in before concluding the data
is missing.

## 2. Inputs that ARE in git

Everything an analysis node reads is now committed, including three directories that were
gitignored until this commit:

| directory | files | size | note |
|---|---|---|---|
| `data/odds_capture` | 710 | 73.9 MB | **un-ignored here.** The odds tape. M30, M31 and the opportunity board are unreproducible without it |
| `data/officials` | 1,489 | 5.8 MB | **un-ignored here.** Referee assignments; the crew-tendency work reads these |
| `data/drive_masters` | 3 | 11.2 MB | **un-ignored here.** Master odds export; D147's spread-line dispersion reads it |
| `data/props_capture` | 1,028 | 30.6 MB | player prop archive — M13, M14, M32 |
| `data/injury_official_live` | 845 | 86.7 MB | official injury reports — M34, M35 |
| `data/masters` | 14 | 19.3 MB | master player/team tables |
| `data/shotcharts` | 22 | 2.5 MB | per-shot zones |
| `data/market_snapshots` | 11 | 45.9 MB | market ladder snapshots |
| `data/sxbet_capture` | 6 | 975 MB | exchange tape (provenance unverified — D138 ruling 6) |

## 3. Inputs that are NOT in git, deliberately

| directory | size | why |
|---|---|---|
| `data/injury_history/raw/` | 622 MB | raw scrape archive. The derived tables ARE committed |
| `data/news_capture/raw/` | 200 MB | raw scrape archive. Same |
| `data/zone_maps/shots_enriched.parquet` | — | derived; rebuild from `data/shotcharts` |
| `data/possessions/possessions.parquet` | — | derived; `build_possessions.py` |

**These are raw source archives, not analysis inputs.** No node in the graph reads them
directly. If one ever does, that node cannot be reproduced from a clone and must say so.

## 4. What GitHub cannot carry, and what to do about it

**Every capture in this programme is a Windows Scheduled Task on one laptop.** Clone the repo
on another machine and you get the code and the history; you get **no data collection at all**,
and the archives simply stop growing.

The task definitions are exported to `ops/scheduled_tasks/*.xml` (17 tasks). To restore them:

```
Register-ScheduledTask -Xml (Get-Content .\ops\scheduled_tasks\WNBA_OddsCapture.xml | Out-String) -TaskName "WNBA_OddsCapture"
```

Each task runs `wscript.exe //nologo scripts/run_hidden.vbs <wrapper>.cmd`, where the wrappers
live in `logs/task_wrappers/` and **are tracked**. The `run_hidden.vbs` indirection exists so
the captures do not flash console windows every few minutes (D148); it is not decoration —
closed windows previously destroyed about 28 capture cycles.

**Known operational limits, unchanged by this commit:**

* Capture coverage is roughly 61% and the binding constraint is whether the laptop is awake,
  not how fast it polls (D154). A six-day blackout sits inside the August 2026 injury window.
* `WNBA_DailyRefresh` exits 1. That is a **correct detection of a real capture gap**, not a
  defect to be silenced.
* The tasks reference paths inside `.claude/worktrees/player-model-program/`. Moving or
  removing that worktree breaks every capture.

## 5. Where to start reading

1. `experiments/player_program/orchestration/reports/CURRENT_STATUS.md` — regenerate first with
   `python scripts/graphctl.py status`; it is derived, not hand-maintained.
2. `experiments/player_program/orchestration/GRAPH_POLICY.md` — the rules the programme runs
   under, including the evidence ladder and the partition rule (§13.2: 2025/26 is confirmation
   holdout for exploration screens; market-program nodes score it deliberately).
3. `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` — **the single most
   valuable artifact here.** 175 decisions, each with its ruling, the discipline applied, and a
   preserved disagreement. Read the last twenty before touching anything.
4. `HANDOFF_PLAYER_MODEL_PROGRAM.md` and the other `HANDOFF_*.md` files.

## 6. The state of the science, in four lines

* **No profitable strategy has been found.** The last candidate — betting quotes that beat the
  de-vigged consensus of other books — returns **−7.2%** against realised outcomes (D172).
* **The model loses to the market by 0.31 points of MAE, and the deficit is entirely minutes.**
  Given correct minutes its existing rate model beats the market by 0.33 (D173).
* **Closing that needs a 40% cut in minutes error**, roughly five times anything the modelling
  programme has achieved on that target.
* **Promotions are the only route never measured**, and only because no real offer has ever
  been entered into `promos.json`.
