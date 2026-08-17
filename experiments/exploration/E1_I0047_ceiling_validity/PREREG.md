# PREREG — E1_I0047_ceiling_validity

**Screen**: is `(d·d)/SST` — the statistic D084 and D089 call "the arithmetic ceiling" — an upper
bound on ΔR², and if not, what is the exposure across the 213 cells the programme killed with it?

Written and hashed **before any statistic in this screen was computed**. Source code and prior
artifacts were read first; that is reading, not measuring. Nothing below was chosen after seeing a
number produced by this screen.

Partition: **2021–2024 only**. 2025/26 is a sealed holdout and is never opened. No file under any
`2025`/`2026` season key is read. Manifests: `row`/`season` usable, `artifact` not.

---

## 0. WHAT WAS READ BEFORE WRITING THIS (provenance of the question)

- `E1_I0043_opponent_defence/CEILING.md`, `DEFECTS.md` (D-01, D-02) — the screen that raised it.
- `E1_I0023_usage_defence_interaction/s03_arithmetic_ceiling.py` — the **explicit** D084/D089 form.
- `E1_I0018_teammate_volume_channel/s04_points.py` — D089's own construction.
- `E0_I0024_reb_ast_characterisation/s04_screen.py` + `rb_base.py` — D097's construction, which is
  **the sole source of every one of the 213 ceiling kills**.
- `E1_I0036_level_artefact_sweep/scripts/s07_census.py` — the census rule that produced the 213.

**Established from source before any measurement, and recorded here so it cannot be back-fitted:**
the census column `ceiling_recorded` is populated for exactly one screen — `E0_I0024` (D097) — from
its column `CEILING_dr2_D089form`. Every other screen in the census passes `ceiling=None`. Therefore
**all 213 CEILING kills are D097 cells and all use one single construction.** This is the fact that
makes the exposure question finite.

---

## 1. THE THREE CONSTRUCTIONS IN USE, NAMED

Let `e` = response residual on the base, `d` = the forecast shift the candidate produces,
`SST` = Σ(y−ȳ)² on the scored rows.

| tag | formula | where it is written |
|---|---|---|
| **C-VARSHARE** | `(d·d)/SST` | `E1_I0023/s03` as `ceiling_D084_form_var_share`; D089's `CEILING_dr2_points` |
| **C-1SD** | `(\|β\|·sd(x)·mean(m̂)/sd(y))²` | `E1_I0023/s03` as `ceiling_1sd_form`; D089's `CEILING_dr2_points_per_sd` |
| **C-RAWSD (D097)** | `(\|β̂\|·sd(x)/sd(y))²` | `E0_I0024/s04` as `CEILING_dr2_D089form` — **the 213** |
| **C-RESID (D097)** | `(\|β̂\|·sd(x⊥)/sd(y))²` | `E0_I0024/s04` as `CEILING_dr2_residualised` |
| **ORACLE** | `(d·e)²/((d·d)·SST)` | `E1_I0023/s03`; `E1_I0043/s04` |

---

## 2. HYPOTHESES, STATED BEFORE MEASUREMENT

- **H1 (algebra).** `ΔR² = (2 d·e − d·d)/SST`. Hence `(d·d)/SST ≥ ΔR²` **iff `d·e ≤ d·d`**, i.e. iff
  `c* := (d·e)/(d·d) ≤ 1`. The exact factor by which the achievable-by-rescaling ceiling exceeds the
  computed one is **`c*²`**.
- **H2 (the sufficient condition).** If `d` is the OLS fitted contribution of the candidate on the
  **same rows, same response, same base** on which ΔR² is scored, then `d·e = d·d` identically, so
  `c* = 1` and C-VARSHARE **equals** ΔR² exactly. It is a bound with zero slack, not a loose bound.
- **H3 (D097 specifically).** C-RESID ≡ ΔR² to machine precision, and
  **C-RAWSD = ΔR² × VIF** where `VIF = (sd(x)/sd(x⊥))² = 1/(1−R²_{x∼base}) ≥ 1`.
  **Collinearity with the base makes C-RAWSD MORE conservative, not less.** If this holds, the
  orthogonality suspicion in the brief is exactly inverted and the 213 are safe by construction.
- **H4 (where it genuinely fails).** `c* ≠ 1` — and can exceed 1 — whenever `d` is *transported*:
  fitted on one scale/response/rowset and scored on another (walk-forward; a ppm coefficient
  multiplied by minutes and scored against points). That is E1_I0043's case and D084/D089's case.

**H3 and H4 are opposed predictions about different screens. Both are falsifiable here.**

---

## 3. ANCHORS — REPRODUCED EXACTLY BEFORE ANY NEW STATISTIC

Preregistered targets, `|new − recorded|` reported to full precision, target `0.000e+00`:

| id | anchor | recorded value | source |
|---|---|---|---|
| A1 | D097 identity: `CEILING_dr2_residualised == dr2` over all 1,286 recorded cells | max abs diff | `E0_I0024/upstream_signals.csv` |
| A2 | D097 identity: `CEILING_dr2_D089form == dr2·(sd_x/sd_xr)²` over all cells | max abs diff | same |
| A3 | D097 cell `DECISION\|y_oreb\|B_COMPLETE\|R08_player_ra_share` `dr2` refitted from the frozen parquet | as recorded | `screen_frame.parquet` |
| A4 | D097 cell `POOLED\|y_oreb\|B_COMPLETE\|R08_player_ra_share` `dr2` = 0.006488 (E1_I0036 reproduced it at 0.0064881160) | as recorded | same |
| A5 | E1_I0023 max negative-control `ceiling_1sd_form` = 4.375669e-03 | as recorded | `E1_I0023/arithmetic_ceiling.csv` |
| A6 | E1_I0023 disclosed floor cell `DECISION/ALL_TIERS/INTERACTION/walk_forward` = 3.979894e-04 | as recorded | same |
| A7 | E1_I0023 D098 headline ceiling `DECISION/T3_high_usage/MAIN_EFFECT/walk_forward` D084-form = 0.01280821 | as recorded | same |
| A8 | E1_I0043 primary-cell ORACLE = 0.01094259 and D084 form = 0.00344222 | as recorded | `E1_I0043/CEILING_MATCHED.csv` |

**If A1–A4 do not reproduce, this screen halts and reports the failure instead of a verdict.**

---

## 4. D101 DECLARATIONS — every ceiling and every ΔR² in this screen

No critical value is compared against a statistic on a different scale. Each computed quantity
carries all five fields.

**Q1 — the 213 exposure audit (no refitting; arithmetic on recorded columns).**
response: as recorded per cell (`y_reb`/`y_oreb`/`y_dreb`/`y_ast`/`y_pts`) ·
row set: D097's own complete-case rows per cell, as recorded in its `n` ·
SST basis: Σ(y−ȳ)² on **those same rows**, unweighted (D069 convention, `rb_base.BaseFit.sst`) ·
weighting: none ·
base: as recorded (`B_COMPLETE` or `B_COMPLETE_PLUS_R10`) ·
fit: **in-sample OLS**, Frisch–Waugh, same rows.

**Q2 — re-measurement (§6).** Same response / rows / SST / weighting / base as Q1 for the
reproduction arm. The clean-window arm re-scores on `season ∈ {2023, 2024}` **and recomputes SST on
those rows** — it is never compared against a 2021–2024 SST. Both arms reported side by side and
never mixed.

**Q3 — detection floors.** `FLOOR_1CELL = 0.00102` and `FLOOR_132 = 0.00235` are D103's
**injection-verified** single-cell and 132-cell floors, and are the exact constants the census used
(`s07_census.py` lines 18–19). They were derived on a player-game in-sample incremental-R² scale,
which is the scale Q1 is on. **Any floor applied to a walk-forward or points-transported statistic
is re-derived on that scale or the comparison is not made.** `BEST_LIVE = 0.002057`.

**Frozen-intercept rule.** Every fit in this screen includes an explicit intercept column and
reports the statistic both with the intercept **frozen at the base fit's value** and **refitted**.
Both figures are published for every re-measured cell.

---

## 5. CLASSIFICATION RULE FOR THE 213 (frozen, first match wins)

For each of the 213, with `C` = `ceiling_recorded`, `R` = `dr2_reported`, `F` = `FLOOR_1CELL`:

- `slack = C / R` (the predicted VIF under H3)
- `understatement_factor U` = the factor by which the true achievable ceiling could exceed `C`.
  Under H3, `U = c*² / slack`. `c*` is **1 by construction** for an in-sample OLS fit on the same
  rows; the screen verifies this rather than assuming it.
- `margin = F / C` (how many times below the single-cell floor the computed ceiling sits)
- `true_ceiling_upper = C × U`
- **`SAFE_BY_MARGIN`** iff `margin ≥ 100`.
- **`SAFE_BY_CONSTRUCTION`** iff `C ≥ R` verified numerically **and** `U ≤ 1`.
- **`AT_RISK`** iff `true_ceiling_upper ≥ F`.
- Ranked by `rank_score = U × (1/margin)` = `U × C / F`, descending.

`SAFE_BY_MARGIN` is reported **before** any expensive work, as the brief requires.

---

## 6. RE-MEASUREMENT RULE (frozen, preregistered, applied without amendment)

A cell is re-measured iff **either**:

- **(a)** `margin < 10` — the computed ceiling is within one decade of the single-cell floor; **or**
- **(b)** it is in the **top 25 of the 213 by `ceiling_recorded`**, which is a deterministic
  selection requiring no threshold and no name matching; **or**
- **(c)** the identity check `C ≥ R` fails for it.

Cap: 30 cells. If the rule selects more than 30, the top 30 by `rank_score` are taken and the
remainder are reported as selected-but-not-run. **A ceiling kill whose margin is ≥ 100× is not
re-measured under any circumstance** — that is the brief's own instruction and it is frozen here.

**NO NAME-BASED SELECTION.** No cell enters or leaves any set in this screen because of a substring
in its candidate, target, base or stratum. Selection is by recorded numeric columns only. The one
place a name appears is the anchor list in §3, where the cell is named to identify a *reproduction
target*, not to select a result.

---

## 7. NULLS AND POWER (applies only to re-measured cells)

- Candidate levels are taken from D097's own recorded `level` column, never inferred from a name.
- Null must permute **within the entity the candidate is (near-)constant in is the BLIND one and is
  excluded**; the matched null permutes across it (E1_I0043 D-05). For an `opp_team_season`
  candidate the matched instrument is `N_ESWAP` (reassign opponent-team-season series within
  season); for a `player_season` candidate it is `N_PSWAP` (reassign player series within season).
  `N_CYCLIC`/within-entity shuffles are computed and reported **as the blind arm**, never as a
  verdict (E1_I0036 D097 re-examination).
- **Null-centre check** is mandatory: `null_mean / real` reported for every arm; an arm whose null
  centre sits at the real effect is declared blind.
- **Component-wise injection**: for every re-measured cell the candidate is decomposed into
  between-entity and within-entity components and a signal is planted in **each** separately;
  an arm is valid only if it has power against every component that carries ≥10% of the variance.
- **Blocks**: block count is published per cell. **Below six blocks no two-sided sign-flip verdict
  is issued** — the cell is reported as `POWER_NOT_ASSESSED`.
- **Signed statistics only.** Every stratum arm of every null is stored raw and unstandardised in
  `nulls/*.npz`. No absolute values are saved.

---

## 8. NOISE-FLOOR CHECK (D-01 verification, independent)

`E1_I0023/NOTES.md` §7 states the pure-noise control returns "up to 3.98e-04". Verified against
`E1_I0023/arithmetic_ceiling.csv` under **three** scopes, all reported:

1. **literal scope** — `is_negative_control & contrast==INTERACTION & fit==walk_forward`;
2. **walk-forward scope** — `is_negative_control & fit==walk_forward` (both contrasts);
3. **whole-table scope** — all `is_negative_control` rows.

Both ceiling forms reported under each scope. The understatement factor is quoted per scope rather
than as one number, because E1_I0043 quoted one and the sentence's literal scope is narrower than
the use it is put to. Whichever way it falls is reported.

Then: the same pattern is searched for **in every screen that wrote a negative control beside a
ceiling**, by scanning artifacts for a negative-control flag column — **not by candidate name**.

---

## 9. WHAT WOULD FALSIFY THE FAVOURABLE OUTCOME

Stated in advance so it cannot be quietly dropped:

- any of the 213 with `C < R`;
- any D097 cell with `c* ≠ 1` at tolerance 1e-9;
- any re-measured cell whose 2023–24 clean-window ΔR² exceeds its own recorded ceiling;
- a counterexample constructed **within D097's own construction** (not merely within the general
  algebra) where realised exceeds computed.

## 10. STANDING CONSTRAINTS

- Write scope: `experiments/exploration/E1_I0047_ceiling_validity/` only. No writes elsewhere. No
  `git` write commands. The shared screen kit is **not modified** and is not imported for writing.
- **Process isolation**: no blanket process kill of any kind. Only PIDs this screen launches and
  records may be signalled, and they are reported.
- No champion is fitted. No production change is enacted. No model is loaded or retrained.
- `SEED = 20260808`.
- Every claim that weakens this screen's own conclusion is published in the same document as the
  conclusion.
