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
cmp = sk.null_width_comparison(stat_fn, df, lvl["recommended_key_cols"],
                               400, seed=1, feature_col="my_feature",
                               block_col="season", verbose=True)  # 4. verdict + inflation factor
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
rediscovering it).

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
| `r2_plain(y, X)` | Unweighted OLS R2 with SST about the **unweighted** mean — the adopted D069 convention. |
| `delta_r2_plain(y, X_base, X_full)` | Incremental plain R2 with a **shared** SST, so it is exactly `(SSE_base − SSE_full)/SST`. |
| `r2_weighted_standard(y, X, w)` | Weighted R2 with SST about the **weighted** mean — the textbook form. |
| `delta_r2_weighted(...)` | Incremental standard weighted R2, shared SST about `mu_w`. |
| `wls_r2_DEFECTIVE(y, X, w)` | Bit-comparable reproduction of the **broken** frozen convention. Never for a new result. |
| `detect_grouping_level(df, feature_col, ...)` | Reports distinct values and constancy at each candidate key, and names the **coarsest constant level** = the correct permutation level. |
| `permutation_null(stat_fn, data, group_col, n_draws, seed, *, feature_col, ...)` | Permutes **only the assignment** of already-computed values, at an **explicitly named** level; refuses to default to rows. |
| `null_width_comparison(...)` | Runs both nulls with the same seed and statistic and reports `sd_correct / sd_row`. |
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

---

## What `TESTS.py` proves

`python TESTS.py` → **49 assertions, all passing, exit code 0** (~142 s wall clock; the critical
test does 48,000 permutation fits). Full captured output is in `run_log.txt`.

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
