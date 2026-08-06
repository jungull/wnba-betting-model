@echo off
REM ===================================================================
REM  WNBA prospective pair -- scheduled entry point.
REM
REM  Runs the BASE forecast job, then mirrors it into the W2-C1 arm log,
REM  then writes a coverage receipt. All three steps are idempotent, so
REM  this is safe to fire every 15 minutes: each (game, cutoff) is
REM  written at most once and re-fires are no-ops.
REM
REM  Firing every 15 min is what covers all four registered decision
REM  times (T-24h, T-8h, T-90m, T-30m) without four separate schedules.
REM  A once-a-day task CANNOT satisfy the prediction contract.
REM
REM  Exit code is non-zero if either job fails, so Task Scheduler's
REM  "Last Run Result" is a real health signal rather than always 0.
REM ===================================================================
setlocal
set PY=C:\Users\jgallagher\AppData\Local\Programs\Python\Python313\python.exe
set REPO=C:\Users\jgallagher\wnba-betting-model
set LOGDIR=%REPO%\forecasts\runner_logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
REM %DATE% formatting is locale-dependent; ask PowerShell so the log name is stable
REM whatever regional settings the scheduler runs under.
set STAMP=unknown
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set STAMP=%%i
set OUT=%LOGDIR%\pair_%STAMP%.log

cd /d "%REPO%" || exit /b 90
echo ==== %DATE% %TIME% ==== >> "%OUT%"

REM 1. base structural forecast -> OFFICIAL chain (freeze-v0, John-approved).
REM    GATED: daily_forecast.py de-duplicates on the exact cutoff timestamp, so an
REM    ungated 15-minute cadence would append ~288 near-identical records per night
REM    to an append-only chain. The gate fires it at most once per (game, cutoff).
set RC_BASE=0
"%PY%" prospective_pair\should_run_base.py >> "%OUT%" 2>&1
if %ERRORLEVEL%==0 (
    "%PY%" daily_forecast.py --live >> "%OUT%" 2>&1
    set RC_BASE=%ERRORLEVEL%
) else (
    echo [base] skipped - no unserved obligation in its lead window >> "%OUT%"
)
echo [base] exit=%RC_BASE% >> "%OUT%"

REM 2. mirror into the W2-C1 companion arm log (never touches the official chain)
"%PY%" prospective_pair\run_prospective.py >> "%OUT%" 2>&1
set RC_ARM=%ERRORLEVEL%
echo [arm] exit=%RC_ARM% >> "%OUT%"

REM 3. coverage receipt
"%PY%" prospective_pair\coverage_audit.py >> "%OUT%" 2>&1
set RC_AUD=%ERRORLEVEL%
echo [audit] exit=%RC_AUD% >> "%OUT%"

if not "%RC_BASE%"=="0" exit /b %RC_BASE%
if not "%RC_ARM%"=="0" exit /b %RC_ARM%
if not "%RC_AUD%"=="0" exit /b %RC_AUD%
exit /b 0
