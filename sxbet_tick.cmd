@echo off
rem SX Bet WNBA public-API capture tick - user-authorized activation (D035, 2026-08-06;
rem scheduled under D044/worklist by the coordinator, 2026-08-07).
rem One capture cycle per invocation (no --loop); schtasks provides the 5-minute cadence.
rem Outputs land in the DATA worktree (this repo root) so the program worktree stays
rem quiescent for pushes; data is checkpoint-committed on data-refresh-2026 per D044.
cd /d C:\Users\jgallagher\wnba-betting-model
if not exist data\sxbet_capture mkdir data\sxbet_capture
if not exist data\sxbet_capture\state mkdir data\sxbet_capture\state
if not exist logs\sxbet mkdir logs\sxbet
python .claude\worktrees\player-model-program\experiments\market_program\EXCHANGE_CAPTURE\sxbet\capture_sxbet.py --data-dir data\sxbet_capture --state-path data\sxbet_capture\state\sxbet_state.json --log-path logs\sxbet\poll_log.jsonl >> logs\sxbet\tick_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
