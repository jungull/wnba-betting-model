# E1 I0009 — opponent forced-turnover pressure, additive form

Family: `F_TURNOVER_PRESSURE`. Stage: **E1 (does the effect persist?)**.

**NON-CLAIMING (GRAPH_POLICY §13.1).** This is a **LEAD, never a RESULT**. No registry entry, no
preregistration, no leaderboard row, no bootstrap, no promotion threshold, no significance claim.
Nothing here may be cited as evidence for anything.

## Verdict

**`keep-as-lead`** — home/away does **not** kill it, and the effect persists out-of-sample in every
fold of two independent protocols. See "What this does not establish" before believing the size.

---

## Partition compliance

**Exploration partition only: 2021, 2022, 2023, 2024.** No 2025/2026 row was read, joined,
plotted, filtered against, counted, or described. **Partition incident: none.**

Filters are applied immediately after each parquet load, before any join or aggregation:

- `turnover_targets_v1/player_turnover_targets_v1.parquet` → `season.isin([2021..2024])` at load
  (18,216 rows survive; `rate_defined == True` leaves 18,178).
- `possessions_v2/possessions_raw_v2.parquet` → `season` is stored as **string**; cast to int, then
  the same filter (155,149 rows survive). 2025/2026 rows were touched only by the boolean mask.

**Artifact contamination check (§13.2.2).** `build_data.py` explicitly looks for a sibling
`<artifact>.manifest.json` for each input and asserts `asof_granularity == "row"` if one exists.
Neither input has a manifest; both are raw row-per-game / row-per-possession artifacts with an
explicit `season` column and no fitted cross-season parameter, so row-level filtering is sufficient.
(`master_team.parquet` — which *does* carry `asof_granularity: "row"` — was **not needed**: venue
comes from `is_home_offense` inside `possessions_raw_v2`, the same source E0 used, so no master was
opened and no `observed_time` column ever entered a frame. Both written CSVs are asserted free of it.)

**Verification is on COLUMN VALUES, not bytes.** Every written frame is checked on
`season.unique()` and `game_date.dt.year`. The byte-scan-for-"2025"/"2026" approach used elsewhere
in this program is **deliberately not repeated** — it produced a false partition violation by
matching row counts and digit runs inside floats.

---

## Reconciliation with E0 — and a reporting-convention discrepancy

The E1 frame is rebuilt from source and reproduces E0's frame exactly: 18,165 rows,
season counts `{2021: 3878, 2022: 4508, 2023: 4886, 2024: 4893}`, 13 rows dropped for thin
support, `corr(pressure_loo, pressure_pregame) = 0.861`, 464 pure-anchor rows.

**But E0's published ΔR² figures use a non-standard weighted-R² denominator.** E0 computed
`R² = 1 − SSE_w / Σ(y·√w − mean(y·√w))²` — the SST of the **sqrt-weight-transformed** response
around *its own* mean, rather than the weighted SST of `y` around the **weighted mean of y**. The
SSE numerators are identical; only the denominator differs, and E0's is larger, so **every E0 ΔR²
is ~8% smaller than the standard weighted figure.**

Recomputing under E0's own convention reproduces E0 to six decimals, which is the check that this
E1 rebuilt the same frame and the same predictor:

| | E1 under E0's convention | E0 published |
|---|---|---|
| rung-2 (pregame) pooled ΔR² | 0.006505 | 0.006505 |
| rung-1 (idealised) pooled ΔR² | 0.008424 | 0.008424 |
| rung-2 per season | 0.015038 / 0.005329 / 0.002279 / 0.006121 | identical |

β also matches exactly (+0.1244). **All E1 headline numbers below use the standard weighted R²**,
under which the E0-replication pooled ΔR² is **0.007035**, not 0.006505. This is a bookkeeping
difference, not a correction of E0's conclusion — the direction is conservative for E0.

---

## PART 1 — The uncontrolled confound: home/away

This was the first thing tested, because E0 flagged it as the most likely killer and because the
program has already killed I0010 for being "overall opponent strength in a position costume".

### 1a. The venue effect on forced turnovers is real

Forced turnovers per 100 defensive possessions, defending at home vs on the road:

| season | home | away | home − away |
|---|---|---|---|
| 2021 | 17.491 | 16.889 | +0.602 |
| 2022 | 18.001 | 17.434 | +0.566 |
| 2023 | 17.656 | 16.921 | +0.734 |
| 2024 | 17.806 | 17.162 | +0.643 |
| **pooled** | **17.746** | **17.106** | **+0.640** |

Teams do force meaningfully more turnovers at home, in every season, with a stable size. The
confound premise is correct as far as it goes.

### 1b. …but it is ~30x smaller than team identity

Weighted R² on the team-game forced-TO rate (n = 1,940 team-games):

```
season FE only          0.00168
season FE + venue       0.00608   venue increment = 0.00441
team-season FE          0.13175   team identity increment = 0.13007
team-season FE + venue  0.13618
```

**Team identity explains 29x more of a team-game's forced-TO rate than venue does.** Venue is a
small, real main effect sitting on top of a much larger team trait.

### 1c. The pressure measure is essentially orthogonal to venue — collinearity diagnostics

`opponent_pressure_pregame` is an expanding season-to-date team average over a mixed home/away
schedule, so it *cannot* track this game's venue, and it doesn't:

| season | r(pressure, player_is_home) | r(pressure, opp prior-home-share) | r(pressure, opp def rating) | R²(pressure ~ venue) | R²(pressure ~ venue + defrtg) |
|---|---|---|---|---|---|
| 2021 | +0.0164 | +0.0480 | −0.2278 | 0.00275 | 0.05142 |
| 2022 | +0.0169 | −0.0631 | −0.4404 | 0.00580 | 0.21017 |
| 2023 | +0.0258 | +0.1367 | −0.3330 | 0.02040 | 0.14391 |
| 2024 | −0.0193 | +0.1344 | −0.6190 | 0.02037 | **0.38320** |
| **pooled** | **+0.0079** | **+0.0589** | **−0.4050** | **0.00381** | **0.16240** |

- **Venue: 0.4% of the pressure measure's variance pooled** (worst season 2.0%). Not a costume.
- The schedule-imbalance channel — a team whose early games happened to be home-heavy looking more
  disruptive — was tested explicitly (`opp_prior_home_share`, the share of the opponent's prior
  games played at home) and is also near-zero.
- **Opponent defensive strength is the collinearity that actually matters**, at r = −0.405 pooled,
  and it is **strongly season-dependent**: −0.228 in 2021 rising to **−0.619 in 2024**, where
  venue + defensive rating jointly explain **38%** of the pressure measure's variance. See §2 and
  the caveats.

Home/away's own main effect on the *player* outcome is tiny: β = −0.0633, ΔR² = 0.000120.

### 1d. How much of the effect survives the home/away control

| model | baseline | pooled ΔR² | β | retained vs E0 replication |
|---|---|---|---|---|
| M_A E0 replication | tendency (LOO) | 0.007035 | +0.1244 | 100.0% |
| **M_B + venue** | + `player_is_home` | **0.007045** | +0.1245 | **100.1%** |
| M_C + schedule balance | + `opp_prior_home_share` | 0.007013 | +0.1245 | 99.7% |
| M_D + opponent def rating | + `opponent_defrtg_pregame` | 0.005999 | +0.1255 | 85.3% |
| M_E fully pregame baseline | pregame tendency + venue | 0.006765 | +0.1220 | 96.2% |
| M_F pregame + full control | + schedule + def rating | 0.005649 | +0.1218 | 80.3% |

**100.1% of the effect survives the home/away control** — controlling venue does not move it at
all, exactly as the orthogonality in §1c predicts. The coefficient is unchanged to three decimals.

Two further venue tests, both confirming the same thing:

- **Venue-stratified fits.** Inside home games only: ΔR² = 0.007200, β = +0.1242 (n = 9,085).
  Inside away games only: ΔR² = 0.006867, β = +0.1246 (n = 9,080). The effect is fully present in
  each venue stratum separately, at the same magnitude. A venue artifact would not do this.
- **A venue-matched pressure measure is strictly worse.** Rebuilding the measure from only the
  opponent's prior games *on this side of the venue* gives ΔR² = 0.005804 (down from 0.007045), and
  adding it **on top of** the venue-blind measure buys **ΔR² = 0.000020** — nothing. The venue
  component of a team's pressure carries no usable signal; halving the sample to chase it only adds
  noise. The signal is the team, not the building.

**Conclusion on the confound: home/away is a real main effect on forced turnovers, but it is not
what this predictor is measuring. This is NOT the I0010 failure shape.** The I0010 kill was
"most of the measure's variance is an obvious main effect"; here venue accounts for 0.4%.

---

## PART 2 — Does it persist out-of-sample inside 2021-2024?

Two protocols, not a single split. Out-of-sample ΔR² = `(SSE_base − SSE_full) / SST`, with SST taken
around the **training-set** weighted mean and all coefficients fit on training folds only.

### Leave-one-season-out (train on the other three)

| hold-out | M_B (venue ctrl) | M_D (+ def rating) | M_E (pregame baseline) | M_F (pregame + full ctrl) |
|---|---|---|---|---|
| 2021 | +0.014195 | +0.013426 | +0.013658 | +0.012671 |
| 2022 | +0.005359 | +0.005763 | +0.005267 | +0.005794 |
| 2023 | +0.002193 | +0.001955 | +0.001751 | **+0.001637** |
| 2024 | +0.006536 | +0.004043 | +0.006245 | +0.003530 |
| **mean** | **+0.007071** | +0.006297 | +0.006731 | **+0.005908** |
| **sd** | 0.005091 | 0.005001 | 0.005005 | 0.004818 |
| all folds positive | yes | yes | yes | yes |

### Walk-forward (the stricter protocol — no future season ever in training)

| fold | M_B | M_D | M_E | M_F |
|---|---|---|---|---|
| train ≤2021 → test 2022 | +0.003276 | +0.004452 | +0.002413 | +0.003881 |
| train ≤2022 → test 2023 | +0.002197 | +0.001313 | +0.001778 | +0.000974 |
| train ≤2023 → test 2024 | +0.006536 | +0.004043 | +0.006245 | +0.003530 |
| **mean** | **+0.004003** | +0.003270 | +0.003479 | **+0.002795** |
| **sd** | 0.002259 | 0.001707 | 0.002417 | 0.001587 |
| all folds positive | yes | yes | yes | yes |

**It persists: 7/7 folds positive under every specification, including the fully-controlled,
fully-pregame one.** The out-of-sample β is stable across folds (+0.110 to +0.157).

**But per-fold variability is large and must be reported, not averaged away.** LOSO sd is 72% of
its mean; the folds span 0.0016 to 0.0142, an 8x range. 2023 is the weakest fold under every
specification — the same season E0 flagged as barely clearing its placebo maximum (1.07x). And
**walk-forward runs ~40% below LOSO** (0.0040 vs 0.0071 for M_B; 0.0028 vs 0.0059 for M_F).
**Walk-forward is the honest number**, because LOSO lets later seasons inform the 2021 hold-out.

### Is it all 2021?

No. Dropping 2021 entirely and re-running LOSO on 2022-2024:

```
M_B_plus_venue            LOSO(2022-24) mean=+0.004796 sd=0.002353 all_positive=True
                          in-sample pooled(2022-24) dR2=0.004938
M_F_pregame_full_control  LOSO(2022-24) mean=+0.003902 sd=0.001684 all_positive=True
                          in-sample pooled(2022-24) dR2=0.003579
```

2021 roughly doubles the pooled figure, but removing it leaves a positive, all-folds-positive
effect at ~2/3 the size. The lead does not rest on one season.

---

## PART 3 — Placebo (negative control)

**The no-op defect was explicitly avoided.** The placebo does **not** permute a grouping key and
recompute the aggregate from it. It permutes the **assignment of already-computed values to rows**:
a `[n_rows × n_teams]` matrix of every team's pregame pressure evaluated at each row's own date is
built first, `analyze.py` asserts it reproduces the real measure exactly (max abs err = 3.6e-15),
and only then are values reassigned. Two forms, 200 draws each, seed 20260807:

1. **Team-identity derangement** (within season, no fixed points) — every row receives *another*
   team's already-computed pregame value at the same date.
2. **Row shuffle** (within season) — the value vector is shuffled across rows.

| placebo | statistic | real | placebo mean | **placebo sd** | placebo max | draws ≥ real |
|---|---|---|---|---|---|---|
| derangement | in-sample M_A | +0.007035 | +0.000281 | **0.000382** | +0.002136 | 0/200 |
| derangement | in-sample M_B (venue ctrl) | +0.007045 | +0.000282 | **0.000382** | +0.002136 | 0/200 |
| derangement | in-sample M_F (full ctrl) | +0.005649 | +0.000271 | **0.000351** | +0.001976 | 0/200 |
| derangement | **LOSO mean, M_B** | +0.007071 | −0.000258 | **0.000669** | +0.001539 | 0/200 |
| derangement | **LOSO mean, M_F** | +0.005908 | −0.000200 | **0.000607** | +0.001563 | 0/200 |
| row shuffle | in-sample M_A | +0.007035 | +0.000043 | **0.000059** | +0.000389 | 0/200 |
| row shuffle | in-sample M_B | +0.007045 | +0.000044 | **0.000060** | +0.000397 | 0/200 |
| row shuffle | in-sample M_F | +0.005649 | +0.000045 | **0.000062** | +0.000478 | 0/200 |
| row shuffle | LOSO mean, M_B | +0.007071 | −0.000084 | **0.000131** | +0.000338 | 0/200 |
| row shuffle | LOSO mean, M_F | +0.005908 | −0.000085 | **0.000134** | +0.000432 | 0/200 |

**All ten placebo sds are non-zero** (0.000059 to 0.000669); `analyze.py` asserts `sd > 1e-12` and
would abort on the degenerate `sd = 0.000000` signature. The derangement placebo has the larger sd,
as it should — it preserves the team-level structure of the values and only breaks the identity
link, so it is the harder control. On the out-of-sample statistics the placebo mean is **negative**,
which is the correct behaviour for a useless predictor evaluated out of sample.

Real over the largest of 200 derangement draws: **4.6x** (LOSO M_B), **3.8x** (LOSO M_F),
3.3x (in-sample M_B), 2.9x (in-sample M_F). Comfortable, though a smaller margin than E0's 13x —
because this E1's placebo is applied to the *out-of-sample* statistic, where the floor is wider.

---

## PART 4 — Reliability of the instrument (ambiguous-null guard)

Not an ambiguous null. Team forced-TO rate per 100 defensive possessions:

```
within-season split-half   2021 r=+0.681   2022 r=+0.359   2023 r=+0.735   2024 r=+0.515
                           mean r = +0.573
season-over-season         r = +0.464  (n = 36 team-season pairs)
```

The measure is adequately reliable, so a positive finding on it is bankable as a lead.
**Caveat retained from E0: n = 12 teams per season.** The 0.36-to-0.74 spread is consistent with
sampling noise around one underlying value and must not be over-read.

---

## PART 5 — The baseline caveat (read before quoting any number)

**Which baseline was used, explicitly:**

- **E0's baseline, replicated here as M_A/M_B**, is `player_tendency_loo` — the player's own season
  turnover rate per 100 offensive possessions, leaving out the current game. This is a
  "player's own recent rate" baseline, it is **hindsight** (it uses the rest of the season), and it
  is **one variable**.
- Because a companion screen has shown that baseline family is **materially improvable**, this E1
  also built a **fully pregame-observable** replacement — `player_tendency_pregame`, an expanding
  strictly-before-date rate shrunk (K = 100 offensive possessions) toward the player's prior-season
  rate where season−1 is inside 2021-2024, else the season league mean. Models M_E/M_F use it.
  `corr(LOO, pregame) = 0.780`.

Swapping to the pregame baseline costs little (96.2% retained; LOSO mean +0.00673 vs +0.00707), so
the effect is not fragile to *that particular* upgrade. **But both are still one-variable
player-rate baselines.** A real forecasting model would already carry rest, minutes/role, teammate
context, opponent pace, and recent form.

> **Every incremental number in this document is stated against a weak, one-variable player-rate
> baseline and is therefore an UPPER BOUND on marginal value, and provisional against the stronger
> baseline now known to exist. Do not quote these ΔR² figures as settled incremental value.**

**Practical size**, for calibration only: fully-controlled β = +0.1218 per unit of pregame pressure;
the p10-p90 spread of the measure is 4.78 forced TO/100 def poss, so the interquantile end-to-end
effect is **+0.583 turnovers per 100 offensive possessions**, or **17.7%** of the 3.30 weighted mean.

---

## What survived, what did not

**Survived:**
- The home/away control, completely (100.1% retained; venue explains 0.4% of the measure's variance;
  present at full strength inside both venue strata separately).
- The schedule-imbalance channel (99.7% retained).
- Genuine out-of-sample evaluation: 4/4 LOSO folds and 3/3 walk-forward folds positive, under both
  the E0 baseline and a fully pregame-observable one, with and without the opponent-quality control.
- A non-degenerate placebo, in two forms, on both in-sample and out-of-sample statistics: 0/200.
- Removal of 2021, the strongest season.
- The swap to a pregame-observable player baseline (96% retained).

**Did not survive / weakened:**
- **The venue-matched version of the measure.** Restricting to the opponent's same-venue prior games
  makes the measure *worse* and adds nothing over the venue-blind one. The venue component is noise.
- **Magnitude under the opponent-defensive-strength control**, especially in 2024: in-sample ΔR²
  falls 0.006783 → 0.003291 (−51%), LOSO 2024 falls +0.006536 → +0.004043. Pooled retention is
  85.3% (M_D) / 80.3% (M_F), so the pooled figure is partly masking a per-season problem that E0
  also noticed.
- **The idea that this is a stable-magnitude effect.** It is a stable-*sign*, stable-*coefficient*
  effect with a highly variable magnitude (LOSO sd is 72% of the mean; 8x fold range).
- **Walk-forward magnitude**: ~40% below LOSO, and only +0.0028 under full pregame control.

## What was NOT tested — may not be claimed

1. **Nothing beyond 2024.** The 2025/2026 confirmation holdout was never read. Persistence into the
   holdout era is entirely unknown.
2. **The baseline is still one variable.** See PART 5. The ΔR² figures are upper bounds.
3. **Collinearity with opponent defensive strength is growing across seasons** (r −0.228 → −0.619;
   R² of pressure on venue+defrtg reaching 0.383 in 2024). Whether the two are becoming genuinely
   redundant, or 2024 is a fluke of 12 teams, was not determined. **This, not home/away, is the
   confound an E2 should attack.**
4. **No mechanism split.** The target still has no steal-induced vs. unforced and no live-ball vs.
   dead-ball decomposition (`"no_steal_linkage": true`). Inherited from I0005/E0.
5. **No interaction was tested or revived.** I0005's interaction remains killed; this screen is
   purely additive.
6. **No forecasting or market evaluation of any kind.** ΔR² is not out-of-sample skill against a
   market line. E1 does not do that.
7. **Opponent pace, rest, travel, and back-to-backs are uncontrolled.** Only venue, schedule
   balance, and opponent defensive rating were controlled.
8. **n = 12 teams per season** limits every team-level correlation reported here.
9. **Incidental, untested, flagged not claimed:** E0's published ΔR² figures are ~8% smaller than
   the standard weighted R² because of the SST convention described above. This affects the
   *presentation* of E0's numbers only, not its verdict. If other screens in this program share
   E0's `wls_r2` helper, their ΔR² figures carry the same ~8% understatement — worth a separate
   look, not part of this screen's verdict.

## Artifacts

- `pressure_lib_e1.py` — pregame lookups (team pressure, venue-split pressure, player tendency),
  shared by the real and placebo paths so they cannot diverge.
- `build_data.py` — frame build, partition filters, manifest contamination check.
- `analyze.py` — venue control, collinearity, out-of-sample protocols, placebos, E0 reconciliation.
- `player_game_analysis.csv` (18,165 rows, 2021-2024 only, no `observed_time`)
- `team_game_defense.csv` (1,940 rows, 2021-2024 only, no `observed_time`)
- `FINDINGS.json`
- `run_log.txt` (actual stdout of `analyze.py`)
