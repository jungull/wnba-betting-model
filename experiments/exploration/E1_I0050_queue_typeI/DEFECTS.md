# DEFECTS — E1_I0050

Two lists. **D-** are defects in *this* screen's own work. **F-** are defects this screen found
in other screens' work and did not create.

---

## D — MY OWN

### D-1. My Clopper–Pearson helper was wrong on its first run and I kept the output.

`s02_typeI.py` as first written omitted the symmetry swap
`if x > (a+1)/(a+b+2): return 1 - betainc(b, a, 1-x)`, without which the continued fraction does
not converge on the right branch. Every interval it produced came out `[1.0000, 1.0000]`. The
**rejection rates themselves were unaffected** — they are `k/B` and touch none of that code —
but every interval in the first A4 run's log is garbage.

The crashed first A4 run's log is preserved as `scripts/run_log_s02_A4_run1_CRASHED.txt` and its
stderr alongside it; nothing was overwritten. The fixed function is used in `s02` and again,
independently, in `s04_verdicts.py`, and the intervals in `TYPEI_PER_CELL.csv` come from the
fixed one. Sanity check available to a reader: at k = 50, B = 1,000 the interval is
[0.0374, 0.0654], which brackets 0.05 as it must.

### D-2. My PREREG self-test T2 FAILED, and it took a second script to find out whose fault it was.

T2 put an iid-noise candidate through the pipeline and required composed-2 Type-I of
0.05 ± 3 MC se. It returned **0.0230 and 0.0060**. Two readings with opposite consequences: my
harness under-rejects (every number in this screen is wrong), or the composed-2 null is
conservative (every p it produces is valid but under-powered).

`s05b_harness_exactness.py` discriminates. On an iid candidate with an **iid** response — no
clustering anywhere, so all three schemes are exact — the harness returns **0.0490 / 0.0470 /
0.0510**. On the same clustered synthetic responses that made composed-2 return 0.016, a
row-naive permutation, which is exact when the candidate is iid and independent of the response,
returns **0.0400 and 0.0510**. **The harness is exact; the composed-2 null is conservative.**

The mechanism is measured rather than argued: composed-2 fills a receiving block from one donor
block, so an iid carrier acquires a between-block variance share of **0.1142** against its real
**0.0344**. Removing the with-replacement resampling changes that to 0.1058, so the resampling is
not the cause — the whole-block donor assignment is.

**Consequence, stated plainly: every floor and every `BLIND` classification `E1_I0044` published
for these 54 cells is pessimistic**, because a conservative null gives a larger 97.5th percentile
and therefore a larger `MDE80`. This is the direction that loses findings, not the direction that
invents them, and it is the third such case in this programme.

### D-3. Two of my five preregistered predictions failed and one failed as stated.

`P4` predicted Spearman(within-block excess kurtosis, Type-I) > +0.5. Measured **+0.205 on A4 and
−0.283 on A1** — below threshold and sign-unstable. `P5` predicted at most 12 of the 17 A4
family-wise cells would survive; **16 do**. `P3` predicted all three position-monotone counters
would be condemned by the BLOCKBOOT generator and cleared by EXCH; the EXCH half held for all
three, the BLOCKBOOT half held for **one of three**. All three are reported in `FINDINGS.json`
and in the body of `SHAPE_RULE.md` in the direction the data gave, not the direction predicted.

I did not adjust any threshold, sample size or generator after seeing a result. `B = 1000`,
`POOL = 1000`, `R_NULL = 500` and the 0.075 tolerance are as preregistered.

### D-4. Replicates share a permutation pool, and I did not quantify the extra variance.

Each cell's `POOL = 1000` permuted carriers are built once and every replicate draws
`R_NULL = 500` of them without replacement. This is `E1_I0044`'s D-4 approximation, inherited
deliberately for comparability. It does not bias the rate but it correlates the rejection
indicators across replicates, so the true standard error of each Type-I estimate exceeds the
binomial `0.00689` I report. A back-of-envelope on the quantile uncertainty puts the extra
component at roughly the same magnitude again, i.e. a combined se near 0.010 rather than 0.007.
**I did not measure it**, so every Clopper–Pearson interval in `TYPEI_PER_CELL.csv` is narrower
than the truth. This does not move any verdict — the acceptance tolerance is 0.075 against a
median of 0.021–0.035 — but it would matter for the three cells near the boundary.

### D-5. Two cells sit just over the tolerance, and the tolerance is mine.

`pl_pts_sd5|pts_sqres` (A4 0.092, A1 0.086) and `pl_fga_sd5|fga_sqres` (A4 0.081) are marked
`INVALID_ANTICONSERVATIVE` and therefore `UNVERIFIABLE`. Their Clopper–Pearson upper bounds are
0.112, 0.105 and 0.100. **A reader who set the tolerance at 0.10 rather than 0.075 would keep all
three**, which would make the A4 survivor count 17 of 17 rather than 16 of 17. The threshold was
preregistered before measurement and is not revised, but it is a judgement and the numbers needed
to overturn it are in the file.

### D-6. I ran the position-adjusted robustness arm, which was not preregistered.

`s06_position_adjusted.py` was written after the Type-I results were in, to test whether the
surviving associations are a within-block time trend. It is a **new arm with its own base, its
own SST and its own bar**, declared as such, and no quantity in it is compared to or differenced
against the main arms. It is reported because it could have retracted the survivors and did not
(16 of 16 and 24 of 24 hold). Because it is post hoc it should be read as a check that failed to
find a problem, not as a preregistered confirmation.

### D-7. Fifteen candidates carry fifty-four cells.

Every shape correlation in `SHAPE_RULE.md` has at most 15 independent points. Cells sharing a
candidate share its column exactly, so the nominal `n = 50` and `n = 54` in `_SHAPE_SPEARMAN.csv`
overstate the information. I report the correlations as suggestive and decline to propose a
screening rule from them.

### D-8. Processes I launched, and what happened to them.

**No blanket kill of any kind was issued at any point in this screen.** No
`Get-Process python | Stop-Process`, no `taskkill`, no wildcard. Three sibling agents were
running throughout and none of their processes was touched.

| PID | script | fate |
|---|---|---|
| 7540 | `s02_typeI.py A4_CLEAN_DEC` (run 1) | **exited on its own** with `ZeroDivisionError` — `pts__fallback_level` and `pts__is_fallback` are constant inside the decision stratum. Not killed. Log preserved. |
| 31028 | `s02_typeI.py A4_CLEAN_DEC` (run 2) | ran to completion |
| 11504 | `s02_typeI.py A1_FULL` | ran to completion |
| 29792 | `s05_selftests.py` | ran to completion |
| 28156 | `s05b_harness_exactness.py` | ran to completion |
| 33200 | `s06_position_adjusted.py` | ran to completion |

PIDs are recorded in `scripts/_s0*_pid.txt`.

---

## F — FOUND IN OTHER SCREENS

### F-1. `E1_I0044`'s "41 of the 54" does not reproduce; the number is 49.

`E1_I0044/VERDICT.md` §2 point 2 and §5 state that `E0_I0014` published
`p_familywise_whole_screen = exactly 1.000` for **41 of the 54**. Recomputed from
`E0_I0014/screen_results.csv` the count is **49 of the 54**, and **301 of all 348**. No script in
`E1_I0044/scripts/` computes 41; `grep` over the whole directory finds it only in the prose.
Nearby counts that a reader might mistake for it: 45 (`==1.000` **and** composed-2 A1 `p<0.05`),
36 (`==1.000` **and** composed-2 A4 `p<0.05`), 35 (`p_familywise_within_dependent == 1.000`).
This screen uses 49. The direction of the finding is unaffected — it is larger, not smaller.

### F-2. `E1_I0044`'s Type-I generator is not effect-free, and it condemned its own instrument on that basis.

`E1_I0044/scripts/s13_typeI_injection_fast.py:95-103`, `block_resample_matrix`, builds the
"effect-free" response by copying whole donor blocks with
`out[b, bi] = vec[don[np.arange(len(b)) % len(don)]]`, which preserves **absolute within-block
position**. These responses have a within-block positional profile shared across blocks
(measured here: `resp_shared_position_profile_sd` 0.167–0.264 on the full frame), so the profile
is transplanted intact into every synthetic dataset and a candidate that is a function of
position is genuinely associated with it.

Measured directly on `E1_I0044`'s own arm: over 1,000 of its synthetic "effect-free" datasets,
the mean **signed** observed `t` exceeds 0.5 in magnitude on **41 of the 54** cells and reaches
**7.31**. Under two generators for which H0 does hold it exceeds 0.5 on **0 of 54**.

**Consequence.** `E1_I0044`'s five Type-I numbers reproduce (I get 0.0240, 0.0280, 0.0580,
0.1390, 0.5810 against its 0.0225, 0.0250, 0.0525, 0.1475, 0.5950, ordering preserved) but they
measure the generator, not the null. Its `D-2` — "no null tested here, including mine, is valid
for a counter candidate" — is **not supported**: under EXCH and CIRCSHIFT the composed-2 null's
Type-I on the counter cells is 0.001–0.045. Its refusal to claim the queue was the right
instinct on the evidence it had; the evidence was wrong in the conservative direction.

### F-3. `E1_I0044` measured its most alarming Type-I on a cell outside its own queue.

`s13`'s allowlist contains `pl_games_prior|pts_absres`, the cell that produced the 0.5950 quoted
in its VERDICT headline, its `DEFECTS.md` D-2, and its §6.1 "single largest threat". That cell is
**not one of the 54** — the queue contains `pl_games_prior|minutes_absres` and
`|minutes_sqres` only. On the two `pl_games_prior` cells that *are* in the queue, the same
generator gives 0.0040–0.0080. Four of its five Type-I cells are in the queue; the fifth, and the
worst, is not.

### F-4. `E0_I0014`'s family-wise bar is one cell, and its `p_familywise_whole_screen` column is unusable as published.

`s04_screen.py:237-249, 297`. `maxt_cor` is an unstandardised `max|t|` over 348 cells whose nulls
include 54 with mean `|t|` between 6 and 27.6. **In 1,000 of 1,000 draws the max is supplied by
the single cell `pl_pts_sd5|pts_absres`**, whose within-block null sits at mean `|t|` = 27.578
with sd 0.917. The published bar's p95 is **29.127**; the same 348-cell bar under the screen's own
row-naive null is **3.730**. Consequently 301 of 348 cells carry `p_familywise_whole_screen` of
exactly 1.000 and the column cannot be used for any purpose as published. `E1_I0041` and
`E1_I0044` both identified this class of problem; this is the measurement that reduces it to one
cell.

### F-5. `E0_I0014`'s own null is blind, not anticonservative, and a Type-I audit alone would clear it.

Same cell, same null, measured Type-I at δ = 0 under a generator for which H0 holds: **0.057**
against nominal 0.05. Its null on the *real* response is centred at **+27.616** with sd 0.872.
Recorded because it is a trap for future audits: **level and blindness are different failures**.
An audit that measures only Type-I will pass a null that contains the alternative, and an audit
that measures only blindness will pass a null that over-rejects. `E1_I0044` measured blindness
(its `_STATISTIC_BLINDNESS.csv`); this screen measures level; neither alone was sufficient.

### F-6. D103's floors for these cells inherit both errors and are wrong in both directions.

Not new — `E1_I0044` established it — but re-measured here and worth restating with the sign
attached. For the 54, D103's `mde80` is built from `(t_crit + z80)·sd` where `t_crit` comes from
the degenerate null's 97.5th percentile of `|t|`, which runs to 8–20 instead of ≈2. Those floors
are **too large**. For the six cells whose `sd` is exactly 0 the floor is exactly 0.0, which is
too small by an infinite factor — and those six turn out to have no statistic at all. Both errors
are in `E1_I0026/out/retrospective_power.csv` as shipped.
