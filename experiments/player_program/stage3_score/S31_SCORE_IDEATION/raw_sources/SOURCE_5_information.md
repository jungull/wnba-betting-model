# SOURCE 5 — INFORMATION AUDITOR
**Node:** S31_SCORE_IDEATION · cycle-2 score family · ideation wave, source 5 of N
**Lens:** what pregame information exists under the contract's cutoff rules that a season-average or trailing-window baseline provably discards.
**Sole input:** `CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md` (frozen ideation edition) + this source's own prompt. No other file was read.
**Bound by:** §8 cutoff rules (strictly-lagged own data; schedule identity as-of-cutoff; no market fields; no availability without T0 provenance); §7 conditional cycle-1-null clause (rest/schedule/home-court candidates act on scoring, never on pace mechanisms in cycle-1 forms); the generic identification bullet (any scale/identification indeterminacy must register its constraint); §5 covariance obligation for any side-separate or aggregated construction.

---

## Part I — The audit: pregame information sets that exist under the contract

First principles. At the declared cutoff for a game cluster g = (home team H, away team A, scheduled date d, season s), the admissible information is exactly:

**I1. Own strictly-prior settled outcomes.** For every team, the full sequence of its strictly-prior games: points for, points against, settled margin, win/loss, season label of each — from owned committed data (the contract names `master_team.parquet` pts/opp_pts as the settled-outcome source). This is a *sequence with tags*, not a bag of numbers.

**I2. Strictly-prior box/possession internals.** Owned possession and score-composition data (the contract's "efficiency inputs: strictly-lagged constructions from owned possession/score data"; `possessions_v2/` is named as corroborating). Field-level admissibility is governed by the F13 inventory (5 CUTOFF_VALID, 37 CUTOFF_UNPROVEN at its writing): any UNPROVEN field an arm consumes must first be promoted by a receipted S37 cutoff-validity measurement. Every mechanism below that touches composition channels is therefore written **conditionally on that promotion** and names its degradation if promotion fails.

**I3. The opponent tag on every prior observation.** Each strictly-prior game row carries who it was played against. Joining that tag to the *opponent's* own strictly-prior history yields the full league-wide bipartite results graph up to the cutoff. This is enormous relative to what a trailing average keeps.

**I4. Schedule identity of the upcoming game (closed column set, as-of-cutoff).** Scheduled date, opponent/matchup identity, home/away designation, season — valued as-of-cutoff, never as-played (§1's postponement precedent). Extendable only by S34 adjudication.

**I5. Derived schedule texture.** Computable entirely from I1 dates + I4: rest days for each side, rest differential, games-in-last-k-days density, position within a road/home stand, days since season start, games played so far. All strictly-lagged arithmetic on admissible columns.

**I6. Public league structure.** Season calendar boundaries, league membership, the home-court convention, season-level rule/environment constants. Public, non-market, not game-outcome-derived.

**I7. The verified pace ingredient.** `team_possession_prior_v1.projected_team_off_possessions` — frozen, consumable as-is, regulation-equivalent (so any use inside a full-game estimand needs an explicit lagged OT-inflation treatment; historical OT rates are expressly legitimate pregame constructions per §1).

**I8. Cross-season history and identity continuity.** Franchise identity persists across the 2021–2026 universe; prior-season team aggregates are strictly-lagged by construction. If owned lagged box data carries player identities and minutes (an I2-conditional fact), a roster-continuity proxy is derivable without any availability feed.

**I9. Second and higher moments of the past.** Variance of own scoring/margins, tail frequencies, historical OT rates — all strictly-prior, all admissible, none consumed by a mean-only baseline.

**Excluded by contract, restated so no mechanism below leans on them:** market odds anywhere (features or coverage predicates); injury/lineup/availability for 2021–2026 (no T0-provenanced store covers the window); every same-game realized quantity.

### What a trailing-window average actually keeps

A season-average or EWMA of team scoring is (approximately) a single exchangeably-weighted scalar per team per side. It provably discards, from the sets above:

1. the **opponent tag** on every observation (I3) — 12 points allowed to the league's best defense counts the same as 12 to its worst;
2. the **venue tag** on every observation (home/away of each *past* game, I1×I4-type info) — pooled means mix two different data-generating conditions;
3. the **date spacing** of observations and of the upcoming game (I5) — rest and congestion context;
4. the **composition** of each scoring total (I2) — a 3PT-heavy 84 and a paint-heavy 84 are identical to the average;
5. the **within-window ordering** beyond geometric decay — trend/trajectory is collapsed into level;
6. **cross-season information modulated by continuity** (I8) — either ignored or blended at a fixed rate blind to whether the team is the same team;
7. the **second moment** (I9) — dispersion, which is irrelevant to a mean but decisive for a probability (E3);
8. the **pairwise structure of the upcoming matchup** — averages enter additively; any style-interaction term is discarded by construction.

The K0 null-strength floor (§4) means each mechanism must add value *beyond the frozen public composite's own ingredients*, not beyond an intercept. Each proposal below is therefore framed as recovering one of the eight discarded channels, orthogonal to a pace×efficiency level estimate.

---

## Part II — Candidate mechanisms

Conventions for all candidates: unit is the game cluster; folds are the five D006 expanding folds; every kill diagnostic named is a **receipted sealed-run output** (§4(c)); any side-separate construction reports per-side residual variances, home/away residual covariance and corr(e_home, e_away) (§5); no floor/bar values are referenced in any kill, stop rule, or grid choice (§4). Coverage predicates are information-based and cutoff-valid only.

---

### M1. Schedule-deconvolved efficiency (two-way opponent adjustment)

**Information-theoretic story.** The baseline's trailing mean treats every observation as exchangeable, discarding the opponent tag (audit item 1). Points scored are a convolution of own offense with the faced defenses; a raw average is biased for any team whose realized schedule-to-date is unrepresentative — systematically so early in the season and around unbalanced stretches. The league results graph (I3) identifies the deconvolution.

**Exact lagged information.** Strictly-prior team-game rows: points for/against, opponent tag, venue tag, season; optionally per-100-possession rates using strictly-lagged possession counts (I2, CUTOFF_VALID fields only, else raw points).

**Functional form.** At each cutoff, fit on strictly-prior rows a ridge-regularized two-way model: `pts_{ij} = μ + o_i − d_j + η·home_i + ε`, teams' offense effects o and defense effects d shrunk toward zero, refit (or recursively updated) per prediction date within the training discipline. Predictions: E1 = (μ̂ + ô_H − d̂_A + η̂) + (μ̂ + ô_A − d̂_H); E2 from the difference; E3 via a monotone link on E2 (link calibrated on train-years only). **Identification constraint (registered per §7 generic bullet):** o and d are separately identified only up to a shared constant; register sum-to-zero constraints over teams within season (equivalently, absorb the level into μ). The ridge penalty and its selection rule are card-pinned.

**Estimands and why.** E1, E2, E3 — this is a level-correction mechanism; it moves both sides' expectations, hence all three. Strongest a priori case is E2/E3, where schedule asymmetry between the two clubs is exactly what an unadjusted average cannot see.

**Expected failure mode.** In a 12–13 team league with a near-balanced long-run schedule, opponent adjustment may be worth little once the season matures; the adjustment's variance cost (estimating ~26 effects from few games) can exceed its bias savings, especially in early folds. Also the public composite's ingredients (carried in K0 as null-granted terms) may already absorb most of the level signal, leaving the *deconvolution increment* small.

**Kill conditions (receipted).**
- K1: pooled OOF ΔMAE(E2) vs K0_MATCHED ≤ 0 AND the receipted per-fold ΔMAE table shows no fold with a 95% bootstrap CI excluding zero → kill (uncorrected, per §4).
- K2: receipted shrinkage-path diagnostic — if the card-pinned selection rule drives the ridge penalty to its grid maximum in ≥ 4 of 5 folds (effects shrunk to ~zero, mechanism degenerate), kill regardless of Δ sign.

**Coverage vs §2 floors.** Predicate: "both clubs have ≥ 1 strictly-prior game in the current season OR any prior-season history" — effectively full coverage (≥ 90% pooled and ≥ 80% per fold trivially satisfied); the ridge prior handles thin early-season data by shrinking to league mean rather than by trimming games. Card-declared fallback for the mandatory all-covered-games row: league-mean effects.

---

### M2. Venue-split retention (team-specific home/away decomposition)

**Information-theoretic story.** Pooled averages discard the venue tag on every past observation (audit item 2). Home advantage in the baseline is at best a single league constant; teams differ in home/road scoring splits (venue environment, travel burden by geography), and each team's ~half-home history estimates its own split. The information is free — it sits in the same rows the average already consumed.

**Exact lagged information.** Strictly-prior team-game rows with home/away tag (I1 + venue tag); season labels for pooling.

**Functional form.** For each team, shrunken venue offsets: `δ_T = shrink(mean(pts | home) − mean(pts | away))`, empirical-Bayes shrinkage toward the league home-advantage constant estimated on strictly-prior data; prediction adds +δ_H/2 to the home side and −δ_A/2-type terms to the away side on top of the K0-carried level (exact split parameterization card-pinned). E2 receives the differential; E1 the sum (near-cancellation expected); E3 via link.

**Estimands and why.** Primarily E2 and E3 — venue effects are margin-shaped almost by definition. E1 registered only if the card argues asymmetric venue scoring (weak prior).

**Expected failure mode.** Team-specific home advantage is a notoriously noisy quantity; with ≤ ~20 home games per team-season the split estimates may shrink to the league constant, which the K0's null-granted ingredients plus a global intercept already capture — leaving Δ ≈ 0. Small-league travel structure may also make δ confounded with schedule texture (see M3; the card must declare which mechanism owns the shared variance if both are registered — family assignment per §4).

**Kill conditions (receipted).**
- K1: receipted shrinkage-weight table — if the posterior weight on the team-specific component is < 0.1 for ≥ 80% of team-seasons (mechanism collapsed to the league constant), kill.
- K2: pooled OOF ΔBrier(E3) ≤ 0 AND ΔMAE(E2) ≤ 0 → kill.

**Coverage vs §2 floors.** Predicate: "team has ≥ 2 strictly-prior home AND ≥ 2 strictly-prior away observations pooled across seasons" — comfortably above both floors; fallback: league-constant home advantage (which is the K0-equivalent behavior, making the sensitivity row honest).

---

### M3. Schedule-texture scoring adjustments (rest, congestion, differential form)

**Information-theoretic story.** The baseline is calendar-blind: it discards the date spacing of past observations and of the upcoming game (audit item 3). Rest days, third-game-in-four-nights congestion, and the *differential* between the two clubs are computable to the day from admissible columns, cost nothing, and plausibly move scoring efficiency (fatigue → worse shooting/defense execution). **Cycle-1 null compliance (§7 conditional clause):** this candidate acts on *scoring*, explicitly not on pace mechanisms in the cycle-1 forms; it never touches the possession prior's construction, and any pace-adjacent variance is left to the K0-carried ingredients.

**Exact lagged information.** I5 derived quantities only: rest days each side (upcoming scheduled date minus each club's most recent strictly-prior game date, both as-of-cutoff), games in trailing 7 days per side, rest differential, all from I1 dates + I4 schedule identity.

**Functional form.** Additive scoring adjustments on top of the K0-carried level: `E[pts_side] += β1·f(rest_side) + β2·congestion_side`, with f a card-pinned saturating bucket map (e.g. {0–1, 2, 3+} days — bucket edges pinned before any fit); E2 consumes the differential `β·(f(rest_H) − f(rest_A)) + γ·(cong_A − cong_H)`; E3 via link.

**Estimands and why.** E2/E3 first (the differential is the clean, asymmetric signal); E1 second (symmetric fatigue could depress joint scoring, a weaker and confounded story).

**Expected failure mode.** WNBA schedule texture is compressed and partially collinear with venue/travel structure (M2) and with strength-of-schedule (M1); the marginal coefficient may be genuine but tiny relative to game-level score noise, giving correct-sign, CI-straddling-zero results that fail the gate. Season-structure quirks (mid-season breaks) create rare long-rest outliers that dominate a linear form — hence the bucket map.

**Kill conditions (receipted).**
- K1: receipted coefficient table — pooled train-refit bootstrap CI (B=2,000 config, §3) for the rest-differential coefficient covers zero in ≥ 4 of 5 folds → kill.
- K2: pooled OOF ΔMAE(E2) ≤ 0 → kill (uncorrected).

**Coverage vs §2 floors.** Rest is computable for any club with ≥ 1 strictly-prior game in-season; season openers lack an in-season rest value. Predicate: "both clubs have ≥ 1 strictly-prior same-season game" — drops only each season's opening slate per team (order 1–2% of clusters pooled; well above 90%/80%). Fallback: neutral-rest bucket for openers, reported in the mandatory sensitivity row.

---

### M4. Score-composition channel decomposition with differential shrinkage

**Information-theoretic story.** The average consumes the scoring total and discards its composition (audit item 4). Total points = Σ channels (2P, 3P, FT), and the channels have sharply different signal-to-noise: attempt *rates* are stable team-style properties; conversion *percentages* (especially 3P%) are noisy. A single trailing mean of totals implicitly shrinks all channels equally, so a lucky 3P% fortnight and a real attempt-mix shift look identical to it. Decomposing and shrinking each channel at its own rate recovers information the pooled average provably cannot represent.

**Exact lagged information.** Strictly-prior per-team channel columns from owned box/possession data (I2): 3PA rate, 3P%, 2PA rate, 2P%, FTA rate, FT% (or the owned store's nearest equivalents) — **conditional on those fields being CUTOFF_VALID or promoted via the receipted S37 measurement (§8)**; plus the frozen pace ingredient (I7) with a lagged historical-OT-rate inflation to full-game scale (legitimate per §1). Degradation if promotion fails: the mechanism is not registrable; no fallback reconstruction is attempted.

**Functional form.** Per side: `E[pts] = posŝ_fullgame · Σ_c ratê_c · valuê_c · pts_c`, where each `ratê_c`, `valuê_c` is an EWMA-style estimate with **channel-specific shrinkage intensity toward strictly-prior league means** (intensities card-pinned or selected train-years-only by a pinned rule). Sides sum to E1, difference to E2, link to E3. **Covariance obligation (§5) applies in full:** per-side residual variances, home/away residual covariance and corr(e_home, e_away) are first-class receipted outputs — the contract's own precedent (per-side improvement is not game-level evidence until covariance is shown) is treated as binding on this arm's claims.

**Estimands and why.** E1 primarily (composition is a total-points story); E2 secondarily; E3 only via the link.

**Expected failure mode.** The null-strength floor: the K0 carries the public composite's frozen ingredients, which already encode a pace×efficiency level. If differential shrinkage mostly reproduces that level, Δ ≈ 0 and the channel machinery is dead weight. Second: regulation-equivalent→full-game rescaling done sloppily injects bias into E1 exactly where the estimand is OT-inclusive.

**Kill conditions (receipted).**
- K1: receipted channel-orthogonality diagnostic — R² of the arm's E1 prediction on the K0's null-granted-ingredient prediction, computed per fold and sealed; if pooled R² > 0.98 AND pooled ΔMAE(E1) ≤ 0, the mechanism reproduced the floor and is killed.
- K2: receipted covariance table — if per-side MAE improves but game-level ΔMAE(E1) ≤ 0 with corr(e_home, e_away) materially negative in the receipt (side gains cancelling), kill the E1 element rather than re-aggregating post hoc.

**Coverage vs §2 floors.** Predicate: "both clubs have ≥ 3 strictly-prior same-season games with channel columns present OR prior-season channel aggregates" — cross-season fallback keeps pooled coverage ≈ full; per-fold 80% floor safe. Missing-channel games take the card's declared fallback (level-only prediction) in the sensitivity row.

---

### M5. Matchup style interaction (own-rate × opponent-allowed-rate)

**Information-theoretic story.** Averages enter any prediction additively; the pairwise interaction of the *specific* matchup is discarded by construction (audit item 8). The opponent tag joined to the opponent's own lagged history (I3) supports "allowed" profiles: how a defense shifts opposing teams' channel mix relative to those teams' own baselines. A 3PT-reliant offense against a 3PT-suppressing defense is a different game than the additive sum predicts.

**Exact lagged information.** Same channel columns as M4 (same CUTOFF_VALID/promotion condition), computed twice: own offensive profile (team's strictly-prior rates, deviation from league) and opponent's allowed profile (opponents-of-opponent deviations, strictly-prior). All constructed from the owned results graph; no external data.

**Functional form.** For each channel: `adj_ratê_c = league_c + a·(own_c − league_c) + b·(opp_allowed_c − league_c)`, with (a, b) fit on strictly-prior seasons (train-years-only), then priced as in M4. The interaction is the b-term; a = 1, b = 0 recovers the additive baseline, making the null nested and the test clean.

**Estimands and why.** E1 and E2 — the interaction moves expected totals and can be asymmetric across sides. E3 only derivatively; not separately registered unless the card argues it.

**Expected failure mode.** Double-counting with M1: opponent-allowed profiles partially re-encode defensive strength, so if both arms are registered the family sits together at S33/S35 and the stricter partition governs (§4). Also "allowed" profiles need more games to stabilize than own profiles (they are second-order statistics); early-fold noise may swamp b.

**Kill conditions (receipted).**
- K1: receipted (a, b) table per fold — if the b 95% train-refit CI covers zero in ≥ 4 of 5 folds, kill.
- K2: pooled OOF ΔMAE(E1) ≤ 0 vs K0_MATCHED → kill.

**Coverage vs §2 floors.** Needs both clubs' opponents to have history: predicate "both clubs have ≥ 5 strictly-prior same-season games OR cross-season profiles" — cross-season arm keeps pooled coverage ≥ 90%; the per-fold floor is the binding check for the earliest fold and the card must show the receipt (dropped-count line, §2.4) at S33.

---

### M6. Continuity-weighted cross-season carryover

**Information-theoretic story.** At every season boundary the within-season average has near-zero sample and the baseline either ignores last season or blends at a fixed rate — blind to whether this year's team *is* last year's team (audit item 6). A roster-continuity proxy derivable purely from owned lagged box data (shared player identities, minutes-weighted, between last season and this season's strictly-prior games) tells us how much last season's team-level statistics should be trusted. Continuity is not availability data: it is arithmetic on already-played, strictly-lagged box rows, so the §8 availability bar is not touched.

**Exact lagged information.** Prior-season team-level aggregates (I1/I2); **conditional** on owned lagged player-game box rows carrying player identity and minutes (an I2 inventory question for S37): minutes-weighted roster-overlap `w_T = Σ_p min(share_p^{s−1}, share_p^{s,prior}) ∈ [0,1]`. Degradation if unavailable: w_T fixed to a train-years-estimated league constant — the mechanism collapses to a standard fixed-rate cross-season blend, which is still registrable but is a different, weaker card.

**Functional form.** `level̂_T = w̃_T · prior_season_T + (1 − w̃_T) · (shrunken within-season estimate)`, with w̃ a card-pinned monotone map of the raw overlap (and of games-played-so-far, so within-season data takes over as it accumulates). Feeds all three estimands through whatever level slot the arm's design has; natural companion to M1's μ/o/d priors.

**Estimands and why.** E1, E2, E3 — it is an early-season information mechanism for the level, hence all three; its value concentrates where every other mechanism is starving.

**Expected failure mode.** WNBA offseasons move coaches and systems, not just rosters; overlap can be high while the style changed (expansion/relocation years break franchise continuity in the label itself). The proxy then confidently imports a stale prior — worst exactly where confidence is highest.

**Kill conditions (receipted).**
- K1: receipted early-season split — pooled OOF ΔMAE(E1) on each fold-season's first quartile of cluster dates (a season-split row already required by §4's secondary metrics) ≤ 0 → kill; this is the only regime the mechanism claims.
- K2: receipted weight-error correlation — Spearman correlation between w̃_T and the signed early-season prediction error, sealed; if high-continuity teams show *larger* absolute early errors than low-continuity teams (correlation contradicting the mechanism's premise, CI excluding zero), kill.

**Coverage vs §2 floors.** This mechanism *raises* effective coverage: it exists to keep early-season clusters that min-games predicates would trim. Predicate: full base universe (first-ever-season clubs get w̃ = 0 and the within-season/league-mean path). Pooled and per-fold floors satisfied at 100%; the mandatory sensitivity row coincides with the gated row.

---

### M7. Dispersion-aware probability mapping (second-moment channel for E3)

**Information-theoretic story.** E3 is a probability, and a probability is a mean *divided by a dispersion*: P(home wins) ≈ Φ(E[margin]/sd[margin]). The baseline discards the second moment entirely (audit item 7), implicitly using one league-constant sd. But margin dispersion varies by matchup — pace, style (3PT reliance ⇒ fatter tails), and team-specific volatility, all estimable from strictly-prior residual/outcome dispersion (I9). Two matchups with identical expected margin and different dispersion have genuinely different win probabilities; a constant-sd map is provably miscalibrated across the dispersion spectrum.

**Exact lagged information.** Strictly-prior game margins/totals for both clubs (I1); each club's strictly-prior margin dispersion (shrunken); optionally 3PA-rate (M4's channel columns, same promotion condition) and the frozen pace ingredient as dispersion covariates; historical OT rates (expressly legitimate) as a small variance inflation.

**Functional form.** E3 = Φ((Ê2)/σ̂_g), Ê2 taken from whatever margin model the arm pairs with (including the K0-carried level — this mechanism can ride on a null-granted mean), and `σ̂_g² = σ0² + λ1·(vol_H + vol_A) + λ2·pace_g` fit train-years-only. **Distributional discipline (§5):** if the arm also emits E1/E2 distributions, CRPS/PIT are sealed secondary endpoints and the K0 must match functional form and dispersion estimation, train-years-only; no promotion rests on them. **Identification note (generic bullet):** mean and dispersion trade off in a probability-only fit; the card registers that Ê2 is frozen from the paired mean model and only σ̂ parameters are free — that is the identification constraint.

**Estimands and why.** E3 alone as the gated element (Brier). This is the purest "information the average discards" candidate: it can leave the mean untouched and still move the probability.

**Expected failure mode.** Game-level margin dispersion differences across WNBA matchups may be small relative to the ~14-point base sd; the 10-bin calibration gain may be real but below Brier detectability at N ≈ 1,491. Also σ̂ overfit on thin team-level dispersion estimates makes extreme-p predictions worse — the tails are where Brier punishes hardest.

**Kill conditions (receipted).**
- K1: receipted variance-calibration slope — regress squared OOF margin residuals on σ̂_g² per fold (sealed diagnostic); if the pooled slope's 95% CI excludes 1 on the low side AND ΔBrier ≤ 0, the dispersion signal is fictitious → kill.
- K2: receipted 10-bin calibration table (already a required sealed output for E3, §4): if the arm's calibration is worse than K0's in ≥ 6 of 10 bins by the sealed table, kill regardless of pooled ΔBrier sign.

**Coverage vs §2 floors.** Dispersion estimates need modest history: predicate "both clubs ≥ 4 strictly-prior games pooled across seasons" — near-full coverage, both floors safe; fallback: league-constant σ0 (the K0-equivalent behavior).

---

### M8. Within-window trajectory (level-vs-trend orthogonalization) — compact candidate

**Information-theoretic story.** An EWMA is a level estimator; it discards the *ordering* of observations beyond geometric decay (audit item 5). A team whose last-10 efficiency is flat at x and a team that climbed monotonically to x have the same EWMA but arguably different next-game expectations (integration of new players, tactical change, season-long conditioning arcs). The slope is the cheapest un-consumed statistic in the window.

**Exact lagged information.** The same strictly-prior scoring/efficiency sequence the level estimate consumes (I1, optionally per-possession via I2 CUTOFF_VALID fields), plus each observation's date/index for the regressor.

**Functional form.** Per side: weighted least-squares slope β_T over the trailing window (window and weights card-pinned), entering as `E[pts] += κ·β_T` with κ fit train-years-only and shrunk hard toward zero. E1/E2 via sum/difference.

**Estimands and why.** E1/E2. Registered honestly as a low-prior, cheap candidate: it is the canonical "momentum" claim, and most momentum claims die.

**Expected failure mode.** Slope on ~10 noisy observations is mostly noise; κ shrinks to zero and the element fails the gate. If κ survives, the likelier explanation is schedule confounding (an easy recent stretch produces both a positive slope and inflated level) — which M1 already models; family adjudication per §4 if both are registered.

**Kill conditions (receipted).**
- K1: receipted κ path — κ's train-refit bootstrap CI covers zero pooled and in every fold → kill.
- K2: receipted confound check — pooled ΔMAE(E1) ≤ 0 once the slope is orthogonalized against the trailing-window opponent-strength mean (the orthogonalized-regressor run is the sealed variant, declared in the card) → kill.

**Coverage vs §2 floors.** Predicate "both clubs ≥ 6 strictly-prior games pooled across seasons" (slope needs points to be defined) with a zero-slope fallback for thinner histories — fallback path keeps pooled coverage effectively full; both floors safe.

---

## Part III — Cross-cutting notes for S32/S33

1. **Orthogonality map.** M1×M5 (opponent strength vs allowed-profiles) and M1×M8 (schedule confounding of trend) share variance; M2×M3 (venue vs travel texture) share variance. If multiple survive ideation triage, family assignments at S33/S35 should group by mechanism per §4, and disputed assignments run both partitions with the stricter result governing.
2. **Every mechanism above is K0-compatible by construction:** each is written as an increment on top of a level slot that the null-granted public-composite ingredients can occupy, so the cannot-host path (§4) should not be needed by any of the eight; no below-floor-null labels anticipated.
3. **Conditionality ledger:** M4, M5, and (partially) M7 depend on channel-column cutoff-validity promotion at S37; M6's full form depends on lagged player-identity box rows existing in the owned store. These are stated as registration conditions, not assumptions.
4. **Nothing above consumes:** market fields, availability data, as-played dates, or any same-game realized quantity; every named kill diagnostic is a sealed-run receipted output per §4(c).
