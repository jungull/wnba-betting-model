# O13_LEAD_WINDOW_LATENCY — Lead-window latency defect

**Epistemic status (verbatim from the node contract):**

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch
> only. This lane does not block possession research unless it changes the historical feature
> evidence.

**Node:** O13_LEAD_WINDOW_LATENCY · lane operations · type audit · severity on failure C
**Worktree:** `C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`, branch `player-model-program`
**Write scope used:** `experiments/player_program/ops_lane/O13_LEAD_WINDOW_LATENCY/` only. No file outside it was created or modified. No git command was run. No shared schema or contract file was edited.

---

## 0. Verdict in one paragraph

The defect **is documented**, it **reproduces exactly** — byte-for-byte the two records the
document names — and its **stated mechanism and stated remediation target are both wrong**. The
two late records were not produced by the gated 15-minute path at all. `should_run_base.py`
evaluated 2.44 seconds before they were written and **declined to fire**. They were written by a
*second, independent Windows scheduled task* (`WNBA_DailyForecast_PM`) that runs
`daily_forecast.py --live` at a fixed 18:45 ET wall-clock time and never consults the gate.
Amending `should_run_base.py` — the fix the project update assigns to D-d — therefore cannot fix
D-d, because the writer never reads it. Separately, one of the two "late" records was **on time by
15 minutes against the tip that was known when it was written**; it became late only because an
upstream tip revision arrived afterwards and the auditor recomputes cutoffs from the latest tip.
That second fact has a numeric consequence for a published receipt figure, stated in section 6.

---

## 1. Is the defect documented, and where

Yes. It is defect **D-d** in the project update:

- `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:202` — the defect row:
  *"**Lead-window execution latency.** Two records created 22:45:08Z against 22:34 / 22:44 cutoffs.
  Distinct from D-b: discovery worked, execution was late."* Severity **B**, required action
  "separate correction".
- `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:266` — prioritized action (4),
  "Address lead-window latency (D-d)".
- `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:571-572` — repair-set item (iv),
  "lead-window execution latency (D-d), a separate correction since discovery worked and execution
  was late."
- `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:611` — contract-amendment map assigns
  D-d to `prospective_pair/should_run_base.py`, owner "team thread", bundle "no — internal".

The node graph pairs this node with O11 (`PROGRAM_GRAPH.json`, node `O11_OBLIGATION_DISCOVERY_LEAD_WINDOW`,
title "Obligation-discovery lead window defect"), which is the *other* documented defect, D-b
(`PROJECT_UPDATE_2026-08-04.md:200`). The two nodes are not duplicates; D-b is discovery, D-d is
this one.

**Scope note, stated plainly.** The node's declared read scope is `experiments/player_program/`.
The defect's subject code — `prospective_pair/*`, `daily_forecast.py`, `forecasts/forecast_log.jsonl`,
`forecasts/runner_logs/*` — lives at the live repository root, on a different worktree/branch. It
was **read only**, never written, and never executed in a mode that writes (see section 3). Without
reading it the defect could not have been reproduced at all.

## 2. Reproduction — REPRODUCED

Script: `repro_d_d.py` (this directory). Run as
`python repro_d_d.py C:/Users/jgallagher/wnba-betting-model`.
It imports `prospective_pair.coverage_audit` and calls `audit()` **in memory**; it never calls
`coverage_audit.main()`, which would write `forecasts/coverage_audit.csv` and
`forecasts/coverage_receipt.json` into the live repository.

Official chain: **23 records**. Exactly **two** were created after their own nominal cutoff:

| record_idx | game_id | matchup | label | nominal cutoff (latest tip) | created | latency |
|---|---|---|---|---|---|---|
| 19 | 1022600223 | NYL v SEA | T-30m | 2026-08-03T22:34:00Z | 2026-08-03T22:45:08.958486Z | **+11.15 min** |
| 20 | 1022600222 | ATL v LVA | T-30m | 2026-08-03T22:44:00Z | 2026-08-03T22:45:08.976775Z | **+1.15 min** |

This is the documented pair exactly: "two records created 22:45:08Z against 22:34 / 22:44 cutoffs".
The auditor independently classifies both as `late_record`
(`prospective_pair/coverage_audit.py:228`), and its in-memory summary reproduces the published
receipt of `PROJECT_UPDATE_2026-08-04.md:539-552` term for term: obligations 84, not-yet-due 22,
due 47, served 15, coverage 0.3191, operational misses 26, unexplained 0, `promotion_grade` false.

**D-d reproduces.**

## 3. Root cause — the documented mechanism is wrong

### 3.1 The gate declined, 2.44 s before the write

`forecasts/runner_logs/pair_20260803.log:862-870`, the 18:45 ET tick of the gated runner:

```
==== Mon 08/03/2026 18:45:02.67 ====
[gate] 2026-08-03T22:45:06.515064+00:00  fire=False  -- would duplicate 1 already-served obligation(s); ...
       NYL v SEA      T-30m   unserved cutoff 2026-08-03T22:30:00 (-15 min)
       ATL v LVA      T-30m   unserved cutoff 2026-08-03T23:00:00 (+15 min) IN-WINDOW
       CHI v PHX      T-90m   SERVED   cutoff 2026-08-03T23:30:00 (+45 min)
[gate] HOLDING: firing now would append 1 permanent duplicate record(s) ...
[base] skipped - no unserved obligation in its lead window
```

The gate ran at **22:45:06.515Z**, returned `fire=False`, and `run_pair.cmd` took the `else`
branch and did not invoke `daily_forecast.py`. The records were written at **22:45:08.958Z**,
2.44 s later. The companion arm runner, which started at 22:45:08.859Z, printed
`base records in official chain: 19` (`pair_20260803.log:872-874`) — i.e. records 19-21 did not
yet exist when it read the chain 0.1 s before they appeared. The writes came from a **different
process**, concurrently.

### 3.2 The actual writer

`schtasks /query` (read-only) shows two scheduled tasks that run the base job directly, outside
`run_pair.cmd` and outside the gate:

| task | action | schedule | last run |
|---|---|---|---|
| `\WNBA_DailyForecast_AM` | `python daily_forecast.py --live` | Daily 10:20:00 AM, no repetition | 8/4/2026 10:20:01 AM |
| `\WNBA_DailyForecast_PM` | `python daily_forecast.py --live` | Daily 6:45:00 PM, no repetition | **8/3/2026 6:45:01 PM** |
| `\WNBA prospective pair` | `prospective_pair\run_pair.cmd` | Daily, repeat PT15M | — |

`WNBA_DailyForecast_PM` last ran **2026-08-03 18:45:01 ET = 22:45:01Z**. The first of the two late
records appeared **7.96 s later**, at 22:45:08.958Z. Startup-to-write latency of that process is
therefore about 8 seconds, and the three records it wrote are 0.037 s apart end to end.

The same signature appears on every other day of the chain: records at 22:45:06Z (2026-07-31,
idx 3-5), 22:45:07Z (2026-08-01, idx 8-9), 22:45:08Z (2026-08-03, idx 19-21), and 14:20:03Z
(2026-08-04, idx 22 — the 10:20 ET AM task). On 2026-08-04 the gated runner **never fired at all**
(`grep "BASE RUN DUE" forecasts/runner_logs/pair_20260804.log` returns nothing) yet idx 22 exists.
Only idx 13-18, created 21:09:39Z and 21:10:13Z, came from `run_pair.cmd`
(`pair_20260803.log:1,104`) — and those are the four commissioning duplicates the auditor already
counts.

### 3.3 What that means for the documented remediation

`PROJECT_UPDATE_2026-08-04.md:611` assigns D-d to `prospective_pair/should_run_base.py`. The gate
in that file admits an obligation when `-0.5 <= minutes_to_cutoff <= 20`
(`should_run_base.py:92`, `LEAD` at `should_run_base.py:43`). It is arithmetically incapable of
authorising a write 11.15 minutes past a cutoff, and on the night in question it authorised
nothing. **Any amendment to `should_run_base.py` leaves D-d exactly where it is.** The document's
own framing — "discovery worked, execution was late" (`:202`, `:572`) — is the part that does not
hold: discovery was not consulted.

Note the asymmetry this exposes. The **challenger** path already refuses late writes in two
places: `prospective_pair/alt_model_log.py:21-24` ("NEVER LATE ... A normal forecast whose
creation time is after its own cutoff is refused") and `prospective_pair/run_prospective.py:177-183`
(`late_prevented`). The **official** chain has no equivalent rule anywhere. That is why every late
record in the repository is a base record.

## 4. Second, independent finding — retroactive relabelling by tip revision

The gate's own log line at 22:45:06Z prints T-30m cutoffs of **22:30** (NYL v SEA) and **23:00**
(ATL v LVA). The auditor computes **22:34** and **22:44** for the same two obligations. Both derive
the cutoff from the tip (`coverage_audit.py:200`), so the tip moved between the two evaluations.

`tip_drift_probe.py` (this directory) reads every `data/odds_capture/live_*.json` in capture order:

| capture | matchup | commence_time | implied T-30m cutoff |
|---|---|---|---|
| 2026-08-02T00:00:03Z | NYL v SEA | 2026-08-03T23:00:00Z | 22:30:00Z |
| 2026-08-02T00:00:03Z | ATL v LVA | 2026-08-03T23:30:00Z | 23:00:00Z |
| 2026-08-03T23:00:02Z | ATL v LVA | 2026-08-03T23:00:00Z | 22:30:00Z |
| 2026-08-03T23:00:02Z | NYL v SEA | 2026-08-03T23:05:00Z | 22:35:00Z |
| 2026-08-04T00:00:02Z | NYL v SEA | 2026-08-03T23:04:00Z | 22:34:00Z |
| 2026-08-04T00:00:02Z | ATL v LVA | 2026-08-03T23:14:00Z | 22:44:00Z |

At 22:45:08Z the newest capture in existence was the 2026-08-02T00:00:03Z one. Judged against what
was knowable then:

| record | as-of cutoff (known at write) | as-of latency | latest cutoff | latest latency |
|---|---|---|---|---|
| idx 19 NYL v SEA | 22:30:00Z | **+15.15 min (late)** | 22:34:00Z | +11.15 min (late) |
| idx 20 ATL v LVA | 23:00:00Z | **-14.85 min (early)** | 22:44:00Z | +1.15 min (late) |

**Record 20 was on time by about 15 minutes when it was written.** Its `late_record` classification
is produced entirely by a -16 minute tip revision that arrived after the write. The ATL v LVA tip
moved 23:30 -> 23:00 -> 23:14; `TIP_MOVE_TOLERANCE` is 30 minutes (`coverage_audit.py:75`), so none
of this is flagged as a tip move either.

## 5. The fix — designed and tested in isolation

Implemented in this directory only, wired into nothing: `late_write_guard.py`, tested by `TESTS.py`.
Two independent rules, because sections 3 and 4 are independent defects.

**G1 — `refuse_late(created, cutoff)`, a WRITE-SITE guard.** Refuse to append a base record whose
creation instant is at or after its own cutoff. Correct regardless of which process is writing and
what schedule invoked it, which is precisely the property a discovery-gate amendment lacks. It is
the rule `alt_model_log.py:21-24` already enforces on the challenger chain, applied to the official
one. The boundary is closed against the write (a record created exactly on the cutoff instant has
already seen the cutoff instant).

**G2 — `asof_cutoff(tip_history, label, at)`, an AUDIT rule.** Judge lateness against the cutoff
implied by the newest tip captured at or before the write, not the latest tip ever seen. Where no
capture predates the write, return `None` — an unknowable cutoff must be reported, not silently
replaced by the latest tip. `classify_write()` returns both clocks plus a
`retroactively_relabelled` flag, so the two populations are never merged.

`TESTS.py` — standalone, no pytest, `main()` returns 1 on failure, per repo convention:

```
python TESTS.py C:/Users/jgallagher/wnba-betting-model
```

**26 checks, 26 pass, exit 0.** Five synthetic groups (cutoff arithmetic for all four registered
labels; G1 boundary behaviour including the exact-boundary and naive-datetime cases; G2 as-of
selection including the no-prior-capture null; the retroactive-relabel separation; and a
schedule-independence sweep showing G1 refuses 7 and allows 18 of 25 synthetic cutoffs against a
fixed 22:45:01Z firing), plus a replay against the live chain that confirms on the real bytes:
idx 19 late on both clocks and **refused** by G1; idx 20 late on the latest clock only, flagged
`retroactively_relabelled`, and **allowed** by G1.

**Not fixable from inside this node, proposed only:**

1. `daily_forecast.py` must not be able to append a late base record — G1 belongs at its write
   site (or in a wrapper the scheduled tasks call instead of it). That file is a shared operational
   artifact owned by another thread.
2. The two fixed-wall-clock scheduled tasks `WNBA_DailyForecast_AM` / `WNBA_DailyForecast_PM` must
   be retired or subordinated to the gate. A fixed 10:20/18:45 ET firing has no relationship to a
   cutoff that moves with the tip. **Changing a scheduled task is a system-configuration change and
   was not made.**
3. G2 changes `coverage_audit.py`'s classification contract. **Proposed, not merged.**

## 6. Numeric consequence for a published figure — flagged, not resolved

The published receipt (`PROJECT_UPDATE_2026-08-04.md:539-556`) carries `operational misses` as
**26 published / 27 corrected**, the correction being D-a: 2026-08-03 CHI v PHX T-30m is
reclassified because "its only health evidence was two `late_record`s" (`:558`, `:199`). I verified
in memory that those two are exactly records 19 and 20: the auditor's reason string for CHI v PHX
T-30m is `job served 2 other game(s) on 2026-08-03 at T-30m`, and `served_at` is built from all
official records without regard to lateness (`coverage_audit.py:186-194`).

If G2 is adopted, record 20 is **not** late, one timely companion survives, and CHI v PHX T-30m
stays `missing_data_unavailable` — i.e. **operational misses would remain 26, not 27.** D-a and
D-d interact; the corrected figure depends on which of the two lateness clocks the auditor uses.

I did **not** recompute the full receipt under G2 — that would require patching `coverage_audit.py`,
which is outside this node's write scope. This is stated as a conditional implication of the
classification rule at `coverage_audit.py:186-194` and `:228`, for the owner of D-a to settle.

## 7. Contradictions found

1. **Document vs bytes — mechanism.** `PROJECT_UPDATE_2026-08-04.md:202` and `:572` say "discovery
   worked, execution was late". `pair_20260803.log:863` shows discovery ran at 22:45:06.515Z and
   returned `fire=False`; `schtasks` shows the writer was a task that never calls discovery.
2. **Document vs bytes — remediation target.** `PROJECT_UPDATE_2026-08-04.md:611` assigns D-d to
   `should_run_base.py`. The producing process does not import, invoke or depend on that file.
3. **Document vs bytes — one of the two records.** The 22:44 cutoff cited at `:202` did not exist
   when the record was written; the cutoff known then was 23:00, and the record was 14.85 minutes
   early.
4. **Code vs code.** The challenger chain refuses late writes (`alt_model_log.py:21-24`,
   `run_prospective.py:177-183`); the official chain, which is the one graded, has no such rule.
5. **Design comment vs deployment.** `run_pair.cmd` states the base step is gated so "each (game,
   decision time) is written at most once"; two additional ungated tasks write the same chain, so
   that guarantee does not hold at the chain level.

## 8. What I could NOT establish

- **Whether `daily_forecast.py` itself contains any cutoff check.** It sits at the live repository
  root, outside this node's declared read scope; I bounded the question from the outside (a late
  record exists in the chain, therefore nothing refused it) rather than reading it. The fix in
  section 5 is written as an external guard for exactly that reason.
- **Why the two extra scheduled tasks exist.** No document I read registers, justifies or even
  mentions `WNBA_DailyForecast_AM` / `WNBA_DailyForecast_PM`. They are absent from the D-d
  narrative, from the amendment map at `:605-612`, and from `prospective_pair/task_definition.xml`,
  which registers only the 15-minute paired task. Whether they predate the gate or were added
  deliberately is not recoverable from the repository.
- **The true tip for either game.** I have the odds-capture history only; there is no independent
  schedule source in what I read, so "the tip moved" is established, but which value was ever
  correct is not.
- **Whether the AM task has produced late records.** Record 22 (2026-08-04T14:20:03Z, T-8h,
  cutoff 18:00Z) is 219.94 minutes early, so the AM task has not produced a late record *yet*; a
  T-30m obligation falling near 10:20 ET would put it in the same position. Not measurable from the
  four days of chain that exist.
- **Any effect of the two duplicate-record pairs (idx 13-15 vs 16-18)** on anything beyond the
  auditor's `duplicate_records_excluded = 4`. Not in scope for D-d.

## 9. Stop conditions

**None tripped.** No finding here touches the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set or the leakage status. The
artifacts involved (`forecasts/forecast_log.jsonl`, the odds captures, the runner logs) are the
prospective operational chain; the historical feature evidence used by the possession lane is built
from the master gamelogs and is untouched by anything in this report. **No escalation to the
possession lane is warranted.** Section 6 is an escalation to the operations/audit owner, not to
research.

**No shared schema or contract change was merged from this node.** Both proposals (G1 at the
`daily_forecast.py` write site; G2 in `coverage_audit.py`) are stated and tested here and left
unapplied, along with the scheduler change, for the shared-adoption decision.

---

## Files in this directory

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `FINDINGS.json` | machine-readable findings |
| `repro_d_d.py` | reproduction probe; read-only, never calls `coverage_audit.main()` |
| `tip_drift_probe.py` | tip-revision probe over `data/odds_capture/live_*.json`; read-only |
| `late_write_guard.py` | proposed fix (G1 + G2), wired into nothing |
| `TESTS.py` | 26 checks; `main()` returns 1 on failure; 26/26 pass |
