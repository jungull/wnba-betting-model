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

Feature built with `.shift(1).expanding()` — a running mean of the entity's own history? **Then it
is autocorrelated by construction and `scheme="within"` gives you a null that is too narrow.** Use
the cyclic shift, and tell the kit which column puts the rows in time order:

```python
sk.within_group_acf1(df, "my_prior", "player_id", order_col="game_date")   # measure it first
sk.permutation_null(stat_fn, df, "player_id", 2000, seed=1, feature_col="my_prior",
                    scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date")
```

Validating a **per-player** claim? The control you were about to reach for — relabel the player key
and refit — is a **literal no-op**. Use the one that can fail:

```python
sk.per_entity_control(stat_fn, df, "player_id", feature_col="my_prior",
                      n_draws=2000, seed=1, order_col="game_date", verbose=True)
```

Feature varies **inside** its entity, but the question is **between** entities (an expanding prior
against an opponent-defence family, say)? Neither `scheme` is a null there — use `entity_swap_null`:

```python
sk.entity_swap_null(stat_fn, df, ["opp_team_id", "season"], 2000, seed=1,
                    feature_col="my_prior", date_col="game_date",
                    season_col="season", tiebreak_col="game_id", verbose=True)
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

> **Trap 3 recurred a fourth time — inside this guard.** The date branch of `assert_partition` had
> no value gate, and the word **"candi-DATE" contains "date"**. See **K0** below. The invariant now
> stated in the module header is: *a substring match on a column name may only ever nominate a
> column for a value test; it may never, by itself, cause a violation.*

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
| `permutation_null(stat_fn, data, group_col, n_draws, seed, *, feature_col, scheme=..., order_col=..., ...)` | Permutes at an **explicitly named** level; refuses to default to rows. `scheme="between"` kills the group level, `scheme="within"` preserves it and kills only the within-group alignment, `scheme="within_cyclic"` preserves the group level **and the feature's serial structure**. **Refuses `"within"` on an autocorrelated feature** (K6). |
| `within_group_acf1(data, feature_col, group_col, order_col=None)` | Pooled **lag-1 autocorrelation of the feature inside its groups** — the number that decides whether `scheme="within"` gives you a null that is too narrow. (K6) |
| `per_entity_control(stat_fn, data, entity_col, *, feature_col, ...)` | **Two controls for a per-entity statistic: the vacuous one and one that can fail.** Runs the relabel-the-key arm (always a no-op) beside a within-entity cyclic-shift arm that really does perturb the per-entity fits. (K7) |
| `null_width_comparison(...)` | Runs both nulls with the same seed and statistic and reports `sd_correct / sd_row`. |
| `var_share_between(data, feature_col, group_col)` | Fraction of a feature's variance living **between** groups — tells you which `scheme` is actually a null. Exactly `1.0` for a constant-within feature, exactly `0.0` when all group means are equal. |
| `paired_forecast_comparison(y, yhat_a, yhat_b, groups, ...)` | **Forecast vs forecast on the same rows.** Paired loss difference, null by sign-flipping whole **clusters**; refuses a `None` clustering level exactly as `permutation_null` does. |
| `entity_swap_null(stat_fn, data, entity_cols, ...)` | **The between-entity question for a feature that varies *within* the entity.** Swaps whole entity-season series inside a season, preserving series length and temporal shape. The only valid scheme when `detect_grouping_level` finds no constant level. |
| `EntitySwap(df, entity_cols, date_col=...)` | The swapper itself, exposed so one grouping can be reused across many candidates. |
| `noop_placebo(stat_fn, data, n_draws, transform=None)` | Detects a placebo that is secretly the identity; asserts `sd < 1e-15`, **returns the observed sd**, and **names the non-vacuous alternative** rather than stopping at the diagnosis. |
| `assert_partition(df, ...)` | Value-based 2021–2024 check on parsed dates and season-valued columns; never reads text, **never treats a name match as a violation**, and **classifies every out-of-partition value by DIRECTION** so a `draft_year` of 2008 is recorded rather than fatal while a 2026 anywhere still raises. (K4) |
| `check_manifest(artifact_path)` | `row` → usable if filtered; `artifact` → **unusable, filtering does not help**; missing → **`UNVERIFIABLE`, never a pass**. |
| `future_leakage_probe(...)` | Correlates each baseline with the entity's **own strictly-after-date future** and reports the dR2 of the suspect over the clean one in predicting it. **A screening flag, not a verdict** — read `status`. |

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

**If `detect_grouping_level` finds *no* constant level and your question is still "does which
*entity* this row belongs to matter", neither scheme applies** — that is the K2 gap, and the answer
is `entity_swap_null`, which swaps whole entity-season **series** rather than individual values.
Do **not** reach for `allow_nonconstant=True` to force `scheme="between"` onto that question.

**And `scheme="within"` is not safe just because the level is right.** It destroys the feature's
**serial** structure as well as its alignment, which makes the null **too narrow** whenever the
feature is autocorrelated — the shape of every `.shift(1).expanding()` prior in this repository.
`scheme="within_cyclic"` preserves the serial structure and destroys only the alignment; the kit
**refuses** the shuffle when it measures a material `acf1` and points you here. That is **K6**, it
is the most serious defect found so far, and it has its own section below.

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

## Three more defects found by the kit's **second and third** real users

**This provenance is the point.** The kit was adopted at **D077** with 49 assertions. Its **first**
user found four defects (P1–P4 above), which took it to 100. Its **second and third** users —
`E0_I0016_efficiency_predictors` and the screen alongside it — then found **three more, plus a
usage nit**, in code that had already been repaired once and that had 100 passing assertions
behind it.

That is not a sign the kit is failing. **It is the kit working as intended.** Every real user
exercises paths the tests do not, and the only remedy for a blind spot is a user who walks into it.
All three are closed below, each with a regression test that **fails against the pre-fix code**.

### K0 — `assert_partition` **raised on clean data** (the priority)

`assert_partition` auto-detected date columns by `"date" in name.lower()`.

> **The word "candi‑DATE" contains "date".**

So `candidate`, `n_candidates`, `mae_with_candidate`, `update_flag` and `validated` were all treated
as date columns — and `pd.to_datetime` on a **float** column *does not raise*. It reads the values
as **nanoseconds since the epoch** and returns `1970-01-01`. Year 1970 is outside every real
partition, so **`assert_partition` raised `PartitionViolation` on a frame whose every value sat
inside 2021–2024**.

`candidate` is not an unlucky word. It is the vocabulary of every exploration screen here.

**The real defect was an asymmetry.** The **season** branch already had `_is_season_valued`, added
precisely to stop name-based false hits, with the `_team_season_2025` regression test. The **date**
branch had no equivalent. The reporter's reproduction shows both behaviours side by side:

| column | name matches | values are | pre-fix outcome |
|---|---|---|---|
| `_team_season_2025` | `season` | dR2 draws ~`1e-4` | **skipped** — *"name is season-like but VALUES are not seasons"* |
| `candidate_mae` | `date` (candi‑**date**) | MAE floats | **checked, and flagged as year 1970** |

**Fix:** `_is_date_valued`, the missing half of that symmetry.

1. **datetime64 dtype → accepted outright.** The dtype is the proof; no year range is imposed, so a
   genuine 2026 column is still checked and still flagged.
2. **Numeric dtype (int/float/bool) → refused outright.** *The epoch-nanosecond reading is never
   used.* No threshold, no heuristic, no rescue: a float is not a date, and inferring a year from
   one is exactly how the false positive was manufactured.
3. **String/object → parsed**, and required to reach an 80 % parse rate *and* land every year inside
   **1990–2100**. That window is a second, independent line of defence (1970 is outside it) and is
   deliberately far wider than any partition, so it can never mask a real violation.

**The obvious workaround was deliberately not made the fix.** Passing `date_cols=[]` silences the
false positive *and disables the true check* — the reporter demonstrated a genuine 2026 date passing
clean under it. That is a **false-pass door**, and a guard that cries wolf on the program's most
common column name is a guard that trains callers to open it.

**Two declared behavioural breaks** (as D082 declared its one):

| # | change | before | after |
|---|---|---|---|
| **B1** | a **numeric** column whose name contains `date` | parsed as epoch ns, flagged as year 1970 | recorded in `skipped_name_only`, never flagged. Convert epoch columns yourself with `pd.to_datetime(col, unit=...)` — the kit will not guess an encoding |
| **B2** | `date_cols` | **exhaustive** — `date_cols=[]` disabled the date check entirely | **additive** — datetime64 columns are checked regardless. Pass `include_datetime_dtype_cols=False` for the old behaviour and say why in `FINDINGS.json`. A column named explicitly in `date_cols` whose values are not dates now **raises `ValueError`** rather than being silently skipped |

The reported `UserWarning: Could not infer format …` noise is also gone: parsing goes through
`_parse_datetimes`, which passes `format="mixed"` — which is strictly *more* capable here
(`07/04/2022` now parses; under the default it became `NaT`).

**K0 was the fourth instance of a name-based false hit in this program, and the first one inside
the guard built to prevent them.** The whole module was therefore swept; the audit is in the module
header. There are exactly two substring matches on column names (`season`/`year`, and `date`), both
now value-gated, under a stated invariant: **a substring match on a column name may only ever
nominate a column for a value test; it may never, by itself, cause a violation.**

### K1 — `future_leakage_probe` stated a **false conclusion** in its verdict

The verdict text asserted:

> *"That is only possible because it CONTAINS the future."*

**That is not true in general.** The probe fired on `refB_ppm` versus `refA_ppm` — **both strictly
prior-games-only**, differing only as *estimators*. A better (less noisy) estimator of a quantity
that **persists over time** correlates more with the entity's own future *without reading a single
future row*. **A caller trusting that wording would discard a clean baseline.**

**The numbers are unchanged.** Only the claim attached to them is fixed. A flag now means exactly:

> the suspect tracks the entity's own unplayed future more closely than the contrast does, which is
> **consistent with** the suspect containing future information and **equally consistent with** the
> suspect simply being a better estimator of a persistent quantity — and **this probe cannot tell
> them apart**.

The probe is a **screening flag, not a verdict**, and now says so in its verdict string, in a new
`status` field (`FLAGGED__CONSISTENT_WITH_LEAKAGE__ALSO_CONSISTENT_WITH_A_BETTER_ESTIMATOR`), and in
a new `alternative_explanation` field. Treat a flag as a **request for an audit of the
construction**, not a finding of leakage. The legacy `reads_future` field is kept with its value
unchanged for compatibility, but — applying the **P2** lesson about field names carrying claims —
**its name overstates what it means; read `status`.**

The regression test builds two baselines from `shift(1)` alone, so **neither can read the future by
construction**, and requires the probe to fire on them — which it does, at
corr **+0.8959** vs **+0.8142** and dR2 **0.1397**. Sensitivity is unchanged: the genuine
leave-one-out leak is still flagged.

### K2 — a genuine capability gap, not misuse

**No valid permutation scheme existed for the between-entity question on a within-varying feature.**

- `scheme="between"` **requires** the feature to be constant within groups, and forcing it with
  `allow_nonconstant=True` is what this kit itself calls a p *"manufactured rather than measured"*.
- `scheme="within"` is the **literal identity** when the feature *is* constant — `permutation_null`
  refuses it.

Every expanding-prior candidate is neither. The reporter verified with `detect_grouping_level` that
**no candidate was constant within its entity-season in any of 132 cells**, declared the gap
explicitly rather than papering over it, and built `EntitySwap` / `entity_swap_null` itself.

**Fix:** both are ported into the kit, crediting
`E0_I0016_efficiency_predictors/ep_base.py` (read-only) in the source comments. Generalised only in
that the intra-date tiebreak column is a parameter rather than hard-coded to `game_id`, and season
blocking can be switched off.

**What it exchanges: the entity labels.** Entity-seasons are permuted *inside each season*; an
entity of length `n_a` receives its partner's values at proportional positions
`round(k/(n_a−1)·(n_b−1))`, so **position 0 maps to position 0 and the last to the last**. Series
length and within-season temporal shape are preserved — which matters, because an early-season
expanding prior is mechanically noisier than a late-season one, and a null that scrambled that would
not be comparing like with like.

It answers the **between**-entity question *only*, and the returned `warning` says so: run
`scheme=SCHEME_WITHIN` for the other half and credit a candidate only if it beats **both**.

### K3 — the reported usage nit

`detect_grouping_level`'s `candidate_keys` must be a **mapping** from a level *name* to its key
*columns*. Passing a list reached `.items()` and died with a bare
`AttributeError: 'list' object has no attribute 'items'` — naming neither the parameter nor the
required shape. It now raises a `TypeError` that names the parameter, the type received, the
required shape, and shows the fix using the caller's own column name.

---

## FALSE-ASSURANCE DEFECTS — the class, and why naming it matters more than the individual fixes

**Nine defects across seven users, and the pattern has shifted.** The early ones crashed or were
obviously wrong: `numpy boolean subtract` (P1), `PartitionViolation` on clean data (K0), a bare
`AttributeError` (K3). **The last three are silent** — a field *name* that endorsed the wrong
choice (P2), a guard whose obvious workaround hides real leaks (K4), and a null that is too narrow
(K6). A defect class that recurs three times is a **design property, not bad luck**, so it gets a
name:

> **A false-assurance defect is one where the kit returns a confident, well-formed, non-crashing
> answer that is wrong in the reassuring direction.**

There are exactly **two shapes** of it, and they are the two ways this kit can lie to someone while
appearing to work:

| shape | what it looks like | instances found so far |
|---|---|---|
| **1 — a control that cannot fail** | It reports "clean" because it tests **nothing**. Every draw reproduces the real statistic. | permute-the-key-and-recompute (what `noop_placebo` exists for); `scheme="within"` on a feature constant within groups (refused); **relabel the entity key and refit (K7)** |
| **2 — a null that is too narrow** | It reports a small `p` because the permuted draws destroy **more** structure than the null says is exchangeable. | the row-level null on a clustered feature (**trap 1**, found 4×); **`scheme="within"` on an autocorrelated feature (K6)** |

Both look identical to a working tool from the outside. **Neither is detectable from the output
alone** — there is no number in the returned dict that says "this p is too small", because the
number *is* the p. That is why the kit must **refuse or warn** rather than leave it to the caller
to notice, and it is why K6 refuses by default rather than warning.

The two failure directions are not symmetric and the kit is not neutral between them. A **false
alarm** costs a caller ten minutes of adjudication. A **false pass** costs the program a published
result. Every design choice below breaks toward the alarm.

`screenkit.py`'s module header carries a standing **FALSE-ASSURANCE AUDIT** of every public
function against both shapes, including the seven places where a confident wrong answer is still
reachable and was **deliberately not changed** (cyclic shift depends on row order and cannot verify
it; the acf gate inspects the feature and never the response; the cluster sign-flip null has only
`2^n_groups` states; `var_share_between` is a raw share and not an ICC; …). Read it before
trusting an output you did not construct yourself.

---

## Four items found by the kit's **seventh and eighth** real users

`E1_I0020_coldstart_tiering` (seventh) reported **K4** and **K5**;
`E1_I0021_heterogeneity_diagnostic` (eighth) reported **K6** and **K7**. **K6 and K7 are both
false-assurance defects** — one of each shape. A fifth, **K8**, was found by this round's own audit
rather than by a user.

### K6 — `scheme="within"` is **anticonservative for an autocorrelated regressor** (the priority)

The within-group shuffle destroys the regressor's **serial** structure while the response keeps its
own slow drift, so the null comes out **too narrow** by exactly the overlap between them.

> **Measured by the reporter: `p = 0.0015` under `scheme="within"` where the honest null gives
> `0.39`** — on a diagnostic whose headline would then have been *"per-player heterogeneity is real
> and pooling has been destroying it"*, the most consequential result the program could produce,
> **and a false positive.** The screen caught it only because it built the honest null itself.

**This is the modal case, not an edge case.** The program's most common construction is
`.shift(1).expanding()`, which is autocorrelated *by design*: `refA_*`, `refB_*`, `O01_own_usg_pg`,
`P01_c04_prevgame` and every running-mean prior in the repository have this shape.

The reporter measured the mechanism rather than asserting it — across 48 (floor × relationship)
cells, `corr(lag-1 within-player acf of x, shuffle-minus-cyclic null-ratio gap) = +0.832`:

| relationship | mean lag-1 acf of x | mean N1−N4 gap |
|---|---|---|
| `NC1_noise` (iid by construction) | −0.029 | −0.004 |
| `NC2_noise` (iid by construction) | −0.025 | −0.004 |
| `R01_prior_efficiency_persistence` | +0.550 | **+0.179** |
| `R06_own_usage` | +0.864 | **+0.121** |

**Two changes, both required.**

**(a) `SCHEME_WITHIN_CYCLIC` is added.** A within-group **cyclic shift**: rotate each group's series
by a random offset. It preserves each group's **marginal distribution** *and* its **serial
structure** exactly, and destroys only the alignment to the response. Ported from
`E1_I0021_heterogeneity_diagnostic/hd_base.py :: cyclic_shift_within_groups` (read-only), which the
reporter had to write itself. TEST 18 reproduces the failure on synthetic data with **true effect
exactly zero**:

| `rho_x` | measured `acf1` | rejection, `scheme="within"` | rejection, `scheme="within_cyclic"` | `sd_cyclic / sd_shuffle` |
|---|---|---|---|---|
| 0.00 (**iid control**) | −0.022 | 0.050 | 0.062 | **1.02** |
| 0.40 | +0.357 | 0.175 | 0.062 | 1.41 |
| 0.70 | +0.637 | 0.287 | 0.087 | 1.89 |
| 0.95 | +0.846 | **0.525** | **0.062** | **2.45** |

80 replicates per row, 150 draws each, α = 0.05, 25 entities × 40 games in time order, `x` and `y`
drawn **independently** so the true effect is zero at every `rho`. **Every one of those 0.525
rejections is a false positive a real screen would have published.** The gap tracks the
autocorrelation at `corr = +0.979` and **vanishes on the iid control** — the same relationship the
reporter measured at `+0.832` on real data. Directly: the shuffle drives the feature's acf from
`+0.7591` to `+0.0399`; the cyclic shift holds it at `+0.7397`.

**(b) The hazard is made impossible to walk into.** `permutation_null` now measures the feature's
within-group lag-1 autocorrelation **before** running, and **refuses** `scheme="within"` when it is
material, naming the measured value and `SCHEME_WITHIN_CYCLIC`.

> **Why refuse and not warn.** The **D086 P2 precedent** is that the unsafe path must require an
> **explicit opt-in**, because anything that still returns a well-formed answer carries the kit's
> authority. That precedent has since been **vindicated twice in the wild**: the seventh user read
> `status` rather than the field name and chose the game-team scheme deliberately; the eighth user's
> `recommended_permutation_level = None` is what stopped it reaching for the row null. A warning
> printed beside a returned `p = 0.0015` would have been read as a caveat on a real finding.
> `accept_serial_structure_destroyed=True` is the opt-in, and the result then carries
> `serial_structure_preserved=False` and a non-`None` `warning`.

The threshold is `max(0.15, 2/sqrt(n_pairs))` — a **materiality floor**, or **twice acf1's sampling
standard error** under the iid null on a small frame, whichever is larger — and it is **one-sided**.
Positive serial correlation is the hazard; a *negative* acf1 makes the shuffle null **wider**, i.e.
conservative, and refusing on it would block a safe call. The signed value is always reported.

**Row order is an input and the kit cannot verify it.** A cyclic shift is only
structure-preserving if the rows inside each group are in **time order**. Pass `order_col`. When
you do not, the kit measures the acf in **frame row order** and says so — and if the cyclic scheme
is used on a feature whose measured acf1 is *not* material, the result carries a warning naming
exactly this mistake, because a scrambled frame reports `acf1 = −0.039` where `order_col` recovers
`+0.779`.

`detect_grouping_level` also reports `acf1_within_group` per level as a diagnostic (the reporter's
suggestion 3).

### K7 — the natural per-player control is a **literal no-op**

*"Shuffle the player labels and see whether the coefficient spread shrinks"* is the control an
analyst reaches for **first** when validating per-player work, and **it tests nothing**.
Relabelling entity ids is a **bijection on whole groups**: every player's row set travels intact to
its new label, every per-player fit is refitted on exactly the same rows, and the **multiset** of
coefficients — hence its spread — is *exactly* unchanged.

> **Confirmed by the reporter at observed sd = `5.207e-17` over 3 distinct draw values.** It
> returned a clean bill of health while testing nothing. This is the trap family the program has
> now caught nine times, **one level down**: not the row-level no-op, the *entity*-level one.

**This was not a bug in `noop_placebo`.** It worked exactly as designed and correctly reported a
no-op. **The defect was that the kit offered no alternative and no guidance** — a tool that says
*"your control is vacuous"* and stops there leaves the caller stuck.

`per_entity_control` runs **both arms and reports them side by side**:

| arm | what it does | expected |
|---|---|---|
| **1 — relabel** | permute the entity key labels and recompute | `sd ≈ 0`, `is_noop=True`. Proven vacuous **on your own statistic**, not argued. If it is *not* a no-op, your `stat_fn` depends on entity **identity** too, and it says so. |
| **2 — genuine** | permute the feature **inside** each entity (default `SCHEME_WITHIN_CYCLIC`) | a null with real width. Each entity keeps its sample size, its marginal **and** its serial structure; only the alignment dies, so the per-entity fits really do change. |

Measured in TEST 19 on 40 players × 30 games: arm 1 `sd = 1.1e-16` (**vacuous**), arm 2
`sd = 0.045205`, `p = 0.0050` (**can fail**). `controls_are_informative` is `True` only when arm 1
is vacuous *and* arm 2 moves; anything else returns a `warning` instead of a verdict.
`noop_placebo`'s no-op verdict now **names** this function and `SCHEME_WITHIN_CYCLIC` instead of
ending at the diagnosis.

### K4 — `assert_partition` **raised on clean data** carrying a year-valued player attribute

A frame whose every observation sits in 2021–2024 was **rejected** if it carried `draft_year`
(2002–2020), `birth_year`, `grad_year` or `founded`.

**This is not a repeat of K0 and it was not fixed the same way.** K0's fix installed the invariant
*a substring match on a column name may only ever nominate a column for a value test; it may never,
by itself, cause a violation.* **K4 satisfies that invariant and fails anyway:** the token `year`
nominates `draft_year`, `_is_season_valued` is asked *"are these values years?"*, answers **yes,
correctly**, and the column is checked against a partition it legitimately **predates**.

| the gate asked | what the partition needs to know |
|---|---|
| are these values plausible **years**? | is this column the **observation season of the row**? |

Every year-valued attribute of a person or an organisation answers **yes** to the first and **no**
to the second, so no sharper value test can separate them. **Direction can** — and direction is what
the guard is actually for. The guard exists to stop **2025 and 2026**, the holdout, the **future**.
`draft_year = 2008` cannot be a holdout leak; it is fourteen years in the past.

| direction | rule |
|---|---|
| **`FUTURE`** (> max allowed) | **fatal, always, in every column, however detected.** |
| **`INTERIOR`** (inside the span, not in `allowed`) | **fatal.** |
| **`PAST`** (< min allowed), auto-detected | recorded in `historical_year_cols`, **not fatal** — *conditionally*, see below |
| **`PAST`**, column **named** in `season_cols` | **fatal.** Naming a column asserts it *is* an observation season; that assertion is honoured loudly, the same asymmetry **B2** established for `date_cols`. |

Violations are now also returned as **structured records** (`{col, kind, direction, values, fatal,
source}`), so a caller can adjudicate **without re-parsing the guard's own prose** — which is the
textual check this whole module exists to forbid. Pre-fix, a harmless 2008 and a genuine 2026
produced violation strings of the *same shape*.

**The obvious workaround was again worse than the bug (break B4).** Pre-fix,
`season_cols=["season"]` silenced the `draft_year` false alarm **and silenced a genuine 2026 leak in
`source_season`**, a column the caller never named — precisely the "false-pass door" K0 named.
`season_cols` is therefore now **additive**, exactly as `date_cols` is: it adds columns and marks
them strict, and it never disables auto-detection.

**And "PAST is never fatal" would have opened a *new* false-pass door**, which is the mistake this
whole round is about avoiding. Taken literally it would wave through a frame whose `season` column
genuinely holds **2019 observation rows**. So a purely-`PAST` verdict is non-fatal **only when the
frame carries an anchor**: some season or date column *every one of whose values is inside the
partition*. With an anchor, the observation window is demonstrably in-partition and an earlier
column is an **attribute**. Without one, nothing establishes that the frame is in-partition at all
and every out-of-partition value stays **fatal in both directions**. `in_partition_anchor_cols`
reports which columns anchored the frame, or is empty.

**Not done, and deliberately:** the reporter's suggestion (3) of an `_ATTRIBUTE_YEAR_TOKENS`
nomination list. Direction subsumes it — every case the token list would route to the historical
branch is already routed there **by its values** — and adding a *third* name-based mechanism to a
module whose standing audit says *"a substring match may only ever nominate"* buys nothing and costs
a maintenance surface. A `draft_year` of **2026** must still surface; under direction it does,
under the token list it might not.

### K5 — `permutation_null` refuses string categoricals (a nit, not a defect)

The behaviour and the message are both **correct and unchanged**. Guessing an encoding would impose
an ordering the caller never declared, so the kit refuses:
*"the kit will not guess an encoding for you."* It is reported only as **friction** — group priors
over categorical labels (position, draft bucket, depth bucket) are among the most natural things to
permute in this program, so most users meet it. **The fix is this worked example, not a code
change.**

Declare a **bijective integer codebook**, apply it identically to the real frame and every draw, and
map **back to the label inside `stat_fn`** so no arithmetic is ever done on the codes and no
ordering is implied:

```python
codebook = {"G": 0, "F": 1, "C": 2}          # record this in FINDINGS.json
inv      = {v: k for k, v in codebook.items()}
d = df.copy()
d["position_code"] = d["position"].map(codebook).astype(int)

def stat(d):
    lab = d["position_code"].map(inv)         # map BACK: no arithmetic on the codes
    return float(d.groupby(lab.to_numpy(), sort=True)["y"].mean().max())

res = sk.permutation_null(stat, d, "player_id", 2000, 0, feature_col="position_code",
                          scheme=sk.SCHEME_WITHIN)
```

Two things make this safe rather than a workaround: the codebook is **bijective** (so the
permutation acts on labels, not on an invented scale), and `stat_fn` **maps back**, so a code is
never compared, ordered or averaged. `E1_I0020` recorded its codebooks in
`FINDINGS.json › kit_defects.K5….categorical_codebooks`; do the same.

### K8 — a NULL in a composite grouping key **silently merged two groups** (found by this audit)

`_group_codes` built a composite key as `codes * n_levels + next_code`. That is injective only
while every code is in `[0, n_levels)` — and `pd.factorize` returns the sentinel **−1** for a NULL.
With `n_levels = 3`, `(group 0, code −1)` and `(group −1, code 2)` both land on **−1**:

| key tuple | pre-fix group code | post-fix |
|---|---|---|
| `('B', 3.0)` | **2** | 2 |
| `('C', NaN)` | **2** ← *same group* | 4 |

Six distinct key tuples became **five groups**. Every consumer inherited it: `n_groups` was wrong,
`constant_within` was wrong, and `permutation_null` shuffled values **across two genuinely
different groups** while returning a perfectly well-formed `p`. **No crash, no warning, no
symptom** — a false-assurance defect of the purest kind. Fixed by factorizing with
`use_na_sentinel=False`, which gives NULL its own real code and restores injectivity
(**break B5**: a NULL key cell is now a visible level).

### The declared behavioural breaks from this round

| break | before | after | old behaviour still reachable by |
|---|---|---|---|
| **B3** | `scheme="within"` ran silently on an autocorrelated feature and returned a `p` that was too small | raises, naming the measured `acf1`, the threshold and `SCHEME_WITHIN_CYCLIC` | `accept_serial_structure_destroyed=True` (result then carries a `warning`) |
| **B4** | `season_cols=[...]` **replaced** auto-detection — a false-pass door | `season_cols` is **additive**; named columns are additionally **strict in both directions** | `include_name_matched_season_cols=False` |
| **B5** | a NULL in a composite key could merge two groups | the NULL cell is its own group | — (there is nothing sane to restore) |

---

## What `TESTS.py` proves

`python TESTS.py` → **224 assertions, all passing, exit code 0** (~155–205 s wall clock; TEST 4 does
48,000 permutation fits and TEST 18 does 192,000). Full captured output for all four runs is in
`run_log.txt`.

> **49 → 100 → 159 → 224.** The original 49 are unchanged apart from **one rewritten assertion** in
> TEST 3 that had encoded the P2 defect; the 100 and the 159 are unchanged outright. All the
> hard-won numbers are bit-identical after every repair: the 73.3 %-vs-3.3 % over-rejection
> demonstration, the 39.19x median null-sd inflation, the exactly-`1.0000000000` uniform-weight
> identity, the `0.999310` centered-response ratio, the 15.3117 % dR2 shortfall, the
> `_team_season_2025` trap-3 partition regression, the P2 `None`-not-`"row"` contract, the
> 0.735-vs-0.045 paired demonstration, and the K0 date gates.
>
> **Every one of the 51 P-fix assertions was verified to fail against the pre-D082 module** (git
> `374fce9`): TEST 9 → the `numpy boolean subtract` `TypeError`; TEST 10 → `recommended = 'row'`;
> TESTS 11–13 → `AttributeError` for each function that did not yet exist.
>
> **The 59 K0–K3 assertions were likewise verified against the pre-K module** (git `56dc793`).
>
> **The 65 assertions added for K4–K8 were verified against the pre-fix module** (git `6d6a17c`), by
> running this same `TESTS.py` against a copy extracted with `git show` into a scratch directory
> together with the pre-fix `README.md`. Pre-fix the run **reaches all 224 assertions** — the new
> tests wrap each group in a `block` context manager that records a FAIL per assertion when the
> group raises, precisely so the two runs are comparable rather than one aborting early — and
> reports **168 PASSED, 56 FAILED**. The 168 are the 159 pre-existing assertions (**none broken**)
> plus **9 of the 65 new ones**. Those 9 are labelled positive controls and no-regression checks:
>
> | passes pre-fix | why it is not evidence of a fix |
> |---|---|
> | `[positive control] relabelling the player key is a CONFIRMED NO-OP` | the **measured fact the fix responds to** (K7). It was always true; it is pinned so it cannot silently change. |
> | `[positive control] the no-op reproduces the real statistic, so it tests NOTHING` | same |
> | `[positive control] _is_season_valued says YES to draft_year, and it is RIGHT` | the **point** of K4: the value gate is not the bug (this is what makes K4 ≠ K0) |
> | `[positive control] the K0 case still gets NO from the same gate` | K0 sensitivity preserved |
> | `REPRO 3: a draft_year of 2026 STILL RAISES` | a **no-regression** guard: pre-fix everything raises, so it passes trivially. Its job is to fail if the K4 fix ever over-reaches. |
> | `[positive control] a str feature is REFUSED with TypeError` | K5 behaviour is **correct and unchanged** |
> | `[positive control] the refusal message names the column, the dtype and the remedy` | same |
> | `a bijective integer codebook makes the categorical permutable end to end` | the K5 remedy needs no code change, so it works pre-fix too |
> | `a key with no NULLs is unaffected` | K8 **no-regression** check |
>
> **Not one assertion that encodes a fix passes against the pre-fix code.** The 56 failures and
> their causes:
>
> | test | pre-fix cause | assertions failed |
> |---|---|---|
> | **18 (K6)** | `TypeError: permutation_null() got an unexpected keyword argument 'order_col'`; then `AttributeError: module 'screenkit' has no attribute 'within_group_acf1'`; then `KeyError: 'acf1_within_group'`. The refusal message check fails on its own terms (`acf1=False cyclic=False threshold=False`) because **there is no refusal** — pre-fix the anticonservative call simply returns a `p`. | 25 of 25 |
> | **19 (K7)** | `AttributeError: module 'screenkit' has no attribute 'per_entity_control'`; and the no-op verdict ends at *"…real reproduced)"* with no alternative named | 10 of 12 |
> | **20 (K4)** | `PartitionViolation: season column 'draft_year' has out-of-partition VALUES [2002, 2008, 2015, 2019]` — **raised on clean 2021–2024 data**; then `KeyError: 'violation_records'`, `KeyError: 'in_partition_anchor_cols'`; and `season_cols=['y_pts']` / `['not_a_column']` raise **nothing at all** | 14 of 16 |
> | **21 (K5)** | the README carries no K5 example, no `SCHEME_WITHIN_CYCLIC`, no `per_entity_control` and no false-assurance section | 3 of 6 |
> | **22 (K8)** | 6 distinct key tuples → **5 group codes**; `code('B',3.0) = code('C',NaN) = 2`; `detect_grouping_level` reports `n_groups = 5` | 3 of 4 |
>
> A fix without a failing-first test is not accepted here — **the suite's blind spots are what let
> all nine defects ship**.
>
> `python TESTS.py k4 k5 k6 k7 k8` runs a name-filtered subset, which is how that check was
> performed.

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
- **K0 (the date value gate)** — 21 assertions. The reporter's frame passes; all five
  `candi-DATE`-named columns (`str`, `float64`, `int64`, `int64`, `bool`) are skipped with the same
  *"name is X-like but VALUES are not"* wording the season branch uses; the real `game_date` is
  still checked and reports `[2021, 2022, 2023, 2024]`; a genuine 2026 date is caught **both** by
  default **and** under `date_cols=[]`; a 2026 date stored as a **string** is caught; naming a
  non-date column in `date_cols` raises an actionable `ValueError`; the whole call emits **zero
  warnings**; and `_is_date_valued` is unit-tested on datetime64 / float / int / date-string /
  feature-id columns.
- **K1 (screening flag, not verdict)** — 12 assertions. Two baselines built from `shift(1)` alone —
  so **neither can read the future by construction** — and the probe fires on them anyway
  (**+0.8959** vs **+0.8142**, dR2 **0.1397**). The verdict is required *not* to contain the old
  sentence, and required to offer the better-estimator explanation as an equal alternative. The
  genuine leave-one-out leak is still flagged, so no sensitivity was traded away.
- **K2 (`entity_swap_null`)** — 20 assertions. Decoding draws through a provenance-encoding value
  (`entity_code·1000 + position`) proves, over 20 draws, that swaps **never cross a season**, that
  **position 0 always receives the partner's position 0** and the last always the partner's last,
  and that values really do move (9,099 rows reassigned). A single-entity season block returns its
  own series **exactly**; an entity spanning two seasons **raises**. Calibrated under a true
  between-entity effect of zero (rejection **0.083**, mean p **0.451** over 60 replicates), and a
  real effect is detected at `real = 0.4381` against a null mean of `0.0225`, **p = 0.0025**.
- **K3 (`candidate_keys`)** — 6 assertions: list and tuple both raise `TypeError`, the message is
  484 chars naming the parameter, the type and the shape and echoing the caller's own column name,
  and both the mapping path and the default path are confirmed unchanged.
- **K6 (the serial-structure null)** — 25 assertions, and **the second demonstration in this suite
  that shows a failure rather than asserting an inequality.** 4 values of `rho_x` × 80 replicate
  datasets × 150 draws × 2 schemes = **192,000 permutation fits**, with the true effect **exactly
  zero at every `rho`**. At `rho_x = 0.95` the shuffle rejects **52.5 %** of the time against the
  cyclic shift's **6.2 %**; on the **iid control** the two agree (5.0 % vs 6.2 %) and their null
  widths agree to **1.02**. The gap tracks the measured autocorrelation at **`corr = +0.979`** and
  is monotone in `rho`. Mechanically: the shuffle drives the feature's within-group acf from
  `+0.7591` to `+0.0399`, the cyclic shift holds it at `+0.7397`, and the cyclic draws preserve
  each group's multiset to `0.0e+00`. The gate is tested from both sides — it refuses the
  autocorrelated feature with a message naming `acf1`, the threshold and the alternative, and it
  **does not** refuse an iid one. The row-order trap is tested directly: a scrambled frame reports
  `acf1 = −0.039`, `order_col` recovers `+0.779`, and the cyclic scheme warns.
- **K7 (the per-entity control)** — 12 assertions. The relabel arm is confirmed vacuous at
  `sd = 1.1e-16` over 1 distinct draw value (the reporter measured `5.207e-17`); the genuine arm
  moves at `sd = 0.045205`, `p = 0.0050` while preserving each player's marginal to `0.0e+00`. Both
  degenerate cases are tested and both are *reported*, not silently passed: a `stat_fn` that
  ignores the feature makes **both** arms vacuous (`DID NOT MOVE`), and one that depends on entity
  **identity** breaks arm 1 (`NOT A NO-OP`, `sd = 1.37e+01`).
- **K4 (direction in the partition guard)** — 16 assertions, one per reproduction plus the doors.
  The reporter's clean frame passes with `draft_year` recorded under `historical_year_cols` and
  `in_partition_anchor_cols = ['game_date', 'season']`; a `draft_year` of **2026** still raises;
  the two cases are distinguished by `violation_records[…]['direction']` **without parsing prose**;
  `season_cols=['season']` no longer hides the 2026 in `source_season`; naming `draft_year` in
  `season_cols` makes its **past** values fatal. And the door the fix could itself have opened is
  closed: a frame whose season column really holds **2019** observation rows is **still rejected**,
  because a partly-in-partition column is not an anchor and cannot excuse itself.
- **K5 (categorical friction)** — 6 assertions: the refusal contract is pinned, the bijective
  codebook is exercised **end to end** through `permutation_null`, and the README is required to
  carry the worked example. A documentation fix gets a test too.
- **K8 (NULL keys)** — 4 assertions: 6 key tuples → 6 group codes (pre-fix 5), `('B',3.0)` and
  `('C',NaN)` are no longer the same group, `detect_grouping_level` reports `n_groups = 6`, and a
  NULL-free key is unchanged.

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
| `EntitySwap`, `entity_swap_null` (K2) | `E0_I0016_efficiency_predictors/ep_base.py :: EntitySwap` / `entity_swap_null` — built there because the kit had no valid scheme for it |
| `SCHEME_WITHIN_CYCLIC` (K6) | `E1_I0021_heterogeneity_diagnostic/hd_base.py :: cyclic_shift_within_groups` — built there because the kit had no serial-structure-preserving null |

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
