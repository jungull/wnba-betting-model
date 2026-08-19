@echo off
rem ---------------------------------------------------------------------------
rem  Regenerate the WNBA opportunity board from the newest capture snapshot.
rem
rem  The board was previously only as fresh as the last time someone ran
rem  render.py by hand, which makes a "live" dashboard a manual snapshot. This
rem  runs on a schedule so board.html always reflects the most recent capture.
rem
rem  Launched WINDOWLESS via scripts\run_hidden.vbs -- see D148. It writes to a
rem  log rather than a console, so nothing appears on screen and nothing can be
rem  closed mid-run.
rem
rem  Reads the odds tape read-only. Places nothing, contacts no venue, holds no
rem  credential. Execution mode is fixed at SHADOW inside the board itself.
rem ---------------------------------------------------------------------------
setlocal
set NODE=C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M28_OPPORTUNITY_BOARD
set PY=C:\Users\jgallagher\AppData\Local\Programs\Python\Python313\python.exe
set LOGDIR=C:\Users\jgallagher\wnba-betting-model\logs\board

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%NODE%" || exit /b 90

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set STAMP=%%i
set OUT=%LOGDIR%\board_%STAMP%.log

echo ==== %DATE% %TIME% ==== >> "%OUT%"
"%PY%" render.py >> "%OUT%" 2>&1
set RC=%ERRORLEVEL%
echo [render] exit=%RC% >> "%OUT%"
exit /b %RC%
