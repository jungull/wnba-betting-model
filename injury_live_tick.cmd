@echo off
rem WNBA official injury-report live capture tick (D033 track; D048 real-browser
rem client authorized by the user 2026-08-07). One 15-minute cycle per invocation;
rem schtasks provides the cadence.
rem Store lives in the DATA worktree (data\injury_official_live) via
rem INJURY_LIVE_DATA_ROOT so the program worktree stays quiescent for pushes;
rem checkpoint-committed on data-refresh-2026 per D044. Seeded 2026-08-07 with the
rem recovery snapshot (28 docs / 552 rows) so hash-dedup and supersession carry over.
rem NOTE: the D048 fallback launches a REAL HEADED Chromium (off-screen window) -
rem it needs an interactive desktop session. While logged out the cycle logs honest
rem NETWORK_UNAVAILABLE rows and the next logged-in cycle backfills the gap from
rem the discovery API's same-day listing.
set INJURY_LIVE_DATA_ROOT=C:\Users\jgallagher\wnba-betting-model\data\injury_official_live
cd /d C:\Users\jgallagher\wnba-betting-model
if not exist logs\injury_live mkdir logs\injury_live
python .claude\worktrees\player-model-program\experiments\market_program\INJURY_OFFICIAL\live\capture_injury_live.py >> logs\injury_live\tick_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
