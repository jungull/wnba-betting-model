# RAPM v1 — multi-season priors + extended lambda sweep — 2026-07-30 17:21

*Model-infrastructure measurement only. No promotion claim; no registry entry;*
*adoption of any candidate is the orchestrator's decision under a separate*
*registered experiment. Candidate CSVs live in experiments/rapm_multiseason/,*
*NOT data/rapm/.*

## 0. Data
- possessions: 237,567 rows; usable (v0 filter: non-technical, full 5v5): 236,478 (99.54%)
  - 2021: 33,161 possessions, 209 games, ppp 1.0132
  - 2022: 38,103 possessions, 239 games, ppp 1.0259
  - 2023: 41,344 possessions, 260 games, ppp 1.0303
  - 2024: 41,657 possessions, 262 games, ppp 1.0248
  - 2025: 48,666 possessions, 310 games, ppp 1.0387
  - 2026: 33,547 possessions, 209 games, ppp 1.0824
- players across 2021-2026: 384
- gram identity check: gram_w(w=1) == v0.gram on season 2021: PASS

## 1. Protocol identity — reproduce v0's selection fold
v0 protocol: train 2021-24 pooled ridge, predict 2025+2026 stint margins,
unseen players -> league average (0).
- lam=500: sel-fold MAE 2.1044 (v0 build log 2.1044) PASS
- lam=1000: sel-fold MAE 2.0999 (v0 build log 2.0999) PASS
- lam=2000: sel-fold MAE 2.0963 (v0 build log 2.0963) PASS
- lam=5000: sel-fold MAE 2.0934 (v0 build log 2.0934) PASS
- lam=5000 intercept 0.9962 home +0.0147 (v0: 0.9962 / +0.0147)

## 2. Extended lambda sweep — was 5000 censored by the boundary?
Selection-fold curve (v0's exact protocol, train 21-24 -> 25+26 stints):
      500  2.1044  |################################################
     1000  2.0999  |################################
     2000  2.0963  |###################
     3500  2.0943  |###########
     5000  2.0934  |########
     7500  2.0926  |#####
    11000  2.0922  |####
    16000  2.0918  |##
    23000  2.0916  |##
    33000  2.0914  |#
    47000  2.0912  |
    68000  2.0912  | <-- min
   100000  2.0912  |
- winner on v0's protocol (ties to larger): lambda = 68,000
- winner on the ->2025 fold only (used for the walk-forward table): lambda = 68,000
- VERDICT: yes — the v0 sweep boundary censored the optimum. lam=68,000 beats lam=5000 by 0.0022 stint-MAE points on the identical protocol.

## 3. Replacement-level prior (for new players in the anchored model)
Entrant = player first appearing in season u (absent from every earlier
season's design). Their single-season lam=2000 coefficients are
possession-weight averaged over entrant seasons STRICTLY BEFORE t to give
the season-t anchor for new players (walk-forward safe; already shrunk
toward 0 by the single-season ridge, so conservative). 2021/2022 have no
entrant history -> anchor 0 (documented fallback, not a rookie model).
- rep_at[2021]: off +0.000/100, def(allowed) +0.000/100 -> net +0.000/100  (from 0 prior entrants)
- rep_at[2022]: off +0.000/100, def(allowed) +0.000/100 -> net +0.000/100  (from 0 prior entrants)
- rep_at[2023]: off -0.025/100, def(allowed) +0.166/100 -> net -0.191/100  (from 51 prior entrants)
- rep_at[2024]: off -0.065/100, def(allowed) +0.308/100 -> net -0.373/100  (from 82 prior entrants)
- rep_at[2025]: off +0.019/100, def(allowed) +0.294/100 -> net -0.275/100  (from 110 prior entrants)
- rep_at[2026]: off -0.042/100, def(allowed) +0.206/100 -> net -0.248/100  (from 159 prior entrants)

## 4. Prior-anchored two-level sweep (lambda_within x lambda_prior)
Fit chain 2021->2024 per config; deployed rating = post-2024 snapshot;
selected on the ->2025 fold (train<=2024 -> 2025 stints, unseen->0).
- grid: lw in [0, 500, 1000, 2000, 5000, 10000, 20000, 50000], lp in [0, 500, 1000, 2000, 5000, 10000, 20000, 50000] (63 configs)
- chosen on ->2025 fold: lambda_within=10,000, lambda_prior=5,000 (MAE 2.1582)
- ->2025 MAE grid (rows lw, cols lp):
```
lambda_prior    0       500     1000    2000    5000    10000   20000   50000
lambda_within                                                                
0                 NaN  2.1805  2.1705  2.1639  2.1608  2.1604  2.1603  2.1596
500            2.1764  2.1682  2.1646  2.1616  2.1600  2.1601  2.1602  2.1595
1000           2.1686  2.1644  2.1623  2.1605  2.1595  2.1598  2.1600  2.1595
2000           2.1632  2.1615  2.1605  2.1595  2.1590  2.1594  2.1597  2.1594
5000           2.1597  2.1593  2.1590  2.1587  2.1585  2.1588  2.1592  2.1592
10000          2.1586  2.1585  2.1584  2.1583  2.1582  2.1584  2.1587  2.1590
20000          2.1583  2.1583  2.1583  2.1583  2.1583  2.1583  2.1585  2.1589
50000          2.1588  2.1588  2.1588  2.1588  2.1588  2.1588  2.1589  2.1591
```

## 5. Decay-pooled sweep (half_life x lambda)
One weighted ridge on 2021-2024, weight 0.5^((2024-season)/half_life);
half_life=inf == v0's equal pooling. Selected on the ->2025 fold.
- grid: half_life in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, inf], lambda = extended grid (91 configs)
- chosen on ->2025 fold: half_life=0.5, lambda=11,000 (MAE 2.1583)
- ->2025 MAE grid (rows half_life, cols lambda):
```
lambda     500     1000    2000    3500    5000    7500    11000   16000   23000   33000   47000   68000   100000
half_life                                                                                                        
0.5        2.1684  2.1634  2.1602  2.1589  2.1585  2.1583  2.1583  2.1583  2.1584  2.1587  2.1590  2.1594  2.1598
1.0        2.1673  2.1629  2.1603  2.1592  2.1588  2.1587  2.1588  2.1587  2.1588  2.1589  2.1591  2.1595  2.1598
1.5        2.1673  2.1632  2.1607  2.1596  2.1592  2.1591  2.1591  2.1590  2.1590  2.1591  2.1592  2.1595  2.1598
2.0        2.1675  2.1634  2.1609  2.1599  2.1594  2.1593  2.1593  2.1593  2.1592  2.1592  2.1593  2.1595  2.1597
3.0        2.1679  2.1638  2.1613  2.1602  2.1597  2.1595  2.1595  2.1595  2.1594  2.1594  2.1594  2.1595  2.1597
5.0        2.1685  2.1643  2.1616  2.1605  2.1600  2.1598  2.1598  2.1597  2.1596  2.1595  2.1595  2.1595  2.1597
inf        2.1696  2.1653  2.1623  2.1610  2.1605  2.1602  2.1601  2.1601  2.1599  2.1598  2.1597  2.1596  2.1597
```

## 6. Walk-forward comparison — train <= s, predict s+1 stints
Hyperparameters frozen from the ->2025 selection above; the ->2026 fold is
therefore BLIND for all three v1 methods. ->2023/->2024 are supplementary
folds evaluated at those same (future-selected) settings — labeled as such.
v0-method rows are refit per window at their fixed lambdas. Unseen players
predict at league average (0), v0 convention.

Folds: ->2023 (7,031 stints, 11.2% unseen slots); ->2024 (6,721 stints, 11.7% unseen slots); ->2025 (8,673 stints, 15.8% unseen slots); ->2026 (6,474 stints, 19.9% unseen slots)

| model | ->2023 | ->2024 | ->2025* | ->2026 (blind) | pooled | RMSE pooled |
|---|---|---|---|---|---|---|
| zero baseline | 2.2391 | 2.2599 | 2.2261 | 2.0553 | 2.1989 | 2.9731 |
| team baseline | 2.1967 | 2.2229 | 2.1807 | 2.0082 | 2.1558 | 2.8539 |
| v0 pooled lam=5000 | 2.1736 | 2.2096 | 2.1605 | 2.0023 | 2.1397 | 2.8326 |
| v0 pooled lam=5000 [unseen->repl] | 2.1734 | 2.2094 | 2.1606 | 2.0023 | 2.1396 | 2.8323 |
| single ext lam=68000 | 2.1781 | 2.2087 | 2.1596 | 1.9999 | 2.1398 | 2.8421 |
| single ext lam=68000 [unseen->repl] | 2.1779 | 2.2084 | 2.1595 | 1.9998 | 2.1396 | 2.8416 |
| prior-anchored (lw=10000, lp=5000) | 2.1762 | 2.2116 | 2.1582 | 2.0023 | 2.1401 | 2.8377 |
| prior-anchored (lw=10000, lp=5000) [unseen->repl] | 2.1760 | 2.2113 | 2.1582 | 2.0023 | 2.1399 | 2.8373 |
| decay-pooled (h=0.5, lam=11000) | 2.1756 | 2.2117 | 2.1583 | 2.0014 | 2.1398 | 2.8366 |
| decay-pooled (h=0.5, lam=11000) [unseen->repl] | 2.1754 | 2.2114 | 2.1582 | 2.0014 | 2.1396 | 2.8362 |

*->2025 is the selection fold for the three v1 methods (their hyperparameters
minimize this column — read it as in-selection, not held out). v0 lam=5000 was
itself chosen on 2025-26 data in the v0 build, so its ->2025/->2026 cells carry
the same caveat. ->2023/->2024 use hyperparameters selected on later seasons
(reverse-time selection): fair for method comparison, not a prospective sim.
[unseen->repl] rows: identical fit, but players unseen in training predict at
the walk-forward replacement prior instead of league average.

## 7. Stability of deployed ratings (as-of season s vs s+1)
Eligibility: >= 1000 on-court possessions in BOTH seasons of the pair
(v0 diagnostic-2 convention). Deployed rating after season s uses data <= s
only. NOTE: multi-season methods share training data across a pair, so their
r is partly mechanical persistence — that is the operationally relevant number
for a rating you re-ship each season, but it is NOT comparable to v0's
independent single-season 'signal' YoY, shown last.

| method | YoY r (22-23, 23-24, 24-25) | mean r | top-25 overlap | bottom-25 overlap | Spearman (mean) |
|---|---|---|---|---|---|
| v0 pooled lam=5000 | 0.905, 0.919, 0.945 | 0.923 | 20.3/25 | 19.0/25 | 0.893 |
| single ext lam=68000 | 0.915, 0.944, 0.945 | 0.934 | 20.3/25 | 18.3/25 | 0.866 |
| prior-anchored (lw=10000, lp=5000) | 0.722, 0.611, 0.671 | 0.668 | 16.0/25 | 12.3/25 | 0.567 |
| decay-pooled (h=0.5, lam=11000) | 0.715, 0.616, 0.662 | 0.664 | 15.7/25 | 12.0/25 | 0.567 |

Reference — v0 'signal' YoY (independent single-season fits, lam=5000):
- r(2022 vs 2023) = 0.515  (n=84)  (v0 build log: 0.515)
- r(2023 vs 2024) = 0.353  (n=90)  (v0 build log: 0.353)
- r(2024 vs 2025) = 0.397  (n=95)

## 8. Garbage-time sensitivity (train<=2024 window)
- garbage possessions (period>=4, |margin|>= 15): 10,571 of 154,265 (6.85%)
- v0 pooled lam=5000: r(full vs garbage-excluded) = 0.9770 (n=216, >=500 poss)  (v0 build log: 0.9770)
- single ext lam=68000: r(full vs garbage-excluded) = 0.9925 (n=216, >=500 poss)
- prior-anchored (lw=10000, lp=5000): r(full vs garbage-excluded) = 0.9840 (n=216, >=500 poss)
- decay-pooled (h=0.5, lam=11000): r(full vs garbage-excluded) = 0.9878 (n=216, >=500 poss)

## 9. Candidate CSVs (exact rapm_v0.csv schema, written to experiments/rapm_multiseason/)
- rapm_v1_singleseason_extlambda_train2021_24.csv: 265 players. v0 method, lambda=68,000 (extended-sweep winner on v0's own selection protocol). Drop-in replacement shape for rapm_v0.csv.
- cross-check vs data/rapm/rapm_v0.csv on net_100_lam{500..5000}: max |diff| = 0.0000 over 265 joined players (PASS)
- rapm_v1_prior_anchored_train2021_24.csv: 265 players. anchored chain 2021->2024, lw=10,000, lp=5,000 (lp fixed in the lamX columns). lambda_chosen = lambda_within.
- rapm_v1_prior_anchored_train2021_26.csv: 384 players. anchored chain 2021->2026 (deployment-shaped), lw=10,000, lp=5,000. minutes_2021_24 column holds 2021-26 minutes (schema-name kept for joins).
- rapm_v1_decay_pooled_train2021_24.csv: 265 players. decay-pooled 2021-2024, half_life=0.5, lam=11,000.
- rapm_v1_decay_pooled_train2021_26.csv: 384 players. decay-pooled 2021-2026 (deployment-shaped), half_life=0.5, lam=11,000. minutes_2021_24 column holds 2021-26 minutes.

## 10. Replacement-level behavior (train<=2024 candidates)
- v0 pooled lam=5000: net mean <300 poss -0.058 (n=35, min -0.543, max +0.378); >=1000 poss +0.121 (n=198); 2024 entrants -0.212 (n=28)
- single ext lam=68000: net mean <300 poss -0.005 (n=35, min -0.043, max +0.027); >=1000 poss +0.010 (n=198); 2024 entrants -0.040 (n=28)
- prior-anchored (lw=10000, lp=5000): net mean <300 poss -0.063 (n=35, min -0.273, max +0.125); >=1000 poss -0.024 (n=198); 2024 entrants -0.258 (n=28)
- decay-pooled (h=0.5, lam=11000): net mean <300 poss -0.014 (n=35, min -0.203, max +0.114); >=1000 poss +0.021 (n=198); 2024 entrants -0.172 (n=28)
  (want: low-poss and entrant means below the established-player mean,
   and shrunk toward the prior rather than at noisy extremes)

## 11. Smoke test ONLY (broken-data check, never a promotion criterion)
top-12 net, prior-anchored thru-2026 candidate (>=1500 poss 2021-26):
  A'ja Wilson                  net  +1.56  (o +1.26 / d +0.30, poss 32,677)
  Candace Parker               net  +1.35  (o +0.61 / d +0.75, poss  9,984)
  Kayla McBride                net  +1.30  (o +0.83 / d +0.47, poss 28,968)
  Jackie Young                 net  +1.29  (o +0.98 / d +0.31, poss 32,828)
  Natasha Howard               net  +1.27  (o +0.89 / d +0.38, poss 23,517)
  Jordin Canada                net  +1.11  (o +0.53 / d +0.57, poss 19,948)
  Veronica Burton              net  +1.08  (o +0.27 / d +0.81, poss 14,991)
  Kelsey Mitchell              net  +1.07  (o +1.13 / d -0.06, poss 29,239)
  Courtney Williams            net  +1.01  (o +0.54 / d +0.48, poss 29,192)
  Chelsea Gray                 net  +0.98  (o +0.97 / d +0.01, poss 30,311)
  Elena Delle Donne            net  +0.97  (o +0.37 / d +0.60, poss  5,898)
  Allie Quigley                net  +0.92  (o +0.71 / d +0.21, poss  8,276)

## 12. Honest recommendation (measurement, not promotion)
- Boundary flag: RESOLVED — censored. On v0's exact protocol the extended sweep prefers lambda=68,000 (sel-fold MAE 2.0912 vs 2.0934 at 5000).
- Best pooled walk-forward MAE: v0 pooled lam=5000 (2.1397 vs v0-method 2.1397, team baseline 2.1558).
- Margins between RAPM variants are small on stint MAE (stints are ~5
  possessions of near-coin-flip noise); the stability table is where the
  multi-season structure shows its value for a rating re-shipped seasonally.
- No promotion claim is made here. The promotion question (does any of this
  move the GAME model?) belongs to the orchestrator's registered experiment
  (minute-weighted aggregation vs team chains), per ROADMAP 2b.

## Files
- experiments/rapm_multiseason/fold_results.csv
- experiments/rapm_multiseason/rapm_v1_decay_pooled_train2021_24.csv
- experiments/rapm_multiseason/rapm_v1_decay_pooled_train2021_26.csv
- experiments/rapm_multiseason/rapm_v1_prior_anchored_train2021_24.csv
- experiments/rapm_multiseason/rapm_v1_prior_anchored_train2021_26.csv
- experiments/rapm_multiseason/rapm_v1_singleseason_extlambda_train2021_24.csv
- experiments/rapm_multiseason/sweep_decay_pooled.csv
- experiments/rapm_multiseason/sweep_lambda_extended.csv
- experiments/rapm_multiseason/sweep_prior_anchored.csv

runtime 126s
