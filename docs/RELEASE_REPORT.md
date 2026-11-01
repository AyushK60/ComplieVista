# CompileVista Release Report — M8 "The Living Compiler"

Date: 1 November 2026. Scope: the complete visual recovery (Phases 1–3) on top
of the M0–M7 + M8-G0 technical base. This report is written by the implementing
agent; M9-style independent verification is partially embedded in the Part-3
sweep (§16 below) and remains recommended as a separate audit.

## What ships

- **Landing** ("The Living Compiler", porcelain design system): proposition
  hero with instrument-bezel conceptual animation, five chapters, working CTAs.
- **Demo Library**: 20 real programs (5 Python, 5 C, 5 matched pairs) organized
  by language family with concept + difficulty filters, per-program ink
  specimen previews, honest capability matrices, guided story levels.
- **Observatory workspace**: Source Dock | Journey Navigator (phase-grouped:
  C Frontend/Middle/Backend; Python Frontend/Compiler) | Visual Canvas |
  Contextual Inspector | Execution Observatory. Explore/Technical modes.
- **Token Formation**: exact tool tokens on their source lines, meaningful
  default focus, category filters, search, hover→source-span sync, virtual
  ENCODING chips, guided script.
- **Syntax trees**: tidy-tree layout, function-subtree default framing at a
  0.7 zoom floor, node categories, compiler-node filter, ancestry path,
  keyboard navigation, search, collapse/expand.
- **Bytecode observatory**: code objects with constants/names, source-line
  grouped lanes, real branch arcs, source↔instruction sync.
- **LLVM IR**: functions → basic blocks (real terminator-derived edges) with
  verbatim per-block instructions, inspector integration.
- **Execution Observatory**: recorded call structure with arguments and return
  values on each call, ×N aggregation with argument ranges, call detail
  (ancestry, arguments, return, event span, jump-to-return), stack scene,
  kind-filtered event navigation, guided execution story. All values from the
  recorded trace only.
- **MemoryScope**: C heap-lifetime ladder (allocator interposition), Python
  frame-lifetime ladder + recent frame snapshots (id()-based identities,
  honestly labeled), alias groups, bounded object graph, tracemalloc, gc,
  explained unavailable states.
- **ProcessScope**: sampled /proc lanes drawn as steps with sample dots, exit
  marker, honest policy gap for syscalls.
- **Dual-Language Observatory**: two independent pipelines with an explicit
  "no equivalent stage" marker, side-by-side sources, per-concept semantic
  notes, verified outputs, honest timing caveats, observatory deep-links.
- **OptimizationLab**: real O0/O1/O2 builds, side-by-side diff with
  changed/removed/added counts, size bars, benchmarks with checksums; Python
  honestly has no O-levels.
- **Error Microscope**: real diagnostics with phase-of-detection labels
  (before execution / link time / during execution).
- **Security posture unchanged**: restricted containers, digest-pinned images,
  read-only GitHub import (never executed), framed trace channel with trust
  labels, no new backend endpoints.

## Verification

- Backend: `backend/.venv/bin/python -m pytest backend/tests -q` → **208
  passed** (from repo root; includes the three M8 backend additions:
  C-token primary-file ordering, IR block instructions ×2).
- Frontend: `tsc --noEmit` clean; `vite build` OK.
- Browser E2E (committed, real stack, no mocks):
  - `e2e/m8_journeys.py` — Part-1 journeys: ALL CHECKS PASSED.
  - `e2e/m8b_journeys.py` — Part-2 graph engine: ALL CHECKS PASSED.
  - `e2e/m8c_journeys.py` — Part-3: all-20-demo sweep (every available stage
    renders), runtime tabs, Error Microscope, Compare, §15 screenshot suite.
- Screenshots: `docs/TEST_EVIDENCE/m8/recovery/`, `m8b/`, `m8c/`.
- Console errors: zero across all sweeps.

## Known limitations (honest)

1. Trace replay is capped at 5000 events (pagination cap); deeper traces
   remain digest-verified but partially navigable (labeled TRUNCATED).
2. C trace records call/return only (no lines/locals) — shim policy, labeled.
3. C source→IR/assembly mapping is UNAVAILABLE (labeled); IR block
   instructions are verbatim text but not instruction-level source-linked.
4. Python memory evidence is snapshot-based (cooperative tracer), never
   continuous; the object graph is a bounded module-globals subgraph.
5. Process lanes are 50 ms /proc samples; syscalls are policy-unavailable.
6. Container wall times are not cross-language benchmarks; C benchmarks are
   OptimizationLab-only.
7. Bundle ~490 kB (156 kB gzip), no code-splitting yet.
8. Trace theater aggregates >2 consecutive identical sibling calls; full
   traces remain reachable via expansion + filtered event navigation.
9. Landing hero is a labeled conceptual animation.
10. Execution of imported GitHub repositories remains BLOCKED by design.

## Part-3 defect list (found by self-review and browser verification; all fixed)

1. [HIGH] Trace theater showed "produced no trace events" while events were
   still paginating → explicit loading state added.
2. [MED] Graph CSS node width (196px) diverged from the layout engine (172px),
   clipping edge labels on CFG framing → matched.
3. [MED] CFG graphs that missed the 0.7 legibility floor by a few percent were
   centered with clipped edges → floor tuned to 0.66 (near-misses fit).
4. [LOW] ProcessScope exit label overlapped the axis caption → removed the
   redundant top label (dashed exit line + bottom caption retained).
5. [LOW] Empty child-process record rendered "pids " → explicit
   "no child pids recorded".
6. [LOW] E2E timing races (event pagination, compare >45 s) → proper waits;
   re-run green.
7. [LOW] C IR graph legend lacked the basic-block category → added.

## Release readiness

Educational standard: a beginner can follow source → tokens → tree →
bytecode/IR → recorded execution with one-sentence explanations and guided
scripts (verified by walking PY-01/PY-03/C-01/C-03 in a clean browser state).
Technical standard: exact artifacts with provenance, versions, digests and
honest confidence labels in Technical Mode. Product standard: one design
system (Porcelain Instrument × Ink Canvas), one typography and color system,
consistent panel geometry across all surfaces.
