# `contract_baseline_suite_v13` — the player order corrected, the player path opened

**Status:** registered; corrected; awaiting supervisory review. Not validated, not confirmed,
not replicated.

**Evidence label:** correction and executability only. **No real fitted player output exists, and
none is authorized before supervisory review of this pushed unit.** The arm *is* executable on the
real player path — the real 2021 fold traverses the complete boundary end to end — but 2021 is the
first contracted season, its training window is empty, and the inherited runner therefore takes
its declared-constant path. A runtime sentinel installed before the first real byte is read never
fires. The only fitting anywhere in this arm is on synthetic fixtures. Nothing computes or
inspects a score, accuracy, calibration, threshold, edge, return or profitability figure, and no
forecast is compared to any outcome. "Coverage" means **obligation completeness** throughout.

**Authorised by:** Codex supervisor reply `20260802T232025204Z`, player branch.

**Immutable:** `cbs_generator.py`, `cbs_v8.py`, `cbs_v12.py`, `cbs_v11.py`, `cbs_v10.py` and every
artifact under `experiments/prediction_contract_v4/` are byte-untouched. **No module's globals
were rebound.** Registry 93 → 94, append-only, the 93 prior lines byte-identical. Nothing deleted.

---

## 1. What v12 left, and why it could not go further

v12 was accepted. Its player path failed closed on the last obstacle between contract v4 and a
real player run:

> `cbs_generator.order_obligations` refuses rows indistinguishable on
> `(player_id, season, forecast_cutoff, game_id)`. The rule is sound — leaving the order to
> however the frame arrived would make every shifted feature depend on input order. The **tuple**
> is team-blind, and `prediction_contract_v4` deliberately carries dual-team obligations: one
> player, one game, one cutoff, two clubs, two forecasts owed. **28 rows, 14 groups, in every
> season 2021-2026.** Adding `team_id` resolves all 28.

## 2. The three pieces

### 2.1 `cbs_obligation_order/2`

    (player_id, season, forecast_cutoff, game_id)  →  (…, team_id, row_uid)

`team_id` distinguishes the pair; `row_uid` is the **terminal tie-breaker**, so the order is
*total*. Because the canonical key is unique over the contract, a remaining tie can only be a
genuine duplicate row — which is refused. Uniqueness is re-asserted **after** sorting, not only
before: `/1` checked its key before sorting and returned, but the property the modelling core
relies on is a property of the *result*.

The key is an **extension** of `/1`'s and the sort is stable, so everything `/1` could already
distinguish keeps its relative order. The refusal is strictly narrower and never wider — asserted
in §2 of the suite by ordering a collision-free frame both ways and comparing the row sequences.

### 2.2 `cbs_player_runner/13` — a two-line fork

`cbs_v8.run_player_fold` **generated from `inspect.getsource`**, so the copy is exact by
construction rather than by care. The entire permitted diff:

```diff
-    train = order_obligations(train) if len(train) else train
-    test = order_obligations(test)
+    train = (_order.order_obligations_v2(train, where="train frame") if len(train) else train)
+    test = _order.order_obligations_v2(test, where="test frame")
```

Every other name — the estimator, the standardizer, the lambda and alpha selection, the masks, the
calibration, the dispersion, the walk-forward plan, the emission and the receipt helpers — is
**imported from `cbs_v8`**, so they are the same objects and cannot drift. §8 asserts object
identity for fourteen of them by name, and re-derives the source diff against the **live**
inherited function, failing on any third differing line. If `cbs_v8.run_player_fold` is ever
amended, this stops being a fork and the gate says so.

Why a fork at all: `run_player_fold` calls the orderer with its default column names and exposes
no seam. Rebinding another module's global would change that module's behaviour for every other
caller in the process — which `cbs_v8._provenance_rows` already rejects **by name** as not
reentrant. §8 also greps this arm for monkey-patch assignments and finds none.

### 2.3 The wrapper — v12's boundary, called rather than copied

`snapshot_identity`, `require_canonical_keys`, `require_fold_frame_map`, `require_real_sources`,
`require_team_universe_key`, `build_legacy_identity_shim` and `sidecar_identity` are **v12's own
function objects**, asserted identical in §9. Only two things are restated: which registered
config digest is expected, and which arm the receipt names. Copying clause bodies to change an arm
id is how two gates meant to be identical stop being identical.

## 3. `team_id` is an ordering discriminator only

It enters the sort key and nothing else — no grouping, no admission rule, no feature, no
estimator. Player history stays grouped by `(player_id, season)`, so it follows a player across a
trade instead of resetting at it.

That is not left to a comment. `require_history_grouping_unchanged` runs on every player fold, and
the `group_cols` it checks are **read out of the forked runner's own source AST**, not restated in
the wrapper. Grouping history by team would silently shorten a traded player's window and raise
nothing; this reads what the code actually does.

## 4. The eight properties the ruling named

| # | property | where |
|---|---|---|
| 1 | all 28 real collisions resolved, no other obligation count changes | `test_cbs_v13.py` §2 |
| 2 | input shuffling leaves outputs and provenance invariant | §4 |
| 3 | both rows of a dual-team group emitted, validating against their canonical keys | §3, and on the **real** collision in `…_v13.py` P5 |
| 4 | equal-cutoff rows cannot leak into one another's lagged history | §5 and P5 — **with one measured exception, below** |
| 5 | history crosses a team change but never a season boundary | §6 |
| 6 | a duplicate even after the full v13 key fails closed before any fit | §7 |
| 7 | the fork is parity-checked, diff limited to the ordering call | §8 |
| 8 | a real 2021 player cold-start fold traverses the complete boundary, zero fits | `…_v13.py` P1–P4 |

### On property 2, precisely

Every **decision** and every **point forecast** is bit-identical across a shuffled input:
`row_uid`, `pred_point`, `component_id`, `fallback_level`, `is_cold_start`, `n_prior_games`,
`feature_asof`, `model_hash`, `exclusion_reason`. The provenance sidecar is identical row for row
and hashes to the same `cbs_sidecar_identity/2` string.

One quantity is **not** bit-identical: `pred_sd` for `e_minutes_given_active` moves by
**8.9 × 10⁻¹⁶** — one ULP — because the dispersion is a standard deviation over a residual pool
that numpy sums in input order. Nothing the run decides depends on it at that magnitude. It is
reported as a measured bound rather than waved through with a tolerance.

### On property 4, precisely — and blocker 11

**What holds, structurally.** Admission in `cbs_v7.build_walk_forward_plan` is an explicit
`availability < cutoff` comparison, and `require_own_outcome_unavailable` already forbids a row's
own outcome from being available at its own cutoff. A dual-team sibling shares that game and that
cutoff, so it is **never admitted**. This covers `n_prior_available_obligations`,
`n_prior_appearances`, `p_plays_prior` and every EWMA and conditional center. Asserted on the
**real** collision, not a fixture: the two siblings come back with identical values.

**What does not.** `cbs_v8._prior_by_cutoff` is documented as *"Prior rows by CUTOFF — a scheduling
fact, needing no availability gate"* and is implemented as a **positional prefix**: every earlier
row in sort order counts, whether or not its cutoff is strictly earlier. So the sibling the sort
puts second counts the first as prior. Measured over the whole contract:

| | |
|---|---|
| rows where the positional count exceeds the causal one | **55** |
| collision rows over-counted by exactly one | **28** |
| rows whose `p_active` fallback band would differ | **2** (`ob_f2e6b1c4373894ac`, `ob_a8c6201e99f29bba`, both 2022) |
| outcome leak | **no** — the count carries no outcome |

It matters because `n_prior_candidate_games` feeds `player_fallback_level` for `p_active`, so a
row can move between the ladder's bands. **v13 does not repair it**: the ruling requires the
walk-forward logic preserved byte-for-byte, and `_prior_by_cutoff` lives inside
`player_history_walk_forward`, not inside `run_player_fold`, so correcting it would widen the
permitted fork beyond the ordering call. Instead `measure_equal_cutoff_candidate_count` runs on
**every** player fold and reports the exact counts in the `obligation_order` receipt, so the
quantity is pinned and cannot grow silently.

**A ruling is requested**: register a corrected prior-count component and widen the fork by one
more seam before the player OOF, or accept the 2-row exposure with the receipt as the record.

## 5. What actually ran

| path | result |
|---|---|
| **real player, 2021** | **end to end.** All eight v13-owned receipts green from the real `/5` boundary; four targets × **4,850** obligations; exact obligation completeness; the real collision's two siblings both forecast with distinct canonical keys. Declared-constant cold start, **zero estimator calls** by runtime sentinel. |
| **real player, 2022-2026** | **not run.** The ruling forbids a real fitted player run before review of this unit. |
| **synthetic player, nondegenerate** | ran to emitted predictions through a fitted Stage-A ridge logistic, all eight receipts green, carrying a real-shaped dual-team collision. |

## 6. Gate

Two new standing checks: `test_cbs_v13` (139) and `test_cbs_real_integration_v13` (90).
The attestation scan moves **49 → 68**: the team branch's 19 forecast, sidecar and receipt
artifacts are now matched by an explicit glob and attested, because from 2022 they are genuinely
fitted and a stale copy would misstate a run.

## 7. The sibling branch

The same authorisation's **team branch** produced the generation-only chronological team OOF under
`experiments/cbs_v12_team_oof/`, against the **accepted v12** rather than against this arm. It is
separately identifiable, separately receipted, and is not evidence about v13. See
`project_docs/GATE_LOG_2026-08-01.md` §15.

## 8. What remains unperformed and unauthorised

Real fitted player output, chronological player OOF, scoring, model accuracy or coverage-quality
inspection, and profitability evaluation. Per the supervisor, after v13 passes review the next
step is generation-only chronological player OOF with bounded target fan-out — `p_active`; the
conditional chain (`minutes → attempts/usage → scoring`) as one dependency-respecting branch; and
the already-completed team branch — followed by one receipt-checked fan-in. Scoring remains a
separate later authorisation.
