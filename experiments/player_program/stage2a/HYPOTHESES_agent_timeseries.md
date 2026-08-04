# HYPOTHESES — Stage 2A independent source: statistical time-series and shrinkage

**Source mandate:** estimation theory, time series, shrinkage and partial pooling.
**Lane:** IDEATION ONLY. Nothing in this document was fitted, tuned, selected or scored. No model
was estimated. No accuracy number was computed from data.
**Evidence used:** `experiments/player_program/stage2a/EVIDENCE_PACKET.json`
(sha256 `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`, verified in place),
`experiments/player_program/build_projected_exposure.py` (read only),
`experiments/player_program/stage2a/build_evidence_packet.py` (read only — consulted solely to
resolve the definition of the realised target), plus read-only *existence and coverage* checks on
frozen artifacts.
**Not read:** any `HYPOTHESES_*` file. `HYPOTHESES_coordinator.md` is present in this directory and
was deliberately not opened.

---

## 0. Read of the evidence before proposing anything

### 0.1 The packet's own arithmetic pins the variance budget almost exactly

The mandate asks me to reason about estimator variance versus bias. Before proposing arms I did the
moment algebra the packet makes possible. **This is algebra on the packet's published moments under a
stated structural assumption. It is not a fit, not a score, and it must be checked empirically before
anyone relies on it.**

Assume the standard additive pace decomposition

```
game_pace_g  =  mu + alpha_i + alpha_j + eps_g
```

with team effects `alpha` i.i.d. variance `tau^2`, game noise `eps` variance `sigma^2`, independent,
and `alpha` static over the window. Then:

- `Var(target) = 2 tau^2 + sigma^2 = 15.273` (packet: `target_variance`)
- a team's trailing-K mean of its own past `game_pace` values estimates `mu + alpha_i` with
  estimation-noise variance `(tau^2 + sigma^2)/K` — the opponent mix and the game noise are *both*
  inside that noise term
- the incumbent's prediction is `mu + 0.5 * (S_hat)` where `S_hat = (alpha_i + alpha_j) + n`,
  `Var(n) = 2(tau^2+sigma^2)/K`
- therefore `Var(err) = 0.25 Var(S) + 0.25 Var(n) + sigma^2 = 0.55 tau^2 + 1.05 sigma^2` at K=10

Setting that equal to the packet's `residual_variance = 13.500` and solving jointly with the target
variance gives

| quantity | implied value |
|---|---|
| between-team pace sd `tau` | **≈ 1.28 possessions / 40 min** |
| game-level noise sd `sigma` | **≈ 3.46** |
| implied `Var(err)` at K=10, lambda=0.5 | **13.50** |

The last row reproduces the packet's `residual_variance` to three decimals. The variance-components
model is therefore *consistent with every published moment in the packet*, which is meaningful
support for using it as a headroom bound (though not proof — see §0.5).

### 0.2 The consequence: the achievable headroom is small and quantifiable

An estimator restricted to lagged own-and-opponent pace history cannot beat `Var(err) = sigma^2`,
which is what remains when `alpha_i` and `alpha_j` are known exactly.

| scenario | MSE | implied MAE (≈ current × sqrt ratio) | gain vs incumbent |
|---|---|---|---|
| incumbent (K=10, lambda=0.5) | 13.50 | 2.903 (published) | — |
| MSE-optimal lambda at K=10 (lambda\*≈0.546) | 13.49 | 2.902 | **≈ 0.001 — a null** |
| K=20 with matched optimal lambda (≈0.71) | 12.96 | ≈ 2.845 | ≈ 0.058 (2.0%) |
| K=30 with matched optimal lambda (≈0.78) | 12.71 | ≈ 2.816 | ≈ 0.087 (3.0%) |
| **perfect team levels, lambda=1 (absolute ceiling)** | **12.00** | **≈ 2.737** | **≈ 0.166 (5.7%)** |

**Finding N1 (negative, high value).** The incumbent's `(a + b)/2` combination rule looks on its face
like a functional-form error — under the additive model the correct combination of two team pace
*ratings* is `rating_i + rating_j - mu`, not their average. But the MSE-optimal shrinkage of a
pair-signal observed with 10-game estimation noise is `Var(S)/(Var(S)+Var(n)) ≈ 0.546`. **The
incumbent's 0.5 is within 0.05 of the optimum by coincidence.** Anyone proposing "use the additive
combination instead of the average" is proposing a change that the packet's own variance budget says
will *lose*, because lambda=1 is the correct combination of *true* levels and a badly over-aggressive
weighting of *estimated* ones. I expect several independent sources to propose exactly this. It is
the single most attractive-looking and least productive change available.

**Finding N2 (negative).** Opponent-mix adjustment has a tiny ceiling. Of the `Var(n) = 2.73` of
estimation noise, the opponent-identity share is `2 tau^2/K = 0.33`; the rest is game noise. Removing
opponent-mix contamination *entirely* moves MSE by well under 0.1. A 10-game window in a 12-team
league is already close to schedule-balanced. This is worth stating because opponent adjustment is
the most obvious "the incumbent ignores the opponent" critique and its payoff is near zero.

**Finding N3 (negative, with a stated ceiling).** The incumbent gives both sides of a game the
identical projection. Possessions alternate, so the two sides' regulation-equivalent counts differ by
roughly a possession. The *entire* information content of within-game team-vs-team differentiation is
therefore on the order of ±0.5 possessions, i.e. a ceiling of well under 0.1 MAE even if perfectly
predicted. It is not zero and it is not where the problem is. (Cheap to check exactly from the frozen
possession stream: the distribution of the two sides' count difference per game. That is a one-line
distributional diagnostic, not a model.)

**Where the gain therefore has to come from:** reducing `Var(n)`, the estimation noise in the two team
levels. That means *effective sample size* — longer or better-weighted windows, borrowing strength
across the hierarchy, and denoising each historical observation. Every other lever is bounded below
0.1 MAE by the algebra above.

### 0.3 The bias strata: cancellation, not absence

The packet reports `bias_share_of_mse = 0.0019` and reads it as "a better point estimate must reduce
dispersion, not re-centre." That reading is correct **pooled** and misleading **conditionally**. The
pooled bias is near zero because large opposite-signed stratum biases cancel:

| stratum | n | bias | share of rows |
|---|---|---|---|
| `team_window_prior_season` | 183 | **−2.84** | 6.1% |
| `game_no_in_season` 1–3 | 228 | **−2.17** | 7.6% |
| `days_rest` 7+ | 162 | **−1.43** | 5.4% |
| support 3–4 | 156 | **+1.34** | 5.2% |
| support 5–9 | 390 | **+1.15** | 13.1% |
| `game_no_in_season` 4–10 | 532 | **+1.13** | 17.8% |
| support 10 (full window) | 2413 | −0.06 | 80.9% |

Stratum-level re-centring *does* reduce MSE even though the pooled bias is ~0. Budgeting it from the
packet's own published numbers (`bias^2 × row share`, before overlap deduplication):

- prior-season fallback: `2.84^2 × 183/2982 ≈ 0.50` MSE ≈ 3.7% → **≈ 0.045 MAE**
- early-same-season positive bias: `1.15^2 × ~546/2982 ≈ 0.24` MSE ≈ 1.8% → **≈ 0.020 MAE**
- long-rest stratum: `1.43^2 × 162/2982 ≈ 0.11` MSE ≈ 0.8% → **≈ 0.010 MAE**

These strata overlap heavily (prior-season fallback ⊂ game_no 1–3; support 3–9 ⊂ game_no 4–10), so the
deduplicated total is roughly **0.05–0.07 MAE**, not the sum. This is a *ceiling* on the whole
"fix the level in the bad strata" programme, and it assumes the biases are estimated without error and
fully removable.

**Combined realistic budget for everything in Category A: ≈ 0.10–0.15 MAE against a base of 2.903,
i.e. 3.5–5%. Absolute ceiling 0.166 (5.7%).**

### 0.4 What that is worth operationally — the number the question actually asks for

The packet gives `mean_abs_propagated = 0.51744` turnovers per team-game at the current possession
MAE of 2.903, a ratio of 0.178 ≈ the mean implied turnover rate. Propagation is close to linear, so:

> **The entire achievable improvement in the possession channel — including the unreachable
> perfect-team-levels ceiling — is worth about 0.03 turnovers per team-game. A realistic Category A
> programme is worth about 0.01–0.02 turnovers per team-game.**

I state this plainly because it should govern how much multiplicity budget Stage 2 spends here. If
operational turnover-team MAE needs to move by more than ~0.03, **it cannot come from the possession
count at all** — it must come from the turnover *rate*, or from genuinely new information (Category B).
This is the most important thing this source has to contribute and it is derived entirely from the
frozen packet.

### 0.5 Where I am uncertain about §0.1–0.4

1. **The additive assumption may be wrong.** If pace is genuinely *averaging* (a slow team drags a
   fast opponent down, so `E[pace] = mu + (alpha_i+alpha_j)/2`), then the incumbent's form is exactly
   right and there is even *less* headroom than I computed. A1 below is designed to resolve this.
2. **`alpha` is assumed static.** If team level drifts within a season, part of my `sigma^2 = 12.00`
   is predictable by recency weighting and the ceiling is looser than 12.00. This is the strongest
   argument for the A3 family and it is the one genuinely open empirical question.
3. **`sigma^2` may contain target measurement noise.** The possession count is derived from a PBP
   algorithm carrying `is_technical_derived`, `is_zero_duration`, `source_order_differs` and
   `inferred_flip` / `miss_flip_no_rebound` end reasons. Any derivation error is irreducible by *any*
   model and tightens the ceiling below 12.00. See D1.
4. **MAE-from-MSE conversion assumes near-normal errors.** The packet's `p50` (0.176) ≈ `bias` (0.159)
   and near-symmetric `p05`/`p95` (−5.875 / +6.147) support this, but the mapping is approximate.
5. The K=3 stratum's observed sd (3.687) is *below* what my model predicts, so the variance-components
   fit is good in aggregate and rougher in the tails.

### 0.6 A methodological defect that affects every arm regardless of which is chosen

**`n = 2982` overstates precision by roughly sqrt(2).** `projected_team_off_possessions` is computed
per *game* and merged onto both team rows (`build_projected_exposure.py`, the `agg` merge on
`game_id`). Both sides of a game receive the identical projection; only the realised value differs,
and it differs by roughly the within-game possession asymmetry (see N3). The two errors within a game
are therefore correlated at roughly ρ ≈ 0.97. There are **1491 independent projections, not 2982**.

Consequences:
- Unpaired SE(MAE) ≈ `sd(|err|)/sqrt(1491) ≈ 2.215/38.6 ≈ 0.057`. The *entire realistic headroom*
  (0.10–0.15) is only 2–3 unpaired standard errors.
- Any arm comparison **must be paired on identical games** (same game_id, incumbent vs challenger
  error side by side) and **clustered at game level**, not team-game level. A paired comparison is
  far more powerful here because the two estimators' errors are highly correlated; an unpaired
  comparison at this headroom will not resolve anything.
- With a headroom this small relative to selection noise, **the number of arms is itself the primary
  risk to this stage**. I have deliberately kept the Category A list short and collapsed all
  hyperparameter variation into families.

---

## CATEGORY A — immediately testable

Every input named below is lagged-only, present in a frozen artifact, and complete over the modelling
span. Coverage claims were verified by read-only existence checks; **availability is not the same as
cutoff validity**, and per the packet's own warning no receipt's `cutoff_valid` declaration is treated
here as proof. Each record's "cutoff-valid inputs required" line is a claim requiring scientific
review before it may back a registered arm.

Records use a fixed schema. "Changes what" distinguishes: **TOTAL** (moves the projected possession
number), **CALIBRATION** (changes uncertainty/conditional-mean properties without necessarily moving
the point estimate), **ALLOCATION** (moves only how error is distributed across subgroups).

---

### A1 — Pair-combination scaling family (`lambda`)

- **Source:** shrinkage / estimator variance.
- **Mechanism:** replace `pred = (est_i + est_j)/2` with
  `pred = mu_hat + lambda * (est_i + est_j - 2*mu_hat)`. `lambda = 0.5` recovers the incumbent
  exactly; `lambda = 1` is the additive-decomposition combination. One scalar. Hyperparameter
  variation (fixed lambda vs support-dependent `lambda(n_i, n_j)` vs a per-season lambda) is nested
  inside this single family and counted once.
- **Expected direction:** **essentially no change at full support** — §0.1 puts `lambda*` at ≈0.546
  against the incumbent's 0.5, worth ≈0.001 MAE. At *low* support the optimum is far below 0.5
  (`lambda* ≈ 0.27` at K=3), so a support-dependent lambda should **reduce** the projection's
  deviation from the league level for cold-start rows, cutting their MSE by ≈4–5% on those rows.
- **Affected stratum:** support 3–4 and 5–9 (546 rows); negligible on the 2413 full-window rows.
- **Cutoff-valid inputs:** `team_pace_estimate`, `n_history_games` — both already in
  `team_possession_prior_v1.parquet`. Nothing new.
- **Inputs exist:** YES, entirely within the incumbent's own output.
- **Overlap risk:** HIGH with A2 (a support-dependent lambda *is* shrinkage; if A2 runs, A1's
  support-dependent variant is redundant and must not be counted twice). LOW with A3/A4/A6.
- **Leakage risk:** LOW. Lambda must be estimated on strictly-earlier data or on a held-out
  chronological block; a lambda fitted on the same rows it is scored on is a mild but real
  in-sample optimism, worth roughly one SE at this headroom.
- **Expected information gain:** **LOW as an MAE lever, HIGH as a diagnostic.** The fitted lambda
  discriminates the additive generative model (lambda near 1 at high support) from the averaging model
  (lambda at or below 0.5). That single coefficient governs how much headroom every *other*
  hypothesis has. Worth running for that reason alone.
- **Implementation complexity:** LOW (one scalar, one line).
- **Falsifier:** if a chronologically-honest lambda estimated on full-support rows lands in
  [0.45, 0.60], the additive-form critique of the incumbent is dead and the "use `a + b − mu`"
  direction should be closed for the rest of the programme.
- **Changes what:** TOTAL (marginally), and CALIBRATION via projection dispersion.
- **I expect this to produce no MAE win.** I include it because it is one free scalar that nests the
  incumbent and resolves a structural question the whole stage depends on.

---

### A2 — Continuous hierarchical partial pooling, replacing the discrete 3-tier ladder

- **Source:** shrinkage / partial pooling / hierarchical structure (team ⊂ season ⊂ league).
- **Mechanism:** the incumbent's ladder is a hard switch at `MIN_HISTORY_M = 3`: with 2 same-season
  games it uses the *prior season*; with 3 it uses a 3-game mean whose standard error is
  `≈ 3.9/sqrt(3) ≈ 2.25`. That discontinuity is indefensible on estimation grounds — the estimator
  lurches between two very different variances at an arbitrary threshold. Replace it with a
  precision-weighted combination that is continuous in support:
  `est_i = w_same * xbar_same + w_prior * (prior_season_team_level + league_drift) + w_league * league_level_now`,
  with weights `w ∝ 1/Var` from an empirical-Bayes or hierarchical estimate of `tau^2` and `sigma^2`.
  Hyperparameter variation — shrinkage strength, whether the shrinkage target is the league level or
  the drift-adjusted own-prior-season level or a weighted mix, and whether `tau` is estimated per
  season or pooled — is **one family, counted once**.
- **Expected direction:** low-support rows' estimates move **toward** the pooled level, reducing the
  `+1.15` to `+1.34` over-projection at support 3–9 and part of the `−2.84` under-projection at
  prior-season fallback (the latter only if the drift term from A4 is included). No material change
  on the 2413 full-window rows. Net: **reduces MAE on ~569 low-support rows by ~4–6%, pooled effect
  ≈ 0.02–0.05 MAE.**
- **Affected stratum:** support 3–4, 5–9, `pace_source = team_window_prior_season`,
  `game_no_in_season` 1–10, and the 37 `league_prior_all` rows.
- **Cutoff-valid inputs:** own strictly-earlier `game_pace` (same and prior season) and the
  strictly-earlier league mean. All already used by the incumbent; no new field.
- **Inputs exist:** YES.
- **Overlap risk:** **HIGH** with A1's support-dependent variant (identical mechanism), **HIGH** with
  A4 (A2 needs a correctly-levelled league anchor to shrink toward, so A4 is arguably a *prerequisite*
  rather than a competitor), MODERATE with A3 (both change effective sample size, by different
  routes). If run together, run them as one arm with a declared nesting order, not three.
- **Leakage risk:** MODERATE and specific. `tau^2` and `sigma^2` must be estimated from strictly
  earlier games only, or from an expanding window. A variance-components estimate that uses the full
  span leaks the future into every early-season row — this is the most likely way this arm is
  implemented wrongly.
- **Expected information gain:** MODERATE. Pooled MAE effect small, but it removes a structural
  defect (a discontinuous estimator) and is the correct home for every cold-start improvement.
- **Implementation complexity:** MODERATE. Closed-form empirical Bayes is straightforward; the
  chronologically-honest variance estimation is the fiddly part.
- **Falsifier:** if the fitted shrinkage weight on the low-support rows is indistinguishable from the
  incumbent's implicit hard weight of 1.0, or if per-stratum MAE on support 3–9 does not improve while
  full-window MAE degrades, the family is dead.
- **Changes what:** TOTAL and ALLOCATION. It re-centres specific strata; it barely moves the pooled
  level (which is already near-unbiased by cancellation).

---

### A3 — Effective sample size: window length, recency weighting, local-level state space

- **Source:** time series / effective sample size / bias-variance.
- **Mechanism:** `WINDOW_K = 10` unweighted is an unjustified constant. Per §0.2 this is **the largest
  single lever available**, because `Var(n) = 2(tau^2+sigma^2)/K` is the only sizeable reducible term.
  Three nested variants, ONE family:
  1. longer fixed window (K=15, 20, 30, or all same-season games);
  2. exponentially-weighted mean with a half-life parameter (equivalent to a fractional effective K);
  3. a local-level / Kalman formulation `alpha_{i,t} = alpha_{i,t-1} + eta_t`, run strictly forward in
     time, which yields the recency weight *and* the support-dependent shrinkage automatically as
     functions of the signal-to-noise ratio `Var(eta)/sigma^2`.
  Variant 3 subsumes 1 and 2 and, if the drift and league components are added, subsumes A2 and A4 too.
- **Expected direction:** **if team level is static, longer is strictly better** — §0.2 gives ≈0.058
  MAE at K=20 and ≈0.087 at K=30. **If team level drifts, there is an interior optimum** and the
  EWMA/local-level variants beat both K=10 and K=30. The sign of the K=20-vs-K=10 comparison is
  therefore the cleanest available test of whether WNBA team pace is a static level or a slow random
  walk — which is exactly caveat (2) in §0.5.
- **Affected stratum:** the 2413 full-window rows — i.e. **the 81% of rows every other hypothesis
  leaves untouched.** This is the only Category A entry that meaningfully attacks the main stratum.
- **Cutoff-valid inputs:** own strictly-earlier `game_pace` only. Nothing new.
- **Inputs exist:** YES.
- **Overlap risk:** MODERATE with A2 (both raise effective sample size; K and shrinkage-strength are
  partly substitutable and their gains are **sub-additive**, so do not add their measured effects),
  MODERATE with A4 (a longer window crossing a league-level drift needs the drift term).
- **Leakage risk:** LOW for variants 1–2 (pure lagged windows). MODERATE for variant 3: the state-space
  hyperparameters (`Var(eta)`, `sigma^2`) must be fitted on strictly earlier data or held-out blocks;
  a whole-sample MLE leaks.
- **Expected information gain:** **HIGHEST in Category A.** It is the only entry whose ceiling
  (≈0.09 MAE at K=30) is a meaningful fraction of the ≈0.166 absolute ceiling.
- **Implementation complexity:** LOW for variants 1–2 (a constant change and a weight vector).
  HIGH for variant 3.
- **Falsifier:** if MAE at K=20 and K=30 is not below K=10 on full-window rows *and* the EWMA
  half-life optimum sits at or below 10 games, then team pace level drifts fast enough that the
  incumbent's K=10 is already near-optimal and this family — and with it most of the headroom in
  §0.2 — is closed.
- **Changes what:** TOTAL. Also CALIBRATION: a longer window narrows the projection's own dispersion,
  which interacts with A9.
- **Recommendation:** if only one arm is affordable, run variants 1–2 of this family. The K sweep is
  the cheapest informative experiment in the whole stage.

---

### A4 — Non-stationary league anchor and season-boundary drift correction

- **Source:** time series / regime and level drift / hierarchical level decomposition.
- **Mechanism:** two related defects.
  (a) The level-3 prior is a **cumulative all-history mean** (`build_projected_exposure.py`:
  `by_date["sum"].cumsum().shift(1) / by_date["count"].cumsum().shift(1)`). By 2026 it is a five-season
  average and lags the current league level; in early 2021 it is estimated from a handful of games.
  Replace with a recent-window or local-level league estimate.
  (b) The prior-season fallback carries **bias −2.84** — it applies last season's *absolute* level to
  this season. Decompose instead into `league_level + team_deviation`: carry forward the team's
  prior-season *deviation* and re-anchor it on the **current** season's league level estimated from
  strictly-earlier games league-wide. The league level updates fast (many teams contribute per date),
  so it is well identified even at game 1 of a team's season after the league has opened.
- **Expected direction:** the `team_window_prior_season` bias moves from **−2.84 toward 0**; the
  `game_no_in_season` 1–3 bias moves from **−2.17 toward 0**. Direction is unambiguous and signed. The
  sign of the residual bias also **directly tests a secular upward league pace drift** across 2021–2026,
  which is the natural explanation for a systematic negative fallback bias plus 2021 bias +0.72 and
  2026 bias −0.27.
- **Affected stratum:** `team_window_prior_season` (183), `league_prior_all` (37),
  `game_no_in_season` 1–3 (228) — heavily overlapping, ~250–300 distinct rows.
- **Cutoff-valid inputs:** league-wide `game_pace` over strictly earlier dates (already computed by the
  incumbent), plus the same restricted to the current season. Nothing new.
- **Inputs exist:** YES.
- **Overlap risk:** **HIGH — but as a prerequisite, not a competitor.** A2 shrinks toward a league
  anchor; if that anchor is the incumbent's stale cumulative mean, A2 inherits the defect. A4 should
  be implemented *inside* A2 rather than scored as a separate arm, and its contribution isolated by
  ablation.
- **Leakage risk:** **MODERATE and the highest in Category A.** "Current season league level" is the
  one construction here that can silently include same-day or future games. The league mean must be
  restricted to *strictly earlier dates*, and same-date games must be excluded — the incumbent's own
  `.shift(1)` on a date-grouped cumsum does this correctly and the pattern should be copied verbatim
  rather than re-derived.
- **Expected information gain:** MODERATE-HIGH per affected row (bias 2.84 is large), LOW-MODERATE
  pooled (≈0.045 MAE ceiling, §0.3).
- **Implementation complexity:** LOW-MODERATE.
- **Falsifier:** if the residual bias on `team_window_prior_season` after drift adjustment is still
  below −2.0, the fallback's error is not a league-level drift and the diagnosis is wrong — the more
  likely alternative being roster turnover (Category B, B3).
- **Changes what:** TOTAL and ALLOCATION. Explicitly a **re-centring**, in strata where re-centring is
  justified even though the pooled bias is ~0.

---

### A5 — Opponent and schedule-mix adjustment (two-way additive with ridge)

- **Source:** partial pooling / design imbalance.
- **Mechanism:** a team's trailing mean is contaminated by which opponents happened to fall in the
  window. Estimate `mu`, `alpha_i` jointly by a ridge-regularised two-way additive model on strictly
  earlier games, so each team's level is opponent-adjusted rather than raw.
- **Expected direction:** reduces `Var(n)` by removing the opponent share. **Per Finding N2 that share
  is `2 tau^2/K ≈ 0.33` of `Var(n) = 2.73`, so the total effect is under 0.1 MSE ≈ 0.01 MAE.**
- **Affected stratum:** all rows, weakly; slightly more where the window's opponent mix is unbalanced
  (early season, post-break stretches).
- **Cutoff-valid inputs:** own and **opponent** strictly-earlier `game_pace` plus schedule identity.
  The packet lists opponent lagged pace as available and not used by the incumbent.
- **Inputs exist:** YES.
- **Overlap risk:** HIGH with A2 (the ridge penalty *is* shrinkage — a ridge two-way model and an
  empirical-Bayes hierarchical model are the same estimator with different parameterisations). Do not
  run both and add their gains.
- **Leakage risk:** LOW-MODERATE. The model must be re-estimated as of each date on strictly earlier
  games, which is expensive; a single whole-span fit would leak badly and is the obvious wrong
  shortcut.
- **Expected information gain:** **LOW.** I am recording it mainly so the programme does not spend a
  multiplicity slot on it under the impression that "the incumbent ignores the opponent" is a large
  defect. It is a real defect with a ceiling of roughly 0.01 MAE.
- **Implementation complexity:** MODERATE-HIGH (expanding-window refit at every date).
- **Falsifier:** if opponent-adjusted team levels correlate above ~0.98 with raw trailing means at
  full support, the adjustment is doing nothing and should be dropped.
- **Changes what:** TOTAL, marginally.

---

### A6 — History denoising and robust aggregation of the window

- **Source:** measurement error in the *predictor*; robust location estimation.
- **Mechanism:** the incumbent feeds each past game's raw `game_pace` into the mean. Each such value is
  contaminated by within-game state that says nothing about team tendency: blowout garbage time,
  late-game intentional fouling, technical-free-throw and zero-duration sequences. Reduce the
  measurement error of each historical observation before averaging. Variants, ONE family:
  1. compute each past game's pace over **competitive** possessions only, using
     `non_competitive_conservative` (verified present, zero nulls, boolean, 238,563 rows);
  2. exclude `possession_kind ∈ {zero_duration_sequence, technical_free_throw_sequence}` and/or
     `is_technical_derived` / `is_zero_duration` rows from the count (all verified present, zero nulls);
  3. compute pace over the first three periods only, or weight by `duration_sec` exposure;
  4. robust location over the window — trimmed mean, median, or Huber — instead of the plain mean.
- **Expected direction:** reduces `Var(n)`'s game-noise component (the dominant `2 sigma^2/K ≈ 2.40`
  of 2.73). If, say, a fifth of that component is removable state noise, MSE falls by ≈0.1–0.15
  → **≈0.01–0.02 MAE**. Modest, and I would not rank it above A3.
- **Affected stratum:** all rows; most where the window contains blowouts, OT games, or foul-heavy
  endings.
- **Cutoff-valid inputs:** possession-level `non_competitive_conservative`, `possession_kind`,
  `is_technical_derived`, `is_zero_duration`, `duration_sec`, `period`, `abs_score_diff_start` — all
  strictly-earlier games only. **Existence and zero-null coverage verified directly.**
- **Inputs exist:** YES, and completely.
- **Overlap risk:** LOW with A1/A2/A4. MODERATE with A3 (both reduce estimation noise; sub-additive).
- **Leakage risk:** **This is the entry where leakage is easiest to introduce accidentally.** The
  denoising must be applied to *history only*. The target must remain the full realised
  possession count of the target game. An implementation that also "cleans" the target is measuring a
  different, easier problem and will produce a spurious win. This should be an explicit gate check on
  the arm.
- **Expected information gain:** LOW-MODERATE. Its real value is that it is the only entry that
  attacks the *quality* rather than the *quantity* of history, and it composes cleanly with A3.
- **Implementation complexity:** MODERATE (needs a per-past-game re-derivation of pace from the
  possession stream rather than a lookup).
- **Falsifier:** if state-restricted historical pace correlates above ~0.99 with raw historical pace
  at the game level, there is nothing to denoise. Check that correlation first — it is a one-line
  distributional check and it kills or confirms the whole family before any arm is built.
- **Changes what:** TOTAL.

---

### A7 — Target-unit reconciliation: regulation-equivalent versus actual-length possessions

- **Source:** measurement error in the target itself; unit consistency.
- **Mechanism / the finding:** these two facts are both verified and they are in tension.
  - The evidence packet's target is **regulation-equivalent**:
    `build_evidence_packet.py:53` computes `realised_off_poss = n_off_poss * 40.0 / game_minutes`.
    The projection is likewise a regulation-equivalent quantity. Internally consistent.
  - `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet` carries
    `team_off_possessions` as **int64, verified all-integer-valued, zero nulls** — i.e. the **raw
    actual-length** possession count.
  - `team_turnovers_total` is likewise a raw actual-game count.

  So the packet's `implied_team_tov_rate` is `raw_turnovers / regulation_equivalent_possessions`,
  which is inflated on the 132 overtime team-games. More importantly, **if the operational
  turnover-team metric is scored against raw actual-game possessions rather than regulation-equivalent
  ones, then the diagnostic in the packet is measuring a different target from the one that matters.**
  Under a raw target, each overtime team-game would carry an error of roughly −9 to −10 possessions,
  and the 132 OT rows alone would contribute on the order of `132/2982 × 90 ≈ 4.0` to MSE — comparable
  to *thirty times* the entire Category A headroom.
- **Expected direction:** **I am not asserting a defect. I am asserting that the unit question is
  unresolved and is worth more than every estimator refinement in this document combined.** If the
  operational target is regulation-equivalent, nothing changes and this entry costs one verification.
  If it is raw, then (i) the current diagnostic understates operational error dramatically, and (ii)
  the correct projection is `regulation_equivalent × E[game_minutes]/40`, where the multiplier
  (≈1.006 league-wide, from the ~4.4% OT rate) is a knowable-at-cutoff expectation. That correction
  would *worsen* measured bias against the reg-equivalent target and *improve* it against the raw one.
- **Affected stratum:** `went_ot = True` (132 rows) in the extreme; all rows via the level multiplier.
- **Cutoff-valid inputs:** none beyond a league OT base rate estimated from strictly earlier games.
- **Inputs exist:** YES.
- **Overlap risk:** NONE. This is orthogonal to every estimator hypothesis.
- **Leakage risk:** **The one real trap:** actual game length is a target-game outcome and is NOT
  cutoff-valid. Only the *expected* multiplier from a lagged league OT rate may be used. Any
  implementation reading `max_period` for the target game is leaking.
- **Expected information gain:** **HIGH — as a governance and correctness finding, not as an MAE win.**
  A challenger tuned against the regulation-equivalent target could be operationally worse if the
  operational objective is raw.
- **Implementation complexity:** LOW (verification), LOW (the multiplier if needed).
- **Falsifier:** read the turnover-model scoring code and determine which possession quantity it
  consumes. If it consumes the regulation-equivalent projection consistently on both sides, this
  entry closes immediately.
- **Changes what:** TOTAL and CALIBRATION, and potentially the definition of the metric itself.
- **Recommendation: settle this before registering any arm.** It is cheap and it conditions the
  meaning of every subsequent number.

---

### A8 — Adaptive window via changepoint detection

- **Source:** structural breaks / regime change.
- **Mechanism:** run a CUSUM or binary-segmentation changepoint statistic on each team's
  strictly-earlier `game_pace` series; on detection, truncate the window to post-break games.
- **Expected direction:** shortens the window for teams with a genuine regime shift, reducing bias at
  the cost of variance.
- **Affected stratum:** in principle, teams mid-season after a personnel or tactical shift. In practice
  unidentifiable — see below.
- **Cutoff-valid inputs:** own strictly-earlier `game_pace`. Exists.
- **Overlap risk:** MODERATE with A3 (an adaptive window is a data-dependent K).
- **Leakage risk:** LOW mechanically; HIGH statistically via detection-then-estimation on the same
  series (post-selection inference).
- **Expected information gain:** **LOW. I expect this hypothesis to fail and I am including it
  deliberately.**
- **Why I expect it to fail:** the signal-to-noise ratio for break detection here is
  `tau/sigma ≈ 1.28/3.46 ≈ 0.37`. A changepoint test on 10–20 observations at SNR 0.37 fires
  overwhelmingly on noise. Truncating a window on a false positive *raises* variance in exactly the
  low-support regime that is already the worst stratum. The expected effect is a small MAE
  **increase**.
- **Why include it anyway:** (i) it is the natural null against which A3's fixed/EWMA weighting should
  be judged — if adaptive truncation loses, that is affirmative evidence that team level is stable and
  longer windows are safe, which is the key open question in §0.5(2); (ii) it is the arm that a
  Category B coaching table (B1) would convert from an inference problem into an *observation* problem,
  so its failure now establishes the value of B1.
- **Implementation complexity:** MODERATE.
- **Falsifier:** it falsifies itself — a detection rate materially above the nominal false-positive
  rate, coupled with no MAE gain, confirms it is firing on noise.
- **Changes what:** TOTAL and ALLOCATION.

---

### A9 — Emit predictive uncertainty and a reliability field (no change to the point estimate)

- **Source:** heteroscedastic support; calibration versus dispersion.
- **Mechanism:** the incumbent emits a bare point estimate. Its conditional error variance is strongly
  heteroscedastic and *predictable at cutoff* from `n_history_games` and `pace_level` alone — the
  packet publishes sd 3.62 at full window, 3.69 at support 3–4, 3.71 at prior-season fallback, 4.90 at
  league prior. Emit `projected_possessions_sd` and a reliability weight alongside the point estimate.
- **Expected direction:** point estimate and possession MAE **unchanged by construction**. Downstream
  turnover error becomes weightable/abstainable, and any interval or simulation consumer becomes
  correctly calibrated.
- **A tension the stage must decide explicitly:** the current projection has predictive variance of
  roughly `0.25 × Var(S_hat) ≈ 1.5` against a target variance of 15.27 — **it is already about 3.2×
  under-dispersed**, which is *correct* for MSE and *wrong* for anything that simulates from it. Every
  hypothesis above that increases shrinkage (A1 low-support, A2) makes the projection **more**
  under-dispersed. **"Without degrading calibration" and "minimise MAE" are in direct conflict here**,
  and the conflict is currently invisible because no dispersion diagnostic is reported. Any arm should
  report the projection's own sd next to its MAE.
- **Affected stratum:** all; most valuable on `league_prior_all` (sd 4.90) and support >10 (sd 5.50).
- **Cutoff-valid inputs:** `n_history_games`, `pace_level` — already in the incumbent's output.
- **Inputs exist:** YES.
- **Overlap risk:** NONE with the point-estimate hypotheses; it is an additive output field.
- **Leakage risk:** LOW-MODERATE (the variance function must be estimated on strictly earlier data).
- **Expected information gain:** MODERATE for the programme, ZERO for possession MAE.
- **Implementation complexity:** LOW.
- **Falsifier:** if a support-conditioned predictive sd is not better calibrated than a single pooled
  sd (by coverage or CRPS on chronological hold-out), the heteroscedasticity is not exploitable.
- **Changes what:** **CALIBRATION only.** It cannot move the possession total and must not be scored
  on MAE.

---

### A10 — Schedule-context terms estimated *jointly* with the pooling, not layered on top

- **Source:** my mandate only in the specific methodological claim below.
- **Mechanism:** `days_rest`, back-to-back, `game_no_in_season` and schedule density are cutoff-valid
  (packet: 2990/2990 coverage) and the packet shows real signal — long rest (7+, n=162) carries bias
  **−1.43** (teams play faster than projected after long rest), back-to-backs (n=89) **+0.50**, with a
  monotone gradient in between.
- **My distinct contribution here is a warning, not the feature.** These covariates are very likely
  another source's mandate, and the overlap risk is HIGH. What this source adds: **a context
  adjustment estimated on the incumbent's raw residuals and then added to a shrunk estimate
  double-counts.** The residuals of an unshrunk estimator contain estimation noise that a shrinkage
  estimator will already have removed; a rest coefficient fitted on those residuals absorbs part of it
  and will be biased upward. Context terms must enter as fixed effects **inside** the hierarchical
  model of A2/A3, estimated jointly, or the two changes will not compose.
- **Expected direction:** removes the −1.43 long-rest and +0.50 b2b biases. Budget from §0.3:
  **≈0.010 MAE pooled.** Small.
- **Affected stratum:** `days_rest` 7+ (162), 0–1 (89) — 251 rows, 8.4%.
- **Cutoff-valid inputs:** schedule dates only. Exist (2990/2990).
- **Overlap risk:** **HIGH with other sources.** Recorded for the composition warning; I do not claim
  it.
- **Leakage risk:** LOW.
- **Expected information gain:** LOW on its own; MODERATE as a constraint on how arms are combined.
- **Implementation complexity:** LOW.
- **Falsifier:** if the rest gradient's sign flips or vanishes once estimated jointly with shrinkage,
  it was an artifact of the incumbent's estimation noise, which is precisely the double-counting the
  warning describes.
- **Changes what:** TOTAL and ALLOCATION.

---

### Two Category A items that are DIAGNOSTICS, not arms

**D1 — Bound the target's own measurement noise using a second, independent possession derivation.**
`data/masters/master_team.parquet` (verified: 2990 rows, 65 columns) carries `fga`, `fta`, `oreb`,
`tov` and their `opp_` counterparts, which support the classical box-score possession estimator
`FGA − OREB + TOV + 0.44·FTA`. The packet's target comes from a PBP-derived possession stream carrying
`is_technical_derived`, `is_zero_duration`, `source_order_differs` and `inferred_flip` /
`miss_flip_no_rebound` end reasons (all verified present, zero nulls), and two distinct
`source_system` values appear in the reconciliation artifact (`nba_playbyplayv2`,
`nba_cdn_playbyplay`). Comparing the two derivations on the same games bounds how much of my
`sigma^2 ≈ 12.00` is **target measurement error rather than team behaviour**. If a non-trivial share
is measurement error, the 12.00 floor is optimistic, the true headroom is *below* 0.166 MAE, and the
programme should stop earlier than it otherwise would. This is a distributional comparison of two
existing columns, not a model. **It should run before any arm is registered.**

**D2 — Adopt the clustering and pairing protocol of §0.6.** Score at game level (n≈1491), compare
paired on identical games, and pre-declare the arm count. At a realistic headroom of 0.10–0.15 MAE
against an unpaired SE of ≈0.057, an unpaired multi-arm comparison cannot distinguish a winner from
selection noise.

---

## CATEGORY B — high value, currently unavailable

These may not become arms. Each records: missing input; why it may matter *from a time-series and
shrinkage standpoint specifically*; minimum viable collection; whether prospective-only validation is
required; expected value of closing the gap.

### B1 — Coaching identity and coaching-change events

- **Missing input:** a coach-by-team-season table with mid-season change dates. Packet confirms
  ABSENT; a `*coach*` sweep over `data/` returns nothing.
- **Why it matters (my lens):** it converts structural-break detection from an *inference* problem at
  SNR 0.37 — which A8 argues is hopeless — into an *observation* problem. With observed break dates
  the window resets exactly and the prior-season fallback can be down-weighted precisely when the
  regime that generated it no longer exists. It is the single instrument that rescues A8 and sharpens
  A2's prior-season shrinkage target.
- **Minimum viable collection:** ~72 rows (12 teams × 6 seasons) plus mid-season change dates, hand
  maintained from public records. Cheap.
- **Prospective-only validation required:** **NO.** Coaching identity is public before tip, so a
  retrospectively constructed table is genuinely cutoff-valid provided the *change date* is the
  announcement date, not a backdated effective date. (This is exactly the distinction the exposure
  erratum already draws between captured-as-of and retrospective-effective-date evidence — the same
  trap applies here.)
- **Expected value:** small pooled (a handful of transitions per season, perhaps 3–8% of team-games in
  a transition window), potentially 1–3 possessions per affected row. Order 0.01–0.02 MAE pooled.
  Its real value is diagnostic: it tells you whether the residual `sigma^2` contains regime structure
  at all.

### B2 — Pregame availability / injury feed with historical depth

- **Missing input:** packet confirms `data/injury_capture/injury_log.csv` covers 2026-07-30 to
  2026-08-04 only — 6 days of a 5-season span.
- **Why it matters (my lens):** this is where my `sigma^2 ≈ 12.00` "irreducible" floor could actually
  be lowered. Availability shocks are the main generator of genuine short-run level shifts in a team's
  pace; without them, injury-driven regime changes sit inside the trailing window disguised as noise
  and are structurally unrecoverable by *any* estimator using pace history alone. Note the asymmetry:
  A3's longer windows are only safe if such shocks are rare; if they are common, longer windows will
  underperform and the failure will be misread as "team level drifts."
- **Minimum viable collection:** persist the existing capture forward from 2026-07-30; backfill only
  from an archival source with a verifiable observation timestamp.
- **Prospective-only validation required:** **YES**, and strictly. Any backfill without a captured
  observation time is retrospective and inadmissible on the same grounds the exposure erratum used to
  reject transaction Tier B.
- **Expected value:** potentially the largest of any item in this document, because it is the only one
  that attacks `sigma^2` rather than `Var(n)`. Unquantifiable from the frozen evidence. Multi-season
  lead time before it can be validated.

### B3 — Verified as-of roster continuity index (partially constructible — GATED)

- **Missing input:** an independently verified point-in-time roster feed. The prediction contract
  (`experiments/prediction_contract_v5/player_game_enriched.parquet`, 44,851 rows, 63 columns) does
  carry `candidate_evidence_time`, `candidate_published_time`, `candidate_observed_time`,
  `src_asof_roster`, `roster_evidence_regime` and `n_prior_team_games`, and the A_primary tier is
  declared `captured_asof`. So a roster-continuity index — the share of last season's team minutes
  carried by players in the cutoff-available candidate set — is *mechanically* constructible today.
- **Why it matters (my lens):** it is the missing covariate that should govern **how much to shrink
  toward the prior season**. A4 diagnoses the −2.84 fallback bias as league drift; roster turnover is
  the competing explanation, and in a 12-team league with high offseason turnover it is a strong
  candidate. A continuity index would make A2's shrinkage weight a function of *how much of the team
  is still the same team*, which is the statistically correct thing for the prior-season target and is
  currently assumed to be constant.
- **Why it is in Category B and not A:** it depends entirely on the contract's own cutoff-validity
  declarations, and the packet is explicit that a construction receipt *binds* such a declaration but
  cannot *verify* it (`PROGRAM_STATE` gap `cutoff_validity_asserted`). Per my instructions I do not
  treat `cutoff_valid: true` as proof. **This may move to Category A the moment the A_primary as-of
  candidate evidence is independently verified — and it is the item with the best
  value-per-unit-of-verification-effort in this document.**
- **Minimum viable collection:** none new; an independent verification of existing timestamps.
- **Prospective-only validation required:** NO if verification succeeds; YES if it does not.
- **Expected value:** MODERATE. It would sharpen A2/A4 on the ~250–300 season-boundary rows and could
  plausibly capture a majority of that stratum's 0.045 MAE budget.

### B4 — Historical span before 2021

- **Missing input:** possession-level data earlier than the 2021 season.
- **Why it matters (my lens):** this is not about more training rows for a predictor — it is about
  estimating the *shrinkage constants*. `tau^2`, `sigma^2`, the local-level drift variance and the
  league-drift rate are all estimated from 1495 games across 6 seasons. §0.6 shows the headroom is only
  2–3 unpaired SE wide; hyperparameters estimated on a span this short carry selection variance
  comparable to the effect being measured. More span narrows the shrinkage constants directly.
- **Minimum viable collection:** extend the existing possession derivation backward over the same
  source systems.
- **Prospective-only validation required:** NO — it is history.
- **Expected value:** LOW-MODERATE and indirect: it does not raise the ceiling, it raises confidence
  that a chosen arm is genuinely better rather than selected on noise.

### B5 — Venue table with coordinates (travel and time-zone deltas)

- **Missing input:** packet confirms ABSENT; ~12 rows would suffice.
- **Why it matters (my lens):** only as an extension of A10's rest gradient, which already shows real
  signal (7+ rest bias −1.43). Travel would refine it.
- **Minimum viable collection:** a static 12-team venue table with coordinates. Trivial.
- **Prospective-only validation required:** NO.
- **Expected value:** LOW. A10's *entire* stratum budget is ≈0.010 MAE and travel would capture a
  fraction of it. Recorded for completeness; I would not spend on it.

### B6 — An independent second possession count (measurement replicate)

- **Missing input:** an authoritative external possession count per team-game, independent of the PBP
  derivation.
- **Why it matters (my lens):** D1 can *bound* target measurement noise using the box-score estimator,
  but the box-score estimator is itself an approximation with its own error, so D1 gives a bound and
  not a decomposition. A genuinely independent count would separate "the model cannot predict this"
  from "the target is not measured precisely" — which decides whether the 12.00 floor is real.
- **Minimum viable collection:** a licensed or official possession/pace feed for the same games.
- **Prospective-only validation required:** NO — historical games can be re-counted.
- **Expected value:** MODERATE for the programme's epistemics, ZERO for MAE. It would tell you when to
  stop, which at a headroom of 0.166 MAE is worth knowing.

### B7 — Pregame market total with history

- **Missing input:** packet confirms capture begins 2026-07-31, after the modelling span.
- **Why it matters (my lens):** a market total is a *consensus* estimator built on strictly more
  information than lagged pace, so its residual against realised pace directly measures how much of
  my `sigma^2 ≈ 12.00` is genuinely irreducible versus merely unavailable-to-us. That is a bound on
  the whole programme.
- **Minimum viable collection:** persist odds capture forward.
- **Prospective-only validation required:** YES.
- **Expected value:** HIGH as a *benchmark*, questionable as a *feature* — I echo the packet's own
  caution that a market input changes what the artifact is. My recommendation is to collect it as a
  yardstick for the irreducible floor, not as a model input.

---

## Summary of this source's position

1. **The possession projection is much closer to its information ceiling than it looks.** Under a
   variance-components model that reproduces the packet's `residual_variance` to three decimals, the
   absolute ceiling for any estimator built on lagged pace history is ≈0.166 MAE (5.7%), and a
   realistic Category A programme is worth ≈0.10–0.15 MAE.
2. **That is worth ≈0.01–0.03 turnovers per team-game operationally.** If the turnover-team objective
   needs more than that, it cannot come from the possession count.
3. **The most attractive-looking change is a null.** The incumbent's `(a+b)/2` is within 0.05 of the
   MSE-optimal pair-shrinkage at K=10. Opponent adjustment and within-game team differentiation are
   also near-null, with stated ceilings.
4. **The one lever with real headroom is effective sample size** — window length, recency weighting,
   local-level filtering (A3). It is also the cheapest to test.
5. **The packet's "bias is negligible" reading is right pooled and wrong conditionally.** The pooled
   bias is near zero by cancellation of large opposite-signed stratum biases; stratum re-centring
   (A2 + A4) is legitimate and worth ≈0.05–0.07 MAE.
6. **A7 (regulation-equivalent versus actual-length possessions) may matter more than every estimator
   change combined**, and should be settled before any arm is registered.
7. **The evaluation protocol currently overstates precision by ~sqrt(2)** — 1491 independent
   projections, not 2982 — and at this headroom that is decisive.
