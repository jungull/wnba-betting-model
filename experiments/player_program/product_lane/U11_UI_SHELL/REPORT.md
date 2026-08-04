# U11_UI_SHELL — UI shell built against fixtures

**Epistemic status (verbatim from the node contract):**

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model has been promoted.

> PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
> has been promoted.

Nothing in this node implies that a model has been promoted. No model was fitted, evaluated,
scored, compared or read. No possession candidate is named anywhere in the shell, its fixtures or
its rendered pages. Arm D is untouched; `PROGRAM_STATE.json:216` still records
`"experiment_currently_authorized": false` and `PROGRAM_STATE.json:219` still records
`"arm_D": "UNCHANGED"`, and this node changed neither.

---

## What was built

All paths relative to `experiments/player_program/product_lane/U11_UI_SHELL/`.

| File | What it is |
| --- | --- |
| `ui_shell.py` | The shell. `render_payload(payload_dict) -> html` and nothing else. |
| `VIEW_CONTRACT.md` | The `u11_view_payload/1` contract and the full suppression rule table. |
| `fixtures/F1..F6*.json` | Six hand-authored fixtures: nominal, stale input, missing lineup, failed job, absent/malformed values, unbound output. |
| `rendered/F1..F6*.html` | The six pages, committed so a reviewer reads what a user would see. |
| `MANIFEST.json` | Machine-readable: payload and page digests, and the number/warning counts each page produced. |
| `make_manifest.py` | Regenerates `MANIFEST.json`. |
| `u10_adapter.py` | **Optional and unblessed** — see "The U10 question" below. Not a dependency of anything above. |
| `TESTS.py` | The validation command in the node contract. |

Reproduce end to end:

```
python experiments/player_program/product_lane/U11_UI_SHELL/ui_shell.py       # renders 6 pages
python experiments/player_program/product_lane/U11_UI_SHELL/make_manifest.py  # rebuilds MANIFEST.json
python experiments/player_program/product_lane/U11_UI_SHELL/TESTS.py          # 53 checks, exit 0
```

---

## Acceptance criterion 1 — the UI runs entirely against fixtures or frozen outputs

Cited from the node contract at `orchestration/PROGRAM_GRAPH.json:3049`.

Measured, not asserted:

* `render_payload` is a **pure function of a dict**. `TESTS.py::test_render_touches_no_filesystem_and_is_deterministic`
  replaces `builtins.open`, `io.open`, `Path.open` and `Path.read_text` with a raiser, then renders;
  it completes. Rendering the same payload twice gives byte-identical HTML.
* An AST scan of `ui_shell.py` (`test_no_scientific_or_network_imports`) found exactly these
  imports: `__future__, datetime, html, json, math, pathlib, sys, typing`. There is no `pandas`,
  `numpy`, `pyarrow`, `subprocess`, `socket`, `urllib`, `requests` or `http`, and nothing from the
  scientific lanes.
* The only filesystem access in the module is in `main()`, which reads `fixtures/*.json` and writes
  `rendered/*.html` — both inside this node's own directory.
* Every fixture declares `audit.source == "FIXTURE"`, and no fixture contains `.parquet`,
  `experiments/` or `SEALED`. No node file mentions the forbidden input
  `experiments/player_program/stage2b/SEALED_RESULTS` (`PROGRAM_GRAPH.json:39` and the U11 contract
  block). I did not read it.
* `rendered/*.html` reproduce byte-identically from the fixtures
  (`test_rendered_pages_match_the_fixtures`), and `MANIFEST.json` matches a fresh rebuild including
  every digest (`test_manifest_is_current`).

## Acceptance criterion 2 — no possession challenger is hard-coded

Cited from `orchestration/PROGRAM_GRAPH.json:3050`.

`test_no_model_or_challenger_is_hard_coded` greps `ui_shell.py`, all six fixtures and all six
rendered pages for a 19-token blocklist covering arm and estimator names, the registry, the K0
control names, the frozen incumbent's tuning constants and its two MAE figures
(`PROGRAM_STATE.json:18-23`). **Zero hits in all thirteen files.**

That is a negative check, so it is backed by a positive one. `test_model_identity_is_payload_data`
renders two payloads that differ only in `model.version` and `model.artifact_sha256`:

* each version string appears verbatim on its own page and on neither other page;
* the digest appears on its own page only;
* **the number of projection cells is identical across both** — swapping the producing model
  changes the identity block and nothing else.

Structurally: the shell has no notion of a preferred, current or correct model. `model_binding()`
reads three opaque strings out of the payload. `promotion_status` is rendered under the label
"promotion status (as stated by payload)" so a claim in the data is never presented as a claim by
the interface. `test_page_never_claims_promotion` confirms none of the six pages contains a
promotion claim once the three explicit *disclaimers* are removed from the text.

The one policy the shell does impose on model identity is a refusal, not a preference: a payload
carrying no `model.version` or no `artifact_sha256` renders `OUTPUT_UNBOUND` and **every number on
the page is suppressed** (`fixtures/F6_unbound_model.json` -> 0 numbers, 9 warnings). An
unattributable number is not shown.

## Acceptance criterion 3 — an absent or stale input renders as a warning, never as a number

Cited from `orchestration/PROGRAM_GRAPH.json:3051`. This is the criterion the design is actually
organised around.

**The producer is not trusted.** `F2_stale_input.json` and `F4_failed_job.json` deliberately carry a
complete, plausible set of projections, intervals, market lines and components *behind* a broken
input, exactly as a silently-degraded pipeline would. The shell suppresses them anyway, because
suppression is re-derived at render time from the freshness facts rather than taken from the
producer's own verdict.

Counts, produced by `make_manifest.py` (every number below is a count of the marked spans in the
committed HTML, not an estimate):

| Fixture | numbers rendered | warnings rendered |
| --- | --- | --- |
| `F1_nominal` | 15 | 0 |
| `F2_stale_input` | 0 | 7 |
| `F3_missing_lineup` | 6 | 11 |
| `F4_failed_job` | 0 | 6 |
| `F5_absent_values` | 11 | 17 |
| `F6_unbound_model` | 0 | 9 |

`F1` is the control: without 15 numbers on a healthy page, every suppression result above would be
vacuous, so `test_nominal_actually_renders_numbers` asserts it.

`F3` is the discrimination case: a missing lineup suppresses the game that requires it (0 numbers),
leaves the game that does not (6 numbers), and separately suppresses a single *row* inside that
healthy game which declares the dependency itself. Suppression is dependency-scoped, not
page-wide — page-wide suppression would be safe but useless, and users route around useless.

Two sweeps carry the general claim rather than these six examples:

* **`test_sweep_every_numeric_leaf` — 40 cases.** Each of 8 numeric leaves of the nominal payload
  (projection, interval lo/hi, market line, component contribution, across two rows) is corrupted
  five ways: set to `null`, key deleted, set to `NaN`, set to the *string* `"12.3"`, set to `True`.
  In all 40 cases the page must lose a number **and** gain a warning. All 40 pass.
* **`test_sweep_every_blocker_class` — 12 cases.** Stale input, missing input, failed input, empty
  input list, absent input ledger, absent model version, absent digests, absent model block, absent
  `as_of`, unparseable `as_of`, absent freshness claim, explicit row blocker. Eleven must suppress
  the whole game view; the twelfth (row blocker) must suppress only its row. All 12 pass.

Fail-closed details worth naming:

* An input whose `captured_at`, `as_of` or `max_age_seconds` cannot be parsed is classified
  MISSING, never OK. Freshness that cannot be evaluated is not freshness.
* A negative age (input timestamped after `as_of`) is STALE, not fresh.
* An input named in `required_inputs` but absent from the input ledger is `INPUT_UNDECLARED` — an
  undeclared dependency is a warning, not a silence (`F6`).
* A rejected non-finite value is **not echoed** even inside its own warning:
  `test_non_finite_values_never_render` asserts the strings `nan` and `inf` appear nowhere on the
  page for NaN, +inf and -inf.
* Malformed payloads (`None`, `[]`, `""`, `0`, `{}`, wrong schema, empty game) render warnings and
  0 numbers, and never raise.
* The epistemic banner is not payload-driven, so no payload can suppress it, and payload strings
  are HTML-escaped (a `<script>` tag in a title does not survive).

## The U10 question — a contradiction between the graph and the working tree, reported not resolved

The node contract for `U10_PREDICTION_API_SCHEMA` specifies the response schema this UI would
naturally consume (`PROGRAM_GRAPH.json:2987` and its `acceptance_criteria[1]`). At the time I
started, `orchestration/GRAPH_STATE.json:245` recorded U10 as `RUNNING` — in flight, not verified,
nothing to build against. I therefore defined a local rendering contract, `u11_view_payload/1`
(`VIEW_CONTRACT.md`), field-for-field over the same families U10's criteria name.

**Mid-node, `product_lane/U10_PREDICTION_API_SCHEMA/` appeared in the working tree** with
`prediction_response.schema.json`, `SCHEMA.md` and seven response fixtures. Its graph status is
still `RUNNING`; those bytes are unaccepted and may change. I did not make this node depend on
them. What I did instead:

* wrote `u10_adapter.py`, a pure dict transform from a U10 response to `u11_view_payload/1`, which
  makes **no** suppression decision — it moves identity, freshness facts and `depends_on` edges
  across and lets the shell re-derive everything;
* wrote `test_optional_u10_adapter_is_advisory_only`, which **cannot fail this node on U10's
  account**: if U10's files vanish or its shape changes, it prints SKIP.

Advisory result from that test, as run: all seven U10 response fixtures adapted and rendered.
`stale_input.json` -> 0 numbers / 20 warnings. `failed_job.json` and `missing_lineup.json` -> 8
numbers / 13 warnings each, because U10 scopes those degradations to some projections via
`depends_on` and the shell honours that scoping. `nominal.json` -> 21 numbers / 2 warnings. This is
an observation about an unverified concurrent artifact, not a result.

The one U10-driven change I made to the shell is general, not U10-specific: rows may declare their
own `required_inputs`, evaluated by the shell under the same rules as game-level dependencies. It
is exercised by `F3_missing_lineup.json` independently of U10.

## What I could NOT establish

* **That the shell is safe against real inputs.** It has never seen one. Every number in every
  fixture is invented for this node. Whether a production payload's freshness stamps are truthful
  is a property of the producer, and no interface can check it — this is the same class of gap
  `PROGRAM_STATE.json` records for `cutoff_validity_asserted` (asserted per source, cannot be
  verified from bytes) and `fresh_execution_unprovable` (a copied-forward receipt cannot be
  distinguished from an identical rerun). A payload that lies about `captured_at` renders as fresh.
  The shell reduces this to one auditable claim per input; it does not eliminate it.
* **That `u11_view_payload/1` will match U10's final schema.** U10 was `RUNNING` throughout. The
  adapter is evidence that the gap is small, not evidence that it is zero.
* **Whether the artifact digests a real payload would carry are the right ones.** The shell renders
  whatever digests it is handed and cannot verify them against `PROGRAM_STATE.json.canonical_artifacts`
  without reading frozen artifacts, which a fixtures-only product node must not do. Recommend a
  separate node bind digest verification; naming it here would be scope creep.
* **Anything about model quality, ranking or comparative performance.** Not measured, not read,
  not inspectable from this node. No performance peeking occurred.
* **Any claim about the nine V2 halt findings.** `stage2a/V2_STOP_CONDITION.json:193` lists the
  triggered stop conditions as the cutoff-valid feature set (S1, S3, S5, S8), the candidate
  universe (S2), K0_MATCHED (S4, S6, S9) and the inference structure (S7). I read them to confirm
  none of them is touched by a rendering layer, and confirmed nothing about them.

## Contradictions found

1. **Graph status vs working tree (U10).** `GRAPH_STATE.json:245` says `RUNNING`; the working tree
   already contains U10 deliverables. Not reconciled here — reported, per standing rule 1. The
   coordinator owns the reconciliation.
2. **No contradiction found between any document and the bytes I read.** `PROGRAM_STATE.json`,
   `V2_STOP_CONDITION.json`, `RESEARCH_CONTRACT_V1.md`, `GATE_INVOCATION_CONTRACT.md` and
   `PROGRAM_GRAPH.json` agree on everything this node depends on: no challenger is promoted, no
   experiment is authorized, Arm D is frozen.

## Stop conditions

**None tripped.** The node's stop condition fires on a finding that would change the primary
target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature
set or the leakage status. This node fitted nothing, measured no target, touched no control and
read no feature. Its outputs are HTML pages generated from invented data.

One thing worth the coordinator's eye, stated plainly rather than worked around: this shell is
built to make a silent failure impossible *at the presentation layer*. That is strictly weaker than
making it impossible in the pipeline. The suppression rules assume the payload's freshness fields
are honest; if a producer stamps `captured_at` at read time rather than capture time, the interface
will render a stale number as fresh and will do so confidently. If a stronger guarantee is wanted,
it has to be bound upstream — in the producer's receipt — not here.

## Compliance

* No git command was run other than read-only `git status --porcelain` and `git rev-parse
  --abbrev-ref HEAD` (which reports `player-model-program`).
* Everything written is under
  `experiments/player_program/product_lane/U11_UI_SHELL/`. Nothing else was modified. No frozen
  artifact, registry, gate or `PROGRAM_STATE.json` was touched.
* `python experiments/player_program/product_lane/U11_UI_SHELL/TESTS.py` -> **53 checks, 0 failures,
  exit code 0**. `pytest` is not installed and is not used.
