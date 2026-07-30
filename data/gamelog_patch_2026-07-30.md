# Gamelog patch 2026-07-30 -- two pbp-contradicted games

Source: BoxScoreTraditionalV3 refetched 2026-07-30T18:01:02+00:00 into `data/refresh_2026/traditional/` by `repair_gamelog_two_games.py`.
Cause: REBUILD_VALIDATION.md category `local_gamelog_pbp_disagreement` (local old-era season gamelogs contradicted the raw play-by-play; evidence in `data/masters/diff_drive_team_mismatches.csv`).
Rule: every patched value is the refetched boxscore value -- nothing derived from pbp, nothing imputed. pbp is the post-patch arbiter only.

## Patched cells

| file | game | team | player | column | old | new |
|---|---|---|---|---|---|---|
| wnba_gamelog_2023.parquet | 1022300092 | CON | Liz Dixon (1641700) | TO | 1.0 | 0.0 |
| wnba_gamelog_2023.parquet | 1022300092 | LVA | A'ja Wilson (1628932) | STL | 1.0 | 0.0 |
| wnba_gamelog_2022.parquet | 1022200107 | DAL | Marina Mabrey (1629497) | TO | 3.0 | 4.0 |

## Post-patch verification vs pbp

- 1022300092 LVA sum(STL) = 7, pbp 7: PASS (pbp stl=7)
- 1022300092 CON sum(TO) = 10, pbp 10: PASS (pbp player-credited TO=10 (game total 12 incl. 2 TEAM turnovers))
- 1022200107 DAL sum(TO) = 15, pbp 15: PASS (pbp player-credited TO=15 (game total 16 incl. 1 TEAM turnover))

## Backups

- data/backups/wnba_gamelog_2022.pre_patch_2026-07-30.parquet
- data/backups/wnba_gamelog_2023.pre_patch_2026-07-30.parquet
