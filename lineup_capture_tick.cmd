@echo off
rem WNBA projected-lineup capture tick. One fetch of RotoWire's public WNBA lineups
rem page per invocation; schtasks provides the cadence.
rem
rem WHY IT RUNS REPEATEDLY RATHER THAN ONCE A DAY. The value is in the REVISIONS.
rem RotoWire posts an expected lineup 24-30 hours out and edits it through gameday,
rem and M39 s02 found half of all Out designations break inside 90 minutes of tip.
rem A single daily snapshot would record the stale version and miss the news; the
rem file is append-only so each revision lands as a new row and a later analysis can
rem ask honestly what we held at a given hour.
rem
rem POLITE BY CONSTRUCTION: one public page per tick, honest User-Agent, no login,
rem no disallowed path. Exits non-zero on a fetch failure or a zero-row parse.
cd /d C:\Users\jgallagher\wnba-betting-model
if not exist logs\lineup_capture mkdir logs\lineup_capture
python ops\lineup_capture.py >> logs\lineup_capture\tick_%date:~-4%%date:~4,2%%date:~7,2%.log 2>&1
