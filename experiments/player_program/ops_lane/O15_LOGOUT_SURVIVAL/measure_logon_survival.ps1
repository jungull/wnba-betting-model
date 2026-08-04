<#
.SYNOPSIS
    O15_LOGOUT_SURVIVAL -- measurement script. READ-ONLY. Mutates nothing.

.DESCRIPTION
    Regenerates every number quoted in REPORT.md, from the two authorities that
    actually hold the answer:

      * Get-ScheduledTask       -- the live principal of every WNBA_* task
      * Microsoft-Windows-TaskScheduler/Operational, event id 332
                                  -- "did not launch ... because user was not
                                     logged on", i.e. the defect firing

    Task state is not in the repo. This must run ON THE MACHINE THAT OWNS THE
    TASKS, exactly as setup_scripts\verify_scheduled_tasks.ps1:25-26 says.

    Writes EVIDENCE_measured.json next to this script. Nothing else is touched.

.NOTES
    Event id reference observed in the live log on this machine:
      332 = task not launched, user not logged on   (the D-f mechanism)
      100 = task started
      322 = not launched, instance already running  (unrelated; excluded)
#>

[CmdletBinding()]
param(
    [string]$OutFile
)

$ErrorActionPreference = 'Stop'

if (-not $OutFile) {
    $here = $PSScriptRoot
    if (-not $here -and $PSCommandPath) { $here = Split-Path -Parent $PSCommandPath }
    if (-not $here) { $here = (Get-Location).Path }
    $OutFile = Join-Path $here 'EVIDENCE_measured.json'
}

$LOG = 'Microsoft-Windows-TaskScheduler/Operational'

# --------------------------------------------------------------------------- #
# 1. live principals
# --------------------------------------------------------------------------- #
$principals = @()
foreach ($t in (Get-ScheduledTask | Where-Object { $_.TaskName -like 'WNBA*' } | Sort-Object TaskName)) {
    $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $t.TaskPath
    $principals += [pscustomobject]@{
        task                = $t.TaskName
        task_path           = $t.TaskPath
        state               = [string]$t.State
        logon_type          = [string]$t.Principal.LogonType
        run_level           = [string]$t.Principal.RunLevel
        user_id             = [string]$t.Principal.UserId
        start_when_available= [bool]$t.Settings.StartWhenAvailable
        last_result         = $info.LastTaskResult
    }
}

$interactive = @($principals | Where-Object { $_.logon_type -eq 'Interactive' })

# --------------------------------------------------------------------------- #
# 2. every id-332 event the log still holds
# --------------------------------------------------------------------------- #
# The Operational log is a rolling 10 MB buffer. Its OLDEST retained record
# bounds the observation window: absence of a 332 before that instant is not
# evidence the defect did not fire, only that the log no longer holds it.
$logInfo = Get-WinEvent -ListLog $LOG
$oldest  = (Get-WinEvent -LogName $LOG -Oldest -MaxEvents 1).TimeCreated

$e332 = @(Get-WinEvent -FilterHashtable @{ LogName = $LOG; Id = 332 } -ErrorAction SilentlyContinue)

$rows = foreach ($e in $e332) {
    $name = $null
    if ($e.Message -match 'task "([^"]+)"') { $name = $Matches[1] }
    [pscustomobject]@{ task = $name; t = $e.TimeCreated }
}

$wnba332 = @($rows | Where-Object { $_.task -like '*WNBA*' } | Sort-Object t)

$byTask = @{}
foreach ($r in $wnba332) {
    $k = $r.task
    if (-not $byTask.ContainsKey($k)) { $byTask[$k] = 0 }
    $byTask[$k] = $byTask[$k] + 1
}

# --------------------------------------------------------------------------- #
# 3. did StartWhenAvailable recover any of them?
# --------------------------------------------------------------------------- #
# A catch-up run lands at an ARBITRARY instant (whenever the machine became
# available), not on the trigger's second boundary. So: list every id-100 start
# for the worst-hit task on the affected day and check whether any start is off
# the regular :00:01 cadence.
$worst = ($byTask.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1).Key
$affectedDays = @($wnba332 | ForEach-Object { $_.t.ToString('yyyy-MM-dd') } | Sort-Object -Unique)

$starts = @()
foreach ($d in $affectedDays) {
    $s = Get-Date $d
    $s100 = @(Get-WinEvent -FilterHashtable @{
                  LogName = $LOG; Id = 100; StartTime = $s; EndTime = $s.AddDays(1)
              } -ErrorAction SilentlyContinue |
              Where-Object { $_.Message -like "*$worst*" } | Sort-Object TimeCreated)
    foreach ($x in $s100) { $starts += $x.TimeCreated.ToString('o') }
}

$out = [ordered]@{
    generated_utc          = (Get-Date).ToUniversalTime().ToString('o')
    machine                = $env:COMPUTERNAME
    log_name               = $LOG
    log_record_count       = $logInfo.RecordCount
    log_max_bytes          = $logInfo.MaximumSizeInBytes
    log_oldest_record      = $oldest.ToString('o')
    wnba_tasks_total       = $principals.Count
    wnba_tasks_interactive = $interactive.Count
    principals             = $principals
    e332_total_all_tasks   = $e332.Count
    e332_wnba_total        = $wnba332.Count
    e332_wnba_by_task      = $byTask
    e332_wnba_first        = if ($wnba332.Count) { $wnba332[0].t.ToString('o') } else { $null }
    e332_wnba_last         = if ($wnba332.Count) { $wnba332[-1].t.ToString('o') } else { $null }
    e332_affected_days     = $affectedDays
    worst_hit_task         = $worst
    worst_hit_starts_on_affected_days = $starts
}

$out | ConvertTo-Json -Depth 6 | Out-File -FilePath $OutFile -Encoding utf8
Write-Host "wrote $OutFile"
Write-Host ("WNBA tasks: {0}, Interactive: {1}, id-332 WNBA events: {2}" -f `
            $principals.Count, $interactive.Count, $wnba332.Count)
