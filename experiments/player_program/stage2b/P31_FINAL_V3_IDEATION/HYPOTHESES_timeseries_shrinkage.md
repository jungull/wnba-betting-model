# HYPOTHESES — timeseries_shrinkage (final ideation wave)

## Provenance and setup attestation

- Role: `timeseries_shrinkage`, one of six independent sources in the final ideation wave.
- SETUP ANOMALY, recorded for the coordinator: the isolation directory path and the expected
  packet sha256 both arrived in the task prompt as the literal string `undefined`. No
  `ROLE_PROMPT.md` exists anywhere on disk (verified by recursive search). The evidence packet
  was read from its staging location
  `experiments/player_program/stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json`
  — the only copy in existence — and NOTHING else in the repository was read: no other role
  directory, no prior hypothesis file, no source code, no data artifact. Independence is
  preserved to the maximum extent the broken setup allows.
- Computed packet sha256: `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75`
  (74,025 bytes). Confirmation against the expected hash was IMPOSSIBLE (expected value was
  `undefined`); the coordinator must confirm this hash against the frozen P30 record before
  admitting these hypotheses to the wave.

## Shared frame (from EVIDENCE_PACKET_V3 only)

- Target: REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS, team-game unit; universe 2,982
  resolved rows / 1,491 clusters (both-numbers rule; 2,990/1,495 full schedule).
- Inference: FIVE chronological expanding-window folds (D006): train_lt_2022 (410/478),
  train_lt_2023 (888/520), train_lt_2024 (1408/524), train_lt_2025 (1932/620),
  train_lt_2026 (2552/430). Game-clustered resampling, both team-rows carried together.
- Offset: the incumbent projection. The offset-dependency guard (S4/S5, P25/R11) rejects
  near-affine functions of the offset and the own+opp pair; a single preregistered
  nonredundant contrast (own − opp) is admissible.
- Admissible raw material for this family: (a) ELIGIBLE schedule facts (game_id, season_type,
  is_home_offense, game_date); (b) strictly-lagged aggregates of prior completed games'
  realised possession quantities — LAGGED_USE_ONLY per the 48-column adjudication (S8/P2A),
  with each lag construction requiring its own adjudication through
  postgame_surrogate_guard.py (P22: correctly lagged prior-game constructions PASS; every
  same-game surrogate FAILS). No injury field (0 cutoff-valid rows in every fold, P24), no
  tip-time field (P29), no market field (P2B) enters any hypothesis below.
- Cold-start caveat (D010): the universe excludes the 2021 opening day, so every cold-start
  coverage figure is flattered by construction. Hypothesis TS3 names this in its expected
  failure mode.
- This file proposes; it fits nothing. Fitting requires the preregistration chain P33–P37.

All four hypotheses form ONE multiplicity family, `timeseries_shrinkage`, with family-wise
error accounting across the four arms and all preregistered hyperparameter grid points
counted inside the family. Each arm carries its own K0_MATCHED null per the P26 per-arm
contract (D007).

Notation: for team t before game g, let P(t, <g) be the set of t's completed prior games
ordered by game_date (ELIGIBLE); pace(j) the realised regulation-equivalent possession count
of prior game j (a strictly-lagged aggregate of LAGGED_USE_ONLY columns); n_t the count
|P(t, <g)| (a schedule fact); Lbar_<g the mean pace over ALL completed league games dated
strictly before game_date(g). All aggregates are frozen at the pregame cutoff.

---

## TS1 — Evidence-depth-adaptive shrinkage (empirical-Bayes pooling weight)

- **Mechanism.** A team's lagged pace deviation from the league is informative in proportion
  to how much evidence supports it. A fixed-weight use of the lagged deviation (the K0
  lower-order structure) over- or under-weights teams early vs late in a season. The
  treatment is the classical partial-pooling weight w(n) = n/(n+kappa): the deviation is
  shrunk toward zero when evidence is thin and released as evidence accumulates.
- **Formula sketch.** log E[y_g,t] = log(offset_g,t) + beta * w(n_t) * d_t, with
  d_t = mean_{j in P(t,<g)} pace(j) − Lbar_<g and w(n) = n/(n+kappa), kappa on a
  preregistered grid fit fold-locally on training rows only.
- **Features.**
  - `lag_pace_dev_flat` (d_t): strictly-lagged mean of prior-game realised pace minus the
    lagged league mean. Cutoff: lag >= 1 completed game, ordered by ELIGIBLE game_date;
    the exact construction P22 proves PASSES the postgame surrogate guard; must be
    re-adjudicated by the guard at preregistration.
  - `n_prior_games` (n_t): count of the team's completed prior games — a pure schedule
    fact recoverable from game_date/game_id (both ELIGIBLE), no realised content.
- **K0_MATCHED sketch.** Identical rows, target, five folds, clustering, weights, offset,
  fallback and nuisance terms; K0 carries the flat lower-order term beta0 * d_t (the
  non-substantive structural degree of freedom granted to the candidate). The null fixes
  w ≡ 1 (equivalently kappa = 0); the treatment's ONLY excluded mechanism is the
  evidence-depth adaptivity of the weight.
- **Fold support.** Both features are continuous and defined on every row of the resolved
  universe (which by construction contains only prior-evidence rows). Smallest training
  fold is 410 rows / 205 clusters, far above the 10-cluster floor (P27); no levels, no
  zero-variance, no fold-degenerate structure. kappa grid is fit on training rows only,
  symmetric across folds, preregistered per the R12 active-set discipline.
- **Expected failure mode.** The incumbent projection plausibly already performs implicit
  pooling; then w(n)*d_t is a near-affine function of information already inside the offset
  and the P25 guard rejects the design, or beta ≈ 0 against K0. Secondarily, kappa is weakly
  identified in train_lt_2022 (single season of training data).
- **Multiplicity family:** `timeseries_shrinkage`.

---

## TS2 — Recency-weighted evidence (EWMA vs flat window), preregistered contrast

- **Mechanism.** Within-season pace is non-stationary (rotation changes, tactical drift), so
  recent prior games carry more information than early ones. The treatment is not the EWMA
  itself but the CONTRAST between exponentially-discounted and flat lagged deviations — a
  single nonredundant contrast in the form P25 admits, so the arm cannot smuggle in a second
  copy of the flat signal.
- **Formula sketch.** log E[y_g,t] = log(offset_g,t) + beta0 * d_t + beta1 * c_t, where
  c_t = ewma_lambda{pace(j) − Lbar_<j : j in P(t,<g)} − d_t, lambda on a preregistered
  grid, fold-locally selected on training rows only.
- **Features.**
  - `lag_pace_dev_flat` (d_t): as TS1.
  - `recency_contrast` (c_t): EWMA-minus-flat contrast of the same strictly-lagged
    deviations. Cutoff: identical lag structure to d_t — a deterministic reweighting of the
    same prior-game aggregates that P22's guard passes; the reweighting introduces no new
    source and no new timestamp risk. Adjudicated by the guard at preregistration.
- **K0_MATCHED sketch.** K0 = offset + beta0 * d_t (identical everything else). The null
  excludes only the recency contrast c_t. Estimating lambda counts as treatment degrees of
  freedom inside the family's multiplicity budget.
- **Fold support.** Continuous, defined everywhere on the universe; the contrast is exactly
  zero only for teams with one prior game (no zero-variance column in any training fold
  since all folds contain mid-season rows). Full rank alongside d_t by construction
  (contrast, not level), which is precisely the P25-admissible parameterisation.
- **Expected failure mode.** Half-life effects in possession pace are small and the contrast
  is noisy at short histories; beta1 indistinguishable from 0 against K0 in the two small
  early folds, and lambda selection burns family alpha without a stable cross-fold optimum.
- **Multiplicity family:** `timeseries_shrinkage`.

---

## TS3 — Season-boundary carryover shrinkage (between-season discounting)

- **Mechanism.** At a season boundary the roster and staff churn partially invalidates last
  season's pace evidence. The incumbent-equivalent flat pooling treats prior-season and
  current-season games as exchangeable (or ignores prior seasons entirely — either way, a
  fixed carryover). The treatment estimates a carryover weight rho in [0,1] that blends
  prior-season evidence into the current-season estimate and lets current-season evidence
  progressively displace it.
- **Formula sketch.** log E[y_g,t] = log(offset_g,t) + beta * dblend_t(rho), with
  dblend_t(rho) = (n_cur * dcur_t + rho * m_prev * dprev_t) / (n_cur + rho * m_prev),
  where dcur_t / dprev_t are the flat lagged deviations computed over current-season /
  immediately-prior-season completed games and n_cur / m_prev their counts; rho on a
  preregistered grid, fold-local, training-only.
- **Features.**
  - `lag_pace_dev_cur_season` (dcur_t): as TS1's d_t restricted to same-season prior games.
  - `lag_pace_dev_prev_season` (dprev_t): flat deviation over the team's prior-season
    completed games — strictly earlier by construction (whole prior season precedes the
    cutoff date); same P22 guard adjudication.
  - `n_prior_games_cur` / `n_prior_games_prev`: schedule-fact counts (ELIGIBLE game_date).
- **K0_MATCHED sketch.** K0 carries BOTH lower-order main effects (beta_a * dcur_t +
  beta_b * dprev_t) so the treatment cannot take credit for merely having prior-season
  information — the tier-interaction rule's lower-order-mains requirement applied to this
  family. The null fixes the blend at the preregistered incumbent-equivalent carryover
  (rho ≡ 1, undifferentiated pooling); the treatment's only excluded mechanism is the
  estimated season-boundary discount.
- **Fold support.** dprev_t is undefined for 2021 rows (no archived prior season): declare
  the GATE_INVOCATION_CONTRACT §4 frozen fold-level fallback for train_lt_2022's training
  season BEFORE results are visible, exactly as P27/R12 requires for partially-supported
  columns; every other fold has full continuous support and >10 clusters at every level of
  the construction. The fallback is preregistered, training-support-based and symmetric.
- **Expected failure mode.** This is a cold-start-adjacent mechanism and D010 warns the
  universe already excludes the single hardest cold-start day (2021 opening day), so any
  measured benefit is flattered by construction and must be reported under that caveat.
  Additionally early-season rows are a minority of every test fold, so the arm is
  underpowered; and the 2021 missing-prior-season fallback consumes its one degree of
  structural mercy.
- **Multiplicity family:** `timeseries_shrinkage`.

---

## TS4 — Shrinkage target correction: drifting league level (lagged league mean)

- **Mechanism.** TS1–TS3 shrink toward the lagged league mean as if it were the right
  centre. If league-wide pace drifts across time (rules emphasis, style diffusion), the
  correct shrinkage TARGET is a moving league level, and the offset — frozen per-game from
  the incumbent — may track it imperfectly. The treatment adds the lagged league-level
  deviation from its long-run training mean as a level-transport term.
- **Formula sketch.** log E[y_g,t] = log(offset_g,t) + beta0 * d_t + gamma * L_t, with
  L_t = Lbar_<g − Lbar_train, where Lbar_<g is the strictly-lagged league mean (trailing
  window of the last K completed league games, K preregistered) and Lbar_train the
  training-fold constant.
- **Features.**
  - `lag_pace_dev_flat` (d_t): as TS1 (lower-order team term, in K0).
  - `league_lag_level` (L_t): trailing league mean of realised pace over strictly earlier
    completed games, centred on the training constant. Cutoff: every contributing game
    precedes game_date(g); construction adjudicated by the P22 guard. NOT built from
    `era` (CUTOFF_UNPROVEN) and NOT from season-as-feature (S8 hazard: fold identifier) —
    only from lagged realised play, which is why it is cutoff-clean.
- **K0_MATCHED sketch.** K0 = offset + beta0 * d_t, identical machinery otherwise; the null
  excludes only the league-level term. Per the S9/D007 lesson this arm's mechanism is
  level transport, so the preregistration must state explicitly that a team-identity
  permutation control is NOT a valid null for it (permutation does not destroy a
  league-level time signal); the K0_MATCHED nested null above is the only control.
- **Fold support.** L_t is continuous, defined on all rows once >= K league games have
  completed (K small, preregistered; within the first days of 2021 the trailing window
  spans fewer games — the window rule is symmetric and training-support-based, declared
  under the same R12 discipline). No degenerate levels in any fold; condition-number check
  against the offset is the live risk, handled next.
- **Expected failure mode.** Most likely rejection point in the family: if the incumbent
  projection already tracks league drift, L_t is a near-affine function of the offset and
  the P25 guard rejects the design outright (this is the desired behaviour, not a defect).
  Under expanding-window folds the test season's drift is always an extrapolation, so even
  a real gamma can transport poorly across the fold boundary.
- **Multiplicity family:** `timeseries_shrinkage`.

---

## Family-level notes

- Family: `timeseries_shrinkage`, 4 arms, one family-wise correction; every grid point of
  kappa (TS1), lambda (TS2), rho (TS3), K (TS4) is counted inside the family budget.
- Every arm passes its registered PRIMARY possession-target gate before any downstream
  turnover number exists (P28 ordering contract); no arm claims credit on the frozen
  turnover scorer's raw/regulation-equivalent mismatch.
- Every lag construction above must be run through postgame_surrogate_guard.py
  (sha256 951e85132f470fdd939c8039958f0544413aaaa485da5dba7da9c1b9b73ceeda) and the
  offset-dependency and fold-estimability guards at preregistration; this file licenses
  none of that by itself.
