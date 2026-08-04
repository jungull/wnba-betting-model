# O15_LOGOUT_SURVIVAL — Logout survival for the capture scheduler

**This document is a REMEDIATION, not the original run.**

| | |
|---|---|
| Written by | `R10_O15_REPORT_REMEDIATION` (lane: operations, type: documentation, severity on failure: C) |
| Subject node | `O15_LOGOUT_SURVIVAL` (lane: operations, type: audit, severity on failure: C) |
| Subject node status | **FAILED** — `validation_failed`, 2026-08-04T20:31:54Z |
| Derived exclusively from | `experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/` |
| New measurement performed | **none** |
| Anything under `ops_lane/O15_LOGOUT_SURVIVAL/` modified | **no** |

---

## 1. Why this document exists

`O15_LOGOUT_SURVIVAL` declared two required outputs in its contract:

* `experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/REPORT.md`
* `experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/FINDINGS.json`

It wrote the second and **did not write the first**. The coordinator recorded this in
`orchestration/GRAPH_EVENTS.jsonl`:

> `"event": "validation_failed"`, `"node": "O15_LOGOUT_SURVIVAL"`, ts `2026-08-04T20:31:54Z` —
> "declared output REPORT.md is MISSING. The independent verifier scored PASS_WITH_DEFECTS and did
> not catch this; the mechanical expected-output check did. Severity C: documented and scheduled,
> does not halt unrelated work. Substantive artifacts (FINDINGS.json, TESTS.py, measurement
> scripts, evidence) were produced and are preserved."

The original node gave its own account of the same absence, in
`FINDINGS.json` -> `required_output_not_written`:

> "The harness running this node blocked the Write call with 'Subagents should return findings as
> text, not write report files.' The full report content was returned in the node's final message
> instead. This is a harness constraint, not an omission of the work; the coordinator should paste
> the returned text into REPORT.md to satisfy the contract's required-outputs list."

Both accounts are preserved here and **neither is adjudicated by this node**. The returned text the
parent refers to is not present in the repository, so it could not be pasted; this report is
reconstructed from the preserved artifacts instead. It is therefore **not** the parent's prose and
should not be cited as though it were.

The absence left three dangling references inside the parent's own preserved code, each pointing at
a file that was never written:

| File | Line | Text |
|---|---|---|
| `logon_survival_fix.py` | 49 | "See REPORT.md." |
| `apply_logon_survival.ps1` | 10 | "See REPORT.md." |
| `measure_logon_survival.ps1` | 7 | "Regenerates every number quoted in REPORT.md" |

Writing this file resolves those references only in the sense that a document now exists at the
remediation path. The parent's `REPORT.md` path remains empty, because this node may not write
inside `ops_lane/O15_LOGOUT_SURVIVAL/`.

The parent `validation_failed` event is preserved and not rewritten.

---

## 2. Epistemic status

### 2.1 Epistemic status of the original node, carried verbatim

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch only. This lane does not block possession research unless it changes the historical feature evidence.

### 2.2 Epistemic status of this remediation, verbatim

> REMEDIATION of a confirmed missing declared output. It writes up evidence that ALREADY EXISTS in ops_lane/O15_LOGOUT_SURVIVAL/ and may not add a finding the original run did not make. Its parent finding is O15_LOGOUT_SURVIVAL's validation_failed event, which is preserved and not rewritten.

Both lines bound what this document may be cited for. Section 2.1 bounds the *findings*; section 2.2
bounds the *document*.

---

## 3. Derivation basis

Every statement below is traceable to one of these preserved files, all of which were read
read-only:

```
experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/
  FINDINGS.json                        17,617 B
  EVIDENCE_measured.json                8,164 B
  EVIDENCE_capture_gap.json             1,735 B
  TESTS.py                              9,740 B
  logon_survival_fix.py                 7,167 B
  apply_logon_survival.ps1              9,410 B
  measure_logon_survival.ps1            5,599 B
  evidence_task_WNBA_OddsCapture.xml    1,879 B
```

Plus, for the remediation framing only (sections 1 and 9): `orchestration/GRAPH_EVENTS.jsonl`,
`orchestration/GRAPH_STATE.json`, `orchestration/DECISION_LEDGER.jsonl`, and the two generated
contract prompts `orchestration/prompts/O15_LOGOUT_SURVIVAL.md` and
`orchestration/prompts/R10_O15_REPORT_REMEDIATION.md`.

**No script was executed by this node.** `TESTS.py` was not re-run; `measure_logon_survival.ps1`
was not re-run; `corroborate_capture_gap.py` was not re-run. Every number below is the number the
original run recorded, reported as its number and not as a fresh observation.

---

## 4. Documentation status — DOCUMENTED

The defect is defect **D-f** in `PROJECT_UPDATE_2026-08-04.md`. The original run recorded these
citations:

| Path | Line | Quote |
|---|---|---|
| `experiments/player_program/PROJECT_UPDATE_2026-08-04.md` | 204 | "D-f \| Logout survival. The Interactive-mode task does not run when logged out. \| C \| reliability improvement, not the primary historical cause - 25 of 26 job-did-not-run misses predate a functioning scheduler entirely" |
| `PROJECT_UPDATE_2026-08-04.md` | 573 | "Logout survival (D-f) is a reliability improvement, not the primary historical cause" |
| `PROJECT_UPDATE_2026-08-04.md` | 591 | "Batch-logon entered in PL-006 as logout survival - a reliability improvement - and was never a registered validity condition." |
| `PROJECT_UPDATE_2026-08-04.md` | 267 | "(5) Batch-logon with IT - reliability, demoted." |
| `PROJECT_UPDATE_2026-08-04.md` | 596 | "D-b / D-c / D-f mean served obligations are not a random subset" |
| `project_docs/FREEZE_PROPOSAL_v0.md` | 65 | "Create WNBA_DailyForecast_AM (10:00) and _PM (18:30) scheduled tasks" — names no principal or logon mode |
| `project_docs/FREEZE_PROPOSAL_v0.md` | 58 | "Missed days are missed - never backfilled into the chain." |
| `setup_scripts/verify_scheduled_tasks.ps1` | 108 | `$swa  = [bool]$task.Settings.StartWhenAvailable` — the only standing audit reads StartWhenAvailable and never reads `Principal.LogonType` |
| `setup_scripts/verify_scheduled_tasks.ps1` | 25 | "Task state is not in the repo and cannot be checked from anywhere else." |
| `START_HERE.md` | 50 | "Six scheduled tasks on this machine" |

### Documentation gaps the original run recorded

1. **No script in the repository registers the scheduled tasks.** A grep over `*.ps1 *.bat *.py *.md`
   for `Register-ScheduledTask|New-ScheduledTask|schtasks` returned only auditing, documentation and
   deletion references. The 13 live task definitions exist only on the machine.
2. **Nothing in the repository ever reads `Principal.LogonType`.** A repo-wide grep for
   `LogonType|Principal|RunLevel|batch logon` returned zero hits in any script. The one automated
   task audit is structurally blind to D-f.
3. **D-f is documented as a fact but nowhere quantified.** No document states how many launches it
   suppressed, on which days, or with what artifact consequence.

---

## 5. Reproduction — REPRODUCED

The contract's first acceptance criterion was "the defect is reproduced or shown not to reproduce,
with evidence." The original run reproduced it from two independent machine authorities and then
corroborated the consequence from the artifact record.

### 5.1 Authority 1 — the live task definitions

Command the original run recorded:

```
powershell -ExecutionPolicy Bypass -File experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/measure_logon_survival.ps1
  -> experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/EVIDENCE_measured.json
```

Source of the numbers: `Get-ScheduledTask` filtered to `WNBA*`.

| Quantity | Value |
|---|---|
| WNBA tasks registered | **13** |
| ...with `LogonType` = Interactive | **13** (all of them) |
| `StartWhenAvailable` | `true` on all 13 |
| `RunLevel` | `Limited` on all 13 |
| `UserId` | `jgallagher` on all 13 |
| `State` | `Ready` on all 13 |
| `LastTaskResult` | `0` on all 13 |
| XML spelling of the defect | `InteractiveToken` |

The 13 tasks (`EVIDENCE_measured.json` -> `principals`): `WNBA prospective pair`,
`WNBA_DailyForecast_AM`, `WNBA_DailyForecast_PM`, `WNBA_DailyRefresh`, `WNBA_InjuryCapture`,
`WNBA_NewsCapture`, `WNBA_OddsCapture`, `WNBA_PropsCapture_1` ... `_4`, `WNBA_RefAssignments`,
`WNBA_ReplyDeliveryWatchdog`.

The XML spelling is evidenced by one real exported definition preserved in the node directory,
`evidence_task_WNBA_OddsCapture.xml`, which carries `<LogonType>InteractiveToken</LogonType>` and
`<StartWhenAvailable>true</StartWhenAvailable>`.

### 5.2 Authority 2 — the Task Scheduler operational log

Same script, same output file. Source: `Microsoft-Windows-TaskScheduler/Operational`, **event id 332**
— "Task Scheduler did not launch task X because user Y was not logged on when the launching
conditions were met." That event *is* the defect firing.

Verbatim example the original run captured:

> Task Scheduler did not launch task "\WNBA_OddsCapture"  because user "(NONE)" was not logged on
> when the launching conditions were met. User Action: Ensure user is logged on or change the task
> definition to allow launching when user is logged off.
>
> — local time `2026-08-02T16:00:01.6488732-04:00`

| Quantity | Value |
|---|---|
| id-332 events, all tasks | **118** |
| id-332 events, WNBA tasks | **23** |
| Affected days | **2026-08-02 only** |
| Window (local) | `2026-08-02T08:00:02-04:00` ... `2026-08-02T16:00:01-04:00` |
| Log record count | 17,021 |
| Log max size | 10,485,760 B (rolling 10 MB) |
| Oldest retained record (local) | `2026-07-30T21:32:55-04:00` |

Per-task breakdown of the 23 suppressed WNBA launches:

| Task | Suppressed launches |
|---|---|
| `WNBA_OddsCapture` | 7 |
| `WNBA_InjuryCapture` | 7 |
| `WNBA_NewsCapture` | 4 |
| `WNBA_DailyForecast_AM` | 1 |
| `WNBA_DailyRefresh` | 1 |
| `WNBA_RefAssignments` | 1 |
| `WNBA_PropsCapture_1` | 1 |
| `WNBA_PropsCapture_2` | 1 |
| **Total** | **23** |

### 5.3 `StartWhenAvailable` did not recover any suppressed launch

This matters because `StartWhenAvailable=true` is the mitigation
`setup_scripts/verify_scheduled_tasks.ps1` exists to protect, and it is the property a reader would
assume rescued the missed runs. It did not.

**Claim as recorded:** "StartWhenAvailable=True retried none of the suppressed launches."

**Evidence as recorded:** every id-100 start for `WNBA_InjuryCapture` on 2026-08-02 sits on the
trigger's own `:00:01` cadence — 17:00:01, 18:00:01, 19:00:01, 20:00:01, 21:00:01, 22:00:01,
23:00:01 local. A catch-up run fires at an arbitrary instant, whenever the machine became available,
and would land off-cadence. There is no off-cadence start.

Asserted by `TESTS.py` test group **[6]**, which reduces each recorded start to its `mm:ss` component
and asserts the set has exactly one member.

### 5.4 Artifact corroboration — the hole is in the outputs too

The scheduler log is one witness. The original run checked whether the capture outputs carry a hole
in exactly the same window, from the artifacts rather than from the log.

```
python experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/corroborate_capture_gap.py
  -> experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/EVIDENCE_capture_gap.json
```

**Read scope, stated plainly because it crosses a boundary:** this script performed a READ-ONLY read
of the live capture tree at the repository root `C:\Users\jgallagher\wnba-betting-model` — a
different worktree on a different branch. Nothing was written there. It was necessary because this
program worktree's `data/` stops on 2026-08-01 and therefore cannot see the window at issue.

Injury-PDF series (`data/injury_capture/raw/wnba_official_*.pdf`):

| Quantity | Value |
|---|---|
| PDFs in series | 71 |
| Series span (UTC) | `2026-07-30T15:49:50Z` ... `2026-08-04T20:00:08Z` |
| Largest gap | **18.0 h** — `2026-08-01T23:00:05` ... `2026-08-02T17:00:04` local |
| Next four gaps | 11.914 h, 11.0 h, 11.0 h, 10.102 h — all the ordinary 23:00-10:00 overnight window |
| 2026-08-02 local hours present | 17, 18, 19, 20, 21, 22, 23 |
| 2026-08-02 local hours missing | 10, 11, 12, 13, 14, 15, 16 |
| Missing hourly slots | **7** |

The 18-hour gap is the only anomaly in the series; every other large gap is the scheduled overnight
window. **7 missing hourly injury slots == 7 `WNBA_InjuryCapture` id-332 events, hour for hour.**

Prospective forecast chain (`forecasts/forecast_log.jsonl`):

| Cutoff date (UTC) | Records |
|---|---|
| 2026-07-31 | 6 |
| 2026-08-01 | 4 |
| **2026-08-02** | **0** |
| 2026-08-03 | 12 |
| 2026-08-04 | 1 |
| Total | 23 |

2026-08-02 is the only zero-record day in the prospective chain. The AM half is directly attributable
— id-332 on `WNBA_DailyForecast_AM` at `2026-08-02T10:20:01` local. Per
`project_docs/FREEZE_PROPOSAL_v0.md:58` ("Missed days are missed - never backfilled into the chain")
it is permanently missing.

---

## 6. The fix — designed and unit-tested, NOT applied

| Property | Value |
|---|---|
| Designed | yes |
| Tested | yes |
| Applied to the machine | **no** |
| Change | Principal `LogonType`: `InteractiveToken` -> `S4U` |

### 6.1 Why it was not applied

Recorded verbatim in `FINDINGS.json`: "Changing scheduled-task principals is a machine configuration
change and belongs to the operator, not to an analyst node. Additionally this session is not elevated
(SZ\jgallagher, IsInRole(Administrator)=False) and S4U registration requires elevation."

### 6.2 The shape of the change, and why that shape

The remediation is a **minimal rewrite of exactly one XML element**. Everything else — triggers,
actions, settings, `UserId`, `RunLevel` and above all `StartWhenAvailable` — is required to survive
byte-identical.

The reason is a trap the repository already documented the hard way.
`setup_scripts/verify_scheduled_tasks.ps1:129-135` records that rebuilding a settings object with
`New-ScheduledTaskSettingsSet` silently resets every other setting to its default. The identical trap
exists for `New-ScheduledTaskPrincipal`. A careless logon-mode change could therefore destroy the
`StartWhenAvailable` mitigation while fixing D-f — trading one silent-loss defect for another.

`logon_survival_fix.py` implements the change as a pure function over task XML, not as PowerShell
object surgery, precisely so that invariant is statable and testable. It refuses rather than guesses:
a target that does not survive logoff, a definition with no `<LogonType>`, more than one
`<Principals>` block, or more than one `<LogonType>` all raise `RemediationError`. An **absent**
`<LogonType>` is treated as defective, not benign, because Task Scheduler then defaults the principal
to `InteractiveToken` — defective in exactly the same way while looking clean to a naive grep.

### 6.3 Why S4U rather than Password

| Route | Assessment as recorded |
|---|---|
| **S4U** (chosen) | Cost: the process receives no outbound network credentials. That cost does not bind here — `odds_capture_daily.py:42`, `props_capture_daily.py:55,70`, `injury_capture_daily.py`, `news_capture_daily.py` and `ref_assignments_capture_daily.py` all use plain `requests`/`urllib` against public endpoints and write to local disk; none drives a browser (no selenium/playwright/pyautogui anywhere in the capture family — only a Chrome User-Agent string at `injury_capture_daily.py:63` and `ref_assignments_capture_daily.py:71`); none reads a UNC path; the API key comes from a local `.env` (`odds_capture_daily.py:32`), not a credential store. |
| **Password** | The "batch-logon with IT" route at `PROJECT_UPDATE_2026-08-04.md:267`. Available as an explicit mode but deliberately not applied from a repo file, so no secret passes through one. `apply_logon_survival.ps1` refuses `-Apply -Mode Password` outright and directs the operator to `taskschd.msc` or an interactive `Register-ScheduledTask -Password`. |

### 6.4 One task deliberately excluded

`WNBA_ReplyDeliveryWatchdog` is **skipped**. Its action script lives under
`C:\Users\jgallagher\OneDrive - Sasserath Co\...`. Under S4U there is no interactive OneDrive client
to hydrate a cloud-only placeholder, so conversion could turn a logout failure into a file-not-found
failure. It needs its own decision.

### 6.5 Tests

```
python experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/TESTS.py
```

Convention: standalone runnable script, `main()` returns 1 on failure (pytest is not installed).

| Result | Value |
|---|---|
| Exit code | **0** |
| Assertions passed | **37** |
| Assertions failed | **0** |
| Skipped | **0** |

Groups:

1. Logon-mode classification, including that an **absent** `<LogonType>` must count as non-surviving
   because Task Scheduler defaults it to `InteractiveToken`.
2. The rewrite changes exactly one line and preserves `StartWhenAvailable`, `UserId`, `RunLevel`,
   repetition interval, `MultipleInstancesPolicy` and action arguments.
3. Idempotence (second application byte-identical) and refusal to guess — rejects a non-surviving
   target, a definition with no `<LogonType>`, a definition with two `<Principals>` blocks.
4. The Password alternative is also a single-line rewrite.
5. The rewrite against this machine's **real** exported `WNBA_OddsCapture` definition — every
   non-`LogonType` line byte-identical; the real definition's
   `<StartWhenAvailable>true</StartWhenAvailable>` confirmed present **so the assertion is not
   vacuous**.
6. The classifier reproduces the PowerShell count (13) and the no-catch-up property.

### 6.6 Dry run

```
powershell -File apply_logon_survival.ps1        (no -Apply)
```

| Result | Value |
|---|---|
| Exit code | **1** — correct for a read-only run; exit 1 means "at least one task still does not survive logoff" |
| Tasks listed Interactive | 13 |
| Tasks planned for conversion | 12 |
| Skipped | `WNBA_ReplyDeliveryWatchdog` |

### 6.7 Verification limit — the honest bound on this fix

Recorded verbatim: "Reading back LogonType=S4U proves the DEFINITION changed. It does not prove a
launch succeeds with no session present. The only confirming observation is an actual logged-out
firing: log out across a trigger boundary, log back in, and check for a new id-100 start at the
trigger instant AND no new id-332. Until then the fix is designed and unit-tested but NOT
operationally confirmed."

---

## 7. Contradictions found

### C1 — the scheduled-task inventory disagrees three ways

| Source | Says |
|---|---|
| `START_HERE.md:50` | "Six scheduled tasks on this machine" |
| `setup_scripts/verify_scheduled_tasks.ps1:67-79` | `$Expected` lists **11** tasks |
| `Get-ScheduledTask` (measured) | **13** `WNBA*` tasks registered |

Unknown to the standing auditor: **`WNBA prospective pair`** and **`WNBA_ReplyDeliveryWatchdog`**.

**Consequence as recorded:** the task that runs `prospective_pair\run_pair.cmd` — the one producing
the prospective-pair records whose validity `PROJECT_UPDATE_2026-08-04.md:576-592` adjudicates — is
absent from the inventory of the script whose job is to prove those tasks are healthy.

**Resolution:** frozen bytes govern. The machine wins over both documents. Reported, not reconciled.

### C2 — D-f's severity-C label is unquantified in the repository

Explicitly flagged by the original run as **not a factual contradiction**.

`PROJECT_UPDATE_2026-08-04.md:204` concerns the 26 forecast-obligation misses — a quantity the
original run did not test and does not contest. But the same defect destroyed 23 capture launches, an
18-hour injury-capture hole and the only zero-record day in the prospective forecast chain. **No
document carries any of those numbers.**

---

## 8. Escalation, stop conditions, and lane containment

**Escalation test asked:** does this defect change historical feature evidence?

**Answer recorded: NO.**

**Reasoning recorded:** what D-f destroyed on 2026-08-02 is *prospective capture* — 7 injury
snapshots, 7 odds snapshots, 4 news captures, one refresh, one referee pull, two props pulls and the
AM forecast run. None of it touches the frozen historical universe (2,982 team-game rows over 1,491
game clusters), the primary target `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, the K0
structure, the inference structure, the candidate universe, the cutoff-valid feature set or the
leakage status.

* **Escalations raised: none.**
* **Stop conditions tripped: none.**

**What does stay in the ops lane:** `PROJECT_UPDATE_2026-08-04.md:596-598` already states that
D-b/D-c/D-f mean served obligations are not a random subset. The original run made that concrete for
one day: on 2026-08-02 the served subset is the afternoon and evening only — a
**time-of-day-structured, not random**, selection.

This remediation raises no stop condition of its own.

---

## 9. Verifier defects carried

The independent verifier scored `O15_LOGOUT_SURVIVAL` **PASS_WITH_DEFECTS**. This section exists so
that nothing the verifier raised is quietly dropped. Its honest state is as follows.

**Defect 1 — the declared output `REPORT.md` was missing, and the verifier did not catch it.**
Recorded in the `validation_failed` event: "The independent verifier scored PASS_WITH_DEFECTS and did
not catch this; the mechanical expected-output check did." This is the parent finding of the present
node, it is carried in full in section 1, and it is the reason this document exists. It is **not
closed** by this document: the file at
`experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/REPORT.md` still does not exist, because
this node may not write there.

**Defect 2 and beyond — the verifier's itemized defect list is not recoverable from the repository.**
Stated plainly rather than papered over. The verifier's verdict for O15 survives only as the one-line
`detail` string on the `validation_failed` event in `orchestration/GRAPH_EVENTS.jsonl`. There is no
per-node verifier artifact for O15, and there is none for any other node in this graph either — the
program's convention, visible on the `node_passed` events for `O13_LEAD_WINDOW_LATENCY` and
`O14_OPS_ENTITY_RESOLUTION`, is "defects recorded in the node FINDINGS and carried, not closed", i.e.
the defect list is expected to live in the node's own `FINDINGS.json`.

This negative was checked rather than assumed:

* a repository-wide search for `PASS_WITH_DEFECTS` returns hits in exactly three files —
  `orchestration/GRAPH_EVENTS.jsonl`, `orchestration/DECISION_LEDGER.jsonl`, and
  `orchestration/scripts/seed_graph.py` — and the only O15 record among them is the
  `validation_failed` event quoted above;
* a repository-wide search for `O15_LOGOUT` finds no verifier verdict file;
* a filename search for `*VERIF*`, `*verdict*`, `*DEFECT*`, `*review*` across the worktree returns
  only unrelated Stage-1 experiment `gate_verdict.json` files, `verify_v14_control.py`,
  `setup_scripts/verify_scheduled_tasks.ps1` and `verify_all.py` — no orchestration verifier output;
* the same greps were run against a string known to be present (`e332_wnba_total`) and returned the
  expected four files, so the search itself is not silently failing.

Accordingly: **every verifier defect that is recoverable has been carried. It is possible that the
verifier raised further defects that were never persisted, and this document cannot recover them.**
That gap is stated rather than concealed, and it is a limitation of this remediation, not a claim
that no such defects exist.

Because the parent's `FINDINGS.json` was the designated home for carried defects, the whole of it is
represented in sections 4 through 12 of this document, including every item the original run itself
recorded against its own work.

---

## 10. What the original run could NOT establish

Carried in full. Each item is a limitation the original run recorded against itself.

1. **That S4U actually launches these tasks while logged out on this machine.** Not applied, not
   elevated, and a logged-out firing cannot be staged from inside a session.
2. **Whether the "25 of 26" claim at `PROJECT_UPDATE_2026-08-04.md:204,573-574` is correct.** It
   concerns forecast obligations, whose ledger the original run did not open. Neither confirmed nor
   contested; the O15 numbers are about capture launches, a different quantity.
3. **Why the 2026-08-02 evening forecast run (18:45 local) produced nothing.** The last WNBA id-332 is
   at 16:00:01, so the PM absence is **not** attributable to D-f. Cause unestablished.
4. **Anything before `2026-07-30T21:32:55-04:00`**, the oldest record the rolling 10 MB Operational
   log still holds. Absence of an id-332 before that instant is not evidence the defect did not fire.
   The window does cover essentially the whole prospective era, which began 2026-07-30
   (`project_docs/FREEZE_PROPOSAL_v0.md:21`).
5. **Whether the odds, props, news and referee streams show file gaps matching their 7/2/4/1
   suppressed launches.** Only the injury-PDF series and the forecast chain were independently
   corroborated.
6. **What working directory these tasks run in** — recorded as "every action's WorkingDirectory is
   empty". Unchanged by a logon-mode change, so not a regression risk of this fix, but an unexamined
   property of the task set.
7. **Whether S4U registration succeeds for a `Limited` RunLevel principal under this machine's
   policy.** The script carries `RunLevel` across explicitly and verifies it after, but that path was
   never executed.

---

## 11. Shared-contract changes — PROPOSED ONLY, nothing merged

The contract's third acceptance criterion was "no shared schema or contract change is merged from this
node." Neither proposal was applied; `setup_scripts/verify_scheduled_tasks.ps1` was not modified and
is outside the node's write scope.

**P1 — `setup_scripts/verify_scheduled_tasks.ps1` should read `Principal.LogonType`.**
Change: add to `$problems` when `LogonType` is not in `@('S4U','Password')`; add a "logon type" column
to the table. Measured rationale: the script reads `Settings.StartWhenAvailable` at line 108 and
nothing about *how* the task runs. On 2026-08-02 it would have printed `LastTaskResult=0`,
`StartWhenAvailable=True`, `State=Ready` for tasks that had just lost 23 launches.

**P2 — extend `$Expected` (lines 67-79) from 11 to 13 entries.**
Add `WNBA prospective pair` (Critical=`$true`) and `WNBA_ReplyDeliveryWatchdog`. Measured rationale:
`Get-ScheduledTask` reports 13 `WNBA*` tasks; the auditor knows 11.

Both proposals sit behind the coordinator ruling `D003_OPS_LANE_TARGETS_LIVE_ON_ANOTHER_BRANCH`
(2026-08-04T20:32:18Z), which held the ops-lane analyses **admissible as analysis, not mergeable
here**, reserving any cross-branch shared-contract change to the user under `GRAPH_POLICY.md` s6 via
node `O16_SHARED_SCHEMA_ADOPTION`.

---

## 12. Constraints observed by the original run

| Constraint | Recorded value |
|---|---|
| Mutating git commands run | 0 |
| Read-only git commands run | `git rev-parse --abbrev-ref HEAD` |
| Frozen artifacts modified | none |
| Writes outside scope | none |
| `stage2b/SEALED_RESULTS` read | no |
| Performance peeking | no |
| Machine state modified | **no** |

---

## 13. Constraints observed by this remediation

| Constraint | Value |
|---|---|
| New measurements performed | **0** |
| New findings introduced | **0** |
| Scripts executed | none |
| Files written | `experiments/player_program/ops_lane/R10_O15_REPORT_REMEDIATION/REPORT.md` only |
| Anything under `ops_lane/O15_LOGOUT_SURVIVAL/` modified | **no** |
| Frozen artifacts modified | none |
| Mutating git commands run | 0 |
| Read-only git commands run | `git rev-parse --abbrev-ref HEAD`, `git log --oneline --all -- <O15 path>` |
| `stage2b/SEALED_RESULTS` read | no |
| Performance peeking | no |
| Stop conditions tripped by this node | none |

**Standing limitation of this document.** It is a reconstruction from preserved artifacts by a
different agent, written 2026-08-04, after the original run failed validation. Where it and the
parent's `FINDINGS.json` could ever disagree, `FINDINGS.json` governs — it is the artifact the
original run actually produced, and this is prose about it.
