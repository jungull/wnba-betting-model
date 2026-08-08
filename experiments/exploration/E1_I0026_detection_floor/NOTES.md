# E1_I0026_detection_floor — NOTES

E1 **diagnostic**. Every output here is a measurement of this programme's own machinery. Nothing
here is a lead, a result, or a promotion. No registry, ledger, graph-event or idea-log entry was
written by this screen, and none should be written on its behalf without the user's decision.

Preregistration: `PREREGISTRATION.md`, SHA-256
`9260f7dbcb2560daa7f141231d78954f52dad90fdb688710283f42406442ea7c`, hashed before any statistic
in this directory was computed.

Partition: **2021–2024 only**, enforced by `screenkit.assert_partition` (a VALUE test on parsed
dates and season-valued columns) after every load and every filter. 2025/2026 were never read,
joined, plotted or described.

---

## 1. What was actually done

Effects of known size were planted into **real** frames and recovery was measured under the
programme's **real** nulls, from `_screen_kit` (imported, not copied).

**Frame.** `E1_I0018_teammate_volume_channel/screen_frame.parquet` (14,852 rows), joined 1:1 and
losslessly on `(player_id, game_id)` to `E0_I0016_efficiency_predictors/screen_frame.parquet` for
the opponent columns. 247 players, 12 teams, 827 games, 313 dates, 48 team-seasons, 600
player-seasons. This is the frame that produced **D089**, the programme's best-ever lead, chosen
so that a statement about its floor is a statement about the design that generated the number
everything else is compared to.

**Designs.** Strata and bases are `E1_I0018/s03_screen.py`'s own, unchanged:
`POOLED` (14,852) and `DECISION` (`n_prior>=8 & prior5_minutes>=24`, 5,673);
`B_SINGLE = [1, refB_ppm]` and `B_COMPLETE = [1, refB_ppm, refB_spm, refB_pps, refB_mpg]`.
Outcome `y_ppm`.

**Carriers**, fixed in the preregistration before any statistic:
`P01_c04_prevgame` (player-level, strictly prior, within-player acf1 **+0.476** — materially
autocorrelated, so `SCHEME_WITHIN` is refused by the kit and the cyclic variant is used, K6) and
`A10_opp_defrtg` (opponent-level, constant within opponent-team-game — `detect_grouping_level`
returns `COARSER_LEVEL_FOUND` at `team_game`/`opp_team_game`).

**Nulls.** All from the kit. Cluster-robust SEs were **not** computed and are not offered as a
substitute (README trap 1, confirmed inadequate three times).

| id | kit call | clusters (POOLED / DECISION) |
|---|---|---|
| `N_A` within-player cyclic shift | `permutation_null(SCHEME_WITHIN_CYCLIC, ["player_id","season"], order_col="game_date")` | 600 / 343 |
| `N_B` entity swap, team-season | `entity_swap_null(["team_id","season"])` | 48 / 48 |
| `N_C` entity swap, opponent-team-season | `entity_swap_null(["opp_team_id","season"])` | 48 / 48 |
| `N_D` within-date opponent swap | `permutation_null(SCHEME_BETWEEN, ["opp_team_id","game_id"], block_col="game_date")` | 1,632 / 1,388 |
| `N_E` entity swap, player-season **(added after hashing)** | `entity_swap_null(["player_id","season"])` | 600 / 343 |
| `N_R` row level | `permutation_null(ROW_LEVEL)` — **contrast only, never a verdict** | — |

---

## 2. The planting, and why it is honest

A permuted carrier `x_r` drawn from the null being tested has the carrier's **real marginal
distribution** and **real grouping structure** — that is exactly what the kit's schemes preserve
by construction — and, under that null, no association with the response beyond chance. The
effect is added to the **real** response along it:

```
y(δ) = y_real + c · xt_r ,      c = sqrt(δ · SST0 / (xt_r · xt_r))
```

Nothing is simulated from scratch. Because the base design matrix `X` is fixed and `xt_r` is
already orthogonal to it,

```
e(δ)   = e + c·xt_r                                   (exactly)
SST(δ) = SST + 2c·(e·xt_r) + c²·(xt_r·xt_r)           (exactly)
dR2(δ) = ((e·xt_r + c·(xt_r·xt_r))² / (xt_r·xt_r)) / SST(δ)
```

so the whole δ grid is closed-form from two dot products per replicate. This is not an
approximation of the refit — it **is** the refit, written out, and it was checked against a
literal `BaseFit` refit on 75 random cases (worst absolute difference **1.457e-16**).

**At δ = 0 the statistic is literally a draw from the null**, so the type-I rate is 0.05 by
construction and the δ=0 row of every curve is a machinery check rather than a result. Across all
24 design cells it landed between **0.040 and 0.069** (median 0.049).

The fast dR2 was checked against `screenkit.delta_r2_plain` on the real frame: **|diff| =
7.55e-17**.

---

## 3. The preregistered check that failed

`PREREGISTRATION.md` §6 committed to abandoning the "compute the null once per design, reuse it
across δ" factorisation if the null's width drifted more than 10% on a planted response, and to
recomputing the MDEs with the drifted σ if it did.

**It failed, badly, and not in one direction.** Median relative drift in σ across the four design
cells per null (`out/s07_null_drift_probe.csv`; the first, coarser probe in
`out/s05_sigma_drift.csv` reached **+506%** on a single within-date cell):

| null | drift in σ at δ=1e-3 | at δ=1e-2 | consequence for the uncorrected number |
|---|---|---|---|
| within-date opponent swap | **+50%** | **+269%** | uncorrected floor was **anticonservative** |
| entity swap, opponent-team-season | +11% | **+115%** | anticonservative |
| entity swap, team-season | −13% | −1% | mildly conservative |
| within-player cyclic shift | **−29%** | **−73%** | uncorrected floor was **conservative** |

Every headline MDE was therefore recomputed (`s07`) with μ(δ) and σ(δ) **measured with the kit on
the planted response**, on a 4-point δ probe (6 replicates × 300 draws each), log-log
interpolated, and the fixed point of

```
sqrt(δ) = sqrt(μ(δ) + t_crit·σ(δ)) + 0.8416·sqrt(μ₀)
```

solved on a dense grid. Had the uncorrected numbers been reported instead, the within-player
cyclic floor would have been overstated by ~3x and the within-date opponent floor understated by
~2x. **Both sets are on disk** (`out/s04_mde_table.csv` uncorrected,
`out/s07_mde_drift_corrected.csv` corrected) rather than the uncorrected ones being deleted.

---

## 4. Family-wise thresholds come from the programme's own null matrix

`E1_I0018/permutation_draws.npz` holds a **real 154-cell × 600-draw** null matrix with this
programme's actual between-cell correlation. Thresholds are the median over 400 random K-cell
subsets of the 95th percentile of max-t.

| K | 1 | 18 | 39 | 44 | 132 | 154 | 250* | 318* | 348* |
|---|---|---|---|---|---|---|---|---|---|
| within-entity | 2.00 | 4.97 | 5.70 | 5.83 | 6.61 | 6.73 | 6.54 | 6.61 | 6.69 |
| entity swap | 2.00 | 5.07 | 5.75 | 5.87 | 6.97 | 7.01 | 6.96 | 6.97 | 6.97 |

`*` sampled **with** replacement — an extrapolation beyond the real family, flagged in every row
of `out/s04_familywise_thresholds.csv`. The threshold is flat from K=132 onward, so the
extrapolation carries little weight.

Note `t_crit(K=1) ≈ 2.00`, not 1.645: a dR2 null is right-skewed, and using a normal quantile
would understate every per-cell threshold.

---

## 5. The headline table (drift-corrected MDE80)

`DECISION`, n = 5,673:

| null | base | K=1 | K=18 | K=44 | K=132+ |
|---|---|---|---|---|---|
| entity swap team-season | B_COMPLETE | 0.00102 | 0.00190 | 0.00209 | 0.00235 |
| entity swap team-season | B_SINGLE | 0.00106 | 0.00196 | 0.00215 | 0.00241 |
| entity swap player-season | B_COMPLETE | 0.00111 | 0.00212 | 0.00235 | 0.00265 |
| within-date opponent swap | B_COMPLETE | 0.00097 | 0.00215 | 0.00244 | 0.00284 |
| within-player cyclic | B_COMPLETE | 0.00267 | 0.00383 | 0.00407 | 0.00428 |
| entity swap opp-team-season | B_COMPLETE | 0.00325 | 0.00732 | 0.00832 | 0.00974 |

`POOLED`, n = 14,852:

| null | base | K=1 | K=18 | K=44 | K=132+ |
|---|---|---|---|---|---|
| within-date opponent swap | B_SINGLE | 0.00029 | 0.00067 | 0.00077 | 0.00091 |
| within-date opponent swap | B_COMPLETE | 0.00031 | 0.00075 | 0.00086 | 0.00102 |
| entity swap team-season | B_COMPLETE | 0.00050 | 0.00091 | 0.00100 | 0.00112 |
| entity swap player-season | B_COMPLETE | 0.00056 | 0.00106 | 0.00117 | 0.00132 |
| entity swap opp-team-season | B_COMPLETE | 0.00084 | 0.00186 | 0.00212 | 0.00248 |
| within-player cyclic | B_COMPLETE | 0.00148 | 0.00212 | 0.00226 | 0.00238 |
| within-player cyclic | B_SINGLE | 0.00490 | 0.00633 | 0.00665 | 0.00692 |

Sample-size sweep (whole player-seasons dropped, never rows): `out/s05_mde_vs_n.csv`, eight n
values from 3,554 to 14,852. The floor falls as roughly **n^-0.65**.

---

## 6. The retrospective, and its one methodological wrinkle

The analytic MDE

```
MDE80 = ( sqrt(μ_null + t_crit·σ_null) + 0.8416·sqrt(μ_null) )²
```

follows from `dR2(δ) = (u + sqrt(δ))²` with `u ~ N(0, sqrt(μ_null))`, and was **validated against
the 5,616-row simulated power surface before being used**: analytic/simulated median ratio
**0.989** family-wise and **0.984** per-cell (p10–p90 0.73–1.16). It needs only quantities the
screens already publish, so no screen was re-run.

**Wrinkle.** Two screens published their nulls on the **classical-t** scale, not the dR2 scale:
`E0_I0014_residual_heterogeneity` (`null_correct_sd ≈ 0.87`) and `E0_I0019_availability_forecast`
(`nullsd_between ≈ 0.8–1.2`). For those, `MDE80 = ((t_crit + 0.8416)·σ_t)² / n`, using
`dR2 ≈ t²/n` for small increments; the null mean cancels because both threshold and shift are
measured from it. Every cell touched by that conversion carries `stat_family="t_statistic"` in
`retrospective_power.csv`. Their row counts were read from their own analysis frames
(13,879 and 17,809). One screen (`E1_I0023`) uses a **paired** sign-flip statistic centred at
zero, so `MDE80 = (t_crit + 0.8416)·σ`; those carry `stat_family="paired"` and are never mixed
with the others.

**Decision rule.** A screen's verdict is taken on the **worse** (larger) of its correct-level
MDEs, matching the programme's own `p_correct_level = max(...)` convention. **No screen's result
enters the decision about whether it was powered** — only n, null width, and family size
(preregistration §7 item 7).

**Coverage.** 1,349 unique cells with a published null width, across 7 screens. 56.3% blind to
0.0023; 90.0% blind to D079's 0.001127; 98.7% blind to D084's 0.000129. 628 cells were both
blind and reported as family-wise nulls.

**Not covered**, because they publish no null width in a machine-readable results file:
`E0_I0003/4/5/6/8/9/10/11/12/13`, `E1_I0004*`, `E1_I0008/9/11/12/13`, `E1_I0020/21/22/25`,
`E0_I0015`. Those screens report p-values without the null width that produced them, so their
detection floor cannot be reconstructed from their outputs at all. The honest position is that
their power is **unknown**, not that it is adequate. **A one-line fix for every future screen:
publish `null_mean` and `null_sd` alongside every p.** With those two numbers a successor can
compute what any cell could have detected, for free, forever.

---

## 7. Things a successor should know

**The within-player cyclic shift is not a stricter version of the entity swap — it is a different
question.** Its null mean on `P01_c04_prevgame` is **2.13e-3** against a real dR2 of **2.20e-3**
(p = 0.43) at POOLED/B_SINGLE. That is not the feature failing; it is the feature's association
living almost entirely **between** players, which every cyclic rotation preserves. The cyclic
null asks "does the within-player movement carry signal", and for that question this data has
essentially no resolution below ~0.0015 even pooled with a complete reference. Any screen that
runs the cyclic shift on a player-level prior and reports a null should say which question it
answered.

**Cluster count is not the lever it looks like.** 48 team-seasons vs 600 player-seasons: the same
floor. 1,632 opponent-team-games: 1.6x better. 600 player-seasons under a cyclic shift: 3x worse.
The ordering is by how much structure survives the null, not by how many exchangeable units there
are.

**Multiplicity saturates.** 1→18 costs 1.9x; 18→318 costs 1.24x more. The ledger's comparison of
p-values across screens of 18 and 318 cells is roughly fair; the unfair comparison is either of
them against a single pre-registered test.

**Incidental, deliberately not raised as a lead.** `A10_opp_defrtg` carries an in-sample
screening dR2 of **0.0082–0.0086** against `y_ppm` on the DECISION stratum, p = 0.0017 on both
opponent-level nulls. It was used here **only as a carrier** for opponent-level power
measurement. It is a single uncorrected in-sample cell on an outcome D085 did not screen the
A-family against (D085 screened them against **efficiency**, not points-per-minute), it has no
family-wise correction, no walk-forward check, no leakage probe, and no preregistered mechanism.
It is recorded so it is not lost. **It is not a lead and must not be cited as one.** If anyone
wants it, it needs its own screen.

---

## 8. Where I could have cheated

1. **Carrier choice.** Both carriers were fixed in the hashed preregistration and neither was
   changed. A carrier with more between-entity variance would have flattered every entity-swap
   floor.
2. **Reusing the unplanted null width.** Declared with a test that could fail. It failed. The
   headline numbers are the recomputed ones; the uncorrected ones are kept beside them.
3. **Reporting only the per-cell floor.** It is 1.9–2.3x better than the family-wise one. Both
   are reported everywhere and the verdict quotes the family-wise one.
4. **Extrapolating K > 154.** Flagged in every row of the threshold table.
5. **Stratum shopping.** Both strata are reported for every null and both are in the verdict.
6. **Grid endpoints.** Fixed at 1e-5..1e-2 before computing.
7. **Hindsight flagging in the retrospective.** Design only; never the result.
8. **One frame.** The power curves come from D089's frame, the programme's most favourable. The
   floors here are if anything optimistic for the rest of the programme; the seven-screen
   retrospective is the check, and it agrees.
9. **`N_E` was added after hashing.** It is a null, not a candidate — it cannot manufacture an
   effect — and its result went **against** the hypothesis that motivated adding it. Counted in
   `FINDINGS.json:preregistration.added_after_hashing`.

## 9. Files

| file | what |
|---|---|
| `PREREGISTRATION.md` / `.sha256` | the hashed design grid |
| `POWER_VERDICT.md` | the plain-language answer |
| `FINDINGS.json` | every number, machine-readable |
| `power_curves.csv` | 5,616 rows: power vs planted dR2, per design × null × family size |
| `retrospective_power.csv` | 1,975 rows: what each recorded cell could have detected |
| `mde_table.csv` | the drift-corrected MDE80 surface |
| `run_log.txt` | every stage's console output |
| `scripts/` | `df_base`, `s00`–`s10`, run in order |
| `out/` | every intermediate, written incrementally |
