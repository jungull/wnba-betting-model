# E0 I0010 — Positional matchup interaction (family F_POSITIONAL_MATCHUP)

**Verdict: `kill` for points, `kill` for rebounds, `kill` for assists.**
This is an E0 exploration screen. It produces a LEAD or a kill, never a RESULT. No significance
claim, no promotion, no leaderboard entry. Time-boxed.

## The hypothesis as registered

> Opponent defensive allowance **to a player's position group** interacts with that player's own
> context-normalized tendency, and the interaction carries signal beyond the two additive main
> effects — for **points, rebounds and assists separately**.

Deliberately built to be pregame-observable and to require **no on-court lineup attribution**
(the ~72% side-of-play defect from I0003 that confounded the earlier rebound screen). No
clock-time possession join is used anywhere in this experiment.

## Partition compliance (GRAPH_POLICY §13.2)

Seasons **2021, 2022, 2023, 2024 only**. The filter is applied immediately after every load,
before any other computation, and marked `# FILTER-POINT`:

- `build_features.py` line ~52 and `analyze.py` line ~60: `mp = mp[mp["season"].isin([2021,2022,2023,2024])]`
  on the line after `read_parquet`, followed by `assert set(mp["season"].unique()) <= set(PARTITION)`.
- `diagnostics.py` line ~35: same pattern, same assert.
- Re-asserted before every CSV write.

2025/2026 rows were never present in any dataframe used for any computation, plot, count or
printed statistic. `run_log_build.txt` line 5 prints the raw file's season list
(`2021…2026`) *before* the filter — that print is the documentation that the filter had
something to remove, and is the only place the excluded seasons are enumerated.

### Artifact safety check (§13.2.2) — manifest quoted

`data/masters/master_player.parquet.manifest.json`, read before use, says verbatim:

```
"asof_granularity": "row",
"bound_source": "game_date via asof_invariant.bound_from_dates",
"fit_seasons": [2021, 2022, 2023, 2024, 2025, 2026],
"fit_through_season": 2026,
"notes": "As-of bound derived from game dates via bound_from_dates. Any observed_time column in
          this artifact is a LOCAL FILE MTIME and is deliberately NOT used as an as-of bound."
```

`asof_granularity` is `"row"`, **not** `"artifact"` — therefore filtering to 2021-2024 is
sufficient and this artifact is usable without a rebuild. This is exactly the case the
row-granularity rule covers, and it is why the I0008 caveat (which predates the granularity
rule and treated `fit_through_season: 2026` as disqualifying on its own) does not apply here.
`master_team.parquet.manifest.json` is identical in every relevant field; it was checked but in
the end not needed — everything came from `master_player`.

### Partition verification on the actual output bytes

`verify_partition.py` → `run_log_partition_verification.txt`. For every file this experiment
wrote it (1) asserts the `season` column ⊆ {2021,2022,2023,2024}, (2) asserts the date column
falls in range, (3) byte-scans for any ISO date in 2025/2026, (4) byte-scans for bare
2025/2026 tokens and prints each with context.

```
features_ast.csv          [2021, 2022, 2023, 2024]   2021-05-16..2024-09-19   0 bad dates
features_pts.csv          [2021, 2022, 2023, 2024]   2021-05-16..2024-09-19   0 bad dates
features_reb.csv          [2021, 2022, 2023, 2024]   2021-05-16..2024-09-19   0 bad dates
player_game_features.csv  [2021, 2022, 2023, 2024]   2021-05-16..2024-09-19   0 bad dates
placebo_draws_{pts,reb,ast}.csv  (no season column — 200 permutation R² draws)  0 bad dates
RESULT: PARTITION VERIFIED CLEAN
```

Every remaining bare `2025`/`2026` token is prose in a comment, a log line documenting the
pre-filter season list, or the verifier's own regex description — all 7 are printed with
context in the verification log.

**One real catch from this check**: the first version of `features_*.csv` carried
`observed_time` straight through from `master_player`, a mid-2026 **local file mtime** (the
manifest explicitly says it is not an as-of bound). Not season data and not leakage, but it put
2026 date bytes in my outputs. The column is now dropped before every write and the byte scan
is clean. Worth propagating: the master carries a build-timestamp column that will silently
land in any downstream artifact that does `to_csv` on the full frame.

## Inputs

`data/masters/master_player.parquet` only. 33,712 × 78 raw → 21,462 rows after the partition
filter → 19,642 Regular Season (playoffs excluded, 1,820 rows) → 16,574 with `minutes ≥ 1` and
`possessions > 0`.

## How position group was derived, and what it costs

**`master_player` has a `position` column, but it is not a position field.** It is populated on
exactly 8,880 of 16,574 rows (53.6%), and every single one of those rows is `starter_flag == 1`
(labelled & non-starter = 0). The counts are exactly 2×G, 2×F, 1×C per team-game — i.e. it is a
**starting-lineup slot label**, not a scouting position, and it is completely missing for
bench players.

**Route taken:** for each player-game, position group = the **modal starting-slot label over
that player's games strictly before the current game date** (expanding, across seasons). A
player plays at most one game per date, so a within-player `shift(1)`-equivalent is exact.

Why this route: it is pregame-observable, and — crucially — it is derived from *lineup slot*,
**not** from points/rebounds/assists. That sidesteps the circularity the brief warns about,
where a position proxy built from the same stats being predicted manufactures the interaction.
I did not need the prior-season statistical-profile fallback at all.

**What it costs, stated plainly:**

- Coverage: 13,849 / 16,574 pooled rows (83.6%) get a group; 89.7% of the `minutes ≥ 10`
  analysis rows. Everything else is dropped.
- Coverage is uneven at the partition boundary: **2021 = 77.8%**, 2022 = 90.9%, 2023 = 94.1%,
  2024 = 94.0%. Early 2021 has no prior games to derive from, so 2021 is the thinnest season.
- 9.7% of player-seasons (49/504) have their derived group flip mid-season as the running mode
  updates. That is genuine measurement churn, not a bug.
- It is **coarse**: 3 groups, and it inherits whatever a coach's starting-slot convention was.
  A player who never starts never gets a group.
- Descriptive sanity (not used to build it) — mean per-100-possessions by derived group:
  C 18.95 pts / 12.38 reb / 2.92 ast; F 18.79 / 9.17 / 3.85; G 18.82 / 5.24 / 6.55. The groups
  separate rebounds and assists strongly and points not at all, which is what real positions do.

## Construction

**Normalisation (Step 1).** Per **100 possessions**, using the row-level `possessions` column,
not per-game totals. Chosen over per-36-minutes because "allowance" is precisely the quantity
that pace confounds — a fast opponent allows more of everything per game. The whole screen was
re-run per-36 as a robustness check (`run_log_per36.txt`); every conclusion is unchanged
(pooled pregame interaction ΔR²: pts 0.00095, reb 0.00023, ast 0.00006; all ≤ 0.00004 after the
overall-defence control).

Outcome modelled is the player-game **rate** (stat per 100 possessions), not the raw total, so
that minutes and pace don't swamp the R² and hide the interaction. Analysis rows require
`minutes ≥ 10`.

**Step 2 — leave-one-out, strict.** For allowance cell (season, opponent, position group), the
attached aggregate excludes **the entire game being explained AND every row belonging to that
player in that cell** (inclusion–exclusion: `total − game − player + this row`). I went beyond
the letter of the brief here: excluding only the current game still leaves the player's *other*
games against that opponent in the aggregate, which is the same contamination one game later.

**Step 3 — pregame-observable.** Expanding within season, strictly before the current
`game_date` (date-level aggregation so same-day games can't see each other), minus that
player's own prior contributions, shrunk toward the expanding within-season league mean for
that position group with `k = 5` (≈500 possessions). Early-season fallback: prior-season league
mean for the group; rows with fewer than 300 prior possessions in the cell are dropped. Own
tendency is built with the identical discipline (shrunk to the player's prior-season rate, then
to the league group rate for rookies). Complete pregame rows: **9,262 of 12,337 analysis rows
(75.1%)** — the 25% loss is early-season rows and players without enough prior history.

**A structural correction that the screen forced, and that matters.** Raw
`corr(own tendency, allowance)` is **+0.68 for rebounds** and **+0.59 for assists** — and strict
LOO barely moves it (+0.66 / +0.56). That is not self-contamination; it is that the raw
allowance is mostly a **position label**. Variance decomposition of the full-season allowance:

| target | sd across all cells | sd within (season, position) | share of variance that is *between-position* |
|---|---|---|---|
| pts | 1.766 | 1.632 | **0.15** |
| reb | 3.209 | 0.857 | **0.93** |
| ast | 1.618 | 0.411 | **0.94** |

For rebounds and assists, **93–94% of "opponent allowance to position group" is just which
position the player is**. Testing the hypothesis on the raw variable would have been testing
`own tendency × position dummy` and calling it a matchup effect. Everything below therefore
centres both the allowance and the own tendency **within (season, position group)** and carries
position dummies in every model, so the interaction tested is genuinely
*opponent-specific allowance* × *own tendency*.

Once demeaned, the LOO diagnostic reads as it should:

| target | corr(own, allowance) naive | corr(own, allowance) strict LOO |
|---|---|---|
| pts | +0.018 | −0.108 |
| reb | +0.014 | −0.090 |
| ast | +0.012 | −0.129 |

LOO drives it slightly **negative**, which is the expected mechanical artifact of removing
yourself from a finite pool, not a finding.

## Step 4 — the actual test: incremental R² of the interaction over both main effects

Base model = own tendency + positional allowance + position dummies. Full model adds the
interaction. Both variables centred within (season, position) and scaled to unit sd.

### Pregame-observable version — **this is the one that decides the verdict**

| target | 2021 | 2022 | 2023 | 2024 | POOLED | base R² (pooled) |
|---|---|---|---|---|---|---|
| **pts** | 0.00060 | 0.00026 | 0.00123 | 0.00050 | **0.00056** | 0.235 |
| **reb** | 0.00006 | 0.00044 | 0.00018 | 0.00001 | **0.00010** | 0.404 |
| **ast** | 0.00015 | 0.00107 | 0.00080 | 0.00084 | **0.00003** | 0.340 |

n = 1,662 / 2,304 / 2,656 / 2,640; pooled 9,262.

Interaction coefficients, pregame: pts +0.34 / +0.17 / +0.39 / +0.25 (consistent sign, tiny);
reb −0.05 / +0.10 / +0.07 / +0.02 (**sign flips**); ast −0.06 / −0.11 / +0.11 / +0.12
(**sign flips, and flips as a block between 2022 and 2023**).

### Within-season LOO version (reported for completeness; uses future games, not available at tipoff)

| target | 2021 | 2022 | 2023 | 2024 | POOLED |
|---|---|---|---|---|---|
| pts | 0.00213 | 0.00068 | 0.00054 | 0.00201 | 0.00113 |
| reb | 0.00184 | 0.00097 | 0.00129 | 0.00001 | 0.00072 |
| ast | 0.00001 | 0.00031 | 0.00028 | 0.00017 | 0.00001 |

n = 11,960 pooled. Uniformly larger than the pregame version and still negligible — the
in-sample version flatters the effect roughly 2× and is still nowhere.

**Read this plainly**: the largest pregame interaction increment anywhere in the table is
0.00123 R² (points, 2023) on a base of 0.268. That is one eighth of one percent of variance, in
the single best season, before any confound control.

## Step 5 — the overall-opponent-defence confound

Positional allowance correlates with overall opponent defensive allowance (same stat, all
positions pooled, same pregame discipline) at **+0.57 (pts), +0.58 (reb), +0.59 (ast)** *within
(season, position)*. Control model = own + overall defence + position dummies + own×overall.

| target | quantity | 2021 | 2022 | 2023 | 2024 | POOLED |
|---|---|---|---|---|---|---|
| pts | ΔR² positional allowance over overall D | 0.00148 | 0.00325 | 0.00241 | **0.00013** | 0.00124 |
| pts | **ΔR² interaction over all of it** | 0.00007 | 0.00012 | 0.00003 | 0.00014 | **0.00001** |
| reb | ΔR² positional allowance over overall D | 0.00001 | 0.00044 | 0.00396 | 0.00004 | 0.00070 |
| reb | **ΔR² interaction over all of it** | 0.00040 | 0.00067 | 0.00023 | 0.00004 | **0.00008** |
| ast | ΔR² positional allowance over overall D | 0.00029 | 0.00000 | 0.00040 | 0.00012 | 0.00000 |
| ast | **ΔR² interaction over all of it** | 0.00050 | 0.00237 | 0.00049 | 0.00024 | **0.00004** |

Orthogonalising the positional allowance on overall defence first (`dR2_OxAres`) gives
identical numbers to four decimal places.

**This is the kill shot.** The interaction's incremental R² over the additive model *plus
overall opponent defence* is ≤ 0.00014 in every season of every target, and ≤ 0.00008 pooled.
The idea is a re-labelled main effect: whatever little the "positional" allowance carries is
opponent defensive strength wearing a position costume, and the interaction on top of it is
nothing.

## Step 6 — negative control (placebo)

200 permutations, seed 20260807. Within each season the 12 teams are **deranged** (no team keeps
its own defence), the allowance panel stays keyed on **true** opponents, and each player-game
looks up a *different* team's allowance as of the same date. Own tendency, position and outcome
are untouched.

> **A bug worth propagating to other screens in this program.** My first placebo simply
> relabelled opponent ids and rebuilt the aggregates. That is a **no-op**: the cell
> (season, π(opp), pos) is the same set of rows as (season, opp, pos) merely renamed, so every
> row still receives its own true allowance. It reproduced the real number to every decimal with
> sd exactly 0.000000 across all 200 draws — which is how it was caught. Any permutation placebo
> in this program that permutes a grouping key **and then recomputes the aggregate from the
> permuted key** is testing nothing. The permutation has to break the *pairing* between row and
> aggregate, not rename both sides together.

Pooled, pregame, interaction ΔR² against the floor:

| target | REAL | placebo mean | placebo sd | placebo p95 | frac(placebo ≥ real) |
|---|---|---|---|---|---|
| **pts** | 0.000542 | 0.000123 | 0.000144 | 0.000422 | **0.020** |
| **reb** | 0.000158 | 0.000111 | 0.000156 | 0.000447 | **0.240** |
| **ast** | 0.000091 | 0.000093 | 0.000136 | 0.000346 | **0.315** |

Per season (frac of placebos ≥ real — **this is where points dies**):

| target | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| pts | 0.490 | 0.445 | **0.040** | 0.280 |
| reb | 0.680 | 0.425 | 0.445 | 0.570 |
| ast | 0.615 | 0.060 | 0.065 | 0.080 |

Rebounds and assists sit **inside** the noise floor pooled and in every season. Points clears
the pooled floor at 0.020 — but that pooled number is carried entirely by 2023 (0.040) while
2021, 2022 and 2024 sit at 0.49, 0.45 and 0.28, i.e. squarely inside the floor. That is the
I0006 failure mode exactly: a pooled number that looks like something and per-season partials
that say nothing. Per the binding discipline, persistence beats significance, and points has no
persistence.

## Is this a real null, or a null through a noisy construction? (binding discipline #4)

This is the check that decides whether "kill" is honest. Split-half reliability of the
allowance measure: each defence's games split odd/even by date, rate computed in each half,
level differences removed within (season, position) so it measures *opponent* variation only,
Spearman-Brown corrected to full-season reliability.

| target | **positional allowance (this idea)** | overall team defence (known-real benchmark) |
|---|---|---|
| pts | **r_half 0.386 → r_full 0.557** (n=144) | r_half 0.699 → r_full 0.823 (n=48) |
| reb | **r_half 0.474 → r_full 0.644** (n=144) | r_half 0.693 → r_full 0.819 (n=48) |
| ast | **r_half 0.163 → r_full 0.281** (n=144) | r_half 0.451 → r_full 0.622 (n=48) |

**Points and rebounds: the null is a real null.** The positional allowance is a genuinely
reliable measurement (0.56 / 0.64) — opponents really do differ, stably, in what they allow to
each position group, and that stable difference is measured well enough to detect an
interaction if one existed. It doesn't. That is a negative, not a shrug.

**Assists: the null is weaker evidence.** Reliability 0.281 is low. A sharper assist-allowance
measure could in principle recover something this construction cannot see. I am still calling
it a kill — the interaction is inside the placebo floor pooled and in 2021, the per-season
coefficients flip sign as a block between 2022 and 2023, and the confound-controlled increment
is 0.00004 — but the coordinator should know this particular kill rests partly on a
badly-measured input, and is the one of the three most worth overruling.

The main effect is also alive and well-measured, which further rules out "the whole construction
is dead". Partial correlation of the pregame positional allowance with the outcome after own
tendency and position dummies: pts **+0.066 / +0.100 / +0.065 / +0.068** across 2021-2024 (all
four seasons, same sign, stable); reb +0.063 / +0.067 / +0.089 / +0.032; ast +0.044 / +0.014 /
−0.015 / +0.042 (sign flips — not persistent). So the pipeline can detect a persistent effect
when one is there. It just isn't there for the *interaction*, which is what the hypothesis
claims.

## Verdicts

| target | verdict | reason |
|---|---|---|
| **points** | **`kill`** | Pregame interaction ΔR² pooled 0.00056; collapses to **0.00001** once overall opponent defence is controlled. Clears the pooled placebo floor only on the strength of one season (2023, frac 0.040) while 2021/2022/2024 sit at 0.49/0.45/0.28 — no persistence. Measurement is reliable (0.557), so this is a genuine negative, not a noise null. |
| **rebounds** | **`kill`** | Pregame interaction ΔR² pooled 0.00010, **inside the placebo floor pooled (0.240) and in all four seasons** (0.43–0.68). Interaction coefficient flips sign across seasons. 0.00008 after the defence control. Measurement is the most reliable of the three (0.644), so the null is real. |
| **assists** | **`kill`** | Pregame interaction ΔR² pooled 0.00003, inside the placebo floor pooled (0.315). Per-season coefficients flip sign as a block (−0.06/−0.11/+0.11/+0.12). 0.00004 after the defence control. The positional-allowance main effect itself fails persistence. **Caveat: allowance reliability is only 0.281**, so this kill is the least secure of the three. |

Aggregate: the interaction carries **≤ 0.00014 R² in any season of any target** once overall
opponent defence is in the model. The construction is sound, pregame-observable, uses no lineup
attribution, and is reliable enough to have found the effect. There is no interaction to find.

## Noticed but NOT tested — candidate ideas, not findings

These are flagged so they are not mistaken for results. None of them was placebo-tested and
none may be claimed.

1. **The positional-allowance MAIN effect for points is persistent across all four seasons**
   (partial r +0.066/+0.100/+0.065/+0.068 after own tendency and position). It partly survives
   the overall-defence control in 3 of 4 seasons (ΔR² 0.0015/0.0033/0.0024) but dies in 2024
   (0.0001). **Not placebo-tested, not a claim.** Candidate idea: "opponent allowance to
   position group as an additive term for points" — a different, weaker idea than this one, and
   it would need its own screen with its own noise floor.
2. **For rebounds and assists, 93–94% of positional-allowance variance is between-position.**
   Any future positional-matchup construction must decompose this first or it will be testing a
   position dummy. Structural design warning, not a hypothesis.
3. **The position construct is the weakest link.** Starting-lineup slot gives 3 coarse groups,
   misses non-starters entirely, and churns in 9.7% of player-seasons. A continuous "role/bigness"
   score built from prior-season non-target stats (shot-location mix, usage, foul rate) would be
   finer and would cover bench players. Whether that sharpens the allowance is untested.
4. **Assist allowance may need a different denominator.** Per-100-possessions gives reliability
   0.281. An assist-opportunity denominator (teammate FGM, or passes) might be materially more
   reliable and is the one thing that could plausibly reopen the assist verdict.
5. **The permutation-placebo no-op bug** (documented in Step 6) — worth auditing any other
   screen in this program that permutes a grouping key and recomputes the aggregate from the
   permuted key.
6. **`master_player.observed_time` is a build mtime that leaks 2026 date bytes into any
   downstream `to_csv` of the full frame.** Not a partition violation, but a byte-scan tripwire
   that other experiments will hit.

## Artifacts

`experiments/exploration/E0_I0010_positional_matchup/`

| file | what |
|---|---|
| `probe.py`, `probe2.py` | schema / position-field probes (how the starter-slot finding was made) |
| `build_features.py` | intermediate feature frame builder → `player_game_features.csv` |
| `analyze.py` | the screen: steps 2, 4, 5, 6. `I0010_UNIT=unit36` env var switches normalisation |
| `diagnostics.py` | split-half reliability, variance decomposition, main-effect persistence |
| `verify_partition.py` | partition verification on output bytes |
| `player_game_features.csv` | 41,547 rows (3 targets × player-games), 2021-2024 |
| `features_{pts,reb,ast}.csv` | per-target analysis frames with all features |
| `placebo_draws_{pts,reb,ast}.csv` | 200 permutation draws each, pooled + per season |
| `run_log.txt` | stdout of `analyze.py` (per-100-possessions, the headline run) |
| `run_log_build.txt`, `run_log_diagnostics.txt`, `run_log_per36.txt` | stdout of the other runs |
| `run_log_partition_verification.txt` | stdout of the byte-level partition check |

Deterministic: seed 20260807 for the placebo, parity split (no RNG) for the reliability check.
Re-running `analyze.py` reproduces every number in this file.
