# CompileVista Project Status

Updated: 1 November 2026 (M6QA)

## Current milestone: **M6QA — Optimization/Comparison Oracle Audit & Repair**

Status: **M6QA PASS on all exit gates Q1–Q5** (`docs/TEST_EVIDENCE/M6QA.md`,
`docs/milestones/M6QA.json`, handoff `docs/HANDOFF_AFTER_M6QA.md`). The
second-pass self-audit ran independent oracles — distinct per-level digests
(no relabeling), fresh host-clang assembly fingerprint equality at O0/O2, exact
recomputation of benchmark statistics from raw samples, and a CPython 3.12 dis
oracle — then fixed two UI findings (OptimizationLab stale state across target
switches; compare-rail duration now labeled as container wall including startup
and explicitly non-comparable to benchmark medians). Backend **183/0/0**; E2E
all suites green; TSC clean; vite build OK. **M7 authorized on this PASS; M7
NOT STARTED.**

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

**M7 NOT STARTED.** M6QA PASS (docs/milestones/M6QA.json) authorizes M7; begin
any later stage only with a fresh entry-gate check of git ancestry and manifests.

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
