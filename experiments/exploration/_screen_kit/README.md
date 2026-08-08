# `_screen_kit` — shared, tested guard rails for E0/E1 exploration screens

One module (`screenkit.py`), one test file (`TESTS.py`), one template (`SCREEN_TEMPLATE.py`).
No config framework, no CLI, no plugin system. Standard library + numpy + pandas only
(**scipy is not installed in this environment** — do not import it).

---

## Why this exists

There is no shared library for exploration screens in this program. Every screen is a
self-contained directory that re-implements its own statistics from scratch. The measured
consequence is that **the same four errors kept being rediscovered, each time by a different
screen, at full cost**. This kit makes all four hard to get wrong *by default* — in **future**
screens.

**It does not retrofit anything.** See "Scope boundary" at the bottom.

---

## Quick start

```python
import sys, os
sys.path.insert(0, r"...\experiments\exploration\_screen_kit")
import screenkit as sk

sk.check_manifest(parquet_path, verbose=True)         # 1. before you trust an input
sk.assert_partition(df, verbose=True)                 # 2. after every load and every filter

lvl = sk.detect_grouping_level(df, "my_feature", verbose=True)   # 3. before choosing a null
if lvl["status"] == sk.STATUS_NO_COARSER_LEVEL:       # 3b. READ THE STATUS, not just the level
    print(lvl["warning"])                             #     -> no coarser level exists; see below
    ...

cmp = sk.null_width_comparison(stat_fn, df, lvl["recommended_key_cols"],
                               400, seed=1, feature_col="my_feature",
                               block_col="season", verbose=True)  # 4. verdict + inflation factor
```

Comparing **two forecasts** rather than testing one feature? That is the other half of the kit:

```python
sk.var_share_between(df, "my_feature", "game_id")     # which permutation scheme is the real null?
sk.paired_forecast_comparison(y, yhat_a, yhat_b, groups=df["game_id"],
                              n_draws=2000, seed=1, verbose=True)   # clustered paired sign-flip
```

Then copy `SCREEN_TEMPLATE.py` into your screen directory and replace the DEMO DATA block.
The template runs end-to-end on synthetic data as shipped, so you can watch the whole pipeline
work before touching real data.

Run the tests any time you change `screenkit.py`:

```
python TESTS.py          # exit 0 = all pass, 1 = failure
```

---

## The four traps, with the measured evidence

These are not ceremony. Each guard exists because the failure it prevents actually happened,
repeatedly, and cost a full screen each time.

### Trap 1 — the wrong null (rediscovered **four** times)

Team- and game-aggregate features were given a naive **row-level** permutation null, which is
anticonservative.

- A feature with only **12 distinct values per season**, shared across **16,345 rows**, carried a
  nominally significant `t = +2.22` while sitting **inside its own correct null**.
- Row-level nulls measured **1.00–3.82x too narrow** in one screen and **1.60x too narrow** in
  another — where the feature took **one value per game** (774 distinct values across 10,167 rows
  from 48 team-season series), so a published family-wise `p = 0.003` was computed against the
  wrong null entirely.

**Critical corollary, confirmed three separate times: cluster-robust standard errors are NOT a
substitute.** Clustering moved `t` the **wrong way** (up, anticonservatively) in two screens, and
landed nowhere near the permutation width in a third. Do not report a cluster-robust `t` as an
alternative to a correct-level permutation null.

**Guards:** `detect_grouping_level` (finds the level — this is the function that would have caught
all four instances), `permutation_null` (**refuses to run without an explicit grouping level**;
you must pass `screenkit.ROW_LEVEL` by name to get the wrong one), `null_width_comparison`
(runs both and publishes the inflation factor so every screen surfaces the number instead of
rediscovering it), and `paired_forecast_comparison` for the forecast-vs-forecast form of the same
trap.

**The kit itself fell into trap 1 once** — by *recommending* the row level under that name when no
coarser level existed. See **P2** below; the field is now `None` plus an explicit status.

`SCREEN_TEMPLATE.py` demonstrates the trap live on synthetic data where the feature has **zero**
true effect: the row-level null returns `p = 0.0033` (spuriously significant) while the correct
game-level null returns `p = 0.0598`, an inflation factor of **10.57x**.

### Trap 2 — the retrospective baseline (found **four** times)

An increment over a baseline that **reads the future** is not a forecasting increment.

Confirmed offenders: `player_tendency_loo` (full-season leave-one-out), a leave-one-*season*-out
player-by-zone rate that reads later seasons, and a leave-one-*game*-out full-season opponent rate
that reads the opponent's later games.

The measured signature on `player_tendency_loo`:

| baseline | corr with the player's OWN strictly-after-date future rate |
|---|---|
| `player_tendency_loo` (retrospective) | **+0.6455** |
| a clean pregame baseline | +0.3647 |

and the dR2 of the suspect over the clean one **in predicting that future** was **0.3319**.
A baseline that predicts the unplayed future substantially better than a legitimately pregame one
does so because it *contains* it.

**Names lie systematically.** `"leave-one-out"`, `"expected"`, `"pregame"`, `"prior"` and
`"baseline"` have **all** appeared in this program on quantities that read the future. Read the
construction *and* run the probe.

**Guards:** `future_leakage_probe`, plus the mandatory `TIME_WINDOW_TABLE` in
`SCREEN_TEMPLATE.py` where the author must declare, for every constructed feature, exactly what
window it reads.

### Trap 3 — the byte-scan partition check (failed **three** times)

Screens verified the 2021–2024 exploration partition by regex/text-scanning files for season
strings. This produces false hits:

- one verifier returned **14 hits that were all prose** about the partition rule — including its
  own log re-scanning its own context lines;
- another returned **18 false hits from columns named `_team_season`** that actually held dR2
  permutation draws (values near `1e-4`).

**The check must be on COLUMN VALUES** — parsed dates and year-range checks — **never on text.**
A name is not a value.

**Guard:** `assert_partition`. Its regression test builds a frame with a column literally named
`_team_season_2025` whose values are dR2 draws, plus a text column containing the sentence
"seasons 2025 and 2026 are the holdout", and requires the check to **pass**.

### Trap 4 — the weighted-R2 defect

A `wls_r2` helper computing

```python
sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)     # SST of the TRANSFORMED response about ITS OWN mean
```

instead of the standard weighted SST about the weighted mean, `sum(w*(y - mu_w)**2)`. SSE is
identical, so it is a **pure denominator effect**. It is **copy-pasted into six separate
`analyze.py` files** with no import graph.

Measured behaviour, all three reproduced as known-answer tests in `TESTS.py`:

| condition | ratio defective / standard |
|---|---|
| uniform weights | **exactly 1.0000000000** (analytic, and exact) |
| centered response | **≈ 0.99931 — not exactly 1** |
| dispersed weights, non-centered response | understates dR2 by **0 % to 25.3 %** |

Exact cancellation needs **both** `sum(w*y)=0` and `sum(sqrt(w)*y)=0`, which is why the centered
case lands near but not at 1.

**Guards:** `r2_plain` / `delta_r2_plain` (the adopted D069 default), `r2_weighted_standard` /
`delta_r2_weighted` (the correct weighted form), and `wls_r2_DEFECTIVE` — deliberately preserved
and loudly named, **for reproducing frozen screens' published numbers only**.

---

## Function reference

Every function's docstring states what it **guarantees** and what it explicitly **does not**.
Read them; the "does not" halves are where the remaining sharp edges live.

| function | guarantees, in one line |
|---|---|
| `r2_plain(y, X)` | **Refits OLS.** Unweighted R2 with SST about the **unweighted** mean — the adopted D069 convention for a *fitted model*. |
| `r2_of_forecast(y, yhat)` | **Scores a forecast you already have.** `1 − SSE/SST`, nothing fitted. Can be negative, and is meant to be. |
| `delta_r2_plain(y, X_base, X_full)` | Incremental plain R2 with a **shared** SST, so it is exactly `(SSE_base − SSE_full)/SST`. |
| `r2_weighted_standard(y, X, w)` | Weighted R2 with SST about the **weighted** mean — the textbook form. |
| `delta_r2_weighted(...)` | Incremental standard weighted R2, shared SST about `mu_w`. |
| `wls_r2_DEFECTIVE(y, X, w)` | Bit-comparable reproduction of the **broken** frozen convention. Never for a new result. |
| `detect_grouping_level(df, feature_col, ...)` | Reports distinct values and constancy at each candidate key, and names the **coarsest constant level** = the correct permutation level — or returns `None` with a status saying no coarser level exists. |
| `permutation_null(stat_fn, data, group_col, n_draws, seed, *, feature_col, scheme=..., ...)` | Permutes at an **explicitly named** level; refuses to default to rows. `scheme="between"` kills the group level, `scheme="within"` preserves it and kills only the within-group alignment. |
| `null_width_comparison(...)` | Runs both nulls with the same seed and statistic and reports `sd_correct / sd_row`. |
| `var_share_between(data, feature_col, group_col)` | Fraction of a feature's variance living **between** groups — tells you which `scheme` is actually a null. Exactly `1.0` for a constant-within feature, exactly `0.0` when all group means are equal. |
| `paired_forecast_comparison(y, yhat_a, yhat_b, groups, ...)` | **Forecast vs forecast on the same rows.** Paired loss difference, null by sign-flipping whole **clusters**; refuses a `None` clustering level exactly as `permutation_null` does. |
| `noop_placebo(stat_fn, data, n_draws, transform=None)` | Detects a placebo that is secretly the identity; asserts `sd < 1e-15` and **returns the observed sd**. |
| `assert_partition(df, ...)` | Value-based 2021–2024 check on parsed dates and season-valued columns; never reads text. |
| `check_manifest(artifact_path)` | `row` → usable if filtered; `artifact` → **unusable, filtering does not help**; missing → **`UNVERIFIABLE`, never a pass**. |
| `future_leakage_probe(...)` | Correlates each baseline with the entity's **own strictly-after-date future** and reports the dR2 of the suspect over the clean one in predicting it. |

### Two API details worth knowing

**`permutation_null` refuses to guess.** `group_col` has no default; `None` raises with a message
pointing at `detect_grouping_level`. To get the naive row-level null you must pass
`screenkit.ROW_LEVEL` explicitly. It also **raises if the feature is not constant within the level
you named**, because permuting group-representative values would silently discard within-group
variation.

**`noop_placebo` does not assert bitwise-exact zero.** A real screen found 5 of 7 statistics
bitwise exact and 2 at `~1e-19` from LAPACK non-determinism. The function tests `sd < 1e-15` and
**returns the observed sd** so the caller can report it honestly rather than rounding it to
`0.000000`. (Even the pure-identity case can show `sd ≈ 7e-18`, purely from rounding in the mean
used by the variance computation — `n_distinct_draw_values == 1` confirms the draws really are
identical.)

**Choosing a permutation scheme is not automatic.** `scheme="between"` destroys the *between*-group
signal and leaves the within-group signal intact; `scheme="within"` does the opposite. Neither is a
superset of the other, and a candidate that beats only one has not been shown to beat a null. Run
`var_share_between` first: near `1.0` → between is the null; near `0.0` → within is the null;
in between → **run both and credit the candidate only if it beats both**, which is what
`E0_I0014` did. Applying `scheme="between"` to a within-varying feature (via
`allow_nonconstant=True`) annihilates **100 %** of the within-group variation — a test proves the
draws collapse to `5e-29` against a real value of `586` — so any p taken there is manufactured
rather than measured.

---

## Four defects found by the kit's first real user

The adoption note for this kit (**D077**) recorded the risk deliberately: *"a shared kit
concentrates failure — one wrong function would propagate silently into everything downstream and
carry more authority while doing it."*

The first screen to use it, **`E0_I0015_points_skill_decomposition`**, found **four issues within
hours** and wrote a minimal reproduction (`KIT_BUG_REPRO.py`) rather than patching around them
silently. **That is the system working**, and the provenance is worth keeping. All four are closed,
and **each one now has a regression test that fails against the pre-fix code**.

### P1 — crash on boolean features

`detect_grouping_level` raised

```
TypeError: numpy boolean subtract, the `-` operator, is not supported
```

on **any** boolean feature: `bool` passes `pd.api.types.is_numeric_dtype`, so the numeric branch
was taken and `max − min` on numpy booleans is undefined. `permutation_null` inherited it through
the same helper.

This was not academic — binary pre-game flags are among the most common candidates here, and **two
of the four surviving leads** from `E0_I0014`'s residual-heterogeneity screen are booleans
(`is_fallback` among them).

**The 49-assertion suite passed while this was broken, because it only ever exercised floats.**
That blind spot is the real defect; the remedy is closing the blind spot, not just the bug.

**Fix:** booleans are converted **explicitly** in `_as_float_for_spread` (`False→0.0`, `True→1.0`,
`pd.NA→nan` — exact, total, order-preserving, so `max − min <= tol` means the same thing it means
for any numeric feature). A crash is the *safe* failure mode, so this is deliberately **not** a
permissive coercion of arbitrary dtypes: only `bool` is special-cased, non-numeric types still take
the distinct-count path, and anything else still raises. `permutation_null` additionally hands the
permuted column back to `stat_fn` **as `bool`**, so a `stat_fn` that boolean-masks (`d[d[col]]`)
behaves identically on the real frame and on every draw. Nullable `boolean` columns with `pd.NA`
work too.

### P2 — `recommended_permutation_level: "row"` — the serious one, and the silent one

`detect_grouping_level` returned `recommended_permutation_level: "row"` for genuinely row-varying
features — **34 of the reporter's 55 candidates**. The docstring carried the caveat, **but the
field name undid it**: a field called `recommended_permutation_level` holding the value `"row"`
reads as *the kit recommending the anticonservative null, with the kit's authority behind it*.
`"row"` is also the exact sentinel `permutation_null` accepts. **That is the precise error the
entire kit exists to prevent, and unlike P1 it is silent.**

**Fix — the semantics, not the wording. THIS IS A BREAKING CHANGE.**

| field | before | after |
|---|---|---|
| `recommended_permutation_level` | `"row"` | **`None`** — never the string `"row"` |
| `recommended_key_cols` | `None` | `None` (unchanged) |
| `status` | *(did not exist)* | `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` |
| `row_null_is_anticonservative` | *(did not exist)* | `True` |
| `warning` | *(did not exist)* | full explanation with the three options ranked |
| `level_if_you_accept_the_anticonservative_row_null` | *(did not exist)* | `"row"` — the only route to the sentinel |

The requirement was that *a caller who reads only the field name cannot be misled*, and the test
that enforces it is end-to-end: **piping `recommended_permutation_level` straight into
`permutation_null` now triggers its refusal** rather than quietly producing the wrong null. A
further assertion sweeps the whole returned dict for any field whose *name* reads as a
recommendation and whose *value* is `"row"`, so the defect cannot be reintroduced under a new name.

A related hazard is closed at the same time: a key that happens to identify rows uniquely (e.g.
`player_game` on a player-game frame) is a row-level null wearing key columns. Such levels are now
flagged `is_row_equivalent: True` and are never recommended.

**Migration:** compare `status` to `sk.STATUS_NO_COARSER_LEVEL`, not
`recommended_permutation_level` to `"row"`. One assertion in `TESTS.py` (TEST 3) was rewritten
because it had encoded the old contract; its *intent* — a row-varying feature must not be pushed to
a coarse level — is preserved.

### P3 — name collision that caused a false alarm

`screenkit.r2_plain(y, X)` **refits OLS**. The screens' own `rh_base.r2_plain(y, yhat)` computes
`1 − SSE/SST` for an **already-given forecast**. Same name, opposite semantics. The reporter got
**0.4747 against a published 0.4694** and briefly believed its reproduction had failed.

**Fix:** `r2_of_forecast(y, yhat)` is added — scores a given forecast, fits nothing — and both
docstrings now state plainly which is which. **`r2_plain` is unchanged in behaviour**; frozen
screens and this session's committed work depend on it exactly as it stands.

The sharpest statement of the difference, both hand-derived and both asserted:

| call | value | why |
|---|---|---|
| `r2_plain(y, −y)` | **`1.0` exactly** | it refits, so the sign is free |
| `r2_of_forecast(y, −y)` | **`−23.0` exactly** | it does not refit |

`r2_plain(y, f) >= r2_of_forecast(y, f)` always, and the two **coincide exactly** when `f` is
already the OLS-fitted value — which is precisely the miscalibration gap the reporter saw.

### P4 — missing machinery

The kit shipped only a *between*-block permutation scheme, and nothing at all for
forecast-versus-forecast contrasts — **which is what every skill comparison in this program actually
needs**. `E0_I0014` had to reimplement within/between schemes and a `var_share_between` measure
itself.

**Fix:** ported in, crediting `E0_I0014_residual_heterogeneity/rh_base.py` (frozen, read only) in
the source comments:

- **`permutation_null(..., scheme=SCHEME_WITHIN)`** — shuffles values *inside* each group, so the
  group's level survives and only the within-group alignment dies. Refused when the feature is
  constant within groups, because it is then the literal identity (the same vacuous control
  `noop_placebo` exists to catch), and refused at `ROW_LEVEL` for the same reason.
- **`var_share_between`** — the between/within variance split that tells you which scheme is real.
- **`paired_forecast_comparison`** — the paired contrast. Per-row loss difference
  `d_i = (y−a)² − (y−b)²`, aggregated to
  `dR2 = r2_of_forecast(y,a) − r2_of_forecast(y,b)` **exactly**, with a null built by sign-flipping
  **whole clusters**. Under exchangeability of the two forecasts within a cluster the test is
  **exact, not asymptotic**, and it needs no scipy. `groups` has no default and `None` raises,
  mirroring `permutation_null`.

**The paired test reproduces trap 1 in its own shape**, which is why row-wise sign flipping is
reported for contrast only:

| paired null, 200 replicates, two exchangeable forecasts (true dR2 = 0) | rejection rate at α = 0.05 |
|---|---|
| **naive row-wise sign flip** | **0.735** |
| correct cluster sign flip | 0.045 (nominal 0.05) |

with cluster p-values uniform (mean 0.493, median 0.490) and the row-wise null a median **4.91x too
narrow**. Compare the original trap-1 numbers below — 0.733 vs 0.033. It is the same error.

---

## What `TESTS.py` proves

`python TESTS.py` → **100 assertions, all passing, exit code 0** (~92 s wall clock; the critical
test does 48,000 permutation fits). Full captured output for both runs is in `run_log.txt`.

> **49 → 100.** The original 49 are unchanged apart from **one rewritten assertion** in TEST 3 that
> had encoded the P2 defect. All the hard-won numbers are bit-identical after the fixes: the
> 73.3 %-vs-3.3 % over-rejection demonstration, the 39.19x median null-sd inflation, the
> exactly-`1.0000000000` uniform-weight identity, the `0.99931` centered-response ratio, the
> 15.3117 % dR2 shortfall, and the `_team_season_2025` trap-3 partition regression.
>
> **Every one of the 51 new assertions was verified to fail against the pre-fix module** (git
> `374fce9`), by running this same `TESTS.py` against a copy of it: TEST 9 → the `numpy boolean
> subtract` `TypeError` at `screenkit.py:302`; TEST 10 → `recommended = 'row'`; TESTS 11–13 →
> `AttributeError` for each function that did not yet exist. A fix without a failing-first test is
> not accepted here — the suite's blind spot is what let P1 ship.
>
> `python TESTS.py p1 p2` runs a name-filtered subset, which is how that check was performed.

A shared library that is subtly wrong is *worse* than copy-paste, because it propagates one error
into every future screen with the authority of a shared helper. Every assertion is against a value
derived independently of the implementation — hand arithmetic, closed-form algebra, or a
construction whose answer is fixed before the code runs. **Synthetic data only; no real season data
is loaded and 2025/2026 appear only in a 4-row in-memory partition-violation fixture.**

Highlights:

- **`r2_plain`** against hand arithmetic: `169/175 = 0.9657142857142857`, matched to `0.0e+00`.
- **Trap 4, all three regimes.** The centered-response case is built by *inverting* the closed form
  `ratio = [1 − (1−R)/(1−t)]/R` for the target `0.99931`, constructing data with exactly that
  `(R, t)` via an orthogonality construction, and requiring the implementation to return it —
  matched to `< 1e-8`. The dispersed non-centered case lands at a **15.31 % shortfall**, inside the
  measured 0–25.3 % band, and matches its closed form to `4.8e-15`.
- **THE CRITICAL TEST** — 120 replicate synthetic datasets (200 permutation draws each) with
  **no real effect** and a group-level feature. It *demonstrates* the over-rejection rather than
  asserting an inequality:

  | null | rejection rate at α = 0.05 (true effect = 0) |
  |---|---|
  | naive row-level | **0.733** |
  | correct game-level | 0.033 (nominal 0.05) |

  The correct-level p-values are uniform (mean 0.517, median 0.530, min 0.005); independently
  confirmed at 200 replicates (mean 0.508, deciles on the diagonal, 3.5 % rejection, row-level
  76 %). The measured sd inflation (median **39.19x**) matches the analytic design effect
  `DE = 1 + (m−1)·ICC = 40.2` — on the dR2 scale the inflation is `DE` itself, since dR2 = r²,
  and `sqrt(DE) = 6.34x` on the correlation scale.
- **`noop_placebo`**: `sd = 0` on the identity, `sd = 4.3e-19` on the real
  permute-the-key-and-recompute defect (correctly flagged a no-op), `sd = 6.3e-04` on a genuine
  shuffle (correctly not flagged).
- **`assert_partition`**: passes clean data, raises on a 2025 season value and on a 2025 date-year
  value, catches a year-valued column with an innocuous name, and — the trap-3 regression —
  **passes** on `_team_season_2025` holding dR2 draws.
- **`check_manifest`**: missing manifest → `UNVERIFIABLE`, not a pass.
- **`future_leakage_probe`**: flags a full-season leave-one-out baseline
  (corr +0.9504 vs +0.8781 with the unplayed future, dR2 0.1424) and does **not** flag the clean
  pregame one in the reverse contrast.
- **P1 (booleans)** — 10 assertions. A boolean feature and its float twin produce an *identical*
  levels table; the boolean takes the numeric spread path (`0.0` within game, `1.0` within season)
  rather than the `nan` fallback; `stat_fn` sees dtype `bool` on all 40 permuted frames and the
  True count is invariant across every draw; nullable `boolean` with `pd.NA` works; a string
  feature still takes the distinct-count path with `nan` spread.
- **P2 (`row` is not a recommendation)** — 11 assertions, including the end-to-end one: piping
  `recommended_permutation_level` **and** `recommended_key_cols` into `permutation_null` both
  trigger its refusal, the whole dict is swept for endorsement-shaped field names holding `"row"`,
  a row-equivalent key (`player_game`, 300 groups over 300 rows) is flagged and never recommended,
  and the good path (`game_pace` → `game`) is confirmed unchanged.
- **P3 (`r2_of_forecast`)** — 9 assertions: `1 − 0.07/5.0 = 0.986` by hand, the `1.0` vs `−23.0`
  contrast, `r2_plain >= r2_of_forecast` on 25 random forecasts, exact agreement on OLS-fitted
  values, exact agreement with the frozen `rh_base` form recomputed inline, and a refusal when
  handed a design matrix.
- **P4 (schemes, variance share, paired test)** — 21 assertions: `var_share_between` hits exactly
  `1.0`, exactly `0.0` and exactly `0.5` on three constructions; the within scheme preserves every
  group mean to `6.7e-16` and each group's multiset to `1.1e-13`; forcing the between scheme onto a
  within-varying feature collapses the draws to `5.5e-29` against a real value of `585.94`; the
  within null is calibrated under a group-level confounder (rejection 0.025, mean p 0.513);
  identical forecasts give `dR2 = 0` and `p = 1.0` **exactly**; swapping A and B negates dR2 exactly
  and preserves the two-sided p; and the paired cluster/row rejection rates land at 0.045 vs 0.735.

---

## Provenance — what was adapted, and from where

Nothing here was reinvented where the program had already converged on a convention. All source
screens were read **read-only**:

| kit function | adapted from (frozen screen) |
|---|---|
| `r2_plain`, `delta_r2_plain` | `E1_I0013_tempo_redundancy/e1_lib.py :: r2()` |
| `r2_weighted_standard` | `E1_I0009_r2_rerun/step23_reproduce_and_rerun.py :: r2_standard_weighted()` |
| `wls_r2_DEFECTIVE` | same file, `:: r2_defective()`, itself verbatim from `E0_I0009_additive_pressure/analyze.py :: wls_r2()` |
| `permutation_null` group semantics | `E1_I0013_tempo_redundancy/e1_lib.py :: GamePerm` |
| the naive row-level null | `e1_lib.py :: perm_rows` and `E0_I0013_possession_volume/run_screen.py` |
| `assert_partition` value gate | `E1_I0013_tempo_redundancy/verify_partition.py :: looks_like_a_season_column()` |
| `check_manifest` fields and verdicts | `E1_I0008_height_mismatch/build_frame.py` manifest block |
| `future_leakage_probe` | `E1_I0009_r2_rerun/step5_baseline_audit_and_gate.py` section (a) |
| `noop_placebo` tolerance behaviour | `E1_I0008_height_mismatch/stage1_noise_floor.py`, `E0_I0013_possession_volume/run_screen.py` |
| `scheme="within"` (P4) | `E0_I0014_residual_heterogeneity/rh_base.py :: within_block_index()` |
| `var_share_between` (P4) | `E0_I0014_residual_heterogeneity/rh_base.py :: var_share_between()` |
| `r2_of_forecast` (P3) | `E0_I0014_residual_heterogeneity/rh_base.py :: r2_plain(y, yhat)` — the colliding name |

---

## Scope boundary

**This kit is for future screens. It does not edit, "fix", or retrofit any existing screen.**

The completed screens are deliberately frozen so their published numbers stay reproducible. A
standing decision (**D069**) rules explicitly that the six copies of the defective weighted-R2
helper **stay as they are**, and that this is deliberate rather than neglect. Changing them would
silently alter numbers in shipped artifacts and destroy the audit trail. `wls_r2_DEFECTIVE` exists
precisely so a new screen can reproduce those published numbers *before* re-running them correctly
— which is exactly what `E1_I0009_r2_rerun` did.

## Files

| file | what it is |
|---|---|
| `screenkit.py` | the module — the only thing you import |
| `TESTS.py` | known-answer tests; run after any change (`python TESTS.py`) |
| `SCREEN_TEMPLATE.py` | runnable skeleton screen in the correct order of operations |
| `run_log.txt` | captured output of an actual `python TESTS.py` run |
| `_demo_out/` | artifacts written by the template's demo run (not a real screen) |
