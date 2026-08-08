# NOTES — E1_I0033_aggregation_level

Technical record. The user-facing answer is `WHICH_LEVEL_WINS.md`; the Step-4 scoping is
`player_value_scope.md`; self-reported defects are `DEFECTS.md`.

Preregistration `COMPARISONS_PRESELECTED.md`, sha256
**`0787b5caf7b035c2f3df3b95970ec637abf7d9e9780e17fe0f88d92a2838db2e`**.
**14 cells hashed, 0 dropped, 5 added after hashing.** Every downstream script re-reads the hashed
file and asserts both the stored hash and the in-script text still match; the run log records the
assertion passing at every step.

**Direction of the additions.** `B1A_TIER_A_ONLY`, `B1N_ROSTER_NORMALISED`, `P07b_EXPLORATORY`,
`X1_EXPLORATORY`, `X2_EXPLORATORY`. **All five make the player/bottom-up side look better than the
preregistered construction did.** None was added to rescue a result; each was added because
leaving it out would have made the headline stronger than the evidence warrants.

---

## 0. TIME-WINDOW TABLE

| Column | Construction | Window | Reads future? | Evidence |
|---|---|---|---|---|
| `pts` (response) | `master_team.pts` | this game | no | the response; never a regressor anywhere |
| `A_TEAM` | stored `pred_point`, `cbs_v12_team_oof_v2/attempt_001` | (−∞, cutoff]; season *S* fitted on seasons < *S* | no | fold receipt: `fold_boundary` ok, `own_outcome_never_informed_its_forecast: true`, `forecast_scored_against_outcome: false`, `evaluation_metric_calculated: false`, `train_seasons` strictly < season. **Nothing refitted.** |
| `pts_hat`, `p_active_hat`, `min_hat`, `fga_hat` | stored `pred_point`, `cbs_v15_player_oof_v5/attempt_001` | same | no | same receipts; D076 established this walk-forward |
| `B1`, `B2` | Σ over the team-game's champion rows of (`p_active_hat` ×) `pts_hat` | strictly pre-game | no | candidate set is the contract's pre-cutoff candidacy; both factors are stored pre-cutoff forecasts. No realised minutes, appearance or roster |
| **`B3_ORACLE_ROSTER`** | Σ `pts_hat` over rows with `appeared == 1` | **this game** | **YES** | **ORACLE by construction. Diagnostic only. Excluded from every headline and ranking.** |
| `R0`,`R1`,`R2`, `LEVEL_TEAM_*`, `LEVEL_PLAYER_*` | expanding / EWMA over strictly earlier same-season games, shrunk | (−∞, game_date) | no | prefix accumulator writes the statistic **before** folding row *i* in; asserted by requiring zero prior mass on the first row of every entity block |
| league targets | expanding mean over strictly earlier **dates** | (−∞, game_date) | no | same-date rows never see each other — implemented on unique dates, not row order |
| half-life, shrinkage *k*, blend *w*, affine *(a,b)*, β | grid search / OLS on **strictly earlier seasons only** | whole seasons < scored season | no | walk-forward loop; the 2022 fold sees 2021 only and its thin fits are printed |
| `FT_PCT_PRIOR`, `FTA_RATE_PRIOR` | team FTM/FTA over strictly earlier same-season games, shrunk to the strictly-prior league rate | (−∞, game_date) | no | ratio-of-sums, never mean-of-ratios |
| `is_home` | venue from the box score | schedule fact, known pre-tip | no | fixture attribute, not an outcome (D104's treatment) |
| `n_top3_out`, `naive_points_lost` | absence of a **pre-game-ranked** top-3 player | **realised absence** | **YES on the indicator** | ranking is `p_active_hat × min_hat`, both pre-cutoff. The absence itself is realised and the conditioning is declared in `player_value_scope.md` §2 |

---

## 1. Provenance established, not assumed

### The team arm

`cbs_v12_team_oof/1` carries `PROVISIONAL_SUPERSEDED.md`: its producing tree was **dirty (97
paths)** so the exact generating code is not reconstructible, and its resume path was **fail-open**
(a missing or substituted output could be marked RESUMED and still yield
`all_folds_receipted=true`). **It is not used.** `cbs_v12_team_oof_v2/attempt_001` refuses a dirty
tree, digests producing sources before any frame is built, and validates artifact bytes and
identity on resume against twelve enumerated fail-closed conditions.

| season | fitted | degenerate | train_seasons | n_test | fold_boundary | components |
|---|---|---|---|---:|---|---|
| 2021 | **false** | **true** | [] | 418 | ok | declared_constant only |
| 2022 | true | false | [2021] | 478 | ok | + `walk_forward_channel_ewma_side_map` |
| 2023 | true | false | [2021, 2022] | 520 | ok | same |
| 2024 | true | false | [2021, 2022, 2023] | 524 | ok | same |

2021 emits **`pred_point` 82.0 on all 418 rows (`nunique == 1`)** — verified on bytes, not inferred
from the receipt. **Excluded**, exactly as D076 excluded the player arm's 2021 fold. Every season
carries `own_outcome_never_informed_its_forecast: true`, `forecast_scored_against_outcome: false`,
`evaluation_metric_calculated: false`, and zero `failed_receipts`.

### The identity map — and why it was reconstructed

The champion player arm's fold receipts **bind `prediction_contract_v4` artifacts**, but all 26,614
of its emitted `row_uid`s (2021–2024) belong to **`prediction_contract_v5`'s** universe, which is
strictly larger (6,333 vs 5,563 rows in 2022; tier A 22,659 / tier B 3,955). **`prediction_contract_v5`
has no sibling manifest — `check_manifest` returns UNVERIFIABLE, and UNVERIFIABLE IS NOT A PASS.**

So the map `row_uid → (player_id, game_id, team_id)` was **recomputed** from the canonical key
(`cbs_obligation_key/1`, `CANONICAL_KEY_FIELDS = (player_id, game_id, team_id)`) over the cross
product of team-games from `master_team` and the 268 players seen anywhere in the partition —
519,920 triples, all keys unique.

* **Cross-check: 22,659 of 22,659 contract-v4 `row_uid`s reconstructed, and all 22,659 agree on all
  three fields.** Exact.
* Resolution on the champion's rows: **26,574 of 26,614 (99.85 %)**. The 40 unresolved are all
  tier-B, cold-start, fallback rows for players with no box-score row anywhere in 2021–2024, so no
  manifest-verified artifact can name them. They are dropped and reported.
* `prediction_contract_v5` was opened **once**, to *describe* those 40 dropped rows. No number in
  this screen depends on it.

### Manifest status of every input

| Artifact | granularity | status | use |
|---|---|---|---|
| `data/masters/master_team.parquet` | row | USABLE_IF_FILTERED | outcomes + strictly-prior team history |
| `data/masters/master_player.parquet` | row | USABLE_IF_FILTERED | outcomes + strictly-prior player history |
| `prediction_contract_v4/{player_game,team_game}.parquet` | row | USABLE_IF_FILTERED | identity cross-check, team-arm key map |
| `prediction_contract_v5/player_game.parquet` | — | **UNVERIFIABLE** | **not used for any number** |
| arm `predictions__*.parquet` | artifact | UNUSABLE **as a feature source** | not used as one. These are the **stored forecasts being scored**, one file per fold, and the per-fold receipt is the as-of evidence, not the file-level manifest |

`data/w1_truth/player_game_availability.csv` and `roster_asof.csv` were **never opened** — D076
records both failing the manifest check for exactly this kind of screen.

---

## 2. Anchors reproduced before any new statistic

| Anchor | Published | Reproduced | Error |
|---|---|---|---|
| D104 team home advantage, regular season 2021–2024 | +0.965090 over 888 games (82.367 / 81.402) | **+0.965090 over 888 games (82.367117 / 81.402027)** | < 1e-5, exact to 6 dp |
| D076 appeared player-games 2022–2024 | 13,879 | **13,879** on the tier-A obligation set | exact |

The screen halts on either failure; the assertion is in `s05_build.py` and the run log shows it
passing. (On the *full* champion universe including tier B the count is 14,262; D076 screened the
contract-v4 set, and the exact match on that set is what identifies the row set.)

---

## 3. Row sets, response and denominator

**RS1 (headline):** season ∈ {2022, 2023, 2024}, `season_type == "Regular Season"`, team-arm
forecast present, ≥1 champion player forecast present → **1,392 team-games** (432 / 480 / 480).
Response mean 82.2220, sd 11.0130, **SST 168 710.4073**, computed once and passed as an explicit
argument to every R² so no code path can take a subset's own SST (D101 rule D3).

**RS2 (playoffs, 2022–2024): 130 team-games. Reported separately, never pooled** — D104's reason:
playoff home court is awarded to the better seed, so the stratum is not exchangeable. The ordering
is unchanged there (A_TEAM 9.222, B1 9.771, B2 15.436).

**Denominator declaration.** Every figure in the top-down-versus-bottom-up table shares the same
response, row set, SST, weighting (none) and base (none), so all are comparable to each other and
**to nothing outside**. **No team-level ΔR² is compared to any player-level ΔR² anywhere.** Where
both levels appear together only skill-against-a-matched-reference is shown, with the response
difference stated in the same sentence.

---

## 4. Results

### 4.1 The central test (P01)

`A_TEAM` MAE **8.685506** vs `B1_BOTTOMUP_AVAIL` MAE **18.263037** → advantage **+9.57753** MAE
points per team-game.

* N1 (team-season blocks, 36): **p < 0.0001**, null_mean +1.39e-02, null_sd 1.77217
* N1b (game blocks): p < 0.0001
* N2 (row-level, naive, **never a verdict**): p < 0.0001; **inflation N1/N2 = 2.194×**
* observed effect = **5.4 null sd**; this cell's 80 %-power floor = 4.95 MAE points

**DR1 fires: TEAM LEVEL WINS.** DR2 (levels agree) false, DR3 (bottom-up wins) false.

### 4.2 Every arm on RS1

| arm | MAE | R² (common SST) | bias | skill vs R2_TEAM_EWMA |
|---|---:|---:|---:|---:|
| R1_TEAM_EXPAND | 8.476967 | +0.056748 | −0.652 | +0.04 % |
| R2_TEAM_EWMA | 8.480207 | +0.057026 | −0.559 | — |
| **A_TEAM** | **8.685506** | +0.021723 | −1.029 | **−2.42 %** |
| C2_PRORATE | 8.685506 | +0.021723 | −1.029 | −2.42 % (**identical to A_TEAM by construction**) |
| C1_BLEND | 8.695863 | +0.019650 | −0.968 | −2.54 % |
| R0_LEAGUE | 8.790932 | −0.005095 | −0.636 | −3.66 % |
| B4_BOTTOMUP_CAL | 8.819619 | −0.010721 | −0.832 | −4.00 % |
| *B3_ORACLE_ROSTER* | *10.650052* | *−0.544608* | *−0.648* | *−25.59 %* |
| **B1_BOTTOMUP_AVAIL** | **18.263037** | **−8.662697** | **+8.139** | **−115.36 %** |
| B2_BOTTOMUP_RAW | 37.417746 | −39.926588 | +35.749 | −341.24 % |

**`C2_PRORATE` is the reconciled arm and it is `A_TEAM` to the last bit.** Proportionally
reconciling player forecasts to the direct team forecast reproduces the direct forecast exactly at
the team total. Reconciliation does no work on the total; all of its work is at the player level.

`C1_BLEND`'s walk-forward weight on `A_TEAM` is **0.9712 / 1.0000 / 1.0000** — the blend chooses
the team arm outright in two of three seasons, and P04 (C1 vs A_TEAM) is p 0.2823, not established.

### 4.3 P02 — the team arm loses to its own matched reference

`A_TEAM` − `R2_TEAM_EWMA` = **−0.20530 MAE**, N1 p **0.0159**, null_mean +6.06e-04, null_sd
0.08971, N1b p 0.0028, N2 p 0.0023, inflation 1.342×.

**This is significant AND underpowered and must always be quoted with both facts.** The observed
gap of 0.205 is 2.3 null sd, which clears the 1.96 significance line but sits **below this cell's
80 %-power floor of 0.2512**. Consistent with D076 ("the champion barely matches, and on points
slightly trails, a naive prior mean") and D101 ("D076's reference is worse than a plain player
expanding mean").

### 4.4 The gap decomposition (Step 2)

Sequential; each step applied on top of the last, so they sum to the total exactly. n = 1,392.

| step | MAE | improvement | share |
|---|---:|---:|---:|
| literal bottom-up | 18.26304 | — | — |
| + roster-size normalisation | 10.44256 | **+7.82048** | **81.7 %** |
| + walk-forward affine level/scale | 8.65463 | +1.78793 | 18.7 % |
| target A_TEAM | 8.68551 | −0.03088 | −0.3 % |
| **total** | | **9.57753** | **100.0 %** |

**(b) The roster problem — the mechanism, on bytes.**

| tier | n rows | mean `p_active_hat` | mean `pts_hat` | **realised appearance rate** | mean realised pts |
|---|---:|---:|---:|---:|---:|
| A | 16,312 | 0.7608 | 8.088 | **0.7788** | 6.813 |
| **B** | **3,772** | **0.5249** | **8.561** | **0.1015** | **0.814** |

Tier-B rows carry `p_active` **0.52 against a realised 0.10**. Universe size 14.428 rows per
team-game; Σ`p_active_hat` = **10.3381** against a realised roster of **9.4016**. One phantom
player × ~8.7 conditional points = **+8.14 points of level bias**, which is essentially the whole
disadvantage. The prior-games roster-size estimate is **9.3999** against the realised 9.4016 — so
the normalisation target is itself accurate, and the miscalibration is entirely in `p_active`.

**(a) Error compounding — refuted; the errors cancel.**

| | raw B1 | roster-normalised |
|---|---:|---:|
| players summed | 14.428 | 14.428 |
| sd of summed error | 33.4357 | **13.2634** |
| sd under independence | 20.1445 | **19.6766** |
| **ratio observed / independent** | 1.6598 | **0.6741** |
| cancellation ratio \|Σe\| / Σ\|e\| | 0.3256 | **0.2010** |
| within-team-game share of error variance | 0.9068 | 0.9646 |

The raw ratio of 1.66 is *the level bias*, not compounding — every player's error carries the same
positive offset, so they add. Once the roster is normalised the ratio is **0.674**, i.e. errors
cancel substantially. Points are a near-fixed team budget, so one player's over-forecast is
another's under-forecast.

**(c) Individually weaker player forecasts — a little; both levels negative.**

* player level: n = 13,021, champion MAE 4.2491, matched player prior reference 4.1324 → skill
  **−2.8245 %**
* team level: n = 1,392, A_TEAM 8.6855, matched team prior reference 8.4802 → skill **−2.4209 %**

*Different responses; skill ratios only; no ΔR² comparison is made.*

**The counterweight, published because it weakens the headline.** `B4N_NORMALISED_CAL` (roster
normalised **and** walk-forward affine) reaches MAE **8.654625**, and X1_EXPLORATORY finds it
**+0.03088 better than `A_TEAM` at p 0.7295** — i.e. the levels **tie** once bottom-up is fully
repaired. X2_EXPLORATORY finds `R2_TEAM_EWMA` ahead of it by +0.17442 at p 0.1951, also not
established.

**But it ties by ceasing to be bottom-up.** Walk-forward affine slopes:

| source | 2022 | 2023 | 2024 |
|---|---:|---:|---:|
| `B1_BOTTOMUP_AVAIL` | −0.0166 | 0.0001 | −0.0102 |
| `B1N_ROSTER_NORMALISED` | 0.0713 | 0.1172 | 0.1534 |
| `B3_ORACLE_ROSTER` | 0.0151 | 0.0832 | 0.1201 |
| `A_TEAM` | 0.9857 | 0.3259 | 0.6987 |

A slope of 0.07–0.15 means the recalibration is emitting a near-constant. Correlation with the
response confirms it: `B1` **+0.0013**, `B1N` +0.1655, `B4N` +0.1483, `A_TEAM` +0.1879,
`R2_TEAM_EWMA` +0.2526.

### 4.5 Which level wins (P09–P14) — matched construction

Estimator class held fixed, only the level varies. Both sides are the same EWMA-with-shrinkage,
same grid, same tuning rule on strictly earlier seasons, same team-level response, same rows, same
SST per quantity. `LEVEL_PLAYER_NORM` uses the roster-normalised weights and was **added after the
hash** because the preregistered raw weighting flattered the team side.

| cell | quantity | TEAM MAE | PLAYER MAE (prereg) | PLAYER_NORM MAE | TEAM adv (prereg) | p | TEAM adv (norm) | p | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| P09 | pts | 8.4802 | 14.7593 | 10.7915 | +6.2791 | <1e-4 | +2.3113 | <1e-4 | **TEAM DECIDED** |
| P10 | fga | 4.6977 | 10.5818 | 7.0252 | +5.8841 | <1e-4 | +2.3275 | <1e-4 | **TEAM DECIDED** |
| P11 | fta | 4.8674 | 5.7987 | 5.2217 | +0.9313 | <1e-4 | +0.3543 | <1e-4 | **TEAM DECIDED** |
| P12 | ftm | 4.2202 | 4.9157 | 4.4972 | +0.6955 | <1e-4 | +0.2769 | <1e-4 | **TEAM DECIDED** |
| P13 | reb | 4.3999 | 7.1203 | 5.0917 | +2.7203 | <1e-4 | +0.6917 | <1e-4 | **TEAM DECIDED** |
| P14 | ast | 3.2330 | 4.6112 | 3.5871 | +1.3783 | <1e-4 | +0.3542 | <1e-4 | **TEAM DECIDED** |

**Six for six, both weightings, all decided.** But the *size* is strongly quantity-dependent —
the normalised penalty as a fraction of team MAE ranges from **49.6 %** (FGA) to **6.6 %** (FTM), a
factor of 7.5. Correlation ratio player/team: **assists 0.86**, points 0.72, FTM 0.68, FTA 0.58,
rebounds 0.58, **FGA 0.45**.

**The ordering is mechanistic, not incidental.** Individual acts (a free throw is one player alone
at the line; an assist is attributed to one player) survive aggregation from below. Allocations of
a shared fixed budget (shot attempts out of ~200 team minutes and a shared possession count) do
not, because modelling players separately discards the constraint that their attempts must sum to
the team's. D104 verified both budgets are shared: team minutes identical in 970 of 970 games;
possessions a shared game property with home−away +0.135 at p 0.165.

### 4.6 The free-throw composition (P07, P08) — Step 3

**The arithmetic ceiling was computed before anything was fitted**, as D104 did.

* venue FTA edge: ±0.5435 attempts (differential 1.087, D104)
* venue points edge at the league rate: 0.4348 points
* composed − flat: mean −0.000075, **sd 0.015341**, range [−0.0564, +0.0566] points
* response sd 11.0130
* **largest ΔR² a perfect composition could add over a flat constant: 1.9405e-06**
* **526× below D103's single-cell floor (~1.02e-03); 24× below D104's player-level home ceiling
  (4.63e-05)**

D108 honoured: prior FT % and prior FTA rate are **in the base from the start**.

| arm | MAE | R² | ΔR² vs BASE_NO_VENUE |
|---|---:|---:|---:|
| R2_TEAM_EWMA | 8.480207 | +0.057026 | +0.003029 |
| BASE_NO_VENUE | 8.489782 | +0.053997 | 0 |
| FT_FLAT | 8.489927 | +0.055242 | +0.001244 |
| FT_COMPOSED | 8.489554 | +0.055356 | +0.001358 |
| FT_COMPOSED_OVER_FLAT | 8.478908 | +0.056303 | +0.002306 |

| cell | comparison | ΔMAE | p | null_mean | null_sd | MDE80 |
|---|---|---:|---:|---:|---:|---:|
| P07 | FT_COMPOSED vs FT_FLAT | +0.000373 | 0.6716 | +9.00e-06 | 0.000852 | 0.00239 |
| P08 | FT_COMPOSED vs BASE_NO_VENUE | +0.000229 | 0.9895 | +1.09e-04 | 0.016692 | 0.04674 |
| P07b (exploratory) | FT_COMPOSED_OVER_FLAT vs FT_FLAT | +0.011019 | 0.4785 | +1.57e-04 | 0.015351 | 0.04298 |

**Reported as NOT ESTABLISHED, not ABSENT** (D108 ruling 4). Here the two coincide only because the
arithmetic ceiling is ~500× below anything this data can resolve — that is a statement about the
effect, not about the test.

**The spread the user asked for, quantified.** Team-season FT % over 2022–2024 ranges **74.23 % to
83.98 %** (sd 0.0273 across 36 team-seasons). The same +1.087 attempts is worth **0.8068** points
to the first and **0.9129** to the second — **a spread of 0.1061 points per game**, which is
**11.0 %** of the +0.965 home advantage and **0.0096** of one response standard deviation. Real,
exactly calculable, not actionable.

Note also: adding the free-throw main effects makes the forecast **worse** than the plain prior
reference (8.4898 vs 8.4802). The whole team-side free-throw family is a net loss for forecasting
points — the team-level counterpart of D108 ruling 1.

### 4.7 Player value (Step 4)

See `player_value_scope.md`. Headline: **β = +0.0284, 95 % [−0.0569, +0.1137]**, p 0.6013,
null_mean −0.0298, null_sd 0.0435, on 183 team-games with a pre-game top-3 absence worth 15.815
naive points. **β = 1.0 is 22.3 null sd away and decisively rejected**; the null detects a planted
β of 0.10 (p 0.0077). Absence-aware forecasting with an **oracle** absence indicator improves team
MAE by −0.00004 against an 80 %-power floor of 0.00584.

---

## 5. Nulls, power and controls

**Null choice.** Both arms forecast the same row, so the comparison is paired. N1 is a sign flip on
the per-row absolute-error difference with **whole team-seasons flipped together** (36 blocks),
because a team's forecast series shares its fitted state in both arms. N1b uses game blocks. N2 is
the row-level flip, computed **only** to publish the inflation factor (2.194× on P01, 1.342× on
P02) and never carrying a verdict. `null_mean` and `null_sd` sit beside every p (D103 ruling 2).

**D108 honoured explicitly.** The within-player cyclic shift is **not used anywhere in this
screen.** Every candidate here varies at team-game or between-team level, which a within-player
rotation preserves exactly, so it would have had no power at all. This is the first screen in the
programme where that rule was applied *before* the fact rather than diagnosed after.

**Power verified by injection, per cell** (`injection_power_per_cell.csv`):

| cell | null_sd | observed (null sd) | MDE80 (MAE pts) | detects 1.96 sd |
|---|---:|---:|---:|---|
| P01 | 1.76625 | +5.4 | 4.9455 | yes |
| P02 | 0.08971 | −2.3 | 0.2512 | yes |
| P03 | 1.77885 | −5.5 | 4.9808 | yes |
| P04 | 0.00920 | −1.1 | 0.0257 | boundary |
| P05 | 1.44570 | +5.3 | 4.0479 | yes |
| P06 | 1.75943 | +5.4 | 4.9264 | yes |

**Type-I check.** 400 synthetic no-effect datasets (whole blocks randomly sign-flipped) pushed
through the full null: **rejection rate at nominal 0.05 = 0.0425**, p quartiles 0.255 / 0.488 /
0.735. Calibrated.

**Controls.**

| control | rows actually perturbed | result |
|---|---:|---|
| NEG1 — `A_TEAM` swapped with another team's forecast on the same date | **88.0 %** | MAE 9.1782 vs real 8.6855; the team advantage over B1 shrinks from +9.578 to +9.085 |
| NEG2 — `B1` swapped the same way | **99.9 %** | MAE 19.2904 vs real 18.2630 |
| PLACEBO — identity transform through the whole scoring path | — | reproduces P01 with maximum deviation **exactly 0.000e+00** |

Both negative controls **verified to actually perturb** (D093 K7); neither is vacuous. NEG1's
advantage does not vanish entirely, and that is expected and worth naming: swapping a team's
forecast for another team's on the same date leaves a *plausible team points forecast* in place,
and B1's +8.14 level bias is so large that even a wrong-team forecast beats it. The control that
matters is that the swap **costs 0.49 MAE**, i.e. team identity carries real information.

---

## 6. Where this screen could have cheated

Declared in advance in `COMPARISONS_PRESELECTED.md` (C-1…C-7), and one found afterwards.

1. **C-1 — summing only players who appeared.** The largest available cheat. That is
   `B3_ORACLE_ROSTER`, labelled ORACLE, excluded from every headline and ranking. It would have
   made bottom-up look far better (10.650 against B1's 18.263).
2. **C-2 — tuning on the scored season.** Every half-life, shrinkage constant, blend weight, affine
   calibration and β is fitted on strictly earlier seasons. The 2022 fold sees only 2021 and its
   thin fits are printed in the run log (its `_ftpct_c` coefficients are exactly 0.0 because the
   2021 fold provides too little; that is visible, not hidden).
3. **C-3 — recalibrating using the scored season's mean.** B4 uses earlier seasons only.
4. **C-4 — rung shopping.** All three team reference rungs published. The conclusion is
   rung-independent: `A_TEAM` loses to R1 and R2 and beats only R0.
5. **C-5 — dropping the playoffs after seeing them.** Excluded before any statistic for D104's
   structural reason, and reported separately anyway; the ordering is unchanged.
6. **C-6 — quietly using the unmanifested contract v5.** The identity map was reconstructed from
   the canonical key and verified exact against manifest-verified v4 on all 22,659 shared rows.
7. **C-7 — cross-level ΔR².** Not done anywhere.
8. **Found afterwards, not in the prereg.** I could have quoted P02 — the team arm losing to its
   own matched reference — without noting that its observed 0.205 MAE sits **below** its own
   80 %-power floor of 0.251. It is significant at p 0.0159 *and* underpowered, and both facts are
   stated wherever it is quoted.

---

## 7. What is NOT established

* **Nothing about 2025 or 2026.** Never read, joined, plotted or described.
* **Nothing about player props or distributional accuracy.** This screen scored team totals only.
  The claim that the player level owns the *allocation* is an inference from the shared-budget
  mechanism and from where bottom-up loses least, **not a measurement**.
* **P02 is underpowered** (see above) and X1/X2 are both **not established**, so "fully repaired
  bottom-up ties top-down" is a failure to reject, not a demonstrated equality.
* **The FT composition is NOT ESTABLISHED, not absent** — though here the arithmetic ceiling makes
  the distinction academic.
* **The absence β is measured on 183 team-games.** The interval separates 0.10 from 0 but cannot
  separate 0.03 from 0.08. The *size* of the substitution effect is not established; only its
  smallness is.
* **`B1`'s roster miscalibration is a property of this champion arm**, not a proof that any
  bottom-up construction must fail. The matched-construction test (P09–P14) is the level result
  that does not depend on it, and it still favours the team level on all six quantities.
* **Sample.** D103's floor stands: effects below ~3e-04 are unreachable from 2021–2024 at the
  correct grouping level under any design. Every cell here is far above or far below that, so the
  floor does not bind on any conclusion drawn.

---

## 8. Files

| File | What |
|---|---|
| `WHICH_LEVEL_WINS.md` | **the user-facing answer** |
| `player_value_scope.md` | Step 4 scoping |
| `FINDINGS.json` | machine-readable, all steps |
| `COMPARISONS_PRESELECTED.md` | preregistration + hash |
| `DEFECTS.md` | three self-reported defects |
| `topdown_vs_bottomup.csv`, `..._by_season.csv`, `..._playoffs.csv` | Step 1 tables |
| `primary_cells_P01_P06.csv` | the six preregistered forecast cells |
| `gap_decomposition.csv`, `bottomup_repairs.csv` | Step 2 |
| `which_level_wins.csv`, `information_content.csv` | Step 5 |
| `ft_composition.csv`, `ft_cells.csv`, `ft_team_season_spread.csv` | Step 3 |
| `player_value_absence.csv`, `player_value_absence_heterogeneity.csv`, `absence_injection_power.csv` | Step 4 |
| `injection_power_per_cell.csv` | corrected power (D-1) |
| `injection_power.csv` | **DEFECTIVE, superseded, kept on disk** (D-1) |
| `exploratory_cells.csv` | X1, X2 |
| `nulls/*.npz` | permutation draws: P01–P06, P09–P14, type-I p-values, absence β |
| `scripts/` | s00…s11, `agg_base.py`, `refs.py` |
| `run_log.txt` | combined; `run_log_s*.txt` per step |
