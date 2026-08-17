# PREREG — E1_I0055_shot_selection_recheck

**Written and hashed BEFORE any statistic other than the schema probe (`out/s00.txt`,
which computes no statistic) and BEFORE any fit.**

**E1 IS NON-CLAIMING.** Nothing produced here is a RESULT. It is a LEAD, a downgrade, or it
is dead. No registry entry, no promotion, no production change, no champion.

---

## 0. THE QUESTION

`E1_I0004_shot_selection` carries the programme's last live `KEEP-AS-LEAD`:
**β = +0.7743 (row-level), family-wise p = 0.0002** on a five-zone shot-mix simplex.
`E1_I0051_constraint_sweep` flagged it as the one exposed live lead whose response is a
constrained composition and which was never re-measured against that constraint, and
deliberately did not re-measure it.

**This screen re-measures it.** Killing it is a fully acceptable and, on the sibling prior
(three of four candidates reverse under projection), a likely outcome. Surviving cleanly is
equally acceptable and must then be reported with every counterweight attached.

---

## 1. PARTITION AND ARTIFACT POLICY (binding)

* Seasons **2021, 2022, 2023, 2024 ONLY**. **2025 and 2026 are a SEALED confirmation
  holdout and will never be read, joined, filtered against, counted, described or plotted.**
  Every load is followed immediately by a `# FILTER-POINT` and a printed
  `sorted(season.unique())` and a hard assertion.
* Manifests: `asof_granularity` values `row` and `season` are usable (filtered);
  `artifact` is NOT usable; a MISSING manifest is UNVERIFIABLE and the artifact is not read
  unless the season is the filename.
* Artifacts this screen may read:
  - `data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet` — no manifests exist and
    none are needed: **the season is the filename**, and a shot's zone label is a property of
    that shot's own coordinates.
  - `data/masters/master_player.parquet` — manifest read as a **column value**:
    `asof_granularity == "row"` → usable, filtered to the partition. Used ONLY to build the
    decision stratum (minutes) and for no response quantity.
  - `experiments/exploration/E1_I0004_shot_selection/*` — the screen under re-measurement,
    **read-only**.
  - `experiments/exploration/E1_I0011_split_alpha/baseline/corrected_baseline.py` — code, not
    data, the frozen baseline module.
* `data/zone_maps/*` are **FORBIDDEN** (`asof_granularity == "artifact"`) and will not be
  opened.
* **CLEAN WINDOW.** One clean evaluation window exists: **2023–2024**. 2021 is degenerate and
  2022 depends only on 2021. The primary verdict is on the clean window. The full published
  window 2021–2024 is reported beside every primary cell as the published-window contrast,
  never as the verdict.

## 2. WRITE SCOPE AND PROCESS ISOLATION (binding)

* Writes **only** inside `experiments/exploration/E1_I0055_shot_selection_recheck/`.
* **No `git` write command of any kind.**
* The shared screen kit, the original screen `E1_I0004_shot_selection`, and every production
  file are **not modified**.
* **NO BLANKET PROCESS KILL.** No `Get-Process python | Stop-Process`, no `taskkill`, no
  wildcard kill. Only PIDs this screen launched and recorded may be signalled, and every such
  PID is written to `scripts/_pid_*.txt` and reported in `NOTES.md`.

---

## 3. ANCHORS — REPRODUCED BEFORE ANY NEW STATISTIC

No new statistic is computed until every anchor below has been attempted and its deviation
published, pass or fail. A failure is a headline, not a footnote.

| id | anchor | target | source |
|---|---|---|---|
| **A1** | row-level β, Restricted Area, selection | **+0.7742726671354552** | `analysis_results.json` `familywise.selection["Restricted Area"].real_beta_row` |
| **A2** | row-level β, other four zones | +0.6529896973770617 / +0.5558250299356523 / +0.32472289963558754 / +0.5629840482545649 | same |
| **A3** | cluster-level β, Restricted Area | **+0.9193293906251634** | same, `real_beta_cluster` |
| **A4** | permutation null mean and sd, RA | −0.0004875570814531993 / 0.15473938432791973 | same |
| **A5** | family-wise p (row-level real, 1-sided), five zones | 0.0002 / 0.0024 / 0.0010 / 0.0602 / 0.0002 | `robustness_results.json` `familywise_rowlevel.selection` |
| **A6** | selection analysis rows | 51,473 rows = 10,307 player-games × 5 zones | `build_results.json` |
| **A7** | R², Restricted Area | 0.035209 | `analysis_results.json` |
| **A8** | independent rebuild of `selection_frame.parquet` from the 132,558 raw shots | cell-exact on `share, S1, OS, resid_S1, role_prior_fga` | raw shotcharts |
| **A9** | decision-stratum machinery: `E1_I0051`'s DECISION × CLEAN 2023–24 | **n = 3,167 in 764 team-game blocks** | `E1_I0051_constraint_sweep/VERDICT.md` §3 |

**A8 is the load-bearing anchor**: without an independent rebuild every later number would be
a re-arrangement of the published frame rather than a re-measurement. If A8 fails, the
published frame is used and the failure is reported as this screen's headline defect.

**Halting rule.** If **A1 or A5 does not reproduce**, that is the headline: the screen stops,
`REPRODUCTION.md` reports the non-reproduction, and no projection statistic is computed.

---

## 4. THE CONSTRAINT, AND HOW IT WILL BE ASSERTED

The response is `share_z` = a player-game's share of her own field-goal attempts falling in
zone *z*, over the five zones (`Restricted Area`, `In The Paint (Non-RA)`, `Mid-Range`,
`Corner 3`, `Above the Break 3`; `Backcourt` excluded by the parent screen's n ≥ 200 gate).

**Closure will be ASSERTED NUMERICALLY, not assumed.** For every player-game with all five
zones present, on the full frame and on every analysis row set, this screen reports the
**maximum absolute deviation** of each of:

| id | assertion | expected |
|---|---|---|
| **C1** | Σ_z `share_z` = 1 | 0 to floating point |
| **C2** | Σ_z `S1_z` = 1 | 0 to floating point — this is a *claim to be tested*, not an assumption |
| **C3** | Σ_z `resid_S1_z` = 0 | follows from C1 ∧ C2 |
| **C4** | Σ_z `opp_share_prior_z` = 1 | 0 to floating point |
| **C5** | Σ_z `lg_share_prior_z` = 1 | 0 to floating point |
| **C6** | Σ_z `OS_z` = 0 | follows from C4 ∧ C5 — the `E1_I0051` claim |
| **C7** | the fitted coefficient range | published as 0.325 … 0.774 |
| **C8** | **completeness of the simplex on the analysis rows** — every player-game must carry all five zones | **KNOWN TO FAIL: the probe shows 62 of 10,307 player-games carry only 4 zones** |

The standard is the sibling's: a closure assertion is reported as `max|Σ − target|` over a
stated number of units, and the count of units is printed. C8 is reported as a count and the
cause is diagnosed.

**The violation is in the FIT, not in the data.** If C1–C6 hold, the response and the
regressor both already live in the zero-sum tangent space of the simplex; what breaks closure
is that five *independently fitted* slopes do not agree. The fitted share vector is
`ŝ_z = S1_z + â_z + b̂_z·OS_z` and

    Σ_z ŝ_z − 1  =  Σ_z â_z + Σ_z (b̂_z − b̄)·OS_z

which is identically zero only if all five `b̂_z` are equal. **The magnitude of that violation
will be measured, in units of the budget (which is exactly 1, with zero pre-tip uncertainty),
and stated beside the sibling minutes screen's 13.09 minutes on a budget of 200 (6.5 %).**

---

## 5. THE PROJECTION — DEFINED BEFORE IT IS APPLIED

Two projections are preregistered. **PROJ_TANGENT is primary** because it is the direct
analogue of the sibling minutes screen's `PROJ_BUDGET`: a post-hoc rescale of the forecast
onto the budget.

**PROJ_TANGENT (primary).** For each player-game *g* with all five zones present, the fitted
increment vector `d_g = (ŷ_{g,z})_z` is replaced by its Euclidean projection onto the
zero-sum subspace:

    d^PROJ_{g,z} = d_{g,z} − (1/5)·Σ_w d_{g,w}

so that `Σ_z (S1 + d^PROJ) = 1` exactly. The reported per-zone effect is

    β^PROJ_z = cov(d^PROJ_{·,z}, OS_{·,z}) / var(OS_{·,z})

i.e. the slope on that zone's own regressor of the *closure-legal* fitted increment.
**Note, stated in advance:** because Σ_z OS_z = 0 exactly, a genuinely common slope
(`b_z ≡ b` for all z) is invariant under this projection — the projection does **not**
mechanically annihilate a real common effect. It removes only the part of the per-zone slope
spread that cannot be a share increment.

**PROJ_COMMON (secondary).** The projection of the RAW fit onto the closure-legal linear model
class: the single common slope `b` minimising Σ_g Σ_z (y_{g,z} − a_z − b·OS_{g,z})² with
zone-specific intercepts. This is the *only* linear model in `OS` whose fitted share vector
closes for every input. `β^PROJ_COMMON` is one number, reported for the family.

**Applied identically everywhere.** The projection map is applied to (i) the real data,
(ii) every null draw, (iii) every arm, (iv) every injection, (v) every bootstrap resample, by
calling the same function. A no-op placebo (projecting a fit whose five slopes are already
equal by construction) must return deviation exactly `0.000e+00`; it is run and published.

**Both arms reported beside each other.** Every cell in `VERDICT.md` and `FINDINGS.json`
carries `beta_RAW` and `beta_PROJ` on the same row, **and the sign of each**. A sign flip is
the signature and is reported before any magnitude.

---

## 6. ARMS

| axis | levels |
|---|---|
| projection | `RAW` · `PROJ_TANGENT` · (`PROJ_COMMON`, family-level) |
| intercept | **`FROZEN`** — response is the offset `share_z − S1_z`, the frozen own-prior baseline, exactly as published; nothing about the base is fitted. **`UNFROZEN`** — response is `share_z`, base regressors are fitted OLS, candidate `OS_z` appended; statistic is the coefficient on `OS_z`. |
| row set | **`DECISION × CLEAN`** (primary) · `ALL × CLEAN` · `DECISION × PUBLISHED` · `ALL × PUBLISHED` (the published 2021–2024 window) |
| zone | all five, always. No zone is dropped, ever. |

**Decision stratum (fixed here, D081's definition as `E1_I0023`/`E1_I0043`/`E1_I0046`/`E1_I0051`
used it):** `n_prior ≥ 8` AND `prior5_minutes ≥ 24`, where `n_prior` is the player's count of
prior **appeared** games in the season and `prior5_minutes` is the mean of the player's
minutes over her previous five appeared games (`shift(1).rolling(5, min_periods=1).mean()`),
both built from `master_player` restricted to the partition. **The intersection of the
decision stratum with this screen's shot frame is reported BEFORE any effect size.**

---

## 7. NULLS

The candidate `OS_z` varies at the level **opponent-team × season × game** (it is an expanding
mean over the opponent's strictly prior games), and its five-zone vector is a unit.

| id | construction | level | why |
|---|---|---|---|
| **N_TSSWAP** | permute opponent-team labels within season across the 48 opponent-team-seasons; the whole five-zone vector travels | opponent-team-season | **the published null** — reproduced so this screen's numbers sit beside the published ones |
| **N_OPPGAME** | permute the opponent-game five-zone allowance vectors across opponent-games within season | opponent-team-game | **matched to the level the candidate actually varies at.** N_TSSWAP is blind to the within-team-season component of `OS`, which the published row-level β uses. |
| **N_BLIND** | permute `OS` within player across that player's own games | player | **a deliberately blind null** for a between-opponent candidate. Expected to be arbitrarily wrong in whichever direction its own centre falls. |

**Controls.**
* `G01_noise` — a random zero-sum five-vector assigned at the opponent-game level. Must be null.
* `G02_TGCONST` — a genuinely **team-game-constant** candidate, the same scalar broadcast to
  all five zones. Under closure it **cannot move an allocation by arithmetic**; the projection
  must attenuate it to zero. Run as a control that cannot fail, reported as such.
* `G03_NOOP` — the identity projection placebo; deviation must be exactly `0.000e+00`.

**Required checks, all preregistered:**
1. **NULL-CENTRE CHECK.** For every null used for a verdict, the **mean signed t over draws
   must be ≈ 0**. A null whose centre is displaced is defective and its cells are not used.
2. **COMPONENT-WISE INJECTION.** A known per-zone effect is injected into the response, one
   zone at a time and jointly, and the arm must recover it with the right sign and
   approximately the right magnitude, **in both the RAW and the PROJ arm**. A null that cannot
   see an injected component is blind for that component.
3. **BLINDNESS AUDIT, SEPARATE FROM TYPE-I.** A Type-I audit does not subsume a blindness
   audit. Both are run. A cell may have a nominal Type-I and still sit at an absurd |t| on the
   real response.
4. **TYPE-I, CENTRED.** Synthetic data with no effect (the five-zone share vector permuted
   *within* the player-game so closure is preserved exactly). Required: rejection rate ≈ 0.05
   **AND mean signed t ≈ 0**. A correct rejection rate on a displaced generator is a correct
   measurement of a defective generator and is reported as such if found.
5. **FAMILY-WISE SINGLE-CELL DOMINANCE.** The max-z family-wise bar is built from **one shared
   draw stream** so cross-zone correlation survives. The **fraction of draws in which each zone
   supplies the maximum is published.** If one cell supplies the bar in > 90 % of draws, that
   is stated in `VERDICT.md`, not buried.

**Storage.** Every null stores **signed, raw, unstandardised draws** with full stratum keys
(`arm`, `rowset`, `frozen`, `zone`, `null`, `draw`) as `.npz` under `raw/`.

---

## 8. DEFLATING EXPLANATIONS — CHECKED BEFORE ANYTHING IS SAID TO SURVIVE

| id | question | test |
|---|---|---|
| **X1 — volume proxy** | do players who shoot more simply have more extreme zone shares? | trailing volume (`role_prior_fga` = EWMA₀.₃₀ of prior FGA/game, prior-only) is put **in the base from the start** in the UNFROZEN arm, together with realised `fga` and `1/fga`. Also reported: corr(role, max_z|share − lg_share|), and var(share_z) by volume bin. |
| **X2 — team-game-constant in disguise** | is the effect carried by a quantity constant within the team-game, which cannot move an allocation? | `OS_z`'s within-team-game across-zone variation is measured and reported as a fraction of its total variation; `G02_TGCONST` is run as the arithmetic control. |
| **X3 — reference completeness** | is the reference complete across all rows? | base ladder, each rung reported with the shrinkage factor: **B0** `[1]` (pure offset) → **B1** `[1, S1]` → **B2** `[1, S1, S2]` → **B3** `[1, S1, S2, lg_share_prior, role_prior_fga, log fga]` → **B4** `+ shooting-team prior zone share`. A sibling screen's effects shrank 2.2×–8.3× when one missing column was added; the same ladder is run here. |
| **X4 — "all five zones positive" is not evidence** | | under a single common slope `b > 0` on a closed regressor, **all five per-zone slopes are positive by construction**. The published "all five zones are positive, therefore this is a general shot-location effect" is therefore checked against the common-slope null, not asserted. |
| **X5 — the published null is blind to the reported statistic's variation** | | the published β is row-level; the published null replaces `x` by its team-season mean. The two are not like-for-like. `N_OPPGAME` supplies the matched null and both are reported. |

---

## 9. FLOORS — MEASURED HERE, NOT QUOTED

**The programme's published constants are `NOT_COMPARABLE` to this screen's response and will
not be used as a bar.** Per `E1_I0049`'s corrected reference card:
`0.00102` and `0.00235` are ΔR² on **points per minute** (n = 5,673); `0.002057` is an
in-sample transported **ceiling** with `c* = 1.359` — not an effect and not a bound;
`0.0023492` is a walk-forward ΔR² on **points**, n = 4,517.
This screen's response is a **per-zone share residual** and its statistic is an **OLS slope**.
Different response, different row set, different SST basis, different statistic family →
`NOT_COMPARABLE` under D101. Stated in `VERDICT.md`.

**This screen measures its own floors**, all three kinds, on its own row set:
1. **analytic** — `t_crit · sd(null)` at 80 % power from each null's own draw sd, `K = 1` and
   `K = 5` (the five-zone family);
2. **injection-verified** — the smallest injected per-zone effect recovered at 80 % power over
   200 injections, confirming the analytic floor is not a fiction;
3. **block bootstrap** — 1,000 resamples of **opponent-game blocks** (the candidate's level),
   reporting `|obs| ÷ floor`.

A cell is `ESTABLISHED` only if `|obs| ÷ floor ≥ 1` on the **bootstrap** floor as well as
clearing its family-wise bar. If the permutation null and the bootstrap disagree, **both are
stated** and the weaker governs.

---

## 10. D101 — EVERY NUMBER CARRIES ITS DENOMINATOR

Every number in `FINDINGS.json` and every table cell in `VERDICT.md` carries: **response ·
row set (with n) · SST basis · weighting · base · fit kind · statistic family · null · draws**.
A number without its denominator is not quotable and will be marked `NOT_COMPARABLE`.

Default conventions, fixed here: **plain unweighted OLS**; `R² = 1 − SSE/SST` with **SST about
the unweighted mean of the response on the scored rows** (D069); **no weighting anywhere**;
attempt-weighted variants, where run, carry weighted SST about the weighted mean and are
labelled.

---

## 11. NO NAME-BASED SELECTION

Zones are enumerated from a fixed literal list fixed in this preregistration. Columns are
selected by exact name from an enumerated list. **No substring matching, no regex column
selection, no `startswith`/`contains` filter selects any candidate, zone, row set or cell
anywhere in this screen.** Six findings in this programme have died to substring matching.

---

## 12. THE VERDICT RULE — FIXED BEFORE THE MEASUREMENT

The lead `E1_I0004_shot_selection` selection channel is declared:

* **SURVIVES-PROJECTION** iff, on **DECISION × CLEAN, FROZEN, PROJ_TANGENT**, the Restricted
  Area cell (a) keeps the published **positive** sign, (b) has family-wise one-sided
  p ≤ 0.05 under **N_OPPGAME** (the matched null), and (c) has `|obs| ÷ bootstrap floor ≥ 1`.
* **DOWNGRADED** iff the sign is kept and (b) or (c) fails.
* **KILLED-BY-PROJECTION** iff the sign reverses on that cell.
* **NOT-RE-MEASURED** iff an anchor in §3 fails the halting rule.

The rule is applied mechanically to whatever the numbers say. Every other row set, arm and
zone is reported beside the primary, including every one that contradicts it. **The result
that most weakens this screen's own conclusion appears in the same document as the
conclusion, in `VERDICT.md`, above the fold.**

**No production change will be proposed. No champion will be fitted. No repair will be
enacted. Nothing in `E1_I0004_shot_selection` will be edited.**

---

## 13. DELIVERABLES

`PREREG.md` + `PREREG.sha256` · `REPRODUCTION.md` · `CLOSURE.md` · `VERDICT.md` ·
`FINDINGS.json` · `NOTES.md` · `DEFECTS.md` (this screen's own) · `raw/*.npz` (signed raw
unstandardised draws with full stratum keys) · `scripts/` · `out/` run logs.

## 14. SEEDS

`SEED = 20260809`. Draw counts: nulls **5,000** where the published screen used 5,000 and
**2,000** for the auxiliary nulls; bootstrap **1,000**; injections **200**; Type-I **1,000**.
Every count is fixed here and will not be raised after seeing a p-value.
