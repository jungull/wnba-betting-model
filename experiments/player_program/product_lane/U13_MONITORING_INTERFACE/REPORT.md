# U13_MONITORING_INTERFACE — stale-input, missing-lineup, failed-job and rollback visibility

**Epistemic status (verbatim from the node contract):**

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model has been promoted.

**Nothing in this node implies a model has been promoted.** The incumbent `D_ewma_shrunk` is
frozen (`experiments/player_program/PROGRAM_STATE.json:18`) and no challenger has been registered.
The interface is model-agnostic by construction and by test: it takes a model version and artifact
hashes as opaque data and cannot tell which model — or whether any model — produced the numbers it
is asked to display. It would render exactly as well against the frozen incumbent, against nothing
at all, or against a challenger that never arrives.

Worktree: `C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`, branch
`player-model-program`. No git command other than `rev-parse --abbrev-ref HEAD` was run. No file
outside `experiments/player_program/product_lane/U13_MONITORING_INTERFACE/` was written. No frozen
artifact was opened for writing. `experiments/player_program/stage2b/SEALED_RESULTS` was never
read; the repository scan in `measure_repo_facts.py` skips it by path.

---

## 1. What was built

| File | What it is |
|---|---|
| `monitor_schema.py` | status vocabularies, alert codes, severities, the display-cell contract |
| `monitor_state.py` | `evaluate(snapshot, evaluated_at_utc)` — a pure, fail-closed judgement of one frame |
| `render_monitor.py` | the operator panel: four separate failure panels plus projections and alerts |
| `make_fixtures.py` | deterministic generator for the nine fixtures |
| `build_views.py` | renders every fixture into `MONITOR_VIEWS.md` and `MONITOR_EVALUATIONS.json` |
| `measure_repo_facts.py` | every repository number quoted below, written to `REPO_FACTS.json` |
| `TESTS.py` | 148 checks; `main()` returns 1 on any failure |
| `MONITOR_CONTRACT.md` | the product contract a later implementer is held to |
| `FINDINGS.json` | machine-readable form of this report |

Commands actually run, in order:

```
python make_fixtures.py          # 9 fixtures
python build_views.py            # MONITOR_VIEWS.md, MONITOR_EVALUATIONS.json
python measure_repo_facts.py     # REPO_FACTS.json
python build_report.py           # this file
python TESTS.py                  # checks run: 148   failures: 0
```

---

## 2. What I measured

### 2.1 Zero live inputs exist to monitor

`measure_repo_facts.py` parses
`experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/SOURCE_BINDING.json` and counts
`domains[*].bound` independently of the file's own summary fields. Both agree:

* **8 domains, 0 bound** — `SOURCE_BINDING.json:443` (`"n_bound": 0`) and `:444`
  (`"n_domains": 8`); the file's own headline at `:442` states that zero of the eight domains is
  bound to a live source.

This is the single most consequential fact for this node. The failure classes I was asked to make
visible are, today, all in their most severe state at once: there is no bound source for lineups,
injuries, odds, starters, minute restrictions, transactions, coaching or news.

I did not paper over this. `fixtures/unbound_reality.json` is the frame the monitor would produce
if pointed at the program as it stands: **16 CRITICAL alerts, 0 of 2 projections rendered, every
one of the eight domains rendering `UNBOUND`**. The rendered panel is in `MONITOR_VIEWS.md`. That
is the honest view, and building an interface whose honest view is empty is the point.

### 2.2 The status vocabulary is quoted, not invented

The lineup statuses `PROJECTED / ANNOUNCED / CONFIRMED` are taken from the repository's own capture
schema at
`experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/capture_schema.py:98`. The eight
input domains are the eight D11 contract domains declared at `capture_schema.py:78` and restated as
contract criteria at `capture_schema.py:175`. Those line numbers were located by
`measure_repo_facts.py` and are recorded in `REPO_FACTS.json`.

### 2.3 The job-status logic is derived from documented real defects

`measure_repo_facts.py` extracts the capture-defect table by regex: **6 defects, D-a through D-f,
at `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:199-204`**. Two shaped the evaluator:

* **D-a** (`:199`) — the coverage auditor accepts late records as evidence the job was healthy.
* **D-d** (`:202`) — two records created 22:45:08Z against 22:34 / 22:44 cutoffs; discovery worked,
  execution was late.

`monitor_state._eval_job` therefore refuses to take `SUCCEEDED` at face value: a job whose
`completed_at_utc` is after its own `cutoff_utc` is downgraded to `LATE` on the timestamps alone.
`fixtures/failed_job.json` encodes the D-d timestamps; the evaluator measures **11.133 minutes past
cutoff** and reports `LATE`, not `SUCCEEDED` (`TESTS.py` section A3).

**D-b** (`:200`) is the silent-discovery miss — an obligation that never became visible produced no
alarm. Its monitor-side analogue is `expected_projections` (section 3.4).

### 2.4 Rollback is not documented anywhere in this program — a negative result

`measure_repo_facts.py` scans every `.py/.md/.json/.jsonl/.txt/.csv` file under
`experiments/player_program`, excluding this node's own directory and `SEALED_RESULTS`:

* **10 occurrences of "rollback", 10 of them self-referential, 0 elsewhere.**

All ten are the graph restating this node's own acceptance criterion:
`orchestration/PROGRAM_GRAPH.json:3174` and `:3227`, `orchestration/scripts/seed_graph.py:741,743`,
the generated prompt `orchestration/prompts/U13_MONITORING_INTERFACE.md:1,64,71`, and the generated
`orchestration/reports/CURRENT_STATUS.md:57` and `DOCUMENT_INDEX.md:303`.

**There is no rollback mechanism, procedure, log, state file or version-pinning convention in this
program.** The ROLLBACK panel I built is therefore a *specification of what a rollback record would
have to contain* — state, serving version, superseded version, timestamp, reason, initiator — fed
by fixtures only. I did not invent a producer for it and I did not describe it as if one existed.

---

## 3. How each acceptance criterion is met

Fixture results, reproduced by `python build_views.py`:

| fixture | serving | shown | alerts | codes raised |
|---|---|---|---|---|
| `healthy` | SERVING | 2/2 | 0 | — |
| `stale_input` | SUPPRESSED | 0/2 | 3 | `INPUT_STALE` |
| `missing_lineup` | DEGRADED | 1/2 | 2 | `LINEUP_MISSING` |
| `failed_job` | SUPPRESSED | 0/2 | 5 | `JOB_FAILED`, `JOB_DID_NOT_RUN`, `JOB_LATE` |
| `rollback_active` | SERVING | 2/2 | 1 | `ROLLBACK_ACTIVE` |
| `rollback_pending` | SUPPRESSED | 0/2 | 3 | `ROLLBACK_PENDING` |
| `vanished_projection` | DEGRADED | 1/2 | 1 | `PROJECTION_ROW_ABSENT` |
| `silent_failure_attempt` | SUPPRESSED | 0/2 | 15 | binding, snapshot, rollback and coverage codes |
| `unbound_reality` | SUPPRESSED | 0/2 | 16 | `INPUT_UNBOUND`, `LINEUP_UNBOUND`, `DEPENDENCY_UNDECLARED` |

### 3.1 Stale inputs, missing lineups and failed jobs are each individually visible

Four separate panels, four separate code families, four separate status vocabularies. They are
never merged into one health light.

* **Stale** — `stale_input` puts exactly one input row in `STALE` (`odds_feed`, measured age
  2520.0 s against its declared 600 s limit), leaves the other three `OK`, and raises no `LINEUP_*`
  or `JOB_*` code. A stale feed cannot masquerade as a lineup or job problem.
* **Missing lineup** — `missing_lineup` puts exactly one lineup row in `MISSING` with a null player
  count rather than a fabricated one, **and the other team's projection still renders**. The gap is
  scoped to the affected entity; one missing lineup does not blind the slate, and it does not
  silently pass either.
* **Failed jobs** — `failed_job` carries three distinct pathologies in one frame: an outright
  `FAILED`, a job that was due with no run (`DID_NOT_RUN`), and a job declaring `SUCCEEDED` that
  finished after its own cutoff (`LATE`). `TESTS.py` section A3 asserts all three are distinct.

### 3.2 Rollback state is visible

The ROLLBACK panel prints state, serving version, superseded version, changed-at, reason and
initiator, with `UNAVAILABLE` in any field the snapshot does not carry.

`ROLLBACK_ACTIVE` deliberately does **not** suppress. A rolled-back version is a real serving
version and its numbers are real; hiding them would push an operator to a worse source. It raises a
mandatory banner naming both versions instead. `ROLLBACK_PENDING`, `ROLLBACK_FAILED` and
`ROLLBACK_UNKNOWN` do suppress, because in those states which version is serving is not
established. An absent rollback block evaluates to `UNKNOWN`, never `NONE`.

### 3.3 A silent failure is impossible

This is the criterion the lane exists for, and it is tested four independent ways.

1. **The adversarial fixture.** `silent_failure_attempt` is a snapshot carrying two entirely
   plausible projections (81.25 and 79.5 possessions) and no evidence of any kind: no generated-at
   timestamp, no model binding, no inputs, no lineups, no jobs, no rollback state, no declared
   dependencies and no expected slate. Result: **0 numbers rendered, 15 CRITICAL alerts**, and
   `TESTS.py` section C1 asserts the strings `81.25` and `79.5` appear nowhere in the rendered
   panel.
2. **Malformed and absent input.** `evaluate(None)`, `evaluate({})`, `evaluate([1,2,3])`,
   `evaluate("everything is fine")` and a wrong-schema object each return `SUPPRESSED` with alerts
   and never raise. A monitor that crashes on bad input is a monitor that shows nothing while
   something is wrong.
3. **Exhaustive ablation sweep** (`TESTS.py` section C3). Every one of the **132 addressable
   locations** in the healthy snapshot is deleted in turn and the frame re-evaluated. Invariants
   asserted: deleting information never *increases* the number of rendered numbers; no deletion
   reduces output without raising an alert; no alert cell ever lacks an explanatory code. **58 of
   the 132 deletions suppress a projection**, so the sweep bites rather than passing vacuously. A
   parallel null-sweep (section C4) over the same 132 locations confirms nulling a field is never
   rewarded with a number.
4. **The value is structurally unreachable.** An `ALERT` display cell does not carry the underlying
   value at all — `monitor_state` drops it. The renderer holds no policy and cannot override the
   evaluator, because it never receives the number.

The alert token is the word `UNAVAILABLE`: not a blank, not a dash, not a zero, nothing a reader
can mistake for a quantity (`TESTS.py` section C6).

Two further guards worth naming:

* **A frozen dashboard is a failing dashboard.** The snapshot's own age is checked against
  `snapshot_max_age_seconds` (default 900 s). Evaluating the healthy fixture five hours late raises
  `SNAPSHOT_STALE` and renders nothing. The last good frame is never reused.
* **Forgetting to declare a dependency does not buy a number.** If a projection omits its lineup
  dependency but a lineup row exists for its own game and team, the row still gates it
  (`TESTS.py` section A2b).

### 3.4 Expected coverage — the failure mode the criteria do not name

A projection that vanishes from the snapshot is invisible: a shorter table reads as a complete
table. This is the monitor-side form of documented defect D-b, where an obligation that never
became visible produced no alarm.

The snapshot therefore declares `expected_projections`, its obligations for the frame. An expected
key with no matching projection is rendered as **its own suppressed row** plus a CRITICAL
`PROJECTION_ROW_ABSENT` alert (`fixtures/vanished_projection.json`). A snapshot that declares no
expected slate raises `EXPECTED_COVERAGE_UNDECLARED` and suppresses everything: a monitor that does
not know what it should be showing cannot certify that it is showing it.

### 3.5 Model-agnosticism, mechanically enforced

`TESTS.py` section D reads every `arm_id`, `experiment_id` and `artifact_id` from
`experiments/player_program/arm_registry.jsonl`, adds the frozen incumbent's arm name from
`PROGRAM_STATE.json:18` and both of its MAE figures — **50 identifiers** — and fails if any of them
appears in `monitor_schema.py`, `monitor_state.py`, `render_monitor.py`, `build_views.py`,
`make_fixtures.py` or any fixture. The check passes. The suite then feeds three arbitrary model
version strings through the interface and confirms each is carried, echoed and rendered unchanged.

Fixture model versions are self-describing placeholders (`fixture-model-v0`) and fixture artifact
hashes are sha256 of their own label, so no reader can mistake either for program bytes.

---

## 4. Contradictions and divergences found

**U13-C1 — the contract presumes a rollback state that does not exist.** The brief and
`PROGRAM_GRAPH.json:3174` require that rollback state be visible, which reads as though a rollback
state exists to be surfaced. Measured: zero non-self-referential occurrences of the word in the
program (section 2.4). I did not resolve this by inventing a producer. The panel is built and
specified; it is fed by fixtures; the absence is reported.

**U13-C2 — sibling product nodes diverge on one alert code.** The concurrently running
`U10_PREDICTION_API_SCHEMA` emits `INPUT_MISSING`
(`product_lane/U10_PREDICTION_API_SCHEMA/prediction_response_schema.py:388`), `INPUT_STALE`
(`:398`) and `JOB_FAILED` (`:408`) — identical to this node's codes — but uses `JOB_NOT_RUN`
(`:418`) where this node uses `JOB_DID_NOT_RUN`, and carries no rollback vocabulary at all. I did
not resolve it: U10 is in flight and unvalidated, editing it is outside my write scope, and
coupling this node's runtime to unvalidated concurrent output would be worse than the divergence.
Recorded in `FINDINGS.json` as a proposed shared-contract change for the coordinator. **Nothing was
merged and no sibling file was touched.**

**U13-C3 — severity and suppression are separate axes, and the panel must not be read otherwise.**
The `stale_input` fixture raises three WARNING alerts and **zero** CRITICAL alerts, yet serving is
`SUPPRESSED`. An operator who equates "no critical alerts" with "healthy" would misread it. The
serving banner is therefore printed first and independently of any severity count, and the contract
states the two axes explicitly (`MONITOR_CONTRACT.md` section 7).

---

## 5. What I could NOT establish

* **Whether any real producer will ever write a monitor snapshot.** None exists in the repository,
  and building one is outside this node's write scope. Everything here is evaluated against
  fixtures.
* **Real staleness thresholds.** Every `max_age_seconds` in the fixtures is invented. There is no
  measured refresh cadence anywhere in the program to derive one from — precisely because zero
  capture domains are bound (section 2.1). A later node with read access to `data/` could measure
  actual inter-capture intervals; I could not, and did not guess a number in this report.
* **Rollback semantics in the operational system.** There is nothing to reproduce (U13-C1).
* **Whether the modelled input domains would in practice arrive through the D11 capture ledger or a
  separate path.** D11's own adapters are unbuilt; its `SOURCE_BINDING.json` states the candidate
  source files lie outside that node's read scope.
* **Whether `U11_UI_SHELL` renders these panels compatibly.** I did not read it for behaviour, do
  not import it, and make no claim about interoperability beyond the U10 code comparison above.
* **Any statement about model quality, calibration or comparative performance.** Out of scope by
  the standing rules; nothing in this node inspects a fit, a fold or a result.

---

## 6. Stop conditions

**None tripped.** Nothing in this node touches the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set or the leakage status. The monitor
never reads a feature, a fold, a fit or a result; it reads timestamps, statuses and opaque version
strings. No frozen artifact was modified. No performance figure was inspected or reproduced.

---

## 7. Validation

```
$ python experiments/player_program/product_lane/U13_MONITORING_INTERFACE/TESTS.py
checks run: 148   failures: 0
```

`TESTS.py` also re-evaluates every fixture and compares against the stored
`MONITOR_EVALUATIONS.json`, so a change to the evaluator that is not reflected in the committed
views fails the suite.
