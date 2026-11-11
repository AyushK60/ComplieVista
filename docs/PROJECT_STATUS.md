# CompileVista Project Status

Updated: 11 November 2026 (Petrol & Coral redesign, presentation only)

### Suite results after the fourth pass (11-Nov-2026)

PASS: a11y_suite, layout_widths_suite, keyboard_suite, learning_suite, m8, m8b, m9, m10, m11, repair_watch_ast.
**FAIL (recorded, not fixed): `e2e/m8c_journeys.py` and `e2e/m8d_journeys.py`**, both at the Compare journey:
`expect(".cmp-verdict").to_be_visible(timeout=150_000)` times out. Reproducer: open `/compare`, click the
"recursion" pair. Observed cause: the backend `compare` experiment now takes about 165 to 170 s on this
machine (completed at 15:54:30 after starting 15:51:45; the same experiment took about 93 s at 14:51 the same
day), which exceeds the suites' hard-coded 150 s limit. The compare finishes COMPLETED, so this looks like
slowness, not a wrong result, but the rest of the journey after the verdict was NOT verified on this run
(an extended-timeout attempt was cut off by the shell limit). m8d had passed earlier in this session, before
the slowdown. No frontend or backend code touched by these passes is on the Compare path; the slowdown is
undiagnosed (candidate causes: host load, a growing DB with 317 executions and 59 compare experiments). Next
step for whoever picks this up: time a lone compare with the machine idle, then decide whether to raise the
limit or investigate the backend.

## Fourth pass: learning-layer tests, wording, phone fixes

- `optLearnModel.ts` holds the lesson/quiz logic with 5 unit tests (vitest total 25). A line the compiler
  linked no IR instruction to no longer reads "0 IR instructions".
- `e2e/learning_suite.py` (new): diff, lesson, quiz, share link reopening the lesson, print media and PDF,
  and no horizontal scroll at 375 and 768 px. PASS.
- Fixed a real 336 px overflow on a phone-width workspace with a run (five view tabs now wrap; the per-line
  comparison table scrolls inside its own region; line-link panes use minmax(0, 1fr)).
- C demo thumbnails (real token and syntax-node counts) were already in place from an earlier pass.
- Still out of scope: Rust/Java; pasted-code execution is governed by the M4 gate (see SECURITY.md).

## Third pass: Memory and process view, keyboard audit (frontend + one e2e suite)

- New workspace tab **Memory and process** (`MemoryProcessView.tsx`, shown once a run exists, deep link
  `?memory=1`): a scrubbable, playable call-stack and call-tree replay over the recorded trace events
  (verified on PY-03 recursion: stack grows to depth 8 and unwinds to empty), followed by the existing
  MemoryScope heap/frame panel and ProcessScope /proc lanes. Replay only; nothing is simulated.
- `e2e/keyboard_suite.py` (new): Tab audit of home (light and dark), library, evidence, about, workspace,
  memory view: visible focus indicator on every stop, no trap, on-screen focus, sane order, skip link,
  plus keyboard-only use of the slider, Play, lesson Next, diff rows and quiz. ALL CHECKS PASSED, zero
  console errors. Two false alarms during development (smooth scroll in flight, CodeMirror applying its
  focus class a tick late) were fixed in the test, not the app.
- Native C tokens card: already present on the home page (C tab of the tokens figure, real
  `clang -dump-tokens` output), so nothing added.
- Re-run after these changes: a11y_suite, layout_widths_suite, m8d, m9 all PASS; tsc, vitest (20), build OK.

## Second enhancement pass: home figure, Evidence page, polish (frontend + one script)

- Home: "What does -O2 delete?" figure from a real C-02 -O0/-O2 build (`scripts/media/build_opt_figure.py`
  writes `frontend/src/data/optDiff.json` with tool, flags, exit codes, SHA-256).
- `/evidence` page: every recorded stage with command, tool, exit code, SHA-256, counts, limitations
  (read live from the backend; "not recorded" shown when a field is absent).
- Home reel pauses when off-screen or the tab is hidden; header fixed for the new Evidence link and
  Teacher toggle (two rows at 375 px, no overflow at 1024 px).
- Checked live (Browser pane): evidence table (13 rows), home figure in light and dark, 375 px layout.
  Suites run on this pass: `a11y_suite.py` PASS (16 screens, 0 violations), `layout_widths_suite.py` PASS
  (after fixing a 15 px header overflow at 768 px that the new nav items caused), `m9`, `m8d`, `m8` PASS.
  Not re-run: m8b, m8c, m10, m11, repair_watch_ast. Not done: Rust/Java; pasted-code execution (BLOCKED until the M4 gate);
  token cap and launcher were already fixed in ae4f012.

## Learning layer: -O0 vs -O2 diff, guided lesson, quiz, teacher mode (frontend only)

Added `frontend/src/components/observatory/OptLearn.tsx`, wired into `SourceLinkView`: a per-line
-O0 vs -O2 diff (asm counts, real instructions side by side), an 8-step source -> IR -> assembly
lesson with Next/Back, a predict-then-reveal quiz scored from the real line map, "copy link to this
step" (`?view=&line=&step=`), Print/PDF poster styles, and a Teacher toggle in the nav. All text states
counts from the stored compiler output, never reasons. Verified: `tsc`, vitest (20), `vite build`.
Live check (manual, Browser pane, C-02 via the real backend, zero console errors): diff, lesson,
quiz, Teacher toggle and link copy all worked on real -O0/-O2 data. Shared links (`?view=`) now open the Optimization lab and reuse the idempotent build (verified live). Earlier gap: a link opened the
workspace but does not yet jump to the Optimization lab, and the experiment must be rebuilt first.
No e2e suite covers this yet.
Not started: new languages, pasted-code execution (stays BLOCKED until the M4 gate), evidence page,
light/mobile/perf passes.

## Redesign pass: Petrol & Coral (frontend styles and markup only)

New tokens, self-hosted Archivo + IBM Plex Mono, rectangular tags, a petrol hero band with a wide
live stage, ruled numbered sections, a coral call-to-action band, a two-row phone header, flat graph
nodes. Backend, routes, IDs, form fields and API calls untouched. Design summary in
`docs/M8_DESIGN_SYSTEM.md`. Verified on this pass: `tsc`, vitest (20), `vite build`,
`e2e/a11y_suite.py` (axe, 16 screens, light and dark, PASS after contrast fixes),
`e2e/layout_widths_suite.py` (7 widths, PASS), `e2e/m8d_journeys.py` and `e2e/m8_journeys.py` (PASS,
zero console errors). Not re-run: m8b, m8c, m10, m11, repair_watch_ast suites. Evidence screenshots
from the suites above were regenerated on the new UI.

## Portfolio pass: foundation, flagship features, research framing

Added (details and evidence in the commit history; fresh verification run recorded below
once it completes):

- **Foundation:** DB index on `execution_events` (events API 1.3 s → 0.02 s), `Setup.cmd` for a
  fresh machine, GitHub Actions CI (frontend typecheck/build + backend tests; first run
  unverified), hard-coded user path removed, layout suite at seven widths, stale e2e suites
  repaired or retired (m2/m3/m5/m6 replaced by `m9_journeys.py`).
- **Flagship C features:** source ↔ LLVM IR ↔ assembly linking and an -O0 vs -O2 comparison
  (`backend/app/services/linemap.py`, `SourceLinkView.tsx`); self-contained one-file replay
  export (`backend/app/services/replay_export.py`).
- **Student features:** CodeMirror editor, recent-session history, code-splitting
  (main bundle 521 kB → 193 kB), skip link.
- **Research framing:** `docs/REPORT.md` (draft, evidence marked as needed),
  `eval/fidelity_study.py` (app vs host toolchain), `docs/USABILITY_STUDY.md` (protocol only).
- **Maintainability:** `main.py` split into `app/routes/*` (39 routes unchanged); new
  concise `README.md`, original specification kept as `docs/SPECIFICATION.md`.

## Repair pass: Watch It Work usability + AST edges/auto-focus/contrast (frontend only)

User-visible symptoms fixed with verified root causes (evidence:
`docs/TEST_EVIDENCE/repair_watch_ast/REPORT.md` + before/after screenshots,
acceptance suite `e2e/repair_watch_ast_suite.py` ALL PASSED, zero console
errors; m8/m8b/m8c/m8d regression suites green):

- **AST edges were invisible, not faint**: xyflow v12 renders every edge as
  its own absolutely-positioned `<svg>` inside a 0×0 `.react-flow__edges`
  div; the global `svg { max-width: 100% }` reset capped their used width at
  0 and Chromium paints nothing in a zero-width SVG root (hit-testing still
  worked, which is why DOM-only checks passed). The edge layer now has a real
  paint box; containment strokes raised to ≈6:1 contrast, 2 px. Painted-pixel
  proof recorded for C and Python ASTs.
- **Watch It Work rebuilt as a flowing scene**: the duplicate cramped source
  card was removed (the full-height left SourceDock is the single source, all
  lines reachable), the four event panels flow in a 2×2 grid in a naturally
  scrolling center (no fixed-height shell, no overlap — asserted for zero
  overlapping/clipped rectangles at 1920/1366/390), the transport bar is
  sticky with universally-rendered glyphs, and playback/step/seek/first/last
  were verified against real PY-02 + PY-03 recordings with source, call
  stack, variables and narration reflecting the same selected event.
- **AST auto-focus**: entering the Syntax Tree stage opens the existing
  canvas focus once per navigation; manual Exit Focus persists (no re-force
  on rerender/selection); leaving and returning re-arms it.
- **Light theme contrast to WCAG AA**: `--ink-3` 4.0→5.4:1+, `--clay/--plum/
  --moss` ≥4.5:1 on badge backgrounds, `--c-ink-3` up on ink screens, panel
  lines slightly stronger — same palette identity, no redesign.
- **Layout integrity fixes found on the way**: collapsed-inspector rail
  wrapped to a second grid row (shrank the whole workspace to content
  height); dock resize handle anchored to the page edge (5 px page-wide
  overflow); mobile grid was inheriting desktop 3-column tracks (0-width
  center) — all fixed and covered by the suites.

No backend, toolchain, demo, API, route or engine changes.

---

## Previous status (1 November 2026 — M8 Part 3 — execution, systems, comparison; whole-product verification)

## Current milestone: **M8 complete — awaiting M9 independent audit**

Status: **M8 Parts 1–3 IMPLEMENTED and browser-verified.** Part 3 completed the
observatory: the Execution Observatory (call structure with recorded arguments
and returns, call detail with ancestry and jump-to-return, stack scene, kind
filters, guided execution story), MemoryScope frame-lifetime ladder, sampled
ProcessScope lanes, the Dual-Language Observatory (independent pipelines, no
equivalent stage, side-by-side sources, per-concept difference notes), Error
Microscope phase labels, and whole-product verification: all 20 demos swept in
a real browser with every available stage rendering, zero console errors.
Evidence: `docs/TEST_EVIDENCE/M8.md` (Part 1/2/3 sections),
`docs/TEST_EVIDENCE/m8{,b,c}/` (screenshots + metrics + report.json),
`docs/RELEASE_REPORT.md`, committed E2E `e2e/m8{,b,c}_journeys.py` (all green).

What Part 3 changed (frontend only):
- **Execution Observatory**: call cards carry recorded arguments + return
  values; ×N aggregation shows the varying argument range; call detail panel
  (ancestry, arguments, return, event span, jump-to-return); stack scene with
  connector rails; kind filters + filtered event navigation; guided 6-step
  execution story driving the canvas. All values from the recorded trace.
- **MemoryScope**: Python frame-lifetime ladder (per-frame bands from real
  frame_snapshot records; peak concurrent frames derived, e.g. 13 on PY-03).
- **ProcessScope**: step-drawn sampled lanes (no implied continuous
  measurement), exit marker.
- **Dual-Language Observatory**: replaced the two-result-card compare with two
  independent pipeline chains, an explicit no-equivalent-stage marker,
  side-by-side sources, honest per-concept difference notes, observatory
  deep-links for both sides.
- **Error Microscope**: phase-of-detection labels (front-end / link / runtime).
- **Framing fixes**: CSS/layout node width mismatch removed; legibility floor
  tuned so near-miss CFGs fit instead of clipping.

What Part 2 changed (frontend, except one tested backend extraction):
- **Layout engine**: tidy tree for syntax trees (was: unrelated layer columns),
  top-down layered CFG for IR; stable source-order siblings; zoom floor 0.7 so
  labels are always legible; full-tree overview is an explicit action.
- **Default framing**: the program's first function subtree, selected and
  framed, with its source line highlighted; full graph available via "Full".
- **Node categories**: declarations/statements/expressions/operators/names/
  literals + compiler-inserted nodes (dashed, honest, filterable).
- **Cross-stage selection continuity**: node→source-line and
  source-line→node both work; stage switches preserve the journey context.
- **Bytecode observatory**: code-object constants/names, source-line grouped
  lanes, source↔instruction selection, real branch arcs, guided script.
- **LLVM IR**: per-block verbatim instructions extracted from the stored .ll
  (backend `_ir_summary`, capped + honestly flagged; regression-tested in
  `backend/tests/test_m8b_ir_instructions.py`); block inspector shows them.
- **Full-screen exploration** per stage with compact stage bar + on-demand
  inspector; Explore-mode copy shortened to one sentence per stage.

What revision 2 (earlier today) changed:
- **Design system**: all four stylesheets rewritten — porcelain page chrome,
  ink visualization canvases set into instrument bezels (never full-page black
  sections), semantic accents (teal=interactive/identifiers, clay=runtime/
  numbers/DERIVED, plum=structure/keywords, moss=verified/strings/EXACT,
  crimson=errors), Fraunces display serif + Inter + JetBrains Mono,
  restrained radii (≤16px), no glow/gradients.
- **Landing**: proposition headline ("Your code transforms before it runs.
  See how."), instrument-bezel hero (conceptual source→tokens→AST→bytecode→
  execution loop, reduced-motion aware), phase rail, five hairline-separated
  chapters, live CTAs (Explore a Program / Import Your Code), diagnostics in
  the footer.
- **Demo Library**: Explore Python / Explore C / Compare sections, concept +
  difficulty filters, per-program ink specimen previews, teaches-line, honest
  capability-derived stage chips; detail pages unchanged in substance.
- **Token Formation (signature)**: default meaningful-expression focus
  (docstrings can never monopolize), full-file toggle, category filters, token
  search, hover-token → source-span highlight, virtual chips for CPython
  ENCODING (never faked source), 5-step guided script that drives the canvas
  and hands off to the Syntax Tree.
- **Workspace shell**: source-span hover sync, collapsible Contextual
  Inspector, canvas full-screen focus mode, mobile grid overflow fix.
- **Backend fix (ordering-only, tested)**: C tokens stage now serves the
  primary file's tokens before included-header tokens when the 500-item cap
  applies (CV-01 policy, as the AST walk already did). Regression test:
  `backend/tests/test_m8_tokens_primary_file.py`.

## Previous milestone: M8-G0 (technical integrity repairs + one-click launcher)

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
- **M8 visual recovery, revision 2**: the porcelain rebuild above, verified
  end-to-end in a real browser (committed Playwright E2E + screenshots).

## Deliberately NOT done (no false claims)

- No code-splitting/lazy loading yet (bundle ~460 kB / 146 kB gzip); no Monaco
  editor (the read-only Source Dock is deliberately bounded to immutable
  snapshots); no session history browser UI.
- Trace theater draws up to 400 children per node and aggregates identical
  sibling runs (×N); older records stay reachable via the timeline (labeled).
- No M9 independent audit; no public/remote exposure; execution of
  GitHub-imported code remains BLOCKED.
- Full observer/target trust-domain separation (beyond the framed channel) is
  future work; `UNTRUSTED_TARGET` labeling is the honest interim contract.

## Redesign and fix-first pass (2026-11-11)

Title Sequence redesign (home, Demo Library film catalog, Workspace and Compare restyle; see `DESIGN.md`,
`PRODUCT.md`) plus the fix-first list: C token cap removed (policy `m2.analyzer.v2`), Compare locking, progress,
cancel and cache, launcher diagnostics, native home figures from recorded data, stale e2e updated.
Evidence: `docs/TEST_EVIDENCE/REDESIGN_2026-11-11.md` (224 backend tests, 20 unit tests, axe, 7-width layout and
all browser journeys passed). Install frontend dependencies from WSL, not Windows npm.

## Next

**M9 independent audit** (per `docs/REMAINING_M8_M9.md`): independent code +
screenshot review, deployment threat-model review, 20-demo regression re-run by
a party other than the developer agent, release report. Optional M8 extras
(code-splitting, history UI, Prediction Lab) remain deferred.

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
