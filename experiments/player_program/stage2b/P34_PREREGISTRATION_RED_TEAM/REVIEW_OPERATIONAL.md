# P34 red-team review — OPERATIONAL RELEVANCE dimension

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

**Reviewer dimension:** operational relevance — can each arm actually run at decision time in the
daily pipeline: pre-tip availability of every feature from receipted artifacts, cold-start
behaviour, PHO/PHX merge-guard fail-closed handling, the A19/A20 end_reason dictionary deferral,
A06 conditional-path operability, and whether expected failure modes are specific and falsifiable.

**Blindness attestation:** I did not author the P33 preregistration. I did not open, read, or
grep any other reviewer's file. A directory listing of `P34_PREREGISTRATION_RED_TEAM/` exposed
six filenames (`REVIEW_FOLD_ESTIMABILITY.md`, `REVIEW_K0_PARITY.md`, `REVIEW_LEAKAGE.md`,
`REVIEW_MULTIPLICITY.md`, `REVIEW_OFFSET.md`, `REVIEW_TARGET_UNITS.md`); no byte of their content
was read.

**VERDICT: ACCEPT_WITH_REQUIRED_CHANGES.**

**Stop conditions: NONE TRIPPED in my assessment.** None of my findings changes the primary
target, the K0 structure, the five-fold cluster-bootstrap inference structure, the candidate
universe, the cutoff-valid feature set, or the leakage status. The three Severity A findings are
arm-level operability defects; each has a closure path the draft itself already provides
(preregistered withdrawal-as-design-failure, or a pre-fit fallback declaration under
GATE_INVOCATION_CONTRACT section 4 made BEFORE the P35 freeze). One consequence — withdrawal of
A19 — changes a multiplicity family's composition through the draft's own preregistered
withdrawal mechanism; the multiplicity reviewer should confirm denominator handling, but that is
family accounting, not inference structure.

---

## 0. Input hash verification (ran first; all match)

`Get-FileHash -Algorithm SHA256 <path>` from the worktree root, compared case-insensitively:

| artifact | expected sha256 | result |
|---|---|---|
| `stage2b/P33_PREREGISTRATION_DRAFT/SPEC.json` | `066b2a04…d093` | MATCH |
| `stage2b/P33_PREREGISTRATION_DRAFT/REPORT.md` | `6d945b86…48ab` | MATCH |
| `stage2b/P32_CANDIDATE_SYNTHESIS/SPEC.json` | `1dc25981…138c` | MATCH |
| `stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json` | `95d24128…75` (`95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75`) | MATCH |

No mismatch; review proceeded. Nothing under `SEALED_RESULTS` was read (and no such directory
exists in this worktree). Nothing was fitted; no target value entered any statistic below; every
measurement is a schedule/feature/schema fact.

---

## 1. Severity A findings

### A-1. A19's live-ball dictionary CANNOT be constructed from the frozen artifact — the P35 deferral is already decided by the bytes, and the draft defers a question it could have measured

The draft freezes A19's `E_LB` as an "explicit level list frozen at P35 from the artifact's data
dictionary BEFORE any fit," carries "withdrawal as design failure if the frozen dictionary cannot
distinguish live-ball turnover terminators," and lists the adequacy question under
`could_not_establish`. It is establishable now, from frozen bytes, with one groupby:

```python
import pandas as pd
df = pd.read_parquet('experiments/player_program/possessions_v2/possessions_raw_v2.parquet',
                     columns=['season','end_reason'])
print(df['end_reason'].value_counts())
print(pd.crosstab(df['end_reason'], df['season']))
```

Measured on all 238,563 possessions: the complete `end_reason` vocabulary is
`defensive_rebound` (84,647), `made_shot` (82,738), **`turnover` (41,505)**, `made_ft_final`
(22,821), `period_end` (6,054), `technical_ft` (588), `inferred_flip` (200),
`miss_flip_no_rebound` (8), `made_ft_nonfinal_flip` (2). **There is exactly ONE turnover level,
undifferentiated.** No level distinguishes live-ball turnovers (steals) from dead-ball turnovers
(out-of-bounds, offensive foul, violation). The vocabulary is stable across all six seasons and
across both `era` values (v2/v3): `turnover` appears 5,736 / 6,787 / 7,212 / 7,301 / 8,490 /
5,979 times in 2021–2026, with zero nulls. There is no era schema drift to fail closed against —
and no live-ball distinction to freeze.

Consequence: A19's declared mechanism — "defensive live-ball turnover forcing … a creation
channel **distinct from clock tempo**" — is unmeasurable in this artifact. At P35 the dictionary
freezer faces exactly two options: (a) withdraw A19 (the preregistered outcome), or (b) degrade
`E_LB` to `{turnover}`, which silently converts A19 into a symmetric total-turnover-forcing
share — a *different* mechanism, materially overlapping A20's channel, that this red team never
reviewed. Option (b) chosen quietly at P35 is the landmine: a discretionary mechanism swap after
adversarial review, inside a family (LAGGED_TEMPO_MIX) that is *scored jointly* with A17, so the
swap would also change A17's effective correction.

**Required change:** resolve A19 NOW, not at P35. Either execute the preregistered withdrawal
(recording the measurement above as the reason and adjusting the LAGGED_TEMPO_MIX family to a
single-member test of A17, with the denominator change recorded), or — if the program wants the
total-turnover-forcing version — preregister it explicitly as a redefined mechanism BEFORE the
P35 freeze so it can be reviewed as what it is. Silence until P35 is not acceptable.

Note what this does NOT touch: **A20 is operable as frozen.** Its dictionary needs only
"turnover-terminator end_reason" levels, and the single `turnover` level suffices. The P35 freeze
for A20 should pin `{turnover}` with the per-season counts above attached as the receipt.

### A-2. Seven universe rows have ZERO strictly-earlier completed games — the definedness claims of A09, A10, A16, A17, A21, A24 (and A11's fallback coverage) are contradicted by the bytes, and no fallback is preregistered for them

The draft's lagged arms repeatedly assert total definedness: A16 "resolved universe already
excludes the no-prior-games stratum; defined on all 2,982 rows in every fold"; A17 "share defined
from |P| >= 1 by universe construction"; A21 "defined on every row, bounded [0,1]"; A24 "none
needed (cross-season prior game covers openers)"; A09 "both features continuous on every resolved
row"; A10 "contrast defined everywhere". These claims trace to P32 (`fold_support: defined on
every resolved row (|P| >= 1 by universe construction)`) and were carried into P33 unexamined.

Measured (script below): the universe retains rows for teams with **no completed prior game
anywhere in the archive**, because `pace_resolved` is TRUE for league-prior-fallback rows —
universe membership never required prior games. Within the full 2,990-row schedule:

```python
import possession_features as pf, pandas as pd
u = pf.load_universe(); F = u.frame.copy()
F['game_date'] = pd.to_datetime(F['game_date'])
P = pd.read_parquet(pf.PRIOR_PARQUET, columns=['game_id','team_id','game_date'])
P['game_date'] = pd.to_datetime(P['game_date'])
P = P.sort_values(['team_id','game_date'])
P['n_prior_any'] = P.groupby('team_id').cumcount()
z = F.merge(P[['game_id','team_id','n_prior_any']], on=['game_id','team_id'])
print(z[z['n_prior_any']==0][['team_id','game_date','season']])
```

**7 rows**: 1611661319, 1611661322, 1611661328, 1611661329 (all 2021-05-15 — teams that did not
play the excluded opening day, so D010's exclusion does NOT remove them) and the three expansion
debuts 1611661331 (2025-05-16), 1611661332 (2026-05-08), 1611661327 (2026-05-09). For symmetric
and contrast constructions both team-rows of each affected cluster are hit (≤ 14 rows). Fold
placement is the worst case available: the four 2021 rows sit in the TRAINING set of **all five
folds**; the 2025 debut is a TEST row of `train_lt_2025` and a training row of `train_lt_2026`;
the 2026 debuts are TEST rows of `train_lt_2026`. So the affected arms carry undefined features
in every training fold AND undefined out-of-fold predictions in the two most recent test folds.

Per arm, on the measured stratum: A16's `dev_team` (mean over last 5 completed games) is a mean
over an empty set; A17/A21's w-weighted shares are 0/0; A24's `rest = min(days since max prior
contract game date, 10)` is a max over an empty set — its declared fallback "cross-season prior
game covers openers" is simply false for franchise debuts; A09/A10's `d_t`/EWMA are means over
empty sets; A11's declared fallback covers ONLY 2021 (`train_lt_2022`), leaving the expansion
debut rows (n_cur = 0 and m_prev = 0 → 0/0) and — because A11's K0 carries `dprev_t` as a main
effect — the expansion teams' entire first seasons (46 rows in 2025, 57 in 2026 per the draft's
own A14 measurement) with an undefined null-design column.

An additional A16-specific hole: the draft's "ARCHIVE RETRIEVABILITY RESOLVED" claim says the
prior artifact "carries projected_team_off_possessions per (game_id, team_id) row for all 2,990
team-games." The column exists on 2,990 rows but is **NaN on 8 of them** (the unresolved
2021-05-14 opening-day rows; measured: `P['projected_team_off_possessions'].isna().sum() == 8`).
Those 8 games sit inside the last-5-game windows of the 8 opening-day teams' next games:
**40 own-side universe rows** (all 2021, hence in every training fold) have a window containing a
NaN archived projection, before counting opponent-side propagation through the contrast. A16's
residual is undefined there unless a skip-or-impute rule is preregistered. None is.

Why this is Severity A and not a nit: `feature_gate` blocks on `non_finite`
(GATE_INVOCATION_CONTRACT §3, blocking set), and §4 is explicit that a fold-degenerate feature
must FAIL for the fold **or be governed by a fallback frozen and registered before any result is
visible — there is no third option**, and a repair chosen after the failure is observed
invalidates the arm. As frozen, six arms walk into a blocking gate finding with no preregistered
fallback, and the "repair" would have to be invented mid-P36 — exactly what the contract
prohibits. The draft's own `d010_caveat` compounds the irony: it warns that cold-start coverage
is flattered because the hardest cold-start day was removed, while six arms assume the remaining
genuine cold-start rows do not exist.

The fix pattern already exists inside the draft — A18/A20/A26 (E=3 imputation, z := 0), A12
(dev_prev := 0 for no-prior-season teams), A22 (churn := 0 with no base window) are all correctly
covered. The defect is confined to the arms that asserted definedness instead of declaring a rule.

**Required change:** before the P35 task-card freeze, preregister an explicit, symmetric,
numerically-triggered empty-history rule for each of A09, A10, A11 (extend the fallback beyond
2021: dprev := 0 and dblend := dcur where m_prev = 0; define the n_cur = 0 ∧ m_prev = 0 case),
A16 (empty window AND NaN-projection-in-window handling), A17, A21, A24 (rest := cap for
no-prior-game teams, or the row is unevaluable — pick one, in advance), identical in arm and
null. Alternatively declare the affected rows prospectively unevaluable per arm — but say it
before fitting, with the trigger stated numerically.

### A-3. A08: BOTH enumerated window elements violate the arm's own frozen admissibility constraint in ALL FIVE training folds, and the "window rule" it defers to has no content anywhere

A08's record freezes: "K elements must keep L_t defined on all rows of every training fold under
the symmetric training-support window rule (R12 discipline); verified at P25/P27 invocation."
L_t requires ≥ K completed league games strictly before the row's date. Measured against the
possessions archive (1,495 games, first date 2021-05-14):

```python
pg = poss.drop_duplicates('game_id').sort_values('game_date')
F['n_league_prior'] = np.searchsorted(pg['game_date'].values, F['game_date'].values, side='left')
# per training fold: (n_league_prior < 20).sum(), (n_league_prior < 80).sum()
```

| training fold | rows with < 20 league priors | rows with < 80 league priors |
|---|---|---|
| train_lt_2022 | 36 | 154 |
| train_lt_2023 | 36 | 154 |
| train_lt_2024 | 36 | 154 |
| train_lt_2025 | 36 | 154 |
| train_lt_2026 | 36 | 154 |

The counts are constant because the folds are expanding windows and every training set contains
the start of 2021. **K = 20 fails the constraint in every fold; K = 80 fails it in every fold.**
On the strict reading of the frozen text, A08's entire enumerated grid is inadmissible at
invocation and the arm is dead on arrival — while carrying 2 charged elements of the
timeseries_shrinkage Holm budget. On the charitable reading, the "symmetric training-support
window rule" is supposed to handle those rows — but that rule has no definition anywhere: it is
not `ACTIVE_SET_RULE_PREREGISTRATION.json` (which I read in full — it is a TIER-indicator
10-cluster support rule, `S7_TIER_SUPPORT_v1`, conditioning on `SupportSummary`; it says nothing
about undefined continuous columns, and its own status line says it "is NOT registered for any
arm"), and neither the P33 SPEC nor A08's record states a trigger, an action (impute 0? drop
rows? collapse to null?), or the row accounting. GATE_INVOCATION_CONTRACT §4 requires the
fallback's trigger to be "stated numerically" before execution. A rule with a name but no content
is not a preregistered fallback; it is deferred discretion.

**Required change:** before P35, either (a) define the window rule numerically — e.g.
`L_t := 0 (training-fold-centered null value) for rows with n_league_prior < K, identically in
arm and null`, with the measured 36/154-row counts recorded — and restate the constraint so it is
satisfiable, or (b) withdraw A08 as a design failure (its own expected_failure_mode already names
"most likely death in its source family"). If rows are dropped rather than imputed, state the
delta_MAE row-accounting consequence explicitly.

---

## 2. Severity B findings

### B-1. A06 repair path (b) is a blank cheque: an unreviewed feature definition may enter at P35, after adversarial review

Path (a) — a preseason-published schedule artifact receipted under P23 discipline — is decidable
and fails closed; operationally it is also *hard* (it requires the schedule as published before
each of five PAST seasons, with provenance; nothing in `experiments/player_program/` carries it,
confirmed by P33 and consistent with my directory enumeration). Path (b) — "redefinition of the
phase/index denominator from past-only schedule facts" — is not a definition; it is a licence to
write one at P35. If exercised, a brand-new feature construction enters the fit set that no
red-team reviewer has seen. That is the same class of landmine as A-1(b): discretion scheduled
to occur after review. **Required change:** either freeze the path-(b) definition text now
(before P35), or strike path (b) and let A06 stand or fall on path (a) — in which case the
already-specified exclusion branch (`PREREGISTERED_CONDITIONAL_NOT_FIT`, 2 elements leave the
denominator) executes cleanly. The exclusion branch itself is well-constructed; my objection is
only to path (b)'s unbounded content.

### B-2. The P23 franchise-continuity precondition gates 13 arms — including the ENTIRE timeseries_shrinkage family — but names no producer, no artifact, and no deadline

`shared_arm_invariants.p23_franchise_continuity_precondition` lists A08, A09, A10, A11, A12,
A13, A14, A16, A17, A19, A21, A22, A24 (13 arms; exactly half the slate) and says the feature
fails closed absent the receipt. Correct discipline — but nothing in the draft says WHO produces
the receipt, WHAT artifact constitutes it, or WHEN it must exist. If it is still absent at P36
gate invocation, half the slate goes unevaluable at once, and the timeseries_shrinkage family
(A08–A11, all four members gated) vanishes entirely — post-freeze denominator churn under
fail-closed rules. The substance is trivially dischargeable NOW: measured, team_id 1611661317
(PHO/PHX) appears under ONE team_id across all six seasons 2021–2026 (247 rows) in the frozen
prior artifact, and the P23 merge guard already carries the declared-interval resolution
semantics (its FINDINGS pin PHO→PHX by season interval and the fail-closed criterion).
**Required change:** the P35 task cards must name the continuity receipt as a concrete
deliverable (artifact + hash) produced BEFORE fit dispatch — the same before-the-freeze
discipline the draft already imposes on A06's receipt — so that a missing receipt is a P35
blocker, not a P36 surprise.

### B-3. The A19/A20 "dictionary freeze at P35" procedure lacks a receipt requirement

Even with A-1 resolved, the P35 dictionary freeze (for A20, and for A19 if a redefined arm is
preregistered) should be required to record: the complete measured level list, per-season level
counts (the era-stability evidence — measured above, vocabulary identical across v2/v3), and the
explicit mapping of every level to {numerator, denominator-only}. Freezing "from the artifact's
data dictionary" without binding the measured bytes leaves the freeze unauditable. This is one
sentence in the P35 task card and closes the last discretionary gap in the F15 family.

---

## 3. Severity C findings (record)

* **C-1. Active-set rule registration step is missing from the pipeline plan.**
  `ACTIVE_SET_RULE_PREREGISTRATION.json` self-declares: "It is NOT registered for any arm. An arm
  that wishes to use it must register it in the arm registry before its own execution." A03, A12,
  A13, A14 (and A08's fallback if repaired) cite the rule; no P33 text schedules the arm-registry
  registration. P35 task cards should include it explicitly, or the rule's own status line makes
  every citation of it inoperative at execution time.
* **C-2. Fold-local constants have no final-model convention.** `m_bar` (A01/A04), `cbar_F`
  (A13), `Lbar_train` (A08) are training-fold statistics. If an arm promotes, the deployed model
  needs ONE value of each. This is promotion-protocol scope, not preregistration scope, but
  recording the convention now (e.g. full-archive value at promotion) costs one line and prevents
  a post-hoc choice later.
* **C-3. A16 deployment cost.** If A16 promotes, the daily pipeline must persist its own
  projections with receipts going forward (the frozen artifact ends 2026-07-31); the draft's
  backtest rule "joined from the frozen artifact bytes, not recomputed" has no deployment-side
  analogue. Deterministic recomputation from the frozen incumbent is possible but is exactly what
  the backtest rule prohibits; the convention should be stated at promotion time. Recorded as
  cost, not defect.
* **C-4. Partial-lineup rows are unhandled in A13/A22 set construction.** Measured in
  `possessions_raw_v2`: 64 possessions with null `off_p1` (n_off_oncourt = 0) and 217 with
  n_off_oncourt = 4. The Jaccard/usage constructions are defined over "player-id sets from
  off_p1..off_p5"; whether a partial or null lineup row contributes a smaller set, is skipped, or
  poisons the union is unspecified. 281 of 238,563 possessions (0.12%) — one sentence at P35.
* **C-5. A14's Holm-slot spend is operationally sound.** It burns a COLDSTART_FALLBACK element on
  a promotion-ineligible arm, deliberately, so the denominator is not quietly shrunk; the arm
  costs only schedule facts to fit. Deliberate, defended, cheap. No change requested.

---

## 4. What the draft gets RIGHT operationally (verified, not assumed)

* **Pre-tip availability is structurally sound for all 26 arms.** Every candidate column is a
  function of (i) the frozen incumbent's own pre-tip artifacts, (ii) pure schedule facts, or
  (iii) strictly-earlier-by-`game_date` lagged aggregates. Measured: **no team plays two games on
  one calendar date anywhere in the 2,982-row universe** (0 occurrences), so the strict-date lag
  operator gives the daily pipeline a full overnight window to ingest the previous night's PBP —
  no intra-day race exists in any arm. No arm uses tip times (P29 ruled them ineligible; the
  slate complies).
* **The transition-share construction (A17) is live and non-degenerate:** measured
  `duration_sec <= 8` share by season is 0.195–0.210, stable, on zero-null `duration_sec`.
* **Cold-start rules, where actually declared, are correct in form:** A18/A20/A26's E=3
  imputation, A12's dev_prev := 0, A22's churn := 0, A03/A14's 10-cluster floors, A05's numeric
  fold-2026 trigger (0 test playoff rows, measured by P33 and consistent with my read) are
  symmetric, deterministic, and stated before results. The A-2 arms should copy this pattern.
* **Expected failure modes are genuinely specific, not boilerplate.** Spot-checked all 26: most
  name a measured quantity and a decidable death (A01: the 0.869 R11 t19 slope vs bootstrap
  resolution; A03: 113 shallow rows vs the 37–42% S6 bias share; A07: the measured 0.958 R2
  against depth in train_lt_2022; A14: a wide interval on 46 clusters; A16/A26: P25 near-affinity
  as withdrawal-before-any-number). The weakest ("covered-zero interval", A18/A24) still carry
  preregistered interpretations or positive-control roles (A24's lag-operator control, A25's
  guard control — both operationally valuable). No change requested.

---

## 5. Contradictions found (document vs bytes)

1. **P32/P33 "|P| >= 1 by universe construction" vs the bytes:** false — 7 universe rows have
   zero strictly-earlier completed games (finding A-2). Root cause: `pace_resolved` is TRUE for
   league-prior-fallback rows, so universe membership never implied prior games.
2. **A16 "defined on all 2,982 rows in every fold" / "resolved universe already excludes the
   no-prior-games stratum" vs the bytes:** false — same 7 rows, plus 40 own-side rows whose
   5-game windows contain a NaN archived projection.
3. **A16 "carries projected_team_off_possessions … for all 2,990 team-games" vs the bytes:**
   the column is NaN on exactly 8 of 2,990 rows (the unresolved opening-day rows). Retrievability
   is real; completeness is overstated.
4. **A24 "cross-season prior game covers openers" vs the bytes:** false for the three franchise
   debuts and the four 2021-05-15 first-ever games.
5. **A08's element constraint vs the schedule facts:** both enumerated K violate it in all five
   training folds (finding A-3).
6. **A19's "fixed live-ball dictionary" vs the artifact vocabulary:** no live-ball distinction
   exists to freeze (finding A-1).

## 6. What I could NOT establish

* Whether the P32 SOURCE texts (upstream of the SPEC) define |P| = 0 behaviour for the w-weighted
  lag operator somewhere the SPEC failed to carry — I checked the P32 SPEC (the frozen input),
  which asserts "|P| >= 1 by universe construction"; the raw role-source files were not among my
  inputs. Immaterial: the frozen SPEC governs and is contradicted by the bytes either way.
* Whether a preseason-published schedule artifact exists OUTSIDE `experiments/player_program/`
  (A06 path (a)) — out of my read scope; inside scope, none exists (agrees with P33).
* Live daily-pipeline behaviour — no daily scoring run exists to observe in this worktree; all
  decision-time claims above are assessed against artifact structure and schedule facts, which is
  the strongest evidence available without fitting.
* The A04/A09 near-affinity numbers (d_t is P36 scope) — the frozen test itself is decidable and
  operationally clean; no objection.

## 7. Required changes (consolidated)

1. **(A-1)** Withdraw A19 now on the measured single-level `end_reason` vocabulary, or
   preregister the degraded `{turnover}` mechanism explicitly before P35 for review; record the
   LAGGED_TEMPO_MIX family consequence either way. Freeze A20's dictionary as `{turnover}` with
   the measured per-season counts attached.
2. **(A-2)** Preregister numeric, symmetric empty-history rules (or prospective unevaluability)
   for A09, A10, A11, A16, A17, A21, A24 covering the 7 zero-prior rows, A11's expansion-season
   `dprev_t`, and A16's NaN-projection windows — before P35, identical in arm and null.
3. **(A-3)** Give A08's window rule numeric content (trigger + action + row accounting) or
   withdraw A08; reconcile the element-admissibility constraint with the measured 36/154
   undefined-row counts.
4. **(B-1)** Freeze A06 path (b)'s definition text now, or strike path (b).
5. **(B-2)** Name the P23 franchise-continuity receipt as a hash-pinned P35 deliverable produced
   before fit dispatch.
6. **(B-3)** Require the P35 dictionary freeze to bind the measured level list and per-season
   counts as its receipt.
7. **(C-1)** Add the arm-registry registration of `S7_TIER_SUPPORT_v1` to the P35 task cards for
   every arm citing it.

Every measurement above is reproducible from the commands shown, run from
`experiments/player_program/` against the frozen artifacts
(`possessions_v2/possessions_raw_v2.parquet`, `possession_features.PRIOR_PARQUET =
team_possession_prior_v1.parquet`, `possession_features.load_universe()` /
`chronological_folds()`). No fit was run; no performance number exists in this review.
