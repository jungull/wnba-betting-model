# U12_PREDICTION_HISTORY — immutable prediction-history and model-version views

**Epistemic status (verbatim from the brief, `orchestration/prompts/U12_PREDICTION_HISTORY.md:36`):**

> PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
> has been promoted.

**Nothing in this node implies a model has been promoted.** No model was fitted, scored, compared
or evaluated here. No possession challenger is named anywhere in the code — the store takes a
model version and its artifact hashes as *data* and never learns which estimator produced a
number. Every fixture record declares `promotion_status: "not_promoted"`, and that value is
supplied by the fixture builder, never inferred by the store. Nothing under
`experiments/player_program/stage2b/SEALED_RESULTS/` was read, and no comparative performance of
any arm was inspected.

---

## 1. What was built

All paths relative to the worktree root
`C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program`
(branch `player-model-program`, verified with `git rev-parse --abbrev-ref HEAD` — the only git
command run, read-only). Everything written is inside the declared write scope
(`orchestration/prompts/U12_PREDICTION_HISTORY.md:84`):

| file | what it is |
|---|---|
| `experiments/player_program/product_lane/U12_PREDICTION_HISTORY/prediction_history.py` | the store: record construction, validation, the single append primitive, chain verification, and the read-time views |
| `.../build_fixture_history.py` | deterministic builder of the synthetic fixture ledger |
| `.../fixtures/prediction_history.jsonl` | the fixture ledger, 8 records |
| `.../fixtures/LEDGER_HEAD.json` | head sidecar (tail digest + record count) |
| `.../fixtures/FIXTURE_SUMMARY.json` | the fixture's own counts and digest |
| `.../VIEW_SAMPLE.txt` | the three rendered views over that ledger |
| `.../TESTS.py` | the validation command in the contract (`prompts/U12_PREDICTION_HISTORY.md:94`) |
| `.../measure.py` | produces `EVIDENCE_measured.json`; every number below comes from it |
| `.../EVIDENCE_measured.json` | machine-readable evidence |

Standard library only, Python 3.13. `pytest` is not installed, so `TESTS.py` follows the repo
convention of a standalone script whose `main()` returns 1 on failure — the same shape as
`experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/TESTS.py:1-12`.

Three primitives are restated locally rather than imported, so this node has **no import
dependency on a frozen artifact**: `sha256_file` (`receipt_integrity.py:266`), the
recorded-timestamp parsing rule (`receipt_integrity.py:312` — a recorded timestamp, never an
mtime, because an mtime does not survive a `git checkout`), and canonical sorted-key comparison
(`receipt_integrity.py:333`). No frozen file was modified.

## 2. The three acceptance criteria, and how each is enforced rather than asserted

The criteria are `orchestration/PROGRAM_GRAPH.json:3111-3113`, restated in the brief at
`prompts/U12_PREDICTION_HISTORY.md:70-72`.

### (a) "prediction history is immutable and append-only"

* The module exports exactly one write function, `append_prediction`. `TESTS.py` block [1]
  enumerates the module's public namespace and asserts that (i) no exported name matches
  `update|delete|edit|overwrite|rewrite|patch|drop`, and (ii) the only exported write primitive is
  `append_prediction`. It also scans the module source for every `.open(...)` mode literal and
  asserts the set is a subset of `{a, r, rb}` — the ledger is never opened for truncation or
  update.
* Block [2] measures the byte-level claim directly: it captures the ledger bytes, appends a new
  record, and asserts the new file's leading bytes are identical to the whole of the old file.
* Each record carries `prev_record_sha256` and `record_sha256 = sha256(prev + canonical(body))`.
  `verify_ledger` recomputes the whole chain and every derived identity. Block [3] performs six
  out-of-band tampers on a throwaway ledger in the system temp directory and asserts each is
  caught: an edited value (`RECORD_DIGEST_MISMATCH` + `RECORD_ID_NOT_DERIVABLE`), a deleted record
  (`CHAIN_BROKEN`), a reorder (`CHAIN_BROKEN`), a truncated tail (`HEAD_COUNT_MISMATCH` /
  `HEAD_DIGEST_MISMATCH`), a forged `record_id` whose chain digest was recomputed to match
  (`RECORD_ID_NOT_DERIVABLE`), and a duplicated line (`DUPLICATE_RECORD_ID`).
* `append_prediction` verifies the existing ledger *before* extending it and refuses to append to
  one that does not verify, so a tampered history cannot be quietly normalised by continuing to
  write to it. Block [3](g) measures the refusal.

### (b) "each prediction is bound to its model version and artifact hashes"

`validate_record` requires `model.model_version` (non-empty string), `model.artifact_sha256` (a
non-empty map, every value 64 lowercase hex characters) and `model.promotion_status`. The check
runs twice: at construction (`make_record`) and again at append. Block [4] measures seven
distinct refusals — absent version, blank version, absent hash map, empty hash map, a
non-sha256 value, uppercase hex, and absent promotion status — and asserts each is refused *for
the stated reason*, not incidentally.

`model_version` is a caller-supplied opaque string. `render_model_version_view` groups history by
it and raises a visible `WARNING` when one `model_version` string is observed with more than one
artifact digest for the same artifact name — i.e. when the version string is not actually
identifying the bytes.

### (c) "a revised prediction appears as a new record, never as an edit"

A prediction key is `(game_id, team_id, player_id, target, forecast_cutoff)`; `key_uid` is the
digest of that key and is re-derivable by any reader, which is the same re-derivability rule the
contract states for `row_uid` at `PREDICTION_CONTRACT_V5_SPEC.md:272`. A key may not be partially
unknown (block [9]).

A correction is appended with `revision_index = previous + 1` and `revises_record_id` = the
**current head** record for that key. `append_prediction` refuses: a reused `revision_index`, a
fork of a superseded record, a second revision 0 for an existing key, and a first record that
claims to revise something. Block [5] measures all four refusals, then asserts the ledger is
unchanged after them (fail-closed: a refusal writes nothing), then appends a legitimate revision
and asserts the superseded record's bytes are byte-identical to what they were before.
Supersession is *derived* at read time by `view_current`; the superseded records stay in the
ledger and stay readable (`view_superseded`, `view_lineage`, `render_lineage`).

## 3. Absence renders as a warning, never as a number

This is the failure mode the lane exists to prevent, so it is enforced in three places:

1. `evaluate_inputs` turns each declared input into a blocking warning when it is absent
   (`INPUT_MISSING`), carries an unparseable observation time
   (`INPUT_UNPARSEABLE_TIMESTAMP`), is dated after the record itself
   (`INPUT_TIMESTAMP_IN_FUTURE`), or exceeds its own declared `max_age_seconds`
   (`INPUT_STALE`).
2. `make_record` discards the caller's number when any blocking warning is present and emits a
   `WITHHELD` record. A caller who passes a point *and* an interval alongside a missing lineup
   gets neither.
3. `validate_record` refuses a hand-built record that is `status: OK` while carrying a blocking
   warning, and refuses a `WITHHELD` record carrying **any** numeric projection field — including
   an interval with a null point, which is the obvious way to smuggle a plausible-looking number
   past a point-only check. `render_record` then returns `is_numeric: False` and a string naming
   the causes.

Block [6] measures all four absence causes; for each it asserts the record is `WITHHELD`, the
supplied number (42.0) is gone from the record, the render is non-numeric, a cause is named, and
the string "42" does not appear anywhere in the rendered text. It also measures the converse —
an *advisory* warning does not suppress a number, and an absent input declared `required: false`
is advisory — so the rule is not a blanket suppression that would make every projection useless.
A null projection with no declared cause becomes `MODEL_OUTPUT_MISSING`: silence is not a
permitted state.

## 4. What was measured

Reproduce with:

    python experiments/player_program/product_lane/U12_PREDICTION_HISTORY/measure.py

which runs the other two scripts as subprocesses and records their real exit codes and output.
Results, from `EVIDENCE_measured.json`:

| measurement | value |
|---|---|
| `python .../TESTS.py` | exit 0, **99 assertions passed, 0 failed, 0 skipped** |
| `python .../build_fixture_history.py` | exit 0, `verify ok: True findings: []` |
| fixture ledger records / distinct prediction keys | 8 / 5 |
| fixture records projected (`OK`) / withheld | 5 / 3 |
| superseded-but-retained records | 3 |
| distinct model versions in the fixture | 2 (`fixture_model/2026.08.01a`, `fixture_model/2026.08.01b`) |
| distinct `promotion_status` values | 1 — `not_promoted` |
| blocking codes exercised by the fixture | `INPUT_MISSING`, `INPUT_STALE`, `UPSTREAM_JOB_FAILED` |
| fixture ledger sha256 | `2d2efb10bd0f7fcb819e60b1e7ecb677c00aa03d0bd410807ac4f1f2e1761bea` |
| ledger rebuild determinism | the builder was run twice; both runs produced that same digest |

Cross-check I ran against the repository (`measure.py::state_hash_check`, recorded under
`program_state_cross_check`): the four shared-contract digests recorded in
`PROGRAM_STATE.json:64-85` all still match the bytes on disk, and the registry record count
recorded at `PROGRAM_STATE.json:86-91` (41) matches the 41 non-blank lines actually in
`arm_registry.jsonl`. **No contradiction was found** between those documents and those bytes.
That is a negative result and is recorded as one; it is not evidence about any other document.

## 5. Interoperability probe against U10 (concurrent, not depended upon)

`record_from_api_response` converts one projection of a prediction-API-shaped response into a
history record. It imports nothing from any other node and tolerates either spelling of the two
fields most likely to drift (`artifact_sha256`/`sha256`, `observed_at`/`observed_at_utc`). It is
fail-closed twice over: a projection the API itself did not serve, and a projection carrying
withheld reasons, both become blocking warnings even when the payload also carries a number.

`U10_PREDICTION_API_SCHEMA/` appeared in the worktree while this node was running — it is a
**concurrent, unvalidated** sibling. I therefore probed it rather than depending on it: block [10]
converts every projection in its fixture responses and **skips with a stated reason** if that
directory is absent or its shape has moved. As measured at the time of this run: **7 response
files, 21 projections, all 21 converted — 6 numeric, 15 withheld.** (The withheld majority is
expected: those fixtures are named `stale_input`, `missing_lineup`, `failed_job`,
`no_value_produced`.) A first pass of this probe judged all 21 as withheld; that was an artifact
of my test judging their fixtures' freshness against *my* fixture clock, and is corrected — the
probe now takes the record time from each response's own `generated_at_utc`. I am reporting the
mistake rather than only its correction.

Independent convergence worth recording: U10's `model` object requires exactly
`model_version`, `model_family`, `artifact_sha256`, `promotion_status`
(`product_lane/U10_PREDICTION_API_SCHEMA/prediction_response.schema.json`), and its warning
severity enum is `{blocking, advisory}` — the same names and the same enum this store arrived at
independently. Divergences that a later integration node must reconcile, **not** resolved here:
U10 spells the warning text `message` (this node: `detail`) and requires a `scope` field this
node does not; U10 names input digests `sha256` and times `observed_at_utc`.

## 6. What I could NOT establish

* **Tamper evidence is not tamper proofing.** The chain and the head sidecar make an edit, a
  deletion, a reorder and a truncation *detectable*. They do not make them impossible. There is
  no signature, no append-only filesystem guarantee and no external witness, so an actor with
  write access to both `prediction_history.jsonl` and `LEDGER_HEAD.json` can rewrite the entire
  chain and it will verify. I could not close this inside the node's write scope. This is the
  same class of limitation `PROGRAM_STATE.json:266-272` already records for construction receipts
  ("a construction receipt is not a cryptographic attestation").
* **Truncation is only detectable via the sidecar.** Block [3](d) asserts this explicitly, in both
  directions: the sidecar catches it, and the chain alone does not. That is a stated property, not
  a bug, but it means a ledger shipped without its sidecar has a blind spot at the tail.
* **The store cannot verify that a declared artifact hash corresponds to the artifact that
  actually produced the number.** It checks that a hash is well-formed and recorded, not that it
  is true. This is the same asserted-not-verified gap `PROGRAM_STATE.json:274-277` records as
  `cutoff_validity_asserted`.
* **No production wiring exists and none was attempted.** There is no live writer, no scheduler
  integration and no retention policy. The ledger is a fixture built from synthetic keys and
  placeholder digests; no repository artifact and no estimator was read to produce any number in
  it.
* **I could not bind to a validated upstream schema.** At the time this node ran, `product_lane/`
  contained no *accepted* output — U10 and U11 were being written concurrently by other contexts.
  The record shape here is therefore this node's own, and the U10 alignment in §5 is a probe of
  bytes that may still change, not an agreed contract.
* **Concurrency of writers is unaddressed.** `append_prediction` is safe against interleaving only
  to the extent a single-line append to a local file is atomic; two processes appending
  simultaneously are not serialised by anything here. The program's own convention for its
  registries is a single writer (`PROGRAM_STATE.json:86-91`, "single_writer: coordinator only"),
  and this store inherits that assumption without enforcing it.

## 7. Contradictions found

None between a document and the bytes, on the checks I actually ran (§4). I did not audit
documents outside the five input artifacts and the files cited here, so this is a bounded null
result, not a clean bill of health for the program's documentation.

## 8. Stop conditions

**Nothing here trips a stop condition** (`prompts/U12_PREDICTION_HISTORY.md:76`). This node
touched no primary target, no K0 structure, no inference structure, no candidate universe, no
cutoff-valid feature set and no leakage status. It fitted nothing, scored nothing and compared
nothing. The nine V2 halt findings S1–S9 (`stage2a/V2_STOP_CONDITION.json`, key `findings` — I
confirmed it holds exactly nine keys, S1 through S9, matching the brief at
`prompts/U12_PREDICTION_HISTORY.md:57`) were read for context and none of them is affected by, or
resolved by, anything in this node.

One deliberate design consequence worth flagging to the coordinator rather than deciding here:
this store records `n_prior_*`-style history counts only if a caller puts them in `context`. It
does not compute them, and it will record whatever a caller supplies. The retirement of
`n_prior_games` and its replacement by three separately-defined fields
(`PREDICTION_CONTRACT_V5_SPEC.md:229-244`, "a consumer requesting it gets an error, not a guess")
is a producer-side obligation that this store cannot enforce on its callers. If it should be
enforced at this boundary too, that is a contract decision for a later node, not one for a
product scaffold to make unilaterally.

## 9. Citations

* `experiments/player_program/orchestration/prompts/U12_PREDICTION_HISTORY.md:36` — epistemic status
* `orchestration/prompts/U12_PREDICTION_HISTORY.md:70-72` — acceptance criteria
* `orchestration/prompts/U12_PREDICTION_HISTORY.md:76` — stop condition
* `orchestration/prompts/U12_PREDICTION_HISTORY.md:84` — write scope
* `orchestration/prompts/U12_PREDICTION_HISTORY.md:94` — validation command
* `orchestration/prompts/U12_PREDICTION_HISTORY.md:57` — "the V2 halt carries NINE findings, S1–S9"
* `experiments/player_program/orchestration/PROGRAM_GRAPH.json:3111-3113`, `:3145` — the node's
  acceptance criteria and id
* `experiments/player_program/PROGRAM_STATE.json:18-25` — frozen incumbent (read, untouched)
* `PROGRAM_STATE.json:64-85` — shared-contract digests cross-checked in §4
* `PROGRAM_STATE.json:86-91` — registry is append-only, single writer
* `PROGRAM_STATE.json:266-272`, `:274-277` — the attestation and asserted-validity gaps §6 cites
* `experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md:229-244` — `n_prior_games` retired
* `PREDICTION_CONTRACT_V5_SPEC.md:272` — key identity must be re-derivable
* `experiments/player_program/receipt_integrity.py:266`, `:312`, `:333` — primitives restated
* `experiments/player_program/ops_lane/O15_LOGOUT_SURVIVAL/TESTS.py:1-12` — test-script convention
* `experiments/player_program/stage2a/V2_STOP_CONDITION.json` — nine findings, S1–S9
* `experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/prediction_response.schema.json`
  — the concurrent sibling probed in §5
