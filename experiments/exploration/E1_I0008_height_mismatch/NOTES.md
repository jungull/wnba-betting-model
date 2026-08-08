# E1 I0008 — height/size mismatch vs rebounding: **KILLED AT THE STAGE 1 GATE**

**Non-claiming.** This is an E0/E1 exploration screen. No registry entry, no preregistration,
no leaderboard row, no REPORT.md was created and none should be. The only assertion here is a
negative one about a lead.

---

## The one-line kill

> **I0008 is dead.** Its advertised +0.0203 / +0.0175 incremental R² sits **inside its own
> permutation null** (null mean +0.0196 / +0.0169, sd 0.00055 / 0.00051, `frac_ge_real`
> **0.1025 / 0.0725** over 400 draws) — because **99% of the effect is the player's own height,
> not the height *mismatch*.**

Stage 2 was **not run**, deliberately. That is the gate working.

---

## What the lead actually was

`rung1_height_diff = (player's own height) − (opponent's season minutes-weighted roster height)`

Two terms. The first varies with sd **3.489 inches** across player-games. The second varies with
sd **0.554 inches** across the 48 team-seasons. The feature is ~98% the first term by variance.

So the "height mismatch effect" is a main effect of **being tall**, with a nearly-constant
opponent term subtracted off it. Tall players get more rebounds. That is true, and it is not a
matchup finding, and it is not news.

The decomposition says it directly. Put the player's own height in the model *first*, then ask
what the opponent adds:

| target | headline ΔR² | ΔR² from **own height alone** | ΔR² from **opponent**, given own height |
|---|---|---|---|
| OREB% | +0.020260 | +0.020116 (**99.3%**) | **+0.000262** |
| DREB% | +0.017546 | +0.017329 (**98.8%**) | **+0.000295** |

The genuinely opponent-carrying part is ~1/70th of what the lead was credited with. And it also
fails its own null (`frac_ge_real` 0.1425 / 0.0950).

---

## Stage 1 — the noise floor

The single most important fact about this lead going in was that **it had no placebo of any
kind.** Its +0.018–0.020 had never been compared to anything. Screen I0006 already proved on
this program's own data that a plausible-looking statistic can be beaten by its own noise floor,
so I0008 could not be ranked against another lead until it had one. Building it was the whole
job; everything below Stage 1 in this document is explanation, not additional evidence.

### First, the trap — run on purpose

A control that permutes a **grouping key** and then **recomputes the aggregate from the permuted
key** is a **no-op**. Renaming cells does not change their membership: cell σ(t) after the
permutation is exactly the row set of cell t before it, so joining back on the equally-permuted
opponent key hands every row its own true value. It looks like a working placebo and tests
nothing.

Run deliberately, 50 draws, all four cells:

```
mean = +0.020276   sd = 0.000000  (sd exact = 0.000e+00)
distinct values across all 50 draws = 1
unpermuted-key reference (same recompute path) = +0.020276
max|draw - unpermuted reference| = 0.000e+00
DIAGNOSTIC -> CONFIRMED NO-OP (as predicted -- this control tests nothing)
```

**sd exactly 0.000000, one distinct value across every draw, the unpermuted result reproduced to
0.000e+00.** That is the signature. If a control ever prints it, it is not a control.

(The no-op lands at +0.020276 against the stored-column real of +0.020260. That ~1.6e-05 gap is
*not* the permutation — it is because the no-op path recomputes the aggregate from the 16,345
analysis rows while the stored column was built over all 18,212 played rows. Against its own
unpermuted reference, which uses the identical recompute path, the deviation is exactly zero.)

### Then, the real control

Aggregate computed **once**, on the **true** opponent rosters, **never recomputed**. What gets
permuted is the **assignment of that already-computed value to rows**: within each season the 12
team-season aggregates are permuted across team labels and joined on the row's **true**
`opp_team_id`. Every row receives some *other* real team's roster-height aggregate.

Team-level rather than row-level permutation is the primary form, chosen on structural grounds
*before* seeing either result: the feature genuinely takes only 12 distinct values per season,
shared by every row facing that opponent. A row-level shuffle destroys that clustering and
therefore **understates** the null. It is reported alongside as a secondary variant.

400 draws, seed 20260807, zero identity permutations drawn:

| rung × target | n | real ΔR² | E0 said | null mean | null sd | null max | **frac_ge_real** | z | row-level variant |
|---|---|---|---|---|---|---|---|---|---|
| rung1 × OREB% | 16,345 | **+0.020260** | +0.0203 | +0.019606 | 0.000545 | +0.021579 | **0.1025** | +1.20 | 0.0350 |
| rung1 × DREB% | 16,345 | **+0.017546** | +0.0176 | +0.016852 | 0.000508 | +0.018272 | **0.0725** | +1.36 | 0.0225 |
| rung2 × OREB% | 16,345 | +0.019982 | +0.020 | +0.019168 | 0.000729 | +0.021384 | **0.1325** | +1.12 | 0.0450 |
| rung2 × DREB% | 16,345 | +0.017288 | +0.017 | +0.016440 | 0.000645 | +0.018237 | **0.0950** | +1.32 | 0.0425 |

Note the null **max** column against the real value: in every cell, permuted opponents routinely
produce a *larger* effect than the true ones.

The real numbers reproduce E0 I0008's headline to four decimals on the same 16,345 of 18,212
rows. **The thing killed is the same number the lead reported**, independently rebuilt from the
same two raw sources — not a differently-constructed proxy for it.

### The one place I could have cheated, and didn't

The row-level variant (B2) is *stricter* — `frac_ge_real` 0.0350 / 0.0225 — and on DREB% it would
have squeaked past a 0.05 line. Swapping to it after seeing the primary fail would have been a
manufactured pass. The primary was chosen on structure, it is the conservative one, and both are
in the table.

---

## Two claims from the E0 write-up that do not survive

**"Signal concentrates hardest in forwards."** The raw correlation reproduces (F +0.3632 vs E0's
0.367), but decomposed, **88.8%** of the forward cell's incremental R² is the player's own
height. Guards are **101.6%** own height. The opponent-specific residue is actually largest in
**centers** — the opposite of the claim. The pattern E0 saw is a within-position *own-height
gradient*, not a matchup gradient.

**The position column is blank on 46.7% of rows.** `master_player.position` is empty for 8,512 of
18,212 played rows. Every position cut in E0 I0008 — and every one here — describes only the
53.3% that carry a G/F/C label. The bios `position_raw` field is fully populated and richer
(7 classes, including Guard-Forward and Forward-Center) and no screen has used it. Worth knowing
before anyone runs another positional cut.

---

## What I did *not* let survive

Post-hoc per-position nulls on the opponent-specific residual: 2 of 6 cells clear 0.05
(expected 0.3 by chance) — Centers/OREB% at +0.006365 (`frac_ge_real` 0.0150) and Forwards/DREB%
at +0.001254 (0.0450).

These are **post-hoc subgroups of an effect already killed pooled**, with no multiplicity
correction, on a position column blank for nearly half the data, in a subgroup chosen *after*
watching the pooled result fail. The Centers/OREB% cell is the only one of any size and it is
still ~31% of the advertised headline on 1,781 rows. **This is not a surviving form of I0008 and
must not be reported as one.** If someone wants it, it is a new and much narrower question — "does
opponent roster size affect *offensive* rebounding by *centers* specifically" — and it needs its
own screen with the subgroup fixed in advance. I ran it only so the question would be closed
rather than left dangling, not to give the lead somewhere to hide.

---

## A methodological result worth keeping

The classical single-regressor t on the opponent aggregate is **+2.22** (OREB%) and **+2.40**
(DREB%) — nominally significant at 0.05. **Both are wrong.** The feature takes 12 distinct values
per season and every row facing the same opponent shares one, so OLS standard errors that treat
16,345 rows as independent are badly anticonservative. The permutation null, which respects the
clustering, puts both cells comfortably inside it.

That is a clean, concrete demonstration on this program's own data of why cluster-structured
team-level features need noise floors and not t-statistics. It generalises to every other lead in
this program whose feature is a team-season or team-game aggregate.

---

## Corrections carried, and the one defect that is real

**I did not re-inherit I0008's self-downgrade.** E0 I0008 marked its rungs 1 and 2 "UNCONFIRMED
PENDING A CLEAN REBUILD" because `master_player.parquet` has `fit_through_season: 2026` and
`fit_seasons: [2021..2026]`. That is the wrong test. I read the manifest bytes myself this
session: it declares **`asof_granularity: "row"`**, and the GRAPH_POLICY 13.2.2 test is
`asof_granularity == "row"`. `fit_seasons` says what the file *contains*, not how it was fit; a
row-granular artifact filtered to 2021–2024 is safe. Recorded in `manifest_checks.json`, printed
in `run_log_build.txt`. `player_bios.csv` has no manifest sibling — static biographical data,
not a fit artifact.

**Which rung every number comes from: rung 1 and rung 2, always.** Neither uses any on-court
lineup attribution — no `possessions_v2` join, no clock-time-to-possession matching. The ~72%
side-of-play accuracy I0003 measured (84% DRB, 43% ORB) applies to **rung 3 only** and is nowhere
in the causal path of anything above. Rung 3 was not re-run; E0 already flagged that its `is_orb`
construction fires ~95% positive against a true WNBA ORB rate of ~25–30%, i.e. it is broken, and
its null there is uninformative either way.

**Forward-fill audit — the answer is no, but there is a different defect.** The roster-height
aggregate is a minutes-weighted mean of `height_inches`, a *static* biographical field. No
per-player rate is being carried forward, so the "forward-fill the last observed rate
indefinitely" defect seen in sibling roster-pool constructions does not apply. But the
**weights** are full-season minutes totals, computed over the whole season *including games after
the row being scored*. The opponent aggregate is therefore **not strictly pregame-observable at
game t**, contrary to how the lead is described. This cuts *against* the lead, not for it — it
means the killed number was mildly optimistic. Materially small (the aggregate's across-team sd
is 0.554 inches and the weighting choice moves it far less than that), so it is recorded for
completeness, not offered as the cause of death.

---

## Partition

Seasons **2021, 2022, 2023, 2024** only. `holdout_touched: false`.

Both raw sources contain 2025/2026 rows; both were filtered on **season column values**
immediately after load, before any merge or aggregation, marked `# FILTER-POINT`. E0 I0008 did
not filter the bios table at all — it relied on the `(player_id, season)` join key to exclude
holdout bio rows implicitly. That works, but it is not an explicit filter point, so I added one.

`assert_partition()` prints `sorted(season.unique())` and hard-exits on any 2025/2026 value. It
runs after every load, after every filter, after every merge, before the frame is written, on
load of the frame in each analysis script, and on every analysis subset. Every call is in the run
logs; none fired. Final frame `game_date` range: **2021-05-14 to 2024-10-20**.

**No raw byte-scan for "2025"/"2026" was used anywhere.** That method produced a documented false
partition violation in this program by matching row counts and digit runs inside floats. Season
and date **column values** were tested instead.

## R² convention

**Plain unweighted OLS R²**: `R2 = 1 − SS_res/SS_tot`, `SS_tot` about the unweighted mean of y,
no sample weights. The shared E0 `wls_r2` helper is **not** used anywhere in this screen — it
computes SST of the sqrt-weight-transformed response about its own mean rather than weighted SST
about the weighted mean, making every ΔR² from it ~8% too small. Conservative, so nothing it
reports is overstated, but not comparable across screens to three significant figures.

Since the reproduction here matches E0 I0008's headline to four decimals, E0 was evidently also
using plain OLS. Either way the real-vs-null comparison is convention-internal: both sides use
the identical estimator.

---

## Stage 2 — not run

Gated out. The corrected baseline `../E1_I0011_split_alpha/baseline/`
(`own_rate_v2_split_alpha`, `alpha_eff=0.03` / `alpha_exp=0.30`, gate `n_prior >= 3`) was read
and is confirmed present, importable and runnable, but was **never invoked** and
`validate_baseline.py` was **never run** — there was no surviving effect to re-measure against
it. Re-measuring a noise-floor-indistinguishable effect against a stronger baseline could only
have made it smaller; it could not have made it real.

One note for whoever uses that baseline next: its interface is per-36-rate × minutes over
**counting** stats (`pts`/`reb`/`ast`), whereas I0008's target is
`offensive_/defensive_rebound_percentage`, a per-game **percentage**. A Stage 2 here would have
had to re-express the target as `oreb`/`dreb` counts — which changes the *target*, not just the
baseline. It is not a drop-in swap, and that is worth knowing before someone assumes it is.

---

## Files

All inside `experiments/exploration/E1_I0008_height_mismatch/`. Nothing under `data/`, nothing
under `experiments/player_program/`, and no other screen directory was touched.

| file | what |
|---|---|
| `build_frame.py` → `run_log_build.txt` | rebuilds the rung-1/rung-2 frame from `master_player.parquet` + `player_bios.csv`; manifest check; partition filters |
| `frame.parquet` | 18,212 played player-game rows, 2021–2024 |
| `manifest_checks.json` | per-artifact 13.2.2 check, read from bytes this session |
| `stage1_noise_floor.py` → `run_log_stage1.txt`, `stage1_noise_floor.json` | **the gate**: no-op diagnostic + real control, 400 draws |
| `stage1_addendum.py` → `run_log_stage1_addendum.txt`, `stage1_addendum.json` | opponent-specific residual vs its own null; position decomposition |
| `stage1_position_null.py` → `run_log_stage1_position_null.txt`, `stage1_position_null.json` | post-hoc per-position nulls (closing check, not a revival) |
| `make_findings.py` → `run_log_findings.txt`, `FINDINGS.json` | assembles FINDINGS.json by *reading* the run artifacts — no hand-transcribed numbers |
