# props_edge_v1 — Results

*Generated 2026-07-31T16:10:35+00:00 by props_edge.py. Registered protocol: experiments/registry.jsonl (props_edge_v1, 2026-07-31T14:59:26Z). MEASUREMENT STUDY — sentinel gates by design; nothing here promotes anything.*

## THE HEADLINE — are our projections better than the books' lines?

- **ALL rows (regular + playoffs)** (n=5845 player-games): projection MAE **5.222** vs line MAE **4.921** -> difference **+0.301** points (90% CI +0.258 to +0.344); projection closer on 44.9% of player-games. **THE BOOKS' LINE IS CLOSER.**
- **REGULAR SEASON only (headline)** (n=5383 player-games): projection MAE **5.244** vs line MAE **4.932** -> difference **+0.312** points (90% CI +0.268 to +0.355); projection closer on 44.7% of player-games. **THE BOOKS' LINE IS CLOSER.**
- **PLAYOFFS only (reported, never aggregated)** (n=462 player-games): projection MAE **4.965** vs line MAE **4.790** -> difference **+0.175** points (90% CI +0.047 to +0.304); projection closer on 47.8% of player-games. **THE BOOKS' LINE IS CLOSER.**

> **Plainly: the books' player-points lines are a better predictor of actual points than our projection is, by 0.31 points of MAE per player-game in the regular season. Any pocket found below is a pocket found DESPITE a worse point estimate, and must be treated as a candidate for live confirmation only.**


Full breakdown (by season, phase, line height, role, minutes volume, venue, book): `projection_vs_line.csv`.

## Coverage

- backfill: 784/784 games done (0 missing); statuses {'ok': 784}; by season {'2025': 310, '2024': 262, '2026': 212}
- rows: 36946 total -> 36946 player_points -> 36946 near-tip unique -> 33610 candidate rows (5930 candidate player-games)
- resolution: 36390/36946 rows; unique names 4420 (team-scope 4352, season-scope 0, ambiguous 0, unresolved 3)
- skip ladder: {"rows_in": 36946, "skip_unresolved_rows": 556, "skip_ambiguous_rows": 0, "skip_no_prior_appearance_rows": 915, "skip_below_min_prior_rows": 1865, "skip_ungraded_game_rows": 0, "candidate_rows": 33610}
- voids (DNP, no action): 310 rows; venue unknown: 7 rows; alternate-ladder share of candidate rows: 0.092 (30517 (game,book,player) groups)
- phase: 5466 regular-season player-games vs 464 playoff player-games (46 playoff games over 27 dates). **The playoff sample is 7.8% of the study and every playoff cell re-uses those same rows.**
- tercile boundaries (per season, candidate player-games): {"line_2024": [12.5, 16.5], "line_2025": [11.5, 14.5], "line_2026": [10.5, 14.5], "min_2024": [29.4178753079, 32.80127700782365], "min_2025": [27.672478185713338, 31.009641285365408], "min_2026": [25.688571309611014, 30.237754948616445]}

## Battery

Cells are the registered closed battery — execution ['consensus', 'best_line', 'per_book'] x price basis ['captured', 'synthetic110'] x threshold [1.0, 2.0, 3.0] x conditioner ['none', 'line_terc', 'role', 'min_terc', 'book', 'season', 'venue'] — evaluated under three scopes: `all` (**the registered battery**), `regular` (the headline-safe companion) and `playoff` (reported, never aggregated into a headline; John has paused playoff betting). BH runs WITHIN each scope family, so the playoff split does not inflate the registered battery's multiplicity.

**Two nulls are reported.** `p_perm` is the REGISTERED null (projection shuffled within season). `p_perm_phaseblock` shuffles within (season, phase) and is the only valid null for a phase-scoped cell: playoff player-games are 7.8% of the pool and carry a different projection level, so a season-wide shuffle hands playoff rows regular-season projections and mis-centres the playoff null. Measured here: mean null ROI on eligible playoff cells is -0.076 under the registered shuffle vs -0.051 on regular-season cells, which manufactures 'significance' for ordinary playoff results. **Treat every playoff star under the registered null as an artefact until the phase-blocked column agrees.**


### scope = all  (REGISTERED BATTERY)

- cells 306; eligible (n_settled >= 100) 298; **starred (BH q <= 0.1): 3**, of which **0 have ROI > 0**; expected false among starred at q=0.1: 0.3
- under the phase-blocked companion null: 3 starred, 0 of them profitable
- **every starred cell in this scope LOSES money.** A permutation star means 'better than a shuffled projection', not 'profitable'; a cell that loses less than chance is not a bet.
- best observed eligible-cell ROI +0.0237; P(best null >= best observed) = 0.935 (200 within-season permutations)
- mean ROI across eligible cells: -0.0638

**The 3 starred cell(s) in this scope (these are what BH selected, whatever their ROI):**

execution  price_basis  threshold  cond_dim  cond_level  n_bets  wins  losses  pushes  hit_rate     roi  roi_ci90_low  roi_ci90_high  p_perm   q_bh  starred  p_perm_phaseblock  starred_phaseblock
 per_book synthetic110     1.0000      book betonlineag    2499  1286    1213       0    0.5146 -0.0176       -0.0462         0.0100  0.0000 0.0000     True             0.0000                True
best_line synthetic110     1.0000 line_terc         low    1260   637     623       0    0.5056 -0.0348       -0.0711         0.0040  0.0000 0.0000     True             0.0050               False
consensus synthetic110     1.0000 line_terc         low    1262   627     633       2    0.4976 -0.0499       -0.0870        -0.0118  0.0000 0.0000     True             0.0000                True


**Top eligible cells by ROI** (ranking is by return, not by significance — a high-ROI cell with a large p_perm is noise):


execution  price_basis  threshold  cond_dim cond_level  n_bets  wins  losses  pushes  hit_rate     roi  roi_ci90_low  roi_ci90_high  p_perm   q_bh  starred  p_perm_phaseblock  starred_phaseblock
best_line synthetic110     2.0000      role      bench     138    74      64       0    0.5362  0.0237       -0.1042         0.1402  0.0100 0.3311    False             0.0100               False
best_line synthetic110     1.0000 line_terc        mid    1142   603     539       0    0.5280  0.0080       -0.0358         0.0528  0.2950 1.0000    False             0.3450               False
best_line synthetic110     1.0000    season       2024    1113   585     528       0    0.5256  0.0034       -0.0446         0.0513  0.6450 1.0000    False             0.6350               False
best_line synthetic110     1.0000  min_terc       high    1283   671     612       0    0.5230 -0.0016       -0.0462         0.0424  0.5850 1.0000    False             0.5750               False
best_line synthetic110     1.0000 line_terc       high    1222   637     585       0    0.5213 -0.0048       -0.0536         0.0419  0.9250 1.0000    False             0.9600               False
best_line     captured     2.0000      role      bench     138    74      64       0    0.5362 -0.0054       -0.1306         0.1083  0.0150 0.3438    False             0.0200               False
 per_book synthetic110     2.0000      role      bench     626   326     300       0    0.5208 -0.0058       -0.1376         0.1163  0.0100 0.3311    False             0.0250               False
best_line synthetic110     1.0000     venue       away    1783   927     856       0    0.5199 -0.0074       -0.0465         0.0287  0.1950 1.0000    False             0.1600               False
best_line synthetic110     1.0000      role    starter    3389  1758    1631       0    0.5187 -0.0097       -0.0348         0.0158  0.1250 0.9551    False             0.1300               False
best_line synthetic110     1.0000      none        all    3624  1877    1747       0    0.5179 -0.0112       -0.0359         0.0137  0.1050 0.9106    False             0.1200               False
best_line     captured     1.0000    season       2024    1113   585     528       0    0.5256 -0.0115       -0.0593         0.0366  0.6000 1.0000    False             0.6050               False
best_line synthetic110     1.0000  min_terc        mid    1229   635     594       0    0.5167 -0.0136       -0.0544         0.0289  0.5150 1.0000    False             0.5000               False


### scope = regular  (companion)

- cells 306; eligible (n_settled >= 100) 298; **starred (BH q <= 0.1): 0**, of which **0 have ROI > 0**; expected false among starred at q=0.1: 0.0
- under the phase-blocked companion null: 1 starred, 0 of them profitable
- best observed eligible-cell ROI +0.0052; P(best null >= best observed) = 0.990 (200 within-season permutations)
- mean ROI across eligible cells: -0.0709

**Top eligible cells by ROI** (ranking is by return, not by significance — a high-ROI cell with a large p_perm is noise):


execution  price_basis  threshold  cond_dim cond_level  n_bets  wins  losses  pushes  hit_rate     roi  roi_ci90_low  roi_ci90_high  p_perm   q_bh  starred  p_perm_phaseblock  starred_phaseblock
best_line synthetic110     1.0000 line_terc        mid    1075   566     509       0    0.5265  0.0052       -0.0391         0.0487  0.3000 1.0000    False             0.3450               False
best_line synthetic110     2.0000      role      bench     116    61      55       0    0.5259  0.0039       -0.1337         0.1385  0.0300 1.0000    False             0.0550               False
best_line synthetic110     1.0000  min_terc       high    1188   623     565       0    0.5244  0.0011       -0.0455         0.0478  0.4800 1.0000    False             0.5150               False
best_line synthetic110     2.0000 line_terc        mid     622   323     299       0    0.5193 -0.0086       -0.0688         0.0562  0.5500 1.0000    False             0.5550               False
best_line synthetic110     1.0000 line_terc       high    1135   588     547       0    0.5181 -0.0110       -0.0602         0.0390  0.9850 1.0000    False             0.9800               False
best_line synthetic110     1.0000    season       2026    1096   566     530       0    0.5164 -0.0141       -0.0606         0.0315  0.1650 1.0000    False             0.1100               False
best_line synthetic110     1.0000      role    starter    3145  1624    1521       0    0.5164 -0.0142       -0.0400         0.0119  0.3150 1.0000    False             0.2750               False
best_line synthetic110     1.0000     venue       away    1654   854     800       0    0.5163 -0.0143       -0.0543         0.0238  0.3200 1.0000    False             0.2650               False
best_line synthetic110     2.0000  min_terc       high     707   365     342       0    0.5163 -0.0144       -0.0828         0.0526  0.8200 1.0000    False             0.7700               False
best_line synthetic110     1.0000    season       2024     984   508     476       0    0.5163 -0.0144       -0.0656         0.0376  0.8600 1.0000    False             0.8550               False
best_line synthetic110     1.0000      none        all    3344  1724    1620       0    0.5156 -0.0158       -0.0411         0.0097  0.2600 1.0000    False             0.2300               False
best_line     captured     1.0000 line_terc        mid    1075   566     509       0    0.5265 -0.0171       -0.0608         0.0261  0.2950 1.0000    False             0.3350               False


### scope = playoff  (companion)

- cells 306; eligible (n_settled >= 100) 134; **starred (BH q <= 0.1): 89**, of which **68 have ROI > 0**; expected false among starred at q=0.1: 8.9
- under the phase-blocked companion null: 54 starred, 51 of them profitable
- best observed eligible-cell ROI +0.2638; P(best null >= best observed) = 0.005 (200 within-season permutations)
- mean ROI across eligible cells: +0.0140

**The 89 starred cell(s) in this scope (these are what BH selected, whatever their ROI):**

execution  price_basis  threshold  cond_dim  cond_level  n_bets  wins  losses  pushes  hit_rate     roi  roi_ci90_low  roi_ci90_high  p_perm   q_bh  starred  p_perm_phaseblock  starred_phaseblock
 per_book synthetic110     3.0000  min_terc         low     142    94      48       0    0.6620  0.2638       -0.0356         0.5306  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000     venue        away     191   122      69       0    0.6387  0.2194        0.0231         0.3951  0.0000 0.0000     True             0.0000                True
 per_book     captured     3.0000  min_terc         low     142    94      48       0    0.6620  0.2009       -0.0888         0.4575  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     2.0000  min_terc         low     294   182     112       0    0.6190  0.1818       -0.0325         0.3954  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     1.0000      book   betrivers     164   101      63       0    0.6159  0.1757        0.0289         0.3056  0.0000 0.0000     True             0.0100                True
 per_book synthetic110     2.0000 line_terc        high     299   183     116       0    0.6120  0.1684       -0.0734         0.3830  0.0000 0.0000     True             0.0000                True
 per_book     captured     3.0000     venue        away     191   122      69       0    0.6387  0.1512       -0.0375         0.3166  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000 line_terc        high     167   100      67       0    0.5988  0.1432       -0.2322         0.4753  0.0050 0.0149     True             0.0000                True
best_line synthetic110     1.0000    season        2024     129    77      52       0    0.5969  0.1395       -0.0156         0.2576  0.0150 0.0324     True             0.0250                True
 per_book     captured     2.0000  min_terc         low     294   182     112       0    0.6190  0.1307       -0.0818         0.3390  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000    season        2025     224   132      92       0    0.5893  0.1250       -0.1905         0.3446  0.0000 0.0000     True             0.0000                True
consensus synthetic110     1.0000    season        2024     129    76      53       0    0.5891  0.1247       -0.0192         0.2397  0.0000 0.0000     True             0.0050                True
best_line     captured     1.0000    season        2024     129    77      52       0    0.5969  0.1243       -0.0305         0.2435  0.0300 0.0529     True             0.0300                True
 per_book synthetic110     1.0000    season        2024     804   472     332       0    0.5871  0.1208       -0.0097         0.2263  0.0050 0.0149     True             0.0200                True
consensus synthetic110     1.0000  min_terc         low     104    61      43       0    0.5865  0.1198        0.0118         0.2202  0.0000 0.0000     True             0.0000                True
best_line synthetic110     1.0000  min_terc         low     104    61      43       0    0.5865  0.1198        0.0118         0.2202  0.0000 0.0000     True             0.0000                True
 per_book     captured     2.0000 line_terc        high     299   183     116       0    0.6120  0.1146       -0.1162         0.3237  0.0050 0.0149     True             0.0050                True
 per_book synthetic110     2.0000      role       bench     123    71      52       0    0.5772  0.1020       -0.2610         0.4087  0.0100 0.0239     True             0.0700               False
 per_book synthetic110     1.0000  min_terc         low     567   325     242       0    0.5732  0.0943       -0.0158         0.1981  0.0000 0.0000     True             0.0050                True
consensus     captured     1.0000    season        2024     122    71      51       0    0.5820  0.0888       -0.0406         0.1889  0.0200 0.0383     True             0.0150                True
 per_book synthetic110     2.0000     venue        away     395   225     170       0    0.5696  0.0875       -0.0597         0.2315  0.0050 0.0149     True             0.0150                True
 per_book     captured     3.0000    season        2025     224   132      92       0    0.5893  0.0854       -0.2194         0.3001  0.0000 0.0000     True             0.0000                True
 per_book     captured     1.0000    season        2024     804   472     332       0    0.5871  0.0818       -0.0419         0.1848  0.0200 0.0383     True             0.0200                True
consensus synthetic110     1.0000     venue        away     129    73      56       0    0.5659  0.0803       -0.0455         0.2081  0.0000 0.0000     True             0.0150                True
best_line synthetic110     1.0000     venue        away     129    73      56       0    0.5659  0.0803       -0.0455         0.2081  0.0200 0.0383     True             0.0200                True
 per_book     captured     1.0000      book   betrivers     164   101      63       0    0.6159  0.0799       -0.0457         0.1938  0.0200 0.0383     True             0.0150                True
 per_book synthetic110     1.0000 line_terc        high     580   327     253       0    0.5638  0.0763       -0.0786         0.2229  0.0450 0.0718     True             0.0800               False
consensus     captured     1.0000  min_terc         low     101    59      42       0    0.5842  0.0761       -0.0457         0.1830  0.0000 0.0000     True             0.0000                True
best_line     captured     1.0000  min_terc         low     104    61      43       0    0.5865  0.0758       -0.0312         0.1757  0.0000 0.0000     True             0.0050                True
 per_book     captured     2.0000      role       bench     123    71      52       0    0.5772  0.0729       -0.2858         0.3512  0.0150 0.0324     True             0.0900               False
 per_book     captured     3.0000 line_terc        high     167   100      67       0    0.5988  0.0693       -0.2939         0.3862  0.0400 0.0654     True             0.0300                True
 per_book synthetic110     3.0000      none         all     365   204     161       0    0.5589  0.0670       -0.1567         0.2414  0.0000 0.0000     True             0.0150                True
 per_book     captured     1.0000  min_terc         low     567   325     242       0    0.5732  0.0571       -0.0522         0.1600  0.0000 0.0000     True             0.0100                True
 per_book synthetic110     1.0000     venue        away     779   428     351       0    0.5494  0.0489       -0.0673         0.1646  0.0550 0.0838     True             0.0750               False
best_line synthetic110     1.0000      role     starter     244   134     110       0    0.5492  0.0484       -0.0455         0.1347  0.0000 0.0000     True             0.0250                True
 per_book synthetic110     1.0000      book      betmgm     204   112      92       0    0.5490  0.0481       -0.0626         0.1367  0.0450 0.0718     True             0.1150               False
best_line     captured     1.0000     venue        away     129    73      56       0    0.5659  0.0480       -0.0750         0.1701  0.0400 0.0654     True             0.0600               False
 per_book synthetic110     2.0000    season        2025     486   266     220       0    0.5473  0.0449       -0.1565         0.2111  0.0000 0.0000     True             0.0050                True
 per_book synthetic110     3.0000      role     starter     318   174     144       0    0.5472  0.0446       -0.1888         0.2354  0.0050 0.0149     True             0.0350                True
best_line synthetic110     1.0000      none         all     280   153     127       0    0.5464  0.0432       -0.0492         0.1260  0.0000 0.0000     True             0.0250                True
consensus synthetic110     1.0000      role     starter     244   133     111       0    0.5451  0.0406       -0.0493         0.1230  0.0000 0.0000     True             0.0000                True
 per_book     captured     2.0000     venue        away     395   225     170       0    0.5696  0.0388       -0.1027         0.1775  0.0250 0.0465     True             0.0500               False
 per_book synthetic110     1.0000      role     starter    1486   807     679       0    0.5431  0.0368       -0.0507         0.1177  0.0050 0.0149     True             0.0400                True
consensus synthetic110     1.0000      none         all     280   152     128       0    0.5429  0.0364       -0.0525         0.1147  0.0000 0.0000     True             0.0000                True
consensus     captured     1.0000     venue        away     123    69      54       0    0.5610  0.0337       -0.0892         0.1542  0.0200 0.0383     True             0.0250                True
 per_book synthetic110     2.0000      book      bovada     113    61      52       0    0.5398  0.0306       -0.0989         0.1621  0.0000 0.0000     True             0.0200                True
best_line     captured     1.0000      role     starter     244   134     110       0    0.5492  0.0272       -0.0682         0.1156  0.0100 0.0239     True             0.0450               False
 per_book synthetic110     1.0000      none         all    1677   901     776       0    0.5373  0.0257       -0.0605         0.1039  0.0050 0.0149     True             0.0450               False
 per_book synthetic110     1.0000      book     fanduel     265   142     123       0    0.5358  0.0230       -0.0809         0.1116  0.0000 0.0000     True             0.0350                True
 per_book synthetic110     2.0000      none         all     829   444     385       0    0.5356  0.0225       -0.1100         0.1511  0.0100 0.0239     True             0.0350                True
 per_book     captured     1.0000      book      betmgm     204   112      92       0    0.5490  0.0223       -0.0893         0.1095  0.0650 0.0979     True             0.1450               False
best_line     captured     1.0000      none         all     280   153     127       0    0.5464  0.0202       -0.0740         0.1036  0.0050 0.0149     True             0.0400                True
 per_book synthetic110     1.0000      book      bovada     236   126     110       0    0.5339  0.0193       -0.0877         0.1112  0.0050 0.0149     True             0.0350                True
best_line synthetic110     2.0000      none         all     133    71      62       0    0.5338  0.0191       -0.1229         0.1596  0.0150 0.0324     True             0.0650               False
consensus synthetic110     2.0000      none         all     133    71      62       0    0.5338  0.0191       -0.1229         0.1596  0.0000 0.0000     True             0.0050                True
consensus synthetic110     1.0000 line_terc         low     126    67      59       0    0.5317  0.0152       -0.1091         0.1319  0.0000 0.0000     True             0.0100                True
best_line synthetic110     1.0000 line_terc         low     126    67      59       0    0.5317  0.0152       -0.1091         0.1319  0.0100 0.0239     True             0.0300                True
 per_book synthetic110     2.0000      book     fanduel     128    68      60       0    0.5312  0.0142       -0.1409         0.1634  0.0100 0.0239     True             0.0450               False
 per_book synthetic110     2.0000 line_terc         low     317   168     149       0    0.5300  0.0118       -0.1957         0.2049  0.0050 0.0149     True             0.0250                True
best_line synthetic110     1.0000     venue        home     151    80      71       0    0.5298  0.0114       -0.1311         0.1381  0.0300 0.0529     True             0.1100               False
 per_book synthetic110     2.0000      role     starter     706   373     333       0    0.5283  0.0086       -0.1264         0.1395  0.0400 0.0654     True             0.1050               False
 per_book     captured     2.0000    season        2025     486   266     220       0    0.5473  0.0081       -0.1902         0.1727  0.0050 0.0149     True             0.0200                True
 per_book     captured     3.0000      none         all     365   204     161       0    0.5589  0.0068       -0.2112         0.1796  0.0050 0.0149     True             0.0450               False
 per_book synthetic110     1.0000     venue        home     898   473     425       0    0.5267  0.0056       -0.1371         0.1357  0.0500 0.0779     True             0.1100               False
 per_book synthetic110     2.0000      book betonlineag     133    70      63       0    0.5263  0.0048       -0.1337         0.1395  0.0100 0.0239     True             0.0350                True
 per_book     captured     1.0000      book     fanduel     265   142     123       0    0.5358  0.0020       -0.0976         0.0886  0.0050 0.0149     True             0.0400                True
 per_book     captured     2.0000      book      bovada     113    61      52       0    0.5398  0.0011       -0.1264         0.1295  0.0050 0.0149     True             0.0200                True
 per_book     captured     1.0000      role     starter    1486   807     679       0    0.5431  0.0006       -0.0826         0.0770  0.0250 0.0465     True             0.0650               False
consensus     captured     1.0000      role     starter     237   128     109       0    0.5401 -0.0001       -0.0819         0.0760  0.0050 0.0149     True             0.0400                True
consensus synthetic110     1.0000     venue        home     151    79      72       0    0.5232 -0.0012       -0.1383         0.1221  0.0150 0.0324     True             0.0600               False
consensus synthetic110     2.0000      role     starter     111    58      53       0    0.5225 -0.0025       -0.1449         0.1455  0.0200 0.0383     True             0.0550               False
 per_book synthetic110     1.0000      book betonlineag     272   142     130       0    0.5221 -0.0033       -0.0826         0.0691  0.0150 0.0324     True             0.0550               False
best_line     captured     1.0000     venue        home     151    80      71       0    0.5298 -0.0036       -0.1476         0.1234  0.0550 0.0838     True             0.1350               False
consensus     captured     1.0000      none         all     272   146     126       0    0.5368 -0.0036       -0.0873         0.0713  0.0050 0.0149     True             0.0200                True
 per_book     captured     2.0000      book     fanduel     128    68      60       0    0.5312 -0.0042       -0.1578         0.1459  0.0100 0.0239     True             0.0450               False
best_line     captured     2.0000      none         all     133    71      62       0    0.5338 -0.0056       -0.1466         0.1354  0.0350 0.0594     True             0.1050               False
 per_book     captured     1.0000      none         all    1677   901     776       0    0.5373 -0.0081       -0.0916         0.0667  0.0350 0.0594     True             0.0700               False
 per_book     captured     1.0000      book      bovada     236   126     110       0    0.5339 -0.0084       -0.1128         0.0810  0.0050 0.0149     True             0.0350                True
best_line     captured     1.0000 line_terc         low     126    67      59       0    0.5317 -0.0159       -0.1370         0.1006  0.0100 0.0239     True             0.0550               False
 per_book     captured     2.0000      none         all     829   444     385       0    0.5356 -0.0182       -0.1470         0.1093  0.0350 0.0594     True             0.0950               False
 per_book     captured     2.0000      book betonlineag     133    70      63       0    0.5263 -0.0188       -0.1569         0.1138  0.0300 0.0529     True             0.0800               False
 per_book     captured     2.0000 line_terc         low     317   168     149       0    0.5300 -0.0203       -0.2232         0.1640  0.0100 0.0239     True             0.0500               False
consensus     captured     2.0000      none         all     129    68      61       0    0.5271 -0.0260       -0.1650         0.1083  0.0150 0.0324     True             0.0650               False
 per_book synthetic110     1.0000 line_terc         low     661   335     326       0    0.5068 -0.0325       -0.1649         0.0946  0.0200 0.0383     True             0.1050               False
consensus     captured     1.0000     venue        home     149    77      72       0    0.5168 -0.0344       -0.1730         0.0860  0.0500 0.0779     True             0.1500               False
consensus     captured     1.0000 line_terc         low     122    64      58       0    0.5246 -0.0355       -0.1610         0.0771  0.0100 0.0239     True             0.0600               False
consensus synthetic110     1.0000    season        2025     151    76      75       0    0.5033 -0.0391       -0.1360         0.0352  0.0100 0.0239     True             0.1000               False
best_line synthetic110     1.0000    season        2025     151    76      75       0    0.5033 -0.0391       -0.1360         0.0352  0.0300 0.0529     True             0.1550               False
 per_book synthetic110     1.0000      book    fanatics     149    74      75       0    0.4966 -0.0519       -0.1336         0.0093  0.0200 0.0383     True             0.1300               False


**Top eligible cells by ROI** (ranking is by return, not by significance — a high-ROI cell with a large p_perm is noise):


execution  price_basis  threshold  cond_dim cond_level  n_bets  wins  losses  pushes  hit_rate    roi  roi_ci90_low  roi_ci90_high  p_perm   q_bh  starred  p_perm_phaseblock  starred_phaseblock
 per_book synthetic110     3.0000  min_terc        low     142    94      48       0    0.6620 0.2638       -0.0356         0.5306  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000     venue       away     191   122      69       0    0.6387 0.2194        0.0231         0.3951  0.0000 0.0000     True             0.0000                True
 per_book     captured     3.0000  min_terc        low     142    94      48       0    0.6620 0.2009       -0.0888         0.4575  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     2.0000  min_terc        low     294   182     112       0    0.6190 0.1818       -0.0325         0.3954  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     1.0000      book  betrivers     164   101      63       0    0.6159 0.1757        0.0289         0.3056  0.0000 0.0000     True             0.0100                True
 per_book synthetic110     2.0000 line_terc       high     299   183     116       0    0.6120 0.1684       -0.0734         0.3830  0.0000 0.0000     True             0.0000                True
 per_book     captured     3.0000     venue       away     191   122      69       0    0.6387 0.1512       -0.0375         0.3166  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000 line_terc       high     167   100      67       0    0.5988 0.1432       -0.2322         0.4753  0.0050 0.0149     True             0.0000                True
best_line synthetic110     1.0000    season       2024     129    77      52       0    0.5969 0.1395       -0.0156         0.2576  0.0150 0.0324     True             0.0250                True
 per_book     captured     2.0000  min_terc        low     294   182     112       0    0.6190 0.1307       -0.0818         0.3390  0.0000 0.0000     True             0.0000                True
 per_book synthetic110     3.0000    season       2025     224   132      92       0    0.5893 0.1250       -0.1905         0.3446  0.0000 0.0000     True             0.0000                True
consensus synthetic110     1.0000    season       2024     129    76      53       0    0.5891 0.1247       -0.0192         0.2397  0.0000 0.0000     True             0.0050                True


### Companion diagnostic — main lines vs alternate ladders (per_book universe, NOT a registered cell)

 threshold  price_basis line_kind   scope  n_bets     roi
    1.0000     captured      main     all   18621 -0.0624
    1.0000     captured      main regular   16986 -0.0679
    1.0000     captured alternate     all    1089 -0.1291
    1.0000     captured alternate regular    1047 -0.1306
    1.0000 synthetic110      main     all   19108 -0.0354
    1.0000 synthetic110      main regular   17473 -0.0407
    1.0000 synthetic110 alternate     all    2058 -0.0093
    1.0000 synthetic110 alternate regular    2016 -0.0133
    2.0000     captured      main     all   10481 -0.0839
    2.0000     captured      main regular    9684 -0.0891
    2.0000     captured alternate     all     705 -0.1383
    2.0000     captured alternate regular     673 -0.1458
    2.0000 synthetic110      main     all   10753 -0.0548
    2.0000 synthetic110      main regular    9956 -0.0598
    2.0000 synthetic110 alternate     all    1292 -0.0100
    2.0000 synthetic110 alternate regular    1260 -0.0197
    3.0000     captured      main     all    5299 -0.1093
    3.0000     captured      main regular    4957 -0.1171
    3.0000     captured alternate     all     389 -0.1292
    3.0000     captured alternate regular     366 -0.1408
    3.0000 synthetic110      main     all    5442 -0.0805
    3.0000 synthetic110      main regular    5100 -0.0885
    3.0000 synthetic110 alternate     all     711  0.0042
    3.0000 synthetic110 alternate regular     688 -0.0122

*If a pocket lives only in the `alternate` rows it is almost certainly a price artefact, not an edge.*


### Headline cells (no conditioner), both phases

execution  price_basis  threshold   scope  n_bets  hit_rate     roi  roi_ci90_low  roi_ci90_high  p_perm
best_line     captured     1.0000     all    3624    0.5179 -0.0348       -0.0589        -0.0103  0.1450
best_line     captured     1.0000 playoff     280    0.5464  0.0202       -0.0740         0.1036  0.0050
best_line     captured     1.0000 regular    3344    0.5156 -0.0394       -0.0645        -0.0139  0.3500
best_line     captured     2.0000     all    2029    0.5067 -0.0579       -0.0916        -0.0230  0.8000
best_line     captured     2.0000 playoff     133    0.5338 -0.0056       -0.1466         0.1354  0.0350
best_line     captured     2.0000 regular    1896    0.5047 -0.0616       -0.0985        -0.0245  0.8900
best_line     captured     3.0000     all    1013    0.4946 -0.0816       -0.1311        -0.0349  0.9950
best_line     captured     3.0000 playoff      56    0.5357 -0.0069       -0.2397         0.1817  0.0550
best_line     captured     3.0000 regular     957    0.4922 -0.0860       -0.1350        -0.0400  0.9950
best_line synthetic110     1.0000     all    3624    0.5179 -0.0112       -0.0359         0.0137  0.1050
best_line synthetic110     1.0000 playoff     280    0.5464  0.0432       -0.0492         0.1260  0.0000
best_line synthetic110     1.0000 regular    3344    0.5156 -0.0158       -0.0411         0.0097  0.2600
best_line synthetic110     2.0000     all    2029    0.5067 -0.0328       -0.0665         0.0032  0.6650
best_line synthetic110     2.0000 playoff     133    0.5338  0.0191       -0.1229         0.1596  0.0150
best_line synthetic110     2.0000 regular    1896    0.5047 -0.0364       -0.0742         0.0007  0.7850
best_line synthetic110     3.0000     all    1013    0.4946 -0.0558       -0.1051        -0.0092  0.9800
best_line synthetic110     3.0000 playoff      56    0.5357  0.0227       -0.2139         0.2174  0.0300
best_line synthetic110     3.0000 regular     957    0.4922 -0.0604       -0.1104        -0.0128  0.9950
consensus     captured     1.0000     all    3475    0.5016 -0.0678       -0.0923        -0.0433  0.3900
consensus     captured     1.0000 playoff     272    0.5368 -0.0036       -0.0873         0.0713  0.0050
consensus     captured     1.0000 regular    3203    0.4986 -0.0732       -0.0982        -0.0495  0.6550
consensus     captured     2.0000     all    1939    0.4910 -0.0887       -0.1231        -0.0531  0.9000
consensus     captured     2.0000 playoff     129    0.5271 -0.0260       -0.1650         0.1083  0.0150
consensus     captured     2.0000 regular    1810    0.4884 -0.0932       -0.1313        -0.0548  0.9750
consensus     captured     3.0000     all     964    0.4844 -0.1033       -0.1528        -0.0562  0.9950
consensus     captured     3.0000 playoff      54    0.5370 -0.0085       -0.2352         0.1841  0.0050
consensus     captured     3.0000 regular     910    0.4813 -0.1090       -0.1596        -0.0592  0.9950
consensus synthetic110     1.0000     all    3626    0.5047 -0.0364       -0.0607        -0.0122  0.0900
consensus synthetic110     1.0000 playoff     280    0.5429  0.0364       -0.0525         0.1147  0.0000
consensus synthetic110     1.0000 regular    3346    0.5015 -0.0425       -0.0674        -0.0178  0.2750
consensus synthetic110     2.0000     all    2030    0.4916 -0.0613       -0.0947        -0.0261  0.7200
consensus synthetic110     2.0000 playoff     133    0.5338  0.0191       -0.1229         0.1596  0.0000
consensus synthetic110     2.0000 regular    1897    0.4886 -0.0669       -0.1042        -0.0297  0.8850
consensus synthetic110     3.0000     all    1014    0.4812 -0.0810       -0.1298        -0.0326  0.9800
consensus synthetic110     3.0000 playoff      56    0.5357  0.0227       -0.2139         0.2174  0.0000
consensus synthetic110     3.0000 regular     958    0.4780 -0.0871       -0.1371        -0.0391  0.9950
 per_book     captured     1.0000     all   19710    0.5040 -0.0661       -0.0899        -0.0423  0.5800
 per_book     captured     1.0000 playoff    1677    0.5373 -0.0081       -0.0916         0.0667  0.0350
 per_book     captured     1.0000 regular   18033    0.5009 -0.0715       -0.0962        -0.0469  0.7550
 per_book     captured     2.0000     all   11186    0.4943 -0.0873       -0.1236        -0.0520  0.9550
 per_book     captured     2.0000 playoff     829    0.5356 -0.0182       -0.1470         0.1093  0.0350
 per_book     captured     2.0000 regular   10357    0.4910 -0.0928       -0.1265        -0.0576  0.9850
 per_book     captured     3.0000     all    5688    0.4835 -0.1107       -0.1603        -0.0621  1.0000
 per_book     captured     3.0000 playoff     365    0.5589  0.0068       -0.2112         0.1796  0.0050
 per_book     captured     3.0000 regular    5323    0.4783 -0.1187       -0.1687        -0.0682  1.0000
 per_book synthetic110     1.0000     all   21166    0.5066 -0.0328       -0.0566        -0.0088  0.2700
 per_book synthetic110     1.0000 playoff    1677    0.5373  0.0257       -0.0605         0.1039  0.0050
 per_book synthetic110     1.0000 regular   19489    0.5040 -0.0379       -0.0620        -0.0141  0.4850
 per_book synthetic110     2.0000     all   12045    0.4976 -0.0500       -0.0846        -0.0160  0.7800
 per_book synthetic110     2.0000 playoff     829    0.5356  0.0225       -0.1100         0.1511  0.0100
 per_book synthetic110     2.0000 regular   11216    0.4948 -0.0553       -0.0884        -0.0211  0.8950
 per_book synthetic110     3.0000     all    6153    0.4868 -0.0707       -0.1208        -0.0222  0.9850
 per_book synthetic110     3.0000 playoff     365    0.5589  0.0670       -0.1567         0.2414  0.0000
 per_book synthetic110     3.0000 regular    5788    0.4822 -0.0794       -0.1277        -0.0297  1.0000


*Pushes risk the stake and return 0 (house convention); voids (player did not play) are no-action and sit outside stakes settled. Captured basis excludes bets whose side price was not posted (n_noprice per cell). ROI is flat-stake profit per unit staked.*


## Artifacts

- `all_cells.csv` — every battery cell, all three scopes
- `bet_log.csv` — row-level: one row per placed bet
- `projection_vs_line.csv` — THE MAE diagnostic
- `resolution_accounting.csv` — every row and where it went
- `permutation_summary.csv` — the 200-permutation null
- `PROPS_LEDGER.md` — surviving pockets, ranked
- `accounting.json` — full machine-readable accounting
- `bet_universe_*.csv` — all candidate rows incl. no-bets
