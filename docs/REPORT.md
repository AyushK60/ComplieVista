# CompileVista: observing how source code becomes execution

*Technical report — working draft. Sections marked **[evidence needed]** have a planned
measurement that has not been run yet; no number below is a result unless it says so.*

## 1. Motivation

Introductory compilers and systems courses explain the path from source text to a running
program (tokens, syntax tree, intermediate representation, machine code or bytecode,
execution) with hand-drawn diagrams. Students rarely see the *real* artifacts that a real
toolchain produces for their own program, and visualizers that do exist tend to simulate a
toy language. CompileVista is a local-first tool that shows genuine artifacts from Clang/LLVM 18
(C) and CPython 3.12 (Python) for code the student brings.

**Contribution (as built, not as claimed):**
1. A provenance contract: every displayed artifact records tool and version, invocation, exit
   code, SHA-256, counts and limitations, and nothing is synthesized when a tool does not
   provide it (§3).
2. A sandboxed pipeline that analyzes and *runs* untrusted student code in restricted
   containers and records execution as replayable events (§4).
3. Source ↔ LLVM IR ↔ assembly line linking with an -O0/-O2 comparison derived from real
   debug info (§5).
4. A self-contained replay export: one HTML file that replays a recorded run with no backend
   (§6).

## 2. System overview

FastAPI backend (SQLite metadata + content-addressed artifacts), React/TypeScript frontend,
three pinned Docker images (static analyzer/builder, runtime, debug). C and Python pipelines
are deliberately distinct: Python bytecode is not machine code and Python has no LLVM
optimization levels. See `docs/ARCHITECTURE.md`.

## 3. The artifact-honesty contract

Each artifact is tagged with an availability state from a fixed vocabulary (ADR-0002) instead
of being omitted or faked. Examples: C execution traces are function-level only, so the UI
states that line stepping is unavailable for C; Python traces carry line events.
Measured result in §7.

## 4. Safe execution of untrusted code

Static inspection never executes analyzed code. Execution happens only in containers with no
network, read-only root filesystem, dropped capabilities, resource and time limits, and a
non-root user; the host Docker socket is never exposed to user code. Adversarial fixtures
(fork bomb, infinite loop, output flood, path traversal archives) are part of the test suite
(`backend/tests/test_m4_execution.py`, `test_m1_archive_security.py`).
**[evidence needed]** a table of adversarial cases with observed outcomes, taken from a fresh run.

## 5. Source ↔ IR ↔ assembly linking

`backend/app/services/linemap.py`. IR instructions are linked through `!dbg` → `DILocation`
metadata; assembly instructions through `.loc` directives restricted to the primary source
file. The -O0 vs -O2 comparison reports, per source line, instruction counts at both levels
and which lines lost, gained or kept code. It reports *what* changed, never *why*.
Limitations: relies on `-g` output; lines with no debug location are unlinked; inlined code is
attributed to the callee's source line.

## 6. Replay export

`backend/app/services/replay_export.py`. One HTML file with the source, recorded events,
captured output and run provenance embedded as JSON and a small vanilla-JS player. It replays
a recording and cannot execute code; embedded content is escaped against script breakout and a
CSP forbids network access.

## 7. Evaluation plan

| Question | Method | Status |
|---|---|---|
| Do shown artifacts equal the tools' own output? | `eval/fidelity_study.py`: analyze each single-file demo/pair program in the container, recompute the same quantities with the host toolchain, compare | **Run once:** 19 programs, 76 metrics (token, AST-node, bytecode-instruction and code-object counts for Python; token, IR-function (-O0/-O2) and assembly-line counts for C), 76 of 76 equal. The C token display is capped at 8000 by design (one program), which the study accounts for. Multi-file C-05 is not covered. Counts, not content: this does not prove the artifact text is identical. Raw data: `eval/results/`. |
| Is line linking correct? | Check linked lines against hand-annotated ground truth on a fixed set | **[evidence needed]** (unit tests cover one program) |
| Is untrusted execution contained? | Adversarial suite, fresh-run outcomes | **[evidence needed]** |
| Does it help learners? | Small task-based usability study (optional) | not started |

## 7.1 Other measurements (as of this draft)

- **Automated tests:** 223 backend tests (including adversarial sandbox cases, oracle checks
  against the real toolchains and the 20-program demo matrix) and 20 frontend unit tests pass.
  Browser journeys cover the main flows; the layout suite checks seven viewport widths
  (390 to 1920 px) for overflow, overlap and covered controls.
- **Accessibility:** an axe-core scan (WCAG 2.0/2.1 A and AA rules) over 12 screens reached
  through the real UI (home, library, demo page, compare, workspace states, each stage view,
  the optimization lab, execution, walkthrough) found 23 violations initially (links
  distinguished by colour only, a tab list with non-tab children, low-contrast badges,
  scrollable panes without keyboard access, nested interactive controls in graph nodes);
  all were fixed and the rescan reports 0. Machine checks only: no manual screen-reader or
  full keyboard audit was done.
- **Load size:** the initial JavaScript bundle went from 521 kB to 193 kB by loading routes,
  the code editor and the optimization explorer on demand.
- **Not measured:** wall-clock performance claims, any learning outcome (see
  `docs/USABILITY_STUDY.md`), CI behaviour on a hosted runner.

## 8. Limitations and future work

Local single-user tool (not a hosted service); C execution tracing is function-level; Python
memory/process views are observed within an instrumented run, not a debugger; the front end
is not yet covered by unit tests; only the two language pipelines above are supported.

## 9. Reproducing

`Setup.cmd` once, then `Start.cmd` (see `docs/LOCAL_RUN_GUIDE.md`).
