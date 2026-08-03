# Erratum · `clean_producer/1` could report a clean tree it never measured

**Raised by:** the player model program, 2026-08-03
**Applies to:** `clean_producer/1`, the producer gate in `run_team_oof_v12_2.py` and (as committed
at `d69aa02`) `run_player_oof_v14.py`
**Superseded by:** `clean_producer/2`
**Historical registrations v10–v14 are NOT amended.** This erratum lives outside them, per the
convention in `project_docs/SPEC_ERRATA.md`: a registered specification is frozen, and corrections
live outside the frozen document.

---

## 1. The defect

`clean_producer/1` established working-tree cleanliness like this:

```python
dirty = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
```

`_git` is best-effort: it swallows a non-zero exit and returns `""`. **An empty porcelain status
is exactly what a clean tree returns.** So a `git status` that *failed* and a tree that was
*clean* produce the identical value, and the gate cannot tell them apart.

`git rev-parse HEAD` is a different matter — it does not need a work tree and frequently still
succeeds when `git status` does not. The receipt therefore carries a **real commit** alongside an
**unmeasured** cleanliness verdict, which is the worst available combination: the artifact looks
fully attributed.

### Two independent triggers, both observed

| trigger | what git does | observed |
|---|---|---|
| **`core.bare=true` on a normal checkout** | `git status` exits 128 (`fatal: this operation must be run in a work tree`); `git rev-parse HEAD` exits 0 | **measured in this repository on 2026-08-03**, in every worktree and in the main checkout |
| **inherited `GIT_DIR` + `GIT_WORK_TREE`** (a `pre-push` hook exports `GIT_DIR`, and this project's hook runs the whole Layer-A gate) | `git status` describes a *different* repository and can return empty | **reproduced in the test suite**: `GIT_DIR+GIT_WORK_TREE` yields an empty, false-clean status. (`GIT_DIR` alone yields foreign noise on git 2.55 — also wrong, differently) |

### Demonstration

Executed against a pristine checkout of `d69aa02` while `core.bare=true`:

```
ok:                         True
working_tree_clean_vs_head: True
n_dirty_paths:              0
commit:                     d69aa0250fc95cbebacecb821482734819bebf36
```

The tree actually had **98 dirty paths**.

## 2. What a `/1` receipt means, exactly

A `clean_producer/1` receipt reporting `n_dirty_paths: 0` is **an unmeasured claim, not a false
one.** It must be re-read, not discarded. Whether the tree was in fact clean is a separate
question that has to be settled by other evidence — see §4.

## 3. `clean_producer/2`

Three changes, all confined to the gate. **No prediction, fitting, selection, emission or
validation logic is touched**, and forecasts are bit-identical when the gate passes (§5, T5).

1. **`_git_checked`** — a non-zero git exit raises `DirtyProducer` instead of returning `""`.
   Absence of evidence of dirt is not evidence of cleanliness.
2. **`_git_env`** — `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`,
   `GIT_NAMESPACE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES` and
   `GIT_CEILING_DIRECTORIES` are stripped from the environment of every git call.
3. **Toplevel-matches-root** — `git rev-parse --show-toplevel` must resolve to the `--root` the
   run was given, or the gate refuses rather than reporting a verdict measured somewhere else.

Plus: the dirty refusal now happens **before** the receipt is constructed, so a refused run cannot
leave a half-built clean-looking receipt; `HEAD` must match `^[0-9a-f]{40}$` when the tree reports
clean; and the receipt records `git_toplevel_matched_root`, `inherited_git_env_scrubbed` and
`git_failure_is_a_refusal_not_a_clean_verdict` so a reader can see the gate *measured* rather than
merely *concluded*.

**Receipt versioning.** The preserved repair left `run_team_oof_v12_2.py` emitting
`clean_producer/1`, which would have made a measured verdict textually identical to an unmeasured
one. The player program bumped it to `/2` with `supersedes` and `superseded_because` fields, and
added the same fields to the player runner. That bump is a **player-program addition on top of the
preserved repair**, recorded here so the divergence from the team thread's uncommitted copy is
explicit.

## 4. What survives independently — `cbs_v12_team_oof/2`

The only fitted contract artifact in the repository. Its receipt is `clean_producer/1`
(`n_dirty_paths: 0`, commit `3b04be5`), so by §2 its cleanliness claim is unmeasured.

**Its reproducibility claim nevertheless holds, and does not depend on the gate.** The receipt
records a SHA-256 for each of the 19 producer sources, computed from the bytes on disk at runtime.
All 19 recompute **exactly** from `git show 3b04be5:<path>`, and the recorded
`producer_source_set_digest` `12ce0b88…` recomputes exactly from those 19:

```
match 19   mismatch 0   missing 0
SET DIGEST MATCHES: True
```

Because the runtime digests were taken from disk and equal the commit's blobs, **the producing
code on disk was byte-identical to `3b04be5`** — which is the guarantee that matters. What remains
unverified is only the weaker, broader claim that *no other file anywhere in the tree* differed.

Two further points of record. The retained generating checkout
`_gen_3b04be5__20260803T011852Z` **no longer exists on disk** — `find` over the repository returns
no `_gen_*` directory — so it cannot now be re-inspected. And the exposure window is undetermined:
this program cannot establish when `core.bare=true` was set relative to the run's completion at
`2026-08-03T01:20:04Z`. Neither point changes the digest verification above, which is why that
verification is the one to rely on.

**The team thread decides which receipts require regeneration.** This erratum makes no such
determination.

## 5. Evidence

`experiments/player_program/test_failclosed_gate.py` — **61/61 checks pass**, receipt at
`FAILCLOSED_GATE_TEST_RECEIPT.json`. Both runners, five conditions:

| | condition | result |
|---|---|---|
| **T1** | a genuinely clean tree passes, and the receipt asserts it measured one | pass |
| **T2** | a dirty tree fails — untracked file *and* modified producer source; `--allow-dirty` still stamps `not_reproducible` | pass |
| **T3** | a failed git command fails closed — reproduces `core.bare=true` exactly, confirming `status` exits 128 while `rev-parse HEAD` exits 0 and the failure *looks* like a clean status | pass |
| **T4** | a leaked `GIT_DIR` / `GIT_DIR+GIT_WORK_TREE` cannot forge a false-clean receipt; the clean tree reports its **own** commit, never the foreign one | pass |
| **T5** | predictions bit-identical across two runs of the real 2022 player fold — all four targets, all 22 columns, 5,563 rows each, identical sidecar digest and identical selected constants | pass |

Every fixture is a throwaway repository in a temp directory. No test touches this repository, its
worktrees, its configuration or any artifact. Nothing is scored: T5 compares forecast bytes to
forecast bytes, reads no outcome and computes no metric.

## 6. Confirmed in production conditions

With `core.bare=false` restored, `require_clean_producer` on the live player worktree now
**refuses** with `7 dirty path(s) relative to d69aa02` — correctly, since the repair itself was
applied there. The gate fails closed where it previously would have reported a clean tree.
