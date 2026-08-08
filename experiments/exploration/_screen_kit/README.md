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
| `permutation_null(stat_fn, data, group_col, n_draws, seed, *, feature_col, scheme=..., ...)` | Permutes at an **explicitly named** level; refuses to default to rows. `scheme="between"` kills the group level, `scheme="within"` preserves it and kills only the within-group alignment. |
| `null_width_comparison(...)` | Runs both nulls with the same seed and statistic and reports `sd_correct / sd_row`. |
| `var_share_between(data, feature_col, group_col)` | Fraction of a feature's variance living **between** groups — tells you which `scheme` is actually a null. Exactly `1.0` for a constant-within feature, exactly `0.0` when all group means are equal. |
| `paired_forecast_comparison(y, yhat_a, yhat_b, groups, ...)` | **Forecast vs forecast on the same rows.** Paired loss difference, null by sign-flipping whole **clusters**; refuses a `None` clustering level exactly as `permutation_null` does. |
| `entity_swap_null(stat_fn, data, entity_cols, ...)` | **The between-entity question for a feature that varies *within* the entity.** Swaps whole entity-season series inside a season, preserving series length and temporal shape. The only valid scheme when `detect_grouping_level` finds no constant level. |
| `EntitySwap(df, entity_cols, date_col=...)` | The swapper itself, exposed so one grouping can be reused across many candidates. |
| `noop_placebo(stat_fn, data, n_draws, transform=None)` | Detects a placebo that is secretly the identity; asserts `sd < 1e-15` and **returns the observed sd**. |
| `assert_partition(df, ...)` | Value-based 2021–2024 check on parsed dates and season-valued columns; never reads text, and **never treats a name match as a violation** — a date-named column must be *date-valued* too. |
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

## What `TESTS.py` proves

`python TESTS.py` → **159 assertions, all passing, exit code 0** (~95–105 s wall clock; the critical
test does 48,000 permutation fits). Full captured output for all three runs is in `run_log.txt`.

> **49 → 100 → 159.** The original 49 are unchanged apart from **one rewritten assertion** in TEST 3
> that had encoded the P2 defect; the 100 are unchanged outright. All the hard-won numbers are
> bit-identical after every repair: the 73.3 %-vs-3.3 % over-rejection demonstration, the 39.19x
> median null-sd inflation, the exactly-`1.0000000000` uniform-weight identity, the `0.999310`
> centered-response ratio, the 15.3117 % dR2 shortfall, the `_team_season_2025` trap-3 partition
> regression, the P2 `None`-not-`"row"` contract, and the 0.735-vs-0.045 paired demonstration.
>
> **Every one of the 51 P-fix assertions was verified to fail against the pre-D082 module** (git
> `374fce9`): TEST 9 → the `numpy boolean subtract` `TypeError`; TEST 10 → `recommended = 'row'`;
> TESTS 11–13 → `AttributeError` for each function that did not yet exist.
>
> **Every one of the 59 K-fix assertions was likewise verified against the pre-K module** (git
> `56dc793`), by running this same `TESTS.py` against a copy of it extracted with `git show`.
> Pre-fix, the run reaches only **116 of the 159** assertions and **11 of the 16 it reaches inside
> TESTS 14–17 fail**; the remaining 43 are unreachable because three of the four test functions
> abort. The five that *do* pass pre-fix are positive controls and fixture-sanity checks
> (*"a genuine 2026 date is still caught"*, *"a proper mapping still works"*, …) — **not one
> assertion that encodes a fix passes against the pre-fix code**. Causes:
>
> | test | pre-fix cause |
> |---|---|
> | **14 (K0)** | `PartitionViolation: date column 'mae_with_candidate' has out-of-partition YEAR VALUES [1970]` — raised on clean 2021–2024 data; then `TypeError: assert_partition() got an unexpected keyword argument 'include_datetime_dtype_cols'` |
> | **15 (K1)** | verdict contains *"That is only possible because it CONTAINS the future"*; then `KeyError: 'screening_flag'` |
> | **16 (K2)** | `AttributeError: module 'screenkit' has no attribute 'EntitySwap'` |
> | **17 (K3)** | `AttributeError: 'list' object has no attribute 'items'` (38 chars, naming neither the parameter nor the shape) |
>
> A fix without a failing-first test is not accepted here — **the suite's blind spots are what let
> all seven defects ship**.
>
> `python TESTS.py k0 k1 k2 k3` runs a name-filtered subset, which is how that check was performed.

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
