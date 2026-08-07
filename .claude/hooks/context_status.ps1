[CmdletBinding()]
param()

# Claude Code status-line command. Records exact context usage without consuming tokens.

$ErrorActionPreference = "SilentlyContinue"
$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) {
    Write-Output "Claude context: --"
    exit 0
}

$data = $raw | ConvertFrom-Json
$used = $data.context_window.used_percentage
$remaining = $data.context_window.remaining_percentage
$model = [string]$data.model.display_name
$sessionId = [string]$data.session_id
$transcriptPath = [string]$data.transcript_path
$correspondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence"
$stateDirectory = Join-Path $correspondenceRoot "state"
[void](New-Item -ItemType Directory -Force -Path $stateDirectory)

$state = [ordered]@{
    schema_version = 1
    updated_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    session_id = $sessionId
    transcript_path = $transcriptPath
    model = $model
    used_percentage = $used
    remaining_percentage = $remaining
    context_window_size = $data.context_window.context_window_size
    five_hour_rate_limit_used_percentage = $data.rate_limits.five_hour.used_percentage
    five_hour_rate_limit_resets_at = $data.rate_limits.five_hour.resets_at
    seven_day_rate_limit_used_percentage = $data.rate_limits.seven_day.used_percentage
    seven_day_rate_limit_resets_at = $data.rate_limits.seven_day.resets_at
}

$statePath = Join-Path $stateDirectory "claude_context.json"
$temporaryPath = Join-Path $stateDirectory (".claude_context." + $PID + ".tmp")
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($temporaryPath, ($state | ConvertTo-Json -Depth 5), $utf8WithoutBom)
Move-Item -Force -LiteralPath $temporaryPath -Destination $statePath

if ($null -eq $used) {
    Write-Output "[$model] context --"
}
elseif ([double]$used -ge 70) {
    Write-Output ("[{0}] context {1:N0}% - handoff at next stop" -f $model, [double]$used)
}
else {
    Write-Output ("[{0}] context {1:N0}%" -f $model, [double]$used)
}

exit 0
