# O11_OBLIGATION_DISCOVERY_LEAD_WINDOW — obligation-discovery lead window defect

**Epistemic status (verbatim from the node contract):**

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch
> only. This lane does not block possession research unless it changes the historical feature
> evidence.

**Verdict: the defect is DOCUMENTED, and it REPRODUCES.** Root cause identified, measured, and
fixed in an isolated implementation inside this directory. Nothing outside
`experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/` was written. No git
command other than `git rev-parse --abbrev-ref HEAD` was run.

---

## 1. It is documented, and where

`experiments/player_program/PROJECT_UPDATE_2026-08-04.md:200`, defect **D-b**, one of four faults
the capture defect decomposes into (`:189-191`):

> **Obligation discovery / lead window.** 2026-08-04 TOR@GSV T-24h, cutoff 02:00:00Z: the gate
> declined at 01:30, 01:45 and 02:00 with *"no unserved obligation inside its 20-minute lead
> window"* — yet at 01:45 the cutoff was 14.9 minutes away, inside the window. **Per-game scope
> does not fix this, and it fails silently.** | **A** for coverage integrity | independent fix in
> `should_run_base.py`

The node's title is taken verbatim from that row: `orchestration/scripts/seed_graph.py:694`.
`PROJECT_UPDATE_2026-08-04.md:573` bounds it historically — 25 of the 26 job-did-not-run misses
predate a functioning scheduler, so D-b is not their cause.

### A scope contradiction that must be recorded

The node's declared read scope is `experiments/player_program/`. **The artifact under audit is not
in it.** `should_run_base.py`, `coverage_audit.py`, `daily_forecast.py`, the odds captures, the
assignments log and the runner logs exist **only in the repository-root worktree**
(`C:/Users/jgallagher/wnba-betting-model`, branch `data-refresh-2026`). Measured: the
player-model-program worktree has **0** `data/odds_capture/live_*.json` files, no `prospective_pair/`,
no `forecasts/runner_logs/`, and a 70-row `assignments_log.csv` against the root's 109-row copy.
Every read outside the declared scope was read-only.

---

## 2. It reproduces

### 2.1 The primary evidence is the gate's own log

`forecasts/runner_logs/pair_20260803.log:1996, 2093, 2190` — the three declines D-b names:

```
[gate] 2026-08-04T01:30:05.128408+00:00  fire=False  -- no unserved obligation inside its 20-minute lead window
[gate] 2026-08-04T01:45:04.560181+00:00  fire=False  -- no unserved obligation inside its 20-minute lead window
[gate] 2026-08-04T02:00:05.384686+00:00  fire=False  -- no unserved obligation inside its 20-minute lead window
```

At each of the three, the line immediately following is `[gate] skipping the base job`. The gate's
`main()` prints one line per game in `upcoming` (`should_run_base.py:113-118`). **No line was
printed for GSV v TOR at any of the three firings.** The game was never enumerated. Contrast
`forecasts/runner_logs/pair_20260804.log:3922-3923`, after the official id existed:

```
[gate] 2026-08-04T14:00:04.934899+00:00  fire=False  -- no unserved obligation inside its 20-minute lead window
       GSV v TOR      T-8h    unserved cutoff 2026-08-04T18:00:00 (+240 min)
```

### 2.2 Reproduced in isolation

`gate_logic.classify_original` transcribes the decision structure of
`should_run_base.py:78-102`. `TESTS.py` section 2, on the measured fixture (tip
`2026-08-05T02:00:00Z`, no `game_id`), returns at all three instants: `fire=False`, reason
`"no unserved obligation inside its 20-minute lead window"`, and `upcoming == new ==
would_duplicate == []`. Section 1 confirms the obligation itself: label `T-24h`, cutoff
`2026-08-04T02:00:00`, `minutes_to_cutoff == 14.9` at 01:45 — **the exact figure PROJECT_UPDATE
quotes**, recovered independently from the tip time and the logged firing timestamp.

Section 3 isolates the cause. Same three instants, same code, **only** the `game_id` supplied:
01:45 and 02:00 both fire; 01:30 correctly holds (29.9 minutes out).
**The cause is identity, not timing.**

---

## 3. Root cause

`prospective_pair/should_run_base.py:80-82`:

```python
gid = str(g.game_id) if pd.notna(g.game_id) else None
if gid is None or g.tip <= now:
    continue                      # already tipped: cannot be forecast now
```

`game_id` reaches the slate from exactly two places: the ref-assignments log
(`coverage_audit.py:116-124`) and **completed** games in `master_team.parquet`
(`coverage_audit.py:128-142`). The second cannot apply to a game that has not been played, so for
a prospective obligation the referee assignment is the sole source of identity — and referee
assignments are published on the morning of the game.

**The gate is stricter than the job it guards.** `daily_forecast.py:561-563` already mints
`PROV-{slate_date}-{away}@{home}` and sets `game_id_provisional` when the ref id is missing, and
`coverage_audit.py:148-168` resolves those provisional ids back to real ids retroactively. Every
component of the prospective path tolerates a missing official id **except** the gate.

**Why it is silent.** A dropped row never enters `upcoming`, so nothing prints. Control then falls
to `should_run_base.py:97-98`, whose message names the lead window. The lead window did not cause
the decline. The module docstring (`should_run_base.py:16-17`) claims the gate fires "only if at
least one (game, registered cutoff) obligation is BOTH unserved AND inside its lead window" — a
claim about obligations it never enumerated.

---

## 4. What was measured

`python measure_discovery_lag.py --repo C:/Users/jgallagher/wnba-betting-model --json DISCOVERY_LAG.json --csv DISCOVERY_LAG.csv`
over 68 odds captures and 108 assignments rows, as of the `20260804T190005Z` capture.
Per game it compares each registered cutoff against the earliest instant the gate could have seen
an official id.

| label | obligations | discoverable before cutoff | median id lead (min) | median odds lead (min) |
|---|---|---|---|---|
| T-24h | 21 | **0** | **-971.2** | +660.0 |
| T-8h  | 21 | 8  | -11.2  | +1620.0 |
| T-90m | 21 | 13 | +378.8 | +2010.0 |
| T-30m | 21 | 14 | +438.8 | +2070.0 |

**Not one T-24h obligation in the entire captured period was discoverable before its cutoff.** The
failure is total, not sporadic. T-8h sits on the boundary (median lead -11 minutes), so it fails
about half the time by coincidence of publication hour.

The named case, `DISCOVERY_LAG.csv` rows 60-63:

| quantity | value |
|---|---|
| tip | `2026-08-05T02:00:00Z` |
| T-24h cutoff | `2026-08-04T02:00:00Z` |
| first odds capture showing the game | `2026-08-03T03:00:02Z` — **1,380 min (23.0 h) of lead** |
| first assignments row with a game_id | `2026-08-04T14:00:02Z` — **720 min AFTER the cutoff** |

The obligation was knowable a full day early. The gate could not see it because it demanded a
different fact, which arrived twelve hours late.

### Blast radius, measured and bounded

From `forecasts/coverage_audit.csv` (frozen auditor, read only): 26 `missing_job_did_not_run`, of
which **10 are T-24h**. But the gate has existed only since `2026-08-03T21:45:03Z` (earliest
`[gate]` line across both runner logs; 89 firings total), so **exactly one** miss has a cutoff
after the gate existed and is attributable to D-b: 2026-08-04 GSV v TOR T-24h. This is consistent
with `PROJECT_UPDATE_2026-08-04.md:573`. **D-b's damage is prospective, not historical.**

Prospectively it is live right now: the 2026-08-05 and 2026-08-06 slates carry **5 games with no
game_id anywhere in the assignments log** (ATL v PHX, CHI v LAS, NYL v SEA, WAS v DAL, IND v LVA).
Their T-24h obligations are all classified `not_yet_due`. Under the unfixed gate every one becomes
an operational miss when its cutoff passes, logged again as a lead-window decline. The promotion
threshold is `MAX_OPERATIONAL_MISSES = 0` (`coverage_audit.py:52`).

---

## 5. The fix — designed and tested here, applied nowhere

Implemented as `gate_logic.classify_fixed`; the corresponding edit to the live file is recorded,
**unapplied**, as `PROPOSED_PATCH.diff`.

1. **Do not drop a row without an official id.** Identify it with the same
   `PROV-<slate_date>-<away>@<home>` the job already mints (`daily_forecast.py:562`). `TESTS.py`
   section 7 verifies the string round-trips through the parser at `coverage_audit.py:161-165` and
   is stable across firings, so retroactive resolution to the real id still works.
2. **Never decline silently.** The reason string now carries the number of games examined and
   names every unresolved game.
3. **Change nothing else.** `current_label` is left alone deliberately — it mirrors the label
   `daily_forecast.py` will actually assign, and decoupling them would create a worse defect. The
   `fire = bool(in_window) and not dup` conjunction is left alone deliberately: that is **D-c**,
   node `O12_PER_GAME_EXECUTION_SCOPE`.

`python TESTS.py` gives **45 checks, 0 failures** (`TESTS_OUTPUT.txt`). Key results:

- section 4 — at 01:45 the fixed gate fires, with exactly one obligation in window: T-24h at 14.9
  minutes, flagged provisional.
- section 5 — at 01:30 it still declines, and the reason is now *true*: 1 game examined, 1
  unresolved id named.
- section 6 — once served under the provisional id, 02:00 classifies as `would_duplicate`. **The
  append-only chain is still protected**; the fix does not trade a miss for a duplicate.
- section 8 — on a slate where every game has a real id, fixed and original agree on `fire` and on
  `in_window` at all three instants. No regression.

`TESTS.py` section 9 re-runs the live measurement and skips cleanly when the capture data is
absent, so the node's tests do not depend on a worktree it does not own.

---

## 6. What I could NOT establish

- **That the base job actually produces a good forecast once the gate lets it through on a
  provisional id.** The job's slate builder mints the id (`daily_forecast.py:561-563`), so it is
  designed to, but I did not execute it. Doing so appends to an append-only official chain, which
  this node must not do. **The fix is verified at the gate boundary only.**
- **The tip time in force at each firing.** `build_slate` keeps the *latest* observed
  `commence_time` (`coverage_audit.py:104-106`). The measured tip carries `tip_moved=False`, so no
  shift of 30 minutes or more is recorded, but I did not rebuild the slate as-of each capture.
- **Whether the 20-minute `LEAD` is itself adequate.** That is D-d / `O13_LEAD_WINDOW_LATENCY`.
  Not evaluated.
- **Whether ref assignments are *always* published after T-24h or merely were in this window.** I
  measured 21 games over six days; I did not establish a publication-time policy.

## 7. Contradictions found

1. **Code contradicts its own message.** The decline reason at `should_run_base.py:97-98` names a
   cause that the measurement refutes.
2. **Auditor and gate disagree on what an obligation is.** `coverage_audit.audit()`
   (`:197-198`) keeps slate rows whose `game_id` is null and charges misses for them; the gate
   drops those same rows. The program is therefore graded on obligations its gate is structurally
   unable to serve. Recorded, **not fixed** — the classification question belongs to
   `O10_LATE_RECORD_AUDIT_CLASSIFICATION`.
3. **PROJECT_UPDATE's "per-game scope does not fix this" is confirmed.** The duplicate branch takes
   precedence in the reason string; the logged reason was the lead-window one, so the `not dup`
   conjunction was never reached at these firings.

## 8. Stop conditions

**None tripped.** No finding touches the primary target, the K0 structure, the inference structure,
the candidate universe, the cutoff-valid feature set or the leakage status. This is a
forward-capture scheduling defect; it does not alter historical feature evidence, so **nothing is
escalated to the possession lane**.

**No shared schema or contract change is merged from this node.** `should_run_base.py` is
untouched; the intended edit is proposed in `PROPOSED_PATCH.diff` and left to
`O16_SHARED_SCHEMA_ADOPTION` / the user.

---

## 9. Files in this directory

| file | what it is |
|---|---|
| `REPORT.md` | this document |
| `FINDINGS.json` | machine-readable findings (passes the node's validation command) |
| `measure_discovery_lag.py` | read-only measurement of discovery lag vs. every cutoff |
| `DISCOVERY_LAG.csv` / `DISCOVERY_LAG.json` | its output: 84 obligations, 21 games |
| `gate_logic.py` | `classify_original` (reproduction) and `classify_fixed` (candidate) |
| `TESTS.py` / `TESTS_OUTPUT.txt` | 45 checks, 0 failures; `main()` returns 1 on failure |
| `PROPOSED_PATCH.diff` | the unapplied edit to `prospective_pair/should_run_base.py` |
