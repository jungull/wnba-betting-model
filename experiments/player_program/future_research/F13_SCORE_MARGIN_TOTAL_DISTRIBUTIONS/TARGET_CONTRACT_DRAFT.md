# F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS — TARGET CONTRACT DRAFT

**Node:** F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS · lane `future_research` · type `documentation` ·
role: read-only research scout. Generated 2026-08-04.

DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration and an independent gate review.

---

## 0. The one-line answer

**The estimand is `NOT_DERIVABLE_FROM_DOCUMENTATION`.**

The player program's documentation names this track, names its construction order, names its
accounting constraints and names its binding negative precedent. It nowhere states the target
statistic, its unit or its denominator for a score / margin / total *distribution*. I have not
supplied one. A candidate estimand does exist on the **team** thread (§3.4) and it is deliberately
**not** adopted here, for four stated reasons.

This draft therefore registers an absence, not a specification. §4 states the matched-K0
requirement that would attach to whatever estimand is one day written; §5 inventories the
cutoff-valid evidence as measured; §6 lists the blockers; §7 states what this draft does not do.

---

## 1. What "estimand" is being asked for

A target contract needs three things this program keeps distinct:

| component | question it answers |
|---|---|
| **target statistic** | *what quantity is being estimated* — e.g. the predictive distribution of a game's final margin |
| **unit** | *the scale and the row grain* — points? probability? per team-game, per game cluster? |
| **denominator** | *conditional on what* — the opportunity/exposure base the quantity is a rate over, or the population the average is taken across |

A metric name alone is not an estimand. "CRPS" is a scoring rule; it does not say what is being
scored, on what rows, against what baseline. G04 established that thirteen documented tracks carry
machinery and no estimand (`orchestration/reports/ROADMAP_EXTRACTION.json`,
`counts.needs_target_contract = 13`). This track's documentation is of the same character.

---

## 2. Estimand: NOT_DERIVABLE_FROM_DOCUMENTATION

Stated in the required terms:

* **target statistic** — NOT_DERIVABLE_FROM_DOCUMENTATION
* **unit** — NOT_DERIVABLE_FROM_DOCUMENTATION
* **denominator** — NOT_DERIVABLE_FROM_DOCUMENTATION

No document in the player program states which of {home score, away score, margin, total} is the
graded object; whether the graded object is a full predictive distribution, a set of quantiles, an
interval, or a cover probability against a market line; what scoring rule is primary; what the
comparison baseline is; or whether the denominator is the team-game row or the game cluster.

---

## 3. What I did find, with citations

### 3.1 The track is registered as an *obligation*, with no metric

`experiments/player_program/register_program_roadmap.py`, record `player_program_objective_v2`
(`authorises_execution: False`, line 45):

* line 84 — `multi_stage_forecast_structure` ends with `"predictive distribution and uncertainty"`.
* lines 115–119 — `simulation_causal_order` ends `"player and team scoring", "uncertainty distributions"`.
* lines 121–128 — `accounting_constraints`: team minutes sum to 200; player possessions reconcile
  to team possessions; rebounds originate from missed shots; assists relate to made field goals;
  made shots cannot exceed attempts; player totals reconcile with team totals; both teams'
  possession accounting is coherent.
* lines 130–131 — `correlation_requirement`: `"preserve correlations between event channels rather than independently sampling every statistic"`.
* lines 320–321 — `predictive_uncertainty.requirement`: `"each mature event channel emits an uncertainty DISTRIBUTION, not only a mean"`.
* lines 86–89 — the wave process makes `"baseline metric"` a **P0 deliverable**, i.e. the metric is
  something the program owes, not something it has.

Causal order, constraints and a correlation requirement are a *construction specification*. None of
them is a target statistic, a unit or a denominator.

### 3.2 The generative side is recorded as not started; the evaluation side is canonical

`experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md`:

* line 289 — heading `### uncertainty and simulation — 'not started'`.
* lines 291–293 — `"No simulation code exists."` … `"so the *evaluation* side is 'canonical' while the *generative* side is 'not started'."`
* lines 293–296 — constraints already enforced by the exposure bridge (team minutes 200; player
  possessions reconcile; both clubs coherent) versus `"Constraints not yet enforced anywhere: rebounds originate from missed shots, assists relate to made field goals, makes ≤ attempts."`

I verified the evaluation-side claim against bytes rather than accepting it: `evalharness/metrics.py`
defines `pinball_loss` (line 63), `mean_pinball_loss` (87), `crps_ensemble` (92), `mean_crps` (116),
`brier_score` (136), `log_loss` (142), `reliability_table` (149), `interval_coverage` (195). The
primitives exist. **Having a scoring rule implemented is not having an estimand.**

### 3.3 The player-side coverage record for exactly this object is ABSENT

`PLAYER_RESEARCH_COVERAGE_MATRIX.md` (repository root):

* line 73 — `### Stage E — final stat distributions`; line 75 — `"**ABSENT in full.** No points, rebounds, assists, 3PM, FTA or turnover distribution."`; lines 76–77 — `player_scoring_distribution` is `"a **conditional centre plus a fold-level σ**, not a distribution over points."`
* line 162 — downstream gate: `"**ABSENT in full.** No player prediction has ever been aggregated to a team quantity."`
* line 166 — `| aggregate to home score / away score / margin / total | **ABSENT** |`
* line 46 — even the *minutes* quantiles are `"BUILT-U, shape only"`, emitted `"from a **single fold-level dispersion σ with fixed z-offsets** — not a fitted conditional distribution."`

`experiments/player_program/PROJECT_UPDATE_2026-08-04.md`:

* line 284 — `"**Deferred.** Staged distributional layer; decision-time comparison; player props last…"`
* lines 463–465 — `"Complete-gate simulation under hypothetical effects was not attempted — shifting the margin series while holding home/away/total fixed is incoherent (margin ≡ home − away), and no generative model of joint four-target challenger effects exists."`
* line 635 — the staged construction lead (`marginals → within-player dependence → team reconciliation → cross-team`) is filed in **Appendix G, external research leads**, at `"hypothesis-generation strength only"` (line 629). It is an idea the program noted, not a commitment it made.

### 3.4 A complete estimand DOES exist — on the team thread — and this draft does not adopt it

This is the finding that most tempts invention, so it is recorded in full and then declined.

* `ROADMAP.md` line 138 — `"Score/margin/total MAE and RMSE; pinball loss on forecast quantiles; CRPS (distributional); cover-probability Brier; log loss; reliability/calibration plots."` This is a **metric menu for four leaderboards**, not an estimand: no primary, no unit, no denominator, no baseline.
* `experiments/registry.jsonl` line 18 — `dist_margin_cover_v1`, `schema: "evalharness/1"`, `kind: "experiment"`, `registered_at: "2026-07-30T21:23:43.828696+00:00"`, `decision_time: "T-24h"`, `primary_metric: "margin_crps"`, `incumbent_id: "gaussian_train_sigma_baseline"`, `extra.universe: "the 673 chanreval test games for CRPS; the odds-covered subset for cover metrics"`, `thresholds.min_improvement: 0.05`, `thresholds.per_season_tolerance: 0.1`, `thresholds.coverage_tolerance: 0.0`. That **is** a complete estimand: statistic = the predictive distribution of team game margin, graded by CRPS; unit = points, per game; denominator/population = 673 chanreval test games, walk-forward 2024/2025/2026, date-clustered.

**Four reasons it is not this node's estimand.**

1. **Wrong thread.** It is a team-thread registration on the team leaderboards. The player and team
   programs are run as isolated threads; importing a team registration into a player-lane contract
   would create a cross-thread commitment nobody made.
2. **Wrong universe.** Its denominator is 673 games from `experiments/channel_reval/predictions_v2.csv`.
   The player program's contracted universe is 2,982 team-game rows over 1,491 game clusters
   (§5.1). These are different populations; silently substituting one is the exact failure this
   draft exists to prevent.
3. **Its own primary metric is contradicted in the record.** `project_docs/ASSUMPTION_AUDIT_2026-07-30.md`
   lines 537–539 design E1 with `"Preregister: primary = cover-Brier vs the line-implied-probability benchmark; floor challenger = constant-σ"`, while the registry record that landed the same day carries `primary_metric: "margin_crps"`. A precedent whose own primary metric is disputed between design and bytes cannot be lifted as settled.
4. **It carries no player-side aggregation obligation.** The binding precedent below applies to any
   player→team aggregation candidate and is absent from the team registration.

### 3.5 The binding precedent any future estimand must carry

`PLAYER_RESEARCH_COVERAGE_MATRIX.md` lines 204–221, on `bottomup_3pt_channel_v1`:

* lines 204–209 — `"The player layer won at its own target and lost the game."` Because
  `var(margin err) = var(e_h) + var(e_a) − 2·cov(e_h, e_a)`, the bottom-up channel reduced each
  side's error variance yet decorrelated the two sides.
* line 213 — `"**Per-side improvement is not evidence.** Every aggregation candidate is judged on margin and total, not on its own channel."`
* lines 215–217 — `"**corr(e_home, e_away) is a first-class reported quantity**, alongside the two variances, for every aggregation candidate."`
* `PLAYER_MODEL_CAPABILITY_MATRIX.md` line 282 — `"any aggregation experiment must report home/away residual variance, covariance, corr(e_home, e_away), and resulting margin variance and MAE"`.

Note what this is: a reporting obligation on **point** error, expressed in variances and
covariances. It constrains an estimand; it is not one. It is also the sharpest argument against
inventing a distributional estimand here — a distributional contract written without carrying this
requirement forward would silently drop the program's one binding aggregation precedent.

---

## 4. The matched-K0 requirement for this target

Stated as it would attach to any estimand later written for score / margin / total distributions.

**4.1 K0 is authoritative and per-arm.** `K0_FLAT` is diagnostic only; `K0_MATCHED` is authoritative
and is per-arm. K0 is the challenger's own pipeline with zero substantive features
(`experiments/player_program/comparison_gate.py` lines 37–40: `"K0 is the challenger's own pipeline with zero substantive features. There is no legitimate reason for any dimension to differ"`).

**4.2 Layer A is strict and non-adjudicable.** A Layer A mismatch is blocking and is not adjudicable
by an ordinary reason (comparison_gate.py lines 41–43). The prose dimension list — rows and
universe; folds; offset; intercept; penalty treatment; clipping; link; preprocessing; missingness;
companion components; fallback; **aggregation**; post-processing — maps onto seventeen machine
dimensions (lines 66–74). `aggregation` is called out there as `"genuinely new"` and is precisely
the dimension a player→team score/margin/total layer moves in.

**4.3 The distribution-specific requirement — this is the part that does not exist yet.**
A featureless control that emits only a point forecast **cannot be compared on a distributional
scoring rule**. For a distributional target, K0 must itself emit a predictive distribution *of the
same functional form, produced by the challenger's own pipeline*, with the substantive features
zeroed and nothing else changed. Concretely, the K0 must fix, and match the challenger on:

* the distributional family or the sampler (a Gaussian-σ control and an ensemble-sample control are
  not interchangeable);
* the dispersion estimator and the rows it is estimated on (train-years-only; no test residuals);
* the quantile grid, if the object is graded by pinball;
* the aggregation from player grain to team grain, including how home and away residuals are
  allowed to co-vary — because under §3.5 the covariance is the mechanism, a K0 that imposes
  independence and a challenger that does not are not parity-matched;
* any post-fit calibration (comparison_gate lines 72–74 place `calibration_freedom` under
  "post-processing" precisely because it `"must never be inferred from silence"`).

**None of this is specified anywhere in the player program today.** There is no featureless
distributional control, and no code that could emit one (`"No simulation code exists"`,
capability matrix line 291).

**4.4 The three contrasts must be reported separately** and never collapsed
(comparison_gate.py lines 87–92): `challenger_vs_k0` = FEATURE VALUE = the primary test;
`challenger_vs_incumbent` = operational relevance only; `k0_vs_incumbent` = free flexibility. The
hard rule (lines 55–59): a challenger that beats the frozen incumbent but not its own K0 has **not**
demonstrated feature value.

**4.5 Known K0 defects that would apply to this target.**

* `pipeline_id` is asserted, not demonstrated (comparison_gate.py lines 98–108); PROGRAM_STATE
  `open_methodological_gaps` `pipeline_id_asserted`, severity C.
* `ws6_no_featureless_control`, severity B — a precedent of an arm with no K0 of any kind.

**4.6 Clustering.** Games must never be split across folds or cluster-bootstrap draws. For margin
and total this is structural, not merely conventional: the home and away rows of a game are the two
halves of the same quantity, so the game cluster is the only admissible independent unit. Folds are
the five expanding-window chronological folds in §5.3.

---

## 5. Cutoff-valid evidence — inventoried, not assumed

Every figure in this section was computed or read directly during this node; the command is named.

### 5.1 The universe, and a documented mismatch in it

The contracted universe is **2,982 team-game rows over 1,491 game clusters**
(`data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json → row_universe`, digest
`raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371`).

The same record states the event/contract universe is **wider**: `prediction_contract_v4/game.parquet`
and `EVENT_SOURCE_INVENTORY.json` carry 1,495 games and `master_team` carries 2,990 team-game rows;
the 4-game / 8-row difference is `"the possession producer's own exclusion and is reported, not reconciled here."`

I confirmed both sides of that mismatch from bytes:

* `possessions_v2/possessions_raw_v2.parquet` — 238,563 rows, **1,495** distinct `game_id`
  (pandas `read_parquet`, `game_id.nunique()`).
* `projected_exposure_v1/team_possession_prior_v1.parquet` — **2,990** rows × 11 columns.

**Consequence for this target: the denominator is contested at the row level and must be chosen
explicitly, not inherited.** 1,491 vs 1,495 game clusters is a 0.27% difference in the population a
CRPS-like average would be taken over.

### 5.2 The cutoff definition in force

From the same D10 record (`cutoff_definition`):

* source: `experiments/prediction_contract_v4/game.parquet::forecast_cutoff`;
* two policies — `exact_tip_T-90m` (scheduled tip minus 90 minutes) and
  `date_only_prior_day_cutoff` (18:00 UTC the day before);
* universe games joined to a cutoff: **1,491**;
* policy counts over universe team-games: **2,168** date-only, **814** exact-tip;
* the rule: `"a field is CUTOFF_VALID for a row only if a per-row source observation timestamp exists and is <= that row's forecast_cutoff. No timestamp means CUTOFF_UNPROVEN. Structural plausibility is never a substitute."`

### 5.3 Folds

`possession_features.chronological_folds()`, expanding-window, one fold per season with at least one
strictly earlier season, games never split across folds (D10 `fold_structure`):

| fold | test season | cutoff date | train rows | test rows |
|---|---|---|---|---|
| train_lt_2022 | 2022 | 2022-05-06 | 410 | 478 |
| train_lt_2023 | 2023 | 2023-05-19 | 888 | 520 |
| train_lt_2024 | 2024 | 2024-05-14 | 1,408 | 524 |
| train_lt_2025 | 2025 | 2025-05-16 | 1,932 | 620 |
| train_lt_2026 | 2026 | 2026-05-08 | 2,552 | 430 |

D10 also records that `prediction_contract_v5/player_game_enriched.parquet` carries a *different and
degenerate* `fold_id` of the form `season:YYYY` (six values, no train/test split), and that the two
are not the same object.

### 5.4 Predictor-side cutoff-valid evidence: five fields out of fifty-two

D10 `verdict_counts` over 52 catalogued fields:

| verdict | count |
|---|---|
| CUTOFF_VALID | **5** |
| CUTOFF_UNPROVEN | 37 |
| CUTOFF_INVALID | 3 |
| ABSENT | 7 |

The five CUTOFF_VALID fields are, in full:

1. `tip.scheduled_tip_time__contract_v4_screened`
2. `injury.status`
3. `injury.reason`
4. `injury.report_date`
5. `roster.captured_availability_affiliation`

**None of the five is a scoring, pace, or prior-performance quantity.** The fields a
score/margin/total model would actually want are not among them:
`opponent.opp_pace_estimate` — CUTOFF_UNPROVEN; `opponent.prior_box_aggregates` — CUTOFF_UNPROVEN;
`rest.days_since_prev_game`, `rest.is_back_to_back` — CUTOFF_UNPROVEN;
`sched.is_home`, `sched.game_date` — CUTOFF_UNPROVEN. Three fields are CUTOFF_**INVALID**:
`tip.tip_hour_et__pbp_wallclock`, `roster.starter_flag`, `roster.roster_asof_tenure`.
All four coaching fields are ABSENT.

Availability is not eligibility, and eligibility is not admission. This ledger records availability.

### 5.5 Outcome-side evidence: realized score, margin and total are derivable

Measured with pandas over `experiments/player_program/possessions_v2/possessions_raw_v2.parquet`,
taking the last possession per `game_id` ordered by `canonical_seq` and adding `points_scored` to the
offensive side of `home_pts_before` / `away_pts_before`:

| quantity | n | mean | sd | min | max |
|---|---|---|---|---|---|
| home score | 1,495 | 83.443 | 11.432 | 49 | 125 |
| away score | 1,495 | 81.764 | 11.676 | 47 | 123 |
| margin (home − away) | 1,495 | 1.680 | 14.014 | −53 | 48 |
| total | 1,495 | 165.207 | 18.376 | 111 | 247 |

Games by season/type: 2021 R192/P17, 2022 R216/P23, 2023 R240/P20, 2024 R240/P22, 2025 R286/P24,
2026 R215. Ties at end of game: **0**.

**The overtime split, which is load-bearing here.** 66 of 1,495 games contain at least one
possession flagged `is_overtime`. Recomputing the same quantities over regulation possessions only:

| quantity | full game | regulation only |
|---|---|---|
| sd(margin) | 14.014 | 13.952 |
| sd(total) | 18.376 | 17.650 |
| mean(total) | 165.207 | 164.248 |

The primary target is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, and realized duration may
normalize a completed-game historical outcome **only**; current-game realized overtime,
`game_minutes`, duration, overtime periods and any same-game surrogate are prohibited from the
prediction path. A score/margin/total distribution therefore faces an undocumented fork: is the
graded object the **full-game** outcome (which the bettable object is) or the
**regulation-equivalent** outcome (which the program's possession target is)? The two differ
materially in dispersion — 0.73 points of sd on total. **No document resolves this.** It is a
first-order component of the missing estimand, not a detail.

### 5.6 Prospective evidence: eight rows

`forecasts/forecast_log.jsonl` — **8** lines (counted directly). Capability matrix line 303 records
the same count, and line 307 records `must not reuse: "8 entries as prospective evidence of anything"`.
There is no prospective distributional evidence.

### 5.7 What is NOT inventoried here

`experiments/player_program/stage2b/SEALED_RESULTS/` was not read; it is a forbidden input.

---

## 6. Known data blockers

Blockers that would bind any future fit against this target, each with a citation.

**Structural / modelling**

1. **No generative model exists anywhere.** `"No simulation code exists"` (capability matrix 291);
   `"no generative model of joint four-target challenger effects exists"` (PROJECT_UPDATE 464–465).
2. **Three accounting constraints are enforced nowhere** — rebounds originate from missed shots,
   assists relate to made field goals, makes ≤ attempts (capability matrix 295–296). A simulator that
   violates these can still be scored, which is exactly why the constraint list is not a substitute
   for an estimand.
3. **No projected substitution timing** (capability matrix 323–325). v1 exposure assigns equal
   offensive and defensive possessions; until a stint-level projection exists no experiment can
   distinguish offensive from defensive exposure.
4. **Opportunity denominators do not exist** (capability matrix 319–322). Rebound opportunities,
   potential assists, blockable attempts and touches are not derivable from the possession stream and
   only partly from the event stream.
5. **Neither source supplies free-throw outcome or offensive-vs-defensive rebound type**
   (capability matrix 314–318). Both sit on the causal path from possessions to points, so a
   bottom-up points distribution cannot presently be built from documented components.

**Provenance / admissibility**

6. **`general_feature_producer_provenance`, severity A** (PROGRAM_STATE `open_methodological_gaps`):
   only `possession_features.py` emits a producer construction receipt, so any arm fitted through
   another producer caps at `RAW_PROVENANCE_ASSERTED` and is not a full Stage 1 pass.
7. **`cutoff_validity_asserted`, severity B**: `cutoff_valid` is asserted per source and bound into
   the receipt forever, but it is a property of upstream construction and cannot be verified from
   bytes. Every CUTOFF_VALID verdict in §5.4 inherits this.
8. **`validator_lineage`** and **`fresh_execution_unprovable`**, both severity B — the receipt chain
   is not cryptographically closed and a copied-forward receipt cannot be distinguished from a rerun.
9. **`pipeline_id_asserted`**, severity C — bears directly on §4.5.

**Universe / evidence**

10. **The row universe is contested** — 2,982/1,491 versus 2,990/1,495, documented as unreconciled (§5.1).
11. **Predictor-side cutoff-valid evidence is five fields, none of them performance-related** (§5.4).
12. **Prospective evidence is eight rows and explicitly unusable** (§5.6).

**Authorisation**

13. `PROGRAM_STATE.json` → `state_of_play.experiment_currently_authorized = false`;
    `state_of_play.next_substantive_direction = "REQUIRES USER AUTHORIZATION"`;
    `stop_boundary.in_force = true`, which forbids beginning a confirmation experiment, promoting any
    discovery arm, altering the canonical exposure or canonical target, and appending new scientific
    registry records without fresh authorisation.

---

## 7. This draft does NOT authorise fitting

Stated plainly, as the acceptance criteria require:

**This draft does not authorise fitting.** It does not authorise building a generative or
simulation layer, fitting a distributional head over any existing point forecast, computing CRPS,
pinball loss, cover-Brier, log loss or interval coverage against any outcome, registering an arm, or
touching any frozen artifact. It is a record of an absence and an inventory of what exists.

Fitting requires **all five** of: a target contract, a matched K0, cutoff-valid evidence, a
preregistration, and an independent gate review. **None is in this node's gift**, and on the
evidence above at least three of the five do not currently exist for this target: there is no
estimand (§2), there is no distributional featureless control (§4.3), and the predictor-side
cutoff-valid inventory is five non-performance fields (§5.4).

The correct next step is **not** to write an estimand faster. It is for the estimand to be issued as
a versioned specification under `RESEARCH_CONTRACT_V1`, by the authority that can make a commitment
on the program's behalf, resolving at minimum: (a) which of home/away/margin/total is graded;
(b) full-game or regulation-equivalent (§5.5); (c) the primary scoring rule and its unit;
(d) the denominator — team-game rows or game clusters, and which universe (§5.1); (e) the baseline;
and (f) how the §3.5 covariance obligation is carried into a distributional setting.

---

## 8. Contradictions and disclosures

**C-1 — team-thread primary metric disputed between design and bytes.**
`project_docs/ASSUMPTION_AUDIT_2026-07-30.md` lines 537–539 design E1 with
`"Preregister: primary = cover-Brier vs the line-implied-probability benchmark; floor challenger = constant-σ"`.
`experiments/registry.jsonl` line 18, registered `2026-07-30T21:23:43`, carries
`primary_metric: "margin_crps"`. Frozen bytes govern over prose, so the registration's
`margin_crps` is what was registered — but the divergence from its own design document is reported,
not reconciled, and is reason 3 in §3.4 for not borrowing this estimand.

**C-2 — a superseded absence claim.** `project_docs/ASSUMPTION_AUDIT_2026-07-30.md` lines 112–114
state that no margin/total distribution and no CRPS `"exists anywhere on the ledger"`. The
`dist_margin_cover_v1` registration landed the same day at 21:23:43Z. The audit statement appears to
predate the registration rather than contradict it; both are cited so a later reader is not misled
by the earlier sentence.

**C-3 — row universe unreconciled.** §5.1. Documented as such by D10; not resolved here.

**D-1 — no-performance-peeking disclosure.** While proving the negative in §3.4 I ran a
whole-repository text scan for a distributional estimand attached to margin or total. Two of its
hits were outcome-bearing lines (`leaderboards/PROBABILISTIC.md` line 22 and
`experiments/dist_margin_cover/REPORT.md`), and a subsequent field-level extraction from
`experiments/registry.jsonl` — written with an outcome-field suppressor — leaked several result
fields of the team-thread record `dist_margin_cover_v1` despite it. I am disclosing this rather than
omitting it. The exposure is to a **team-thread** experiment, not to any player-program challenger,
and not to `stage2b/SEALED_RESULTS/`, which was never opened. **No figure from any of those sources
is used, cited or relied on anywhere in this draft**; §3.4 cites only definitional fields
(experiment id, schema, decision time, primary metric name, incumbent id, universe, thresholds), and
the decision recorded there — *do not adopt this estimand* — rests on thread, universe, and the C-1
contradiction, none of which is an outcome.

---

## 9. Stop conditions

No stop condition is tripped. Nothing in this draft changes the primary target
(`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`), the K0 structure, the inference structure, the
candidate universe, the cutoff-valid feature set, or the leakage status. §5.5 identifies a fork
(full-game versus regulation-equivalent) that a *future* estimand must resolve; it is raised here and
deliberately left unresolved, because resolving it would be changing the target.

D-1 above is a rule-compliance disclosure, not a scientific finding.
