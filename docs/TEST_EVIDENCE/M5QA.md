# M5QA Test Evidence — Memory/Process Scientific Audit & Repair

Date: 1 November 2026. Scope: M5QA only (M6 NOT STARTED). **SAME-AGENT second-pass
self-audit — explicitly NOT an independent external review.** M5's self-report
was treated as an untrusted hypothesis: the entry gate re-verified manifests and
lineage on disk, confirmed the pinned image ids matched the M5 manifest exactly,
and re-ran the M5 suite fresh (10/10) before any audit code ran.

## Entry gate

- HEAD `6428a76` (M5) is ancestor of the audit tree; M5.json and M4QA.json both
  PASS with all gates green; `runtime:m4` = `sha256:8e195e20…`, `debug:m5` =
  `sha256:e081c742…` matched the live daemon before any changes.

## Boundary re-checks (challenges from the audit brief, answered)

- **Does ProcessScope request privileged flags/syscalls?** No. All three images
  run the identical `_BASE_FLAGS` (network none, read-only rootfs, cap-drop ALL,
  no-new-privileges, uid 1000, tmpfs, memory/cpu/pids caps). No SYS_PTRACE; the
  gdb profile traces its own child. `docker inspect` is host-side (trusted
  orchestrator), polled for the best-effort host pid only while the container
  lives.
- **Any untrusted execution outside a container?** No. Grep + path review: the
  orchestrator only invokes `docker` with argv arrays and fixed images; the
  debug worker compiles/runs strictly inside the debug image.
- **Does traced user code run inside the tracer?** THREE side-effect/identity
  defects found and fixed (below). After repair, the program itself proves zero
  side effects (stdout `side-effects: 0`).
- **Does the browser trigger a new run?** No: Memory/Process tabs issue GETs
  only; re-POST of the same (snapshot, target, image, profile) dedups to the
  existing execution. Verified by `test_no_container_left_after_observation_browse`
  (M5) and the determinism assertions.
- **Can artifacts leak host paths/env/secrets?** Records carry container paths
  only (`/work/...`), no environment capture, secret-named bindings redacted by
  the documented name rule (asserted in tests and E2E).
- **Cancellation / failed-trace partial sessions:** CANCELLED executions store
  no memory/process rows at all (regression `test_m5qa06`); timeouts likewise
  discard partial streams (M4QA behavior preserved).

## Findings (all reproduced live before repair)

| ID | Severity | Finding | Repair | Regression |
|---|---|---|---|---|
| CV-M5QA-01 | **High** | `safe_value` preview called `repr()` on ANY `str`/`int`/… instance — a primitive-subclass's user `__repr__` executed inside the tracer (reproduced: `LoudStr.__repr__` ran, its `<LOUD>` output leaked into stored evidence as if observed). | Exact-type previews (`type(v) is str` etc.); subclasses get identity treatment. Program-side side-effect counter now reads 0. | `test_m5qa01_no_user_repr_or_str_in_tracer` |
| CV-M5QA-02 | Medium | Exception records misidentified exceptions: CPython 3.12 passes the `(type, value, tb)` tuple, so `arg[0]` is the CLASS — `exc` recorded `"type"` and `msg` was the class repr. | Instance extracted from the tuple; `exc` = actual class name; `str()` evaluated ONLY for builtin-module exceptions; user `__str__` never runs (`msg_unavailable` + reason recorded). | `test_m5qa02_exception_records_identify_the_instance` |
| CV-M5QA-03 | Medium | Generator frames got a NEW frame_id at every resumption plus an exit-style snapshot per yield — one suspended frame appeared as three frames with implied deaths. | Generator returns are suspensions: no snapshot, no id eviction; frame_id stable across all snapshots of the frame (verified live: three snapshots, one id). | `test_m5qa03_generator_frame_identity_stable_across_suspensions` |
| CV-M5QA-04 | Low | `mem_meta.outstanding` was approximate for realloc-heavy programs (reallocs uncounted). | `reallocs` counted separately; caveat states outstanding is malloc/free-based. First attempt deadlocked the shim (nested mutex) — caught by this regression test before commit and fixed. | `test_m5qa04_c_realloc_counted_separately` (real libc allocator, 5 reallocs observed) |
| CV-M5QA-05 | Low | Stale UI evidence: selecting a new run briefly showed the previous run's events/memory/process until the new run completed. | ExecutionPanel resets events/memory/process/cursor/tab on executionId change. | E2E journey flow (new run starts blank); manual check |
| CV-M5QA-06 | Low | Imprecise metric labels: "max RSS" could read as a true peak; `len` fields could read as bytes. | UI now says "max SAMPLED RSS (not a guaranteed true peak)" and "len counts elements, not bytes". | UI text asserted implicitly via E2E text checks |

Challenge results with NO defect found (checked, documented): same
address/identity asserted across runs — obj_ids and container pids are labeled
within-run/namespace-qualified, and the memory API limitation text is asserted
(`test_m5qa05`); optimized-away C variables — the debug profile is -O0-only and
claims nothing at higher optimization; "heap allocation"/"pointer"/"object size"
wording matches what each tool actually observes (interposition, gdb, element
counts); peak CPU/scheduler order/syscall counts are never claimed; deep
recursion (depth 200) respects the documented 64-frame cap and the program still
completes honestly (`test_m5qa_deep_recursion_bounded_not_fabricated`); no host
path/env/secret leaks in artifacts; no browser-initiated runs.

## Independent oracles

- **Side-effect oracle:** the traced program itself counts instrumentation side
  effects (`SIDE_EFFECTS`) — after repair: `side-effects: 0` (exact, program-observed).
- **Frame-identity oracle:** one generator frame → exactly one frame_id across
  all suspensions (previously 3).
- **Exception fidelity oracle:** `exc: "LoudError"` + `msg_unavailable` with the
  policy reason (previously `exc: "type"`, class repr as msg).
- **C allocator oracle:** 5 reallocs in a real loop observed as 5 `realloc`
  records + `mem_meta.reallocs >= 5` (deadlock in the first fix caught here).
- **Process measurement comparison:** container `/proc/self/status` samples vs
  runtime-reported host pid and exit status — both recorded with units and
  interval; host pid marked unavailable when the container exits first (fast C
  runs) rather than invented.
- **Replay/static oracles unchanged:** M4 oracle tests (event parity, C call
  counts) still pass — the memory fixes did not perturb the M4 trace stream.

## Final gate results (fresh, post-repair)

```
Backend:  171 passed / 0 failed / 0 skipped   (incl. 7 new M5QA regressions)
E2E:      M5 4/4 (desktop 1440 + 1366 + 1920 + mobile 390 screenshots),
          M3 incl M4 6/6, M2 3/3, M1 5/5 (real GitHub import)
TSC:      clean.  Vite build: OK (387 kB).
Images:   analyzer sha256:77d175e8…, runtime sha256:37cbc9ff…, debug sha256:63d87538…
Leak check: no leftover containers/job dirs after full runs (M4QA reconcile).
```

## Residual risks

1. gdb remains curated-only (untrusted DWARF/ELF parsing stays out of scope).
2. `id()` values may repeat within a run after object free/realloc-of-id — alias
   detection only compares simultaneously-live objects in one snapshot
   (uniqueness holds), and within-run labeling is asserted in evidence.
3. RSS samples can miss sub-interval spikes; labeled as sampled data.
4. This remains a SAME-AGENT audit; the independent external audit is M9.
