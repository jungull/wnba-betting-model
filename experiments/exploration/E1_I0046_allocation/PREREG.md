# PREREG — E1_I0046_allocation

**Is the ALLOCATION of a team's scoring across its roster forecastable at all, independent of
absences?**

Frozen before any statistic in §5–§9 was computed. The sha256 of this file as committed is in
`PREREG.sha256`. Every cell below is fixed here; additions after the hash are listed in `NOTES.md`
with their direction of effect on the headline.

---

## 0. WHAT THIS SCREEN IS NOT

* It does **not** fit a champion, propose a production change, or tune anything on evaluation rows.
* It does **not** compare a share response to a level response by ΔR², MAE, or any variance share.
  **Share and level are different responses (D101).** The only quantity compared across them is
  **autocorrelation**, which is unitless, computed on identical rows, in identical order. That
  comparison is declared here as the sole exception and is justified in §8.
* It does **not** claim a live increment. Two oracles are granted throughout (§2.4) and every
  number is therefore an **oracle ceiling**, in the sense E1_I0034 used the term.

---

## 1. THE QUESTION, DECOMPOSED INTO TWO

E1_I0033 established the team owns the total (summed player forecasts correlate **+0.0013** with
team points; substitution is essentially complete, β = 0.028 with β = 1 rejected at 22 null sd).
E1_I0034 established that, *in the absence-driven case*, the allocation of **minutes** is real,
threshold-dependent and **diffuse** — no pre-game predictor explains more than 1.5% of who
benefits — and that the same term applied to **points** is harmful (−1.17% vs champion).

Nobody has asked the general question. It splits in two and both halves are preregistered:

* **Q1 — IS ALLOCATION FORECASTABLE AT ALL?** Does a trailing-share allocator beat a
  no-information allocator (equal split across the realised roster)? Expected answer: **yes,
  trivially and largely** — a star takes a bigger share than a bench player. Q1 is preregistered
  anyway because the programme's headline claim must not rest on an unstated assumption, and
  because its *size* is the denominator for Q2.
* **Q2 — IS ANYTHING FORECASTABLE BEYOND THE TRAILING SHARE?** Can any preregistered pre-game
  candidate add to a **TUNED** trailing-share allocator? This is the commercially central half.
  **Prior: null.** This programme has repeatedly found that a well-built simple estimator beats
  everything (D101, E1_I0022, E1_I0033 §1 where a tuned team EWMA beats the champion team arm), and
  one headline was withdrawn when re-tested against a tuned rather than a weak benchmark.

**A powered honest null on Q2 is the expected and fully acceptable outcome and will be reported as
the headline if that is what the data says.** No survivor will be manufactured.

---

## 2. CONSTRUCTION — THIS IS THE WHOLE SCREEN

### 2.1 The composition universe

Source: `data\masters\master_player.parquet` and `data\masters\master_team.parquet`, **regular
season only**, **seasons 2021–2024 only, enforced on VALUES**. 2025 and 2026 are never read,
joined, merged or described.

For a team-game `g`, the **composition universe** `C(g)` is every player of that team with
`minutes > 0` — the realised appeared roster. Mean size ≈ 9.41.

**Closure is asserted, not assumed**, on all 1,776 team-games:

* `Σ_{i∈C(g)} pts_i == team pts` — required **exact**, max |diff| = 0.
* `Σ_{i∈C(g)} fga_i == team fga` — required **exact**, max |diff| = 0.
* `Σ_{i∈C(g)} minutes_i` vs team minutes — max |diff| ≤ 0.07 (minute:second rounding). The
  minutes share therefore uses the **roster sum** as its denominator, not the team box minutes, so
  the minutes composition closes to exactly 1 as well.

If any closure assertion fails the run halts.

### 2.2 The response — THE CHOICE THAT IS THE WHOLE SCREEN

For player `i` in team-game `g`:

```
s_i  =  y_i / Y_g        where   Y_g = Σ_{j ∈ C(g)} y_j
```

with `y` one of **points**, **minutes**, **field-goal attempts**. By construction
`Σ_{i∈C(g)} s_i = 1` exactly (asserted to 1e-12 on every team-game).

**Why conditioning on the realised total is the point.** The team total is the part E1_I0033 showed
the team model already owns and the player model is worst at. Dividing it out removes exactly that
part and leaves the part **only a player model can supply**. The residual question — who takes
which share of whatever the team scores — is the entire content of a player-props market.

Three responses, three separate cells, never compared to each other:

| id | response | denominator |
|---|---|---|
| **R1_s_pts** (PRIMARY) | player points share | roster points |
| R2_s_min | player minutes share | roster minutes |
| R3_s_fga | player attempts share | roster attempts |

### 2.3 The compositional constraint (D111) — how it is handled

**Shares sum to one. Ordinary independent modelling of shares is wrong by construction**, and
D111's rule is exactly on point: *allocations of a shared fixed budget do not survive being modelled
separately.* Handled in three places, all of them declared here:

1. **PROJECTION (primary).** Every forecast — base and augmented, identically — is projected onto
   the simplex inside its team-game: `ŝ_i ← max(ŝ_i, 0) / Σ_{j∈C(g)} max(ŝ_j, 0)`. A team-game
   whose projected sum is 0 falls back to `1/|C(g)|`; the count of such team-games and of clipped
   rows is reported. The projection is applied to **every** arm and **every** null draw, so it can
   advantage neither side.
2. **RAW arm reported beside it.** The identical cell with **no** projection — the "model them
   separately" construction D111 forbids — is computed and reported for every cell. The
   **difference between PROJ and RAW is the measured cost of ignoring the constraint** and is a
   deliverable, not a footnote.
3. **BLOCKING.** The exchangeable unit for every null and every power calculation is the
   **team-game**, because the composition is the unit. Never the row.

**A consequence, derived here before any fit and tested in §5 as cell A5.** A candidate that is
**constant within the team-game** cannot move a projected allocation to first order: it shifts every
member's forecast identically and the shift cancels in the renormalisation. Opponent, venue, pace
and rest are all such candidates. This is an arithmetic property of the response, not an empirical
finding, and A5 is preregistered specifically to demonstrate it on real data.

### 2.4 THE TWO ORACLES — declared, because a null under an oracle is stronger

| oracle | what is granted | why it is granted |
|---|---|---|
| **ORACLE TOTAL** | `Y_g`, the realised team total, defines the response | This is the conditioning that isolates allocation. It is in the **response only**. |
| **ORACLE ROSTER** | `C(g)`, who actually appeared, defines the composition and the projection denominator | Renormalising an allocation requires knowing across whom. The programme's own availability forecast sums to 10.34 players where 9.40 play (E1_I0033) and both pre-game injury sources return `manifest_present: false`, so no honest pre-game roster exists. |

**These make every number here an upper bound.** A null measured with the total and the roster
handed over for free is a null *a fortiori* under live conditions. That is the point of granting
them.

### 2.5 NO RETROSPECTIVE BASELINE — the leakage firewall

The programme has six retrospective-baseline instances, one inside inference machinery. The two
uses of the realised total are kept strictly apart and the separation is enforced mechanically:

* **LEGITIMATE — response side.** `Y_g` and `C(g)` enter the *response* and the *projection
  denominator*.
* **FORBIDDEN — forecast side.** No feature, base or candidate may read `Y_g`, any same-game box
  quantity of any player, or anything dated on or after `game_date`.

Enforced by: every feature built by an explicit `.shift(1)` inside `(season, player_id)` or
`(season, team_id)` ordered by `(game_date, game_id)`; an explicit literal allowlist of feature
columns whose length is asserted against a literal; and a **future-leakage probe** run on the base
and on each candidate (correlation with the entity's own strictly-after-date future, per the kit's
`future_leakage_probe`, read as a **screening flag, not a verdict**). `starter_flag` and every
same-game box column are **excluded by construction** — the candidate A3 uses the player's
**prior** starting rate, never this game's.

**NO NAME-BASED SELECTION.** Six findings in this programme died to substring matching. Every
column list in this screen is an explicit literal, printed when resolved, with its length asserted
against a literal. The partition gate is on **VALUES** only: seasons are checked against
`{2021,2022,2023,2024}`; a column is date-checked only if its dtype is genuinely datetime
(`candi-DATE` contains `date`, and `pd.to_datetime` on a float silently returns 1970).

### 2.6 The window

**One clean window exists: 2023–2024**, verified from fold receipts by E1_I0042 — 2021 is
degenerate (all forecasts at fallback level 4, a constant) and 2022 depends only on 2021.

| window | eval seasons | train | status |
|---|---|---|---|
| **CLEAN_2023_24** | 2023, 2024 | strictly earlier seasons | **every headline** |
| DISCLOSED_2022 | 2022 | 2021 only | reported, never a headline |
| 2021 | — | — | **never evaluated** |

Every number in every deliverable states which window backs it.

### 2.7 The decision stratum — REPORTED BEFORE ANY POOLED NUMBER

`n_prior ≥ 8` **AND** `prior5_minutes ≥ 24` (D081, as `E1_I0023/s00_prereg.py` defined it).
`n_prior` is prior **appeared** games in the same season; `prior5_minutes` is the mean of the
player's prior five appeared games' minutes. Both reproduce `E1_I0018/screen_frame.parquet` exactly
(anchor A2).

**Why it is the point of this screen.** A prior screen reported a +3.51% headline that touched
**zero** betting-relevant rows, and a stacked result shrank **17.5×** on crossing into this stratum.
**Pooled numbers here are close to meaningless and are reported second, always, in every file.**
`VERDICT.md` states the decision-stratum result frozen and unfrozen **in its first three sentences**.

---

## 3. THE REFERENCE — TUNED, NOT NAIVE

Beating a weak benchmark is how this programme has manufactured and then withdrawn results.

| id | allocator | definition |
|---|---|---|
| **N_UNIFORM** | no information | `1/|C(g)|` |
| **B_NAIVE** | the naive allocator named in the brief | mean of the player's prior 5 appeared-game shares, projected |
| **B_TUNED** | **the reference every Q2 cell must beat** | shrunken EWMA of the player's own prior shares, hyperparameters tuned on strictly earlier seasons, projected |

`B_TUNED`:

```
raw_i = (1 - w_i) * EWMA_h(prior shares of i, this season, shift(1)) + w_i * T_g
w_i   = k / (k + n_prior_i)                      # w = 1 exactly at n_prior = 0
T_g   = 1 / n_hat_g                              # n_hat_g = team's trailing mean appeared roster
                                                 #   size, strictly prior, this season; 10.0 default
ŝ_i   = raw_i / Σ_{j∈C(g)} raw_j                 # the projection of §2.3
```

Grid, fixed here: `h ∈ {2, 3, 5, 8, 13, 21, EXPANDING}` × `k ∈ {0, 0.5, 1, 2, 4, 8}` = **42
combinations**. Selected by minimum SSE on the share response over **strictly earlier seasons only**,
re-selected independently for each eval season, on the **same stratum the cell is scored on**. The
selected `(h, k)` per eval season per response is reported in `REFERENCE_TUNING.csv`. **No
hyperparameter is ever chosen using an evaluation row.**

---

## 4. THE ARITHMETIC CEILING — COMPUTED BEFORE ANY FIT, AND IT IS A GATE

`CEILING.md` and `CEILING.csv` are written **before** §5 runs.

Per candidate, on the primary cell's own response and rows, with `d` = the candidate residualised on
the base design and `e` = the base's eval residual:

```
ORACLE ΔR²  =  (d·e)² / ((d·d) * SST)
```

This is the strict upper bound on the ΔR² any linear addition of that column can achieve, with the
coefficient set by hindsight. E1_I0043 established (`DEFECTS.md` D-02) that the D084/D089
variance-share form `(d·d)/SST` **is not a bound**; both are reported and the gate is applied to the
**ORACLE** form. A **family oracle** — the multivariate hindsight R² of `e` on all real candidates
jointly — is reported alongside. `G01_noise` is pushed through the identical path to give the
ceiling statistic's own noise floor.

**Programme benchmarks, frozen here before any of these numbers exist:**

| benchmark | value |
|---|---|
| largest live effect ever measured (D089) | **0.002057** |
| single-cell detection floor (D103, injection-verified) | **0.00102** |
| 132-cell floor (D103, injection-verified) | **0.00235** |

**PREREGISTERED GATE, applied per response, on the DECISION stratum, CLEAN window:**

> **If the family ORACLE ceiling < 0.00102 (the single-cell floor), the fit is NOT RUN for that
> response and the cell is reported CLOSED ON ARITHMETIC.**

Stated plainly: **if the ceiling is below the floor, say so and do not fit.**

---

## 5. THE CELLS

### 5.1 Q1 — is allocation forecastable at all (no gate; these are forecast contrasts)

| cell | contrast | statistic | null |
|---|---|---|---|
| **Q1a** | `B_TUNED` vs `N_UNIFORM` | `R²_of_forecast` difference on identical rows and SST | paired sign-flip, blocks = **team-game** |
| **Q1b** | `B_TUNED` vs `B_NAIVE` | same | same |
| Q1c | `B_NAIVE` vs `N_UNIFORM` | same | same |

### 5.2 Q2 — the incremental candidates

Explicit literal allowlist, length asserted = **6**:

| id | candidate | varies at | why it is here |
|---|---|---|---|
| **A1_min_share_prior** | player's prior EWMA **minutes** share | between players in the team-game | E1_I0034 found minutes forecastable and points harmful; this asks whether the minutes allocation carries the points allocation |
| **A2_fga_share_prior** | player's prior EWMA **attempts** share | between players in the team-game | attempts pay the largest bottom-up penalty (49.6%, E1_I0033); D111 predicts the constraint bites hardest here |
| **A3_starter_rate_prior** | player's prior rate of starting (`shift(1)`, expanding) | between players in the team-game | role, not form |
| **A4_vac_x_own** | (own prior share) × (prior share vacated by established teammates who did not appear) | between players in the team-game | the general form of E1_I0034's absence channel, freed from the absence-only case |
| **A5_opp_defrtg** | opponent prior defensive rating | **constant within the team-game** | the §2.3 annihilation demonstration, on real data |
| **G01_noise** | seeded pseudorandom, row level | row | negative control through the identical path |

Arms, all four run for every cell:

| arm | intercept and base coefficients | projection |
|---|---|---|
| **FROZEN / PROJ** (headline) | **held at the base fit**; only the candidate coefficient estimated, on the base's training residual, against a **train-mean-centred** candidate | yes |
| UNFROZEN / PROJ | all refit | yes |
| FROZEN / RAW | held | no |
| UNFROZEN / RAW | all refit | no |

**Both frozen and unfrozen figures are reported everywhere.** A component in a prior screen scored
+0.0287 at p 0.00005 on rows where it substituted nothing; the freeze is what catches that.

Fit population: **all appeared roster rows** in the training seasons (the projection requires a
forecast for every roster member). Scored on **DECISION stratum eval rows** (headline) and on **all
eval roster rows** (pooled, reported second). A sensitivity fitting on decision rows only is
reported in `NOTES.md`.

`SST` is computed **once**, on the concatenated eval-fold response, and is shared by both arms of
every comparison (**D101**: identical response, row set, SST basis, weighting, base).

---

## 6. NULLS — MATCHED TO THE LEVEL THE CANDIDATE VARIES AT

A within-player null is **structurally blind** to a between-player candidate: measured p = 1.0000 in
0/15 planted configurations elsewhere in this programme, and it killed a real rebound signal.

| id | null | exchangeability tested | valid for |
|---|---|---|---|
| **N_TGSWAP** | permute the candidate **among the players inside the same team-game** | which player in this composition holds which candidate value | A1, A2, A3, A4, G01 — **every between-player candidate** |
| **N_TGBLOCK** | permute the team-game-constant candidate **among team-games on the same date** | which opponent this composition faced | A5 |
| N_WITHIN_PLAYER | cyclic shift inside each player-season | — | **CONTRAST ONLY, never a verdict.** Run so this screen *demonstrates* the blindness on its own candidate rather than citing another screen. |
| N_SIGNFLIP_TG | paired loss-difference sign-flip, blocks = team-game | — | the Q1 forecast contrasts |

`N_TGSWAP` is the null for the between-player family and it is valid for **every** component of that
family (D120), because every component varies between players inside the team-game and nowhere else.
This is **verified by component-wise injection, not asserted and not by shuffled residuals**: an
effect is planted into the **real response** through each component separately and the whole path is
rerun. `n_groups` and `n_blocks` are reported for every null.

Draws: **2,000**, seed **20260808**. Raw, unstandardised, signed draws are saved as `.npz`; absolute
values are never stored, and standardising would erase the null mean irrecoverably. `null_mean` and
`null_sd` are printed beside every p. **A null whose mean has the same sign as, and a material
fraction of, the observed statistic is disclosed as partially absorbing its own effect.**

---

## 7. POWER

* **Block count per cell is reported.** Blocks are team-games. Below six blocks a two-sided
  sign-flip cannot reject at all (`p_min = 2^(1−nb)`); any cell below that is reported as
  UNDECIDABLE, not as null.
* **Injection-verified floors are preferred and every floor is labelled** `injection` or `analytic`.
  The analytic rule `MDE80 = 2.80 × null_sd` is known anti-conservative in this programme by
  1.22×–3.40×; where a simulated curve is available the injection floor is used and the analytic one
  is shown beside it.
* **Type-I calibration** on synthetic no-effect data through the identical path.
* A statistic that is significant but **below** its own 80%-power floor is **NOT ESTABLISHED**
  (D103), however small its p.

---

## 8. STABILITY — SHARE VERSUS LEVEL

A player's *share* may be more persistent than her raw output, because dividing by the team total
strips out pace, opponent and game state. **If share is genuinely more stable, that is a mechanism
worth having even if Q2 is null.**

`STABILITY.csv`, on **identical rows**, in identical `(game_date, game_id)` order, within
`(season, player_id)`:

* pooled lag-`L` autocorrelation, `L = 1..5`, of **share** and of **level**, for each of points,
  minutes, attempts;
* the intraclass correlation (between-player-season variance share) of share and of level;
* both on the DECISION stratum (first) and on all appeared rows (second);
* the **counterweight**, computed in the same file: share and level would have identical
  autocorrelation if team totals were constant, so the gap is bounded by the variance the team total
  contributes. `Var(log Y_g)` and the correlation of `y_i` with `Y_g` are reported so the reader can
  see how much of any gap is arithmetic rather than behavioural.

**This is the one cross-response comparison this screen makes and it is made only on
autocorrelation and ICC — unitless quantities on identical rows.** No ΔR², MAE, skill ratio or
variance share is ever set beside a differently-scaled one.

---

## 9. CONTROLS AND DISCIPLINE

* **Anchors reproduced exactly before any new statistic**, and the run **halts** if any fails:
  D104's home advantage **+0.965090 on 888 games**; `E0_I0016` and `E1_I0018` screen frames at
  **14,852** rows and their inner merge at **14,852**; the D081 decision stratum at **5,673** rows /
  149 players / 708 games and **3,167** rows in 2023–24; D085's `A10_opp_defrtg → y_ppm` ΔR² over
  `refB_ppm` at **0.0014430974149688** and over `refA_ppm` at **0.0015087657892969**, recomputed not
  read; and the from-scratch `n_prior` and `prior5_minutes` reproducing `E1_I0018`'s on **all
  14,852** shared rows.
* **No-op placebo** — the identity permutation through the whole path; deviation reported as
  measured, not rounded.
* **Negative control** — `G01_noise` through the identical path, and a **pseudo-composition
  control** on a disjoint row set.
* **Future-leakage probe** on the base and every candidate, read as a screening flag.
* **DEFECTS.md** records every defect found, including those that change a headline.
* **The result that most weakens the conclusion is stated in the same document as the conclusion.**

---

## 10. DECISION RULE

1. Compute anchors. Any failure halts the run.
2. Compute `STABILITY.csv`. No gate.
3. Compute the decision-stratum census and `CEILING.md`. **Apply the §4 gate.**
4. If the gate closes a response: report **CLOSED ON ARITHMETIC** and **do not fit** it.
5. If the gate opens: run Q1 and Q2, decision stratum first, frozen and unfrozen, PROJ and RAW,
   with matched nulls and injection-verified floors.
6. A cell is **ESTABLISHED** only if it beats its matched null **and** exceeds its own 80%-power
   floor **and** survives the family-wise correction. Anything else is **NOT ESTABLISHED**, which is
   not the same as ABSENT (D108 ruling 4).
7. **A powered honest null is a fully acceptable and valuable outcome.** Do not manufacture a
   survivor.
