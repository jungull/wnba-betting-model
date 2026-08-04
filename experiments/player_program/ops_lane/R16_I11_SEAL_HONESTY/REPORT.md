# R16_I11_SEAL_HONESTY — obfuscation is not blinding

**Epistemic status (verbatim from the node contract):**

> REMEDIATION of an OVERSTATED ACCEPTANCE CRITERION. An independent verifier reconstructed the
> plaintext of both sealed payloads in about ten lines from public inputs. Blinding for the
> possession experiment rests on PROCESS separation enforced by the graph, not on cryptography;
> this node removes the temptation to treat the crypto as a second line of defence when it is not
> one.

Lane: operations · Type: implementation · Severity on failure: B · Role: blinding infrastructure
engineer
Write scope: `experiments/player_program/ops_lane/R16_I11_SEAL_HONESTY/` — nothing outside it was
written. I11's directory was read only, and section [5] of `TESTS.py` proves that by hash.

Measured against worktree `player-model-program` at HEAD `e82ee721f6aef78f3013952af043e2ba60ecd06e`,
Python 3.13.14. Every number below came from one command:

```
python experiments/player_program/ops_lane/R16_I11_SEAL_HONESTY/TESTS.py
```

which prints each assertion, then a `MEASURED:` block containing the raw values quoted here.

---

## 1. The finding, stated plainly

I11 delivered two things. One of them is sound and this node keeps it. The other is not what its
report says it is, and this node withdraws it.

**Sound, retained:** the *manifest binding*. Six bindings, all mandatory, all digested, all
tamper-evident. Verified again here against I11's own delivered demonstration seal — see §4.

**Withdrawn:** the acceptance criterion **"a sealed directory cannot be read by the writing
process"**. It is **WITHDRAWN**, not weakened and not restated. It was never met. §2 and §3
demonstrate that as executable tests that pass while the defect exists. §5 states the guarantee
that replaces it.

The distinction that got lost in I11's report is between *integrity* and *disclosure*. The seal is
strongly tamper-evident and always was. It provides no barrier to disclosure at all — not a weak
one, none — because every input needed to invert the at-rest transform is written into the sealed
directory beside the payload, in the clear, by the writer.

---

## 2. ATTACK 1 — the whole plaintext of both delivered payloads, from public bytes

`TESTS.py` section [1]. It calls **no** I11 code. It imports `hashlib`, `json` and `pathlib`.

The inversion is one function, `deobfuscate()` in `TESTS.py`. Measured length: **5 statement
lines** (`MEASURED: attack_core_lines = 5`), counted by the suite itself rather than by eye. That
is the same order as the "about ten lines" the independent verifier reported; I did not take the
verifier's figure, I counted my own.

Inputs it consumed, and nothing else:

| input | where it comes from | is it withheld from a reader? |
|---|---|---|
| the domain-separation string | a literal in the committed `sealed_package.py` | no — asserted present in the published source by the test |
| `manifest_digest` | `demo_seal/MANIFEST.json`, a declared **public member** of the seal | no |
| the payload name | the stored filename, minus `.sealed` | no |
| the per-payload nonce | bytes 8..24 of the stored file itself | no — and it is *also* written a second time into `SEAL.json` |

No secret material is involved at any step.

Results, both payloads of I11's real `demo_seal/`:

| payload | declared `n_bytes` | recovered bytes | sha256 of recovery vs the seal's own `plaintext_sha256` |
|---|---|---|---|
| `synthetic_fold_table.json` | 129 | 129 | matches `279cdec5…` |
| `synthetic_predictions.bin` | 2602 | 2602 | matches `40ec4585…` |

`MEASURED: payloads_reconstructed = 2`, `plaintext_bytes_recovered = 2731`. The marker string I11
planted in the plaintext, `I11_SYNTHETIC_PAYLOAD_MARKER_NOT_A_RESULT`, is legible in both
recoveries. No `open_seal()` call was made; no actor, reason, authorization reference or node id
was presented; `SEAL_OPEN_LOG.jsonl` gained no entry, because nothing in the seal was invoked.

A second run of the same attack using **only** `MANIFEST.json` and the `.sealed` bytes — discarding
`SEAL.json` entirely — produced byte-identical output. `SEAL.json` is used in the test purely to
*check* the recovery against the seal's own declaration.

The payloads here are synthetic by construction, and I11 labelled them so inside the seal. That is
the only reason this attack is safe to publish: had `demo_seal/` contained a real comparative
result, running section [1] would itself have been a blinding violation. That property of the
attack is a fact about I11's demonstration data, not a property of the mechanism.

---

## 3. ATTACK 2 — the writing process reads its own payload, guard armed, leaving no trace

`TESTS.py` section [2]. This is the criterion's own words tested literally.

A fresh `SealedWriter` is opened on a temporary directory, so I11's bytes are untouched. Inside the
`with` block — read trap armed, payload written, seal not yet finalized — the writing process reads
its own stored payload and inverts it.

The bypass is a single stdlib call: **`_io.open`**. `SealGuard._install()` rebinds `builtins.open`,
`io.open`, `os.open`, `os.listdir` and `os.scandir`. `io.open` *is* `_io.open`; rebinding the name
in the `io` namespace leaves the C function reachable under its own module. The test asserts
`io.open is not _io.open` while the guard is armed, which is exactly the rebinding that makes the
bypass work.

Measured, inside the guarded block:

| quantity | value |
|---|---|
| stored bytes read through `_io.open` | 1,950 |
| plaintext recovered, byte-identical to what was written | 1,926 |
| planted marker legible to the writer | yes |
| violations recorded by the guard for this read | **0** |

Measured after `finalize()`:

| the seal's own record | value |
|---|---|
| `SEAL_VIOLATIONS.jsonl` lines | **0** |
| `SEAL.json → writer_read_attempts` | **0** |
| `SEAL_OPEN_LOG.jsonl` entries | **0** |
| `verify_seal(root)["ok"]` | **True** |

So the peeked seal is indistinguishable, by every artifact the seal produces about itself, from a
seal that was never peeked.

**Positive control (section [3]).** L1 is not vacuous, and this report does not claim it is. Of six
in-process surfaces probed on a live guarded seal, five raise `SealViolation`: `builtins.open`,
`io.open`, `os.open`, `os.listdir`, `pathlib.Path.read_bytes`. `_io.open` is the one that does not.
`MEASURED: l1_trapped` / `l1_untrapped` carry the lists.

**Proving that negative.** The claim "`_io` was not among I11's probed surfaces" is a negative, and
this program has already produced one manufactured negative, so the test does not assert it bare:
it asserts that the string `_io` is absent from `surface_probe.py` **and** that the same search
finds `io.open`, which is present. An empty result from a matcher that finds nothing at all would
fail this assertion.

---

## 4. What I11 got right, re-measured and retained

`TESTS.py` section [4], run against a **copy** of `demo_seal/` so that I11's bytes stay frozen.

* `verify_seal()` on the seal exactly as I11 delivered it: `ok = True`, empty failure list.
* All six bindings present: `code_commit`, `data_hashes`, `row_universe`, `folds`, `k0_pairing`,
  `seeds`.
* `manifest_digest_of(manifest)` recomputes the recorded digest `71bbbf74e4644cae…` from the
  bindings alone.
* The row-universe digest strings re-parse to **2,982 rows over 1,491 game clusters**, which is the
  universe the contract states. I rederived these from the digest strings the manifest carries; I
  did not re-read the exposure artifact, so this is a check of the manifest's internal consistency,
  not an independent recount of the parquet. I11 did that recount; I did not repeat it.
* Three tamper classes, each on its own copy, each detected: editing a bound seed inside
  `MANIFEST.json`; flipping one bit of a stored payload; deleting a declared output.
* And the point of the whole node: after ATTACK 1 has recovered both plaintexts, `verify_seal()`
  still returns `ok = True`. Integrity and disclosure are independent properties of this design.
  Only the first one is real.

**The manifest binding is retained without amendment.** Nothing in this node changes
`sealed_package.py`, and nothing here argues against using it. A runner should still bind all six.

---

## 5. The replacement: what the graph actually enforces

The withdrawn criterion is replaced by a **process-separation** guarantee. I measured what that
guarantee actually consists of rather than assuming it (`TESTS.py` section [6]).

**What is real, measured from `PROGRAM_GRAPH.json` and the prompt files:**

1. 64 nodes, and every node has a **unique `agent_prompt_path`**. One node is one agent context.
2. `P38_BLINDED_FIT` (writes `stage2b/SEALED_RESULTS/`) and `P39_RESULT_INTEGRITY` (writes
   `stage2b/P39_RESULT_INTEGRITY/`) are distinct nodes with **disjoint write scopes**, and P39
   lists P38 in `dependencies`, so they can never be dispatched concurrently.
3. Standing rule 8 — *"you may not read anything under
   `experiments/player_program/stage2b/SEALED_RESULTS/`"* — is rendered into **64 of 64** generated
   prompts, P38's included (`MEASURED: prompts_carrying_rule8 = 64`).
4. `GRAPH_POLICY.md` §7 states the sequence in prose: the runner writes into a sealed result
   directory, a separate result-integrity node verifies the bindings, and only then may a separate
   adjudication node open results.

**What is not real, and must stop being cited as if it were:**

5. `forbidden_inputs` is a **declaration, not an enforcement**. The string occurs at exactly five
   places in `orchestration/scripts/`: `graph_lib.py:459` (schema field list), `seed_graph.py:79`
   (seeding default), `generate_prompts.py:143` (rendering it into prompt text), and
   `validate_graph.py:112,114` (checking that a path is not simultaneously declared forbidden and
   readable). None of the five reads, blocks, sandboxes or audits a file at run time. The test
   proves this negative by asserting the search is non-empty first.
6. `P38_BLINDED_FIT` is the **only one of the 64 nodes whose `forbidden_inputs` is empty**
   (`MEASURED: nodes_with_empty_forbidden_inputs = ['P38_BLINDED_FIT']`), and it is precisely the
   node that writes the sealed results. Its `allowed_read_paths` is `experiments/player_program/`,
   which contains `stage2b/SEALED_RESULTS/`.
7. `validate_graph.py`'s audit-independence check (*"an audit node may not be the implementation
   node it audits"*) skips the P38 → P39 pair: it only examines dependencies whose `type` is
   `"implementation"`, and P38's declared `type` is `"experiment"`.

**The honest statement of the guarantee, which replaces the withdrawn criterion:**

> A sealed result directory is not read by the writing process **because the writing process is a
> separate, single-purpose agent context whose prompt forbids it, whose declared write scope is
> disjoint from the verifier's, and whose output is integrity-bound by a manifest that makes any
> later substitution detectable.** The guarantee is procedural and its enforcement is at dispatch
> and review time. It is not a filesystem control and it is not a mathematical one. A writer that
> disregards its prompt is not stopped by the seal, and the seal will not record that it happened.

That is a weaker guarantee than I11's report implied, and it is the true one. It is also not
worthless: it is the same class of guarantee the rest of this program's blinding rests on, and it
is auditable — the prompt text is committed, the write scopes are committed, and the manifest makes
a *swapped* result detectable even though it cannot make a *read* result detectable.

---

## 6. Claims of I11's report that this node supersedes

Each fragment below is quoted verbatim from
`ops_lane/I11_BLINDED_RESULT_PACKAGING/REPORT.md`. `TESTS.py` section [7] asserts that each one
really does occur there — so that this is a correction and not a straw man — and that each appears
here with its verdict.

| I11's words | verdict | why |
|---|---|---|
| "Two independent layers, because one is not enough and pretending otherwise would be theatre." | **WITHDRAWN** | L2 is not a second layer against a reader. It is a formatting step whose inverse is published beside it. Both layers fall to §2 and §3. |
| "Totals: **13 surfaces probed, 11 trapped, 2 not trapped, 0 leaked.**" | **CORRECTED** | "0 leaked" is an artifact of the scoring rule. `surface_probe._probe` scores a surface as no-leak when the *literal marker* is absent from the returned bytes. The returned bytes were the plaintext, one published transform away. Under a scoring rule that asks "could the caller obtain the plaintext", all 13 leak, and so does a 14th (`_io.open`) that was not probed. |
| "so a runner that peeked cannot hide it." | **WITHDRAWN** | Measured in §3: a runner that peeks via `_io.open` produces `writer_read_attempts = 0` and an empty violation file. There is nothing to hide. |
| "so by construction they behave like the two measured misses." | **WITHDRAWN** | The unprobed surfaces were dismissed as all being out-of-process or below the Python surface. `_io.open` is neither: it is in-process, in the standard library, and reached by ordinary Python. The dismissal was reasoning, not measurement, and it was wrong. |
| "the writing process cannot open its own seal" | **NARROWED** | True of `open_seal()`, which does refuse while a guard is armed. False of *obtaining the plaintext*, which is what the criterion is about. The sentence is accurate about the API and misleading about the property. |

I11's report also states, correctly and to its credit, that the at-rest layer is obfuscation rather
than a disclosure control, that the keystream is derivable by anyone holding the seal, and that a
determined writing process cannot be stopped. Those statements are consistent with everything
measured here. The defect is that the acceptance criterion was nevertheless reported as met, and
the two-layer framing invited a later reader to treat the at-rest transform as a second line of
defence. It is not one.

---

## 7. Contradictions found

**K1 — P38's own generated prompt contradicts itself, measured.**
`orchestration/prompts/P38_BLINDED_FIT.md` renders `**Forbidden inputs:** _none_` and, in the same
file, standing rule 8 forbidding any read under `stage2b/SEALED_RESULTS/`. The prompt generator
emits rule 8 unconditionally; the Scope section emits the node record's `forbidden_inputs`, which is
empty for this node alone. A reader of that prompt is told both things. Asserted in `TESTS.py`
section [6]. **I did not resolve it** — amending a node contract is not this node's authority. The
minimal fix is one list entry on P38, and it belongs to whoever owns `PROGRAM_GRAPH.json`.

**K2 — the audit-independence rule does not cover the pair it most needs to.**
`validate_graph.py` guards audit nodes against auditing "the implementation node" they depend on.
P38's `type` is `"experiment"`, so P39 → P38 is outside the check. Nothing is currently wrong —
P38 and P39 have different prompts and disjoint write scopes — but the invariant is unenforced for
exactly the pair on which blinding depends. Recorded, not resolved.

**K3 — I11 C1, re-confirmed, unchanged.** P39 is contractually forbidden from reading the directory
it is required to verify. I add one measurement to I11's account: `verify_seal()` returns a dict
whose payload entries carry digests, byte counts and nonces but no payload content, and §2 shows
that a nonce plus a manifest digest is *sufficient* to reconstruct plaintext. So "verify_seal
returns no content" is true and, for this design, does not imply "the caller learns no content".
Whether P39 may run it remains a coordinator ruling; the ruling should be made knowing that.

**K4 — no contradiction between any document and the bytes was found in the manifest binding.**
The delivered `demo_seal/` verifies, its digest recomputes, and its universe counts re-parse to
2,982 / 1,491. Recorded because a null here is a finding.

---

## 8. What I could NOT establish

* **That any mechanism available in this repository would meet the withdrawn criterion.** I did not
  attempt to build one, and the mandate did not ask me to. Within one process at one privilege
  level, a writer holds the plaintext in memory before it is ever stored; nothing downstream of that
  can take it back. Any real defence would have to move the key material out of the writer's reach
  entirely — a different actor, a different machine, or material the writer never possesses — and
  none of those exist in this program today. I make **no** claim that such a mechanism is
  impossible in general; I claim only that this repository contains none and that I built none.
* **Complete read-surface coverage.** I probed six in-process surfaces plus the four native and
  out-of-process ones I11 had already measured. I did not probe `ctypes`, `mmap`, Win32 handles,
  or a shell reading the file. I did not need to: §2 already recovers the plaintext from the
  ordinary published bytes, so enumerating further surfaces cannot change the conclusion. I state
  this as a limit of measurement, not as an argument that they behave a certain way — that is the
  exact reasoning-instead-of-measuring step I flagged in §6.
* **Whether P38 will in fact adopt `sealed_package.py`.** Adoption sits in
  `O16_SHARED_SCHEMA_ADOPTION`, which is `USER_REQUIRED`. Nothing here imports into a shared module
  and nothing here changes one.
* **Anything about experimental results.** This node read nothing under `stage2b/SEALED_RESULTS/`.
  That path does not exist in this worktree; I re-checked and it is still absent, so the forbidden
  input was not merely unread, it was not there. Every payload this node produced or recovered is
  synthetic and labelled so. No comparative statement about any challenger appears anywhere in this
  report, and `TESTS.py` section [7] scans for one.
* **The verifier's own figure.** I did not reuse "about ten lines". I counted my own inversion:
  5 statement lines. I have not seen the verifier's script and cannot confirm the two are the same
  attack, only that both recover the same plaintext.

---

## 9. Stop conditions

**No stop condition is tripped.** Nothing in this node changes the primary target
(`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`), the K0 structure, the inference structure,
the candidate universe, the cutoff-valid feature set, or the leakage status. K1 and K2 are
orchestration-contract findings; K3 is a coordinator ruling already open from I11. All three are
raised here rather than resolved inside the node.

One escalation is worth stating in the coordinator's terms rather than as an infrastructure note:
**if the possession experiment's blinding is ever cited as resting on the seal's at-rest layer,
that citation is now known to be false.** It rests on the process separation described in §5, and
that separation currently has a measurable hole at P38's empty `forbidden_inputs`. Closing it is a
one-line change to a file this node may not write.

---

## 10. Reading the test suite

`TESTS.py` sections [1] and [2] **pass while the defect exists**. That inverts the usual reading
and the file says so at the top and in its banner. If a future node replaces the at-rest scheme
with something that resists reconstruction, those sections will start failing — that failure means
the defect was fixed, and the correct response is to retire or re-point them, not to "repair" the
attack. Sections [3] through [7] are ordinary tests and a failure there means what it usually
means.

Current run: **68 assertions, 0 failures**, exit code 0.
