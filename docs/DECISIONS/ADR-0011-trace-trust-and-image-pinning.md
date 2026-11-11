# ADR-0011 - Trace channel integrity, trust labeling, and immutable image identity (Stage 8)

Status: Accepted (Stage 8 repairs finding from the independent stage 7 review audit).

## Context

The stage 7 review audit found: (finding) arbitrary pasted Python executes in the tracer's
own interpreter and shares a writable `/out` bind mount, so a target could forge
or rewrite trace artifacts or disable tracing; (finding) `docker run` argvs used
mutable tags (`compilevista/runtime:m4` etc.) while only *recording* the resolved
image ID; (finding) Python benchmark checksums covered only `str(return)`, so a
workload printing different output per repetition could claim identical
checksums; (finding) trace previews used `isinstance(x, list)` + `len(x)`,
invoking user-defined `__len__`.

## Decision

1. **Protected Python trace channel (finding).** Python trace runs mount NO
   writable host path: only `/work:ro`. `py_trace_harness.py` is the privileged
   observer and multiplexes all artifacts over the container stdout pipe as
   framed JSONL (`{"c":"t"|"m"|"p"|"out"|"meta", ...}`). User-level stdout is
   redirected to an internal capture pipe, so `print` cannot inject frames. The
   orchestrator (`parse_framed_stream`) validates: meta frame present and LAST,
   authoritative event count equals received trace frames, zero foreign frames,
   stdout cap not hit. Any violation ⇒ `trace_integrity = SUSPECT`, never
   silently promoted. The harness reports `trace_disabled_by_target` when the
   target replaces/removes the installed tracer. C runs keep the shim file
   channel and now end with a `trace_meta` record whose event count is verified
   the same way.
2. **Honest trust labeling (finding).** Every execution records
   `trace_trust`: `CURATED_COOPERATIVE` only for curated-manifest snapshots
   (regression-tested cooperative targets), `UNTRUSTED_TARGET` for everything
   else (pasted/uploaded). The label is surfaced in the API execution record,
   the UI (ExecutionPanel warning: events are NOT guaranteed genuine), and
   exported evidence. Residual risk is documented, not hidden: the target
   shares the pid/uid domain, so a `/proc/self/fd` scan could in principle
   reach the observer channel fd; full trust-domain separation is future work
   before any public exposure.
3. **Immutable image identity (finding).** `resolve_image_id(tag)` resolves the
   `sha256:` image ID immediately before every `docker run`; argv uses that ID,
   never the tag. The IDs resolved at submission are stored
   (`requested_image_ids`) and re-verified at run start; mismatch ⇒ BLOCKED
   `IMAGE_ID_CHANGED`, unresolvable ⇒ BLOCKED `IMAGE_ID_UNAVAILABLE` (fail
   closed TOCTOU). Recorded `image_id`/`build_image_id` always match the
   launched images. Applies to analysis, execution (C build + run, demo-link,
   debug), OptimizationLab and benchmarks. Only job-dir cleanup fallback keeps
   a tag (not reproducibility-sensitive).
4. **Benchmark checksums (finding).** Per-repeat checksum = SHA-256 over
   captured stdout + bounded return `repr` (≤200 chars, guard-guarded) +
   exception type (Python) or exit code (C). A workload whose output varies per
   repetition can never produce identical checksums;
   `levels_semantics_equivalent` additionally requires every level to be
   internally identical. A raising `main()` is data (recorded per repeat), not
   a crash; warmup tolerates raising workloads.
5. **Safe previews (finding).** `len()` is applied only to EXACT built-in
   container types (`type(v) is list` etc.); subclasses get identity-only
   treatment without `len()`. `repr`/`str` remain restricted to exact
   primitives and builtin-module exception types (existing stage 5 review rule).

## Consequences

- Pinned images must be rebuilt when sandbox code changes; the recorded IDs
  change with them (visible in evidence).
- Traces of untrusted pasted programs are explicitly NOT verifiable guarantees;
  UI and exports say so.
- The Python trace pipe cap is 32 MB (framed stream), trace events remain
  capped at 5000 in-band.

## Verification

`backend/tests/test_stage8_gate.py` (13 tests: real-container tamper/adversarial
fixtures + deterministic argv/tag-mutation/stream-validation units) and
`e2e/stage8_gate_journeys.py` (trust badges + Demo Library recovery).

## Rollback

Revert to tag `m8g0-baseline`; the schema additions are additive columns.
