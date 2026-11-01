# M7QA Test Evidence — Whole-Product Self-Audit, Repair & Handoff

Date: 1 November 2026. Scope: M7QA only. **SAME-AGENT developer self-audit of
all work M0–M7 — NOT an independent external review and NOT an M9 release
audit.** M7 first-pass evidence was treated as potentially containing hidden
bugs; the audit began with a fresh clean boot and independent oracles rather
than re-running only the existing suite.

## Entry gate

M4/M4QA/M5/M5QA/M6/M6QA/M7 manifests all PASS on disk with ancestry
`8feaf62`; 20 key sandbox/compiler/benchmark regressions re-ran green
pre-audit.

## Fresh clean boot (isolated store, new-account simulation)

`COMPILEVISTA` booted with an empty isolated data directory: /health OK
(schema m6.v1), capabilities honest (pasted_execution PARTIAL), an arbitrary
pasted C program executed end-to-end (`fresh ok`), demo C-01 completed with
matched output + process records + sanitized report, demo PY-04 matched.
**Launch from nothing works.** (Probe logic preserved as named regressions
where applicable; probe script removed per repo convention.)

## Audit A — security/abuse (all clean, probes + full suites)

- **Full backend suite: 191 passed / 0 failed / 0 skipped** (includes: chunked
  and missing-Content-Length body caps on /sources and /imports/github, ZIP
  bomb ratios, path/symlink traversal, SSRF redirect-host allowlist, rate-limit
  typed errors, DOCKER_UNAVAILABLE paths, cancellation, restart recovery).
- New M7 endpoint probes: a 4 MB chunked body on POST /demos/{id}/run is
  ignored safely (no read/hang); `demo-link` on an arbitrary pasted C snapshot
  → **403 DEMO_LINK_BLOCKED** (content-hash gate holds); demo report contains
  no source text and no host paths.
- Docker invocations remain argv-arrays with fixed flags; image ids recorded
  per run; no privileged fallbacks anywhere (re-verified by the M4QA/M5 suites
  in the final run: ghost-container, flood, pids, network, canary negatives).
- GitHub-imported code still never executes (403 EXECUTION_ORIGIN_BLOCKED).
- Internet-facing execution remains disabled pending M9 (unchanged).

## Audit B — compiler/runtime scientific truth (clean)

- M4QA/M5QA/M6QA oracle suites re-ran inside the final backend run: trace
  event parity vs host CPython, C call counts, host-clang asm fingerprint
  equality, distinct per-level digests, benchmark stat recomputation, dis
  structure, side-effect-free tracer, generator frame identity, exception
  fidelity. No ghost frames, honest truncation markers, no invented pointer/
  GC/syscall/CPU counts.
- Fresh trace excerpts captured for evidence: C-01 first events
  `call,call,call,return` (instrumented) with per-event sha256; PY-03
  `call,line,line,line` (settrace).
- Five-pair comparison table regenerated through fresh real executions — all
  5 match with recorded source/output hashes: add `sum=299995`
  (c 34551b8287b5…), conditional `c0=16 c1=8 c2=4 c3=2` (f812fa95d2bf…),
  recursion `fib20=6765` (12bf8615984e…), arraysum `total=50010`
  (d49e224ba6c6…), sort `sorted=471613008` (1235947f318e…).

## Audit C — user journeys (all green, inspected visually)

- Browser E2E: M7 **20/20 demos journeyed** (run + recorded replay each,
  individual results logged), deep checks (C-05 multi-file, PY-03 recursion
  replay), Error Microscope 4/4 genuine diagnostics; M6 2/2, M5 4/4,
  M3+M4 6/6, M2 3/3, M1 5/5 (real GitHub import this window). No page JS
  exceptions (pageerror captured in every journey).
- **Viewport matrix visually inspected** (screenshots read as images, not
  assumed): 1920 (all 20 cards + filters + microscope visible, no clipping),
  1366, 390 (single-column, no overlap/empty views). Cards carry
  id/group/difficulty/concepts and enabled Open CTAs.

## Audit D — portability/persistence/hygiene (clean)

- Working tree clean at commit; tree hash and HEAD recorded in
  docs/milestones/M7QA.json.
- Tracked-file scan: 0 hits for `.env`, node_modules, `__pycache__`, `.venv`,
  key material (regex scan for sk-/ghp-/PRIVATE KEY patterns → 0 files);
  275 tracked files; repository contains no large generated binaries.
- Schema migrations additive (m1→m6.v1 tested); demo sessions reopen
  idempotently without re-execution (M7 tests); restart/cancel/disk-retention
  regressions green (M4QA/M5QA suites).
- Launch instructions for a fresh machine written to
  docs/FINAL_M0_M7_FUNCTIONAL_MATRIX.md (verified against actual requirements
  and scripts; `backend/requirements.txt` exists).

## Audit E — 20-program matrix (re-verified)

`test_g3_all_20_demos_execute_with_expected_output` re-ran inside the final
suite: **20/20 SUCCEEDED** (awaited, asserted — not scheduled). C-05 linked
target present with cross-TU trace evidence. No mock-only or blocked example
counted; Error Microscope fixtures remain outside the count.

## Audit F — deviations (explicit)

See docs/REMAINING_M8_M9.md: Monaco, ELK 2000-node stress tuning, semantic-
zoom refinements, accessibility pass, history UI, Prediction Lab, M8 visual
polish, M9 independent audit/authenticated deployment. **None of M8/M9 is
done or implied.**

## Repairs made during M7QA

No new defects requiring code repair were found beyond the two honest
documentation fixes below — the earlier QA milestones' regression nets held:
1. README header claimed "application not yet implemented or audited" —
   replaced with a truthful M0–M7 status note that still states M8/M9 are NOT
   started and that this is a self-assessment (Q6).
2. README canonical path said `E:\CompileVista` — corrected to the real
   `E:\ComplieVista` (consistent with every prior document).

## Final gate results

```
Backend:  191 passed / 0 failed / 0 skipped
E2E:      M7 20/20 journeyed + microscope 4/4 · M6 2/2 · M5 4/4 · M3+M4 6/6 ·
          M2 3/3 · M1 5/5 (real GitHub import)
TSC:      clean.  Vite build: OK (403 kB).
Fresh boot (isolated store): OK.  Viewport matrix: inspected OK.
```

## Residual risks

1. Same-agent audit — everything above is internal evidence; M9's independent
   review is still required before any release.
2. Benchmarks container-throttled; sub-5 ms medians flagged.
3. GitHub rate limits make import journeys window-dependent (typed skips).
