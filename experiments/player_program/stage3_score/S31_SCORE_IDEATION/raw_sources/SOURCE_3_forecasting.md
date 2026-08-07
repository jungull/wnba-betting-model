# SOURCE 3 — FORECASTING PRACTITIONER LENS
**Node:** S31_SCORE_IDEATION · cycle-2 score-family ideation wave · source 3 of the wave
**Input artifact:** `CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md` (frozen ideation edition) — the ONLY file read.
**Lens:** what actually wins M-competition-style evaluations against strong simple baselines: combination of simple components, damped/shrunk level estimation, variance modeling for probability targets, calibration structure, robustness to outliers, and honest exploitation of the MAE-vs-MSE (median-vs-mean) distinction.

**Standing observations from the lens, applied to this contract before any candidate:**

1. The K0_MATCHED null-strength floor (§4) carries the public composite's frozen ingredients as null-granted terms. Decades of forecasting-competition evidence say a well-tuned exponential-smoothing baseline is brutally hard to beat; most "sophisticated" challengers lose to it out of sample. Every candidate below is therefore designed to add something the composite's ingredient set *structurally cannot contain* (extra horizons, cross-sectional shrinkage, variance structure, calibration structure, schedule context, tail handling) rather than a re-estimation of what it already has. Re-estimating the same signal with a fancier fitter is the classic way to lose to your own null.
2. `estimation_objective` is a matched K0 dimension (§4): the arm cannot buy Δ merely by training on a better-aligned loss, because the K0 trains on the same loss. Loss alignment below is treated as *hygiene every card should declare* (pinball τ=0.5 for the MAE-graded E1/E2; proper-score maximum likelihood for E3), and the candidates claim value only from added *structure*.
3. E1/E2 are graded by MAE → the target functional is the conditional **median**. E3 is graded by Brier → the target is the true conditional probability, and Brier decomposes into calibration + resolution: variance and calibration structure are first-class levers there, not afterthoughts.

---

## Candidate F3-1 — Multi-horizon damped-level combination ("Theta-flavored" team scoring state)

**Description.** The public composite's ingredient set (by frozen bytes) embodies one smoothing choice per signal. M-competition history (Theta, damped exponential smoothing, ETS ensembling) says the reliable win over any single smoother is a *combination of the same signal at several horizons with damping toward a long-run anchor*. Maintain, per team, per side of the ball, strictly-lagged scoring-rate and allowed-rate states at three half-lives (short ≈ 3–5 games, medium ≈ 10–15, long = season-to-date) plus a prior-season anchor, and let a penalized combiner (weights fit train-only, per fold) blend them, with an explicit damping coefficient shrinking the short-horizon deviation toward the long-run level. This is not "another EWMA" (which would be blocked as a bytes-mismatched reimplementation of the null-granted ingredient — and rightly so); it is the *spread between horizons* as new information: teams whose recent form deviates from their season level regress predictably, and the damped blend captures how much.

**Information consumed (all strictly-lagged, cutoff-valid):** own committed team points-for / points-against history from prior games (the §8 "efficiency inputs" channel); season labels for the prior-season anchor; nothing same-game, no market, no injury.

**Functional form sketch.**
- State per team t, side s, horizon h: `L_{t,s,h}(g) = λ_h · x_{t,s}(g−1) + (1−λ_h) · L_{t,s,h}(g−1)` computed over strictly-prior games only.
- Arm feature block: `{L_short − L_long, L_med − L_long, L_long, L_prevseason_shrunk}` per team-side.
- Prediction head (declared identically in arm and K0): linear in the null-granted composite ingredients (K0 terms) **plus** the horizon-spread block, ridge-penalized, trained under pinball τ=0.5 for E1/E2.
- Damping enters as the penalty's prior mean of 0 on the spread coefficients — the fitted spread weight *is* the damping factor, estimated not asserted.

**Estimands helped:** E1 and E2 (both are sums/differences of team scoring levels; better level estimation moves both). E3 only indirectly via F3-4.

**Expected failure mode, honestly:** collinearity with the null-granted composite ingredients. If the frozen composite's smoothing already sits near the optimal single half-life, the horizon spreads carry mostly noise, the ridge shrinks them to ~0, and Δ ≈ 0 with added variance. Short-horizon terms chasing 3-game noise is the specific classic failure.

**Kill conditions (receipted):**
- K1: receipted per-fold coefficient table for the spread block; if the 95% train-refit bootstrap CI for *every* spread coefficient covers 0 in ≥ 4 of 5 folds, kill.
- K2: pooled OOF ΔMAE vs K0_MATCHED ≤ 0 (the gate's own receipted primary; kills are uncorrected per §4).

**Coverage vs §2 floors:** no new predicate needed beyond "team has ≥ 1 strictly-prior game this season" (prior-season anchor + league mean serve as the declared fallback for openers), so full base universe is retainable: ≥ 90% pooled and ≥ 80% per fold are met trivially. The mandatory all-covered-games sensitivity row costs nothing extra.

---

## Candidate F3-2 — Hierarchical shrinkage-to-the-field for team strength (James–Stein early-season structure)

**Description.** The single most reliable cross-sectional forecasting win: shrink each unit's estimate toward the field mean by an amount that grows as that unit's sample shrinks. Early-season team scoring estimates are noise-dominated; a fixed-λ smoother under-shrinks them. Model team offensive/defensive strength as a deviation from the league-season mean with an empirical-Bayes shrinkage factor `k/(k+n_games_prior)` (k estimated train-years-only), so a team's week-2 rating is mostly field and its week-12 rating is mostly its own data. The composite's frozen ingredients (fixed smoothing, by bytes) cannot represent sample-size-adaptive shrinkage, so this is genuinely outside the null.

**Information consumed:** strictly-prior team points-for/against; strictly-prior league-season scoring mean (computed over games completed before the cutoff, never the season's final mean — the season-label convenience trap §2 warns about); count of strictly-prior games per team.

**Functional form sketch.** `strength_{t,s} = (n_t/(n_t+k)) · (obs mean dev)_{t,s} + (k/(k+n_t)) · 0`, with league level itself lightly smoothed across seasons; features enter the same declared head as F3-1. For E3, shrunk strengths feed the margin model of F3-4.

**Estimands helped:** E1, E2 directly; E3 through the margin path. The mechanism's value is concentrated in the first ~6 games of each season — which is exactly where a fixed smoother initialized from thin data is worst.

**Expected failure mode:** if the frozen composite ingredients already encode a reasonable initialization (e.g. prior-season carryover), the marginal value of adaptive shrinkage may live in ~10–15% of games (early season) and be too small pooled to clear the gate. Also, k is one more train-estimated hyperparameter that can overfit fold idiosyncrasies (2021 COVID-adjacent scheduling, 2026 expansion-era drift, if present in the universe).

**Kill conditions (receipted):**
- K1: receipted season-split secondary table (already mandated §4): if the early-season stratum (declared in the card as games where either team has < 6 strictly-prior games, a cutoff-valid information predicate) shows ΔMAE ≤ 0, the mechanism's own story is falsified — kill even if pooled Δ is accidentally positive.
- K2: receipted train-only k path per fold; if fitted k diverges (→∞, i.e. "shrink everything to league mean") or → 0 ("no shrinkage") inconsistently across folds, kill for instability.

**Coverage vs §2 floors:** this candidate's whole point is to *avoid* "both teams ≥ N prior games" trimming predicates — it keeps openers in-universe by shrinking them to the field. Coverage predicate = full base universe. Strictly floor-friendly; it is the anti-trimming mechanism.

---

## Candidate F3-3 — Constrained combination of deliberately diverse simple components (the forecast-combination puzzle, exploited)

**Description.** The oldest, most replicated result in the evaluation literature: an equal-or-near-equal-weight average of *diverse, individually unimpressive* forecasters beats almost every individually optimized model, and beats picking the best component in-sample. Build K ≈ 4–6 simple pregame predictors per estimand from owned data — (a) season-to-date mean levels, (b) prior-season levels, (c) home/away-split levels, (d) opponent-adjusted levels (one pass of adjustment, not iterated), (e) league-mean climatology, (f) the pace-prior-scaled efficiency product using the verified `team_possession_prior_v1.projected_team_off_possessions` ingredient — and combine with weights constrained to the simplex (nonnegative, sum to 1), estimated train-only with a strong prior toward equal weights. The null-granted composite is *one* component-generating recipe; the arm's claim is that the *combination across diverse recipes* — specifically its variance-cancelling property — is the added value, which the K0's fixed ingredient set cannot manufacture.

**Information consumed:** strictly-prior team scores, strictly-prior home/away splits, prior-season aggregates, the frozen verified pace ingredient (§8 explicitly consumable), strictly-prior opponent-strength one-pass adjustment. All cutoff-valid; the identification constraint (§7 generic form) is registered for the opponent-adjustment component: strength deviations sum to zero league-wide at each cutoff, pinning the scale.

**Functional form sketch.** `ŷ = Σ_k w_k f_k(x_lagged)`, `w ∈ Δ^{K−1}`, `w ~ shrunk toward 1/K` (e.g. simplex-constrained ridge to the equal-weight point, penalty chosen train-only per fold). Same head declared for arm and K0 per the matched-dimension rules; the K0 hosts the null-granted ingredients inside the same pipeline with zero substantive components added.

**Estimands helped:** E1 and E2 (component diversity is easy to construct for levels); E3 via combined-margin input to F3-4. Combination helps MAE precisely because averaging kills the variance term of each component's error while diverse biases partially cancel.

**Expected failure mode:** the components are all built from the same underlying score history, so realized diversity may be far lower than nominal diversity — pairwise error correlations of 0.95+ — in which case the combination collapses to approximately the best single component, which is approximately the null, and Δ ≈ 0. This is the known boundary of the combination result: it needs genuinely decorrelated errors.

**Kill conditions (receipted):**
- K1: receipted component-error correlation matrix (train-side, per fold, sealed output). If the minimum pairwise error correlation among components exceeds 0.95 in every fold, the diversity premise is dead — kill before wasting the element's family slot (this is checkable at S37-audit time from train-side receipts without opening comparative OOF results, since it involves no arm-vs-K0 comparison; if adjudication reads the sealing rules more strictly, it runs as an uncorrected kill at S40 like the rest).
- K2: pooled OOF ΔMAE ≤ 0 vs K0_MATCHED.

**Coverage vs §2 floors:** components have different data demands (home/away splits are thin early); handled by card-declared per-component fallbacks (component reverts to league climatology when its input is empty), never by trimming the universe. Full-universe coverage; floors met.

---

## Candidate F3-4 — Margin-to-probability variance mapping for E3 (get σ right, then Φ)

**Description.** The practitioner's route to winning a Brier evaluation is almost never "more features in a logistic regression"; it is a well-estimated latent-variable mapping `p = Φ(μ_margin/σ)` where μ comes from the best available margin model and σ is estimated honestly (train-years-only) — because Brier punishes variance misspecification (over-confidence) more reliably than it rewards marginal resolution. The contract itself hints the raw material exists: F13 measured sd(margin) ≈ 14 on the full-game reading. The candidate: E3 is produced *only* through the E2 model's μ and a dispersion model for σ — a homoskedastic σ̂ as the base form, plus one preregistered heteroskedastic term: σ as a mild function of the game's combined pace prior (the verified §8 ingredient), on the argument that more possessions give the favorite more trials — CLT thinking says margin *sd in points* grows like √possessions while μ grows like possessions, so pace moves p even at fixed per-possession strengths.

**Information consumed:** the arm's own E2 prediction path (same strictly-lagged inputs), the frozen verified pace ingredient, train-years-only residual variance estimates. Nothing else. No market, no injuries.

**Functional form sketch.** `p̂ = Φ( μ̂_margin / σ̂(pace) )`, `σ̂(pace) = exp(γ0 + γ1 · z(pace_prior_sum))`, γ fit train-only per fold by Gaussian likelihood on train margin residuals; γ1 = 0 recovers the homoskedastic base. p-clipping bounds declared in the card, identical for arm and K0 (matched dimension, §4). The matched K0 for the E3 element runs the identical mapping over the K0's own μ (null-granted ingredients only) with its own train-fitted σ — so Δ isolates the *margin-model information plus variance structure*, not the link trick itself.

**Estimands helped:** E3 primarily (Brier). The σ machinery also positions the arm to emit the §5 secondary distributional endpoints for E2 nearly for free (Gaussian predictive with matched dispersion estimation), though nothing is claimed on secondaries per contract.

**Expected failure mode:** two, honestly. (i) γ1: WNBA pace variation may be too narrow for the √possessions effect to matter — the heteroskedastic term fits noise and slightly worsens calibration. (ii) The Gaussian shape assumption in the tails: if margins are heavier-tailed than Gaussian, Φ misprices lopsided games; but Brier (unlike log-loss) is forgiving in the tails, which is exactly why this design targets Brier and reports log-loss as the mandated secondary without claiming it.

**Kill conditions (receipted):**
- K1: the mandated 10-bin calibration table (a receipted sealed output per §4) shows monotonicity violation or bin-wise miscalibration exceeding what the pooled Brier decomposition attributes to resolution gain — operationalized in the card as: reliability component of the pooled OOF Brier decomposition (receipted) larger for the arm than for its K0_MATCHED → kill.
- K2: receipted per-fold γ1 train CIs: if γ1's sign flips across folds with CIs excluding 0 on both sides, the heteroskedastic term is unstable → the card's preregistered fallback drops to homoskedastic form; if the *homoskedastic* form then fails ΔBrier > 0, kill.

**Coverage vs §2 floors:** inherits the E2 arm's universe; pace-prior ingredient is frozen and full-coverage; no additional trimming. Floors met by construction.

---

## Candidate F3-5 — Post-fit probability recalibration with shrinkage toward the pregame base rate (E3 calibration layer)

**Description.** Separate resolution from calibration and buy the calibration term directly: a one-parameter-pair logistic recalibration `p' = σ(a + b·logit(p_raw))`, fit train-only per fold, with (a,b) shrunk toward the values that map the raw model onto the strictly-lagged home-win base rate. This is the forecasting-evaluation workhorse (Platt scaling with a prior): raw score-model probabilities are systematically overconfident out of sample because train-fit sharpness never fully survives the regime shift to test years, and expanding-window folds guarantee some drift. The layer is cheap, preregistrable, and its effect is exactly measurable in the mandated calibration receipts. Declared as `calibration_freedom` in the card explicitly (the contract requires this dimension never be inferred from silence), identically specified for arm and K0.

**Information consumed:** train-years-only raw predictions and outcomes (per fold, strictly inside the expanding window); the strictly-prior home-win base rate computed as-of-cutoff. No test-side information of any kind touches (a,b).

**Functional form sketch.** `p' = σ(a + b · logit(clip(p_raw)))`, with ridge shrinkage of (a,b) toward (logit(base_rate_prior_shrunk-target), 0)-consistent values — concretely, toward the (a,b) that would output the lagged base rate regardless of p_raw — with shrinkage weight chosen train-only. Note b < 1 is shrinkage-toward-the-field for probabilities: the M-competition lesson (damp your trend) transplanted to the probability simplex.

**Estimands helped:** E3 only. Brier = calibration + refinement; this attacks the calibration term with 2 parameters.

**Expected failure mode:** if the upstream E3 model (e.g. F3-4) is already well-calibrated — which Φ(μ/σ̂) with honestly estimated σ often is — the layer is a no-op that adds two fitted parameters of pure variance, and per-fold (a,b) estimated on limited train outcomes (a few hundred games in early folds) is noisy enough to *hurt*. This candidate is insurance that pays only when something upstream is miscalibrated.

**Kill conditions (receipted):**
- K1: receipted per-fold (a,b) table: if b's 95% train-refit CI contains 1 and a's contains 0 in all folds (nothing to fix), and pooled ΔBrier of layered-vs-unlayered (both receipted within the arm's sealed run as declared variants — the card registers the layered form as the arm, unlayered as a receipted diagnostic) is ≤ 0, kill.
- K2: the mandated 10-bin calibration table for the layered arm shows *worse* max-bin deviation than the unlayered diagnostic → kill.

**Coverage vs §2 floors:** none — no universe impact; a pure post-processing dimension, declared as such on the card's post-processing/matched-dimension line.

---

## Candidate F3-6 — Rest and schedule-density context acting on scoring efficiency

**Description.** The one context family the contract explicitly leaves open in conditional form (§7: rest/schedule/home-court candidates "may not target pace mechanisms in the cycle-1 forms; such context, if proposed, acts on scoring"). Complying exactly: rest and schedule-density enter as modifiers of *scoring efficiency levels* (points scored/allowed relative to team baseline), never as pace/possession-count mechanisms. Features: days since own prior game (capped), back-to-back indicator, games-in-prior-5-days density, and a road-trip-length proxy (consecutive strictly-prior away games) — all computable from the closed schedule-identity column set (scheduled game date, opponent, home/away, season) valued as-of-cutoff, which is precisely the enumerated set the current-game-deletion receipt retains. Practitioner rationale: this is a *small, stable, near-orthogonal* signal — the kind that survives out of sample precisely because it is boring — and it is orthogonal to anything the score-history-driven null ingredients can encode.

**Information consumed:** strictly-prior scheduled game dates and home/away designations for both teams (as-of-cutoff, never as-played — the contract's postponement precedent is the binding reading: a rest-days feature computed off a postponement-updated date would encode realized facts, so the card pins date semantics to the as-of-cutoff schedule state); no injuries, no minutes, no travel-distance vendor data.

**Functional form sketch.** Additive efficiency modifiers on each team's expected scoring and allowed levels: `E[pts_t] = level_t + β1·b2b_t + β2·f(rest_days_t) + β3·density5_t + β4·roadlen_t (+ mirrored opponent terms)`, β shared across teams (pooled, not per-team — per-team rest effects are unestimable at this N), ridge-shrunk to 0, entering the same declared head as the level features. E1 collects the sum of both teams' modifiers, E2 the difference.

**Estimands helped:** E2 modestly (asymmetric rest is a margin effect), E1 weakly (fatigue may depress both sides' efficiency jointly). Honest prior from the lens: this is a ≤ 1-point-scale mechanism.

**Expected failure mode:** effect sizes in a ~40-game season league with a compressed schedule may be real but *tiny*, and MAE is insensitive to small corrections on a σ≈14–18-point outcome: a true 0.5-point effect moves pooled MAE by a few hundredths at best, likely inside the CI. The most probable outcome is "correct sign, insufficient Δ" — which is a null result, not a scandal, and should be reported as exactly that.

**Kill conditions (receipted):**
- K1: receipted pooled coefficient CIs: if the joint block test (train-refit bootstrap, receipted) fails to exclude zero pooled across folds, kill.
- K2: pooled OOF ΔMAE ≤ 0 vs K0_MATCHED on the claimed estimand(s), uncorrected.

**Coverage vs §2 floors:** rest features are defined for every game whose team has ≥ 1 strictly-prior game in-season; season openers get the card-declared fallback (modifier = 0, i.e. league-typical rest). Full universe retained; floors met. No predicate trimming — trimming openers to avoid the fallback would be exactly the §2-barred convenience move.

---

## Candidate F3-7 — Overtime-inflation expected-value correction for E1 (median-vs-mean and the OT tail, handled explicitly)

**Description.** The settled estimands include OT by definition (§1), and OT is a *conditionally predictable* right-tail event: it occurs when regulation ends tied, which is more likely when the pregame expected margin is near zero, and when it occurs it adds a roughly-known increment to the total. A model trained on settled totals absorbs OT inflation as smeared noise; making it explicit is structure the null cannot represent. Two receipted uses, cleanly separated: (i) an additive expected-OT-points term for E1's *mean* path, `E[OT pts] = P(OT | pregame closeness) × E[pts per OT | historical]`, with both factors estimated from strictly-prior games only; (ii) the MAE/median observation, stated honestly — under MAE grading the optimal E1 prediction is the conditional *median* of the settled total, and since OT is a low-probability upward increment (league OT rates are single-digit percent), the median of the settled distribution sits essentially at the regulation-conditional median: the correct MAE-optimal move is to add *little or none* of the expected OT increment. The candidate therefore registers the OT term with a *freely fitted* (not fixed-at-1) coefficient under the declared pinball-τ=0.5 objective and lets the loss decide how much of the tail to price — the receipt showing that fitted weight is itself the honest measurement of the median-mean gap this contract's metric choice creates, and becomes program knowledge for any future RMSE- or distribution-graded cycle. All inputs are the "legitimately pregame constructions" §1 explicitly protects (historical OT rates; prior-game realized outcomes inside lagged constructions); nothing touches current-game OT, minutes, or duration, and the column-grain deletion receipt passes because only strictly-prior rows feed the term.

**Information consumed:** strictly-prior league/era OT frequency by pregame-expected-closeness bucket (closeness = the arm's own strictly-lagged |μ̂_margin|, a pregame construction); strictly-prior mean OT scoring increment; nothing same-game.

**Functional form sketch.** `Ê1 = base_total̂ + θ · P̂(OT | |μ̂_margin|) · Δ̂_OT`, θ ∈ [0, 1.5] fitted train-only under the declared objective; `P̂(OT|·)` a two-parameter monotone-decreasing curve (e.g. logistic in |μ̂_margin|) fit on strictly-prior seasons; `Δ̂_OT` a train-years scalar.

**Estimands helped:** E1 (its settled definition is the only estimand where OT points enter additively). E2 is nearly OT-neutral (OT resolves ties; its margin contribution is small and sign-balanced) and E3 is defined on the settled winner regardless — no claims there.

**Expected failure mode:** the effect is small by arithmetic — OT probability of order 5–8% times an increment of order 8–12 points is a ≤ 1-point mean effect concentrated in close games — and under MAE the fitted θ may correctly go to ≈ 0, making the candidate a well-executed null. Secondary risk: `P̂(OT|·)` conditions on the arm's own μ̂_margin, so a bad margin model contaminates the OT curve (registered as a dependency in the card's lineage table).

**Kill conditions (receipted):**
- K1: receipted fitted θ with train-refit CI: if θ's CI covers 0 in ≥ 4 of 5 folds *and* pooled ΔMAE ≤ 0, kill — and record the θ receipt as the measured median-mean verdict either way.
- K2: receipted reliability check of the OT-probability curve on train years (predicted vs realized OT rate by closeness tercile, sealed output): monotonicity violated → curve is noise → kill.

**Coverage vs §2 floors:** no universe impact (the term defaults to the unconditional lagged OT rate when μ̂_margin is unavailable under the card's fallback). Floors met.

---

## Candidate F3-8 — Robust input construction: winsorized/asymmetric-trimmed scoring histories feeding the level estimators

**Description.** M-competition and demand-forecasting practice: level estimators fed by *robustified* observations forecast better under outliers than raw-fed ones, because a single blowout contaminates a fixed-λ smoother for weeks. Construct the arm's team scoring-level inputs from winsorized strictly-prior game scores (per-side, clipped at train-years-estimated quantiles, e.g. the 5th/95th of the team-score distribution), so garbage-time-distorted blowouts and rest-the-starters anomalies stop propagating into future predictions at full weight. The null-granted composite ingredients are pinned to bytes and consume raw history; robust-input variants are therefore structurally outside the null (and this is the honest framing: the candidate must beat *raw-fed* ingredients sitting in its own K0, which is exactly the right test of whether robustification adds value rather than merely differing).

**Information consumed:** strictly-prior team game scores; train-years-only clip quantiles (frozen per fold from the training window, never test-informed). No same-game data; deletion receipt unaffected.

**Functional form sketch.** `x̃_{t,s}(g) = clip(x_{t,s}(g), q_lo^{train}, q_hi^{train})` feeding the F3-1 (or standalone) level recursion; the winsorization quantile pair is a card-declared grid of at most 2 preregistered options (e.g. 5/95 and 10/90) to avoid tuning-surface bloat, with the multiplicity pin honored (both variants inside one mechanism family).

**Estimands helped:** E1 and E2, through cleaner level states — and note the alignment: MAE grading rewards median-like robustness end to end, so robust inputs + pinball training is a coherent pipeline, not two patches.

**Expected failure mode:** blowout scores may carry *real* signal about team strength (good teams cause blowouts), and winsorizing could throw away exactly the information that separates the top of the league — robustification helps when outliers are noise, hurts when they are signal. In a 12–15 team league where dominance is real, the latter is live. Also interacts with F3-1: if both register, they are one family (§4 multiplicity pin) and the combined tuning surface must stay small.

**Kill conditions (receipted):**
- K1: pooled OOF ΔMAE ≤ 0 vs K0_MATCHED (uncorrected).
- K2: receipted season-split table: if Δ is negative in the seasons with the widest strictly-prior strength spread (declared in the card as the two train-observable widest-spread seasons, an information-based split) while positive elsewhere, the "outliers are signal" failure is confirmed → kill rather than universe-shop.

**Coverage vs §2 floors:** none — input transformation only; full universe; floors met.

---

## Cross-candidate notes for S32/S33 (from this lens, no rankings of other sources implied)

1. **Natural composition.** F3-2 (shrinkage) → F3-1 (multi-horizon levels) → F3-3 (combination) → F3-4 (variance mapping) → F3-5 (recalibration) is a coherent single pipeline: levels, combined, mapped to probability, calibrated. But the contract's element/family discipline (§4) argues for registering the smallest coherent units as separate mechanisms with frozen family assignments, letting Holm do its job, rather than one mega-arm whose Δ is unattributable.
2. **Where the lens expects the real money:** E3 via F3-4 + F3-5. Brier rewards variance and calibration structure that simple baselines (even strong ones granted to the K0) do not model, whereas E1/E2 MAE improvements against a bytes-pinned public composite will be fought in tenths of a point. Stated as an expectation, not a prejudgment; the gate decides.
3. **Honest global failure mode of this whole slate:** every candidate consumes the same underlying score history; the effective information budget is one 1,491-game panel. The combination-puzzle warning (F3-3 K1) generalizes: if all mechanisms' OOF error vectors correlate > 0.95 with the null's, the cycle's honest outcome is "the public floor is near the information ceiling of lagged scores alone" — a reportable, valuable null under this contract's rules.
4. **Coverage posture:** every candidate above declares the full base universe with card-declared fallbacks (the §2(3) sensitivity row is then identical to the gated row, which is the cleanest possible selection story). None needs a trimming predicate; none touches the per-fold 80% floor.
