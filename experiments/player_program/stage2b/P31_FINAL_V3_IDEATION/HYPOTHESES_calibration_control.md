# P31 FINAL IDEATION — CALIBRATION AND CONTROL STRUCTURE

Role: calibration_control (one of six independent sources, final ideation wave)
Evidence basis: EVIDENCE_PACKET_V3.json, sha256
`95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` (computed by this role,
matches the hash stated in ROLE_PROMPT.md).
Files read: ROLE_PROMPT.md and EVIDENCE_PACKET_V3.json in this directory, nothing else.

## Shared frame for every hypothesis below

* Target: REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS (packet
  `six_dimension_check.target_unit`, UNCHANGED). Universe: 2,982 team-game rows / 1,491
  game clusters, both-numbers reporting carried (packet `inference`).
* Folds: the FIVE expanding-window folds of D006 — train_lt_2022 (410 train / 478 test),
  train_lt_2023 (888/520), train_lt_2024 (1408/524), train_lt_2025 (1932/620),
  train_lt_2026 (2552/430). "Every fold" below means these five.
* The incumbent is Arm D, frozen, unbeaten (`correction_addendum.unchanged`). Its projection
  enters the design as the offset. Per `enforcement.offset_dependency_guard_S4_S5`, an affine
  function of the offset is REJECTED inside a substantive arm precisely because
  "recalibration is its own hypothesis family" — this document IS that family, so here the
  affine-in-offset terms are the declared treatments, never smuggled confounds.
* Per `k0_matched.core_rules` (calibration-only arm): each null below holds identical rows,
  target, folds, weights, offset, fallback machinery and lower-order structure, and fixes the
  tested calibration parameter at its incumbent value — slope 1, the preregistered lower-order
  intercept structure — adding ONLY the named treatment.
* All estimation is TRAINING-ONLY within each fold: every centering constant, threshold and
  coefficient is computed on that fold's training rows alone.
* Scale note: sketches are written on the model's linear-predictor scale beside the offset,
  under whatever link the frozen inference specification fixes; nothing below depends on the
  link choice, only on the design terms named.
* No feature below is a possession column outside the S8 ELIGIBLE set, no market or tip or
  injury field is used (all ineligible per packet), no same-game information enters under any
  disguise, and no value channel touches the raw/regulation-equivalent scorer mismatch (P28
  ordering contract respected: the primary target gate is the only gate addressed).
* Multiplicity: every hypothesis here is a member of the single family
  CALIBRATION_CONTROL_FAMILY, which carries its own family-level accounting
  (`k0_matched.core_rules`: "its own nested null and its own multiplicity accounting").
  Declared rule: one family-wise correction across the six members (Holm or max-T at the
  family level, fixed at preregistration, before any result exists). No member may be
  reported uncorrected.

Notation: `off` = incumbent offset projection for the row; `m̄` = training-fold mean of
`off`; `1[·]` = indicator. Reference coding is used everywhere so that setting every
treatment coefficient to zero recovers the incumbent EXACTLY (nested nulls).

---

## CALIBRATION_CONTROL_H1 — Global slope on the centered incumbent projection

**Mechanism (one):** shrinkage-gain miscalibration. The incumbent's projected deviations from
league-mean pace are produced by averaging finite prior-game evidence, so their amplitude is a
choice of regression-to-the-mean gain. If that gain is wrong, projections are systematically
over- or under-dispersed around the league mean: fast-projected teams realise fewer possessions
than projected and slow-projected teams more (gain too high), or the reverse (gain too low). A
single slope on the centered projection corrects the gain without touching the level.

**Formula sketch:** linear predictor = `off` + `δ · (off − m̄)`, with `m̄` the training-fold
mean of the offset. One free parameter, `δ`, estimated training-only per fold. `δ = 0`
recovers the incumbent identically (slope fixed at its incumbent value 1). Centering against
`m̄` is part of the treatment's DEFINITION, not a free re-centring: at `δ = 0` the centering
constant vanishes from the design, so the null receives no re-centring credit
(`k0_matched.core_rules`: "no arm receives credit for free re-centring").

**Features:**
* `off` (incumbent projection, offset) — source: `enforcement.offset_dependency_guard_S4_S5`
  (the design is `[offset | nuisance | candidate]`); Arm D frozen per
  `correction_addendum.unchanged`. Cutoff: the offset is the incumbent's own output, governed
  by the Stage 1B scoped acceptance under D009 standard (a); no new field enters.

**K0_MATCHED sketch:** identical rows, target, five D006 folds, cluster weights, offset,
fallback machinery. Null design = `[off]` with slope fixed at 1 and the preregistered
lower-order intercept structure; treatment design = `[off | (off − m̄)]`. The ONLY difference
is the single slope column.

**Fold support:** the term is `off − m̄`, non-constant wherever the offset varies across
training rows. The smallest training fold is 410 rows / 205 clusters (train_lt_2022), far
above the 10-cluster support floor, and a projection constant across 205 game clusters is
impossible for a pace model that distinguishes teams at all; degenerate variance would in any
case be caught by the S7 fold-local estimability guard's zero-variance and rank checks, which
this arm invokes as its gate. No active-set rule needed: one column, present in every fold.

**Expected failure mode (kill condition):** across the five folds the family-corrected test of
`δ = 0` fails to reject AND the out-of-fold primary-target score does not improve over K0 —
i.e. the estimated gain correction is indistinguishable from zero or unstable in sign across
folds. Sign instability across folds kills the mechanism even if one fold rejects.

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## CALIBRATION_CONTROL_H2 — Own-vs-opponent blend contrast (pace-control asymmetry)

**Mechanism (one):** offense controls tempo more than defense. The incumbent's projection
satisfies the measured identity `own_est + opp_est == 2 * projected`
(`enforcement.offset_dependency_guard_S4_S5`), i.e. it blends the two team-side pace estimates
with implicit equal weights. Basketball asymmetry says the offense chooses to push or walk the
ball while the defense mostly reacts, so the optimal blend weight on the offense's own estimate
should exceed one half. A coefficient on the (own − opp) contrast re-weights the blend without
adding any new information source.

**Formula sketch:** linear predictor = `off` + `γ · (own_est − opp_est)`, `γ` estimated
training-only per fold. `γ = 0` recovers the incumbent's equal-weight blend exactly; `γ > 0`
tilts toward the offense's own estimate (effective weights ½+γ′, ½−γ′ after scale
normalisation). This is precisely the "single preregistered nonredundant contrast (own−opp)"
that the offset guard names as admissible beside the offset — the PAIR (own, opp) is
prohibited there because it reconstructs the offset; the contrast is not.

**Features:**
* `own_est`, `opp_est` — source: `enforcement.offset_dependency_guard_S4_S5.rule` (named
  there, with the identity own+opp = 2·projected measured and the (own−opp) contrast
  explicitly admitted "with fold-local full rank"). Cutoff: both are internal components of
  the frozen incumbent's receipted projection path, governed by the Stage 1B scoped
  acceptance under D009 standard (a); no new field enters the candidate universe.

**K0_MATCHED sketch:** identical everything; null design = `[off]` (blend weight fixed at its
incumbent value, equal halves); treatment design = `[off | (own_est − opp_est)]`. Only the
contrast column differs.

**Fold support:** admissibility is conditional on fold-local full rank of
`[offset | own−opp]`, exactly as the offset guard demands; the S7 guard's per-fold rank and
condition-number checks are the arm's gate. The contrast is non-degenerate whenever the two
team-side estimates differ on a supported set of training rows — with 205+ training clusters
per fold and team-specific pace estimation, exact own=opp on a whole fold is a measurable
degeneracy the guard would flag, in which case the arm/fold is prospectively UNEVALUABLE per
the S7 rule (declared now, before results).

**Expected failure mode (kill condition):** family-corrected `γ = 0` not rejected across
folds, or the sign of `γ̂` flips across folds, or the S7 guard finds the contrast near-collinear
with the offset in any fold (near-collinearity would mean the "contrast" is secretly a slope,
and the arm yields to H1 rather than claiming its credit).

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## CALIBRATION_CONTROL_H3 — Evidence-tier intercepts (collapsed ladder, preregistered active set)

**Mechanism (one):** cold-start level bias. Where the incumbent has shallow prior-game
evidence for the offensive team, its fallback machinery pulls the projection toward a league
prior estimated from earlier history; if current-season league pace has drifted from that
prior (secular pace trends across 2021–2026), every shallow-evidence projection shares a
common level error. A tier intercept on the shallow-evidence stratum corrects that shared
level. This is a LEVEL correction indexed by an incumbent-internal state, not a substantive
feature: the information used (evidence depth) is already inside the incumbent.

**Formula sketch:** linear predictor = `off` + `α_S · 1[tier = SHALLOW]`, where the tier is a
binary collapse of the evidence-depth ladder: SHALLOW vs DEEP by a preregistered threshold on
`pace_evidence_depth`, threshold fixed before any result and applied training-only. DEEP is
the reference tier (`α_DEEP = 0`), so `α_S = 0` recovers the incumbent exactly. The full V2
tier ladder is NOT proposed: P27 measured that under a 10-cluster support floor NO training
fold supports it (`k0_matched.core_rules`, tier support constraint), and D007 records the
single universal control as unestimable as written. The binary collapse is this arm's
preregistered active-set structure, declared per the S7 rule (training-support-based,
symmetric, receipt-recorded), aligned with the preregistration bound in the packet at
P27/ACTIVE_SET_RULE_PREREGISTRATION.json (sha256
`327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7`).

**Features:**
* `pace_evidence_depth` (tier index only) — source: ruling D009, which names it as one of the
  four incumbent-equivalent possession features on the exact receipted path. Cutoff: governed
  by the Stage 1B scoped acceptance under D009 standard (a) (validated construction order);
  it is NOT a new field entering the candidate universe, so standard (b) does not apply.
  DECLARED DEPENDENCY: if the program ever narrows standard (a), this arm and H4 fall with
  it; under standard (b) alone the field is CUTOFF_UNPROVEN and the arm is inadmissible.
* `off` — as in H1.

**K0_MATCHED sketch:** identical everything; null design = `[off]` with the preregistered
lower-order intercept structure (the incumbent's own); treatment design =
`[off | 1[SHALLOW]]`. Only the tier-intercept column differs. (Tier MAIN effects are
themselves the treatment here, so nothing lower-order is omitted from the null: the
lower-order structure of an intercept is the global intercept structure the incumbent already
carries.)

**Fold support:** by construction shallow-evidence rows concentrate in early-season stretches,
and EVERY training fold contains at least one complete season (train_lt_2022 holds all of
2021: 205 resolved clusters), so both tiers have support in every training fold at any
threshold that is not extreme; the preregistered active-set rule handles the remainder — if
either tier falls below the 10-cluster training floor in a fold, the declared symmetric rule
collapses the arm to the incumbent for that fold and the fold is recorded UNEVALUABLE for
this member, per S7, decided from training support only, before results are visible.

**Expected failure mode (kill condition):** family-corrected `α_S = 0` not rejected across
folds, or sign instability of `α̂_S` across folds. INTERPRETIVE LIMIT DECLARED NOW (D010): the
universe excludes the 2021 opening day — the single hardest cold-start day — so every
cold-start figure is flattered by construction; a kill here kills the hypothesis ON THIS
UNIVERSE and is stated as such, but the kill condition itself is unconditional: no post-hoc
appeal to the missing opening day may rescue a dead result.

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## CALIBRATION_CONTROL_H4 — Evidence-tier slope (shrinkage gain depends on evidence depth)

**Mechanism (one):** evidence-dependent shrinkage. The optimal regression-to-the-mean gain is
not one number: a projection built on few prior games carries more sampling noise, so its
deviations from the league mean deserve MORE shrinkage than deep-evidence projections. The
incumbent applies one implicit gain everywhere; a tier-specific slope lets the shallow tier's
gain differ from the deep tier's.

**Formula sketch:** linear predictor =
`off + α_S·1[SHALLOW] + δ0·(off − m̄) + δ_S·1[SHALLOW]·(off − m̄)`,
with ONLY `δ_S` as the treatment. `δ_S = 0` recovers the null. Tiers exactly as in H3
(binary collapse, preregistered threshold, training-only).

**Features:** `off`, `pace_evidence_depth` (tier index) — sources and cutoff arguments
identical to H3, including the declared D009 standard-(a) dependency.

**K0_MATCHED sketch:** identical everything; null design =
`[off | 1[SHALLOW] | (off − m̄)]` — the null CONTAINS the tier main effect AND the global
slope, per `k0_matched.core_rules` ("tier interactions require lower-order tier main effects
in K0") and per S4's warning, which this role reads as binding: a free slope the control lacks
is the confound, not a finding. So H4 can only win by the INTERACTION being real, never by
re-discovering H1's global slope or H3's tier level. Treatment design adds only
`1[SHALLOW]·(off − m̄)`.

**Fold support:** requires joint fold-local support of tier mains, global slope and the
interaction: rank-4 design (with offset) over training rows. The interaction column is
non-degenerate iff the shallow tier exists and the offset varies within it — guaranteed
wherever H3's tier support holds and shallow-tier teams are not all projected identically;
gated by the same S7 rank/condition checks and the same preregistered active-set rule as H3
(collapse to null for the fold, fold UNEVALUABLE for this member, decided from training
support only). H4 is declared strictly JUNIOR to H3 and H1 in the family ordering: if its
lower-order terms are unsupported in a fold, it does not run there.

**Expected failure mode (kill condition):** family-corrected `δ_S = 0` not rejected across
folds given the full lower-order null, or sign instability of `δ̂_S` across folds. If H1's δ
and H4's δ_S trade explanatory weight such that the interaction only rejects when the global
slope is REMOVED from the null, that is the S4 confound pattern and the result is recorded as
a kill, not a find. D010 interpretive limit applies as in H3.

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## CALIBRATION_CONTROL_H5 — Season-phase tier intercepts (within-season pace drift)

**Mechanism (one):** within-season pace drift. Conditioning, rotation tightening and
defensive-scheme maturation change league tempo across a season, while the incumbent's
projection is an average over EARLIER games of the same season and so lags any monotone
drift — early-season games are predicted with no drift correction at all and late-season
games with a projection anchored on faster, earlier basketball. Phase-of-season intercepts on
the offset test for the residual drift the incumbent cannot represent.

**Formula sketch:** linear predictor = `off + φ_E·1[phase = EARLY] + φ_L·1[phase = LATE]`,
MID as reference. Phase is the within-season schedule-time third: for each season, the day
fraction `(game_date − season_first_game_date) / (season_last_scheduled_date −
season_first_game_date)` cut at preregistered thirds. `φ_E = φ_L = 0` recovers the incumbent.
Season enters ONLY through the within-season day fraction — no cross-season level is encoded,
respecting the S8 hazard on `season` (fold identifier, not a feature). Two parameters, one
treatment mechanism (drift), tested jointly.

**Features:**
* `game_date` — source: S8 48-column table, ELIGIBLE ("schedule fact; constant within game;
  it is the cutoff boundary itself"). Cutoff: a schedule fact known before tip; the S8 table
  notes the join carries master_team's revision risk, which this arm inherits and declares.
* `off` — as in H1.

**K0_MATCHED sketch:** identical everything; null design = `[off]` with the incumbent
intercept structure; treatment design = `[off | 1[EARLY] | 1[LATE]]`. Only the two phase
columns differ; they are tested as ONE treatment (joint test), not two findings.

**Fold support:** every training fold contains at least one COMPLETE season (2021 complete in
train_lt_2022, and so on), so all three phases appear in every training fold with roughly a
third of that season's clusters each (2021: ~68 clusters per phase, far above the 10-cluster
floor). Later folds only add complete seasons. The one asymmetry is the TEST side of
train_lt_2026 (season 2026 truncated at 2026-07-31, so its LATE phase is thin or empty on
test rows) — a prediction-side thinness, not an estimability failure; training-side support
is what the S7 guard gates, and it holds in all five folds.

**Expected failure mode (kill condition):** the family-corrected JOINT test of
`(φ_E, φ_L) = 0` fails to reject across folds, or the fitted phase pattern is not stable in
ORDER across folds (e.g. early-positive in some folds and early-negative in others). A
monotone drift mechanism predicts a consistent sign pattern; an inconsistent pattern kills
the mechanism even if the joint test rejects somewhere.

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## CALIBRATION_CONTROL_H6 — Playoff-tier intercept (regime-shift recalibration)

**Mechanism (one):** playoff regime shift. Playoff basketball is slower — tighter rotations,
longer defensive possessions, more half-court execution — and the incumbent already carries
`is_playoff_game` as its one possession-column feature, so the QUESTION is not whether
playoffs matter but whether the frozen incumbent's playoff adjustment is CORRECTLY SIZED on
the current universe. A playoff intercept beside the offset measures the residual playoff
level error; it is a recalibration of an existing incumbent degree of freedom, squarely
inside this family and nowhere else (per S4/D007 it may not hide inside a substantive arm).

**Formula sketch:** linear predictor = `off + π · 1[is_playoff_game]`, `π` estimated
training-only per fold; `π = 0` recovers the incumbent exactly.

**Features:**
* `season_type` / `is_playoff_game` — source: S8 table, ELIGIBLE ("schedule fact known at the
  cutoff; the one possession column already used, as is_playoff_game in
  possession_features.py"). Cutoff: schedule fact, known pregame.
* `off` — as in H1.

**K0_MATCHED sketch:** identical everything; null design = `[off]`; treatment design =
`[off | 1[is_playoff_game]]`. One column difference.

**Fold support:** every training fold contains completed prior seasons INCLUDING their
playoffs (the per-season row counts in the packet's S3 coverage table exceed
regular-season-only counts, e.g. 2021: 209 game clusters against a 192-game regular
double-counted schedule, and the fold table's training rows are cumulative over complete
seasons), so `1[is_playoff_game]` has both levels with cluster support in every TRAINING
fold. The documented degeneracy is the TEST side: fold 2026 has 0 playoff games
(`enforcement.fold_local_estimability_guard_S7.known_degeneracies`). Per that clause this arm
DECLARES NOW, before any result is visible, the GATE_INVOCATION_CONTRACT §4 frozen fold-level
fallback for test rows in fold 2026 (where the treatment column is identically zero on test,
the arm's prediction reduces to the null's by construction and the fold contributes no
discriminating information for π — recorded, not hidden). Cluster-support counts are still
gate-checked per fold; if any training fold's playoff stratum falls below the 10-cluster
floor, that fold is UNEVALUABLE for this member per S7, declared in advance.

**Expected failure mode (kill condition):** family-corrected `π = 0` not rejected on the
folds where the term is evaluable, or sign instability of `π̂` across those folds. Because
fold 2026 contributes nothing discriminating, the effective evidence base is four folds; the
kill condition applies to those four, and thin playoff strata (playoffs are a small share of
each season) make a null result here MORE likely a priori — accepted and declared: this
member exists to be cheap to test and easy to kill.

**Multiplicity family:** CALIBRATION_CONTROL_FAMILY.

---

## Family-level declarations

1. **Family:** CALIBRATION_CONTROL_FAMILY = {H1, H2, H3, H4, H5, H6}. One family-wise
   correction across all six (Holm or max-T, fixed at preregistration). Joint tests (H5)
   count once.
2. **Nesting discipline:** every null recovers the frozen incumbent exactly at zero treatment;
   no member changes rows, weights, folds, fallback, estimator flexibility or link; K0_FLAT is
   not used (diagnostic only, per packet).
3. **Ordering:** H4 is junior to H1 and H3 (its null carries their terms). No member's credit
   may be assessed with a null missing a lower-order term another family member names — S4's
   confound rule applied inside the family.
4. **Prohibitions honoured:** no fitting was performed and no performance number appears in
   this document; no PROHIBITED or CUTOFF_UNPROVEN column enters any design (the D009
   standard-(a) dependency of H3/H4 is declared explicitly, not silently); no market, tip,
   injury, era or same-game field is used; nothing touches the raw/regulation-equivalent
   scorer mismatch channel.
5. **Universe caveat carried:** D010 (missing 2021 opening day) is declared as an interpretive
   limit on H3/H4's cold-start mechanism, with unconditional kill conditions regardless.
