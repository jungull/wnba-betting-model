# DEFECTS — E1_I0054

Two lists. **D-** are defects in *this* screen's own work. **F-** are defects this screen found
in other work and did not create.

---

## D — MY OWN

### D-1. My first calibration run crashed, and the crash was the most important finding in the screen.

`s03_calibration.py` run 1 (PID 4512) died with `numpy.linalg.LinAlgError: Singular matrix`
inside `ridge_fit`. The cause: the `VSD` variance model uses `<target>__pred_sd` as its only
feature, and that column is **constant on every early expanding-window training set** — in fact
it takes exactly one value per season on the whole decision stratum.

I fixed the solver (zero-variance columns are now zeroed and a least-norm fallback is used, so a
constant column correctly gets a zero coefficient) and re-ran. **The stderr from run 1 was
overwritten by run 2 and is not preserved** — that is a real record-keeping failure and I am not
going to pretend otherwise. The finding it produced is reproduced independently and on purpose in
`s02b_mechanism.py` / `_PRED_COLUMN_DEGENERACY.csv`, so nothing rests on the lost log.

### D-2. Two of my twelve preregistered predictions failed, and one of them failed in my favour.

**P-C3** predicted the signal-based variance model would not beat the incumbent `pred_sd` model
by more than 0.02 out-of-fold R² on points. Measured gap **0.032**. It failed because the
incumbent is degenerate, not because my model is strong — a fact that makes my own PART C look
*better* than predicted, which is the direction I should be most suspicious of. It is reported at
full size in `SKILL_OR_VARIANCE.md` §3 with the reason attached.

**P-S3** predicted abstention would cut MSE by more than 15% at q = 30%. Measured **13.2%**
(`ABSTENTION.csv`, per-fold training threshold) and **12.5%** (`_ABSTENTION_DECOMPOSED.csv`,
fixed global threshold). Both are below the threshold I set. I did not move it.

No threshold, seed, draw count, sample size or tolerance was revised after seeing a result.

### D-3. Two of my own PART S channels have an uncentred null and I found it only because T2 required it.

`_T2_PLACEBO.csv`: `S3_ADD_VHAT` has mean signed ΔR² **−2.91e-4** under H0 (required |mean| <
2e-4) and its cluster sign-flip test rejects at **0.160** against nominal 0.05.
`S3_ADD_VHAT_X_LEVEL` is worse: mean **−2.18e-3**, rate 0.117. Adding a regressor built from
noise costs out-of-fold R², so the statistic is not centred, and the sign-flip test on a paired
loss difference over-rejects when the difference has a systematic sign.

**Consequence: the largest ΔR² in the entire screen (+0.00047) belongs to `S3_ADD_VHAT`, and its
nominal p of 0.408 is not usable.** Read against its own placebo it is +1.5 sd. The conclusion
does not change — it moves further towards null — but a reader must not quote that +0.00047 with
its nominal p.

`S2_SHRINK`'s placebo rate is **0.087**, above the 0.075 tolerance the programme inherited from
`E1_I0050` §4. S2's observed result is negative so it costs nothing here. Recorded anyway.

### D-4. The T2 placebo ran on the GKF scheme, not the WF scheme the primary uses.

PREREG §7 says "the identical PART C pipeline". I ran 300 placebo replicates on the 5-fold GKF
scheme rather than the 138-fold WF scheme, for tractability (WF is ~28× the fits per replicate).
**This is a deviation from the PREREG and it is not a small one**: the WF channels' Type-I is
therefore *not* directly measured. The GKF and WF observed results agree in sign and magnitude
for every channel, and the placebo's verdict (S1/S2/S4 centred, S3 not) is a property of the
statistic rather than of the fold scheme, but I did not demonstrate that. A reader who wants the
WF Type-I must run it.

### D-5. My WF arm scores 2,945 of 3,549 rows and my GKF arm leaks time.

The expanding window needs a 600-row warm-up, so the earliest 604 rows of 2023 are never scored;
`SST` and every ΔR² in the WF arm are on the remaining 2,945. The GKF arm scores all 3,549 but
its folds contain future games. **Neither arm is clean on both axes and both are reported.** No
quantity is differenced across them.

### D-6. Retained share is not a variance decomposition and one cell exceeds 1.

`pl_dnp_frac5|minutes_sqres` retains **1.001** of its B0 ΔR² under B3 — conditioning on level
makes it slightly stronger (a suppression effect). "Retained share" is a ratio of two
increments measured against two different bases with two different SSTs and two different
family-wise bars. It is a readable summary, not a partition, and I use it only to sort cells
into "collapses" and "does not".

### D-7. I inherited `E1_I0050`'s per-cell Type-I verdicts for 38 of the 54 cells.

I re-measured Type-I with a centred generator only for the 16 reproduced cells and the 4 that
survive base B3 (`TYPEI_CENTRED.csv`). For the other 38, the `null_validity` field that gates my
`FAMILYWISE_SIGNIFICANT` verdict comes from `E1_I0050/TYPEI_PER_CELL.csv`. The two cells it marks
`INVALID_ANTICONSERVATIVE` are excluded on its authority, not mine, and its own `D-5` notes that
a reader who set the tolerance at 0.10 instead of 0.075 would keep all of them.

### D-8. Processes I launched, and what happened to them.

**No blanket kill of any kind was issued at any point in this screen.** No
`Get-Process python | Stop-Process`, no `taskkill`, no wildcard, no `Stop-Process` at all.
Sibling agents were running throughout and none of their processes was touched. The full table
of PIDs and fates is in `NOTES.md`; PIDs are recorded in `scripts/_pid_s0*.txt`. One process
(4512) exited on its own with the error in D-1; it was not killed.

---

## F — FOUND IN OTHER WORK

### F-1. `<target>__pred_sd` is a per-season CONSTANT on the decision stratum, and `pred_cv` is therefore `1/pred_point`.

`E0_I0014/analysis_frame.parquet`, columns `pts__pred_sd`, `minutes__pred_sd`, `fga__pred_sd`.
On `A4_CLEAN_DEC` (n = 3,549) each takes **exactly one distinct value per season**; on the full
13,879 rows each takes exactly three, one per season. `<target>__pred_cv` is defined in
`E0_I0014/s04_screen.py:26` as `pred_sd / pred_point`, so on this frame it is
**`k(season) / pred_point`** — within-season correlation with `1/pred_point` is
**1.000000** and the identity residual is exactly **0.0** (`_PRED_CV_MECHANISM.csv`).

**Consequence.** Five of `E1_I0050`'s sixteen surviving cells, including the largest
(`pts__pred_cv|pts_absres`, ΔR² 0.0274), are the statement *"the reciprocal of the forecast's
own point prediction predicts the size of the forecast's own error"*. Substituting
`1/pts__pred_point` for the candidate reproduces `t` and ΔR² **to every printed digit**
(`_PRED_CV_SUBSTITUTION.csv`). All five collapse to a retained ΔR² share of 0.001–0.013 once
level is in the base.

This is **not** an error in `E1_I0050`, whose arithmetic I reproduced exactly and which stated in
its own §5.5 that these numbers make no betting edge. It is a property of the frame that
`E0_I0014` built and that nothing downstream has checked. **Whether the producing pipeline is
supposed to emit a constant `pred_sd` is outside my write scope and I have not traced it.**
Someone who owns that pipeline should.

### F-2. The repaired family-wise bar for this 348-cell family is set by 17 team-level candidates against 24 blocks.

`_BAR_ANATOMY.csv`. Under composed-2 on `A4_CLEAN_DEC` the most frequent supplier of the
family-wise `max|t|` is `tm_poss_mean_prior|minutes_absres` (249 of 2,000 draws, 284 distinct
suppliers). The arm has **174 player-season blocks but only 24 team-season blocks**, so
TEAM-scheme candidates get much wider nulls and dominate the upper tail of a family in which
41 of 58 candidates are player-level.

This is the opposite of `E0_I0014`'s defect — the bar is a genuine bar, not one cell — but it
means every player-level cell in the family is judged against a threshold set by a different
permutation scheme with 7× fewer clusters. The direction is **conservative** (the bar is too
high for player cells), which is the direction that loses findings. It is the fourth separately
suspected anticonservative issue in this programme to turn out conservative on measurement.
Nobody has reported it; `E1_I0050` reported dominance but not scheme.

### F-3. `E1_I0050`'s A1_FULL headline count of 24 needs its qualifier carried with it.

`E1_I0050/WHY_1.000.md` §4 reports **24** family-wise-significant cells on A1_FULL. My
independent rebuild gets **36** with symmetric difference 0 against
`24 FAMILYWISE_SIGNIFICANT + 12 FAMILYWISE_SIGNIFICANT_BUT_CONFOUNDED_WITH_BLOCK_POSITION`.
Both numbers are correct; they differ only in whether the block-position-confounded cells are
counted. **This is a naming hazard, not an arithmetic error** — but "24" and "36" both describe
"family-wise significant on A1" depending on one unstated filter, and the A4 headline "16"
happens to have no confounded cells so the qualifier is invisible there. A brief that carries
"16 of 17" and "24" together should say which filter each uses.
