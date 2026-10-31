# HANDOFF AFTER M4 — fresh-session resume

## What M4 added

- Two pinned images: analyzer (build, clang-18 + instrumentation shim) and runtime
  (execute, python3.12 + trace harness). Immutable ids recorded per execution.
- Execution service: POST/GET/cancel /api/v1/executions; event pagination with
  checksums; admission gates (target eligibility, GitHub-origin fail-closed); lifecycle
  (QUEUED→RUNNING→COMPLETED/FAILED/CANCELLED/TIMEOUT/BLOCKED); restart reconciliation.
- C: `-finstrument-functions` call/return + llvm-nm symbol resolution; `-no-pie` for
  address stability. GDB/ptrace UNSUPPORTED by policy.
- Python: `sys.settrace` call/line/return/exception with `safe_value` locals (bounded,
  no user `__repr__`). fd-level stdout redirect inside harness.
- Frontend: Run button, recorded replay timeline (play/pause/step/jump), stdout panel,
  source highlight, explicit banner "does not rewind the running process".
- Hardening: streaming ASGI body caps, bounded receive for all endpoints, container
  reconciliation at startup, orchestrator-forced cleanup.

## Launch / test

Same as HANDOFF_AFTER_M2/M3 plus:
- `sandbox/runtime/Dockerfile` (runtime image), `sandbox/analyzer/c_build_worker.py`,
  `sandbox/runtime/py_trace_harness.py`, `c_trace_shim.c`.
- Tests: `pytest backend/tests -q` (143); E2E: `python e2e/m3_journeys.py` (6 incl. M4).

## Key constraints to preserve

1. GitHub imports NEVER execute (403 fail-closed).
2. GDB/ptrace UNSUPPORTED (ADR-0007); C tracing via -finstrument-functions only.
3. Docker Desktop chowns bind-mount dirs: orchestrator only READS container-written dirs.
4. Trace caps: 5000 events / 64 frames / 200 locals / 120 bytes; flags set honestly.
5. stdout: Python fd-redirect in harness; C docker pipe with pump cap (1MB).

## Remaining M5–M9

M5 MemoryScope/ProcessScope → M6 OptimizationLab → M7 20-demo suite → M8 polish →
M9 independent audit/deployment review. Each requires its own preflight + authorization.
