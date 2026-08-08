# E1_I0012_survivor_2021drop — is the last surviving lead dying on its own?

**Non-claiming.** No registry entry, no preregistration, no leaderboard row, no REPORT.md. This is a
single narrow re-run whose only job was to decide whether an existing exploration lead deserves any
further spend.

**Answer: yes, it is dying on its own. KILL it. The holdout was not touched and does not need to be.**

---

## 1. The question

`E0_I0012_layer3_noncollinear` swept 30 formulation × target cells and killed 29. The one survivor was
`formulations[13]`: **opponent pace × the player's own pregame rebound rate, target rebounds**
(`F3_style_orthogonalized__dpace`). It looked genuinely good — pooled ΔR²(O×M) = 0.001071 with 0/200
permutations at or above it, split-half reliability 0.808, collinearity with overall opponent defence
of only +0.108, and it survived four separate robustness checks including a decisive asymmetry test.

But its per-season slope decayed monotonically: **+0.356 → +0.335 → +0.167 → +0.064** across
2021→2024. The pooled number was carried by the two oldest seasons, and 2024 — the season immediately
before the holdout — was nearly zero. The E0 screen's own notes flagged this as the caveat that should
govern any decision about the lead, and named the fix: re-run with 2021 dropped entirely.

- If the 2022–2024 trend **still decays** → the lead is dying on its own → abandon it, don't spend holdout.
- If dropping 2021 **flattens the decay** → 2021 was an artifact of that season's odd structure
  (COVID-era schedule, roster churn, only 2,128 analysis rows) → the lead survives in reduced form.

## 2. Anchor first

A re-run you cannot anchor is not interpretable, so before anything else the published all-four-season
result was reproduced from scratch with this harness, importing E0's `base.py` and `f34_style_rest.py`
unmodified rather than reimplementing anything.

| | reproduced | published |
|---|---|---|
| pooled ΔR²(O×M) | 0.0010713241 | 0.0010713241 |
| β 2021 | +0.3559976797 | +0.3559976797 |
| β 2022 | +0.3347762429 | +0.3347762429 |
| β 2023 | +0.1674330836 | +0.1674330836 |
| β 2024 | +0.0640167956 | +0.0640167956 |

**Exact to every printed digit, |diff| = 0.0.** Per-season n, R²_base, ΔR²(M), β(M) and the whole
collinearity vector match too. So everything below is the season drop, not the harness.

## 3. The re-run — 2021 dropped

2021 was removed and O, D, O×D, M and the residualisation of M were all recomputed within 2022–2024
only (n falls 10,167 → 8,039).

| season | β(O×M) in E0, all four seasons | β(O×M) after dropping 2021 | change |
|---|---|---|---|
| 2022 | +0.3348 | **+0.3225** | −3.7% |
| 2023 | +0.1674 | **+0.1615** | −3.6% |
| 2024 | +0.0640 | **+0.0617** | −3.6% |

**Dropping 2021 does essentially nothing.** The decay is not something 2021 was causing; it is internal
to 2022–2024 and reproduces almost perfectly with 2021 gone.

Pooled on 2022–2024: **ΔR²(O×M) = 0.000809**, placebo mean 0.0000925, sd 0.000126, **1 of 400
permutations at or above it** (frac_ge = 0.0025). The placebo sd widened from 0.0000928 to 0.000126 as
expected with the smaller n, and the effect is compared to that wider floor, not the old one.

A formal decay test — adding a season-index interaction, `O × Mres × t` — gives a coefficient of
**−0.1387 per season** against a midpoint level of +0.1699. One season past the partition that
extrapolates to about +0.03. The decay term by itself carries ΔR² 0.000367, roughly 45% of the size of
the whole pooled effect it is eating.

Dropping 2021 at the *load* stage instead (2021 never read at all, so 2022 loses its prior-season
shrinkage prior) gives the same verdict, slightly worse for the lead: betas +0.418 → +0.147 → +0.056,
pooled ΔR² 0.000503, decay coefficient −0.1634.

## 4. What a confirmation run would actually be testing

The pooled 0.000809 is not evidence the lead is alive. It is 2022 wearing a pooled label:

| slice | n | pooled ΔR²(O×M) | placebo mean | placebo sd | frac ≥ real |
|---|---|---|---|---|---|
| 2022–2024 | 8,039 | 0.000809 | 0.0000925 | 0.000126 | **0.0025** |
| 2023–2024 | 5,555 | 0.000269 | 0.000125 | 0.000178 | 0.118 |
| 2024 alone | 2,771 | 0.000111 | 0.000259 | 0.000385 | **0.488** |

Per-season ΔR² tells the same story directly: 2022 = 0.002944, 2023 = 0.000735, 2024 = 0.000111.

**In 2024 the effect is indistinguishable from noise — its point estimate is actually *below* the mean
of its own placebo distribution, and 195 of 400 permutations beat it.** The two seasons nearest the
holdout, taken together, do not clear their own placebo either. A confirmation run on 2025/2026 would
be testing something that had already reached zero a year before the holdout starts.

## 5. Verdict

> **KILL.** `F3_style_orthogonalized__dpace` / rebounds is abandoned. Dropping 2021 does not flatten
> the decay — the 2022–2024 betas are unchanged to within 4%, the decay stays monotonic with a
> season-trend coefficient of −0.139, and by 2024 the effect is placebo. No 2025/2026 confirmation
> budget will be spent on it.

This is the branch the worklist anticipated and it is a clean outcome: one cheap re-run on data we
already had, and the last lead out of a 30-cell sweep is closed out without touching the holdout. The
holdout remains unspent.

## 6. Limits — what this does *not* settle

- **It does not explain the decay.** Whether the league's rebounding-versus-tempo relationship really
  changed after 2022 or the `dpace` instrument degraded is untested, and is no longer worth testing for
  this lead's sake.
- **It does not run the E0 notes' follow-ups 2–4** (cleaner supply-side pace instruments such as
  opponent shot attempts or missed shots per 48; splitting rebounds into OREB/DREB; heterogeneity by
  player rebound volume). Those were deliberately skipped. They are ways to *strengthen* a lead, and the
  prior question — is the lead alive at all — has now been answered no. If someone later wants the
  underlying mechanism rather than this specific formulation, they are still open, but they should be
  proposed as new work, not as a rescue of this one.
- **The recency slices are small** (n = 2,771 and 5,555) with correspondingly wide placebo bands. They
  are reported as evidence of *absence of signal at usable precision*, not as precise effect estimates.
- The other 29 cells E0 killed were out of scope and untouched.

## 7. Partition and conventions

- **Seasons:** 2022–2024 for every headline number; 2021 appears only in the Stage A reproduction
  anchor. **The 2025/2026 confirmation holdout was never read, joined, filtered against, counted,
  plotted or described.**
- Filtering happens in `base.load_player()` / `base.load_team()` immediately after `read_parquet`, and
  every further restriction is marked `# FILTER-POINT` and passed through `guard()`, which prints
  `sorted(season.unique())`, asserts the season set is a subset of what's allowed, and asserts no
  intersection with {2025, 2026}. A final re-assertion runs before every write. All season lists are
  visible in the run logs.
- **Artifact contamination (13.2.2):** tested via `base.check_manifest()`, i.e. on
  `asof_granularity == "row"`, not on `fit_seasons`. Both masters are `row`, so the row filter bounds
  them and both are usable. No raw byte-scan for "2025"/"2026" was run — that check has produced a false
  violation in this program by matching row counts and digit runs inside floats.
- **R²:** plain unweighted OLS, inherited unchanged from `base.r2`, to stay comparable with E0. The ~8%
  understatement defect reported elsewhere in the program affects a *weighted*-R² helper and touches
  nothing here.
- **Placebos:** `f34_style_rest.placebo()` unchanged — it permutes the *assignment of an already-computed
  value to rows* within season. No grouping key is permuted and no aggregate recomputed from one; that
  no-op's signature is sd exactly 0.000000. Every sd reported here is non-degenerate (minimum observed
  0.000105), and 400 draws were used throughout.
- **Write scope:** this directory only. `base.OUT` was re-pointed here at import so no reused helper
  could write into E0, and `PYTHONDONTWRITEBYTECODE=1` kept even `.pyc` files out of it.
  `E0_I0012_layer3_noncollinear` was read from and not modified in any way.

## 8. Files

| file | what it is |
|---|---|
| `run_drop2021.py` | Stage A anchor, Stage B headline 2022–2024, Stage C load-stage variant, trend test |
| `run_recency.py` | Supplement: 2023–2024 and 2024-alone slices |
| `run_log_drop2021.txt`, `run_log_recency.txt` | Full stdout, including every printed season list |
| `results_raw.json`, `results_recency.json` | Machine-readable results |
| `placebo_draws_*.csv` | The 400-draw permutation distributions behind each placebo line |
| `FINDINGS.json` | Structured findings, verdict, partition block, limits |
