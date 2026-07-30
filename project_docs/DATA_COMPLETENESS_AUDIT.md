# Dataset Completeness Audit

*July 29, 2026 · sources: GitHub `jungull/wnba-betting-model` (public clone, last substantive push Jul 2 2025 + one Aug 28 2025 commit) and Google Drive masters (exported Jul 15 2025)*

## What exists, and where the best copy lives

| Dataset | Best copy | Coverage | Status |
|---|---|---|---|
| Player box-score gamelogs | repo `data/wnba_gamelog_*.parquet` | 2021–2025 (through Jul 3 2025), 996 games | ✅ matches official schedule incl. 2022–24 postseasons |
| Play-by-play (per game) | repo `data/playbyplay/` — 996 files | same 996 games, every season | ✅ complete for covered span — **RAPM-ready** |
| Possession features | repo `player_possession_features.parquet` | 17,335 player-games, 996 games | ✅ |
| Misc/advanced player stats (paint, PFD, fastbreak, 2nd-chance) | **Drive only** — `master_player.csv` / `master_all.csv` | 2021–22, 2024–25 good | ⚠️ **2023 is broken everywhere** (480/520 team-games zero). Repo's `*_with_misc_stats.parquet` are mislabeled — they contain **no** misc columns in any season |
| Team gamelogs (cleaned) | Drive `master_team_cleaned.csv` | 2021–Jul 2025, 2,132 rows | ✅ clean (verified: 0 box-score identity violations) |
| Betting odds | Drive `master_odds.csv` + raw JSONs | 2022: 181/239 games · 2023: full · 2024: full · 2025: through Jul 4 | ⚠️ **2021: zero odds**; 2022 76%; nothing after Jul 4 2025 |
| Tier 2 champion code + results (`modeling_v2`) | **nowhere recoverable** | repo has only the tier-0 CSV | ❌ the Tier 1 rebuild, Tier 2 RF 9.81 champion, bake-off recipes, and the **repaired 2023 granular data** were never pushed and aren't in Drive — check your machine |

## The gap list (in priority order)

1. **2023 misc/advanced stats — broken in every surviving copy.** Blocks the paint/fouls-drawn channels for a full training season. Fix: re-fetch per-game from stats.wnba.com (`boxscoremiscv2` + advanced endpoints) — the acquisition scripts already exist in `scripts/01_acquisition/`. ~260 games ≈ an hour with polite rate limiting.
2. **Everything after July 3, 2025.** Rest of 2025 regular season + playoffs (~190 games) and the entire 2026 season to date (15 teams now, ~150+ games played): gamelogs, misc stats, play-by-play. Same scripts, larger run. Note: 2026 brings Toronto/Portland expansion — team-ID mappings need two additions.
3. **Odds after July 4, 2025.** Free Odds API tier can't backfill (10× credit cost ≈ 8 historical snapshots/month). Options: (a) one paid month to backfill 2025-26 history in one sweep, then drop to free-tier daily capture; (b) accept the gap and start free-tier daily capture now — benchmarks resume from today. 2021 odds and the 2022 gaps are likely gone for good (acceptable: those are benchmark years, not feature inputs).
4. **2021 postseason** box scores + PBP (~15 games): one small fetch, same scripts.
5. **`modeling_v2` recovery.** If the folder still exists on your machine, push it — it holds the repaired 2023 data and the 9.81 champion's bake-off recipes. If it's gone, nothing is truly lost: the channel-experiment architecture already outperforms it, and the recipes are re-derivable overnight.

## Execution note

stats.wnba.com is blocked from this cloud sandbox, so collection runs must execute on your machine (I can prep a single runnable script + requirements for it, and process the outputs back here), or any environment with open internet. The odds capture (api.the-odds-api.com) has the same constraint. Also: rotate the two Odds API keys hardcoded in the now-public repo (`fetch_historical_wnba_spreads.py`, `wnba-odds-aggregator/.env`, `historical_odds_api_fetcher.py`) — lapsed or not, keys shouldn't sit in a public repo.
