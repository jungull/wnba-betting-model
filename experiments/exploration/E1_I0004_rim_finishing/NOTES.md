# E1 I0004 — rim finishing × opponent rim-defence allowance

**E1 is NON-CLAIMING.** Nothing below is a RESULT. E1 asks exactly one question —
*does the effect persist* under a basic season split inside the exploration
partition — and answers only that. No preregistration, no walk-forward, no
confirmation-holdout evaluation, no registry entry, no leaderboard row, no
promotion. Seasons 2021–2024 only; the 2025/2026 confirmation holdout was never
read, joined, filtered against, counted, plotted or described.

Parent: `experiments/exploration/E0_I0004_shot_location_allowance/`.

---

## The short version

**How much of the E0 +0.039 survives: about 45%.**

E0's headline was a hi-lo difference of **+0.0392** (corr +0.0444). Re-measured
with a proper, pregame-observable baseline on *both* sides it is **+0.0176**
(corr **+0.0288**). Roughly **2.2×** overstated on the difference metric, **1.5×**
on the correlation metric.

But the effect itself does not go away. On the fully pregame-observable
construction the OLS slope is **+0.373**, cluster-robust SE **0.090** across 48
opponent-team-season clusters (**t = +4.14**), positive in **4/4 seasons** and in
both halves of the partition, retaining **93%** of its slope once pooled opponent
defence is controlled, and *strengthening* under player-season fixed effects.
Against a genuine 400-draw permutation null, **0/400** draws reach the real
correlation or slope.

So: the lead is real and it persists. The number attached to it was not.

The R² is **0.00083**. That is the honest size of this thing at the shot level.

---

## 1. Which baseline was the E0 headline actually stated over?

Established from the code, not the prose.
`E0_I0004_shot_location_allowance/build_and_test.py` L180–188 and
`robustness_loo.py` L91–102 both build:

```python
other = g[g["season"] != row["season"]]        # g grouped by (PLAYER_ID, zone)
if other["att"].sum() >= 10:
    base = other["mk"].sum() / other["att"].sum()
```

**Answer: a leave-one-SEASON-out, attempt-weighted, player × zone conversion
rate.** It is *not* `props_edge.py`'s frozen-alpha own-rate, and it is *not*
`player_tendency_loo` (the within-season `(season_sum − y_t)/(n−1)` form).

It is a third thing, and it fails for the same reason the second one does. For a
2021 shot it is computed from the player's **2022/2023/2024** attempts — it reads
the player's *later seasons*. It is also **constant within (player, season,
zone)**, so it carries no within-season time variation whatsoever and is not a
"recent rate" in any sense of the phrase. **An increment measured over it is not a
forecasting increment.**

### The LOO disambiguation, since it was asked

`robustness_loo.py`'s `zone_conv_residual_loo` (L75–88) is **leave-one-GAME-out
over the OPPONENT-allowance construction** — excising the current game's
makes/attempts from the opponent's season-zone tally. That is the **benign** kind,
not a leave-one-out over the player's own season. The two objects are distinct and
only the latter would be fatal. So E0 did not commit *that* error.

**But there is a second problem on that side, which E0 did not flag.** The
opponent statistic is a leave-one-game-out **full-season** team rate. It therefore
reads the *opponent's* later games. **Both sides of the E0 headline are
retrospective.** That is why this screen builds a strictly-prior-games opponent
allowance as well, and reports the fully-pregame cell as the headline.

---

## 2. What was built

Everything runs on the same **30,764 Restricted-Area shots** — 88.7% of E0's
34,681-shot row set, the shortfall being the `n_prior >= 3` warm-up gate the
corrected baseline imposes.

**Own-rate baselines**

| id | what | pregame-observable? |
|---|---|---|
| `B0` | E0's incumbent: leave-one-season-out player × zone rate | **no** |
| `B1` | **`own_rate_v2_split_alpha`** — the frozen corrected baseline, imported | **yes** |
| `B2` | attempt-weighted expanding prior-games rate, shrunk to the expanding league rate (K = 50) | yes |

**Opponent allowance**

| id | what | pregame-observable? |
|---|---|---|
| `O1` | E0's: leave-one-game-out **full-season** zone rate minus pooled rate | **no** |
| `O2` | strictly **prior games** in season (expanding, shifted), gate ≥ 20 prior attempts | **yes** |

### Using the frozen baseline on a per-attempt rate

`own_rate_v2_split_alpha` is written for per-game counting stats — an efficiency
channel `stat/minutes*36` at `alpha_eff = 0.03` times an exposure channel
`minutes` at `alpha_exp = 0.30`. Rim conversion is a per-**attempt** quantity, so
the exposure unit is the attempt: the module is called with
`minutes := Restricted-Area attempts in the game` and `target := RA makes`. Its
efficiency channel then *is* `EWMA_0.03(makes/attempts)` over the player's
strictly-prior RA games within the season, gated at `n_prior >= 3`.

The module was **imported, not reimplemented**, and the extracted quantity was
checked against a direct `pandas.ewm` computation: `max|diff| = 7.8e-16`.

`validate_baseline.py` was run **first**, in an isolated copy under
`_validate_sandbox/` (it writes `BASELINE_PERFORMANCE.json` next to itself, and
nothing outside this screen's directory may be written). **All 24 equivalence
checks MATCH at |d| = 0.00e+00**, far inside the 1e-9 requirement. Log:
`run_log_00_validate_baseline.txt`.

### E0 was reproduced exactly first

Before changing anything, `robustness_loo.py`'s numbers were re-derived from the
raw shot files: Restricted Area **n = 34,681, corr = +0.0444, diff = +0.0392,
SE = 0.0052** — an exact match to the published figures, and every other zone
matched too. Whatever else this screen says, it is talking about the same object
E0 was.

---

## 3. The re-measurement

All cells on the common 30,764 rows. R² convention: **plain unweighted OLS,
1 − SSE/SST, SST about the unweighted mean.**

| baseline | opponent | corr | diff | beta | SE(clust) | t(clust) |
|---|---|---|---|---|---|---|
| B0 (E0) | O1 (E0) | +0.0434 | +0.0360 | +0.726 | 0.094 | +7.72 |
| B0 (E0) | **O2 pregame** | +0.0356 | +0.0251 | +0.453 | 0.080 | +5.65 |
| **B1 corrected** | O1 (E0) | +0.0372 | +0.0298 | +0.633 | 0.118 | +5.37 |
| **B1 corrected** | **O2 pregame** | **+0.0288** | **+0.0176** | **+0.373** | **0.090** | **+4.14** |
| B2 | O1 (E0) | +0.0381 | +0.0313 | +0.638 | 0.115 | +5.54 |
| B2 | O2 pregame | +0.0294 | +0.0195 | +0.374 | 0.086 | +4.36 |

Reading down the correction path:

- **Fixing only the own-rate baseline** (B0→B1, holding E0's opponent measure):
  +0.0392 → **+0.0298**, i.e. **76% survives**.
- **Also requiring the opponent measure to be pregame-observable** (→ O2):
  **+0.0176**, i.e. **45% of the E0 difference survives**; on correlation,
  **65%** (+0.0444 → +0.0288).

B2 lands within a hair of B1 in every cell, so the conclusion is not an artifact
of how the pregame own-rate was smoothed.

**Standard errors.** The regressor is essentially constant within an opponent
team-season, so the honest SE is clustered on (opponent team, season) — 48
clusters. E0 reported neither a clustered nor a regression SE, only an
unclustered approximate SE of a mean difference.

### Persistence (the actual E1 question)

Per-season slopes, headline cell **B1 × O2**: **+0.565, +0.281, +0.448, +0.509**
— 4/4 positive. Halves: +0.361 (2021–22), +0.477 (2023–24). On the correlation
metric the halves are +0.0300 and +0.0326, against E0's +0.049 / +0.034. Every
one of the six cells is 4/4 positive by season and positive in both halves.

The effect is smaller than E0 said and it is stable.

---

## 4. Robustness — the two things the verdict hung on

**Is it actually net of pooled opponent defence?** The deterministic control C1
showed the shooting residual *also* correlates positively with the opponent's
pooled FG% allowed (corr ≈ +0.021), so this needed testing rather than assuming.
Putting pooled and rim-specific allowance in the same regression: the rim-specific
slope goes +0.373 → **+0.347 (93% retained)**, and its clustered t *rises* to
+4.59. Across all four baseline × opponent cells, retention is **93–97%**. The
claim holds.

**Is it within-player or composition?** Under **player-season fixed effects** the
headline slope rises from +0.373 to **+0.432** (t = +4.66); under
**shooting-team-season fixed effects** to **+0.450** (t = +4.88). It is not a
story about which players happen to draw permissive rim defences.

**Negative-zone control.** Above the Break 3 — the zone E0's own dispersion test
found has no real between-team variation in allowance — gives corr +0.0027, diff
+0.0033 against SE 0.0051. Flat, as it should be.

---

## 5. The player-game view, and why it is much less impressive

The claim "incremental value over the player's own recent rate" in the form the
frozen baseline was actually built for: predict a player's **Restricted-Area makes
in a game** from the split-alpha projection, then ask whether opponent rim
allowance adds anything.

- M0: `ra_mk ~ 1 + split_alpha_projection`
- M1: adds `exposure_channel × opponent_rim_allowance`

Pooled 2021–2024 with the pregame opponent measure, **ΔR² = +0.00092** on 10,734
player-games. All four seasons non-negative — but **2022 is +0.0000004** and 2021
is +0.00015. Essentially the whole pooled effect is 2023 (+0.00142) and 2024
(+0.00442).

The per-season interaction coefficients (+0.124, +0.001, +0.428, +0.640) rank the
same way as the shot-level per-season betas, so this is the same signal measured
with far less power rather than a contradiction. But stated plainly: **at the
player-game level the increment is about 0.001 R² and it is not stable season to
season.** Whether that is worth anything is an E2 question and is not claimed here.

---

## 6. Placebo / noise floor

400 draws, seed 20260807.

### The deliberate no-op, run on purpose

The defective design — permute the **grouping key** (a bijective relabel of
opponent teams within season) and then **recompute the aggregate from the permuted
key** — was run deliberately as a positive diagnostic. A bijective relabel maps
each permuted cell onto exactly the same row set under a different name, so every
row still receives its own true value.

**Signature confirmed on both cells.** Across 400 draws every draw is
bit-identical to the identity-relabel reference (`max|dev| = 0.00e+00` on corr,
diff and beta) and `sd = 0.0000000000` — the residual ~1e-17 is rounding dust from
numpy's two-pass std on a constant array. This control tests **nothing**. It is
here only so the genuine controls below can be seen to be genuine by contrast.

*(Note: the reference for D0 is the identity relabel run through the same recompute
pipeline. Scoring D0 against the row-weighted real instead would compare a
per-game-mean aggregate to a per-row-mean one and would hide the exact-reproduction
point behind a weighting difference.)*

### The genuine control (P1) — the one to read

Permutes the **assignment of an already-computed value to rows**: the team-season
allowance values are reshuffled across teams within season, then re-assigned to
shots. Preserves the marginal distribution and the clustered row structure;
destroys only the true team↔allowance pairing.

Headline cell (**B1 × O2**), null mean / sd / `frac_ge_real`:

| metric | real (row-level) | null mean | null sd | z | frac_ge_real |
|---|---|---|---|---|---|
| corr | +0.0288 | −0.0017 | 0.0098 | **+3.13** | **0.000** |
| beta | +0.3732 | −0.0238 | 0.1413 | **+2.81** | **0.000** |
| diff | +0.0176 | −0.0005 | 0.0098 | +1.85 | 0.030 |

Against the like-for-like team-season-mean comparator (corr +0.0441, diff +0.0391,
beta +0.6471) all three metrics are **0/400**.

E0's own cell (B0 × O1) sits at z = +3.80 / +3.29 / +3.76, 0/400 on all three.

**The hi-lo difference is the weakest of the three metrics** (p ≈ 0.03) and is
also the one E0 headlined. Worth knowing.

### P2 — reported, but not the one to read

Shuffling values across *rows* within season destroys the within-team clustering
and so gives an **understated** noise floor (sd 0.0055 vs P1's 0.0098). Everything
is 0/400 there too, but P1 is the honest null.

### Deterministic controls

`C1` (opponent pooled FG% allowed instead of the rim-specific residual) and `C2`
(Above the Break 3). **Their sd is 0 by construction — there is nothing random in
them.** This is *not* the D0 defect signature and must not be read as one.

---

## 7. Partition compliance

Filter points are marked `# FILTER-POINT` in the source: per-file immediately
after each `read_parquet` (with `sorted(season.unique())` printed per file), again
on the concatenated frame with `assert season.max() <= 2024` and
`game_date.dt.year.max() <= 2024`, again on each assembled frame before any
statistic, again on load in `placebo.py` and `robustness.py`, and once more
immediately before every write.

`verify_partition.py`: **0 structural violations.** Four targeted textual hits,
all of them prose describing the partition rule itself (this screen's docstring
and the frozen baseline's SPEC/module/validator docstrings). No data value.

**Artifact contamination** was tested with `asof_granularity == "row"` from each
artifact's `.manifest.json` — **not** `fit_seasons`/`fit_through_season`, which
only say what a file *contains*, and **not** a raw byte-scan for "2025"/"2026",
which produced a false partition violation in this program by matching row counts
and digit runs inside floats.

- `data/shotcharts/shots_*.parquet` — no manifests exist (0 found in that
  directory). Raw single-season sources; the season *is* the filename, so there is
  no pooled quantity that could carry holdout information. Only the 8 files for
  2021–2024 were opened.
- `data/masters/master_player.parquet` — `asof_granularity = "row"`, safe when
  filtered. This screen's own code path never reads it; it is reached only inside
  the frozen baseline's `validate_baseline.py`, which scores E1_I0011's
  `frame.parquet` (2021–2024, asserted at load).
- `data/zone_maps/*.csv` — **not read.** E0 established their shrinkage priors are
  pooled across 2021–2026. That decision is deliberately preserved; zone rates are
  rebuilt from raw per-season shot files.

---

## 8. R² convention

**Plain unweighted OLS R² = 1 − SSE/SST, SST about the unweighted mean of the
response.** Declared explicitly; the shared E0 `wls_r2` helper was **not** used.

That helper computes SST of the sqrt-weight-transformed response about *its own*
mean rather than weighted SST about the weighted mean, making every ΔR² from it
roughly 8% too small. The direction is conservative so nothing produced by it is
overstated — but **ΔR² figures in this screen are not comparable to three
significant figures with figures from screens that used it.**

---

## 9. Verdicts

| target | verdict |
|---|---|
| RA conversion × opponent rim allowance — existence & within-partition persistence | **keep_as_lead** |
| The E0 headline **magnitude** (+0.0444 corr / +0.0392 diff) | **kill** |
| Player-game ΔR² over `own_rate_v2_split_alpha` | **keep_as_lead** (weak; ~0.001 R², unstable) |
| Corner 3 / ATB3 / Paint non-RA / Mid-Range / Backcourt | **kill** (already killed at E0; reproduced) |

The middle row is the load-bearing one. The lead survives; **the published number
does not, and should be replaced by +0.0176 diff / +0.0288 corr / beta +0.373
wherever it is carried forward.**

---

## 10. What could not be established

- **No multiplicity correction** across the 5 zones E0 tested. Restricted Area was
  pre-selected by an independent between-team dispersion test rather than by its
  interaction size, which mitigates but does not remove the concern.
- **The shot-selection / tendency channel was not tested** — whether a player's
  *share* of shots at the rim shifts with the opponent's rim-share allowance. Only
  the conversion channel is measured, same as E0.
- **Concentration by player type / role was not tested.** The player-season
  fixed-effect result shows the effect is within-player, but not whether it is
  broad-based or driven by a subset of high-volume rim finishers.
- **No walk-forward, no preregistration** — deliberately out of E1 scope.
- **B2's shrinkage constant K = 50 was chosen by judgement, not tuned.** B2 is a
  robustness variant only; the headline uses B1, whose constants come from the
  frozen baseline.
- **Pace, rest and home/away were not conditioned on.** The opponent allowance is
  built from shot-event data alone.
