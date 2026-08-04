# I11_BLINDED_RESULT_PACKAGING — generic sealed-result and integrity-manifest tooling

**Epistemic status (verbatim from the node contract):**

> INFRASTRUCTURE. Enforces the seal mechanically rather than by convention.

Lane: operations · Type: implementation · Severity on failure: B
Write scope: `experiments/player_program/ops_lane/I11_BLINDED_RESULT_PACKAGING/` — nothing outside it was written.

---

## 1. What was delivered

| file | role |
|---|---|
| `sealed_package.py` | the library: manifest builder, `SealedWriter`, `SealGuard`, `verify_seal`, `open_seal` |
| `surface_probe.py` | the read-surface probe, shared by the tests and the demonstration so claim and measurement cannot drift |
| `TESTS.py` | 122 assertions, standalone, `main()` returns 1 on failure |
| `demo_seal.py` | end-to-end exercise against the **real** program artifacts; writes `MEASUREMENTS.json` and `demo_seal/` |
| `MEASUREMENTS.json` | every number in this report, machine-readable |
| `demo_seal/` | a real sealed directory: manifest, seal record, hash-chained open log, obfuscated payloads |

Nothing frozen was modified. `feature_gate.py`, `comparison_gate.py`, `gate_invocation.py`,
`receipt_integrity.py`, the registries, `PROGRAM_STATE.json`, `stage2a/` and the canonical `*_v1`
artifact directories are untouched — the only interaction with a frozen module is a **read-only
import** of `comparison_gate.row_digest`, with `sys.dont_write_bytecode` set for the duration so
that the import cannot even leave a `.pyc` beside a frozen file. Reusing the frozen digest function
is deliberate: a row set described by this manifest and the same row set described by the frozen
comparison gate produce the identical string (asserted in TESTS.py section 11).

---

## 2. Acceptance criteria, against measurement

Every number below was produced by one of exactly two commands:

```
A:  python experiments/player_program/ops_lane/I11_BLINDED_RESULT_PACKAGING/TESTS.py
B:  python experiments/player_program/ops_lane/I11_BLINDED_RESULT_PACKAGING/demo_seal.py
```

Command **A** exits 0 with **122 PASS / 0 FAIL**. Command **B** exits 0 and writes
`MEASUREMENTS.json`.

### 2.1 "a sealed directory cannot be read by the writing process"

Two independent layers, because one is not enough and pretending otherwise would be theatre.

**L1 — in-process read trap.** While a `SealedWriter` is open, `builtins.open`, `io.open`,
`os.open`, `os.listdir` and `os.scandir` are patched; any access to a path under the payload
directory that is not the writer's own API-mediated write raises `SealViolation` and is recorded.
`SealedWriter` itself exposes exactly four public members — `write_payload`, `write_json_payload`,
`finalize`, `violations` — and no read method at all. `write_payload` returns a 64-hex digest,
never bytes.

**L2 — at-rest obfuscation.** Payloads are stored XORed with a SHA-256 counter keystream derived
from public material (domain string, manifest digest, payload name, per-payload nonce). This is
**obfuscation, not confidentiality** — anyone holding the seal can derive the keystream. What it
buys is that a reader who gets *past* L1 still recovers no plaintext by accident. Getting plaintext
requires `open_seal()`, which logs.

Measured on the demonstration seal (command B, `MEASUREMENTS.json -> read_surface_probe`), with a
known marker string planted in the payload plaintext:

| surface | outcome |
|---|---|
| `builtins.open(rb)` · `builtins.open(w)` · `io.open(rb)` · `os.open(O_RDONLY)` | TRAPPED |
| `os.listdir` · `os.scandir` on the payload directory | TRAPPED |
| `pathlib.Path.read_bytes` · `read_text` · `iterdir` | TRAPPED |
| `shutil.copy` · `pandas.read_parquet` | TRAPPED |
| `pyarrow.OSFile` (native C file handle) | NOT TRAPPED — recovered **no** plaintext (L2 held) |
| a **separate python process** reading the file | NOT TRAPPED — recovered **no** plaintext (L2 held) |

Totals: **13 surfaces probed, 11 trapped, 2 not trapped, 0 leaked.**
At rest: plaintext 2,602 bytes, stored 2,626 bytes (8-byte magic + 16-byte nonce + payload); the
marker does not appear in the stored bytes; **0** of the plaintext's 8-byte windows occur in the
stored file. The same plaintext sealed twice produces different bytes (fresh nonce) — verified in A.

The demonstration seal's `SEAL_VIOLATIONS.jsonl` records **11** refused read attempts. That count is
11 *by construction* — the probe deliberately attacks its own seal. A real run's expected value is
0, and `finalize()` reports it, so a runner that peeked cannot hide it.

### 2.2 "the manifest binds code commit, data hashes, row universe, folds, K0 pairing and seeds"

All six are **required**. `build_manifest` raises `ManifestError` if any is missing or empty —
tested individually, six ways (A). `manifest_digest` is `sha256` over the canonical JSON of
`schema + run_id + target + bindings (+ extra)`. Tested in A: changing **any one** of the six
changes the digest; rebuilding with identical bindings reproduces it; `created_at` is deliberately
outside the digest so that the same run rebuilt later digests identically.

The bindings are not accepted on trust — each is measured or structurally checked:

| binding | what is enforced |
|---|---|
| `code_commit` | 40-hex sha required (`"HEAD"` is refused); branch required; `dirty` must be an explicit boolean; `require_clean_tree=True` refuses a dirty tree |
| `data_hashes` | every declared input is re-hashed from disk; a missing file is an error, never a null entry |
| `row_universe` | rows **and** clusters both carried; row keys must be unique; digests must agree with the counts they claim |
| `folds` | a cluster appearing in two folds is refused at construction; fold row/cluster totals must reconcile with the universe; a single fold is refused |
| `k0_pairing` | one matched control **per arm**; a control shared by two arms is refused; `K0_FLAT` named as a matched control is refused; `K0_FLAT` is recorded `diagnostic_only`; `K0_MATCHED` is the sole `authoritative_control`; the control is bound by the **digest of its specification record**, not by its name |
| `seeds` | explicit integers only — `None`, `1.5`, `"42"` and `True` are all refused |

Measured against the real program (command B):

* **code commit** `b6228a17d974691e21bdc0afa8226ce613461eac`, branch `player-model-program`,
  `dirty = true`, 14 dirty paths — read with read-only `git rev-parse` / `git status --porcelain`.
* **data hashes** for the five contract input artifacts plus the exposure artifact. The
  independently computed sha256 of `projected_exposure_v1/team_possession_prior_v1.parquet` is
  `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18`, which **agrees with the
  canonical hash recorded in `PROGRAM_STATE.json`**.
* **row universe** read out of that artifact under `pace_resolved == True`:
  **2,982 rows over 1,491 game clusters**, 8 unresolved rows excluded, rows-per-cluster histogram
  `{2: 1491}` — every cluster is exactly two team-game rows, none is a singleton. This reproduces
  the packet claim and independently agrees with P27's `M1_universe`.
  `row_digest = rows:n=2982:sha256=cadbe660c3af29e81c62b8f3bdf7bdd4`,
  `cluster_digest = clusters:n=1491:sha256=9ab675df6d4a037c20902af588b679b8`.
* **folds** under `SEASON_BLOCK`: 6 folds — 2021: 410 rows / 205 clusters, 2022: 478 / 239,
  2023: 520 / 260, 2024: 524 / 262, 2025: 620 / 310, 2026: 430 / 215. Totals reconcile to
  2,982 / 1,491. No cluster is split.
* **negative control**: a naive *row-level* random 5-fold (seed 20260804) over the same rows splits
  **1,227 of 1,491 clusters** across folds. `describe_folds` refuses it. This is the failure mode
  the check exists for, with a number attached.
* **K0 pairing** built from the real `P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_EXAMPLES.json`
  (sha256 `c959b0bc077b8e5b1829b435a278b15a77d473878fade24a829b08737c09fe39`): two arms, two
  distinct matched controls, each bound by the sha256 of its own `k0_matched/1` record.
* **seeds**: `{fold_seed: 20260804, bootstrap_seed: 902144, init_seed: 7}`.
* resulting **manifest digest**
  `71bbbf74e4644caeb8a968eb9c15e960edb0da92659b308ff4fc9f7db1f9b0b8`, stable across rebuild.

`verify_seal` re-derives that digest and fails if any bound field was altered afterwards — tested
in A by editing one seed inside a written `MANIFEST.json` (detected), flipping one bit of a stored
payload (detected), and deleting a declared output (detected, and named in the failure list).

### 2.3 "opening a seal is a separate, logged operation"

`verify_seal()` and `open_seal()` are different functions with different return types.
`verify_seal` streams payload bytes through `hashlib` and discards them; its result carries digests
and booleans only. Measured (B): the verification result **does not contain** the planted plaintext
marker, and it reports `discloses_payload_content: false`. This is the primitive that lets a
result-integrity verifier confirm "this is the preregistered run, and every declared output is
present" without learning which arm won.

`open_seal()` is the only route to plaintext, and it:

* refuses without an `actor`, `reason`, `authorization_ref` and `node_id` (four checks, A);
* refuses while a `SealGuard` is armed on the seal — **the writing process cannot open its own
  seal** — and writes no log entry for the refused attempt (A);
* refuses to open a seal that does not verify, and leaves the log untouched when it does (A);
* appends a hash-chained entry to `SEAL_OPEN_LOG.jsonl`, and fsyncs it, **before** returning any
  byte. The demonstration seal carries one real entry, `entry_hash f904473364ac...`, recording
  actor, reason, authorization reference, node, manifest digest, seal digest and the exact payloads
  disclosed. Round-tripped plaintext is byte-identical to what was sealed.

Editing a log line breaks the chain. Deleting the *last* line does not — a pure chain cannot see its
own truncation — so `SEAL_OPEN_HEAD.json` anchors the sequence number and head hash, and
verification fails when log and anchor disagree (measured message: *"open-log anchor says 2 open(s),
the log carries 1; an open record was removed"*). Removing the anchor is itself a failure. This
makes erasing an open take two coordinated edits rather than one; it is **not** tamper-proof, and
the durable anchor remains the coordinator's commit of both files.

---

## 3. Contradictions found

**C1 — `P39_RESULT_INTEGRITY` is contractually forbidden from reading the directory it is
contractually required to verify.** In `orchestration/PROGRAM_GRAPH.json`, that node's
`forbidden_inputs` is `["experiments/player_program/stage2b/SEALED_RESULTS"]`, while its title is
*"Verify sealed outputs without interpreting which arm won"* and its acceptance criteria are
*"exact code commit, data hashes, row universe, folds, K0 pairing and seeds all verify"* and
*"every declared output is present"*. Read literally, the node cannot satisfy its criteria without
violating its input restriction. I did not resolve this — resolving a node contract is not this
node's authority. I note only that `verify_seal()` is built to be exactly the reconciliation the
wording seems to want: it establishes both criteria while returning no payload content, and touches
only the public seal members plus a streaming digest pass. Whether that counts as "reading
`SEALED_RESULTS`" is a coordinator ruling, not a measurement.

**C2 — `P38_BLINDED_FIT` has empty `forbidden_inputs`.** The runner that writes `SEALED_RESULTS/`
is not contractually forbidden from reading it; its acceptance criterion *"results ... are not
opened by the runner"* is a behavioural claim with no declared enforcement. That is precisely the
gap this node's mandate names ("mechanically rather than by convention"), and `SealedWriter` closes
it — but only if P38 actually uses it. Adoption is not in my scope.

**C3 — the working tree is dirty.** The commit binding measured today is `b6228a1` with
`dirty: true` and 14 dirty paths. A seal built now with `require_clean_tree=True` would refuse;
built without it, the manifest records `dirty: true` and the dirty path list rather than silently
implying clean provenance. A real P38 seal should set `require_clean_tree=True`.

**C4 — `stage2b/SEALED_RESULTS/` does not exist.** It is my declared forbidden input and it is
absent from the worktree (`ls` returns "No such file or directory"). I therefore could not, and did
not, read it. This contradicts no document — it is recorded because "the forbidden thing was not
there to be read" is a stronger statement than "I chose not to read it".

---

## 4. What I could NOT establish

* **That a determined writing process cannot read its seal.** Not established, and not
  establishable: within one process, one filesystem and one privilege level, a writer can always
  reach bytes it wrote. Measured limit: 2 of 13 probed surfaces (a native `pyarrow.OSFile` handle
  and a separate Python process) get past L1. Both recovered no plaintext because of L2, but L2 is
  obfuscation from public material — a reader who *wants* the plaintext and knows the format can
  reconstruct it. What the mechanism actually guarantees is that **accidental** disclosure is
  impossible, and **deliberate** disclosure requires either a logged `open_seal()` or a
  reconstruction that leaves the seal's own record inconsistent with itself.
* **Complete read-surface coverage.** I probed 13 surfaces. `ctypes`/direct Win32 calls,
  memory-mapped files, `os.startfile`, and a shell-level `type`/`cat` were not probed. Every one of
  them is out-of-process or below the Python surface, so by construction they behave like the two
  measured misses.
* **That the tooling matches the real wave's arms.** No arm for the possession wave is registered,
  so the demonstration binds P26's two `EXAMPLE_*` K0_MATCHED records. The pairing rules are
  enforced against their real bytes; the arm identities are examples.
* **Whether P38/P39 will adopt this.** Shared adoption is a separate node
  (`O16_SHARED_SCHEMA_ADOPTION`, currently `USER_REQUIRED`). Nothing here amends a shared contract,
  and nothing here is imported by any existing module.
* **Anything about experimental results.** This node produced none, read none, and makes no
  comparative statement of any kind. All sealed payloads in `demo_seal/` are synthetic and labelled
  as such inside the seal itself.

---

## 5. Stop conditions and escalations

**No stop condition is tripped.** Nothing in this node changes the primary target, the K0 structure,
the inference structure, the candidate universe, the cutoff-valid feature set or the leakage status.
C1 and C2 are contract-consistency findings about the orchestration graph, not scientific findings.

**No escalation to the possession lane.** The one substantive measurement that touches the
possession evidence — 2,982 team-game rows over 1,491 game clusters, every cluster exactly two rows,
8 unresolved rows excluded — **reproduces** the packet claim and P27's independent measurement. It
confirms the historical feature evidence; it does not change it.

---

## 6. How a runner uses this

```python
import sealed_package as sp

manifest = sp.build_manifest(
    run_id=..., target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
    code_commit=sp.read_code_commit(repo_root),          # read-only git
    data_hashes=sp.hash_inputs([...], root=program),     # re-hashed from disk
    row_universe=sp.describe_universe(rows, clusters, ...),
    folds=sp.describe_folds(scheme=..., cluster_keys=..., fold_keys=...),
    k0_pairing=sp.describe_k0_pairing({arm_id: {...}}, k0_flat_id="K0_FLAT"),
    seeds={...}, require_clean_tree=True)

with sp.SealedWriter(seal_root, manifest, actor=..., node_id="P38_BLINDED_FIT") as w:
    for name, blob in outputs:
        w.write_payload(name, blob)     # returns a digest; there is no way to read it back
    w.finalize()                        # writes MANIFEST.json, SEAL.json, the open log, the anchor
```

The verifier calls `sp.verify_seal(seal_root)`. Only an adjudicator calls
`sp.open_seal(seal_root, actor=..., reason=..., authorization_ref=..., node_id=...)`, and that call
is on the record forever.
