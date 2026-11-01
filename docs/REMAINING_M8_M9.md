# REMAINING M8/M9 — explicit outstanding work (deviations, not hidden)

Status: 1 November 2026, end of M7QA. **M8 and M9 are NOT started.** This file is
the authoritative deviations list required by the M7QA contract.

## M8 — Premium product polish (NOT STARTED)

1. Monaco editor (line-numbered, syntax-highlighted) — the workspace currently
   uses a plain text code view.
2. ELK/worker-based layout for very large graphs (2000-node stress) and
   scroll-driven semantic zoom refinements — current layouts are worker-based
   but not stress-tuned.
3. Cohesive landing-page redesign and consistent panel polish across Home /
   Workspace / Demo Library / Compare.
4. Accessibility pass (full keyboard navigation audit, reduced-motion honoring
   beyond defaults, ARIA refinements beyond the existing roles/labels).
5. Export/history session browser UI (the sanitized JSON report endpoint
   exists; a history UI does not).
6. Performance profiling of the frontend bundle (403 kB) and lazy loading.
7. Optional Prediction Lab — explicitly deferred until after the mandatory 20
   E2E journeys (which are complete); still not built.

## M9 — Independent audit & release (NOT STARTED)

1. **Independent** code/screenshot review (every milestone evidence file so far
   is a SAME-AGENT self-audit — none is an external certification).
2. Deployment threat-model review BEFORE any remotely hosted demo: internet-
   facing untrusted execution stays disabled until this review (README §10/§21).
3. Public/semi-public hosting: auth, HTTPS, rate limiting, resource accounting.
4. 20-demo regression re-run by a party other than the developer agent.
5. Release report with independent PASS/FAIL per gate.

## Known residual defects / limitations (accepted, documented)

- C-05 analysis covers the primary TU only (second TU compiled+linked, not
  independently analyzed — declared in capabilities).
- Python worker threads are not traced (settrace is thread-local — declared).
- C-05 OptimizationLab builds the primary file only.
- Benchmarks are container-throttled (0.5 CPU) and single-machine; sub-5 ms
  medians flagged `resolution_warning`.
- GDB/strace/ptrace remain UNSUPPORTED by policy (no frame-level C debugging).
- GitHub unauthenticated rate limit (60 req/h) causes typed RATE_LIMITED skips
  in E2E on exhausted windows (real import verified on reset windows).
- Docker/WSL2 shares one kernel: not an unconditional sandbox; local-only
  execution until M9.
