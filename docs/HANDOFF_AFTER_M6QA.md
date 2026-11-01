# Handoff after M6QA — Optimization/comparison oracle audit & repair

Date: 1 November 2026. Scope: M6QA only. **M6QA verdict: PASS** (gates Q1–Q5
green). **M7 is authorized per the stage contract; M7 itself has NOT been
started.**

## What M6QA changed (relative to M6 at `6f9deb9`)

The second-pass self-audit (SAME-AGENT — not an external review) ran independent
oracles before judging M6, then fixed two UI honesty/staleness defects and
locked two verification gaps with permanent tests:

- **Independent oracles (all clean)**: fresh opt experiment → three distinct IR
  and asm digests per level (no single-level relabeling); fresh host clang-18
  compiles match container assembly exactly at O0/O2 under path-independent
  fingerprints; stored benchmark medians/stdev recompute exactly from raw
  samples (n=5 each); host CPython 3.12 `dis` structure equals the pinned
  container analysis.
- **CV-M6QA-01 (medium)**: OptimizationLab carried the previous target's
  experiment state across target changes — reset on snapshot/target change
  (same class as the M5QA stale-evidence fix).
- **CV-M6QA-02 (medium)**: the Compare rail's `duration_ms` includes container
  + interpreter startup; it now says so and is explicitly marked NOT comparable
  to benchmark medians (misleading-comparison channel blocked/explained, not
  silently permitted).
- **CV-M6QA-03/04 (verification gaps closed)**: Python `dis` oracle test
  (host 3.12 == pinned container) and content-address digest verification of
  all opt artifacts plus no-container-on-reopen.

Challenge classes verified clean: no XSS surface (no dangerouslySetInnerHTML),
no unit-conversion or stats-derivation errors, no tool-diagnostic-vs-inference
conflation, C/Python input equivalence holds (host oracles), result consumption
guarded by checksums, persistence reopen deterministic, M4 sandbox and M5
provenance suites intact.

## Verification (fresh, post-repair)

- Backend **183/0/0** (4 new M6QA regressions + all prior suites/adversarials).
- E2E: M6 2/2 (with the relabeled rail), M5 4/4, M3 incl. M4 6/6, M2 3/3,
  M1 5/5. TSC clean; vite build OK.
- Oracle evidence recorded in `docs/TEST_EVIDENCE/M6QA.md` and
  `docs/milestones/M6QA.json`.

## Residual risks

1. Same-agent audit; the independent external audit remains M9.
2. Benchmarks are container-throttled (0.5 CPU) — same-environment comparisons
   only; sub-5 ms medians flagged; M7 should scale workloads for publication
   grade numbers.

## Next

**M7 (20-program demo suite) is authorized but NOT STARTED.** Its seed: the
five verified pair specs, the fixture conventions (deterministic, UB-free,
bounded), and `scripts/dev/m6_verify_pairs.sh` (extend for new programs).
Entry checks for M7: ancestry includes the M6QA commit, manifests PASS, sandbox
suites re-run green; never infer authorization from queued prompts if a gate
fails.
