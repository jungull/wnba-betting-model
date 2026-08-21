@echo off
rem WNBA market capture ladder tick - user-authorized activation (D028, 2026-08-06).
rem Runs one scheduler tick: due ladder rungs + injury/news burst watch.
set MARKET_LADDER_ENABLED=1
rem Per-book polling enabled on direct user instruction 2026-08-19 (D147).
rem Bounded by M27's own declared scope: 3 books, 60-min pre-tip window, 300s
rem interval, kill switch below. Affordability measured in M29/D145: +144 credits/day
rem at the realistic mid, leaving ~144 days of runway against 31,622 remaining.
rem To disable: set this to 0 or delete the line.
set MARKET_PER_BOOK_POLLING_ENABLED=1
cd /d C:\Users\jgallagher\wnba-betting-model
if not exist logs\market_ladder mkdir logs\market_ladder
python market_capture_run.py >> logs\market_ladder\ladder_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
