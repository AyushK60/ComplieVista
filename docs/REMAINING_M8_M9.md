# REMAINING M8/M9 — explicit outstanding work (deviations, not hidden)

Status: 1 November 2026, end of M8-G0. **M8 visual polish and M9 are NOT
started.** M8-G0 (technical integrity repairs + one-click launcher,
ADR-0010..0012) is COMPLETE — see `docs/TEST_EVIDENCE/M8G0.md`; the repairs
below marked ~~struck~~ are done.

## M8 — Premium product polish

**M8 visual recovery (Project Phoenix) IMPLEMENTED 1 Nov 2026** — see
`docs/TEST_EVIDENCE/M8.md` and `docs/M8_DESIGN_SYSTEM.md`. Landing page fully
replaced; observatory shell (Source Dock / Journey Navigator / per-stage visual
canvas / Inspector / Execution dock) with Explore+Technical modes; Trace
Theater, MemoryScope/ProcessScope and Optimization Explorer rebuilt; Demo
Library is a grouped learning gallery; both mandatory journeys browser-verified.

Still open (deviations, not hidden):
1. Monaco editor — not used; the Source Dock is a bounded read-only view of
   immutable snapshots (Monaco was deferred in M3 for a Vite worker issue).
2. ELK/worker layout for very large graphs (2000-node stress) — the M3 worker
   layout is retained but not stress-tuned for 2000-node inputs.
3. ~~Cohesive landing-page redesign and consistent panel polish~~ DONE.
4. Accessibility pass — reduced-motion honored, focus-visible rings, ARIA
   roles/labels carried over; a full keyboard-navigation audit is NOT done.
5. Export/history session browser UI — still absent (report endpoint exists).
6. Performance profiling / code-splitting — not done; bundle ~460 kB
   (146 kB gzip).
7. Optional Prediction Lab — still not built.

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
