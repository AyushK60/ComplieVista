# Handoff after M4QA — adversarial runtime/sandbox audit & repair

Date: 1 November 2026. Scope: M4QA only. **M4QA verdict: PASS** — all exit gates
Q1–Q6 green. Per the stage contract, M4QA PASS authorizes M5; nothing of M5 has
been started.

## What M4QA changed (relative to M4 at `6c34e39`)

- **Blocker fixed (CV-M4QA-01)**: run/build TIMEOUT previously killed only the
  `docker run` CLI, leaving the container running forever. The orchestrator now
  `docker rm -f`s the exec container on run timeout and the build container on
  build timeout.
- **Resource caps at the source**: the Python harness caps stdout at 1 MB (drain
  + in-band `stdout_truncated` meta flag); the C shim stops at 5000 trace events
  with an in-band truncated marker. The orchestrator additionally reads all
  container-written files through defensive caps (`_read_capped`) and never
  trusts file sizes. Probes pre-repair: 1.75 GB stdout / 442 MB trace in 10 s.
- **Cancel is now flag-first**: `cancel_requested` commits before `rm -f`, both
  `cv-exec-*` and `cv-build-*` are killed, the worker refuses to launch
  containers after a cancel, and a killed run can no longer be recorded
  COMPLETED.
- **Body caps** added to `POST /api/v1/executions` and `/api/v1/analyses`.
- **Honesty fixes**: `/capabilities` now reports `pasted_execution: PARTIAL`
  (the M4 gate passed); target readiness reflects the real admission rule
  (no contradictory "gated by M4" chip next to a working Run button); the M4
  manifest/evidence analyzer image id was corrected (`8f1234168b12…` was wrong;
  pre-M4-commit reality was `061d3d8b958e…`).
- **Cleanup robustness**: shared `staging.remove_disposable_dir` (retry against
  mount-teardown races, privileged fallback bounded to the jobs parent, LOUD
  failure), used by both orchestrators; startup reconciliation mops up orphaned
  `execution-*` job dirs. Silent cleanup failures were proven by M4-era
  leftovers and can no longer disappear silently.
- **Images rebuilt** from the audited sources:
  analyzer `sha256:fa9621bbd919…`, runtime `sha256:3d13eada5686…` (runtime still
  has no compiler).
- Dead `SCHEMA_MISMATCH` branch removed from the db migration.

## Verification (fresh, post-repair)

- Backend: **154 passed / 0 failed / 0 skipped** (includes 9 audit regressions in
  `backend/tests/test_m4qa_audit.py` and 3 fresh independent oracles in
  `backend/tests/test_m4qa_oracles.py` — real containers, no mocks for
  acceptance).
- E2E (real browser → Vite → FastAPI → Docker): M3 incl. M4 **6/6**, M2 **3/3**,
  M1 5 journeys PASS with 1 reasoned skip (GitHub unauthenticated rate limit;
  typed RATE_LIMITED probed pre-flight, never a silent pass).
- TSC clean; Vite production build OK.
- Leak check after full runs: 0 `cv-exec-`/`cv-build-` containers, 0 leftover
  job dirs.
- Evidence: `docs/TEST_EVIDENCE/M4QA.md`; manifest `docs/milestones/M4QA.json`.

## Honest scope statement

M4QA was a **second-pass self-audit by the same agent** — it re-verified M4 from
code and live containers and repaired 9 findings (1 blocker, 2 high, 3 medium,
3 low), but it is NOT an independent external review. That remains M9.

## Environment notes

- Backend dev server: WSL uvicorn on `127.0.0.1:8123`; Vite on `5173` proxies
  `/api`. Windows port 8000 occupied (M0 note).
- The M1 real-GitHub E2E journey skips with a recorded reason while GitHub's
  unauthenticated rate limit is exhausted; it passes on reset windows.

## Next

M5 (MemoryScope/ProcessScope) is **authorized but NOT STARTED**. Entry checks
for any future stage: verify git ancestry includes the M4QA commit, re-read
`docs/milestones/M4QA.json`, and do not infer authorization from queued prompts
if any gate is found failing.
