# DEFECTS — E1_I0056_minutes_variance

Two lists. **D-** are defects in *this* screen's own work. **F-** are things this screen found in
other work and did not create.

---

## D — MY OWN

### D-1. My preregistered "strongest level reference" was not the strongest, and the error runs in my favour.

`PREREG.md` §3 names `L5` — the eight level columns plus squares, cubes and reciprocals — as the
rung "designed to span everything a level-only forecaster could use", and §4 makes
`dR2(C5 over L5)` the **PRIMARY** statistic. It is not the strongest rung. `L4` (the eight level
columns, linear, no expansions) scores **+0.034756** against `L5`'s **+0.033377**: the seven extra
terms cost 0.0014 of out-of-fold R² to overfitting on 2,945 rows.

**Consequence: my preregistered primary increment (+0.012057) is 0.0014 LARGER than the increment
over the best level reference available (+0.010678).** That is exactly the direction a reader
should distrust. I did not move the primary — the preregistered number is reported as the primary
— but the `L4` figure is reported beside it everywhere and is the one a sceptical reader should
use. This is a reference-incompleteness error committed *inside a screen whose headline is a
reference-incompleteness finding*, which is worth recording plainly.

### D-2. My preregistered power curve uses an iid injection and therefore OVERSTATES power.

`PREREG.md` §5 injects `y + c·sd(y)·u` with `u` iid N(0,1). A cluster sign-flip null over
player-seasons is at its **most** powerful against an iid per-row signal. The real block `N` is
nothing like iid: its median within-player-season lag-1 autocorrelation is ~0.57 and several of its
columns are near-constant inside a player-season. So the preregistered MDE is a **lower bound on
the true detection floor**, not the detection floor.

I did not revise the preregistered curve. I added a second, clearly labelled **POST-HOC**
curve (`s04_posthoc_power.py`, `POWER_INJECTION_CLUSTERED_POSTHOC.csv`) with a
player-season-constant injection, which brackets the real case from the other side. Every
conclusion about power is stated against **both** brackets.

### D-3. The `c = 0` row of my power curve is not a Type-I calibration, and the script's own label said it was.

`s03_worth.py` prints "false-positive rate at c=0 (should be near 0.05)". That is wrong: at `c = 0`
the candidate arm still contains the real block `N`, so the row measures the **detection rate of the
real observed increment**, not a false-positive rate. The genuine Type-I calibration is the `N3`
noise control in `s02` (block `N` replaced by 36 iid columns), which is a proper null and is
reported. The mislabelled line is left in the log rather than edited out, and the correction is
here.

### D-4. The matched-coverage interval comparison uses an oracle scaling.

`INTERVALS.csv`'s `mean_width_at_80pct_cover` divides each model's per-row sd by the 80th
percentile of `|residual| / sd`, computed **on the scored rows themselves**. That is an oracle. It
is applied identically to every arm, so it compares *widths at equal coverage* and nothing else,
and it is not used to support any claim about coverage. Disclosed here and in `NOTES.md`; the
nominal-80 % coverage column beside it is honest and un-oracled.

### D-5. The block bootstrap does not propagate fitting uncertainty.

`block_boot_dr2` resamples player-season blocks of **stored** out-of-fold predictions. The
predictions themselves were produced by a walk-forward that trained on all blocks, so the interval
covers scoring variability only, not the variability of the fit. Standard for this program's
screens; recorded so nobody reads the CI as complete.

### D-6. My cyclic null answers a narrower question than my headline asks.

`N1` shifts block `N` cyclically **within** each player-season. That destroys the timing of a
player's volatility features relative to her own outcomes but preserves everything that lives
*between* player-seasons — which is where most of the block's information sits. So `N1`'s p answers
"does the within-player-season timing matter?", not "does the block carry information at all?".
The question the headline asks is answered by the **paired cluster sign-flip (`N2`)** and the
**block bootstrap**, both of which are reported and both of which are the basis for the verdict.
`detect_grouping_level` returned `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE`, i.e. the
kit's K2 gap, and the kit's own answer to that gap (`entity_swap_null`) was **not** preregistered
and was **not** run. A future screen wanting a permutation answer to the between-player-season
question should run it.

### D-8. `s03` crashed on the conversion arms, and the first version of two of those arms was silently wrong before it crashed.

`s03_worth.py` run 1 (11:30, 2026-08-17) died with
`numpy.linalg.LinAlgError: SVD did not converge in Linear Least Squares` in the adaptive-blend
arm. **The stderr is preserved at `scripts/run_log_s03_err_CRASH1_PRESERVED.txt` and the partial
stdout at `scripts/run_log_s03_CRASH1_PRESERVED.txt`** — the sibling screen lost its equivalent
log (`E1_I0054` D-1) and I did not want to repeat that.

Cause: the walk-forward warm-up rows (the first 604, which are never scored) have **no**
out-of-fold prediction, so `lev_ref` and `vhat` are `NaN` there. The blend arm fitted its
coefficients on training windows containing those `NaN`s and crashed. **The variance-weighted
refit arm did not crash and would have returned `NaN` silently** — that is the more dangerous half
and it is why this is recorded as a defect rather than a hiccup.

Fixes, both of which change *implementation* and not any arm definition, threshold, seed or draw
count: the blend fits on the training rows where `lev_ref` is defined; the weighting `vhat` is
filled on warm-up rows only from the **strictly prior expanding mean of the response**, which is
the `L0` arm's own forecast and reads nothing a forecaster at that row could not have. No warm-up
row is ever scored — the script asserts and prints that. `s03` was then re-run in full; its seeds
are fixed so the power curve reproduces identically.

### D-9. Every paired cluster sign-flip p in this screen is uncalibrated, and I only know that because P11 was preregistered.

The `dR²` statistic for "add 36 columns to a ridge" is **not centred at zero under H0**: the noise
control's 200 draws have mean **−0.006882**, sd 0.001988, and **every single draw is negative**
(max −0.001482). Adding uninformative columns reliably costs out-of-fold R², so the paired loss
difference carries a systematic sign, and the two-sided cluster sign-flip **rejects at 0.420 against
a nominal 0.05**.

**Consequence: the sign-flip p = 0.342 for the primary increment is not usable, in either
direction, and neither is the p = 0.0194 on the replication response or the p = 0.0124 on the
post-hoc `L4`-over-`L1` comparison.** Every one of them is reported with that caveat attached, and
the verdicts rest on the **block bootstrap** instead, which resamples the entities the effect is
attached to and needs no centring.

This is `E1_I0054`'s D-3 on a different response and a much larger arm — it found mean −2.91e-4 and
a rate of 0.160 on a 1-column channel; this screen finds −6.88e-3 and 0.420 on a 36-column block.
**The defect scales with the number of added columns**, which is worth carrying forward: any screen
comparing a big arm to a small one with a sign-flip has this problem, and it gets worse the bigger
the arm.

I did not build a properly centred test. The available honest statements are the bootstrap CI and
the distance from the noise placebo (+9.53 sd), and both are reported.

### D-7. `s00` ran before this preregistration existed, by design, and I did not re-run it.

`scripts/s00_probe.py` executed 2026-08-09 under a coordinator that then died. Its log ends
cleanly and its stderr is empty, and it computes no candidate-to-response statistic, so I accepted
it as input rather than re-running it. Every structural claim it makes that this screen relies on
(the season-constancy of `pred_sd`, the `pred_cv` reciprocal identity) was **re-derived
independently in `s01` from the shipped parquet bytes**, so nothing rests on the un-re-run stage.

---

## F — FOUND, NOT CREATED

### F-1. The shipped per-row uncertainty is a per-season constant, and the emitting line is a scalar broadcast.

`cbs_player_runner_v14.py:313` passes `pd.Series(sd_v, index=test.index)` into `_emit` — a single
scalar `sd_v`, computed once per (fold, target) at `cbs_player_runner_v14.py:286` from
`cbs_v5.py:169-180 dispersion()`, broadcast to every test row. The same construction appears at
`cbs_v8.py:965`, `cbs_v8.py:1134`, `cbs_v7.py:1428` and `cbs_v7.py:1603`. The v15 arm forks
`cbs_v14._run` at exactly one identity line and leaves the inner core unforked, so this is the
live path for every prediction file in `experiments/cbs_v15_player_oof_v5/attempt_001/`.

This is **not a bug** in the sense of a mistake in the code — `dispersion()` is documented as
returning one sd for the fold's residual pool, and the emitted quantiles are internally consistent
with it. It is a **capability gap presented as a capability**: the column is named `pred_sd` and
sits in a per-row prediction table, so every downstream consumer reads it as per-row uncertainty,
and it is not. D134 already recorded the consequence (a negative out-of-fold R² for the incumbent
variance model); this screen records the mechanism at file and line, and confirms it on the bytes
of all three targets and all three seasons rather than on the decision stratum alone.

**Not reported as a code change and not worked around.** No file outside this screen was modified.

### F-2. `E1_I0054`'s `VSIG` arm is selection-carrying, and the premium is small.

The seven `VSIG` columns were formed from the 16 surviving cells of `E0_I0014`, measured on this
same partition and this same stratum, so `VSIG`'s +0.042866 / 1.9089 carries the selection. The
unselected arms land at **+0.041048** (`NONLY`, 36 columns) and **+0.041046** (`C1`), so the
selection premium is about **+0.0018** — real but small. `E1_I0054` also reported an unselected
`VALL` arm at +0.041420, i.e. it supplied the material to see this. Recording it because D134's
ruling 4 quotes the selected number (1.91) and not the unselected one.

### F-3. `_common.py`'s season-median imputation reads the future — measured, and numerically nil here.

`_common._impute_by_season` fills missing candidate cells with the median over the **whole**
season, future rows included (T1). Exposure on the stratum: 385 of 3,549 rows (10.85 %) for every
`x53_*` column, 3 rows for `pl_dnp_frac5`. The primary arms of this screen use a strictly-prior
expanding median instead, and the maximum absolute difference between the two rules over every
candidate cell is **0.000000** — because the 385 unjoined rows are exactly the **postseason**
(2023-09-13 to 2023-10-18 and 2024-09-22 to 2024-10-20) and fall strictly after every joined row,
so the expanding prior median has already converged to the season median. **Verified on dates, not
assumed.** The leak is real in construction and empty in effect on this stratum; on any stratum
where the missing rows are not terminal it would not be.

Two facts fall out of that check and are worth carrying forward: **10.85 % of the decision stratum
is postseason**, and `E1_I0053`'s frame is regular-season only.
