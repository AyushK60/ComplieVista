# CompileVista Project Status

Updated: 1 November 2026 (M5QA)

## Current milestone: **M5QA — Memory/Process scientific audit & repair**

Status: **M5QA PASS on all exit gates Q1–Q5** (`docs/TEST_EVIDENCE/M5QA.md`,
`docs/milestones/M5QA.json`, handoff `docs/HANDOFF_AFTER_M5QA.md`). The
second-pass self-audit (not an external review) reproduced and fixed six
findings — most notably the Python tracer executing user `__repr__` on primitive
subclasses, misidentified exception records under CPython 3.12's tuple args, and
unstable generator frame identity — plus UI staleness/label precision and C
realloc accounting (the first fix deadlocked the shim and was caught by its own
regression test before commit). Backend **171/0/0**; E2E M5 4/4 (four viewport
widths), M3 6/6, M2 3/3, M1 5/5; TSC clean; vite build OK.
**M6 authorized on this PASS; M6 NOT STARTED.**

## What exists now (cumulative)

- **M0**: toolchain proofs, staging bridge, Docker feasibility, API/UI skeleton.
- **M1**: ingestion (paste/upload/ZIP with safe extraction), pinned GitHub import,
  classification, source workspace UI, SQLite + content-addressed persistence.
- **M2**: untrusted C/Python analyzed ONLY inside the pinned restricted container
  (`compilevista/analyzer:m2`): C preprocess/tokens/AST/IR-O0+O2/assembly/object/symbols/
  disassembly; Python tokenize/AST/symtable/code-objects/bytecode — never executed.
  Analysis job lifecycle (queued/running/terminal/cancel/timeout/BLOCKED, idempotent),
  typed bounded stage views with per-item mapping confidence, source-to-stage
  highlighting, raw-output toggle, honest per-stage degradation on invalid source.
  Independent host clang/CPython oracle tests. 103 backend tests passed (4 honest GitHub
  rate-limit skips), 3/3 M2 browser journeys + M1 regression (4/5, one 429 skip).

## Deliberately NOT done (no false claims)

- No multi-file linked builds (M6). Single-file C/Python execution only, in
  restricted containers, local-only (M4, audited M4QA).
- No semantic-zoom graph observatory/Monaco/minimap (M3). No MemoryScope/ProcessScope
  (M5), OptimizationLab (M6), 20-demo suite (M7), premium polish (M8), independent audit (M9).

## Next

**M6 NOT STARTED — authorized by M5QA PASS (docs/milestones/M5QA.json); begin
only with a fresh entry-gate check of git ancestry and manifests.**

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
