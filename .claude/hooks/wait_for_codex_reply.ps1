[CmdletBinding()]
param(
    [string]$CorrespondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence",

    [ValidateRange(1, 3600)]
    [int]$PollSeconds = 300,

    [ValidateRange(0.01, 48)]
    [double]$MaxHours = 24
)

# Async Claude Code hook. It waits for the Codex heartbeat to save a reply,
# then exits 2 so asyncRewake delivers the path to Claude and starts a turn.

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

function Wait-ForReplyChange {
    param([string]$Directory, [int]$FallbackSeconds)

    # FileSystemWatcher provides the normal event-driven path. WaitForChanged
    # also has a bounded timeout, so dropped OneDrive/Windows events fall back
    # to the existing periodic directory scan without spinning.
    try {
        $watcher = New-Object System.IO.FileSystemWatcher($Directory, "*.md")
        $watcher.IncludeSubdirectories = $false
        $watcher.NotifyFilter = (
            [System.IO.NotifyFilters]::FileName -bor
            [System.IO.NotifyFilters]::LastWrite -bor
            [System.IO.NotifyFilters]::CreationTime
        )
        $watcher.EnableRaisingEvents = $true
        try {
            [void]$watcher.WaitForChanged(
                [System.IO.WatcherChangeTypes]::All,
                $FallbackSeconds * 1000
            )
        }
        finally {
            $watcher.Dispose()
        }
    }
    catch {
        Start-Sleep -Seconds $FallbackSeconds
    }
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

    $sessionId = [string]$event.session_id
    $message = [string]$event.last_assistant_message
    $expectedHash = if ($eventName -eq "Stop") {
        Get-Sha256Hex -Value "$eventName`n$sessionId`n$message"
    }
    else {
        $null
    }

    $root = $CorrespondenceRoot
    $stateRoot = Join-Path $root "state"
    $waitingPath = Join-Path $stateRoot "claude_waiting.json"
    $activePath = Join-Path $stateRoot "claude_active_reply.json"
    $deliveryRoot = Join-Path $stateRoot "delivery-receipts"
    [void](New-Item -ItemType Directory -Force -Path $deliveryRoot)

    # The archival hook runs in parallel. For a normal Stop, wait briefly for
    # the state record matching this exact message rather than latching onto an
    # older record from the same session.
    $stateDeadline = [DateTime]::UtcNow.AddSeconds(30)
    $waiting = $null
    do {
        if (Test-Path -LiteralPath $waitingPath) {
            try {
                $candidate = Get-Content -Raw -LiteralPath $waitingPath | ConvertFrom-Json
                $sessionMatches = [string]$candidate.session_id -eq $sessionId
                $messageMatches = ($null -eq $expectedHash) -or ([string]$candidate.message_sha256 -eq $expectedHash)
                if ($sessionMatches -and $messageMatches) {
                    $waiting = $candidate
                    break
                }
            }
            catch {
                $waiting = $null
            }
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $stateDeadline)

    # A rate-limit StopFailure has no new inbox item. It should keep monitoring
    # the prior request for this session, if one exists.
    if ($null -eq $waiting -and $eventName -eq "StopFailure" -and (Test-Path -LiteralPath $waitingPath)) {
        try {
            $candidate = Get-Content -Raw -LiteralPath $waitingPath | ConvertFrom-Json
            if ([string]$candidate.session_id -eq $sessionId) {
                $waiting = $candidate
            }
        }
        catch {
            $waiting = $null
        }
    }
    if ($null -eq $waiting) {
        exit 0
    }

    $sourceFile = [string]$waiting.source_file
    $sourceLeaf = [System.IO.Path]::GetFileName($sourceFile)
    $deadline = [DateTime]::UtcNow.AddHours($MaxHours)

    while ([DateTime]::UtcNow -lt $deadline) {
        # A newer Claude message supersedes this watcher.
        try {
            $currentWaiting = Get-Content -Raw -LiteralPath $waitingPath | ConvertFrom-Json
            if (
                [string]$currentWaiting.session_id -ne $sessionId -or
                [string]$currentWaiting.source_file -ne $sourceFile
            ) {
                exit 0
            }
        }
        catch {
            Wait-ForReplyChange -Directory (Join-Path $root "replies") -FallbackSeconds $PollSeconds
            continue
        }

        $reply = Get-ChildItem -LiteralPath (Join-Path $root "replies") -File -Filter "*.md" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*__reply-to__${sourceLeaf}*" } |
            Sort-Object LastWriteTimeUtc |
            Select-Object -Last 1

        if ($null -ne $reply) {
            $replyToken = (Get-Sha256Hex -Value $reply.Name).Substring(0, 16)
            $deliveredPath = Join-Path $deliveryRoot "${replyToken}.json"
            if (Test-Path -LiteralPath $deliveredPath) {
                exit 0
            }

            $mayWake = $true
            if (Test-Path -LiteralPath $activePath) {
                try {
                    $active = Get-Content -Raw -LiteralPath $activePath | ConvertFrom-Json
                    if (
                        [string]$active.session_id -eq $sessionId -and
                        [string]$active.reply_file -eq $reply.Name
                    ) {
                        $lastWake = [DateTime]::Parse([string]$active.wake_requested_at_utc).ToUniversalTime()
                        $mayWake = [DateTime]::UtcNow -ge $lastWake.AddMinutes(30)
                    }
                }
                catch {
                    $mayWake = $true
                }
            }

            if ($mayWake) {
                $activeReply = [ordered]@{
                    schema_version = 1
                    session_id = $sessionId
                    source_file = $sourceFile
                    reply_file = $reply.Name
                    wake_requested_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
                }
                $temporaryActivePath = Join-Path $stateRoot (".claude_active_reply." + $PID + ".tmp")
                $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
                [System.IO.File]::WriteAllText(
                    $temporaryActivePath,
                    ($activeReply | ConvertTo-Json -Depth 4),
                    $utf8WithoutBom
                )
                Move-Item -Force -LiteralPath $temporaryActivePath -Destination $activePath

                [Console]::Error.WriteLine(
                    "Codex supervisor response is ready at $($reply.FullName). Read it in full, verify its referenced repository state, and act on it. Do not resend the prior handoff unchanged. If it requires no code change, report the requested evidence or clarification."
                )
                exit 2
            }
        }

        Wait-ForReplyChange -Directory (Join-Path $root "replies") -FallbackSeconds $PollSeconds
    }
}
catch {
    # A watcher failure is advisory. Archive logging remains the durable path.
    exit 0
}

exit 0
