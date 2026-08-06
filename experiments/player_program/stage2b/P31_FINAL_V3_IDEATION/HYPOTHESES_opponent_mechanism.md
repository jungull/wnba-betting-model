# P31 Final Ideation — OPPONENT AND BASKETBALL MECHANISM

## Attestation

- Files read, in full: `ROLE_PROMPT.md`, `EVIDENCE_PACKET_V3.json` — both inside this
  directory. Nothing else was read. (Locating this directory required listing file NAMES
  after the orchestrator passed a literal `undefined` base path; no file CONTENT outside
  this directory was opened.)
- `EVIDENCE_PACKET_V3.json` sha256 computed:
  `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` — MATCHES the value
  declared in ROLE_PROMPT.md.
- Files written: this file only.

## Shared design conventions (all hypotheses)

- **Target / unit:** REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS per team-game row
  (packet `six_dimension_check.target_unit`, unchanged). Universe: 2,982 resolved rows /
  1,491 clusters; both-numbers reporting per `inference.report_both`; the D010 opening-day
  exclusion caveat applies to every cold-start/imputation coverage figure below.
- **Design shape:** every arm enters exactly ONE candidate column `z` in the audited
  complete design `[offset | nuisance | z]` (packet `enforcement.offset_dependency_guard_S4_S5`).
  Because `own_est + opp_est == 2*projected`, no arm enters an own/opp pair; every `z`
  below is a single preregistered own-minus-opp contrast (or a within-cluster antisymmetric
  indicator, the degenerate case of one). Each `z` is antisymmetric within a game cluster
  (the two rows of a game carry `+z` and `-z`), which makes it structurally orthogonal to
  any cluster-constant term and non-reconstructive of the offset.
- **Folds:** the five expanding-window folds of D006 (`train_lt_2022` … `train_lt_2026`),
  game clusters never split.
- **Cutoff discipline:** all trailing aggregates use ONLY games with `game_date` strictly
  earlier than the target row's `game_date` (`game_date` is ELIGIBLE — "the cutoff boundary
  itself"), a documented lag of >= 1 completed prior game, same-game joins failing closed,
  per `enforcement.postgame_surrogate_guard_S1` ("correctly lagged prior-game duration
  PASSES all cutoff checks"). The 48-column table's LAGGED_USE_ONLY label licenses
  *proposing* strictly-earlier-game aggregates while requiring their own adjudication —
  that adjudication is exactly what each cutoff argument below supplies for preregistration.
- **Team identity joins:** `offense_team_id` / `defense_team_id` / `is_home_offense` are
  used ONLY as drop-duplicates identity joins on the target row (the SEVERE row-multiplicity
  hazard in the 48-column table is respected: no target-game row aggregate of any kind).
  Row counts are taken only over strictly earlier games, where they are the intended lagged
  mechanism, not target reconstruction.
- **Excluded families honoured:** no injury_history field (0 cutoff-valid rows in every
  fold, S3), no tip times (P29), no market odds (P2B), no `era`, no coaching (CUTOFF_UNPROVEN),
  no same-game column value in any disguise, no lineup-availability mechanism at all —
  the mandate restricts lineup-availability mechanisms to ELIGIBLE columns, and no ELIGIBLE
  column carries lineup/availability content, so that family is empty this wave and is
  deliberately not proposed.
- **P28 ordering:** every arm is valued on the PRIMARY possession target first; none of the
  mechanisms below has the raw/regulation-equivalent turnover-scorer mismatch as a value
  channel.
- **Preregistered cold-start imputation rule (used where stated):** if either team of the
  cluster has fewer than E = 3 completed prior same-season games at the cutoff, set z = 0
  (the contrast's null value). This is a deterministic, symmetric, training-support-free
  imputation — not a fitted fallback and not an extra design column — declared here, before
  any result exists, to satisfy the GATE_INVOCATION_CONTRACT §4 requirement that fold-level
  behaviour be frozen in advance. Its coverage figures are flattered by construction on this
  universe (D010) and must be reported on both universes.
- **Multiplicity:** all five hypotheses declare the single family
  `OPPONENT_MECHANISM_F1` (5 arms), corrected jointly within the family under the program's
  preregistration chain (P33–P37). Calibration is its own separate family per S4 and is not
  touched by any arm here.

---

## OPPONENT_MECHANISM_H1 — Tempo imposition is asymmetric, and possession DURATION carries it more cleanly than possession counts

**Mechanism (basketball/statistics).** Game pace is a within-game equilibrium between two
tempos: every short offensive possession returns the ball to the opponent sooner, so a team
that systematically shortens its own possessions (early-clock shots, transition pushes)
mechanically raises BOTH teams' possession counts, while a slow team cannot fully decline
the transition opportunities the fast team's alternations create. The equilibrium therefore
sits closer to the faster team's tempo than a symmetric blend implies. Statistically, the
trailing MEDIAN of a team's own offensive possession duration is a cleaner tempo signature
than trailing possession counts: counts are contaminated by overtime, technical/zero-duration
possessions and garbage time, while the median duration is robust to all three tails. The
incumbent offset is built from count-based estimates; the duration-median contrast carries
the imposition asymmetry the count blend cannot.

**Formula sketch.** One candidate column beside the frozen offset:
`z1(row) = med_dur_opp − med_dur_own`, where `med_dur_team` = median of `duration_sec`
over ALL of that team's offensive possessions (rows with `offense_team_id == team`) in
strictly earlier same-season games. Sign: own team faster than opponent → z1 > 0 → predicted
possessions above offset (expected beta1 > 0). Enters untransformed (seconds); no
interaction, no pair.

**Features and cutoff arguments.**
- `duration_sec` — 48-column table, LAGGED_USE_ONLY; used ONLY as a strictly-earlier-game
  aggregate with lag >= 1 completed game, same-game join failing closed (P22 guard proves
  the lagged-duration construction passes all cutoff checks).
- `offense_team_id` — ELIGIBLE; identity/grouping key only; earlier-game grouping plus a
  drop-duplicates identity join on the target row.
- `game_date` — ELIGIBLE; the cutoff boundary; defines "strictly earlier".
- `game_id` — ELIGIBLE; join key only.

**K0_MATCHED sketch.** The null holds: identical rows, target, five folds, cluster
weights, the frozen offset, the identical E=3 imputation machinery, and any nuisance terms
granted to the candidate (none requested — no tier structure, so no lower-order terms are
owed). The treatment adds ONLY the single column z1. No re-centring, no fallback change, no
estimator change.

**Fold-support argument.** z1 is a continuous contrast with nonzero cross-team variance in
every season (teams' tempo signatures differ every year); it is defined from each team's
E=3rd game onward, and the AVAILABILITY table shows ~100% of team-games have prior
same-season rows, so the z=0 imputation stratum is the thin early-season edge only. The
design is a single column, antisymmetric within cluster, varying across clusters — full
rank in every one of the five training folds (rank check per S7 guard); no unique-level or
zero-variance degeneracy is possible for a continuous contrast. The E=3 rule above is the
preregistered active-set/imputation declaration.

**Expected failure mode (kill criterion, preregistered).** Dead if the fold-aggregated
game-cluster-resampled interval for beta1 covers 0, or if the arm fails its registered
primary possession gate against this K0. Separately withdrawn (design failure, not a null
result) if the S4/S5 offset-dependency audit finds z1 near-affine in the offset or in the
incumbent `pace_gap` in every training fold — that would mean z1 is a repackaging of the
incumbent contrast, not new information.

**Multiplicity family.** `OPPONENT_MECHANISM_F1`.

---

## OPPONENT_MECHANISM_H2 — Possession creation through defensive turnover forcing is a channel distinct from tempo

**Mechanism (basketball/statistics).** Total possessions rise through two distinct
basketball channels: (a) faster clock usage (H1's channel) and (b) live-ball turnovers,
which truncate possessions far below their natural clock length and immediately create a new
alternation. Turnover FORCING is a defensive skill (ball pressure, passing-lane steals) that
is stable within team-season and acts on the OPPONENT'S possessions, so it raises the
game's total alternations regardless of the forcing team's own offensive tempo. Count-based
pace estimates confound the two channels; the forced-turnover-rate contrast isolates the
creation channel. The value channel is the primary possession target itself — more forced
turnovers means more possessions for BOTH rows of the cluster — not anything downstream in
the frozen turnover scorer (P28 respected).

**Formula sketch.** `z2(row) = ftr_own − ftr_opp`, where `ftr_team` = share of that team's
DEFENSIVE possessions (rows with `defense_team_id == team`) whose `end_reason` is a
turnover terminator, over strictly earlier same-season games. Preregistration will freeze
the exact `end_reason` level set mapped to "turnover terminator" from the artifact's level
dictionary BEFORE any fit; the mapping is a data-dictionary lookup, not a tuned choice.
Sign: own defense forces more than opponent's → z2 > 0 → expected beta2 > 0. One column,
untransformed proportion difference.

**Features and cutoff arguments.**
- `end_reason` — LAGGED_USE_ONLY; strictly-earlier-game share only, lag >= 1, P22 guard.
- `defense_team_id` — ELIGIBLE; identity/grouping key; earlier-game grouping plus
  drop-duplicates identity join on the target row.
- `game_date` — ELIGIBLE; cutoff boundary.
- `game_id` — ELIGIBLE; join key only.

**K0_MATCHED sketch.** Null holds identical rows, target, folds, weights, offset, the E=3
imputation machinery, and no other candidate column; treatment adds ONLY z2. If the
program later wants H1 and H2 jointly, that is a NEW arm with its own K0 — neither arm here
receives the other as nuisance, and that separation is declared now.

**Fold-support argument.** ftr is a proportion strictly inside (0,1) with cross-team
variance in every season; z2 is continuous and antisymmetric within cluster; defined from
the E=3rd game per team with the same preregistered z=0 imputation for the early-season
stratum. Single-column design, full rank in all five training folds; no level-support or
tier-ladder issue exists.

**Expected failure mode (kill criterion, preregistered).** Dead if the cluster-resampled
interval for beta2 covers 0 or the primary gate shows no improvement over K0. Withdrawn as
a design failure if the frozen `end_reason` level dictionary proves not to distinguish
turnover terminators from other terminators (the mechanism is then unmeasurable in this
artifact), or if the S4/S5 audit finds z2 jointly reconstructing the offset with any
nuisance column.

**Multiplicity family.** `OPPONENT_MECHANISM_F1`.

---

## OPPONENT_MECHANISM_H3 — Residual home-court tempo not priced by the offset

**Mechanism (basketball/statistics).** Home teams play systematically (if modestly) faster:
crowd-fed defensive intensity raises transition frequency, and the visiting team carries
travel fatigue that suppresses early-clock pushes. If the frozen incumbent projection is
home-agnostic — or prices home only through team-level trailing means that smear home and
away games together — then a within-cluster home/away antisymmetric term captures the
residual. This is the cheapest possible opponent-differentiated arm: it uses one ELIGIBLE
schedule fact, and it doubles as an empirical audit of what the offset already prices.

**Formula sketch.** `z3(row) = +1 if is_home_offense else −1` (identity join,
drop-duplicates, per the multiplicity-hazard instruction on that column). One column beside
the offset; expected beta3 > 0 (home rows above offset, away rows below, symmetrically).

**Features and cutoff arguments.**
- `is_home_offense` — ELIGIBLE ("home/away mapping, schedule-determined and known
  pregame; measured constant within (game_id, offense_team_id)"); taken by identity join,
  never by row aggregate.
- `game_id` — ELIGIBLE; join key only.
No lagged construction exists in this arm at all, so its cutoff argument is complete on
schedule facts alone.

**K0_MATCHED sketch.** Null holds identical rows, target, folds, weights, offset; there is
no imputation machinery in this arm and no nuisance term; treatment adds ONLY z3. The
comparison is pure: any lift is tempo information the offset does not carry.

**Fold-support argument.** Every game cluster contributes exactly one +1 and one −1 row,
so z3 is perfectly balanced in every training fold by construction — the strongest possible
fold-support guarantee, immune to the is_playoff_game-style fold-2026 degeneracy (S7
known_degeneracies). Full rank is trivial; zero-variance impossible.

**Expected failure mode (kill criterion, preregistered).** Dead if the cluster-resampled
interval for beta3 covers 0 — the reading then is that the offset already prices home
tempo, and that reading is itself the preregistered interpretation of the null result.
This arm has a HIGH prior probability of dying exactly that way; it is proposed because it
is nearly free, fully cutoff-clean, and its death cleanly certifies one property of the
frozen offset.

**Multiplicity family.** `OPPONENT_MECHANISM_F1`.

---

## OPPONENT_MECHANISM_H4 — Rest asymmetry shifts the tempo equilibrium toward the fresher team

**Mechanism (basketball/statistics).** Fatigue suppresses exactly the behaviours that
create possessions: transition pushes, full-court and half-court ball pressure, and deep
rotations. A team on the short end of a rest differential (back-to-back vs a rested
opponent) walks the ball up, declines transition, and presses less — lowering the
alternation rate it contributes to the equilibrium. The DIFFERENTIAL, not the level, is the
opponent-differentiated quantity: it predicts which direction the game's tempo equilibrium
is dragged, and it is built entirely from schedule facts available at any pregame cutoff.
WNBA schedule congestion (including Commissioner's Cup compression and charter-flight era
differences across seasons) makes the differential's variance real in every season.

**Formula sketch.** `z4(row) = rest_own − rest_opp`, where `rest_team` = min(days between
the target `game_date` and the team's most recent strictly earlier same-season contract
game's `game_date`, capped at 4). Season-first games (no prior same-season game) assign the
cap value 4 (fully rested) — a deterministic preregistered rule, so this arm needs NO
imputation stratum and no active-set rule. The cap at 4 days is frozen here, before any
result: it encodes that marginal recovery beyond 4 days is physiologically negligible while
uncapped values would let long All-Star-break tails dominate a linear term. One column,
integer-valued in [−4, +4].

**Features and cutoff arguments.**
- `game_date` — ELIGIBLE; "the cutoff boundary itself"; both the target date and the prior
  games' dates are schedule facts fixed before the target cutoff. The construction touches
  NO realised outcome of any game — only the fact that contract games occurred on given
  dates, which is the schedule identity the ELIGIBLE label covers. (Join carries
  master_team's revision risk as the table notes; that risk is identical to the one already
  accepted for `game_date` itself.)
- `offense_team_id` / `defense_team_id` — ELIGIBLE; identity keys to locate each team's
  prior game dates and to join the target row.
- `game_id` — ELIGIBLE; join key only.

**K0_MATCHED sketch.** Null holds identical rows, target, folds, weights, offset; no
nuisance, no imputation machinery (the cap rule is part of the feature's definition, present
identically in... — vacuously, since the null carries no z4 at all); treatment adds ONLY z4.

**Fold-support argument.** Every season's schedule mixes back-to-backs with 3+ day gaps, so
z4 has nonzero variance in every one of the five training folds; it is defined on EVERY row
(the season-first cap rule removes the undefined stratum entirely — no active-set rule
needed, the cleanest possible S7 posture after H3). Antisymmetric within cluster; single
column; full rank everywhere.

**Expected failure mode (kill criterion, preregistered).** Dead if the cluster-resampled
interval for beta4 covers 0 or the primary gate shows no improvement over K0. A sign
OPPOSITE to prediction (fresher team associated with FEWER possessions) with an interval
excluding 0 also kills the mechanism as stated — it would not be reinterpreted post hoc.

**Multiplicity family.** `OPPONENT_MECHANISM_F1`.

---

## OPPONENT_MECHANISM_H5 — Schedule confounding of trailing pace estimates: the strength-of-schedule CORRECTION is the new information

**Mechanism (basketball/statistics).** In a 12–13 team league, early-season trailing pace
means are heavily confounded by opponent mix: a team that happened to draw the league's
fastest teams shows an inflated trailing count signature through no property of its own.
Every count-based own/opp estimate — including whatever feeds the frozen offset — inherits
this confounding. The first-order fix is ratings-style: subtract from each team's raw
trailing signature the mean trailing signature of the opponents it faced (leave-one-out).
The candidate is NOT the adjusted pace pair (inadmissible beside the offset and redundant
with it); it is the contrast of the CORRECTION TERMS alone — the piece of the adjustment
that the raw-estimate-built offset cannot contain. Basketball reading: it answers "whose
trailing pace signature is inflated by whom they played, own or opponent, and by how much."

**Formula sketch.** For team t before date d, let `raw_t` = mean over t's strictly earlier
same-season games g of (t's possession count in g, i.e. that game's per-team row count in
the possessions artifact), and let `sched_t` = mean over those same games g of
`raw_{opp(g)}` computed leave-one-out (opponent's trailing mean EXCLUDING game g itself),
each centred on the league trailing mean at d. The correction term is `c_t = −sched_t`
(positive when t faced slow teams, i.e. t's raw signature understates t). Candidate:
`z5(row) = c_own − c_opp`. One column. Expected beta5 > 0 (a team whose raw signature is
understated relative to its opponent's should beat an offset built on raw signatures).

**Features and cutoff arguments.**
- Possession counts of strictly earlier games — constructed as per-(game, team) row counts
  in the possessions artifact restricted to `game_date` strictly before d, lag >= 1, P22
  guard. The 48-column table's SEVERE hazard (row multiplicity IS the target) applies to the
  TARGET game; here counts are taken ONLY over completed earlier games, which is precisely
  the lagged construction the table permits proposing and this entry adjudicates for
  preregistration. OT games enter raw (uncorrected) on BOTH sides of every mean;
  preregistered as-is, no OT reweighting — any OT adjustment would be a separate arm, and
  none is proposed (the raw/regulation-equivalent mismatch is not a value channel here:
  the correction contrast differences OT noise symmetrically).
- `offense_team_id` / `defense_team_id` — ELIGIBLE; identity/grouping keys, including
  locating opp(g) for each earlier game.
- `game_date` — ELIGIBLE; cutoff boundary.
- `game_id` — ELIGIBLE; join key only.

**K0_MATCHED sketch.** Null holds identical rows, target, folds, weights, offset, and the
identical E=3 imputation machinery (z5 = 0 when either team has < 3 prior same-season
games, or when any required leave-one-out opponent mean is undefined — the same
deterministic rule, extended symmetrically and preregistered here); treatment adds ONLY z5.
No re-centring: the league-mean centring inside z5's construction is part of the feature
definition, not a design change, and the null never sees the column at all.

**Fold-support argument.** z5 is continuous with cross-cluster variance in every season
(schedule imbalance is largest early, but persists all season in a short league schedule);
the E=3-plus-undefined-LOO imputation rule covers every row deterministically, so the
column exists on all 2,982 rows in all five folds. Single antisymmetric column; full rank
per fold. D010 caveat carried explicitly: the imputation stratum's coverage is flattered by
the opening-day exclusion, and this arm's early-season mechanism is evaluated on a universe
missing the hardest cold-start day — reported on both universes per `do_not_substitute`.

**Expected failure mode (kill criterion, preregistered).** Dead if the cluster-resampled
interval for beta5 covers 0 or the primary gate shows no improvement over K0. Withdrawn as
a design failure (before any performance number) if the S4/S5 offset-dependency audit finds
z5 near-affine in the offset or in the incumbent `pace_gap` within training folds — that
would mean the incumbent's construction already implicitly schedule-adjusts, and the
correction carries nothing.

**Multiplicity family.** `OPPONENT_MECHANISM_F1`.

---

## What was considered and NOT proposed, and why

- **Lineup-continuity / roster-churn mechanisms** (lagged `off_p*`/`def_p*` overlap): these
  are lineup-availability mechanisms; the mandate restricts that family to ELIGIBLE columns
  and no ELIGIBLE column carries lineup content. Family empty this wave.
- **Injury/absence mechanisms:** S3 measures ZERO cutoff-valid rows in every fold. Nothing
  to build.
- **Overtime-correction of trailing counts:** its only clear value channel is the
  raw/regulation-equivalent mismatch, prohibited by name. H5 notes OT noise differences out
  symmetrically instead.
- **season_type / is_playoff_game refinements:** fold-2026 degeneracy (S7) makes any new
  playoff term a fallback-contract liability for zero opponent-differentiated content.
- **Market, tip-time, era, coaching families:** excluded/CUTOFF_UNPROVEN in the packet;
  honoured without exception.
