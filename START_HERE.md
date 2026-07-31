# START HERE — WNBA prediction engine

*Entry point for any new session. Read this first, then the three documents in §1.
Last updated 2026-07-31.*

## 0. What this project is

Three separate systems sharing one data foundation, each with its own targets and gates:
a **basketball forecasting model** (game outcomes from basketball information only), a
**market model** (line behaviour), and a **betting decision system** (the first two, sized
under risk control). The goal is to beat the market on a preregistered prospective sample
**or to prove honestly that we cannot**. Both are acceptable outcomes; a backtest mirage is
not.

## 1. Read these, in order, before touching anything

| # | document | what it gives you |
|---|---|---|
| 1 | `project_docs/HANDOFF_2026-07-31.md` | **current state and next actions** — start here |
| 2 | `ROADMAP.md` | the plan, the four evaluation regimes, promotion gates |
| 3 | `project_docs/HANDOFF.md` §3 | the constitution — leakage discipline, walk-forward, no imputation |
| 4 | `project_docs/SESSION_JOURNAL_2026-07-31.md` | how we got here, including every retraction |
| 5 | `project_docs/PROGRAM_FIREWALL.md` | which program may know what; why the live log is the only holdout |
| 6 | `experiments/registry.jsonl` | every registered experiment, every result, every erratum |

The amendment chain (`screening_protocol_amendment_v2` … `v5`,
`conditional_edge_design_freeze_v2`) in the registry is **binding** and supersedes older
methodology wherever they conflict. Later amendments control over earlier ones.

## 2. The one rule that matters most

**Preregister every experiment before computing anything.** Write the hypothesis, features,
metric and pass/fail thresholds into `experiments/registry.jsonl` via
`evalharness.register(...)` and commit it *first*. Unregistered results are void. Agents
never register, never render leaderboards, never run git — the orchestrator preregisters,
independently verifies the agent's numbers from row-level artifacts, records, renders and
commits.

## 3. Where things stand in one paragraph

The model does not beat the market. Best case is 2026 game margins about 0.12 points behind
with an interval spanning zero — parity, not edge. We are behind on totals (0.29), behind
on player props (0.31, in every slice), and our cover probabilities are worse than a coin
flip at near-tip. The prospective log started 2026-07-31 and is the only surface that can
confirm anything. The live research question is not "do we beat the market" but **"can we
predict in advance the subset where we do"** — the conditional-edge experiments.

## 4. What runs by itself

Six scheduled tasks on this machine: odds and injury capture hourly (10:00–23:00), news
plus extraction 4×/day, referee assignments daily, `daily_refresh.py` at 08:30, props
capture 4×/day, and the two forecast runs (10:20, 18:45 ET). **The machine must stay on** —
a missed day is permanently missing from the prospective chain and is never backfilled.

## 5. Standing rules for working here

- `python daily_certify.py` before believing anything about the data.
- Gate every commit on test exit codes: `tests/test_evalharness.py`,
  `test_forecast_log.py`, `test_permutation_integrity.py`, `test_asof_invariant.py`.
- No double-quote characters inside `git commit -m` here-strings (PowerShell 5.1 mangles
  them).
- One stats.nba.com crawler at a time; avoid 08:25–08:45 local (the refresh window).
- API keys live in the git-ignored `.env` at the repo root. The repo is public. Never
  commit them.
- Report candidates as candidates. Nothing is "confirmed" until an untouched holdout
  evaluates a frozen model.
