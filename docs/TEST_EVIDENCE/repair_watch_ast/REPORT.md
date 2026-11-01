# Repair evidence — Watch It Work usability + AST edges/focus/contrast

Date: 2026-11-01 · Scope: surgical frontend repair only (no backend, no engine,
no demo/API/route changes). Pre-change checkpoint tag: `pre-repair-watch-ast`
(commit 5ecdcf4, clean tree).

## Before state (reproduced, not assumed)

- `before/` screenshots: PY-02 Watch + AST at 1920×1080 / 1366×768 / 390×844
  (`e2e/repair_g0_before.py`).
- Watch geometry at 1920: the walkthrough source panel was **101 px tall**
  (63 px of visible body) for 24 lines; at 1366 the panels visually overlapped
  (Recorded Output over Variables/What-happens-now) because the walkthrough
  was crushed into a fixed-height center column.
- AST at 1920: nodes rendered, **zero painted edges** (probe evidence:
  `before/ast_edge_crop.png` — handle dots visible, no strokes).

## Root causes (verified, each with a live probe)

1. **AST edges invisible — `svg { max-width: 100% }` reset (base.css) collapsed
   xyflow v12's per-edge `<svg>` elements to 0 width.** xyflow renders each
   edge as its own `position:absolute` `<svg>` inside `.react-flow__edges`
   (which shrink-wraps to 0×0). `max-width:100%` resolved against that 0-width
   containing block and capped even inline `width:4000px !important` at 0
   (probe: computed `width:0px, max-width:100%`). Chromium paints nothing in a
   zero-width SVG root while still hit-testing it — which is why the earlier
   DOM-count assertion ("edges rendered") passed while users saw no edges.
   Isolated reproduction: `before/svg_paint_test*.png`.
2. **Watch crushed/overlapping** — the walkthrough (a flowing 2-column scene)
   was forced into `obs-center` with `overflow:hidden` and a content-sized grid
   row; with `.obs-grid.insp-collapsed` being 2-column, the 44 px inspector
   rail wrapped to a second grid row, shrinking the whole workspace to content
   height (~561 px) over dead space.
3. **Duplicate cramped source panel** — the walkthrough rendered its own
   source card beside the full-height left SourceDock.
4. **Readability** — `--ink-3 #6f7f88` = 4.0:1 on panel backgrounds (fails
   AA for normal text); `--clay #c77950` = 3.2:1, `--plum #84719b` = 4.2:1 on
   badge backgrounds; edge stroke alpha 0.45 ≈ 3.6:1 on the ink canvas;
   transport glyphs ⏮/⏭/⏸ render as tofu boxes on common fonts.
5. **No auto-focus** — entering AST never opened the existing canvas focus.

## Changes (frontend only)

- `frontend/src/styles/observatory.css`
  - Edge paint-box fix: `.react-flow .react-flow__edges{width/height:100%}` and
    `.react-flow .react-flow__edges svg{max-width:none;width/height:100%}`.
  - Connector contrast: containment stroke alpha 0.45→0.66 (≈6.0:1), width
    1.5→2 px; branch 0.6→0.75; on-path 2→2.4 px; `--xy-edge-stroke` token up.
  - Watch scene: `obs-center-flow` (center scrolls naturally), 2×2 flow grid
    (`flow vars / stack out`), removed the duplicate source panel styles,
    sticky opaque transport bar, output max-height 110→180 px, flowline
    horizontal scroll, mobile areas collapse (`"flow" "vars" "stack" "out"`).
  - Grid: row `minmax(0,1fr)` fills the app frame; `.obs-app
    .obs-grid.insp-collapsed` keeps 3 columns so the rail stays in column 3
    (it previously wrapped and shrank the workspace); `.obs-app .obs-left`
    is `position:relative` again so the dock-handle anchors to the dock
    (removes a 5 px page-wide overflow); ≤1180 px media query resets the
    desktop track templates at matching specificity (fixes 0-width center on
    mobile that the desktop rules were imposing).
- `frontend/src/styles/tokens.css` — AA contrast: `--ink-3 #57676f` (5.4–5.7:1),
  `--c-ink-3 #94a8ae` (5.3–6.0:1), `--clay #9c562e`, `--plum #6a5b80`,
  `--moss #4d6f47` (all ≥4.5:1 on their badge/label backgrounds), `--line`
  0.13→0.17, `--line-strong` 0.26→0.34.
- `frontend/src/components/observatory/ProgramWalkthrough.tsx` — removed the
  duplicate source card (the full-height left SourceDock is the single source
  view; active-line scroll-into-view targets it); panels flow naturally;
  transport glyphs replaced with universally-rendered ones (« ‹ ▶/❚❚ › »)
  with titles; no logic/semantics changed (same meaningful-event model,
  same honesty labels).
- `frontend/src/pages/Workspace.tsx` — AST auto-focus: entering the `ast`
  stage opens the existing canvas focus ONCE per navigation; a manual exit
  stays closed while on the stage; leaving the stage re-arms it; entering the
  walkthrough collapses the inspector (rail can reopen it).
- `frontend/src/components/GraphView.tsx` — brighter node handle dots
  (0.5→0.85, 6→7 px); `initial_zoom` metric now recorded after the fit rAF
  (it always reported 0 before).
- `e2e/repair_g0_before.py`, `e2e/repair_watch_ast_suite.py` — evidence +
  acceptance suites (see below).
- `e2e/m8_journeys.py`, `e2e/m8b_journeys.py`, `e2e/m8c_journeys.py` — adapted
  to authorized behavior changes only: exit auto-focus before using the
  covered journey rail (m8, m8b), scope inspector locators to the visible
  inspector (m8b — two inspectors exist while focused), fix a stale
  pre-existing selector `Run & replay execution` → `Run (observatory)` (m8c —
  broken before this repair; verified by the pre-change checkpoint).

## After-state verification (all commands executed; exit codes 0)

`backend/.venv/bin/python e2e/repair_watch_ast_suite.py` — **ALL CHECKS PASSED** (127.9 s):

- A: no overlapping/clipped watch panels at 1920/1366/390; all 24 PY-02
  source lines reachable by scrolling (last line fully visible at bottom);
  no page-wide horizontal overflow; sticky transport; honesty label intact.
- A playback (real PY-02 run, 53 meaningful events): play at 2× advanced and
  pause held; step back/forward exact; restart→1; jump-to-end→53/53; scrubber
  seek→11/11; highlighted source line == explained line; call stack reflects
  the event. PY-03 recursion: stack ≥2 frames mid-run, fully unwound (0
  frames) at the last recorded event — honest end state.
- B: for BOTH PY-02 (CPython) and C-01 (Clang): entering AST auto-opens focus
  exactly once; edge SVG layer has a real paint box (0 zero-width layers);
  containment strokes ≥2 px ≈6:1 contrast; **painted-pixel proof** — sampled
  stroke midpoints contain bright pixels over the canvas background
  (`b_ast_*_edgepixel.png`); AST uses containment edges only (no CFG branch
  edges); collapse/expand restores node counts (19→13→19, 21→14→21);
  selection opens the inspector and highlights the source line; manual Exit
  Focus persists across selection/rerender and stage switches; fresh
  navigation into AST re-opens focus once; fit applied once per navigation
  (zoom ≈1.0 recorded honestly in `data-metrics`).
- Zero console errors across all journeys and viewports.

Regressions (unchanged assertions; two stale-selector/locator adaptations
documented above): `m8d_journeys.py` ALL PASSED (275 s), `m8_journeys.py` ALL
PASSED, `m8b_journeys.py` ALL PASSED (105 s), `m8c_journeys.py` ALL PASSED
(531 s) — zero console errors in each. `tsc --noEmit` clean; `npm run build`
succeeds (518 kB JS / 164 kB gzip — pre-existing size, no new dependencies).

Screenshots: `after/` (watch + AST matrices, 1920/1366/390, focus + unfocus,
source scrolled to bottom, edge pixel proofs).

## Limitations / remaining

- The sticky transport bar intentionally overlays scrolled content with an
  opaque bar (standard toolbar pattern); content panels themselves do not
  overlap.
- At 390 px the auto-focused AST shows the focus inspector over the small
  canvas (existing focus-mode layout); exit focus works and is asserted.
- Edge stroke color follows the existing ink-canvas palette; no new theme.
- `data-metrics.initial_zoom` is now measured post-fit; the framing algorithm
  itself (MIN_READ_ZOOM anchoring) is unchanged.
- Backend untouched: no backend suite re-run needed (no backend change).
