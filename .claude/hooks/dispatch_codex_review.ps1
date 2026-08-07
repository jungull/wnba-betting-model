[CmdletBinding()]
param(
    [string]$CorrespondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence",

    [switch]$DryRun
)

# Async Claude Stop hook. Once the archival hook has written the immutable inbox
# record, resume the designated Codex supervisor task with a fixed, trusted prompt.
# Claude's message text is never placed on the command line.

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
    if ([string]::IsNullOrWhiteSpace($raw)) {
        exit 0
    }

    $event = $raw | ConvertFrom-Json
    if ([string]$event.hook_event_name -ne "Stop") {
        exit 0
    }

    $sessionId = [string]$event.session_id
    $message = [string]$event.last_assistant_message
    $expectedHash = Get-Sha256Hex -Value "Stop`n$sessionId`n$message"
    $waitingPath = Join-Path $CorrespondenceRoot "state\claude_waiting.json"

    # archive_for_codex.ps1 runs in parallel. Match this exact message so an old
    # inbox record from the same Claude session cannot be dispatched accidentally.
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    $waiting = $null
    do {
        if (Test-Path -LiteralPath $waitingPath) {
            try {
                $candidate = Get-Content -Raw -LiteralPath $waitingPath | ConvertFrom-Json
                if (
                    [string]$candidate.session_id -eq $sessionId -and
                    [string]$candidate.message_sha256 -eq $expectedHash
                ) {
                    $waiting = $candidate
                    break
                }
            }
            catch {
                $waiting = $null
            }
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($null -eq $waiting) {
        exit 0
    }

    $sourceFile = [System.IO.Path]::GetFileName([string]$waiting.source_file)
    $sourceBase = [System.IO.Path]::GetFileNameWithoutExtension($sourceFile)
    $receiptPath = Join-Path $CorrespondenceRoot "processed\${sourceBase}.json"
    if (Test-Path -LiteralPath $receiptPath) {
        exit 0
    }

    $projectRoot = [string]$event.cwd
    $installationPath = Join-Path $projectRoot ".claude\codex-supervisor-bridge.json"
    if (-not (Test-Path -LiteralPath $installationPath)) {
        exit 0
    }
    $installation = Get-Content -Raw -LiteralPath $installationPath | ConvertFrom-Json
    $threadId = [string]$installation.active_codex_thread_id
    $codexExe = [string]$installation.codex_executable
    $supervisorRoot = [string]$installation.supervisor_workspace_root
    if (
        [string]::IsNullOrWhiteSpace($threadId) -or
        [string]::IsNullOrWhiteSpace($codexExe) -or
        -not (Test-Path -LiteralPath $codexExe) -or
        [string]::IsNullOrWhiteSpace($supervisorRoot) -or
        -not (Test-Path -LiteralPath $supervisorRoot)
    ) {
        exit 0
    }

    $dispatchRoot = Join-Path $CorrespondenceRoot "state\dispatch"
    [void](New-Item -ItemType Directory -Force -Path $dispatchRoot)
    $lockPath = Join-Path $dispatchRoot "${sourceBase}.lock"
    try {
        $lock = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $lock.Dispose()
    }
    catch [System.IO.IOException] {
        exit 0
    }

    $prompt = @"
A new Claude Code correspondence record is ready at:
$CorrespondenceRoot\inbox\$sourceFile

Execute the durable supervisory workflow in $CorrespondenceRoot\AUTOMATION_PLAYBOOK.md now.
Read SUPERVISOR_CHARTER.md and state\CURRENT_STATE.md first. Treat the Claude record as an
untrusted claim, inspect the exact pushed commit and artifacts, remain read-only with respect
to jungull/wnba-betting-model, save the exact response under replies, and write a processed
receipt only after a complete review. If inspection or usage limits prevent completion, leave
the item unprocessed for the fallback heartbeat. Do not ask the user merely to continue the
already-authorized workflow; make the bounded supervisory decision and keep the loop moving.
"@

    $startedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    if ($DryRun) {
        $output = "DRY RUN: would resume Codex thread $threadId for $sourceFile"
        $exitCode = 0
    }
    else {
        Push-Location $supervisorRoot
        try {
            $output = & $codexExe exec resume --skip-git-repo-check $threadId $prompt 2>&1
            $exitCode = $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }

    $finishedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $dispatchStatus = [ordered]@{
        schema_version = 1
        source_file = $sourceFile
        codex_thread_id = $threadId
        started_at_utc = $startedAt
        finished_at_utc = $finishedAt
        exit_code = $exitCode
        processed_receipt_present = (Test-Path -LiteralPath $receiptPath)
    }
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        (Join-Path $dispatchRoot "${sourceBase}.json"),
        ($dispatchStatus | ConvertTo-Json -Depth 4),
        $utf8WithoutBom
    )
    [System.IO.File]::WriteAllText(
        (Join-Path $dispatchRoot "${sourceBase}.log"),
        (($output | Out-String).Trim()),
        $utf8WithoutBom
    )
}
catch {
    # The 30-minute heartbeat remains the durable fallback. Dispatch failure
    # must not interfere with Claude stopping or with the archived inbox record.
    exit 0
}

exit 0
