# CompileVista Security (M0)

Authoritative threat model: README §10. This document records the M0-relevant subset and
residual risks. Nothing here weakens the README.

## Execution modes (M4, audited by M4QA)

- Static analysis: never executes source (M0–M3 unchanged).
- Curated/pasted execution: restricted containers only; explicit user action required;
  admission checks target eligibility + provenance. GitHub-imported code: 403 fail-closed.
- Runtime image: minimal (no compiler), pinned id per execution; build image separate.
- C tracing via `-finstrument-functions` (compiler instrumentation, no ptrace);
  GDB/ptrace UNSUPPORTED by policy (ADR-0007).
- Python tracing via `sys.settrace` with bounded safe_locals (no user `__repr__`).
- All previous constraints unchanged; Docker socket never enters containers.
- **M4QA hardening (2026-11-01)**: timeouts force-remove containers (no ghosts);
  container-written output files are size-capped in-container (stdout 1 MB, trace
  5000 events) AND read through defensive host-side caps; cancel commits its flag
  before killing containers and is honoured before container launch; both job
  orchestrators share a robust, loud-on-failure disposable-dir cleanup; POST
  /executions and /analyses enforce the same streaming body caps as the other
  endpoints. See docs/TEST_EVIDENCE/M4QA.md for reproductions (1.75 GB stdout and
  442 MB C trace in 10 s pre-repair).

## Memory & process evidence (M5, ADR-0008)

- Capture rides the existing restricted containers (no second executor, no new
  privileges). C heap evidence via allocator interposition (no ptrace); Python
  evidence via the trace harness (id()-based identities, bounded graph,
  tracemalloc/gc); process evidence via /proc inside the container (stated
  sample interval, capped) plus a best-effort host-side pid from the runtime.
- **Curated gdb debug profile** (`compilevista/debug:m5`): gdb-based frame/
  variable/pointer capture for content-hash-allowlisted curated fixtures ONLY.
  Verified: no capability expansion needed (gdb traces its own child under
  cap-drop ALL / no-new-privileges). Pasted/untrusted code never runs under gdb
  (untrusted DWARF/ELF parsing is attack surface); it gets an explicit
  `unavailable` record and 403 `DEBUG_PROFILE_BLOCKED` at admission.
- Syscall/strace timelines: UNSUPPORTED by policy; shown as unavailable, never
  inferred. Secret-named bindings are redacted in value previews by a documented
  name rule. Python references are id()-based identities, not C pointers; C
  addresses carry an ASLR instability caveat.

## Trust assumptions

| Asset | Trust level |
|---|---|
| Browser / frontend | Untrusted client; API validates and bounds everything |
| Source fixtures, staged files, imported code (future) | Untrusted data; never executed during static inspection |
| Toolchain binaries (clang, python3, objdump, docker CLI) | Trusted host tools invoked via fixed argv arrays |
| Docker daemon / socket | **Host-equivalent privilege.** Accessible only to trusted orchestration; never mounted into or passed to any container |
| Job staging dir `/home/khana/.cache/compilevista` | Disposable, non-executable data; validated paths only |

## M0 invariant: static inspection never executes fixtures

The CPython adapter uses `tokenize` / `ast.parse` / `compile` / `dis` only. `compile()`
does not run top-level code. No fixture is imported, no `exec`/`eval`, no user-defined
`__repr__` is invoked. Clang invocations are analysis-only (`-fsyntax-only`, `-E`,
`-emit-llvm`, `-c`); invalid fixtures are never linked or run.

## Path and input defenses (implemented in staging bridge)

- Reject absolute paths, `..` segments, Windows drive letters, backslash tricks, NUL bytes,
  and non-regular files (symlinks/devices) before copying.
- Per-file and total size caps; file-count cap; archive handling is **out of M0 scope**
  (M1) and explicitly not implemented here.
- Hash everything (SHA-256); snapshot hash binds outputs to inputs.

## Docker baseline (feasibility only — NOT a safety claim)

Curated M0 containers run with: no network, read-only rootfs, size-capped tmpfs,
`--cap-drop ALL`, `no-new-privileges`, default seccomp, non-root UID, memory/CPU/pids/fsize
limits, no ports, `--rm`, external timeout, pre/post container-count cleanup check.
Tested only against trivial curated fixtures with deterministic outputs plus one
deliberately looping fixture proving wall-clock timeout + cleanup.

## Residual risks / not yet proven (explicit)

1. **No adversarial escape testing in M0** — fork bombs, syscall abuse, container escape
   probes, malformed tool outputs are M4 admission tests (README §10).
2. **Docker-in-WSL2 shares one kernel** with the analysis worker; seccomp is the default
   profile; AppArmor/LSM customization unverified in M0.
3. **ptrace/GDB inside containers: UNSUPPORTED** by current profile (deliberate).
4. **Localhost-only binding** protects the M0 API; any networked demo requires the README
   §21 authenticated/TLS design and a separate review.
5. **Static analyzers themselves** (clang/python) are exposed to untrusted bytes only
   through bounded files in staging; compiler-attack hardening (caps, timeouts) is present
   in M0 as timeouts + size caps, and full containment of analysis workers is a later gate.
6. Secrets policy: none exist in the repo; `.env` is ignored; no API keys, no paid APIs.
