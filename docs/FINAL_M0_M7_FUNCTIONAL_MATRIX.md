# FINAL M0–M7 Functional Matrix (developer-agent self-assessment)

Date: 1 November 2026. HEAD at assessment: see docs/milestones/M7QA.json.
**This is internal evidence from the developer agent, pending independent
review (M9). It is NOT a certification.**

| Milestone | Scope delivered | Verdict | Primary evidence |
|---|---|---|---|
| M0 | Toolchain proofs, staging bridge, Docker baseline, API/UI skeleton | PASS | docs/TEST_EVIDENCE/M0.md |
| M1 | Ingestion (paste/upload/ZIP), pinned GitHub import, workspace UI, SQLite+artifacts | PASS | M1.md (real GitHub import verified on reset windows) |
| M2 | Untrusted C/Python static analysis in pinned containers; job lifecycle; honest degradation | PASS | M2.md + M2.5.md |
| M2.5→G0 | Streaming body caps, rate/size hardening (F01–F05 era) | PASS | M2.5.md, M4G0.md |
| M3 | Graph observatory (m3.graph.v1), typed contracts, inspector with evidence levels | PASS | M3.md |
| M3.5 | M3 audit findings closed | PASS | M3.5.md |
| M4 | Controlled C/Python execution, real traces, recorded replay | PASS | M4.md |
| M4QA | Ghost-container blocker fixed; output caps at source; cancel races; honesty fixes | PASS | M4QA.md (9 findings) |
| M5 | MemoryScope + ProcessScope (id-based identities, tracemalloc/gc, allocator interposition, curated gdb profile, /proc evidence) | PASS | M5.md, ADR-0008 |
| M5QA | Side-effect-free tracer (no user repr/str), exception fidelity, generator frame identity, UI staleness, realloc accounting | PASS | M5QA.md (6 findings) |
| M6 | OptimizationLab (O0/O1/O2 with host-clang oracle), benchmarks (uninstrumented, warmup-excluded, ≥5 samples, checksum guard), 5 pair comparisons | PASS | M6.md, ADR-0009 |
| M6QA | Level-digest distinctness oracle, host-asm fingerprint equality, stats recomputation, dis oracle, UI label honesty | PASS | M6QA.md |
| M7 | Exactly 20 real programs (5+5+10), guided 3-level stories, capability matrices, Error Microscope (4 genuine fixtures), sanitized reports, Demo Library UI | PASS | M7.md, DEMO_CATALOG.md |

## Cross-cutting guarantees (current state)

- Real Clang 18.1.3 and CPython 3.12.3 pipelines; no mock artifacts anywhere in
  acceptance paths.
- All untrusted execution inside restricted containers: network none, read-only
  rootfs, cap-drop ALL, no-new-privileges, uid 1000, tmpfs, memory/cpu/pids
  caps, byte-capped outputs, external timeouts with force-removal, startup
  reconciliation. No Docker socket in containers. GitHub-imported code NEVER
  executes; demo-link/debug profiles are content-hash-gated (403 otherwise).
- Benchmarks: uninstrumented, warmup-excluded, ≥5 samples, per-sample wall+CPU,
  checksum guards, environment provenance; no universal speed claims.
- Memory/process evidence: observed-only with observed/derived/unavailable
  classes; secret-name redaction; no user code executed by the tracer.

## Launch instructions (fresh machine / second account)

1. Install: Windows + WSL2 Ubuntu-24.04, Docker engine in WSL, Node 20+, and
   the repo at `E:\ComplieVista` (do NOT rename; the path is load-bearing).
2. Backend: `wsl.exe -d Ubuntu-24.04`, then
   `cd /mnt/e/ComplieVista/backend && python3 -m venv .venv &&
   .venv/bin/pip install -r requirements.txt` (or reuse the committed
   requirements), then
   `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123`.
3. Frontend: `cd frontend && npm ci && npm run dev` (Vite on 5173, proxies /api
   to 8123).
4. Images: `docker build -t compilevista/analyzer:m2 sandbox/analyzer &&
   docker build -t compilevista/runtime:m4 sandbox/runtime &&
   docker build -t compilevista/debug:m5 sandbox/debug` (record the ids and
   update docs/milestones manifests if they change).
5. Open http://127.0.0.1:5173 — Home (proof), Source Workspace (paste/upload/
   ZIP/GitHub import), Demo Library (20 programs + Error Microscope), Compare
   (5 pairs).
6. Tests: `backend/.venv/bin/python -m pytest backend/tests -q` from the repo
   root (191 tests), E2E `python e2e/m{1..7}_journeys.py` from Windows.

## Upload/ZIP guidance for the user audit

Exclude: `.git/`, `node_modules/`, `backend/.venv/`, `frontend/dist/`,
`backend/data/` (SQLite + artifacts — regenerable), `__pycache__/`,
`/tmp` outputs, any `.env`. Keep: all source, `sandbox/`, `docs/` (evidence),
`e2e/`, `scripts/` (incl. `m7_verify_demos.sh`, `m7_gen_manifest.py`),
`evidence/`, lockfiles. No secrets exist in the repo (verified by scan).
