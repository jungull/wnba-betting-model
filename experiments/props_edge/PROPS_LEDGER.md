# PROPS_LEDGER — props_edge_v1 surviving pockets

*2026-07-31T16:10:35+00:00. Ranking of every pocket that survived the registered honesty machinery (200 within-season permutations of the projection column, BH at 0.1 within scope family, 100-bet minimum, 90% date-clustered bootstrap CIs). MEASUREMENT STUDY: everything here is a CANDIDATE. The confirmation channel is the live prospective props log, not this file.*

## Context that governs every row below

Regular-season projection MAE **5.244** vs line MAE **4.932** (+0.312). The books' lines are the better point estimate. A profitable pocket therefore cannot be explained by 'our projection is more accurate'; it would have to be a pricing/threshold artefact, and that is a much weaker prior than accuracy.


## REGISTERED BATTERY (all rows)

- eligible cells tested: 298; cells beating the registered null after BH: 3; **of those, PROFITABLE (ROI > 0): 0**; expected false among the 3 at q=0.1: **0.3**
- under the phase-blocked companion null: 3 cells survive
- 3 cell(s) beat the null while still LOSING money (ROI -0.0499 to -0.0176). A permutation star says 'better than a shuffled projection', not 'profitable'. These are NOT bets and are excluded from the ranking below; they are in `all_cells.csv`.
- family-wise sanity: P(best permuted cell >= best observed cell) = 0.935 over 200 permutations — the best observed cell is INDISTINGUISHABLE from the best cell a shuffled projection produces.

**No surviving profitable pockets.** This is a legitimate result: under the registered rules, no conditioning slice of the projection-vs-line disagreement produced a profitable pocket that beat its own permutation null after multiplicity correction.

## COMPANION — regular only

- eligible cells tested: 298; cells beating the registered null after BH: 0; **of those, PROFITABLE (ROI > 0): 0**; expected false among the 0 at q=0.1: **0.0**
- under the phase-blocked companion null: 1 cells survive
- family-wise sanity: P(best permuted cell >= best observed cell) = 0.990 over 200 permutations — the best observed cell is INDISTINGUISHABLE from the best cell a shuffled projection produces.

**No surviving profitable pockets.** This is a legitimate result: under the registered rules, no conditioning slice of the projection-vs-line disagreement produced a profitable pocket that beat its own permutation null after multiplicity correction.

## COMPANION — playoff only

- eligible cells tested: 134; cells beating the registered null after BH: 89; **of those, PROFITABLE (ROI > 0): 68**; expected false among the 89 at q=0.1: **8.9**
- under the phase-blocked companion null: 54 cells survive
- 21 cell(s) beat the null while still LOSING money (ROI -0.0519 to -0.0001). A permutation star says 'better than a shuffled projection', not 'profitable'. These are NOT bets and are excluded from the ranking below; they are in `all_cells.csv`.
- family-wise sanity: P(best permuted cell >= best observed cell) = 0.005 over 200 permutations — the best observed cell is beyond what shuffling typically produces.
- **Playoff pockets are reported, never acted on: John has paused playoff betting pending model improvements.**
- **NULL WARNING: playoff stars under the registered within-season shuffle are mis-calibrated** (the shuffle hands playoff rows regular-season projections). The phase-blocked count above is the trustworthy one.

*Listing the 15 highest-ROI of 68; the rest are in `all_cells.csv`. Note these cells are NOT independent — they are overlapping views of the same underlying player-games.*

### 1. per_book / synthetic110 / thr 3.0 / min_terc=low
- **ROI +0.2638** (90% CI -0.0356 to +0.5306) on **142 bets** (94W-48L-0P, hit 0.662) over 14 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1562, null 95th pct -0.0592
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 30 overs and 112 unders at a mean edge of -2.68 points on a mean line of 12.5.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (142 bets, just over the 100 floor); only 14 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 2. per_book / synthetic110 / thr 3.0 / venue=away
- **ROI +0.2194** (90% CI +0.0231 to +0.3951) on **191 bets** (122W-69L-0P, hit 0.639) over 21 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.0462, null 95th pct +0.0454
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 98 overs and 93 unders at a mean edge of -0.08 points on a mean line of 15.7.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; thin (191 bets, just over the 100 floor); only 21 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 3. per_book / captured / thr 3.0 / min_terc=low
- **ROI +0.2009** (90% CI -0.0888 to +0.4575) on **142 bets** (94W-48L-0P, hit 0.662) over 14 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1655, null 95th pct -0.0695
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 30 overs and 112 unders at a mean edge of -2.68 points on a mean line of 12.5.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (142 bets, just over the 100 floor); only 14 distinct dates — clustered

### 4. per_book / synthetic110 / thr 2.0 / min_terc=low
- **ROI +0.1818** (90% CI -0.0325 to +0.3954) on **294 bets** (182W-112L-0P, hit 0.619) over 19 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1475, null 95th pct -0.0477
- mechanism note: bets fire when |projection - line| >= 2.0; this cell took 90 overs and 204 unders at a mean edge of -1.58 points on a mean line of 11.0.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); only 19 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 5. per_book / synthetic110 / thr 1.0 / book=betrivers
- **ROI +0.1757** (90% CI +0.0289 to +0.3056) on **164 bets** (101W-63L-0P, hit 0.616) over 13 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI +0.0358, null 95th pct +0.1209
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 74 overs and 90 unders at a mean edge of -0.69 points on a mean line of 16.0.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; thin (164 bets, just over the 100 floor); only 13 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin; single-book pocket — book-level slices are the most fragile (limits, availability, line drift)

### 6. per_book / synthetic110 / thr 2.0 / line_terc=high
- **ROI +0.1684** (90% CI -0.0734 to +0.3830) on **299 bets** (183W-116L-0P, hit 0.612) over 26 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.0080, null 95th pct +0.0890
- mechanism note: bets fire when |projection - line| >= 2.0; this cell took 162 overs and 137 unders at a mean edge of +0.15 points on a mean line of 19.1.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); only 26 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 7. per_book / captured / thr 3.0 / venue=away
- **ROI +0.1512** (90% CI -0.0375 to +0.3166) on **191 bets** (122W-69L-0P, hit 0.639) over 21 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.0669, null 95th pct +0.0280
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 98 overs and 93 unders at a mean edge of -0.08 points on a mean line of 15.7.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (191 bets, just over the 100 floor); only 21 distinct dates — clustered

### 8. per_book / synthetic110 / thr 3.0 / line_terc=high
- **ROI +0.1432** (90% CI -0.2322 to +0.4753) on **167 bets** (100W-67L-0P, hit 0.599) over 20 dates
- permutation p = 0.0050 (Phipson-Smyth 0.0100); BH q = 0.0149; null-mean ROI -0.0029, null 95th pct +0.0817
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 84 overs and 83 unders at a mean edge of -0.13 points on a mean line of 19.3.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (167 bets, just over the 100 floor); only 20 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 9. best_line / synthetic110 / thr 1.0 / season=2024
- **ROI +0.1395** (90% CI -0.0156 to +0.2576) on **129 bets** (77W-52L-0P, hit 0.597) over 13 dates
- permutation p = 0.0150 (Phipson-Smyth 0.0199); BH q = 0.0324; null-mean ROI +0.0402, null 95th pct +0.1212
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 61 overs and 68 unders at a mean edge of -0.08 points on a mean line of 14.5.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (129 bets, just over the 100 floor); only 13 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin; best-line execution assumes you get the best number across books on every bet

### 10. per_book / captured / thr 2.0 / min_terc=low
- **ROI +0.1307** (90% CI -0.0818 to +0.3390) on **294 bets** (182W-112L-0P, hit 0.619) over 19 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1574, null 95th pct -0.0583
- mechanism note: bets fire when |projection - line| >= 2.0; this cell took 90 overs and 204 unders at a mean edge of -1.58 points on a mean line of 11.0.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); only 19 distinct dates — clustered

### 11. per_book / synthetic110 / thr 3.0 / season=2025
- **ROI +0.1250** (90% CI -0.1905 to +0.3446) on **224 bets** (132W-92L-0P, hit 0.589) over 13 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1398, null 95th pct -0.0533
- mechanism note: bets fire when |projection - line| >= 3.0; this cell took 97 overs and 127 unders at a mean edge of -0.63 points on a mean line of 14.1.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); only 13 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 12. consensus / synthetic110 / thr 1.0 / season=2024
- **ROI +0.1247** (90% CI -0.0192 to +0.2397) on **129 bets** (76W-53L-0P, hit 0.589) over 13 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.0168, null 95th pct +0.0702
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 61 overs and 68 unders at a mean edge of -0.08 points on a mean line of 14.5.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (129 bets, just over the 100 floor); only 13 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 13. best_line / captured / thr 1.0 / season=2024
- **ROI +0.1243** (90% CI -0.0305 to +0.2435) on **129 bets** (77W-52L-0P, hit 0.597) over 13 dates
- permutation p = 0.0300 (Phipson-Smyth 0.0348); BH q = 0.0529; null-mean ROI +0.0302, null 95th pct +0.1071
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 61 overs and 68 unders at a mean edge of -0.08 points on a mean line of 14.5.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); thin (129 bets, just over the 100 floor); only 13 distinct dates — clustered; best-line execution assumes you get the best number across books on every bet

### 14. per_book / synthetic110 / thr 1.0 / season=2024
- **ROI +0.1208** (90% CI -0.0097 to +0.2263) on **804 bets** (472W-332L-0P, hit 0.587) over 13 dates
- permutation p = 0.0050 (Phipson-Smyth 0.0100); BH q = 0.0149; null-mean ROI +0.0061, null 95th pct +0.0919
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 379 overs and 425 unders at a mean edge of -0.21 points on a mean line of 15.2.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; CI SPANS ZERO (bootstrap disagrees with the permutation p-value); only 13 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin

### 15. consensus / synthetic110 / thr 1.0 / min_terc=low
- **ROI +0.1198** (90% CI +0.0118 to +0.2202) on **104 bets** (61W-43L-0P, hit 0.587) over 24 dates
- permutation p = 0.0000 (Phipson-Smyth 0.0050); BH q = 0.0000; null-mean ROI -0.1658, null 95th pct -0.0697
- mechanism note: bets fire when |projection - line| >= 1.0; this cell took 38 overs and 66 unders at a mean edge of -0.89 points on a mean line of 10.2.
- anomaly flags: drawn from a 464-player-game postseason sample across 27 dates; every playoff cell re-uses these same rows, so the survivors are one finding, not many; thin (104 bets, just over the 100 floor); only 24 distinct dates — clustered; SYNTHETIC -110 price: real prop prices are worse than -110 on at least one side far more often than not; check the captured-basis twin


## What would confirm any of this

Nothing in this file is evidence a pocket is real — a retrospective battery can only nominate. Confirmation = preregistering the surviving cell as a live paper-trade cell and grading it on games played AFTER registration, using the 4x-daily props capture.
