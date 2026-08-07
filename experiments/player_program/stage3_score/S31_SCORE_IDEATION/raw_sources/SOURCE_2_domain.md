# S31 SCORE IDEATION — SOURCE 2 (BASKETBALL DOMAIN ANALYST: game mechanisms)

**Input artifact:** `CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md` (frozen, sole file read).
**Lens:** how WNBA basketball physically generates points — possessions, shot profiles,
matchup styles, rotations, season arcs, venue, fatigue.
**Isolation attestation:** this document was produced from the ideation edition and the
source prompt only. No other file, directory, ledger, or artifact was read. No floor or
market-bar values are known to this source beyond the contract's statement that they exist.

All candidates below respect §8 (pregame strictly-lagged only; market-odds fields
inadmissible as features and coverage inputs; injury/lineup/availability barred absent
witnessed point-in-time provenance, which does not exist for 2021–2026), §7's conditional
null bound (any rest/schedule/home-context candidate acts on **scoring**, never on pace
mechanisms in the cycle-1 forms), and §1's overtime discipline (no same-game realized
anything; schedule identity valued as-of-cutoff). Where a candidate would want a field from
F13's 37 CUTOFF_UNPROVEN inventory, that dependency is stated explicitly and the candidate
is written to degrade gracefully to owned possession/score data if S37 promotion fails.

---

## C2-1 · Pace–Efficiency Multiplicative Recombination ("points = possessions × efficiency")

**Basketball story.** A basketball score is not a primitive; it is the product of two
processes with different persistence. Possessions (pace) are highly stable team habits set
by coaching philosophy and roster speed; points-per-possession (efficiency) is noisier but
mean-reverts differently for offense and defense. Smoothing final scores directly conflates
the two and inherits the worse persistence of each. The program already owns a verified,
frozen pace projection; the domain claim is that recombining it multiplicatively with
separately-smoothed offensive and defensive efficiency estimates predicts totals better
than any direct smoothing of points, because each factor is estimated at its own natural
timescale.

**Information consumed (all strictly lagged, cutoff-valid).**
- `team_possession_prior_v1.projected_team_off_possessions` (verified ingredient, §8) for
  both teams — note it is declared **regulation-equivalent** while the estimand is
  **full-game settled**; see the OT bridge term below.
- Strictly-prior points and opponent points per game (owned `master_team` lineage) divided
  by strictly-prior possession counts (owned possession artifacts) → lagged off/def
  points-per-possession EWMAs per team.
- Historical (strictly prior) league OT frequency and mean OT points added, as a lagged
  league-level bridge from regulation-equivalent expectation to full-game settled
  expectation. This is the §1-sanctioned "legitimately pregame construction" — historical
  OT rates, never current-game OT.

**Functional form sketch.**
E1: `T̂ = Σ_sides [ p̂oss_side × (α·offPPP_side + (1−α)·defPPP_opp + λ_lg) ] × (1 + κ·OTrate_lag)`
where offPPP/defPPP are EWMA-shrunk toward the lagged league mean, α blends offense vs
opposing defense, and κ·OTrate is the league OT bridge. E2 from the side difference plus a
home term; E3 via a link on E2's mean and a train-years dispersion estimate.

**Estimands helped.** E1 primarily (level accuracy from correct pace × efficiency
factorization); E2 secondarily (side decomposition); E3 through E2.

**Expected failure mode, honestly.** WNBA seasons are ~40 games; efficiency EWMAs are noisy
and the multiplicative form **amplifies** pace error into total error rather than averaging
it out. If the frozen pace projection's error correlates with efficiency error (fast teams
misestimated in both), the product is worse than the sum of parts. Also this is the most
obvious candidate in the space — its marginal value over a null that already carries the
public composite's ingredients (§4 null-strength floor) may be near zero, since the
composite is plausibly built from similar material.

**Kill conditions (receipted).**
1. Pooled OOF ΔMAE(E1) vs K0_MATCHED ≤ 0 **and** the receipted error-decomposition table
   (a sealed output: per-game pace-error × efficiency-error cross term) shows the
   multiplicative cross-term contributing ≥ 25% of squared error — the factorization is
   then structurally harming, not just underpowered. Kill evaluated uncorrected.
2. Bootstrap CI (game-clustered, B=10,000) on ΔMAE(E1) covers 0 with point estimate < 0.15
   points in every one of the five folds' receipted per-fold rows.

**Coverage vs §2 floors.** EWMAs need ≥ N strictly-prior games. With N=3 both-teams and a
card-declared fallback to lagged league means for earlier games, the predicate is
information-based and should clear 90% pooled / 80% per fold comfortably (only the first
~2 weeks of each season are affected; the fallback keeps those games covered rather than
trimmed). Mandatory all-covered sensitivity row runs on the fallback.

---

## C2-2 · Opponent-Adjusted Off/Def Strength Ratings (ridge bilinear, sum-to-zero identified)

**Basketball story.** In a 12–14 team league with unbalanced early schedules and 4–5 games
against each opponent, raw per-team averages are badly contaminated by strength of
schedule: a team that opened against the league's two best defenses looks offensively
broken when it is merely schedule-unlucky. Basketball scoring is an interaction — my
offense against *your* defense — so a jointly-estimated rating system (each game's side
score modeled as off_i − def_j + home term, ridge-shrunk, fit only on strictly-prior games
at each cutoff) recovers the true strengths a simple EWMA cannot, and does so fastest
exactly where the schedule is most unbalanced (early season, expansion entries).

**Information consumed.** Strictly-prior game results only (side points, possessions,
opponent identity, home/away, season) from owned committed data. Nothing else. Fully
cutoff-valid by construction; refit at every fold cutoff and, within test folds, using only
games strictly prior to each predicted game's cutoff.

**Functional form sketch.**
Per side: `pts_ij = μ_lg + off_i − def_j + h·home_ij + ε`, ridge penalty on (off, def),
**identification constraint registered explicitly per §7: Σ off_i = Σ def_i = 0** (the
scale indeterminacy between off and def levels is absorbed by μ_lg). Optionally per-100-poss
scale using owned possession counts, recombined with the verified pace ingredient as in
C2-1. E2 = (off_h − def_a) − (off_a − def_h) + h; E1 = sum; E3 via probit on E2 mean over
train-years margin sd.

**Estimands helped.** E2 and E3 most (margin is exactly the strength difference; schedule
adjustment is a pure margin play); E1 modestly.

**Expected failure mode.** Ratings and shrunk EWMAs converge to nearly the same numbers by
mid-season, so the edge lives only in ~the first 10–12 games per season — a small slice of
the pooled metric; the pooled gate may not resolve it. Ridge λ chosen on train years can
over-shrink for expansion-team seasons where the prior is genuinely wrong.

**Kill conditions (receipted).**
1. The receipted season-split secondary table (mandated reported secondary, §4) shows
   ΔMAE(E2) vs K0_MATCHED ≤ 0 in the early-season stratum (each team ≤ 12 prior games,
   stratum defined information-based in the card) — the mechanism's only theorized locus
   failing kills it regardless of pooled noise.
2. Receipted coefficient-interval output (train-refit bootstrap, B=2,000): if the ridge-path
   receipt shows the fitted λ at the grid boundary (maximal shrinkage) in ≥ 4 of 5 folds,
   the model is collapsing to the league mean and the arm is dead machinery.

**Coverage.** Needs each team ≥ 1 strictly-prior game in the rating window plus a declared
expansion-team prior (league-mean rating, card-declared). Retains effectively 100% of
clusters with the fallback; floors are safe.

---

## C2-3 · Garbage-Time-Robust Efficiency (leverage-capped lagged inputs)

**Basketball story.** WNBA blowouts end with benches emptied: starters sit, defensive
intensity vanishes, and the last 6–8 minutes of a 25-point game generate points-per-
possession numbers that say nothing about either team's next game. Every lagged efficiency
input built from raw final scores inherits this contamination. A margin-capped (winsorized)
or possession-leverage-weighted version of the *same* lagged efficiency EWMAs should be a
strictly better forward-looking signal — same data, cleaned of the possessions that carry
no forward information. This is an input-hygiene mechanism: it upgrades whatever efficiency
terms other arms (or the null's granted ingredients) consume.

**Information consumed.** Strictly-prior game scores and possessions (owned). The cap is
applied to **prior** games' contributions only (e.g., a prior game's margin contribution
winsorized at ±15 before entering the EWMA). If play-by-play–derived garbage-time
possession flags exist in the F13 inventory they are almost certainly CUTOFF_UNPROVEN;
the candidate is therefore specified on **final-score winsorization only**, needing no S37
promotion; a PBP-leverage refinement is a labeled optional upgrade contingent on S37.

**Functional form sketch.** Identical pipeline to C2-1/C2-2 with each prior game g's inputs
transformed: `margin_g* = clip(margin_g, −c, +c)`, and side points reconstructed
consistently (`pts* = pts − max(0,(|margin|−c))/2 · sign adjustments`), c ∈ small
card-declared grid frozen before fit. The treatment is the transform; the arm nests its K0
(null-granted ingredients uncapped).

**Estimands helped.** E2 (margin prediction is what blowout noise pollutes most) and E3;
E1 mildly (totals in blowouts are distorted in both directions and partially cancel).

**Expected failure mode.** The margin-of-victory literature's honest warning: big margins
carry real signal — dominant teams are genuinely dominant — and capping throws away truth
along with noise. Net effect may be a wash, or the optimal c may sit so high it changes
almost nothing (an epsilon-arm). WNBA blowout frequency may also be too low for the
transform to touch enough prior games to matter.

**Kill conditions (receipted).**
1. Receipted transform-incidence table (sealed output: count and share of prior-game inputs
   actually clipped per fold): if < 8% of input games are touched at the frozen c, the arm
   is declared inert and killed regardless of Δ sign (an uncheckable-by-construction
   improvement is a card defect; this makes inertness checkable).
2. Pooled OOF ΔMAE(E2) ≤ 0 with the game-clustered bootstrap CI upper bound < +0.10 points.

**Coverage.** Identical universe to its base pipeline; no additional trimming; floors
unaffected.

---

## C2-4 · Rest & Travel Fatigue Acting on Scoring Efficiency (charter-era interacted)

**Basketball story.** Fatigue in basketball shows up first in the legs: contested-shot
quality, defensive rotation speed, and free-throw legs late in games. The WNBA schedule is
uniquely condensed (40 games in ~14 weeks, Commissioner's Cup congestion, a mid-season
Olympic/All-Star break) and, until the 2024 charter-flight program, travel was commercial —
a mechanism no NBA-trained prior calibrates correctly. Back-to-backs, 3-games-in-4-days,
and long travel legs should depress a team's *scoring efficiency* (and slightly inflate the
opponent's), asymmetrically when one side is rested and one is not. **Per the contract's
conditional null bound, this candidate acts on scoring (points-per-possession terms) only;
it does not touch pace mechanisms in any cycle-1 form.**

**Information consumed.** Entirely from schedule identity valued as-of-cutoff (§1's closed
column set): scheduled game dates → rest-day counts and k-in-n density; home/away
designation + opponent identity → venue city sequence → great-circle travel distance and
time-zone crossings since last game, computed from a frozen static arena-location table
(static reference data, not game data). Season label → charter-era interaction (pre/post
2024). No injury, no lineup, no market. A postponement-updated date is as-played
information; the card consumes the as-of-cutoff scheduled date per §1's precedent.

**Functional form sketch.** Additive efficiency adjustments on top of a C2-1-style base:
`ppp_side += β1·B2B + β2·threeIn4 + β3·log(1+km_traveled)·1[tzΔ≥2] + interactions with
season≥2024 (charter) and restDiff = rest_home − rest_away` entering E2 directly.
Coefficients ridge-shrunk; grid frozen at card time.

**Estimands helped.** E2 and E3 via the rest *differential* (a rested home team vs a
back-to-back road team is the cleanest fatigue bet basketball offers); E1 via the sum
(two tired teams → lower total, though offense and defense fatigue partially offset —
domain honesty: fatigue hurts defense too, so the E1 sign is genuinely uncertain and the
card should not pretend otherwise).

**Expected failure mode.** Three ways. (i) Effects are real but tiny (~1 point) and drown
in a 14-point-sd margin. (ii) The charter era (2024+) attenuates the travel term to zero,
leaving only rest density — and 2021's COVID-condensed idiosyncrasies as leverage points.
(iii) Rest correlates with schedule placement quality, partially absorbed by opponent
adjustment, leaving less unique signal than the raw correlation suggests.

**Kill conditions (receipted).**
1. Receipted coefficient table with bootstrap intervals: if the sign of the rest-differential
   coefficient on E2 flips across ≥ 2 of 5 folds' train-refit receipts, the mechanism is
   unstable noise — kill.
2. Pooled OOF ΔBrier(E3) ≤ 0 **and** the receipted season-split table shows no fold with
   ΔMAE(E2) > 0 whose CI excludes zero.

**Coverage.** Schedule identity exists for every cluster; rest features are defined from
each team's first game of season onward (first game gets a card-declared "season opener"
level). 100% coverage; floors trivially met.

---

## C2-5 · Team-Specific, Time-Drifting Home Advantage (shrunk HCA field)

**Basketball story.** Home advantage is treated as a league constant, but its basketball
causes — crowd-driven officiating pressure, rim familiarity and depth perception in
dedicated vs shared/converted arenas, travel landing on the visitor — vary by franchise and
by era. 2021 games ran under attendance restrictions (a materially weaker crowd mechanism);
several franchises changed arenas across 2021–2026; expansion teams open in new buildings
with unusually loud crowds. A team-and-season-varying home effect, estimated from each
team's strictly-prior home/away scoring splits and shrunk hard toward the lagged league
mean, should beat any constant-h term for margin and win probability.

**Information consumed.** Strictly-prior home and away side scores per team (owned data),
home/away designation and season from the schedule-identity set, all as-of-cutoff. The
league-level component is itself estimated only from strictly-prior games (so 2021's
depressed HCA is *learned* by mid-2021, not assumed).

**Functional form sketch.** Hierarchical: `h_team,t = μ_h,lg(t) + δ_team,t` with
`μ_h,lg(t)` a lagged league EWMA of home-minus-away margin and δ shrunk by an
empirical-Bayes factor toward 0 given each team's prior home/away sample. Enters E2
additively and E3 through the link; E1 receives only the (small) total-side component of
HCA, reported but not the point of the arm.

**Estimands helped.** E2 and E3 directly — this is purely a margin/win-prob mechanism.

**Expected failure mode.** The honest one: decades of basketball analytics suggest
team-specific HCA is mostly noise at feasible sample sizes; with ~20 home games per team
per season the empirical-Bayes shrinkage may (correctly) collapse every δ to ~0, leaving
only the league drift term — which the null may effectively already carry. The arm then
survives or dies on whether the *time-varying league* component alone beats a constant.

**Kill conditions (receipted).**
1. Receipted shrinkage report (sealed output: distribution of |δ_team| after shrinkage per
   fold): if the 90th-percentile shrunk |δ| < 0.5 points in every fold **and** pooled
   ΔMAE(E2) CI covers zero, the team-specific component is declared empty and the arm is
   killed (its residue, league drift, is not the registered mechanism).
2. ΔBrier(E3) ≤ 0 pooled OOF vs K0_MATCHED.

**Coverage.** Defined for all clusters (early-season teams fall back to the shrunk league
mean — information-based fallback). Floors met at 100%.

---

## C2-6 · Cross-Season Carryover Decay with Roster-Free Continuity (learned season-boundary discount)

**Basketball story.** Every lagged-strength mechanism above must decide what a team's 2024
rating says about its 2025 opener. In the WNBA the honest answer is "less than you think":
rosters churn hard (core contracts, overseas commitments, a compressed draft-to-opener
window), coaching turnover is frequent, and the league is actively expanding (new
franchises entering with no history at all). Rather than importing an injury/roster store
(barred, §8), the decay itself is *learnable from owned score data*: fit, on strictly-prior
seasons only, how much predictive weight last season's ratings deserve at game n of the new
season, and apply that learned decay curve going forward. Expansion teams get an explicit
league-conditional prior (historical first-season expansion performance is itself lagged
data once ≥ 1 expansion season is strictly prior).

**Information consumed.** Only owned prior-season and current-season results plus season
labels and team identity (schedule-identity set). The decay parameter is estimated on
train-years only (a matched-dimension declaration in the card, mirroring §5's
train-years-only dispersion discipline). No roster, transaction, or availability data of
any kind.

**Functional form sketch.** Prior for team i at game n of season t:
`rating_i,t,n = w(n)·rating_i,t−1,final + (1−w(n))·rating_i,t,within-season`, with
`w(n) = w0·exp(−n/τ)`; (w0, τ) fit on strictly-prior seasons' one-step-ahead score errors.
Expansion teams: `rating = lagged mean of historical expansion first-k-game performance`
(defined only when ≥ 1 expansion season is strictly prior; else lagged league minimum
quartile, card-declared). Wraps around C2-1 or C2-2 as their initialization layer.

**Estimands helped.** All three, concentrated in the early-season stratum — exactly where
C2-2 predicted its own weakness, making this its natural complement. E3 especially: badly
initialized ratings produce confidently wrong early-season win probabilities, and Brier
punishes confident wrongness quadratically.

**Expected failure mode.** Only five season boundaries exist in-universe, and the folds
consume them progressively — (w0, τ) is fit on as few as one or two boundaries in early
folds, so the "learned" decay may be an anecdote wearing a functional form. The expansion
prior is honest but nearly unfalsifiable in-sample (very few expansion team-seasons).

**Kill conditions (receipted).**
1. Receipted (w0, τ) per-fold estimates with train-refit bootstrap intervals: if the τ
   interval spans more than one order of magnitude in ≥ 3 of 5 folds, the decay is
   unidentified — kill, do not promote an anecdote.
2. Receipted early-season stratum row (games with team-season game-number ≤ 8): pooled
   ΔMAE(E2) in-stratum ≤ 0 → kill (the mechanism has no other theorized locus).

**Coverage.** This candidate **adds** coverage robustness: it gives principled predictions
for exactly the low-history games that minimum-prior-games predicates would trim, letting
sibling arms keep predicates loose and clear the 90/80 floors without concentrated
early-fold trimming (the exploit §2's per-fold floor exists to block). It should be offered
to other arms as the standard card-declared fallback.

---

## C2-7 · Style-Matchup Margin Dispersion (variance model feeding E3 and the distributional endpoints)

**Basketball story.** Two games with the same expected margin are not the same bet. A
matchup between two three-point-reliant, high-variance offenses produces a wider margin
distribution than one between two rim-pressure, free-throw-drawing teams — the binomial
variance of the three-ball propagates to the final score. Win probability is roughly
Φ(mean margin / sd margin): everyone models the numerator; the denominator is where E3
calibration is won. A pregame dispersion model — even a crude one — converts the same
margin mean into better-calibrated probabilities and directly discharges the §5
distributional obligations (matched dispersion, PIT, covariance reporting).

**Information consumed.** Strictly-lagged team shot-profile aggregates (3PA rate, FT rate)
**if and only if** those fields clear an S37 receipted cutoff-validity promotion from F13's
UNPROVEN inventory (they are not assumed valid here). **Degradation path needing no
promotion:** lagged realized score variance per team (rolling sd of own game margins and
totals, owned data) and the pace level itself (more possessions → more variance in raw
points but *lower relative* variance — the form must get this direction right). Historical
league OT rate enters the total-dispersion term (OT is a variance event for E1).

**Functional form sketch.** `sd_margin(g) = σ0 · exp(γ1·z(3PArate_sum) + γ2·z(paceSum) +
γ3·z(laggedMarginSd_sum))` (or the degraded form without γ1), train-years σ0;
`E3 = Φ(Ê2/sd_margin)`. For §5: Gaussian (or skew-t if train-years residuals demand)
predictive distributions for E1/E2 with the matched-K0 emitting the same family with
constant train-years dispersion; per-side residual covariance and `corr(e_home, e_away)`
reported as first-class receipts per the §5 obligation.

**Estimands helped.** E3 primarily (Brier and the receipted 10-bin calibration table reward
correct confidence, not just correct sign); the §5 secondary CRPS/PIT endpoints for E1/E2.
Zero direct help to E1/E2 MAE — the card must say so plainly and register E3 only as its
gated element (plus optional secondary distributional claims, which per §5 can never carry
a promotion).

**Expected failure mode.** Heteroskedasticity in game margins is real but shallow; the
dispersion model may explain so little variance in sd that Φ(m/sd) is indistinguishable
from a constant-sd probit, and the arm dies to its own K0 (which, matched on response
family, already has a constant train-years sd). If the shot-profile fields fail S37
promotion, the degraded form (lagged realized variance) is weaker still — rolling sd over
~15 games is a famously bad variance estimator.

**Kill conditions (receipted).**
1. Receipted dispersion-spread diagnostic (sealed output: ratio of 90th to 10th percentile
   predicted sd_margin per fold): if that ratio < 1.15 pooled, the model is predicting a
   constant and cannot beat its constant-sd K0 by its own mechanism — kill.
2. Pooled ΔBrier(E3) ≤ 0, or the receipted 10-bin calibration table shows the arm's
   calibration slope CI excluding 1 while the K0's includes 1 (the variance model made
   calibration *worse*).

**Coverage.** Degraded form: covered wherever lagged sd is computable (≥ ~5 prior games;
league fallback below that, information-based) — floors met. Promoted form additionally
gated on S37, which affects feature availability, not row coverage.

---

## Cross-candidate notes for S32/S33

- **Complementarity:** C2-6 initializes C2-1/C2-2; C2-3 cleans their inputs; C2-4 and C2-5
  add orthogonal scoring context; C2-7 converts any of their margin means into calibrated
  E3. They are proposed as separable arms (each with its own K0 per §4) but compose.
- **Family hygiene:** C2-1/C2-2/C2-6 are plausibly one mechanism family
  (strength-estimation); C2-4/C2-5 (context-on-scoring) and C2-3 (input hygiene) and C2-7
  (dispersion) are distinct mechanisms. Stated now so the S33/S35 family freeze isn't
  reverse-engineered from results later.
- **Identification registrations (§7 generic clause):** C2-2's off/def sum-to-zero
  constraint; C2-1's α blend (off vs opposing def) has a symmetry indeterminacy at α=0.5
  that the card should pin by grid; C2-7's σ0 scale is train-years-fixed.
- **Nothing above** consumes market fields, injury/availability data, current-game realized
  anything, or postponement-updated dates; every candidate passes the column-grain
  deletion-invariance receipt by construction because every feature is a function of
  strictly-prior rows plus the closed schedule-identity column set.
