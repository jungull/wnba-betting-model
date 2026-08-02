# `contract_baseline_suite_v12` — the fit boundary, made executable and fail-closed

**Status:** registered; corrected; awaiting supervisory review. Not validated, not confirmed,
not replicated.

**Evidence label:** correction and executability only. **No real model fit, prediction, score,
accuracy result, coverage result, profitability result or model output exists.** Real artifacts
are read, real frames are built and identity-bound, and the real 2021 **team** fold is run end to
end — but 2021 is the first contracted season, its training window is empty, and the inherited
runner therefore takes its declared-constant path. A runtime sentinel asserts that no estimator
was called. The real **player** fold emits nothing at all: it is blocked before delegation by
blocker 9 below. The only fitting anywhere in this arm is on synthetic fixtures in
`tests/test_cbs_v12.py`. "Coverage" means **obligation completeness** throughout — did every owed
forecast receive a slot — never predictive accuracy.

**Authorised by:** Codex supervisor reply `20260802T213940181Z`.

**Immutable:** `cbs_v11.py`, `cbs_v10.py`, every earlier arm, and every artifact under
`experiments/prediction_contract_v4/` are byte-untouched. Registry 91 → 93, append-only, the 91
prior lines byte-identical. Zero deletions.

---

## 1. Why this arm exists

v11 closed the **frame** boundary and the supervisor accepted it: contract v4's team-bearing key,
its 35,627 obligations, its 2,990 visible team-games, its 407 exact-tip games and its labelling
corrections were all independently reproduced, and `tests/test_cbs_real_integration_v11.py`
passes 268/268 building all twelve real folds.

It then rejected v11's **executability** claim one boundary later. `cbs_v11._run` — the function a
chronological OOF would actually call — is neither executable nor fail-closed.

The reason all of it survived a green 27-check gate is a single fact:

> **No test ever called `cbs_v11.run_player_fold` or `cbs_v11.run_team_fold` with a universe.**

The v11 real gate builds real frames and stops at a bound snapshot manifest. The v11 unit suite
tests `snapshot_identity` and `require_canonical_keys` in isolation. Between them lies the runner,
and nothing entered it. This is the same shape as the v10 failure it was written to prevent — a
green gate over a path that was synthetic at exactly the boundary that had changed — one layer
deeper.

## 2. The six v11 defects

Four are the supervisor's; two more were measured while implementing the correction, and each of
those independently prevents any real v11 run from executing.

| # | Defect | Where |
|---|--------|-------|
| 1 | `require_registered_identity` documents a real-manifest, artifact-byte and frame-identity check and **calls none of them**. It accepts `artifact_root` and never reads it. | `cbs_v11.py:181-215` |
| 2 | The delegation shim declares no `frames` member, so the inherited v10 binder refuses it. | `cbs_v11.py:248-252` |
| 3 | After restamping, the inner receipts are **copied verbatim**; only `prediction_validation` is replaced. `identity_binding`, `frame_binding` and `provenance_history` therefore describe the synthetic v10 identity and the pre-restamp sidecar — and `scoring_permitted` is their conjunction. | `cbs_v11.py:265-287` |
| 4 | Delegation passes `synthetic=True`, which resolves `allow_declared_defaults` to `True` in the inherited player runner and leaves the all-source-absent fallback to a declared `feature_asof` reachable. | `cbs_v11.py:254-256` |
| 5 | **The shim cannot reach the v10 binder at all.** `cbs_v10.snapshot_identity` enforces exact artifact-set equality through `cbs_provenance_v3.require_exact_artifact_set`, whose required set names `experiments/prediction_contract_v3/`. A v4 manifest names `experiments/prediction_contract_v4/`, so the shim raises `ArtifactSetError` (MISSING 3, EXTRA 3) *before* the missing-`frames` refusal. No repair confined to the shim's `frames` member would change this. | measured |
| 6 | `_run` calls `validate_arm_output_v4` **without `expected_fold_id`**, which that function declares keyword-only and required. Any v11 run supplied with a universe raises `TypeError` before it can produce the receipt. | `cbs_v11.py:269-271` |

All six are pinned as standing regressions in `tests/test_cbs_v12.py` §2, so a future arm cannot
quietly reintroduce one.

## 3. What v12 changes

### 3.1 A per-fold `/5` manifest

`build_fold_manifest` builds a `cbs_snapshot_manifest/5` through `cbs_provenance_v4` whose
`frames` map names the actual `train`, `test` and `universe` frames of **one run**.
`require_fold_frame_map` then requires the declared roles to equal the supplied roles in **both
directions** before any digest is compared. v11's manifest could legitimately describe frames
other than the ones a fit consumed; `snapshot_identity` only checked that each declared digest was
64 hex characters.

The `/5` schema itself is **inherited unchanged**. Minting a `/6` to fix a caller's defect would
invalidate every correctly-built `/5` document for no reason a reader could point at in the
document.

### 3.2 Every real check actually called

On the real path `require_registered_identity` calls, in order and before any delegation:

1. `cbs_provenance_v4.require_real_snapshot_manifest` — the real stamps;
2. `require_fold_frame_map` — this fold's frames and no others;
3. `cbs_v8.verify_artifact_bytes` against a **mandatory** `artifact_root` — and a run that
   verified fewer than all five fails even if none mismatched;
4. `cbs_v10.bind_frames` — every supplied frame's `cbs_frame_identity/3` digest;
5. `cbs_v11.require_canonical_keys` — the unique declared obligation key.

### 3.3 Real-data semantics separated from the legacy identity shim

The inherited modelling core's registered config digest and required artifact set name earlier
contracts, so a contract-v4 run cannot enter it on **its** real path. That is an identity
concession and nothing more, and v12 refuses to let it become a data concession:

* `allow_declared_defaults=False` is passed explicitly, and a caller who passes `True` is refused.
* `require_real_sources` calls `cbs_v8.resolve_sources_receipted` **directly** on both frames, so
  the three-way branch containing the declared-`feature_asof` fallback is not on this path at all.
  §5 of the unit suite demonstrates the inherited escape firing, then shows v12 refusing the same
  frame.
* An **empty** training frame is still schema-validated: it must carry every registered source
  column, and the receipt records `row_level_clauses_vacuous: true` rather than omitting the role
  the way the inherited fold-level wrapper does. "Zero training rows violated the cutoff rule" and
  "the training frame was never looked at" are different claims.
* The shim is stamped `real_path_permitted: false`, carries the **real** artifact digests already
  verified against disk and the **real** frame digests, and invents nothing.

### 3.4 Delegation goes to the modelling core, not through the v10 wrapper

Defect 5 makes the v10 wrapper impassable for a contract-v4 manifest. `cbs_v10` delegates its own
modelling to `cbs_v8`, so the modelling core is identical, and every check the wrapper contributed
v12 performs itself **against the real `/5` manifest rather than against a shim** — strictly
stronger. `cbs_v10` remains registered, imported by `cbs_v11`, and unmodified.

### 3.5 v12 receipts, recomputed after the restamp

All eight required receipts are recomputed against the restamped predictions and sidecar and
stamped `recomputed_by`. `validated` and `scoring_permitted` are the conjunction of exactly those,
**and a required receipt that is not v12-owned fails the run even when it reports `ok`** — the
`receipt_authorship/1` clause. The inner receipts are retained under `inner_receipts` for audit
and take no part in the verdict.

`provenance_history/2` additionally requires every emitted prediction frame *and* the sidecar to
carry the run's `arm_id`, `config_hash` and `data_snapshot_hash`, and reports the digest of the
**restamped sidecar the run returns**. The arm-substituted probe the inherited clauses run on is a
different document with a different digest; it is reported separately as `legacy_probe_digest`,
and the substitution is **proved** confined to the named columns rather than asserted.

## 4. Four more defects, found only by running things

None could have been surfaced by a synthetic fixture at the boundary v11 tested, and none is in
the supervisor's list. Defects 7-9 came from running the corrected boundary on real frames;
defect 10 came from running this arm's own gate.

### 7. `cbs_v7.canonical_digest` cannot encode a `pandas.Timestamp`

The real team sidecar carries datetime-valued `forecast_cutoff` and `feature_asof`, so
`cbs_v7.sidecar_digest` raises `TypeError: Object of type Timestamp is not JSON serializable`.
Worse: `cbs_v8.validate_provenance_sidecar` takes that digest in its **return statement**, after
every clause, inside a blanket `except Exception`. On a real sidecar all of its clause results are
therefore discarded and replaced by one opaque *"sidecar validator raised"* problem. Every sidecar
the validator had ever been shown was a synthetic fixture carrying ISO strings.

**Closed by `cbs_sidecar_identity/2`** — a new id, not a redefinition; `/1` documents remain valid
`/1` documents. Same shape as `/1`, with `str(v)` replaced by `cbs_identity_v3.encode_cell` in the
real-path mode, so it is total over the real sidecar and a null and the empty string stop sharing
a digest. The inherited clauses still run, on a probe whose datetime cells are rendered as ISO-8601
text — the same rendering applied to the prediction copies, so every cross-frame comparison stays
verdict-identical because `isoformat` is injective. The substituted columns are named in the
receipt.

### 8. The team universe declares no key rule, and cannot

The team universe is keyed by `prediction_contract_v2.tg_uid(team_id, game_id)` and carries no
`obligation_key_id`, so `contract_v4_strict/1` refuses it. It **cannot** declare
`cbs_obligation_key/1`: that key is `sha256(player_id, game_id, team_id)` and a team-game
obligation has no player.

**Closed by** `require_declared_key=False` for the team target only — the documented use of that
flag, which waives the *declaration* and never uniqueness — plus `require_team_universe_key`,
which discharges the waived obligation explicitly: the key must be present, non-null, uniformly
`tg_`-prefixed and unique. A bare flag would have been a quiet exemption.

### 9. BLOCKER — the inherited obligation ordering is team-blind

`cbs_generator.order_obligations` refuses rows that are indistinguishable on
`(player_id, season, forecast_cutoff, game_id)`. The rule is **sound**: leaving the order to
however the frame arrived would make every shifted feature depend on input order. The **tuple** is
team-blind, and `prediction_contract_v4` deliberately carries dual-team obligations — one player,
one game, one cutoff, two clubs, two forecasts owed.

Measured over the whole contract:

| | |
|---|---|
| colliding rows | **28** |
| groups | **14** |
| by season | 2021: 2, 2022: 4, 2023: 8, 2024: 8, 2025: 2, 2026: 4 |
| seasons affected | **all six — no real player fold can enter the modelling core** |
| identical to | exactly the 28 rows sharing a legacy `player_game_uid`; set equality verified |
| rows still colliding once `team_id` joins the key | **0** |

This is the same defect class v11 corrected one layer up — the team-blind `(game_id, player_id)`
master join and the `game_id`-keyed appearance index. It survived at the fit boundary because
nothing had ever entered the runner with a real frame.

**v12 does not repair it.** `cbs_generator` and `cbs_v8` are registered and immutable;
`run_player_fold` calls the function with its default column names and exposes no seam to pass
`team_id` or `row_uid` through the delegation. Rebinding another module's global would change that
module's behaviour for every other caller in the process — which `cbs_v8._provenance_rows` already
rejects **by name** as not reentrant. Correcting it in this project's usual style — registering a
new component alongside the old one — would require forking the player runner that calls it, i.e.
the whole modelling core, far outside this correction's authorization.

So `require_orderable_obligations` **fails closed at the v12 boundary**, before delegation, with
the exact count, the affected seasons and the offending canonical keys — instead of surfacing three
layers down as an opaque `ObligationOrderError` — and records that adding `team_id` resolves all
28. **The frame is not reordered behind the guard's back.**

**A ruling is requested**: whether to register a corrected ordering component plus the minimum
runner fork that can call it, or to take another route. Choosing how to correct an immutable
registered module is a methodology decision, not the engineer's.

### 10. The v11 suite forbade the registry from growing

`tests/test_cbs_v11.py` §1 asserted `len(recs) == 91` and identified v11's own record as
`recs[-1]` — that is, *"v11 is the newest registry record"*. An append-only registry falsifies
that on the very next arm, and it did: the standing gate check went red the moment v12 registered,
on a registration that was correct.

**Closed by** rebinding v11's assertions to the **indices** v11 was registered at (record 91,
erratum 90) — which is what they were actually about — and relaxing the count to `>= 91`. Every
claim v11 made about its own registration (position, adjacency, uniqueness, kind,
`prior_records_mutated`) is preserved exactly. `tests/test_cbs_v12.py` is written the same way from
the start and asserts that v11's is too, so the trap cannot be re-laid. This touches a **test**
file; `cbs_v11.py` is byte-untouched.

## 5. What actually runs

| path | status |
|---|---|
| **real team, 2021** | **runs end to end.** All eight v12-owned receipts pass from the real `/5` boundary — real stamps, five artifact digests verified against disk, three frame digests bound, both frames' feature sources validated, exact obligation completeness over 418 obligations. Declared-constant cold-start path; **zero fits**, proved by a runtime sentinel installed before the first real byte was read. |
| **real player, all seasons** | **blocked** before delegation by blocker 9. Nothing emitted; zero estimator calls. The real player *frame* still builds and still identity-binds — v11's correction holds. |
| **synthetic player, nondegenerate** | **runs end to end to emitted predictions** through a fitted Stage-A ridge logistic, all eight receipts green. This is what shows the corrected boundary itself is sound. |

A label the emitted rows do **not** support, recorded so nobody later reads it as one they do:
`is_cold_start` marks an obligation with no prior admitted same-season team game — 12 season
openers out of 418. It is **not** a statement that no model was fitted; 406 rows carry `False`
while the run fitted nothing at all. The no-fit claim rests on the sentinel, the uniform maximum
fallback level and the declared-constant component, never on that column.

## 6. Tests

Both are **named standing checks** in `verify_all.REPOSITORY_CHECKS`. The v11 suites are unchanged
and still run.

* **`tests/test_cbs_v12.py`** — 146 assertions. Registration and append-only prefix; the six v11
  defects pinned as regressions; the `/5` boundary and per-fold frame map; the forced real-data
  semantics with the inherited escape demonstrated and then refused; **the nondegenerate
  end-to-end run**; the negative pre-fit controls, each asserting **zero estimator calls ran before
  the rejection**; the receipts checked against the artifacts actually emitted; the blocker; and
  the no-scoring scan.
* **`tests/test_cbs_real_integration_v12.py`** — 80 assertions. The real 2021 team fold across the
  real boundary, the cold-start no-fit proof, the blocker measured over the whole contract, the
  real-path negative controls against real bytes, and the runtime sentinel.

The negative controls the supervisor asked for, and where they live:

| control | location |
|---|---|
| missing required feature | `test_cbs_v12.py` §7(a) |
| all source timestamps removed | §7(b) |
| a source read exactly at its own cutoff | §7(b) |
| missing / stale frame digest | §7(c), §7(c′); real bytes in `…_v12.py` R5 |
| changed artifact bytes | §7(d); real bytes in R5 |
| post-restamp sidecar / identity mismatch | §8 |
| emitted receipt identities and digests vs the emitted artifacts | §8, R2 |

## 7. What remains unperformed and unauthorised

Real fitting, chronological OOF prediction, scoring, model accuracy or coverage-quality
inspection, and profitability evaluation. Per the supervisor, once this fit-boundary correction
passes, the next action is generation-only chronological OOF with a bounded target fan-out and one
fan-in **before** any accuracy or profitability metric is opened — but **blocker 9 must be ruled on
first**, because the player half of that run cannot start until the inherited team-blind ordering
is corrected.
