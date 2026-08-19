<#
.SYNOPSIS
  Stop the WNBA scheduled tasks popping console windows, and raise odds-capture cadence.

.WHY
  Two separate problems, one elevated fix:

  1. POPUP WINDOWS. Every WNBA task runs with LogonType = Interactive, which runs it inside
     your desktop session and therefore shows a console window. Switching to S4U ("run whether
     the user is logged on or not", no stored password) runs them in session 0 -- no window,
     ever. Nothing else about the tasks changes: same user, same privilege level, same command.

     ONE TASK IS DELIBERATELY LEFT ALONE. WNBA_InjuryLive launches a REAL HEADED Chromium via
     Playwright and its own wrapper says it "needs an interactive desktop session". Converting
     it would leave NETWORK_UNAVAILABLE rows instead of injury reports. It is the only script
     in the repo that imports Playwright, verified 2026-08-19.

  2. HOURLY ODDS CAPTURE. WNBA_OddsCapture repeats every PT1H. That hourly grid is why the
     opportunity board cannot claim any arbitrage is still takeable -- a price seen on an
     hourly grid describes some moment in the last hour. This raises it to 5-minute capture
     across an 8-hour evening window.

     COST, measured in M29/D145, not assumed: 5-minute capture costs ~3 credits/call, so
     8h/day = 96 calls = ~288 credits/day. Against 31,622 credits remaining and 75/day of
     existing burn, that leaves roughly 87 days of runway -- past an October season end.
     Widen the window at your own cost: 12h/day is ~432/day and ~62 days.

.HOW TO RUN
  Right-click Windows Terminal or PowerShell -> "Run as administrator", then:

      & "C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\scripts\ops_fix_task_windows_and_cadence.ps1"

  To preview without changing anything:   -WhatIfOnly
  To undo everything:                     -Undo
  To hide windows but NOT touch cadence:  -SkipCadence

.NOTES
  Writes a fresh backup of every task principal and trigger before changing anything.
#>
[CmdletBinding()]
param(
    [switch]$Undo,
    [switch]$WhatIfOnly,
    [switch]$SkipCadence,
    [string]$CadenceInterval = 'PT5M',
    [string]$CadenceDuration = 'PT8H',
    [string]$CadenceStartTime = '15:00',
    [string]$BackupDir = 'C:\Users\jgallagher\wnba-betting-model\logs'
)

$ErrorActionPreference = 'Stop'

# The only task that must keep an interactive desktop.
$KEEP_INTERACTIVE = @('WNBA_InjuryLive')
$CADENCE_TASK = 'WNBA_OddsCapture'
$BackupFile = Join-Path $BackupDir 'wnba_task_backup.json'

function Test-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Elevated)) {
    Write-Host ""
    Write-Host "  NOT ELEVATED." -ForegroundColor Red
    Write-Host "  Windows refuses to modify tasks in the root task folder without admin rights,"
    Write-Host "  which is why this could not be done for you automatically."
    Write-Host ""
    Write-Host "  Close this, reopen PowerShell with 'Run as administrator', and run the same"
    Write-Host "  command again."
    Write-Host ""
    exit 1
}

$tasks = Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' }
if (-not $tasks) { Write-Host "  No WNBA tasks found."; exit 1 }

# ---------------------------------------------------------------- UNDO
if ($Undo) {
    if (-not (Test-Path $BackupFile)) {
        Write-Host "  No backup at $BackupFile -- nothing to restore." -ForegroundColor Red
        exit 1
    }
    $backup = Get-Content $BackupFile -Raw | ConvertFrom-Json
    foreach ($b in $backup) {
        try {
            $p = New-ScheduledTaskPrincipal -UserId $b.UserId -LogonType $b.LogonType -RunLevel $b.RunLevel
            Set-ScheduledTask -TaskName $b.TaskName -Principal $p | Out-Null
            Write-Host ("  restored  {0,-28} -> {1}" -f $b.TaskName, $b.LogonType) -ForegroundColor Yellow
        } catch {
            Write-Host ("  FAILED    {0,-28} {1}" -f $b.TaskName, $_.Exception.Message) -ForegroundColor Red
        }
    }
    if ($backup | Where-Object { $_.TaskName -eq $CADENCE_TASK -and $_.RepetitionInterval }) {
        $b = $backup | Where-Object { $_.TaskName -eq $CADENCE_TASK }
        Write-Host ""
        Write-Host ("  NOTE: {0} cadence was {1}/{2}. Restore it by hand in Task Scheduler if" -f `
                    $CADENCE_TASK, $b.RepetitionInterval, $b.RepetitionDuration)
        Write-Host "        this script changed it -- trigger restore is not automated."
    }
    exit 0
}

# ---------------------------------------------------------------- BACKUP
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Force $BackupDir | Out-Null }
$snapshot = $tasks | ForEach-Object {
    $t = $_.Triggers | Select-Object -First 1
    [PSCustomObject]@{
        TaskName            = $_.TaskName
        UserId              = $_.Principal.UserId
        LogonType           = [string]$_.Principal.LogonType
        RunLevel            = [string]$_.Principal.RunLevel
        RepetitionInterval  = if ($t) { [string]$t.Repetition.Interval } else { $null }
        RepetitionDuration  = if ($t) { [string]$t.Repetition.Duration } else { $null }
        StartBoundary       = if ($t) { [string]$t.StartBoundary } else { $null }
    }
}
if (-not $WhatIfOnly) {
    $snapshot | ConvertTo-Json -Depth 4 | Out-File -FilePath $BackupFile -Encoding utf8
    Write-Host "  backup written: $BackupFile" -ForegroundColor Green
}

# ---------------------------------------------------------------- 1. HIDE WINDOWS
Write-Host ""
Write-Host "  1. STOPPING THE POPUP WINDOWS" -ForegroundColor Cyan
foreach ($t in $tasks) {
    $n = $t.TaskName
    if ($KEEP_INTERACTIVE -contains $n) {
        Write-Host ("     skipped   {0,-28} needs a desktop for headed Chromium" -f $n) -ForegroundColor Yellow
        continue
    }
    if ([string]$t.Principal.LogonType -eq 'S4U') {
        Write-Host ("     already   {0,-28} hidden" -f $n) -ForegroundColor DarkGray
        continue
    }
    if ($WhatIfOnly) {
        Write-Host ("     WOULD FIX {0,-28} Interactive -> S4U" -f $n)
        continue
    }
    try {
        $p = New-ScheduledTaskPrincipal -UserId $t.Principal.UserId -LogonType S4U -RunLevel $t.Principal.RunLevel
        Set-ScheduledTask -TaskName $n -Principal $p | Out-Null
        Write-Host ("     fixed     {0,-28} no more window" -f $n) -ForegroundColor Green
    } catch {
        Write-Host ("     FAILED    {0,-28} {1}" -f $n, $_.Exception.Message) -ForegroundColor Red
    }
}

# ---------------------------------------------------------------- 2. CADENCE
if (-not $SkipCadence) {
    Write-Host ""
    Write-Host "  2. RAISING ODDS-CAPTURE CADENCE" -ForegroundColor Cyan
    $oc = $tasks | Where-Object { $_.TaskName -eq $CADENCE_TASK }
    if (-not $oc) {
        Write-Host "     $CADENCE_TASK not found -- skipped." -ForegroundColor Yellow
    } else {
        $cur = $oc.Triggers | Select-Object -First 1
        Write-Host ("     current   repeat {0} for {1}" -f $cur.Repetition.Interval, $cur.Repetition.Duration)
        Write-Host ("     target    repeat {0} for {1} from {2}" -f $CadenceInterval, $CadenceDuration, $CadenceStartTime)
        $calls = [math]::Floor(([System.Xml.XmlConvert]::ToTimeSpan($CadenceDuration)).TotalMinutes /
                               ([System.Xml.XmlConvert]::ToTimeSpan($CadenceInterval)).TotalMinutes)
        Write-Host ("     cost      ~{0} calls/day x 3 credits = ~{1} credits/day" -f $calls, ($calls * 3))
        if ($WhatIfOnly) {
            Write-Host "     WOULD CHANGE (preview only)"
        } else {
            try {
                $trigger = New-ScheduledTaskTrigger -Daily -At $CadenceStartTime
                $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $CadenceStartTime `
                    -RepetitionInterval ([System.Xml.XmlConvert]::ToTimeSpan($CadenceInterval)) `
                    -RepetitionDuration ([System.Xml.XmlConvert]::ToTimeSpan($CadenceDuration))).Repetition
                Set-ScheduledTask -TaskName $CADENCE_TASK -Trigger $trigger | Out-Null
                $now = (Get-ScheduledTask -TaskName $CADENCE_TASK).Triggers | Select-Object -First 1
                Write-Host ("     now       repeat {0} for {1}" -f $now.Repetition.Interval, $now.Repetition.Duration) -ForegroundColor Green
            } catch {
                Write-Host ("     FAILED    {0}" -f $_.Exception.Message) -ForegroundColor Red
                Write-Host "     Set it by hand: Task Scheduler -> $CADENCE_TASK -> Triggers -> Edit"
            }
        }
    }
}

# ---------------------------------------------------------------- VERIFY
Write-Host ""
Write-Host "  RESULT" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' } | ForEach-Object {
    $t = $_.Triggers | Select-Object -First 1
    [PSCustomObject]@{
        Task    = $_.TaskName
        Logon   = [string]$_.Principal.LogonType
        Window  = if ([string]$_.Principal.LogonType -eq 'S4U') { 'hidden' } else { 'VISIBLE' }
        Repeat  = if ($t) { [string]$t.Repetition.Interval } else { '' }
    }
} | Format-Table -AutoSize

Write-Host "  Undo everything:  ... \ops_fix_task_windows_and_cadence.ps1 -Undo"
Write-Host ""
