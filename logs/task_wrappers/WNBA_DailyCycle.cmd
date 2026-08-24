@echo off
rem Overnight cycle: re-check the waiting studies, settle the paper bets, write the
rem plain-language brief. See ops/daily_cycle.py.
rem Runs AFTER WNBA_DailyRefresh (08:30 ET) so it sees the previous night's outcomes.
cd /d "C:\Users\jgallagher\wnba-betting-model"
"C:\Users\jgallagher\AppData\Local\Programs\Python\Python313\python.exe" "C:\Users\jgallagher\wnba-betting-model\ops\daily_cycle.py" >> "C:\Users\jgallagher\wnba-betting-model\logs\daily_cycle.log" 2>&1
exit /b %ERRORLEVEL%
