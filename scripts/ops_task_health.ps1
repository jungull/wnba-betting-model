# Health check across every WNBA scheduled task, after today's conversion of all 16 to a
# windowless launcher (D148) plus the new board-refresh task.
#
# WHY: 16 tasks were changed and only 3 were verified by running them. A conversion that
# silently broke a job would show up as missing data days later, which is exactly the kind
# of failure that is cheap to find now and expensive to find then.
#
# Reports, per task: how it launches, its last exit code, when it last ran, and whether its
# OUTPUT is actually recent -- because a task can exit 0 and still write nothing.

$ErrorActionPreference = 'Stop'
$now = Get-Date

# task -> a path whose freshness proves the task did work
$evidence = @{
  'WNBA_OddsCapture'           = 'C:\Users\jgallagher\wnba-betting-model\data\odds_capture'
  'WNBA_PropsCapture_1'        = 'C:\Users\jgallagher\wnba-betting-model\data\props_capture'
  'WNBA_PropsCapture_2'        = 'C:\Users\jgallagher\wnba-betting-model\data\props_capture'
  'WNBA_PropsCapture_3'        = 'C:\Users\jgallagher\wnba-betting-model\data\props_capture'
  'WNBA_PropsCapture_4'        = 'C:\Users\jgallagher\wnba-betting-model\data\props_capture'
  'WNBA_InjuryLive'            = 'C:\Users\jgallagher\wnba-betting-model\logs\injury_live'
  'WNBA_InjuryCapture'         = 'C:\Users\jgallagher\wnba-betting-model\data\injury_capture'
  'WNBA_MarketLadder'          = 'C:\Users\jgallagher\wnba-betting-model\logs\market_ladder'
  'WNBA_SxBetCapture'          = 'C:\Users\jgallagher\wnba-betting-model\logs\sxbet'
  'WNBA_NewsCapture'           = 'C:\Users\jgallagher\wnba-betting-model\data\news_capture'
  'WNBA_RefAssignments'        = 'C:\Users\jgallagher\wnba-betting-model\data\ref_assignments'
  'WNBA_OpportunityBoard'      = 'C:\Users\jgallagher\wnba-betting-model\logs\board'
  'WNBA prospective pair'      = 'C:\Users\jgallagher\wnba-betting-model\forecasts\runner_logs'
  'WNBA_DailyForecast_AM'      = 'C:\Users\jgallagher\wnba-betting-model\forecasts'
  'WNBA_DailyForecast_PM'      = 'C:\Users\jgallagher\wnba-betting-model\forecasts'
  'WNBA_DailyRefresh'          = 'C:\Users\jgallagher\wnba-betting-model\data'
  'WNBA_ReplyDeliveryWatchdog' = $null
}

function Newest-Age($path) {
  if (-not $path -or -not (Test-Path $path)) { return $null }
  $item = Get-Item $path
  if ($item.PSIsContainer) {
    $f = Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $f) { return $null }
    return [math]::Round((New-TimeSpan -Start $f.LastWriteTime -End $now).TotalHours, 1)
  }
  return [math]::Round((New-TimeSpan -Start $item.LastWriteTime -End $now).TotalHours, 1)
}

$rows = Get-ScheduledTask | Where-Object { $_.TaskName -match '^WNBA' } | ForEach-Object {
  $n = $_.TaskName
  $a = $_.Actions | Select-Object -First 1
  $i = Get-ScheduledTaskInfo -TaskName $n
  $lastRunH = if ($i.LastRunTime -and $i.LastRunTime.Year -gt 1999) {
      [math]::Round((New-TimeSpan -Start $i.LastRunTime -End $now).TotalHours, 1) } else { $null }
  $outH = Newest-Age $evidence[$n]

  $flags = @()
  if ($a.Execute -notmatch 'wscript') { $flags += 'VISIBLE-WINDOW' }
  if ($i.LastTaskResult -ne 0)        { $flags += "EXIT=$($i.LastTaskResult)" }
  if ($null -eq $lastRunH)            { $flags += 'NEVER-RAN' }
  elseif ($lastRunH -gt 26)           { $flags += 'STALE-RUN' }
  if ($null -ne $outH -and $outH -gt 30) { $flags += 'STALE-OUTPUT' }

  [PSCustomObject]@{
    Task       = $n
    Launch     = if ($a.Execute -match 'wscript') { 'hidden' } else { 'VISIBLE' }
    Exit       = $i.LastTaskResult
    RanHrsAgo  = $lastRunH
    OutputHrs  = $outH
    Flags      = ($flags -join ' ')
  }
}

$rows | Sort-Object Task | Format-Table -AutoSize

$bad = $rows | Where-Object { $_.Flags }
Write-Host ""
if ($bad) {
  Write-Host ("  {0} task(s) need attention:" -f $bad.Count) -ForegroundColor Yellow
  $bad | ForEach-Object { Write-Host ("    {0,-28} {1}" -f $_.Task, $_.Flags) -ForegroundColor Yellow }
} else {
  Write-Host "  ALL TASKS HEALTHY: launching hidden, exiting 0, and producing recent output." -ForegroundColor Green
}
Write-Host ""
Write-Host "  Note: a daily task legitimately shows a larger RanHrsAgo than a 10-minute one."
Write-Host "  STALE-OUTPUT is the flag that matters -- it means the job ran and wrote nothing."
