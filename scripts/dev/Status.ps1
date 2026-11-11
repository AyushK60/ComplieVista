# CompileVista Status (Stage 8). Honest reporting only - no false green states.
$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "cv-common.ps1")

$roots = Get-CvRoots
$statePath = Join-Path $roots.StateDir "state.json"
$state = Read-CvState -Path $statePath

Write-Host "CompileVista local status"
Write-Host " repo:  $($roots.WinRoot)"

$d = Invoke-Wsl -ShCommand "docker info --format ok" -TimeoutSec 30
if ($d.ExitCode -eq 0 -and $d.StdOut.Trim() -eq "ok") {
    Write-CvOk "Docker engine: running"
} else {
    Write-CvWarn "Docker engine: NOT available (executions will report BLOCKED)"
}

$backendHealth = "http://127.0.0.1:$script:BackendPort/api/v1/health"
$frontendUrl = "http://127.0.0.1:$script:FrontendPort/"
$bOk = Test-CvHealth -Url $backendHealth
$fOk = Test-CvHealth -Url $frontendUrl

if ($state) {
    Write-Host " session $($state.run_id) started $($state.started_utc) (commit $($state.commit))"
    foreach ($svc in @("backend", "frontend")) {
        $e = $state.$svc
        if (-not $e) { continue }
        $live = Get-WslProcInfo -ProcId ([int]$e.pid)
        $liveTxt = if ($live) { "pid $($e.pid) alive" } else { "pid $($e.pid) NOT running" }
        Write-Host ("  {0,-9} {1,-9} port {2,-5} {3}" -f $svc, $e.ownership, $e.port, $liveTxt)
    }
} else {
    Write-CvWarn "No launcher state (Start.cmd has not been used here, or Stop.cmd already ran)."
}

if ($bOk) { Write-CvOk "Backend:  HEALTHY  $backendHealth" } else { Write-CvWarn "Backend:  not responding  $backendHealth" }
if ($fOk) { Write-CvOk "Frontend: HEALTHY  $frontendUrl" } else { Write-CvWarn "Frontend: not responding  $frontendUrl" }
exit 0
