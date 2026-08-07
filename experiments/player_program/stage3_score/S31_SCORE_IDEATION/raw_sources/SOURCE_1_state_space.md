# S31 SCORE IDEATION — SOURCE 1 — STATISTICAL TIME-SERIES / STATE-SPACE LENS

**Node:** `S31_SCORE_IDEATION` · **Source:** 1 of the cycle-2 ideation wave
**Input artifact:** `S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md` (frozen ideation edition) — the ONLY file read by this source, per the isolation rules.
**Lens:** state-space / latent-strength evolution, shrinkage structure, regime change, heteroskedasticity, distributional shape.
**Estimands addressed:** E1_GAME_TOTAL, E2_FINAL_MARGIN_HOME, E3_HOME_WIN_PROB (full-game settled quantities, OT included, per D049 as recorded in the contract).

All candidates below consume strictly-lagged, cutoff-valid information only. None consumes market-odds fields, injury/availability data, or any same-game realized quantity (contract §8). Where a candidate has a scale or identification indeterminacy, its identification constraint is registered explicitly per the contract's generic identification bullet (§7). Every proposed kill condition is stated as a diagnostic that can be a **receipted output of a sealed run** (contract §4(c)).

A note on the null-strength floor (§4): the K0_MATCHED for every element carries the frozen public composite's ingredients as null-granted terms. Every candidate below is therefore pitched as structure **on top of** those ingredients — dynamics, joint shape, or variance information the static composite cannot express — not as a rediscovery of level effects the floor already owns.

---

## Candidate 1 — `SS1_KALMAN_OFFDEF`: Bivariate latent off/def strength with Kalman/DLM evolution

**Mechanism story.** Each team carries two latent states — offensive scoring strength and defensive scoring allowance — that evolve as a Gaussian random walk across that team's game sequence. A game's expected side score is (league scoring environment) + (home offense state) + (away defense state) + home-advantage term, and symmetrically for the away side. The causal story: team quality is not static within a season (form, tactical drift, internal roster development), and a filtered state with fitted innovation variance adapts at the statistically correct rate, whereas fixed-window or fixed-decay averages (the natural form of static public composites) adapt at an arbitrary rate. The filter's gain is learned from data, which is precisely the kind of structure a frozen ingredient store cannot carry. The state recursion is inherently strictly-lagged: the state used for game *t* is the posterior after game *t−1*.

**Information consumed.** Owned settled team-game scores (points for/against per team-game row, collapsed to game clusters), strictly prior to each prediction's cutoff; schedule identity columns (opponent, home/away, season, scheduled date valued as-of-cutoff) to sequence the filter; optionally the verified frozen pace ingredient `team_possession_prior_v1.projected_team_off_possessions` as an exposure offset so the latent states are per-possession efficiencies rather than raw points (keeping the candidate off pace mechanisms entirely — pace enters only through the already-frozen, contract-sanctioned ingredient).

**Functional form.**
- Observation: `pts_home = m_t + a_home·(off_H − def_A + h) `, `pts_away = m_t + a_away·(off_A − def_H)` with `a` the pace offset (frozen ingredient, not fitted) or `a ≡ 1` in a raw-points variant; observation noise `N(0, σ_obs²)`.
- State: `off_{i,t} = off_{i,t−1} + η`, `η ~ N(0, q_off)`; same for `def`. Fitted: `q_off, q_def, σ_obs, h`, initial-state variance. Fixed: the random-walk form; the pace offset.
- **Identification constraint (registered):** off/def states are identified only up to a location shift (adding c to every off and every def leaves side scores unchanged). Constraint: league-mean centering — off and def states each sum to zero across active teams at every filter step, with the level absorbed by `m_t`. This is declared in the card, not left implicit.
- Predictions: E1 = sum of the two side means; E2 = their difference; E3 via `Φ(E2 / σ_margin)` with `σ_margin` from the filter's predictive variance (train-years-only estimation).

**Estimands helped.** E2 and E3 primarily (margin is a difference of strengths — the state structure is exactly a margin model); E1 secondarily (the off+def sum tracks total-scoring propensity beyond a static average).

**Expected failure mode, honestly.** With ~40 regular-season games per team-season and only 2021–2026 of history, the fitted innovation variances may collapse toward zero — at which point the filter degenerates into exactly the kind of shrunk long-run average the null-granted composite ingredients already carry, and Δ over K0_MATCHED is ≈ 0. This is the single most likely outcome and it is a legitimate null result.

**Kill conditions (receipted diagnostics).**
1. Fitted innovation variance receipt: if, in ≥ 4 of 5 folds, the fitted `q_off + q_def` is below a card-pinned numeric threshold (declared before fit) such that the filter's effective memory exceeds a full season, the arm is killed — it has become the null. Diagnostic: the per-fold fitted `(q_off, q_def, implied effective half-life)` table, sealed with the run.
2. Pooled OOF ΔMAE(E2) vs K0_MATCHED ≤ 0 with the 95% game-clustered bootstrap CI upper bound below a card-pinned margin. Diagnostic: the standard sealed Δ table.

**Coverage.** Needs a burn-in: predicate of the contract-sanctioned form, e.g. "both teams have ≥ 5 strictly-prior games this season OR ≥ 20 strictly-prior games all-time" (exact N tuned on train years only and pinned in the card). Diffuse initialization means the filter emits predictions from game 1, so the strict predicate can be as loose as "≥ 1 strictly-prior game for both teams"; the §2 floors (≥ 90% pooled, ≥ 80% per fold) are comfortably satisfiable, and the mandatory all-covered-games sensitivity row uses diffuse-prior predictions as the declared fallback.

---

## Candidate 2 — `SS2_BIVARIATE_SCORE`: Joint bivariate model of (home pts, away pts) with explicit residual covariance

**Mechanism story.** E1 and E2 are the sum and difference of the same bivariate outcome. Modeling the pair jointly — rather than modeling total and margin as separate univariate targets — enforces internal consistency and exploits the fact that home and away scores in a game are positively correlated (shared pace realization, shared officiating environment, mutual garbage-time dynamics). The covariance structure determines how side-level predictive skill translates into total-level and margin-level skill: Var(total) = Var(H) + Var(A) + 2Cov, Var(margin) = Var(H) + Var(A) − 2Cov. A model that estimates Cov(e_home, e_away) explicitly can weight its side predictions optimally for each estimand, where independent side models implicitly assume Cov = 0 and misallocate. This candidate is also the natural host for the contract's §5 covariance obligation: the quantities the contract demands as receipts are this model's actual parameters.

**Information consumed.** Same as Candidate 1: strictly-lagged owned scores, schedule identity, optional frozen pace ingredient. Nothing else.

**Functional form.** `(pts_H, pts_A) ~ N₂((μ_H, μ_A), Σ)` where `μ` comes from any admissible mean model (including Candidate 1's states or simply the null-granted composite ingredients as regressors — the minimal version is "K0's own mean structure + fitted Σ"), and `Σ = [[σ_H², ρσ_Hσ_A], [ρσ_Hσ_A, σ_A²]]` fitted on train years only, optionally with `ρ` and the σ's as slowly-varying (per-season random walk) rather than global constants. E3 = P(H − A > 0) under the fitted bivariate predictive — a closed form. Fitted: Σ components (and their dynamics if enabled). Fixed: Gaussianity (see Candidate 5 for the relaxation).

**Estimands helped.** E3 most directly (the margin's predictive sd, which calibrates the win probability, is derived rather than assumed); E1/E2 point predictions improve only insofar as the mean model does, but the *distributional* secondary endpoints (§5 CRPS/PIT, if emitted) inherit a principled dispersion. Honest statement: if the mean model equals K0's, ΔMAE on E1/E2 will be ~0 and the element's value is concentrated in E3 Brier via better implied dispersion.

**Expected failure mode.** ρ may be small and stable enough that the K0's implicit treatment (whatever dispersion matching the S32B schema grants the null) captures it; then the covariance machinery adds parameters without moving Brier. Also, a global Gaussian Σ may be flatly wrong in high-total games (variance increasing with total), which is Candidate 3's job, not this one's — the two should be registered so that the family correction treats them as one mechanism family if S33/S35 so freezes.

**Kill conditions (receipted diagnostics).**
1. Sealed receipt of fitted `corr(e_home, e_away)` per fold with bootstrap CI: if the CI covers 0 in ≥ 4 of 5 folds, kill — the joint structure has nothing to transmit. (This receipt is *already contract-mandated* for any two-sided arm by §5, so it is free.)
2. ΔBrier(E3) pooled OOF vs K0_MATCHED ≤ 0 (uncorrected, per the kills-uncorrected rule) with the 10-bin calibration table (a contract-named receipted output) showing no bin-level improvement pattern. Diagnostic: the sealed calibration table plus Δ row.

**Coverage.** No burn-in beyond the mean model's; if the mean model is the K0's own, coverage predicate can be near-total ("both teams have ≥ 1 strictly-prior game"), trivially clearing the §2 floors.

---

## Candidate 3 — `SS3_HETEROSKED_TOTAL`: Conditional heteroskedasticity — predictive variance as a modeled quantity

**Mechanism story.** Scoring variance is not constant across games. Games projected to be high-pace/high-total have more possessions and therefore mechanically more variance in points (roughly Poisson-binomial scaling: variance grows with the number of scoring opportunities); mismatched games (large strength gap) plausibly have inflated margin variance via garbage-time dynamics; OT-inflation itself is a variance phenomenon concentrated in games whose *expected* margin is near zero (close games go to OT more often, and OT adds points — a legitimate pregame-expectation effect on both the mean and the variance of the settled total). A model of `σ²(total)` and `σ²(margin)` as functions of strictly-lagged covariates improves E3 directly (win probability is mean/sd, so sd errors are first-order for calibration) and improves any distributional secondary endpoint; it does not move E1/E2 MAE much and should not claim to.

**Information consumed.** Strictly-lagged: the frozen pace ingredient (projected possessions — variance scaling with expected possessions is the cleanest channel and uses only the sanctioned artifact); lagged own-history realized scoring variance per team (dispersion of a team's prior game totals); the mean model's own predicted margin magnitude |E2̂| (a pregame construction); historical OT rates as a function of predicted closeness (explicitly sanctioned by the contract's OT clause: "historical OT rates … are NOT swept up"). No same-game realized possessions, minutes, or OT indicators anywhere.

**Functional form.** Log-linear variance model: `log σ²_total = γ0 + γ1·log(projected_possessions_H + projected_possessions_A) + γ2·team_dispersion_lag + γ3·f(|Ê2|)`, and analogously for margin variance, fitted jointly with (or two-stage after) the mean model on train years only; the OT channel enters as an additive mixture: settled total = regulation-scale component + P(OT | predicted closeness)·E[OT points], with P(OT|·) fitted on strictly-prior seasons. Fitted: γ's, OT-rate curve. Fixed: log link, two-stage structure. E3 = `Φ(Ê2 / σ̂_margin)`. **Identification note:** none needed — all quantities are directly parameterized; the mixture's components are identified by the historical OT-rate curve being fit on lagged data, not jointly free.

**Estimands helped.** E3 (Brier is directly sensitive to sd misspecification near the p≈0.5 mass where WNBA games concentrate); E1 marginally via the OT-mixture mean correction (expected OT points added for predictably-close games — a real, small, mean effect on the settled total that a static composite cannot represent); distributional secondaries under §5 if emitted.

**Expected failure mode.** The variance signal may be almost entirely absorbed by the possession-scaling term, which is close enough to constant across the retained universe that a single pooled sd (which the K0's matched dispersion estimation already provides) is not measurably worse. The OT mean correction is small (OT is rare) and may not survive noise.

**Kill conditions (receipted diagnostics).**
1. Variance-model likelihood-ratio receipt: sealed per-fold train-side LR of the heteroskedastic vs homoskedastic dispersion model; if the card-pinned improvement threshold is not met in ≥ 3 of 5 folds, kill the variance channel before it reaches the gate (this is a preregistered, receipted, train-side diagnostic — no test leakage).
2. PIT-calibration receipt (if the distributional secondary is emitted): sealed PIT histogram uniformly no better than K0's by the card-pinned statistic; kill the distributional claim. E3 gate failure kills the rest on its own.

**Coverage.** Needs enough lagged games to compute team dispersion (e.g. ≥ 8 strictly-prior games for the dispersion term, with a card-declared fallback to league-mean dispersion below that). With the fallback, the predicate can stay at "≥ 1 strictly-prior game", satisfying §2 floors; the fallback row doubles as the mandatory all-covered-games sensitivity row.

---

## Candidate 4 — `SS4_SEASON_REGIME`: Season-boundary regime handling — discounted likelihood with boundary variance inflation

**Mechanism story.** The single largest structural non-stationarity in a 2021–2026 panel is the offseason: rosters turn over, coaching changes land, and league composition shifts (expansion). A model that treats a team's identity as continuous across the boundary over-trusts stale information; one that resets fully throws away real signal (franchise quality persists partially). The right structure is a fitted *partial* reset: at each season boundary, each team's latent strength (or its stand-in: the weight given to prior-season aggregates) is shrunk toward the league mean by a fitted factor κ, and its state uncertainty is inflated by a fitted amount. This is a regime-change mechanism in the strict state-space sense, and it is knowledge the static composite ingredients cannot carry: they either include prior seasons at a fixed decay or exclude them, but the *optimal* boundary discount is an estimable parameter.

**Information consumed.** Strictly-lagged owned scores and schedule identity (season labels are schedule-identity columns, contract §1); nothing else. Explicitly NOT consumed: roster or transaction data (availability-adjacent, barred without point-in-time provenance).

**Functional form.** As an overlay on Candidate 1: at season boundary, `state ← κ·state` and `P ← P + V_boundary` with `κ ∈ [0,1]` and `V_boundary` fitted on train years. As a standalone (composite-compatible) form: the arm's design carries the null-granted composite ingredients *twice* — current-season-only and all-history versions — with a fitted, early-season-decaying mixing weight `w(n_games_this_season)`; this version hosts the null ingredients natively, so the cannot-host path is never invoked. Fitted: κ, V_boundary (or the mixing curve's 2 parameters). Fixed: the boundary event set (schedule identity). **Identification:** none needed in the overlay; in the standalone form the mixing weight is identified because the two ingredient copies differ on early-season games.

**Estimands helped.** All three, concentrated in **early-season games** (roughly the first quarter of each season), which is exactly where static composites are weakest and where fold `train_lt_2022`-style early-window test games live. E2/E3 most (strength errors hit margin hardest); E1 via the level component.

**Expected failure mode.** The effect is real but small and concentrated in a minority of games; pooled OOF Δ over the full universe may not clear the corrected gate even if the early-season slice improves markedly. Honest risk: this candidate's value may be diagnostic (season splits are a contract-named secondary) rather than gate-clearing.

**Kill conditions (receipted diagnostics).**
1. Fitted κ receipt: if the pooled fitted κ pins to the boundary of its allowed interval (κ → 1, i.e. "no reset", or the mixing weight degenerates to all-history) in ≥ 4 of 5 folds, kill — the mechanism found nothing. Diagnostic: sealed per-fold parameter table.
2. Season-split receipt: the contract already mandates season splits as secondary outputs; if the early-season slice (card-pinned definition, e.g. each team's first 10 games) shows ΔMAE ≤ 0, kill regardless of pooled results — the mechanism's own story predicts improvement exactly there, and its absence falsifies the story even if pooled noise flatters it.

**Coverage.** This candidate's whole point is early-season games, so its predicate must be *loose*: "both teams ≥ 1 strictly-prior game (any season)" — near-total coverage, trivially clearing §2. Trimming early-season games would be self-defeating and would rightly look like predicate gaming under §2's selection-visibility rule.

---

## Candidate 5 — `SS5_HEAVY_TAIL`: Student-t observation noise — robust filtering and honest tail mass

**Mechanism story.** Score residuals are not Gaussian: blowouts produce heavier-than-normal tails in the margin distribution, and single anomalous games (a 30-point blowout driven by transient circumstances) should move a team's latent strength estimate *less* than a Gaussian filter moves it, because the Gaussian likelihood over-weights tail observations. Replacing Gaussian observation noise with Student-t noise does two independent jobs: (i) robustifies the state update — the filter discounts outlier games automatically, improving the *mean* path of latent strengths — and (ii) puts honest mass in the tails of the predictive margin distribution, which matters for E3 when the predicted margin is large (Gaussian tails make 15-point favorites too certain) and for any §5 distributional endpoint.

**Information consumed.** Identical to Candidate 1 — this is a shape change, not an information change. Zero new ingredients.

**Functional form.** Candidate 1's observation equation with `e ~ t_ν(0, σ²)`, ν fitted on train years (one global ν, or one per estimand-side); filtering via standard scale-mixture augmentation. E3 = `T_ν(Ê2 / σ̂)` instead of Φ. Fitted: ν, σ. Fixed: the t family. **Identification:** ν and σ are jointly identified by tail mass vs central mass; no constraint needed beyond ν > 2 (finite variance), pinned in the card.

**Estimands helped.** E3 in the tails (large predicted margins — Brier improvements concentrated in the confident bins of the mandated 10-bin calibration table); E2 MAE mildly via the robustified state path (outlier games stop whipsawing the strength estimates). E1 marginally at best.

**Expected failure mode.** Fitted ν may come out large (≈ 30+), i.e. effectively Gaussian — WNBA margins may be less heavy-tailed than intuition suggests once strength differences are conditioned out. Then the candidate is pure parameter overhead. Also its E3 benefit lives in the low-population extreme calibration bins, where the game-clustered bootstrap CIs are wide.

**Kill conditions (receipted diagnostics).**
1. Fitted ν receipt: if the per-fold fitted ν exceeds a card-pinned threshold (declared before fit; e.g. ν ≥ 25) in ≥ 4 of 5 folds, kill — the data rejected the heavy tail. Sealed per-fold ν table.
2. Calibration-bin receipt: in the mandated 10-bin table, if the two most extreme populated bins show no Brier-contribution improvement vs K0 pooled OOF, kill the tail claim; the robust-filtering claim then stands or falls on the E2 gate alone.

**Coverage.** Identical to Candidate 1 (it is Candidate 1 with a different likelihood); same predicate, same floor satisfaction. Family note for S33/S35: Candidates 1 and 5 are plausibly one mechanism family (latent-state margin models); registering them as such is the conservative reading and I flag it here so the freeze can decide with the dual-run rule if disputed.

---

## Candidate 6 — `SS6_LEAGUE_DRIFT`: Common league scoring-environment factor as a slowly-varying latent level

**Mechanism story.** Total scoring drifts league-wide across and within seasons — rule-emphasis changes, evolving shot selection (three-point rate trends), expansion-team effects on average defensive quality. This is a *common factor*: it moves every game's total, is orthogonal to team identity, and is invisible to any per-team aggregate (per-team averages confound team strength with environment). A dedicated slowly-varying league-level state `m_t` (random walk on game date, fitted innovation variance, strictly-lagged updates) captures it with maximal parsimony — one state series for the whole league. Within-season drift (scoring typically shifts as the season progresses — conditioning, rotations tightening) is part of the same state's path rather than a separate calendar dummy, keeping the mechanism information-based.

**Information consumed.** Strictly-lagged league-wide settled totals (all games before the cutoff, all teams); scheduled date as-of-cutoff for sequencing. Nothing per-team, nothing else.

**Functional form.** `m_t` as in Candidate 1's observation equation (it is Candidate 1's level term, but proposable standalone on top of *any* mean model including the K0-plus-nothing design): `total_pred = m_t + (team terms or null-granted composite terms centered within-season)`. Fitted: innovation variance of m, initial level. Fixed: random-walk form. **Identification (registered):** m_t absorbs the global level; team/composite terms must be centered (league-mean-zero within the training window) or the level is doubly counted — the same constraint as Candidate 1's, restated because the standalone version needs it too against the null-granted ingredients (which carry their own level). Concretely: the arm's design centers the null-granted composite columns and lets m_t own the level; declared in the card.

**Estimands helped.** E1 almost exclusively (a common level factor cancels in margins by construction — it should show ≈ 0 on E2/E3, and *that prediction is itself a falsifiable receipt*: if the arm moves E2, something is wrong with the implementation).

**Expected failure mode.** If league drift within the 2021–2026 window is mostly *between*-season steps rather than within-season drift, a season-mean term inside the null-granted composite ingredients may already capture nearly all of it, leaving Δ(E1) ≈ 0. The within-season drift component may be too slow/small to beat the added filtering variance.

**Kill conditions (receipted diagnostics).**
1. Innovation-variance receipt: fitted league-level innovation variance below the card-pinned floor (state effectively constant within seasons) in ≥ 4 of 5 folds → kill. Sealed per-fold table.
2. Cross-estimand sanity receipt: |ΔMAE(E2)| exceeding a card-pinned small bound (mechanism predicts ~0 by construction) → kill on implementation-integrity grounds, not performance grounds; this is a cheap, sealed, self-falsifying check.

**Coverage.** Effectively none needed beyond the league having any prior games at the cutoff — the loosest predicate in this list ("≥ 1 league game strictly prior"); §2 floors trivially satisfied; early-season the state carries over from the prior season's endpoint with boundary inflation (composable with Candidate 4).

---

## Candidate 7 — `SS7_SCHED_FATIGUE_SCORING`: Rest/travel/schedule-density effects on scoring efficiency (contract-conditional form)

**Mechanism story.** Proposed strictly in the contract's conditional form (§7): this candidate acts on **scoring**, not pace, and does not target pace mechanisms in the cycle-1 forms. The story: fatigue (short rest, dense stretches, long travel implied by the schedule's venue sequence) degrades shooting efficiency and defensive execution — points per possession, not possessions. Schedule-derived fatigue is computable entirely from schedule-identity columns valued as-of-cutoff (scheduled dates, venues/home-away sequence, opponent sequence), making it one of the cleanest cutoff-valid feature families available: no measurement, no vendor, no provenance question. Its effect is plausibly asymmetric (rest *disadvantage* hurts more than rest advantage helps) and interacts with the season phase (fatigue compounds late-season) — structure a state-space treatment handles as a time-varying coefficient if the simple form underfits.

**Information consumed.** Schedule identity only, as-of-cutoff: days since each team's previous scheduled-and-played game, games in trailing 7 days, back-to-back indicator, home-stand/road-trip length. Caveat handled honestly: rest computed from *prior* games uses those games' as-played dates, which are realized facts of *past* games — legitimate lagged information, not same-game leakage; only the current game's own date is used as-of-cutoff. Postponement edge cases resolve per the contract's as-of-cutoff rule.

**Functional form.** Additive terms on each side's expected scoring efficiency: `side_pts += β1·rest_deficit + β2·b2b + β3·travel_load`, β's fitted (optionally hierarchically shrunk toward a league effect; optionally time-varying via a small random-walk state on β if the card enables it). Fixed: the feature definitions (pinned formulas in the card). E1 via both sides' terms; E2/E3 via the *differential* (home fatigue − away fatigue). **Identification:** none needed; ordinary regression terms.

**Estimands helped.** E2/E3 via the fatigue differential (the differential is often nonzero when one side is on a back-to-back and the other rested — precisely the games where strength-only models err); E1 via total fatigue load (both sides tired → lower-scoring game, if the efficiency story dominates any pace story; the sign is an empirical question the receipts will answer).

**Expected failure mode.** Cycle-1 nulls on rest/schedule acting on *pace* mechanisms suggest this family's headline effects can be weak in this data. The scoring channel is a different claim, but the honest risk is the same: WNBA scheduling may be dense enough uniformly that variation is too small, and the fatigue differential too rare, to clear a corrected gate. Also collinearity with home-court context (road trips correlate with away status) could reduce the differential's marginal value over the null's home terms.

**Kill conditions (receipted diagnostics).**
1. Coefficient-stability receipt: sealed per-fold β table with bootstrap CIs; if the sign of the primary rest-deficit β flips across folds (any two folds with CIs excluding zero on opposite sides), kill — the effect is noise being fit.
2. Differential-slice receipt: on the card-pinned slice of games with a nonzero fatigue differential (e.g. exactly one team on a back-to-back), sealed ΔMAE(E2); if ≤ 0 on that slice pooled OOF, kill — the mechanism's own target games show nothing.

**Coverage.** Rest features exist for any team with ≥ 1 prior game in-season; a card-declared fallback (league-median rest values) covers season openers. Predicate "≥ 1 strictly-prior game this season for both teams" retains far above the §2 floors; the fallback row is the sensitivity row.

---

## Candidate 8 — `SS8_HCA_DYNAMIC`: Home advantage as a slowly-evolving, partially-pooled latent state

**Mechanism story.** Home advantage is treated by static models as one constant. It is neither constant over time (league-wide HCA has drifted era to era; 2021 in particular sits near pandemic-era attendance regimes inside this very panel) nor uniform across teams (arena environments, travel geometry, altitude/climate differ). The right structure is hierarchical and dynamic: a league-level HCA state evolving slowly on a random walk, plus team-specific offsets shrunk hard toward it (partial pooling — the team-level sample per season is ~20 home games, far too small for unpooled estimates). This acts on scoring levels/margins, not pace, and uses only home/away designation (schedule identity) plus lagged settled scores — cutoff-trivial. The cycle-1 conditional bar (§7) is respected: home-court context here acts on scoring.

**Information consumed.** Strictly-lagged settled scores; home/away designation and venue identity from schedule-identity columns. Nothing else. (No attendance data — not in the owned inventory and not needed; the latent state absorbs whatever drives the drift without measuring it.)

**Functional form.** `h_{team,t} = H_t + δ_team`, with `H_t` a league random walk (fitted innovation variance) and `δ_team ~ N(0, τ²)` with τ fitted (the shrinkage parameter — τ → 0 recovers the single-constant null). Enters Candidate 1's observation equation, or standalone on top of the null-granted composite design as the home-term replacement. Fitted: H innovation variance, τ, initial H. Fixed: hierarchy form. **Identification (registered):** δ's sum to zero across teams (league HCA level owned by H_t); declared in the card.

**Estimands helped.** E2 and E3 directly (HCA is a pure margin/win-prob quantity; a 1-point HCA error is ~3 points of Brier-relevant probability at the p≈0.5 mass). E1 essentially unaffected (HCA mostly transfers points between sides rather than adding them; any total effect is second-order).

**Expected failure mode.** τ may fit to ≈ 0 (no resolvable team-level heterogeneity in 6 seasons of ~20 home games/team/season — entirely plausible), and H_t's drift may be dominated by the single pandemic-to-normal step at the panel's start, which the fold structure (train_lt_2022 has the least training data) is worst-positioned to exploit. Net: a real but small mechanism whose identifiable signal may be one step-change the folds straddle awkwardly.

**Kill conditions (receipted diagnostics).**
1. Shrinkage receipt: fitted τ below the card-pinned floor (team offsets indistinguishable from zero) AND fitted H innovation variance below its floor, in ≥ 4 of 5 folds → kill; the candidate has collapsed to the constant the null already carries. Sealed per-fold (τ, q_H) table.
2. ΔBrier(E3) pooled OOF ≤ 0 (uncorrected kill) with the sealed 10-bin calibration table showing the central bins (0.4–0.6), where HCA errors concentrate, no better than K0.

**Coverage.** None beyond "≥ 1 strictly-prior game"; §2 floors trivially satisfied. Composable with Candidates 1/4/5 as one state-space family; standalone-on-null version available where family assignment prefers separation.

---

## Cross-cutting notes for the coordinator (from this lens only; no knowledge of other sources assumed)

1. **Composability and family structure.** Candidates 1, 4, 5, 6, 8 are modules of one coherent DLM architecture and could be registered as one family with ablation-style arms (each module on/off against the same K0), which is both the honest multiplicity treatment and the cheapest implementation path. Candidates 2, 3 form a dispersion/shape family. Candidate 7 stands alone. I flag this for S33/S35 family freezing; the stricter-partition rule governs disputes.
2. **Null-hosting.** Every candidate above can host the null-granted composite ingredients natively in its design (as centered regressors in the observation equation or as the standalone base design), so none should need the cannot-host path or its BELOW-FLOOR label.
3. **Honest prior from this lens.** The highest-probability-of-signal candidates, in order: 4 (season regime — the non-stationarity is structurally certain, only its magnitude is in question), 2/3 (dispersion structure for E3 — the estimand is new this cycle, so dispersion has never been directly optimized), 1 (within-season dynamics — real but possibly too slow to beat a well-tuned static decay), 8, 5, 6, 7. The weakest claims are stated as such in each candidate's failure-mode paragraph; none of the eight requires information outside the contract's cutoff-valid inventory, and none touches a barred ingredient.
