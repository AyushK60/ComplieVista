# CompileVista one-click Start (M8-G0).
# Double-click entrypoint: Start.cmd -> this script. No admin, no execution-policy change.
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "cv-common.ps1")

$fail = $false
try {
    $roots = Get-CvRoots
    New-Item -ItemType Directory -Force -Path $roots.StateDir, $roots.LogDir | Out-Null
    $statePath = Join-Path $roots.StateDir "state.json"
    $startLock = Join-Path $roots.StateDir "start.lock"

    Write-Host "=============================================="
    Write-Host " CompileVista local start"
    Write-Host " repo: $($roots.WinRoot)"
    Write-Host "=============================================="

    if (-not (New-CvLock -Path $startLock)) {
        Write-CvErr "Another Start/Stop launcher is already running (lock: $startLock)."
        exit 1
    }
    try {
        # ---- 1. WSL distro ----
        Write-CvStep "Checking WSL distro $script:WslDistro..."
        $wsl = Invoke-Wsl -ShCommand "echo ok" -TimeoutSec 45
        if ($wsl.ExitCode -ne 0) {
            throw "WSL distro '$script:WslDistro' is not available. Install/Start it (wsl -d $script:WslDistro), then run Start again."
        }
        Write-CvOk "WSL ready."

        # ---- 2. Docker engine ----
        Write-CvStep "Checking Docker engine (WSL)..."
        $d = Invoke-Wsl -ShCommand "docker info --format ok" -TimeoutSec 60
        if ($d.ExitCode -ne 0 -or $d.StdOut.Trim() -ne "ok") {
            $ddExe = @("$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
                       "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe") |
                     Where-Object { Test-Path $_ } | Select-Object -First 1
            if ($ddExe) {
                Write-CvWarn "Docker daemon not reachable - launching Docker Desktop (user-level)..."
                Start-Process -FilePath $ddExe | Out-Null
                $ready = $false
                for ($i = 0; $i -lt 36; $i++) {
                    Start-Sleep -Seconds 5
                    $d = Invoke-Wsl -ShCommand "docker info --format ok" -TimeoutSec 30
                    if ($d.ExitCode -eq 0 -and $d.StdOut.Trim() -eq "ok") { $ready = $true; break }
                }
                if (-not $ready) {
                    throw "Docker Desktop was started but the engine is still not ready after ~3 minutes. Open Docker Desktop, wait for it to say 'Running', then run Start again."
                }
            } else {
                throw "Docker engine unavailable and Docker Desktop not found at $ddExe. Start Docker Desktop manually, then run Start again."
            }
        }
        Write-CvOk "Docker engine ready."

        # ---- 3. Pinned execution images (reuse; build ONLY if missing, logged) ----
        $images = [ordered]@{
            "compilevista/analyzer:m2" = "$($roots.WslRoot)/sandbox/analyzer"
            "compilevista/runtime:m4"  = "$($roots.WslRoot)/sandbox/runtime"
            "compilevista/debug:m5"    = "$($roots.WslRoot)/sandbox/debug"
        }
        $imageIds = @{}
        foreach ($tag in $images.Keys) {
            $r = Invoke-Wsl -ShCommand "docker image inspect -f '{{.Id}}' $tag" -TimeoutSec 30
            if ($r.ExitCode -eq 0 -and $r.StdOut.Trim().StartsWith("sha256:")) {
                $imageIds[$tag] = $r.StdOut.Trim()
                Write-CvOk "Image present: $tag"
            } else {
                Write-CvWarn "Image $tag MISSING - building it locally from the repo Dockerfile (this is logged explicitly)..."
                $b = Invoke-Wsl -ShCommand "docker build -t $tag $($images[$tag])" -TimeoutSec 900
                if ($b.ExitCode -ne 0) {
                    throw "Failed to build $tag from $($images[$tag]). Error: $($b.StdErr.Substring(0, [Math]::Min(300, $b.StdErr.Length)))"
                }
                $r = Invoke-Wsl -ShCommand "docker image inspect -f '{{.Id}}' $tag" -TimeoutSec 30
                if (-not ($r.ExitCode -eq 0 -and $r.StdOut.Trim().StartsWith("sha256:"))) {
                    throw "Image $tag still unresolvable after build."
                }
                $imageIds[$tag] = $r.StdOut.Trim()
                Write-CvOk "Image built: $tag"
            }
        }

        # ---- 4. Backend (port-ownership safe) ----
        $backendHealth = "http://127.0.0.1:$script:BackendPort/api/v1/health"
        $frontendUrl = "http://127.0.0.1:$script:FrontendPort/"
        $backend = $null
        $lpid = Get-WslListenerPid -Port $script:BackendPort
        if ($lpid) {
            $info = Get-WslProcInfo -ProcId $lpid
            if (Test-IsOurProc -Info $info -WslRoot $roots.WslRoot -Needle "uvicorn") {
                if (Test-CvHealth -Url $backendHealth) {
                    # Adopt our OWN daemon from a previous launcher run when its
                    # recorded leader pid file is alive in this repo (identity-
                    # verified); anything else is externally owned, never killed.
                    $own = $false
                    $ownLeader = 0
                    $pf = Join-Path $roots.StateDir "backend.pid"
                    if (Test-Path $pf) {
                        $pfPid = 0
                        if ([int]::TryParse((Get-Content $pf -Raw).Trim(), [ref]$pfPid)) {
                            $linfo = Get-WslProcInfo -ProcId $pfPid
                            if ($linfo -and $linfo.Cwd.StartsWith($roots.WslRoot) -and
                                ($linfo.Cmdline -like "*uvicorn*" -or $pfPid -eq $lpid)) {
                                $own = $true; $ownLeader = $pfPid
                            }
                        }
                    }
                    if ($own) {
                        Write-CvOk "Backend already running from a previous Start (leader pid $ownLeader), healthy - ADOPTING it (Stop will stop it)."
                        $linfo = Get-WslProcInfo -ProcId $ownLeader
                        $backend = @{ port = $script:BackendPort; pid = $ownLeader; pgid = $ownLeader
                                      ownership = "launched"; cmdline = $linfo.Cmdline; cwd = $linfo.Cwd }
                    } else {
                        Write-CvOk "Backend already running from this repo (pid $lpid) and healthy - REUSING it (Stop will NOT kill it)."
                        $backend = @{ port = $script:BackendPort; pid = $lpid; pgid = $lpid
                                      ownership = "reused"; cmdline = $info.Cmdline; cwd = $info.Cwd }
                    }
                } else {
                    throw ("Port $($script:BackendPort) is held by a CompileVista uvicorn (pid $lpid) that is NOT healthy. " +
                           "Restart it: run Stop.cmd, or kill pid $lpid manually, then run Start again.")
                }
            } else {
                throw ("Port $($script:BackendPort) is occupied in WSL by another process (pid ${lpid}: $($info.Cmdline)). " +
                       "This launcher never steals or kills ports it does not own. Free the port or stop that process, then run Start again.")
            }
        } else {
            if (Test-WindowsPortReallyBlocked -Port $script:BackendPort) {
                $winOwner = Get-WindowsListener -Port $script:BackendPort
                throw ("Port $($script:BackendPort) is occupied on WINDOWS by '$winOwner' [$(Get-WindowsListenerDetail -Port $script:BackendPort)] (not visible in WSL). " +
                       "This launcher never kills unrelated processes. Free the port, then run Start again.")
            }
            if (-not (Test-Path (Join-Path $roots.WinRoot "backend\.venv\bin\uvicorn"))) {
                throw "The backend environment is not installed yet. Double-click Setup.cmd once (it installs everything and checks your prerequisites), then run Start again."
            }
            Write-CvStep "Starting backend (uvicorn, 127.0.0.1:$script:BackendPort)..."
            # WSL 3.x tears down the whole session process tree when the wsl.exe
            # client exits (reproduced: plain nohup/setsid daemons died with it).
            # setsid -f double-forks the daemon out of that tree; the daemon
            # records its own pid (the launcher cannot see the grandchild pid).
            $logFile = "$($roots.WslRoot)/.local/compilevista/logs/backend.log"
            $pidFile = "$($roots.WslRoot)/.local/compilevista/backend.pid"
            $inner = 'echo $$ > ' + $pidFile + '; exec .venv/bin/uvicorn app.main:app' +
                     ' --host 127.0.0.1 --port ' + $script:BackendPort +
                     ' >> ' + $logFile + ' 2>&1'
            $bpid = 0
            $winPidFile = Join-Path $roots.StateDir "backend.pid"
            Remove-Item $winPidFile -ErrorAction SilentlyContinue  # BEFORE launch (race)
            $cmd = "cd $($roots.WslRoot)/backend && mkdir -p $($roots.WslRoot)/.local/compilevista/logs && " +
                   "setsid -f sh -c '$inner' </dev/null"
            $r = Invoke-Wsl -ShCommand $cmd -TimeoutSec 30
            if ($r.ExitCode -ne 0) {
                throw "Backend launch failed: $($r.StdErr)"
            }
            # Poll THROUGH WSL: Windows-side directory caching on /mnt/e (9P)
            # can hide a freshly created pid file from Test-Path (observed).
            $rawPid = ""
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 500
                $rawPid = (Invoke-Wsl -ShCommand "cat $pidFile 2>/dev/null" -TimeoutSec 10).StdOut
                if ("$rawPid".Trim() -match '^\d+$') { break }
            }
            if (-not [int]::TryParse("$rawPid".Trim(), [ref]$bpid) -or $bpid -le 0) {
                $tail = (Invoke-Wsl -ShCommand "tail -n 8 $logFile 2>/dev/null" -TimeoutSec 10).StdOut
                throw "Backend daemon did not record a pid. backend.log tail:`n$tail"
            }
            $info = $null
            for ($i = 0; $i -lt 10 -and -not $info; $i++) {
                Start-Sleep -Milliseconds 500
                $info = Get-WslProcInfo -ProcId $bpid
            }
            $backend = @{ port = $script:BackendPort; pid = $bpid; pgid = $bpid
                          ownership = "launched"; cmdline = if ($info) { $info.Cmdline } else { "" }
                          cwd = if ($info) { $info.Cwd } else { "" } }
            Write-CvOk "Backend spawned (WSL pid $bpid, detached daemon)."
        }

        # ---- 5. Frontend (port-ownership safe) ----
        $frontend = $null
        $lpid = Get-WslListenerPid -Port $script:FrontendPort
        if ($lpid) {
            $info = Get-WslProcInfo -ProcId $lpid
            if (Test-IsOurProc -Info $info -WslRoot $roots.WslRoot -Needle "vite") {
                if (Test-CvHealth -Url $frontendUrl) {
                    $own = $false
                    $ownLeader = 0
                    $pf = Join-Path $roots.StateDir "frontend.pid"
                    if (Test-Path $pf) {
                        $pfPid = 0
                        if ([int]::TryParse((Get-Content $pf -Raw).Trim(), [ref]$pfPid)) {
                            $linfo = Get-WslProcInfo -ProcId $pfPid
                            if ($linfo -and $linfo.Cwd.StartsWith($roots.WslRoot) -and
                                ($linfo.Cmdline -like "*npm run dev*" -or $pfPid -eq $lpid)) {
                                $own = $true; $ownLeader = $pfPid
                            }
                        }
                    }
                    if ($own) {
                        Write-CvOk "Frontend already running from a previous Start (leader pid $ownLeader), healthy - ADOPTING it (Stop will stop it)."
                        $linfo2 = Get-WslProcInfo -ProcId $ownLeader
                        $frontend = @{ port = $script:FrontendPort; pid = $ownLeader; pgid = $ownLeader
                                       ownership = "launched"; cmdline = $linfo2.Cmdline; cwd = $linfo2.Cwd }
                    } else {
                        Write-CvOk "Frontend already running from this repo (pid $lpid) and healthy - REUSING it (Stop will NOT kill it)."
                        $frontend = @{ port = $script:FrontendPort; pid = $lpid; pgid = $lpid
                                       ownership = "reused"; cmdline = $info.Cmdline; cwd = $info.Cwd }
                    }
                } else {
                    throw ("Port $($script:FrontendPort) is held by a vite dev server (pid $lpid) that is NOT healthy. " +
                           "Free the port, then run Start again.")
                }
            } else {
                throw ("Port $($script:FrontendPort) is occupied in WSL by another process (pid ${lpid}: $($info.Cmdline)). " +
                       "This launcher never steals or kills ports it does not own. Free the port, then run Start again.")
            }
        } else {
            if (Test-WindowsPortReallyBlocked -Port $script:FrontendPort) {
                $winOwner = Get-WindowsListener -Port $script:FrontendPort
                throw ("Port $($script:FrontendPort) is occupied on WINDOWS by '$winOwner' [$(Get-WindowsListenerDetail -Port $script:FrontendPort)]. " +
                       "This launcher never kills unrelated processes. Free the port (for example, stop that dev server), then run Start again.")
            }
            if (-not (Test-Path (Join-Path $roots.WinRoot "frontend\node_modules"))) {
                throw "The frontend dependencies are not installed yet. Double-click Setup.cmd once (it installs everything and checks your prerequisites), then run Start again."
            }
            Write-CvStep "Starting frontend (Vite dev server, 127.0.0.1:$script:FrontendPort)..."
            $flogFile = "$($roots.WslRoot)/.local/compilevista/logs/frontend.log"
            $fpidFile = "$($roots.WslRoot)/.local/compilevista/frontend.pid"
            $finner = 'echo $$ > ' + $fpidFile + '; exec npm run dev >> ' + $flogFile + ' 2>&1'
            $cmd = "cd $($roots.WslRoot)/frontend && setsid -f sh -c '$finner' </dev/null"
            $winFpidFile = Join-Path $roots.StateDir "frontend.pid"
            Remove-Item $winFpidFile -ErrorAction SilentlyContinue  # BEFORE launch (race)
            $r = Invoke-Wsl -ShCommand $cmd -TimeoutSec 30
            if ($r.ExitCode -ne 0) {
                throw "Frontend launch failed: $($r.StdErr)"
            }
            $fpid = 0
            $rawFpid = ""
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 500
                $rawFpid = (Invoke-Wsl -ShCommand "cat $fpidFile 2>/dev/null" -TimeoutSec 10).StdOut
                if ("$rawFpid".Trim() -match '^\d+$') { break }
            }
            if (-not [int]::TryParse("$rawFpid".Trim(), [ref]$fpid) -or $fpid -le 0) {
                $ftail = (Invoke-Wsl -ShCommand "tail -n 8 $flogFile 2>/dev/null" -TimeoutSec 10).StdOut
                throw "Frontend daemon did not record a pid. frontend.log tail:`n$ftail"
            }
            $info = $null
            for ($i = 0; $i -lt 10 -and -not $info; $i++) {
                Start-Sleep -Milliseconds 500
                $info = Get-WslProcInfo -ProcId $fpid
            }
            $frontend = @{ port = $script:FrontendPort; pid = $fpid; pgid = $fpid
                           ownership = "launched"; cmdline = if ($info) { $info.Cmdline } else { "" }
                           cwd = if ($info) { $info.Cwd } else { "" } }
            Write-CvOk "Frontend spawned (WSL pid $fpid, detached daemon)."
        }

        # ---- 6. REAL readiness (health endpoints, not just spawn) ----
        Write-CvStep "Waiting for real readiness (API health + frontend HTTP)..."
        $bOk = $false; $fOk = $false
        for ($i = 0; $i -lt 60; $i++) {
            if (-not $bOk) { $bOk = Test-CvHealth -Url $backendHealth -TimeoutSec 2 }
            if (-not $fOk) { $fOk = Test-CvHealth -Url $frontendUrl -TimeoutSec 2 }
            if ($bOk -and $fOk) { break }
            Start-Sleep -Seconds 1
        }
        if (-not $bOk) {
            $tail = Invoke-Wsl -ShCommand "tail -n 25 $($roots.WslRoot)/.local/compilevista/logs/backend.log 2>/dev/null" -TimeoutSec 20
            throw "Backend did NOT become healthy at $backendHealth within 60s. Last backend.log lines:`n$($tail.StdOut)"
        }
        if (-not $fOk) {
            $tail = Invoke-Wsl -ShCommand "tail -n 25 $($roots.WslRoot)/.local/compilevista/logs/frontend.log 2>/dev/null" -TimeoutSec 20
            throw "Frontend did NOT become healthy at $frontendUrl within 60s. Last frontend.log lines:`n$($tail.StdOut)"
        }
        Write-CvOk "Backend healthy:  $backendHealth"
        Write-CvOk "Frontend healthy: $frontendUrl"

        # ---- 7. State (git-ignored, atomic) ----
        $state = [ordered]@{
            run_id       = [guid]::NewGuid().ToString("N").Substring(0, 12)
            started_utc  = (Get-Date).ToUniversalTime().ToString("o")
            repo_win     = $roots.WinRoot
            repo_wsl     = $roots.WslRoot
            commit       = Get-CvCommit -WslRoot $roots.WslRoot
            backend_url  = $backendHealth
            frontend_url = $frontendUrl
            backend      = $backend
            frontend     = $frontend
            images       = $imageIds
        }
        Write-CvState -State $state -Path $statePath
        Write-CvOk "State written: $statePath"

        # ---- 8. Browser (only when healthy) ----
        if (-not $NoBrowser) {
            Write-CvStep "Opening browser at $frontendUrl ..."
            Start-Process $frontendUrl | Out-Null
        }
        Write-Host ""
        Write-Host "================================================="
        Write-CvOk "CompileVista is running. Open: $frontendUrl"
        Write-Host " Stop later with: Stop.cmd    Status: Status.cmd"
        Write-Host " (You can close this window; the servers keep running.)"
        Write-Host "================================================="
    } finally {
        Remove-CvLock -Path $startLock
    }
} catch {
    $fail = $true
    Write-CvErr $_.Exception.Message
    Write-Host ""
    Write-CvWarn "Nothing unhealthy was killed or stolen; fix the issue above and run Start again."
    Write-CvWarn "If servers were partially started before this failure, run Stop.cmd to clean them up."
    Write-CvWarn "Logs: .local\compilevista\logs\ (backend.log / frontend.log)"
}
if ($fail) { exit 1 }
exit 0
