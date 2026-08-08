# E0 I0013 — Possession volume as a driver of player production, at player level

**Status: E0 exploration screen. Non-claiming.** No registry entry, no preregistration, no
leaderboard row, no promotion threshold, no REPORT.md. Everything below is a **lead or a kill**,
never a result.

**Cells screened: 27** (9 formulations × 3 targets). **Killed: 26. Kept as lead: 1.**

**Partition: 2021–2024 only.** The 2025/2026 confirmation holdout was never read, joined, filtered
against, counted, plotted or described. Verified in `run_log_partition_verification.txt`, which
re-parses every file this directory wrote and tests the *values* of season and date columns — not
by a byte-scan for "2025"/"2026", which has produced a false violation in this program twice.

---

## 1. Where this sits

Layer-3 **personnel matching** is closed. `E0_I0012_layer3_noncollinear` killed 29 of 30 cells and
`E1_I0012_survivor_2021drop` killed the last one. I did not rebuild any of it: no familiarity, no
availability, no style-fit, no positional matchup.

What I took instead is what I0012's own conclusion named as the live surface — **possession
volume** — plus the three follow-ups it deliberately left unrun (cleaner supply-side pace
instruments, an OREB channel, volume heterogeneity). Those are new work here, not a rescue.

## 2. The one design change that made this a different question

I0012 modelled `y = per-100-possession rate`. **That divides possession volume out of the outcome
by construction**, which is why volume could only ever show up there as an interaction. This screen
models the **raw counting stat**, on the decomposition

```
count  =  rate  ×  minutes  ×  possessions-per-minute
```

and puts the first two into the base model so every candidate has to beat the naive prediction:

```
y_count ~ O + D + O*D + Mexp + O*Mexp
```

`O` is the player's pregame expanding per-100 rate, `D` the opponent's pregame expanding **overall**
allowance of that stat (excluding the player's own prior contribution), `Mexp` the player's pregame
expanding minutes per game. `R²_base` is 0.394 / 0.423 / 0.416 for pts / reb / ast on n = 10,167
shared rows.

Because `D` and `O*D` are **in the base**, every increment reported is orthogonal to overall
opponent strength by construction. Worth stating plainly, since it is a nice simplification: the
explicit residualisation of each candidate on `[D, O*D]` **does not change the main-effect ΔR² by
one ulp** — it is the same projection. I kept it because it does change the interaction terms and
the reported β scale, but the costume control is enforced either way.

## 3. What I screened

| # | direction | formulations |
|---|---|---|
| D1 | opponent / own pace as **main** effects, plus supply-side instruments | `opp_pace48`, `own_pace48`, `opp_fgaA48` (FGA allowed/48), `opp_missA48` (misses allowed/48 = OREB supply), `opp_missO48` (opponent's own misses/48 = DREB supply) |
| D2 | expected game possessions | `exp_gposs` = mean of both teams' pregame pace |
| D3 | possessions-per-minute as an exposure channel distinct from minutes | `ppm` |
| D4 | layer-2 OREB main effect | `opp_orebA100` (OREB allowed/100), `own_orebR100` (own OREB/100) |
| D5 | volume heterogeneity | terciles of pregame minutes and pregame usage, applied to the above |

I dropped nothing from the brief. I added the two miss-supply instruments and the own-team OREB rate
because D1's tempo proxy and D4's allowance both have an obvious mechanistic competitor, and it is
cheaper to screen them together than to come back.

## 4. The primary test, and what counts

**Primary test in every cell is the MAIN effect ΔR²** — 27 tests. The two interaction increments
(`O × Mres` and `(O×Mexp) × Mres`) are computed and reported but **never placebo'd**, so they have
no noise floor, are not leads, and are not ranked against anything.

## 5. Data hazards, verified rather than assumed

- `master_player.possessions` — **clean**, and I checked rather than trusting the prior screen:
  range 0–95, median 39, `corr(possessions, minutes) = +0.9950`. Used.
- `master_player.pace` — **corrupt**, confirmed: max 7200, `corr(pace, minutes) = +0.20`.
  `pace_per40` (max 6000) and `estimated_pace` (max 7200) are the same defect. **Not read.** All
  pace comes from `master_team` via `base.team_possessions`.
- `master_player.position` — lineup-slot label. Not used.
- `observed_time` — dropped at load, re-checked before every write.

## 6. The four traps

### Trap 1 — costume. Did not bite.
Within-season |r| against overall opponent defensive allowance ranges **0.00 to 0.45** across the 27
cells, against I0010's disqualifying +0.57/+0.59. The highest is `opp_orebA100` vs rebounds at
+0.45, and that cell is dead anyway. The one survivor sits at **−0.06**. And again: `D` and `O*D`
are in the base, so this is a diagnostic, not the control.

### Trap 2 — retrospective baseline. Did not bite.
Every quantity on both sides is built with `base.prior_expanding`: aggregate to date level, then
strict cumulative-minus-self within `(season, key)`. A value serving a target game comes only from
rows **strictly before** that game's date, in the **same season**. Shrinkage priors use the
*previous* season's totals, which is prior information. There is no leave-one-out, no
leave-one-season-out, no leave-one-game-out full-season anything. I read the construction of every
imported helper rather than trusting its name.

Two rungs in the robustness stage **do** use post-hoc quantities — actual minutes played and actual
possessions. They are labelled as **mediation diagnostics, not forecasting models**, and no verdict
rests on them.

### Trap 3 — anticonservative t. **IT BIT, and it would have manufactured four leads.**
Seven of nine candidates are team-season aggregates: 12 values per season, **48 team-season
clusters** across the partition, shared across every row facing that team. So no verdict anywhere
uses a classical t. Every cell got a cluster-level permutation null, a cluster-robust sandwich SE
with the cluster count printed, and a joint family-wise max-T null.

I also ran the **naive row-level permutation on every cell, purely to measure the damage.** It is
**1.00× to 3.82× narrower** than the correct cluster-level null, median 1.62×. Four cells cross 0.05
under the wrong null and do not under the right one:

| cell | naive frac ≥ real | correct (cluster) frac ≥ real |
|---|---|---|
| pts × `own_pace48` | 0.025 | **0.185** |
| pts × `ppm` | 0.010 | **0.085** |
| ast × `ppm` | 0.030 | **0.065** |
| ast × `opp_missO48` | 0.050 | **0.145** |

Two more sit just outside (ast × `opp_orebA100` 0.060 → 0.145; ast × `own_orebR100` 0.065 → 0.145).

A second observation that matters for anyone reaching for cluster-robust SEs as the fix: **clustering
does not uniformly widen the SE here.** For ast × `exp_gposs` the t goes 4.44 → **4.62**; for
pts × `own_pace48` it goes 1.96 → 1.47. The permutation null, not the sandwich, is what the verdicts
rest on.

### Trap 4 — the no-op placebo. Run on purpose; signature reproduced exactly.
I permuted the team grouping key consistently in `master_team` **and** in the player frame and then
**recomputed** the pregame aggregate from the permuted key, 200 draws, on `opp_pace48 × pts`.

```
real dR2_M        = 0.0004531994
no-op mean        = 0.0004531994
no-op sd          = 0.0000000000   <-- the defect signature
max |draw - real| = 2.7e-19        (floating-point noise)
```

The permuted cell is the same row set under a bijection, so every row still receives its own true
value. **By contrast the real cluster-level control for that same cell has mean 0.000081, sd
0.000104** — non-degenerate. Across all 59 placebo distributions in this screen the **minimum sd
observed is 7.79e-05** and none is degenerate. The split-half reliability figure in
`survivor_checks.json` is deterministic and is labelled **"sd 0 by construction"** so it can never
be confused with the defect.

## 7. What died, plainly

**26 of 27 cells.** Grouped by why:

**Sixteen cells never cleared their own noise floor at all.** The whole rebound family is the
clearest: with the exception of the two pace variables, every rebound cell sits flatly inside its
placebo (frac ≥ real of 0.425 to 0.935). `own_orebR100` on points is ΔR² = **0.000000** with frac
0.985 — as dead as a cell can be.

**Ten cells cleared their own floor and were killed on multiplicity.** 11 of 27 cells reached
nominal frac ≥ real ≤ 0.05. Against a **joint max-T randomization null** over all 27 cells — 400
draws, one opponent-side and one own-side team relabelling per season applied to every candidate and
every target *within the same draw*, so the null preserves the real correlation between cells — the
null has p50 = 2.64, **p95 = 5.69**, max = 8.28. Exactly one cell clears it. The other ten are the
false positives a 27-test sweep predicts:

| cell | ΔR² | z | nominal | family-wise p |
|---|---|---|---|---|
| pts × `opp_fgaA48` | 0.000529 | 5.01 | 0.000 | 0.098 |
| reb × `opp_pace48` | 0.000579 | 4.30 | 0.000 | 0.168 |
| pts × `exp_gposs` | 0.000736 | 4.20 | 0.015 | 0.185 |
| pts × `opp_pace48` | 0.000453 | 3.59 | 0.010 | 0.300 |
| ast × `own_pace48` | 0.000476 | 3.48 | 0.015 | 0.320 |
| ast × `opp_pace48` | 0.000533 | 3.31 | 0.020 | 0.350 |
| reb × `exp_gposs` | 0.000616 | 3.27 | 0.025 | 0.357 |
| pts × `opp_orebA100` | 0.000433 | 3.29 | 0.015 | 0.357 |
| pts × `opp_missA48` | 0.000471 | 2.71 | 0.015 | 0.480 |
| ast × `opp_fgaA48` | 0.000350 | 2.50 | 0.025 | 0.542 |

### Three specific things this settles

1. **The layer-2 OREB main effect is screened and dead.** I0012 sent it to the layer-2 backlog on
   the strength of opponent-OREB-allowed predicting player points with betas positive in 4/4
   seasons. Here it reaches nominal 0.015 on points and dies family-wise at p = 0.357, is flatly
   dead on rebounds (frac 0.840) and assists (0.145), and own-team OREB rate is dead everywhere.
   There is also a mechanistic point against it: **it is the one candidate that is not absorbed by
   realised possessions** (66% of its increment survives conditioning on actual player possessions,
   against 2–28% for everything else). So even if it were real, it would not be the
   possession-generation channel it was proposed as.

2. **Possessions-per-minute as a player-specific exposure channel is dead.** Nominal 0.085 / 0.065 /
   0.700 on pts / ast / reb, family-wise p 0.83 / 0.80 / 1.00. Minutes remains the exposure
   component that matters; the per-minute component adds nothing measurable at this precision. Two
   of the three `ppm` cells are also trap-3 casualties — they looked significant under the wrong
   null.

3. **The supply-side instruments do not beat the tempo proxy.** I0012's NOTES predicted that
   opponent shot attempts and opponent missed shots per 48 — the actual rebound supply — should beat
   `dpace` if the mechanism was what it thought. On rebounds, the target where that story was
   sharpest, all three supply instruments are flatly inside their floors (0.675 / 0.935 / 0.665)
   while the tempo proxy is the strongest rebound candidate. **The mechanistic story that misses are
   the real rebound supply is not supported.**

## 8. The one survivor

**Expected game possessions → assists.** `exp_gposs` = mean of the two teams' strictly-prior pregame
expanding possessions-per-48, predicting a player's raw assist count.

| diagnostic | value |
|---|---|
| ΔR²(main) over R²_base 0.4165 | **0.001133** |
| β | +0.079 assists per sd |
| cluster placebo mean / sd | 0.000088 / 0.000130 |
| draws ≥ real | **0 / 200** |
| family-wise z / p (400 draws, null p95 = 5.69) | **8.04 / 0.003** |
| collinearity vs overall opponent defence | **−0.06** |
| classical t / cluster-robust t (48 clusters) | 4.44 / 4.62 |
| split-half reliability of the pace instrument | r 0.680, **SB 0.809** (48 team-seasons) |

### It is a possession-volume effect, and the mediation says so
- Given **actual minutes played**: retains **96%**. A fast game does not lengthen the game, so a
  volume effect should be indifferent to minutes — and it is.
- Given **actual player possessions**: retains **16%**. 84% is absorbed by the realised mediator the
  pregame instrument is supposed to be forecasting. That is the signature a possession-volume story
  predicts, and it is the check that distinguishes this from `opp_orebA100`, which keeps 66%.

### It is not team strength or home advantage
Confound ladder, all rungs pregame-observable and on top of `O`, `D`, `O*D`: adding home, then both
teams' strictly-prior net points per 100, then both teams' strictly-prior win rate, then all of them
together, leaves ΔR² at **0.001051 — 93% retained**.

### 🚩 It is LAYER 2, not layer 3
`exp_gposs` is exactly `0.5 × (opp_pace48 + own_pace48)`, so putting all three in one model is
rank-deficient — **precisely the void rung I0012 recorded**. The estimable reparameterisation is
`{sum, difference}`, which spans the same 2-D space and is full rank:

| target | ΔR²(sum) | ΔR²(joint, 2 df) | ΔR²(difference \| sum) |
|---|---|---|---|
| pts | 0.000736 | 0.000754 | 0.000018 |
| reb | 0.000616 | 0.000717 | 0.000101 |
| **ast** | **0.001133** | 0.001133 | **0.000001** |

For assists the difference between the two teams' pace carries **essentially nothing**. This is
**symmetric game tempo — a game-level possession-volume main effect — and explicitly not an opponent
matchup.** That is the mirror image of I0012's survivor, which was asymmetric (β +0.19 opponent vs
−0.10 own) and therefore a matchup. Neither team's pace alone survives family-wise; only their sum
does.

### It does not decay toward the holdout — which is the opposite of I0012's survivor
This is the check that killed the last lead, so I ran it first, each slice against **its own** cluster
placebo recomputed at that n:

| slice | n | ΔR² | β | placebo mean | placebo sd | frac ≥ real |
|---|---|---|---|---|---|---|
| 2021–2024 | 10,167 | 0.001133 | +0.0790 | 0.000086 | 0.000114 | **0.000** |
| 2022–2024 | 8,039 | 0.000698 | +0.0700 | 0.000117 | 0.000158 | 0.005 |
| 2023–2024 | 5,555 | 0.000676 | +0.0696 | 0.000204 | 0.000243 | 0.060 |
| **2024 alone** | 2,771 | **0.002574** | **+0.1315** | 0.000769 | 0.000906 | 0.065 |

Per-season: 2021 ΔR² 0.002526 (β +0.086), 2022 0.000728 (+0.071), **2023 0.000012 (β −0.010)**,
2024 0.002574 (+0.132). I0012's survivor decayed monotonically and in 2024 sat **below** its own
placebo mean. This one's **2024 point estimate is the largest of the four seasons and sits about 2
sd above its own placebo mean**. Neither recent slice clears 0.05 individually — but at n = 5,555
and 2,771 the floors are wide, and the *sign* of the failure is opposite to I0012's.

### Volume heterogeneity — descriptive only, no noise floor
The gradient is clean and monotone in both splits for the survivor:

| split | T0 | T1 | T2 |
|---|---|---|---|
| pregame minutes | ΔR² 0.000010, β −0.005 | 0.002558, +0.111 | 0.002784, +0.133 |
| pregame usage | 0.000225, +0.029 | 0.001414, +0.100 | 0.002251, +0.108 |

The effect is absent in low-minute players and concentrated in high-minute, high-usage ones, which
is what an exposure channel should do. **No permutation null was computed on the tercile splits**, so
this is descriptive and is not a lead in its own right.

### Why it is still only a lead
- ΔR² 0.001133 is **small** — about the size of I0012's now-dead survivor, roughly 6× under I0009's
  existing 0.006–0.007.
- **2023 is a dead season for it** (ΔR² 0.000012, β −0.010). Noisy rather than monotone is better
  than a decay, but it is not stability.
- Neither recent slice clears 0.05 on its own floor.
- It is a **game-level tempo main effect**, so it will correlate with whatever the market already
  prices into totals. **Nothing here tests incremental value over a price**, and that is the first
  thing I would want to know before spending anything on it.

## 9. What I did not get to

I was time-boxed and stopped rather than thinning. Not done:

1. **No OREB/DREB split of the rebound target.** I0012's follow-up 3 is still unrun. Every rebound
   cell here died before the split would have mattered, but the split itself was not performed.
2. **No noise floor on any interaction term.** 54 secondary increments are reported and none is a
   lead.
3. **No noise floor on the heterogeneity terciles.**
4. **No test against a market price**, and none against rest, travel, injury or known-lineup
   information.
5. **No sensitivity analysis** on the `minutes >= 10` analysis cut or on the shrinkage constants
   (30 minutes for `ppm`, 2 games for `Mexp`, 300 prior possessions for team fields).
6. **The survivor's 2023 collapse is unexplained.** If someone spends more on this lead, that is the
   first thing to look at — the same way I0012's decay was.

## 10. Files

| file | what it is |
|---|---|
| `pv_base.py` | shared base; imports `E0_I0012/base.py` **read-only** and re-points its `OUT` into this directory at import so no reused helper can write outside our scope; partition guard, team pregame table, player exposure quantities, OLS + cluster-SE machinery |
| `run_screen_defs.py` | the candidate registry — single source of truth for both run stages |
| `run_screen.py` | the 27 cells, cluster + naive placebos, the deliberate no-op diagnostic, volume heterogeneity |
| `run_maxt_robust.py` | family-wise max-T; actual-minutes and actual-possessions mediation rungs; sum-vs-difference reparameterisation |
| `run_survivor_checks.py` | reliability, confound ladder, recency slices for the one survivor |
| `make_findings.py` | assembles `FINDINGS.json` by reading the result JSONs; retypes no number |
| `verify_partition.py` | re-parses every file this directory wrote and tests season/date column **values** |
| `run_log_*.txt` | full stdout of every run, including every printed season list |
| `placebo_draws_*.csv`, `maxt_null_draws.csv`, `noop_diagnostic.csv` | the raw draw distributions behind every placebo line |

**Write scope.** This directory only. `E0_I0012_layer3_noncollinear` was imported from and **not
modified**; `base.OUT` was re-pointed here at import and `PYTHONDONTWRITEBYTECODE=1` kept even
`.pyc` files out of it. Verified after the fact: no file anywhere else in the repository was
modified by this screen.
