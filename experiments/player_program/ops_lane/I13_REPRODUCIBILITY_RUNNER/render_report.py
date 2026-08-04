#!/usr/bin/env python3
"""render_report.py — emit REPORT.md for this node.

The report is kept in a renderer rather than hand-typed so the epistemic-status line and the file
list stay in one place, and so regenerating it is a command rather than an edit.

Run:  python render_report.py
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

from pathlib import Path                                                      # noqa: E402

HERE = Path(__file__).resolve().parent

REPORT = r"""# I13_REPRODUCIBILITY_RUNNER — Deterministic commands, seed manifests and artifact reconciliation

**Epistemic status (verbatim from the node brief):**

> INFRASTRUCTURE. Makes a run rerunnable and checkable. Proves nothing scientific.

**Lane:** operations · **Type:** implementation · **Severity on failure:** B · **Node write
scope:** `experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/` — nothing outside it was
written, no git command other than read-only `rev-parse` / `log` / `status` / `ls-files` was run,
and no frozen artifact, gate, registry or `PROGRAM_STATE.json` was touched.

Every number below is reproduced in `MEASUREMENTS.json`, which records the value **and the call
that produced it**. Regenerate the whole set with
`python experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/build_measurements.py`.

---

## 0. Headline

A real run of this program now reproduces **byte-identically from its manifest**, and the three
things the manifest binds — the **seed**, the **code commit** and the **input hashes** — are each
checked on replay rather than merely written down. A divergence in any of them is a typed failure
that raises, sets the verdict to `FAIL`, and exits the CLI non-zero. There is no code path in the
runner that returns `PASS` while a blocking finding is present, and no comparison anywhere in it
uses a tolerance: outputs are compared as sha256 over bytes.

Recorded run: `runs/universe_census/` — a structural census of the frozen team-game possession
universe plus a seeded cluster bootstrap, produced through the program's own read-only loader.

| | |
|---|---|
| outputs byte-identical on replay | **2 / 2** |
| blocking findings | **0** |
| context findings | **1** (`code_commit_moved` — see below; it fired for real) |
| seed bound | `20260804`, plus `PYTHONHASHSEED=0` |
| commit bound | `b6228a17d974691e21bdc0afa8226ce613461eac` (`player-model-program`) |
| inputs bound by sha256 | **5** |
| source files bound by sha256 | **4** (2 declared, **2 discovered by measuring the import closure**) |
| manifest signed by digest | `e9e1f067ba9f8a71...` |
| tests | **61 checks, 0 failed, 0 skipped** (`python TESTS.py`, exit 0) |

The negative control matters as much as the positive one: incrementing **only** the recorded seed
and re-signing the manifest moves `cluster_bootstrap.csv` and the verdict becomes `FAIL`. The seed
binding is load-bearing, not decorative.

**The class C mechanism fired for real during this node's own session.** A sibling node's
coordinator committed while this node was running, so live `HEAD` advanced past the commit the
manifest binds — first to `7c5fe7d2...` and onward. `verify()` reported `code_commit_moved`, every
bound source byte was unchanged, both outputs still came back byte-identical, and the verdict
became `PASS_WITH_CONTEXT_FINDINGS` rather than a bare `PASS`. That is exactly the designed
behaviour (section 3), observed rather than asserted.

---

## 1. What I built

| File | What it is |
|---|---|
| `repro_runner.py` | the runner: `record()`, `verify()`, `reconcile()`, and a CLI |
| `_repro_exec.py` | the execution wrapper the runner spawns — injects seeds before the payload gets control, and reports the import closure the interpreter actually built |
| `payload_universe_census.py` | the REAL recorded run: read-only census of the possession universe + a seeded cluster bootstrap |
| `record_real_run.py` | records `runs/universe_census/` (separate from `TESTS.py` on purpose — see section 5) |
| `runs/universe_census/MANIFEST.json` | the recorded manifest, signed by digest |
| `runs/universe_census/outputs/` | the recorded bytes the replay must return |
| `build_measurements.py` -> `MEASUREMENTS.json` | every figure in this report, with its command |
| `render_report.py` | emits this file |
| `TESTS.py` | 14 synthetic cases + 3 real-run cases |

### What a manifest binds

`argv` and working directory · the seed and `PYTHONHASHSEED` (both **injected into the child
environment**, not observed after the fact) · the repository commit, branch and per-path
tracked/dirty state · the sha256 of every source file the run **actually imported** from the
program tree · the sha256 of every declared input, hashed **before and after** the run · the
sha256 and byte length of every file the run emitted · the exit code · a `run_id` (uuid4) · a
`manifest_digest` over the canonical form of all of the above.

---

## 2. What I measured, and with what

### 2.1 Byte-identical reproduction — the primary acceptance criterion

    python experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/repro_runner.py \
        verify experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/runs/universe_census/MANIFEST.json

`2/2 outputs byte-identical, 0 blocking`, exit code 0. The verdict was a bare `PASS` while the
recorded commit was still live HEAD, and `PASS_WITH_CONTEXT_FINDINGS` afterwards, once a sibling
node's commit advanced HEAD.

| output | recorded sha256 | bytes |
|---|---|---|
| `universe_census.json` | `fac42f723041530cf277ab2c7f3196cbe82add766c5f3eaca976ebe29dfb515a` | 1,544 |
| `cluster_bootstrap.csv` | `00c75f760f650ffa58b19d4596437430685a96b7a2444a56bceca8ca8612d847` | 17,442 |

The replay writes to a **fresh scratch directory** that is deleted afterwards, so it cannot be
handed the recorded bytes by accident. A second independent `verify()` returned the same two
hashes again (`MEASUREMENTS.json` -> *"a second independent replay returns the same bytes again"*,
`identical_to_first_replay: true`), so the pass is not a single lucky execution.

### 2.2 The seed binding is load-bearing

Copy the manifest, increment `seeds.seed` from `20260804` to `20260805`, re-sign it, verify:

* `verdict: FAIL`
* diverged: `cluster_bootstrap.csv`
* held: `universe_census.json` (it has no stochastic step, which is exactly why the bootstrap is
  in the payload — without it a runner that silently dropped the seed would still show green)

### 2.3 Provenance is measured, not narrated

`record_real_run.py` declared **two** sources: the payload and the wrapper. The run bound **four**.
The extra two — `experiments/player_program/possession_features.py` and
`experiments/player_program/construction_receipt.py` — were discovered by walking `sys.modules`
inside the child process after the payload finished, and were then re-hashed **from disk by the
runner**, not trusted from the wrapper's report. A file that changed between import and post-run
hashing is `source_mutated_during_run` and aborts the record.

This is the `construction_receipt.py` lesson (a caller that hashes its own source file and
re-digests the frame it is already holding has demonstrated nothing) applied at the run layer. If
a later replay imports program code the manifest does not bind, that is `unbound_imported_source`
— a blocking failure, tested in T8.

### 2.4 Four-way artifact reconciliation

    python repro_runner.py reconcile runs/universe_census/MANIFEST.json

For every input the run consumed, four hashes are compared where they exist: **the manifest**,
**the bytes on disk now**, **`PROGRAM_STATE.json`'s published hash**, and **the artifact's own
receipt**. Result: **0 disagreements across 5 inputs**, verdict `PASS`.

| input | verdict | independent hashes |
|---|---|---|
| `projected_exposure_v1/team_possession_prior_v1.parquet` | AGREE | 3 |
| `possessions_v2/possessions_raw_v2.parquet` | AGREE | 2 |
| `projected_exposure_v1/PROJECTED_EXPOSURE_RECEIPT.json` | **UNCORROBORATED** | 1 |
| `projected_exposure_v1/PROJECTED_EXPOSURE_VALIDATION.json` | **UNCORROBORATED** | 1 |
| `possessions_v2/POSSESSION_INTEGRITY_RECEIPT_V2.json` | **UNCORROBORATED** | 1 |

`UNCORROBORATED` is deliberately **not** a pass. It means the manifest and the disk agree and
nothing else on disk publishes a hash for that file, so a coordinated change to both would be
invisible to this check. Reporting those three as `AGREE` would have been the comfortable lie.

Related, and clean: all four hashes `PROGRAM_STATE.json` publishes under `shared_contracts`
(`feature_gate`, `comparison_gate`, `gate_invocation`, `receipt_integrity`) still match the bytes
on disk.

### 2.5 The recorded census (what the real run actually computed)

Read out of `runs/universe_census/outputs/universe_census.json`, produced by
`possession_features.load_universe()` read-only:

* **2,982 team-game rows** over **1,491 game clusters** — matching the universe declared in the
  brief. `cluster_size_distribution = {"2": 1491}`: every game cluster holds exactly two rows, so
  no game is split by any draw.
* `universe_contract_id = team_possession_universe/1`;
  `row_universe_digest = raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371`
* seasons 2021-2026
* `realised_team_off_possessions_reg_equiv`, read **as a column of numbers** to size a sampling
  distribution: n=2982, mean 79.28757732, sd(ddof=1) 3.90806733, min 66.0, max 94.0

**No model is fitted, no arm is scored, no prediction is contrasted with an outcome, and nothing
under `stage2b/SEALED_RESULTS/` was opened.** The bootstrap resamples game clusters, never rows.

---

## 3. How a divergence is reported — and why one class does not block

Three severity classes, all declared in code, all asserted by the tests:

| class | meaning | blocking |
|---|---|---|
| **A — REPRODUCTION** | the bytes did not come back: `output_hash_divergence`, `output_missing`, `output_extra`, `exit_code_divergence`, `command_failed` | **yes** |
| **B — BINDING INTEGRITY** | the manifest stopped describing the run: `manifest_tampered`, `manifest_unsigned`, `seed_binding_absent`, `input_hash_divergence`, `input_missing`, `input_mutated_by_run`, `source_hash_divergence`, `source_missing`, `source_mutated_during_run`, `unbound_imported_source` | **yes, even if the outputs matched** |
| **C — CONTEXT** | the world moved in a way the bytes survived: `code_commit_moved`, `code_tracking_status_changed`, `worktree_dirty`, `environment_divergence` | reported, never dropped |

**Why the commit is class C, stated plainly rather than buried.** The commit *is* bound: it is
recorded, re-read from git on replay, and compared. But a manifest recorded inside a node is
always verified *after* the coordinator commits that node — so if commit movement were blocking,
every manifest in this repository would self-invalidate the moment it was committed, and the
runner would be useless. Content hashes therefore decide and the commit corroborates, the same
ordering `receipt_integrity.py` uses for mtime versus hash. A commit that moved **while any bound
source byte also moved** is not class C: it is `source_hash_divergence`, class B, and it fails.

A class C finding is never swallowed. The verdict becomes `PASS_WITH_CONTEXT_FINDINGS`, never a
bare `PASS`, so a reader cannot mistake a moved world for an unmoved one. T4b asserts exactly this.

**Observed, then predicted, for this node's own manifest.** `code_commit_moved` already fired
during this session when a sibling node's coordinator advanced HEAD: 2/2 outputs byte-identical,
0 blocking, verdict `PASS_WITH_CONTEXT_FINDINGS`, `TESTS.py` still exit 0. At record time
`payload_universe_census.py` and `_repro_exec.py` were untracked, so once the coordinator commits
*this* node, `code_tracking_status_changed` will join it and the verdict will stay
`PASS_WITH_CONTEXT_FINDINGS`. If instead any bound source *content* changes, that becomes
`source_hash_divergence` and T11 fails. Written here so nobody later mistakes the context findings
for a defect — or the absence of a blocking one for the absence of a check.

---

## 4. Tests

    python experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/TESTS.py

**61 checks, 0 failed, 0 skipped, exit 0.** T1-T10 are hermetic and synthetic (a throwaway tree in
the OS temp directory; no program artifact is touched). T11-T13 replay the real run and report
SKIP rather than FAIL if the frozen artifacts are absent.

| test | what it holds open |
|---|---|
| T1 | a recorded run reproduces byte-identically, with **zero** findings |
| T2 / T2b | a changed seed FAILS as `output_hash_divergence`; a manifest with no seed is rejected |
| T3 / T3b / T3c | a changed input, a vanished input, and a run that writes to its own declared input |
| T4 / T4b | changed source content FAILS; a commit-only move is REPORTED and is not a bare PASS |
| T5 | a genuinely nondeterministic payload (fresh uuid per run) FAILS — the runner does not rubber-stamp |
| T6 | a command exiting non-zero never becomes a recorded run |
| T7 | an edited manifest is caught (`manifest_tampered`); a manifest with no digest is caught |
| T8 | the import closure is measured; dropping a discovered source FAILS |
| T9 | the output **set** is bound: both `output_missing` and `output_extra` fail |
| T10 | `verify()` raises by default, the CLI exits 1, the severity map is total, and no finding escapes the declared vocabulary |
| T11-T13 | the real run: byte-identical replay, bindings present, four-way reconciliation |

---

## 5. Design decisions a reviewer should be able to attack

* **Recording and verifying are different scripts.** `record_real_run.py` overwrites the manifest;
  `TESTS.py` only ever calls `verify()`. Verification must never be able to repair its own subject.
* **`record()` refuses to write a manifest for a failed or input-mutating run.** A manifest for a
  run that did not succeed is worse than none.
* **The payload refuses to run unseeded.** No `REPRO_SEED` in the environment, exit 2.
* **`PYTHONDONTWRITEBYTECODE=1` in every child**, and `sys.dont_write_bytecode = True` at the top
  of every module here, so no `.pyc` is written outside this node's directory.
* **The git helper refuses any non-read-only subcommand** at the call site
  (`_READ_ONLY_GIT = {rev-parse, log, status, ls-files}`); anything else raises.
* **Determinism rules in the payload:** no wall-clock, hostname, pid or absolute path in any
  output; JSON with sorted keys; floats rounded to a fixed number of decimals *before* formatting;
  explicit newline control on every write. Parquet was deliberately **not** used as an output
  format.

---

## 6. What I could NOT establish

* **That this run reproduces anywhere but here.** Verified on CPython 3.13.14 / Windows / AMD64
  with numpy 2.5.1, pandas 3.0.5, pyarrow 25.0.0. Cross-platform and cross-version reproduction is
  untested. `environment_divergence` will *report* a change but the runner cannot promise the bytes
  survive it.
* **That the payload has no nondeterminism finer than the files it writes.** Reproduction is
  demonstrated at the granularity of the emitted bytes. A difference that never reaches an output
  file is invisible to this method, by construction.
* **That the recorded run was executed rather than copied forward** — the general problem
  `receipt_integrity.py` names `fresh_execution_unprovable`. This runner *narrows* it, because the
  manifest carries a per-execution `run_id` (uuid4) and `verify()` genuinely re-executes; but a
  manifest is still byte-for-byte what an honest rerun would have written, so the manifest alone
  cannot prove its own freshness.
* **Whether any other manifest in the program verifies anything.** Section 7.4 reports a keyword
  scan of the four other files named `MANIFEST.json`. I did not read their semantics, and three of
  the four were being written by sibling nodes *while this node ran*.
* **Anything about model performance.** Out of scope by rule and by choice; nothing under
  `stage2b/SEALED_RESULTS/` was read.

---

## 7. Findings about the tree (not about this node)

Neither 7.1 nor 7.2 is a contradiction between a document and the bytes — every hash I checked
agrees with every other hash I could find for the same file. They are **coverage gaps in the
checking apparatus**, measured, and recorded here rather than fixed, because fixing either would
mean editing a registry or a shared gate.

**7.1 — The artifact the primary target is computed from is not in the registered artifact set.**
`possessions_raw_v2.parquet` is the file `possession_features._realised_offensive_possessions()`
reads to build `realised_team_off_possessions_reg_equiv`. The string `possessions_raw_v2` does not
appear anywhere in `PROGRAM_STATE.json`, whose `canonical_artifacts` publishes exactly three
families (`projected_player_possessions/1`, `canonical_player_events/1`,
`player_turnover_targets/1`), and the file is not in `receipt_integrity.FAMILIES` either — so no
program-level sweep binds it. It *is* receipted locally, and that receipt is currently correct:
`POSSESSION_INTEGRITY_RECEIPT_V2.json -> integrity.artifact_sha256` is
`7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a`, which equals the sha256 of the
bytes on disk. Nothing has drifted. What is missing is the *watchman*, not the agreement.

**7.2 — A sibling artifact's bytes are bound by nothing at all.**
`possessions_v2/player_season_possessions_v2.parquet` (sha256
`62ad07849ebd832f4852e314ad2368cfc08c2103871c14b06452c811022d3a58`) has no hash in the receipt that
sits in its own directory, and none in `PROGRAM_STATE.json`. The runner's real run does not consume
it, so this is reported, not acted on.

**7.3 — Not a contradiction, and worth stating so nobody logs it as one.**
`PROGRAM_STATE.generated_from.head` is `64ebf722...` with `working_tree_state: "clean"`, while live
HEAD is `b6228a17...` with untracked lane directories. `PROGRAM_STATE.json` says of itself that it
is authoritative for scientific state and **not** for live repository state, and explains that a
generated file cannot record the hash of the commit that contains it. The runner therefore reads
the commit from git and never from `PROGRAM_STATE.json`.

**7.4 — How seeds were bound before this node.** 13 `.py` files under
`experiments/player_program/` (excluding this node and the sealed directory) construct an RNG; each
carries its seed as a literal in source. Four other files are named `MANIFEST.json`; a keyword scan
finds that one of them — `ops_lane/I11_BLINDED_RESULT_PACKAGING/demo_seal/MANIFEST.json`, written
by a node running concurrently with this one — also mentions a seed, a commit and sha256. The other
three mention sha256 only. This is a keyword scan and is explicitly **not** a claim about what any
of those manifests verifies.

---

## 8. Stop conditions

**None tripped.** Nothing here changes the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set, or the leakage status. The runner
computes no feature, admits no field, and makes no cutoff-validity claim. Sections 7.1 and 7.2 are
provenance-coverage gaps in which every hash that exists agrees with every other hash that exists;
they change no historical feature evidence, which is why they are reported here and not escalated.

I confirmed in passing that `stage2a/V2_STOP_CONDITION.json` carries **nine** findings keyed
`S1_...` through `S9_...`, matching the brief.

---

## 9. How to use this

```
# verify a recorded run reproduces (exit 1 on any blocking divergence)
python experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/repro_runner.py \
    verify  experiments/player_program/ops_lane/I13_REPRODUCIBILITY_RUNNER/runs/universe_census/MANIFEST.json

# read the bindings without re-executing
python .../repro_runner.py inspect   .../runs/universe_census/MANIFEST.json

# four-way artifact reconciliation of a run's inputs
python .../repro_runner.py reconcile .../runs/universe_census/MANIFEST.json
```

To record a new run, import `repro_runner` and call `record(run_dir, payload=..., inputs={...},
seed=..., argv_tail=["--out", "{OUT}"])`. `{OUT}` is the only token that differs between the
recorded run and its replay, so the replay always writes somewhere the recorded bytes are not.
"""


def main() -> int:
    p = HERE / "REPORT.md"
    with p.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(REPORT)
    print(f"wrote {p}  ({len(REPORT)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
