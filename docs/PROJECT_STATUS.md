# CompileVista Project Status

Updated: 1 November 2026 (M4QA adversarial audit)

## Current milestone: **M4QA — adversarial runtime/sandbox audit & surgical repair**

Status: **M4QA PASS on all exit gates Q1–Q6** (`docs/TEST_EVIDENCE/M4QA.md`,
`docs/milestones/M4QA.json`, handoff `docs/HANDOFF_AFTER_M4QA.md`).
The second-pass audit (same-agent, NOT an independent external review) reproduced a
blocker — execution timeouts left live ghost containers — plus unbounded Python
stdout (1.75 GB / 10 s probe) and unbounded C trace files (442 MB / 10 s), and six
more medium/low findings; all 9 fixed surgically with 14 permanent regression/oracle
tests. Backend: 154 passed / 0 failed / 0 skipped. E2E: M3 6/6 (incl. M4), M2 3/3,
M1 5 journeys (1 reasoned GitHub rate-limit skip). TSC clean, Vite build OK.
**M4QA PASS authorizes M5; M5 not started.**

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

**M5 NOT STARTED — authorized by M4QA PASS (docs/milestones/M4QA.json); begin only
with a fresh entry-gate check of git ancestry and manifests.**

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
