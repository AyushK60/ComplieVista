# HANDOFF AFTER M3 — fresh-session resume document

Written 31 October 2026 after M3 PASS. Companion to `docs/HANDOFF_AFTER_M2.md` (still
accurate for launch commands, architecture and constraints); this file adds M3 state.

## What M3 added

- **Graph API**: `GET /api/v1/analyses/{id}/stages/{stage}/graph` (schema `m3.graph.v1`)
  — C/Python AST containment trees (EXACT), LLVM function/basic-block CFG (DERIVED from
  real terminators), CPython code-object/instruction maps with jump edges (DERIVED).
  Caps 2000/4000 with truncation flags. Table/raw views preserved for every stage.
- **Graph canvas** (`frontend/src/components/GraphView.tsx`): @xyflow/react v12 with a
  dependency-free deterministic layered layout in a Web Worker (ELK attempt failed in
  module workers — ADR-0006), semantic zoom (information changes at 0.35/0.8/1.4 zoom
  thresholds), minimap, controls, search with hit dimming, double-click collapse,
  node click → inspector + source-line highlight. Virtualized rendering.
- **Inspector** (`Inspector.tsx`): Simple/Detailed/Technical explanation levels derived
  deterministically from real fields; mapping confidence, incoming/outgoing edges,
  artifact digests, snapshot identity, limitations — Evidence Ledger V1.
- **Source view**: read-only CodeView with keyword/string/comment coloring,
  highlight + scroll-to-line. Monaco attempted and deferred to M8 (ADR-0006).
- **Hardening**: streaming request-body cap (chunked/missing Content-Length safe).
- **Latent M2 bug fixed**: clang AST children-list corruption (parent index captured
  before recursion); AST containment now provably a tree (tested).

## Launch / test commands

Same as HANDOFF_AFTER_M2 (backend :8123, Vite :5173). New:
- Tests: `backend/.venv/bin/python -m pytest backend/tests -q` (126 tests)
- E2E (Windows): `python e2e/m1_journeys.py`, `m2_journeys.py`, `m3_journeys.py`
- Graph evidence: `docs/TEST_EVIDENCE/m3/*.png`; perf numbers in `docs/TEST_EVIDENCE/M3.md`.

## Key M3 constraints to preserve

1. Graph nodes/edges come ONLY from `m3.graph.v1` payloads — never invent nodes/edges.
2. Semantic zoom changes information, not just scale (thresholds 0.35/0.8/1.4).
3. Source→IR/assembly mapping stays UNAVAILABLE until real debug-span metadata justifies it.
4. Fetch/layout race guards (sequence tokens) — any new async view must be stale-guarded.
5. Editor is read-only; editing ⇒ new snapshot ⇒ new analysis.

## Milestone status

M0 PASS · M1 PASS · M2 PASS (CONDITIONAL→closed by M2.5 PASS) · M3 PASS.
Next: M4 (safe execution & replay) — requires the README §10 admission gate and a fresh
security review; do not start without explicit authorization and audit of M3 evidence.
