[CmdletBinding()]
param(
    [string]$CorrespondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence",
    [switch]$DryRun
)

# Async Stop hook. A handoff-ready response is archived in rotations/. This
# launches exactly one fresh coordinating generation. The coordinator may fan
# out bounded workers, but all branches must funnel back through it.

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([string]$Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $event = $raw | ConvertFrom-Json
    if ([string]$event.hook_event_name -ne "Stop") { exit 0 }

    $message = [string]$event.last_assistant_message
    if ($message -notmatch "\[CLAUDE_CONTEXT_HANDOFF_READY\]") { exit 0 }

    $oldSessionId = [string]$event.session_id
    $messageHash = Get-Sha256Hex -Value "Stop`n$oldSessionId`n$message"
    $hashToken = $messageHash.Substring(0, 16)
    $rotationRoot = Join-Path $CorrespondenceRoot "rotations"
    $stateRoot = Join-Path $CorrespondenceRoot "state"
    [void](New-Item -ItemType Directory -Force -Path $stateRoot)

    # Archive and launcher hooks run in parallel. Match this exact response.
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $rotation = $null
    do {
        $rotation = Get-ChildItem -LiteralPath $rotationRoot -File -Filter "*__${hashToken}.md" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $rotation) { break }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($null -eq $rotation) { exit 0 }

    $lockRoot = Join-Path $stateRoot "claude-rotation-locks"
    [void](New-Item -ItemType Directory -Force -Path $lockRoot)
    $lockPath = Join-Path $lockRoot ($rotation.BaseName + ".lock")
    try {
        $lock = [System.IO.File]::Open($lockPath, "CreateNew", "Write", "None")
        $lock.Dispose()
    }
    catch [System.IO.IOException] { exit 0 }

    $projectRoot = [string]$event.cwd
    $installationPath = Join-Path $projectRoot ".claude\codex-supervisor-bridge.json"
    if (-not (Test-Path -LiteralPath $installationPath)) { exit 0 }
    $installation = Get-Content -Raw -LiteralPath $installationPath | ConvertFrom-Json
    $claudeExe = [string]$installation.claude_executable
    $supervisorRoot = [string]$installation.supervisor_workspace_root
    $model = if ([string]::IsNullOrWhiteSpace([string]$installation.claude_model)) { "opus" } else { [string]$installation.claude_model }
    $effort = if ([string]::IsNullOrWhiteSpace([string]$installation.claude_effort)) { "high" } else { [string]$installation.claude_effort }
    if (
        [string]::IsNullOrWhiteSpace($claudeExe) -or
        -not (Test-Path -LiteralPath $claudeExe) -or
        [string]::IsNullOrWhiteSpace($supervisorRoot) -or
        -not (Test-Path -LiteralPath $supervisorRoot)
    ) { exit 0 }

    $launchToken = [guid]::NewGuid().ToString().Substring(0, 8)
    $sessionName = "WNBA-coordinator-" + $launchToken
    $newSessionId = $null
    $backgroundAgentId = $null
    $prompt = @"
You are the sole active Claude Code coordinating generation for this WNBA project.
Read the continuation packet at:
$($rotation.FullName)

Then read $CorrespondenceRoot\SUPERVISOR_CHARTER.md,
$CorrespondenceRoot\AUTOMATION_PLAYBOOK.md, and
$CorrespondenceRoot\state\CURRENT_STATE.md. Verify branch, HEAD, artifacts, and working tree.
Resume the exact authorized next action without repeating completed work or asking merely
whether to continue. You may fan out genuinely independent bounded tasks to parallel workers,
including nested fan-outs when useful, but every branch must funnel back to this coordinator
for conflict checks, unified verification, one gate result, and one message to Codex. Inventory
any inherited workers from the packet before spawning overlapping work. The prior coordinator
$oldSessionId is retired. Stop normally when integrated work is ready for Codex review.
"@

    $startedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    if ($DryRun) {
        $newSessionId = "dry-run-session-${launchToken}"
        $backgroundAgentId = "dryrun-${launchToken}"
        $output = "DRY RUN: would launch Claude coordinator $newSessionId"
        $exitCode = 0
    }
    else {
        Push-Location $projectRoot
        try {
            # Background sessions use the CLI credential store, which can differ
            # from an already-authenticated desktop session. Fail closed before
            # retiring the old coordinator if that credential is unavailable.
            $authOutput = & $claudeExe auth status --json 2>$null
            $authExit = $LASTEXITCODE
            $authState = if ($authExit -eq 0) { $authOutput | ConvertFrom-Json } else { $null }
            if ($null -eq $authState -or -not [bool]$authState.loggedIn) {
                $output = "Claude background CLI is not authenticated. Run 'claude auth login' once; the durable rotation packet remains available."
                $exitCode = 4
            }
            else {
                # In Claude Code 2.1.219 the positional prompt must precede --bg;
                # placing it after --bg creates an empty blocked session.
                $arguments = @(
                    $prompt,
                    "--name", $sessionName,
                    "--model", $model,
                    "--effort", $effort,
                    "--permission-mode", "auto",
                    "--add-dir", $supervisorRoot,
                    "--bg"
                )
                $output = & $claudeExe @arguments 2>&1
                $exitCode = $LASTEXITCODE
            }

            if ($exitCode -eq 0) {
                $outputText = ($output | Out-String)
                if ($outputText -match "backgrounded\s+[^A-Za-z0-9]*([A-Za-z0-9]{8})") {
                    $backgroundAgentId = $Matches[1]
                }

                # --bg owns the session UUID. Resolve it from the local agent
                # roster by the unique name instead of passing --session-id,
                # which Claude Code documents as ignored for background agents.
                Start-Sleep -Seconds 1
                $rosterOutput = & $claudeExe agents --json 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $roster = @($rosterOutput | ConvertFrom-Json)
                    $launched = $roster |
                        Where-Object { [string]$_.name -eq $sessionName -and [string]$_.cwd -eq $projectRoot } |
                        Sort-Object startedAt -Descending |
                        Select-Object -First 1
                    if ($null -ne $launched) {
                        $newSessionId = [string]$launched.sessionId
                        if ([string]::IsNullOrWhiteSpace($backgroundAgentId)) {
                            $backgroundAgentId = [string]$launched.id
                        }
                    }
                }
                if ([string]::IsNullOrWhiteSpace($newSessionId)) {
                    $exitCode = 3
                    $output = @($output) + "Could not resolve the background coordinator's managed session UUID."
                }
            }
        }
        finally { Pop-Location }
    }

    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    $logRoot = Join-Path $stateRoot "claude-rotation-logs"
    [void](New-Item -ItemType Directory -Force -Path $logRoot)
    [System.IO.File]::WriteAllText(
        (Join-Path $logRoot ($rotation.BaseName + ".log")),
        (($output | Out-String).Trim()),
        $utf8WithoutBom
    )

    if ($exitCode -ne 0) {
        $failure = [ordered]@{
            schema_version = 1
            rotation_file = $rotation.FullName
            previous_coordinator_session_id = $oldSessionId
            attempted_coordinator_session_id = $newSessionId
            background_agent_id = $backgroundAgentId
            attempted_at_utc = $startedAt
            exit_code = $exitCode
            status = "launch_failed_pending_recovery"
        }
        [System.IO.File]::WriteAllText(
            (Join-Path $stateRoot "claude_generation_launch_failure.json"),
            ($failure | ConvertTo-Json -Depth 4),
            $utf8WithoutBom
        )
        Remove-Item -Force -LiteralPath $lockPath -ErrorAction SilentlyContinue
        exit 0
    }

    $generation = [ordered]@{
        schema_version = 1
        active_coordinator_session_id = $newSessionId
        previous_coordinator_session_id = $oldSessionId
        background_agent_id = $backgroundAgentId
        mode = "background"
        session_name = $sessionName
        model = $model
        effort = $effort
        rotation_file = $rotation.FullName
        launched_at_utc = $startedAt
        launch_exit_code = $exitCode
    }
    $temporaryPath = Join-Path $stateRoot (".claude_generation." + $PID + ".tmp")
    [System.IO.File]::WriteAllText($temporaryPath, ($generation | ConvertTo-Json -Depth 5), $utf8WithoutBom)
    Move-Item -Force -LiteralPath $temporaryPath -Destination (Join-Path $stateRoot "claude_generation.json")

    $loadedReceipt = [ordered]@{
        schema_version = 1
        loaded_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        new_session_id = $newSessionId
        background_agent_id = $backgroundAgentId
        rotation_file = $rotation.FullName
        mode = "automatic_background_successor"
    }
    [System.IO.File]::WriteAllText(
        (Join-Path $stateRoot ($rotation.BaseName + ".loaded.json")),
        ($loadedReceipt | ConvertTo-Json -Depth 4),
        $utf8WithoutBom
    )
}
catch {
    # The durable packet remains available to the manual /clear recovery path.
    exit 0
}

exit 0
