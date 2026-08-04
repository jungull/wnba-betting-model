# V2 HYPOTHESES — Estimator Structure and Statistical Form

**Source:** independent reasoning source, lens = *estimator structure and statistical form*.
**Lane:** IDEATION ONLY. Nothing in this document was fitted, tuned, selected or scored.
**Task:** can a cutoff-valid improvement to projected regulation-equivalent team possessions reduce
operational turnover-team MAE beyond `team_possession_prior/1`, without degrading calibration or
stability?

---

## 0. Provenance and independence declaration

### 0.1 What I read

| Artifact | Access | Purpose |
|---|---|---|
| `experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json` | read | sole evidence source |
| — sha256 verified | `3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c` | matches the frozen declaration |
| `experiments/player_program/build_projected_exposure.py` | read-only | incumbent implementation, `build_pace()` lines 247–331 |
| `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` | read-only, structural/coverage counts only | field existence and coverage |
| `experiments/player_program/possessions_v2/possessions_raw_v2.parquet` | read-only, schema + coverage counts only | field existence and coverage |

### 0.2 What I did NOT read

I did not open, search, or infer the contents of: `HYPOTHESES_*.md` (any agent),
`SYNTHESIS.md`, `PACKET_ADDENDUM_coordinator.md`, `CORRECTION_ADDENDUM.json`,
`EVIDENCE_PACKET.json` (v1), `PHASE0A_RESOLUTION.md`. Every claim below derives from the V2
packet, the incumbent source, or structural counts I took myself.

### 0.3 What I deliberately did NOT compute

I did **not** compute `Var(projected_team_off_possessions)`, any residual, any fold, any score,
any coefficient. Section 2.1 below shows that a single descriptive scalar decides the ceiling of an
entire hypothesis family in closed form; I have left it unmeasured on purpose, because measuring it
full-sample would pre-empt the in-fold estimate the arm must make. It is named as the arm's first
measurement, not as a finding of mine.

### 0.4 Structural counts I took (existence and coverage only, no model, no accuracy)

**From `team_possession_prior_v1.parquet` (2,990 rows):**

| Fact | Value |
|---|---|
| `pace_level` counts | 1: 2,762 · 2: 183 · 3: 37 · 4: 8 |
| `n_history_games` range by level | L1: 3–10 · L2: exactly 10 · L3: 4–1,300 · L4: 0 |
| `game_no_in_season` range by level | L1: **4–56** · L2: **1–3** · L3: **1–3** · L4: **1** |
| games total | 1,495 |
| games whose two sides sit on **different** `pace_level` | **37** (2.5%) |
| level-1 games with both sides present | 1,366 |
| level-1 between-side support gap `\|n_A − n_B\|` | 0 in **1,174** · 1–2 in **180** · 3–5 in **12** · ≥6 in **0** · max **4** |
| fallback rows (level > 1, n = 228) with ≥1 strictly-earlier **same-season league** game | **184** (81%); ≥5: **154**; ≥10: **92**; zero: **44**; median 8 |

The third row independently reproduces the packet's algebraic-identity finding
(`WITHDRAWN_game_no_in_season`): level 1 spans game numbers 4–56 and levels 2/3/4 span 1–3, with
no overlap. `pace_level > 1` and `game_no_in_season <= 3` are the same partition. I therefore treat
that partition as **one** stratum throughout and never carry both.

**From `possessions_raw_v2.parquet` (238,563 possessions, 1,495 games, zero nulls on all
structural columns used below):**

| Column | Coverage / distribution |
|---|---|
| `is_overtime` (per possession) | 1,434 true (0.601%); 66 games contain ≥1 OT possession |
| `non_competitive_conservative` | 14,593 true (6.117%); per-game share mean 6.15%, p50 2.67%, **p95 23.86%**; 622 games at zero; **395 games (26.4%) above 10%** |
| `lineup_valid_ten` | 238,060 (99.789%) |
| `off_p1..off_p5`, `def_p1..def_p5` | present; nulls 64–281 rows |
| distinct (team, 5-man offensive lineup) cells | **14,272**; possessions per cell p50 **6**, p90 31, max 2,461; **49.6% of all possessions sit in cells with < 50 possessions** |
| `duration_sec` | mean 15.133, sd 7.507, p05 3, p50 15, p95 28, max 86 |
| `end_reason` | defensive_rebound 84,647 · made_shot 82,738 · turnover 41,505 · made_ft_final 22,821 · period_end 6,054 · technical_ft 588 · inferred_flip 200 |
| `possession_kind` | live_ball 236,176 · zero_duration_sequence 1,799 · technical_free_throw_sequence 588 |
| also present | `abs_score_diff_start`, `score_diff_offense_start/end`, `regulation_seconds_remaining`, `is_zero_duration` (2,387), `n_off_oncourt`, `lineup_class` |

The packet's availability table did not enumerate the lineup, competitive-state, or
possession-kind columns. They exist, they are essentially complete, and they are cutoff-valid under
the same lag argument the incumbent already relies on. Several of the hypotheses below exist only
because of them.

**Internal consistency check (arithmetic on published figures, not a new measurement):**
238,563 × 15.133 s ÷ 1,495 games = 2,415 s per game ≈ the 2,400 s regulation clock, and
2,400 ÷ (2 × 15.133) = 79.30 ≈ the packet's `mean_realised = 79.28758`. The possession stream and
the packet's target are mutually consistent, and possessions **tile a fixed clock**. That single
fact drives several of the rulings in §5.

---

## 1. What the packet actually constrains — the structural reading

Before the hypotheses, five constraints the packet establishes that bound every proposal. These
are arithmetic on the packet's own published diagnostics, not new measurements.

### C1 — The error is variance, and the incumbent explains 11.6% of the target

`residual_variance = 13.50014`, `target_variance = 15.27299`, `squared_bias = 0.025335`
(0.19% of MSE). Therefore

```
Var(T − P) = Var(T) + Var(P) − 2·Cov(P,T) = 13.50014
⇒  2·Cov(P,T) − Var(P) = 15.27299 − 13.50014 = 1.77285          … (identity I)
```

Identity **I** is the single most useful algebraic consequence in the packet. It is exploited in
§2.1.

### C2 — Within-game differentiation is worth at most ~0.016 MAE

`between_game_variance = 14.9884`, `within_game_half_spread_variance = 0.1519`,
`game_level_share_of_variance = 0.9778`, `games_with_two_distinct_projections = 0`.

A projection that is symmetric across the two sides of a game cannot explain the within-game
half-spread; it contributes 0.1519 to residual variance unavoidably. A *perfect* asymmetric
predictor would take residual variance from 13.50014 to at best 13.3482. Holding the residual shape
fixed, MAE scales with sd:

```
2.90325 × sqrt(13.3482 / 13.50014) = 2.8869        ⇒ ceiling ≈ 0.016 possessions of MAE
```

**Every hypothesis whose mechanism is "predict team A differently from team B in the same game" is
capped at ≈0.016 MAE (0.56%), or ≈0.003 turnovers downstream.** This is a hard ceiling and it
retires an entire intuitive research direction. It is stated once here and referenced throughout.

### C3 — The downstream exchange rate, and how large a win must be to matter

`mean_abs_propagated = 0.51744` and `implied_team_tov_rate.mean = 0.17733`. Note
2.90325 × 0.17733 = 0.51482 ≈ 0.51744: the propagation is essentially linear at the mean rate.
Therefore

```
Δ(turnover-team MAE)  ≈  0.177 × Δ(possession MAE)        … UPPER bound
```

It is an upper bound because it is attained only if the possession-attributable error component is
perfectly aligned with total turnover error; under any partial independence the realised downstream
gain is strictly smaller. Consequently:

> **To move operational turnover-team MAE by 0.05 requires a possession-MAE improvement of at
> least ≈ 0.28 — a 9.7% reduction on the incumbent's 2.90325.**

No arm below is forecast to reach that alone. Section 6 addresses what follows from that.

### C4 — The bias that does exist is concentrated in 228 rows, and it is a *level* problem

| Corrected stratum | n | MAE | bias |
|---|---|---|---|
| `team_window_prior_season` (level 2) | 183 | 3.69342 | **−2.84451** |
| `season_opener` (corrected, separated) | 76 | 4.26806 | **−3.47113** |
| `league_prior_all` (level 3, zero team support) | 37 | 3.90215 | −0.29560 |
| `team_support 3-4` | 152 | 3.17437 | **+1.35075** |
| `team_support 5-9` | 380 | 3.06164 | **+1.14865** |
| `team_support 10 (full)` | 2,413 | 2.84591 | −0.06474 |
| `team_window_same_season` (level 1) | 2,762 | 2.83751 | +0.36428 |

Two systematic, opposite-signed level errors:

1. **Prior-season history under-projects by ≈2.8**, and season openers by ≈3.5. The league pace
   level moves between seasons and the incumbent transports nothing across the boundary.
2. **Early-season same-season windows over-project by ≈1.2**, decaying to ≈0 at full support.

These are consistent with a league pace level that rises season-over-season and settles within a
season. Together they cover 228 fallback rows plus 532 low-support rows = 760 rows (25.5%).

**Caveat I must state, because it constrains hypothesis A3:** the `team_support` strata are
confounded with time-in-season. Low support *is* early season. The monotone MAE improvement
3.174 → 3.062 → 2.846 is therefore **not** clean evidence that longer windows are better; it is
partly the drift in (2). Any window-length arm must be evaluated with the level-transport arm
already in place, or the two will trade credit.

### C5 — The corrected `days_rest` table shows no exploitable signal

Corrected within-season buckets span MAE 2.77953 (`2` days, n=1,432) to 2.98238 (`7+`, n=101) with
biases 0.108–0.497. A 0.20 MAE range across buckets whose n ranges from 89 to 1,432 is not a
lever. I propose no rest, travel or schedule-density hypothesis. (It is also not my lens.)

---

## 2. CATEGORY A — immediately testable

Six arms. Each is historically available, cutoff-valid under the same lag argument the incumbent
already uses, complete over the resolved 2,982 rows, and operationally reproducible.

**Common to all arms — non-negotiable protocol (see §4 for why):**

- Target unit: `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, the **frozen canonical
  artifact**, unchanged and not regenerated.
- Rows: 2,982 resolved team-games; clusters: 1,491 games. Both reported, never substituted.
- Folds: chronological, nested by season; a game never split; both team-rows in the same fold.
- Resampling: game-clustered over the 1,491 clusters, carrying both team-rows together.
- **P1 (mandatory):** a single additive in-fold L1 recalibration offset, fitted on each fold's
  training portion, applied identically to the incumbent, `K0_FLAT`, `K0_MATCHED` and every
  challenger. Justification and bound in §4.1.
- **P2 (mandatory):** hard-fail assertion that no function of the *target* game's `period`,
  `max_period`, `is_overtime`, `game_minutes` or `regulation_seconds_remaining` reaches any feature,
  weight, fallback branch, arm-selection step or prediction. Historical (strictly-earlier) use is
  permitted and is exactly what `build_pace` already does.

### Notation

For game *g* between teams A and B, on date *t*:

- `p[T,g]` = team T's regulation-equivalent offensive possessions in *g*
  = `n_off(T,g) × 40 / game_minutes(g)` — this is the frozen target when *g* is the target game.
- `π[g]` = `game_pace(g)` = `( p[A,g] + p[B,g] ) / 2` — the incumbent's history element.
- `m[T,t]` = incumbent's `team_pace_estimate`: unweighted mean of the last `K=10` values of `π`
  over T's strictly-earlier same-season games, if ≥ `M=3` exist; else prior season; else the
  cumulative all-history league mean of `π`.
- Incumbent projection: `P[g] = ( m[A,t] + m[B,t] ) / 2`, identical for both sides.
- `L(t)` = a league-level anchor computed from strictly-earlier games (its exact form is A4's
  hyperparameter).

---

### A1 — Deviation gain: the incumbent's projection is a **structurally attenuated** deviation

#### Mechanism

Possessions are a joint property of a game, not of a team. Both the incumbent's history element
`π[g]` and the frozen target `p[T,g]` are approximately `(μ_A + μ_B)/2 + noise`, where `μ_T` is
team T's latent pace level. Write `α_T = μ_T − μ̄`. Then, over a schedule whose opponents average
to the league mean,

```
E[ m[T,t] ]  =  μ̄ + α_T/2 + (1/K)·Σ_i α_{opp(i)}/2   ≈   μ̄ + α_T / 2
E[ P[g]   ]  =  μ̄ + (α_A + α_B) / 4
E[ target ]  =  μ̄ + (α_A + α_B) / 2
```

**The incumbent's projected deviation from the league mean is, in expectation, exactly half the
deviation it is trying to predict.** This is not a bug that was introduced; it is the unavoidable
consequence of estimating a team's level from a statistic that already contains the opponent. Using
own-side `p[T,g]` instead of `π[g]` does *not* fix it — the packet's
`within_game_target_gap_mean = 0.88` shows own-side and game-level pace are nearly the same number,
so own-side history is equally opponent-contaminated.

The fix is **deconvolution**: solve for the team levels jointly and re-expand.

#### Exact formula

Full family (one hyperparameter, ridge penalty `τ`). Over all games with date `< t`, in the fold's
training portion only:

```
minimise over (c, a)     Σ_g  w_g · ( π[g] − c − (a_{A(g)} + a_{B(g)}) / 2 )²  +  τ · Σ_T a_T²
prediction               P_A1[g] = ĉ + ( â_A + â_B ) / 2
```

`τ → ∞` collapses to the league mean; `τ → 0` is exact deconvolution. Under a balanced schedule the
solution has the closed form

```
â_T  =  2 · ( m[T,t] − μ̄ )
P_A1[g] = m[A,t] + m[B,t] − μ̄
        = μ̄ + λ · ( P_incumbent[g] − μ̄ )    with  λ = 2
```

so the whole family is a **single deviation gain** applied to the incumbent's own output:

```
P_A1(λ)[g]  =  μ̄_ref  +  λ · ( P_incumbent[g] − μ̄_ref )
λ = 1  →  incumbent          λ = 2  →  exact deconvolution under balance
```

`μ̄_ref` is the in-fold league anchor (shared with A4). The ridge form additionally corrects
*unbalanced* past schedules (a team whose last 10 opponents were fast); the scalar form does not.

#### Decisive closed-form pre-check

From identity **I** (§C1), for a single fitted gain `β`,

```
β*        = Cov(P,T) / Var(P) = 0.886425 / Var(P) + 0.5
MSE gain  = Var(P) · (β* − 1)²  =  ( 0.886425 − 0.5·Var(P) )² / Var(P)
```

Therefore:

- `Var(P) = 1.77285` exactly ⇒ `β* = 1` ⇒ **the family is worth exactly zero.**
- `Var(P) < 1.77285` ⇒ expand (`λ > 1`); `Var(P) > 1.77285` ⇒ shrink.
- The gain is steeply increasing as `Var(P)` falls: at `Var(P)=1.0` the MSE gain is 0.149
  (≈0.016 MAE); at `Var(P)=0.6` it is 0.573 (≈0.062 MAE); at `Var(P)=1.5` it is 0.012
  (≈0.001 MAE).

**The arm's first action must be to measure in-fold `Var(P)`.** If it lands near 1.77 the arm
should be abandoned before any fit. I have deliberately not measured it (§0.3).

- **Target unit:** frozen canonical, unchanged.
- **Features:** none new. `λ`/`τ` operate on lagged own-history already in the incumbent path, plus
  the in-fold league anchor. Opponent identity of *past* games enters only in the ridge form
  (packet: "OPPONENT realised game_pace over strictly earlier games", coverage 2,982, cutoff-valid).
- **Cutoff-validity evidence:** every input is the incumbent's own lagged history. Ridge fit uses
  only games with date `<` the target date, inside the training fold. No new source.
- **Fallback behaviour:** unchanged tier ladder. For level-3 rows the deviation is ≈0, so the gain
  is inert there by construction — a desirable property.
- **Hyperparameter family:** ONE — `τ` (ridge penalty), with the scalar `λ` as its balanced-schedule
  closed form. Costed once.
- **`K0_MATCHED`:** the incumbent's projection plus a **fitted in-fold intercept only** (one df),
  same folds, same tier ladder, same grid cardinality searched over a null grid. The challenger adds
  exactly one df (the gain). This is the honest control precisely because A1 introduces **no new
  information** — it is pure recalibration, so its control must be recalibration-without-gain.
- **Expected failure mode:** `Var(P)` lands above ≈1.5 because the 10-game window's own sampling
  noise (per-game pace variance ≈15, so ≈1.5 for a 10-game mean, ≈0.75 after averaging two sides)
  already offsets the structural 0.5 attenuation. In that case the incumbent is *accidentally near
  the optimal shrinkage* and the family is worth ~0.001 MAE. I rate this the most likely outcome.
- **Affected stratum:** all of `team_window_same_season` (n=2,762); inert on `league_prior_all`.
- **Expected direction:** `λ̂ ∈ [1.0, 1.3]`, not 2. The theoretical 2 is eroded by window noise.
- **Overlap risk:** HIGH with A3 (any variance reduction in `m` raises `Var(P)` and *reduces* A1's
  payoff — they are substitutes, not complements) and with A4 (both use `μ̄_ref`). Must be
  sequenced after A4 and evaluated jointly with A3, never credited twice.
- **Leakage risk:** LOW. No new source. The one hazard is fitting `τ` or `μ̄_ref` on full-sample
  rather than in-fold data.
- **Changes:** total error and calibration (it rescales the whole prediction distribution). It does
  **not** change subgroup allocation except through the tier-dependent size of the deviation.

---

### A2 — Replace the discrete three-tier ladder with continuous precision pooling

#### Mechanism

The incumbent's ladder is a hard switch. At `MIN_HISTORY_M = 3` same-season games it flips to
level 1 and **discards all prior-season history**, permanently. My counts show 532 rows sit at
level 1 with support 3–9 (`team_support 3-4`: 152, `5-9`: 380) — 17.8% of the data — each throwing
away a full 10-game prior-season window in favour of as few as three noisy same-season games. And
those rows carry bias +1.35 / +1.15 while the discarded prior-season source carries bias −2.84.
**Two oppositely-biased sources, and the incumbent uses exactly one of them at a time.** A
precision-weighted blend dominates either.

The ladder also creates a discontinuity: a team's projection can jump by an arbitrary amount
between its third and fourth game of a season, for no reason connected to basketball.

#### Exact formula

```
μ̂[T,t] = ( n_s · m_s[T,t]  +  γ · n_p · m̃_p[T,t]  +  κ · L(t) )
        / ( n_s            +  γ · n_p              +  κ         )

n_s  = same-season support, min(count of strictly-earlier same-season games, K_max)
m_s  = weighted mean of π over those games          (weights from A3; unweighted if A3 not applied)
n_p  = prior-season support, min(count, K_max)
m̃_p = prior-season mean AFTER level transport       (from A4; = raw prior-season mean if A4 off)
L(t) = in-fold league anchor over strictly-earlier games (window from A4)
γ    ∈ [0,1]   cross-season discount
κ    ≥ 0       league-prior strength, in units of games

then combine sides:  P_A2[g] = ( μ̂[A,t] + μ̂[B,t] ) / 2      (or A1's gain form if composed)
```

`γ = 0, κ = 0, n_s ≥ 3` reproduces the incumbent's level 1 exactly; `γ = 1, κ = 0, n_s = 0`
reproduces level 2; `γ = 0, κ = ∞` reproduces level 3. **The incumbent is a corner of this family.**
That is the property that makes it a fair test: the challenger can only lose by overfitting `γ, κ`,
never by structural mis-specification.

- **Target unit:** frozen canonical, unchanged.
- **Features:** none new. Same-season lagged history, prior-season lagged history, lagged league
  history — all three already exist in the incumbent path; only their *combination rule* changes.
- **Cutoff-validity evidence:** all three components are the incumbent's own inputs. Coverage: the
  incumbent's level counts (2,762 / 183 / 37 / 8) show every resolved row already has at least one
  of the three; a continuous blend cannot resolve fewer rows than the ladder. The 8 unresolved rows
  stay unresolved.
- **Fallback behaviour:** **there is no fallback** — the formula is continuous and degenerates
  smoothly to `L(t)` when `n_s = n_p = 0`. The `pace_level` column becomes a diagnostic label, not a
  switch. This has a compliance consequence, see the `K0_MATCHED` note.
- **Hyperparameter family:** ONE — `{γ, κ}`, a two-parameter shrinkage family. Costed once.
- **`K0_MATCHED`:** the packet's `tier_partition_rule` says a tier partition may appear in
  `K0_MATCHED` only when it reproduces architecture present in the incumbent or challenger path.
  **A2 dissolves the tiers, so its matched control must not carry them.** Construct it as: the
  identical continuous-pooling machinery, identical folds, identical `{γ, κ}` grid and selection
  protocol, with `m_s` and `m̃_p` replaced by the **team-identity-permuted** history — for each
  target row, substitute the history of a different team drawn by a fixed-seed permutation held
  constant within (season, date), and truncated or padded to the recipient's exact support counts
  `n_s, n_p`. This preserves support, date, league drift and every degree of freedom, and destroys
  only *which team*. My counts show this substitution is nearly exact: the between-side support gap
  is 0 in 1,174 of 1,366 level-1 games and never exceeds 4.
- **Expected failure mode:** `γ̂` comes out near 0 — i.e. prior-season pace really is worthless once
  three same-season games exist — and the arm reduces to a small `κ` shrinkage worth ≈0.02 MAE. The
  second failure mode is credit-stealing: much of the +1.2 early-season bias is A4's drift, and if
  A4 is not fitted first, A2 will absorb it as a spurious `κ`.
- **Affected stratum:** `team_support 3-4` (152), `team_support 5-9` (380),
  `team_window_prior_season` (183), `zero_team_support / league_prior` (37). 752 rows, 25.2%.
- **Expected direction:** MAE down on all four strata; overall ≈0.03–0.06 MAE. Bias on the 3–9
  support strata moves toward 0 from above; bias on level 2 moves toward 0 from below.
- **Overlap risk:** HIGH with A4 (they share `L(t)` and the level-2 correction; A4 must be fitted
  first and A2 evaluated conditional on it). MODERATE with A3 (`m_s` is A3's output).
- **Leakage risk:** LOW-MODERATE. `γ` and `κ` must be selected in-fold. The specific hazard is that
  the natural way to write this arm is to compute `L(t)` once over the whole span; that is a
  full-sample leak and must be blocked by construction.
- **Changes:** subgroup allocation primarily (the low-support and fallback strata), with a small
  total effect and a genuine calibration improvement on those strata.

---

### A3 — Window aggregation: weights, effective sample size, and ratio-of-means

#### Mechanism

The incumbent's window is unweighted, capped at 10, and equal-weights every game regardless of how
much information it carries. Three distinct sub-mechanisms, all about *how the window's
observations are combined*:

1. **Recency.** `w_i = ρ^(K − i)`. Trades staleness bias against sampling variance.
2. **Possession-count precision.** A game with 170 possessions carries more information about a
   team's pace than one with 150. `w_i ∝ c_i` where `c_i` is the game's possession count.
3. **Ratio-of-means (the duration reparameterisation).** Because possessions tile a fixed clock
   (§0.4: 238,563 × 15.133 s ≈ 2,415 s/game ≈ the 2,400 s regulation clock), pace is *exactly* the
   reciprocal of mean possession duration. Estimating mean duration by pooling all ~1,600
   possessions in the window and inverting is a **harmonic**, possession-weighted mean of paces —
   a different estimator with a different noise structure and, nominally, ~160× the observation
   count per game.

#### Exact formula

```
weighted mean form:
  w_i     = ρ^(K_max − i) · c_i^ψ                 i indexes the window, most recent = K_max
  m_s     = Σ_i w_i π[g_i] / Σ_i w_i
  n_eff   = ( Σ_i w_i )² / Σ_i w_i²               reported for every row, always

ratio-of-means form:
  m_s^dur = C_reg / ( Σ_i D_i / Σ_i c_i )
            D_i = total regulation offensive-possession seconds in window game i
            c_i = regulation offensive possession count in window game i
            C_reg = the regulation clock constant that reproduces the frozen target's scale
```

Family members: `{ρ ∈ (0,1], K_max ≥ 10, ψ ∈ {0,1}, form ∈ {arithmetic, ratio-of-means}}`.
`ρ = 1, K_max = 10, ψ = 0, arithmetic` is the incumbent exactly.

- **Target unit:** frozen canonical, unchanged. The ratio-of-means form must be rescaled to the
  frozen target's units; the constant is calibrated in-fold, never on the target's realised value.
- **Features:** none new for members 1–2. Member 3 needs `duration_sec` and possession counts from
  `possessions_raw_v2` over strictly-earlier games (coverage: 238,563 possessions, zero nulls on
  `duration_sec`, all 1,495 contract games).
- **Cutoff-validity evidence:** all inputs are the incumbent's own history plus, for member 3,
  possession-level durations of *earlier* games. The packet lists "possession-level end_reason,
  duration_sec, period" as available over all contract games, cutoff-valid ONLY LAGGED — which is
  exactly and only how this arm uses them.
- **Fallback behaviour:** unchanged unless composed with A2. `n_eff` must be reported even for
  fallback rows (it is 0 for level 3 by the packet's own corrected semantics: `league_prior_all`
  has **zero team support**, the 4–1,300 figure being a league count).
- **Hyperparameter family:** ONE — window-aggregation family `{ρ, K_max, ψ, form}`. Costed once.
- **`K0_MATCHED`:** identical weighting machinery, identical grid, applied to the
  **team-identity-permuted** history as in A2, with support truncated to the recipient's exact
  count so `n_eff` matches row-for-row.
- **Expected failure mode:** `ρ̂ ≈ 1` and the recency member is worthless. I predict this explicitly:
  the corrected support strata improve monotonically with *more* games (3.174 → 3.062 → 2.846),
  which is the opposite of what a staleness problem looks like. **But that evidence is confounded
  with season progress (§C4 caveat), so it cannot be used to conclude that longer is better
  either.** The honest prediction is: `K_max` between 12 and 20 beats 10 by a small margin *after*
  A4 removes the drift, and `ρ` contributes nothing. The ratio-of-means member's apparent 160×
  sample-size advantage will largely evaporate because the ~160 possessions inside one game share a
  game-level common factor (§C2: 97.8% of target variance is game-level); its real benefit is the
  Jensen level shift, which P1 absorbs — so I expect it to be **null after recalibration**.
- **Affected stratum:** `team_support 10 (full)` (n=2,413) for `K_max`; all level-1 rows for `ρ`.
- **Expected direction:** small MAE reduction (≈0.02–0.04) from `K_max > 10`; null from `ρ` and
  from `ψ`; null from ratio-of-means after P1.
- **Overlap risk:** HIGH with A1 (substitutes: reducing `m`'s noise raises `Var(P)` and shrinks
  A1's payoff — see A1's closed form). MODERATE with A2 (`m_s` is A3's output). Must not be credited
  alongside A1 without a joint fit.
- **Leakage risk:** LOW for members 1–2. **MODERATE for member 3**: it touches
  `possessions_raw_v2`, which the packet warns "carries no capture timestamp at all", and it is the
  member most exposed to the revision risk in `capture_provenance_caution`. It must also be written
  so that the regulation/OT split of *earlier* games never joins to the target game (P2).
- **Changes:** total error and stability. Not calibration (P1 absorbs the level shift). Not
  subgroup allocation, except that `K_max > 10` cannot act on early-season rows and therefore
  slightly *widens* the gap between low- and full-support strata.

---

### A4 — Level transport: move the anchor across the season boundary and through the season

#### Mechanism

This is the only arm that targets **bias** rather than variance, and it targets the largest
systematic errors in the packet. The incumbent's league anchor is a *cumulative all-history* mean
of `π` — my count confirms `n_history_games` for level 3 runs to **1,300**, i.e. a 2026 projection
can be anchored on a mean that includes 2021. And prior-season team estimates are transported
**not at all**: a team's 2025 pace is used raw to project its 2026 opener.

The packet's own strata say this costs 2.8–3.5 possessions of bias on 228 rows and ≈1.2 on 532
more.

My coverage count establishes the fix is available: **184 of the 228 fallback rows (81%) have at
least one strictly-earlier same-season league game; 154 have ≥5; 92 have ≥10; the median is 8.**
WNBA season openings are staggered across several days, so by the time most teams play their first
game, other teams have already played. The current-season league level is therefore *observable* for
four fifths of exactly the rows that carry the −2.84 bias.

#### Exact formula

```
league anchor (recent-window, replaces the cumulative all-history mean):
  L(t)   = mean of π over league games with date < t, restricted to the trailing W_L games

season-level transport of prior-season team history:
  Δ̂(t)   = ( n_cur / ( n_cur + κ_L ) ) · ( L_season(t) − L_prev_season_final )
           n_cur = number of strictly-earlier same-season league games (my count: median 8,
                   ≥1 for 184/228 fallback rows, 0 for 44)
  m̃_p    = m_p + Δ̂(t)                              [additive]
     or   = m_p × L_season(t) / L_prev_season_final [multiplicative]

within-season drift: subsumed. If W_L is short, L(t) tracks the within-season level automatically;
no separate time index is introduced.
```

`W_L = ∞, κ_L = ∞` reproduces the incumbent (cumulative anchor, no transport). The shrinkage
`n_cur/(n_cur+κ_L)` means the 44 rows with zero earlier same-season games get `Δ̂ = 0`, i.e. exactly
the incumbent's behaviour — **no cliff, no coverage loss, no new unresolved rows.**

- **Target unit:** frozen canonical, unchanged.
- **Features:** the lagged league mean of `π` over a trailing window, and the previous season's
  final league level. Both are aggregates of the incumbent's own history element. **No new source.**
- **Cutoff-validity evidence:** `L(t)` uses only games with date `< t` — the same cumulative
  construction the incumbent already performs at lines 279–282 of `build_projected_exposure.py`,
  restricted to a window. `L_prev_season_final` is fully in the past. Coverage measured directly:
  184/228 fallback rows, and every level-1 row trivially has a full league history.
- **Deliberate design choice — I use *days/games since season start implicitly*, never
  `game_no_in_season`.** The packet withdrew that stratum as algebraically identical to
  `pace_level > 1` (which I reproduced in §0.4), and separately flagged an UNRESOLVED defect claim
  against the column. Anchoring on a *league-level trailing window* sidesteps both: it is not a
  threshold, it is not the disputed column, and it does not reintroduce the duplicated partition.
- **Fallback behaviour:** continuous. Degenerates to the incumbent at `κ_L → ∞`. The 8 unresolved
  rows stay unresolved.
- **Hyperparameter family:** ONE — anchor family `{W_L, κ_L, additive vs multiplicative}`. Costed
  once.
- **`K0_MATCHED`:** team-identity permutation would **not** destroy A4's mechanism, because A4's
  content is league-level and time-level, not team-level. The matched control must instead destroy
  the *time* content: identical pipeline, identical tier ladder, identical grid cardinality and
  selection protocol, with `L(t)` replaced by a **single in-fold global constant** and `Δ̂ ≡ 0`.
  This is the point at which a naive uniform permutation control would have silently passed a
  challenger. I flag it explicitly because it is the subtlest control error available here.
- **Expected failure mode:** the multiplicative form over-corrects on the 37 `league_prior_all` rows
  (they have zero team support, so a level shift is the *only* thing acting on them, and `W_L` will
  be selected on the 2,762 level-1 rows that dominate the objective). A short `W_L` may also import
  noise: a 20-game league window at 12 teams is under two days of play.
- **Affected stratum:** `team_window_prior_season` (183, bias −2.84451), `season_opener` (76, bias
  −3.47113), `league_prior_all` / `zero_team_support` (37, MAE 3.90215 — the worst stratum in the
  packet), and indirectly `team_support 3-4` / `5-9` (532, bias +1.35/+1.15) through the moving
  anchor. Also `by_season`: 2021 bias +0.72021 and 2026 bias −0.26668 are the two extremes and both
  are level errors of exactly this kind.
- **Expected direction:** bias on level-2 and opener rows moves from ≈−3 toward ≈0; bias on the
  low-support strata moves from ≈+1.2 toward 0. Estimated overall MAE effect ≈0.05–0.08 — the
  largest single-arm effect I forecast, and the highest-confidence one.
- **Overlap risk:** HIGH with A2 (shares `L(t)`; A2's `κ` will absorb A4's drift if A4 is not fitted
  first). MODERATE with A1 (shares `μ̄_ref`). **Recommended order: A4 → A1 → A3 → A2.**
- **Leakage risk:** LOW-MODERATE. `L_prev_season_final` is unambiguously past. The hazard is
  `W_L` selection on full-sample data, and the subtler hazard that a "season level" computed as a
  season *mean* would include future games — it must be a trailing quantity throughout.
- **Changes:** **calibration first**, subgroup allocation second, total third. This is the arm most
  likely to satisfy the "without degrading calibration" clause of the research question — it
  *improves* calibration by construction.

---

### A5 — Purify the historical observation before it enters the window

#### Mechanism

Every window element `π[g]` is currently a single number summarising a whole game, including
possessions that are not measuring the same thing:

1. **Overtime.** The incumbent handles OT by the linear rescale `n_off × 40 / game_minutes`. But
   `possessions_raw_v2` carries a per-possession `is_overtime` flag (1,434 possessions, 66 games),
   so the regulation-only count is **exactly** obtainable rather than approximated. The packet
   itself shows the approximation is imperfect: mean realised reg-equivalent is 78.9057 on OT games
   versus 79.3053 on regulation games. And the packet's OT contamination finding says 32.84% of
   10-game windows contain an OT game — a 4.4% event with ~7× reach.
2. **Non-competitive play.** `non_competitive_conservative` marks 6.117% of possessions.
   Per game: p50 2.67%, **p95 23.86%**, and **395 of 1,495 games (26.4%) exceed 10%**. Garbage-time
   possessions are generated by a different process (different personnel, different clock
   management) from the competitive possessions that dominate the target. A window element that is
   24% garbage time is measuring something different from one that is 0%.
3. **Degenerate possessions.** 1,799 `zero_duration_sequence` and 588
   `technical_free_throw_sequence` possessions (1.0% combined) are artifacts of the possession
   definition, not basketball tempo.

Because the frozen target counts **all** possessions, a purified estimator is estimating a
*component* and must be re-inflated. That makes this a genuine **two-component mixture estimator**,
which is a distinct statistical form, not a filter:

#### Exact formula

```
purified window element, for each strictly-earlier game i:
  π_pure[i] = ( n_off_pure(A,i) + n_off_pure(B,i) ) / 2 · ( C_reg / clock_pure(i) )
  where "pure" retains possessions with
        is_overtime == False                                   (exact regulation truncation)
    AND non_competitive_conservative == False                  (optional switch)
    AND possession_kind == 'live_ball'                         (optional switch)
  and clock_pure(i) is the corresponding elapsed regulation/competitive seconds

re-inflation to the frozen target's units (mixture recomposition):
  φ̂(t) = in-fold league-level expected ratio  E[ full-game reg-equiv pace / purified pace ]
          estimated over strictly-earlier games only, over a trailing window
  P_A5[g] = φ̂(t) · ( m_pure[A,t] + m_pure[B,t] ) / 2
```

- **Target unit:** frozen canonical, unchanged. The re-inflation exists specifically so the arm
  predicts the frozen target and not a purified surrogate.
- **Features:** `is_overtime`, `non_competitive_conservative`, `possession_kind`, `duration_sec`,
  `offense_team_id`, `period` — all from `possessions_raw_v2`, all over strictly-earlier games only.
  Coverage: 238,563 possessions, 1,495 games, **zero nulls** on every one of these columns.
- **Cutoff-validity evidence:** these are realised in-game state and are therefore cutoff-valid
  **only** as lagged history — precisely the packet's ruling for possession-level columns. The
  arm's construction receipt must bind: (a) no target-game possession row is read at all; (b) `φ̂`
  is estimated over strictly-earlier games; (c) P2's assertion covers `is_overtime` and
  `regulation_seconds_remaining` for the target game.
- **Ruling compliance — the reason for the exact-truncation form.** The coordinator permitted
  realised duration "solely to construct or normalise the COMPLETED-GAME regulation-equivalent
  outcome". Down-*weighting* a historical game because it went to overtime would arguably exceed
  that permission (it would put `game_minutes` into the weighting logic). **Counting only
  non-overtime possessions does not** — it is exactly "constructing the completed-game
  regulation-equivalent outcome", and it does so more precisely than the 40/45 linear rescale it
  replaces. I therefore propose the truncation form and explicitly reject the weighting form.
- **Fallback behaviour:** unchanged. Purification never removes a whole game (no game is 100%
  non-competitive; 622 games are 0% and the p95 is 23.86%), so support counts are preserved
  row-for-row. If a purified game somehow yields fewer than a minimum possession count, it falls
  back to the unpurified element.
- **Hyperparameter family:** ONE — observation-purification family
  `{OT truncation on/off, competitive filter on/off, live-ball filter on/off, φ̂ window}`.
  Costed once.
- **`K0_MATCHED`:** identical purification and re-inflation machinery, identical `φ̂` estimation,
  applied to **team-identity-permuted** history with support truncated to the recipient's counts —
  and, critically, with the *same* purified/unpurified switch settings, so the control pays for the
  same selection over the same switch grid.
- **Expected failure mode, stated plainly:** **the OT component is bounded near zero by the
  packet's own numbers.** The per-observation distortion is at most the 79.3053 − 78.9057 = 0.3996
  gap; at a 1/10 window weight and 4.4% incidence the induced bias is ~0.002, and even the
  packet's 32.84% window-contamination figure only lifts it to ~0.013. The packet's "7× leverage"
  statement is about *reach*, not *magnitude*, and I want that on the record so the arm is not
  oversold. The live-ball filter touches 1.0% of possessions and is equally null.
- **Why I include it anyway:** the **competitive-state** component is the one purification channel
  whose magnitude the packet does not bound at all. 26.4% of games exceed 10% non-competitive
  possessions and the p95 game is nearly a quarter garbage time; that is an order of magnitude more
  observation-level contamination than overtime, and nobody has measured its per-observation
  distortion. It is also the only Category A arm that improves the *measurement* rather than the
  *aggregation*, so a null here is scientifically informative in a way the other nulls are not: it
  would establish that window elements are already clean and retire the whole measurement-quality
  direction.
- **Affected stratum:** `by_overtime` (True: n=132) for the truncation component — noting the packet
  requires OT/non-OT downstream diagnostics to be reported separately and treated as SECONDARY.
  The competitive component affects no packet stratum specifically; it is a **new** cut and the arm
  should report a `non_competitive_share` stratum as a diagnostic, not as a decision input.
- **Expected direction:** truncation ≈ null (bounded above). Competitive purification: uncertain
  sign, small variance reduction plausible (≈0.01–0.03 MAE). Live-ball filter ≈ null.
- **Overlap risk:** LOW with A1/A2/A4. MODERATE with A3's ratio-of-means member (both re-derive the
  window element from possession-level data and both are absorbed by P1's recalibration at the
  level).
- **Leakage risk:** **HIGHEST of the six.** It is the arm that reads the most realised micro-data,
  from the source the packet says "carries no capture timestamp at all". Its cutoff validity rests
  entirely on a lag argument with no capture argument available (see Category B item B1). It also
  has the most places to accidentally touch the target game. Requires the strictest construction
  receipt.
- **Changes:** subgroup allocation and stability. Small total effect. Level effect fully absorbed
  by P1, which is why P1 is mandatory.

---

### A6 — Player-additive hierarchical decomposition with lagged-minutes reaggregation

#### Mechanism

Pace is a property of who is on the floor, and the incumbent's team-level trailing mean confounds
"this team is fast" with "this team's fast lineup happened to play a lot". `possessions_raw_v2`
carries the full ten-player on-court state for **99.789%** of possessions (238,060 of 238,563), so
this is decomposable.

**Lineup-level estimation is infeasible and I am not proposing it.** My counts: 14,272 distinct
(team, 5-man offensive lineup) cells, median 6 possessions per cell, and **49.6% of all possessions
sit in cells with fewer than 50 possessions**. That is fatal sparsity.

**Player-additive estimation is feasible.** ~240k possessions across roughly a thousand
player-seasons is thin but ridge-tractable, and it is the correct hierarchical form: partial pooling
of player effects toward zero, with the team effect emerging as a minutes-weighted aggregate.

#### Exact formula

Fitted on possessions from strictly-earlier games only, inside the training fold:

```
possession-level:
  d_j = δ + Σ_{i ∈ offence(j)} a_i + Σ_{i ∈ defence(j)} b_i + e_j
  minimise  Σ_j ( d_j − fitted )²  +  τ_a Σ_i a_i²  +  τ_b Σ_i b_i²
  where d_j is possession j's duration (the exact reciprocal parameterisation of pace, §A3.3)

team-level reaggregation, using LAGGED minutes shares only:
  s_i[T,t] = player i's share of team T's on-court possessions over strictly-earlier games
             (trailing window, Σ_i s_i = 5 across the five slots; normalised to 1)
  μ̂_A6[T,t] = C_reg / ( δ̂ + 5 · Σ_i s_i[T,t] · â_i + 5 · b̄̂_league )

combine sides with A1's rule.
```

- **Target unit:** frozen canonical, unchanged.
- **Features:** `off_p1..off_p5`, `def_p1..def_p5`, `duration_sec`, `lineup_valid_ten`,
  `offense_team_id`, over strictly-earlier games only. Coverage: 99.789% valid ten-player state;
  nulls 64–281 rows out of 238,563.
- **Cutoff-validity evidence:** realised on-court state and realised durations, used **only** as
  lagged history — the same standing the packet grants possession-level columns. Minutes shares are
  computed over strictly-earlier games.
- **Explicit rejection of the projected-minutes variant.** It is tempting to weight by
  `projected_team_rotations_v1` instead of lagged shares. **Do not.** In
  `build_projected_exposure.py`, player possessions are allocated as
  `projected_team_off_possessions × (minutes / REGULATION_MIN)` (line 488) — the rotation artifact
  sits *downstream* of the pace prior. Feeding it back in would create a circular dependency and
  import that artifact's entire cutoff-validity chain. Lagged shares only.
- **Fallback behaviour:** a player with fewer than `n_min` prior possessions gets `â_i = 0`
  (full shrinkage to league average) — which is what ridge does anyway, so rookies and call-ups are
  handled without a special branch. If a team's lagged minutes shares cover less than a threshold
  fraction of expected minutes, fall back to A2's `μ̂`. No new unresolved rows.
- **Hyperparameter family:** ONE — hierarchical-decomposition family
  `{τ_a, τ_b, minutes-share window, n_min}`. Costed once.
- **`K0_MATCHED`:** identical ridge machinery, identical folds and grid, with player identities
  **permuted within team-season** by a fixed seed (preserving each team's minutes-share *vector*
  exactly while destroying which player it belongs to). This is the sharpest available control: it
  isolates player-identity content while holding rotation *shape*, support and every degree of
  freedom constant.
- **Expected failure mode — I expect this arm to fail, and here is why.** §C2 establishes that
  97.8% of the target's variance is a *game*-level property shared by both teams. A player's
  measured pace effect is confounded with the opponent, the score state and the coach, and with only
  ~240 possessions per player-season the standard errors will swamp plausible effect sizes. Ridge
  will shrink `â` hard, the reaggregated `μ̂_A6` will land very close to `m[T,t]`, and the arm will
  cost a large implementation for a null. It is also the only arm that produces **two distinct
  projections within a game**, which breaks the packet's `games_with_two_distinct_projections = 0`
  and changes the clustering diagnostics — and §C2 caps the entire value of that asymmetry at
  ≈0.016 MAE.
- **Why I include it anyway:** it is the **only Category A mechanism that can respond to personnel
  change without a pregame injury feed.** The packet's Category B list is dominated by personnel
  inputs (injury feed, lineups, coaching) with `prospective_only_validation = true` — meaning a
  season of waiting before any test has power. A6 converts part of that gap into something testable
  *today* from data already on disk. And a clean, well-powered null from A6 is the strongest
  possible evidence for prioritising the Category B personnel items: it would show that the
  personnel channel is not recoverable from realised minutes and *requires* a pregame feed. That is
  a decision-relevant null, which is the only kind worth paying for.
- **Affected stratum:** all level-1 rows; disproportionately teams with roster churn, which is not
  a packet stratum and must be reported as a new diagnostic cut only.
- **Expected direction:** null to very slightly positive. I would not promote it on anything less
  than a clear, stable margin over its permutation control.
- **Overlap risk:** MODERATE with A3 (both use `duration_sec`; A3's ratio-of-means is A6's
  degenerate case with all `a_i` pooled to a single team effect — in fact **A3-ratio-of-means is
  exactly A6 at `τ_a → ∞`**, which makes A3 the natural nested control for A6 in addition to the
  permutation control). LOW with A1/A2/A4.
- **Leakage risk:** **HIGH.** Three distinct hazards: (a) the circularity described above;
  (b) minutes shares that accidentally include the target game; (c) ridge fitted across the fold
  boundary. Requires the most careful construction receipt of any arm here.
- **Changes:** subgroup allocation, and it is the only arm that changes the *dependence structure*
  of the predictions (breaking within-game identity). That must be declared before it runs, because
  it changes what the game-clustered bootstrap is bootstrapping.

---

## 3. Families I am NOT proposing, with the bound that retires each

This section is a deliberate deliverable. Independent sources tend to converge on the same
attractive-looking ideas; naming the ones that are bounded near zero *with the bound* is worth more
than proposing them.

| # | Family | Bound from the packet / my counts | Verdict |
|---|---|---|---|
| R1 | Within-game asymmetric prediction (team A ≠ team B) | §C2: ceiling **0.016 MAE** (0.56%), ≈0.003 turnovers | Retired as a standalone motive. Permitted only as a side effect of A6. |
| R2 | Precision-weighting the two sides by their support | Between-side support gap is **0 in 1,174 of 1,366** level-1 games, 1–2 in 180, 3–5 in 12, **max 4**; mixed `pace_level` in only **37 of 1,495** games | Retired: there is essentially no support asymmetry to weight. |
| R3 | Functional *shape* of the two-team combination (power mean, harmonic, slow-side dominance) | The lever is `\|m_A − m_B\|`, and both are heavily-averaged 10-game means, so the spread is small; the *level* component is absorbed by P1, leaving only the shape term. Local expansion gives a shift of order `(p−1)·h²/(2μ)` with `μ ≈ 79.3` — order 0.01 possessions | Retired. The basketball claim ("the slow team imposes tempo") is real but unmeasurable at this dispersion. |
| R4 | Count models (Poisson / negative binomial / count GLM) | Target mean **79.28758**, variance **15.27299** → dispersion ratio **0.193**. Strongly **under**-dispersed, because possessions tile a fixed clock (§0.4). Poisson assumes ratio 1 | Retired: structurally the wrong likelihood. |
| R5 | Log / variance-stabilising transform | CV = 3.90807 / 79.28758 = **4.93%**. Over that range `log` is linear to second order (curvature ≈ CV²/2 ≈ 0.12%) | Retired: no benefit, and it adds retransformation bias. |
| R6 | Robust central tendency (median / trimmed mean of the window) | Residual quantiles: p95 − p50 = 5.9701 = **1.625σ**; p50 − p05 = 6.0514 = **1.647σ**; Gaussian is 1.645σ | Retired: the residual is essentially Gaussian. Robustness has nothing to buy. |
| R7 | Overtime-probability modelling | Out of scope by explicit coordinator ruling | Not proposed. |
| R8 | Rest / schedule-density terms | §C5: corrected within-season `days_rest` spans only 0.20 MAE across buckets | Not proposed (also not my lens). |
| R9 | Anything keyed on `game_no_in_season` | Withdrawn stratum; algebraically identical to `pace_level > 1` (reproduced in §0.4), and a separate UNRESOLVED defect claim stands against the column | Not proposed. A4 uses a league trailing window instead, which is neither. |
| R10 | Anything keyed on head-to-head history coverage | Packet: UNRESOLVED, 70.2% vs 85.1% not reconciled, "no figure may be quoted in a task card until reconciled" | Not proposed. |

---

## 4. Protocol requirements that apply to all arms

### P1 — Common in-fold L1 recalibration (mandatory, and it is not an arm)

The scored loss is MAE; the incumbent is a conditional-*mean* estimator. That mismatch is real, but
the packet bounds it as tiny: the residual median is +0.1764 against a mean of +0.15917, and the
residual is near-Gaussian (R6). For a near-symmetric residual with density `f(0) ≈ 0.3989/3.674 =
0.1086` at the median, removing an offset `δ` gains `≈ f(0)·δ² = 0.1086 × 0.176² ≈ 0.003` MAE.

**Therefore: do not run this as an arm.** Run it as a mandatory, identical post-hoc step on the
incumbent, `K0_FLAT`, `K0_MATCHED` and every challenger — a single additive offset fitted on each
fold's training portion. Two reasons:

1. It is worth ≈0.003, so it cannot decide anything, and an arm that "won" by capturing it would be
   a false positive.
2. Several proposals (A3's ratio-of-means, A5's re-inflation, R3's power mean) shift the *level* by
   a Jensen-type term. Without P1, any of them could win on a recentring that carries no
   information. With P1, they must win on shape or lose.

*(Aside, expected null: the target is integer-valued on 95.6% of rows, so the L1-optimal predictor
is formally an integer. Rounding a continuous prediction with sd 3.67 to the nearest integer is a
perturbation of at most 0.5 on a 3.67 scale and is neutral in expectation. Not worth an arm; note
it and move on.)*

### P2 — Target-game duration firewall

Assert, and fail closed, that no function of the target game's `period`, `max_period`,
`is_overtime`, `game_minutes` or `regulation_seconds_remaining` reaches any feature, weight,
fallback branch, arm-selection step or prediction. A5 and A6 both read possession-level columns that
*contain* these fields for earlier games; the join must be provably strict.

### P3 — Inference reporting

Report **n = 2,982 team-game rows and 1,491 game clusters**, always both, never "effective n".
Bootstrap over the 1,491 clusters carrying both team-rows together. A6 is the only arm that breaks
within-game projection identity; it must declare that before it runs.

### P4 — Sequencing, because the arms trade credit

```
A4  (level transport)      →  fixes a documented bias; must be first or A2 will absorb it as κ
A1  (deviation gain)       →  closed-form pre-check on Var(P); abandon before fitting if ≈1.77
A3  (window aggregation)   →  substitute for A1; must be fitted jointly with it, never credited twice
A2  (continuous pooling)   →  conditional on A4's anchor
A5  (observation purity)   →  independent of the above; can run in parallel
A6  (player hierarchy)     →  last; use A3-ratio-of-means as its nested τ_a→∞ control
```

### P5 — `K0_MATCHED` is not one construction

The packet defines `K0_MATCHED` as "identical pipeline, folds, offsets, fallback tiers, switching
rules and allowed estimation flexibility". How to strip the *content* while keeping the *structure*
depends on what the arm claims:

| Arm claims | Destroy | Preserve exactly |
|---|---|---|
| team-identity content (A1 ridge, A2, A3, A5) | which team the history belongs to, via fixed-seed permutation held constant within (season, date) | support counts `n_s, n_p`, tier assignment, date, `n_eff`, league drift, grid cardinality |
| league/time content (A4) | the time-varying anchor → single in-fold constant, `Δ̂ ≡ 0` | tier ladder, folds, grid cardinality, selection protocol |
| pure recalibration (A1 scalar) | the gain → fitted in-fold intercept only | everything else, one fewer df |
| player-identity content (A6) | which player, via permutation within team-season | each team's minutes-share vector, rotation shape, ridge machinery |

**A uniform permutation control would silently pass A4**, because permuting teams does not remove a
league-level time signal. That is the trap in this arm set and it should be written into the task
card.

Additionally, per the packet's `tier_partition_rule`: A2 dissolves the tier ladder, so **its**
matched control must carry the continuous support weighting, not tier dummies.

---

## 5. Category A summary — expected sizes against the C3 threshold

| Arm | Mechanism class | Affected rows | Forecast Δ MAE | Δ turnover MAE (≤0.177×) | Confidence |
|---|---|---|---|---|---|
| A4 | bias / regime | 228 + 532 = 760 | 0.05 – 0.08 | 0.009 – 0.014 | **high** |
| A2 | shrinkage / pooling | 752 | 0.03 – 0.06 | 0.005 – 0.011 | medium |
| A3 | window aggregation | 2,762 | 0.02 – 0.04 | 0.004 – 0.007 | medium |
| A5 | measurement quality | 2,762 | 0.01 – 0.03 | 0.002 – 0.005 | low |
| A1 | scale / deconvolution | 2,762 | 0.00 – 0.06 (closed-form gated) | 0.000 – 0.011 | **decidable before fitting** |
| A6 | hierarchical structure | 2,762 | ≈0 (expected null) | ≈0 | low |

**The honest headline: no single arm reaches the ≈0.28 possession-MAE (9.7%) needed to move
operational turnover MAE by 0.05.** Even a fully additive composition of A4 + A2 + A3 + A5 lands
around 0.11–0.21 — and they are not fully additive, because A1/A3 are substitutes and A2/A4 share an
anchor.

The correct reading of that is not "abandon the wave". It is:

1. **A4 alone is worth registering** — it is high-confidence, it fixes documented bias rather than
   chasing variance, and it improves calibration by construction, which is the clause of the
   research question most at risk from variance-chasing arms.
2. **A1's closed-form gate should be run before anything else.** It costs one descriptive scalar and
   it either opens a 0.06 MAE opportunity or closes an entire direction for free. There is no other
   test in this document with that cost-to-information ratio.
3. **The realistic Stage 2 answer to the research question is probably "yes, but small".** The
   packet's own diagnostics say the incumbent's error is 88.4% unexplained variance with negligible
   bias. Estimator-structure work can recover the bias and shave the estimator's own sampling noise;
   it cannot manufacture signal that is not in the lagged history. Closing the remaining gap needs
   the Category B inputs, and the programme should be told that now rather than after six arms.

---

## 6. CATEGORY B — high-value but unavailable

Ordered by expected value per unit of cost. These may **not** become arms.

### B1 — Per-observation capture timestamps and revision history

- **Missing input:** an immutable `(row_key, observed_at, content_hash)` log for `master_team` and
  `possessions_raw_v2`, never overwritten.
- **Why it may matter (my lens specifically):** every arm above rests on a **lag** argument, and
  the packet's `capture_provenance_caution` is explicit that `master_team` is a retrospective bulk
  scrape (ten distinct `observed_time` values in two windows, covering game dates back to
  2021-05-14) and that `possessions_raw_v2` "carries no capture timestamp at all". A5 and A6 lean
  hardest on exactly the lagged realised micro-data most exposed to silent revision. Without a
  revision history we cannot bound how much of any measured gain is hindsight-corrected data rather
  than information available at the cutoff. The packet's availability table warns of this directly:
  it "records AVAILABILITY and COVERAGE... does NOT prove cutoff validity", against
  `PROGRAM_STATE` gap `cutoff_validity_asserted`.
- **Minimum viable collection:** append-only `(row_key, observed_at, content_hash)` on every pull.
  A small change to the collector. No new external source.
- **Prospective-only validation required:** **yes for verification.** The existing 2021–2026 span
  can never be retro-verified; it remains declaration-only forever.
- **Expected value of closing the gap:** high and cheap. It converts an unclosable `PROGRAM_STATE`
  gap into a closable one, and it is a precondition for trusting A5 and A6 at all. Every day it is
  deferred permanently enlarges the unverifiable span.

### B2 — Coaching identity and coaching-change dates

- **Missing input:** head coach by team-season, plus mid-season change dates. Packet: "no coaching
  source exists; a `*coach*` sweep over `data/` returns nothing."
- **Why it may matter (my lens):** this is the **regime-change instrument**, and the reason I need
  it is a power argument, not a plausibility argument. Any endogenous break detector I could build
  (A3's adaptive-window member) must compare short and long trailing windows. With per-game pace
  variance ≈15, a 3-vs-7 split has a difference-of-means standard error of
  `sqrt(15/3 + 15/7) ≈ 2.7`, so only breaks larger than **≈5.4 possessions (≈1.4 target sd)** are
  detectable at 2 se. Coaching-induced pace shifts are plausibly 2–4 possessions — **below the
  detection floor.** An endogenous detector will therefore return a null that means "underpowered",
  not "no effect", and that null is uninterpretable. An exogenous event marker is the only way to
  test the channel at all. This is why I folded the adaptive-window idea into A3 rather than
  proposing it as its own arm.
- **Minimum viable collection:** 12 teams × 6 seasons ≈ **72 rows** (team, season, coach,
  start_date, end_date), plus the handful of mid-season changes. Public record, hand-maintainable.
- **Prospective-only validation required:** **no.** Fully reconstructible historically, so it can
  be tested retrospectively on the existing 1,491 clusters immediately.
- **Expected value of closing the gap:** **the best cost-to-value ratio in this document.** ~72 rows
  of hand entry buys the only testable regime-change channel in the programme.

### B3 — A provenance ruling on `data/injury_history/injury_history.csv`'s `date` column

- **Missing input:** not data — a **determination**. The packet places this file in Category B "on
  cutoff grounds, NOT availability grounds": 8,340 rows spanning 2021-01-07 to 2026-07-29, the full
  contract span, with "no observation timestamp; cutoff status rests on `date` being an event date
  rather than a compilation date."
- **Why it may matter (my lens):** if `date` is an event date, this becomes a lagged
  **personnel-disruption instrument** — exactly the shrinkage modifier A2 and A3 lack. The natural
  form is a history-relevance weight: down-weight window games that precede a roster disruption,
  because they measure a team that no longer exists. That is a principled, purely
  estimator-structural use, and it does **not** require a pregame feed (which is B4's problem) —
  only that the disruption date be known after the fact and before the target game.
- **Minimum viable collection:** none. A provenance determination on **one column**, plus a
  spot-check of a dozen rows against independently known transaction dates.
- **Prospective-only validation required:** **no**, if the determination is favourable. Retrospective
  testing over the full span becomes available immediately.
- **Expected value of closing the gap:** very high relative to a cost of roughly one afternoon.
  This is the cheapest large unlock in the packet, and it is currently blocked on a question nobody
  has asked rather than on data nobody has.

### B4 — Pregame availability and announced-rotation feed with historical depth

- **Missing input:** the packet's own item. Current capture spans 2026-07-30 → 2026-08-04, six days
  of a five-season span.
- **Why it may matter (my lens):** it is the fix for **A6's expected failure mode.** A6 must weight
  player pace effects by *lagged realised* minutes shares, which are a noisy backward-looking proxy
  for who will actually play. A pregame availability/rotation feed replaces the proxy with the
  quantity the estimator actually wants, and turns the personnel channel from an inference problem
  into a measurement problem.
- **Minimum viable collection:** persist the existing injury capture forward (already running from
  2026-07-30) and add pregame lineup postings.
- **Prospective-only validation required:** **yes.** And note the timeline honestly: a WNBA season
  is ~40 games per team, so a full season adds ~480 team-games — 16% of the current 2,982 rows.
  **Any test with real power is at least one full season away, probably two.**
- **Expected value of closing the gap:** medium. High ceiling, slow accrual. Worth starting now
  precisely because it accrues slowly.

### B5 — A market pace-implied total with history, used **once** as a predictability ceiling

- **Missing input:** the packet's item; capture begins 2026-07-31, after the modelling span.
- **Why it may matter (my lens — and this is a different use from the packet's framing):** the
  programme currently has **no external estimate of the irreducible noise floor.** Variance
  explained is 0.11608, and nobody can say whether the achievable ceiling is 0.15 or 0.45. That
  number determines whether *any* further estimator-structure work is worth funding, and §5 makes
  clear the programme is going to face exactly that question soon. A market total is the only
  external consensus pace signal available, and a single diagnostic comparison against it would
  bound the predictable fraction.
- **Minimum viable collection:** persist the odds capture forward; or license a historical total
  series for 2021–2026.
- **Prospective-only validation required:** **yes** for the forward-capture route; **no** if a
  historical series can be licensed.
- **Caution, carried from the packet and reinforced:** as a **feature** it changes what the model is
  — "it would no longer be a pure pace projection". I propose it **strictly as a one-time
  diagnostic ceiling estimate and never as an arm input.** That distinction must be written into
  whatever task card adopts it, because the temptation to promote a diagnostic into a feature is
  exactly how a pace model quietly becomes a market model.
- **Expected value of closing the gap:** medium-high — not as a predictor, but as a **stop/continue
  decision instrument** for the whole possession-projection programme.

### B6 — Historical span before 2021

- **Missing input:** possession-level play-by-play for seasons before 2021. Current span: 6 seasons,
  1,495 games, 2,990 team-games, 238,563 possessions.
- **Why it may matter (my lens):** every pooling and hierarchical arm here is sample-limited.
  A6 in particular is fitting ~1,000 player-seasons on ~240k possessions with 49.6% of the mass in
  thin cells; A1's ridge `τ` and A2's `{γ, κ}` are selected on 1,491 clusters. Doubling the span
  roughly halves the variance of every hyperparameter estimate and is the single cheapest way to
  make A6 well-powered enough for its null to *mean* something.
- **Minimum viable collection:** extend the existing possession pipeline backward to 2016–2020,
  reusing `build_canonical_events.py` / `possession_artifact_v2.py`. No new schema.
- **Prospective-only validation required:** **no.**
- **Expected value of closing the gap:** medium, **and it carries a specific risk that must be
  stated**: older seasons come from a different pace regime, and this document has documented
  season-over-season level drift of ≈2.8 possessions (§C4). Pre-2021 data is unusable **unless A4's
  level transport is already in place.** That makes B6 strictly downstream of A4 — which is a
  concrete argument for registering A4 first, independent of A4's own merits.

---

## 7. One-paragraph summary for the coordinator

The incumbent's error is 88.4% unexplained variance with negligible bias, so the estimator-structure
lens offers two real levers and one closed-form gate. The real levers are **A4** (transport the
league level across the season boundary and through the season — it targets the −2.84 prior-season
and −3.47 opener biases and the +1.2 early-season bias, covering 760 rows, and 81% of the affected
fallback rows have a usable same-season league anchor) and **A2/A3** (replace the discrete tier
ladder and the flat 10-game window with continuous precision pooling and a longer, possibly
possession-weighted window). The gate is **A1**: because a team's pace history already contains its
opponents, the incumbent's projected deviation from the league mean is structurally half the
deviation it is predicting, and whether that matters is decided in closed form by one descriptive
scalar, `Var(P)` — worth up to 0.06 MAE if it is below ~1.0 and exactly zero if it is 1.77285. I
have not measured it; the arm should, in-fold, first. **A5** (purify window observations of
overtime, garbage time and degenerate possessions — 26.4% of games exceed 10% non-competitive
possessions) and **A6** (player-additive hierarchical decomposition, now possible because the
possession stream carries valid ten-player lineups on 99.8% of possessions) are lower-confidence;
I expect A6 to be null and I say so, but its null is decision-relevant because it is the only way to
probe the personnel channel without waiting a season for a pregame feed. Six families are retired
here with explicit bounds — most importantly, **any hypothesis that predicts team A differently from
team B in the same game is capped at 0.016 MAE**, and count/Poisson models are structurally wrong
because possessions are under-dispersed (ratio 0.193) by virtue of tiling a fixed clock. Finally,
the scoping arithmetic: possession error propagates to turnover error at ≈0.177, so moving
operational turnover MAE by 0.05 needs a 9.7% possession-MAE improvement, and **no arm here reaches
that alone.** The programme should hear that now. The cheapest paths to more headroom are Category B
items **B3** (rule on one column's provenance and 8,340 rows of injury history become a lagged
personnel instrument) and **B2** (72 hand-entered rows of coaching history buy the only
regime-change instrument that clears the ≈5.4-possession endogenous detection floor).
