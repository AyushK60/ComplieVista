# CompileVista one-click Stop (M8-G0).
# Gracefully stops ONLY what this launcher started and can verify by recorded
# identity (WSL pid + cmdline + cwd). Reused/externally-owned servers are NEVER
# killed. Idempotent: safe to run repeatedly, or when nothing was ever started.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "cv-common.ps1")

try {
    $roots = Get-CvRoots
    $statePath = Join-Path $roots.StateDir "state.json"
    $stopLock = Join-Path $roots.StateDir "stop.lock"

    if (-not (New-CvLock -Path $stopLock)) {
        Write-CvErr "Another Start/Stop launcher is already running."
        exit 1
    }
    try {
        $state = Read-CvState -Path $statePath
        if (-not $state) {
            Write-CvOk "No launcher state found - CompileVista was not started by Start.cmd (or already stopped). Nothing to do."
            exit 0
        }
        Write-Host "Stopping CompileVista session $($state.run_id) (started $($state.started_utc), commit $($state.commit))..."

        foreach ($svc in @("backend", "frontend")) {
            $entry = $state.$svc
            if (-not $entry) { continue }
            $name = $entry.ownership
            if ($name -eq "reused") {
                Write-CvWarn "${svc}: EXTERNALLY OWNED / REUSED (pid $($entry.pid)) - left running by design."
                continue
            }
            $info = Get-WslProcInfo -ProcId ([int]$entry.pid)
            if (-not $info) {
                Write-CvOk "${svc}: pid $($entry.pid) is already gone."
                continue
            }
            # Identity check before ANY kill: recorded cmdline must still match
            # AND the process must still live in this repo. Pid reuse => no kill.
            $cmdlineMatches = ($info.Cmdline -eq $entry.cmdline)
            $cwdOk = $info.Cwd -and $info.Cwd.StartsWith($state.repo_wsl)
            if (-not ($cmdlineMatches -and $cwdOk)) {
                Write-CvWarn ("${svc}: pid $($entry.pid) exists but its identity changed " +
                              "(now: '$($info.Cmdline)' in '$($info.Cwd)') - NOT killing (stale PID protection). " +
                              "Verify manually if this is unexpected.")
                continue
            }
            # The REAL process group comes from /proc (a vite listener's group
            # is its npm leader's pid, not its own - reproduced M8-G0).
            $pgid = Get-WslProcPgid -ProcId ([int]$entry.pid)
            Write-CvStep "${svc}: stopping process group $pgid (pid $($entry.pid))..."
            [void](Invoke-Wsl -ShCommand "kill -TERM -$pgid 2>/dev/null; kill -TERM $($entry.pid) 2>/dev/null; true" -TimeoutSec 20)
            $gone = $false
            for ($i = 0; $i -lt 20; $i++) {
                Start-Sleep -Milliseconds 500
                if (-not (Get-WslProcInfo -ProcId ([int]$entry.pid))) { $gone = $true; break }
            }
            if (-not $gone) {
                Write-CvWarn "${svc}: still alive after TERM - sending KILL to the group."
                [void](Invoke-Wsl -ShCommand "kill -KILL -$pgid 2>/dev/null; kill -KILL $($entry.pid) 2>/dev/null; true" -TimeoutSec 20)
                Start-Sleep -Seconds 1
            }
            if (Get-WslProcInfo -ProcId ([int]$entry.pid)) {
                Write-CvErr "${svc}: could not verify termination of pid $($entry.pid). Check manually: ss -ltnp | grep :$($entry.port)"
            } else {
                Write-CvOk "${svc}: stopped (port $($entry.port) released)."
            }
        }

        # Sweep our two ports: kill ONLY leftovers that are verifiably our own
        # uvicorn/vite in this repo (covers the npm-leader vs vite-listener case).
        foreach ($probe in @(
            @{ Port = $script:BackendPort; Needle = "uvicorn" },
            @{ Port = $script:FrontendPort; Needle = "vite" })) {
            $lpid = Get-WslListenerPid -Port $probe.Port
            if (-not $lpid) { continue }
            $li = Get-WslProcInfo -ProcId $lpid
            if (Test-IsOurProc -Info $li -WslRoot $roots.WslRoot -Needle $probe.Needle) {
                $lpgid = Get-WslProcPgid -ProcId $lpid
                Write-CvStep "port $($probe.Port): stopping leftover $($probe.Needle) group $lpgid (pid $lpid)..."
                [void](Invoke-Wsl -ShCommand "kill -TERM -$lpgid 2>/dev/null; kill -TERM $lpid 2>/dev/null; true" -TimeoutSec 20)
                Start-Sleep -Seconds 2
                if (Get-WslProcInfo -ProcId $lpid) {
                    [void](Invoke-Wsl -ShCommand "kill -KILL -$lpgid 2>/dev/null; kill -KILL $lpid 2>/dev/null; true" -TimeoutSec 20)
                }
                Write-CvOk "port $($probe.Port): leftover stopped."
            } else {
                Write-CvWarn "port $($probe.Port): occupied by a NON-CompileVista process (pid $lpid) - left untouched."
            }
        }

        Remove-Item -Force $statePath -ErrorAction SilentlyContinue
        Remove-Item -Force (Join-Path $roots.StateDir "backend.pid"), (Join-Path $roots.StateDir "frontend.pid") -ErrorAction SilentlyContinue
        Write-CvOk "Launcher state cleared. Docker Desktop and unrelated containers/processes were left untouched."
        Write-CvOk "Execution containers (cv-*) are short-lived; the backend removes leftovers itself on next start."
    } finally {
        Remove-CvLock -Path $stopLock
    }
} catch {
    Write-CvErr $_.Exception.Message
    exit 1
}
exit 0
