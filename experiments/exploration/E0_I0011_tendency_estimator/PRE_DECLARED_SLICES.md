# Pre-declared slices for E0 I0011 (written BEFORE any slice result was computed)

Written after `build_frame.py` ran and before `score.py` was written or run.
All slices listed here will be reported in NOTES.md, including the boring ones.
No slice may be added after seeing results; if one is, it will be labelled POST-HOC.

Selection/scoring split (also pre-declared, never revised):
- SELECT on seasons **2021, 2022** (hyperparameter choice only).
- SCORE on seasons **2023, 2024**, reported separately and pooled.
- Nothing computed on 2023/2024 may inform any selection. The frozen home
  multipliers and the mean-possessions normaliser were fit on 2021-2022 only.

Eval universe: player-games with `minutes > 0` and `n_prior >= 3` prior played
games in the same season (so every estimator family is defined on the same rows).

## Slice families

- **S1 role — starter_flag**: `starter_flag == 1` vs `starter_flag == 0`.
- **S2 role — minutes tier**, on the strictly-prior season-to-date mean minutes
  (`std_minutes`): `<15`, `15-25`, `>=25`.
- **S3 role — usage tier**, on strictly-prior season-to-date mean
  `usage_percentage` (`std_usage`): terciles cut on the SELECTION seasons only.
- **S4 history depth**: `n_prior` in `3-7` vs `8-19` vs `>=20`.
  (Plus a separate early-season report on `n_prior` in `1-2`, outside the main
  eval universe, for the prior-season-shrinkage design question.)
- **S5 season_type**: `Regular Season` vs `Playoffs`.

Position is NOT used as a slice: `position` is empty on 55% of partition rows
(11,762 of 21,462) and the non-empty values are suspiciously exactly
3880/3880/1940 F/G/C, so it is not trustworthy for role slicing.

## Negative controls (pre-declared)

- **NEG_reversed**: same prior history, recency weights inverted (oldest game
  weighted most). Should be worse than the tuned estimator.
- **NEG_other_player**: a different, randomly assigned player-season's
  season-to-date mean, aligned by game index (seed 20260807). Should rank LAST.
- **NEG_league_const**: the league-wide selection-season mean of the target,
  constant for everyone. Should rank near-last.

If the harness does not rank NEG_other_player last, no other number in this
screen means anything.
