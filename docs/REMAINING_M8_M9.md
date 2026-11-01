# REMAINING M8/M9 — explicit outstanding work (deviations, not hidden)

Status: 1 November 2026, end of M8-G0. **M8 visual polish and M9 are NOT
started.** M8-G0 (technical integrity repairs + one-click launcher,
ADR-0010..0012) is COMPLETE — see `docs/TEST_EVIDENCE/M8G0.md`; the repairs
below marked ~~struck~~ are done.

## M8 — Premium product polish (NOT STARTED — visual only)

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

- ~~Trace channel: untrusted pasted Python shared a writable /out mount and
  could forge artifacts~~ **FIXED M8-G0** (protected framed channel + trust
  labels); residual: target shares the pid/uid domain, a /proc/self/fd scan
  could in principle reach the observer fd — labeled UNTRUSTED_TARGET per run.
- ~~`docker run` argvs used mutable image tags~~ **FIXED M8-G0** (resolved
  sha256 IDs in argv, fail-closed IMAGE_ID_CHANGED/UNAVAILABLE).
- ~~Python benchmark checksums ignored stdout/exceptions~~ **FIXED M8-G0**.
- ~~Trace previews could invoke user-defined `__len__`~~ **FIXED M8-G0**.
- ~~Demo Library API errors blanked the page~~ **FIXED M8-G0** (Retry +
  recovery E2E).
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
- Clean-Windows-login launcher behavior (reboot-level test) was not exercised;
  manual verification step: log out/in (or reboot) and double-click Start.cmd.
