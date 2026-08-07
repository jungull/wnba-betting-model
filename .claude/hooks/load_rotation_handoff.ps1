[CmdletBinding()]
param()

# SessionStart(clear) hook. Points the fresh session to the newest continuation packet.

$ErrorActionPreference = "SilentlyContinue"
$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) {
    exit 0
}

$event = $raw | ConvertFrom-Json
if ([string]$event.source -ne "clear") {
    exit 0
}

$correspondenceRoot = "C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff\correspondence"
$rotationDirectory = Join-Path $correspondenceRoot "rotations"
$stateDirectory = Join-Path $correspondenceRoot "state"
[void](New-Item -ItemType Directory -Force -Path $stateDirectory)

$rotation = Get-ChildItem -LiteralPath $rotationDirectory -File -Filter "*.md" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTimeUtc -Descending |
    Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $stateDirectory ($_.BaseName + ".loaded.json")))
    } |
    Select-Object -First 1

if ($null -eq $rotation) {
    exit 0
}

$receipt = [ordered]@{
    schema_version = 1
    loaded_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    new_session_id = [string]$event.session_id
    rotation_file = $rotation.FullName
}
$receiptPath = Join-Path $stateDirectory ($rotation.BaseName + ".loaded.json")
[System.IO.File]::WriteAllText(
    $receiptPath,
    ($receipt | ConvertTo-Json -Depth 3),
    (New-Object System.Text.UTF8Encoding($false))
)

[Console]::Out.WriteLine(@"
This is a fresh-context continuation of the prior Claude Code session.
Read the continuation packet at:
$($rotation.FullName)

Resume from its exact next action. Re-read committed files and current git state rather than
assuming the packet's claims are correct. Do not repeat completed work, weaken evidence labels,
or start an experiment that the packet says remains blocked.
"@)

exit 0
