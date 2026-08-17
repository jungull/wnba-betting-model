# DEFECTS — E1_I0044

Two lists. **D-** entries are defects in *this* screen's own work. **F-** entries are defects
this screen found in other screens' work and did not create.

---

## D — MY OWN

### D-1. My first repaired null was itself defective, and I kept it.

The composed null as first written (`scripts/s04_remeasure.py`, arm files
`nulls/composed_null_*.npz`) reused `E0_I0014`'s own `block_index` line
`idx[b] = don[np.arange(len(b)) % len(don)]` and then reshuffled positions. That line
**truncates a donor longer than the receiver to its first `len(b)` rows**, so for a candidate
that is monotone in game index the permuted value stays correlated with block length. Measured
consequence: on arm `A1_FULL` the composed-1 null left `pts__n_prior_games|minutes_absres`
centred at **−3.36** with sd 1.14 (degeneracy ratio 2.95) and `pl_games_prior|minutes_absres` at
**−3.38**. Only **28 of 72** broken cells passed the functioning test, and **91 of 348** cells in
the whole family failed it.

Composed-2 (`scripts/s07_remeasure_v2.py`) replaces the truncation with a uniform resample of the
whole donor block, `idx[b] = don[rng.integers(0, len(don), len(b))]`. **330 of 348 pass**; the 18
that do not are exactly the 18 structurally void cells. Median degeneracy ratio over the family
**1.3259** against the symmetric-null value 1.32; median `|mean signed t|` **0.0230**.

**Both runs are on disk and neither is deleted.** `_REMEASURE_ALL_ARMS.csv` is composed-1;
`_REMEASURE2_ALL_ARMS.csv` is composed-2 and is the one every number in `VERDICT.md` uses.

### D-2. The composed-2 null is NOT uniformly calibrated, and one of my top-ranked survivors sits on a cell where it over-rejects.

`TYPE_I_CALIBRATION.csv`, measured at δ = 0 on 400 block-resampled effect-free responses per
cell, 300 null draws each (MC se 0.0109 at the nominal 0.05):

| cell | composed-2 | E0_I0014's own level-matched null | row-naive |
|---|---:|---:|---:|
| `pl_minutes_prior\|minutes_absres` | 0.0225 | 0.0175 | 0.2625 |
| `pl_dnp_frac5\|pts_sqres` | 0.0250 | 0.0675 | 0.1800 |
| `pl_usg_sd5\|pts_absres` | 0.0525 | **0.2500** | 0.2800 |
| `pts__pred_cv\|fga_absres` | **0.1475** | **0.5925** | 0.5475 |
| `pl_games_prior\|pts_absres` | **0.5950** | **0.9250** | 0.9075 |
| **median** | **0.0525** | **0.2500** | **0.2800** |

**Two of five fail.** `pts__pred_cv` is `pred_sd / pred_point`, a ratio with a heavy right tail
(measured within-block spread on the z-scale 33.7, an order of magnitude larger than any other
candidate) — 0.1475, three times nominal. `pl_games_prior` is a pure within-block counter
(0, 1, 2, …); its within-block deviation is essentially the game index and is near-identical
across blocks, so **no permutation of it can reproduce the real column's autocorrelation
structure** and every scheme tried — mine, `E0_I0014`'s, and the row-naive one — rejects at
0.595, 0.925 and 0.908. **For counter candidates there is no valid null on this design, and that
includes the one I built.**

`pts__pred_cv` occupies four of the top seven places in the arm-A4 survivor ranking and
`pl_games_prior` and `pts__n_prior_games` appear in the A1 ranking. All are marked
`TYPE_I_UNCALIBRATED` in `SURVIVOR_RANKING_*.csv`. **49 of the 54 re-measured cells have no
measured Type-I at all**, so the credible counts (12 of 17 on A4, 31 of 37 on A1) are ceilings.

I did not retune the null after seeing the ranking. A heavy-tailed ratio needs a rank-based
statistic or a studentised bootstrap, and a monotone counter needs a null that preserves its
autocorrelation; inventing either now would be fitting.

### D-3. My analytic floors are optimistic by a factor of 1.4–2.0 against injection.

`INJECTION_VERIFICATION.csv`. `MDE80 = (bar_abs + z80·sd_signed)²/n`, the form `E1_I0041`
validated to a median ratio of 0.989 across 96 *synthetic* conditions, comes out at
**0.739** and **0.491** (analytic ÷ injection-verified) on the first two real cells. So every
`ADEQUATELY_POWERED` verdict in `BROKEN_NULLS.csv` that rests on an analytic floor is
**optimistic**, and using injection-verified floors would move cells toward BLIND, not away.
Every floor in the deliverables carries `floor_basis`; only the cells in
`INJECTION_VERIFICATION.csv` are `INJECTION_VERIFIED`.

### D-4. I killed two of my own processes.

`s10_injection.py` (PID 35364) and `s12_typeI_and_fw.py` (PID 31472) were rebuilding a
permutation index inside the replicate loop and would have taken about three hours. Both PIDs
were launched by this screen, are recorded in `scripts/_s10_pid.txt` and `scripts/_s12_pid.txt`,
and were stopped **individually by PID**. No blanket kill, no `Get-Process python | Stop-Process`,
no `taskkill` was issued at any point in this screen. `s12`'s part B (family-wise p) had already
completed and its output `_FAMILYWISE_P_COMPOSED2.csv` is used; part A was replaced by
`s13_typeI_injection_fast.py`.

`s13` reuses a pool of 600 permuted carriers per cell rather than rebuilding one per replicate,
drawing 300 without replacement per replicate. Replicates therefore share a permutation pool.
This is a real approximation and it makes the Type-I estimates slightly correlated across
replicates; it does not bias them.

### D-5. My construction-site finder over-matched on its first pass and I had to reject 34 generators.

Resolving a candidate name against a *format literal* in source (`app["pl_%s_sd5" % tag]`) is
legitimate — it matches the code's own name generator, not the candidate's spelling. But the
first pass accepted `["%s_%d" % (arm, s)]` from an unrelated dict write in
`E0_I0019/s00_inspect.py:63`, which matched **351 of the 540** candidate names, and
`playoff_note[f"{s}"]` from a file in `player_program`, which matched **410**. Both would have
been name-based inference wearing a code-shaped hat. Three objective rejection rules were added
before any candidate was resolved (≥4 literal characters, ≤10 candidate matches, file inside
`experiments/exploration/`); the rejects are listed with their reasons in
`_GENERATORS_REJECTED.csv`. Cost: 203 GENERATED resolutions fell to 33, and 140 candidates fell
back to a weak site and became `UNDETERMINABLE_SITE` until the source-read pass recovered them.

### D-6. 71 of the 540 pairs have no construction site and 28 composites stay UNDETERMINABLE.

Named in full in `COMPOSITE_SWEEP.csv`. The 28 are not a residue of laziness — 23 of the 51 that
entered undeterminable were resolved by *measuring* variance shares on the screens' own frozen
frames (`MEASURED_COMPONENT_SHARES.csv`), which is the move `E1_I0040` used to resolve 44 of its
50. The remaining 28 include four `E1_I0030` accounting terms that **have no null of any kind**
(F-2 below), three `E1_I0034` cells whose share is not on disk at the null's entity (the same
three `E1_I0040` left open), and three `E0_I0017` composites whose components are raw box
columns not carried into `screen_frame.parquet`.

### D-7. The composite invariant needed a second form and I wrote it after seeing the population.

The invariant as adopted — *a composite candidate requires a null valid for every component* —
is stated for permutation nulls of the candidate. Ten of the 23 screens decide their cells with
a **paired cluster sign-flip**, where nothing is permuted and the question becomes whether the
cluster covers the dependence each component induces. I extended the rule to *the cluster must
be at least as coarse as the coarsest level any component varies at* and applied it. That
extension is mine, it was written after I saw which screens use which null, and every verdict
that rests on it is marked `COMPOSITE_MODEL_SPEC` in `COMPOSITE_SWEEP.csv` so a reader who
rejects the extension can drop those rows. Under the narrow reading, the exposed count falls
from **15 to 5**.

### D-8. PREREG predictions: P1 and P2 held, P3 held, P4 FAILED, P5 half-failed.

* **P1** (composed null functions on ≥90% of re-measurable cells): held for composed-2 —
  54 of 54 non-void broken cells function on every arm. It did **not** hold for composed-1
  (28/72 on A1), which is D-1.
* **P2** (the void 18 classify PERMANENTLY UNVERIFIABLE on every arm): held.
* **P3** (at most 5 of the 35 remain adequately powered on A1): **failed in the stated
  direction but not in the stated magnitude** — 17 remain adequately powered on A1. It holds
  on the decision-stratum clean arm A4, where 0 remain.
* **P4** (every re-measured cell has p ≥ 0.05 on A4): **FAILED. 37 of 54 have p < 0.05.**
  This was the prediction whose failure would be the finding, and it failed.
* **P5** (<25% composites, ≤20 exposed): the second clause held (15 exposed); the first
  **failed** — 174 of 540 pairs, **32.2%**, are composites.

---

## F — FOUND IN OTHER SCREENS

### F-1. `E0_I0014` computes `p_conservative_both = max(p_between_block_null, p_within_block_null)`.

`s04_screen.py:280` — `pb = float((nb >= abs(rt)).mean())`, `pw = float((nw >= abs(rt)).mean())`,
written to `screen_results.csv` as `p_conservative_both`. That is the exact
`max(p_within, p_between)` signature `E1_I0038` named and the programme banned. `E0_I0014` is in
`E1_I0036`'s census, not in the thirty `E1_I0040` swept, so `E1_I0040`'s "does not occur anywhere
in the thirty" is not contradicted. **The column is not the verdict column** — `p_correct_level`
is, and D103 reads that one — so nothing downstream is corrupted by it. Recorded because the ban
is programme-wide and the column is still on disk.

The same pattern is live and *is* the verdict in `E0_I0024_reb_ast_characterisation`:
`s04_screen.py:153`, `p_correct = float(max(p_swap, p_cyc))`.

### F-2. `E1_I0030` publishes four composite accounting terms with no null of any kind.

`__RECON_sum_of_parts`, `__RECON_residual`, `__RECON_within_via_minutes`,
`__RECON_within_via_ppm` appear in `player_reconciliation.csv` with **empty `null_sd`, `t` and
`p_pergame_signflip`**, and they are absent from `_s03.json`'s `decomposition_term_nulls`, which
covers only `G`, `within_player` and `composition`. Two of the four are arithmetic identities and
need no null (`__RECON_residual` is 4.22e-15). The other two — the minutes/ppm split of the
within-player term, values 0.2410 and 1.0734 — are substantive quantities published without one.

### F-3. `E1_I0027`'s twelve "candidates" in `AUDIT_TABLE_EXT.csv` are effect sizes, not names.

`E1_I0040/scripts/s04_audit_table.py:490-492` registers that file with `cc = None` (no candidate
column), and line 544 falls back to `str(r.iloc[0])` — the first column of
`reprice_by_rung.csv`, which is `dr2_common_sst`. So twelve audit rows carry a ΔR² where a
candidate name should be. The real identities are in that file's `feature` column
(`P01_c04_prevgame`, `A10_opp_defrtg`, `G01_noise`). The same fallback puts `ALL_2021_2024` and
`REGULAR_SEASON` — `E1_I0030` stratum keys — into the candidate column.

### F-4. `AUDIT_TABLE_EXT.csv` records `candidate_level = "game-level plus-minus"` and `var_share_between = 1.0` for `E1_I0031`'s `pm_all`, and both are wrong for the bundle.

The 1.0 is a **max over components** (`E1_I0040/scripts/s06_resolve.py:104-107`), not a bundle
measurement, and the label is correct for `pm_game_level`, not for `pm_all`, which also contains
`pm_prev_season_imp` at player-season. The exposure verdict `E1_I0040` reached is right; the two
descriptive fields that support it are not.

### F-5. `E1_I0031`'s `RAPM_as_feature` bundle asserts only 4 of its 10 columns constant within player-season, and its season-mean imputation moves a season-level constant as if it were player content.

`s01_prereg.py:36` asserts `net_100_lam2000`, `z_net_100`, `z_orapm_100`, `z_drapm_100` only, and
only on `f[f["has_rapm"]]`. The other six — three lambda variants, `log_total_poss_imp`,
`has_rapm_f`, `z_net_x_poss` — are unverified. On the ~18% of rows with no RAPM
(`rapm_row_coverage` 0.8204) the `_imp` fill is a **season** mean, so `z_net_x_poss` there is a
product of two season constants that the player-season relabeller then shuffles between players.
Swept as NOT_EXPOSED because the relabel does move all ten together; recorded because the
premise rests on four assertions covering four of ten columns.

### F-6. `E1_I0022`'s `tier_lt3_priors` / `tier_ge3_priors` overlap the six numbered tiers.

`s05_inference_and_where.py:82-85` computes all eleven slices on the same `WF` rows. Any
family-wise count that treats the eleven as disjoint is wrong. Not acted on here; recorded.

### F-7. `E1_I0025` uses the string `POOLED` for two different things.

A stratum id (`E1_I0023/s00_prereg.py:67-71`) and a fit population (`cbase.py:196, 270`). Both
appear in `pooled_tier_dummy.csv`. This is the substring collision the programme has lost six
findings to, sitting in a live results file.
