# ADR-0005 - Restricted analyzer containers and the analysis job lifecycle

Status: Accepted (Stage 2)

## Context

Stage 1 accepts untrusted code; stage 2 must analyze it with real Clang/CPython. the project notes and the
Stage 2 prompt forbid running untrusted source through unrestricted privileged host
subprocesses. Stage 0 already proved the restrictive Docker baseline and recorded that external
timeouts leave containers alive unless the orchestrator forces cleanup.

## Decision

1. **One pinned analyzer image** (`compilevista/analyzer:m2`, image id recorded per run):
   `ubuntu:24.04` + `clang-18`, `llvm-18`, `binutils`, `libc6-dev`, `python3`, with two
   trusted worker scripts baked into `/opt/analyzer`. Built once with network; runs are
   network-less. The image id is stored on every analysis record (tool fingerprint =
   hash(image id + policy version)).
2. **Worker scripts hold ALL tool flags.** The orchestrator passes only the staged file
   path (validated, inside the read-only job mount); no user-supplied flags exist on this
   path. Workers write raw stage outputs + an incrementally-updated `manifest.json` to the
   per-job output mount, so a killed run keeps its completed stages.
3. **Container baseline** (per run): `--network none --read-only --tmpfs /tmp:rw,size=64m,
   noexec --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 --memory 512m
   --cpus 1 --pids-limit 128`, snapshot mounted read-only, per-job output dir mounted rw
   (disposable job space under `/home/khana/.cache/compilevista/jobs/analysis-<id>`),
   external wall-clock timeout (default 180 s, env-overridable) with **orchestrator-forced
   `docker rm -f` + inspect-verified cleanup**. No Docker socket ever enters a container.
4. **Job lifecycle**: `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED | TIMEOUT |
   BLOCKED` (BLOCKED when Docker is unavailable - honest, not faked). One bounded worker
   thread (concurrency 1); jobs persist in SQLite (`m2.v1`, additive upgrade from
   `m1.v1`); cancellation works while queued and is recorded as requested while running;
   idempotency on `(snapshot, target, tool fingerprint)` returns an existing
   COMPLETED/QUEUED/RUNNING analysis. Job directories are always cleaned.
5. **Normalization honesty**: raw outputs are content-addressed (audit trail); normalized
   items are capped (500) and carry per-item `mapping_confidence`. Clang places
   brace-delimited statements' position only in `range.end` (no `loc.line`); the
   normalizer chains `loc.line → range.end.line → line DERIVED from the exact
   tool-reported offset` and labels the last case DERIVED. CFG edges are DERIVED from real
   terminators; source→IR/assembly mapping stays UNAVAILABLE in stage 2.
6. **Stage degradation is per-stage**: e.g. a syntax-error C file yields PARTIAL/ERROR
   token+AST stages with verbatim diagnostics and no IR/assembly at all - never a faked
   green pipeline. A truncated AST capture (huge header-heavy TU) degrades only the AST
   stage.

## Consequences

- Untrusted code never touches a host-privileged compiler; the privileged surface is the
  trusted worker scripts plus the fixed container spec.
- Cost: one container launch per analysis (~250 ms) plus tool time; measured at 0.3–5 s
  per full C pipeline on small units.
- Limitations carried forward: unauthenticated GitHub rate limits; AppArmor/LSM
  customization unverified; default seccomp profile; ptrace/debugging still UNSUPPORTED.
