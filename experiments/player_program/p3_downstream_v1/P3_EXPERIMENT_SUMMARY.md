# `p3_projected_exposure_downstream_v1` — final summary

**Status: COMPLETE. Registered, executed, frozen. No arm promoted. All P3 work stops here.**

Nothing in this document is a production decision. This is historical development evidence.

---

## 1. Experiment question

Does the frozen P3 player-impact signal add chronological out-of-sample team-forecast value when
aggregated using **cutoff-valid projected exposure**, rather than the actual lineups, actual
minutes, actual stint durations and actual possessions that every prior positive P3 result
depended on?

## 2. Final conclusion — authoritative wording

> **The frozen P3 coefficients did not demonstrate incremental team-forecast value under the
> registered cutoff-valid `projected_player_possessions_v1` exposure system.**

This is the wording of record. Two earlier phrasings were broader than the evidence supports and
are **withdrawn**:

- the claim that the P3 signal "did not survive projected exposure";
- the commit subject of `e1ea9ee`, which uses that broader phrasing. The commit message cannot be
  rewritten without rewriting history; **this document supersedes it.**

The test shows no demonstrable value *under this specific registered exposure construction*. It
does **not** prove that no materially different future exposure model could ever recover value.

The negative result is nevertheless **decisive for the current track**:

- all registered arms fail;
- no paired margin improvement is statistically supportable;
- team-score gains are negligible and unstable;
- signs reverse across seasons;
- club-level results are concentrated and inconsistent;
- exposure-bucket behaviour is non-monotonic;
- games improved versus worsened is approximately a coin flip;
- sensitivity gains grow as the candidate universe becomes *less* plausible, which is evidence
  against interpreting them as genuine personnel value.

## 3. Registered design

Registered **before execution** at commit `471d7f9`, registry record
`p3_projected_exposure_downstream_v1` in `experiments/player_program/arm_registry.jsonl`.

Nothing was refit: P3 coefficients, exposure model, pace model and team incumbent were all
consumed frozen. The exposure allocator was not touched after results were opened.

### Frozen inputs

| input | artifact | sha256 (first 20) |
|---|---|---|
| structural team incumbent | `experiments/channel_reval/predictions_v2.csv` | `5ba999544368669d5f4a` |
| P3 coefficients | `experiments/player_program/fits_v1/p3_coefficients_v1.parquet` | `a9948cc418596bb8cefd` |
| projected exposure | `projected_exposure_v1/projected_player_possessions_v1.parquet` | `1f47f1f169955cae5c65` |
| projected rotations | `projected_exposure_v1/projected_team_rotations_v1.parquet` | `d2c4011382eddc82e66e` |
| pace prior | `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c075148553920b79c` |

`experiments/arm_incumbent/` is **REJECTED** (target-box membership controlled its coverage) and
was not consumed.

The operator authorised "commit `9806cb5` versions" of the exposure artifacts. The corrections
commit `471d7f9` added **labelling columns only**. The executor asserts, before any arm is
evaluated, that every projected minute and possession is byte-identical to `9806cb5`; the four
added columns are `information_available_at_cutoff`, `historically_captured_asof`,
`operationally_plausible`, `production_eligible`. **The assertion passed.**

### Commits

| commit | what |
|---|---|
| `9806cb5` | exposure bridge registered, built, validated (34/34) |
| `471d7f9` | receipt corrections + availability/plausibility split (35/35); P3 experiment registered |
| `e1ea9ee` | P3 comparison executed |
| `e4f244c` | club and player-exposure concentration reporting completed |

## 4. Exact primary universe

Regime **`tier_a_only`** — the only regime resting on roster evidence captured before the cutoff.

**673 of 673 incumbent games eligible. Zero exclusions.**

| exclusion reason | games |
|---|---|
| rotation not `normal` (home) | 0 |
| rotation not `normal` (away) | 0 |
| personnel effect unresolved | 0 |
| trailing baseline unresolved | 0 |
| incumbent prediction missing | 0 |

Seasons 2024 (229), 2025 (276), 2026 (168); regular season and playoffs. Every trailing personnel
baseline resolved at **level 1** (≥3 prior same-season games, mean of the most recent 10). All arms
evaluated on **identical games, team rows and decision times** — one eligibility mask, applied to
every arm.

Coefficient support: possession-weighted share of projected offensive possessions held by a player
with a coefficient — mean **0.840**, p05 0.673, median 0.849, max 1.000. Players without a
coefficient take **0.0**, the neutral league-average value in RAPM units.

## 5. Arm equations

Units: `orapm_100` and `drapm_100` are points per 100 possessions; multiplying by possessions/100
yields points, matching the incumbent's score forecast.

Signs: `orapm_100` raises the player's **own** team's score. `drapm_100` is points *prevented* (the
artifact already flipped the internal points-allowed sign), so a positive value **lowers the
opponent's** score. `net_rapm_100 = orapm_100 + drapm_100`.

Personnel effects, per team T and game g:

```
E_off(T,g) = Σ_p orapm_100[p, Y−1]   × projected_off_possessions[p,T,g] / 100
E_def(T,g) = Σ_p drapm_100[p, Y−1]   × projected_def_possessions[p,T,g] / 100
E_net(T,g) = Σ_p net_rapm_100[p, Y−1] × projected_off_possessions[p,T,g] / 100
```

Coefficient cutoff: `training_cutoff_season == season − 1` (`fit_rate_and_p3.py:182` sets
`training_cutoff_season = test_season − 1`).

Centering — the adjustment is **current projected personnel minus the team's prior-games-only
expected personnel**, so the incumbent's existing team tendencies are not double-counted:

```
B_x(T,g) = mean of E_x(T,g′) over T's games g′ strictly earlier than g
           level 1: ≥3 prior same-season games → mean of the most recent 10
           level 2: else ≥3 prior-season games → mean of the most recent 10
           level 3: else league mean of E_x over all strictly earlier games
           level 4: else UNRESOLVED → game excluded from every arm

Δ_x(T,g) = E_x(T,g) − B_x(T,g)      for x ∈ {off, def, net}
```

Window K=10, minimum history m=3, unweighted (no decay). This is the **same** ladder already
registered and validated for `team_possession_prior/1`; reusing a validated ladder avoided
introducing a fresh arbitrary choice. Only **one** baseline rule was registered, so there is no
multiplicity to correct.

| arm | home forecast | away forecast |
|---|---|---|
| **A** incumbent | `str_home_cal` | `str_away_cal` |
| **B** offensive | `str_home_cal + Δ_off(H)` | `str_away_cal + Δ_off(A)` |
| **C** net | `str_home_cal + Δ_net(H)` | `str_away_cal + Δ_net(A)` |
| **D** separate | `str_home_cal + Δ_off(H) − Δ_def(A)` | `str_away_cal + Δ_off(A) − Δ_def(H)` |
| **E** defensive diagnostic | `str_home_cal − Δ_def(A)` | `str_away_cal − Δ_def(H)` |

### Predeclared consequences — both verified at execution

1. v1 assigns **equal** projected offensive and defensive exposure, so `E_net = E_off + E_def`
   exactly. Differences between arms C and D therefore arise from **coefficient construction,
   estimation and shrinkage — never from different offensive and defensive exposure estimates.**
   *Verified: max deviation < 1e-9.*
2. It follows algebraically that **arms C and D produce identical margins.**
   *Verified to 1e-9.* They can differ only in how the adjustment splits between home and away
   **scores**. A margin difference between C and D would have been an executor defect, not a
   finding.

## 6. Results — pass/fail

**Every arm FAILS.** No paired improvement is statistically supportable.

| arm | margin MAE | margin RMSE | margin bias | calib. slope | team-score MAE | total MAE | verdict |
|---|---|---|---|---|---|---|---|
| A incumbent | 10.1603 | — | −0.7631 | 1.1975 | 8.7045 | 14.2236 | baseline |
| B offensive | 10.1531 | — | — | — | 8.6862 | — | **FAIL** |
| C net | 10.1308 | — | −0.6988 | 1.1049 | 8.7040 | 14.1884 | **FAIL** |
| D separate | 10.1308 | — | −0.6988 | 1.1049 | **8.6677** | 14.1397 | **FAIL** |
| E defensive | 10.1347 | — | — | — | 8.6893 | — | **FAIL** |

Home / away score MAE — A 8.7928 / 8.6163; B 8.7800 / 8.5923; C 8.7848 / 8.6232;
D 8.7657 / 8.5698; E 8.7890 / 8.5897.

### Paired differences vs incumbent, 90% game-clustered bootstrap (673 clusters)

Positive means the arm beats the incumbent.

| arm | margin MAE improvement | 90% CI | team-score MAE improvement | 90% CI |
|---|---|---|---|---|
| B offensive | +0.0072 | [−0.0613, +0.0721] | +0.0184 | [−0.0152, +0.0513] |
| C net | +0.0295 | [−0.0568, +0.1144] | +0.0005 | [−0.0446, +0.0451] |
| D separate | +0.0295 | [−0.0568, +0.1144] | +0.0368 | [−0.0000031, +0.0713] |
| E defensive | +0.0256 | [−0.0122, +0.0630] | +0.0152 | [−0.0053, +0.0348] |

**Every interval includes zero.** D's team-score interval has a lower bound of −3.1e-06 — it
touches zero and does not exclude it.

Paired inference is clustered at the **game** level, so the two team-score rows from one game are
never treated as independent.

The median absolute margin adjustment is **0.78 points** against a ~10-point margin MAE (mean 1.04,
p95 2.97, max 5.73). The adjustment barely moves the forecast.

## 7. Diagnostics

### By season — the sign reverses

| season | n | A | B | C / D | E |
|---|---|---|---|---|---|
| 2024 | 229 | 9.0837 | 9.0526 | 8.9790 | 9.0075 |
| 2025 | 276 | 11.0249 | 10.9657 | 10.9551 | 11.0079 |
| 2026 | 168 | 10.2073 | 10.3182 | **10.3465** | 10.2364 |

Mean margin improvement for C/D: **+0.105 (2024), +0.070 (2025), −0.139 (2026)**. Every adjusted
arm degrades in 2026.

### By club — concentrated and inconsistent

| arm | clubs improved | clubs worsened | share of the positive total from the single best club |
|---|---|---|---|
| B offensive | 5 | 10 | **39.9%** |
| C / D | 7 | 8 | **37.4%** |
| E defensive | 11 | 4 | 22.5% |

Arms C and D improve fewer than half the clubs, and over a third of the entire positive total comes
from one club. The aggregate gain is not broad-based. E is the most broad-based arm across clubs,
but its paired CI still includes zero and its 2026 improvement is negative.

### By game — a coin flip

C/D improve **338** games and worsen **335**. About 18% of the total absolute movement sits in the
top 5% of games, for every arm.

### By coefficient support — no monotone relationship

| bucket | n | support range | A | C / D |
|---|---|---|---|---|
| low | 225 | 0.556–0.802 | 10.419 | 10.474 (**worse**) |
| mid | 224 | 0.802–0.892 | 9.550 | 9.498 |
| high | 224 | 0.892–1.000 | 10.511 | 10.419 |

### By largest single-player adjustment — non-monotone

| bucket | n | largest single-player adjustment (points) | A | C / D | E |
|---|---|---|---|---|---|
| low | 225 | 1.19–2.88 | 10.0588 | 9.9846 | 10.0233 |
| mid | 224 | 2.88–4.01 | 10.2235 | 10.2377 (**worse**) | 10.2304 |
| high | 224 | 4.02–7.48 | 10.1990 | 10.1707 | 10.1507 |

There is no coherent relationship between the size of the personnel adjustment and forecast gain.

## 8. Sensitivity regimes — warning

Both sensitivity regimes were run **restricted to the 673 primary games**; neither enlarged or
redefined the primary universe.

| regime | margin MAE (A) | (C/D) | production-eligible? |
|---|---|---|---|
| `tier_a_plus_tx_b` | 10.1603 | 10.0874 | **No** — transaction evidence was retrospectively scraped; all 4,169 rows observed 2026-07-30, after every one of their cutoffs |
| `tier_a_plus_tx_b_plus_s2` | 10.1603 | 10.0832 | **No** — cutoff-available, but operationally implausible: up to 70 allocated players, effective rotation size to 67.8 |

**The apparent gain grows as the candidate universe becomes less plausible.** A gain that tracks
candidate-set breadth rather than personnel quality is evidence *against* reading it as genuine
personnel value. Neither regime may be reopened as a candidate production model.

## 9. Findings preserved

1. **The oracle-conditioned stint result remains valid** evidence of intrinsic player signal under
   realised lineups and exposure: stint differential MAE ≈ 2.147 against ≈ 2.206 intercept-only, on
   35,515 held-out stints across 1,286 games, game-clustered CIs excluding zero.
2. **This downstream result remains valid** evidence that the signal is not operationally useful
   under the registered v1 exposure pipeline.
3. **The offensive/defensive decomposition affected team-score allocation but not margin** relative
   to the net arm, because v1's offensive and defensive exposure assignments are identical.
4. **The null, negative and partial findings stay on the record** — season, club, game-concentration
   and exposure-bucket diagnostics included — in the registry and in the capability matrix.
5. **The frozen P3 coefficients remain available for a future ablation only if** a materially
   different exposure artifact is developed for an **independently justified reason**. This result
   alone is **not** authorisation to build or tune such an artifact.

## 10. Non-promotion decision

**No arm is promoted. Nothing here changes production.**

`projected_player_possessions_v1` is accepted as a **research artifact** only. Every regime carries
`production_eligible = False`.

## 11. No post-result tuning occurred

The following are prohibited and **did not happen**:

- P3 penalties or coefficients were not retuned;
- the adjustment was not rescaled;
- no favourable trailing-baseline window was searched — one ladder was registered before execution
  and used unchanged;
- no club, season, player or exposure bucket was selected post hoc — all diagnostics are
  breakdowns of the single frozen primary universe;
- no arm was promoted;
- `projected_player_possessions_v1` was not revised in response to these results;
- the transaction-derived and S2 regimes were not reopened as candidate production models.

The only change after results were opened was the **addition of the club and player-exposure
concentration breakdowns** the registration already required and I had omitted (`e4f244c`). It
changed no arm, universe, coefficient or allocation, and it made the result *more* negative.

## 12. Limitations

- v1 assigns equal offensive and defensive exposure, so C-vs-D isolates coefficients only; a
  substitution-timing model would be needed to separate the two exposures.
- Coefficient support averages 84% of projected possessions; the low-support bucket is *worse* than
  the incumbent.
- No rotation truncation: every viable candidate receives minutes, and Tier A's maximum effective
  rotation size of 14.21 exceeds the 12-player standard active roster on 994 of 2,914 team-games.
- 2026 is partial (through 2026-07-29 in the incumbent sample).
- The incumbent sample is 673 games over three seasons — small for detecting effects of this size.
- Availability information before 2026-07-30 is not a genuine captured pregame feed; that
  limitation lives in the bound v15 `p_active` and is inherited here unchanged.
