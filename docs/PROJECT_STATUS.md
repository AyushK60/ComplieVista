# CompileVista Project Status

Updated: 1 November 2026 (M7QA)

## Current milestone: **M7QA — whole-product self-audit complete**

Status: **M7QA PASS on all exit gates Q1–Q6** (`docs/TEST_EVIDENCE/M7QA.md`,
`docs/milestones/M7QA.json`, handoff `docs/HANDOFF_AFTER_M7QA.md`).
**M0–M7 FUNCTIONAL PASS (internal evidence only)** — fresh clean boot from an
isolated store verified; security/adversarial suites green (191 backend tests,
0 failures); 20/20 demos journeyed in the browser with real runs and recorded
replay; viewport matrix inspected (1920/1366/390); five-pair comparison table
regenerated with matching outputs and hashes; repo hygiene clean (275 tracked
files, zero secrets/caches). README status now truthful (M0–M7 done, M8/M9 NOT
started). Deviations: docs/REMAINING_M8_M9.md. This remains the developer
agent's self-assessment — the independent external audit is M9.

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

**M8 NOT STARTED.** M7QA PASS (docs/milestones/M7QA.json) authorizes M8; HARD
STOP at end of M7QA per contract — no M8/M9 work has begun.

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
