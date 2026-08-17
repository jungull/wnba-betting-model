# REGIME_BOUNDARY — can this program validate forward?

E1_I0057, 2026-08-17. Verified on bytes from
`data/masters/master_player.parquet` (33,712 rows, 1,495 games).
Scripts: `s03_regime_and_staleness.py`, `s04_regime_detail.py`, `s05_regime_material.py`,
`s06_era_columns.py`.

---

## Short answer

**Yes — and the record on this is more alarming than the evidence supports.**

D095's structural fact is **confirmed and in fact understated**: the separation is perfect, not 92%.
But the *harm* it was assumed to imply is not present in the columns the feature library actually
consumes. The real constraint on forward validation is **raw play-by-play, which is 0% present for
2026**, not the gamelog era.

And a fix better than any of this already exists in the repository: a **market yardstick that spans
the boundary** — see §5.

---

## 1. The separation, verified

`era` counts by season, all rows:

| season | gamelog_old | gamelog_new | v3 |
|---|---|---|---|
| 2021 | 3,565 | 320 | 690 |
| 2022 | 4,096 | 423 | 742 |
| 2023 | 4,544 | 354 | 851 |
| 2024 | 4,515 | 399 | 963 |
| 2025 | **0** | 5,853 | 1,218 |
| 2026 | **0** | 4,259 | 920 |

Now on the population the screens actually fit — **regular season, played rows (minutes > 0)**:

| partition | n | composition |
|---|---|---|
| exploration (≤2024) | 16,717 | **100.00% `gamelog_old`** |
| confirmation (≥2025) | 9,665 | **100.00% `gamelog_new`**, 0 `gamelog_old` rows |

The partition is **perfectly separating**. The "92%" in the record is the figure for played rows
across all season types (91.79%); on the regular-season played frame it is 100%.

## 2. What `era` actually is — read the construction, not the label

`era` is a **source-schema label**, not a measurement-quality label. `wnba_schema.py:320-334`
assigns it by column sniffing: `START_POSITION` present ⇒ `gamelog_old`; `SEASON_ID`+`GAME_ID`+`MIN`
⇒ `gamelog_new`; `personId`+`gameId` ⇒ `v3`. `build_masters.py:473` then sets
`mp["era"] = mp["era_gl"].fillna("v3")` — so `v3` on the player master means *no gamelog row at all*
(these are the DNP/inactive skeleton rows), which is why every rate column is null on them.

`wnba_schema.py:131` names the two consequences the label was expected to carry:

> gamelog_new frames cannot yield starter_flag or dnp_reason (structurally absent); minutes there
> are endpoint-rounded ints.

**Both were checked and neither survives into the master.**

| field | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| `starter_flag` non-null | 100% | 100% | 100% | 100% | 100% | 100% |
| `starter_flag == 1` share | 45.68% | 45.43% | 45.23% | 44.58% | 43.84% | 41.51% |
| `dnp_reason` populated on DNP rows | 100% | 100% | 99.88% | 99.69% | 99.92% | 99.89% |
| played rows with integer minutes | 2.03% | 1.77% | 2.59% | 2.61% | 1.78% | 1.88% |
| `minutes_source` on played rows | 100% `misc` | `misc` | `misc` | `misc` | `misc` | `misc` |

`minutes` comes from the **V3 `misc` boxscore on 100% of played rows in all six seasons**, so
minutes are sub-minute precise on both sides of the boundary; the endpoint-rounding warning applies
to a path the master never takes. `starter_flag` and `dnp_reason` are supplied by the same V3 layer.
**The V3 misc/advanced boxscore bridges the eras.** That is why the label separates perfectly while
the data does not.

## 3. The one place the boundary IS material — and it is not consumed

`scripts/s06_era_columns.py` compared null rates on regular-season played rows across the partition.
Exactly **three** columns differ by more than 2 percentage points:

| column | exploration null% | confirmation null% |
|---|---|---|
| `fg_pct` | 0.00 | 6.28 |
| `fg3_pct` | 0.00 | 24.80 |
| `ft_pct` | 0.00 | **45.11** |

This is a **0/0 encoding change**, not a measurement change: `gamelog_old` wrote `0.0` for a
zero-attempt row, `gamelog_new` writes NULL. The 45.11% matches the known ~46.4% zero-FTA rate.

It produces the largest apparent shifts in the whole frame — `ft_pct` **d = +0.805 sd**,
`fg3_pct` +0.296, `fg_pct` +0.122 — which are **entirely artefacts of dropping the zeros from the
mean**, not changes in shooting. (Ratings shift ~+0.14 sd; every genuine count channel moves
< 0.08 sd: `minutes` −0.053, `pts` well under, `reb` −0.053, `possessions` −0.062.)

**Checked, and this does not propagate:** `features/` never reads a vendor pct column. Every ratio
in the feature library is computed from its own numerator and denominator (e.g.
`matchup_overlay.py:120` `g["fg_pct"] = g["fgm"] / g["fga"]`). The only hit outside builders is a
team-level rename in `daily_forecast.py:288`. A screen that reaches for `ft_pct` directly would be
bitten; none currently does.

## 4. The real forward-validation constraint: raw play-by-play

| season | games with a raw pbp file | total games | % |
|---|---|---|---|
| 2021 | 192 | 209 | 91.9 |
| 2022 | 216 | 239 | 90.4 |
| 2023 | 240 | 260 | 92.3 |
| 2024 | 240 | 262 | 91.6 |
| 2025 | 108 | 310 | 34.8 |
| **2026** | **0** | **215** | **0.0** |

**Any lead built on raw play-by-play is constructible in exploration and cannot be confirmed on
2026.** This is the constraint that actually bites, and it is a data-acquisition problem, not a
measurement-regime problem.

`data/possessions/possessions.parquet` does **not** share the gap — 237,567 possessions over
1,489 games, 100% of 2021–2025 and 209/215 (97.2%) of 2026. It remains without a manifest and its
coverage exceeds the raw pbp it was presumably derived from; that provenance question is still open
and a screen relying on it must resolve it first.

## 5. What would fix forward validation — and it already exists

`data/props_capture/historical/master_props_historical.csv` carries a closing-ish **player points**
line, taken a median **1.16 hours before tip**, for:

| season | games with a line | total games | joined played player-game rows | market corr with realised pts | market MAE |
|---|---|---|---|---|---|
| 2024 (exploration) | **262 / 262** | 262 | 1,972 | 0.5439 | 4.929 |
| 2025 (confirmation) | **310 / 310** | 310 | 2,410 | 0.5380 | 4.977 |
| 2026 (confirmation) | 212 / 235 | 235 | 1,984 | 0.5765 | 4.923 |

*(The correlations and MAEs are descriptive of the market line. They are ILLUSTRATIVE ONLY and are
not a result about any model in this program.)*

This is a **single external yardstick measured on both sides of the partition, and it barely moves
across it.** A model scored against this line on 2024 and again on 2025/26 is compared to the same
opponent under the same conditions, which is exactly what an era change would otherwise destroy.
It converts "a failure to replicate at E2 would be uninterpretable" into an interpretable
comparison.

Coverage is the honest limit: the props market covers **79 / 104 / 130 distinct players** per
season and reaches only ~34% of master rows. It is a benchmark on the players a book will price —
which are also the only players worth betting.

## 6. Verdict

1. The exploration/confirmation regime boundary is **real and perfectly separating on the label**.
2. Its expected material consequences (`minutes` precision, `starter_flag`, `dnp_reason`) **do not
   occur** — the V3 misc boxscore bridges both sides.
3. Its one genuine consequence — null-encoding of `fg_pct`/`fg3_pct`/`ft_pct` — **does not reach the
   feature library**, but is a live trap for any future screen that reads a vendor pct column.
   *Recommended cheap fix: recompute those three columns in `build_masters.py` from
   numerator/denominator with an explicit zero-attempt convention, so the encoding is uniform.*
4. **Forward validation is possible today.** The blocker is not the era; it is raw play-by-play at
   0% for 2026, and a market benchmark spanning the boundary already exists and is unused.

## 7. What I could NOT determine

- Whether any *fitted artifact* (RAPM tables, zone maps, frozen alphas) carries era-specific
  structure that would break at E2. I checked the master frame's columns, not the artifacts.
- Whether the 6 missing 2026 games in `possessions.parquet` are systematic.
- The provenance of `possessions.parquet` — still unmanifested, coverage still exceeds its apparent
  source. Unresolved, as it was before this audit.
