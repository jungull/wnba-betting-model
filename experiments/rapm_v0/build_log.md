# RAPM v0 — build log 2026-07-30 14:15

possessions loaded: 227,385 rows, 1,424 games
usable (non-technical, full 5v5 lineups): 226,750 (99.72%)
train 2021-2024: 144,537 possessions / 905 games; held-out 2025-2026: 82,213 / 519 games
train points-per-possession: 1.0230
players in training design: 265
  lam=500: intercept 0.9720  home +0.0132
  lam=1000: intercept 0.9798  home +0.0131
  lam=2000: intercept 0.9880  home +0.0128
  lam=5000: intercept 0.9980  home +0.0125

## Diagnostic 1 — predictive stint error, 2025-2026 held out
stints: 15,147 (mean 5.4 possessions, mean |actual margin| 2.153)
  zero baseline (predict 0):        MAE 2.1531
  team-strength baseline (2021-24): MAE 2.1096
  RAPM lam=500                      MAE 2.1045
  RAPM lam=1000                     MAE 2.1001
  RAPM lam=2000                     MAE 2.0965
  RAPM lam=5000                     MAE 2.0934
  player-slots in 2025-26 filled by players unseen in 2021-24: 22.4% (they predict at league average in RAPM; expansion teams likewise in the team baseline)
  chosen lambda (min held-out stint MAE, ties to larger): 5000

## Diagnostic 2 — year-over-year stability (single-season fits, lam=5000, players >= 1000 possessions both years)
  net rating r(2022 vs 2023) = 0.456   (n = 82 players)
  net rating r(2023 vs 2024) = 0.366   (n = 90 players)

## Diagnostic 3 — lambda sensitivity (top-50 by net)
  lam  500 vs 1000: Spearman 0.969 on union of top-50s (n=53), top-50 overlap 47/50
  lam  500 vs 2000: Spearman 0.885 on union of top-50s (n=54), top-50 overlap 46/50
  lam  500 vs 5000: Spearman 0.753 on union of top-50s (n=57), top-50 overlap 43/50
  lam 1000 vs 2000: Spearman 0.952 on union of top-50s (n=51), top-50 overlap 49/50
  lam 1000 vs 5000: Spearman 0.844 on union of top-50s (n=55), top-50 overlap 45/50
  lam 2000 vs 5000: Spearman 0.936 on union of top-50s (n=54), top-50 overlap 46/50

## Diagnostic 4 — garbage-time sensitivity
garbage-time possessions (period >= 4, |margin before| >= 15): 9,854 of 144,537 (6.82%)
  net rating r(full vs garbage-excluded), players >= 500 poss: 0.9786  (n = 215)

## Diagnostic 5 — replacement-level behavior
  players < 300 possessions: n=35, mean net -0.069, min -0.542, max +0.383
  players >= 1000 possessions: n=198, mean net +0.121
  all players: mean net -0.000
  (want: low-poss group mean below average, and shrunk — not at extremes)

## Smoke test ONLY (never a promotion criterion) — lam=5000, players >= 1500 possessions 2021-24
  top-15 OFFENSE:
    Breanna Stewart               +4.13  (net  +5.88, poss 18,356, min   4,594)
    Kelsey Plum                   +4.06  (net  +4.25, poss 18,474, min   4,545)
    Jackie Young                  +3.27  (net  +3.72, poss 19,318, min   4,741)
    Jonquel Jones                 +3.20  (net  +5.90, poss 15,763, min   4,033)
    Skylar Diggins                +3.08  (net  +5.20, poss 14,618, min   3,705)
    Aliyah Boston                 +2.96  (net  +2.42, poss  9,825, min   2,485)
    Satou Sabally                 +2.96  (net  +3.30, poss  9,904, min   2,455)
    Sabrina Ionescu               +2.92  (net  +1.83, poss 17,699, min   4,452)
    Allie Quigley                 +2.88  (net  +3.35, poss  7,378, min   1,857)
    Chelsea Gray                  +2.75  (net  +4.24, poss 16,619, min   4,096)
    Teaira McCowan                +2.69  (net  +2.28, poss 12,741, min   3,236)
    A'ja Wilson                   +2.46  (net  +3.63, poss 19,526, min   4,797)
    Marina Mabrey                 +2.31  (net  +1.82, poss 16,384, min   4,146)
    Brionna Jones                 +2.20  (net  +4.86, poss 13,478, min   3,486)
    DeWanna Bonner                +2.12  (net  +4.05, poss 17,931, min   4,627)
  top-15 DEFENSE:
    Jonquel Jones                 +2.70  (net  +5.90, poss 15,763, min   4,033)
    Brionna Jones                 +2.65  (net  +4.86, poss 13,478, min   3,486)
    Courtney Vandersloot          +2.64  (net  +4.23, poss 16,192, min   4,049)
    Candace Parker                +2.46  (net  +4.28, poss  9,083, min   2,268)
    Skylar Diggins                +2.12  (net  +5.20, poss 14,618, min   3,705)
    DeWanna Bonner                +1.93  (net  +4.05, poss 17,931, min   4,627)
    Jewell Loyd                   +1.89  (net  +3.35, poss 18,797, min   4,677)
    Bridget Carleton              +1.87  (net  +1.96, poss 11,685, min   2,976)
    Alyssa Thomas                 +1.85  (net  +3.48, poss 15,753, min   4,024)
    Alanna Smith                  +1.81  (net  +2.28, poss  9,089, min   2,301)
    Elena Delle Donne             +1.79  (net  +3.70, poss  5,383, min   1,379)
    Alysha Clark                  +1.76  (net  +2.15, poss 10,416, min   2,614)
    Breanna Stewart               +1.75  (net  +5.88, poss 18,356, min   4,594)
    Shakira Austin                +1.73  (net  +2.16, poss  5,692, min   1,454)
    Leonie Fiebich                +1.67  (net  +2.48, poss  3,293, min     837)

wrote C:\Users\jgallagher\wnba-betting-model\data\rapm\rapm_v0.csv (265 players), rapm_by_season.csv, stint_eval.csv
runtime 12s
