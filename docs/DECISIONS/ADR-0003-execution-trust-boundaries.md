# ADR-0003 — Execution trust boundaries

Status: Accepted (M0); full enforcement and adversarial validation remain M4 gates

## Context

README §10: Docker/WSL2/`subprocess` are not sandboxes by themselves; `hello-world`
proves connectivity only. The user's Docker group membership is host-equivalent
privilege inside the WSL VM.

## Decision

1. **Three modes (README §10)** are implemented as policy now: Mode A (read-only static
   analysis) is the only mode M0 exercises end-to-end. Mode B (curated execution) is
   proven *feasible* with a restrictive Docker baseline (Deliverable F) but is not opened
   to users. Mode C (pasted code) stays **BLOCKED** until the M4 security gate.
2. **M0 restrictive container baseline** (all flags accepted by Docker 29.9.2 in probes):
   `--network none`, `--read-only`, writable `--tmpfs /tmp` (size-capped), `--cap-drop ALL`,
   `--security-opt no-new-privileges`, default seccomp profile, `--user` non-root UID,
   `--memory`, `--cpus`, `--pids-limit`, `--ulimit fsize`, no published ports, no Docker
   socket or privileged host mounts, `--rm`, external wall-clock `timeout`.
3. **ptrace/GDB-in-container is declared UNSUPPORTED in M0.** We do not loosen the default
   profile to enable debugging; a segregated debug profile is a later, explicitly gated
   decision (README §10, §19).
4. **Orchestration privilege.** Only trusted orchestration code (backend worker, feasibility
   script) touches Docker, via argv arrays; container specs are fixed by us, never built
   from untrusted strings.
5. **No safety claim.** M0 records what was tested (curated fixtures, timeout+cleanup) and
   what was not (adversarial escape tests = M4). This ADR and docs/SECURITY.md are the
   canonical residual-risk record.

## Consequences

- Execution defaults stay closed; feasibility does not become a feature.
- Any later loosening requires a new ADR with negative-test evidence.
