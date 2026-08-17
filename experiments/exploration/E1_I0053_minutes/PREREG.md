# PREREG — E1_I0053_minutes

**A dedicated screen on MINUTES, on the decision stratum, with the reference tuned honestly first.**

Written and hashed **before any statistic relating any candidate to either response existed**. The
only thing measured beforehand is `scripts/s00_probe.py`, which looks at the candidate side and at
row counts alone: coverage, sd, and the **variance level of each candidate** (which fixes its null).
Its output is `out/s00.txt` and `out/_s00_candidate_levels.csv`. It never touches a response.

---

## 0. WHY THIS SCREEN EXISTS, AND WHAT WOULD MAKE IT FAIL

Every positive result the programme has found points at minutes, and minutes has never had its own
screen. All four pointers are by-products of screens aimed elsewhere:

| pointer | what it actually says |
|---|---|
| D116 / `E1_I0034` | absence redistribution: minutes **+1.82 %** of MAE, points **−1.17 %** |
| D121 / `E1_I0042` | that minutes effect survives an intercept freeze (**+1.774 % of MAE**, p 0.0030) where cold-start tiering and fallback routing go to exactly 0.0000 |
| D127 / `E1_I0046` | minutes has the tightest compositional constraint: team total is **0.8 %** of the player level's log-variance, against 4.4 % for points |
| D111 | minutes pays a **modest** bottom-up penalty because minutes are allocated by a coach, not emerged from a possession pool |

**Read `E1_I0042/HEADLINE_WITH_FLOORS.csv` before quoting the second row.** That screen's own
verdict column on the frozen minutes cell reads `BELOW_FLOOR_NOT_ESTABLISHED` against its carried
MDE80 (0.0933 against an effect of 0.0796) and the effect is **0.55×** its injection-verified floor.
The result is real as a *sign* and is **not established** as an effect by its own screen. This
prereg records that before measuring anything, because the brief that commissioned this screen
states it the other way round.

**The prior this screen writes down in advance: the tuned trailing-minutes reference captures most
of what exists, and a powered honest null is the expected outcome.** The programme has found the
same thing at three separate levels, and `E1_I0046` measured the tuning worth **15×** the detection
floor on points and **38×** on minutes share — more than any candidate it tested contributed.

---

## 1. PARTITION, WINDOW, STRATUM

* **Seasons 2021–2024 only.** 2025/26 is a sealed confirmation holdout and is never read, joined,
  merged, described or counted. Enforced on **values** by `mn_base.assert_partition`, which
  date-checks a column only if its dtype is genuinely datetime (K0: `candi-DATE` contains `date`).
* **Manifests**: `row` and `season` are usable, `artifact` is not, MISSING = UNVERIFIABLE.
* **One clean window exists: 2023–2024.** 2021 is degenerate (all forecasts at fallback level 4).
  2022 depends only on 2021 and is reported as a **disclosed contrast, never a headline**.
  **2023's own overlay is one step removed from the degenerate fold and this is stated wherever a
  2023 number is relied on.**
* **Walk-forward.** For eval season `s`, every coefficient and every hyperparameter is fitted on
  rows with `season < s`. Eval seasons: **2023, 2024** (headline), **2022** (disclosed).
* **DECISION stratum**: `n_prior >= 8` AND `prior5_minutes >= 24`, exactly D081/`E1_I0023`.
  Preregistered expectation from the probe: **n = 3,167 in 764 team-game blocks**, 113 players,
  2023–24. Pooled figures are reported **second, always**.

---

## 2. RESPONSES — AND THE CONSTRAINT, STATED HONESTLY

Universe: **appeared player-games** (`minutes > 0`) in regular-season games, 2021–2024. 16,717 rows,
1,776 team-games, 265 players.

| id | response | constraint |
|---|---|---|
| **R1_min** (**PRIMARY**) | `minutes` — the **LEVEL**, in minutes. This is the quantity a minutes prop is written on. | **UNENFORCED in the RAW arm.** Declared, not hidden. |
| **R2_smin** (secondary) | `minutes / T_min(g)` — the **SHARE** of the team's realised minutes | enforced: sums to 1 within team-game, asserted `< 1e-12` |

**The 200-minute budget is not exactly fixed.** The probe measures `T_min` over 1,776 team-games at
mean **201.2695**, sd **5.8573**, min 199.98, max 250.00, and **exactly 200.0 in 81.02 %** of
team-games. Overtime is the whole of the departure. "200 per team-game" is a good approximation and
is not an identity, and every projection below therefore projects onto the **realised** `T_min`,
which is an **oracle** and is recorded as such.

**Every cell is reported in both arms:**

* **RAW** — the forecast is not required to be an allocation. Primary for `R1_min`.
* **PROJ** — the forecast is rescaled inside the team-game to sum to `T_min` (for `R1_min`) or to 1
  (for `R2_smin`). **This uses the realised team total and the realised roster: it is an oracle
  ceiling, not an achievable live increment.**

Three of four candidates flipped sign under this constraint in `E1_I0046`. Both arms appear beside
each other in every table in this screen; neither is suppressed.

---

## 3. THE REFERENCE — TUNED FIRST, AND WHAT THE TUNING ALONE IS WORTH

D094's headline was withdrawn for testing a candidate against a weak benchmark. `E1_I0046` found
the tuning worth more than any candidate it tested. **The reference is therefore tuned before any
candidate is measured, and the value of the tuning alone is published as a result in its own right
in `REFERENCE.md`.**

`B_TUNED(h, k)`: a shrunken EWMA of the player's own strictly earlier response values,

```
raw = (1 - w) * EWMA_h(shift(1) response, within season x player) + w * target
w   = k / (k + n_prior)      target = 200 / n_hat   (R1_min)   or   1 / n_hat   (R2_smin)
```

`n_hat` is the team's own **strictly prior** expanding mean roster size. **200 is the rulebook, not
the realised total: the shrink target reads nothing from the game being forecast.**

* Grid: `h in {2, 3, 5, 8, 13, 21, EXPANDING}` × `k in {0, 0.5, 1, 2, 4, 8}` = **42 combinations**.
* Selected by **SSE on decision-stratum rows from strictly earlier seasons only**. No eval row is
  seen by any hyperparameter.
* Three benchmarks reported beside it, on identical rows:
  1. `B_NAIVE` = `B_TUNED(h = 5, k = 0)` — an untuned halflife-5 EWMA, no shrinkage.
  2. `B_TRAIL5` = the literal untuned **trailing-5 arithmetic mean**. On `R1_min` this is exactly
     `prior5_minutes`, the decision stratum's own gate variable.
  3. `B_UNIFORM` = an equal split of the team's minutes across the realised roster.
* **`TUNED − NAIVE` and `TUNED − TRAIL5` are tested with the same paired cluster sign-flip
  (blocks = team-games) used for every candidate**, so the tuning is held to the same bar.

The base design entering every cell is `X = [1, b]`, `b = B_TUNED`, refitted walk-forward.

---

## 4. CANDIDATES — CHOSEN AND JUSTIFIED BEFORE MEASUREMENT

**Ten columns: eight real, two controls.** Every one is strictly prior-only — a `.shift(1)`
construction inside `(season, player_id)` or `(season, team_id)`. The declared level is the
**measured** level from the probe, not an assumption.

### 4.1 The arithmetic that kills half of them in advance

Adding `g·x_g` to every member of a team-game and renormalising divides through by the same shift.
**A team-game-constant candidate cannot move a share** except through the second-order curvature of
the renormalisation (`E1_I0046` measured this at ΔR² −0.000005 on points). **It can move a level.**
Rest, schedule density, opponent pace, venue, travel and referee assignment are all team-game
constant. **This is exactly why this screen's primary response is the level.** The three
team-game-constant candidates below are preregistered to be **live on `R1_min`/RAW and dead on
`R2_smin`**, and both halves are reported.

### 4.2 The five that vary WITHIN the team-game

| id | construction, all strictly prior | measured var share WITHIN team-game | why |
|---|---|---:|---|
| `C1_player_rest` | days since **this player's own** last appearance, clipped at 21 | **0.377** | a player returning from absence is on a minutes restriction; her team's rest says nothing about that |
| `C2_foul_rate` | EWMA(halflife 5) of `shift(1)` fouls per 36 minutes | **0.905** | foul-trouble history — a high-foul player is removed from games she would otherwise finish |
| `C3_blowout_adj` | (prior mean minutes in **non-blowout** prior games) − (prior mean minutes over all prior games); blowout = prior game's realised \|margin\| ≥ 15 | **0.907** | the reference's own trailing average is contaminated by garbage time; this is the correction, and it is a **difference**, not the base's channel at another halflife |
| `C4_min_volatility` | sd of the player's prior 5 minutes | **0.796** | rotation-position stability: a player whose minutes swing is less forecastable and may be systematically over- or under-forecast |
| `C5_starter_delta` | `shift(1)` rolling-3 start rate − `shift(1)` expanding start rate | **0.930** | starter/bench transition, caught earlier than a level start rate catches it |

**`C1_player_rest` is MIXED — 62.3 % of its variance is between team-games.** It is therefore
**decomposed and tested component-wise**, as are the other four, because a null matched to one
component is blind to the other:

* `xW = x − mean_tg(x)` → tested under `N_TGSWAP` and `N_PSWAP`
* `xB = mean_tg(x)` → tested under `N_TGBLOCK`

The raw column is also reported under `N_TGSWAP`/`N_PSWAP` **with the explicit caveat that those
nulls preserve `xB` exactly and therefore do not test it.**

### 4.3 The three that are CONSTANT within the team-game

| id | construction, all strictly prior | measured var share WITHIN team-game | why |
|---|---|---:|---|
| `C6_team_rest` | days since the **team's** previous game, clipped at 21 | **0.000** | schedule rest — the canonical minutes story |
| `C7_sched_density` | count of the team's own games in the strictly prior 7 calendar days | **0.000** | schedule density / back-to-back load |
| `C8_opp_pace_prior` | opponent's strictly prior expanding mean of `fga + 0.44·fta − oreb + tov` | **0.000** | opponent pace — more possessions, more minutes to give |

`C7_sched_density` takes **5 distinct values** and `C6_team_rest` **9** on the decision stratum,
across 764 team-game blocks. **This is precisely the shape that produced trap 1 four times** — a
handful of values shared across thousands of rows, given a row-level null. It gets `N_TGBLOCK`.

### 4.4 Controls

| id | what it is | its job |
|---|---|---|
| `G01_noise` | seeded row-level standard normal | negative control for the within-team-game family |
| `G02_tg_noise` | seeded **team-game-constant** standard normal | negative control for the team-game-constant family — a matched control the tg-constant candidates are compared against, which the reference card's rule 5 requires |

### 4.5 Considered and DROPPED before the hash, with reasons

* **Recent coach change** — `master_player` and `master_team` carry no coach column. **No data.
  Dropped, not tested, not counted in any family size.**
* **Travel distance / time-zone change** — no venue coordinates in the masters. Dropped.
* **Injury-report designation** — the injury capture is a live daily process, not a historical
  panel over 2021–24 verified for this window. Dropped rather than trusted.
* **Blowout exposure of the *current* game** — reads the future. Only the *prior*-game version
  (`C3_blowout_adj`) is admissible, and that is what is preregistered.

---

## 5. NULLS — MATCHED TO THE LEVEL THE CANDIDATE VARIES AT

| null | what it permutes | tests | blocks (measured) | used for |
|---|---|---|---:|---|
| `N_TGSWAP` | the candidate among players **inside the same team-game** | which player in this team-game holds which value | **1,776** | within-tg candidates and `xW` components |
| `N_PSWAP` | a player-season's **whole series** onto another player in the same team-season, at proportional positions | which player owns the series, with serial shape preserved (K6) | **48** team-seasons, 634 series | second required null for within-tg candidates |
| `N_TGBLOCK` | a team-game-constant value among the **team-games played on the same date** | whether the team-game level of the candidate matters | **335** dates | tg-constant candidates and `xB` components |
| `N_WITHIN_PLAYER` | cyclic shift inside a player-season | **CONTRAST ONLY, NEVER A VERDICT** | 634 | the blind-null demonstration |

* **A within-team-game candidate is credited only if it beats BOTH `N_TGSWAP` and `N_PSWAP`.**
* **`N_TGSWAP` is the literal identity for a team-game-constant candidate.** It is run on
  `C6`/`C7`/`C8`/`G02_tg_noise` anyway, as a control that **cannot** fail, and the observed null sd
  is published rather than rounded to zero.
* **Block counts are published in every cell.** Below six blocks a two-sided sign-flip cannot
  reject; all four nulls are far above that and the number is stated so the reader can check.
* **Null validity is verified by component-wise injection**, never by shuffled residuals, and the
  **null-centre ratio** — the null's own mean divided by the mean of the identical statistic over
  injected-at-θ=0 replicates through the identical path — is reported for every null. A valid null
  sits at ≈ **+1**; `E1_I0043` separated valid from blind at **+1.030 vs −0.040**.
* **A blind null is demonstrated on this screen's own data**, not cited: `N_WITHIN_PLAYER` applied
  to a between-player candidate.
* **2,000 draws** for `N_TGSWAP`, `N_TGBLOCK` and `N_WITHIN_PLAYER`; **600** for `N_PSWAP` (it is a
  Python-level series reassignment). `p` is the add-one estimator; the attainable floor is published.

---

## 6. ARMS — THE FREEZE IS THE DISCRIMINATING CHECK

Every cell is run in **both** arms and **both are reported in the first three sentences of
`VERDICT.md`**:

* **UNFROZEN** — refit `[1, b, d]` walk-forward. The base weight is free to move.
* **FROZEN** — the base intercept and slope are **held at the base fit**; only the candidate's
  coefficient `g` is estimated, on the base's training residual.

Two of three validated components in this programme went to **exactly 0.0000** frozen; a candidate
scored +0.0287 at p 0.00005 on rows where it substituted nothing; and `E1_I0046`'s one surviving
allocation candidate went from **+0.005487 unfrozen to −0.004696 frozen**. A candidate that is large
unfrozen and negative frozen is a **substitute** for the reference, not an addition to it, and this
screen will say so in those words if it sees it.

---

## 7. CEILING — COMPUTED BEFORE ANY FIT, WITH FULL DENOMINATORS

`CEILING.md` is written before `s04` runs. Every ceiling and every floor on that page carries
**response · row set · SST basis · weighting · base · fit kind · statistic family**, or is marked
`NOT_COMPARABLE` under D101.

* **Unconstrained oracle**, bounding the UNFROZEN/RAW arm: `(d·e)² / ((d·d)·SST)`, `d` = candidate
  residualised on `[1, b]` on the eval rows, `e` = the base's walk-forward eval residual.
* **Projected oracle**, bounding the FROZEN/PROJ arm only.
* **Family joint oracle** over the real candidates, with the **degrees-of-freedom cost stated**:
  `K / n` under the pure null on `n` rows.
* **`c*` = (d·e)/(d·d) is published for every ceiling.** No `c*`, no bound claim (reference card
  rule 4). **A matched control goes through the identical path for every ceiling** (rule 5).
* **`(d·d)/SST` is not a bound** and is not used for anything.

### 7.1 Floors — and why the programme's published floors do not apply here

Per `E1_I0049_benchmark_constants/REFERENCE_CARD.md`, quoted from the file and not from memory:

* `0.00102` and `0.00235` are **ΔR² on `y_ppm` (points per minute)**, DECISION stratum n = 5,673,
  `B_COMPLETE` base, entity-swap team-season null, seasons 2021–2024.
* Their **points-scale** equivalents are ≈ **0.00072** and ≈ **0.00181**; the defensible output of
  that conversion is the **ratio 0.704 / 0.770**, not the absolute numbers.
* `0.002057` is an **in-sample transported CEILING**, `c*` = 1.359, so **not a bound**, and it must
  never be quoted as an effect. The largest live **effect** is **0.0023492** — walk-forward paired
  ΔR² on points, n = 4,517, seasons 2022–2024.

**None of those is on this screen's response.** `R1_min` is minutes and `R2_smin` is a minutes
share; neither is `y_ppm` and neither is points. **Every comparison between a number in this screen
and a published programme floor is therefore `NOT_COMPARABLE` under D101 and is labelled so.** This
screen computes and uses **its own floors on its own response, row set and null**:

1. **Analytic**: `MDE80 = 2.80 × null_sd` of the cell's own matched null (1.96 + 0.84).
2. **Injection-verified**: the effect size at which component-wise injection into the **real**
   response, rerun through the whole path, is detected at 80 % power. **This is the floor a verdict
   is taken against** when the two disagree.
3. **Block bootstrap** over the 764 scored team-game blocks, as a second variance estimate.
   `E1_I0046` found these disagreeing by 8.07× and reported it; if they disagree here, both are
   published and the cell is called **not established** if either says so.

---

## 8. THE PREREGISTERED CELL GRID

| grid | response | arm (projection) | fit arm | candidates | cells |
|---|---|---|---|---|---:|
| **PRIMARY** | `R1_min` | **RAW** | FROZEN, UNFROZEN | all 10 | 20 |
| CONSTRAINT | `R1_min` | PROJ | FROZEN, UNFROZEN | all 10 | 20 |
| SHARE | `R2_smin` | PROJ | FROZEN, UNFROZEN | all 10 | 20 |
| COMPONENT | `R1_min` | RAW | FROZEN, UNFROZEN | `xW` and `xB` of the 5 within-tg candidates + `G01_noise` | 24 |

**84 cells.** The headline is the **PRIMARY** grid on the **DECISION** stratum in the **clean
2023–24 window**. Family-wise correction is by **coupled max-z from the same draw stream**
(D120), computed separately within each null family: **K = 5** for the within-tg family under
`N_TGSWAP`, **K = 3** for the tg-constant family under `N_TGBLOCK`. Both are reported, and the
combined **K = 8** figure is reported beside them.

---

## 9. DECISION RULE, FIXED NOW

A candidate is **ESTABLISHED on minutes** only if **all** of the following hold on the DECISION
stratum in the clean window:

1. `p < 0.05` under **every** null matched to its level (both, for a within-tg candidate);
2. the effect exceeds its **injection-verified** 80 %-power floor;
3. it clears the **family-wise** bar within its null family;
4. it survives the **block bootstrap** as well as the permutation null;
5. it is **stable in sign** across eval 2023 and eval 2024 reported separately;
6. its `FROZEN` and `UNFROZEN` values are **both reported**, and if they disagree in sign the cell
   is reported as a **substitute**, not as an addition.

Anything failing any of these is reported as **NOT ESTABLISHED** with its number printed anyway.

**A powered honest null is an acceptable and expected outcome.** No champion is fitted. No
production change is proposed. Nothing is promoted to the ledger from here.

---

## 10. DISCIPLINE COMMITMENTS

* **Anchors reproduced before any new statistic**, with the run halting on failure. The anchor set
  includes **exact** reproductions of `E1_I0046`'s published tuned and naive minutes-share R²
  (0.27683141342060724 / 0.24552519662119843 and 0.2395715216025346 / 0.2059808964669676) from an
  independent reimplementation, D104's home advantage on 888 games, and the decision-stratum counts.
* **Signed statistics and raw unstandardised draws are stored** with full stratum keys in both the
  filename and the payload. 117 cells in this programme are permanently unauditable for the first
  reason and 24 more for the second.
* **No name-based selection anywhere.** Six findings died to substring matching. Every column list
  in `mn_base.py` is an explicit literal allowlist with its length asserted.
* **No retrospective baseline.** Six instances, one hidden inside inference machinery, one caught
  only because it produced an impossible ΔR² of 2.43. Every constructed column's time window is
  declared in `NOTES.md` and a future-leakage probe is run on all ten.
* **The result that most weakens the conclusion appears in the same document as the conclusion.**
* **`DEFECTS.md` records this screen's own defects**, including any found after the hash.
* Anything added after this hash is listed in `NOTES.md` with its **direction** — whether it could
  strengthen or only weaken a headline.
