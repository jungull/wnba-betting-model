# E0_I0029 -- THE FREE-THROW HURDLE

**PREREG SHA256 `e1ef0849e5f79230e27a0baa8b63ce0e6a1f24cca0a3b261cbfa7ba67c69f757` -- 21 candidates,
5 bases, 6 targets, 280 cells, 560 cell runs, added 0, dropped 0.**
Partition 2021-2024, headline 2022-2024. 2025/2026 never read. Champion never loaded.

---

## THE FOUR-LINE ANSWER

1. **The predictability is in the HURDLE, not the rate.** On a common denominator, reaching the
   line buys `+0.24016`, how many attempts buys `+0.17019`, and **conversion buys `+0.02792`**.
   A player's own prior free-throw percentage barely predicts a single game's percentage at all.
2. **The player's own free-throw process does not reach points.** Added to a walk-forward points
   forecast it is worth **-0.001014**. The points base already contains her prior points.
3. **The OPPONENT's free-throw allowance does, and its ceiling is the largest this programme has
   measured** -- `dR2 = 0.002951` on points, DECISION stratum, family-wise `p = 0.0050`, **1.43x
   the 0.002057 benchmark**, and `+0.002865` out-of-sample walk-forward. But it is **one number
   wearing six names**, and its magnitude is concentrated in 2024.
4. **The champion models no free throws at all on the player arm**, while the team arm carries an
   explicit `ch_ft` channel -- and because the hurdle decomposition is **exactly mean-preserving**,
   the only thing free throws could ever have bought the player arm is distributional shape, which
   is exactly what its scalar-plus-residual-envelope cannot represent.

**This is not the clean null the task anticipated.** The player-side channel is closed; the
opponent-side one is open and is the largest measured ceiling in the ledger.

---

## THE PREMISE, VERIFIED ON BYTES

Every feasibility number the ideation queue used reproduces inside the exploration partition,
which matters because the quoted figures were computed over six seasons and this screen may read
only four (`run_log_s00.txt`, `_s00.json`):

| quantity | quoted (6 seasons) | re-derived (2021-2024) |
|---|---|---|
| FT share of points | 0.1737 | **0.173663** |
| `fta == 0` fraction | 0.4640 | **0.464035** |
| `corr(ftm, pts)` | +0.6595 | **+0.659477** (bound R2 0.434911) |
| `corr(fouls_drawn, pts)` | +0.6749 | **+0.674848** (bound R2 0.455420) |
| coverage | 100% | **100.000%** on `ftm`, `fta`, `fouls_drawn` |

**And the hurdle is real, not a low rate.** Mean `fta` is 1.9011; a Poisson with that mean puts
0.1494 at zero against an observed **0.4640** -- an excess of **+0.3146**. By the law of total
variance, knowing *only whether* a player reached the line accounts for **45.74%** of `Var(ftm)`.
`ftm` is 7.72% of `Var(pts)` on its own and **18.32%** counting its covariance with the rest of
scoring.

---

## STEP 1 -- WHICH STAGE CARRIES THE PREDICTABILITY

### The denominator problem, and how it is handled (D099)

Stage A lives on the full stratum; stages B and C live on the `fta>0` subset. Their R2s are on
different SSTs and **must not be compared**. If they were, stage C would look like the answer:
its oracle rung reaches `R2 = 0.887` and only **11.31%** of it is irreducible -- by far the most
tractable number in the ladder. **That is an artefact.** Stage C's oracle exposure is the
*realised attempt count*, and `ftm` is nearly determined by `fta`. It is the same shape D097 caught
in total rebounds. The tell is that the conversion **rate** itself is barely predictable at all:
the matched prior reference scores **+0.0296 (DECISION)** and **-0.0993 (POOLED)** on `FT% | FTA`.

So the cross-stage comparison is made only on `SST(ftm)` over the **full** stratum, by switching
one stage at a time between LEAGUE / HONEST / ORACLE in a composed forecast.

### The answer (DECISION stratum, n = 5111, `hurdle_stages.csv`)

| stage | honest predictability bought | share of the 0.32943 total |
|---|---|---|
| **A -- reaching the line** | **+0.24016** | **72.9%** |
| B -- attempts given one | +0.17019 | 51.7% |
| C -- conversion | **+0.02792** | **8.5%** |

(The shares exceed 100% because the stages overlap; the decomposition is not additive, which is
why both orderings are reported.) On POOLED the split is even starker: A **89.6%**, B 29.2%,
C **6.4%**.

**Where the irreducible variance sits is a different question with a different answer:**

| stage | add-one-oracle | leave-one-honest |
|---|---|---|
| A | +0.22282 | +0.25876 |
| **B** | **+0.45782** | **+0.50777** |
| C | +0.06501 | +0.08312 |

So: **the hurdle is where the honest predictability is; the attempt count is where the
unforecastable variance is; conversion is neither.** Conversion being a dead end is itself worth
recording -- it is the most intuitive place to look and it has almost nothing in it.

### The oracle ladder, per stage (DECISION stratum, `oracle_ladder_ft.csv`)

| target | stage | n | denominator | R2 REF (matched) | R2 best honest | R2 O2 (oracle) | **irreducible even to O2** | headroom |
|---|---|---|---|---|---|---|---|---|
| `y_any_fta` | A | 5111 | FULL | 0.13173 | 0.13870 | 0.22708 | **77.29%** | 0.08838 |
| `y_fta_given` | B | 3733 | subset | 0.11505 | 0.14649 | 0.21392 | **78.61%** | 0.06743 |
| `y_ftm_given` | C | 3733 | subset | 0.11944 | 0.15018 | 0.88695 | 11.31% *(artefact)* | 0.73677 |
| `y_fta` | AB | 5111 | FULL | 0.21063 | 0.22877 | 0.31841 | **68.16%** | 0.08964 |
| **`y_ftm`** | **ABC** | **5111** | **FULL** | 0.20510 | 0.22521 | 0.30541 | **69.46%** | **0.08020** |
| `y_pts` | anchor | 5111 | FULL | 0.30066 | 0.32224 | 0.48316 | **51.68%** | 0.16092 |

**The ladder is calibrated.** The points anchor reproduces D097's 51.68% at **51.6840%** on the
identical n = 5111 decision stratum -- so these numbers sit on the same scale as everything already
in the ledger rather than being a fresh construction.

**Carry this number in any future free-throw proposal**: free-throw points have **0.080** of
reachable headroom against points' **0.161**. That is essentially the same as assists' 0.082, which
D097 ruling 2 says is not worth screening. **On the player's own side, D097's arithmetic applies
here unchanged.**

---

## AN EXACT IDENTITY, AND IT IS ONE OF THE FINDINGS

With `n` prior games, `k` of them with `fta>0`, `S_fta` and `S_ftm` the prior sums:

```
HON_A * HON_G * HON_C = (k/n) * (S_fta/k) * (S_ftm/S_fta) = S_ftm/n = prior mean of ftm
```

Verified to `1.332e-15` over 17,578 rows and asserted in `s06_ceiling.py` so it cannot quietly stop
being true.

**Decomposing the hurdle buys exactly nothing for a point forecast.** The three stage estimators
multiply straight back into the aggregate estimator. Whatever the hurdle is worth is worth it in
the **shape of the distribution** -- the 46.4% mass at zero -- and never in the conditional mean.
This is the sharpest available form of the structural finding in Step 4, and it also explains why
nobody found this by accident: a mean-preserving decomposition would not have shown up as a better
point forecast if anyone had tried it.

---

## STEP 2 -- THE MATCHUP QUESTION

**What D085 did and did not test.** D085 killed the *interaction* (own prior FT-draw rate x opponent
prior fouls conceded); its two main effects were the **control**, never the candidate, and its
twelve opponent constructions were screened against points, rebounds and assists -- **never against
free-throw production**. So the main-effect question was genuinely open.

### It is real, and it is large on the free-throw targets

81 of 214 `B_COMPLETE` cells clear family-wise `p < 0.05`. On the DECISION stratum the opponent
terms reach `dR2` of 0.005-0.010 on free-throw targets (`M02_opp_allowed_fta_pg` = 9.713e-03 on
`y_ftm`, `p_fw` 0.0017).

### And it is ONE degree of freedom, not six

Once the opponent's prior **FTA-allowed per game** is in the base, everything else collapses
(`matchup_decomposition.csv`, DECISION stratum, response **points**):

| candidate | over `B_COMPLETE` | over `B_COMPLETE_PLUS_M02` | collapse |
|---|---|---|---|
| `M03_opp_allowed_ftm_pg` | 0.002951 (`p_fw` 0.0050) | 0.001057 (`p_fw` 0.215) | 2.8x, loses significance |
| `M01_opp_pf_pg` | 0.001990 (`p_fw` 0.0349) | **0.000004** | **~500x** |
| `M04_opp_allowed_ft_rate` | 0.001566 (`p_fw` 0.143) | 0.000872 | 1.8x |
| `M05_opp_allowed_hurdle_rate` | 0.000917 | 0.000017 | 54x |
| `M06_opp_pace` | 0.000359 | 0.000009 | 40x |

**The opponent matchup is one number -- how many free throws a team gives up -- wearing six names.**
Fouls committed, FT rate allowed, hurdle rate allowed and pace are all that number restated. This
must be reported as **one degree of freedom**, and any future work must not count it as six.

The single sharpest statement of it: **44 opponent-or-interaction cells clear family-wise over
`B_COMPLETE`; exactly 1 still clears once opponent FTA-allowed is in the base** -- `M04` on POOLED
points at `dR2 = 0.000709`, which is 0.34x the live benchmark and *below* the dead shot-mix
benchmark. Everything else in the opponent family is `M02` restated.

### D085 reproduces exactly, on a target D085 never tested

`X01_fd_x_oppfoul`, the D085 interaction rebuilt on free throws, over a base **already containing
both of its own main effects**:

- DECISION / `y_any_fta`: **1.703e-04**, `p_correct` 0.313
- DECISION / `y_pts`: 0.000649, `p_correct` 0.048, **family-wise `p` 0.539 -- does not clear**
- POOLED / `y_pts`: 1.293e-04, `p_correct` 0.088

It does not clear anywhere once its own components are controlled. **D085's finding holds on a new
target.** The `B_COMPLETE` figures are printed in `matchup_decomposition.csv` and are explicitly
labelled diagnostics of the trap, not results.

---

## STEP 3 -- DOES IT REACH POINTS, AND WHAT IS THE CEILING

Ceiling form `(|beta| * sd_candidate / sd_y)^2` (D084/D089). Note that with the **base-residualised**
`sd`, this quantity is algebraically identical to the achieved `dR2` over that base -- so these are
**attained** values, not merely bounds.

### DECISION stratum, response POINTS, sd_y = 7.5837 (`arithmetic_ceiling.csv`)

| signal | ceiling (resid) | x 0.002057 | 1 sd moves points by | verdict |
|---|---|---|---|---|
| `FT_ORACLE_REALISED` *(oracle)* | 1.564e-01 | 76.0x | 3.00 pts | upper bound of the whole channel |
| **`M03_opp_allowed_ftm_pg`** | **2.951e-03** | **1.43x** | **0.41 pts** | **ABOVE the largest measured** |
| `M02_opp_allowed_fta_pg` | 2.396e-03 | 1.16x | 0.37 pts | ABOVE the largest measured |
| `M01_opp_pf_pg` | 1.990e-03 | 0.97x | 0.34 pts | at the live benchmark |
| `M04_opp_allowed_ft_rate` | 1.566e-03 | 0.76x | 0.30 pts | between dead and live |
| `F02_prior_fd_pm` | 1.288e-03 | 0.63x | 0.27 pts | between dead and live |
| `FT_HONEST_COMPOSED` (own side) | 5.685e-04 | 0.28x | 0.18 pts | below the dead shot-mix benchmark |
| `G01_noise` *(negative control)* | 4.946e-04 | 0.24x | 0.17 pts | **the noise floor on this metric** |
| `G02_placebo_noop` | 0.000e+00 | 0.00x | 0.00 | confirmed no-op |

Read the noise row before the others: at n = 5111 a pure random regressor attains 4.9e-04, so
anything below about 1e-03 here is not distinguishable from nothing. `M03` is **6x** the noise floor.

### Out-of-sample, which is the test that matters (`propagation_walkforward.csv`)

Fitted on strictly earlier seasons only:

| addition to a `B_COMPLETE` points forecast | POOLED | DECISION |
|---|---|---|
| own composed honest FT forecast | +0.002503 | **-0.001014** |
| **opponent prior FTM-allowed** | +0.000500 | **+0.002865** |
| opponent prior FTA-allowed | +0.000414 | +0.002240 |
| both opponent terms | -0.000655 | +0.003267 |
| REALISED `ftm` *(oracle bound)* | +0.124985 | +0.156610 |

**The player's own free-throw forecast is worth nothing** (negative out-of-sample on the decision
stratum): the points base already contains her prior points, and by the identity above her
free-throw forecast is just a component of that. **The opponent's allowance is worth +0.002865**,
above the live benchmark, out of sample.

### THE CAVEAT THAT MUST TRAVEL WITH THE HEADLINE

`per_season_consistency.csv`, DECISION stratum, `M03` on points:

| season | `dR2` | `beta` |
|---|---|---|
| 2021 | 5.09e-05 | +0.031 |
| 2022 | 2.08e-03 | +0.162 |
| 2023 | 7.78e-04 | +0.119 |
| **2024** | **8.45e-03** | **+0.435** |

**The sign is positive in 4 of 4 seasons, but the magnitude is dominated by 2024** -- roughly a 4x
spread in beta across seasons. The pooled-window figure is not a stable per-season effect, and the
result **does not reproduce on the POOLED stratum** (`dR2` 0.000599, family-wise `p` 0.245), which
is the *opposite* of this programme's usual pattern. Anyone taking this forward should treat
`0.002951` as an upper end of a range whose lower end is near zero, and should note that the
carrier is an **opponent team-season** quantity with about 12 effective values per season.

---

## STEP 4 -- THE STRUCTURAL QUESTION

**The champion carries no free-throw component on the player arm at all.** Verified by reading its
source and artifact schemas; the champion was never loaded, retrained or refitted.

- `player_scoring_distribution` is an **EWMA of the player's prior per-36 TOTAL points x (EWMA
  minutes / 36)** -- one continuous scalar -- wrapped in a residual-derived 5-quantile envelope
  (`cbs_v7.py:437-458`, `cbs_player_runner_v14.py:273-278`, `cbs_builders.py:317-323`). There is no
  2PT/3PT/FT decomposition anywhere.
- `ftm`, `fta`, `ft_pct` and `fouls_drawn` are **dropped at the frame boundary**
  (`cbs_real_frames_v3.py:614-632` -- the `keep` list carries only `minutes`, `points`, `fga`).
  The estimator never sees them.
- `attempts_usage` is **FGA only** -- no `0.44*FTA`, no true-shooting-attempts construction
  (`cbs_v7.py:449-451`).
- A regex for `ftm|fta|ft_pct|free.?throw|fouls_drawn` returns **zero hits across all 16
  champion-lineage `.py` files**.
- The data was **available, not missing**: `master_player.parquet` carries all four columns at
  100% coverage across 2021-2024.

**The asymmetry is what makes this a finding rather than an omission.** The **team** arm carries an
explicit free-throw channel -- `cbs_real_frames_v3.py:722`, `tg["ch_ft"] = tg["ftm"]`, one of four
channels (`ft` / `3pt` / `paint` / `np2`) that satisfy an asserted points identity. **The same
programme decomposed team scoring into free throws and did not decompose player scoring.**

**Why it matters, sharpened by the identity above.** The champion represents free-throw production
as a constant fraction of a scoring rate. This screen measures that (a) the free-throw component is
governed by a hurdle whose predictability is concentrated in the hurdle and not the rate, (b) it is
on a different and lower predictability scale from the rest of scoring, and (c) **the decomposition
is exactly mean-preserving**, so it could only ever have paid in distributional shape -- and a
46.4% mass at zero is exactly the shape a scalar-plus-residual-quantile-envelope cannot hold. This
is D091's post-mortem item 5 made concrete: *"points-per-minute pools field-goal volume, shot mix,
conversion and free throws ... if different components are predictable to different degrees,
aggregating destroys the signal before it can be measured."*

---

## A DEPARTURE FROM THE PREREGISTRATION, MADE ON MEASURED POWER

The preregistered correct-level null for `player_season` candidates was **`N_CYCLIC`**, D093's
within-player cyclic shift. **An injection power check shows it is degenerate.** Handed a signal of
exactly `dR2 = 0.002057` by construction, it returns **`p = 1.0000`** -- at every injected size, on
every target, on both strata, **0 of 15 configurations detected**.

The mechanism: a cyclic rotation leaves each player's **mean** exactly unchanged, and an
own-history trait varies almost entirely **between** players. The rotation preserves precisely the
variation it is meant to destroy.

`N_PSWAP` (whole player-season series reassigned within season, exactly as `N_ENTITY` does for
opponents) was added and its power measured on the same injections (`injection_power.csv`):

| null | 0.002057 | 0.001127 | 0.000500 | 0.000129 |
|---|---|---|---|---|
| `N_ENTITY` (opponent) | **6/6** | **6/6** | 3/6 | 0/6 |
| `N_PSWAP` (player) | **6/6** | **6/6** | 4/6 | 0/6 |
| `N_CYCLIC` (preregistered) | **0/6** | **0/6** | **0/6** | **0/6** |

`p_correct_level` is the max over `{N_ENTITY, N_PSWAP}`. `N_CYCLIC` is retained in full in
`screen_results.csv` (`p_N_CYCLIC_EXCLUDED_no_power`) and excluded from every verdict. Candidate
list, bases, targets and strata are unchanged; **the prereg hash stands, 0 added, 0 dropped**.

**This also bounds what this screen may claim.** Nothing here is detectable below about
`dR2 = 0.0005`, so **the 0.000129 benchmark is beyond this screen's resolution** -- an effect that
size would be reported as absent whether or not it exists.

**Implication beyond this screen.** D093's repair was correct for the anticonservatism it
addressed, and D097 records it catching a false positive. But against a *between-entity* candidate
it is inert. **Any null verdict in this programme resting on a within-player cyclic shift against a
between-player candidate should be re-read as "not established" rather than "absent".**

---

## GUARDS

- **TIME-WINDOW TABLE** covers features *and* inference: 13 rows, `FINDINGS.json`
  `time_window_table`, every `reads_future=True` row labelled RESPONSE / ORACLE RUNG and never in
  any base.
- **Eight brute-force leakage probes**, each recomputed from raw bytes *and* carrying a
  **discrimination arm** proving the column does **not** equal the contemporaneous recomputation
  (a probe that only shows "matches a prior recomputation" is vacuous if the two happen to agree).
  All pass. `leakage_probes.csv`.
- **Partition** asserted on **column values** after every load and every filter, never a name scan.
  2025/2026 (12,250 rows in the same file) never read.
- **Negative control** `G01_noise`: family-wise `p<0.05` in **0.0%** of cells; max `dR2` 6.46e-04,
  which is the honest noise floor on `dR2` at this n.
- **No-op placebo** `G02`: max `|dR2|` = **0.000e+00** across 24 cells -- confirmed no-op, which
  also confirms the base being fitted is the base that was declared.
- **Perturbation**: `G03` is not the identity, but its `dR2` is *correctly* near zero (it is a
  corrupted copy of a column already in the base), so the sensitivity question is answered by the
  injection check above instead.
- **Null inflation**: median correct-level/row-level SD inflation 1.27x, max 4.26x. The row-level
  `p` is reported beside every verdict solely to expose this and never carries one. Cluster-robust
  SEs are not used.
- **Two defects found in this screen's own work**, both by guards rather than inspection, both
  fixed and both documented with evidence that the fix changed only what it should. See
  `DEFECTS.md`. **D-01 was making the headline conclusion look stronger than it is**; it survives
  the fix on a smaller margin.

---

## WHAT SHOULD HAPPEN NEXT (for whoever rules on this)

1. **Do not propose player-side free-throw work.** Headroom 0.080 against points' 0.161, own-side
   propagation negative out-of-sample, and the decomposition is mean-preserving. D097's arithmetic
   applies unchanged.
2. **The opponent free-throw-allowance term is the live item, as ONE degree of freedom.** It is the
   largest ceiling this programme has measured (1.43x the previous largest) and it survives out of
   sample -- but it is 2024-heavy, absent on POOLED, and carried by an opponent team-season
   quantity with ~12 effective values per season. It needs a confirmation design, not a bigger
   screen.
3. **The structural finding is worth more than the feature, as the task anticipated.** The player
   arm aggregates away a component that (a) has a 46.4% zero mass, (b) is exactly mean-preserving
   under decomposition, and (c) the *team* arm already decomposes. Whether that costs anything is a
   model question this screen is not authorised to answer.
4. **Re-examine null choice programme-wide.** The degeneracy of the within-player cyclic shift
   against between-player candidates is a method finding that reaches past this screen.
