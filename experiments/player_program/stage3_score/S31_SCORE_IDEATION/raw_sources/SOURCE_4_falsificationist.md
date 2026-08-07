# S31 IDEATION — SOURCE 4 — FALSIFICATIONIST / SURVIVAL DESIGNER

**Node:** `S31_SCORE_IDEATION` · **Source:** 4 of the cycle-2 ideation wave
**Sole input artifact:** `S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md` (frozen ideation edition) plus this source's own prompt. No other file was read.
**Lens:** propose only candidates judged most likely to SURVIVE a preregistered per-element gate with family-Holm correction against a K0 that already carries the public composite's frozen ingredients as null-granted terms.

---

## 0. Survival economics — why this list is short

The gate this cycle is harsher than an intercept-null gate in three compounding ways, and every
candidate below was chosen against all three simultaneously:

1. **The null already knows the composite.** K0_MATCHED carries the public composite's exact
   ingredient columns (byte-pinned) as fitted null-granted terms (§4). Any candidate whose
   "signal" is a re-expression, smoothing, rescaling, or linear recombination of
   pace-times-efficiency team strength contributes **zero expected Δ** — the null's own fitted
   coefficients absorb it, and the fold-wise refitted intercept absorbs slow global drift.
   Surviving candidates must carry information that is (a) genuinely absent from the ingredient
   columns, or (b) a *nonlinear* transform of them the linear null cannot represent.
2. **Multiplicity is priced per element.** Every (arm, estimand) registration is an element
   inside the mechanism family's Holm correction (§4). Registering an arm on an estimand where
   its magnitude is marginal does not add a lottery ticket — it *raises the bar for the
   estimand where the arm is actually strong*. Each candidate below therefore registers the
   **minimum estimand set** where its predicted effect is largest, and explicitly declines the
   others.
3. **The prior cycle swept nulls against a strong incumbent.** The machinery kills
   plausible-but-weak ideas efficiently. So each candidate carries an explicit
   detectability argument: predicted pooled Δ against the approximate standard error of a
   paired, game-clustered ΔMAE/ΔBrier at N ≈ 1,491 clusters. Rule of thumb used throughout:
   paired per-game metric differences that are exactly zero on unaffected games and modest on
   an affected subset have small paired-difference dispersion, so pooled ΔMAE of order
   +0.04–0.10 points is plausibly separable from zero at these N — but only when the affected
   subset is not tiny and the sign is theoretically pinned in advance.

Four candidates. Not padded to six. Each is a **1-fitted-parameter** addition to the
null-granted design (df discipline: the null's coefficients are refit identically in arm and
K0; each arm adds exactly one substantive coefficient, so the arm-vs-null comparison is a
single-degree-of-freedom test with maximal power per element). All four use the cycle-1
containment reading (arm = null-granted terms + treatment), so the cannot-host path is never
invoked and no below-floor label is ever risked.

**Identification constraint (generic-form bullet, §7):** every candidate below is a single
linear coefficient on a fully pinned, pre-computable feature. No scale or identification
indeterminacy exists in any of them; each card will state this affirmatively.

**Covariance obligation (§5):** none of these arms forecasts the two sides separately or
aggregates player→team→game. All are direct game-level designs on the margin/total/win
response. This is a deliberate survival choice: it keeps the `bottomup_3pt_channel_v1`
covariance obligation out of scope and removes an entire class of kill surface.

---

## Candidate 1 — `SEASON_CARRYOVER_PRIOR` (ranked first on magnitude)

**Mechanism.** Early in a season, any within-season strength estimate is noise-dominated;
last season's terminal team strength, shrunk toward league mean, is a materially better
predictor of this season's early games. If the composite's frozen ingredient columns are
within-season constructions (or re-initialize weakly across seasons), the null is
systematically miscalibrated on the early-season subset, and a carryover term corrects it
*by several points of predicted margin on the affected games*.

**Why the magnitude survives multiplicity.** This is the largest honest effect available
under §8's bars. Roughly 20–30% of a season's games occur before both teams have ~10 prior
games; on that subset, the gap between a noise-dominated within-season rating and a shrunk
prior-season rating is commonly 2–4 points of predicted margin per game for teams whose
quality persisted (and WNBA quality is strongly persistent season-over-season at the team
level — roster continuity is high outside expansion). A 2–4 point correction on 20–25% of
games that moves MAE on that subset by 0.3–0.8 points implies pooled ΔMAE(E2) of order
**+0.08 to +0.20** — comfortably the largest predicted Δ in this document and the one most
likely to clear Holm even as the least-favored element in its family. The same logic applies
to the total (early-season scoring-environment carryover) at somewhat smaller magnitude.

**Conditionality is the point.** If the composite ingredients already encode cross-season
carryover, this arm dies — cleanly, cheaply, and informatively. That is an acceptable and
*designed* outcome under this lens: the arm is a falsifiable claim about a specific,
checkable deficiency of the public floor, not a hopeful feature.

**Information consumed (all strictly lagged, cutoff-valid, §8-compliant).**
* Prior-season settled team scores/opponent scores from owned committed data (strictly prior
  games only; prior-season data is trivially pregame for every current-season game).
* Current-season strictly-prior game count per team, `n_prior(team, t)` — derivable from
  as-of-cutoff schedule identity plus which prior games are settled.
* No market fields, no injury/lineup fields, no same-game anything.

**Functional form (1 fitted parameter per registered estimand).**
* `carry(team)` = prior-season mean net rating (per-game point differential), shrunk toward 0
  by a **pinned** factor λ = 0.5 (chosen a priori from the general season-to-season
  persistence range; pinned, not fitted). Expansion teams (no prior season): `carry = 0`
  (exact league mean) — full coverage, no predicate.
* Fade weight `g(n) = max(0, 1 − n/K)`, K **pinned** at 10 games, `n` = min of the two teams'
  strictly-prior current-season game counts.
* E2 arm: null-granted design + β·`g(n)·(carry_home − carry_away)`. One fitted β.
* E1 arm: same with `carry_total(team)` = prior-season mean (pts + opp_pts)/2 deviation from
  league mean, feature `g(n)·(carry_total_home + carry_total_away)`. One fitted β.

**Estimands registered:** **E2 and E1** (two elements). E3 is deliberately NOT registered:
the E3 gain is a derivative of the E2 gain, and adding it as a third element buys Holm burden
without independent magnitude. Predicted honest magnitudes: ΔMAE(E2) ≈ +0.08 to +0.20 pooled;
ΔMAE(E1) ≈ +0.05 to +0.12 pooled.

**Expected failure mode.** The composite ingredients turn out to carry cross-season
initialization (or EWMAs with long memory spanning the offseason), so the early-season
deficiency the arm targets does not exist and β ≈ 0.

**Pre-committed kill conditions (each diagnostic a receipted sealed-run output).**
* K-A: pooled Δ ≤ 0 on the early subset `n < 10` (receipt: subset ΔMAE table with clustered
  CI, both estimands). The mechanism lives *only* there; a pooled pass driven by the
  late-season complement is a spurious pass and the arm dies regardless of the pooled number.
* K-B: fitted β ≤ 0 (wrong sign) in the pooled fit or in ≥ 3 of 5 folds (receipt: per-fold
  coefficient table with B=2,000 train-refit CIs).
* K-C: Δ concentrated in a single season — dropping any one season's test games from the
  season-split receipt flips the pooled early-subset Δ to ≤ 0 (receipt: leave-one-season-out
  Δ table). Guards against a 2021-only or expansion-cohort-only artifact.

**Coverage vs §2 floors.** Predicate: none — full 1,491-cluster base universe (100% pooled,
100% per fold; floors ≥90/≥80 trivially met). Expansion-team fallback (`carry = 0`) is the
card-declared `fallback_rules` dimension, so the mandatory all-covered-games sensitivity row
is identical to the gated row.

---

## Candidate 2 — `SCHED_FATIGUE_DIFF` (schedule density and travel, acting on scoring)

**Mechanism.** A team playing on zero days' rest, or its third game in four days, or after a
multi-time-zone trip, scores less than its strength rating implies. The contract's cycle-1
nulls clause explicitly anticipates this shape: rest/schedule context **acting on scoring**,
not on pace mechanisms in the cycle-1 forms — this arm touches no pace construction and
consumes the verified pace ingredient only insofar as the null-granted composite terms do.

**Why the magnitude survives multiplicity.** Fatigue is one of the very few well-replicated
external effects on basketball scoring margin (order 1–2 points for back-to-backs in
professional play), and — critically for this gate — **schedule density is absent from
pace×efficiency strength composites**, so the null cannot absorb it. WNBA schedule congestion
is substantial (compressed seasons, Commissioner's Cup, pre-2024 commercial travel), so
back-to-back and 3-in-4 exposure plausibly covers 15–30% of team-games. A ~1-point margin
correction on the fatigue-asymmetric subset (asymmetry is what moves the margin) implies
pooled ΔMAE(E2) of order **+0.03 to +0.08** and ΔBrier(E3) of order **+0.001 to +0.003**.
That is detectable-but-not-comfortable at N ≈ 1,491: the sign pin and 1-df design are doing
real work here, which is exactly why the index weights are pinned rather than fitted.

**Information consumed (all strictly lagged, cutoff-valid).**
* As-of-cutoff scheduled dates of each team's strictly-prior games and the current game's
  scheduled date (schedule identity columns — the closed §1 enumerated set; valued
  as-of-cutoff, never as-played, so a postponement-updated date never enters).
* Static arena locations/time zones (immutable metadata, trivially cutoff-valid).
* Prior games' realized dates are lagged facts and admissible per §1's explicit carve-out.

**Functional form (1 fitted parameter).**
* Pinned fatigue index per team:
  `F = 1.0·1[back-to-back] + 0.5·1[3rd game in 4 days] + 0.25·(time zones crossed since previous game, capped at 3)`.
  All index weights **pinned a priori**; zero fitted parameters inside the index.
* E2 arm: null-granted design + β·(F_home − F_away). One fitted β, expected negative on the
  fatigued side (i.e., β < 0 for F_home − F_away raising home fatigue).
* E3 arm: identical feature in the declared E3 link. One fitted β.

**Estimands registered:** **E2 and E3** (two elements). E1 is deliberately NOT registered:
the total-side effect (both teams tired → slightly fewer points) is second-order relative to
the differential effect and would be a weak element dragging the family.

**Expected failure mode.** WNBA effect size is smaller than the professional-basketball
consensus (shorter travel legs post-2024 charter era; rotations less minutes-concentrated),
leaving pooled Δ inside noise; or the effect exists but the composite's EWMA partially
launders recent fatigue through depressed recent scoring, shrinking the orthogonal component.

**Pre-committed kill conditions (receipted).**
* K-A: fitted β has the wrong sign pooled, or wrong sign in ≥ 3 of 5 folds (receipt:
  per-fold coefficient table with CIs).
* K-B: Δ on the affected subset (|F_home − F_away| ≥ 1) is ≤ 0 (receipt: subset ΔMAE/ΔBrier
  table with clustered CI). The mechanism claims its gain *there*; a pass without subset
  improvement is spurious.
* K-C: era instability — the sign of the subset Δ differs between the pre-2024 and 2024+
  season splits AND the pooled Δ depends on the pre-2024 split alone (receipt: era-split
  table). Guards against betting on a travel regime that no longer exists.

**Coverage vs §2 floors.** Predicate: none — season openers get F computed with
"previous game" undefined → F = 0 (max rest), a card-declared convention, not a row drop.
100% pooled / 100% per fold.

---

## Candidate 3 — `HCA_DRIFT` (time-varying home-court advantage, strictly lagged)

**Mechanism.** Home-court advantage is not a constant. The 2021 attendance-restricted season,
the return of full arenas, and secular league changes moved league-wide HCA by plausibly
1–2 points across 2021–2026. A constant (per-fold-refit) intercept — which is all the
null-granted design offers — tracks this only at fold granularity. A strictly-lagged
league-wide HCA estimate tracks it within-fold and within-season.

**Why the magnitude might survive — stated honestly, this is the marginal pick.** The effect
touches **every game** (no small-subset dilution), which is its power advantage: even a
±0.5-point average correction applied universe-wide can produce pooled ΔMAE(E2) of order
+0.04–0.10. But the expanding-fold refit of the null's intercept absorbs the low-frequency
component, so the arm's true target is only the *residual within-fold drift*. I rank it
third of four and register it narrowly.

**Information consumed.** League-wide settled home-minus-away margins of strictly-prior
games only (owned committed data), plus home/away designation (schedule identity).

**Functional form (1 fitted parameter).**
* `HCA_lag(t)` = EWMA over the league's strictly-prior games of (home pts − away pts), pinned
  halflife of 60 league games, initialized at the training-era mean of the earliest fold's
  train years. Zero fitted parameters inside the construction.
* E2 arm: null-granted design + β·(HCA_lag(t) − HCA_train_mean), centered so the intercept
  keeps its meaning. One fitted β; predicted β ∈ (0, 1.5], honest point expectation ≈ 1.

**Estimands registered:** **E2 only** (one element). E3's Brier gain from a sub-point HCA
correction is too small to justify an element; E1 is untouched by a margin-side mechanism.
Predicted honest magnitude: ΔMAE(E2) ≈ +0.03 to +0.08 pooled.

**Expected failure mode.** Fold-level intercept refit plus any era-adaptivity already inside
the composite ingredients absorbs nearly all the drift; the residual within-fold signal is a
fraction of a point and drowns.

**Pre-committed kill conditions (receipted).**
* K-A: β's pooled CI covers 0 AND covers 0 in ≥ 4 of 5 folds (receipt: coefficient table).
* K-B: leave-one-season-out receipt shows the pooled Δ depends entirely on the 2021 test
  split (receipt: leave-one-season-out Δ table). If this is a COVID-reopening story only, it
  is not a mechanism, it is one historical event — kill.
* K-C: the fitted β > 1.5 or < 0 (receipt: pooled coefficient) — outside the mechanically
  sensible range for a partially-absorbed drift term, indicating the term is proxying
  something else (specification leak), kill.

**Coverage vs §2 floors.** Predicate: none. 100% pooled / 100% per fold; the EWMA is defined
from the first universe game via its pinned initialization.

---

## Candidate 4 — `FAV_GAP_COMPRESSION` (nonlinearity the linear null cannot represent)

**Mechanism.** Realized margins compress relative to a linear function of strength gap when
the gap is large (leads produce bench minutes and slack effort — "garbage time" flattens the
tail). The null is linear in its granted ingredient columns by construction; a concave
transform of the null's own implied gap is information-free but **representation-rich**: it
adds exactly the one shape the linear null cannot express. This is the purest test in this
document of "the null knows the ingredients but not the geometry."

**Why it might survive.** WNBA 2021–2026 contains a heavy tail of mismatched games (expansion
seasons and multi-year rebuilds), so the |gap| > 8 subset is plausibly 15–25% of the
universe. A ~10% compression of the excess gap on those games is a 0.3–0.6 point correction
there, implying pooled ΔMAE(E2) ≈ **+0.02 to +0.06** — the smallest predicted Δ here, which
is why it is ranked last and registered on a single element. Its survival case rests on the
tight 1-df design and the pinned sign, not on raw magnitude. If the family ends up crowded,
this is the candidate to cut first, and I say so now so the cut is principled rather than
post hoc.

**Information consumed.** Nothing beyond the null-granted ingredient columns themselves
(cutoff-valid by inheritance): the feature is a deterministic transform of the null's own
design row. No new data enters; no new leakage surface opens.

**Functional form (1 fitted parameter).**
* Let `ĝ` = the strength-gap linear index formed from the null-granted ingredient columns
  with **train-fold-fitted null coefficients** (i.e., the K0's own fitted margin prediction,
  computed under the identical expanding-fold protocol — no test information enters).
* Feature: `h(ĝ) = sign(ĝ)·max(0, |ĝ| − 8)` with the knee **pinned** at 8 points.
* E2 arm: null-granted design + γ·h(ĝ). One fitted γ, predicted **negative** (compression),
  honest expectation γ ≈ −0.10 to −0.25.

**Estimands registered:** **E2 only** (one element).

**Expected failure mode.** WNBA blowout compression is weaker than assumed, or the settled
(OT-inclusive) margin's tail behavior differs from the intuition (OT only occurs in near-tie
games, so it cannot rescue this tail mechanism); γ lands near 0.

**Pre-committed kill conditions (receipted).**
* K-A: fitted γ ≥ 0 pooled (receipt: coefficient table). Wrong sign = dead, no re-spec.
* K-B: Δ on the |ĝ| > 8 subset ≤ 0 (receipt: subset ΔMAE table with clustered CI); the
  mechanism has no claim anywhere else.
* K-C: the |ĝ| > 8 subset is < 10% of pooled test clusters (receipt: subset count in the
  adjudication report) — the mechanism's habitat is too small for its magnitude claim to
  have been honest; kill rather than reinterpret.

**Coverage vs §2 floors.** Predicate: none. 100% pooled / 100% per fold.

---

## Considered and rejected (so the short list is legible as a choice, not an oversight)

* **Injury/availability/lineup anything** — barred outright this cycle (§8, D048/D034); the
  point-in-time store cannot cover 2021–2026. Not proposed in any laundered form.
* **Market-derived features or market-informed coverage predicates** — barred (§8, P2B).
* **Player→team→game bottom-up aggregation** — cycle-3 territory (§10), and it triggers the
  §5 covariance obligation, a proven graveyard per the cited precedent. Zero candidates here
  split sides.
* **Pace interactions / possession-count refinements** (e.g., nonlinear pace matchup terms) —
  the null-granted composite already carries the verified pace ingredient's information; the
  orthogonal remainder is small, and anything schedule-flavored risks the cycle-1 pace-forms
  retry bound. Dominated by the four above on expected Δ per element.
* **E3-only recalibration arms** (heavier-tailed margin→probability maps, p-shrinkage) — the
  E3 K0 fits its own link on the same ingredients with declared clipping (§4); the residual
  calibration gap is second-order and unlikely to clear Holm. The 10-bin calibration table is
  already a receipted secondary output, which is the right home for this question.
* **Padding elements** — registering every arm on all three estimands. Rejected on the §4
  multiplicity pin: cross-estimand claims require corrected passes on *each* estimand, and
  weak elements tax strong ones inside the family. Total elements proposed here: **6**
  (C1×2, C2×2, C3×1, C4×1) across four mechanism families.

## Summary table

| rank | arm | estimands (elements) | fitted df | predicted pooled Δ (honest) | coverage |
|---|---|---|---|---|---|
| 1 | `SEASON_CARRYOVER_PRIOR` | E2, E1 (2) | 1 per element | ΔMAE(E2) +0.08–0.20; ΔMAE(E1) +0.05–0.12 | 100% / 100% per fold |
| 2 | `SCHED_FATIGUE_DIFF` | E2, E3 (2) | 1 per element | ΔMAE(E2) +0.03–0.08; ΔBrier(E3) +0.001–0.003 | 100% / 100% per fold |
| 3 | `HCA_DRIFT` | E2 (1) | 1 | ΔMAE(E2) +0.03–0.08 | 100% / 100% per fold |
| 4 | `FAV_GAP_COMPRESSION` | E2 (1) | 1 | ΔMAE(E2) +0.02–0.06 | 100% / 100% per fold |

Every arm: containment nesting (arm = null-granted terms + one treatment), no coverage
predicate (floors met trivially, sensitivity row ≡ gated row), no side-splitting (no §5
covariance obligation), no identification indeterminacy, all features strictly lagged and
computable from settled prior scores + as-of-cutoff schedule identity + static venue
metadata, and every kill diagnostic named above is a receipted sealed-run output per gate
clause (c).

*— Source 4, falsificationist / survival designer. Written against the frozen IDEATION
EDITION only; no floor values, no D045/D046/D047 content, no other source's output was seen.*
