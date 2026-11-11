# CompileVista local launcher - shared library (Stage 8).
# Pure ASCII, Windows PowerShell 5.1 compatible. No Administrator requirement.
# Safety rules (Stage 8 contract): never kill a process we did not start and
# verified by recorded identity; never use taskkill /IM, pkill -f, or blanket
# docker stop; ports occupied by unknown owners are reported, never stolen.

$script:WslDistro = if ($env:COMPILEVISTA_WSL_DISTRO) { $env:COMPILEVISTA_WSL_DISTRO } else { "Ubuntu-24.04" }
$script:BackendPort = 8123
$script:FrontendPort = 5173
$script:StateDirName = ".local\compilevista"

function Get-CvRoots {
    # Resolve the repo root from THIS script's location (scripts/dev -> repo root),
    # never from a hardcoded assumed path.
    $scriptsDir = Split-Path -Parent $PSScriptRoot           # ...\ComplieVista\scripts
    $root = (Resolve-Path (Join-Path $scriptsDir "..")).Path # ...\ComplieVista
    if (-not (Test-Path (Join-Path $root "backend\app\main.py")) -or
        -not (Test-Path (Join-Path $root ".git"))) {
        throw "This does not look like the CompileVista repository (resolved: $root)."
    }
    $drive = $root.Substring(0, 1).ToLower()
    $rest = $root.Substring(2).Replace("\", "/")
    [pscustomobject]@{
        WinRoot = $root
        WslRoot = "/mnt/$drive$rest"
        StateDir = Join-Path $root $script:StateDirName
        LogDir = Join-Path $root "$script:StateDirName\logs"
    }
}

function Write-CvStep($msg) { Write-Host "[CV] $msg" -ForegroundColor Cyan }
function Write-CvOk($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-CvWarn($msg) { Write-Host "[!!] $msg" -ForegroundColor Yellow }
function Write-CvErr($msg)  { Write-Host "[XX] $msg" -ForegroundColor Red }

function Invoke-Wsl {
    # Runs: wsl.exe -d <distro> -e sh -c <ShCommand> with a hard timeout.
    # -e is REQUIRED: without it wsl.exe re-wraps the command in the login
    # shell, which strips quoting and breaks '$!' background-pid capture
    # (reproduced: 'wsl -- sh -c "sleep 1 & echo $!"' printed an empty pid).
    param(
        [Parameter(Mandatory = $true)][string]$ShCommand,
        [int]$TimeoutSec = 60
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "wsl.exe"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $quoted = $ShCommand.Replace('"', '\"')
    $psi.Arguments = "-d $script:WslDistro -e sh -c `"$quoted`""
    $p = [System.Diagnostics.Process]::Start($psi)
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        try { $p.Kill() } catch { }
        return @{ ExitCode = 124; StdOut = $outTask.Result; StdErr = "wsl call timed out after ${TimeoutSec}s: $ShCommand" }
    }
    return @{ ExitCode = $p.ExitCode; StdOut = $outTask.Result; StdErr = $errTask.Result }
}

function Test-CvHealth {
    param([Parameter(Mandatory = $true)][string]$Url, [int]$TimeoutSec = 3)
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch { return $false }
}

function Get-WslListenerPid {
    # Linux-side owner of a listening TCP port: returns the pid or $null.
    param([Parameter(Mandatory = $true)][int]$Port)
    $r = Invoke-Wsl -ShCommand "ss -ltnp 2>/dev/null | grep -F '::$Port ' || ss -ltnp 2>/dev/null | grep -F ':$Port ' || true" -TimeoutSec 20
    if ($r.ExitCode -ne 0) { return $null }
    $line = ($r.StdOut -split "`n" | Where-Object { $_ -match "users:\(\(" } | Select-Object -First 1)
    if (-not $line) { return $null }
    if ($line -match "pid=(\d+)") { return [int]$Matches[1] }
    return $null
}

function Get-WindowsListener {
    # Windows-side listener on a port (an app outside WSL). Returns the owning
    # process name or $null. NEVER killed by this launcher - report only.
    # A listener owned by PID 0 ("Idle") is a transient WSL port-forwarding
    # remnant (reproduced right after a WSL server releases its port); callers
    # retry before treating it as a real conflict.
    param([Parameter(Mandatory = $true)][int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $conn) { return $null }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc) { return $proc.ProcessName }
    return "pid $($conn.OwningProcess)"
}

function Get-WindowsListenerDetail {
    # Human-readable "name, pid N, command line" for the Windows listener on a port, for error messages only.
    param([Parameter(Mandatory = $true)][int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -gt 4 } | Select-Object -First 1
    if (-not $conn) { return "no live owner found (a short-lived WSL port-forwarding remnant; wait a few seconds and retry)" }
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $p) { return "pid $($conn.OwningProcess)" }
    return "$($p.Name), pid $($p.ProcessId), $($p.CommandLine)"
}

function Test-WindowsPortReallyBlocked {
    # $true only when a REAL Windows process (pid > 4) listens on the port.
    # Waits out the transient PID-0 WSL relay remnant (up to ~12 s).
    param([Parameter(Mandatory = $true)][int]$Port)
    for ($i = 0; $i -lt 4; $i++) {
        $owner = Get-WindowsListener -Port $Port
        if (-not $owner) { return $false }
        if ($owner -ne "Idle" -and $owner -ne "pid 0" -and $owner -notlike "wsl*" -and $owner -notlike "vmmem*") {
            return $true
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Get-WslProcInfo {
    # Identity of a Linux pid: cmdline (nul-separated -> spaces) + cwd. Never guesses.
    param([Parameter(Mandatory = $true)][int]$ProcId)
    $r = Invoke-Wsl -ShCommand ("tr '\0' ' ' < /proc/$ProcId/cmdline 2>/dev/null; echo; readlink /proc/$ProcId/cwd 2>/dev/null") -TimeoutSec 20
    if ($r.ExitCode -ne 0) { return $null }
    $lines = ($r.StdOut -replace "`r", "") -split "`n"
    $cmdline = ""
    $cwd = ""
    if ($lines.Count -gt 0) { $cmdline = $lines[0].Trim() }
    if ($lines.Count -gt 1) { $cwd = $lines[1].Trim() }
    if (-not $cmdline) { return $null }  # pid does not exist
    return @{ Cmdline = $cmdline; Cwd = $cwd }
}

function Test-IsOurProc {
    # A process is "ours" only when its cwd is inside THIS repo and the cmdline
    # matches the expected program. Protects against pid reuse.
    param([hashtable]$Info, [string]$WslRoot, [string]$Needle)
    if (-not $Info) { return $false }
    if (-not $Info.Cwd -or -not $Info.Cwd.StartsWith($WslRoot)) { return $false }
    return ($Info.Cmdline -like "*$Needle*")
}

function Write-CvState {
    # Atomic state write: temp file + Move-Force.
    param([Parameter(Mandatory = $true)]$State, [Parameter(Mandatory = $true)][string]$Path)
    $tmp = "$Path.tmp"
    $State | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding UTF8
    Move-Item -Force -Path $tmp -Destination $Path
}

function Read-CvState {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    try {
        return Get-Content -Path $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch { return $null }
}

function New-CvLock {
    # Cooperative lock: exclusive-create file holding the launcher pid + kind.
    # A STALE lock (owner dead) is detected and removed; a live one aborts us.
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )
    if (Test-Path $Path) {
        $owner = 0
        try { $owner = [int](Get-Content $Path -Raw).Trim() } catch { $owner = 0 }
        if ($owner -gt 0 -and (Get-Process -Id $owner -ErrorAction SilentlyContinue)) {
            return $false  # a live launcher holds the lock (double-click protection)
        }
        Remove-Item -Force $Path -ErrorAction SilentlyContinue  # stale lock
    }
    try {
        $bytes = [System.Text.Encoding]::ASCII.GetBytes("$PID")
        $fs = [System.IO.File]::Open($Path, 'CreateNew', 'Write', 'None')
        $fs.Write($bytes, 0, $bytes.Length)
        $fs.Close()
        return $true
    } catch {
        return $false
    }
}

function Remove-CvLock { param([Parameter(Mandatory = $true)][string]$Path)
    Remove-Item -Force $Path -ErrorAction SilentlyContinue }

function Get-CvCommit {
    param([Parameter(Mandatory = $true)][string]$WslRoot)
    $r = Invoke-Wsl -ShCommand "cd $WslRoot && git rev-parse --short HEAD 2>/dev/null" -TimeoutSec 20
    if ($r.ExitCode -eq 0 -and $r.StdOut) { return $r.StdOut.Trim() }
    return "unknown"
}

function Get-WslProcPgid {
    # Real process-group id of a Linux pid (from /proc/<pid>/stat field 5).
    # Never assume pgid == pid: a spawned npm leader's listening vite child has
    # pgid == the npm pid, not its own (reproduced stage 8).
    param([Parameter(Mandatory = $true)][int]$ProcId)
    $r = Invoke-Wsl -ShCommand "awk '{print \$5}' /proc/$ProcId/stat 2>/dev/null" -TimeoutSec 20
    $v = 0
    if ($r.StdOut -and [int]::TryParse($r.StdOut.Trim(), [ref]$v) -and $v -gt 0) { return $v }
    return $ProcId
}
