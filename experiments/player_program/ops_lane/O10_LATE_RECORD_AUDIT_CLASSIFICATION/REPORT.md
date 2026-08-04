# O10_LATE_RECORD_AUDIT_CLASSIFICATION — Classify late-arriving records in the prospective capture audit

**Epistemic status (verbatim from the node contract):**

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch
> only. This lane does not block possession research unless it changes the historical feature
> evidence.

**Node:** `O10_LATE_RECORD_AUDIT_CLASSIFICATION` · lane `operations` · type `audit` · severity on
failure `C`

**Verdict:** the defect **IS documented** and **REPRODUCES exactly**, on the numbers the
documentation states. Fix designed, implemented in isolation, 30/30 tests pass. **No shared file
was edited.**

---

## 1. Is it documented, and where

Yes. It is defect **D-a** in the player-program project update.

* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:199` — the defect statement:
  *"The coverage auditor accepts `late_record`s as evidence the job was healthy at a label.
  2026-08-03 PHX@CHI T-30m is classed `missing_data_unavailable` on the strength of two records
  that are themselves late."* Severity **B**; required action *"exclude `late_record` from the
  served-evidence test. Operational misses **26 -> 27**."*
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:558` — the reclassification, named:
  *"Reclassified: 2026-08-03 PHX@CHI T-30m — its only health evidence was two `late_record`s. The
  other three data-unavailable rows have genuine timely-served companions and stand."*
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:552` — the receipt line
  `late records | 2 | 2` in the Appendix E published/corrected table (`:544-556`).
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:571-572` — D-a listed as repair (iii)
  of the four-fault set.
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:612` — the amendment map naming the
  file and owner: `prospective_pair/coverage_audit.py` | *exclude `late_record` from
  served-evidence (D-a)* | owner **team thread** | bundle **no — internal**.
* `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:266` — next-action (3),
  *"Fix the auditor's late-record evidence test (D-a)."*

The node's own generated brief restates the mandate at
`experiments/player_program/orchestration/prompts/O10_LATE_RECORD_AUDIT_CLASSIFICATION.md:64`, and
the graph carries the same title in `orchestration/reports/CURRENT_STATUS.md:39`.

## 2. Where the code is — and a scope fact that must be recorded

The implementation named by the documentation, `prospective_pair/coverage_audit.py`, **does not
exist inside this node's declared read scope**, and does not exist in this worktree at all:

```
$ find <player-model-program worktree> -type d -name prospective_pair     -> (nothing)
$ git cat-file -e player-model-program:prospective_pair/coverage_audit.py
fatal: path 'prospective_pair/coverage_audit.py' exists on disk, but not in 'player-model-program'
$ git ls-files prospective_pair/                                          -> (nothing)
```

It exists **only as an untracked, uncommitted working-tree file** in the repository-root worktree
(`C:/Users/jgallagher/wnba-betting-model`, branch `data-refresh-2026`), together with its output
artifacts `forecasts/coverage_audit.csv` and `forecasts/coverage_receipt.json`. `git ls-files`
returns nothing for the directory and `git log` has no commit touching it: **the subject of this
node is not under version control**, so no line reference to it is reproducible from any commit.

I read those three files **read-only** and wrote nothing outside my write scope. To make the
reproduction auditable and stable I copied the two output artifacts into `evidence/` in this
directory; the source file is referenced by hash, not copied.

| file (repo-root worktree) | sha256 | tracked |
|---|---|---|
| `prospective_pair/coverage_audit.py` (328 lines) | `2360121ef80f0645ce6595a3f7adb6c17008ca8048f32f2de2b008fbbb68ae54` | **no** |
| `forecasts/coverage_audit.csv` | `26b22b90636071a0c2e20bd9ab4cee90bc0ebe9659c378f81fc8d791967ecbb0` | **no** |
| `forecasts/coverage_receipt.json` | `00b2274684125f46f73157d0eabe18d68e3978d88ea090ef43f105d722a61198` | **no** |

## 3. The defect, mechanically

`coverage_audit.py` builds the per-`(slate date, decision-time label)` health-evidence index from
**every** base record, with no timeliness test (`:189-194`):

```python
served_at: dict[tuple, set] = {}
for r in official:
    rgid = prov.get(str(r["game_id"]), str(r["game_id"]))
    d = gid_date.get(rgid)
    if d is not None:
        served_at.setdefault((d, r["decision_time_label"]), set()).add(rgid)
```

The very same record, viewed as its own obligation, is classified `late_record` at `:227-228`
because `created > cutoff`, and `late_record` is deliberately **not** in `SERVED` (`:253`). So a
record the auditor itself refuses to count as served is nonetheless admitted as proof the job was
alive, and at `:242-248` an unserved obligation is downgraded from `missing_job_did_not_run` (an
operational miss) to `missing_data_unavailable` (a benign game-specific gap).

The auditor's own docstring says this is the distinction that matters (`:24-28`):
*"`missing_job_did_not_run` is an OPERATIONAL MISS -- nobody was home... Coverage that conflates
them would hide exactly the failure that demoted `prospective_v0` to a pilot."* The bug conflates
them.

Note the shape: the authors already reasoned about the *date* keying of this same index
(`:184-186` — a global key *"would report 'the job served 6 other games at T-8h' for a day it never
ran at all"*). The lateness axis was not covered by that reasoning.

## 4. Reproduction — **REPRODUCED**

Run: `python experiments/player_program/ops_lane/O10_LATE_RECORD_AUDIT_CLASSIFICATION/TESTS.py`
(exit 0, 30/30 pass). Every number below is produced by that script from
`evidence/coverage_audit_snapshot.csv`; none is transcribed from prose.

**Published frame, by classification** (`A.classification.value_counts()`):

| class | n |
|---|---|
| `missing_job_did_not_run` | 26 |
| `not_yet_due` | 22 |
| `before_period_start` | 15 |
| `forecast_logged` | 15 |
| `missing_data_unavailable` | 4 |
| `late_record` | 2 |
| total obligations | **84** |

This agrees with the published receipt (`obligations_total` 84, `obligations_due` 47, `served` 15,
`coverage_served` 0.3191489361702128, `operational_misses` 26) — test **A15**.

**The named obligation.** `2026-08-03 CHI v PHX T-30m` (the update writes it away@home as
"PHX@CHI") is published `missing_data_unavailable`, reason *"job served 2 other game(s) on
2026-08-03 at T-30m"*. The **only** two records at `(2026-08-03, T-30m)` are:

| game | class | reason |
|---|---|---|
| NYL v SEA T-30m | `late_record` | created `2026-08-03T22:45:08.958486+00:00` after cutoff |
| ATL v LVA T-30m | `late_record` | created `2026-08-03T22:45:08.976775+00:00` after cutoff |

Both late. Its entire health evidence is late records — tests **A5, A6**. Under the corrected
evidence test it becomes `missing_job_did_not_run` — test **A7**.

**Effect on the receipt** (tests A8-A11):

| | published | corrected |
|---|---|---|
| `missing_data_unavailable` | 4 | **3** |
| `operational_misses` | 26 | **27** |
| obligations reclassified | — | **exactly 1** |
| `coverage_served` | 0.3191489362 | **0.3191489362 (unchanged)** |
| `unexplained` | 0 | 0 |
| `late_record` | 2 | 2 (untouched) |

This matches `PROJECT_UPDATE_2026-08-04.md:199` (*"26 -> 27"*), `:552-556` and `:558` **exactly**,
including the coverage figure staying at 31.9% — which follows structurally, since both classes sit
in `DUE` (`:255`) and neither is in `SERVED` (`:253`).

**The three survivors stand** (test A12), independently confirming `:558`. Their evidence:
2026-07-31 T-90m is served by PDX v IND T-90m (`forecast_logged`); 2026-07-31 T-30m by ATL v SEA
and WAS v DAL T-30m (both `forecast_logged`). All timely.

**Registered gate verdicts do not flip.** `coverage_served` 0.319 < 0.95 and operational misses
above 0 both before and after; `promotion_grade` was already `false` and stays `false`.

## 5. The fix — designed and tested in isolation

`late_record_evidence.py` in this directory. `served_at_timely()` is the drop-in replacement for
`coverage_audit.py:189-194`; `reclassify()` applies the identical rule to an already-produced audit
frame so the effect is measurable against frozen bytes without re-running the auditor (whose
`main()` writes into the repo-root worktree — never invoked here).

The rule: **a record is evidence the job was healthy at a label only if it was created at or
before that label's cutoff**, using the same predicate as the `late_record` test (`created >
cutoff` means late), so the two tests cannot disagree. Records whose timeliness cannot be
established — unknown tip, unknown label — are **excluded**: fail closed, in the direction that
reports the miss rather than hides it (tests B5, B6).

Tested properties, all passing:

* B1-B4, B7 — late contributes nothing; timely contributes; exactly-at-cutoff is timely; a mixed
  bucket keeps only the timely game; evidence is keyed per label, not pooled.
* C1-C2 — a late-only bucket promotes the gap to `missing_job_did_not_run`; a timely companion
  keeps `missing_data_unavailable`.
* C3 — `explicit_no_forecast` remains valid health evidence. An honest decline means the job *was*
  present (`:25`); the fix must not, and does not, break that.
* C4 — one late plus one timely still stands as a data gap.
* C5 — evidence does not leak across dates or labels.
* C6 — the fix never turns an operational miss back into a data gap (one-way only).
* C7-C8 — idempotent; no row added, dropped or reordered.

`PROPOSED_PATCH.diff` carries the source change as **text only**. It is not applied: the target is
team-thread-owned (`:612`) and lies outside this node's write scope.

## 6. Shared schema / contract changes — none merged

Nothing shared was touched. Two items are **proposed, not merged**:

1. The `coverage_audit.py` served-evidence patch (`PROPOSED_PATCH.diff`) — team-thread owned,
   internal, no shared consumer per `:612` and `:614`.
2. A one-line docstring amendment at `coverage_audit.py:19-20`, where the
   `missing_data_unavailable` class is defined as *"the job did serve other games at that cutoff"*
   without saying that only timely records count. The class list is the auditor's
   contract-of-record; leaving it silent is how the defect survived review.

Downstream obligations if applied, per `:617-619`: regenerate `coverage_receipt.json`, re-run
`verify_chain()` on both chains, confirm no schema-`/1` consumer breaks, re-run
`build_program_state.py`.

## 7. Escalation and stop conditions

**No stop condition is tripped.** The defect changes **no historical feature evidence**. The
coverage auditor is a read-only reporting layer over the prospective forecast logs
(`coverage_audit.py:5` — *"Both logs are read-only here"*); it produces no feature, target or
training row. It does not touch the primary target, the K0 structure, the inference structure, the
candidate universe, the cutoff-valid feature set, or leakage status. **Nothing escalates to the
possession lane.**

One consequence that belongs to the operations record, not to research: the correction makes the
prospective stream's operational-miss count one worse, and the update itself already states
(`:596-598`) that D-b / D-c / D-f mean served obligations are **not a random subset**, which must
be accounted for whenever the period is graded. D-a does not change that conclusion; it sharpens
the count feeding it.

## 8. Contradictions found

1. **Documentation vs. version control.** `PROJECT_UPDATE_2026-08-04.md:612` cites
   `prospective_pair/coverage_audit.py` as an owned, amendable project file. The file is
   **untracked** — no commit contains it, and it exists only in one worktree's uncommitted state.
   A B-severity defect is being tracked against bytes that git does not know exist, and that no
   other worktree can see. This is a process contradiction, not a numerical one, and I did not
   resolve it.
2. **Unverifiable citation.** `:199` says D-a is *"A variant of the bug PL-003 fixed once."*
   `PL-003` appears **nowhere else** in this worktree — a recursive grep for `PL-003` over the
   whole player-model-program worktree returns exactly that one line. `PL-006` (`:591`, `:600`) is
   likewise self-referential. No ledger defining the `PL-` series is present in
   `experiments/player_program/`. I therefore **could not verify** that the prior fix exists, what
   it changed, or whether it covered a third site of the same pattern.
3. No contradiction was found between the documented numbers and the bytes. Every figure in
   Appendix E that bears on D-a reproduced exactly.

## 9. What I could NOT establish

* **Whether the same pattern occurs at a third site.** I audited `coverage_audit.py` only.
  `prospective_pair/should_run_base.py` (the D-b / D-d subject, `:611`) is equally untracked and
  outside my mandate; I did not read or analyse it. Given PL-003 is described as the same bug fixed
  once before and I could not locate PL-003, I cannot bound how many sites share this pattern.
* **Whether the corrected auditor reproduces on live data.** I did not execute
  `coverage_audit.main()` — it writes `forecasts/coverage_audit.csv` and
  `forecasts/coverage_receipt.json` into the repo-root worktree, which I am forbidden to modify.
  The reproduction is against the frozen published artifact, which is exactly the state the
  documentation reports. A live re-run after applying the patch remains to be done by the owner.
* **Whether `recs[0]` is always the earliest-created record.** My CSV-level reclassifier uses the
  auditor's own stated invariant (`:216-218`, *"`recs` is in chain order, so `recs[0]` is the
  original"*) to infer that if `recs[0]` is late, no later record for that obligation is timely.
  I did not independently verify chain ordering against the log. `served_at_timely()` — the actual
  proposed fix — does **not** depend on this: it tests each record's own timestamp.
* **Any figure in `PROJECT_UPDATE_2026-08-04.md` outside Appendix E and section 5.** Not in scope;
  not checked; not cited as verified here.
* **Whether the four-fault repair set is complete.** Only D-a was in this node's mandate.

## 10. Files produced (all inside the declared write scope)

```
experiments/player_program/ops_lane/O10_LATE_RECORD_AUDIT_CLASSIFICATION/
  REPORT.md
  FINDINGS.json
  late_record_evidence.py            proposed fix + frame-level reclassifier, isolated
  TESTS.py                           30 checks, main() returns 1 on failure; exit 0
  PROPOSED_PATCH.diff                text only, NOT applied
  evidence/coverage_audit_snapshot.csv     sha256 26b22b90...7ecbb0 (read-only copy)
  evidence/coverage_receipt_snapshot.json  sha256 00b22746...2a61198 (read-only copy)
```

No git command was run other than read-only `rev-parse`, `ls-files`, `log` and `cat-file -e`.
