@echo off
rem Capture health watchdog. See ops/capture_health.py and decision D180.
rem Exits non-zero when the tape has no pulse, so the scheduler records the
rem failure in LastTaskResult -- which is the field that went unread for 1.6
rem hours during the 2026-08-23 outage.
cd /d "C:\Users\jgallagher\wnba-betting-model"
"C:\Users\jgallagher\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\jgallagher\wnba-betting-model\ops\capture_health.py" >> "C:\Users\jgallagher\wnba-betting-model\logs\capture_health.log" 2>&1
exit /b %ERRORLEVEL%
