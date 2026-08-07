[CmdletBinding()]
param(
    [string]$CorrespondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence"
)

# Claude Code Stop/StopFailure hook.
# Writes immutable, timestamped correspondence records for the Codex supervisor.
# The only blocking behavior is a one-time request for a continuation packet when
# Claude's status-line telemetry reports at least 70% context use.

$ErrorActionPreference = "Stop"

function ConvertTo-SafeToken {
    param([AllowNull()][string]$Value, [int]$MaxLength = 24)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "unknown"
    }

    $safe = [regex]::Replace($Value, "[^A-Za-z0-9._-]", "-").Trim("-")
    if ([string]::IsNullOrWhiteSpace($safe)) {
        $safe = "unknown"
    }
    if ($safe.Length -gt $MaxLength) {
        $safe = $safe.Substring(0, $MaxLength)
    }
    return $safe
}

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

function Get-GitValue {
    param([string]$WorkingDirectory, [string[]]$Arguments)

    if ([string]::IsNullOrWhiteSpace($WorkingDirectory) -or -not (Test-Path -LiteralPath $WorkingDirectory)) {
        return $null
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $value = & git -C $WorkingDirectory @Arguments 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        return (($value | Select-Object -First 1) -as [string]).Trim()
    }
    catch {
        return $null
    }
}

function Get-TranscriptContextUsage {
    param([AllowNull()][string]$TranscriptPath)

    if ([string]::IsNullOrWhiteSpace($TranscriptPath) -or -not (Test-Path -LiteralPath $TranscriptPath)) {
        return $null
    }

    try {
        $lines = @(Get-Content -LiteralPath $TranscriptPath -Tail 200)
        for ($index = $lines.Count - 1; $index -ge 0; $index--) {
            try {
                $record = $lines[$index] | ConvertFrom-Json
                $usage = $record.message.usage
                if ($null -eq $usage) {
                    continue
                }

                $totalInputTokens = (
                    [double]$usage.input_tokens +
                    [double]$usage.cache_creation_input_tokens +
                    [double]$usage.cache_read_input_tokens
                )
                if ($totalInputTokens -le 0) {
                    continue
                }

                # Above 200k conclusively means Claude Code is using its extended
                # 1M window. This still detects 70% without guessing for other models.
                $contextWindowSize = if ($totalInputTokens -gt 200000) { 1000000 } else { $null }
                return [pscustomobject]@{
                    total_input_tokens = $totalInputTokens
                    context_window_size = $contextWindowSize
                    used_percentage = if ($null -eq $contextWindowSize) {
                        $null
                    }
                    else {
                        100.0 * $totalInputTokens / $contextWindowSize
                    }
                }
            }
            catch {
                continue
            }
        }
    }
    catch {
        return $null
    }

    return $null
}

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        exit 0
    }

    $event = $raw | ConvertFrom-Json
    $eventName = [string]$event.hook_event_name
    if ($eventName -notin @("Stop", "StopFailure")) {
        exit 0
    }

    $correspondenceRoot = $CorrespondenceRoot
    $directories = @(
        "inbox",
        "deferred",
        "failures",
        "processed",
        "replies",
        "rotations",
        "state",
        "state\delivery-receipts",
        "hook-errors"
    )
    foreach ($directory in $directories) {
        $path = Join-Path $correspondenceRoot $directory
        [void](New-Item -ItemType Directory -Force -Path $path)
    }

    $capturedAt = [DateTime]::UtcNow
    $capturedAtText = $capturedAt.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $timestampToken = $capturedAt.ToString("yyyyMMddTHHmmssfffZ")
    $sessionId = [string]$event.session_id
    $sessionToken = ConvertTo-SafeToken -Value $sessionId -MaxLength 12
    $message = [string]$event.last_assistant_message

    # A successful Stop after an async Codex wake is the acknowledgement that
    # Claude received and handled that reply. StopFailure deliberately does not
    # acknowledge it, so rate limits leave the reply eligible for a later retry.
    $activeReplyPath = Join-Path $correspondenceRoot "state\claude_active_reply.json"
    if ($eventName -eq "Stop" -and (Test-Path -LiteralPath $activeReplyPath)) {
        try {
            $activeReply = Get-Content -Raw -LiteralPath $activeReplyPath | ConvertFrom-Json
            if ([string]$activeReply.session_id -eq $sessionId) {
                $replyLeaf = [System.IO.Path]::GetFileName([string]$activeReply.reply_file)
                $replyToken = (Get-Sha256Hex -Value $replyLeaf).Substring(0, 16)
                $deliveryReceipt = [ordered]@{
                    schema_version = 1
                    session_id = $sessionId
                    source_file = [string]$activeReply.source_file
                    reply_file = [string]$activeReply.reply_file
                    wake_requested_at_utc = [string]$activeReply.wake_requested_at_utc
                    acknowledged_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                }
                $deliveryPath = Join-Path $correspondenceRoot "state\delivery-receipts\${replyToken}.json"
                [System.IO.File]::WriteAllText(
                    $deliveryPath,
                    ($deliveryReceipt | ConvertTo-Json -Depth 4),
                    (New-Object System.Text.UTF8Encoding($false))
                )
                Remove-Item -Force -LiteralPath $activeReplyPath
            }
        }
        catch {
            # A malformed advisory state file must not block normal archiving.
        }
    }

    if ($eventName -eq "StopFailure" -and [string]::IsNullOrWhiteSpace($message)) {
        $message = [string]$event.error_details
    }
    if ([string]::IsNullOrWhiteSpace($message)) {
        $message = "(Claude Code emitted no assistant message.)"
    }

    $backgroundCount = if (
        $null -ne $event.PSObject.Properties["background_tasks"] -and
        $null -ne $event.background_tasks
    ) { @($event.background_tasks).Count } else { 0 }
    $sessionCronCount = if (
        $null -ne $event.PSObject.Properties["session_crons"] -and
        $null -ne $event.session_crons
    ) { @($event.session_crons).Count } else { 0 }
    $errorType = if ($eventName -eq "StopFailure") { [string]$event.error } else { $null }

    $contextUsedPercentage = $null
    $contextWindowSize = $null
    $contextTotalInputTokens = $null
    $contextTelemetrySource = $null
    $contextStatePath = Join-Path $correspondenceRoot "state\claude_context.json"
    if (Test-Path -LiteralPath $contextStatePath) {
        try {
            $contextState = Get-Content -Raw -LiteralPath $contextStatePath | ConvertFrom-Json
            if ([string]$contextState.session_id -eq $sessionId) {
                $contextUsedPercentage = [double]$contextState.used_percentage
                $contextWindowSize = $contextState.context_window_size
                $contextTelemetrySource = "status_line"
            }
        }
        catch {
            $contextUsedPercentage = $null
        }
    }

    if ($null -eq $contextUsedPercentage) {
        $transcriptUsage = Get-TranscriptContextUsage -TranscriptPath ([string]$event.transcript_path)
        if ($null -ne $transcriptUsage) {
            $contextUsedPercentage = $transcriptUsage.used_percentage
            $contextWindowSize = $transcriptUsage.context_window_size
            $contextTotalInputTokens = $transcriptUsage.total_input_tokens
            $contextTelemetrySource = "transcript_last_api_usage"
        }
    }

    # Exactly one coordinator owns integration. That coordinator may have many
    # bounded workers, but a retired coordinator cannot re-enter the review loop.
    $isRetiredGeneration = $false
    $generationStatePath = Join-Path $correspondenceRoot "state\claude_generation.json"
    if (Test-Path -LiteralPath $generationStatePath) {
        try {
            $generationState = Get-Content -Raw -LiteralPath $generationStatePath | ConvertFrom-Json
            if (
                -not [string]::IsNullOrWhiteSpace([string]$generationState.active_coordinator_session_id) -and
                [string]$generationState.active_coordinator_session_id -ne $sessionId
            ) {
                $isRetiredGeneration = $true
            }
        }
        catch {
            $isRetiredGeneration = $false
        }
    }

    $rotationReady = $message -match "\[CLAUDE_CONTEXT_HANDOFF_READY\]"
    # DISABLED 2026-08-03 at the user's request. The context-threshold continuation
    # packet fired on every turn once context passed 70%, which made it impossible to
    # hold a normal conversation: every reply was preceded by a handoff nobody wanted.
    # Archiving below is UNAFFECTED and still runs on every Stop and StopFailure, so the
    # Codex correspondence and the rotation state files are still written.
    # To re-enable, restore the original expression kept immediately below.
    $shouldPrepareRotation = $false
    # $shouldPrepareRotation = (
    #     $eventName -eq "Stop" -and
    #     $null -ne $contextUsedPercentage -and
    #     $contextUsedPercentage -ge 70 -and
    #     -not $rotationReady
    # )

    if ($eventName -eq "StopFailure") {
        $bucket = "failures"
        $handoffStatus = if ($errorType -eq "rate_limit") { "waiting_for_claude_usage_reset" } else { "claude_failure_logged" }
    }
    elseif ($isRetiredGeneration) {
        $bucket = "deferred"
        $handoffStatus = "retired_claude_coordinator"
    }
    elseif ($rotationReady) {
        $bucket = "rotations"
        $handoffStatus = "claude_context_handoff_ready"
    }
    elseif ($shouldPrepareRotation) {
        $bucket = "deferred"
        $handoffStatus = "preparing_claude_context_handoff"
    }
    elseif ($backgroundCount -gt 0 -or $sessionCronCount -gt 0) {
        $bucket = "deferred"
        $handoffStatus = "background_work_pending"
    }
    else {
        $bucket = "inbox"
        $handoffStatus = "ready_for_codex_review"
    }

    $dedupeMaterial = "$eventName`n$sessionId`n$message"
    $messageHash = Get-Sha256Hex -Value $dedupeMaterial
    $hashToken = $messageHash.Substring(0, 16)
    $filename = "${timestampToken}__claude__${sessionToken}__${hashToken}.md"
    $bucketPath = Join-Path $correspondenceRoot $bucket

    # Hooks can occasionally be delivered twice. Preserve one immutable record per
    # session/event/message tuple and silently accept duplicate delivery.
    $duplicate = Get-ChildItem -LiteralPath $bucketPath -File -Filter "*__${hashToken}.md" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $duplicate) {
        if ($shouldPrepareRotation) {
            $decision = [ordered]@{
                decision = "block"
                reason = "Context use is at or above 70%. Before stopping, produce a concise but complete continuation packet: objective, verified branch and HEAD, completed work, uncommitted changes, tests and gates actually run, evidence labels, unresolved blockers, exact next action, and every live parallel worker with its task, session/agent id, status, and owned files. End the response with [CLAUDE_CONTEXT_HANDOFF_READY]. Do not continue implementation after preparing the packet."
            } | ConvertTo-Json -Compress
            [Console]::Out.WriteLine($decision)
        }
        exit 0
    }

    $cwd = [string]$event.cwd
    $gitBranch = Get-GitValue -WorkingDirectory $cwd -Arguments @("branch", "--show-current")
    $gitHead = Get-GitValue -WorkingDirectory $cwd -Arguments @("rev-parse", "HEAD")
    $gitRemote = Get-GitValue -WorkingDirectory $cwd -Arguments @("remote", "get-url", "origin")

    $metadata = [ordered]@{
        schema_version = 1
        source = "claude-code"
        hook_event = $eventName
        handoff_status = $handoffStatus
        captured_at_utc = $capturedAtText
        session_id = $sessionId
        transcript_path = [string]$event.transcript_path
        cwd = $cwd
        permission_mode = [string]$event.permission_mode
        message_sha256 = $messageHash
        context_used_percentage = $contextUsedPercentage
        context_window_size = $contextWindowSize
        context_total_input_tokens = $contextTotalInputTokens
        context_telemetry_source = $contextTelemetrySource
        background_task_count = $backgroundCount
        session_cron_count = $sessionCronCount
        error_type = $errorType
        error_details = if ($eventName -eq "StopFailure") { [string]$event.error_details } else { $null }
        git_branch = $gitBranch
        git_head = $gitHead
        git_remote = $gitRemote
    }

    $metadataJson = $metadata | ConvertTo-Json -Depth 5
    $content = @"
# Claude Code correspondence

~~~json
$metadataJson
~~~

## Message

$message
"@

    $finalPath = Join-Path $bucketPath $filename
    $temporaryPath = Join-Path $bucketPath ("." + $filename + "." + $PID + ".tmp")
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($temporaryPath, $content, $utf8WithoutBom)
    Move-Item -LiteralPath $temporaryPath -Destination $finalPath

    if ($bucket -eq "inbox") {
        $waitingState = [ordered]@{
            schema_version = 1
            session_id = $sessionId
            source_file = $filename
            message_sha256 = $messageHash
            awaiting_since_utc = $capturedAtText
        }
        $waitingPath = Join-Path $correspondenceRoot "state\claude_waiting.json"
        $temporaryWaitingPath = Join-Path $correspondenceRoot ("state\.claude_waiting." + $PID + ".tmp")
        [System.IO.File]::WriteAllText(
            $temporaryWaitingPath,
            ($waitingState | ConvertTo-Json -Depth 4),
            $utf8WithoutBom
        )
        Move-Item -Force -LiteralPath $temporaryWaitingPath -Destination $waitingPath
    }

    if ($shouldPrepareRotation) {
        $decision = [ordered]@{
            decision = "block"
            reason = "Context use is at or above 70%. Before stopping, produce a concise but complete continuation packet: objective, verified branch and HEAD, completed work, uncommitted changes, tests and gates actually run, evidence labels, unresolved blockers, exact next action, and every live parallel worker with its task, session/agent id, status, and owned files. End the response with [CLAUDE_CONTEXT_HANDOFF_READY]. Do not continue implementation after preparing the packet."
        } | ConvertTo-Json -Compress
        [Console]::Out.WriteLine($decision)
    }
    elseif ($rotationReady) {
        $notice = [ordered]@{
            systemMessage = "Claude context handoff is ready. The automatic successor hook is launching a fresh coordinating generation. Use /clear only if state/claude_generation_launch_failure.json reports recovery is needed."
        } | ConvertTo-Json -Compress
        [Console]::Out.WriteLine($notice)
    }
}
catch {
    # A logging failure must never alter Claude's response or trap it in a Stop loop.
    try {
        $errorDirectory = Join-Path $CorrespondenceRoot "hook-errors"
        [void](New-Item -ItemType Directory -Force -Path $errorDirectory)
        $errorFile = Join-Path $errorDirectory ([DateTime]::UtcNow.ToString("yyyyMMddTHHmmssfffZ") + "__hook-error.log")
        $errorText = $_ | Out-String
        [System.IO.File]::WriteAllText($errorFile, $errorText)
    }
    catch {
        # Deliberately swallow secondary logging errors.
    }
}

exit 0
