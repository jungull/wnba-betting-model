# P31 Final Ideation — COLD-START AND FALLBACK

Role: coldstart_fallback (one of six independent sources, final ideation wave)
Packet: EVIDENCE_PACKET_V3.json, sha256 `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` (computed and matched against ROLE_PROMPT.md).
Files read: ROLE_PROMPT.md, EVIDENCE_PACKET_V3.json — nothing else. This file is the only file written.

Target: REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS (unchanged, `six_dimension_check.target_unit`).
Universe: 2,982 team-game rows / 1,491 clusters resolved; 2,990 / 1,495 full schedule. The 8-row / 4-game
difference IS the 2021 opening day (D010) — the unresolved-no-prior-games stratum.
Folds: five expanding-window folds per D006 (train_lt_2022 … train_lt_2026).

## Standing constraints this document binds itself to

1. **D010 flattery caveat.** The fitted universe excludes the four 2021-05-14 games — the only
   zero-evidence games in the archive. Therefore every hypothesis below targets the THIN-evidence
   stratum (small but nonzero prior evidence), not the zero-evidence stratum, and no claim of
   "cold-start coverage" below extends to rows the universe does not contain. Cold-start strata
   results must be reported against both universes per `inference.report_both`.
2. **The S6 trap, both directions.** For every arm below, K0_MATCHED carries the evidence-depth
   *level* structure (so the arm cannot take credit for depth-indexed re-centring, which is not the
   mechanism) but K0 does NOT carry the substantive carryover/drift information itself (so the null
   has not already absorbed the bias the arm exists to remove). Each K0 sketch states which side of
   the line each term sits on.
3. **Lagged constructions.** The S8 table marks every realised possession column LAGGED_USE_ONLY and
   says the lagged construction "needs its own adjudication — this node does not license one." Every
   lagged feature below is therefore SUBMITTED FOR ADJUDICATION under postgame_surrogate_guard_S1
   (P22): documented lag of >= 1 completed prior game, source keys and timestamps preceding the
   cutoff, same-game joins fail closed, receipts record the lag transformation. P22's proven result
   ("correctly lagged prior-game duration PASSES all cutoff checks") is the precedent relied on.
4. **Excluded families.** No injury features (S3: zero cutoff-valid rows in every fold), no tip
   times (P29), no market odds (P2B), no `era` (CUTOFF_UNPROVEN), no coaching (D008:
   PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN), no `is_playoff_game` as a new term (fold-degenerate in
   2026, S7). No same-game information under any disguise. No value channel through the
   raw/regulation-equivalent scorer mismatch: every prior-game aggregate below is
   regulation-equivalent by construction (prior-game OT possessions rescaled using that prior game's
   own lagged duration/overtime columns), and every arm passes the P28 primary-before-secondary
   ordering contract on the primary target.
5. **Offset discipline (S4/S5).** No term below is an affine function of the offset or reconstructs
   it; H2 is declared in the calibration family, the only family in which offset-slope terms are
   admissible, with its own nested null and multiplicity accounting per `k0_matched.core_rules`.
6. **Estimability (S7).** Every arm declares either a positive fold-support argument for all five
   folds or a preregistered active-set rule (training-support-based, symmetric between arm and null,
   receipt-recorded) per the fold_local_estimability_guard_S7 rule and the GATE_INVOCATION_CONTRACT
   §4 frozen fold-level fallback requirement.

Notation used throughout:

- `n_i` = number of the team's COMPLETED same-season contract games strictly before the target
  game's date. Built from schedule facts only (game_date ELIGIBLE, season ELIGIBLE,
  offense_team_id ELIGIBLE by identity join) plus completedness of strictly earlier games.
- `m_F` = training-fold league mean of the target, computed on training rows only.
- `depth` = pace_evidence_depth, `opp_depth` = opp_pace_evidence_depth, `gap` = pace_gap — the
  incumbent-equivalent possession features admitted under D009 standard (a) (Stage 1B scoped
  acceptance governs the receipted path; noted that under standard (b) they are CUTOFF_UNPROVEN,
  and this document does not merge the standards).
- `offset` = the frozen incumbent projection entering as offset.

---

## COLDSTART_FALLBACK_H1 — Prior-season carryover with evidence-decay weight

**Mechanism (one).** Early in a season the incumbent's within-season evidence is thin, and its
projection under-uses the strongest information that exists at that moment: the same franchise's
full prior-season pace identity. Basketball: pace is a coached, roster-borne style that persists
across the off-season far more than a handful of early games can reveal; statistically, the
prior-season team deviation from league mean is a low-variance predictor whose optimal weight
decays as within-season evidence accumulates. The S6 halt finding (bias 37–42% of MSE on
cold-start strata, per the halt findings this packet carries by hash) is the signature of exactly
this under-use: systematic, not noise.

**Formula sketch.**

    eta_i = offset_i + [K0 terms] + beta1 * dev_prev_i + beta2 * w(n_i) * dev_prev_i

    dev_prev_i = mean regulation-equivalent offensive possessions per team-game of team i over ALL
                 of its prior-season contract games  minus  the league mean over all prior-season
                 contract games (all games strictly earlier than the target game's date)
    w(n) = 1 / (1 + n/h), h = 5 preregistered and FIXED (no search)

Treatment = the pair {dev_prev, w(n)·dev_prev} (2 df, tested jointly). Teams with no prior season
in the archive get dev_prev = 0 (fallback to league level) — the fallback is identical in arm and
null per core rule 1.

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| game_date | S8 table, ELIGIBLE ("schedule fact; it is the cutoff boundary itself"; master_team revision risk noted) | fixed before tip; used only to order games and delimit seasons |
| season | S8 table, ELIGIBLE | schedule fact; used ONLY to delimit "prior season", never entered as a feature (fold-identifier hazard respected) |
| offense_team_id / defense_team_id | S8 table, ELIGIBLE | identity via drop_duplicates join only, per the SEVERE multiplicity hazard note; join key for team history, never a target-game row aggregate |
| lagged prior-season regulation-equivalent possession counts | S8 LAGGED_USE_ONLY columns (offense_team_id row multiplicity, period, duration_sec, is_overtime of STRICTLY EARLIER games) | postgame_surrogate_guard_S1: lag >= 1 completed prior game; each prior game's pbp exists after that game and before the target cutoff; submitted for adjudication per S8; P22 precedent (lagged duration PASSES) |
| n_i | derived from ELIGIBLE schedule facts + completedness of strictly earlier games | every input known at the cutoff |

**K0_MATCHED sketch (per `k0_matched.core_rules`).** Identical rows, target, five folds,
game-cluster weights, offset, fallback machinery, and nuisance terms. K0 additionally holds
`w(n)` as a MAIN effect and the incumbent structural terms (gap, depth, opp_depth) — so the null
already owns every depth-indexed level/re-centring degree of freedom (S6 trap direction 1: no
credit for re-centring) — but K0 does NOT hold dev_prev in any form (S6 trap direction 2: the null
must not already absorb the carryover information the arm exists to add). ONLY the treatment adds
the carryover pair. Lower-order rule satisfied: the interaction's main effects are w(n) (in K0)
and dev_prev (inside the treatment block, tested jointly with the interaction).

**Fold-support argument.** dev_prev is identically zero across all training rows of fold
train_lt_2022 (its training set is 2021 only — the archive's first season, no prior season exists),
so the treatment is zero-variance there and the arm/fold would be prospectively unevaluable.
DECLARED ACTIVE-SET RULE (preregistered, training-support-based, symmetric, receipt-recorded): the
treatment block enters a fold iff >= 10 training clusters carry |dev_prev| > 0; under the archive's
structure this activates train_lt_2023 … train_lt_2026 (every 2022+ team-season has a 2021+ prior
season) and deactivates train_lt_2022 for arm AND null identically. No silent pooled pass (S7).

**Expected failure mode (kill criteria, stated before any result).** (a) The joint treatment adds
no out-of-fold improvement on the preregistered thin-evidence stratum (n <= 5) beyond K0 under the
family's multiplicity control; (b) or the improvement appears only in the all-rows aggregate and
not in the thin-evidence stratum (then the mechanism is mislabeled and the arm dies as a
cold-start claim); (c) or beta2's sign contradicts decay (weight increasing with n). Any of these
kills the hypothesis. Per D010, absence of the zero-evidence stratum is acknowledged: a null
result here does NOT license the claim that carryover is useless at n = 0.

**Multiplicity family.** COLDSTART_FALLBACK (substantive), joint accounting with H3–H6.

---

## COLDSTART_FALLBACK_H2 — Evidence-depth-indexed calibration slope on the offset

**Mechanism (one).** When its evidence is thin the incumbent projection is over-dispersed: team
estimates built on few games carry sampling noise that the projection passes through undamped, so
extreme projections at low depth are too extreme. Statistically this is classic under-shrinkage;
the optimal regression-to-the-mean coefficient on the projection's deviation from league level is
below 1 at low evidence depth and rises toward 1 as depth grows. The S6 cold-start bias share is
consistent with a fallback curve that shrinks too little, too late.

**Formula sketch.**

    eta_i = m_F + b(depth_i) * (offset_i - m_F) + [preregistered lower-order intercept structure]
    b(depth) = 1 + gamma * 1/(1 + depth/h),  h = 5 preregistered and FIXED; single parameter gamma

Null: gamma = 0, i.e., slope fixed at its incumbent value 1 with the same intercept structure —
exactly the calibration-only null of `k0_matched.core_rules`. Treatment: gamma free.

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| pace_evidence_depth | D009 standard (a): incumbent-equivalent feature on the receipted Stage 1B path | scoped acceptance governs; carried as CUTOFF_UNPROVEN under standard (b), standards not merged |
| offset (incumbent projection) | K0 core rules / offset guard | not a feature; the calibration object; slope terms admissible only inside this family |
| m_F | training-fold statistic | computed from training rows only, per fold |

**K0_MATCHED sketch.** Calibration-family nested null per core rule 2: identical rows, target,
folds, weights, offset, fallback; the tested parameter fixed at its incumbent value (slope 1) with
the preregistered lower-order intercept structure in BOTH arm and null. ONLY gamma is added. S6
trap: the depth-indexed intercept is NOT granted to the treatment (it would be re-centring); the
only new degree of freedom is the depth-indexed slope.

**Fold-support argument.** depth varies within every training fold: each training set spans at
least one full season, and within any season depth runs from its season-opening floor to its
season-end ceiling, so 1/(1+depth/5) has positive variance and full rank against the intercept
structure in all five folds (subject to the S7 guard's condition-number check, which is expected to
pass because the transform is bounded and nonlinear in depth). No active-set rule needed.

**Expected failure mode.** (a) gamma's preregistered interval estimate covers 0 in the joint
analysis; (b) or gamma > 0 (anti-shrinkage — mechanism refuted); (c) or the MSE reduction on the
thin-evidence stratum (depth in its lowest preregistered bucket) is not positive out-of-fold.
Any of these kills it. A positive result that vanishes when the intercept structure absorbs it is
re-centring, not shrinkage, and counts as failure.

**Multiplicity family.** CALIBRATION — its own family with its own nested-null accounting per
`k0_matched.core_rules`; deliberately NOT pooled with the substantive family.

---

## COLDSTART_FALLBACK_H3 — League-common early-season pace drift (within-season decay)

**Mechanism (one).** Beyond any team's own evidence problem, the LEAGUE plays at a different tempo
in the season's first weeks: new rotations, unfinished defensive installs and conditioning produce
more turnovers and short possessions, and pace settles as the season matures. The incumbent, built
from prior-game evidence that is dominated by late-prior-season play, inherits the settled tempo
and misses the league-common early-season deviation. This is estimable even where team-level
history is thin precisely because it is league-common — the natural fallback signal when
team-specific evidence is weakest.

**Formula sketch.**

    eta_i = offset_i + [K0 terms] + delta * exp(-n_i / tau),  tau = 5 preregistered and FIXED
    single parameter delta; n_i as defined above (within-season completed-game count)

Continuous decay chosen over an n=0 bucket DELIBERATELY: the 2021 season in the fitted universe has
no n=0 rows (D010), so a bucket indicator would be degenerate in train_lt_2022; the continuous form
has support wherever early-season games exist.

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| n_i | derived from S8-ELIGIBLE schedule facts (game_date, season, offense_team_id identity join) + completedness of strictly earlier games | all inputs fixed or observable before tip |
| gap, depth, opp_depth (K0 only) | D009 standard (a) | scoped acceptance, as in H1 |

**K0_MATCHED sketch.** Identical rows, target, folds, weights, offset, fallback. K0 holds the full
incumbent structure (gap, depth, opp_depth) and the intercept — so any level information already
carried by total evidence depth belongs to the null (S6 trap direction 1). ONLY the treatment adds
delta·exp(−n/τ). The arm's claim is explicitly "a league-common WITHIN-SEASON drift term beyond
total-evidence depth": if exp(−n/τ) is near-collinear with depth in some fold, the S7
condition-number check must catch it and the arm/fold is unevaluable rather than silently credited.

**Fold-support argument.** Every training fold contains at least one complete season, and every
season contributes early-season games (n small) and late-season games (n large): 2021 contributes
n >= 1 (opening day excluded, D010), 2022+ contribute n >= 0. exp(−n/5) therefore has positive
variance in all five training folds; estimability in every fold rests on the S7 rank and
condition-number checks against depth, and no active-set rule is required. Declared risk: if the
guard finds near-collinearity with depth in train_lt_2022 (one season, depth ≈ monotone in n), the
arm/fold is prospectively UNEVALUABLE by the S7 rule — accepted in advance rather than patched.

**Expected failure mode.** (a) delta's interval covers 0; (b) or the improvement concentrates in
strata OTHER than early-season (n <= 5) rows — mechanism mislabeled, killed as a cold-start claim;
(c) or the S7 guard rules the term unevaluable against depth in >= 2 folds, in which case the
hypothesis is unevaluable as posed and is retired without result. Direction is NOT preregistered
(early-season pace could settle up or down); what is preregistered is that a sign FLIP across folds
kills it — a real league-common drift must be sign-stable across the five folds.

**Multiplicity family.** COLDSTART_FALLBACK (substantive).

---

## COLDSTART_FALLBACK_H4 — Roster-continuity-conditioned carryover (lagged-lineup overlap)

**Mechanism (one).** Prior-season carryover (H1) is only as good as the roster that carries it.
Pace identity travels with players and rotations: a franchise returning its core replays its style;
a rebuilt roster does not. Statistically, the carryover coefficient is heterogeneous, and the
observable moderator is the overlap between the player set actually used this season so far and the
player set used last season — both constructible from strictly earlier games only.

**Formula sketch.**

    cont_i = Jaccard( P_curr_i , P_prev_i )
    P_curr_i = set of player ids in off_p1..off_p5 / def_p1..def_p5 rows of team i's completed
               same-season games strictly before the target (empty when n_i = 0)
    P_prev_i = same construction over team i's full prior season
    fallback: when n_i = 0, cont_i := training-fold mean of cont (identical fallback in arm and null)

    eta_i = offset_i + [K0 terms incl. the H1 carryover pair] + beta3 * (cont_i - cbar_F) * dev_prev_i

Treatment = the single centred interaction (1 df). cbar_F = training-fold mean of cont (centring
inside training only).

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| off_p1..off_p5, def_p1..def_p5 of STRICTLY EARLIER games | S8 table, LAGGED_USE_ONLY ("slots are ascending order statistics" — treated as unordered sets, so the no-positional-meaning caveat is harmless) | postgame_surrogate_guard_S1 lag >= 1 completed game; submitted for adjudication per S8; P22 precedent |
| dev_prev, w(n), n | as in H1 | as in H1 |
| game_date, season, team ids | S8 ELIGIBLE | as in H1 |

**K0_MATCHED sketch.** K0 = H1's FULL arm design (offset, incumbent terms, w(n) main effect, AND
the carryover pair {dev_prev, w(n)·dev_prev}) plus the cont main effect (lower-order rule for the
interaction) and the identical n=0 fallback machinery. ONLY the treatment adds the
(cont − cbar)·dev_prev interaction. S6 trap: uniform carryover belongs to the null here — this arm
is credited only for the continuity-CONDITIONING of carryover, nothing it shares with H1.

**Fold-support argument.** Same structural zero as H1: cont and dev_prev are undefined/degenerate
in train_lt_2022 (no prior season in its training set). DECLARED ACTIVE-SET RULE, identical in form
to H1's (>= 10 training clusters with a defined, nonconstant interaction term), activating
train_lt_2023 … train_lt_2026, symmetric between arm and null, receipt-recorded. Within active
folds, cont varies across franchises (off-season roster churn differs by team every year — a
structural fact of a hard-cap league with expansion and free agency), and the S7 rank check
verifies it against the K0 columns.

**Expected failure mode.** (a) beta3's interval covers 0 given H1's terms in the null — the
continuity story adds nothing beyond uniform carryover; (b) or beta3 < 0 (carryover WEAKER for
continuous rosters — mechanism refuted); (c) or the lagged-lineup construction fails its P22
adjudication, in which case the hypothesis is inadmissible, not merely null. Explicitly accepted
in advance: at n = 0 (season openers, the most cold-start rows in the universe) the moderator is
the fallback constant, so this arm claims nothing on openers themselves — its claim lives on
n in [1, ~8].

**Multiplicity family.** COLDSTART_FALLBACK (substantive).

---

## COLDSTART_FALLBACK_H5 — Expansion-franchise fallback bias

**Mechanism (one).** A franchise in its first archive season has NO franchise history at all; the
incumbent's implicit fallback treats it as a league-average team. Basketball says the fallback is
biased: expansion rosters are assembled from expansion drafts and free agency, skew young and
thin on established half-court creators, and such teams tend to play a distinct tempo profile
while opponents also adapt to them slowly. Statistically: a level offset for the
expansion-team-game stratum, decaying as the team accrues its own evidence.

**Formula sketch.**

    exp_i = 1{ team i's first season in the contract schedule is >= 2022 and equals season_i }
    (2021 is the archive start; first-appearance-in-2021 is archive truncation, NOT expansion,
     and is deliberately excluded from the definition)

    eta_i = offset_i + [K0 terms] + kappa * exp_i * exp(-n_i / tau),  tau = 5 fixed as in H3

Treatment = single parameter kappa. Defense-side analogue (opponent is expansion) is NOT proposed —
one mechanism, one term.

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| offense_team_id, season, game_date | S8 ELIGIBLE | first-appearance is a schedule identity fact, fixed before the season begins |
| n_i | as in H3 | schedule + completed prior games |
| team-id integrity | dimension_cardinality_guard_S2: the PHO/PHX duplicate (team_id 1611661317) | DECLARED PRECONDITION: first-appearance must be computed after resolving the duplicate from documented effective-date semantics, or per the S2 rule this family is EXCLUDED — inherited verbatim |

**K0_MATCHED sketch.** Identical rows, target, folds, weights, offset, fallback. K0 holds the
incumbent structure AND H3's league-common decay term exp(−n/τ) as a granted lower-order/structural
term — so the null already owns generic early-season drift, and ONLY the expansion-specific
increment is credited to the treatment (S6 trap direction 1). K0 does not hold any
expansion-indexed term (direction 2).

**Fold-support argument.** This is the honest weak point, declared rather than hidden. exp_i is
nonzero only in seasons where a franchise debuts (2022+ definition). Whether ANY training fold
contains >= 10 clusters of expansion team-games is a measurable fact of the schedule that this
document does not assert from memory. DECLARED ACTIVE-SET RULE: the term enters a fold iff >= 10
training clusters have exp_i = 1; folds below the floor carry arm = null for this term
(prospectively UNEVALUABLE per S7, no silent pooled pass). If NO fold meets the floor, the
hypothesis is retired unevaluated and reported as such — that outcome is itself informative about
the universe's cold-start coverage and must be recorded against the D010 caveat.

**Expected failure mode.** (a) Retired for support (as above); (b) kappa's interval covers 0 in
every active fold-set analysis; (c) or the effect is absorbed entirely by H3's league drift term in
K0 (the expansion increment is not distinguishable from generic early-season drift). Sign is not
preregistered; sign instability across active folds kills it.

**Multiplicity family.** COLDSTART_FALLBACK (substantive).

---

## COLDSTART_FALLBACK_H6 — Evidence-depth asymmetry weighting of the pace gap

**Mechanism (one).** A game's pace projection combines two teams' estimates, but early in the
season the two teams rarely have EQUAL evidence: staggered schedules mean one side may have played
several games while the other has barely played. The incumbent combines the two estimates as if
equally reliable. Statistically, the optimal combination tilts toward the better-evidenced side;
the observable signature is that the pace gap's predictive weight varies with the depth
DIFFERENCE between the teams.

**Formula sketch.**

    asym_i = s(depth_i) - s(opp_depth_i),  s(d) = 1/(1 + d/5) fixed transform (bounded, so the
             asymmetry saturates once both teams have played a handful of games)
    eta_i = offset_i + [K0 terms] + beta4 * gap_i * asym_i

Treatment = the single interaction (1 df). Note S5 discipline: gap is the incumbent's single
preregistered own-opp CONTRAST — the admissible object under the offset guard ("a single
preregistered nonredundant contrast (own-opp) is admissible with fold-local full rank"); the
own/opp pair itself never enters.

**Features, sources, cutoff arguments.**

| feature | source in packet | cutoff argument |
|---|---|---|
| pace_gap | D009 standard (a) incumbent path; S4/S5 offset guard names the own-opp contrast admissible | scoped acceptance governs the receipted path |
| pace_evidence_depth, opp_pace_evidence_depth | D009 standard (a) | same |

No new data enters at all — this arm is built entirely from features the program has already
admitted, which makes it the cheapest cold-start hypothesis in the set to adjudicate.

**K0_MATCHED sketch.** Identical rows, target, folds, weights, offset, fallback. K0 holds gap,
depth, opp_depth main effects AND the asym main effect (lower-order rule; asym is a fixed transform
of depths, so granting it to the null costs nothing substantive and blocks re-centring credit).
ONLY the treatment adds gap·asym. S6 trap: all depth-level information is in the null; the arm is
credited solely for the reliability-weighting mechanism.

**Fold-support argument.** asym is nonzero exactly where the two teams' completed-game counts
differ in the s-transformed scale — early-season staggered scheduling guarantees such rows in every
season, and gap varies continuously; the product's fold-local rank against the four main effects is
verified by the S7 guard (full design [offset | nuisance | candidate] per the offset-dependency
rule, including the condition-number check). All five folds train on >= 1 full season, so support
is expected in every fold and NO active-set rule is declared; if the S7 check nevertheless fails in
a fold, the arm/fold is prospectively unevaluable by rule, accepted in advance.

**Expected failure mode.** (a) beta4's interval covers 0; (b) or the improvement does not
concentrate in rows with |asym| in its top preregistered bucket (mechanism mislabeled); (c) or
beta4 < 0, meaning the gap should be TRUSTED MORE when evidence is more asymmetric — refuting the
reliability mechanism. Any kills it.

**Multiplicity family.** COLDSTART_FALLBACK (substantive).

---

## Family declaration

- COLDSTART_FALLBACK (substantive): H1, H3, H4, H5, H6 — joint multiplicity accounting; H4 is
  additionally NESTED on H1 (its null contains H1's arm), and the program's accounting must treat
  the H1→H4 sequence as ordered, not independent.
- CALIBRATION: H2 alone, per `k0_matched.core_rules` (calibration "carries its own nested null and
  its own multiplicity accounting" and "may not hide inside a substantive arm").

## Attestation

Files read, in full: this directory's ROLE_PROMPT.md and EVIDENCE_PACKET_V3.json (sha256 computed:
`95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75`, matching the role prompt).
Files written: HYPOTHESES_coldstart_fallback.md (this file). Nothing outside this directory was
read. No fit was performed; no performance number appears above.
