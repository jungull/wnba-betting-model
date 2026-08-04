# U10_PREDICTION_API_SCHEMA — model-agnostic versioned response schema built against fixtures

**Epistemic status (verbatim from the node contract):**

> PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
> has been promoted.

**Nothing in this node implies a model has been promoted.** No fit was run, no model was read, no
out-of-fold artifact was opened, no arm was registered and no comparative performance of anything
was inspected. The incumbent named in `PROGRAM_STATE.json:18-19` (`frozen_incumbent.arm`) is
untouched, and `PROGRAM_STATE.json:157` still records *"DISCOVERY WAVE 1 AUDIT COMPLETE; no
challenger registered; Arm D unchanged"*. Every number this schema can carry came from a fixture I
wrote by hand for the purpose.

---

## 1. What was delivered

All paths under `experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/` — the node's
entire write scope. Nothing outside it was written.

| file | what it is |
|---|---|
| `prediction_response_schema.py` | the envelope `player_prediction_response/1` v`1.0.0`: descriptors, the builder that makes the withholding decision, and `validate_response()` enforcing ten invariants |
| `prediction_response.schema.json` | JSON Schema (draft 2020-12) for the document *shape* — necessary, explicitly not sufficient |
| `SCHEMA.md` | the contract in prose: invariants, degradation ladder, what a consumer may and may not do |
| `build_fixtures.py` | deterministic generator for all fixtures and golden responses |
| `fixtures/` | 3 input fixtures + 7 golden responses |
| `TESTS.py` | 224 checks, standalone, `main()` returns 1 on failure |
| `REPORT.md` | this file |

---

## 2. What I measured, and with what

Every number below came from a command I ran in this worktree
(`git -C ... rev-parse --abbrev-ref HEAD` -> `player-model-program`).

**`python .../U10_PREDICTION_API_SCHEMA/TESTS.py`** -> `224 checks run` / `all assertions passed`,
exit 0. That is the node's declared validation command
(`orchestration/PROGRAM_GRAPH.json:3044`).

**Acceptance criterion 1 — model-agnostic, no possession challenger hard-coded**
(`orchestration/PROGRAM_GRAPH.json:2987`). Measured, not asserted:

* `arm_registry.jsonl` has **41 records** (`wc -l`), from which `TESTS.registry_identifiers()`
  extracts **48 distinct identifiers** (`arm_id`, `experiment_id`, `id`, `name`, `family`).
* Those 48, plus **7** identifiers named in the governing scientific state
  (`D_ewma_shrunk`, `ewma_shrunk`, `K0_FLAT`, `K0_MATCHED`, `bottomup_3pt_channel_v1`,
  `cbs_player_runner_v14`, `cbs_v15`) = **55 banned strings**.
* Occurrences of any of the 55 in `prediction_response_schema.py`: **0**. In `build_fixtures.py`:
  **0**. (`TESTS.t_model_agnosticism`.)
* Positive demonstration, not merely absence: `nominal.json` and `nominal_other_model.json` are
  built from **identical** game, input and projection fixtures under two different
  `ModelDescriptor`s. The test strips `model`, `response_id` and `audit` and requires the remaining
  documents to be **equal** — they are. Swapping the model changes the model block and nothing else.
* The model side of the envelope is `model_version`, `model_family`, an `artifact_sha256` map,
  `promotion_status`, `control_pairing`, `registry_record`, `produced_by`. The validator never
  compares any of them against a literal; the only closed vocabulary is `promotion_status`, whose
  two values are `no_challenger_promoted` and `promoted_by_registered_decision`. All 7 golden
  fixtures carry `no_challenger_promoted`.

**Acceptance criterion 2 — the response carries the ten required blocks.** `TESTS` asserts each of
game ids, model version, artifact hashes, input freshness, projections, uncertainty, warnings,
component explanations, market comparison and audit metadata, on **all 7** golden responses = 70
checks, all passing.

**Acceptance criterion 3 — versioned, built against fixtures, not live model output.** The envelope
carries `schema` + `schema_version` and the audit block repeats both. `is_compatible` accepts
`1.0.0`, rejects `1.1.0` (future minor) and rejects `2.0.0` (different major). Every fixture
response carries `audit.fixture_mode = true`. Fixture artifact hashes are
`sha256("FIXTURE::" + label)` — deliberately not the hash of any real artifact, so a golden response
cannot be mistaken for a real prediction. `TESTS` rebuilds all 7 goldens in memory from
`build_fixtures.scenarios()` and requires **byte-identity** with the files on disk; it holds.

**The absence-is-a-warning invariant.** This is the property the lane exists to protect, so it is
tested from both directions.

*Forward*, over the four degraded scenarios (`stale_input` / `team_history`,
`missing_lineup` / `lineup_report`, `failed_job` / `lineup_report`, `no_market` / `market_capture`):
the degraded input is flagged `degraded: true`, raises a **blocking** warning scoped to it, and
every projection declaring it in `depends_on` is emitted `withheld` with `point`, all four
uncertainty fields, every component contribution and the market edge **all null**, plus a blocking
warning scoped to that projection. A sweep across all 7 goldens finds **0** withheld projections
carrying any number of any kind.

*Backward*, **21 hand-tampered documents** are each required to be rejected by
`validate_response()` with the expected invariant id — a withheld projection given a point (I5); a
withheld projection flipped to `served` over a degraded input (I4); the blocking warning deleted
(I4); the blocking warning downgraded to advisory (I5); a tampered `inputs_digest` and a tampered
input hash (I8); the epistemic-status line rewritten to "production ready" (I8); a freshness verdict
flipped without its `degraded` flag, and a freshness value outside the vocabulary (I3); a market
edge fabricated against an unavailable market (I9); a NaN point and an incomplete uncertainty block
(I6); an empty and a malformed artifact-hash map, and an invented `promotion_status` (I2); an
incompatible major version (I1); a dependency absent from the input ledger (I4); a prohibited term
in a component name (I7); audit counts disagreeing with the body (I8); a deleted top-level block;
an unknown top-level key. All 21 rejected.

**Scoping of the withholding.** Degradation is not all-or-nothing. In `missing_lineup` the team
projection is still `served` (it does not depend on the lineup) while both player projections are
withheld. Market capture is deliberately not a projection dependency: in `no_market` all three
projections are served and every market block is `available: false` with `line` and `edge_vs_line`
null and a populated reason. A missing market suppresses the *edge*, not the projection.

**Freshness is derived, not declared** (`TESTS.t_freshness_derivation`, 8 checks). Age within bound
-> `fresh`; beyond bound -> `stale`; no bytes and no `as_of_utc` -> `missing`; **unmeasurable age
with no explicit declaration -> `missing`, never `fresh`**. A file that is present and fresh on disk
whose producing job returned `failed` or `not_run` is still `degraded` — that is precisely the
"failed job silently shows a plausible-looking projection" case, and it is closed structurally.

---

## 3. A measured repository fact, and the call-site enforcement it justifies

The prohibition — *"Current-game realized overtime, `game_minutes`, duration, overtime periods, and
any exact or approximate same-game surrogate for those are prohibited from the prediction path"* —
is stated at `orchestration/prompts/U10_PREDICTION_API_SCHEMA.md:46-49` (and identically in the 30+
other generated node prompts; `orchestration/PROGRAM_GRAPH.json` names the
`governing_scientific_contract` as `"RESEARCH_CONTRACT_V1"`).

**Measured:** `feature_gate.py` is 208 lines and contains **zero** occurrences of `game_minutes` or
`PROHIBIT` (`grep -c "game_minutes|PROHIBIT" feature_gate.py` -> `0`). Its blocking vocabulary is
`{"exact_duplicate", "near_collinear", "deterministic_transform_of_offset", ...}` at
`feature_gate.py:18` — rank, collinearity and offset dependence. **There is no name-based
prohibition list anywhere in the shared gate.**

So this node enforces the naming prohibition at **its own call site**, exactly as standing rule 3
requires: `validate_response` and the builder both refuse to *serialise* a target or component name
matching `PROHIBITED_PREDICTION_PATH_TERMS` (12 terms, token-subsequence matching, so
`team_minutes_lag1` and `home.game_minutes` are caught while `possessions_per_game_prior` is not).
No shared gate was edited, wrapped or weakened. This is a serialisation refusal, not a
feature-selection decision, and it makes no claim about what is or is not a valid feature.

---

## 4. What I could NOT establish

* **That any real prediction ever conforms to this schema.** Nothing was run end-to-end against a
  real model, because there is nothing to run: no challenger is promoted and this lane may not open
  one. The schema is exercised only by fixtures I authored. Its fit to a real producing pipeline is
  **untested and unknown**.
* **That the fixture field names match the columns a real producer would emit.** I did not bind
  `team_history` / `lineup_report` / `market_capture` to real repository paths, and I did not read
  the frozen `projected_exposure_v1` or `possessions_v2` artifacts to derive field names from them.
  Doing so would couple a product scaffold to bytes it has no authority over. The mapping from real
  artifacts to these input ids is **open work** and belongs to whichever node owns the producing
  pipeline.
* **Whether the four uncertainty fields (`sd`, `p10`, `p50`, `p90`) are the right ones.** No
  interval methodology exists in this lane to defer to; I chose a shape that forces uncertainty to
  be present and complete on any served number. Nothing here calibrates or validates an interval,
  and the fixture values are invented.
* **Whether `PROHIBITED_PREDICTION_PATH_TERMS` is complete.** It is a conservative literal list
  derived from the prohibition's prose, not from an audit of column names. `S8` in
  `stage2a/V2_STOP_CONDITION.json` records that **32 possession columns were never adjudicated** by
  the cutoff-valid availability table — so a complete prohibition list cannot be built from anything
  currently settled. I did not attempt to settle it: that would trip this node's stop condition.
  The list catches what it names and nothing else, and `SCHEMA.md` says so.
* **Any statement about model quality, arm ranking or challenger performance.** Out of scope by
  construction; nothing under `stage2b/SEALED_RESULTS` was read or listed.

---

## 5. Contradictions found

**Checked, and none between the documents and the bytes.** The generated brief and the graph node
record the V2 halt as carrying **nine** findings S1-S9
(`orchestration/prompts/U10_PREDICTION_API_SCHEMA.md:57-58`). The artifact agrees — I counted the
keys of the `findings` object in `stage2a/V2_STOP_CONDITION.json` and got exactly nine, S1 through
S9, with `S9_K0_MATCHED_must_differ_by_arm` at `stage2a/V2_STOP_CONDITION.json:170`. I record the
check because a null result is a finding.

**No contradiction found** between `PROGRAM_STATE.json`, the graph node contract and the generated
brief on: the frozen incumbent, the settled primary target, the promotion state, this node's write
scope, or its validation command.

**One observation, not a contradiction.** `PROGRAM_STATE.json:1-17` declares itself authoritative
for program state but explicitly **not** for live repository state, and its `generated_from` block
describes the *parent* of the commit carrying it. I therefore did not treat its `head` or
`working_tree_state` as current; I verified the branch directly with a read-only git command
instead. I ran no mutating git command.

---

## 6. Stop conditions

**None tripped.** Nothing here changes the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set or the leakage status. The schema is
a serialisation contract: it decides what a response may *say*, never what a model may *use*. The
one place it touches the prohibited-feature question (section 3) is a refusal to serialise a name,
applied at this node's own call site, with no shared artifact modified and no claim about feature
validity.

I noted but deliberately did **not** act on the S8 gap (32 possession columns never adjudicated in
the cutoff-valid availability table). Resolving it would change the cutoff-valid feature set, which
is exactly the stop condition. It is raised here, not resolved.

---

## 7. For the verifier

* Validation command: `python experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/TESTS.py`
  -> exit 0, `224 checks run`, 0 skips.
* Fixtures are regenerable and byte-stable:
  `python experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/build_fixtures.py`
  rewrites 10 files identically; `TESTS.py` proves it without writing.
* Files written: only under
  `experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/`. `TESTS.t_lane_hygiene`
  asserts it, asserts no file in the node references the forbidden sealed-results path, and asserts
  the required documents exist.
* No git command was run other than `rev-parse --abbrev-ref HEAD`, and no registry, ledger or frozen
  artifact was appended to or modified. The coordinator makes the commit.
