# CompileVista Project Status

Updated: 1 November 2026 (M8-G0)

## Current milestone: **M8-G0 — technical integrity repairs + one-click local launcher**

Status: **M8-G0 COMPLETE — see `docs/TEST_EVIDENCE/M8G0.md` and
`docs/milestones/M8G0.json` for per-gate verdicts and exact commands.**

All five M7QA findings repaired with real-container regression tests:
- **F-M7-01** Python trace integrity: protected framed stdout channel (NO
  writable `/out` mount in trace containers), orchestrator-side structural
  validation (meta-last, event-count consistency, foreign-frame detection),
  `trace_disabled_by_target` detection, and honest per-run trust labels
  (`CURATED_COOPERATIVE` vs `UNTRUSTED_TARGET`) in API/UI/evidence (ADR-0011).
- **F-M7-02** Immutable image identity: every `docker run` argv (analysis,
  C build/run, demo-link, debug, OptimizationLab, benchmarks) uses the
  resolved `sha256:` image ID; submission-time IDs re-verified at run start;
  fail-closed `IMAGE_ID_CHANGED` / `IMAGE_ID_UNAVAILABLE`.
- **F-M7-03** Benchmark checksums now cover stdout + bounded return repr +
  exception/exit status; varying-output workloads are flagged, never claimed
  equivalent.
- **F-M7-04** Trace previews use exact-type checks only (`type(v) is list`
  etc.); user-defined `__len__`/`__repr__` are never invoked.
- **F-M7-05** Demo Library API failures no longer replace the page: catalog
  chrome + data persist, accessible Retry control, live-API recovery verified
  in browser E2E.

One-click local launcher (ADR-0012, `docs/LOCAL_RUN_GUIDE.md`): `Start.cmd` /
`Stop.cmd` / `Status.cmd` in the repo root; PowerShell implementation under
`scripts/dev/`. WSL-session teardown-proof daemons (`setsid -f` + self-recorded
pids), identity-verified ownership (never kills unrelated processes), real
readiness gating, Docker Desktop user-level recovery, explicit missing-image
builds, port-conflict refusal with diagnostics.

Pinned image IDs after this milestone (rebuilt from updated sandbox code):
- `compilevista/analyzer:m2` = `sha256:800531b37e3ee64e85fa1c0d995512d0927c58b6a9f30026e4d7322130aa7373`
- `compilevista/runtime:m4` = `sha256:299a137a8238e7f1b76d9b600302b2cec36d5b89870f0e50f38272b74f6ae50d`
- `compilevista/debug:m5` = rebuilt from the same `c_trace_shim.c` (see
  `docker image inspect` output; the ID is recorded in every execution row).

## What exists now (cumulative)

- **M0–M7**: unchanged from M7QA (20 real programs, genuine static pipelines,
  restricted execution with recorded traces, MemoryScope/ProcessScope,
  OptimizationLab, pair comparisons, Error Microscope, 191-test security
  posture). See `docs/FINAL_M0_M7_FUNCTIONAL_MATRIX.md`.
- **M8-G0**: the repairs and launcher above; backend suite extended by
  `backend/tests/test_m8g0.py` (13 tests) and `e2e/m8g0_journeys.py`.

## Deliberately NOT done (no false claims)

- No M8 visual polish (Monaco, ELK stress-tuning, landing redesign,
  accessibility pass, export/history UI, Prediction Lab) — M8-G0 is NOT that.
- No M9 independent audit; no public/remote exposure; execution of
  GitHub-imported code remains BLOCKED.
- Full observer/target trust-domain separation (beyond the framed channel) is
  future work; `UNTRUSTED_TARGET` labeling is the honest interim contract.

## Next

**M8 visual redesign NOT STARTED** — awaiting explicit user go-ahead after
M8-G0 review. Then M9 independent audit.

## Active risks / quirks

1. Unauthenticated GitHub rate limit (60 req/h) — typed errors, no blind retries.
2. Vite on /mnt/e needs polling (M0 measurement); applied.
3. Windows port 8000 occupied by an unrelated process → backend dev port 8123.
4. WSL 3.0.3.0 tears down `wsl.exe` session process trees: the launcher's
   `setsid -f` daemonization is load-bearing (ADR-0012); `wsl -- sh -c` quoting
   mangles `$!` — always use `wsl -e`.
5. Trace trust: an untrusted target shares the pid/uid domain; a
   `/proc/self/fd` scan could in principle reach the observer channel fd —
   documented residual risk, labeled per-run (ADR-0011).
