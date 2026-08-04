"""Emit REPORT.md, the required node artifact for O12_PER_GAME_EXECUTION_SCOPE.

Run: python experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/build_report.py
"""
from pathlib import Path

REPORT = r'''# O12_PER_GAME_EXECUTION_SCOPE — Per-game execution scope defect (D-c)

**Epistemic status (verbatim from the node contract):**

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch
> only. This lane does not block possession research unless it changes the historical feature
> evidence.

Worktree: `C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`,
branch `player-model-program` (verified with `git rev-parse --abbrev-ref HEAD`). Nothing outside
`experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/` was written. No git command
other than read-only `rev-parse` / `log` was run.

---

## 1. Is the defect documented? Yes — `DOCUMENTED`

It is defect **D-c** in the current project update.

| claim | citation |
|---|---|
| "**Per-game execution scope.** `daily_forecast.py` cannot be scoped to one game and keys deduplication on `now`. It was holding **every 15-minute firing** at the as-of time. Serves a **non-random** subset." Severity **A** for confirmation validity. | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:201` |
| Amendment map: `daily_forecast.py` — "per-game scope; stop keying deduplication on `now` (D-c)", owner engineering, bundled. | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:609` |
| D-c is item (i) of a **four**-fault repair set; D-b, D-a and D-d are separate faults. | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:569` |
| "D-b / D-c / D-f mean served obligations are not a random subset, which must be accounted for whenever the period is graded." | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:596` |
| Standing decision D-4 on the bundled amendment: "**Prepare, do not implement.**" | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:304` |
| `prospective_v0` runs "two fixed daily runs"; "Per-game dispatching is a documented v1 upgrade." | `project_docs/FREEZE_PROPOSAL_v0.md:41-43` |

The last row matters for how the defect should be read. The *absence* of per-game scope is a
declared v0 limitation, not an accident. What is defective is that the capture path was put to work
serving per-game obligations it was never built to address, and that its de-duplication cannot tell
one obligation from another.

Searched and found nothing further: `MISSION_LEDGER.md`, `ROADMAP.md`, `START_HERE.md`, the three
`HANDOFF_*.md` files, and the five daily capture scripts (`injury_capture_daily.py`,
`news_capture_daily.py`, `odds_capture_daily.py`, `props_capture_daily.py`,
`ref_assignments_capture_daily.py`) contain no mention of D-c or of per-game scope. D-c is a
`daily_forecast.py` / `evalharness/forecast_log.py` defect only; the capture daemons are not
implicated.

---

## 2. Reproduction — `REPRODUCED`, both limbs

### Limb 1 — cannot be scoped to one game

By inspection of the source:

* `daily_forecast.py:877-889` — argparse exposes exactly `--slate-date`, `--cutoff`, `--live`,
  `--no-log`. There is no game-selecting option of any kind.
* `daily_forecast.py:929` — the slate is discovered whole for the ET date.
* `daily_forecast.py:978` — `for g in slate:` forecasts every discovered game.
* `daily_forecast.py:1058-1061` — the COMPLETENESS RULE frozen 2026-07-31: *every* slate game gets
  a chain record, because "logging only successful forecasts would make the chain a filtered sample
  of its own slate". Per-game scope therefore cannot be bolted on as a quiet filter; it has to be
  declared, or it becomes exactly the survivorship problem that rule exists to prevent.

Measured against the bytes (`measure_chain_scope.py` produces `chain_scope_measurements.json`):

| chain | records | distinct cutoffs | records per firing (min-max) |
|---|---|---|---|
| `forecasts/forecast_log.jsonl` | 8 | 3 | 2 - 3 |
| `experiments/forecast_dryrun/scratch_chain.jsonl` | 15 | 5 | 3 - 3 |

No firing in either chain ever produced a single-game record set. Per-game execution has never
happened.

### Limb 2 — deduplication keyed on `now`

* `daily_forecast.py:893-895` — `now = datetime.now(timezone.utc)`; `cutoff = ... if args.cutoff else now`.
* `evalharness/forecast_log.py:697-707` — the refusal key is
  `(game_id, forecast_cutoff, model_version_hash)`.

Because a scheduled run supplies no `--cutoff`, `forecast_cutoff` is a microsecond-resolution wall
clock and the key can never collide. Measured: **0 of 3** distinct cutoffs in the official chain and
**1 of 5** in the scratch chain fall on a round second — the single round one is
`2026-07-30T15:05:00+00:00`, a manual `--cutoff` run. Every scheduled cutoff is a wall clock.

The consequence is directly visible in the scratch chain:

```
idx  game_id      label   forecast_cutoff                    model_hash
0    1022600211   T-90m   2026-07-30T21:21:36.688985+00:00   8cfca795
1    1022600210   T-90m   2026-07-30T21:21:36.688985+00:00   8cfca795
2    1022600212   T-8h    2026-07-30T21:21:36.688985+00:00   8cfca795
6    1022600211   T-90m   2026-07-30T21:23:26.529578+00:00   8cfca795
7    1022600210   T-90m   2026-07-30T21:23:26.529578+00:00   8cfca795
8    1022600212   T-8h    2026-07-30T21:23:26.529578+00:00   8cfca795
```

Two firings 110 seconds apart, the same three games at the same three contract labels under the same
frozen model hash, and the chain accepted all six.

| | official chain | scratch chain |
|---|---|---|
| repeat servings under the **shipped** key | **0** | **0** |
| repeat servings under the **obligation** key `(game_id, decision_time_label, model_version_hash)` | **0** | **3** |

**The shipped duplicate refusal has fired zero times in the entire recorded history of both
chains.** That is the defect stated as a number: the guard exists (`daily_forecast.py:1183-1187`
even has a prepared INFO gap for it) and is structurally unreachable.

Synthetic confirmation, `TESTS.py` test 1: four simulated 15-minute firings against one T-30m
obligation produce four chain records, zero `DuplicateForecastError`s, one obligation identity, and
a chain that still verifies. **The defect is semantic, not an integrity failure** — nothing about it
is detectable by `verify_chain()`.

### The official chain is *not* currently polluted

Under the obligation key the official chain has 0 repeat servings. Adopting the fix would have
changed nothing already logged there. The realized damage so far is in the scratch chain; the
official chain's exposure is prospective.

---

## 3. A third mechanism, not in the written description of D-c — finding O12-1

`decision_time_label` is not the obligation a run was dispatched to serve. It is computed from the
firing instant, with **no proximity bound**:

* `daily_forecast.py:598-599` — `nearest_label()` returns the `CONTRACT_LABELS`
  (`daily_forecast.py:126`) entry minimising the absolute gap between `hours_to_tip` and the label
  hours.

Measured on real bytes — game `1022600212` in the scratch chain:

| record | hours_to_tip at cutoff | recorded label |
|---|---|---|
| 2 | 4.806 | `T-8h` |
| 8 | 4.776 | `T-8h` |
| 11 | 4.716 | `T-90m` |

The label flips at 4.75 h, the midpoint between the 8 h and 1.5 h contract times. A record can and
does claim to have served the **T-90m** obligation from **4.7 hours** before tip. `TESTS.py` test 8
reproduces the flip and confirms every real label in that game equals `nearest_label(hours_to_tip)`.

This is the concrete mechanism behind the documented "serves a **non-random** subset" claim
(`PROJECT_UPDATE_2026-08-04.md:201`), and it is a **precondition** for any obligation-keyed fix: the
label has to become an input (which obligation am I discharging) rather than an output of the wall
clock. I did not change it — see section 6, proposal P3.

---

## 4. The fix — designed and tested, not adopted

`per_game_obligation_scope.py` in this directory. It is a **call-site wrapper**. It edits no shared
artifact: `evalharness/forecast_log.py` and `daily_forecast.py` are untouched, per the standing rule
that a missing check is added at the call site and never by editing a shared gate.

The single idea: *the thing a run owes is an obligation, not an instant.* An obligation is
`(game_id, decision_time_label, model_version_hash)`. Within a game each of the four contract labels
occurs exactly once (`daily_forecast.py:126`), so the triple is a complete identity — and,
critically, **it is derivable from schema `evalharness/forecast_log/1` records already on disk**
(`evalharness/forecast_log.py:87`). Adopting it requires **no schema change**.

`forecast_cutoff` keeps its existing and correct meaning as the as-of data boundary, including its
never-in-the-future refusal at `daily_forecast.py:899`. The fix does not widen it. This separation
is the whole point: one field is a data boundary, the other is an identity, and D-c is what happens
when one field is asked to be both.

Components:

* `obligations_for_game()` — the four obligations a game owes, with nominal instants.
* `served_obligation_keys()` — reads discharged obligations out of existing `/1` records.
* `due_obligations()` — unserved obligations inside a lead window. **Explicitly not a fix for D-b.**
* `scope_slate_to_games()` — restricts a slate to named games and returns a `ScopeDeclaration`
  naming every excluded game, so scope is *declared* and the COMPLETENESS RULE is honoured rather
  than evaded. `game_ids=None` reproduces existing whole-slate behaviour exactly.
* `guarded_log_forecast()` — raises `ObligationAlreadyServedError` before delegating to the
  unmodified `log_forecast`, whose own `DuplicateForecastError` remains underneath. The wrapper only
  ever *adds* a refusal; it can never permit something the shipped chain would refuse.

### Tests

`python experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/TESTS.py` gives exit **0**,
**34 checks, 34 passing, 0 failing**. Synthetic data plus read-only reads of the two real chains;
nothing is appended to any real chain (test chains go to `_scratch_chains/` in this directory).

1. Reproduction — shipped key never refuses (4 records, 0 refusals, 1 obligation, chain verifies).
2. Fix — 1 logged, 3 refused, 1 record on disk, chain verifies.
3. Regression — all four labels for one game still log; a **new** `model_version_hash` may re-serve
   the same obligation; a different game at the same label is not deduped.
4. Scope — declared and enforced; out-of-scope logging raises and writes nothing; `None` preserves
   existing behaviour.
5. Obligation construction and lead-window due-ness, including boundaries.
6. The mirrored `CONTRACT_LABELS` is byte-equivalent to `daily_forecast.py:126`.
7. Real chains, read-only: official 0 repeats, scratch 3 repeats under the obligation key.
8. The label-drift finding O12-1.

**Backward compatibility:** applied to the real official chain the obligation key finds 0 repeat
servings — adoption changes nothing already logged. Applied to the real scratch chain it finds 3.

**No-performance-peeking hygiene:** every script here reads only chain *metadata* (`record_idx`,
`game_id`, `forecast_cutoff`, `decision_time_label`, `logged_at_utc`, `model_version_hash`) plus
`hours_to_tip_at_cutoff` and `status`. No prediction value, no outcome, no comparison. Nothing under
`stage2b/SEALED_RESULTS/` was opened.

---

## 5. Contradictions found

**C1 — a document disagrees with the bytes.** `PROJECT_UPDATE_2026-08-04.md:580-585` (Appendix E.2)
identifies official-chain `record_idx 3` as GSV v TOR, created `14:30:06.442135Z` against an
`18:00:00Z` cutoff, and rests the `prospective_team_pair_v1` start ruling on it. In **this**
worktree, `forecasts/forecast_log.jsonl` `record_idx 3` is `game_id 1022600213`, `forecast_cutoff
2026-07-31T22:45:04.663008+00:00`, `logged_at_utc 2026-07-31T22:45:06.311020+00:00`, label `T-30m`.
Most likely explanation: the live chain is in the repository-root worktree on a different branch,
which this node is instructed not to read; this copy was last committed in `a5119a3` and its last
cutoff is `2026-08-01T14:20:03Z`, three days before the update. Per the standing rule I report the
contradiction rather than reconcile it. It does not affect the reproduction — both limbs reproduce
on the bytes present here, and the mechanism is in the source code, not in any particular record.
Note also that an `18:00:00Z` cutoff is a *round* instant, which under limb 2 means that record was
produced by a run given an explicit `--cutoff` — not by an unscoped scheduled firing.

**C2 — files named in the amendment map do not exist here.**
`PROJECT_UPDATE_2026-08-04.md:611-612` assigns fixes to `prospective_pair/should_run_base.py` and
`prospective_pair/coverage_audit.py`. Neither file, nor any directory named `prospective_pair`,
exists anywhere in this worktree (searched by filename across the whole tree). Consistent with
Appendix F marking both "no — internal" to the team thread. Consequence: the 20-minute lead window
cited in D-b could not be bound to any byte I read, so it is an explicit parameter in my module and
`due_obligations()` is documented as **not** a fix for D-b.

---

## 6. Shared-contract changes — proposed only, nothing merged

Per the lane rule, none of these is applied. The shared files are byte-untouched.

* **P1 — `evalharness/forecast_log.py:697-707`.** Change (or supplement) the duplicate key to
  `(game_id, decision_time_label, model_version_hash)`. Not merged; the equivalent enforcement lives
  in this node's call-site wrapper instead.
* **P2 — `daily_forecast.py`.** Add `--game-id` (repeatable) plus a written scope declaration, and
  route logging through the obligation guard. Not merged: outside this node's write scope, and
  `PROJECT_UPDATE_2026-08-04.md:304` records the standing decision "Prepare, do not implement."
* **P3 — `daily_forecast.py:598-599` and the `prospective_v0` / `prospective_team_pair_v1`
  contracts.** Make `decision_time_label` the obligation dispatched rather than
  `nearest_label(hours_to_tip)`, and/or bound the label by a maximum distance from the contract
  time. This changes what a prospective record *means* and touches two registered team-thread
  contracts. It is a precondition for P1 and P2 being meaningful.

**Sequencing note for whoever adopts these.** P1 without P3 is unsafe: if the label keeps being
assigned by wall clock, an obligation-keyed refusal will occasionally refuse a *correct* serving
because an earlier, badly-timed firing already claimed that label. P3 first, then P1/P2.

---

## 7. Escalation and stop conditions

**No escalation to the possession lane. No stop condition tripped.**

D-c lives entirely in the prospective capture path — the CLI surface of `daily_forecast.py`, the
chain duplicate key, and the label assignment. It touches no historical feature construction, no
fold rule, no target definition, no K0 structure, no leakage status and no candidate universe.
Checked directly: no `.py` file under `possessions_v1/`, `possessions_v2/`,
`possession_features_v1/` or `stage2a/` references `forecast_log.jsonl` or `scratch_chain`. The
primary target, the 2,982 team-game / 1,491 game-cluster universe, and the frozen incumbent
`D_ewma_shrunk` are untouched by anything in this node.

The finding that *does* need a decision above this node is O12-1 (section 3), because it bears on
what `prospective_team_pair_v1` records mean. I have not resolved it; it is proposal P3.

---

## 8. What I could NOT establish

1. **Whether the live official chain shows the same repeat-serving pattern.** The live chain is in
   the repository-root worktree on a different branch. Out of scope by instruction; not read.
2. **The actual scheduler firing cadence.** No scheduled-task definition, wrapper script, or
   invocation record exists in this worktree. The 15-minute cadence is taken from
   `PROJECT_UPDATE_2026-08-04.md:201` and modelled synthetically in `TESTS.py` — **not measured**.
   The two scratch-chain firings that repeat-served were 110 seconds apart, which is a manual re-run
   pattern rather than a 15-minute one, so the real-byte evidence demonstrates the *mechanism* but
   not the documented *cadence*.
3. **The coverage consequence in numbers.** `coverage_audit.py` is absent (C2), so I could not
   recompute whether a repeat serving counts once or twice toward coverage, and I did **not**
   recompute the published 31.9% figure. The coverage effect of the proposed key is stated as a
   mechanism, not as a number.
4. **Downstream consumer impact of P1.** I did not exhaustively audit `clv_transfer.py` and
   `cbs_accounting_v11.py` (named in the amendment map as shared consumers) for code keying on
   `forecast_cutoff`.
5. **Whether the completeness rule and per-game scope can be reconciled to the coordinator's
   satisfaction.** My `ScopeDeclaration` is a proposal for how; whether a declaration outside the
   chain is sufficient, or whether the scope must be recorded *inside* the record (a schema change),
   is a decision for O16 / the user, not for this node.

---

## 9. Files produced

| file | what it is |
|---|---|
| `REPORT.md` | this document |
| `FINDINGS.json` | machine-readable findings; `json.load()` verified |
| `per_game_obligation_scope.py` | the candidate fix, call-site wrapper, adopted nowhere |
| `TESTS.py` | 34 checks, `main()` returns 1 on failure; exit 0 |
| `measure_chain_scope.py` | read-only metadata measurement of both chains |
| `chain_scope_measurements.json` | its output, the source of every number in section 2 |
| `build_report.py` | emits this file |
| `_scratch_chains/` | throwaway test chains, rebuilt each run |
'''

if __name__ == "__main__":
    dest = Path(__file__).with_name("REPORT.md")
    dest.write_text(REPORT, encoding="utf-8")
    print(f"wrote {dest} ({len(REPORT.splitlines())} lines)")
