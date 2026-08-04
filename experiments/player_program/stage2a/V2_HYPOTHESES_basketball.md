# V2 Hypotheses — Basketball Mechanism and Game Context

**Source:** independent basketball-mechanism reasoning source.
**Evidence:** `EVIDENCE_PACKET_V2.json` (sha256 `3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c`), read-only inspection of `build_projected_exposure.py`, and existence/coverage inspection of frozen data artifacts.
**Lane:** IDEATION ONLY. Nothing fitted, tuned, selected or scored. No arm registered. No artifact modified.

**Target unit for every hypothesis below:** `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, the frozen canonical target. No hypothesis regenerates, restates or re-normalises the target. Where a hypothesis changes a *measure of history*, it changes only the **feature**; the outcome stays frozen.

**Inference spec inherited unchanged:** 2,982 team-game rows / 1,491 game clusters. Chronological folds nested by season; a game never split across folds; game-clustered resampling carrying both team-rows together. Identical rows, weights, folds and target units across `K0_FLAT`, `K0_MATCHED`, the incumbent and every challenger.

---

## 0. Three findings that should govern the whole design

These are prior to any individual hypothesis and constrain which hypotheses are worth an arm at all.

### 0.1 The incumbent's combination rule shrinks the pair signal by exactly one half

Confirmed by direct read of `build_projected_exposure.py:247-331`. Writing `μ̂(t)` for the league prior and `u_i(t) = r_i(t) − μ̂(t)` for a team's trailing deviation:

```
incumbent:  P̂ = (r_A + r_B) / 2  =  μ̂ + 0.5·(u_A + u_B)
```

The coefficient `0.5` is **structural, not estimated**. It arises because `r_i` is a mean of *game* paces (already a two-team quantity) and the two `r_i` are then averaged again.

Clock conservation says the correct coefficient is different. Let `d_i` be the mean game-clock seconds team `i`'s offence consumes per possession against a league-average defence, and `d̄` the league mean. Both teams' possessions fill the same 2,400 regulation seconds, and per-team possession counts are near-equal (packet: `within_game_target_gap_mean = 0.88`), so `n·(d_A + d_B) = 2400`. Defining each team's *neutral* pace `n_i = 2400/(d_i + d̄)` gives an exact, parameter-free identity:

```
1/n_AB  =  1/n_A  +  1/n_B  −  1/n̄
```

whose first-order expansion is `n_AB ≈ n̄ + (n_A − n̄) + (n_B − n̄)` — additive in deviations, coefficient **1.0**, not 0.5.

The identity is not a toy. Mean `duration_sec` over all 238,563 possessions is 15.13 s; `2400 / 15.13 = 158.6` both-team possessions, i.e. **79.3 per team**, against the packet's realised mean of **79.28758**. The clock identity closes to three digits.

The incumbent's `r_i` does approximately estimate a neutral pace (it averages game paces over a schedule whose opponents roughly centre on the league mean), so the incumbent is applying `c = 0.5` where the mechanism calls for `c = 1.0 × ρ`, with `ρ` the reliability of `u_i`. **`c = 0.5` is optimal only under the coincidence `ρ = 0.5`**, and nothing in the construction makes that coincidence likely. This is a one-parameter, strictly nested, cutoff-valid test, and it is the single highest-value thing in this document.

It is also consistent with the packet's own two headline readings: `variance_explained_vs_target = 0.11608` (low, as an over-compressed predictor must be) and `bias_share_of_mse = 0.001874` with the instruction that "a better point estimate must reduce dispersion, not re-centre". A shrinkage-coefficient correction *increases* projection dispersion. It is the only mechanism here that acts directly on the quantity the packet says is the problem.

### 0.2 Within-game differentiation is capped at roughly 1% of residual MSE — decline it

The brief flags that the incumbent gives both teams an identical projection. The packet bounds what that can be worth:

- `between_game_variance = 14.9884`, `within_game_half_spread_variance = 0.1519`, `game_level_share_of_variance = 0.9778`.
- A *perfect* within-game allocator removes at most `0.1519` of the `13.50014` residual variance = **1.13% of residual MSE**.
- At fixed error shape that is `ΔMAE ≈ 2.90325 × (1 − √(1 − 0.0113)) ≈ 0.016` possessions, which propagates at the packet's implied rate (`0.17733`) to **≈ 0.003 turnovers**, against an operational mean absolute propagated error of `0.51744`.

*(Arithmetic on packet-published variance components. Not a measurement, not a fit. Stated so the coordinator can prune, and to be verified before it is relied on.)*

**Design constraint that follows:** every arm must act on the game-level **sum** of the two teams' characteristics, never on their **difference**. Antisymmetric features — home/away advantage, one-sided travel, one-sided rest, one-sided injury — are capped by the number above and are not worth an arm in this wave. The productive reading of "no opponent adjustment" is *not* "differentiate the two teams"; it is "the two teams' ratings are contaminated and are combined by the wrong rule". Both of those are game-level.

### 0.3 The overtime-rescale channel has negligible effect size, despite 33% exposure

The packet elevates `team_games_whose_10_game_window_contains_an_OT_game = 0.3284` with the reading that an OT correction has "~7x the leverage the raw OT count suggests". That is a statement about *exposure*. Effect size per unit of exposure is what decides value, and by counts it is very small:

| | possessions | minutes | possessions / minute |
|---|---|---|---|
| regulation (1,495 games) | 237,129 | 59,800 | 3.965 |
| overtime (66 games, 74 OT periods) | 1,434 | 370 | 3.876 |

Overtime accrues possessions ~2.2% **slower** than regulation, so the incumbent's linear `n_off_poss × 40/game_minutes` rescale is very nearly correct — it understates an OT game's regulation pace by roughly **0.19 possessions**. Diluted through a 10-game window at 33% window exposure, the induced distortion in `r_i` is on the order of **0.006 possessions**. Seven times negligible is still negligible.

*(Arithmetic on possession counts retrieved during coverage inspection. Not a fitted result; the implementer should reproduce it before acting on it.)*

**Consequence:** do not spend an arm on repairing regulation-equivalence. The *selection* channel — OT games were tied late and therefore carry unusual endgame possession behaviour in their regulation portion — survives, but it is a special case of the general game-state mechanism in **A3** and should be handled there, not separately. Per ruling, nothing here creates an overtime-probability arm; no hypothesis below predicts overtime.

---

# CATEGORY A — immediately testable

Historically available, cutoff-valid, complete, reproducible. Only these may become arms.

All A-arms share a common architecture: they modify either the **rating** `r_i` (A2, A3, A4, A5) or the **combination rule** (A1). A1 is on a different axis from the rest and is the only one that is close to orthogonal to the others.

---

## A1 — Pair-combination shrinkage coefficient *(highest priority)*

**Mechanism.** Game possession count is set by total game-clock seconds divided by mean possession duration, and duration is additive across the two teams' offences. Team tempo deviations therefore **add**; the incumbent **averages** them, halving the pair signal by construction. The incumbent is an over-shrunk predictor whose shrinkage factor was never chosen, estimated, or examined.

**Exact formula.** With `μ̂(t)` = the incumbent's own strictly-earlier league mean of `game_pace`, `r_i(t)` = the incumbent's `team_pace_estimate`, `u_i = r_i − μ̂`:

```
identity link:    P̂ = μ̂ + c·(u_A + u_B)
reciprocal link:  1/P̂ = 1/μ̂ + c·(1/r_A − 1/μ̂) + c·(1/r_B − 1/μ̂)
```

`c` estimated by least squares on strictly earlier folds only. Incumbent is exactly `c = 0.5`, identity link. Mechanism endpoint is `c = 1`, reciprocal link. `c = 0` reproduces the league prior.

**Target unit.** Frozen canonical regulation-equivalent team offensive possessions. Unchanged.

**Features.** `r_A`, `r_B`, `μ̂(t)` — no new inputs at all. Every input is already in the incumbent's own prediction path.

**Cutoff-validity evidence.** Strongest available in the wave: the feature set is byte-identical to the incumbent's, which the packet certifies as "lagged by construction". The only new object is the scalar `c`, which must be fitted on strictly-earlier folds.

**Fallback behaviour.** Inherits the incumbent's four tiers unchanged. `c` is estimated once per fold, globally, not per tier (a per-tier `c` is a nested option below). Where the incumbent is unresolved (8 rows) the challenger is unresolved. No new fallback surface is created — a deliberate property, since a new fallback tier would contaminate the `K0_MATCHED` comparison.

**Hyperparameter family (nested, costed once).** One ordered family, one selection cost:
`c ∈ [0, 1.5] continuous` × `link ∈ {identity, reciprocal}` × `tiering ∈ {global c, c per pace_level}`.
Ordered entry: global-identity-`c` first; reciprocal link admitted only if it improves nested CV over identity; per-tier `c` admitted only if it improves over global. Maximum 6 effective parameters, realistically 1.

**`K0_MATCHED` construction.** Identical folds, identical rows, identical four-tier fallback partition (permitted: it reproduces architecture already in the incumbent path), and identical estimation flexibility — *one* fitted scalar per fold — but the fitted scalar is a **global intercept offset**, not a slope on team ratings. No team, opponent, schedule, roster, venue or coaching input. This isolates exactly the quantity in dispute: whether the *pair-deviation slope* carries information beyond a level shift.

**Necessary second comparison.** `K0_MATCHED` is the promotion control per ruling, but a challenger that beats `K0_MATCHED` while failing to beat the **incumbent** has no operational value. Both comparisons must be reported. This applies to every arm below.

**Expected failure mode.** `ĉ ≈ 0.5`. Optimal `c` equals mechanism coefficient × reliability, so if a 10-game trailing window has reliability `ρ ≈ 0.5` for true team tempo, the incumbent is accidentally right and the arm returns nothing. This is a real possibility and the arm should be pre-registered as a two-sided test, not a confirmatory one. A cheap, leakage-free pre-check that would price the arm before it is run: estimate `ρ` by split-half (odd- vs even-indexed games inside each team's trailing window, Spearman-Brown corrected) over strictly earlier games only. If `ρ̂ ≈ 0.5`, deprioritise A1. Secondary failure: `ĉ` unstable across folds, which would itself be informative about window reliability drift.

**Affected error stratum.** All strata, concentrated in `team_window_same_season` (2,762 rows) and in games where `|u_A + u_B|` is large — i.e. mismatch-extreme and both-fast/both-slow games. Should show as improved tail behaviour at `p05`/`p95` (currently −5.875 / +6.1465).

**Expected direction.** If `ĉ > 0.5`: projection dispersion rises, `variance_explained_vs_target` rises above 0.11608, MAE falls. Bias should stay near zero by construction (the fit is centred).

**Overlap risk.** Low against A5, A6. **High against A2, A3, A4** — all three of those raise the reliability of `r_i`, which mechanically raises the optimal `c`. A1 will absorb part of their value if run first, and they will absorb part of A1's if run first. Mandatory design consequence: **A1's `c` must be re-estimated inside every other arm**, and no rating-axis arm may be evaluated against a fixed-`c` incumbent, or it will be credited with A1's gain.

**Leakage risk.** Low but not zero. `c` fitted on the full sample is in-sample shrinkage tuning and is leakage; it must be fold-nested. No realised target-game quantity enters.

**What it changes.** **Total error and calibration.** It rescales the predictive distribution's spread, so it should be assessed with a calibration check (predicted vs realised dispersion), not MAE alone. Not a subgroup reallocation.

---

## A2 — Opponent-schedule deconfounding of the trailing window

**Mechanism.** `r_i` is the mean of the *game* paces of the games team `i` happened to play. Each of those already contains the opponent's tempo. A team that drew a fast slate looks fast. This is classical measurement error in the feature, and measurement error is precisely a variance defect — which is what the packet says the incumbent's error is (`bias_share_of_mse = 0.001874`).

**The confound is materially large here.** Schedule-structure inspection (schedule only, no outcome data): among the 2,230 team-games with a full 10-game same-season window, the window faces a mean of **7.29 distinct opponents** out of 11–14 available, min 3, max 10; **453 of 2,230 windows (20%) see 6 or fewer distinct opponents**. Small-league unbalanced scheduling makes the trailing window a biased sample of the league.

**Exact formula.** Two-pass opponent adjustment (default, closed form, no solver), over `H_i(t)` = team `i`'s strictly-earlier games in the tier the incumbent selected:

```
a_i⁽⁰⁾(t) = mean_{g ∈ H_i(t)} ( p_g − μ̂(t) )
a_i⁽¹⁾(t) = mean_{g ∈ H_i(t)} ( p_g − μ̂(t) − a_{opp(g)}⁽⁰⁾(t) )
u_i       = a_i⁽¹⁾
```

Nested extension — ridge additive decomposition over the same strictly-earlier set:

```
min_{μ,a}  Σ_{g ∈ L(t)} w_g ( p_g − μ − a_{i(g)} − a_{j(g)} )²  +  λ Σ_i a_i²      s.t. Σ_i a_i = 0
```

`u_i` then feeds A1's combination rule with `c` re-estimated.

**Target unit.** Frozen canonical target. Unchanged.

**Features.** `game_id`, `team_id`, `opp_team_id`, `game_date`, `season` (contract schedule, 2,990/2,990) and realised `game_pace` over strictly earlier games only.

**Cutoff-validity evidence.** Packet's corrected availability table, row *"OPPONENT realised game_pace over strictly earlier games"*: coverage 2,982 resolved, `cutoff_valid: true`, basis *"same lagged construction as own history"*. `opp_team_id` verified present with 0 nulls in `master_team.parquet` across all 2,990 rows; schedule identity is fixed before tip.

**Fallback behaviour.** Inherits the incumbent's tiers. Additional degeneracy the incumbent does not have: when an opponent has itself no rating (season openers, expansion teams' first games), `a_opp` is undefined. Fallback ladder must be declared in advance: `a_opp → a_opp` from prior season → `0` (league-average opponent). Because `a_opp = 0` recovers the unadjusted mean, the arm degrades continuously to the incumbent's rating rather than to a new tier — this is required, so that no new fallback partition enters and `K0_MATCHED` stays honest.

**Hyperparameter family (nested, costed once).** `passes ∈ {1, 2, ridge}` × `λ ∈ log-grid` × `w_g ∈ {uniform, exponential half-life h}`. Ordered entry: two-pass/uniform first; ridge admitted only if it beats two-pass; recency weighting admitted only if it beats uniform. `λ → ∞` recovers `a_i = 0` (league mean); one pass with `a⁽⁰⁾ = 0` recovers the incumbent rating exactly. Fully nested on the incumbent.

**`K0_MATCHED` construction.** Same folds, rows, tiers, and the same *count* of fitted quantities, but with all team identity removed: replace `a_i` with a fitted **date-block intercept** over the same lookback window `L(t)` — a quantity with the same estimation flexibility and the same effective degrees of freedom, and no opponent, team or contextual information. Critically, `K0_MATCHED` here must **not** include the team's own pace history: the packet's exclusion list names "basketball" and "opponent", and the whole claim of A2 is that team-identity-resolved history beats a featureless tiered baseline. The incumbent then sits between the control and the challenger, which is exactly the informative configuration.

**Expected failure mode.** The deconfounding is a second-order correction to a quantity averaged over 10 games; with 7.29 distinct opponents the opponent-slate deviation partially self-cancels, so the raw improvement in `r_i` may be small. Worse, the arm's value may show up **entirely** as a larger optimal `c` — i.e. it may be indistinguishable from A1 unless `c` is re-estimated jointly. Third failure: the two-pass adjustment is unstable in the low-support tail (3–4 game windows, 152 rows, `mae 3.17437`, `bias 1.35075`), where each opponent adjustment carries large variance and may make that stratum worse.

**Affected error stratum.** Concentrated in the low-distinct-opponent tail of the window distribution and in the low-support strata (`team_support` 3–4 and 5–9: 152 and 380 rows, MAE 3.17 and 3.06, both with positive bias ~1.15–1.35 — over-projection, consistent with thin windows drawing fast slates early in a season).

**Expected direction.** Reduced dispersion of `r_i` around true tempo → reduced residual variance; and via A1, a higher justified `c`. Should also reduce the positive bias in the low-support strata.

**Overlap risk.** High with A1 (shared channel: reliability of `u_i`). Moderate with A3 and A4 (all three are rating-axis). Low with A5, A6. **Do not run A2 and A4 as independent arms** — see the consolidation note below.

**Leakage risk.** Moderate and the most operationally dangerous in this document. The rating system must be resolved **as of each game date**, using only games strictly earlier. Solving the additive system once per season — the natural, fast, wrong implementation — leaks every future game into every rating. This must be a hard, tested invariant, not a code comment.

**What it changes.** **Total error**, through variance. Also improves subgroup allocation in the thin-window strata. Should not move calibration much on its own.

---

## A3 — Strip non-repeatable game-state contamination from the historical pace measure

**Mechanism.** Realised game pace is not a clean measurement of the two teams' tempo. It contains a large component generated by *game state*, which is unpredictable pregame and does not repeat:

- **Endgame strategic fouling.** A trailing team fouls intentionally in the last two to three minutes. Possessions collapse to a few seconds each and the possession count inflates sharply. Whether this happens depends on the realised score margin.
- **Garbage time.** A decided game is played differently by both benches. `non_competitive_conservative` flags **14,593 of 238,563 possessions (6.1%)** — already computed and frozen in the artifact.
- **Overtime selection.** OT games were tied at the end of regulation, so their regulation portion contains *less* intentional fouling than a comparable close-but-not-tied game. (This is the surviving OT channel; the *rescale* channel is bounded as negligible in §0.3.)

None of this is a stable team property, yet all of it enters `r_i` at full weight. It is variance injected into the feature with no matching signal — again exactly the defect the packet's bias/variance decomposition identifies.

**Exact formula.** For each strictly-earlier game `g`, retain the possession set

```
S_g = { possessions :  non_competitive_conservative = False
                   AND period ≤ 4
                   AND regulation_seconds_remaining > θ
                   AND is_zero_duration = False }
```

and rescale the retained portion to a full regulation game by clock conservation:

```
N_g = |S_g|                       (both teams)
T_g = Σ_{S_g} duration_sec        (game-clock seconds covered by retained possessions)
p_g^strip = (N_g / 2) · (2400 / T_g)
```

Build `r_i` from `p_g^strip` exactly as the incumbent builds it from `p_g`. Because the **frozen target remains the raw regulation-equivalent count**, restore the level with a strictly-earlier additive offset:

```
δ̂(t) = μ̂_raw(t) − μ̂_strip(t)          (both league means over strictly earlier games)
P̂    = μ̂_raw(t) + c·( u_A^strip + u_B^strip )
```

**Target unit.** Frozen canonical target, unmodified. This is emphatically **not** a re-definition of the outcome — only of the historical *feature*. The irreducible game-state component of the target stays irreducible; the arm claims only that the *predictor* is cleaner.

**Features.** From `possessions_raw_v2.parquet`, lagged only: `duration_sec`, `period`, `regulation_seconds_remaining`, `non_competitive_conservative`, `is_zero_duration`, `end_reason`, `offense_team_id`, `game_date`. Verified present with **0 nulls** across all 238,563 possessions, 1,495 games, 2021-05-14 to 2026-07-31 — the full contract span.

**Cutoff-validity evidence.** Packet: *"possession-level end_reason, duration_sec, period — coverage: all contract games — cutoff_valid: ONLY LAGGED"*. The construction uses these only over strictly earlier games. Note the packet's caution that `possessions_raw_v2` carries **no capture timestamp at all**, so cutoff validity rests entirely on the lag argument; that is sufficient here but must be stated in the registration, not assumed.

**Fallback behaviour.** If a game's retained set is degenerate (`T_g` below a floor, e.g. a game with pathological PBP timing), fall back to the raw `p_g` for that game only — a per-game, not per-team, fallback, so it does not create a new tier in the prediction path. Games where the whole set is degenerate revert to the incumbent measure.

**Hyperparameter family (nested, costed once).** `θ ∈ {0, 60, 120, 180} seconds` × `non_competitive filter ∈ {off, on}` × `OT periods ∈ {excluded, included}`. `θ = 0`, filter off, OT included reproduces the incumbent measure almost exactly, so the family is nested. Ordered entry: filter first, then `θ`, then OT handling. 16 cells, one selection cost.

**`K0_MATCHED` construction.** Same folds, rows, tiers and offset structure, with the stripped rating replaced by the **same rating built from a random subset of possessions of matched size** — a placebo strip that removes the same number of possessions with no game-state criterion. This is the honest control: it holds constant the sample-size reduction and the rescaling arithmetic, and isolates the claim that *which* possessions were removed carries information. A featureless-tier control alone would not answer that. Report both this placebo and the standard featureless-tier `K0_MATCHED`.

**Expected failure mode.** Two ways this fails. First, strip too much and `r_i` gets noisier from sample-size loss than it gets cleaner from contamination removal — 6.1% non-competitive plus a 120 s endgame window is roughly 10–15% of possessions, and the trade is not obviously favourable. Second and more likely: endgame fouling is *partly* a stable team property (aggressive-fouling teams, teams that are often trailing), in which case stripping it removes signal along with noise. The placebo control is the only construction that separates these, which is why it is specified above.

**Affected error stratum.** All strata; disproportionately games whose windows contain blowouts or close finishes. Should improve `went_ot = False` (2,850 rows) and `went_ot = True` (132 rows) alike, since the mechanism is about the *window*, not the target game. Per ruling, OT and non-OT downstream diagnostics reported separately; no claim is made about resolving the exposure/outcome mismatch.

**Expected direction.** Reduced residual variance via a higher-reliability `r_i`, and via A1 a higher justified `c`. Level preserved by `δ̂(t)`, so bias should not move.

**Overlap risk.** High with A1 (reliability channel) and moderate with A2 and A4. Low with A5 and A6.

**Leakage risk.** Moderate, with one specific trap: `δ̂(t)` must be computed over strictly earlier games. A single league-wide `δ` computed over the whole sample is leakage of the global level. Also, the stripping criteria must never be applied to the target game's own outcome — that would alter the frozen canonical target and is prohibited.

**What it changes.** **Total error** via variance. Should not change calibration level. Not a subgroup reallocation, though the low-support strata benefit most.

---

## A4 — Mechanistic component reconstruction of the rating

**Mechanism.** Possession count is `2400 / mean duration`, and mean duration is a mixture over how possessions end. Three channels move it in mechanically known directions, and they differ in how *persistent* they are as team properties:

- **Turnovers** end possessions early → more possessions. `end_reason = 'turnover'` is 41,505 of 238,563 (17.4%), matching the packet's `implied_team_tov_rate` mean of `0.17733`. Turnover rate is among the more stable team properties.
- **Offensive rebounds** *extend* a possession → fewer, longer possessions.
- **Fouls and free throws** stop the game clock → the possession consumes less game clock → more possessions per 40 minutes.

A raw trailing pace average weights all channels by however they happened to fire in ten games. Reconstructing the rating from channels weighted by their own persistence should predict better than the raw average, for the same reason component-based projections beat aggregate projections generally.

**Exact formula.** Over the same trailing window the incumbent uses, with all quantities lagged:

```
z₁ = own turnover rate per own possession                 (possessions_raw_v2 end_reason)
z₂ = own offensive rebound rate = oreb / (oreb + opp_dreb) (master_team, lagged)
z₃ = free-throw trip rate = (fta + opp_fta) / possessions  (master_team, lagged)
z₄ = mean own-offence possession duration                  (possessions_raw_v2 duration_sec)

r_i^comp(t) = μ̂(t) + Σ_k β_k · z̃_{i,k}(t)      (z̃ = deviation from the strictly-earlier league mean)
P̂ = μ̂(t) + c·( u_A^comp + u_B^comp ),   u^comp = r^comp − μ̂
```

`β` fitted chronologically on strictly earlier folds.

**Target unit.** Frozen canonical target. Unchanged.

**Features.** As listed. `master_team.parquet` verified: `tov`, `fga`, `fta`, `oreb`, `dreb`, `pf`, `fouls_drawn`, `points_fast_break`, `points_off_turnovers`, `minutes` all present with **0 nulls** across 2,990 rows.

**Cutoff-validity evidence.** Packet: *"team prior-game box aggregates — coverage 2990/2990 — cutoff_valid: ONLY LAGGED"*, with the explicit note that 58 of the 65 columns are realised target-game outcomes. **Additional provenance caution carried forward from the packet's C9 correction:** `master_team` is a retrospective bulk scrape with ten distinct `observed_time` values in two bulk windows; it is cutoff-valid under a **lag** argument only, never a capture argument, and carries revision risk. Any registration must state this.

**⚠ Specific leakage trap this arm walks past.** `master_team.minutes` is team minutes played = 5 × `game_minutes`, which is an **exact overtime indicator** for that game. The possession-unit ruling states that "any function of `game_minutes` used predictively is target leakage". This column is non-null, unremarkable-looking, and one join away from the feature matrix. **`master_team.minutes` must be explicitly excluded from the target-game join**, and the per-possession denominators above must be built from lagged possession counts, never from `minutes`. This should be an enforced invariant, not a convention.

**Fallback behaviour.** A component with insufficient window support falls back to `z̃ = 0` (league-average on that channel), which degrades the arm continuously toward the league prior rather than toward a new tier. No new fallback partition.

**Hyperparameter family (nested, costed once).** One ordered entry sequence — `z₄`, then `z₁`, then `z₂`, then `z₃` — with each component admitted only if it improves nested CV, plus a single ridge penalty `λ` on `β`. `β = 0` recovers the league prior; `z₄` alone with `β` free recovers something very close to the incumbent rating by the clock identity. At most 4 slopes + 1 penalty, one selection cost.

**`K0_MATCHED` construction.** Same folds, rows, tiers, and **the same number of fitted slopes** — but on features carrying no basketball, opponent, schedule or roster content: e.g. slopes on within-fold game-sequence index and on a date-block index. This matches estimation flexibility exactly (which matters most for this arm, since it is the one with real parameter count) while excluding all contextual predictors.

**Expected failure mode — I expect this arm to fail, and I include it deliberately.** Three reasons it should fail, and one reason to run it anyway. It should fail because: (i) `z₄` is near-algebraically the incumbent rating, so the family's first admitted component largely reproduces what already exists and the remaining components are fighting for a residual that A1–A3 have already claimed; (ii) it carries the highest parameter count and the weakest provenance of any A-arm, against a `K0_MATCHED` that now has matched flexibility; (iii) the `master_team` revision risk is real and unquantified. It is worth running anyway because it is the only arm that would tell us *which physical channel* drives residual pace error — a negative result here is a genuine finding that closes the component-decomposition direction for future waves, and it is cheap once A1–A3 are built.

**⚠ Downstream coupling risk specific to A4.** The operational metric is turnover-team MAE = possessions × turnover rate, through the frozen scorer. `z₁` is a lagged turnover rate. Introducing the turnover channel into the *exposure* creates dependence between the exposure model and the downstream rate, and can double-count the turnover signal — flattering or degrading operational MAE for reasons that have nothing to do with possession projection quality. This must be diagnosed explicitly: report the possession-level result and the downstream result separately, and do not promote on downstream MAE alone.

**Affected error stratum.** Diffuse. Most plausibly the low-support strata, where component rates stabilise faster than aggregate pace.

**Expected direction.** Small variance reduction if any; genuine possibility of no effect or a small degradation once `K0_MATCHED` flexibility is matched.

**Overlap risk.** **Highest in the document.** `z₄` overlaps the incumbent rating; `z₁` overlaps A3 (turnover-ending possessions are concentrated in the states A3 strips); the whole arm overlaps A1's reliability channel. See consolidation note.

**Leakage risk.** High relative to the others — the `minutes` trap above, plus the general hazard of joining `master_team` on the target row. Requires the strictest column allowlist of any arm.

**What it changes.** Intended: total error via variance. Realistically: probably nothing, plus a useful negative.

---

## A5 — Continuous cross-season level re-anchoring *(the only bias-dominated stratum)*

**Mechanism.** Everywhere else the incumbent's error is variance. In exactly two places it is **bias**, and they are the same place:

| stratum | rows | clusters | MAE | bias |
|---|---|---|---|---|
| `team_window_prior_season` | 183 | — | 3.69342 | **−2.84451** |
| `season_opener` | 76 | 41 | 4.26806 | **−3.47113** |
| `league_prior_all` (zero team support) | 37 | 26 | 3.90215 | −0.29560 |

A bias of −2.84 possessions (under-projection) on the prior-season fallback is nearly a full standard deviation of the target and is far too large to be noise. The mechanism is that the incumbent carries a team's prior-season pace level forward **un-recentred**, so any league-level pace drift between seasons is transmitted straight into the projection as bias. The hard four-tier switch also throws away same-season information whenever `n_same < 3`, and blends nothing: the packet's own assumption list notes "prior-season history is used only as a fallback and never blended with same-season history".

**Exact formula.** Replace the hard switch with a continuous empirical-Bayes blend:

```
r_i(t) = [ n_s·m_s(i,t)  +  κ_p·( m_p(i) + Δ̂(t) )  +  κ_l·μ̂(t) ] / ( n_s + κ_p + κ_l )

n_s      = # strictly-earlier same-season games for team i, capped at WINDOW_K
m_s      = their mean game_pace
m_p(i)   = team i's prior-season trailing-10 mean
Δ̂(t)     = league level shift, current season vs prior season:
             if the current season has ≥ G_min strictly-earlier league games:
                 Δ̂(t) = μ̂_season(t) − μ̄_{season−1}
             else:
                 Δ̂(t) = extrapolation from prior season-to-season league deltas, or 0
```

`Δ̂(t)` is the term that removes the −2.84 bias: it re-anchors carried-forward prior-season history onto the current season's own emerging level.

**Target unit.** Frozen canonical target. Unchanged.

**Features.** `game_date`, `season`, `team_id` (schedule, 2,990/2,990) and lagged `game_pace`. No new data source.

**Cutoff-validity evidence.** All inputs are the incumbent's own, plus league means over strictly earlier games and strictly earlier seasons. Nothing new is introduced.

**Fallback behaviour.** This arm *is* a fallback redesign: it removes the discontinuity rather than adding a tier. As `κ_p, κ_l → 0` with `n_s ≥ 3` it recovers level 1; as `n_s → 0` and `κ_l → 0` it recovers level 2 plus the drift correction; as `κ_p → 0` it recovers level 3. The incumbent is the hard-switching limit. Fully nested.

**⚠ Note on `K0_MATCHED` and the tier partition.** The packet establishes that `pace_level > 1` is algebraically identical to `game_no_in_season ≤ 3` (2,982/2,982, zero off-diagonal) and that no design may carry both. **A5 dissolves this partition into a continuous weight.** That is a genuine benefit — it removes the double-counting hazard at the source — but it also means A5's `K0_MATCHED` cannot simply reuse the tier dummies. It must instead carry a **matched continuous structure with no team identity**: the same `n_s`-dependent blend applied between the *league* prior and the *league* prior-season mean, i.e. all the shrinkage machinery with the team-specific terms removed. Anything less and A5 beats a control that still suffers the stratum bias A5 was built to remove, which would be a straw comparison — precisely the failure mode the packet's `why_this_is_not_feature_absorption` note warns about, in mirror image.

**Hyperparameter family (nested, costed once).** `κ_p ∈ grid` × `κ_l ∈ grid` × `G_min ∈ {30, 60, 120}` × `Δ̂ extrapolation ∈ {off, on}`. `Δ̂ = off` and `κ` at the hard-switch limits recovers the incumbent. One selection cost.

**Expected failure mode.** The `Δ̂` extrapolation branch is estimated from **five season transitions**. That is not enough data to extrapolate a drift, and I expect the extrapolation branch to be unstable and to be rejected by nested CV — which is why it is specified as a switchable option nested on `off`, not as a required component. The blend itself (`κ_p`, `κ_l`) should survive; the extrapolation probably should not. Second failure mode: the affected strata total 259 of 2,982 rows (8.7%), so even a complete removal of the bias moves total MAE by a bounded amount. This arm should be pre-registered as a **subgroup and calibration** arm, and judged as one.

**Affected error stratum.** `team_window_prior_season` (183), `season_opener` (76 rows / 41 clusters), `league_prior_all` (37), `team_support` 3–4 (152) and 5–9 (380). Also `by_season` 2021 (`bias +0.72021`, the worst seasonal bias) and 2026 (`bias −0.26668`, the worst seasonal MAE at 3.12151).

**Forward-looking operational argument.** The league is expanding: `team_cities.csv` shows Golden State entering 2025 and Portland and Toronto entering 2026; team counts by season are 12, 12, 12, 12, 13, **15**. An expansion franchise has *no* prior season, so level 2 is unavailable and its first games fall to level 3 — the worst stratum in the table (MAE 3.90215, zero team support). The historical row count understates this arm's value in the seasons the model will actually operate in.

**Expected direction.** Bias in the fallback strata moves from −2.84 toward 0. Total MAE improves modestly. Calibration in the cold-start region improves materially.

**Overlap risk.** Low with A1, A2, A3, A4 — it is the only arm on the level/bias axis. It does interact with A2's opponent fallback (both must handle ratingless opponents), so their fallback ladders must be specified jointly.

**Leakage risk.** Concentrated in one place: `μ̂_season(t)` must be a **strictly-earlier** within-season league mean. Computing the current season's league mean over all its games — the obvious and fast implementation — leaks the season's realised level into every projection in that season and would produce a spectacular, entirely fake improvement. Given that this arm's whole claim is about season level, this is the single most consequential invariant in the document.

**What it changes.** **Subgroup allocation and calibration**, with a modest total effect. Explicitly not a total-error arm.

---

## A6 — Venue heterogeneity, travel and time-zone burden *(included expecting failure; cheap closure)*

**Mechanism.** Two separable claims. (i) *Venue*: individual arenas may host systematically faster or slower games — floor, rim, sightlines, crowd, local scorekeeping conventions in the PBP feed from which possessions are derived. (ii) *Travel burden*: cumulative travel and time-zone disruption depress tempo.

**Why the honest version is game-level.** A global home-court term is **unidentifiable** at the game level — every game has exactly one home team, so a constant home increment is a pure intercept shift with zero effect on any projection. Only *per-venue heterogeneity* can do anything. Likewise, travel applied antisymmetrically (road team tired, home team fresh) is a within-game reallocation and is capped by §0.2 at ~1% of residual MSE. The only version worth testing is the **sum** of the two teams' burdens as a game-level term.

**Exact formula.**

```
P̂ = μ̂ + c·(u_A + u_B) + v̂_{venue(g)} + γ₁·( trav_A + trav_B ) + γ₂·( |tzΔ_A| + |tzΔ_B| )

trav_i  = haversine( venue of team i's previous game, venue of this game ) in 1000 km
tzΔ_i   = UTC-offset difference between those two venues, in hours
v̂_venue = heavily shrunk per-venue increment, estimated over strictly earlier games only
```

**Target unit.** Frozen canonical target. Unchanged.

**Features.** `data/reference/team_cities.csv` — verified present: 16 rows, columns `team_id, abbreviation, franchise, first_season, last_season, city, arena, lat, lon, elevation_ft, timezone`, covering all 15 franchises across 2021–2026. Joined with `is_home` (`master_team.parquet`, 0 nulls, exactly 1,495 home and 1,495 away rows) and schedule dates.

**Cutoff-validity evidence.** Packet's `CORRECTED_now_available` block: venue/travel/elevation/time zone are **Category A**, `cutoff_valid: true`, basis *"static reference; venue is schedule-determined and known pregame"*. This corrects the v1 verdict of ABSENT, which the packet records as a coordinator error. Travel and time-zone deltas derive from prior-game venue and current-game venue, both schedule-determined.

**⚠ Two concrete join hazards found by inspecting the file.** (i) `team_id = 1611661317` appears **twice** (PHO 2021–2024, PHX 2025–, same arena and coordinates). A naive join on `team_id` alone fans out 1:m and silently duplicates team-game rows. The join must be on `(team_id, season)` respecting `first_season`/`last_season`. (ii) `last_season` is a float column with nulls for current franchises (`2024.0` vs empty); a null-unsafe range filter drops every current team. Both are silent-corruption failures, not errors.

**Fallback behaviour.** Season-opening games have no previous venue → `trav = tzΔ = 0` (nested at the null hypothesis, not a new tier). Venues with fewer than a support threshold of strictly-earlier games get `v̂ = 0`.

**Hyperparameter family (nested, costed once).** Ordered entry `γ₁`, then `γ₂`, then `v̂` with a single shrinkage `λ_v`; each admitted only on nested-CV improvement; all-zero recovers A1 exactly. 3 parameters + 1 penalty, one selection cost.

**`K0_MATCHED` construction.** Same folds, rows, tiers and the same number of fitted slopes on non-contextual indices (fold sequence index, date-block index), with all venue, travel, schedule and geographic content excluded — venue and travel are named explicitly in the packet's exclusion list.

**Expected failure mode — I expect this arm to fail on all three sub-terms, and I say so in advance.**

- **Elevation is a dead feature and should not be built at all.** The file's actual range is 20 ft (Chase Center) to 2,030 ft (Michelob ULTRA Arena), with only three venues above 1,000 ft (Las Vegas 2,030, Phoenix 1,090, Atlanta 1,010). There is no genuine-altitude WNBA venue — nothing remotely like the Denver case that motivates the altitude literature. A feature with this little physiologically meaningful range cannot carry signal. **Drop it from the family.**
- **The fatigue channel is already empirically flat in the residual.** The packet's corrected within-season rest strata are 2.98238 (7+), 2.97065 (0–1 b2b), 2.95031 (3), 2.94842 (4–6), 2.77953 (2) — a span of 0.20 MAE with **no monotonic gradient**, and biases between +0.11 and +0.50 with no ordering. The packet withdrew the "7+ days rest" stratum as a rest effect and withdrew the schedule-gap-staleness hypothesis that rested on it. Travel is a weaker, noisier proxy for the same channel that rest already fails to show.
- **Venue heterogeneity is largely absorbed.** A team's own `r_i` already averages its home and away games; a per-venue term must beat that from ~15 arenas with shrinkage.

**Why include it anyway.** Availability here was *corrected* — v1 wrongly called it absent, and the packet flags this as a coordinator error. Leaving it untested preserves an open question that will otherwise be re-raised in every future wave. It is the cheapest arm in the document (static 16-row join, three parameters, no new pipeline), and a clean null closes the geographic and fatigue direction with evidence rather than by assertion. Register it as a **closure arm with a pre-declared expectation of no effect**, so a null is a result rather than a disappointment.

**Affected error stratum.** Nominally the b2b and long-road-trip rows; realistically none.

**Expected direction.** No effect. Pre-declared.

**Overlap risk.** Low with everything. `v̂_venue` mildly overlaps `r_i` (a team's home games are in its own window).

**Leakage risk.** Lowest in the document — static reference data, no realised outcomes. The `v̂` increments must still be estimated on strictly earlier games only.

**What it changes.** Expected: nothing. If anything, subgroup allocation only.

---

## Consolidation note — how these should actually be run

Six arms is more than the mechanism count justifies, because four of them (A1–A4) act through one shared channel: **the fidelity of the pair signal**. Run independently they will cannibalise each other and produce an incoherent promotion record.

The distinct mechanisms are really **three**:

1. **Combination rule is wrong** (A1) — the only claim on the combination axis, the only zero-new-input arm, and the only one that acts directly on dispersion, which is what the packet says the error is. **Run first, alone.**
2. **The rating is contaminated** (A2 opponent slate, A3 game state, A4 component mixture) — one axis, three candidate contaminants. Run as a **single nested family with `c` re-estimated at every step**, in the order A3 → A2 → A4 (cleanest mechanism and lowest parameter count first, weakest provenance and highest parameter count last), each admitted only on nested-CV improvement over the previous. One selection cost for the whole family.
3. **The level is wrong in the cold-start region** (A5) — a genuinely separate axis, a genuinely separate stratum, judged on subgroup and calibration rather than total.

A6 sits outside all three as a pre-declared closure arm.

If only one arm can be afforded, it is **A1**: one parameter, zero new inputs, the strongest cutoff-validity story available, exactly nested on the incumbent, and it tests a coefficient that was never chosen by anyone.

---

# CATEGORY B — high-value but unavailable

Not eligible as arms. Recorded so the current inventory does not narrow the scientific question, and sized honestly.

## B1 — Coaching identity and coaching-change events *(highest value in Category B)*

**Missing input.** No coaching source exists anywhere in the repository; the packet records a verified `*coach*` sweep over `data/` returning nothing.

**Why it matters.** Pace is among the most coach-determined properties in basketball — more so than shooting or rebounding, which are personnel-driven. A coaching change is a **structural break the trailing window cannot see and the prior-season fallback actively transmits backwards**: carrying a team's prior-season pace forward under a new coach is not a weak signal, it is a wrong one. This is not a generic wish. It targets the one stratum in the entire packet where **bias, not variance, dominates** — `team_window_prior_season` at bias −2.84451 and season openers at bias −3.47113. A5 attacks that bias with a league-level drift term because that is all the data supports; a coach-change indicator would attack it at the level where the mechanism actually lives.

**Minimum viable collection.** A hand-maintained `(team_id, season, head_coach, first_game_date, is_new_coach, prior_team)` table. Fifteen franchises × six seasons is on the order of **80 rows**, fully documented in public record, constructible in a single session.

**Prospective-only?** **No** — retrospectively constructible for the full 2021–2026 span. This is the only Category B item with that property, which makes it far and away the best return on collection effort.

**Expected value.** High, and unusually well-targeted: a stratum with a known 2.8–3.5 possession bias, an identified mechanism, and a cheap complete backfill.

## B2 — Pregame availability feed with observation timestamps

**Current state, with a refinement to the packet's ruling.** The packet establishes availability (`injury_history.csv`, 8,340 rows, 2021-01-07 to 2026-07-29, full contract span) but not cutoff validity, on the grounds that there is no observation timestamp. Inspection sharpens this into two distinct regimes, which should not be treated alike:

| category group | rows | cutoff assessment |
|---|---|---|
| `missed_game_other` (3,131), `missed_game_injury` (2,242) | 5,373 | **Not usable as dated.** These are derived from post-hoc transaction listings; a row dated on a game date records that a player *did* miss that game — a realised target-game outcome, not a pregame signal. Only strictly-earlier-dated rows are admissible, and even those inherit retrospective-compilation risk. |
| `signing`, `waiver`, `trade`, `draft`, `retirement`, `waiver_claim`, `contract_suspension`, `front_office`, `contract_conversion` | 2,967 | **More defensible.** These are announcement-dated events, and the date is plausibly the date the information became public. Still lacks an observation timestamp; still `source_page = bbref_transactions_*.html`, a retrospective scrape. |

**Why it matters — and an honest downward correction.** The packet's stated rationale is that "a missing primary ball-handler plausibly shifts a team's possession rate". I would rate this **medium, not high**, on mechanism grounds: at team level a replacement player mostly plays at *team* tempo, because tempo is set by scheme, defensive rebounding and shot-clock discipline rather than by any one player's usage. The exception is real but narrow — losing a primary ball-handler who initiates in transition. The packet's own `unavailable_but_potentially_valuable` framing is right that this belongs on a roadmap; I would not rank it above B1.

**Minimum viable collection.** (i) An audit determining whether `date` is an event date or a compilation date, by checking a handful of rows against independently dated public announcements — this is cheap and would settle the packet's open `cutoff_validity_asserted` gap for the transaction regime. (ii) Persist `data/injury_capture/` forward from 2026-07-30 **with capture timestamps**, which is the only path to a genuine pregame feed.

**Prospective-only?** The transaction regime is potentially retrospective-usable if the audit succeeds. The availability regime is **prospective-only**.

**Expected value.** Medium. Concentrated in a small number of games with a genuinely absent primary initiator.

## B3 — Shot-clock and play-type tracking

**Missing input.** `possessions_raw_v2` carries possession start/end seconds and durations but no shot-clock-at-release, no transition/half-court tag, and no play-type classification.

**Why it matters.** It would let A3 and A4 separate *deliberate* tempo (a team choosing to use 18 seconds) from *forced* tempo (a team shooting early because it is trailing, or late because the defence took away the first option). That distinction is the difference between a stable team property and game-state noise, and it is exactly the boundary A3 currently has to approximate with score-margin and clock-remaining proxies.

**Minimum viable collection.** Shot-clock remaining at shot attempt, plus a transition flag, at possession level. Derivable in principle from richer PBP or tracking feeds if one can be licensed.

**Prospective-only?** No, if an archival enriched PBP source can be obtained; otherwise yes.

**Expected value.** Medium-high, but contingent — its value is mostly as a sharpener for A3/A4 rather than as a standalone channel.

## B4 — Referee crew assignments

**Missing input.** Packet: `data/ref_assignments/` overlaps **0 of 1,495** contract games; `officials_master.csv` carries no `game_id` join at all.

**Why it matters.** Officiating crew is a genuine, well-documented driver of foul rate, and foul rate is one of the three mechanical channels in A4 — fouls stop the game clock and therefore raise possessions per 40 minutes. Crew assignment is announced pregame, which makes it *structurally* an ideal cutoff-valid feature: known before tip, not a team property, not absorbed by `r_i`.

**Minimum viable collection.** A `(game_id, official_1..3)` join key. The identities may already be present; what is missing is the join.

**Prospective-only?** Unclear — depends on whether the existing `officials_master.csv` can be keyed retrospectively. Establishing that is a cheap first step and should precede any collection effort.

**Expected value.** Medium. Mechanically clean and genuinely orthogonal to everything in Category A, which is rare here. Its independence from the pair-signal channel is its main attraction.

## B5 — Announced starting lineups and rest designations

**Missing input.** No captured pregame lineup feed; realised lineups are target-game outcomes. (`possessions_raw_v2` does carry realised on-court lineups — `off_p1..off_p5`, `def_p1..def_p5`, `lineup_valid_ten` at 238,060 of 238,563 — but for the target game these are outcomes, and lagged they add little beyond what `r_i` already contains.)

**Why it matters.** Distinguishes a rested-starters game from a full-strength one before tip — the single most actionable pregame personnel signal, and the one case where the B2 mechanism is unambiguous.

**Minimum viable collection.** Capture pregame lineup postings with timestamps.

**Prospective-only?** **Yes**, strictly.

**Expected value.** Medium, and only from the date capture begins.

## B6 — Market total with history

**Missing input.** `data/odds_capture/` covers 2026-07-31 to 2026-08-06, after the modelling span.

**Why it matters.** A market total is an external consensus pace signal that aggregates information this model cannot see, including injury news and rotation intent.

**Prospective-only?** **Yes.**

**Expected value.** Probably high in raw predictive terms — and I would still deprioritise it. The packet's caution is correct and worth restating in stronger form: a market feature changes what the component *is*. `team_possession_prior` would stop being a pace projection and become a market-tracking model, and every downstream claim about mechanism would become a claim about market efficiency instead. That is a different research programme, not an improvement to this one.

## B7 — Pair-specific (head-to-head) style-mismatch effects — *conditional, blocked*

**Status.** The packet marks head-to-head coverage **UNRESOLVED** (70.2% vs 85.1%, not explained by denominator) with an explicit instruction that no figure may be quoted until independently reproduced. **No coverage figure is quoted here.**

**Why it matters.** In a 12–15 team league, teams meet repeatedly, and a pair-specific tempo effect (a particular stylistic matchup that reliably produces a fast or slow game) is mechanically plausible.

**Why it is blocked rather than proposed.** Its feasibility depends entirely on the disputed coverage number, and the number of estimable pair effects grows as `n_teams²` against a fixed row count. **This is deliberately not proposed as a Category A arm**, even though its inputs exist, because doing so would require quoting a figure the packet forbids quoting.

**Minimum viable resolution.** Reconcile the head-to-head coverage discrepancy directly with the originating source, as the packet instructs. Note that a *non-pair* style-mismatch interaction — a term in `|u_A − u_B|` or in the summed component profile from A4 — needs no head-to-head history at all and could be tested inside A4's family. That is the version to reach for if the interaction question becomes pressing before the coverage dispute is settled.

**Expected value.** Unknown and unpriceable until the coverage figure is reconciled.

---

## Compliance record

- Nothing fitted, tuned, selected, or scored. No model run, no accuracy or calibration number computed.
- Arithmetic performed and labelled as such: the within-game variance ceiling (§0.2) from packet-published variance components, and the overtime accrual rate (§0.3) from possession counts obtained during coverage inspection. Both flagged for verification before reliance.
- Read: `EVIDENCE_PACKET_V2.json`; `build_projected_exposure.py` (read-only); existence/coverage/value-domain inspection of `possessions_raw_v2.parquet`, `master_team.parquet`, `team_cities.csv`, `injury_history.csv`, and schedule structure from `master_team` identity columns.
- **Not read**, per protocol: `HYPOTHESES_*.md`, `SYNTHESIS.md`, `PACKET_ADDENDUM_coordinator.md`, `CORRECTION_ADDENDUM.json`, `EVIDENCE_PACKET.json` (v1), `PHASE0A_RESOLUTION.md`. Also avoided as prior-work adjacent: `GENERATION_ORDER.json`, `build_evidence_packet*.py`, `build_correction_addendum.py`.
- No file modified, nothing registered, no git write, Arm D untouched, turnover scorer untouched, registry untouched, canonical artifacts untouched. No overtime-probability arm proposed.
- No head-to-head coverage figure quoted.
