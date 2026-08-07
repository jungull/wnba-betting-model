# CYCLE-2 TARGET CONTRACT — score family (game total · final margin · home win probability)

**Status: DRAFT v2 — post red-team amendment, under re-verification. Nothing herein authorizes
fitting until this contract is FROZEN, arms are preregistered with frozen cards, and
implementation audits pass.**

**Node:** `S30_TARGET_CONTRACT` · **Lane:** score · **Author:** coordinator (highest tier per
GRAPH_POLICY §9: target and contract interpretation)
**Authorities:** D042 (cycle-1 close), D043 (cycle-2 mandate, user directive), D045 (board
baselines), D046 (coordinator priors — planning context only), D047 (user scope directive),
D049 (estimand resolution — recorded on the decision ledger 2026-08-07, after this draft's
first version and before any freeze; the v1 draft's present-tense citation preceded the
recording and is corrected here for the record); `RESEARCH_CONTRACT_V1` governs wherever this
document and it could be read to disagree.
**Lineage:** `future_research/F12_OFF_DEF_STRENGTH_COMPONENTS/TARGET_CONTRACT_DRAFT.md`
(estimand NOT_DERIVABLE; deliberately not invented; deferred to human authorization) and
`future_research/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS/` (estimand NOT_DERIVABLE; the
full-game-vs-regulation-equivalent fork RAISED, not resolved; K0 dimensions, clustering rule,
distribution-specific requirements, covariance obligation and cutoff-valid inventory adopted
below). Both drafts' refusals were correct under their mandates; the missing authorization was
supplied by direct user directive (D043, D047) and D049 records the resolution.
**Red team:** two independent reviews (consistency; leakage/exploitability) completed
2026-08-07; every Severity A/B finding is dispositioned in this revision; the disposition map
is `RED_TEAM_DISPOSITION.md` alongside this file.

---

## 1. Estimands — three, all full-game settled quantities

| id | estimand | unit | denominator |
|---|---|---|---|
| `E1_GAME_TOTAL` | sum of both teams' final points, as officially settled (overtime included) | points | per game |
| `E2_FINAL_MARGIN_HOME` | home team final points minus away team final points, as settled (overtime included) | points | per game |
| `E3_HOME_WIN_PROB` | probability the home team is the settled winner; model emits p ∈ (0,1); the settled winner is well-defined (zero end-of-game ties in the universe, F13 §5.5) | probability | per game |

**Resolution of the F13 fork (D049).** F13 measured the fork and refused to pick:
full-game sd(total) 18.376 vs regulation-equivalent 17.650; sd(margin) 14.014 vs 13.952.
The user's cycle-2 mandate (D043) directs comparison to the measured market bars on matched
universes, and the market's bars settle on **full-game** outcomes; D049 ratifies full-game as
the estimand for every E. Both readings stay preserved in F13's record; nothing is
reinterpreted retroactively. Settled outcomes are derivable from owned committed data
(`data/masters/master_team.parquet` pts/opp_pts; corroborated by `possessions_v2/`).

**Overtime discipline — decidable, not prose.** OT inflation is part of the settled estimand;
predictions are pregame expectations of the settled quantity. Prohibited from every feature,
offset, denominator and post-processing step: current-game realized overtime, game_minutes,
duration, OT periods, current-game realized possession counts, and any same-game surrogate for
those. Legitimately pregame constructions (historical OT rates, prior-game realized durations
inside lagged rescales) are NOT swept up by this clause. The prohibition is enforced by
**receipts, not adjectives** (leakage finding 5):
* every feature column passes the P22 `postgame_surrogate_guard` invocation, carried into the
  S37 audit;
* every arm ships a frozen feature-lineage table (column → source artifact hash → lag
  semantics);
* every arm ships a **current-game-deletion invariance receipt**: the feature matrix is
  recomputed with the current game's rows deleted from every consumed source, and
  byte-identity of the two matrices is the machine-checkable proof that no same-game
  information entered the prediction path.

**Untouched:** the cycle-1 primary target (`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`),
its champion `D_ewma_shrunk`, and every frozen possession artifact. This contract creates new
estimands; it does not modify any existing one.

## 2. Universe and coverage — bounded author freedom (leakage finding 3)

* Base universe: the resolved **1,491 game clusters** (2,982 team-game rows) of WNBA seasons
  2021–2026, collapsed to game level. Report both counts wherever a universe is stated.
* Each arm and its K0_MATCHED share an identical declared coverage predicate, and that
  predicate is constrained:
  1. **Information-based and cutoff-valid only** — expressible solely in terms of
     strictly-prior data availability (e.g. "both teams have ≥ N strictly-prior games this
     season"); never in outcome terms, season-label convenience, or market-coverage terms
     (market fields are barred entirely, §8).
  2. **Minimum-coverage floor, pooled AND per-fold:** the predicate must retain **≥ 90% of
     the 1,491 clusters pooled** and **≥ 80% of every fold's test clusters** (concentrated
     trimming of a single fold is the exploit this second floor closes). The only path around
     the per-fold floor is cycle-1-style **whole-fold structural deactivation** — symmetric
     in arm and K0, declared in the card with its numeric trigger before any fit. A lower
     floor of either kind requires an explicit justification adjudicated at S33/S34 and
     recorded in the card.
  3. **All-covered-games sensitivity row (mandatory, non-gating):** every arm is additionally
     scored on the full base universe with its card-declared fallback (the cycle-1
     `fallback_rules` dimension exists for exactly this); reported alongside the gated result.
  4. **Selection made visible:** the adjudication report states the dropped-game count and
     the naive floor's error on dropped vs kept games, so any easy-subset selection is
     exposed rather than silent.
* Cross-arm and arm-vs-floor comparisons obey the frozen matched-universe rule: exact
  universe-string equality and identical N, else the comparison is not computed (D036 point 4;
  D038; D045 point 3). No exceptions for presentation.
* **The game cluster is the only admissible independent unit; games are never split across
  folds or bootstrap draws** (F13, adopted verbatim).

## 3. Folds and inference

* Five D006 expanding walk-forward folds, `train_lt_2022 … train_lt_2026`, identical to
  cycle 1. Pooled out-of-fold is the primary evaluation surface; per-fold results reported.
* Inference: **game-clustered** bootstrap (the cycle-1 receipted configuration, adopted
  unchanged: B=10,000 test-side for ΔMetric and p-values; B=2,000 train-refit for coefficient
  intervals, per fold). Consistency-finding B2 note for the record: the D045 *board* CIs use
  date-clustering — a different, coarser convention retained there for board context numbers
  only; the gate's inferential unit here is the game cluster, full stop.
* Every number ships with N (games), cluster count, date range, and 95% CI (D036 p7).

## 4. Primary metrics, the test element, multiplicity, and the promotion gate

| estimand | primary metric | secondary (reported, never gating) |
|---|---|---|
| E1 | MAE | RMSE, bias, season splits |
| E2 | MAE | RMSE, bias, season splits |
| E3 | Brier (raw model probability vs settled indicator) | log-loss, 10-bin calibration table (a receipted sealed output) |

**The test element and the multiplicity pin (leakage finding 1).**
* The unit of testing is the **(arm, estimand) pair** — an "element."
* An arm registered against multiple estimands contributes **all** of its elements to its
  single mechanism family; the E1/E2/E3 dimension sits **inside** the family correction.
  Families are frozen at S33/S35 by mechanism (as in cycle 1), never per-estimand; a
  disputed family assignment runs under both partitions and **the stricter result governs**
  (labeled: this is a strengthening of cycle 1, which preserved dual-run disagreements that
  never diverged; here the adjudication rule is frozen in advance).
* **Kills are evaluated uncorrected** (carried from cycle 1).
* A cross-estimand claim ("this arm works") requires the corrected pass on **each** estimand
  claimed — never on the best one. The multi-survivor rule and the program-alpha declaration
  (no program-wide FWER claim; the additive bound stated with the frozen family count) are
  restated in the S35 freeze exactly as cycle 1's P35 did — with one translation pinned here:
  **the multi-survivor comparison operates within-estimand only** (ΔMAE points and ΔBrier are
  not comparable magnitudes; no cross-metric ordering is defined or permitted).

**The gate, per element:**
(a) pooled OOF improvement > 0 against the element's own `K0_MATCHED`;
(b) family-Holm rejection at α = 0.05 under the pin above;
(c) no preregistered kill condition fired — and every kill's diagnostic **must be a receipted
output of the sealed run** (P42 §6 lesson: an uncheckable kill is a card defect);
(d) the possession-first ordering contract (P28) is respected; no secondary or downstream
number exists before its primary verdict.

**K0_MATCHED discipline — with the null-strength floor (leakage finding 2).**
* Base definition: the challenger's own pipeline with zero substantive features, matched on
  the thirteen prose dimensions (rows/universe, folds, offset, intercept, penalty, clipping,
  link, preprocessing, missingness, companion components, fallback, aggregation,
  post-processing) — which map onto the **seventeen machine dimensions of
  `comparison_gate.py`** (cite the mapping; implement against the machine list, not a
  thirteen-item checklist). `calibration_freedom` declared explicitly, never inferred from
  silence. **`estimation_objective` / response family is an explicitly matched dimension**:
  every card declares the training loss (and any shrinkage/regularization and p-clipping
  bounds for E3) for arm and K0 identically; any per-arm deviation at S36 **voids the arm**
  (cycle-1 P35 clause, carried verbatim). `K0_FLAT` remains diagnostic only.
* **Null-strength floor:** every element's K0_MATCHED **must carry, as receipted
  null-granted features** (the cycle-1 K5/A07 pattern), the public composite's own frozen
  ingredients — **pinned to bytes, never to names**: the exact ingredient columns of the
  frozen composite store (`score_baseline_rows.parquet`) by column-level digest, or the
  frozen builder source hash plus its resolved parameters, as the S32B schema specifies. A
  self-reimplemented "EWMA" that matches the name but not the bytes does not satisfy this
  clause. Δ thereby measures value **beyond the public floor**, not beyond an intercept.
* **The cannot-host path is mechanical, labeled, and never promotes unqualified:** where an
  arm's architecture cannot host the null-granted ingredients, its card must **demonstrate
  the blockage mechanically** (the ingredient columns are unrepresentable in the declared
  design, or provably rank-deficient in it) and an S34 reviewer must **reproduce the
  demonstration** — a persuasive argument is not a demonstration. Any gate pass for such an
  element is labeled **"FEATURE VALUE OVER OWN NULL ONLY — BELOW-FLOOR NULL"**; that label is
  inseparable from every citation of the result, the element is **never counted in any
  unqualified pass tally**, and S40 routes any such would-be promotion to the S42 USER gate
  rather than promoting it. Such an element additionally reports (non-gating) its metric
  against the D045 floor recomputed on its exact universe.
* **New K0 schema required (consistency finding B3, disclosed):** the cycle-1
  `K0_MATCHED_SCHEMA.json` (P26) pins `target = REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`
  and **cannot represent E1/E2/E3 controls**. A score-family K0 contract and machine schema —
  the S-lane analog of P26, node `S32B_K0_CONTRACT` — must be frozen before S33 completes.
  Until it exists, no card is registrable. This is stated so the contract never silently
  claims machinery that cannot yet represent its controls.
* Composite-as-K0: permitted only where the K0's `pipeline_id` is identical to the composite
  producer's and the composite's frozen ingredient artifacts appear by hash in the K0
  lineage; adjudicated by the coordinator at highest tier with two independent reviewers
  (GRAPH_POLICY §5). The phrase "genuinely extends" from draft v1 is retired in favor of
  this decidable criterion.

**Declared public floors — referenced, not quoted (leakage finding 7).** The D045 board rows
(`composite_pace_x_eff_v1` and the two naive floors; artifact
`experiments/market_program/SCORE_BASELINES/score_baselines.json`, sha256 pinned at freeze)
are **already-observed public context**. This contract deliberately does not print their
values. Contamination is named and bounded:
* All S33+ authors are **assumed to know the floors and the market bars.** "Cleared the bar"
  is therefore never presentable as a blind result; the adjudication report carries this
  honest-labeling note permanently.
* **No card may reference floor or bar values** in any kill condition, stopping rule,
  coverage predicate, grid choice or justification; S34 checks this explicitly.
* Ideation packets (§7) exclude the D045 numeric rows entirely.
* Floors are context and interestingness bars only; promotion is decided solely by the
  per-element K0 gate above (whose null-strength floor makes the two coincide structurally).

## 5. Distributional endpoints (F13 scope) — secondary this cycle

Arms MAY additionally emit predictive distributions for E1/E2. If they do: CRPS and PIT
calibration are **secondary, exploratory endpoints**, sealed with the primaries and opened
only at S40 (never an unofficial side-channel bar); any distributional claim requires a K0
that itself emits a distribution of the same functional form with matched dispersion
estimation (train-years-only), a **matched quantile grid** where graded by pinball, and
matched treatment of home/away residual covariance (F13 §4.3, restored in full). **No
promotion may rest on a secondary endpoint.**

**Covariance obligation (F13 §3.5/§7(f), carried — consistency finding B6):** any arm that
forecasts the two sides separately, or aggregates player→team→game in any stage, must report
per-side residual variances, the home/away residual covariance and `corr(e_home, e_away)` as
first-class receipted quantities — per the binding `bottomup_3pt_channel_v1` precedent:
per-side improvement is not evidence of game-level improvement until the covariance is shown.

## 6. Market comparison protocol — context, never a gate

* Paired, matched-universe comparison against the LATE cross-book de-vigged consensus,
  exactly the D045 protocol, with the T1 vendor-asserted timing caveat carried verbatim on
  every number; no timing/CLV/reaction inference.
* Market comparison is **reported** and is **never a promotion criterion** this cycle. Any
  "beats the market" claim requires prospective confirmation on witnessed T0 captures — out
  of scope here, F15 pattern.

## 7. Mechanism scope (D047, user-directed) — directed candidates, isolated ideation

Consistency finding B4 exposed a real conflict in draft v1 (required coverage areas listed
inside ideation packets vs D047 p3's "ideation packets stay isolated"). Resolution, frozen
here:
* **The ideation wave (S31) is fully isolated.** Packets contain ONLY this frozen contract
  (which quotes no floor values) and the source's own prompt. No D045 numeric rows, no D046
  priors, no D047 text, no coordinator ideas, no other source's output. Independence is
  structural (GRAPH_POLICY §4).
* **The user-directed families enter as DIRECTED CANDIDATES at synthesis (S32), not through
  ideation.** The coordinator authors them from D047 verbatim; S32 carries every candidate's
  provenance label (`IDEATION_SOURCE_n` vs `USER_DIRECTED`) and directed candidates never
  count toward independent-source tallies. The directed set, from D047: opponent-normalized
  interacting two-team efficiency structures — per-side offensive/defensive strength
  components where each game's realized efficiency is read relative to the opponent's
  concurrent strength, "combined across the two teams (off_A x def_B and off_B x def_A)
  rather than single-team averages" (D047, quoted exactly); home-court structure from a
  single constant upward; rest/travel/schedule with the 2024 charter-program structural
  break modeled explicitly (era interaction or era restriction — pooling across the break
  undeclared is a card defect); referee-crew effects on the totals channel; and the A07
  early-season transient re-registered fresh with its concentration-kill diagnostic as a
  mandatory receipted output (D042/D043).
* **Identifiability acknowledgment (consistency finding C4):** F12 §4.4's finding carries
  forward — off/def decompositions are identifiable only under explicit constraints, and the
  team-level interacting structure has an analogous scale indeterminacy; every directed-
  candidate card must register its identification constraint explicitly.
* Cycle-1 nulls bind: rest/schedule/home arms may not target *pace* mechanisms in the same
  form (P42 §4.4 retry bound); their cycle-2 forms act on scoring.

## 8. Ingredients and cutoff validity

* **Cutoff:** pregame, strictly-lagged information only; no same-game information of any
  kind; each card declares its exact cutoff semantics.
* **Verified pace ingredient** (`team_possession_prior_v1.projected_team_off_possessions`)
  is consumable as-is, frozen, declared regulation-equivalent.
* **Efficiency inputs:** strictly-lagged constructions from owned possession/score data.
* **Market-odds fields are inadmissible — as features AND as coverage-predicate inputs —
  this cycle (P2B, cited by name; leakage finding 4).** P2B ruled the pre-2026-07-30 archive
  permanently CUTOFF_UNPROVEN (a retrospective pull's vendor timestamp "is a claim about a
  past instant, not a witness to it") and found in-play rows inside the extension archives (a
  same-game surrogate). The §8 promotion channel below **explicitly excludes** any field
  whose cutoff validity rests on vendor-asserted timestamps from a retrospective pull. Any
  future market-feature admission requires P2B's open what-is-the-model objection settled at
  USER level first. Any consumption of the live capture stream anywhere filters
  snapshot < commence at the call site (P2B F9).
* **Injury/lineup/availability features are BARRED this cycle** unless drawn from a
  point-in-time store whose capture timestamps are ≤ the declared cutoff with witnessed (T0)
  provenance. The witnessed live injury store began accumulating 2026-08-06/07 (D048 ruling
  2026-08-07; earlier daily captures 2026-07-30..08-04 are separate and likewise cannot cover
  the window) and therefore cannot cover 2021–2026; retrospective injury reconstructions
  without point-in-time provenance are prohibited features (D034 discipline). Availability
  modeling on the live store is prospective-cycle work.
* F13's cutoff-valid field inventory (5 CUTOFF_VALID, 37 CUTOFF_UNPROVEN at its writing)
  binds: an UNPROVEN field used by any arm must first be promoted by a receipted
  cutoff-validity measurement in the S37 audit — subject to the market-field exclusion above.

## 9. Blinding and lifecycle — identical to cycle 1

Sealed-results discipline verbatim: implementation nodes may run unit/synthetic/identity/
schema tests and dry runs that reveal no comparative historical performance; fits write into
`stage3_score/SEALED_RESULTS/`; S39 verifies commit, hashes, row universes, folds, K0
pairing, seeds and completeness **without opening results**; only S40 opens them; adjudicated
numbers reach the board solely through the D036 pipeline. Secondary endpoints seal with
primaries (§5). Lifecycle labels BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED;
never SEALED before an evaluation ran.

## 10. What this contract does NOT do

* Authorize any fit, tuning, registration or comparison (that requires: this contract FROZEN
  + the S32B K0 schema frozen + cards frozen through S33–S35 + S37 audit pass).
* Touch the possession lane, Arm D, or any frozen artifact.
* Create a score-family "champion" — adoption of any fitted score model for operational or
  wager-shaped use is the **S42 USER_REQUIRED gate**, full stop.
* Authorize player-level targets (cycle 3, D043 p3).

## 11. Stop conditions

Carried verbatim from cycle 1, applied to this lane: any finding that would change these
estimands, the K0 structure, the inference structure, the declared universe, the cutoff-valid
feature set or the leakage status HALTS the affected node and is raised to the coordinator
(USER_REQUIRED where policy §6 says so); never resolved inside a node.

---
*Companion machine-readable file `TARGET_CONTRACT.json` is generated at freeze time. The
draft freezes only after re-verification of this revision by the red team and disposition of
every Severity A/B finding; the freeze event pins this file's sha256 in the events ledger.
Red-team disposition map: `RED_TEAM_DISPOSITION.md`.*
