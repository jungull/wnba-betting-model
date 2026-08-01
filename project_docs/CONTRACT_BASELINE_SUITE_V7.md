# `contract_baseline_suite_v7` — registered specification

**Status: DEFINITION + COMPLETE SYNTHETIC IMPLEMENTATION. Nothing has been computed on real
data.** No historical OOF, no fitted suite artifact, no accuracy figure and no coverage score
exists or has been inspected. `cbs_v7.py` reads no data file of any kind; the only file it
opens is `experiments/registry.jsonl`, and only to recompute its own configuration identity.
Every test drives it with fabricated in-process frames.

Registry line **85** (84 → 85, a true one-line append; records v1–v6 are byte-identical).
Authorised by the Codex supervisor reply `20260801T222006044Z`.

| | |
|---|---|
| `arm_id` | `contract_baseline_suite_v7` |
| supersedes | `contract_baseline_suite_v6` (left untouched as the historical record) |
| implementation | `cbs_v7.py`, `contract_validator_v3_strict.py`, plus the unchanged `cbs_v5.py` / `cbs_generator.py` / `cbs_builders.py` primitives |
| tests | `tests/test_cbs_v7.py` — **235 runner-level assertions, synthetic only** |
| `config_hash` | **`237b4c1815d3b9a5c0f7f1af09c9d143c186ff2bfc9244f73fd5c63c6a440fc4`** — SHA-256 over the canonical (`sort_keys=True`, compact separators) JSON of `extra.frozen_config` with `hashes.config_hash_value` removed, the same self-referential convention v1–v6 used |
| `data_snapshot_hash` | **derived** from a `cbs_snapshot_manifest/1` artifact manifest, never supplied as a bare value |
| `model_hash` | `FittedState` digest, per fold **and** per target |
| provenance digest | SHA-256 over the canonical `cbs_provenance_history/1` sidecar content |

---

## 1. Why v7 exists

v6 was not a bad runner. It supplied the end-to-end pipeline v5 never had, and its 104
synthetic assertions pass. The problem is **where** those assertions ran: all of them inside a
single season, against a runner that never checked which season its rows were in.

Ten defects followed from that, and every one of them lives at the outer-fold or as-of
boundary — the two places where a baseline stops being a baseline and becomes a leak.

| # | v6 behaviour | v7 |
|---|---|---|
| 1 | No outer-fold guard at all. v6's own fixtures put train and test in the same season, and such a frame could reach `scoring_permitted=True`. | `require_outer_fold` + `fold_boundary/1` receipt |
| 2 | `require_identity` accepted any nonzero 64-hex string, emitted it, then "validated" it against that same value — a check that cannot fail. | exact registered constant, recomputed from the registry; snapshot identity **derived** from an independent manifest |
| 3 | `resolve_feature_asof` was written in v5 and never called. `_emit` copied `uni["feature_asof"]`. `synthetic=False` still defaulted `allow_declared_defaults=True`. | as-of derived from the sources actually read; declared defaults forbidden outright on the real path |
| 4 | Batch histories used earlier test rows' outcomes because their row *order* was prior — order is not knowability. | availability-gated walk-forward engine with a strict cutoff test |
| 5 | `TEAM_MIN_PRIOR = 5` was frozen in v5 and never read. Teams with 1 prior game influenced alpha selection and emitted nonfallback predictions. | `MIN_PRIOR` binds selection, side-map fitting, the residual pool **and** emission; full player ladder |
| 6 | Excluded rows bypassed the hash-format, as-of, boolean and prior-count checks. | `contract_v2_strict/3` applies every lineage check to **every** row |
| 7 | The history sidecar was unvalidated, unhashed and bound to nothing; a sidecar from another run could be substituted silently. | `cbs_provenance_history/1` with its own digest, schema validator and one-to-one binding |
| 8 | One checker ran over both frames, so a current test row needed its own postgame outcome merely to be predicted. | training requirements separated from prediction obligations |
| 9 | `team_id = T{pair}_{side}` made every team permanently home-only or away-only. | stable league teams that alternate sides; team causal-as-of tests added |
| 10 | No per-row registered provenance. | component id, fallback level, alpha/lambda, residual-pool count and separate prior-history fields, per row |

---

## 2. The outer-fold guard

`cbs_v7.require_outer_fold(train, test, fold_id)` proves, or raises `OuterFoldViolation`:

1. `fold_id` parses as `season:<Y>` — the real contract uses exactly these ids
   (`season:2021` … `season:2026`), alongside a `train_boundary` column reading
   `seasons < Y`;
2. **every** test row is in season `Y`;
3. **every** training row is in a season **strictly before** `Y` — this is the clause that
   rejects same-season and future-season contamination;
4. the train and test `row_uid` sets are **disjoint**;
5. `max(train.forecast_cutoff) < min(test.forecast_cutoff)` — a "training" window that runs
   into the fold is not training.

It returns a `fold_boundary/1` receipt naming the test season, the training seasons, the row
counts and both boundary timestamps. The composite gate requires it.

## 3. Outcome availability and the walk-forward engine

A prior outcome is admitted into a row's history **only when its availability timestamp is
strictly earlier than that row's `forecast_cutoff`.** Position in a sort order is not
knowability: a game played the evening before a morning cutoff is prior in every sort key, and
its box score may still not have existed.

Two sources, and the label always says which:

* **`observed`** — the adapter supplied a genuine per-row `outcome_observed_at`. A
  *partially* populated column is **rejected**, not back-filled: a column that is an
  observation on some rows and a derivation on others is neither.
* **`policy`** — no observation exists, so a conservative timestamp is **derived**:
  midnight UTC of the game date **+ 36 hours**, i.e. noon UTC on the day after the game.

> **The policy constant is not a new invention.** It is numerically identical to
> `asof_invariant.bound_from_dates`, which this repository already froze as its conservative
> date-derived bound (`max(game_date) + 1 day at 12:00 UTC`) for exactly the case where real
> timestamps are unavailable. `OUTCOME_AVAILABILITY_POLICY_ID =
> `postgame_policy_lag_36h_from_game_date_utc/1``.

**A policy timestamp is never relabelled as an observation.** Every row carries
`outcome_availability_source ∈ {observed, policy}`; the sidecar validator rejects a frame
whose policy rows claim `observed`, and rejects observed rows that carry a policy id.

Two further guarantees:

* `require_own_outcome_unavailable` fails closed if any row's own outcome would be available
  before its own cutoff. This is what makes the single `availability < cutoff` test
  sufficient — without it, gating on availability could admit a row's own answer.
* Admission is a function of **timestamps alone**, never of a model parameter. The
  `WalkForwardPlan` is therefore computed once and reused across the whole alpha grid, so no
  tuning choice can widen the history it is tuned on.

### A consequence worth stating plainly

Under the policy source and this project's cutoff convention (`T-90m`, or 18:00 UTC the prior
day), **a team or player's most recent game is not yet knowable at the next day's cutoff.**
Prior counts therefore lag positional counts by one on a daily cadence. That is the gate
working, not a bug — and it is the single largest behavioural difference between v6's numbers
and v7's.

## 4. Identity binding

* **Config.** The runner requires the **exact** registered digest. On the real path it also
  recomputes that digest from this registry record and raises if the two disagree, so editing
  the registered configuration invalidates the constant instead of silently redefining what
  the arm is. The synthetic path is bound just as tightly, to a distinct fixed sentinel
  (`SYNTHETIC_CONFIG_HASH`) — so "any valid 64-hex string is accepted" is untrue on **both**
  paths.
* **Snapshot.** The caller must supply a `cbs_snapshot_manifest/1` manifest of the artifacts
  actually consumed (`{schema, captured_at, artifacts: {path: sha256}}`). The identity is
  **computed from it**, and the caller's claimed digest is checked against that computation.
  A wrong-but-well-formed digest now fails; so does a tampered manifest.

## 5. The feature-source contract

`resolve_feature_asof_strict` takes the **row maximum** over the registered source timestamp
columns and requires it strictly before the cutoff (equality is a violation). Missing, null,
unparseable, at-cutoff and after-cutoff sources all fail closed.

| frame | required source columns |
|---|---|
| player | `src_asof_gamelog`, `src_asof_roster`, `src_asof_schedule` |
| team | `src_asof_team_gamelog`, `src_asof_schedule` |

**Declared Stage-A defaults are forbidden outright on the real path** — the runner raises even
if the caller explicitly asks for them, and a null feature may not become a silent zero.

## 6. Fallback ladders

`fallback_level` is recorded per row; `is_fallback == (fallback_level > 0)` is enforced by the
validator, so the flag and the ladder cannot disagree. Higher levels win.

| level | meaning | player | team |
|---|---|---|---|
| 0 | fitted component produced the value | — | — |
| 1 | degenerate fold, declared constants | no usable training window | no usable training window |
| 2 | short history | **1–2 prior appearances** | **1–4 prior games** (below `MIN_PRIOR`) |
| 3 | no history or non-finite center | 0 prior appearances | 0 prior games (season opener, cold) |
| 4 | registered declared-constant season | season 2021 | season 2021 |

`TEAM_MIN_PRIOR = 5` now binds **four** things, where v6 used it for none: channel-alpha
selection, side-map fitting, the residual pool, and emission.

## 7. The provenance/history sidecar

`cbs_provenance_history/1`, one row per `(row_uid, target_key)`, carrying `component_id`,
`fallback_level`, `selected_alpha`, `selected_lambda`, `residual_pool_n`,
`n_prior_candidate_games`, `n_prior_appearances`, `n_prior_available_obligations`,
`team_prior_games`, `outcome_availability_source` and `outcome_availability_policy_id`.

Its digest is **order-invariant and value-sensitive** — a reindex is not a different artifact,
a changed value is — and it is reported in the run receipt. `validate_provenance_sidecar`
enforces schema, arm/fold/config/snapshot identity, uniqueness, types, the ladder range, the
history invariants (`appearances ≤ available obligations ≤ candidate obligations`), the
availability labelling rule, and **one-to-one `row_uid` equality with every prediction frame**
plus agreement on `component_id`, `fallback_level`, `feature_asof` and `forecast_cutoff`.

## 8. The composite gate

`scoring_permitted` is the **conjunction** of six named receipts:

`identity_binding` · `fold_boundary` · `provenance_history` · `prediction_validation` ·
`exclusion_crosstab` · `coverage`

A run with **no universe** produces **no permission** — the receipts that cannot be produced
are reported as failures rather than skipped, so absence of evidence is never a pass.

`prediction_validation` composes the unchanged historical validator with
`contract_v2_strict/3`. `/2` is left untouched: v6 and its 104 assertions were checked against
it, and tightening it retroactively would change what those checks meant.

## 9. Real-input feasibility audit — schema and provenance only

**Scope discipline:** column names, manifests and timestamp availability only. Nothing was
fitted, no prediction was produced, no coverage or accuracy figure was computed, and no
relationship between any feature and any outcome was inspected.

### What the contract holds

`experiments/prediction_contract_v2/` — `player_game.parquet` (35,615 × 32),
`team_game.parquet` (2,990 × 13), `game.parquet` (1,495 × 12), `contract.json`, and one
manifest sidecar (`player_game.parquet.manifest.json`; the other two tables have none).
`fold_id` ∈ `season:2021 … season:2026` on both row tables, matching v7's guard exactly.

### (a) Stage-A inputs — **feasible, but only via a join, and the join is unattested**

All 14 `p_active` features are **absent** from `player_game.parquet`; so are all four
`ch_*` channels, `side` and `team_points` from `team_game.parquet`. They are derivable:

* `data/masters/master_player.parquet` → `minutes`, `starter_flag`, `dnp_reason`, identity keys;
* `data/masters/master_team.parquet` → `is_home` (→ `side`), `pts` (→ `team_points`), and
  `ftm` / `fgm` / `fg3m` / `points_paint` → the four channels by the identity frozen in
  `build_channel_base_v2.py` (`ch_np2 = 2*(fgm − fg3m) − points_paint`), which
  `build_masters.v2_channel_identity` re-validates with zero violations.

**Caveat to carry forward:** neither master carries a `.manifest.json` and neither is in
`asof_invariant.FITTED_ARTIFACT_GLOBS`. Under this repository's own contract they are
**unattested inputs**, and `master_player.game_date` is a string rather than a timestamp.

### (b) An observed per-row `feature_asof` — **DOES NOT EXIST**

There is no observed source read-time for the history the Stage-A features are built from.

* `master_*.observed_time` is the **local file mtime** of the newest contributing parquet
  (`build_masters.py`), with ~10 distinct values across 33,712 rows, all inside the last two
  refresh runs. It records when this machine wrote a file, not when anything was published.
* The raw season gamelogs carry **no** capture column.
* The genuine per-row observed timestamps that do exist — `tip_time_observed_at`,
  `odds_snapshot_timestamp`, `snapshot_returned_utc`, `capture_utc` — concern tip times, odds
  and injury designations, which the Stage-A feature set does not read, and none reach back
  before 2024-05 while the contract spans 2021–2026.
* The incumbent's current value is a **derived proxy**: the previous game's calendar date,
  clamped to `forecast_cutoff − 1s` when it fails the strict test (`arm_incumbent.py`).

### (c) An observed outcome-availability timestamp — **DOES NOT EXIST ANYWHERE**

Searched: the three contract parquets, `data/masters/`, the raw season gamelogs,
`data/refresh_2026/`, `data/certify/schema_fingerprints.json`, all 31 `*.manifest.json`
sidecars, and `asof_invariant.scan_artifacts`'s field set. **Nothing records when a game's
final box score became observable.** `schema_fingerprints.first_seen` is file-level and takes
one value; manifest `fit_through_date` is itself the derived `bound_from_dates` bound.

### Consequence, stated as a gap rather than closed

The real adapter must run under the **`policy`** availability source and label every row
accordingly. It cannot claim an observation, and v7's validator will reject it if it tries.
The policy constant proposed for review is the one this repository already froze
(`bound_from_dates`), so adopting it introduces no new number — but it remains a
**policy-derived timestamp submitted for supervisory review, not an observation**, and the
choice is a design decision the data cannot settle.

### Additional cutoff caveat, for the record

`forecast_cutoff` is itself a policy constant for most rows: 25,358 of 35,615 player rows use
`date_only_prior_day_cutoff` (18:00 UTC the prior day) and only 10,257 derive from an observed
tip. **Seasons 2021–2024 have zero exact-cutoff rows.** `contract.json` already reports the
two policies separately and forbids merging them; v7 changes nothing about that and inherits
the requirement.

## 10. What is still blocked

No real OOF, no fitting, no prediction, no scoring, no accuracy or coverage inspection, no
hierarchical arm. This document and the implementation it describes are the artifacts to be
reviewed **before** any of that becomes permissible.
