# REPORT — F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

The deliverable is `TARGET_CONTRACT_DRAFT.md` in this directory. This file records how it was
produced. Read-only node: no fitting, no model code, no git mutation, no frozen artifact touched.

## 1. Headline

**The estimand is NOT_DERIVABLE_FROM_DOCUMENTATION.** The corpus supplies a functional form
(two coefficients instead of one pooled), a procedural requirement (preregistration + matched K0),
and — from the adjacent registered arm `turnover_rate_role_context/1` — a unit (player × team-game
at `pregame_cutoff`) and a denominator (projected offensive possessions as log offset). It does not
supply a **target statistic**, and WS6's own audit row states there is none: *"NO promotion metric
by design"* (`FINAL_AUDIT_MATRIX.json:504`). The missing piece is decisive rather than incidental,
because the documented content of the finding is that this feature helps player allocation and
hurts team totals — so the grain *is* the question. No estimand was invented.

## 2. What was measured, and with what

All computation: Python 3.13, pandas/pyarrow, read-only. No fit was run. The only computations were
null crosstabs, variance decompositions, group counts, and git object reads.

**M1 — the P2 involvement leak, re-measured.** Joined
`turnover_p2_v1/turnover_role_context_features_v1.parquet` (35,629 rows) to
`turnover_targets_v1/player_turnover_targets_v1.parquet` on `(game_id, team_id, player_id)` cast to
`int64`, marked appearance, crosstabbed null-ness. Result for each of
`offensive_involvement_proxy`, `trailing_minutes_share`, `role_change`, `trailing_rotation_rank`:
null ∧ did-not-appear = **8,278**; non-null ∧ appeared = **27,351**; off-diagonal = **0**. Exactly
reproduces the documented figures. *Negative-proof note:* the keys were cast to a plain integer
dtype before merging precisely because this program has already produced one manufactured negative
from a silently failing StringDtype match; the crosstabs returned full, non-degenerate tables, so
the search demonstrably works.

**M2 — ws5 clean proxies, null coverage.** Extracted
`git show 6d9e3f2:.../ws5/ws5_opportunity_proxy_features_v1.parquet` (36,523 rows). Restricted to
`is_tier_a_candidate` → **35,629 rows**, matching the operational universe exactly. Nulls on
`x1_fga_share`, `x2_pe_per36`, `x3_pe_share`, `x4_pe_share_delta`, `x5_involvement_rank`,
`x6_responsibility_share`: **0 each**, including on all 8,278 non-appearers. The leak of M1 is
absent. These are the only cutoff-valid involvement constructions in the program.

**M3 — within/between variance decomposition on cutoff-valid inputs.** Standardised each proxy,
centred within `(game_id, team_id)`, took variances.

| feature | universe | rows | between | within | within share |
|---|---|---|---|---|---|
| `x1_fga_share` | all Tier A | 35,629 | 0.049826 | 0.950174 | 0.95017 |
| `x1_fga_share` | appearers | 27,351 | 0.077622 | 0.922378 | 0.92238 |
| `x3_pe_share` | all Tier A | 35,629 | 0.053425 | 0.946575 | 0.94658 |
| `x3_pe_share` | appearers | 27,351 | 0.082265 | 0.917735 | 0.91773 |

WS6's leaked-column value was 0.92568. The clean appearer-restricted replication is **0.92238** —
the architectural claim survives the leakage repair. The between-team share, which carries the
negative coefficient, *shrinks* under the cutoff-valid projected-candidate construction.

**M4 — universes.** `turnover_p2_v1` features: 35,629 rows / **2,914** team-games / 1,458 games.
`player_turnover_targets_v1`: 28,328 rows / 2,990 team-games / 1,495 games.
`team_turnover_reconciliation_v1`: 2,990 rows. Node contract states 2,982 team-game rows / 1,491
clusters. Tier A candidates per team-game: mean 12.23, min 9, max 17. Three non-coinciding
universes; a target contract must name which one defines the estimand's population.

**M5 — the "9 of 9" recount.** From `WS6_MECHANISM_DECOMPOSITION.json` at `5ef1f25`, key
`cancellation_test.competing_explanation_within_team_reallocation.per_mechanism_within_vs_between_fit`
(9 mechanisms): `beta_between < beta_within` in **9 of 9**; sign reversal
(`beta_within > 0 > beta_between`) in **4 of 9**; both coefficients negative in **5 of 9**;
`within_significant_90` 5 of 9; `between_significant_90` 6 of 9.

**M6 — reachability.** `git ls-tree -r --name-only HEAD -- .../discovery_wave_1/<ws>` returns 0
files for every one of ws1…ws8. `git merge-base --is-ancestor 5ef1f25 HEAD` → **NO**;
`... 6d9e3f2 HEAD` → **NO**. Each lives only on an unmerged `worktree-agent-*` branch.
HEAD = `4374f7c548bbac7589df3cacc0dbeed3d7a8e1e1`.

**M7 — nothing registered.** Parsed `arm_registry.jsonl` (41 records). No arm resembling a
within/between form is registered.

## 3. Contradictions found

**C1.** `DISCOVERY_WAVE_1_SUMMARY.md:215-216` and `FINAL_AUDIT_MATRIX.json:506` both say "reversal
in 9 of 9 fitted mechanisms" immediately after quoting `within +0.036, between -0.107`, which reads
as a *sign* claim. The bytes give sign reversal in **4 of 9** (M5).
`HYPOTHESIS_LEDGER.json:847` states it correctly by defining reversal as `beta_between <
beta_within`; the two downstream documents drop that definition. Frozen bytes govern. Reported, not
reconciled; no file edited.

**C2.** `FINAL_AUDIT_MATRIX.json` `supporting_artifacts` points at
`.../discovery_wave_1/ws6/WS6_MECHANISM_DECOMPOSITION.json ... at 5ef1f25`. The commit qualifier is
honest but the path does not resolve at HEAD (M6).

## 4. Blockers carried into the draft

B1 wave-1 evidence unreachable from HEAD (M6) · B2 WS6's offset is realised same-game exposure
(`run_ws6_mechanism_decomposition.py:266`, `:397` at `5ef1f25`), which
`arm_registry.jsonl:29`/`:33` forbid on the forecast path · B3 WS6's `_z_between` is centred over
the realised appearer set (`:642-644`), so a forecaster needs a new construction over the projected
candidate set · B4 the P2 involvement columns are inadmissible (M1) · B5 8,278 never-appearing Tier
A candidates · B6 WS6 ran under an older gate blob (`55f4500` and `42af2cd` both false).

## 5. What could not be established

The estimand (deliberately); the grain at which an F10 arm is graded; whether F10 attaches to the
primary possessions target or the secondary turnover track; whether `beta_between` is identifiable
per fold under the cutoff-valid construction; and anything about how well anything performs.

## 6. Stop conditions

**None tripped.** Nothing here changes the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set, or the leakage status. The
`did_appear` leak was already documented by ws3 and ws5; this node confirmed it by measurement
rather than discovering it. C1, C2 and B1 are raised for the coordinator rather than resolved here.

## 7. No performance peeking

`stage2b/SEALED_RESULTS/` was not opened. `ws5_predictions_intrinsic.parquet`,
`ws5_predictions_operational.parquet` and `WS5_RESULTS.json` were listed in a git tree but **not
read**, because they carry comparative performance.
