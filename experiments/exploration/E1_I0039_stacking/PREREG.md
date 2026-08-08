# PREREGISTRATION — E1_I0039_stacking

**Screen.** Three separately validated improvements have never been measured together. Do they
compose — additively, sub-additively, or destructively — and how much of whatever they produce
reaches the population anyone would bet on?

| id | component | source | published claim | published row set |
|---|---|---|---|---|
| **A** | cold-start tiering | D092, **retargeted by D102** | pooled points skill −0.22% → +3.51% | `fallback_level == 2` |
| **B** | fallback routing to a tuned simple estimator | D094 | points MAE 4.107, +2.85% over champion | champion's `is_fallback` |
| **C** | minutes redistribution above a threshold | D116 | minutes MAE **+1.82%** (p 0.0003) | ≥25 min freed by a pre-game absence |

**Status when this file is hashed.** `s02` (anchors + row overlap) and `s03` (join/coverage probe)
have run. **No outcome statistic and no cell below has been evaluated.** Every number quoted in
this file is a count, a coverage fraction or a reproduced prior-screen anchor. Section 9 discloses
exactly what those two steps looked at.

**No production change is enacted.** All three components remain unauthorised and this screen
requests no authorisation. The champion's stored forecasts are scored, never refitted.

---

## 0. Anchors — reproduced ON BYTES before any new statistic (`out/s02.txt`)

Fourteen, all EXACT (|Δ| = 0.000e+00):

| # | source | published | reproduced |
|---|---|---|---|
| A1 | D076 / D092 tier-A appeared player-games 2022–2024 | 13,879 | 13,879 |
| A2 | D092 champion fallback rows (points) | 1,061 | 1,061 |
| A3 | D092 fallback-row points skill | −0.1863 | −0.1863 |
| A4a | D109 common scored row set | 13,808 | 13,808 |
| A4b | D109 decision stratum | 5,107 | 5,107 |
| A5a | D102 `fallback_level == 2` routed rows | 947 | 947 |
| A5b | D109 routed rows inside the decision stratum | 0 | 0 |
| A5c | D109 max `n_prior` among routed rows | 5 | 5 |
| A6a | E1_I0034 RSP-W2 remaining-player rows | 8,118 | 8,118 |
| A6b | E1_I0034 RSP-W2 team-game blocks | 888 | 888 |
| A6c | D116 ≥25-min-freed rows | 2,475 | 2,475 |
| A6d | D116 ≥25-min-freed team-games | 282 | 282 |
| A7a | E1_I0034 RSP-W1 remaining-player rows | 11,721 | 11,721 |
| A7b | E1_I0034 RSP-W1 team-game blocks | 1,284 | 1,284 |

**A8, declared now and asserted before the lattice runs:** E1_I0034's P04 minutes cell reproduced
on its own row set — `ΔMAE = +0.09269264623364977`, `MAE(M0′) = 5.101386713527127`, n = 2,475,
282 blocks. If A8 does not reproduce to |Δ| < 1e-6, **the screen halts and reports a machinery
failure instead of a finding.**

**A correction I am recording rather than smoothing.** My first draft anchored `_tg_frame` to
E1_I0033's 1,392 RS1 team-games and got 1,284. That was *my* error: 1,392 counts RS1 team-games in
`master_team`, whereas `_tg_frame` carries only team-games containing an established player.
Retargeted to 1,284/11,721, which is E1_I0034's own published RSP-W1 pair.

---

## 1. Partition

**Exploration is 2021–2024 ONLY. 2025 and 2026 are a sealed confirmation holdout and are never
opened.** A value-level partition guard runs after every load and every filter and raises on any
sealed season. Receipts in `_s02.json`.

Manifests, per the programme's rule (`row`/`season` granularity usable, `artifact` NOT usable as a
feature source, MISSING = UNVERIFIABLE and may back no number):

| artefact | granularity | use here |
|---|---|---|
| `E1_I0034/_player_frame.parquet`, `_rem_frame.parquet`, `_tg_frame.parquet` | derived from `row`-granularity masters | row universe, absence construction |
| `E1_I0020/tier_frame.parquet` | derived from `row`-granularity masters | component A's depth-rank / draft-slot inputs |
| `E1_I0032/_work.parquet` | derived from `row`-granularity masters | component B's tuned estimator, imported not refitted |
| `cbs_v15_player_oof_v5` champion forecasts | `artifact` | **NOT a feature source** — stored forecasts scored as-is |
| `data/injury_capture/injury_log.csv`, `data/injury_history/injury_history.csv` | — | **UNVERIFIABLE — REFUSED**, back no number |

**CONDITIONING DECLARED.** Because both pre-game absence sources are UNVERIFIABLE, component C's
absence indicator is **REALISED**. Every cell containing C is an **ORACLE-ON-ABSENCE CEILING** and
carries `ORACLEABS` in its cell id. A ceiling that is empty closes the question; a ceiling that is
large says only that the value is conditional on knowing the absence.

---

## 2. THE COMMON ROW SET — and why the published gains cannot simply be added

**D101 is the single most likely way this screen goes wrong.** A's published gain is on A's rows,
B's on B's, C's on C's. Those are three different denominators, three different SST bases and three
different row sets. **They cannot be added.** Everything below is re-measured on ONE row set.

**U** = the champion's scored, **regular-season**, **appeared** player-games in **2023–2024**.

```
scored seasons W2 (2023-2024)   15,252
  + regular season only         14,293      <- see below
  + appeared == 1                9,022
  + finite y / champ            9,022      <- U, 960 team-games
DECISION stratum on U            3,158      (n_prior >= 8 AND trailing-5 minutes >= 24)
```

**Why W2 and not 2022–2024.** E1_I0034's RSP-W2 is the primary window for every D116 number,
because C's walk-forward increment needs a strictly earlier *scored* season and the champion's 2021
fold is declared degenerate. Keeping every lattice cell on W2 keeps A, B and C on **identical rows,
identical response, identical SST basis, identical weighting and identical base** — the D101 rule —
at the cost of a third of the data. **W1 (2022–2024) is a declared secondary** for the three single
components and the triple, and the direction it moves each result will be stated.

**Why regular season only, and a D087 catch.** The completeness assertion on the team-game reference
fired: `_tg_frame` covered 888 of 1,044 W2 team-games. The 156 missing ones were **all playoff
team-games**, some with 12 established players and up to 90.5 freed minutes — **not vacuous**.
Silently mixing them in would have extended D116's row set without licence. U is restricted to
regular season, the reference is **rebuilt complete** from the full champion candidate frame using
E1_I0034's own definition, and the rebuild is asserted to agree with the inherited frame to
1.42e-14 (floating-point summation order) on all four fields, with the 72 remaining rebuild-only
team-games asserted to have `n_elig == 0` and `freed == 0` **by construction**.

**Consequence to be stated with every number.** The decision stratum here is n = 3,158, the W2
regular-season restriction of the programme's 5,111–5,673. It is not the same n and is not
comparable to a stratum figure quoted on 2022–2024.

---

## 3. THE ROW OVERLAP — run FIRST, and it determines how much of the rest is worth running

`ROW_OVERLAP.csv`, on U:

| set | n | % of U | in DECISION | % of set in DECISION |
|---|---:|---:|---:|---:|
| A cold-start (`fallback_level == 2`) | 632 | 7.01% | **0** | 0.00% |
| B fallback routing (`is_fallback`) | 945 | 10.47% | **0** | 0.00% |
| C redistribution (freed ≥ 25 min) | 2,533 | 28.08% | **1,051** | 41.49% |
| **A ∩ B** | **632** | 7.01% | 0 | — |
| **A ∩ C** | **48** | 0.53% | 0 | — |
| **B ∩ C** | **63** | 0.70% | 0 | — |
| A ∩ B ∩ C | 48 | 0.53% | 0 | — |
| U | 9,022 | 100% | 3,158 | 35.00% |

**Two different answers, and they must not be blurred together.**

1. **A is a STRICT SUBSET of B.** `A \ B` is empty; `B \ A` is 313 rows, all `fallback_level == 3`.
   Jaccard 0.669. A and B are **not independent** — they are two different *replacements* proposed
   for overlapping rows, and the A+B question is **redundancy**, which must be measured
   empirically.
2. **A and C, and B and C, are near-disjoint** — 48 and 63 rows, 0.53% and 0.70% of U. This is by
   construction, not coincidence: E1_I0034's REM requires **≥3 strictly-prior same-season
   appearances** and the champion's fallback flag fires **below 3**. For these pairs the stacking
   question is **arithmetic rather than empirical**, and the empirical work is a *check on that
   arithmetic* rather than a search for an interaction.
3. **Zero A rows and zero B rows are in the decision stratum.** Median `n_prior` is 2 for A and 1
   for B; the stratum requires 8. This reproduces D109's central sentence on a different window.
   **Only C reaches the betting population.**

---

## 4. Column allowlists — NO NAME-BASED SELECTION ANYWHERE

Every column set is written out in full, resolved against the frame, printed, and its length
asserted. Five findings in this programme died to substring matching.

* `PLAYER_KEEP` — 23 columns, asserted.
* `TIER_KEEP` — 8 columns, asserted.
* `WORK_KEEP` — 14 columns, asserted; `n_prior`/`min5` explicitly renamed to `i32_*` and the merge
  asserted to produce **no `_x`/`_y` suffix**, so a silent column collision cannot occur.
* Champion forecast columns are an explicit `{response → column}` dict:
  `{"minutes": "min_hat", "pts": "pts_hat"}`. Two entries, asserted.
* Merge keys are coerced to `str` on **both** sides and the match rate asserted at 1.0000
  (9,022/9,022) — a merge on mismatched dtypes loses rows without raising.

**D087 coverage, asserted on the rows each component actually treats:**
`e_full_*` (B's estimator) 1.0000 on U, on A, on B and on C. `depth_bucket`/`draft_bucket` (A's
inputs) **0.9984 on A** — one row of 632 lacks them and falls back to the league term alone; this
is declared, not hidden, and the cell's n is reported with and without it.

---

## 5. RESPONSES — and the stage boundary D116 drew

**Two responses, measured separately and NEVER compared to each other** (D101: different responses
are never comparable; this category error has been made repeatedly in this programme).

* **MINUTES** — the stage at which D116 says redistribution helps (+1.82%).
* **POINTS** — the stage at which D116 says **the same signal is HARMFUL** (−1.17%, p 0.0008).

**A naive stack that pushed C through to points would destroy value, and this screen is built to
show that rather than to avoid it.** C is therefore measured on **both** responses in the full
lattice. The preregistered expectation is that C's points cells are **negative**, and if they come
back positive that is a result against D116 and will be reported as one.

**The 30-minute threshold.** D116 found that below roughly 30 minutes freed the rotation absorbs
the absence and nothing should be applied. C's switch is `freed_minutes ≥ 25`, D116's own measured
stratum. A declared secondary at `≥ 30` and a declared **negative stratum at `freed = 0`** are run;
the `freed = 0` cells are where a vacuous gain would show up.

---

## 6. THE COMPONENTS AS FORECAST TRANSFORMS — identity outside their own rows

Base **M0** for every response: **champion forecast + a walk-forward intercept**, fitted on
strictly earlier seasons. **An intercept is held in BOTH arms of every comparison.** E1_I0032
documented a HIGH defect where fitting `[1, x]` against a bare champion smuggled in a walk-forward
intercept recalibration and returned a number thirty times an arithmetic ceiling with the wrong
sign. That defect is designed out here rather than guarded against.

* **A — cold-start tiering.** On `fallback_level == 2`:
  `ŷ = λ(n)·own_running_mean + (1−λ(n))·(league + depth-rank deviation + draft-slot deviation)`,
  `λ(n) = n/(n+2)`. League level and both deviations are fitted on **strictly earlier seasons
  only**. **Listed position is NOT included** — D092 ruling 2 dropped it (p 0.783, permutation null
  0.1996). Identity elsewhere.
* **B — fallback routing.** On `is_fallback`: replace with the **tuned simple estimator**
  (`e_full_*`), imported from E1_I0032, which imports E1_I0027's CANON grid, which is D094's tuned
  configuration. **Not refitted here.** Identity elsewhere.
* **C — minutes redistribution.** On rows that are **established** AND in a team-game with
  `freed_minutes ≥ 25`: add a walk-forward OLS increment on `[u_i, u_i·z_i]` over M0, where
  `u_i = FREED_g / |REM_g|` is the **even** allocation term and `z_i` is the absence-blind
  within-team-game z-score of the player's trailing-5. Identical construction to E1_I0034's P04.
  Identically **zero** on non-established rows and on `freed < 25`.

**COMPOSITION RULE WHEN A AND B COLLIDE, fixed now.** A ⊂ B. In the `AB` and `ABC` cells,
**A takes precedence on `fallback_level == 2` and B covers `fallback_level == 3`.** A declared
sensitivity runs **B-wins-everywhere** (i.e. A contributes nothing), and the difference is reported.

**ORDER.** C is applied on top of A/B. Because A/B and C are near-disjoint the order should be
immaterial; **the reverse order is run on the ABC cell and the difference reported**, rather than
asserted to be zero.

---

## 7. THE LATTICE — 8 arms × 2 responses × 2 strata, fixed

Arms: `{}` (M0 base), `A`, `B`, `C`, `AB`, `AC`, `BC`, `ABC`.
Responses: `minutes`, `pts`. Strata: `POOLED` (U, n=9,022), `DECISION` (n=3,158).
Statistic: `ΔMAE = MAE(M0) − MAE(arm)`, positive = better; `ΔR²` on a **common SST** per
(response, stratum) reported beside it. **28 evaluated cells** (7 arms × 2 responses × 2 strata).

**Additivity test.** For every pair and the triple, `sum-of-parts / whole` is computed and reported.
Additive ≈ 1.0; sub-additive > 1.0; interference means a pair below either part alone.

---

## 8. NULLS AND POWER

**Null (D115).** Paired **block sign-flip at TEAM-GAME**, 20,000 draws, seed 20260815, on the
per-row loss difference. C's treatment is a **team-game** property so all rows of a team-game share
it and a row-level flip would be **anticonservative**; A and B vary at player-game level, for which
a team-game block is **conservative rather than wrong**. On a common row set mixing both levels the
coarser block is the only construction valid for every cell. **`null_mean` is published beside the
observed statistic for EVERY cell** — a null mean exceeding the observed statistic means the null
absorbed the effect (D114's absorption tell).

**Power (D103 / D113 / D116).** Two floors are printed for every cell and **every number is labelled
with which floor backs it**:
* `MDE80_analytic = 2.80 × null_sd` — **the programme's analytic rule, under active suspicion of
  being anti-conservative by 1.2×–3.4×** (D113/D116, partially confirmed, audit still running).
  Never quoted alone.
* `MDE80_injection` — from **component-wise injection run on this screen's own machinery**: a
  known ΔMAE shift is planted through the identical code path at 0 (must NOT detect), 0.5×, 1×, 2×
  and 4× the cell's own null sd, and the recovery reported. **NOT shuffled residuals** — E1_I0034
  confirmed that construction systematically attenuates the recovered effect (0.024 → −0.001 at 2
  null sd). Type-I calibration over 400 synthetic no-effect datasets, target ≈ 0.05.

**A null that cannot recover a planted signal carries no verdict and is reported UNINFORMATIVE, not
as evidence of absence.** Where MDE80 exceeds the observed effect the verdict is **NOT ESTABLISHED**,
never "no effect".

---

## 9. CONTROLS — including the one that killed a finding on this programme last week

* **VACUOUS CONTROL (E1_I0034's own trap).** For every component, the gain is **split by treated
  and untreated rows** and both are reported. E1_I0034 found an apparent gain whose entire effect
  came from rows where the treatment term was identically zero. C's nominal row set contains 58
  non-established rows inside `freed ≥ 25` where its term **is** identically zero; those rows are a
  built-in vacuous control and are reported separately.
* **NO-OP PLACEBO.** An identity transform pushed through each statistic function must reproduce
  the real number with deviation **exactly 0.0**.
* **RANDOM-TARGET CONTROL.** Each component's treatment is reassigned to a random row set of the
  same size and the arm re-measured. D092's equivalent returned +0.0028 against a real +0.0348.
* **NEGATIVE STRATUM.** Every C cell is re-run on `freed = 0`, where there is nothing to
  redistribute. A material gain there is a machinery defect, not a finding.
* **NO RETROSPECTIVE BASELINE.** Every fitted quantity (A's league/depth/draft deviations, C's OLS
  slopes, the walk-forward intercept) is fitted on **strictly earlier seasons only**; the trailing-5
  baselines are inherited from E1_I0034, whose build asserts the first row of every player-season
  block is NaN. Six instances of this defect have been found in this programme, one hidden inside
  inference machinery.
* **D087.** Coverage counts asserted on the cell row set, not assumed from the build (s4 above).

---

## 10. WHAT s02 AND s03 LOOKED AT BEFORE THIS FILE WAS HASHED

Full disclosure, because s7's composition rule was chosen partly in response to these:

1. `s02` — the 14 anchors; the D087 completeness failure that produced the regular-season
   restriction; the row-overlap table in s3 above; the fallback_level composition on U
   (0 → 8,077, 2 → 632, 3 → 313); and the `n_prior` / trailing-5 medians per component.
   **The finding that A ⊂ B came from here and is why s6 needed an explicit precedence rule.**
2. `s03` — join and coverage counts only. `e_full_*` coverage 1.0000 on U and on all three treated
   sets; `depth_bucket`/`draft_bucket` 0.9984 on A and 0.7376 on B (which is why A's structural
   placeholder is **not** extended to B's extra 313 rows); E1_I0032's `n_prior` agreeing with the
   champion's `n_prior_games` on 7,981 of 8,765 shared rows at corr 0.99952, and the two DECISION
   definitions agreeing on 0.9991 of U (3,164 vs 3,158); and the count `established ∧ freed ≥ 25`
   = **2,475**, which is D116's own row set reproduced from a different direction.

**No outcome statistic was computed in either step.** No `y` was compared to any `ŷ` anywhere
before this hash.

---

## 11. DECISION RULES, fixed now

* **DR1.** An arm is **DECIDED-POSITIVE** on a cell if `ΔMAE > 0`, `p < 0.05` and
  `ΔMAE > MDE80_injection`; **DECIDED-NEGATIVE** under the same conditions with `ΔMAE < 0`;
  otherwise **NOT ESTABLISHED**, with both floors quoted.
* **DR2.** If the negative stratum (`freed = 0`) or the random-target control returns a gain
  exceeding its own MDE80, **every cell containing that component is withdrawn** and the screen
  reports a machinery defect instead of a finding.
* **DR3.** If the vacuous split shows a component's gain concentrated on rows where its term is
  identically zero, that component's verdict is **WITHDRAWN** on that response.
* **DR4.** **The headline is the weakest of the pooled and decision-stratum readings, not the
  strongest**, and the decision-stratum number is printed beside the pooled one everywhere, in
  every document, without exception.
* **DR5.** Any cell added after this hash is reported as ADDED with the direction it moved the
  result; any cell dropped is reported as DROPPED with the reason.
* **DR6.** **"They don't stack" is an acceptable and complete answer.** No champion is fitted, no
  component is selected on its measured sign, and nothing here is proposed for production.

---

*Nothing below this line was known when this file was hashed.*
