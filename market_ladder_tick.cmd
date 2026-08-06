@echo off
rem WNBA market capture ladder tick - user-authorized activation (D028, 2026-08-06).
rem Runs one scheduler tick: due ladder rungs + injury/news burst watch.
set MARKET_LADDER_ENABLED=1
cd /d C:\Users\jgallagher\wnba-betting-model
if not exist logs\market_ladder mkdir logs\market_ladder
python market_capture_run.py >> logs\market_ladder\ladder_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
