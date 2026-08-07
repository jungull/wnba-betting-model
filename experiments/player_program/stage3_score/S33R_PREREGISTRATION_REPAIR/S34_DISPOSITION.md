# S34_DISPOSITION — finding-by-finding closure of the S34 adversarial review

**Node:** `S33R_PREREGISTRATION_REPAIR` · **Lane:** score · **Cycle:** 2
**Program worktree (the only admissible root, stated explicitly):**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`
**Reviewed artifact (BYTE-FROZEN, not edited):**
`experiments/player_program/stage3_score/S33_PREREGISTRATION_DRAFT/SPEC.json`
**Repaired artifact:** `…/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json`
**Source of the findings:** `orchestration/GRAPH_EVENTS.jsonl`, node `S34_PREREGISTRATION_RED_TEAM`,
event `agent_returned`, ts `2026-08-07T13:53:36Z` — VERDICT FAIL, 4 Severity A, 8 B, 4 C.

> REPAIR. Dispositions S34's findings against the REVIEWED draft, which stays byte-frozen and
> auditable. Emits SPEC_V2.json; authorizes nothing to fit.

**A root-path finding that governs every number below.** `data/masters/master_team.parquet` in the
**program worktree** hashes to `ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528`
— the S33 SPEC pin. The same path in the **main working tree** hashes to
`e8e35b539df2d13f2325e207b9fb2ba8b2e96da476eaa0ec877fcf5588a71c19` and yields a 1,508-cluster
universe with 232 clusters in 2026, because live captures continue there. Every measurement in
this node was re-run against the worktree after that was caught. Measuring the main tree is a
defect, and it is the same class of error that made a prior agent conclude these artifacts were
missing.

---

## Severity A

### A1 — `game_date` cutoff promotion · **CLOSED**

**S34, verbatim:** "the named S37 promotion measurement for the game_date CUTOFF_UNPROVEN field is
barred by S30 section 8's own exclusion (it rests on the P2B-barred retrospective market archive —
406 of the witness rows are 'extension' source), returns zero deviations BY CONSTRUCTION (0/1219
mismatches, cannot falsify), leaves 272 universe clusters unwitnessed (67 pooled-test), never
consults the one column that could detect a reschedule (n_commence_variants>1 on 36 games), and its
second 'independent' witness is master_team's own upstream with a file that does not exist for 240
clusters of test fold 3."

**Every one of those numbers re-derived here, independently:** 1,219 tip_times rows on the
universe; source_table = 813 `drive_master` + 406 `extension`; **0** date deviations; **272**
unwitnessed clusters (205 in 2021, 59 in 2022, 1 in 2023, 1 in 2024, 6 in 2026) of which **67** are
pooled-test; **36** games with `n_commence_variants > 1`. The 240-cluster hole is confirmed:
`gamelog_team_2024_regular_season.parquet` is absent from `data/refresh_2026/` (240 of the 262
clusters of test fold `train_lt_2024`); those rows reach `master_team` through
`data/wnba_team_gamelog_2024.parquet`, which `master_team.source` also names as its own input, so
the "second witness" has zero independence either way.

**The inadmissibility is worse than 406 rows.** P2B `F3_tip_times_provenance` closed the chain:
`data/reference/tip_times.csv` **descends from** the odds archive (builder
`data/reference/collect_bios.py::phase_tips` lines 241–291, per-season counts matching exactly).
*Every* row is archive-derived, not just the 406 extension rows.

**Repair.** The S33-named measurement is **withdrawn**. `M_A1_GAME_DATE_CUTOFF_V2` is registered in
its place and was **run at this node** (`MEASURE_A1_DATE_WITNESS.py` →
`A1_DATE_WITNESS_RECEIPT.json`):

* **Witness A — an NBA-Stats endpoint outside `master_team`'s build chain.**
  `data/shotcharts/shots_<season>_<type>.parquet` (11 files, each sha256-pinned in the receipt)
  carry `GAME_DATE` per `GAME_ID` from the *shotchartdetail* endpoint. `master_team.source` names
  only `gamelog_team_*` / `wnba_team_gamelog_2024`, so this is a different pull. **Covers 2021.**
  Measured: **1,485 of 1,491 clusters witnessed** (all 205 of 2021), **0 date disagreements**,
  0 games with internally conflicting dates. Hole: **6 clusters, all 2026**, enumerated.
* **Witness B — the schedule-release ordinal, a reschedule-*direct* test on all 1,491 clusters.**
  The trailing five digits of a regular-season `game_id` are the league's release sequence number,
  fixed at publication before any game is played; a game moved to another date keeps its number and
  lands out of order. Playoff ids encode round/series/game and are reported separately as
  structural, never as reschedule evidence. Measured: **10 displaced regular-season clusters**, of
  which **one is material** — `1022300038`, played **2023-07-28, 51 days after its next release-order
  neighbour**, with **103 universe games inside the displacement window**. Eight are one-day
  displacements; one is three days.
* **The barred archive is retained as an ALARM-ONLY probe.** Using an excluded channel to attempt
  *falsification* is not promotion through it; using it to *confirm* would be, and is forbidden.
  Convergence: `1022600183` is flagged **both** by the release-ordinal test and by
  `n_commence_variants > 1` — two independently derived flags on the same fixture.

**Verdict on the field.** `master_team.game_date` is promoted to
**`CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS`**, not to unconditional CUTOFF_VALID. The exception set
(10 displaced + 6 unwitnessed clusters) is enumerated by game_id in
`SPEC_V2.a1_game_date_cutoff_promotion.enumerated_exception_set`, carried as the mandatory
non-gating receipt **R-A1-EXCEPTIONS** on every element, and, on SC06 — the only arm whose
*treatment* reads the field — as a new **A1-SENSITIVITY kill**: if removing those clusters flips
the sign of the affected-subset Δ, the arm dies.

**No arm withdrawn.** **What remains unestablished:** no committed artifact in this branch witnesses
what the schedule *said before tip*. Both admissible witnesses are postgame records; a postponement
both endpoints agree on is invisible to Witness A and visible to Witness B only when it breaks
release order.

### A2 — deletion-invariance unsatisfiable for all 17 elements · **CLOSED**

**S34, verbatim:** "the mandatory current-game-deletion invariance receipt is UNSATISFIABLE as
carded for all 17 elements — every element consumes the current game's row of
score_baseline_rows.parquet (the null floor itself) whose prediction columns sit outside the closed
identity set, and that artifact carries actual_total/actual_margin/y_home_win on the SAME rows; S30
section 1 provides exactly one lawful path (identity-set extension by S34 adjudication) and SPEC
registers none."

**Confirmed by measurement.** `score_baseline_rows.parquet` columns are exactly
`game_id, pred_home, pred_away, pred_total, pred_margin, p_home, game_date, season, actual_total,
actual_margin, y_home_win, method` — settled outcomes on the same rows as the predictions. Source-
grain retention proves nothing.

**Repair — the extension is registered** in
`SPEC_V2.schedule_identity_set_extension_s34_adjudicated`:

| extension member | pin | current-game row consumed |
|---|---|---|
| `pred_home` | column sha256 `e754709c…` | yes |
| `pred_away` | `9178138c…` | yes |
| `pred_total` | `16c312ab…` | yes |
| `pred_margin` | `1d79ff3a…` | yes |
| `p_home` | `8a92c017…` (188 structural NaN) | yes |
| `projected_team_off_possessions` | **column pin computed at this node** (none existed): artifact `c37c0751…db18`, 2,990 values, 8 NaN, sort `(str(game_id), str(team_id))`, S32B canonicalisation | yes |

Each is justified as a frozen, hash-pinned, strictly-lagged pregame construction, citing the frozen
builder's own bytes: `build_score_baselines.py` line 286 restricts every efficiency input to
`prior_idx = [j for j in range(len(sub)) if dates[j] < dates[i]]` (strictly earlier dates, never
same-day), and lines 411–437 calibrate the win-probability logistic on strictly-prior **seasons**
only, walk-forward, never pooled. The pace prior is the frozen VERIFIED regulation-equivalent
ingredient S30 §8 declares consumable as-is.

**Columns explicitly NOT extended and nulled by the receipt:**
`score_baseline_rows.{actual_total, actual_margin, y_home_win}` and `master_team.{pts, opp_pts, …}`
on the current game's rows.

**And the lineage is now column-grain.** Every `arms[].features_lineage[].sources[]` entry carries a
`columns` list; every column carries a `classification` — one of
`SCHEDULE_IDENTITY_S30_SECTION_1` / `IDENTITY_SET_EXTENSION_S34_ADJUDICATED` /
`LAGGED_OUTCOME_STRICTLY_PRIOR_ROWS_ONLY` / `IMMUTABLE_REFERENCE_METADATA` /
`PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM` — and a `current_game_row_consumed` boolean. Each arm
also carries a per-column `p22_guard_obligation`. Mechanically checked: `N2` and `N3` in
`SPEC_V2.self_validation.repair_specific_checks`, both `true` over all 11 arms.

The extension is a **reviewable registration, not a self-grant**: if a later reviewer rejects a
member, the affected element set is mechanically readable from the `current_game_row_consumed`
flags.

### A3 — SC01 stratum ambiguity · **CLOSED**

**S34, verbatim:** "SC01's arm-killing early-season stratum is not uniquely determined — the carded
PREDICATE says BOTH-teams (max<=12, 472 clusters) while the carded NUMBERS are the min reading
(516); 9.3 percent apart, and the report's reconciliation is logically incoherent; the kill
terminates all three SC01 elements."

**Re-derived from `master_team.parquet` on the 1,491-cluster universe**
(`MEASURE_A3_B_STRATA.py` → `A3_B_STRATA_RECEIPT.json`), with the clock defined as same-season
strictly-prior completed games on the pinned row base:

| reading | pooled | per test season 2022/23/24/25/26 | 2021 (training only) |
|---|---|---|---|
| `max(n_H,n_A) ≤ 12` — **BOTH** teams early | **472** | 75 / 76 / 74 / 81 / 92 | 74 |
| `min(n_H,n_A) ≤ 12` — at least one early | 516 | 81 / 80 / 82 / 88 / 103 | 82 |

**Pinned: `max(n_H, n_A) ≤ 12`, count 472.** The card's predicate text ("BOTH teams ≤ 12") is kept
and the *number* is corrected — J12 itself declared the BOTH reading the intended conservative one,
so the predicate was right and the arithmetic was wrong. **J12's reconciliation is false and is
corrected on the record:** "each team ≤ 12" is `max ≤ 12`; `min ≤ 12` means *at least one* team is
early. Non-empty in every fold, so the kill stays checkable. SC02 (`min ≤ 5` → 249) and SC03
(`min < 10` → 399) card their reducer explicitly, agree with their numbers, and are re-derived
unchanged; every stratum in V2 now states its reducer.

### A4 — SC08::E3 null strength · **CLOSED**

**S34, verbatim:** "SC08::E3's K0 does not host the E3 null-granted ingredient in the prediction
path (its map is OLS-to-margin plus Gaussian MLE, never fitted to the win outcome, unlike SC01/SC06
whose logistic DOES reproduce the builder), so it is eligible for the unqualified label over a null
never shown to reach the floor — and the defense exists only in the report, not the binding SPEC."

**Confirmed from the record's own bytes.** SC08::E3's `estimation_objective.training_loss` is
`gaussian_mle_on_train_margin_residuals_for_dispersion_parameters_only__mean_path_frozen_before_
dispersion_fit`, and its `missing_value_handling` states outright that "the prediction path never
consumes p_home" — the byte-pinned floor column is carried as an inert anchor.

**Repair — the receipt route, deliberately, not the refit.** Refitting SC08's mean map to the win
outcome would change the element's estimation objective and K0 structure, which S30 §11 makes a
**stop condition for this node**. Registered instead, in the binding records:

* **`R_SC08_FLOOR` — MANDATORY sealed receipt** (`verdict_label_policy` + `notes` on the element,
  full rule in `SPEC_V2.a4_sc08_null_strength_receipt`): pooled and per-fold Brier of (i) SC08::E3's
  own `K0_MATCHED` probability path and (ii) the frozen byte-pinned `p_home` column, on the
  identical matched universe with identical handling of the 188 structural NaN rows. Both are
  **control** objects; no challenger number enters. Absence is a card defect.
* **Preregistered below-floor rule:** if the K0's pooled Brier is not strictly better than the
  frozen `p_home` column's, the K0 is declared not to have reached the public floor and the element
  takes **"FEATURE VALUE OVER OWN NULL ONLY — BELOW-FLOOR NULL"**, inseparable from every citation,
  excluded from every unqualified pass tally, with **S40 routing any would-be promotion to the S42
  USER gate**, plus the non-gating D045-floor-on-exact-universe row.
* **Floor/bar discipline checked explicitly:** the rule references the floor *artifact column* S30
  §4 already obliges every K0 to carry by byte pin, prints no floor or bar **value**, and is a
  **labelling** rule — not a kill, stopping rule, coverage predicate or grid choice, the four things
  S30 §4 forbids from referencing floor values. A mechanical scan for the three D043 bar numerals
  over `SPEC_V2.json` passes (`N6`).
* The J3 justification is moved out of the report into the binding records, and the same
  agreement receipt is registered **non-gating** on SC01::E3 and SC06::E3, whose per-fold logistic
  of the composite margin on seasons `< Y` *is* the frozen builder's walk-forward construction.

---

## Severity B

| # | finding | disposition |
|---|---|---|
| B1 | R5 key-vs-name mismatch on SC06's two records + the false PASS | **CLOSED** |
| B2 | two undeclared strictly-prior row bases in live simultaneous use | **CLOSED** |
| B3 | SC12's inertness kill cannot fire; its justification is reversed | **CLOSED** |
| B4 | SC10's orthogonalisation covariate has no lineage, hash or P22 obligation | **CLOSED** |
| B5 | SC02's retirement kill has no numeric threshold | **CLOSED** |
| B6 | the uncarried SC10↔SC12 family dispute | **CLOSED (carried)** |
| B7 | SC05's disputed assignment unregistered on its own card | **CLOSED** |
| B8 | SC09's `calibration_freedom` contradicts its own treatment | **CLOSED (re-carded)** |

**B1.** S33 declared the era main effect under the key `era_2024_main_effect` while the treatment
term is `ERA2024:fatigue_diff`. R5 as written in the S32B schema is a *literal key* rule — "a
treatment term 'FACTOR:feature' requires FACTOR's main effect in `k0_spec.structural_terms`" — and
`ERA2024 ∉ {composite_pred_margin, era_2024_main_effect}`. S33's self_validation reported PASS by
matching intent instead of keys. **Repaired** by renaming the main effect to the byte-identical key
`ERA2024` in both sides' `structural_terms`, `declaration_routing`, `nuisance_terms` and
`lower_order_structural_terms` on both SC06 records. **Demonstrated mechanically, not asserted:**
`VALIDATE.py` was run against the frozen S33 bytes and against V2 — S33 fails exactly the two SC06
records on literal R5 (recorded verbatim in
`SPEC_V2.self_validation.same_validator_run_against_the_frozen_S33_bytes`), V2 passes 17/17.

**B2.** Both bases were genuinely live: the 1,491-cluster resolved universe and the 1,495-cluster
full schedule. **Pinned to ONE: the 1,491-cluster resolved universe**, for every strictly-prior
construction, arm and K0 alike, declared in `shared_universe`-adjacent form on every arm
(`strictly_prior_row_base`, check `N5`) and inside every record's `invariants.rows`. **Measured
consequence of the pin:** 187 universe clusters have different same-season strictly-prior counts
under the two bases — **all 187 are 2021 games, i.e. training-only rows in every fold; zero in any
test season.** Carded stratum counts move: SC01 `max≤12` 472 vs 470, `min≤12` 516 vs 510, SC02
`min≤5` 249 vs 245, SC03 `min<10` 399 vs 394 — **no test-season stratum count changes.**

**B3.** The kill read "< 8% of prior-game inputs actually clipped at the frozen cap". Measured on
the pinned base: **780 of 2,982** team-game margin observations exceed ±15 = **26.16%**, and the
**lowest** per-season share is **20.61%** (2024). The 8% floor is unreachable from above — the kill
cannot fire. The S33 justification ("so the floor is live, not vacuous") reads the same measurement
backwards. **Repair:** the incidence table survives as a **mandatory non-gating receipt**; the kill
moves onto the statistic that carries the mechanism's bite, `|w_H − w_A|` where
`w = EWMA(clip(margin,±15)) − EWMA(margin)`. Pre-registration distribution over the 1,491 clusters:
median 1.704, p75 3.068, p90 4.706, max 13.0 points; 9.93% of clusters below 0.25 points. **New
kill:** pooled ΔMAE(E2) ≤ 0 on the high-bite subset `|w_H − w_A| ≥ 2.0` — habitat measured at **652
pooled clusters (43.7%)**, per test season 97/118/102/141/107, non-empty in every fold. A second,
explicitly labelled **implementation-integrity** kill fires if p90 of `|w_H − w_A|` < 1.0, which on
the frozen construction can only mean a build defect.

**B4.** The covariate existed only in a K0 note. It is now a first-class
`features_lineage` entry on the SC10 arm block — `trailing_opponent_strength_diff` — with source
`data/masters/master_team.parquet` sha256 `ad79ce5c…`, its consumed columns and their identity
classification, lag semantics (same-season strictly-prior settled games only; no current-game score
column), an explicit per-column P22 obligation, and a **measured** support floor: both sides have
≥ 4 same-season strictly-prior games on **1,322 of 1,491 clusters (88.67%)**; the remaining **169**
take the declared zero fallback, identically on both sides. It enters only the declared kill-bearing
orthogonalised variant, never the primary head, and needs no source the slate does not already
consume.

**B5.** "Condition-number failure" now has a number: **κ₂ ≥ 1000** on the fold's *training* design
matrix `[intercept, standardised null-granted column, standardised treatment term]`; failure in ≥ 2
folds retires the arm UNEVALUATED; the per-fold κ₂ table is a mandatory sealed receipt. The
threshold is a pinned convention, informed by no floor or bar value. Pre-registration feasibility
(a condition number involves no target and no metric): per-fold maxima 1.087 / 1.241 / 1.211 /
1.143 / 1.121, overall **1.241** — far below the threshold, so the kill is a live guard against an
implementation that actually degenerates rather than a pre-satisfied formality.

**B6.** **Carried.** SC10 and SC12 are both level-free contrasts of an EWMA over each side's own
strictly-prior settled results, differenced across sides, added to the same null-granted composite
head — at least as close a kinship as the SC04↔SC11 lagged-league-drift merge the draft already
carried. Registered as **partition D, `FAM_S2_LAGGED_OWN_FORM = {SC10, SC12}` (3 elements)**, on
both arms' cards and all three K0 records. **Alpha arithmetic, stated:** the additive bound uses the
maximum family count over registered partitions; D is a *merge*, and a merge never raises the count,
so the maximum is still 10 (partition B) and the bound is **unchanged at 8 × 0.05 = 0.40 primary /
10 × 0.05 = 0.50 maximal.** D makes Holm strictly *harder* for those three elements.

**B7.** SC05's dual assignment lived only in the multiplicity block. It is now registered on the
SC05 arm card (`family_disputed`) **and** on its own K0 record's notes: partition A
`{SC04, SC05}`; partition B merges SC04 with SC11 and leaves `{SC05}` alone; survive both, stricter
governs.

**B8.** `calibration_freedom = "none"` is accurate for the *post-fit machine dimension* — SC09's
hinge is a within-head regressor, not a post-fit fix-up — so changing that string would have broken
Layer-A byte identity for no gain. The real defect is the **kind claim**: the treatment is
`h(ĝ) = sign(ĝ)·max(0, |ĝ| − 8)` on the **K0's own fitted prediction**, which introduces no
information the null lacks. **SC09 is re-carded `arm_kind: "calibration_only"`** (its
`tested_parameters` is non-empty, so the P26 1.5 validator rule holds), its `verdict_label_policy`
rewritten so the element **may never be reported as feature value however large `challenger_vs_k0`
is**, and the `calibration_freedom` string amended **identically on both sides** to say explicitly
that "none" describes the post-fit dimension only while the arm *is* a shape-restricted
recalibration of the null's prediction in the scientific sense. Consequence recorded before any fit.

---

## Severity C — **NOT RECOVERABLE; stated plainly rather than invented**

S34 wrote no artifact directory. The only surviving text is the `agent_returned` event, which
enumerates the four Severity A findings and gives **counts only** for B and C. The eight B findings
reached this node through its own acceptance criteria; **the four C notes did not, and no other file
in the repo carries them** (`DECISION_LEDGER.jsonl` has one S34 entry, D050, about operating policy;
`COORDINATOR_HANDOFF_2026-08-07.md` reports "4 Severity A, 8 B, 4 C" and details only the A's).

Rather than invent quotations, `SPEC_V2.s34_severity_c_notes` dispositions the **four items the S33
draft itself escalated to S34**, clearly labelled a reconstruction:

1. **J3 — "S34 should review this E3 K0 probability-path reading explicitly."** **ANSWERED** by A4.
2. **J11 — "S34 should confirm this reading or demand a pre-build digest of the game_id set."**
   **ACCEPTED WITH REASON** — no feature matrix exists before S36, but the row *base* is now pinned
   in `invariants.rows` and the universe is already pinned by count, per-season census and the
   measured identity with the frozen store's `league_average_v1` id set. A pre-build game_id-set
   digest is available to S35 at zero cost and is recommended.
3. **The pooled-floor denominator reading (S32B §5.5).** **ACCEPTED WITH REASON** — measured moot
   for this slate (100% retention under both readings, re-derived here); both denominators continue
   to be reported and the stricter governs; the reading stays flagged for any future boundary card.
4. **`pipeline_id` asserted, not demonstrated.** **ACCEPTED WITH REASON** — a property of the frozen
   `comparison_gate`, which this node may not modify. Recorded as an inherited limitation.

**Recommendation to the independent re-verifier:** if the S34 reviewer's Severity C text can be
recovered from its session transcript, re-run this section against the real notes before S35
freezes. Until then this is the one part of the mandate that is **not** closed against the actual
review.

---

## Result

* **11 arms retained · 17 elements · 1 withdrawal (SC07, unchanged) · 8 primary families / 10
  maximal · 4 registered partitions (A, B, C, D) · additive program-alpha bound 0.40 / 0.50,
  unchanged.**
* **All four Severity A: CLOSED.** No arm withdrawn; no arm re-carded out of the slate. SC06, SC09,
  SC12, SC10, SC02, SC05 and SC01 are re-carded in place.
* **All eight Severity B: CLOSED.**
* **Four Severity C: not recoverable from the program record; four reconstructed items
  dispositioned, one ANSWERED and three ACCEPTED-WITH-REASON.**
* `SPEC_V2.json` — 17/17 records pass schema validation **and** the literal cross-field rules under
  a validator that raises on any keyword it does not implement; 8/8 repair-specific checks pass; the
  same validator fails the frozen S33 bytes on exactly the two SC06 records, which is B1 made
  mechanical.
