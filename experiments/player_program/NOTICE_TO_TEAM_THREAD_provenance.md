# NOTICE to the team-model thread · a producer gate could report a clean tree it never measured

**From:** the player model program (branch `player-model-program`)
**Date:** 2026-08-03
**Severity:** provenance only. **No model result is challenged by this notice.**
**Action requested:** none forced. The team thread decides what, if anything, to regenerate.

**This notice changes nothing in the team thread.** No team file, receipt, registry row,
leaderboard, ledger entry or classification has been altered. The repair described in §6 is
committed **only on the player branch** (`ef0d557`).

---

## 1. The defect, exactly

A producer gate established working-tree cleanliness like this:

```python
dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
```

`_git` is best-effort — it swallows a non-zero exit and returns `""`. **An empty porcelain status
is exactly what a clean tree returns.** A `git status` that *failed* and a tree that was *clean*
are therefore the same value, and the gate cannot distinguish them.

`git rev-parse HEAD` needs no work tree and frequently still succeeds where `git status` does not.
So the receipt carries a **real commit** next to an **unmeasured** cleanliness verdict — the worst
available combination, because the artifact looks fully attributed.

### Two triggers, both real

| trigger | effect | status |
|---|---|---|
| **`core.bare=true` on a normal checkout** | `git status` exits 128; `git rev-parse HEAD` exits 0 | **was live in this repository on 2026-08-03**, in the main checkout and every worktree. Corrected by the user; `core.bare=false` verified across all seven checkouts |
| **inherited `GIT_DIR` + `GIT_WORK_TREE`** — a `pre-push` hook exports `GIT_DIR`, and this project's hook runs the whole Layer-A gate | `git status` describes a *different* repository and can return empty | reproduced in the test suite: `GIT_DIR+GIT_WORK_TREE` yields an empty, false-clean status. (`GIT_DIR` alone yields foreign noise on git 2.55 — also wrong, differently) |

### Demonstration

Against a pristine checkout of `d69aa02` while `core.bare=true`:

```
ok: True    working_tree_clean_vs_head: True    n_dirty_paths: 0
commit: d69aa0250fc95cbebacecb821482734819bebf36
```

The tree actually had **98 dirty paths**.

---

## 2. Which runners and commits contain it

Three modules share the pattern. **All three are present at `d69aa02` and at every earlier commit
that carries them.**

| module | role | receipt it writes | repaired? |
|---|---|---|---|
| `run_team_oof_v12_2.py` | the corrected team OOF runner | `clean_producer/1` | **yes**, on the player branch only |
| `run_player_oof_v14.py` | the player OOF runner (as committed at `d69aa02`) | `clean_producer/1`-equivalent | **yes**, on the player branch only |
| `gate_receipt.py` | writes every `GATE_RECEIPT_A*_producer_tree.json` | `layer_a_gate_receipt/1` | **NO — untouched. See §5** |

`run_team_oof_v12.py` (the superseded `/1` runner) carries it too and is inert.

---

## 3. Which prior receipts may be unmeasured

Every receipt in the repository carrying a cleanliness claim was enumerated. **Nine exist. Exactly
one is at risk.**

| receipt | claim | verdict |
|---|---|---|
| `GATE_RECEIPT_A14` (`2a5da64`) | 112 dirty | **measured** — reports dirt, so git ran |
| `GATE_RECEIPT_A16` (`027de4a`) | 98 dirty | **measured** |
| `GATE_RECEIPT_A19` (`56c336a`) | 102 dirty | **measured** |
| `GATE_RECEIPT_A21` (`0225f6a`) | 106 dirty | **measured** |
| `GATE_RECEIPT_A23` (`6f6329f`) | 110 dirty | **measured** |
| `GATE_RECEIPT_A25` (`702a948`) | 100 dirty | **measured** |
| `cbs_v12_team_oof/1` `run_index.json` (`0225f6a`) | 97 dirty | **measured** — this is the known `/1` defect, honestly recorded |
| **`cbs_v12_team_oof/2` `attempt_001` `run_index.json` (`3b04be5`)** | **0 dirty, clean, `clean_producer/1`** | **UNMEASURED-OR-CLEAN — cannot be told apart from the receipt alone. See §4** |
| player program `PHASE0_AUDIT_RECEIPT.json` | 0 dirty | the deliberate reproduction of the defect; labelled `FAIL_OPEN: true` |

**A non-zero dirty count is proof the gate measured.** Only a zero-count `/1` receipt is ambiguous,
and there is exactly one of those.

A useful corollary: because all six A-receipts report dirt, git was working whenever they ran.
`core.bare=true` was therefore **not** a permanent condition, which narrows the exposure window —
though this program cannot establish when it was set relative to any given run.

---

## 4. What remains reproducible independently — `cbs_v12_team_oof/2`

**Its reproducibility claim holds, and does not depend on the gate.**

The receipt records a SHA-256 for each of the 19 producer sources, **computed from the bytes on
disk at runtime**. Re-derived by the player program:

```
git show 3b04be5:<path>  for all 19 sources
    match 19    mismatch 0    missing 0
recorded  set digest: 12ce0b88ca495fc0d97f4fc90b3a4eeda55a1ab794a2d877ccd5239ac800057d
recomputed set digest: 12ce0b88ca495fc0d97f4fc90b3a4eeda55a1ab794a2d877ccd5239ac800057d   MATCH
```

Because the runtime digests were taken from disk and equal the commit's blobs, **the producing code
on disk was byte-identical to `3b04be5`.** That is the guarantee that matters, and it is
independent of `git status` entirely.

**What is therefore NOT in question:** the forecasts, the fitted values, the model identities, the
snapshot hashes, the fold receipts, and the attribution of the artifacts to commit `3b04be5`.

**What IS unverified:** only the broader, weaker claim that *no other file anywhere in the tree*
differed from `3b04be5`. That claim affects no output, because a file outside `PRODUCER_SOURCES`
cannot by construction change what the run produced — unless the `PRODUCER_SOURCES` list is itself
incomplete, which is a separate question this notice does not open.

Two facts of record, neither of which changes the above:

* the retained generating checkout `_gen_3b04be5__20260803T011852Z` **no longer exists on disk** —
  a `find` over the repository returns no `_gen_*` directory — so it cannot now be re-inspected;
* the exposure window is **undetermined**: this program cannot establish when `core.bare=true` was
  set relative to the run's completion at `2026-08-03T01:20:04Z`.

**Recommendation: do not regenerate `cbs_v12_team_oof/2`.** Regenerating would attach a different
`producer_source_set_digest` to byte-identical forecasts, which misrepresents history rather than
improving it — the same reasoning the team thread already applied when the `mkdir` fix changed two
of the nineteen sources at HEAD.

---

## 5. What does require attention — `gate_receipt.py`

**This is the part of the notice that is forward-looking rather than historical, and it is the
one worth acting on.**

`gate_receipt.py` is **not repaired** and carries the same best-effort `_git` with no exit check
and no environment scrubbing. Its receipt includes:

```python
"certifies_this_commit": (receipt_kind == "post_push_clean_checkout" and not dirty)
```

Under the fail-open condition `dirty` is `[]`, so **`certifies_this_commit` becomes `true` for a
commit whose tree the gate never inspected.** No existing A-receipt is affected — all six report
dirt — but the next `post_push_clean_checkout` receipt run under a broken git environment would
issue a false certification, and a certification is a stronger claim than a cleanliness note.

The hazard is not hypothetical: the `pre-push` hook runs the Layer-A gate and exports `GIT_DIR`,
which is precisely the second trigger in §1.

**`gate_receipt.py` is a team-thread file and has been left untouched.**

---

## 6. The proposed repair — `clean_producer/2`

Already reviewed, tested and committed on the player branch at `ef0d557`. Offered for adoption; not
imposed. Three changes, all confined to the gate:

1. **`_git_checked`** — a non-zero git exit raises `DirtyProducer` instead of returning `""`.
   Absence of evidence of dirt is not evidence of cleanliness.
2. **`_git_env`** — eight variables (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`,
   `GIT_COMMON_DIR`, `GIT_NAMESPACE`, `GIT_OBJECT_DIRECTORY`,
   `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_CEILING_DIRECTORIES`) stripped from every git call.
3. **Toplevel-matches-root** — `git rev-parse --show-toplevel` must resolve to the run's `--root`,
   or the gate refuses rather than reporting a verdict measured somewhere else.

Plus: the dirty refusal precedes receipt construction; `HEAD` must match `^[0-9a-f]{40}$` when the
tree reports clean; and the receipt records `git_toplevel_matched_root`,
`inherited_git_env_scrubbed` and `git_failure_is_a_refusal_not_a_clean_verdict`, so a reader can
see the gate *measured* rather than merely *concluded*.

**Receipt version bumped `/1` → `/2` with `supersedes` and `superseded_because`.** Without this a
measured clean verdict is textually identical to an unmeasured one and no reader can tell which
gate wrote a given receipt. The preserved repair left the team runner at `/1`; the bump is a
**player-program addition**, flagged so the divergence is explicit.

**No prediction, fitting, selection, emission or validation logic is touched.** The diff is
confined to `_git`, `_git_checked`, `_git_env` and `require_clean_producer`.

### Evidence — `experiments/player_program/test_failclosed_gate.py`, 61/61, both runners

| | condition | result |
|---|---|---|
| T1 | a genuinely clean tree passes, and the receipt asserts it measured one | pass |
| T2 | a dirty tree fails — untracked file *and* modified producer source; `--allow-dirty` still stamps `not_reproducible` | pass |
| T3 | a failed git call fails closed — reproduces `core.bare=true`, confirming `status` exits 128 while `rev-parse HEAD` exits 0 and the failure *looks* clean | pass |
| T4 | a leaked `GIT_DIR` / `GIT_DIR+GIT_WORK_TREE` cannot forge a false-clean receipt; the clean tree reports its **own** commit, never the foreign one | pass |
| T5 | forecasts bit-identical across two runs of the real 2022 player fold — four targets, 22 columns, 5,563 rows each, identical sidecar digest, identical selected constants | pass |

Every fixture is a throwaway repository in a temp directory; no test touches this repository, its
worktrees, its configuration or any artifact. Nothing is scored — T5 compares forecast bytes to
forecast bytes, reads no outcome, computes no metric.

Confirmed in production: with `core.bare=false` restored, the repaired gate **refuses** the live
player worktree with `7 dirty path(s)`.

---

## 7. Summary of what the team thread may want to decide

| # | item | player program's view |
|---|---|---|
| 1 | regenerate `cbs_v12_team_oof/2`? | **no** — digests verify independently; regenerating would misrepresent history |
| 2 | adopt `clean_producer/2` in the team runner? | **recommended** — reviewed, tested, provenance-only |
| 3 | repair `gate_receipt.py`? | **recommended, and the highest-value item here** — it is unrepaired and its `certifies_this_commit` field would issue a false certification under the hook's own `GIT_DIR` |
| 4 | re-read the six A-receipts? | **not required** — all six report dirt and are therefore measured |
| 5 | record an erratum against v10–v14? | one exists at `experiments/player_program/ERRATUM_CLEAN_PRODUCER_1.md`. **The registrations themselves are not amended**, per `project_docs/SPEC_ERRATA.md` |

---

## 8. Supporting artifacts (all on the player branch)

* `experiments/player_program/ERRATUM_CLEAN_PRODUCER_1.md` — the erratum
* `experiments/player_program/test_failclosed_gate.py` — the five conditions
* `experiments/player_program/FAILCLOSED_GATE_TEST_RECEIPT.json` — 61/61
* `experiments/player_program/PHASE0_AUDIT_RECEIPT.json` — the original detection
* `experiments/player_program/preserved_uncommitted_d69aa02/` — the repair as found, with patches
  and hashes, before the player program touched it
