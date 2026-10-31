# CompileVista Project Status

Updated: 31 October 2026 (M2 execution)

## Current milestone: **M3.5 — post-M3-audit corrections (M3-CV-01..09 closed)**

Status: **M3.5 PASS** — all 9 M3-audit findings fixed with quantitative regressions
(`docs/TEST_EVIDENCE/M3.5.md`, `docs/milestones/M3.5.json`). M3 passed 9/9 gates
(`docs/TEST_EVIDENCE/M3.md`); M2.5 closed the M2 audit findings. 127 backend tests
passed / 0 failed; E2E M3 4/4, M2 3/3, M1 5/5. Structural semantic zoom, SCC-aware
layout, race-guarded stage loads, wide multi-pane observatory shell.

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

- No runtime execution or tracing (M4 gate). No multi-file linked builds (M6).
- No semantic-zoom graph observatory/Monaco/minimap (M3). No MemoryScope/ProcessScope
  (M5), OptimizationLab (M6), 20-demo suite (M7), premium polish (M8), independent audit (M9).

## Next

**M4 NOT STARTED — await independent M3.5 re-verification and explicit authorization.**

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
