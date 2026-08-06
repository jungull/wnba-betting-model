<#
D032/D033 INJURY_OFFICIAL/live -- network-fetch half of the capture cycle.

Split out from capture_injury_official.py because this sandbox's egress
policy resets connections made via Python's requests/urllib3 (observed,
reproducible, ConnectionResetError 10054 on every probe) while
Invoke-WebRequest -UseBasicParsing (WinHTTP-backed) succeeds cleanly against
the same host. This script owns ONLY the network fetch + raw archival; all
parsing, entity resolution and CSV writing stays in capture_injury_official.py
so there is exactly one parser implementation, not two.

Access posture: single polite client, 1 request in flight, >=1s spacing,
honest User-Agent with a contact address. Walks back in 15-minute steps
(bounded, LookbackHours) from the current US/Eastern quarter-hour slot until
a real report PDF is found. If the host ever returns a bot-detection-shaped
response (403 from a Cloudflare/PerimeterX-style challenge), this script
reports it to stderr and STOPS -- it never retries with a different identity
to evade.

Output: writes the raw PDF verbatim to raw/wnba_official_<captureUtc>.pdf and
prints one JSON line to stdout:
  {"raw_path":..., "source_url":..., "url_slot_ts_et":..., "capture_id":...,
   "retrieval_ts_utc":...}
capture_injury_official.py --from-fetch <that JSON> consumes it.
#>

param(
    [int]$LookbackHours = 6
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$rawDir = Join-Path $here "raw"
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

$headers = @{
    "User-Agent" = "wnba-betting-model-research/1.0 market_intelligence INJURY_OFFICIAL live capture (contact: jgallagher@sasscpas.com; polite client, 1 request in flight, >=1s spacing)"
}

# US/Eastern "now", DST-aware via .NET's own TZ database.
$utcNow = [DateTime]::UtcNow
try {
    $etZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
    $etNow = [System.TimeZoneInfo]::ConvertTimeFromUtc($utcNow, $etZone)
} catch {
    # Fallback if the Windows TZ id is unavailable: fixed EDT offset.
    $etNow = $utcNow.AddHours(-4)
}
$minuteFloor = [Math]::Floor($etNow.Minute / 15) * 15
$slotDt = New-Object DateTime($etNow.Year, $etNow.Month, $etNow.Day, $etNow.Hour, [int]$minuteFloor, 0)

function Slot-Label([DateTime]$dt) {
    $h = $dt.Hour % 12
    if ($h -eq 0) { $h = 12 }
    $ap = if ($dt.Hour -lt 12) { "AM" } else { "PM" }
    return "{0:D2}_{1:D2}{2}" -f $h, $dt.Minute, $ap
}

$found = $false
$foundUrl = $null
$foundSlot = $null
$maxSteps = $LookbackHours * 4
for ($i = 0; $i -lt $maxSteps; $i++) {
    $dateStr = $slotDt.ToString("yyyy-MM-dd")
    $slotStr = Slot-Label $slotDt
    $url = "https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_${dateStr}_${slotStr}.pdf"
    try {
        $r = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 15 -UseBasicParsing -Headers $headers
        $server = $r.Headers["Server"]
        if ($r.StatusCode -eq 403 -and ($server -match "cloudflare")) {
            Write-Error "BOT-BLOCK DETECTED at $url (status=403, server=$server) -- STOPPING, not bypassing, per standing rules."
            exit 2
        }
        if ($r.StatusCode -eq 200) {
            $found = $true
            $foundUrl = $url
            $foundSlot = $slotDt
            break
        }
    } catch {
        $resp = $_.Exception.Response
        if ($resp -and ([int]$resp.StatusCode -eq 403)) {
            $srv = $resp.Headers["Server"]
            if ($srv -match "cloudflare") {
                Write-Error "BOT-BLOCK DETECTED at $url (status=403, server=$srv) -- STOPPING, not bypassing, per standing rules."
                exit 2
            }
        }
        # plain miss (404) or transient error: keep walking back
    }
    Start-Sleep -Seconds 1
    $slotDt = $slotDt.AddMinutes(-15)
}

if (-not $found) {
    Write-Error "no official report found in the last $LookbackHours h walk-back"
    exit 1
}

Start-Sleep -Seconds 1
$getResp = Invoke-WebRequest -Uri $foundUrl -Method Get -TimeoutSec 30 -UseBasicParsing -Headers $headers
$retrievalUtc = [DateTime]::UtcNow
$captureId = $retrievalUtc.ToString("yyyyMMddTHHmmssZ")
$rawPath = Join-Path $rawDir "wnba_official_$captureId.pdf"
[System.IO.File]::WriteAllBytes($rawPath, $getResp.Content)

$out = [ordered]@{
    raw_path         = $rawPath
    source_url       = $foundUrl
    url_slot_ts_et   = $foundSlot.ToString("yyyy-MM-ddTHH:mm:00")
    capture_id       = $captureId
    retrieval_ts_utc = $retrievalUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
}
$out | ConvertTo-Json -Compress
