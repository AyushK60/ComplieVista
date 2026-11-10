# CompileVista first-time setup.
# Double-click entrypoint: Setup.cmd -> this script. No admin, no execution-policy change.
# Checks the prerequisites (WSL Ubuntu, Python 3.12, Node, Docker), then installs the
# backend venv, the frontend dependencies and builds the three sandbox images.
# Safe to re-run: every step is skipped when it is already done.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "cv-common.ps1")

function Invoke-CvChecked {
    # Run a WSL command; on failure stop with the tail of its output so the user can act on it.
    param([string]$What, [string]$ShCommand, [int]$TimeoutSec = 600)
    $r = Invoke-Wsl -ShCommand $ShCommand -TimeoutSec $TimeoutSec
    if ($r.ExitCode -ne 0) {
        $err = ($r.StdErr + "`n" + $r.StdOut).Trim()
        if ($err.Length -gt 600) { $err = $err.Substring($err.Length - 600) }
        throw "$What failed (exit $($r.ExitCode)).`n$err"
    }
    return $r
}

try {
    $roots = Get-CvRoots
    Write-Host "=============================================="
    Write-Host " CompileVista first-time setup"
    Write-Host " repo: $($roots.WinRoot)"
    Write-Host "=============================================="

    # ---- 1. WSL distro ----
    Write-CvStep "Checking WSL distro $script:WslDistro..."
    $w = Invoke-Wsl -ShCommand "echo ok" -TimeoutSec 45
    if ($w.ExitCode -ne 0) {
        throw ("WSL distro '$script:WslDistro' is not available.`n" +
               "Install it from an administrator PowerShell:  wsl --install -d $script:WslDistro`n" +
               "Then open it once to finish creating your user, and run Setup again.`n" +
               "(Use another distro by setting the COMPILEVISTA_WSL_DISTRO environment variable.)")
    }
    Write-CvOk "WSL ready."

    # ---- 2. Tools inside WSL ----
    Write-CvStep "Checking tools inside WSL..."
    $py = Invoke-Wsl -ShCommand "python3 -c 'import sys; print(sys.version_info[0]*100+sys.version_info[1])'" -TimeoutSec 30
    if ($py.ExitCode -ne 0 -or [int]($py.StdOut.Trim()) -lt 312) {
        throw ("Python 3.12 or newer is required inside WSL (found: '$($py.StdOut.Trim())').`n" +
               "Ubuntu 24.04 ships it:  wsl -d $script:WslDistro -- sudo apt install -y python3 python3-venv")
    }
    $venvOk = Invoke-Wsl -ShCommand "python3 -c 'import ensurepip, venv'" -TimeoutSec 30
    if ($venvOk.ExitCode -ne 0) {
        throw "python3-venv is missing.  Run:  wsl -d $script:WslDistro -- sudo apt install -y python3-venv"
    }
    $node = Invoke-Wsl -ShCommand "node -v && npm -v" -TimeoutSec 30
    if ($node.ExitCode -ne 0) {
        throw ("Node.js and npm are required inside WSL (not just on Windows).`n" +
               "Run:  wsl -d $script:WslDistro -- sudo apt install -y nodejs npm")
    }
    Write-CvOk ("Python " + ($py.StdOut.Trim().Insert(1, ".")) + " / Node " + ($node.StdOut -split "`n")[0].Trim())

    # ---- 3. Docker ----
    Write-CvStep "Checking Docker engine (WSL)..."
    $d = Invoke-Wsl -ShCommand "docker info --format ok" -TimeoutSec 60
    if ($d.ExitCode -ne 0 -or $d.StdOut.Trim() -ne "ok") {
        throw ("The Docker engine is not reachable from WSL.`n" +
               "Install Docker Desktop, enable 'Use the WSL 2 based engine' and WSL integration for $script:WslDistro " +
               "(Settings > Resources > WSL integration), start it, then run Setup again.")
    }
    Write-CvOk "Docker engine ready."

    # ---- 4. Backend environment ----
    if (Test-Path (Join-Path $roots.WinRoot "backend\.venv\bin\uvicorn")) {
        Write-CvOk "Backend environment already installed."
    } else {
        Write-CvStep "Creating the backend virtual environment (a minute or two)..."
        Invoke-CvChecked "Backend install" ("cd $($roots.WslRoot)/backend && rm -rf .venv && python3 -m venv .venv && " +
            ".venv/bin/pip install --disable-pip-version-check -r requirements.txt") 900 | Out-Null
        Write-CvOk "Backend environment installed."
    }

    # ---- 5. Frontend dependencies (must be installed from WSL: Linux node_modules) ----
    if (Test-Path (Join-Path $roots.WinRoot "frontend\node_modules\.bin\vite")) {
        Write-CvOk "Frontend dependencies already installed."
    } else {
        Write-CvStep "Installing frontend dependencies with npm (a minute or two)..."
        Invoke-CvChecked "Frontend install" "cd $($roots.WslRoot)/frontend && npm ci" 900 | Out-Null
        Write-CvOk "Frontend dependencies installed."
    }

    # ---- 6. Sandbox images ----
    $images = [ordered]@{
        "compilevista/analyzer:m2" = "$($roots.WslRoot)/sandbox/analyzer"
        "compilevista/runtime:m4"  = "$($roots.WslRoot)/sandbox/runtime"
        "compilevista/debug:m5"    = "$($roots.WslRoot)/sandbox/debug"
    }
    foreach ($tag in $images.Keys) {
        $r = Invoke-Wsl -ShCommand "docker image inspect -f '{{.Id}}' $tag" -TimeoutSec 30
        if ($r.ExitCode -eq 0 -and $r.StdOut.Trim().StartsWith("sha256:")) {
            Write-CvOk "Image present: $tag"
        } else {
            Write-CvStep "Building image $tag (first time only; this can take several minutes)..."
            Invoke-CvChecked "Building $tag" "docker build -t $tag $($images[$tag])" 1800 | Out-Null
            Write-CvOk "Image built: $tag"
        }
    }

    Write-Host ""
    Write-Host "=================================================="
    Write-CvOk "Setup complete. Double-click Start.cmd to launch CompileVista."
    Write-Host "=================================================="
    exit 0
} catch {
    Write-Host ""
    Write-CvErr $_.Exception.Message
    exit 1
}
