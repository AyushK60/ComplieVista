# CompileVista Project Status

Updated: 31 October 2026 (M0 execution)

## Current milestone: **M0 — Architecture & toolchain proof**

Status: **implemented and verified; verdict PASS on all 7 M0 gates** (evidence:
`docs/TEST_EVIDENCE/M0.md`, machine-readable `docs/milestones/M0.json`).

## What exists now

- One git repository at `E:\ComplieVista` (↔ `/mnt/e/ComplieVista`), authoritative
  `README.md` preserved (with the narrowly scoped, ADR-recorded path-spelling correction).
- Real C pipeline proof (Clang/LLVM 18.1.3): preprocessing, tokens (stderr note),
  JSON AST, LLVM IR (O0), assembly, object/disassembly/symbols, verbatim diagnostics
  for one syntax + one semantic error fixture.
- Real CPython 3.12.3 pipeline proof: tokenize (exact offsets), AST, code objects,
  dis bytecode with positions, verbatim SyntaxError — never executing fixtures.
- Typed `m0.v1` contracts (Pydantic) with honest availability/mapping/observation enums.
- Windows→WSL staging bridge with hash manifests, attack rejection, measured timings.
- FastAPI control plane (`/api/v1/health`, `/capabilities`, `/analyses…`), loopback-only,
  structured errors; thin React/Vite frontend rendering genuine artifacts; proven
  Windows-browser→WSL reachability + browser screenshot.
- Docker restrictive-baseline feasibility (3/3 probes) with orchestrator-enforced
  cleanup; NOT a sandbox safety claim.
- 33 passing tests incl. independent toolchain oracles; ADRs 0001–0003; SECURITY.md;
  AGENTS.md; API contracts.

## Deliberately NOT done (no false claims)

- No GitHub import (M1), no user-pasted execution (BLOCKED until M4 gate), no
  MemoryScope/ProcessScope/OptimizationLab, no premium UI (M3/M8), no 20-demo suite
  (M7), no independent audit (M9).

## Next

**M1 NOT STARTED; awaiting separate prompt** (source workspace & GitHub import per
README §16).

## Active risks (see also README §19 and docs/SECURITY.md)

1. Windows process occupies localhost:8000 → dev backend port is 8123.
2. /mnt/e inotify dead → Vite polling enabled (bounded 300 ms interval).
3. External timeouts do not clean containers → orchestrator-enforced `docker rm -f`
   is mandatory in all future execution code.
4. Docker group membership = host-equivalent privilege inside WSL; access must stay
   in trusted orchestration only.
