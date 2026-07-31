# RAPM walk-forward (`build_rapm_walkforward_v1`) — build log 2026-07-31 12:18

*Regime A, INFRASTRUCTURE PREREQUISITE — no promotion claim. Registration is*
*BLOCKING; acceptance is governed by `asof_invariant_audit_v1` (C). This script*
*does not touch the registry, the leaderboards, `data/rapm/rapm_v0.csv`, or*
*`build_rapm.py`.*

## 0. Data (v0 filter: non-technical, full 5v5)
- possessions 237,567 -> usable 236,478 (99.54%)
  - 2021: 33,161 possessions, 209 games
  - 2022: 38,103 possessions, 239 games
  - 2023: 41,344 possessions, 260 games
  - 2024: 41,657 possessions, 262 games
  - 2025: 48,666 possessions, 310 games
  - 2026: 33,547 possessions, 209 games
- global player space 2021-2026: 384 players (design dim 770)
- lambda grid (registered extended sweep): [500, 1000, 2000, 3500, 5000, 7500, 11000, 16000, 23000, 33000, 47000, 68000, 100000]
- per-season grams built in 2s (every window is a sum of these)
- GATE 2 global-space gram identity (season 2021): PASS

## 1. Walk-forward fits — emit season s trained on seasons < s

Lambda is chosen per season on an INNER split strictly inside the training
window (fit seasons < s-1, score stint MAE on s-1), never on s or later, using
v0's argmin rule verbatim. Emit 2022 has a one-season window and no inner
split; it falls back to the largest grid value (thin-history caveat, flagged).

`net_100` follows the REGISTERED extended sweep. `net_100_v0grid` is the same
fit with selection restricted to v0's {500..5000}. Both are equally
uncontaminated — see section 5 for why the default is contested.

- emit 2022: train 2021 (33,161 poss, 155 players), fit_through 2021 | inner val - -> lambda 100000 (fallback_max_grid); v0-grid pick 5000
    stint_mae_walkforward on 2022: 2.1744 (v0-grid 2.1742) vs team baseline 2.1829 vs zero 2.2278; 18.4% of 2022 slots have no prior history (p25 replacement -0.054)
- emit 2023: train 2021-2022 (71,264 poss, 206 players), fit_through 2022 | inner val 2022 -> lambda 33000 (inner_validation); v0-grid pick 5000
    stint_mae_walkforward on 2023: 2.1771 (v0-grid 2.1736) vs team baseline 2.1967 vs zero 2.2391; 11.2% of 2023 slots have no prior history (p25 replacement -0.194)
- emit 2024: train 2021-2023 (112,608 poss, 237 players), fit_through 2023 | inner val 2023 -> lambda 2000 (inner_validation); v0-grid pick 2000
    stint_mae_walkforward on 2024: 2.2119 (v0-grid 2.2119) vs team baseline 2.2229 vs zero 2.2599; 11.7% of 2024 slots have no prior history (p25 replacement -1.490)
- emit 2025: train 2021-2024 (154,265 poss, 265 players), fit_through 2024 | inner val 2024 -> lambda 47000 (inner_validation); v0-grid pick 5000
    stint_mae_walkforward on 2025: 2.1597 (v0-grid 2.1605) vs team baseline 2.1807 vs zero 2.2261; 15.8% of 2025 slots have no prior history (p25 replacement -0.189)
- emit 2026: train 2021-2025 (202,931 poss, 314 players), fit_through 2025 | inner val 2025 -> lambda 68000 (inner_validation); v0-grid pick 5000
    stint_mae_walkforward on 2026: 1.9999 (v0-grid 2.0023) vs team baseline 2.0082 vs zero 2.0553; 19.9% of 2026 slots have no prior history (p25 replacement -0.148)

## 2. GATE 1 — emit-2025 block reproduces rapm_v0.csv
Emit season 2025 trains on 2021-2024, exactly build_rapm.py's TRAIN_SEASONS.
Same window + same lambdas + same estimator must give the same coefficients.
- joined 265 players; max |diff| on net_100_lam[500, 1000, 2000, 5000] = 0.000000 -> PASS

## 3. Contaminated vs walk-forward on identical observations

Registry run 4 withdrew the phrase *roster turnover does not decay like that*
and queued **a direct contaminated-vs-walk-forward comparison on identical
observations** under this experiment as the decisive test. This is it.

Per season: corr(possession-weighted team player-value differential, realized
margin). Same games, same weights, same replacement convention (each table's
own p25) — the ONLY thing that differs is which value table is joined.

*Read as a CONTAMINATION diagnostic, not a forecast. Weights come from
realized on-court possessions, so neither arm is a pregame feature and no
number here is a skill estimate. Per registry run 4 the leakage is already
established by DATA LINEAGE; this quantifies its size on matched data.*

The primary contrast is the FIXED-lambda column, because both arms then hold
lambda at 5,000 and the only difference left is the fit window. The two
selection arms vary lambda by season, so their cross-season shape mixes
shrinkage changes with the window change and is shown for completeness only.

| season | in v0 fit window | static rapm_v0 | **wf lam5000 (fixed)** | wf `net_100` (registered) | wf `net_100_v0grid` | rated share v0 | rated share wf |
|---|---|---|---|---|---|---|---|
| 2022 | YES | +0.527 | **+0.416** | +0.413 | +0.416 | 100.0% | 76.0% |
| 2023 | YES | +0.570 | **+0.461** | +0.433 | +0.461 | 100.0% | 83.1% |
| 2024 | YES | +0.561 | **+0.380** | +0.390 | +0.390 | 100.0% | 86.1% |
| 2025 | no | +0.400 | **+0.400** | +0.310 | +0.400 | 79.3% | 79.3% |
| 2026 | no | +0.207 | **+0.308** | +0.227 | +0.308 | 60.7% | 73.9% |

- On the fixed-lambda contrast the static arm breaks at its fit-window edge: +0.561 (2024, in-window) -> +0.400 -> +0.207, while the walk-forward arm runs +0.380 -> +0.400 -> +0.308 with no break at the boundary.
- CONTROLLED READ, 2025: the walk-forward window for 2025 IS 2021-2024, so at
  fixed lambda the two arms are the SAME table on the SAME player set — equal
  coverage, equal correlation, as the row shows. That row is a harness check,
  not evidence. 2026 is the clean comparison, and there walk-forward is higher
  on both correlation and coverage.
- CONFOUND, stated plainly: on 2022-2024 the arms do not have equal coverage.
  rapm_v0 rates ~100% of those slots precisely BECAUSE it was fit on them,
  while a walk-forward table has no value for a player with no prior history
  and falls back to p25. Lower coverage attenuates correlation on its own, so
  part of the 2022-2024 gap is coverage, not look-ahead.
- The registered arm declines across seasons partly because its selected
  lambda climbs (2,000 -> 47,000 -> 68,000). That is the shrinkage effect of
  section 5, NOT contamination — which is exactly why the fixed-lambda column
  is the one to read here.
- This diagnostic sizes the defect; it does not re-run any affected
  experiment. Re-running joint_differential_v1 and oracle_..._bracket_v2 on
  clean values is their own registered work, not this build's to claim.

## 4. Stability of consecutive emit seasons
Consecutive tables share all but one season of training data, so this r is
largely mechanical persistence — the operational number for a rating
re-shipped each season, NOT an independent-signal YoY.
- r(2022 vs 2023) = 0.880  (n=113 players >= 1000 poss both)
- r(2023 vs 2024) = 0.764  (n=151 players >= 1000 poss both)
- r(2024 vs 2025) = 0.771  (n=179 players >= 1000 poss both)
- r(2025 vs 2026) = 0.952  (n=198 players >= 1000 poss both)

## 5. Lambda protocol — registered default vs measured recommendation

The registration specifies the extended sweep re-selected per season, so it
drives `net_100`. Reporting the measurement rather than acting on it
unilaterally, because the registration is binding and acceptance belongs to
`asof_invariant_audit_v1`:

| season | registered lambda | v0-grid lambda | sd net_100 | sd v0grid | p25 repl | p25 repl v0grid |
|---|---|---|---|---|---|---|
| 2022 | 100,000 | 5,000 | 0.10 | 1.02 | -0.054 | -0.647 |
| 2023 | 33,000 | 5,000 | 0.37 | 1.28 | -0.194 | -0.732 |
| 2024 | 2,000 | 2,000 | 2.37 | 2.37 | -1.490 | -1.491 |
| 2025 | 47,000 | 5,000 | 0.40 | 1.59 | -0.189 | -0.890 |
| 2026 | 68,000 | 5,000 | 0.32 | 1.64 | -0.148 | -0.935 |

- The inner-validation curve is FLAT above ~5,000 (the 2023 fold reads 2.1742
  at every lambda from 5,000 to 47,000; folds separate in the 4th decimal).
  v0's tie-break rounds at 6 decimals so it never fires, and the argmin lands
  high by noise rather than at a real optimum.
- The extra shrinkage buys 0.0008-0.0024 stint MAE and costs the separation
  the table exists to provide: margin correlation falls and the p25
  replacement collapses toward zero (see the table above and section 3).
- RECOMMENDATION: amend the registration to v0's grid, or have consumers read
  `net_100_v0grid`. Both columns are equally uncontaminated — this is a
  shrinkage/utility question, never a leakage one.

## 6. Consumer audit (mandatory per the registration)

Every repo-root module that reads a fitted player-value table, its fit window,
the seasons it scored, and whether they intersect. The scan is programmatic so
a new consumer cannot be added without this audit noticing; verdicts are
curated from committed artifacts.

| consumer | experiment | regime | scored | in fit window | verdict |
|---|---|---|---|---|---|
| `build_rapm.py` | (none) | n/a | (none scored) | (none) | PRODUCER of the contaminated table |
| `build_rapm_v1.py` | (none) | n/a | (none scored) | (none) | CLEAN — no registry entry, no promotion claim |
| `build_rapm_walkforward.py` | build_rapm_walkforward_v1 | A | (none scored) | (none) | CLEAN — this script |
| `joint_differential.py` | joint_differential_v1 | A | 2024,2025,2026 | 2024 | CONTAMINATED — RECORDED FAIL |
| `oracle_bracket.py` | oracle_availability_bracket_v2 | C | 2024,2025,2026 | 2024 | CONTAMINATED — ERRATUM + RETRACTION ON LEDGER |

- **joint_differential.py** — d_rapm built from rapm_v0 net_100. Pooled +0.2439 contaminated vs +0.0219 on clean seasons — the apparent gain was 2024 leakage. Ablation: the differential reframing carries +0.004 clean.
- **oracle_bracket.py** — 2024 scored inside the fit window (207 of 627 games). Registered verdict was FAIL on gate1_pooled_improvement either way, so no promotion rests on it. Clean-season corrections (registry run 4): deployable v2 REVERSES +5.3%->-4.2% of market gap; achievable pregame ceiling FALLS 15.6%->12.6%; omniscient v4 rose 18.2%->36.3% but is regime-C diagnostic and must not headline.

- NOT consumers: feature_lab.py, interactions_lab.py, crossseason_screen.py, volume_heterogeneity.py (player_feature_screen_v1, player_feature_interactions_v1, player_vs_archetype_v1, player_feature_crossseason_v1, player_volume_heterogeneity_v1 — all regime A, all with *_delta_2024 primary metrics) validate on 2024 but read data/player_possession_features.parquet, NOT any RAPM table. Verified by repo-wide scan below: they do not appear. Clean with respect to THIS defect.

- Scope limit, stated: this scan covers repo-root `*.py` reading a RAPM table.
  The full multi-artifact blast radius (zone maps, calibration params, frozen
  baselines, EB shrinkage constants) is deliverable (A) of
  `asof_invariant_audit_v1`, not this build.

## 7. How to consume

```python
wf = pd.read_csv('data/rapm/rapm_walkforward.csv', dtype={'season': str})
meta = pd.read_csv('data/rapm/rapm_walkforward_seasons.csv', dtype={'season': str})
# join on BOTH keys - joining on player_id alone re-creates the defect
df = df.merge(wf[['season','player_id','net_100']], on=['season','player_id'],
              how='left')
# players with no prior history take that season's own p25, not a global one
repl = dict(zip(meta['season'], meta['replacement_net_100_p25']))
df['net_100'] = df['net_100'].fillna(df['season'].map(repl))
# cleanliness assertion the registration asks every consumer to make
assert (df['fit_through_season'] < df['season']).all()
```

- seasons 2022-2026 are emitted; 2021 has no prior data and is excluded.
- a game in season s only ever sees values fit on seasons <= s-1.
- 2022 carries the thin-history caveat (one training season, no inner split);
  `thin_history_caveat` is flagged in the season manifest.
- `minutes_2021_24` keeps its rapm_v0 name for join compatibility but holds
  THIS ROW's training-window minutes (the build_rapm_v1.py precedent).
- SCALE WARNING: `lambda_chosen` varies by season (that is what makes it
  walk-forward), and lambda sets shrinkage, so `net_100` is not on one scale
  across seasons. For pooled cross-season fits use a fixed-lambda column
  (`net_100_lam5000` is the closest analogue to rapm_v0's `net_100`) or
  standardize within season.

## Files
- data/rapm/rapm_walkforward.csv (1,177 rows, 5 seasons, 314 players)
- data/rapm/rapm_walkforward_seasons.csv (5 rows)
- experiments/rapm_walkforward/{consumer_audit,margin_corr_diagnostic,stint_eval_by_season}.csv
- NOT modified: data/rapm/rapm_v0.csv, build_rapm.py, experiments/registry.jsonl, leaderboards/

runtime 26s
