# M6QA Test Evidence — Optimization/Comparison Oracle Audit & Repair

Date: 1 November 2026. Scope: M6QA only (M7 NOT STARTED). **SAME-AGENT second-pass
self-audit — explicitly NOT an independent external review.** M6's self-report
was treated as an untrusted hypothesis.

Entry gate: M6/M5QA/M4QA all PASS on disk, ancestry `6f9deb9` verified; a fresh
-O0/-O2 oracle and a matched C/Python execution were re-run BEFORE judging M6.

## Independent oracle results (fresh runs, separate from M6 tests)

Script (run live, retained in evidence below as recorded output; logic
documented here and encoded as permanent tests):

1. **Per-level digest distinctness**: a fresh opt experiment produced three
   DISTINCT IR digests and three DISTINCT asm digests (O0 `b1a1913d…`,
   O1 `923f3765…`, O2 `0da9dd97…`; exe sizes 16944/17216/17096 B) — the code is
   not compiled once and relabeled (Q1).
2. **Fresh host compile vs container asm**: with the recorded flags, host
   clang-18 output matched the container's assembly EXACTLY at O0 and O2 under
   a path-independent fingerprint (debug `.file`/`.loc` lines legitimately
   embed the build path) — 64-bit fingerprint equality both levels (Q1).
3. **Benchmark stats recomputation**: stored raw samples recompute to the
   stored median/min/max/stdev exactly (O0 0.593 ms, O1 0.429 ms, O2 0.379 ms
   medians; n=5 each; stdev match) — no fabricated or misderived statistics (Q3).
4. **Python dis oracle** (`test_m6qa03`): host CPython 3.12 `dis` structure
   (instruction count and code-object count) equals the pinned container
   analysis for the same source; adaptive specialization is a runtime
   phenomenon and is not claimed in static bytecode evidence (Q1/Q2).

## Findings (reproduced, repaired, regression-tested)

| ID | Severity | Finding | Repair | Regression |
|---|---|---|---|---|
| CV-M6QA-01 | Medium | OptimizationLab kept the previous target's experiment ids/results when the selected file changed (M5QA staleness class回归). | State resets on snapshot/target change. | `test_m6qa01` (per-target fingerprint isolation at API level) |
| CV-M6QA-02 | Medium | Compare rail showed the execution `duration_ms` unqualified — that number includes container + interpreter startup and invites false "C vs Python speed" comparisons against benchmark medians. | Relabeled "container wall … includes runtime startup — **not comparable** to OptimizationLab benchmark medians". | `test_m6qa02` (UI honesty text asserted) |
| CV-M6QA-03 | Low (verification) | Python version pinning had no automated cross-check. | `dis` oracle test added (host 3.12 vs pinned container analysis). | `test_m6qa03` |
| CV-M6QA-04 | Low (verification) | Artifact integrity + second-process reopen had no digest-level check. | Content-address verification of all 9 opt artifacts; no-container-on-reopen asserted. | `test_m6qa04` |

Challenge classes with NO defect found (checked, documented):
- Tool diagnostics vs inferred diffs: remarks availability is recorded only when
  the compiler emitted them; diffs are computed from real stored artifacts.
- No XSS surface: zero `dangerouslySetInnerHTML` in the frontend (React escapes).
- No benchmark/unit conversion errors: recomputation matches; units explicit
  (ms) with wall vs CPU separated; traced (M4/M5 records) vs uninstrumented
  (bench) numbers are labeled non-comparable after CV-M6QA-02.
- C/Python input equivalence: pair arithmetic re-verified (host oracles from M6
  still agree); integer boundaries respected (pair policy bans signed overflow —
  enforced since M6 by the modulo checksum after the host verification caught it).
- Result consumption: bench checksums prove the workload output is produced and
  identical across levels (dead-code elimination guard).
- Persistence reopen: same digests, no docker activity, deterministic (Q4).
- M4 sandbox restrictions and M5 provenance intact: full adversarial suites
  green in the final backend run (183/0/0).

## Final gate results (fresh, post-repair)

```
Backend:  183 passed / 0 failed / 0 skipped  (incl. 4 new M6QA regressions)
E2E:      M6 2/2 (with relabeled duration) · M5 4/4 · M3 incl M4 6/6 · M2 3/3 · M1 5/5
TSC:      clean.  Vite build: OK (397 kB).
Oracle:   distinct level digests; host-asm fingerprint equality; bench stats recompute exactly
```

## Residual risks

1. Same-agent audit — the independent external audit remains M9.
2. Benchmark numbers are container-throttled and single-machine (documented in
   ADR-0009); cross-level comparisons only.
3. Sub-5 ms pair-fixture medians remain flagged `resolution_warning`; M7 should
   scale workloads for publication-grade timing.
4. The asm fingerprint oracle strips path/debug lines; content-bearing
   differences would still be caught (verified: distinct per level).
