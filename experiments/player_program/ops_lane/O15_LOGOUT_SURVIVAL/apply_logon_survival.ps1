<#
.SYNOPSIS
    O15_LOGOUT_SURVIVAL -- the remediation for defect D-f. READ-ONLY BY DEFAULT.

.DESCRIPTION
    Defect D-f (PROJECT_UPDATE_2026-08-04.md:204): every WNBA scheduled task is
    registered with LogonType = InteractiveToken, so Task Scheduler refuses to
    launch it while nobody is logged on and records event 332 instead. Measured
    on this machine: 13/13 tasks Interactive, 23 suppressed launches on
    2026-08-02 between 08:00 and 16:00 local. See REPORT.md.

    This script changes ONE thing per task: the principal's LogonType, from
    InteractiveToken to S4U ("run whether user is logged on or not, do not store
    password"). Triggers, actions and settings -- above all StartWhenAvailable,
    which setup_scripts\verify_scheduled_tasks.ps1 exists to protect -- are
    passed through untouched. logon_survival_fix.py states that invariant and
    TESTS.py asserts it against this machine's real exported definitions.

    NOTHING IS MODIFIED WITHOUT -Apply. Without it the script prints the plan.

    -Apply is a change to the machine's scheduled-task configuration. It is the
    operator's decision, not the analyst's. This script was NEVER run with
    -Apply by the node that wrote it.

.PARAMETER Apply
    Actually set the principal. Requires an ELEVATED shell: registering an S4U
    principal needs administrative rights, and a non-elevated attempt fails with
    access denied rather than silently doing nothing.

.PARAMETER Mode
    S4U (default) or Password.

      S4U       no stored password; the process gets NO outbound network
                credentials. Correct for these jobs -- verified: every capture
                script uses plain HTTPS (requests/urllib) to public endpoints
                and writes to local disk; none drives a browser and none reads
                a UNC path. Wrong for anything needing a file share.

      Password  full network credentials, but the scheduler must be given the
                account password and the account needs the "Log on as a batch
                job" right. This is the "batch-logon with IT" route demoted at
                PROJECT_UPDATE_2026-08-04.md:267. This script does NOT accept a
                password: use taskschd.msc or Register-ScheduledTask -Password
                so the secret never passes through a repo file.

.PARAMETER ExcludeWatchdog
    Default true. WNBA_ReplyDeliveryWatchdog runs a script under a
    OneDrive-synced path. Under S4U there is no interactive OneDrive client to
    hydrate a cloud-only placeholder, so that task needs its own decision and is
    left alone. Pass -ExcludeWatchdog:$false to include it deliberately.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File apply_logon_survival.ps1
    powershell -ExecutionPolicy Bypass -File apply_logon_survival.ps1 -Apply   # elevated

.NOTES
    Exit codes: 0 = every in-scope task already survives logoff
                1 = at least one task still does not (or a change failed)
                2 = -Apply requested without elevation

    VERIFICATION LIMIT, stated because it is the honest bound on this fix:
    reading back LogonType = S4U proves the DEFINITION changed. It does not
    prove a launch succeeds with no session present. Only an actual logged-out
    firing does that -- log out over a trigger boundary, log back in, and
    confirm (a) no new id-332 for the task and (b) a new id-100 start at the
    trigger instant. Until that is observed, the fix is designed and unit-tested
    but not operationally confirmed.
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [ValidateSet('S4U', 'Password')]
    [string]$Mode = 'S4U',
    [bool]$ExcludeWatchdog = $true
)

$ErrorActionPreference = 'Stop'

$SURVIVING = @('S4U', 'Password')
$WATCHDOG  = 'WNBA_ReplyDeliveryWatchdog'

if ($Apply -and $Mode -eq 'Password') {
    Write-Host 'Password mode is not applied from this script -- it would require a secret in or through a repo file.' -ForegroundColor Red
    Write-Host 'Use taskschd.msc, or Register-ScheduledTask -User <acct> -Password <pw> interactively.' -ForegroundColor Red
    exit 1
}

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$elevated  = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($Apply -and -not $elevated) {
    Write-Host 'Refusing to -Apply from a non-elevated shell.' -ForegroundColor Red
    Write-Host 'Registering an S4U principal requires administrative rights; a non-elevated'
    Write-Host 'attempt fails partway and would leave the task set half-converted.'
    exit 2
}

$tasks = @(Get-ScheduledTask | Where-Object { $_.TaskName -like 'WNBA*' } | Sort-Object TaskName)
if (-not $tasks.Count) {
    Write-Host 'No WNBA_* tasks registered on this machine. Task state is not in the repo --' -ForegroundColor Yellow
    Write-Host 'this must run on the machine that owns the tasks.' -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host ("WNBA task principals  (mode={0}, apply={1}, elevated={2})" -f $Mode, [bool]$Apply, $elevated) -ForegroundColor Cyan
Write-Host ('-' * 96)
Write-Host ('{0,-28} {1,-14} {2,-9} {3,-8} {4}' -f 'task', 'logon type', 'run level', 'SWA', 'action')
Write-Host ('-' * 96)

$stillDefective = New-Object System.Collections.Generic.List[string]
$changed        = New-Object System.Collections.Generic.List[string]
$failed         = New-Object System.Collections.Generic.List[string]

foreach ($t in $tasks) {
    $lt  = [string]$t.Principal.LogonType
    $rl  = [string]$t.Principal.RunLevel
    $uid = [string]$t.Principal.UserId
    $swa = [bool]$t.Settings.StartWhenAvailable

    $survives = $SURVIVING -contains $lt
    $skipped  = $ExcludeWatchdog -and ($t.TaskName -eq $WATCHDOG)

    if ($survives) {
        $action = 'ok -- already survives logoff'
        $colour = 'Gray'
    } elseif ($skipped) {
        $action = 'SKIPPED -- OneDrive-hosted script, needs its own decision'
        $colour = 'Yellow'
        $stillDefective.Add($t.TaskName)
    } elseif (-not $Apply) {
        $action = "would set LogonType -> $Mode  (re-run elevated with -Apply)"
        $colour = 'Yellow'
        $stillDefective.Add($t.TaskName)
    } else {
        $action = '...'
        $colour = 'Gray'
    }

    Write-Host ('{0,-28} {1,-14} {2,-9} {3,-8} {4}' -f $t.TaskName, $lt, $rl, $swa, $action) -ForegroundColor $colour

    if ($Apply -and -not $survives -and -not $skipped) {
        try {
            # Carry UserId AND RunLevel across explicitly. A principal built
            # without them silently drops to the defaults -- the same class of
            # collateral reset that verify_scheduled_tasks.ps1:129-135 warns
            # about for settings.
            $newPrincipal = New-ScheduledTaskPrincipal -UserId $uid -LogonType $Mode -RunLevel $rl
            Set-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -Principal $newPrincipal | Out-Null

            $after = Get-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath
            $okLogon = ($SURVIVING -contains [string]$after.Principal.LogonType)
            $okSwa   = ([bool]$after.Settings.StartWhenAvailable -eq $swa)
            $okLevel = ([string]$after.Principal.RunLevel -eq $rl)

            if ($okLogon -and $okSwa -and $okLevel) {
                Write-Host ("    changed: LogonType {0} -> {1}; StartWhenAvailable and RunLevel intact" -f $lt, $after.Principal.LogonType) -ForegroundColor Green
                $changed.Add($t.TaskName)
            } else {
                $why = @()
                if (-not $okLogon) { $why += "LogonType is still $($after.Principal.LogonType)" }
                if (-not $okSwa)   { $why += "StartWhenAvailable changed $swa -> $($after.Settings.StartWhenAvailable)" }
                if (-not $okLevel) { $why += "RunLevel changed $rl -> $($after.Principal.RunLevel)" }
                Write-Host ("    PROBLEM: " + ($why -join '; ')) -ForegroundColor Red
                $failed.Add("$($t.TaskName) -- $($why -join '; ')")
                $stillDefective.Add($t.TaskName)
            }
        } catch {
            Write-Host ("    FAILED: " + $_.Exception.Message) -ForegroundColor Red
            $failed.Add("$($t.TaskName) -- $($_.Exception.Message)")
            $stillDefective.Add($t.TaskName)
        }
    }
}

Write-Host ''
Write-Host 'Summary' -ForegroundColor Cyan
Write-Host ('-' * 96)
if ($changed.Count)        { Write-Host ("changed {0}: {1}" -f $changed.Count, ($changed -join ', ')) -ForegroundColor Green }
if ($failed.Count)         { foreach ($f in $failed) { Write-Host "  * $f" -ForegroundColor Red } }
if ($stillDefective.Count) { Write-Host ("{0} task(s) still will not launch while logged out: {1}" -f $stillDefective.Count, ($stillDefective -join ', ')) -ForegroundColor Yellow }
else                       { Write-Host 'Every in-scope task now declares a logon mode that survives logoff.' -ForegroundColor Green }

Write-Host ''
Write-Host 'A read-back is not a confirmation. The definition changing is not the same as a'
Write-Host 'launch succeeding with no session present. Confirm by logging out across a trigger'
Write-Host 'boundary and checking for a new id-100 start and no new id-332 in'
Write-Host 'Microsoft-Windows-TaskScheduler/Operational.'
Write-Host ''

if ($failed.Count -or $stillDefective.Count) { exit 1 }
exit 0
