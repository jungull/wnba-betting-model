# P31 Final Ideation — CUTOFF-VALIDITY AND LEAKAGE

Role: cutoff_leakage
Packet: EVIDENCE_PACKET_V3.json, sha256 `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` (computed by this role; matches the role prompt's expected hash).

Attestation of reads: exactly `ROLE_PROMPT.md` and `EVIDENCE_PACKET_V3.json` in this directory, plus this file, which I wrote. Nothing else.

---

## 0. The shared lag operator L — the cutoff argument every hypothesis inherits

Every hypothesis below builds features ONLY through the following operator, so the cutoff
proof is stated once and inherited.

For a target team-game row (g, t) with schedule date `d_g`:

- **Prior-game set** `P(t, g)` = all contract team-games of team `t` with `game_date < d_g`
  strictly (date granularity; a same-date row is NEVER a prior game — same-game and same-day
  joins fail closed, exactly the P22 rule).
- **Source bytes**: possession rows of `possessions_raw_v2` keyed by `game_id` (ELIGIBLE,
  join key only), joined to `game_date` (ELIGIBLE — schedule fact; the packet notes the
  master_team revision risk and still adjudicates the DATE eligible). Team attribution via
  `offense_team_id` / `defense_team_id` (ELIGIBLE as identities). The multiplicity hazard the
  packet flags for these identities is a TARGET-GAME hazard (target-row counts reconstruct
  the target); aggregates over `P(t,g)` rows are lagged realised outcomes of completed prior
  games — precisely the object the postgame-surrogate rules license: documented lag >= 1
  completed prior game, source keys and dates strictly before the cutoff.
- **Proof tool**: `postgame_surrogate_guard.py` (sha
  `951e85132f470fdd939c8039958f0544413aaaa485da5dba7da9c1b9b73ceeda`). P22's proven results
  bind: unlagged current-game constructions FAIL; correctly lagged prior-game constructions
  PASS all cutoff checks. Every feature below is submitted to the guard with its lag
  transformation recorded in the receipt.
- **Weights**: exponential decay over `P(t,g)` by game recency, half-life **h = 10 games**,
  with a season-boundary discount **λ = 0.5** applied once per season crossed. Both constants
  are fixed here, before any fit, and are not tunable.
- **Fold-support floor**: the resolved universe (2,982 rows / 1,491 clusters) EXCLUDES the
  no-prior-games stratum and the 2021 opening day (D010), so every row has |P(t,g)| >= 1 by
  construction. Every L-feature is therefore defined on every row of every one of the FIVE
  folds (D006: train_lt_2022 … train_lt_2026). D010's caveat is acknowledged: none of the
  hypotheses below claims a cold-start mechanism, so the flattered-by-construction caveat
  does not silently advantage them.

Prohibition compliance, stated once: no target-game column enters any design; no PROHIBITED
column (`all_possessions`, `source_pbp_game_id`) is used; no CUTOFF_UNPROVEN column (`era`,
tip times, market family, the T-wire) is used; no injury field is proposed as a feature
(H3 addresses the injury question the only way the mandate permits); no hypothesis's value
channel is the raw/regulation-equivalent scorer mismatch — all mechanisms are stated against
the primary target REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS and pass through P28's
primary-before-secondary ordering.

Offset-guard compliance (S4/S5): every treatment below is a bounded SHARE or DISTANCE, not a
pace level, so it is not an affine reconstruction of the offset; each arm is nonetheless run
through `offset_dependency_guard` and dies if it is found to be a near-affine function of the
offset or of the incumbent projection. Where own- and opponent-versions of a quantity exist,
they enter as ONE preregistered composite (1 df), never as a free pair.

---

## CUTOFF_LEAKAGE_H1 — Transition-mix persistence

**Mechanism (one).** Team-game possession count is, mechanically, playing time divided by
mean possession duration, and mean duration is a mixture of short transition possessions and
long half-court possessions. A team's propensity to play in transition is a stylistic trait
that regresses and transfers across opponents differently than the scalar pace level does,
so the trailing MIXTURE COMPOSITION predicts the target beyond the trailing pace level the
incumbent offset already carries.

**Formula sketch.**
`short_off(t,g) = Σ_{p ∈ P(t,g), offense_team_id=t} w(p)·1[duration_sec(p) ≤ 8] / Σ w(p)`
`short_def(t,g) = same with defense_team_id = t` (short possessions ALLOWED).
Treatment (1 df): `x_H1(g,t) = ( short_off(t,g) + short_def(opp(g,t),g) ) / 2` — the
game-level transition intensity implied by this row's offense and the opposing defense.
The 8-second threshold is fixed here, not tuned.

**Features and cutoff arguments.**
- `duration_sec` — S8 table, LAGGED_USE_ONLY ("only an aggregate over STRICTLY EARLIER games
  may be proposed"); this is that aggregate, under L; P22 proved lagged prior-game duration
  passes all cutoff checks.
- `offense_team_id`, `defense_team_id` — S8, ELIGIBLE; identity attribution only.
- `game_date` — S8, ELIGIBLE; the cutoff boundary itself.

**K0_MATCHED sketch (per `k0_matched.core_rules`).** Identical rows, target, five folds,
game-cluster weights, the frozen incumbent projection as offset, the frozen fallback
machinery, and the nuisance set including `is_playoff_game` with the GATE_INVOCATION_CONTRACT
§4 frozen fold-level fallback declared for the fold-2026 degeneracy. The null holds ALL of
that; the treatment adds ONLY `x_H1`. No re-centring, no changed fallback, no estimator
change is credited.

**Fold support.** `x_H1` is defined on every resolved row (|P| >= 1 by universe
construction), bounded in [0,1], continuous; short possessions exist in every season, so
zero-variance failure is not expected in any of the five folds — verified prospectively by
`fold_estimability_guard` (rank, zero-variance, cluster-support, condition number) before
any result is visible. No tier ladder, so P27's tier-support constraint is not triggered.

**Expected failure mode (kill conditions, stated now).** (a) The preregistered score/LR test
of the treatment against K0, family-adjusted, is null on the fold-aggregated evaluation; or
(b) `offset_dependency_guard` finds `x_H1` near-affine in the offset — meaning the mixture
share is just re-encoding trailing pace and adds nothing. Either kills the arm.

**Multiplicity family.** `LAGGED_TEMPO_MIX` (shared with H4; the family correction spans
both arms).

---

## CUTOFF_LEAKAGE_H2 — Evidence-contamination correction (garbage time)

**Mechanism (one).** The incumbent's trailing-pace evidence is generated partly in
non-competitive game states, where possession generation departs systematically from
competitive play. Teams differ in how much of their recent evidence was garbage time, so the
incumbent projection carries a heterogeneous, measurable bias: rows whose trailing evidence
is more contaminated should deviate from the offset in a predictable direction. This is a
correction to the QUALITY of the lagged evidence, not a new pace signal.

**Formula sketch.**
`nc(t,g) = Σ_{p ∈ P(t,g), offense_team_id=t} w(p)·1[non_competitive_conservative(p)] / Σ w(p)`
Treatment (1 df): `x_H2(g,t) = ( nc(t,g) + nc(opp(g,t),g) ) / 2` — contamination of the
joint evidence behind this game's projection.

**Features and cutoff arguments.**
- `non_competitive_conservative` — S8, LAGGED_USE_ONLY; the packet notes it is exactly
  reproducible from three realised columns and is pre-possession within its own game; used
  here ONLY as a lagged aggregate over strictly earlier completed games under L.
- `offense_team_id`, `game_date` — ELIGIBLE, as in H1.

**K0_MATCHED sketch.** Identical to H1's null (same offset, folds, weights, fallbacks,
nuisances); treatment adds ONLY `x_H2`. Critically, K0 is NOT granted any re-weighting of
its evidence — the arm must show the correction as an additive term, not smuggle in a better
estimator (core rule: no credit for free re-centring or changed fallback).

**Fold support.** Defined on every row; bounded in [0,1]; blowouts occur in every season so
within-fold variance is expected in all five folds; S7 guard run prospectively. No tiers.

**Expected failure mode.** (a) Null preregistered test vs K0; or (b) the preregistered
robustness check — adding `pace_evidence_depth` (an incumbent-equivalent feature governed by
the D009 standard-(a) scoped acceptance) to the nuisance set — absorbs the effect, which
would mean `x_H2` proxies evidence VOLUME, not contamination, and the mechanism is falsified
even if the naive test is positive. Either kills it.

**Multiplicity family.** `EVIDENCE_QUALITY_CORRECTION`.

---

## CUTOFF_LEAKAGE_H3 — Personnel-continuity (lineup churn), doubling as the injury-mechanism arm

**Mechanism (one).** Pace is produced by the players on the floor. When the personnel that
generated a team's trailing evidence differ from the personnel most recently observed, the
trailing estimate mis-projects. Lineup churn computed from PRIOR games' realised lineups is
the postgame-observable footprint of absences, returns and rotation changes — the same
mechanism an injury feature would exploit, measured from bytes that are actually
cutoff-valid.

**Mandate note on injury.** The packet measured ZERO cutoff-valid injury rows in every fold,
so no injury feature is proposed. What would make one provable prospectively: a capture
stream whose rows carry a source OBSERVATION timestamp at or before the declared pregame
cutoff plus documented availability-designation semantics (the injury_S3 classification
rule) — i.e., timestamped pregame status capture going forward, adjudicated under the D009
standard (b). This hypothesis is the mandated current-wave twin: it tests whether personnel
discontinuity moves the primary target AT ALL, using only lagged bytes. If churn shows
nothing, prospective injury capture loses its mechanistic warrant; if it shows signal, the
prospective feature has a preregistered effect direction to beat.

**Formula sketch.** For team t: usage vector over player ids,
`u_last(j)` = share of t's offensive possessions in its MOST RECENT prior game with player j
among {off_p1..off_p5}; `u_base(j)` = w-decayed share over `P(t,g)` EXCLUDING that most
recent game. Churn = total-variation distance
`churn(t,g) = 0.5 · Σ_j | u_last(j) − u_base(j) |` ∈ [0,1].
Treatment (1 df): `x_H3(g,t) = ( churn(t,g) + churn(opp(g,t),g) ) / 2`.
Active-set rule, preregistered: if `|P(t,g)| = 1` (no base window exists), `churn := 0` —
"no evidence of change" — a symmetric, training-support-independent, receipt-recorded rule,
declared per S7 so the arm is estimable rather than UNEVALUABLE.

**Features and cutoff arguments.**
- `off_p1..off_p5` — S8, LAGGED_USE_ONLY (realised lineups are target-game outcomes; used
  ONLY from strictly earlier completed games under L). The packet's measurement that the
  five slots are ascending order statistics is respected: slots are read as an unordered
  set, no positional meaning is used.
- `offense_team_id`, `game_date` — ELIGIBLE, as above.

**K0_MATCHED sketch.** Same null machinery as H1/H2; treatment adds ONLY `x_H3`. The
interaction of churn with evidence depth is explicitly NOT in this arm — it would be a
separate arm whose K0 must carry both main effects (core rule: tier/interaction terms
require lower-order terms in the null).

**Fold support.** Defined on every row via the preregistered rule above; rows with
`|P| = 1` exist only among early-2021 team-games (cross-season L counts all history), i.e.
only inside train_lt_2022's training window, and the rule handles them symmetrically; bounded
[0,1]; roster churn exists in every season (trades, rotations), so variance is expected in
every fold; S7 guard run prospectively.

**Expected failure mode.** (a) Null preregistered test vs K0 on the fold-aggregated
evaluation; (b) the preregistered check that adding `pace_evidence_depth` to the nuisance
set absorbs the effect (churn proxying early-season thin evidence rather than personnel
change). Either kills the arm — and with it, the priority claim of prospective injury
capture on this target.

**Multiplicity family.** `PERSONNEL_CONTINUITY`.

---

## CUTOFF_LEAKAGE_H4 — Terminal-event mix: the forced live-ball-turnover channel

**Mechanism (one).** Mean possession duration decomposes over terminal events with
characteristically different durations AND different successor-possession types: a live-ball
turnover both truncates the current possession and launches an opponent transition
possession, so a defense's propensity to force live-ball turnovers raises game pace through
a channel the scalar pace level averages away. This is the defensive complement of H1's
offensive mixture: same family, different actor.

**Formula sketch.**
`fto(t,g) = Σ_{p ∈ P(t,g), defense_team_id=t} w(p)·1[end_reason(p) ∈ E_LB] / Σ w(p)`
over t's DEFENSIVE possessions, where `E_LB` is a fixed dictionary of live-ball-turnover
`end_reason` levels (steal-type terminations), preregistered as an explicit level list
before any fit; any level outside the dictionary counts only in the denominator — unmapped
levels fail closed, never enrich the numerator.
Treatment (1 df): `x_H4(g,t) = ( fto(t,g) + fto(opp(g,t),g) ) / 2`.

**Features and cutoff arguments.**
- `end_reason` — S8, LAGGED_USE_ONLY; lagged categorical aggregate under L only.
- `defense_team_id` — S8, ELIGIBLE; identity attribution of the defensive possession.
- `game_date` — ELIGIBLE.

**K0_MATCHED sketch.** Same null machinery; treatment adds ONLY `x_H4`. If H1 and H4 are
ever carried in one arm, the null of each must contain the other — they are declared
separate arms in the same family precisely so neither borrows the other's credit.

**Fold support.** The fixed level dictionary removes the fold-local unseen-level hazard
(S7 unique-level check); shares defined on all rows, bounded; turnovers occur in every
season; era is NOT used — schema drift across eras is handled entirely by the fail-closed
dictionary, never by conditioning on the CUTOFF_UNPROVEN `era` column.

**Expected failure mode.** (a) Null preregistered test vs K0; (b) redundancy: conditional on
H1's `x_H1` (the within-family joint test), `x_H4` adds nothing — the family is scored
jointly and the weaker member is dropped by the preregistered family rule, not post hoc; (c)
offset-guard rejection as in H1. Any of the three kills it.

**Multiplicity family.** `LAGGED_TEMPO_MIX` (with H1; family-level correction declared).

---

## CUTOFF_LEAKAGE_H5 — Schedule rest and the lag operator's positive control

**Scope declaration, honest.** The treatment here is built from `game_date` and team
identities — ELIGIBLE schedule columns — passed through the SAME lag operator L (its "prior
completed game" set), not from a LAGGED_USE_ONLY column. It is included by this role because
it is the maximally provable lagged construction available (pure schedule arithmetic, no
postgame bytes at all — it satisfies even the strict D009 standard (b) trivially), and it
serves as the wave's positive control: if the preregistration machinery, K0 matching and
fold guards cannot cleanly evaluate THIS arm, no H1–H4 result should be trusted. If the
program rules it off-mandate for this role, discarding it costs the wave nothing.

**Mechanism (one).** Fatigue: transition frequency and defensive pressure — the possession-
generating behaviours — decline on short rest and dense schedules, so the game's realised
possession count falls below the trailing projection when both teams are schedule-loaded.

**Formula sketch.**
`rest(t,g) = min( d_g − max{ game_date : prior contract games of t }, 10 )` (cap fixed here).
Treatment (1 df): `x_H5(g) = ( rest(t,g) + rest(opp(g,t),g) ) / 2`.
Schedule density (games in the trailing 7 days) is a SEPARATE potential arm, not this one.

**Features and cutoff arguments.** `game_date` (ELIGIBLE — the cutoff boundary itself;
master_team revision risk carried as the packet carries it), team identities (ELIGIBLE).
No realised-outcome column is touched; the only lag content is the EXISTENCE of the prior
completed game, which is exactly the universe's own resolvedness criterion.

**K0_MATCHED sketch.** Same null machinery as all arms; treatment adds ONLY `x_H5`.

**Fold support.** Defined on every resolved row; the cap bounds offseason leverage; in-season
rest varies in every season, so every fold has variance; S7 guard run prospectively.

**Expected failure mode.** Null preregistered test vs K0 kills it. There is no scorer-
mismatch channel and no offset-affinity risk (rest is not a pace level); if the offset guard
nonetheless flags it, that is evidence the incumbent already encodes schedule structure, and
the arm dies.

**Multiplicity family.** `SCHEDULE_FATIGUE`.

---

## Cross-cutting declarations

1. **No fitting occurred.** Nothing here reports or implies a performance estimate; all
   constants (h=10, λ=0.5, 8 s, cap 10 d, E_LB dictionary) are fixed in this document before
   the preregistration chain P33–P37 and may not be tuned inside it.
2. **Five folds, not six.** All fold-support arguments are stated against D006's five
   expanding-window folds.
3. **Families.** `LAGGED_TEMPO_MIX` = {H1, H4}; `EVIDENCE_QUALITY_CORRECTION` = {H2};
   `PERSONNEL_CONTINUITY` = {H3}; `SCHEDULE_FATIGUE` = {H5}. Each family carries its own
   correction; no arm hides a recalibration (S4 rule: calibration is its own family, and none
   of these arms touches the calibration slope or intercept structure).
4. **Enforcement path.** Every candidate frame passes `postgame_surrogate_guard` (P22),
   `merge_guard` cardinality checks (P23), `offset_dependency_guard` (P25), and
   `fold_estimability_guard` (P27) BEFORE any result exists, because D005 established that
   the shared feature_gate enforces none of this.
