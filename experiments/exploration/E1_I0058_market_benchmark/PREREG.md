# PREREG — E1_I0058_market_benchmark

**Decision:** D138.
**Question:** does this program's player-points forecast add anything to a real market price?
**Written:** after `run_log_s00.txt` (structural probe: shapes, keys, digests, join rates,
partition boundary) and **before any statistic involving the outcome `pts` was computed.**
**Hash of this file at freeze time:** see `PREREG.sha256`.

**RULE OF THIS DOCUMENT.** If a prediction below fails, the failure is recorded in
`FINDINGS.json` and `NOTES.md` as a FAILURE. No threshold, seed, draw count, arm, reference or
subgroup in this file is revised after freezing. Anything not in this file that is nevertheless
computed is labelled POST-HOC everywhere it appears.

---

## 0. The partition, and why this screen can only use one season

The boundary is the repository's own, not an assumption:
`experiments/exploration/_screen_kit/screenkit.py`

```
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS     = (2025, 2026)      # FORBIDDEN
```

`master_props_historical.csv` carries 2024 (11,237 rows), 2025 (15,053) and 2026 (10,656).
**Only the 2024 rows may be touched.** 2025 and 2026 are the confirmation holdout and are
excluded by a filter applied *before* any other operation, proven row-by-row in
`PARTITION_PROOF.md`. The prices calibration in §3.3 uses **2021–2023**, also exploration.

## 1. Population, and the selection that defines it

**Unit of analysis: the player-game obligation** (`row_uid = sha256(player_id, game_id, team_id)`,
reproduced from `cbs_obligation_key/1` and asserted byte-equal in s00).

Admitted iff **all** of:

1. `master_player.season == 2024`;
2. `minutes > 0` (the player actually played) — required because the model target is a
   **conditional-on-active** centre (§2), and a prop on a DNP is not a points forecast problem;
3. at least one bookmaker row for `market_key == "player_points"` matched **exactly** on the
   normalised name key, with non-null `line`, `over_price` and `under_price`;
4. a forecast exists in the primary anchor (§2).

Expected n ≈ **1,972 obligations, 78 players, 262 games** (s00).

> **SELECTION STATEMENT — attached to every number this screen produces.**
> These are **40.2% of season-2024 played player-game rows**. Books price the players they
> choose to price: high-minute, high-usage, nationally visible players. **Every figure in this
> screen is conditional on the book-priced population.** Nothing here may be generalised to
> unpriced players, and no statement of the form "the model is behind the market on player
> points" may be made without that clause.

**Name join.** Exact match on `norm(name) = ascii-fold → lowercase → drop non-letters`. **No
substring, fuzzy or nickname matching, anywhere.** s00 measured 78/79 distinct props names
matched (98.7%); the single miss is `cheyenneparker` (62 book rows, 0.55%), which is **dropped
and reported**, not repaired. Zero (game, normalised-name) keys map to more than one obligation.

## 2. The model arm — what it is, and why it is the honest anchor

**F1 (PRIMARY): `cbs_v15_player_oof_v5/1`**,
`experiments/cbs_v15_player_oof_v5/attempt_001/predictions__player_scoring_distribution__2024.parquet`,
column `pred_point`. sha256 `f01151ef…28cd21`, **re-hashed from the bytes on disk and matched
against its own committed manifest in s00.**

*What that column actually is* (D086 — read the construction). `cbs_v7.conditional_center`:

```
pred_point = ewma_walkforward(points_per_36) * ewma_walkforward(minutes) / 36
```

i.e. **E[points | the player is active]**, both legs walk-forward over history *knowable at the
cutoff*. It is not an unconditional expectation. This is why §1 restricts to played rows.

*Why this anchor and not another.* It is the only registered, chronological, out-of-fold,
provenance-sidecar-carrying player-points forecast this repository contains for 2024. It is the
program's own accepted player path (`prediction_contract_v5` universe, `cbs_v14` estimator
unchanged). Nothing better exists to score; if a better one existed it would be used.

**F2 (ROBUSTNESS ONLY): `cbs_v14_player_oof/1`** — same estimator over the v4 contract universe,
sha256 `955f534c…cb8388`, manifest matched. Reported only to show the result does not turn on
the anchor choice. **F1 is the headline; F2 never replaces it.**

**Pre-game verification (not assumption).** s00 established: `feature_asof < forecast_cutoff` on
100% of rows; `forecast_cutoff` precedes tip on 100% of rows; the market snapshot precedes
`commence_time` on 100% of rows (median lead 1.156 h). `pts` enters this screen **only as the
response**, never as a regressor, in any stage.

## 3. The market arms

Per (obligation, bookmaker) the **latest snapshot before tip** is taken (s00: up to 5 snapshots
per event/book exist; the last one is used, and its lead time is reported).

### 3.1 M1 — the raw line (RAW BENCHMARK)
`M1 = median over books of line`. Reported because **the line is a betting line, not a mean
forecast**: it is set to balance two-sided action, so its distance from E[pts] is exactly the
quantity §3.2 tries to recover.

### 3.2 M2 — the de-vigged central estimate (PRIMARY MARKET ARM)

Per book: American odds → implied probabilities → **proportional (multiplicative) de-vig**,
`p_over_fair = p_over_raw / (p_over_raw + p_under_raw)`.

*Assumption stated:* the book's margin is a common multiplicative factor on both sides. It
introduces no favourite–longshot correction of its own. It is exact only if the book prices that
way; it is the standard method and the neutral one.

Then, assuming points are locally Gaussian around the book's central estimate,

```
mu_book = line + sigma(line) * Phi^-1(p_over_fair)
M2      = mean over books of mu_book
```

*Assumption stated:* points are discrete, non-negative and right-skewed, so the Gaussian
inversion is an approximation. Its only job is to convert a small probability tilt into a small
points tilt; over the range `p_over_fair ∈ [0.4, 0.6]` the mapping is near-linear and the choice
of tail shape is second-order. **This is declared a limitation, not a result.**

### 3.3 `sigma(·)` — calibrated on 2021–2023 only, with no props and no 2024 outcome

Player-seasons in `master_player`, seasons **2021, 2022, 2023** (exploration; the props file does
not reach them), played rows only, player-seasons with **≥ 10 played games**. For each,
`mu_ps = mean(pts)`, `s_ps = sd(pts)`. Fit by OLS:

```
s_ps = a + b * sqrt(mu_ps)        ->      sigma(x) = a + b * sqrt(max(x, 0))
```

Coefficients are frozen the moment they are fitted and reported in `FINDINGS.json`.
`sigma` is clipped to `[1.0, 15.0]`.

### 3.4 M3 — additive-margin de-vig (SENSITIVITY ONLY)
`p_fair = p_raw - (p_over_raw + p_under_raw - 1)/2`, otherwise identical to §3.2. Never headline.

## 4. Metrics and the reference, stated explicitly

**Reference incompleteness is this program's top-ranked source of wrong answers (D087/D136).**

**Headline metrics are reference-free: MAE and RMSE.** They require no baseline and cannot move
6.5× on a reference choice.

Where a proportional-skill number is wanted, R² is reported **against a named ladder**, and the
name travels with the number, always:

| ref id | reference | honest? |
|---|---|---|
| `R0_grand_mean` | mean `pts` over the admitted population | **the honest denominator for this screen.** It is the only reference that is (a) defined on exactly the population being scored and (b) not a forecast anyone could have made better. Reported as the headline R². |
| `R1_player_season_mean` | each player's own 2024 season mean `pts` | **RETROSPECTIVE — not a forecast.** Reported only as a ceiling-flavoured yardstick and labelled retrospective at every occurrence. |
| `R2_market_raw` | M1 | skill of a forecast *relative to the raw line* |

**Declared in advance:** `R0_grand_mean` is the honest reference for the headline R². The others
exist so the reader can see how far the number moves — which is itself reported.

**Materiality floor:** an MAE or RMSE difference below **0.10 points** is called a TIE regardless
of any interval or p-value.

## 5. THE DECISIVE TEST — forecast encompassing

OLS on the admitted obligations:

```
(A)  pts_i = a + bM * M2_i + bF * F1_i + e_i        # does the model add to the market?
(B)  pts_i = a + bF * F1_i + bM * M2_i + e_i        # identical fit; both coefficients reported
```

The four preregistered outcomes:

* **bF indistinguishable from 0, bM not** → *market encompasses model*: **the program has no edge
  on this population, and that is the answer.**
* **bF distinguishable from 0** → model adds; to be treated with extreme scepticism and
  interrogated against §7 before any positive claim.
* **both distinguishable** → report combination weights.
* **neither** → construction is suspect; report as a construction failure, not a finding.

Also fitted and reported: univariate `pts ~ M2`, `pts ~ F1`, and `pts ~ M1`.

**"Distinguishable from zero" requires BOTH:** (i) the 95% cluster-bootstrap percentile interval
excludes 0, **and** (ii) the two-sided permutation p-value < 0.05.

## 6. Inference — clustering, nulls, seeds, draw counts

**Rows are not independent.** Classical t-statistics on this program's data have been found
untrustworthy twice independently, and cluster-robust SEs are **not** accepted here as a
substitute. **No classical or cluster-robust SE is used for any headline interval.**

**6.1 Cluster bootstrap (intervals).** Pairs bootstrap resampling whole clusters with
replacement, refitting the regression each draw, 95% percentile intervals.

* `BOOT_GAME`: cluster = `game_id` (262 clusters). **seed 20240817, 5000 draws.**
* `BOOT_PLAYER`: cluster = `player_id` (78 clusters). **seed 20240817, 5000 draws.**
* **The headline interval is the WIDER of the two**, declared now, before seeing either.

**6.2 Permutation null (p-values).** **`SCHEME_WITHIN_CYCLIC` — the cyclic within-player shift
(D093).** The model forecast is a `shift(1).expanding()`-shaped regressor (walk-forward EWMA);
a plain within-player shuffle destroys its autocorrelation while the response keeps its drift
and is therefore **anticonservative**. The cyclic shift preserves each player's marginal
distribution *and* serial structure and destroys only the alignment to the response.

* Null for `bF`: cyclically shift `F1` within `player_id`, refit (A), record `bF`.
* Null for `bM`: cyclically shift `M2` within `player_id`, refit (A), record `bM`.
* Rows are ordered by `game_date` within player; the shift offset is drawn uniformly from
  `1..n_p-1`. **seed 20240818, 5000 draws.** Two-sided p = share of |null| ≥ |observed|,
  with the +1/+1 correction.

**6.3 MDE — computed and reported BEFORE the null is interpreted.**
`MDE(bF) = 2.802 * SD_bootstrap(bF)` (80% power, α = 0.05 two-sided). Also reported in
interpretable units: the MAE improvement of the fitted combination over M2 alone that a
coefficient of exactly `MDE(bF)` would deliver. **An underpowered null is not a finding (D136);
if `MDE(bF)` is large relative to 1.0, the null is reported as UNINFORMATIVE, not as evidence of
no edge.**

## 7. The five preregistered predictions (pass/fail recorded either way)

| id | prediction | threshold |
|---|---|---|
| **P1** | Market **M2** has lower MAE than model **F1** | `MAE(F1) - MAE(M2) > 0.10` |
| **P2** | In (A), **bF is NOT distinguishable from 0** — market encompasses model | both criteria in §5 fail for `bF` |
| **P3** | In (A), **bM IS distinguishable from 0** | both criteria in §5 hold for `bM` |
| **P4** | De-vigging materially improves the market estimate | `MAE(M1) - MAE(M2) >= 0.05` |
| **P5** | The raw line sits **above** realised points on average (books shade the over) | `mean(M1) - mean(pts) > 0`, bootstrap 95% CI excludes 0 |

P1–P3 are the expected outcome. **P4 and P5 are genuinely uncertain and are expected to be
informative whichever way they land.**

## 8. Subgroups — pre-specified now, examined ONLY if §5 leaves something alive

Examined **only** if `bF` is distinguishable from 0 in (A). Exactly these four, no others,
Bonferroni α = 0.05/4 = **0.0125**:

1. **S1 minutes**: split at the median of the model's own *pregame* `e_minutes_given_active`
   forecast (never realised minutes — that would be retrospective).
2. **S2 cold start**: `fallback_level > 0` vs `== 0` in the anchor.
3. **S3 volume**: `M1 <= 10` vs `M1 > 10`.
4. **S4 book disagreement**: cross-book SD of `line` above vs below its median.

**No subgroup outside this list will be reported.** If §5 kills the model, §8 is not run at all
and `FINDINGS.json` says so.

## 9. Registered limitations, in advance

* One season, one league, ~1,972 obligations, 78 players. This is a **screen**, not a
  confirmation. Nothing here can promote anything.
* One snapshot regime (median 1.156 h before tip). Says nothing about lines at other times.
* Conditional on the book-priced population (§1).
* `sigma(·)` for the de-vig is a 2021–2023 extrapolation onto a 2024 population selected
  differently from the one it was fitted on.
* The Gaussian inversion in §3.2 is an approximation on a discrete, skewed variable.
* The dropped `cheyenneparker` rows are a known identity gap, reported not repaired.

## 10. Evidence level claimed in advance

At most **E1** (single-partition screen with preregistered nulls). **E2/E3 are impossible here**
by construction: the confirmation partition may not be touched.
