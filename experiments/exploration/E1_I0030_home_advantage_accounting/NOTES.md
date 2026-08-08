# E1_I0030 — Home-advantage accounting. Method, verdicts, and where I could have cheated.

**Screen id:** `E1_I0030_home_advantage_accounting`
**Partition:** 2021–2024 only. 2025 and 2026 were never read, joined, plotted or described.
**Headline stratum:** regular season, 888 games / 1,776 team-games / 16,717 player appearances.
**Preregistration:** `CANDIDATES_PRESELECTED.md`, SHA256
`d513e27ade1afa01c4c1e9fc16ed33d773c648ebd41785c6b6fae2f63bc81f7d`, written and hashed by
`s00_prereg.py` before any statistic. Stages `s01`–`s06` re-hash it at run time and abort if it moved.
**Seed:** 20260808. **Plain-language deliverable:** `WHERE_IT_WENT.md`.

---

## 1. The framing this screen was given, and what changed under it

The brief said the user's argument is an accounting identity, not a hypothesis: team points are the
sum of player points, so a team-level home advantage must be somewhere at player level. That is
correct and it is verified rather than assumed — `sum of player points == team points` on every one
of 1,940 team-games, **max |difference| = 0**.

The brief also proposed three hiding places (pace, reference absorption, minutes) and treated pace as
the most likely. **Two of the three turn out to be structurally closed, not merely small**, and that
was the most useful thing this screen found:

- **Minutes.** Both teams play the same team minutes in a game (200 + 25 per overtime, and overtime is
  shared). Measured: identical in **970 of 970** games, gap exactly 0.
- **Pace.** Possessions alternate; the two teams get the same number to within one. Measured gap
  +0.135 possessions (p = 0.16), corr(home poss, away poss) = 0.816.

So the per-rate screens this programme ran were **not** structurally blind to the effect. There was
no pace effect for them to be blind to. The brief's leading hypothesis is refuted on arithmetic.

---

## 2. Inputs and manifests

| artifact | manifest | status | used |
|---|---|---|---|
| `data/masters/master_team.parquet` | present, `asof_granularity: row` | **USABLE_IF_FILTERED** | yes |
| `data/masters/master_player.parquet` | present, `asof_granularity: row` | **USABLE_IF_FILTERED** | yes |
| `data/reference/team_cities.csv` | none | UNVERIFIABLE | venue lat/lon/timezone only |
| `data/possessions/possessions.parquet` | **none** | UNVERIFIABLE | **deliberately NOT used** |
| `E0_I0015/decomp_frame.parquet` | **none** | UNVERIFIABLE | **not used for any headline** |

`check_manifest` was run from bytes this session on every one, including the two that were rejected,
and all five records are in `FINDINGS.json`. Possessions are derived here from the box score
(`FGA − OREB + TOV + 0.44·FTA`) so their as-of bound is inherited from a manifest-verified,
row-granular artifact rather than from a file with no manifest at all. `decomp_frame.parquet` carries
`tm_is_home` and would have been the convenient input; it has no manifest, so nothing headline rests
on it.

`team_cities.csv` has no manifest either, but it supplies only static geography (arena, latitude,
longitude, time zone) with no as-of semantics, and the three rows for franchises whose first season
is 2025 or 2026 were **dropped**, not ignored. `assert_partition` was then re-run on values.

---

## 3. Time-window table

Full table in `FINDINGS.json → stages.s01_guards_and_build.time_window_table`. Every constructed
column, its window, and the evidence:

| column | window | reads future? |
|---|---|---|
| `is_home` | schedule fact, known before tipoff | no |
| `poss` | **this game** — an outcome, used only as a decomposition denominator, never as a regressor | no (and never used as a feature) |
| `tz_delta`, `eastbound`, `westbound`, `same_zone_travel` | `(-inf, game_date)` for the prior venue | no |
| `rest_days` | `(-inf, game_date)` | no |
| all `ref_*` forecasts | `(-inf, game_date)`, prefix indexed at `h` never `h+1` | no |
| `ref_venue_split_*` | two independent strictly-prior prefixes, one per venue type | no |
| `beta_home` | whole seasons strictly earlier than the season scored | no |
| `decision_stratum` | `(-inf, game_date)` | no |

The strictly-prior claim on the travel columns is **asserted, not argued**: `prev_game_date <
game_date` on all 1,892 team-games that have a predecessor, checked in `s01`.

`poss` is contemporaneous and is flagged as such in the table. It is a decomposition denominator
only — no forecast in this screen consumes it, and none of the `main_effect_test.csv` cells use any
same-game quantity.

---

## 4. The null, and why it is not the usual one

`is_home` is **perfectly balanced within a game**: exactly one of the two team-game rows carries it.
`detect_grouping_level` was run before any null was chosen and returned
`NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` with `recommended_permutation_level = None`.
So neither kit scheme is reached by the standard path — `SCHEME_BETWEEN` is invalid (not constant
within any coarser key) and `SCHEME_WITHIN` inside a group of size 2 is a coin flip, i.e. it is the
sign flip arrived at by accident.

The verdict-carrying null is therefore the **exact randomisation test the design implies: relabel
which of the two teams in each game is the home team**, a per-game sign flip on the paired
difference. It preserves each game's total exactly and destroys only the venue attribution. This is
the same construction `paired_forecast_comparison` uses for paired forecasts, applied to a paired
outcome. **Cluster-robust standard errors are used nowhere in this screen.**

### The inflation factor goes the *other* way here, and that matters

The naive row-level null (pool all 1,940 team-game values, relabel half at random, ignoring
one-home-per-game) was computed for contrast:

| quantity | sd(correct, per-game flip) | sd(row-level naive) | ratio |
|---|---|---|---|
| points | 0.434 | 0.499 | **0.87** |
| points per possession | 0.0055 | 0.0058 | 0.96 |
| possessions | 0.093 | 0.218 | **0.43** |

**The naive null is WIDER, i.e. conservative, not anticonservative** — the opposite of the direction
this programme has been burned by four times. Pooling the two teams across games throws in the whole
between-game variation that the pairing removes. A screen that used the row-level null here would
have **understated** the home effect, not overstated it. That is worth recording because the
programme's standing prior ("row-level nulls are too narrow") is a property of a clustered-outcome
design, not a law, and this design inverts it.

Travel uses a different null (see §8) because `tz_delta` is neither constant within a game nor
balanced within one.

---

## 5. Step 1–2 — the team effect and its decomposition

Regular season 2021–2024, 888 games, per-game sign flip, 20,000 draws. Full table in
`team_effect.csv` (7 strata × 25 preselected cells).

| cell | home | away | gap | p | family-wise p† |
|---|---|---|---|---|---|
| **FT attempts** | 18.578 | 17.491 | **+1.087** | 0.00005 | **0.00005** |
| **FT makes** | 14.829 | 13.887 | **+0.941** | 0.00010 | **0.00005** |
| **fouls drawn** | 17.851 | 17.259 | **+0.592** | 0.00015 | **0.00015** |
| **fouls committed** | 17.259 | 17.851 | **−0.592** | 0.00015 | **0.00015** |
| turnovers | 14.036 | 14.461 | −0.425 | 0.019 | 0.069 |
| **points** | 82.367 | 81.402 | **+0.965** | 0.036 | **0.029** |
| points per possession | 1.0009 | 0.9903 | +0.0106 | 0.070 | 0.069 |
| possessions | 82.378 | 82.243 | +0.135 | 0.165 | 0.913 |
| eFG% | 0.4958 | 0.4962 | −0.0004 | 0.905 | 1.000 |
| FGA | 68.297 | 68.203 | +0.095 | 0.735 | 1.000 |
| **team minutes** | 201.267 | 201.267 | **0.000** | — | — |

† family-wise p is a **max-|t| step-down over the shared sign-flip draws** across the 25 preselected
team cells, computed on `ALL_2021_2024`. It respects the correlation between cells (points and
points-per-possession are nearly the same quantity) in a way Bonferroni cannot. Family size 38 was
fixed in the preregistration.

**Only the free-throw and foul cells survive multiplicity. Points itself barely does. Efficiency does
not.** The whistle is a cleaner signal than the points it causes.

### Exact decompositions (zero residual, not regressions)

For `H = P_h·E_h` and `A = P_a·E_a`, `H − A ≡ P̄·(E_h − E_a) + Ē·(P_h − P_a)` with
`P̄ = (P_h+P_a)/2`. Expanding both sides shows this holds with no residual term. Verified numerically
at `max |row residual| ≤ 1.4 × 10⁻¹⁴` on every split. `decomposition.csv`.

| decomposition | total | volume part | rate part |
|---|---|---|---|
| pts = poss × ppp | +0.965 | **+0.142** pace | **+0.823** efficiency |
| pts = team minutes × pts/min | +0.965 | **+0.000** minutes | +0.965 rate |
| ftm = fta × ft% | +0.925 | **+0.860** volume | +0.065 accuracy |
| fgm = fga × fg% | −0.021 | +0.039 | −0.060 |
| fg3m = fg3a × fg3% | +0.066 | +0.009 | +0.058 |
| fg2m = fg2a × fg2% | −0.088 | +0.077 | −0.165 |

And the exact points identity `pts = 2·FG2M + 3·FG3M + FTM` (checked at max |error| = 0):

| channel | contribution | share |
|---|---|---|
| FT makes | +0.941 | **97.6%** |
| 3pt makes (×3) | +0.199 | 20.7% |
| 2pt makes (×2) | −0.176 | −18.2% |
| **sum** | **+0.965** | ✓ residual 0.000 |

---

## 6. Step 3 — the reconciliation (the centrepiece)

Identity used, exact and residual-free:

```
G = mean_H(team pts) − mean_A(team pts)
  = Σ_i [ f_i^H · p̄_i^H − f_i^A · p̄_i^A ]
  = Σ_i f̄_i·(p̄_i^H − p̄_i^A)        ← WITHIN-PLAYER
  + Σ_i p̄̄_i·(f_i^H − f_i^A)         ← COMPOSITION
```

with `f_i^H` = player i's appearance rate per home team-game and `p̄_i^H` their mean points in those.

**Both sides, and the residual** (`player_reconciliation.csv`, `per_player_contributions.csv`):

| | value | share of G |
|---|---|---|
| **G (team)** | **+0.965090** | 100% |
| player-side reconstruction of mean home pts | 82.36712 (error **0.00e+00**) | — |
| player-side reconstruction of mean away pts | 81.40203 (error **0.00e+00**) | — |
| **(1) within-player** | **+1.314419** | 136.2% |
| (2) composition | −0.349329 | −36.2% |
| (1)+(2) | +0.965090 | ✓ |
| **residual** | **−4.2 × 10⁻¹⁶** | zero |
| \|(1)+(2) − G\| | 4.2 × 10⁻¹⁵ | zero |

**Both terms were tested against their own null**, by recomputing the whole 265-player decomposition
on each of 4,000 per-game sign-flip draws. The flip preserves `N_H = N_A = 888` exactly, so the
appearance rates stay comparable across draws:

| term | real | null sd | t | p |
|---|---|---|---|---|
| G | +0.965 | 0.452 | +2.13 | 0.035 |
| **within-player** | **+1.314** | 0.600 | +2.19 | **0.028** |
| composition | −0.349 | 0.578 | −0.60 | **0.545** |

**The composition term is noise.** Without this null the −36% would have been uninterpretable, and
reporting a term that is a third of G in the wrong direction without testing it would have been the
easiest way to mislead in this whole screen.

Splitting the within-player term again, exactly: **minutes per appearance +0.241 (18.3%), points per
minute +1.073 (81.7%)**, residual −8.9 × 10⁻¹⁶.

Same identity on free throws made: **within-player +0.988 (104.9%), composition −0.046 (−4.9%)**.

### Where the leaks the brief named would have been

- **Minutes budget** — closed by construction (§1).
- **Bench composition** — number of players used +0.001 (p = 1.00), minutes-Herfindahl −0.00004
  (p = 0.94), starter minute share +0.0001 (p = 0.98). Nothing.
- **Blowout substitution** — home teams win 53.2% of regular-season games, mean |margin| 11.2. On
  close games only (|margin| ≤ 8, n = 392) the FT channel survives (FTA +0.842, p = 0.042; fouls
  −0.508, p = 0.035) while points does not (−0.171, p = 0.53). The effect is **not** garbage time; if
  anything the points gap is a blowout artefact and the foul gap is the real thing.

### Player-level cells (per-game paired, same null)

| cell | home | away | gap | p |
|---|---|---|---|---|
| **FTA per minute (minute-weighted)** | 0.0923 | 0.0869 | **+0.0054** | **0.00005** |
| **mean player FTA** | 1.998 | 1.882 | **+0.116** | **0.00015** |
| mean player FTA per minute | 0.0859 | 0.0780 | +0.0079 | 0.00050 |
| mean player points per minute | 0.3669 | 0.3595 | +0.0074 | 0.023 |
| team points per team minute | 0.4093 | 0.4045 | +0.0048 | 0.034 |
| mean player points | 8.854 | 8.754 | +0.100 | 0.103 |
| mean player minutes | 21.635 | 21.642 | −0.007 | 0.947 |
| mean player FGA | 7.340 | 7.332 | +0.007 | 0.864 |
| eFG% | 0.4958 | 0.4962 | −0.0004 | 0.903 |

By minutes tier (`by_minutes_tier.csv`), the effect is concentrated in high-minute players:
stars (>28 mpg) +0.543 pts / +0.258 FTA; starters (20–28) −0.054 pts / +0.139 FTA; rotation (10–20)
+0.067 / +0.039; bench (<10) +0.018 / −0.017.

**Per-player concentration is a warning, not a finding.** Only 128 of 265 players (48.3%) have a
positive contribution, and the cumulative curve overshoots badly — the top 10 players account for
124% of the within term and the top 50 for 313%, cancelled by the rest. That is the signature of
per-player noise, and it is exactly the D093 pattern. It is why §7 tests heterogeneity properly
rather than reading this table as evidence.

---

## 7. Step 4 — the main-effect test, and Step 5 heterogeneity

### The detection floor, computed before any model was fitted

| target | home−away per appearance | sd | increment vs a blended reference | as % of sd | max attainable ΔR² |
|---|---|---|---|---|---|
| points | +0.1015 | 7.457 | +0.0507 | **0.68%** | **4.63 × 10⁻⁵** |
| FT attempts | +0.1152 | 2.474 | +0.0576 | 2.33% | 5.43 × 10⁻⁴ |
| points/min | +0.0072 | 0.276 | +0.0036 | 1.31% | 1.71 × 10⁻⁴ |
| FGA | +0.0092 | 5.271 | +0.0046 | 0.09% | 7.59 × 10⁻⁷ |
| minutes | −0.0025 | 10.492 | −0.0013 | 0.01% | 1.47 × 10⁻⁸ |

### The test (`main_effect_test.csv`, 32 cells)

`yhat = ref + a + b·(is_home − 0.5)`, with `a` and `b` fitted by OLS on the residual over **strictly
earlier seasons only** (2022 scored on 2021; 2023 on 2021–22; 2024 on 2021–23). The base arm carries
`a` too, so `b` is isolated. Null: `paired_forecast_comparison`, clusters = (season, player).

References, all strictly prior and all **complete** (every available prior measurement, not a
truncated window): `REF_EXPANDING_COMPLETE`, `REF_EWMA8_COMPLETE` (E1_I0022's winning form),
`REF_VENUE_SPLIT_EXPANDING`, `REF_VENUE_SPLIT_EWMA8`.

**Verdict: no cell improves.** Best is points on the decision stratum against the expanding
reference: MAE +0.028%, **ΔR² = +1.07 × 10⁻⁴ on the common denominator**, p = 0.168. Pooled points
against EWMA8: ΔR² = +6.5 × 10⁻⁵, p = 0.556.

**The observed +6.5 × 10⁻⁵ is at the a-priori ceiling of 4.6 × 10⁻⁵.** The effect is not absent; it
is exactly its predicted size and its predicted size is below resolution. Fitted `beta_home` for
points in 2024 is +0.17, the right sign and the right order of magnitude.

**Negative control:** a fake venue label (random one-per-game) through the identical pipeline gives
ΔR² = −2.33 × 10⁻⁵ on points (real: +6.5 × 10⁻⁵) and −2.83 × 10⁻⁵ on points-per-minute (real:
+7.5 × 10⁻⁵). Real positive at ceiling, fake negative.

**Denominator rule (D099):** every ΔR² is reported on `dR2_commonSST`, the SST of the **full pooled
evaluation stratum** (13,152 rows). The decision-stratum-own-SST version sits beside it in the same
CSV as `dR2_ownSST_LABELLED` and is never substituted.

### Reference absorption — tested directly, and refuted as the explanation

`reference_absorption.csv`, venue-split vs all-games, same rows, cluster sign-flip:

| target | form | MAE venue-split | MAE all-games | change | p |
|---|---|---|---|---|---|
| points | expanding | 4.2589 | 4.1052 | **−3.75%** | 0.0002 |
| points | ewma8 | 4.2442 | 4.0799 | **−4.03%** | 0.0002 |
| minutes | ewma8 | 5.2519 | 4.9746 | **−5.58%** | 0.0002 |
| points/min | expanding | 0.1898 | 0.1822 | **−4.15%** | 0.0002 |
| FGA | ewma8 | 2.6692 | 2.5440 | **−4.92%** | 0.0002 |

(8 of 8 cells worse; table above is a subset.) Absorption is real as arithmetic — it is why the
detectable increment is half the gap — but **un-blending the reference costs ~100× more than the
signal it recovers**, so it is not why the earlier screens returned null. The screens returned null
because the effect is 0.68% of one sd.

### Heterogeneity (`heterogeneity.csv`), 149 players with ≥20 home and ≥20 away appearances

Null: `per_entity_control` with `SCHEME_WITHIN_CYCLIC`, order = game_date. Within-player
`acf1(is_home) = +0.046` over 14,145 pairs — non-zero, so the shuffle is inadmissible.

| target | observed sd of per-player home−away | cyclic null mean | cyclic null sd | **p (cyclic)** | p (unsafe shuffle) |
|---|---|---|---|---|---|
| points | 1.216 | 1.127 | 0.0715 | **0.109** | 0.232 |
| points/min | 0.0548 | 0.0497 | 0.0035 | **0.077** | 0.072 |
| FT attempts | 0.469 | 0.421 | 0.0285 | **0.054** | 0.119 |
| FTA per min | 0.0263 | 0.0275 | 0.0023 | **0.691** | 0.756 |

**Nothing clears 0.05.** The relabel arm is a **confirmed no-op at sd ≈ 10⁻¹⁷** in all four targets
(K7), reported as vacuous rather than as a pass; `controls_are_informative = True` in all four.
D093's single-player ceiling is not contested — this screen makes no per-player claim.

---

## 8. Step 6 — eastbound travel

**Preregistered before any statistic** (hash above): eastbound (`tz_delta ≥ +1`) HURTS —
**negative** on points and on points per possession.

Zones are **UTC clock offsets in season**, not time-zone strings. Every 2021–2024 game falls in US
daylight-saving time, so **America/Phoenix (no DST) has the same clock as Pacific** and a
Phoenix↔Las Vegas/Seattle trip is a **same-zone** trip. Using the tz string would have manufactured
crossings that do not exist. Three real zones in season: −4 (NY, Indianapolis, Connecticut,
Washington, Atlanta), −5 (Chicago, Minnesota, Dallas), −7 (LA, Las Vegas, Seattle, Phoenix).

Arms (team-games with a strictly prior game, regular season): eastbound 341, westbound 331,
same-zone travel 532, no travel 524.

**The confound check, run first:** the crossing arms are 30–38% home games; the no-travel arm is 87%
home games. **The raw contrast is mostly the home effect in a travel costume**, which is why only
the adjusted arm carries a verdict.

Null: **cyclic shift** of the arm indicator within each (season, team) date-ordered series.
Measured `acf1`: eastbound −0.150, westbound −0.116, same-zone +0.100 — all non-zero, so the shuffle
is inadmissible (K6).

| target | arm | β (adjusted for is_home, rest, prior own strength, prior opponent allowed) | null sd | **p, preregistered lower tail** |
|---|---|---|---|---|
| points | **eastbound** | **+0.856 (WRONG SIGN)** | 0.621 | **0.869** |
| points | westbound | +0.561 | 0.601 | 0.783 |
| points | same-zone travel | −0.532 | 0.541 | 0.261 |
| ppp | **eastbound** | **+0.0011** | 0.0071 | **0.471** |
| ppp | westbound | +0.0076 | 0.0071 | 0.823 |
| ppp | same-zone travel | −0.0055 | 0.0062 | 0.281 |

**Internal controls refute the mechanism.** Circadian phase advance predicts
east < same-zone < west. Observed on ppp: east +0.001, west +0.008, **same-zone −0.005 (worst)**.
Travel with no circadian component is the most damaging arm.

**Sharpest test — road games only, east vs west** (removes the home confound entirely; n = 211 vs
212): raw east−west = **+0.006 points**, adjusted β = +0.308, p = 0.403; on ppp β = −0.005,
p = 0.256.

**Dose response:** non-monotone. `tz_delta = +2` is the highest-scoring road cell (84.25) and `+3`
the lowest (80.04). Noise.

**Is it the dead rest/schedule family in new clothes? Yes, and it should be recorded as the fifth
death.** The signature is identical to the previous four: a raw contrast that looks like something,
driven by a schedule variable's correlation with venue and rest, that vanishes on adjustment.

---

## 9. Step 7 — attendance

**It does not exist.** 5,612 tabular artifacts under `data/` scanned; **zero** carry a column
matching `/attend/i`. Every mention in the repository is a field name on an un-ingested upstream
endpoint, a placeholder key in a forward-looking live-capture schema, `FEATURE_LAB_CATALOG.md`
row 99 marked "not captured; noted", prose about 2021's restrictions, or one league-wide press
figure. **Per the brief this stage stopped.** No proxy was built and none is reported. Details and
the acquisition note in `FINDINGS.json → stages.s07_attendance`.

---

## 10. WHERE I COULD HAVE CHEATED, AND ONE PLACE I DID GET IT WRONG

**A defective negative control that I am reporting rather than deleting.** NC2's first version was
`(home_team_id % 2 − away_team_id % 2) × points gap`. That is 0 on half the games and ±1 on the
rest — so on the games where it was +1 it **retained the real home effect intact**. It returned
p = 0.0002. It "failed" because it was a masked copy of the treatment, not a placebo. Replaced with
"the team with the larger team_id", which is structurally identical to `is_home` (exactly one team
per game carries it). Both versions are in `FINDINGS.json`.

**And the replacement fails too, for a reason that is itself the finding.** NC2′ gives p = 0.073 on
points and p = 0.0086 on FT makes. `team_id` orders the franchises and franchise identity encodes
strength — low ids here are NYL/PHO/LVA/LAS, high ids SEA/CHI/ATL, and those groups are not equally
good. **Any fixed team-level label is a quality contrast and cannot be a null.** The home/away label
does not share that confound, and the reason is measured not asserted: every team's home share sits
within 3.1 percentage points of 0.500 in every (season, team) cell, so franchise quality enters both
sides of the difference and cancels. **NC1 — a random one-per-game relabel, which is genuinely
structurally identical to `is_home` and genuinely meaningless — passes at p = 0.982.** That is the
control that counts.

**Ways I could have manufactured a result and did not:**

1. **Pooling the playoffs into the headline.** Playoffs give +5.68 points, 5.9× the regular-season
   figure, because home court is *awarded to the better seed* — a strength contrast wearing a venue
   label. Pooling them would have inflated the headline to +1.36 and made the whole story look
   stronger. The headline is regular season; the pooled and playoff figures are reported and labelled.
2. **Reporting the composition term without a null.** −0.349 is 36% of G in the wrong direction and
   would have been a compelling "the leak is roster composition" story. Its p is 0.545.
3. **Reporting the per-player concentration table as heterogeneity.** The top-10 players carry 124%
   of the within term. That reads as "a few players drive it" and it is cancellation noise; the
   proper cyclic-shift test gives p = 0.109.
4. **Using the row-level null.** Here it is *conservative*, so switching to it would have made the
   effect look weaker, not stronger — but the temptation runs the other way for the travel arms, and
   they use the cyclic shift.
5. **Reporting the raw travel contrasts.** Eastbound "gains +0.48 points vs no travel" is in the
   output and is nearly pure home-effect confound. Both raw and adjusted are shown, labelled.
6. **Choosing the direction after seeing the sign.** Eastbound came back positive. The negative
   direction was hashed before anything was computed and the p is reported in the preregistered tail
   (0.869), not the convenient one.
7. **Sub-setting to close games.** The FT channel survives there and points does not; I could have
   led with the close-game FT number. The headline is the full stratum.
8. **Selecting the reference.** Four references were preregistered, all reported, none dropped. The
   venue-split pair loses badly and is reported as losing.
9. **Denominators.** Every ΔR² is on the full pooled SST; the subset-SST column is present and
   labelled and never substituted for it.

**Genuine limitations:**

- **n = 888 games** is small. The regular-season points gap is significant at p = 0.036 and would not
  survive a much harsher multiplicity correction; the *free-throw* channel would, comfortably.
- **The box possession estimator is not the identity.** Its +0.135 gap is partly the estimator's own
  asymmetry (the 0.44 coefficient, the OREB term), not extra pace. The structural argument (real
  possessions are equal to within one) does the work; the estimate only fails to contradict it.
- **`minutes` has a rounding artefact.** Player minutes sum to team minutes with max |difference|
  0.067, from the mm:ss source. Immaterial at the scale of anything here.
- **The composition term is estimated over 265 pooled player ids.** A player-season entity would give
  a different (still exact) split. Not run; the identity holds either way.
- **2021 was played under attendance restrictions** and is in the partition. The FT channel is
  present in all four seasons (+1.27, +0.86, +0.56, +1.14) so it is not a 2021 artefact, but the
  foul differential *declines monotonically* across seasons (0.86 → 0.76 → 0.48 → 0.34), which is a
  real and unexplained drift and a reason not to extrapolate the size forward.
- **Nothing here was validated out of partition.** 2025–26 were never touched.

---

## 11. Files

| file | what |
|---|---|
| `WHERE_IT_WENT.md` | **the plain-language accounting — the main deliverable** |
| `FINDINGS.json` | merged machine-readable findings, all seven stages + `ANSWERS` block |
| `CANDIDATES_PRESELECTED.md` | the preregistration, hashed before any statistic |
| `_prereg.json` | the hash and the preregistered direction |
| `team_effect.csv` | 7 strata × 25 cells, gaps, per-game sign-flip p, family-wise p |
| `decomposition.csv` | exact two-way decompositions, both strata, with residuals |
| `player_reconciliation.csv` | player cells **and** the reconciliation rows in one table |
| `per_player_contributions.csv` | per-player within and composition contributions |
| `by_minutes_tier.csv` | the effect by role tier |
| `main_effect_test.csv` | 32 walk-forward cells, both denominators, cluster p |
| `reference_absorption.csv` | venue-split vs all-games, 8 cells |
| `heterogeneity.csv` | cyclic-null spread test, 4 targets |
| `travel_directional.csv` | raw, adjusted, road-only-east-vs-west |
| `permutation_draws_*.csv` | the draws behind every verdict (5 files) |
| `run_log.txt` | all eight stage logs concatenated |
| `ha_base.py`, `s00`–`s08` | the scripts, in run order |
| `_team_frame.parquet`, `_player_frame.parquet`, `_venues.csv` | built intermediates |
