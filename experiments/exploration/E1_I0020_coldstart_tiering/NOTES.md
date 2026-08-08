# E1_I0020 — cold-start tiering and smart placeholders

Screen directory: `experiments\exploration\E1_I0020_coldstart_tiering\`
Partition: scored rows 2022–2024; season 2021 used **only** as observed outcomes seeding the
walk-forward prior pool. 2025/2026 never read, joined, plotted or described in any result.

---

## 1. TIME-WINDOW TABLE

Constraint 2 requires this to cover **features, placeholders AND inference steps**, because D085
showed the leak can enter through the inference machinery rather than the features.

### 1a. Inputs

| artifact | window read | manifest status |
|---|---|---|
| `E0_I0014.../analysis_frame.parquet` | 2022–2024 scored player-games | **UNVERIFIABLE** (no manifest) — frozen D076 output, value-checked here |
| `E0_I0015.../decomp_frame.parquet` | 2022–2024 | **UNVERIFIABLE** (no manifest) — frozen D081 output, value-checked here |
| `data\masters\master_player.parquet` | filtered to 2021–2024 at load | `asof_granularity=row` → USABLE_IF_FILTERED |
| `data\reference\player_bios.csv` | filtered to season ≤ 2024 at load | **UNVERIFIABLE** (no manifest) — see §4 |
| `data\w1_truth\player_game_availability.csv`, `roster_asof.csv` | **NOT OPENED** | artifact-granular, `fit_through_season: 2026` |

### 1b. Features and derived quantities

| quantity | what it reads | forward-looking? |
|---|---|---|
| `pl_games_prior` | player's own appearances strictly earlier in the same season (`shift(1).cumsum()`) | no |
| `pl_career_games_prior` | player's own appearances strictly earlier, across seasons, **inside 2021–2024** | no (window-truncated — see §5) |
| `pl_minutes_prior`, `pl_prior_season_games`, `pl_is_rookie_window`, `pl_teamgames_since_appear` | frozen D076 columns, all `shift(1)`-based | no |
| `own_season_{pts,minutes,ppm}` | `shift(1).expanding().mean()` inside (season, player), **appearances only**, over the COMPLETE master record | no |
| `own_career_{...}` | same, grouped by player across seasons | no |
| `lg_{...}` (cold fallback) | expanding mean over games strictly earlier in the same season | no |
| `depth_rank` / `depth_bucket` | each rostered player's expanding prior-appearance mean minutes, ranked inside (game_id, team_id). Reads the player's own and teammates' **strictly prior** games; box membership used only as the roster list | no |
| `pos_group`, `draft_round`, `draft_pick`, `draft_bucket` | fixed at or before league entry; knowable before a player's first game | no |

`.shift(1)` is applied **before** every `.expanding()` / `.cumsum()`, without exception.

### 1c. Placeholders — the walk-forward rule

Every placeholder for target season **S** is estimated on appeared player-games of seasons **< S**,
inside 2021–2024, and is asserted per fold (`assert len(pool) and pool.season.max() < S`).

| target season | estimation pool | pool rows |
|---|---|---|
| 2022 | {2021} | 3,885 |
| 2023 | {2021, 2022} | 8,404 |
| 2024 | {2021, 2022, 2023} | 13,301 |

| placeholder | fitted on | reads season S? |
|---|---|---|
| P0 champion | **nothing — scored as stored, never refitted** | n/a |
| P1 `ref_D076` / P1full running mean | the player's own strictly prior same-season games | no |
| P1c career mean | player's own strictly prior games across seasons | no |
| P2 position prior | shrunk mean by `pos_group`, prior seasons | no |
| P3 draft prior (binned + 3-parameter OLS on log pick) | prior seasons | no |
| P4 team-role prior | shrunk mean by `depth_bucket`, prior seasons | no |
| P5a/P5b crosses, P5c additive | prior seasons | no |
| P5d/P5e blends | λ(n)=n/(n+k) — a **fixed functional form**, not fitted; combines P1full/P1c with P5c | no |

Shrinkage constant for group means **preregistered at k = 200 player-games** before any result was
computed; swept over {0, 50, 200, 1000} in `shrinkage_sensitivity.csv` and the conclusion is
unchanged at every value.

### 1d. Inference steps — the D085 column

| step | what it consumes | forward-looking? |
|---|---|---|
| `paired_forecast_comparison` | two already-computed forecast vectors and y on the same rows; clusters = (season, player_id) | no — nothing is recomputed inside a draw |
| `permutation_null` | permutes the **assignment** of already-computed prior values; `block_col="season"` keeps every swap inside its season | no |
| depth-slot permutation | reshuffles depth buckets within (game_id, team_id) — one roster, one night | no |
| cluster bootstrap (handover curve) | resamples (season, player_id) blocks with replacement | no |
| `noop_placebo` | permutes a column the statistic does not consult | n/a — confirmed no-op, sd = 0.000e+00, 1 distinct draw value |

**No entity-season-mean decomposition, no leave-one-out, no leave-one-season-out, and no
full-season aggregate is used anywhere in this screen — including inside the nulls.** That is the
specific D085 failure mode and it is absent by construction.

---

## 2. KIT FEEDBACK — I am the seventh user

### K4 (HIGH) — `assert_partition` raises `PartitionViolation` on clean, wholly in-partition data

Full write-up and four reproductions in `KIT_DEFECT_K4_REPRO.py` / `run_log_kit_defect_K4.txt`.

A frame whose every observation sits in 2021–2024 is **rejected** if it carries a year-valued player
attribute — `draft_year` (values 2002–2020) here, but `birth_year`, `grad_year`, `founded` are the
same shape.

**This is not a repeat of K0.** K0 was a name match with no value gate ("candi-DATE"), and its fix
installed the invariant *a substring match on a column name may only ever nominate a column for a
value test; it may never, by itself, cause a violation.* **K4 satisfies that invariant and fails
anyway.** `_is_season_valued` is asked "are these values years?", answers **yes, correctly**, and
the column is then checked against the partition it legitimately predates.

The defect is the question the value gate asks:

| the gate asks | the partition needs to know |
|---|---|
| are these values plausible **years**? | is this column the **observation season of the row**? |

Every year-valued attribute of a person or organisation answers yes to the first and no to the
second.

**Direction is ignored, and that is the actionable half.** The guard exists to stop 2025/2026 — the
future — from entering. `draft_year = 2008` cannot be a holdout leak. Reproduction 3 shows the
harmless-history case and a genuine 2026 case returning violation **strings of the same shape**, so
a caller cannot tell them apart without parsing the guard's own prose — the textual check this
module exists to forbid.

**The obvious workaround is a false-pass door** (reproduction 4): `season_cols=["season"]` silences
the false alarm *and* a genuine 2026 leak in `source_season`, a column the caller never named. That
is precisely what K0 warned against, so "callers should pass season_cols" cannot be the fix.

Suggested repair (reported, **not applied** — `screenkit.py` is outside this screen's write scope
and two other agents are running against it):

1. Split the season branch's verdict by direction — `VIOLATION_FUTURE` (any value > max(allowed))
   stays fatal; `OUT_OF_RANGE_PAST` (all values < min(allowed)) becomes a recorded, non-fatal
   `historical_year_cols` entry **for auto-detected columns only**. A column the caller *names* in
   `season_cols` stays strict in both directions — the same asymmetry B2 already established for
   `date_cols`.
2. Return violations as structured records `{col, kind, values, direction}`, not only strings.
3. Add `_ATTRIBUTE_YEAR_TOKENS` as a **nomination-only** hint choosing which report the value test
   writes to — never deciding anything by itself.

A regression test that fails against the current module: reproduction 1 must return `ok=True`;
reproduction 4's `source_season` 2026 must still raise; a `draft_year` of 2026 must still surface.

**What this screen did instead**, so no result depends on the defect:
`ct_base.assert_partition_adjudicated` calls the kit with `raise_on_violation=False`; **any** flagged
value ≥ 2025 is fatal in **any** column; a flagged column is tolerated only if it is on a one-column
explicit allowlist **and** every flagged value is strictly earlier than the partition; and the
strict unmodified kit check is **also** run on the frame with the allowlisted column dropped, so
nothing else gets a weaker check. Both checks pass at every write.

### K5 (LOW, a nit, not a defect) — `permutation_null` refuses string categoricals

`permutation_null` raises `TypeError` on a `str`/categorical feature: *"the kit will not guess an
encoding for you."* That refusal is **correct** — it is the safe failure mode and the message names
the fix. Reporting it only as friction: group priors over categorical labels (position, draft
bucket, depth bucket) are among the most natural things to permute in this program, so most users
will hit it. A worked categorical example in the README would remove the round trip.

This screen declared a bijective integer codebook (recorded in `FINDINGS.json ›
kit_defects.K5... .categorical_codebooks`), applied it identically to the real frame and every draw,
and mapped back to the label inside `stat_fn`. No arithmetic is done on the codes, so no ordering is
implied.

### Things the kit got right and that mattered here

- `r2_of_forecast` vs `r2_plain` — the P3 fix. The gap on the champion's points is real
  (0.4694 as-is vs 0.4747 refit) and I would have published the wrong one without the two names.
- `paired_forecast_comparison` did the entire headline. Identical forecasts gave `p = 1.0` and
  `dR2 = -0.0` exactly (negative control 1), which is the assurance the docstring promises.
- `detect_grouping_level` returned `NO_COARSER_LEVEL_EXISTS` for `depth_bucket` with
  `recommended_permutation_level = None` — the P2 fix working exactly as designed. I read the
  status, not the field, and chose the game-team scheme deliberately.
- `check_manifest` returning `UNVERIFIABLE` for three of four inputs is exactly the right answer and
  forced the structural argument in §4 to be made explicitly rather than assumed.

---

## 3. WHERE I COULD HAVE CHEATED — full disclosure

**1. The baseline I scored against. This is the big one.**
D076's `ref_*` is an expanding mean over *the champion's scored rows*, and the champion scores only
71 of 479 true first appearances. For 404 of 475 player-seasons its first scored row has no prior
row of its own frame, so the "running mean of the player's own prior games" is, on precisely the
rows this screen is about, **the league mean wearing that name**. Scoring my placeholders against it
would have handed me a points dR2 of **+0.3165** instead of **+0.1099** — nearly three times the
real number, large, significant, and it survives every permutation null. That is D087's signature
exactly. I built `P1full` (the complete record from `master_player`) and every contrast is reported
against **both**. The inflated numbers are in `placeholder_comparison.csv` under
`dr2_vs_P1refD076`, labelled, so the difference is auditable rather than quietly corrected.

**2. The blend constant k was chosen after seeing results.** `k = 2` was picked from the grid
{1, 2, 3, 5, 10} because it is the best compromise across points, minutes and ppm; k = 1 is better
on minutes, k = 5 better on ppm. All five are reported for every cell in
`placeholder_comparison.csv` and `d087_decomposition.csv`, and the *decomposition verdict* —
structure beats league-shrinkage — holds at every k with p = 0.0005. The group-mean shrinkage
constant (k = 200) **was** preregistered, and is swept.

**3. I could have stopped at "the blend beats the running mean" and shipped a win.** The blend
confounds shrinkage with structure. The `BLEND_LEAGUE` control — identical construction, shrinking
toward the plain league mean — was built specifically to try to kill my own result. It did not
(shrinkage alone contributes −0.027 on points and −0.161 on minutes), which is why the finding
stands. Had it succeeded the headline would have been "shrinkage is the whole effect".

**4. I could have dropped the position prior once it failed.** It is the user's own words and it
does not work (permutation p = 0.20; adds −0.0014 to points). It is reported at full length in the
component ladder and in the permutation table, and the recommendation says to drop it.

**5. Selection on the zero-games population.** 14.8% coverage of true debuts is a severe selection
and it makes the strongest-looking cell in the screen (n = 22, dR2 +1.16) the least trustworthy. It
is stated in `FINDINGS.json`, in `TIER_RULE.md`, and beside every number in that section, rather
than in a footnote.

**6. The tier variable.** I was asked to derive the boundary from where skill crosses zero, and did
— it crosses at 3. The *choice to express the rule as the champion's own `is_fallback` flag* rather
than as a count was made **after** observing that the two coincide (all 999 rows with <3 priors are
flagged; 0 escape). That is a post-hoc reformulation of a pre-derived boundary, and both forms are
given.

**7. ppm has a soft baseline.** `P1full` is a *bad* forecast of points-per-minute (R² = −0.21 —
a ratio of two noisy small numbers), so almost anything beats it and the structural priors look
great on ppm. The honest comparator for ppm is the champion, which is better than P1full there.
Both contrasts are reported; no ppm claim rests on the P1full comparison.

**8. I described 2025/2026 row *counts* once.** The initial inspection (`run_log_s00.txt`) printed
`player_bios.csv` season counts before filtering, which included 2025 and 2026 row counts. No
2025/2026 **value** entered any analysis, table, model or result — every loader filters at the
filter-point and `assert_partition` runs on every frame — but the count was printed, and I am
recording it rather than deleting the log. `s02` redoes the same verification restricted to
2021–2024 and that is the version every result uses.

---

## 4. `player_bios.csv` — the structural argument, made explicitly

The manifest is missing, so `check_manifest` returns **UNVERIFIABLE**, which is never a pass. The
file is used anyway on a stated structural argument, tested on **column values** inside 2021–2024:

| test | result | what it rules out |
|---|---|---|
| age delta across consecutive player-seasons | **+1 in 100.0%** of 342 pairs | a replicated current-state pull (which gives 0 everywhere) |
| `height_inches` varies within player | 7.07% of multi-season players | as above |
| `weight_lbs` varies within player | 23.91% | as above |
| `draft_year` / `draft_round` / `draft_number` vary within player | **0.00%** | confirms immutable facts behave as immutable facts |
| join coverage onto scored rows | 475/475 season-player keys; `position_raw` 100%, draft fields 90.9% | — |

**Residual caveat, not resolved:** `position_raw` varies within player in 0.00% of cases, so this
screen **cannot** distinguish "position never changes" from "position is a current-state field
replicated backwards". This is defused by the *result* rather than by evidence — the position prior
carries no signal (p = 0.20) and is dropped from the recommendation, so nothing recommended depends
on it. Anyone who later wants to use position must resolve this first.

---

## 5. Other honest limits

- **`pl_career_games_prior` is truncated at 2021**, because `master_player` is filtered to the
  partition. A 2022 row with "zero career appearances" is a player with no 2021 appearance — a
  genuine rookie *or* a returning player whose history predates the window. 11 of the 22
  zero-career rows have `draft_year == season`; 5 are undrafted. The distinction cannot be made
  sharper without reading outside the partition, which is not permitted.
- **The tier is defined on the points fallback flag.** `minutes__is_fallback` and `fga__is_fallback`
  are near-identical here but were not separately audited.
- **62 returning-from-absence rows** are in the tier by virtue of the flag, not the count. They are
  reported as their own sub-cell (`sub: fallback with >=3 priors`), where no placeholder beats the
  complete running mean significantly — the tier's gain does not come from them.
- **The blend can go slightly negative on points** (min −0.10). Clip at 0 in production; the effect
  on every number here is negligible and no result was clipped.

---

## 6. Files

| file | what it is |
|---|---|
| `FINDINGS.json` | every result, structured |
| `TIER_RULE.md` | the operating rule in plain language, for the user |
| `NOTES.md` | this file |
| `ct_base.py` | loaders, guards, prior estimation, scoring, K4 adjudication |
| `s00_inspect.py` … `s06_findings.py` | the screen, in order |
| `KIT_DEFECT_K4_REPRO.py` | standalone minimal reproduction of the kit defect |
| `run_log*.txt` | captured output of every step |
| `tier_frame.parquet`, `prior_pool.parquet`, `placeholder_frame.parquet` | working frames |
| `skill_versus_tier.csv`, `crossover_curve.csv`, `tier_sizes.csv` | step 2 |
| `placeholder_comparison.csv`, `placeholders_{pts,minutes,ppm}.csv`, `shrinkage_sensitivity.csv` | step 3 |
| `d087_decomposition.csv`, `component_decomposition.csv`, `permutation_nulls.csv` | step 3b/3c |
| `zero_games_case.csv` | step 4 |
| `handover_curve.csv` | step 5 |
| `pooled_operating_rule.csv`, `per_season_stability.csv`, `negative_control_random_tier.csv` | step 7 |
| `permutation_draws_datapoor_pts.csv`, `perm_draws_*_pts.csv`, `noop_placebo_draws.csv` | permutation draws |
