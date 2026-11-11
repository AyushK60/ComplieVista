# ADR-0012 - One-click local Start/Stop/Status launcher (Stage 8)

Status: Accepted (Stage 8 developer-experience milestone).

## Context

Starting the local stack required manual WSL terminals, venv activation, port
knowledge, and PID cleanup; a second launch collided with port 8123 already in
use. The user requires double-clickable `Start.cmd` / `Stop.cmd` /
`Status.cmd` from Windows Explorer that manage the whole local stack safely -
without killing anything they do not own.

## Decision

1. **Entrypoints are minimal `.cmd` wrappers** in the repo root calling
   `scripts/dev/{Start,Stop,Status}.ps1` with
   `-ExecutionPolicy Bypass` (per-invocation; no permanent policy change, no
   Administrator). Real implementation lives in PowerShell under `scripts/dev/`
   with shared logic in `cv-common.ps1`. All scripts are ASCII-only,
   PowerShell 5.1-compatible, and resolve the repo root from the script
   location (never a hardcoded path), converting to `/mnt/...` form for WSL.
2. **WSL process lifetime (reproduced facts).** On this machine (WSL 3.0.3.0),
   background processes started by a `wsl.exe` invocation are torn down with
   that session - plain `nohup … &` and `setsid … &` both die when the launcher
   exits. The launcher therefore spawns services with
   `setsid -f sh -c 'echo $$ > <pidfile>; exec <service> >> <logfile> 2>&1'`:
   the double fork detaches the daemon from the session tree (verified to
   survive `wsl.exe` exit) and the daemon records its own PID (the grandchild
   PID is not observable by the launcher). Closing the Start window does not
   stop the services.
3. **wsl.exe invocation detail (reproduced).** `wsl -- sh -c "…"` re-wraps the
   command in the login shell and destroys quoting (`$!` came back empty);
   all launcher WSL calls use `wsl -d <distro> -e sh -c "…"` (direct execv).
   PID-file presence is polled through WSL, not Windows `Test-Path` (9P
   directory caching on `/mnt/e` can hide fresh files from Windows).
4. **Port ownership is never stolen.** For 8123/5173: if a WSL listener exists,
   its identity is checked (`/proc/<pid>/cmdline` + `/proc/<pid>/cwd`):
   healthy uvicorn/vite from THIS repo is reused or adopted, anything else ⇒
   Start refuses with the PID and cmdline and never signals it. A real
   Windows-side listener (PID > 4) ⇒ refuse with the process name. The PID-0
   "Idle" listener (transient WSL port-forwarding remnant) is waited out, not
   treated as a conflict. Broad kills (`pkill -f uvicorn`, `taskkill /IM
   node.exe`, blanket `docker stop`) are never used.
5. **Ownership state.** `.local/compilevista/state.json` (git-ignored, atomic
   write, guarded by a PID-stamped lock file with stale-lock recovery) records
   run id, commit, image IDs, per-service port/PID/cmdline/cwd and
   `ownership`: `launched` (this launcher or an adopted previous launcher run -
   adoption requires the recorded daemon-leader pid file to be alive in this
   repo) or `reused` (externally owned; Stop never kills it).
6. **Stop is identity-verified and idempotent.** Only processes whose recorded
   cmdline still matches and whose cwd is inside this repo are signalled; the
   real process group is read from `/proc/<pid>/stat` (a vite listener's group
   is its npm leader's PID, not its own - reproduced). TERM then KILL, group
   then pid. A final port sweep stops only leftovers that are verifiably our
   uvicorn/vite in this repo. No state ⇒ calm success. Docker Desktop and
   unrelated containers are never touched (execution containers are
   short-lived and reconciled by the backend itself on next start).
7. **Readiness is real.** Start waits for the API health endpoint AND frontend
   HTTP 2xx AND the Docker engine before reporting success and opening the
   browser; failure prints the relevant log tail, never a false green.
8. **Scope.** Local-only (127.0.0.1); this is NOT an authenticated HTTPS
   deployment and NOT public-facing (the project notes still govern any exposure).

## Consequences

- First run may build missing pinned images with explicit logging (trusted
  local Dockerfiles only; no silent installs, no remote scripts).
- `wsl.exe -e` + `setsid -f` + pid files are load-bearing; regressions are
  caught by the stage 8 browser tests.

## Rollback

Delete `Start.cmd`/`Stop.cmd`/`Status.cmd` and `scripts/dev/*.ps1`; the manual
workflow (`wsl` + uvicorn/vite) is unchanged and remains documented in
`docs/LOCAL_RUN_GUIDE.md`.
