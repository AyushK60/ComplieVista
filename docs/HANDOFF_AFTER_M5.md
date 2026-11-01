# Handoff after M5 — MemoryScope & ProcessScope

Date: 1 November 2026. Scope: M5 only. **M5 verdict: PASS** (all exit gates G0–G7
green). M5QA audit is authorized on this PASS per the stage contract; **M6 has
NOT been started**.

## What M5 added

- **Capture layer (in the existing workers, no second executor)**:
  - Python harness: frame snapshots at call AND return (id()-based identity,
    aliasing at frame exit), bounded object-reference graph (60 nodes/120 edges/
    depth 2), tracemalloc current/peak + top stats, gc counters + one documented
    forced collect, name-based secret redaction, /proc process sampler
    (50 ms interval, 240-sample cap) with periodic child-process observation.
  - C shim: malloc/free/calloc/realloc interposition (real addresses/sizes/
    lifetime, 5000-event cap), /proc sampler with deterministic first sample and
    thread ids at exit. No ptrace.
  - Curated gdb debug profile: `compilevista/debug:m5` + `c_debug_worker.py`,
    admitted ONLY for content-hash-allowlisted curated fixtures (ADR-0008).
    Verified: gdb works under cap-drop ALL / no-new-privileges / uid 1000 with
    NO capability expansion. Debug builds omit `-finstrument-functions` (the
    entry hook shifts gdb breakpoints ahead of argument setup — root-caused).
  - Schema `m5.v1` (additive), `execution_observations` table, content-addressed
    artifacts, paginated checksummed APIs (`/memory`, `/process`, versioned
    `m5.memory.v1` / `m5.process.v1`). Browsing never re-runs code.
- **UI**: Replay / Memory / Process tabs in the execution panel; MemoryScope
  (active frame synced to the replay cursor with an honest final-state fallback,
  variables, C heap table or Python reference graph, gdb stops for curated runs,
  tracemalloc/gc panes, observed/unavailable badges, limitation lists);
  ProcessScope (container-vs-host pid, kernel, RSS sparkline, children, thread
  ids, exit, syscall-UNAVAILABLE banner). "Debug run (curated only)" button with
  typed refusal for non-curated code.

## Honest capability matrix (do not over-claim)

- C frame locals for pasted code: **unavailable by policy** (first record in the
  memory stream explains it).
- Syscall/strace timelines: **unavailable by policy** (no ptrace anywhere).
- Python references are id()-based identities within a run, NOT C pointers.
- C addresses are per-run (ASLR caveat attached to every gdb stop).
- Allocator interposition is not exhaustive heap coverage; tracemalloc totals
  exclude pre-existing allocations; the graph is a bounded subgraph.

## Verification

- Backend **164/0/0** (incl. 10 new M5 tests + all M4QA adversarial regressions).
- E2E: M5 4/4 (desktop 1440×900 + mobile 390×844 screenshots), M1 5/5 (real
  GitHub import), M2 3/3, M3 incl. M4 6/6. TSC clean; vite build OK.
- Evidence: `docs/TEST_EVIDENCE/M5.md`, screenshots in `docs/TEST_EVIDENCE/m5/`,
  manifest `docs/milestones/M5.json`, ADR-0008.

## Defects found and fixed during M5 (all with regression coverage)

1. M4.json was invalid JSON (`\C` escape) — entry-gate hygiene fix.
2. Harness crashed on classes defining `__len__` during heavy imports
   (`hasattr` guard insufficient) — builtin-only `len`; covered by the network
   adversarial fixture.
3. C shim wrote uninitialized stack bytes when snprintf truncated the meta line
   (return-value-as-length bug) — buffer sizing + clamps; per-line orchestrator
   resilience as defense in depth.
4. gdb `-ex commands` semantics (three wrong approaches tested before the
   command-file solution) and the instrumentation-shift breakpoint issue.

## Environment notes

- Backend dev server: WSL uvicorn on `127.0.0.1:8123` (restart to pick up code
  changes — a stale server caused a false E2E failure during M5); Vite on 5173.
- Image ids are recorded in `docs/milestones/M5.json`; rebuild after any change
  under `sandbox/` and update the manifest.

## Next

M5QA (second-pass audit of M5) is authorized. M6 (OptimizationLab) NOT STARTED.
Entry checks: verify ancestry includes the M5 commit, manifests PASS, and never
infer authorization from queued prompts if any gate fails.
