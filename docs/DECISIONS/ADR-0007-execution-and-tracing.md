# ADR-0007 — Execution service, trace instrumentation, and honest limitations

Status: Accepted (M4)

## Decision

1. **Separate privilege domains**: builds in the pinned analyzer container (clang-18 +
   build worker + trace shim); execution in the minimal runtime container (python3.12
   only, no compiler). Both run the restrictive baseline; the orchestrator alone calls
   Docker. No container ever receives the Docker socket.
2. **C call/return trace via `-finstrument-functions`**: the shim defines
   `__cyg_profile_func_enter/exit` and writes JSON lines to `$CV_TRACE_OUT`. The shim
   is compiled WITHOUT the flag (clang 18 has no `-fno-instrument-functions`; the shim
   is simply compiled separately). User code is compiled with `-no-pie` so nm addresses
   match runtime addresses. Symbol resolution via `llvm-nm-18 -S`. This is real
   compiler instrumentation — NOT ptrace, NOT a debugger.
3. **GDB/ptrace: UNSUPPORTED by policy**. Frame-stepping, breakpoints, registers,
   memory contents are documented as unavailable rather than weakened.
4. **Python trace via `sys.settrace`**: call/line/return/exception events; bounded
   `safe_value` (primitives → repr, others → type+identity; never user `__repr__`);
   caps: 5000 events / 64 frames / 200 locals / 120 bytes.
5. **stdout capture**: Python uses fd-level `os.dup2` inside the harness (reliable for
   C-level and Python-level writes). C uses the docker pipe with pump threads (1 MB
   cap, discards flood).
6. **Output ownership**: Docker Desktop chowns bind-mounted dirs after container
   writes; the orchestrator only READS container-written dirs (never writes into
   them). Job-dir cleanup uses a one-off privileged container for root-owned remnants
   (bounded to the jobs root; trusted orchestration).
7. **GitHub imports never execute**: `EXECUTION_ORIGIN_BLOCKED` fail-closed at admission
   regardless of classification.
8. **Schema `m4.v1`**: `executions` + `execution_events` tables with checksummed,
   paginated events; additive migration from any earlier m*.v1.

## Consequences

- C call/return tracing is real but limited: no line-level events, no locals, no
  breakpoints, no step — documented honestly.
- Python line-level tracing has measurable overhead (settrace); trace duration is
  recorded separately from wall-clock run time.
- Docker Desktop bind-mount chown is a known platform quirk; the read-only-orchestrator
  pattern works around it without weakening container isolation.
- Public/semi-public deployment of pasted execution remains blocked for M9 review.
