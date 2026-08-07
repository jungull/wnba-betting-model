# CYCLE-2 TARGET CONTRACT — score family (game total · final margin · home win probability)

**Status: DRAFT — under two-reviewer red team. Nothing herein authorizes fitting until this
contract is FROZEN, arms are preregistered with frozen cards, and implementation audits pass.**

**Node:** `S30_TARGET_CONTRACT` · **Lane:** score · **Author:** coordinator (highest tier per
GRAPH_POLICY §9: target and contract interpretation)
**Authorities:** D042 (cycle-1 close), D043 (cycle-2 mandate, user directive), D045 (board
baselines), D046 (coordinator priors — planning context only), D047 (user scope directive),
D049 (estimand resolution, this contract's companion ruling); `RESEARCH_CONTRACT_V1` governs
wherever this document and it could be read to disagree.
**Lineage:** `future_research/F12_OFF_DEF_STRENGTH_COMPONENTS/TARGET_CONTRACT_DRAFT.md`
(estimand NOT_DERIVABLE; deliberately not invented; deferred to human authorization) and
`future_research/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS/` (estimand NOT_DERIVABLE; the
full-game-vs-regulation-equivalent fork RAISED, not resolved; K0 distribution requirements and
cutoff-valid evidence inventory adopted below). Both drafts' refusals were correct under their
mandates; the missing authorization has since been supplied by direct user directive (D043,
D047), and D049 records the resolution.

---

## 1. Estimands — three, all full-game settled quantities

| id | estimand | unit | denominator |
|---|---|---|---|
| `E1_GAME_TOTAL` | sum of both teams' final points, as officially settled (overtime included) | points | per game |
| `E2_FINAL_MARGIN_HOME` | home team final points minus away team final points, as settled (overtime included) | points | per game |
| `E3_HOME_WIN_PROB` | probability the home team is the settled winner; model emits p ∈ (0,1) | probability | per game |

**Resolution of the F13 fork (D049).** F13 measured the fork and refused to pick:
full-game sd(total) 18.376 vs regulation-equivalent 17.650; sd(margin) 14.014 vs 13.952.
The user's cycle-2 mandate (D043) directs comparison "to the measured market bars … on
matched universes"; the market's bars settle on **full-game** outcomes. Full-game is
therefore the estimand for every E. Both readings stay preserved in F13's record; nothing
is reinterpreted retroactively.

**Overtime discipline.** OT inflation is part of the settled estimand — predictions are
pregame expectations of the settled quantity. The cycle-1 prohibition is carried verbatim on
the *prediction path*: current-game realized overtime, game_minutes, duration, OT periods,
and any exact or approximate same-game surrogate for those are prohibited from every
feature, offset, denominator and post-processing step. Regulation-equivalent quantities
remain legitimate **ingredient-side** constructions (the verified pace ingredient is
regulation-equivalent by construction and is declared as such wherever used).

**Untouched:** the cycle-1 primary target (`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`),
its champion `D_ewma_shrunk`, and every frozen possession artifact. This contract creates new
estimands; it does not modify any existing one.

## 2. Universe

* Base universe: the resolved **1,491 game clusters** (2,982 team-game rows) of WNBA seasons
  2021–2026 — the same corrected candidate universe as cycle 1, collapsed to game level.
  Report both counts wherever a universe is stated.
* Each arm (and its K0_MATCHED) must **declare its coverage rule** — which games drop and
  why (e.g. insufficient strictly-prior history) — as a deterministic predicate written in
  its card. The arm and its K0 share the identical resolved universe; a mismatch is
  Layer-A blocking per `comparison_gate.py`.
* Cross-arm and arm-vs-floor comparisons obey the frozen matched-universe rule: exact
  universe-string equality and identical N, else the comparison is not computed (D036 p6,
  D045). No exceptions for presentation.
* The game cluster is the only admissible independent unit; games are never split across
  folds or bootstrap draws (adopted verbatim from F13).

## 3. Folds and inference

* Five D006 expanding walk-forward folds, `train_lt_2022 … train_lt_2026`, identical to
  cycle 1. Pooled out-of-fold is the primary evaluation surface; per-fold results reported.
* Inference: game-date-clustered bootstrap, **B=10,000** test-side for ΔMetric and p-values;
  train-refit coefficient intervals (where an arm has coefficients) **B=2,000**, per fold —
  the cycle-1 receipted configuration, adopted unchanged.
* Every number ships with N (games), cluster count, date range, and 95% CI (D036 p7).

## 4. Primary metrics and the promotion gate

| estimand | primary metric | secondary (reported, never gating) |
|---|---|---|
| E1 | MAE | RMSE, bias, season splits |
| E2 | MAE | RMSE, bias, season splits |
| E3 | Brier (raw model probability vs settled indicator) | log-loss, 10-bin calibration table |

**The gate, per element (mirrors the cycle-1 frozen gate):**
(a) pooled OOF improvement > 0 against the element's own `K0_MATCHED`;
(b) family-Holm rejection at α = 0.05 (families frozen at preregistration; disputed
assignments run under both partitions, stricter governs);
(c) no preregistered kill condition fired — and every kill's diagnostic **must be a
receipted output of the sealed run** (the P42 §6 lesson: an uncheckable kill is a defect
in the card, not a pass);
(d) the possession-first ordering contract (P28) is respected — no score-family verdict may
launder a failed possession candidate, and no downstream/secondary number exists before its
primary verdict.

**K0_MATCHED discipline** (adopted from F13's inventory, binding per element): the
challenger's own pipeline with zero substantive features, matched on all thirteen strict
dimensions (rows/universe, folds, offset, intercept, penalty, clipping, link,
preprocessing, missingness, companion components, fallback, aggregation, post-processing),
with `calibration_freedom` declared explicitly — never inferred from silence. `K0_FLAT`
remains diagnostic only.

**Declared public floors (context, never K0):** the D045 board rows —
`composite_pace_x_eff_v1` (E1 pooled MAE 13.818, E2 10.336, E3 Brier 0.2181 on their own
coverage universes) and the two naive floors. These are already-observed public numbers;
they are the bar an adjudicated model should clear to be *interesting*, but promotion is
decided only by the per-arm K0 gate above. No arm's K0 may be "the composite" unless the
arm genuinely extends the composite's own pipeline and the thirteen dimensions match.

## 5. Distributional endpoints (F13 scope) — secondary this cycle

Arms MAY additionally emit predictive distributions for E1/E2. If they do: CRPS and PIT
calibration are **secondary, exploratory endpoints**; any distributional claim requires a
K0 that itself emits a distribution of the same functional form with matched dispersion
estimation (train-years-only) per F13's `distribution_specific` requirements. **No
promotion may rest on a secondary endpoint.** A dedicated distributional cycle may follow;
this contract does not authorize one.

## 6. Market comparison protocol — context, never a gate

* Paired, matched-universe comparison against the LATE cross-book de-vigged consensus,
  exactly the D045 protocol, with the T1 vendor-asserted timing caveat carried verbatim on
  every number; no timing/CLV/reaction inference.
* Market comparison is **reported** (board rows, adjudication context) and is **never a
  promotion criterion** this cycle. Any "beats the market" claim requires prospective
  confirmation on witnessed T0 captures (the live tape) — out of scope here, F15 pattern.

## 7. Mechanism scope (D047, user-directed) — what ideation must cover, not what it may not exceed

The candidate set MUST include, and ideation packets will list as *required coverage
areas* (stated abstractly, without proposing forms):

1. **Opponent-normalized interacting two-team efficiency structures** — per-side
   offensive/defensive strength components where each game's realized efficiency is read
   relative to the opponent's concurrent strength, combined as off_A×def_B / off_B×def_A
   (D047 verbatim scope; F12's "components" are hereby mechanisms toward E1–E3, not
   estimands — D049).
2. **Home-court structure** — from a single constant upward.
3. **Rest / travel / schedule** — any arm using travel features MUST model the 2024
   charter-program structural break explicitly (era interaction or era restriction);
   pooling across the break without declaring it is a card defect.
4. **Referee-crew effects** — totals channel.
5. **The A07 early-season transient** — carried as a registered candidate per D042/D043,
   re-registered fresh with its concentration-kill diagnostic as a mandatory receipted
   output.
6. Whatever else independent ideation surfaces — the required areas are a floor, not a
   ceiling, and nothing in this section pre-commits any functional form.

Cycle-1 nulls bind: rest/schedule/home arms may not target *pace* mechanisms in the same
form (P42 §7.3 retry bound); their cycle-2 forms act on scoring.

## 8. Ingredients and cutoff validity

* **Cutoff:** pregame, strictly-lagged information only; no same-game information of any
  kind; each card declares its exact cutoff semantics.
* **Verified pace ingredient** (`team_possession_prior_v1.projected_team_off_possessions`)
  is consumable as-is, frozen, declared regulation-equivalent.
* **Efficiency inputs:** strictly-lagged constructions from owned possession/score data.
* **Injury/lineup/availability features are BARRED this cycle** unless drawn from a
  point-in-time store whose capture timestamps are ≤ the declared cutoff with witnessed
  (T0) provenance. The live injury store (D048) began 2026-08-07 and therefore cannot
  cover the 2021–2026 evaluation window; retrospective injury reconstructions without
  point-in-time provenance are prohibited features (D034 discipline). Availability
  modeling on the live store is prospective-cycle work.
* F13's cutoff-valid field inventory (5 CUTOFF_VALID, 37 CUTOFF_UNPROVEN at its writing)
  binds: an UNPROVEN field used by any arm must first be promoted by a receipted
  cutoff-validity measurement in the implementation audit.

## 9. Blinding and lifecycle — identical to cycle 1

Sealed-results discipline verbatim: implementation nodes may run unit/synthetic/identity/
schema tests and dry runs that reveal no comparative historical performance; fits write
into `stage3_score/SEALED_RESULTS/`; a result-integrity node verifies commit, hashes, row
universes, folds, K0 pairing, seeds and completeness **without opening results**; only the
adjudication node opens them; adjudicated numbers reach the board solely through the D036
pipeline. Lifecycle labels BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED;
never SEALED before an evaluation ran.

## 10. What this contract does NOT do

* Authorize any fit, tuning, registration or comparison (that requires: this contract
  FROZEN + cards frozen through the S33–S35 gates + S37 audit pass).
* Touch the possession lane, Arm D, or any frozen artifact.
* Create a score-family "champion" — adoption of any fitted score model for operational or
  wager-shaped use is a **USER_REQUIRED** gate, full stop.
* Authorize player-level targets (cycle 3, D043 p3).

## 11. Stop conditions

Carried verbatim from cycle 1, applied to this lane: any finding that would change these
estimands, the K0 structure, the inference structure, the declared universe, the
cutoff-valid feature set or the leakage status HALTS the affected node and is raised to
the coordinator (USER_REQUIRED where policy §6 says so); never resolved inside a node.

---
*Companion machine-readable file `TARGET_CONTRACT.json` is generated at freeze time. The
draft freezes only after two independent red-team reviews and disposition of every
Severity A/B finding; the freeze event pins this file's sha256 in the events ledger.*
