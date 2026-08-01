<#
.SYNOPSIS
    Audit (and optionally repair) the WNBA scheduled tasks, then verify that the
    forecast chain actually grew.

.DESCRIPTION
    Step 1 of project_docs/PLAN_2026-07-31_W1_AUDIT_AND_BAKEOFF.md, frozen as
    plan_freeze_2026_07_31. Two problems this addresses, both recorded in that plan:

      * WNBA_PropsCapture_1..4 carry StartWhenAvailable = False. A once-daily task
        created that way SKIPS A MISSED WINDOW SILENTLY -- if the machine is asleep
        or busy at 11:05, that capture is simply gone, with no error anywhere. The
        handoff's Gotchas section (2026-07-31) records this as the standing hazard.
      * Both forecast tasks and all four props tasks reported 267011
        (SCHED_S_TASK_HAS_NOT_RUN) at the time the plan was written, because they
        were registered AFTER their morning triggers. The three chain records in
        forecasts/forecast_log.jsonl came from a manual run, so the AUTOMATED PATH
        WAS UNPROVEN. WNBA_PropsCapture_2 has since fired at 15:05 with result 0;
        the forecast tasks still need confirming.

    READ-ONLY BY DEFAULT. Nothing is modified unless -Apply is passed. The repair
    is idempotent: a task already carrying StartWhenAvailable is reported and left
    alone.

    Run this ON THE MACHINE THAT OWNS THE TASKS. Task state is not in the repo and
    cannot be checked from anywhere else.

.PARAMETER Apply
    Actually set StartWhenAvailable on the tasks that lack it. Without this the
    script only reports what it would change.

.PARAMETER RepoRoot
    Repo root, for the forecast-log check. Defaults to this script's parent.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup_scripts\verify_scheduled_tasks.ps1
    powershell -ExecutionPolicy Bypass -File setup_scripts\verify_scheduled_tasks.ps1 -Apply

.NOTES
    Exit codes:  0 = every task healthy and the chain verified
                 1 = something needs attention (details printed)
                 2 = a task is missing entirely
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$RepoRoot
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot is not reliably populated inside a param() default under Windows
# PowerShell 5.1 (it came back empty when invoked as `powershell -File ...`,
# and Split-Path then threw on an empty Path before the script could start).
# Resolve it in the body instead, where $PSCommandPath is dependable.
if (-not $RepoRoot) {
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir -and $PSCommandPath) { $scriptDir = Split-Path -Parent $PSCommandPath }
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
    $RepoRoot = Split-Path -Parent $scriptDir
}

# The full expected inventory. Six capture/refresh tasks plus the two forecast
# runs; StartWhenAvailable matters for every one of them, because each is a
# once-or-few-times-daily job whose missed window is permanently missing.
$Expected = @(
    @{ Name = 'WNBA_OddsCapture';        Critical = $true  }
    @{ Name = 'WNBA_InjuryCapture';      Critical = $true  }
    @{ Name = 'WNBA_NewsCapture';        Critical = $false }
    @{ Name = 'WNBA_RefAssignments';     Critical = $false }
    @{ Name = 'WNBA_DailyRefresh';       Critical = $true  }
    @{ Name = 'WNBA_PropsCapture_1';     Critical = $true  }
    @{ Name = 'WNBA_PropsCapture_2';     Critical = $true  }
    @{ Name = 'WNBA_PropsCapture_3';     Critical = $true  }
    @{ Name = 'WNBA_PropsCapture_4';     Critical = $true  }
    @{ Name = 'WNBA_DailyForecast_AM';   Critical = $true  }
    @{ Name = 'WNBA_DailyForecast_PM';   Critical = $true  }
)

# SCHED_S_TASK_HAS_NOT_RUN. Not an error in itself -- a freshly registered task
# legitimately reports it until its first trigger -- but on a task that should
# have fired by now it means the automated path is unproven.
$NEVER_RUN = 267011

$problems = New-Object System.Collections.Generic.List[string]
$missing  = New-Object System.Collections.Generic.List[string]
$repaired = New-Object System.Collections.Generic.List[string]

Write-Host ''
Write-Host 'WNBA scheduled tasks' -ForegroundColor Cyan
Write-Host ('-' * 100)
Write-Host ('{0,-24} {1,-8} {2,-20} {3,-12} {4,-10} {5}' -f `
            'task', 'state', 'last run', 'last result', 'StartWhenAvail', 'next run')
Write-Host ('-' * 100)

foreach ($spec in $Expected) {
    $name = $spec.Name

    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host ('{0,-24} MISSING -- not registered on this machine' -f $name) -ForegroundColor Red
        $missing.Add($name)
        continue
    }

    $info = Get-ScheduledTaskInfo -TaskName $name -TaskPath $task.TaskPath
    $swa  = [bool]$task.Settings.StartWhenAvailable

    # 11/30/1999 is the sentinel Task Scheduler uses for "never".
    $lastRun = if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) {
        $info.LastRunTime.ToString('yyyy-MM-dd HH:mm')
    } else { 'never' }
    $nextRun = if ($info.NextRunTime) { $info.NextRunTime.ToString('MM-dd HH:mm') } else { '-' }

    $resultText = '{0}' -f $info.LastTaskResult
    if ($info.LastTaskResult -eq $NEVER_RUN) { $resultText = '267011 never' }

    $colour = 'Gray'
    if (-not $swa)                                   { $colour = 'Yellow' }
    if ($info.LastTaskResult -notin @(0, $NEVER_RUN)) { $colour = 'Red' }

    Write-Host ('{0,-24} {1,-8} {2,-20} {3,-12} {4,-10} {5}' -f `
                $name, $task.State, $lastRun, $resultText, $swa, $nextRun) -ForegroundColor $colour

    # ---- StartWhenAvailable ------------------------------------------------
    if (-not $swa) {
        if ($Apply) {
            # Mutate the EXISTING settings object rather than constructing a new
            # one: New-ScheduledTaskSettingsSet would silently reset every other
            # setting on the task (idle conditions, power, restart policy) to its
            # default, which is a far larger change than the one being asked for.
            $settings = $task.Settings
            $settings.StartWhenAvailable = $true
            Set-ScheduledTask -TaskName $name -TaskPath $task.TaskPath -Settings $settings | Out-Null

            $check = (Get-ScheduledTask -TaskName $name).Settings.StartWhenAvailable
            if ($check) {
                Write-Host '    repaired: StartWhenAvailable -> True' -ForegroundColor Green
                $repaired.Add($name)
            } else {
                $problems.Add("$name -- Set-ScheduledTask reported success but StartWhenAvailable is still False")
            }
        } else {
            Write-Host '    would set StartWhenAvailable -> True  (re-run with -Apply)' -ForegroundColor Yellow
            $problems.Add("$name -- StartWhenAvailable is False; a missed window is skipped silently")
        }
    }

    # ---- did it actually run? ---------------------------------------------
    if ($info.LastTaskResult -eq $NEVER_RUN) {
        # Only a problem once a trigger has already passed.
        $overdue = $info.NextRunTime -and ($info.NextRunTime - (Get-Date)).TotalHours -lt -0.5
        if ($spec.Critical -and $overdue) {
            $problems.Add("$name -- has NEVER executed and its trigger has passed; the automated path is unproven")
        }
    } elseif ($info.LastTaskResult -ne 0) {
        $problems.Add(("{0} -- last run exited {1} (0x{1:X8})" -f $name, $info.LastTaskResult))
    }
}

# --------------------------------------------------------------------------- #
# the chain actually grew
# --------------------------------------------------------------------------- #
# A green task result only proves the process exited 0. What matters is whether
# a record reached the log, so check the artifact rather than the scheduler.

Write-Host ''
Write-Host 'Forecast chain' -ForegroundColor Cyan
Write-Host ('-' * 100)

$logPath = Join-Path $RepoRoot 'forecasts\forecast_log.jsonl'
if (-not (Test-Path $logPath)) {
    Write-Host "MISSING: $logPath" -ForegroundColor Red
    $problems.Add('forecast_log.jsonl not found')
} else {
    $lines = @(Get-Content $logPath | Where-Object { $_.Trim() })
    Write-Host ("records: {0}" -f $lines.Count)

    # forecast_cutoff is the decision moment -- the field that says when the
    # forecast was COMMITTED. logged_at_utc is when the line was written.
    #
    # Compare against the LOCAL operating day, not the UTC one. The forecast
    # tasks fire at 10:20 and 18:45 ET; the evening run stamps a cutoff around
    # 22:45Z, so from 20:00 ET until midnight the UTC date has already rolled
    # over and a UTC-keyed comparison reports zero records for "today" on a day
    # that ran perfectly. That false alarm fires nightly, and a check that cries
    # wolf is a check that gets ignored -- the same failure mode .gitattributes
    # was added to prevent.
    $today = (Get-Date).ToString('yyyy-MM-dd')
    $todayCount = 0
    $lastCutoff = ''
    foreach ($line in $lines) {
        try { $rec = $line | ConvertFrom-Json } catch { continue }
        if ($rec.forecast_cutoff) {
            $lastCutoff = $rec.forecast_cutoff
            try {
                $cut = [datetimeoffset]::Parse(
                    $rec.forecast_cutoff, [cultureinfo]::InvariantCulture,
                    [System.Globalization.DateTimeStyles]::RoundtripKind)
                if ($cut.ToLocalTime().ToString('yyyy-MM-dd') -eq $today) { $todayCount++ }
            } catch {
                # Unparseable timestamp: fall back to the raw prefix rather than
                # silently dropping the record from the count.
                if ($rec.forecast_cutoff.StartsWith($today)) { $todayCount++ }
            }
        }
    }
    Write-Host ("records with forecast_cutoff today (local {0}): {1}" -f $today, $todayCount)
    if ($lastCutoff) { Write-Host ("last forecast_cutoff: {0}" -f $lastCutoff) }

    if ($todayCount -eq 0) {
        $problems.Add('no forecast record carries a cutoff stamped today -- a scheduled run either did not fire or did not append')
    }

    # Hash-chain integrity, using the repo's own verifier rather than a
    # reimplementation -- one definition of a valid chain, not two.
    Push-Location $RepoRoot
    try {
        $verify = & python -c @"
from evalharness.forecast_log import verify_chain
r = verify_chain('forecasts/forecast_log.jsonl')
print('ok={0} n_records={1} n_verified={2} reason={3}'.format(r.ok, r.n_records, r.n_verified, r.reason))
raise SystemExit(0 if r.ok else 1)
"@ 2>&1
        $verifyExit = $LASTEXITCODE
        Write-Host ("verify_chain: {0}" -f ($verify -join ' '))
        if ($verifyExit -ne 0) {
            $problems.Add('verify_chain did not report a clean chain -- see the reason printed above')
        }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #

Write-Host ''
Write-Host 'Summary' -ForegroundColor Cyan
Write-Host ('-' * 100)

if ($repaired.Count) {
    Write-Host ("repaired {0} task(s): {1}" -f $repaired.Count, ($repaired -join ', ')) -ForegroundColor Green
}
if ($missing.Count) {
    Write-Host ("MISSING {0} task(s): {1}" -f $missing.Count, ($missing -join ', ')) -ForegroundColor Red
}
if ($problems.Count) {
    Write-Host ("{0} item(s) need attention:" -f $problems.Count) -ForegroundColor Yellow
    foreach ($p in $problems) { Write-Host "  * $p" -ForegroundColor Yellow }
} elseif (-not $missing.Count) {
    Write-Host 'All tasks healthy and the chain verifies.' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Reminder: a missed capture day is permanently missing from the prospective'
Write-Host 'chain and is never backfilled. The machine must stay on.'
Write-Host ''

if ($missing.Count)  { exit 2 }
if ($problems.Count) { exit 1 }
exit 0
