# Incumbent mapping audit — what registered control exists per contract target

*2026-08-01, at commit `5b2e49b`. Authorised by the Codex supervisor as a bounded **discovery**
task: reproduce and map the existing registered control from committed code. **No new mapping
is registered here, no model is chosen, no prediction is regenerated, and no accuracy metric
was computed or inspected.** Where several plausible components exist, they are listed and the
conflict explained rather than resolved by judgment.*

Prompted by the rejection of `experiments/arm_incumbent` at `ac2e2f0` (see `REJECTED.md`),
one of whose blockers was that the file could not be labelled the registered incumbent: the
registered control is *"the current EWMA/ridge player layer, unchanged"*, and that layer's
per-target composition was nowhere identified.

## Summary

| contract target | classification | control |
|---|---|---|
| `p_active` | **SEMANTIC_MISMATCH** | live layer uses a deterministic *rule gate*, not a probability |
| `e_minutes_given_active` | **EXACT_EXISTING_CONTROL** | minutes EWMA α=0.30, promoted and running live |
| `attempts_usage` | **NO_REGISTERED_CONTROL** | nothing predicts attempts |
| `player_scoring_distribution` | **SEMANTIC_MISMATCH** | a point projection exists; no distribution |
| `team_game_distribution` | **SEMANTIC_MISMATCH** | margin and total distributions exist; team points does not |

**One of five targets has an exact existing control.** That is the finding.

---

## The live player layer (the authoritative "current" layer)

`daily_forecast.py:640` `player_layer()` is what `freeze-v0` actually runs in the prospective
log. Its own docstring: *"Recency dressed roster + minutes EWMA(0.30) + the Phase-3 rule gate:
latest captured designation 'Out' at the cutoff => excluded. **Informational only in v0: never
modifies the team forecast.**"*

| constant | value | provenance |
|---|---|---|
| `MINUTES_ALPHA` | **0.30** | `daily_forecast.py:112`, comment: *"promoted: minutes_ewma_vs_carryforward_v1"* |
| `RECENCY_GAMES` | **3** | `daily_forecast.py:120`, *"MINUTES_MODEL_SPEC §5 recency roster window"* |
| input | `data/masters/master_player.parquet` | `daily_forecast.py:107` |

Note the live recency window is **3** games; `prediction_contract_v2` uses **5**. Both are
recency-roster proxies of the same family, but they are **not the same universe**. Recorded as
an ambiguity, not reconciled here.

---

## `p_active` — SEMANTIC_MISMATCH

**Two candidate components, neither usable as a probabilistic control.**

1. **The live rule gate** (`player_layer`, `daily_forecast.py:640-690`). Deterministic: if the
   latest captured designation at the cutoff is `Out`, the player is excluded; otherwise
   available. This is a **binary exclusion rule, not P(active)**. It emits no probability and
   has no uncertainty. It is also *informational only in v0*.
2. **`minutes_twostage_availability_v1` Stage A** — *"L2-logistic P(plays) over the dressed
   roster"*, producer `minutes_twostage.py`. This is a genuine probability, but:
   - **`gate_verdict.json`: `verdict: FAIL`, `promote: false`.** It was not promoted, so it is
     not an incumbent.
   - regime **B** (audited availability subset), not A — it consumes the injury-history archive
     (bbref transaction wire + ESPN missed-game records) and applies only to the covered subset.
   - **universe = "the dressed roster"**, not the contract's pregame candidate universe.
   - `decision_time` **T-24h**, not the contract's T-90m.

**Conflict, stated not resolved:** the only promoted thing is a rule gate that emits no
probability; the only probability failed its gate and is defined on a different universe at a
different cutoff.

## `e_minutes_given_active` — EXACT_EXISTING_CONTROL

**`minutes_ewma_vs_carryforward_v1`** (regime A, `primary_metric: minutes_mae`,
`incumbent_id: minutes_carry_forward`, `decision_time: T-24h`).

> *"Shifted minutes-EWMA × played-flag (alpha tuned on 2021-2023) beats carry-forward
> last-game minutes **on played rows**, walk-forward 2024/2025/2026."*

- `experiments/minutes_baselines/gate_verdict.json`: **`verdict: PASS`, `promote: true`.**
- α = **0.30**, frozen, and carried into production as `MINUTES_ALPHA`.
- Estimand matches: E[minutes | played] on played rows — the contract's
  `e_minutes_given_active`.

**Reproducible unchanged.** Two recorded caveats:
- registered `decision_time` is **T-24h**; the contract row cutoff is T-90m (exact) or
  date-only. Same estimator, different cutoff.
- the live implementation calls `.ewm(alpha=0.30, adjust=True).mean().iloc[-1]` over history
  filtered to `game_date < slate_date`. Whether that is *exactly* the registered **shifted**
  EWMA, or shift-by-filter, is an implementation detail to confirm when reproducing — it is
  not settled by reading the registration alone.

## `attempts_usage` — NO_REGISTERED_CONTROL

No registered component predicts field-goal attempts.

- `player_volume_heterogeneity_v1` concerns volume but is **VOID** (permutation resolution,
  B < m/q) and certifies nothing.
- Files touching `fga` (`bottomup_3pt.py`, `build_masters.py`, `build_zone_maps.py`,
  `experiments/channel_reval/build_channel_base_v2.py`) construct **team-level channel inputs**
  or masters, not a player attempts forecast.
- `props_edge_v1` reaches points via a per-36 points rate, bypassing attempts entirely.

## `player_scoring_distribution` — SEMANTIC_MISMATCH

**`props_edge_v1`** (regime A, `decision_time: T-90m` — the only component whose cutoff matches
the contract) defines the projection as:

> *"per-36 points-rate EWMA (alpha=0.30 frozen family) × expected minutes (minutes EWMA
> alpha=0.30) — the committed baseline stack, no new fitting."*

Mismatches:
- it is a **point projection**, not a distribution — no sd, no quantiles;
- `props_edge_v1` is registered as a **MEASUREMENT STUDY** whose incumbent is
  `prop_line_at_neartip`, i.e. the market. It is not a promoted forecasting model;
- conditionality is unstated: the contract asks for points **conditional on appearing**.

The *point* component is reproducible; the **distribution is not** — nothing registered emits
predictive quantiles for player points.

## `team_game_distribution` — SEMANTIC_MISMATCH

Contract target: **team points** distribution. What exists:

- **`dist_margin_cover_v1`** (regime A, `margin_crps`) — empirical train-residual quantiles
  around `str_margin_cal`. A genuine distribution, but of **margin**, not team points. And
  `gate_verdict.json`: **`verdict: FAIL`, `promote: false`.**
- **`totals_head_v1`** (regime A, `total_mae`, incumbent `chanreval_str_total_cal`) — a
  **point** total, not a distribution.
- `experiments/channel_reval/predictions_v2.csv` carries `str_home_cal` / `str_away_cal` —
  **point** team scores, no dispersion.

A team-points distribution could be *derived* from a margin distribution plus a total, but that
derivation is a new specification, not an existing control.

---

## Unresolved ambiguities, for the specification decision

1. **Recency window disagreement**: live layer 3 games, contract 5.
2. **Cutoff disagreement**: promoted minutes control registered at T-24h; contract rows are
   T-90m or date-only.
3. **Shift semantics** of the live EWMA call, to be confirmed by reproduction.
4. **`p_active` has no promoted probabilistic control at all** — the choice between reproducing
   the failed Stage A, using the rule gate as a degenerate 0/1 probability, or registering
   something new is a **specification decision** and is deliberately not made here.
5. Three of five targets need a decision before any arm can claim to be "the incumbent".

## Statement of scope

No accuracy metric was computed or inspected. No predictions were regenerated. No registration
was created, mutated, or reused. `experiments/arm_incumbent` remains rejected and unconsumed.
Evidence labels unchanged: `calibrated_prob_edge_v1` NEGATIVE, mechanism label A,
harmful-controls an uncorrected diagnostic lead, `freeze-v0` untouched.
