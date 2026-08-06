# HYPOTHESES — adversarial_identifiability (final ideation wave)

## Provenance and protocol deviations (recorded first, per adversarial mandate)

- Evidence packet: `EVIDENCE_PACKET_V3.json`, sha256
  `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` (74,025 bytes),
  matching the packet's own shipped `EVIDENCE_PACKET_V3.sha256`. The launcher-supplied
  expected hash was the literal string "undefined" (uninterpolated orchestration
  variable), so verification is against the shipped checksum, not the launcher value.
- The instructed isolated directory `undefined/adversarial_identifiability` did not
  exist; `ROLE_PROMPT.md` does not exist anywhere in the worktree. The packet was read
  from its committed location
  `experiments/player_program/stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json`.
  Nothing else in the repository was read: no other role directory, no prior
  hypothesis file, no source node listed in `sources_bound`. Independence from the
  other five sources is intact; independence from the repository is limited to the
  packet plus its checksum file, and this deviation is declared rather than hidden.
- This document authorises NO fit (packet `epistemic_status`); every hypothesis below
  is an ideation-stage candidate requiring the P33–P37 preregistration chain.

## Role reading

Adversarial identifiability: propose arms that are *constructed to be identifiable*
against the packet's guard battery — and for each, name the exact guard most likely
to kill it and the mechanism by which it would die. A hypothesis without a credible
failure mode is not admitted here.

Shared frame for every arm (packet-fixed, not per-arm choices):

- Target: REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS
  (`six_dimension_check.target_unit`).
- Universe: 2,982 team-game rows / 1,491 clusters, both-numbers reporting, opening-day
  exclusion caveat D010 (`inference`).
- Folds: FIVE chronological expanding-window folds per D006
  (`inference.fold_construction_D006`); game-clustered resampling, both team rows
  carried together.
- K0: per-arm K0_MATCHED map (D007), identical rows/target/folds/weights/offset/
  fallback/nuisance, excluding ONLY the treatment mechanism (`k0_matched.core_rules`).
- Admissible raw material after the packet's cutoff adjudication is brutally small:
  ELIGIBLE schedule/identity columns (game_id, season, season_type, offense_team_id,
  defense_team_id, is_home_offense, game_date), plus LAGGED_USE_ONLY constructions
  over strictly earlier completed games under the P22 lag discipline
  (`enforcement.postgame_surrogate_guard_S1.proven`: correctly lagged prior-game
  duration PASSES). Injury (0 cutoff-valid rows), market odds, tip times, era, and
  coaching are all out this wave.

---

## AI-H1 — Preregistered own-minus-opp lagged pace-deviation contrast

- **Mechanism.** A team's realised pace over its k most recent completed games
  deviates from the incumbent projection in a way that persists into the next game;
  the opponent's symmetric deviation acts in the opposite direction. Entering ONLY the
  single contrast (own − opp) is the one construction the offset guard explicitly
  leaves open, because own_est + opp_est == 2*projected makes the pair jointly
  offset-reconstructing (`enforcement.offset_dependency_guard_S4_S5.rule`).
- **Formula sketch.**
  `y_ig ~ offset(log mu_incumbent_ig) + beta * [dev_own_ig - dev_opp_ig]`,
  where `dev_team = mean over last k completed games (lag >= 1) of
  (realised regulation-equivalent possessions - incumbent projection for that game)`,
  k preregistered (single value, not searched).
- **Features.**
  - `lag_pace_dev_contrast` — built from per-game realised possession counts
    (per-game max of `canonical_seq` + 1; S8 table marks LAGGED_USE_ONLY) normalised
    by regulation-equivalent duration from lagged `duration_sec`/`period` aggregates;
    joined on ELIGIBLE keys (`offense_team_id`, `game_date`).
    Cutoff: every input is an aggregate over strictly earlier completed games with a
    documented lag >= 1, exactly the construction P22 proved passes all cutoff checks;
    same-game joins fail closed under the postgame surrogate guard.
- **K0_MATCHED sketch.** Identical universe, five D006 folds, cluster weights, offset
  `log mu_incumbent`, identical fallback and nuisance; excludes only the beta contrast
  term. No re-centring credit; K0_FLAT diagnostic only.
- **Fold support.** The resolved universe already excludes the no-prior-games stratum
  (D010), so the lagged deviation is defined on all 2,982 rows in every fold; per-fold
  rank and condition-number checks (S7 guard) must still pass because the contrast is
  a function of the same evidence stream the offset was built from.
- **Expected failure mode.** Death by near-affinity with the offset: the incumbent
  projection is itself built from lagged pace evidence (the Stage 1B receipted path
  carries pace_gap / pace_evidence_depth), so `dev_own - dev_opp` may be a near-exact
  affine function of information already in `mu_incumbent`, failing the offset
  dependency guard's near-collinearity rejection — most acutely in the train_lt_2022
  fold (410 training rows) where evidence depth is shallow and the condition number
  is worst.
- **Multiplicity family.** `lagged_pace_contrast_family` (any window-length variant of
  k is the same family; one preregistered k is fitted, the family carries the
  accounting).

## AI-H2 — Rest-differential contrast from pure schedule facts

- **Mechanism.** Short rest depresses pace. Days-since-previous-scheduled-game is
  computable from `game_date` + team identity alone — the only feature family in the
  packet that is cutoff-valid by construction rather than by lag argument, because it
  never touches a realised column at all.
- **Formula sketch.**
  `y_ig ~ offset(log mu_incumbent_ig) + beta * [f(rest_own_ig) - f(rest_opp_ig)]`,
  with `rest = days since the team's previous scheduled game this season`, f a
  preregistered cap (e.g. min(rest, 7)) to control leverage; symmetric contrast only.
- **Features.**
  - `rest_days_contrast` — from `game_date` (S8: ELIGIBLE, "the cutoff boundary
    itself") and `offense_team_id`/`defense_team_id` (S8: ELIGIBLE identity, taken by
    identity join, never row aggregate — the row-multiplicity hazard is the target
    numerator). Cutoff: schedule facts fixed before tip; the only leakage channel is
    master_team's revision risk on the `game_date` join, which the S8 table itself
    flags and which the dimension cardinality guard (P23) must receipt.
- **K0_MATCHED sketch.** Identical everything; excludes only the rest contrast.
  Season-opener rows (no previous game) take the preregistered, training-support-based,
  symmetric active-set/fallback rule of S7 — declared before results are visible per
  GATE_INVOCATION_CONTRACT §4, identically in arm and null.
- **Fold support.** Rest is defined for every row except season openers in every
  season 2021–2026; variance is nonzero in every fold (schedule congestion, including
  Commissioner's Cup compression). Zero-variance and unique-level checks expected to
  pass; the fallback rule covers openers symmetrically.
- **Expected failure mode.** Identified but empty: if the incumbent projection already
  conditions on schedule density, beta is estimable yet the arm shows no gain over its
  K0 — and the effect size in WNBA schedules may sit below the resolution of
  cluster-bootstrap error bars on ~1,491 clusters. Secondary adversarial note: D010
  means the hardest cold-start openers are already excluded, so opener-fallback
  performance is flattered by construction and must not be cited as evidence the
  fallback is safe.
- **Multiplicity family.** `schedule_context_family` (shared with AI-H3 — both are
  pure schedule-fact arms; the family, not the arm, carries the accounting).

## AI-H3 — Home-offense pace term as a within-cluster identified contrast

- **Mechanism.** Home teams play marginally faster (crowd, travel, familiarity). The
  packet's construction makes this the cleanest identification in the candidate set:
  each game cluster carries exactly one home row and one away row, both resampled
  together, so the home coefficient is a within-cluster contrast, orthogonal by design
  to any cluster-level (game-level) confounder.
- **Formula sketch.**
  `y_ig ~ offset(log mu_incumbent_ig) + beta * is_home_offense_ig`.
- **Features.**
  - `is_home_offense` — S8: ELIGIBLE, "home/away mapping, schedule-determined and
    known pregame; measured constant within (game_id, offense_team_id)". Cutoff:
    schedule fact; taken by identity join (drop_duplicates) per the S8 hazard note —
    never by row aggregate, since row multiplicity of the identity columns IS the
    target numerator.
- **K0_MATCHED sketch.** Identical everything; excludes only the home term. No tier
  structure, so the P27 tier-support constraint is vacuous here.
- **Fold support.** Exactly 50/50 balanced within every fold by construction
  (games never split across folds; both rows carried). Full rank trivially; no
  degeneracy possible in any fold including 2026.
- **Expected failure mode.** Attribution collapse: if home advantage is already
  absorbed in `mu_incumbent`, the arm ties its K0 and the "cleanest identification"
  buys nothing — the adversarial value of this arm is that it is nearly
  failure-mode-free at the guard level, so a null result here is a genuine null, and
  it therefore serves as the wave's positive-control-of-the-guards: if AI-H3 is
  declared UNEVALUABLE by any guard, the guard configuration (not the arm) is suspect.
- **Multiplicity family.** `schedule_context_family` (with AI-H2).

## AI-H4 — Lagged overtime-exposure audit arm (normalization-leak detector)

- **Mechanism.** The target is REGULATION-EQUIVALENT possessions, so realised
  overtime in a team's recent games should carry ZERO signal if the incumbent's
  regulation-equivalent normalization and the frozen scorers are exact. A nonzero
  coefficient on lagged OT exposure is therefore not a pace discovery — it is a
  measured defect in the normalization chain. This is an adversarial audit expressed
  as an arm: its interesting outcome is the one that indicts the pipeline, in the
  spirit of P28's raw/regulation-equivalent mismatch prohibition.
- **Formula sketch.**
  `y_ig ~ offset(log mu_incumbent_ig) + beta * OT_share_own_ig`,
  `OT_share = share of the team's last k completed games with is_overtime`
  (lag >= 1; single preregistered k).
- **Features.**
  - `lag_ot_share` — from `is_overtime` (S8: LAGGED_USE_ONLY, "exact: any(is_overtime)
    per game equals game_minutes > 40 on 1495/1495 games"). Cutoff: strictly-earlier
    completed games under the P22 lag discipline; the target-game value is PROHIBITED
    and the postgame surrogate guard fails same-game joins closed.
- **K0_MATCHED sketch.** Identical everything; excludes only the OT-exposure term.
  Because a nonzero beta means "defect", the preregistration must state the
  directional reading BEFORE results: gain over K0 here triggers a pipeline
  investigation, not a candidate promotion (P28 ordering: no credit for arbitraging
  the raw/regulation-equivalent mismatch).
- **Fold support.** Overtime is rare; under the 10-cluster support floor the earliest
  fold (train_lt_2022, 410 training rows) plausibly fails cluster support for
  high-OT-share levels. The arm must preregister the S7 active-set rule or accept
  prospective UNEVALUABLE status in that fold; continuous share (not binned) is chosen
  precisely to avoid unique-level degeneracy.
- **Expected failure mode.** Sparse-support death in early folds, and interpretive
  ambiguity everywhere else: a nonzero effect confounds normalization leakage with a
  genuine physiological fatigue-after-OT effect. The arm is only decision-useful with
  the preregistered directional reading; without it, any result is unactionable.
- **Multiplicity family.** `normalization_audit_family` (its own family; it is not a
  substantive pace candidate and must not share accounting with arms competing for
  promotion).

## AI-H5 — Within-season schedule-index drift (the level-transport trap, faced head-on)

- **Mechanism.** League-wide pace drifts within a season (conditioning, roster churn,
  tactical convergence). The regressor — the team's nth scheduled game of the season,
  or days since the season's first scheduled game — is a pure schedule fact. This is
  deliberately the arm family D007/S9 warned about: a league-level time signal is
  exactly what a naive permutation control passes silently, so it is the sharpest
  available test of whether the per-arm K0_MATCHED discipline actually bites.
- **Formula sketch.**
  `y_ig ~ offset(log mu_incumbent_ig) + beta * g(schedule_index_ig)`,
  g a preregistered monotone transform (e.g. index/season_length, using SCHEDULED
  season length, never realised); `season` itself NEVER enters (S8 hazard: fold
  identifier).
- **Features.**
  - `within_season_schedule_index` — from `game_date` (S8: ELIGIBLE) and the contract
    schedule. Cutoff: fully schedule-determined pregame; no realised column touched.
- **K0_MATCHED sketch.** Identical everything; excludes only the drift term. Crucially
  the null is the NESTED model, never a team-identity permutation (the S9 lesson:
  permuting identities does not destroy a league-level time signal). Any tier or
  spline version must place lower-order terms in K0 per `k0_matched.core_rules`.
- **Fold support.** Expanding-window training folds contain complete seasons, so the
  full index range is supported in training for folds 2022–2025. Fold train_lt_2026
  is the adversarial case: the 2026 test season is truncated at 2026-07-31
  (S3 fold table, `last_game_date`), so late-season index values are trained-on but
  never tested — support asymmetry that the preregistered symmetric,
  training-support-based active-set rule must handle, else the fold is UNEVALUABLE.
- **Expected failure mode.** Level transport masquerading as signal: beta may capture
  between-season level differences leaking through the within-season index's
  correlation with calendar time, and the truncated 2026 test season makes the final
  fold's evaluation regime differ from training by construction. If the arm survives
  its guards but wins only on the truncated fold, the win is an artifact and the
  preregistration must bind itself to reject that pattern in advance.
- **Multiplicity family.** `temporal_drift_family` (all transforms g and all binnings
  of the index are one family).

---

## Cross-cutting adversarial notes for the coordinator

1. **The candidate universe is thinner than any single guard makes it look.** After
   S8 + P24 + P2B + P29, the only fully cutoff-valid raw material is schedule facts;
   everything else rides on the P22 lag licence. Every substantive arm above is
   therefore either a schedule-fact arm (H2, H3, H5) or a P22-lag arm (H1, H4), and a
   failure of the lag licence's own adjudication would kill H1/H4 as a class.
2. **D005 means call-site discipline is the only enforcement.** All five sketches
   assume the P22/P25/P27 wrappers run at the arm's call site; none may cite
   feature_gate.audit as evidence of anything.
3. **D010 flattering is systemic.** Any cold-start-flavoured claim (H2's opener
   fallback especially) is evaluated on a universe missing the hardest cold-start
   day; no such claim should be promoted on this universe alone.
4. **H3 doubles as a guard positive-control.** Its near-unkillable identification
   makes it the canary: guards that reject it are misconfigured.
