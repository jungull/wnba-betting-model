# `contract_baseline_suite_v8` — registered specification

**Status: DEFINITION + COMPLETE SYNTHETIC IMPLEMENTATION + A VERSIONED REAL PROVENANCE LAYER.
Nothing has been computed on real data.** No historical OOF, no fitted suite artifact, no
accuracy figure, no coverage score. The runner reads no data file: it opens
`experiments/registry.jsonl` for config identity and, when given an `artifact_root`, the
snapshot artifacts whose digests it verifies. The adapter reads real artifact **bytes and
schemas** only, and fits, predicts and scores nothing.

Registry line **86** (85 → 86, a true one-line append; records v1–v7 byte-identical).
Authorised by the Codex supervisor reply `20260801T232116278Z`.

| | |
|---|---|
| `arm_id` | `contract_baseline_suite_v8` |
| supersedes | `contract_baseline_suite_v7` (**left byte-untouched**; every unchanged primitive is *imported* from it, not copied) |
| implementation | `cbs_v8.py`, `cbs_real_adapter.py`, plus unchanged `cbs_v7.py` / `cbs_v5.py` / `cbs_generator.py` / `cbs_builders.py` / `contract_validator_v3_strict.py` |
| tests | `tests/test_cbs_v8.py` — **132 runner-level assertions, synthetic only** |
| `config_hash` | **`663058521c36fd5afc4baaab8fc0a29b6121bf5dc7685df3dc1e8afbc67e43e5`** — SHA-256 over the canonical JSON of `extra.frozen_config` with `hashes.config_hash_value` removed, the v1–v7 convention |
| `data_snapshot_hash` | **derived** from a `cbs_snapshot_manifest/2` naming artifact digests **and** canonical frame digests |
| adapter | `cbs_real_adapter/1` |

---

## 1. Why v8 exists

v7's outer-fold and as-of work is real and its 235 assertions pass. Its three remaining
defects were all the same shape: **v7 proved things about the frame it predicted, and took
the frame it fitted on — and the artifacts both came from — on trust.**

| # | v7 | v8 |
|---|---|---|
| 1 | `resolve_feature_asof_strict` ran on `test` only (`cbs_v7.py:1212`, `:1467`). Training Stage-A values and team channels were fitted without proving their sources preceded each *training* cutoff. | every frame read is resolved, validated and receipted — `train` included |
| 2 | `require_team_predict_inputs` reached `_require_team_common`, which demands all four `ch_*`. Those four **reconstruct the target game's own final score**, so v7 could not predict a game without being handed the answer. Dropping `team_points` while keeping its four addends closed nothing. | a current obligation carries **neither** `team_points` **nor any** `ch_*` |
| 3 | `snapshot_identity` hashed whatever mapping the caller passed. Nothing checked it against real artifact bytes; nothing tied it to the `train`/`test`/`universe` frames consumed. | artifact bytes re-hashed on disk; canonical frame digests bound; a mutated frame fails **before any fit** |

## 2. Source provenance on every frame

`resolve_sources_receipted(frame, sources, role=...)` derives `feature_asof` as the row
maximum over the registered source columns and returns a receipt. `resolve_fold_sources`
applies it to **both** frames of a fold.

Rejected, on training and prediction frames alike: a **missing** source column, a **null**
timestamp, an **unparseable** timestamp, a source read **exactly at** the cutoff (equality is
a violation, matching `asof_invariant`), and a source read **after** it.

Also rejected — and new — a frame carrying *some but not all* registered source columns.
Partial provenance is ambiguous provenance; without this rule a frame that lost one source
column would silently fall back to a declared `feature_asof` and look fully derived. This
mirrors the rule `resolve_outcome_availability` already applies to a half-populated observed
column: supply them everywhere or nowhere.

The `cbs_source_provenance/1` receipt reports **`frames_validated`**. That field is the point:
a reader must be able to *see* that `train` is in the list, because v7's failure was precisely
that it was not, and nothing in v7's output revealed the omission. On the real path a receipt
without `train` fails.

## 3. Current obligations carry no outcome

| | required | not required |
|---|---|---|
| `require_team_current_obligations` | `row_uid`, `team_id`, `game_id`, `season`, `game_date`, `forecast_cutoff`, `side` | **`team_points`, `ch_ft`, `ch_3pt`, `ch_paint`, `ch_np2`** |
| `require_team_history_inputs` | all of the above **plus** four finite channels and a finite `team_points` | — |

`team_history_usable` marks which rows carry a **complete** channel observation. A row missing
one channel is an absent observation, not a small one: it is excluded from the EWMA **and**
from `prior_games`, or `MIN_PRIOR` would count games that never reached the average it is
supposed to qualify.

The same correction applies on the player side: `player_history_walk_forward` now restricts
the `n_prior_available_obligations` denominator to rows that actually have an `appeared`
outcome. v7 counted schedule-only rows that can never enter the numerator, biasing
`p_plays_prior` downward — a silent, one-sided error.

The suite exercises three cases: a frame with **no** outcome columns at all (runs, emits every
row, all fallback); the same frame **rejected as history**; and the realistic mixed case where
earlier games in the fold are complete and the target rows are not — those outcome-free rows
accumulate history from the completed games and, once past `MIN_PRIOR`, receive **non-fallback**
predictions.

## 4. Artifact and frame identity

`cbs_snapshot_manifest/2` adds a mandatory `frames` block to v7's `artifacts`:

* `frame_digest` sorts columns by name and rows by `row_uid`, so a reordered or shuffled frame
  is **not** a different artifact, but any changed **value** is;
* `verify_artifact_bytes` re-hashes each declared artifact on disk — absent, mismatched and
  rebuilt-after-attestation artifacts all fail;
* `bind_frames` proves the manifest describes **these** frames.

Both run at the **top** of each runner, ahead of every split, selection and fit. The suite
asserts this directly: it counts calls to `logistic_fit` and requires **zero** before a mutated
frame is rejected. A real run must also supply `artifact_root`, or it is refused.

## 5. The composite gate — eight receipts

`identity_binding` · `frame_binding` · `source_provenance` · `fold_boundary` ·
`provenance_history` · `prediction_validation` · `exclusion_crosstab` · `coverage`

`scoring_permitted` is their conjunction. A run with no universe yields **no permission**
rather than a vacuous pass.

## 6. `cbs_real_adapter/1` — the provenance layer

It fits nothing, predicts nothing, scores nothing. It supplies artifact byte hashing,
`asof_invariant` attestation status, observed-versus-policy source labels **with reasons**,
missing/unparseable/at-cutoff/late counts, `cbs_snapshot_manifest/2` construction, and
`attest_master` (dry-run by default).

**It fails closed.** `build_snapshot_manifest` refuses to describe an artifact that is not
attested. That converts "the masters are unattested" from a sentence in a report into a
condition that stops a run: no manifest → no snapshot identity → the runner will not start.
Attesting is a separate, explicit act so nobody closes the gap by accident.

### `observed_time` is deliberately unused

`master_player.observed_time` and `master_team.observed_time` are **local file mtimes** with
**10 distinct values each** across 33,712 and 2,990 rows, spanning `2026-07-31T20:42Z` →
`2026-08-01T13:01Z` while `game_date` spans `2021-05-14` → `2026-07-31`. They record when this
machine wrote the file. `attest_master` derives its bound from `game_date` through
`asof_invariant.bound_from_dates` and **records in the manifest notes that it did**, so a later
reader cannot mistake which was used.

## 7. Measured real-input status — schema, provenance and identity only

Nothing fitted, no prediction, no coverage or accuracy figure, no target relationship
inspected. Artifact: `project_docs/CBS_REAL_INPUT_AUDIT_2026-08-01.json`.

| verdict | value |
|---|---|
| `stage_a_features_available_from_contract` | **False** — all 14 absent from `player_game.parquet` |
| `team_channels_available_from_contract` | **False** — no `ch_*`, no `side`, no `team_points` in `team_game.parquet` |
| `observed_feature_asof_available` | **False** |
| `observed_outcome_availability_available` | **False** |
| `all_required_artifacts_attested` | **False** |

Attestation, measured:

| artifact | manifest valid | hash ok |
|---|---|---|
| `experiments/prediction_contract_v2/player_game.parquet` | yes | **yes** |
| `experiments/prediction_contract_v2/team_game.parquet` | **no sidecar** | — |
| `experiments/prediction_contract_v2/contract.json` | **no sidecar** | — |
| `data/masters/master_player.parquet` | **no sidecar** | — |
| `data/masters/master_team.parquet` | **no sidecar** | — |

**No entry in `asof_invariant.FITTED_ARTIFACT_GLOBS` matches `data/masters/*.parquet`**, so
`--scan` cannot even report them as missing. Adding such a glob and attesting the masters is a
separate authorised act, not something this registration performs.

All four registered source columns are labelled **`policy`**; `n_observed = 0`. Each carries a
recorded reason. The consequence stands from v7: the real path runs under the policy
availability source, labelled per row, and the `+36 h` bound — numerically identical to
`asof_invariant.bound_from_dates` — is preserved, along with its one-day lag.

## 8. Erratum against v7's test file

`tests/test_cbs_v7.py`'s F3 assertion read
`(plan.n_admitted <= np.arange(len(plan.order))).all() or True`. The `or True` made it
unconditionally true, and it was there because the comparison itself was wrong: it measured
each row's **within-group** admitted count against a **global** ordered position. It has been
replaced with the real invariant — admissions are a subset of the rows prior by cutoff in the
same group. Assertion count unchanged at **235**. **v7's implementation files are
byte-untouched**; only its test file changed, following the v5 `75 → 79` precedent.

## 9. What is still blocked

No real OOF, no fitting, no prediction, no scoring, no accuracy or coverage inspection, no
hierarchical arm. This document and the implementation it describes are the artifacts to be
reviewed before any of that becomes permissible.
