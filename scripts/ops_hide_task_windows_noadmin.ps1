<#
.SYNOPSIS
  Stop the WNBA scheduled tasks popping console windows -- WITHOUT administrator rights.

.WHY THIS APPROACH
  The textbook fix is to switch each task's principal to S4U so it runs in session 0 with no
  window. That needs admin, which is not available here: every Set-ScheduledTask -Principal
  returned "Access is denied".

  But only the PRINCIPAL is protected. Probing showed that changing a task's ACTION, TRIGGER
  and SETTINGS is all permitted for this user. So rather than move the task out of the desktop
  session, this changes WHAT IT LAUNCHES:

      before:  python.exe  "C:\...\odds_capture_daily.py"      <- console host, window appears
      after :  wscript.exe //nologo run_hidden.vbs wrapper.cmd  <- windowless host, no window

  wscript.exe has no console of its own, and run_hidden.vbs starts the real command with
  window style 0 and waits for it, propagating the exit code so "Last Run Result" stays a
  real health signal.

  Each task gets a small generated wrapper .cmd holding its ORIGINAL command verbatim,
  including its working directory. That avoids re-quoting command lines through two layers of
  argument parsing, which is where this kind of change usually breaks.

.WHAT ELSE IT FIXES
  A window that exists can be closed, and closing one sends Ctrl+C to the capture process and
  kills that cycle -- roughly 28 cycles had been destroyed that way, 10 of them from sxbet on
  a single day. A window that never exists cannot be closed.

.RUN
      powershell -NoProfile -ExecutionPolicy Bypass -File "<this file>"

  -WhatIfOnly    show every change, touch nothing
  -Only <name>   convert a single task first (recommended for the first run)
  -Undo          restore every original action from the backup
  -WithCadence   also raise WNBA_OddsCapture from hourly to 5-minute (costs ~288 credits/day)
#>
[CmdletBinding()]
param(
    [switch]$Undo,
    [switch]$WhatIfOnly,
    [switch]$WithCadence,
    [string]$Only,
    [string]$CadenceInterval = 'PT5M',
    [string]$CadenceDuration = 'PT8H',
    [string]$WrapperDir = 'C:\Users\jgallagher\wnba-betting-model\logs\task_wrappers',
    [string]$BackupFile = 'C:\Users\jgallagher\wnba-betting-model\logs\wnba_task_actions_backup.json'
)

$ErrorActionPreference = 'Stop'
$VbsPath = Join-Path $PSScriptRoot 'run_hidden.vbs'
$WScript = 'C:\Windows\System32\wscript.exe'
$CadenceTask = 'WNBA_OddsCapture'

if (-not (Test-Path $VbsPath)) { throw "run_hidden.vbs not found beside this script: $VbsPath" }
if (-not (Test-Path $WScript)) { throw "wscript.exe not found at $WScript" }

function Get-WnbaTasks {
    $t = Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' }
    if ($Only) { $t = $t | Where-Object { $_.TaskName -eq $Only } }
    $t
}

# ------------------------------------------------------------------ UNDO
if ($Undo) {
    if (-not (Test-Path $BackupFile)) { Write-Host "  No backup at $BackupFile" -ForegroundColor Red; exit 1 }
    $backup = Get-Content $BackupFile -Raw | ConvertFrom-Json
    foreach ($b in $backup) {
        if ($Only -and $b.TaskName -ne $Only) { continue }
        try {
            $act = if ([string]::IsNullOrEmpty($b.WorkingDirectory)) {
                New-ScheduledTaskAction -Execute $b.Execute -Argument $b.Arguments
            } else {
                New-ScheduledTaskAction -Execute $b.Execute -Argument $b.Arguments -WorkingDirectory $b.WorkingDirectory
            }
            Set-ScheduledTask -TaskName $b.TaskName -Action $act | Out-Null
            Write-Host ("  restored  {0}" -f $b.TaskName) -ForegroundColor Yellow
        } catch {
            Write-Host ("  FAILED    {0}  {1}" -f $b.TaskName, $_.Exception.Message) -ForegroundColor Red
        }
    }
    exit 0
}

$tasks = Get-WnbaTasks
if (-not $tasks) { Write-Host "  No matching WNBA tasks found."; exit 1 }

# ------------------------------------------------------------------ BACKUP (never overwrite)
if (-not (Test-Path $WrapperDir)) { New-Item -ItemType Directory -Force $WrapperDir | Out-Null }
if (-not (Test-Path $BackupFile) -and -not $WhatIfOnly) {
    $all = Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' } | ForEach-Object {
        $a = $_.Actions | Select-Object -First 1
        [PSCustomObject]@{
            TaskName         = $_.TaskName
            Execute          = $a.Execute
            Arguments        = $a.Arguments
            WorkingDirectory = $a.WorkingDirectory
        }
    }
    $all | ConvertTo-Json -Depth 4 | Out-File -FilePath $BackupFile -Encoding utf8
    Write-Host "  original actions backed up: $BackupFile" -ForegroundColor Green
} elseif (Test-Path $BackupFile) {
    Write-Host "  backup already exists (kept as-is): $BackupFile" -ForegroundColor DarkGray
}

# ------------------------------------------------------------------ CONVERT
Write-Host ""
Write-Host "  MAKING THE TASKS WINDOWLESS" -ForegroundColor Cyan
foreach ($t in $tasks) {
    $n = $t.TaskName
    $a = $t.Actions | Select-Object -First 1

    if ($a.Execute -ieq $WScript) {
        Write-Host ("     already   {0,-28} windowless" -f $n) -ForegroundColor DarkGray
        continue
    }

    # Build a wrapper .cmd holding the ORIGINAL command verbatim.
    $wrapper = Join-Path $WrapperDir ("{0}.cmd" -f ($n -replace '[^\w\.-]', '_'))
    $lines = @(
        '@echo off',
        'rem AUTO-GENERATED by ops_hide_task_windows_noadmin.ps1 -- do not edit by hand.',
        ("rem Original action for scheduled task: {0}" -f $n),
        'rem Restore the task with:  ops_hide_task_windows_noadmin.ps1 -Undo'
    )
    if (-not [string]::IsNullOrEmpty($a.WorkingDirectory)) {
        $lines += ('cd /d "{0}"' -f $a.WorkingDirectory.Trim('"'))
    }
    $exe = $a.Execute.Trim('"')
    if ([string]::IsNullOrEmpty($a.Arguments)) {
        $lines += ('"{0}"' -f $exe)
    } else {
        $lines += ('"{0}" {1}' -f $exe, $a.Arguments)
    }
    $lines += 'exit /b %ERRORLEVEL%'

    $newArgs = ('//nologo "{0}" "{1}"' -f $VbsPath, $wrapper)

    if ($WhatIfOnly) {
        Write-Host ("     WOULD FIX {0}" -f $n)
        Write-Host ("        was: {0} {1}" -f $a.Execute, $a.Arguments)
        Write-Host ("        now: {0} {1}" -f $WScript, $newArgs)
        continue
    }

    try {
        $lines -join "`r`n" | Out-File -FilePath $wrapper -Encoding ascii
        $act = New-ScheduledTaskAction -Execute $WScript -Argument $newArgs
        Set-ScheduledTask -TaskName $n -Action $act | Out-Null
        Write-Host ("     fixed     {0,-28} no window" -f $n) -ForegroundColor Green
    } catch {
        Write-Host ("     FAILED    {0,-28} {1}" -f $n, $_.Exception.Message) -ForegroundColor Red
    }
}

# ------------------------------------------------------------------ CADENCE (opt-in)
if ($WithCadence -and -not $Only) {
    Write-Host ""
    Write-Host "  RAISING ODDS-CAPTURE CADENCE" -ForegroundColor Cyan
    $oc = Get-ScheduledTask | Where-Object { $_.TaskName -eq $CadenceTask }
    if ($oc) {
        $cur = $oc.Triggers | Select-Object -First 1
        Write-Host ("     current   {0} for {1}" -f $cur.Repetition.Interval, $cur.Repetition.Duration)
        if ($WhatIfOnly) {
            Write-Host ("     WOULD SET {0} for {1}" -f $CadenceInterval, $CadenceDuration)
        } else {
            try {
                $trg = $oc.Triggers
                $trg[0].Repetition.Interval = $CadenceInterval
                $trg[0].Repetition.Duration = $CadenceDuration
                Set-ScheduledTask -TaskName $CadenceTask -Trigger $trg | Out-Null
                $now = (Get-ScheduledTask -TaskName $CadenceTask).Triggers | Select-Object -First 1
                Write-Host ("     now       {0} for {1}" -f $now.Repetition.Interval, $now.Repetition.Duration) -ForegroundColor Green
            } catch {
                Write-Host ("     FAILED    {0}" -f $_.Exception.Message) -ForegroundColor Red
            }
        }
    }
}

# ------------------------------------------------------------------ RESULT
Write-Host ""
Write-Host "  RESULT" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' } | ForEach-Object {
    $a = $_.Actions | Select-Object -First 1
    $tr = $_.Triggers | Select-Object -First 1
    [PSCustomObject]@{
        Task   = $_.TaskName
        Window = if ($a.Execute -ieq $WScript) { 'none' } else { 'VISIBLE' }
        Repeat = if ($tr) { [string]$tr.Repetition.Interval } else { '' }
        Last   = $_.TaskName | ForEach-Object { (Get-ScheduledTaskInfo -TaskName $_).LastTaskResult }
    }
} | Format-Table -AutoSize

Write-Host "  Undo:  ops_hide_task_windows_noadmin.ps1 -Undo"
Write-Host ""
