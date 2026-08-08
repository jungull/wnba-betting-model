# E1_I0026_detection_floor — PREREGISTRATION

**Written and hashed BEFORE any statistic in this directory was computed.**
The hash of this file (SHA-256 of its bytes) is recorded in `FINDINGS.json` under
`preregistration.sha256`, together with every addition and every drop made afterwards.

Character: **E1 diagnostic.** Every output here is a measurement of the programme's own
machinery. Nothing here is a lead, a result, or a promotion. No registry, ledger, graph-event
or idea-log entry is written by this screen.

Partition: **exploration seasons 2021–2024 only**, enforced by `screenkit.assert_partition`
(a VALUE test on parsed dates and season-valued columns) after every load and every filter.
2025 and 2026 are never read, joined, plotted or described.

---

## 1. The question

The programme has run ~1,000 candidate cells and killed nearly all of them. It has never
computed the **smallest effect its own designs can detect**. The best lead ever measured is
dR2 **+0.0023** (D089); two leads were killed on arithmetic ceilings of **0.001127** (D079)
and **0.000129** (D084); one screen reported a resolution floor of 1.6–2.2e-04 for its own
design only (D097). If the minimum detectable effect under the programme's own null machinery
sits above those numbers, a large share of the negative record is a power failure rather than
a finding.

## 2. Frames (read-only, from completed screens)

| role | path | rows |
|---|---|---|
| primary | `E1_I0018_teammate_volume_channel/screen_frame.parquet` | 14,852 |
| opponent-feature join | `E0_I0016_efficiency_predictors/screen_frame.parquet` | 14,852 |

Both frames are the frozen outputs of completed screens (D085, D089). They are joined on
`(player_id, game_id)`; the join is required to be **1:1 and lossless** and the check is
recorded. The primary frame is chosen deliberately: it is the frame that produced the
programme's **best-ever lead**, so a power statement about it is a power statement about the
design that generated the number everything else is compared against.

Structure of the primary frame: 247 players, 12 teams, 827 games, 313 dates, seasons 2021–2024.

## 3. Designs

**Strata** (exactly as `E1_I0018/s03_screen.py` defines them):

| id | definition | n |
|---|---|---|
| `POOLED` | all rows | 14,852 |
| `DECISION` | `n_prior >= 8 AND prior5_minutes >= 24` | 5,673 |

**Bases** (exactly as `E1_I0018/s03_screen.py` defines them):

| id | columns |
|---|---|
| `B_SINGLE` | `[1, refB_ppm]` — D085's base |
| `B_COMPLETE` | `[1, refB_ppm, refB_spm, refB_pps, refB_mpg]` |

**Outcome**: `y_ppm` (the screening outcome of D085/D089).

**Sample-size sweep** (separate arm, `B_SINGLE`): n ∈ {3549, 4517, 5111, 5673, 9517, 11738,
14327, 14852}, obtained by sampling **whole player-seasons** (never rows), so cluster count
falls with n exactly as it does in a real smaller screen. These n values are the ones that
actually appear in the ledger's screens.

## 4. Nulls — the programme's real ones

All four are run through `_screen_kit/screenkit.py` (224 assertions, stable, imported not
copied). The anticonservative within-player *shuffle* is not used; the kit refuses it (K6) and
the cyclic variant is used instead. **Cluster-robust standard errors are not computed and are
not offered as a substitute** (confirmed inadequate three times: D085 README trap 1).

| id | null | kit call | carrier |
|---|---|---|---|
| `N_A` | within-player cyclic shift | `permutation_null(scheme=SCHEME_WITHIN_CYCLIC, group_col=["player_id","season"], order_col="game_date")` | `CP` |
| `N_B` | entity swap, team-season | `entity_swap_null(entity_cols=["team_id","season"])` | `CP` |
| `N_C` | entity swap, opponent-team-season | `entity_swap_null(entity_cols=["opp_team_id","season"])` | `CO` |
| `N_D` | within-date opponent swap | `permutation_null(scheme=SCHEME_BETWEEN, group_col=["opp_team_id","game_id"], block_col="game_date")` | `CO` |
| `N_R` | row-level | `permutation_null(ROW_LEVEL)` — **CONTRAST ONLY, never a verdict** | both |

Carriers, chosen before any statistic and fixed:

* `CP = P01_c04_prevgame` — the strictly-prior-only reconstruction of the programme's best
  lead. Player-varying, autocorrelated by construction, real grouping structure.
* `CO = A10_opp_defrtg` — a strictly-prior opponent defensive-rating aggregate. Constant
  within opponent-team-game, which is what makes the opponent-level nulls well posed.

`detect_grouping_level` is run on both carriers and its full output is recorded before any
null is chosen.

## 5. Planting — declared in full

Effects are planted **into the response**, using the **real feature's real distribution and
real grouping structure**. Nothing is simulated from scratch.

1. Fit the base on the **real** response: fitted `F`, residual `e`.
2. `e_null` = the residual **cyclically rotated within (player_id, season)** by a random
   offset per player-season. A rotation preserves each player-season's residual level, its
   marginal distribution, and its serial correlation; it destroys only the alignment between
   the residual and the carrier. This is the same operation the programme's own honest null
   uses, applied to the response instead of the feature.
3. `y_null = F + e_null`. By construction `R2_base(y_null) ≈ R2_base(y_real)` and the residual
   noise level is the real one.
4. `xt` = carrier residualised on the base.
5. `y(δ) = y_null + c·xt`, with `c = +sqrt(δ · SST0 / (xt·xt))`. The alternative is
   one-sided "greater", as every screen in this programme uses.
6. The statistic is the screens' own: `dR2 = ((e(δ)·xt)² / (xt·xt)) / SST(y(δ))`, with the
   base refit on `y(δ)`, i.e. `tv_base.BaseFit.dr2`, which is `screenkit.delta_r2_plain`
   (D069 convention, SST about the unweighted mean).
7. `t = (dR2 − μ_null) / σ_null`.
8. Reject per-cell at α = 0.05 when `t ≥ q95` of that null's own standardised draws.
9. Reject family-wise for family size K when `t ≥ q95` of `maxT` over K cells drawn from the
   **real** 154-cell × 600-draw matrix `E1_I0018/permutation_draws.npz`, which carries this
   programme's actual between-cell correlation.
10. Power = fraction of R replicates rejecting. **MDE80** = the δ at which power crosses 0.80,
    by log-linear interpolation on the grid.

**Effect grid**: δ = 0, then 25 points log-spaced from 1e-5 to 1e-2.
**Replicates**: R = 2000 per (design, null, δ).
**Family sizes**: K ∈ {1, 18, 39, 44, 132, 154, 250, 318, 348}. K ≤ 154 samples cells
**without** replacement from the real matrix; K > 154 samples **with** replacement and is
labelled an extrapolation everywhere it appears.

## 6. Declared assumption, and the test that can fail it

The null draw set is computed **once per (design, null)** and reused across δ and across
replicates. This is only legitimate if the null's width does not move when a small effect is
planted.

**Pre-committed check:** recompute `σ_null` on `y(δ_max = 1e-2)` for 20 independent replicates
and report the maximum relative drift against the `δ = 0` value. **If the drift exceeds 10%,
the factorisation is abandoned and the nulls are recomputed per replicate.** The measured
drift is reported in `FINDINGS.json` whatever it is.

A second pre-committed check: at δ = 0 the per-cell rejection rate must be ≈ 0.05. If it is
not, the machinery — not the finding — is what has been measured, and that is reported first.

## 7. Where I could have cheated (declared before the fact)

1. **Carrier selection.** A carrier with unusually favourable structure would flatter the
   floor. Both carriers are fixed here, before any statistic, and both are real columns from
   completed screens. A third carrier is **not** added later; if one is, it is recorded in the
   added/dropped counts.
2. **Reusing the real response's null width.** Declared in §6 with a test that can fail.
3. **Reporting the per-cell floor and quietly dropping the family-wise one.** Both are
   reported for every design; the headline number is the family-wise one at the screen's own K.
4. **Extrapolating K > 154.** Labelled everywhere.
5. **Choosing the stratum that gives the nicest number.** Both strata are reported for every
   null and both appear in the verdict.
6. **Choosing δ grid endpoints that bracket a flattering crossing.** The grid spans 1e-5 to
   1e-2, three orders of magnitude around every ceiling in the ledger, fixed here.
7. **Retrospective flagging by hindsight.** Step 2 uses only each screen's *design*
   (n, grouping level, family size) and never its result, to decide whether it was powered.

## 8. Deliverables

`FINDINGS.json`, `NOTES.md`, `POWER_VERDICT.md`, `power_curves.csv`,
`retrospective_power.csv`, `run_log.txt`, `scripts/`.

Results are written to disk incrementally, one file per stage, so a crash leaves evidence
rather than nothing.
