# Local Run Guide — one-click Start/Stop + manual workflow (M8-G0)

This guide covers running CompileVista **locally on the developer machine**
(Windows 11 + WSL2 Ubuntu 24.04 + Docker Desktop). Everything binds to
127.0.0.1 only. **This is a local development/demo setup — NOT an authenticated
HTTPS deployment and NOT a public service** (see README §10/§21 before ever
considering exposure).

## First time on a new machine: `Setup.cmd`

Prerequisites (installed once, outside this repo):

- **Windows 11** with **WSL2** and an **Ubuntu 24.04** distro
  (`wsl --install -d Ubuntu-24.04` from an administrator PowerShell).
- Inside that Ubuntu: **Python 3.12+** with `python3-venv`, and **Node.js + npm**
  (`sudo apt install -y python3 python3-venv nodejs npm`). Node must be the
  *Linux* one inside WSL — dependencies are installed from there, so a Windows-only
  Node cannot run the frontend.
- **Docker Desktop** with the WSL 2 engine and WSL integration enabled for Ubuntu.

Then **double-click `Setup.cmd`** once. It checks each prerequisite and tells you
exactly what is missing, creates the backend virtual environment, installs the
frontend dependencies (`npm ci`) and builds the three sandbox images. It is safe to
re-run — finished steps are skipped. Afterwards use `Start.cmd`.

To use a differently named WSL distro, set the `COMPILEVISTA_WSL_DISTRO`
environment variable before running the scripts.

## One-click workflow (recommended)

| File | What it does |
|---|---|
| `Setup.cmd`  | One-time: checks prerequisites, installs backend/frontend dependencies, builds the sandbox images. |
| `Start.cmd`  | Checks WSL, Docker Desktop/engine, pinned images; starts backend + frontend; waits for REAL health; opens the browser. |
| `Stop.cmd`   | Gracefully stops ONLY the servers this launcher started (identity-verified); idempotent; leaves Docker Desktop and unrelated processes alone. |
| `Status.cmd` | Reports engine health, both URLs, ownership, and live pids — no false green states. |

1. Open `E:\ComplieVista` in File Explorer and **double-click `Start.cmd`**.
   - First run may build missing pinned images (`compilevista/analyzer:m2`,
     `compilevista/runtime:m4`, `compilevista/debug:m5`) from the repo
     Dockerfiles — this is logged explicitly and can take a few minutes.
   - If Docker Desktop is not running, Start launches it at user level and
     waits (up to ~3 minutes) for the engine.
2. The browser opens automatically **only after** both health checks pass.
   - Frontend: <http://127.0.0.1:5173/>
   - API health: <http://127.0.0.1:8123/api/v1/health>
3. You can close the Start window; the servers keep running (they are detached
   from the WSL session that spawned them).
4. Double-clicking `Start.cmd` again while running is safe: healthy servers
   from this repo are reported as reused/adopted — never duplicated, and the
   launcher never starts a second copy.
5. **Double-click `Stop.cmd`** to stop the servers. It kills only processes it
   can verify by recorded identity (pid + cmdline + working directory in this
   repo). A server you started yourself (outside the launcher) is reported as
   EXTERNALLY OWNED and left running.

### State, logs, locks

Everything lives in `.local/compilevista/` (git-ignored):

- `state.json` — run id, commit, ports, WSL pids, process identities,
  ownership (`launched` vs `reused`), pinned image IDs. Written atomically.
- `logs/backend.log`, `logs/frontend.log` — bounded dev logs. Minimize what
  you paste into the app if you share logs: submitted source is stored in the
  backend's `data/` artifacts, not in launcher logs.
- `start.lock` / `stop.lock` — guard against double-click races; a stale lock
  whose owner process is dead is removed automatically.

### Port conflicts (what you will see)

- **Port 8123 or 5173 held by another project**: Start refuses with the
  offending pid and process cmdline and never kills anything. Free the port or
  stop that process yourself, then run Start again.
- **Healthy CompileVista server already running from this repo**: reported as
  REUSED (externally owned) or ADOPTED (started by a previous launcher run) —
  Stop will only stop the adopted ones.
- **Windows-side listener** (e.g. another app): refused with the process name;
  the launcher never kills Windows processes.

### Recovery from crashed sessions

- If a previous Start crashed before writing state, run `Stop.cmd` (calm
  no-op if nothing is tracked) and then `Start.cmd` again: healthy servers
  from this repo are detected and re-tracked. The launcher's port sweep also
  stops leftovers that are verifiably our own uvicorn/vite in this repo.
- If WSL was shut down entirely (`wsl --shutdown`), just run `Start.cmd`
  again; if Docker Desktop does not come back, open it manually once.
- Stale PID files cannot cause an unrelated process to be killed: Stop
  verifies the recorded cmdline and working directory before any signal.

## Manual workflow (unchanged, for debugging)

From a WSL Ubuntu-24.04 terminal:

```bash
# backend (terminal 1)
cd /mnt/e/ComplieVista/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8123

# frontend (terminal 2)
cd /mnt/e/ComplieVista/frontend
npm run dev          # strictPort 5173, proxies /api -> 127.0.0.1:8123
```

Notes:

- The backend dev port is **8123** (8000 is occupied by an unrelated Windows
  process on this machine — recorded since M0).
- Vite uses polling (`usePolling: true`) because `/mnt/e` (9P) does not
  propagate inotify events (measured M0).
- Execution needs the three pinned images; rebuild them after changing
  anything under `sandbox/`:
  `docker build -t compilevista/analyzer:m2 sandbox/analyzer` (and the
  obvious equivalents for `runtime:m4`, `debug:m5`).

## First-run prerequisites

- WSL2 with Ubuntu-24.04 (`wsl -d Ubuntu-24.04 -- echo ok`).
- Docker Desktop (WSL2 engine) with the distro integration enabled.
- Backend venv already present at `backend/.venv` (CPython 3.12.3).
- Frontend `node_modules` already present (Node 24 inside WSL).
  The launcher checks these and tells you the exact missing piece; it never
  installs system packages silently and never fetches remote scripts.

## Docker cleanup

`Stop.cmd` does NOT stop containers: user execution containers (`cv-*`) are
short-lived, `--rm`, and forcibly removed by the backend on timeouts/cancels;
the backend also reconciles leftovers from crashed runs on next start. Docker
Desktop itself and any unrelated containers are left exactly as they were.
