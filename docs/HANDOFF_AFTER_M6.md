# Handoff after M6 — OptimizationLab, Cross-Language Comparison & Benchmarks

Date: 1 November 2026. Scope: M6 only. **M6 verdict: PASS** (gates G0–G7 green).
M6QA audit is authorized on this PASS per the stage contract; **M7 has NOT been
started** (5 pair specs prepared as the M7 seed — the 20-program suite remains
M7 work).

## What M6 added

- **Experiments service** (`services/experiments.py`, schema `m6.v1` additive):
  one bounded worker thread, the same restricted docker baseline as M4/M5, no
  new privilege surface, GitHub origins refused. Kinds: `opt` (C builds at
  -O0/-O1/-O2 with recorded verbatim flags, IR/ASM/object/exe/symbols per level
  with digests/sizes/durations/tool version+target), `bench` (uninstrumented
  timing), `compare` (pair comparison through the real M4 execution pipeline).
- **OptimizationLab UI** (Workspace, C targets): per-level build table, A/B
  assembly diff (bounded LCS line diff), benchmark table with wall/CPU medians,
  variability, checksum guard, cgroup provenance, resolution warnings.
- **Compare page** (`/compare`): five pair specs with host-verified expected
  outputs; one click runs a real paired experiment (snapshot creation + both
  executions + expected-output check); two independent rails with measured
  execution ids linking back to M4/M5 replay/memory/process evidence.
- **Benchmark methodology** (ADR-0009): warmup excluded, ≥5 repeats, per-sample
  wall + CPU, checksum-per-run semantic guard, environment provenance (CPU
  model, kernel, cgroup limits), resolution warnings below 5 ms, no universal
  speed claims.

## Honesty rules established (do not regress)

- Static assembly is NOT an executed-instruction count (labeled in UI + API docs).
- Source-level constant folding (`2*21` at -O0) and uncalled-function
  elimination (every level) are NOT optimization-level effects — the M6 test
  documents both and only claims the genuine level transformation.
- Python has NO LLVM levels; its measured level is `py312`.
- Pair C programs must be UB-free; the verification script exists to catch
  violations (it caught signed-overflow UB in the sort checksum during M6).

## Verification

- Backend **179/0/0** (8 new M6 tests incl. host-clang oracle and all five
  pairs through real containers; all M0–M5QA regressions green).
- E2E: M6 2/2 (OptimizationLab + pair compare, desktop+mobile screenshots),
  M5 4/4, M3/M4 6/6, M2 3/3, M1 5/5. TSC clean; vite build OK.
- Evidence: `docs/TEST_EVIDENCE/M6.md`, screenshots in `docs/TEST_EVIDENCE/m6/`,
  manifest `docs/milestones/M6.json`, ADR-0009, reproducibility script
  `scripts/dev/m6_verify_pairs.sh`.

## Environment notes

- Restart the backend (`127.0.0.1:8123`) after backend changes — a stale server
  silently serves old endpoints (bitten twice across M5/M6 E2E).
- WSL heredoc escaping mangles C `\n` sequences — write fixture files with the
  Write tool, not bash heredocs (three pair fixtures were mangled and fixed).
- Pair expected outputs are pinned in the manifest; re-verify with
  `scripts/dev/m6_verify_pairs.sh` after ANY fixture edit.

## Next

**M6QA authorized.** M7 (20-program suite) NOT STARTED; its seed is the pair
manifest plus the fixture conventions (deterministic, UB-free, bounded, verified
expected outputs — extend `m6_verify_pairs.sh` for new programs).
