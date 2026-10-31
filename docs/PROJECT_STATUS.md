# CompileVista Project Status

Updated: 31 October 2026 (M1 execution)

## Current milestone: **M1 — Source workspace, safe ingestion & public GitHub import**

Status: **implemented and verified; verdict PASS on all 7 M1 gates**
(evidence: `docs/TEST_EVIDENCE/M1.md`, machine-readable `docs/milestones/M1.json`).
Prior checkpoint: M0 PASS at `e732c5a`; M1 backend checkpoint `77cc5e4`.

## What exists now

- Everything from M0 (real C/CPython toolchain proofs, staging bridge, API, Docker
  feasibility, tests) — regression-verified at M1 start and at the end (E2E + suite).
- **Persistence** (ADR-0004): SQLite metadata (`data/compilevista.db`, schema `m1.v1`)
  + content-addressed immutable source artifacts; idempotent snapshot re-import.
- **Ingestion**: paste (C/Python), multipart upload (.c/.h/.py), bounded ZIP with the
  shared safe extractor (zip-slip/symlink/bomb/collision/binary rejection, every
  rejected entry recorded). No source is ever executed during intake (adversarial
  fixtures prove it).
- **GitHub import**: strict URL validation → api.github.com metadata + full commit SHA →
  codeload tarball pinned to that SHA → safe extraction; redirect allowlist, rate-limit
  typed errors, streaming caps. Verified against TWO real public repos
  (`antirez/kilo` C, `pallets/click` Python).
- **Classification**: per-file targets with statuses and machine-readable reasons, each
  reason `verified` or `detected`; multi-file C hints; `READY_FOR_CONTROLLED_EXECUTION`
  never emitted in M1.
- **Frontend workspace** (`/workspace`): Paste/Upload/GitHub tabs, filtered file tree
  with status badges, read-only line-numbered code view, target inspector, typed error
  and empty/loading states, live tool-availability header. M0 home page retained.
- **E2E**: 5/5 Playwright journeys pass with committed screenshots.

## Deliberately NOT done (no false claims)

- No analysis of arbitrary user sources (M2 wires the real analyzers; Analyze button is
  disabled with an explanation). No execution of pasted/repository code (M4 gate).
- No graph observatory (M3), no MemoryScope/ProcessScope/OptimizationLab (M5/M6),
  no 20-demo suite (M7), no premium polish (M8), no independent audit (M9).

## Next

**M2 NOT STARTED; may enter its own independent preflight** (core analyzers, per README §16).

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. Lexical `main(` detection can false-positive (e.g. in comments) — always labeled
   `detected`, never `verified`; semantic verification is M2+ toolchain work.
