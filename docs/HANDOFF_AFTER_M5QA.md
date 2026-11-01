# Handoff after M5QA — Memory/Process scientific audit & repair

Date: 1 November 2026. Scope: M5QA only. **M5QA verdict: PASS** (gates Q1–Q5
green). Per the stage contract, **M6 is authorized**; M6 itself has NOT been
started.

## What M5QA changed (relative to M5 at `6428a76`)

The second-pass audit (SAME-AGENT — not an external review) re-challenged every
memory/process claim class and found six issues, all reproduced live before
repair, all locked with named regressions (`backend/tests/test_m5qa_audit.py`):

1. **CV-M5QA-01 (high)** — the Python tracer executed user `__repr__` on
   primitive-subclass values (side-effect channel; its output even entered the
   stored evidence as if observed). Previews are now exact-type; subclasses get
   identity treatment. The traced program itself now proves `side-effects: 0`.
2. **CV-M5QA-02 (medium)** — CPython 3.12 hands the tracer an exception
   `(type, value, tb)` tuple; records said `exc: "type"` with the class repr as
   msg. Now the instance is named; `str()` runs only for builtin-module
   exceptions; user `__str__` never executes (`msg_unavailable` + reason).
3. **CV-M5QA-03 (medium)** — generator frames changed frame_id at every
   suspension and implied frame death per yield. Now one stable frame_id, no
   snapshot on suspension-returns.
4. **CV-M5QA-04 (low)** — C `mem_meta` now counts `reallocs` separately with an
   honest caveat (the first fix deadlocked the shim; the regression test caught
   it before commit — the test worked exactly as intended).
5. **CV-M5QA-05/06 (low)** — UI: no stale previous-run evidence when selecting a
   new run; "max SAMPLED RSS" and "len counts elements" label precision.

Challenge classes with no defect found are listed in
`docs/TEST_EVIDENCE/M5QA.md` (privileged flags, out-of-container execution,
browser-initiated runs, cross-run identity claims, host path/env/secret leaks,
partial cancelled sessions, deep-recursion caps, optimized-away C variables).

## Verification (fresh, post-repair)

- Backend **171/0/0** (includes 7 M5QA regressions + all M4/M4QA/M5 suites).
- E2E: M5 4/4 (screenshots at 1440/1366/1920/390 widths), M3 incl. M4 6/6,
  M2 3/3, M1 5/5 (real GitHub import). TSC clean; vite build OK.
- Images rebuilt from audited sources: analyzer `sha256:77d175e8…`,
  runtime `sha256:37cbc9ff…`, debug `sha256:63d87538…` (recorded in
  `docs/milestones/M5QA.json`; update manifests if you rebuild).

## Environment notes

- A stale uvicorn (pre-restart) causes false E2E failures — restart the backend
  on `127.0.0.1:8123` after backend code changes.
- WSL `bash -c` variable escaping mangles `for` loops from the Windows side;
  use script files per AGENTS.md rule 2.

## Next

**M6 (OptimizationLab) is authorized but NOT STARTED.** Entry checks for the
next stage: verify ancestry includes the M5QA commit, both M5/M5QA manifests
PASS, re-run the sandbox suites, and never infer authorization from queued
prompts if any gate fails.
