# ADR-0009 — OptimizationLab, benchmarks, and pair comparison (M6)

Status: Accepted (M6)

## Decision

1. **Experiments ride the existing orchestration patterns** (`services/experiments.py`):
   one bounded worker thread, argv-array docker invocations, the same restricted
   `_BASE_FLAGS` as M4/M5, `run_capped` with byte caps, defensive reads, forced
   container cleanup, and startup reconciliation. There is NO second executor.
2. **C optimization builds** (`c_opt_worker.py`, analyzer image): the immutable
   snapshot source is compiled at `-O0/-O1/-O2` (+ `-g -no-pie
   -fno-omit-frame-pointer`, recorded verbatim) producing IR (`-S -emit-llvm`),
   assembly, object, linked executable, and `llvm-nm-18 -S` symbols per level,
   each with digests, sizes and per-step durations. Clang version/target are
   recorded. Optimization remarks are marked available only when the compiler
   actually emitted them. No pass-level attribution is claimed beyond what the
   compiler reports.
3. **Benchmarks** (`bench_worker.py`, runtime image): uninstrumented executables
   (no `-finstrument-functions`, no settrace) are timed with warmup excluded,
   ≥5 samples (configurable 5–15), per-sample wall (monotonic) AND CPU
   (`RUSAGE_CHILDREN` delta for C, `process_time` for Python), median/min/max/
   stdev computed from stored raw samples. Checksums per run guard semantic
   equivalence across repeats AND levels (dead-code-elimination / divergence
   guard). Environment provenance: kernel, CPU model, cgroup v2 cpu/memory
   limits. Samples with median < 5 ms carry `resolution_warning` (documented
   workload bound; no invented precision). Python is measured on its own
   `py312` level — NO fake LLVM levels.
4. **Pair comparison** reuses the M4 execution pipeline end-to-end
   (`create_execution` for both sides). Five pair specs
   (`sandbox/fixtures/pairs/manifest.json`) are matched-input, deterministic,
   defined-behavior programs whose `expected_stdout` was verified with the HOST
   toolchain (clang-18 -O2 / CPython 3.12.3) independently of the container
   pipeline; both sides must match exactly. Signed-overflow in C is UB and is
   prohibited by pair policy (the sort checksum initially overflowed — caught
   by the host verification and fixed with a modulo checksum).
5. **Persistence** (`m6.v1`, additive): `experiments` + `experiment_stages`
   tables; artifacts content-addressed; reopening is deterministic (idempotent
   fingerprints; tested). Bounded text artifact excerpts (ir/asm/symbols ≤ 24 KB
   per view, ≤ 64 KB stored) with provenance.
6. **Honesty rules**: static assembly counts are never presented as executed
   instruction counts; source spans are not assumed to survive optimization;
   cross-language rails are synchronized by concept only; "C faster than
   Python" claims are never made from single runs (samples, variability and
   environment are always shown).

## Consequences

- Benchmarks measure the container's throttled environment (0.5 CPU, 256 MB);
  they are internally comparable but not representative of unthrottled hardware.
- Microbenchmark scale is bounded by the fixtures; `resolution_warning` marks
  sub-5 ms medians instead of inventing precision.
- GitHub-imported snapshots are refused for experiments (fail-closed), same as
  executions.
