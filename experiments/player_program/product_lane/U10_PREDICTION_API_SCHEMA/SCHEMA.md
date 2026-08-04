# `player_prediction_response/1` — the response contract

**Epistemic status:** PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must
not imply a model has been promoted.

**Version:** `schema = "player_prediction_response/1"`, `schema_version = "1.0.0"`.
Same major + not-from-the-future minor is readable (`is_compatible`). A major bump is a new envelope
name, never a silent widening.

---

## 1. What this contract is for

One question: *what may a prediction API say, and what must it refuse to say?*

Three properties, enforced structurally rather than by convention:

1. **Model-agnostic.** The document describes a prediction; it does not know which estimator made
   it. Model identity, family, artifact hashes, control pairing and registry record arrive as data
   on a `ModelDescriptor`. No code path in `prediction_response_schema.py` names an arm, a
   challenger or an incumbent, and `TESTS.py` proves that by scanning the source against every
   identifier in `arm_registry.jsonl`.
2. **Absence renders as an explicit warning, never as a number.** A projection standing on a stale,
   missing or failed input is emitted `withheld`: `point` null, all uncertainty null, all component
   contributions null, market edge null, with at least one **blocking** warning naming the input and
   the projection. There is no fallback value, no last-known-good, no zero and no imputation.
3. **Versioned and self-describing.** The audit block repeats the envelope version, the code
   version, the node id, the fixture flag, the epistemic-status line, and a digest over the input
   ledger — so a stored response can be re-checked after it leaves the process that made it.

---

## 2. Top-level shape

| block | carries |
|---|---|
| `schema`, `schema_version` | envelope identity and version |
| `response_id`, `generated_at_utc` | this response's identity and clock |
| `game` | `game_id`, `game_cluster_id`, `season`, both `team_id`s, `scheduled_tip_utc` (nullable), `forecast_cutoff_utc` |
| `model` | `model_version`, `model_family`, `artifact_sha256` map, `promotion_status`, `control_pairing`, `registry_record`, `produced_by` |
| `inputs` | one record per upstream input: bytes hash, `as_of_utc`, `observed_at_utc`, age, age bound, `job_status`, derived `freshness`, derived `degraded` |
| `projections` | per subject: target, unit, status, point, uncertainty, components, `depends_on`, market comparison |
| `warnings` | `code`, `severity` (`blocking` / `advisory`), `message`, `scope` |
| `audit` | version echo, node id, code version, `fixture_mode`, epistemic status, `inputs_digest`, request echo, served/withheld/blocking counts |

`additionalProperties` is false everywhere, in the JSON Schema and in the Python validator. An
unknown key is a rejection, not a passthrough — a consumer cannot smuggle a number in beside the
contract.

---

## 3. The ten invariants

`validate_response()` raises `SchemaViolation` on the first breach. `INVARIANTS` names them.

| id | invariant |
|---|---|
| I1 | envelope named and version-compatible; `generated_at_utc` is ISO-8601 UTC `Z` |
| I2 | model identity is opaque data; `promotion_status` from a closed vocabulary; ≥1 artifact hash, each 64 hex |
| I3 | every input carries a freshness verdict from `{fresh, stale, missing}`, a `job_status` from `{ok, failed, not_run}`, and a `degraded` flag that agrees with both |
| I4 | a projection depending on a degraded input **cannot** be `served`; every degraded input carries a blocking warning; every declared dependency exists in the input ledger |
| I5 | a `withheld` projection carries no point, no uncertainty, no component contribution and no market edge, states ≥1 reason, and is named by ≥1 blocking warning |
| I6 | a `served` projection carries a finite point and all four uncertainty fields, and no withheld reasons |
| I7 | no prohibited prediction-path term is serialised in a target or component name |
| I8 | the audit block is complete, echoes the envelope version, preserves the epistemic-status line verbatim, and its `inputs_digest` and counts recompute from the body |
| I9 | market comparison is explicit about absence: unavailable ⇒ line null, edge null, reason populated; available ⇒ a finite line |
| I10 | game identity present, including `game_cluster_id` — games are cluster-bound throughout the program and the response says so |

**Cross-field invariants are not expressible in JSON Schema.** `prediction_response.schema.json`
checks shape only. Passing it is necessary and *not* sufficient; `validate_response()` is the
authority.

---

## 4. The degradation ladder

`freshness` is **derived**, not declared:

* bytes absent *and* no `as_of_utc` → `missing`;
* age measurable → `fresh` iff `age_seconds <= max_age_seconds`, else `stale`;
* age unmeasurable → the caller's explicit declaration if it made one, otherwise `missing`.
  Unmeasurable age is never silently `fresh`.

`degraded = freshness in {stale, missing} or job_status in {failed, not_run}`. A file that is
present and fresh on disk but whose producing job failed is still degraded — this is the exact
"failed job silently shows a plausible-looking projection" case the lane exists to prevent.

Withholding is scoped by `depends_on`, so degradation is not all-or-nothing: in the
`missing_lineup` fixture the team projection is still served while both player projections are
withheld. Market capture is deliberately **not** a projection dependency — a missing market
suppresses the *edge*, not the projection, and says so with an `available: false` block carrying a
reason.

`blocking` means *blocking for whatever depends on this*. A blocking input warning with no
dependants (the `no_market` fixture) is a real alert about the pipeline that does not falsify the
projections standing on other inputs.

---

## 5. The prediction-path prohibition, enforced at this call site

The settled primary target is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`; current-game
realized overtime, `game_minutes`, duration, overtime periods and any exact or approximate same-game
surrogate are prohibited from the prediction path
(`orchestration/prompts/U10_PREDICTION_API_SCHEMA.md:46-49`).

`feature_gate.py` audits rank, collinearity and offset dependence — it carries **no name-based
prohibition list** (measured: `PROHIBIT` and `game_minutes` do not occur in it). So this schema
enforces the naming prohibition at its own call site, per standing rule 3: it refuses to *serialise*
a target or component name matching `PROHIBITED_PREDICTION_PATH_TERMS`. It does not edit, wrap or
weaken any shared gate, and it is a serialisation refusal, not a feature-selection decision.

Matching is on token subsequences, so `team_minutes_lag1` and `home.game_minutes` are caught while
`possessions_per_game_prior` is not.

---

## 6. Fixtures

`build_fixtures.py` writes `fixtures/` deterministically; `TESTS.py` rebuilds every golden response
in memory and requires byte-identity. Everything is synthetic: fixture game and team ids, and
artifact hashes that are `sha256("FIXTURE::" + label)` — **not** the hash of any real artifact. No
fitted model, out-of-fold artifact, registry arm or sealed result is read anywhere in this node.

| fixture | demonstrates |
|---|---|
| `nominal` | all inputs fresh; three projections served; one market available, one absent |
| `nominal_other_model` | the same document under a different model descriptor — only the model block differs |
| `stale_input` | trailing history beyond its age bound; every dependant withheld |
| `missing_lineup` | lineup absent; player projections withheld, team projection still served |
| `failed_job` | lineup file present and fresh, its job failed; dependants still withheld |
| `no_market` | market job never ran; projections served, every market block explicitly unavailable |
| `no_value_produced` | the producing pipeline returned nothing for one subject; withheld, not defaulted |

---

## 7. What a consumer may and may not do

* **May** display `point` only when `status == "served"`.
* **May not** branch on `model_version` or `model_family`. They are opaque strings; branching on
  them re-introduces the model coupling this schema removes.
* **May not** treat a null as a zero, a blank or a carried-forward value. A null with a blocking
  warning is a refusal to answer and must render as such.
* **May not** read `promotion_status == "promoted_by_registered_decision"` as anything but an echo
  of a registered decision made elsewhere. This node registers nothing and promotes nothing.
