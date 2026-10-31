# M4QA Test Evidence — Adversarial Runtime/Sandbox Audit & Surgical Repair

Date: 1 November 2026. Scope: M4QA only (second-pass skeptical audit of M4 execution;
no M5 work started). **This is STILL a same-agent self-audit, not an independent
external review** — the M4 self-report was treated as an untrusted hypothesis and
re-verified from code, live containers and fresh oracles.

Baseline before any edit: clean tree at `6c34e39`; ancestry M0→M4-G0 verified;
backend suite re-run (143 total: 139–140 passed, 3–4 honest GitHub rate-limit skips).

## Findings, reproduction, repair

| ID | Severity | Finding | Reproduction (pre-repair) | Repair | Regression test |
|---|---|---|---|---|---|
| CV-M4QA-01 | **Blocker** | Run TIMEOUT killed only the `docker run` CLI — the container stayed Up forever (until API restart). M4.json G4 "no ghost containers" was false for executions. | Probe: spin job → TIMEOUT → `docker ps` showed `cv-exec-… Up 36 s` (1.75 GB-class CPU burn unbounded). | `docker rm -f` of the exec container on run timeout and of the build container on build timeout (`execution.py`). | `test_m4qa01_timeout_force_removes_run_container`, `test_m4qa01_build_timeout_handler_removes_build_container` |
| CV-M4QA-02 | High | Python `stdout.txt` on the host bind mount was unbounded. | Probe: 10 s flood → **1 748 463 616 bytes (1.75 GB)** on host disk; orchestrator later `read_bytes()` into host RAM. | Harness redirects fd 1 through a draining pump that persists ≤ 1 MB and discards the rest, then records `stdout_truncated` in the trace meta; orchestrator additionally reads files through `_read_capped` (defense in depth). | `test_m4qa02_python_stdout_capped_and_flagged` (3 MB flood → artifact ≤ 1 MB, flag=1) |
| CV-M4QA-03 | High | C `trace.jsonl` unbounded (5000-event cap applied only after full read + artifact store write). | Probe: looping instrumented binary, 10 s → **442 607 049 bytes (442 MB)** trace file. | Shim stops writing at 5000 events and emits `{"kind":"meta","truncated": true}`; orchestrator capped reads + parsed meta flags. | `test_m4qa03_c_trace_capped_at_5000_events` (1M calls → exactly 5000 events, flag=1, artifact < 1 MB) |
| CV-M4QA-04 | Medium | `POST /api/v1/executions` and `POST /api/v1/analyses` read unbounded bodies (F05 fixed the other endpoints, missed these). | Code inspection + test with 2 MB body. | `_capped_receive_call` (1 MB) on both endpoints. | `test_m4qa04_execution_and_analysis_bodies_capped` (413 PAYLOAD_TOO_LARGE) |
| CV-M4QA-05 | Medium | `/capabilities` still claimed `pasted_execution: BLOCKED` after the M4 gate passed (UI home page repeated it); M4.json recorded a **wrong analyzer image id** (`8f1234168b12…` — the real pre-M4-commit image was `061d3d8b958e…`). | Code inspection; `docker image inspect` + commit timestamps. | Modes now `PARTIAL` with accurate notes; M4.json/M4.md image ids corrected; `e2e/m1_journeys.py` expectation updated to PARTIAL. | `test_m4qa05_capabilities_report_partial_paste`, M1 journey |
| CV-M4QA-06 | Medium | Cancel during the C build phase left `cv-build-*` running; cancel racing container start could leave the container running its full wall clock; a cancel that killed the container before the flag committed could be recorded COMPLETED. | Code inspection + flaky reproduction (job ran 30 s post-cancel / COMPLETED-after-cancel observed). | Cancel commits `cancel_requested` BEFORE `rm -f`; kills both `cv-exec-*` and `cv-build-*`; retried rm -f window; runner checks the flag before launching containers and before/after runs. | `test_m4qa06_cancel_during_run_removes_containers` (3× stable, ~4 s) |
| CV-M4QA-07 | Low | `db.py` migration had an unreachable `SCHEMA_MISMATCH` branch (dead second `elif`) — mismatch was silently "upgraded" with no diagnostic path. | Code inspection. | Dead branch removed with comment. | Existing `test_db_migrates_from_m1_v1` still green |
| CV-M4QA-08 | Low (honesty) | `ready_for_controlled_execution` was hard-coded `False` while the UI offered a working Run button — the "execution: gated by M4" chip contradicted reality. | UI code inspection + M1 journey failure after capabilities fix. | Target list computes readiness from the actual admission rule (eligible class + non-GitHub origin). | `test_m4qa08_readiness_flag_matches_admission`, M1 journey asserts Run button |
| CV-M4QA-09 | Low (hygiene) | Job-dir cleanup failures were silent: M4-era root-owned leftovers persisted (fallback ran before the runtime image existed and its failure was invisible); a process killed mid-job leaks its job dir. | Found 3 M4-era leftover dirs (19:25–19:59 UTC) + 1 fresh pytest-exit leak. | Shared `staging.remove_disposable_dir` (retry against EBUSY, privileged fallback, **loud warning on failure**) used by BOTH orchestrators; startup reconciliation now mops up orphaned `execution-*` dirs. | Full-suite leak check: 0 leftover dirs after final runs |

All repairs are localized; no test was weakened. The M1 journey assertion and the
`test_api`/`test_m1_api` capability assertions were **corrected** to the honest M4
state (PARTIAL), not muted.

## Independent trace oracles (B) — fresh runs, distinct from M4 tests

`backend/tests/test_m4qa_oracles.py` (all real containers):

- **Python** (`test_python_oracle_event_parity`): fresh source with tree-recursive
  fib(6), caught ZeroDivisionError (return-during-exception), a consumed generator,
  and a real `import`. An independently written host tracer provides the oracle.
  Full (kind, fn) multiset parity; structural facts recomputed by hand: fib 25
  calls / 25 returns (2·F(7)−1), divider 1 exception event, generator 5 calls /
  5 returns (each yield suspends as a `return`; each resumption re-fires `call`
  — verified against the host oracle, not assumed). Container-only events are
  exactly the importlib machinery frames, all before the first user call.
  stdout verified: `8 None 4 12 4`.
- **C** (`test_c_oracle_call_counts_and_symbols`): static counts alpha×3, beta×1,
  main×1 with balanced call/return pairing in sequence, all symbols resolved via
  llvm-nm (no raw `0x…` fallback), `ts_ms` present, real exit code 19 (computed,
  not canned).
- **Replay** (`test_replay_pagination_is_stable_and_ordered`): identical repeated
  reads are byte-identical (no re-execution), ordered seqs, 64-hex checksums.

## Trust boundary review (A)

Live `docker inspect` of a RUNNING `cv-exec-*` container (captured during an
infinite-loop execution, pre-repair image):

```
NetworkMode none · Privileged false · CapDrop ALL · SecurityOpt no-new-privileges
Memory 268435456 · NanoCpus 500000000 · PidsLimit 64 · ReadonlyRootfs true
Binds: …/src:/work:ro, …/run:/out · User 1000:1000 · Tmpfs /tmp rw,size=16m,noexec
Cmd: python3 /opt/runtime/py_trace_harness.py --file spin.py --out /out
```

- Input path re-traced end-to-end: HTTP body → typed errors → snapshot artifacts
  (content-addressed) → admission (origin + eligibility; GitHub 403 fail-closed)
  → job store → argv-array docker invocation (no shell strings anywhere) →
  capped output reads → checksummed event pagination → API → UI.
- No user-controlled docker flags, entrypoints, or image refs exist on any path.
- Build/run images rebuilt from the audited sources (analyzer `sha256:fa9621bb…`,
  runtime `sha256:3d13eada…`); the runtime image still has NO compiler.
- Canary + network containment re-proven by the M4 suite (still green).
- The privileged-cleanup fallback mounts only the jobs parent with fixed argv
  `rm -rf /jobs/<jobs-root-name>/<execution-id-dir>` — internally generated
  names only; failure is now loud (CV-M4QA-09).

## Failure modes exercised (C)

Timeout (run + build paths), cancel-during-run (3× stable), cancel racing launch
(fixed + tested), API-restart reconciliation (pre-existing, still green), flood
(stdout, C trace, pids — all capped/contained), malformed trace JSON (existing
`unparsed` path), GitHub-origin 403, docker-unavailable BLOCKED paths (existing
M2 tests), body caps on all POST endpoints. Not exercised live: daemon down /
CLI missing (covered by existing unit tests via monkeypatch), image absent
(BLOCKED path unit-covered).

## UI (D)

- Run button appears only for eligible pasted/uploaded targets (origin-gated);
  GitHub-imported code shows no Run control (fail-closed) — re-verified in browser.
- Replay is read-only navigation over recorded events with the explicit
  "does not rewind" banner; stale-analysis protections unchanged.
- Honest readiness chip now matches admission (CV-M4QA-08).

## Final gate results (fresh, post-repair)

```
Backend:  154 passed / 0 failed / 0 skipped   (pytest backend/tests; incl. 14 new M4QA tests)
E2E:      M3 6/6 PASS (incl. M4 execution, github-no-run, timeout) · M2 3/3 · M1 5 journeys PASS (1 reasoned skip)
TSC:      clean.  Vite production build: OK (376 kB bundle).
Leak check: 0 leftover analysis-*/execution-* job dirs; 0 cv-exec-/cv-build- containers.
```

The M1 skip: real GitHub import journey — unauthenticated GitHub rate limit
exhausted (backend typed `RATE_LIMITED` probed pre-flight; skip recorded with
reason, never a silent pass). It passed on reset windows in M1/M4 evidence.

## Residual limitations (unchanged or newly documented)

1. GDB/ptrace remain UNSUPPORTED by policy (ADR-0007) — unchanged.
2. A process killed mid-job still cannot clean up in the moment; the next API
   start reconciles containers, marks RUNNING→FAILED, and (new) removes orphan
   job dirs. No data loss (source/outputs are content-addressed before cleanup).
3. Container files written to `/out` are read through a defensive 8 MB trace /
   1 MB stdout host-side cap even though the in-container caps bound them first.
4. Docker+WSL2 shares one kernel with the host — Docker is not an unconditional
   sandbox; the README §10/M9 deployment review remains mandatory before any
   non-local execution exposure. Local-only execution policy unchanged.
