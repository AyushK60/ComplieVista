# ADR-0008 — MemoryScope & ProcessScope evidence capture (M5)

Status: Accepted (M5)

## Decision

1. **Capture rides the existing execution workers** (M5-F): the Python trace
   harness and the C shim write additional bounded streams (`memory.jsonl`,
   `process.jsonl`) next to the existing trace, inside the same pinned restricted
   containers. There is no second executor and no extra privilege.
2. **C heap evidence = allocator interposition (no ptrace).** The shim interposes
   `malloc/free/calloc/realloc` (dlsym bootstrap, raw `write(2)` logging, capped
   5000 events) and records real addresses, sizes and lifetime order for
   allocations that flowed through libc malloc. This observes actual heap
   activity for BOTH pasted and curated C; it is NOT exhaustive heap coverage.
3. **C frame/variable/pointer evidence = curated gdb debug profile.** A separate
   pinned image (`compilevista/debug:m5`, clang-18 + gdb) runs ONLY curated
   allowlisted fixtures (content-hash allowlist computed from
   `sandbox/fixtures/curated/manifest.json`). Verified: gdb traces its own child
   under the full restriction profile (cap-drop ALL, no-new-privileges, uid
   1000) with **no capability expansion and no SYS_PTRACE**. The debug build
   omits `-finstrument-functions` because the entry hook shifts gdb breakpoints
   ahead of argument setup (garbage args were observed). gdb stops carry the
   ASLR/Heisenberg caveat on every record. Pasted/untrusted code NEVER runs
   under gdb (gdb parses untrusted DWARF/ELF — attack surface); it receives an
   explicit `unavailable` record instead (403 `DEBUG_PROFILE_BLOCKED` at
   admission).
4. **Python memory evidence is id()-based.** Frame snapshots at call AND return
   (aliasing is visible at frame exit), object identity as `id(v) % 10**8`
   within the run, alias links derived only from observed shared identity,
   bounded object-reference graph (60 nodes / 120 edges / depth 2) from module
   globals, tracemalloc current/peak + top stats, gc counters plus one documented
   forced collection at exit. Python references are NOT C pointers.
5. **Process evidence = /proc inside the container.** pid-namespace pid/ppid,
   kernel release, RSS/VM/threads/fd samples at a stated 50 ms interval (capped
   240, in-band truncated marker), thread ids at exit, child processes observed
   periodically while alive and at exit, exit code/duration. The orchestrator
   adds a best-effort host-side pid (runtime `docker inspect .State.Pid`) and
   marks it unavailable when the container exits before sampling.
6. **Syscall timeline: UNSUPPORTED by policy.** strace/ptrace is not used
   (ADR-0007); the UI shows an explicit unavailable banner, never inferred data.
7. **Bounds and honesty.** Host side reads all container files through defensive
   caps (4 MB) and stores bounded checksummed rows (`execution_observations`,
   capped 2000 per stream per execution, artifacts content-addressed). Value
   previews use the M4 safe-value rules plus a name-based secret redaction rule
   (`pass/secret/token/key/pwd/credential` substrings are never previewed).
   `len()` is called only on builtins (a class defining `__len__` crashed the
   first harness — regression fixed and covered by the network-adversarial
   fixture which imports socket).
8. **Schema `m5.v1`**: additive columns (`profile`, `host_pid`, `memory_*`,
   `process_*`) + `execution_observations` table; API
   `GET /api/v1/executions/{id}/memory` and `.../process` (paginated,
   checksummed, versioned `m5.memory.v1` / `m5.process.v1`). Browsing never
   re-runs code.
9. **M5QA amendment — no instrumentation side effects, faithful identity.**
   Value previews use EXACT type checks (primitive subclasses may override
   `__repr__`; calling it inside the tracer is a side-effect channel —
   reproduced and fixed). Exception records identify the exception INSTANCE
   from CPython 3.12's tuple arg; `str()` is evaluated only for builtin-module
   exception types, so user `__str__` never runs inside the tracer. Generator
   suspensions are not frame exits: frame ids stay stable across yields and no
   exit-style snapshot is emitted per suspension. The C shim counts `reallocs`
   separately in `mem_meta` (outstanding remains malloc/free-based, stated as
   approximate for realloc-heavy programs; the first fix deadlocked the shim on
   a nested mutex and was caught by its regression test before commit).

## Consequences

- C and Python memory semantics stay distinct (addresses vs identities) and are
  labeled so in the UI.
- Sanitizer-style findings (e.g. the curated double-free fixture reproducing the
  real glibc abort) prove the bug detector works but do NOT imply exhaustive
  allocation observation.
- The debug profile's attack surface is bounded to pinned curated content; any
  change to that policy requires a new security review.
- `addresses are unstable across runs (ASLR)` is recorded on every gdb stop.
