# HANDOFF AFTER M2 — fresh-session resume document

Written 31 October 2026 after M2 PASS. This file lets a NEW ZCode session/account resume
without conversation history. The authoritative product contract is `README.md`; milestone
gates live in `docs/milestones/*.json`.

## Product state (what actually exists)

- **M0 (PASS)**: real Clang 18.1.3 + CPython 3.12.3 toolchain proofs with committed
  evidence (`evidence/m0/`), Windows→WSL staging bridge (hashed, attack-validated),
  Docker restrictive-baseline feasibility, FastAPI + React/Vite skeleton, 33 tests.
- **M1 (PASS)**: paste/upload/ZIP ingestion with safe extraction (12 hostile-archive
  tests), pinned public GitHub import (verified live: antirez/kilo, pallets/click),
  capability classification with verified-vs-detected reasons, source workspace UI
  (`/workspace`), persistence (SQLite `m2.v1` + content-addressed artifacts), 90 tests.
- **M2 (PASS)**: real analysis of untrusted pasted/imported C and Python inside a pinned
  restricted container (`compilevista/analyzer:m2`, id `sha256:94d7f405…`):
  - C stages: preprocess, tokens, ast (clang JSON), ir_o0, ir_o2, assembly, object,
    symbols, disassembly — CFG edges derived from real terminators.
  - Python stages: tokens, ast(+symtable scopes), code_object, bytecode — never executed.
  - Analysis job API: POST /api/v1/analyses, GET status/stages, cancel; QUEUED→RUNNING→
    COMPLETED/FAILED/CANCELLED/TIMEOUT/BLOCKED; idempotent; bounded worker thread.
  - UI: Analyze button → live job status → stage navigator with honest
    AVAILABLE/PARTIAL/ERROR chips → token ribbon / expandable AST tree / IR function-block
    listing / symbols / bytecode table / diagnostics — clicking anything with a known
    source line highlights it in the editor (EXACT positions; IR/asm UNAVAILABLE;
    offset-derived lines labeled DERIVED). Raw tool output toggle with digests.
  - Independent oracle tests re-run host clang/CPython and compare structural identity.

## Launch commands (from E:\ComplieVista)

```sh
# WSL: build/refresh analyzer image (only after worker changes)
docker build -t compilevista/analyzer:m2 sandbox/analyzer

# WSL: backend (loopback 8123 — Windows port 8000 is occupied by an unrelated process)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
setsid nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 &

# WSL: frontend (Vite on 5173; polling watcher is REQUIRED on /mnt/e)
cd frontend && npm install    # once
setsid nohup npm run dev &

# Windows browser: http://127.0.0.1:5173/  (home = M0 proof) and /workspace
# Tests (WSL):     backend/.venv/bin/python -m pytest backend/tests -q
# E2E (Windows):   python e2e/m1_journeys.py && python e2e/m2_journeys.py
# Docker probes:   python3 sandbox/feasibility_m0.py
# Toolchain proofs: python3 toolchains/c/proof.py && python3 toolchains/python/proof.py
```

## Architecture (one paragraph)

Windows ZCode agent → `wsl.exe -d Ubuntu-24.04` (argv arrays only) → FastAPI in WSL
(loopback 8123; SQLite `data/compilevista.db` schema `m2.v1`; content-addressed artifacts
`data/artifacts/<sha[:2]>/<sha>`) → analysis jobs run untrusted source ONLY inside the
pinned restricted container (network-none, read-only rootfs, cap-drop ALL, no-new-privileges,
non-root, memory/cpu/pids caps, external timeout + orchestrator `docker rm -f`) → raw
outputs hashed and normalized into capped typed stage views → React/Vite (Node 24 in WSL,
polling watcher) renders honest stage availability with source-linked evidence.
GitHub imports: strict URL validation → api.github.com SHA resolution → codeload tarball
pinned to the SHA → shared safe extractor. Nothing user-supplied is ever executed;
execution is BLOCKED until the M4 security gate.

## Key constraints that must survive refactors

1. One repo at `E:\ComplieVista` (spelling!) ↔ `/mnt/e/ComplieVista`; disposable staging
   under `/home/khana/.cache/compilevista`.
2. Docker socket = host privilege: trusted orchestration only, never inside containers.
3. Static analysis never executes source; execution requires the M4 gate.
4. Every displayed artifact carries tool version, invocation, exit code, SHA-256,
   availability, observation class and mapping confidence (ADR-0002/0005 enums).
5. No paid APIs; no secrets in git; Windows port 8000 is occupied — use 8123.

## Known limitations / open items

- GitHub unauthenticated 60 req/h: some online-import tests SKIP when exhausted (never
  fake-pass); cached pinned snapshots (kilo) are reused.
- Source→IR/assembly mapping: UNAVAILABLE in M2 (M3/M6 may derive more with debug info).
- Multi-file linked builds: not yet (M6). Runtime execution: M4 gate. Monaco editor,
  semantic zoom, minimap: M3.
- Vite on /mnt/e requires `usePolling` (measured M0).

## M3–M9 remaining (per README §16)

M3 visual observatory engine (Monaco sync, semantic zoom, graphs) → M4 safe execution &
replay + security admission gate → M5 MemoryScope/ProcessScope → M6 OptimizationLab &
comparison (+O1) → M7 20-demo suite → M8 premium polish → M9 independent audit.
Each milestone starts with its own independent preflight of prior gates.

## Evidence entry points

- `docs/TEST_EVIDENCE/M0.md`, `M1.md`, `M2.md`; screenshots in `docs/TEST_EVIDENCE/m1/`, `m2/`.
- `docs/milestones/M0.json`, `M1.json`, `M2.json` — verdicts + gate tables.
- `docs/PROJECT_STATUS.md` — current status; `docs/DECISIONS/ADR-0001..0005` — architecture.
- Git: single repo, main branch; milestone commits recorded in the milestone manifests.
