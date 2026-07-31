# bet_pocket_mining_v1 — battery enumeration (closed, preregistered)

*The registration's features_desc is the closed battery; this document enumerates it. No slices added, none dropped.*

## Cell definition

A cell = (era, timing, bet type, disagreement threshold, execution) x ONE conditioning dimension level. The battery is the cross of the base grid with each conditioner separately — NOT the full cross of all conditioners with each other.

## Dimensions

- threshold: {0.5, 1, 1.5, 2, 3} points of model-vs-market disagreement
- timing: extension era {T-24h, near-tip}; old era {near-tip} only (the single ~T-64m snapshot IS the near-tip line; T-24h has zero coverage there — measured in clv_transfer_v1)
- bet type: extension {spread, total, moneyline}; old {spread} only (the old master captured spreads only)
- execution: consensus (no shopping) vs best_book (line shopping at the same vintage)
- conditioners (one at a time): none; |consensus spread| terciles {small, mid, large}; market-total terciles {low, mid, high} (extension only — the old era has no totals market to condition on); bet side {home, away, fav, dog} for spread/moneyline and {over, under} for totals; rest-differential sign {home_more, equal, away_more}; season phase {early <=10, mid 11-30, late >30} team game number; weekend flag {weekend, weekday}

## Cell count

| era | timing | bet_type | n_cells |
|---|---|---|---|
| extension | T-24h | moneyline | 190 |
| extension | T-24h | spread | 190 |
| extension | T-24h | total | 170 |
| extension | near-tip | moneyline | 190 |
| extension | near-tip | spread | 190 |
| extension | near-tip | total | 170 |
| old | near-tip | spread | 160 |

**Total cells: 1260.** Per (era, timing, bet type): 5 thresholds x 2 executions x conditioner levels (extension spread/moneyline 19 = 1 none + 3 line + 3 total + 4 side + 3 rest + 3 phase + 2 weekend; extension totals 17 (side has 2 levels); old spread 16 (no market-total terciles)).

Note: side levels overlap (a home bet on a home favorite sits in both side=home and side=fav) and every bet sits in the none/all cell; within the other dimensions levels partition their frame. Overlap is a property of the registered battery, handled honestly by the permutation null + BH (each cell's null is its own).

## Conventions (binding for reproduction)

- Consensus vintages: hour cutoffs use the latest snapshot timestamp <= cutoff (mean over books present at that single vintage); near-tip uses each book's latest pre-tip row (clv_transfer_v1 conventions, reproduced exactly — see the crosscheck audit).
- Spread edge = str_margin_cal - market_margin, market_margin = -(consensus home spread). Total edge = str_total_cal - consensus total. Moneyline edge (points scale, so the registered thresholds apply unchanged) = str_margin_cal - sigma*ppf(devigged consensus home prob), sigma = 12.9022 from dist_margin_cover; model home-win prob = Phi(center/sigma) = the Gaussian cover formula at spread 0.
- h2h devig: proportional, per book with a valid two-sided pair (|american price| < 10000); consensus prob = mean over books.
- Pricing: spread/total consensus basis settles on the consensus line at synthetic -110; best_book basis takes the most favorable captured line (tie-break: best price) and settles on the line taken. MONEYLINE ADAPTATION (documented deviation): a synthetic -110 is meaningless for moneylines (favorites pay far less), so the consensus basis pays the MEAN payout multiplier over books quoting the bet side at the vintage; best_book pays the best multiplier. Both remain flat-stake.
- Grading: margin_true vs line (spread), total_true vs line (total), margin_true > 0 (moneyline; no ties exist). Pushes risk the stake and return 0; ROI = net profit / stakes settled.
- CLV (T-24h cells only; the only timing with a later reference): signed points the near-tip consensus moved toward the bet side; moneyline CLV in implied-margin points via the same sigma*ppf map.
- Terciles are computed per (era, timing) over candidate games with a model prediction; boundaries:
    - extension/T-24h line_abs_spread: q33 4.023 / q67 7.877
    - extension/T-24h market_total: q33 163.406 / q67 169.500
    - extension/near-tip line_abs_spread: q33 4.439 / q67 8.389
    - extension/near-tip market_total: q33 162.955 / q67 169.742
    - old/near-tip line_abs_spread: q33 4.500 / q67 8.750
- Season phase = mean of the two teams' season game numbers (including the target game, both season types, from master_team dates — schedule known pregame, walk-forward safe). Rest = days since the team's previous game within the season; season openers have undefined rest sign and are excluded from rest cells only. Weekend = Sat/Sun by game date.
- Null calibration: per era, 200 permutations of the model column (margin + total shuffled JOINTLY, one draw per battery) across the era's candidate games; per-cell p = fraction of permuted batteries with equal-or-better ROI in that cell (empty permuted cells count as not-better; min resolvable p = 1/n_perms; a Phipson-Smyth companion column is reported). BH at 10% across all starred-eligible (n >= 40) cells.

Accounting: {"totals_point_mismatch_rows": 0, "h2h_rows_not_matching_either_team": 0, "h2h_price_anomaly_rows": 0, "h2h_games_no_valid_pair": 0, "ml_probs_clipped": 0}
Schedule features: {"pred_games": 673, "master_date_mismatches_vs_predictions": 0, "rest_undefined_games": 0, "phase_counts": {"mid": 384, "late": 200, "early": 89}, "note": "phase = mean of the two teams' season game numbers (incl. this game); rest across both season types within a season; weekend by master_team game date."}
