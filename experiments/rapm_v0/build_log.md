# RAPM v0 — build log 2026-07-30 14:34

possessions loaded: 237,567 rows, 1,489 games
usable (non-technical, full 5v5 lineups): 236,478 (99.54%)
train 2021-2024: 154,265 possessions / 970 games; held-out 2025-2026: 82,213 / 519 games
train points-per-possession: 1.0240
players in training design: 265
  lam=500: intercept 0.9716  home +0.0151
  lam=1000: intercept 0.9788  home +0.0150
  lam=2000: intercept 0.9865  home +0.0148
  lam=5000: intercept 0.9962  home +0.0147

## Diagnostic 1 — predictive stint error, 2025-2026 held out
stints: 15,147 (mean 5.4 possessions, mean |actual margin| 2.153)
  zero baseline (predict 0):        MAE 2.1531
  team-strength baseline (2021-24): MAE 2.1097
  RAPM lam=500                      MAE 2.1044
  RAPM lam=1000                     MAE 2.0999
  RAPM lam=2000                     MAE 2.0963
  RAPM lam=5000                     MAE 2.0934
  player-slots in 2025-26 filled by players unseen in 2021-24: 22.4% (they predict at league average in RAPM; expansion teams likewise in the team baseline)
  chosen lambda (min held-out stint MAE, ties to larger): 5000

## Diagnostic 2 — year-over-year stability (single-season fits, lam=5000, players >= 1000 possessions both years)
  net rating r(2022 vs 2023) = 0.515   (n = 84 players)
  net rating r(2023 vs 2024) = 0.353   (n = 90 players)

## Diagnostic 3 — lambda sensitivity (top-50 by net)
  lam  500 vs 1000: Spearman 0.960 on union of top-50s (n=53), top-50 overlap 47/50
  lam  500 vs 2000: Spearman 0.884 on union of top-50s (n=55), top-50 overlap 45/50
  lam  500 vs 5000: Spearman 0.733 on union of top-50s (n=58), top-50 overlap 42/50
  lam 1000 vs 2000: Spearman 0.966 on union of top-50s (n=52), top-50 overlap 48/50
  lam 1000 vs 5000: Spearman 0.847 on union of top-50s (n=56), top-50 overlap 44/50
  lam 2000 vs 5000: Spearman 0.937 on union of top-50s (n=54), top-50 overlap 46/50

## Diagnostic 4 — garbage-time sensitivity
garbage-time possessions (period >= 4, |margin before| >= 15): 10,571 of 154,265 (6.85%)
  net rating r(full vs garbage-excluded), players >= 500 poss: 0.9770  (n = 216)

## Diagnostic 5 — replacement-level behavior
  players < 300 possessions: n=35, mean net -0.058, min -0.543, max +0.378
  players >= 1000 possessions: n=198, mean net +0.121
  all players: mean net +0.000
  (want: low-poss group mean below average, and shrunk — not at extremes)

## Smoke test ONLY (never a promotion criterion) — lam=5000, players >= 1500 possessions 2021-24
  top-15 OFFENSE:
    Breanna Stewart               +4.30  (net  +5.93, poss 22,126, min   5,609)
    Kelsey Plum                   +4.06  (net  +4.76, poss 21,740, min   5,407)
    Jackie Young                  +3.22  (net  +3.49, poss 22,503, min   5,582)
    Chelsea Gray                  +3.17  (net  +4.67, poss 19,741, min   4,916)
    Jonquel Jones                 +3.11  (net  +6.07, poss 19,541, min   5,062)
    Skylar Diggins                +3.09  (net  +5.33, poss 14,789, min   3,778)
    Sabrina Ionescu               +3.02  (net  +1.79, poss 20,673, min   5,287)
    Aliyah Boston                 +3.01  (net  +2.50, poss 10,078, min   2,550)
    Satou Sabally                 +2.79  (net  +2.90, poss 10,722, min   2,669)
    DeWanna Bonner                +2.73  (net  +4.58, poss 21,191, min   5,498)
    A'ja Wilson                   +2.69  (net  +4.22, poss 22,914, min   5,687)
    Allie Quigley                 +2.61  (net  +3.31, poss  8,276, min   2,089)
    Teaira McCowan                +2.56  (net  +2.27, poss 13,595, min   3,462)
    Marina Mabrey                 +2.33  (net  +1.39, poss 17,893, min   4,539)
    Napheesa Collier              +2.25  (net  +3.40, poss 16,198, min   4,121)
  top-15 DEFENSE:
    Jonquel Jones                 +2.95  (net  +6.07, poss 19,541, min   5,062)
    Candace Parker                +2.79  (net  +4.58, poss  9,984, min   2,504)
    Brionna Jones                 +2.77  (net  +4.32, poss 14,989, min   3,880)
    Courtney Vandersloot          +2.46  (net  +4.08, poss 18,803, min   4,758)
    Skylar Diggins                +2.24  (net  +5.33, poss 14,789, min   3,778)
    Bridget Carleton              +2.03  (net  +2.28, poss 13,514, min   3,454)
    Leonie Fiebich                +2.02  (net  +3.28, poss  4,585, min   1,178)
    Alanna Smith                  +1.95  (net  +2.63, poss 10,532, min   2,678)
    DeWanna Bonner                +1.85  (net  +4.58, poss 21,191, min   5,498)
    Alyssa Thomas                 +1.82  (net  +3.10, poss 19,313, min   4,968)
    Alysha Clark                  +1.76  (net  +1.70, poss 11,979, min   3,037)
    Jewell Loyd                   +1.71  (net  +3.20, poss 19,823, min   4,958)
    Angel Reese                   +1.65  (net  +2.05, poss  4,345, min   1,104)
    Breanna Stewart               +1.63  (net  +5.93, poss 22,126, min   5,609)
    Brittney Sykes                +1.55  (net  +1.40, poss 14,268, min   3,609)

wrote C:\Users\jgallagher\wnba-betting-model\data\rapm\rapm_v0.csv (265 players), rapm_by_season.csv, stint_eval.csv
runtime 14s
