# CompileVista Design System — "The Living Compiler"

Status: **superseded in part by the "Petrol & Coral" redesign (November 2026)**; the summary
below is current, the numbered sections after it describe the earlier porcelain system and are
kept for history. Source of truth is now `frontend/src/styles/tokens.css`.

## Current system: Petrol & Coral (presentation only; behaviour untouched)

- **Proportions:** ~60% base surface (sand `#EEEAE1` light, `#08171F` dark), ~30% petrol (hero band,
  code and graph plates, structure), ~10% coral (`--signal` `#FF5533` light, `#FF6B4A` dark).
- **Coral means one thing:** the thing you are looking at: selection, the active stage, the primary
  action, the highlighter mark behind one headline word. It is never a data colour. On paper, coral
  text uses `--accent-text` (AA); on plates, selection uses `--sel`.
- **Data hues** (fixed roles everywhere): sky = identifiers, violet = keywords and structure,
  apricot = numbers, mint = strings and EXACT, amber = DERIVED/PARTIAL, crimson = errors/BLOCKED.
  Paper and plate variants exist for each (`--sky` / `--sky-l`, ...). Status is always text plus colour.
- **Type:** Archivo (variable, width axis) for display and UI; display is set condensed (`font-stretch`
  80%), weight 800, tight tracking. IBM Plex Mono for all code and data, ligatures off. Both are
  self-hosted through `@fontsource` so nothing loads from a third party.
- **Shape:** radii 2 / 4 / 8px, rectangular tags (no pills), hairline borders, shadow only on floating
  layers, no gradients on surfaces, one backdrop blur (graph toolbar).
- **Layout:** home is a petrol hero band with a wide live stage, then ruled, numbered paper sections and
  one coral call-to-action band. The header floats over the hero and turns solid on scroll. The Demo
  Library is an index of ruled rows, About sets its hard numbers on rules.
- **Contrast:** AA in light and dark, verified by `e2e/a11y_suite.py` (axe-core).

---

Earlier revision (replaced the rejected Project Phoenix "Computational Atlas" midnight theme — see git
history for revision 1):

**Porcelain Instrument × Ink Canvas × Scientific Precision**

This document is the single source of truth for the visual language. It
constrains every surface: landing, observatory workspace, demo library,
compare, error microscope. Implementation: `frontend/src/styles/tokens.css`.

## 1. Product identity

CompileVista is a **precision instrument for watching code transform**. The
metaphor carried through every surface: a **porcelain instrument** (calm,
warm, light, precisely machined chrome) into which **ink screens** are set
(deep, quiet, high-contrast canvases where the machine's artifacts are
shown). Nothing glows, nothing is decorative. Color exists only to explain
concepts, selection and relationships. The tone is a beautifully printed
lab notebook next to an oscilloscope — not a developer dashboard.

The rejected direction (and why): a midnight-blue/purple/cyan dashboard with
random alternation between black and ivory page sections, gradient glow, and
giant rounded panels. All of that is banned.

## 2. The two-surface rule (the core compositional law)

1. **Porcelain** (`#F6F5F0` page, `#FCFBF8` surfaces) is the *page*: chrome,
   navigation, headings, explanatory text, tables, controls, docks.
2. **Ink** (`#1D292F` family) is the *screen inside the instrument*: token
   formation, graphs, bytecode lanes, hero screen, demo specimens, memory
   lanes. Ink **always appears inside a framed instrument bezel** (porcelain
   border, labeled header), never as a full-page background.

A page is therefore never "a black section followed by a white section" —
it is one continuous porcelain composition with instruments set into it.

## 3. Surface hierarchy

| Tier | Token | Use |
|---|---|---|
| Page | `--bg #F6F5F0` | body background |
| Surface | `--bg-raised #FCFBF8` | cards, panels, docks |
| Well | `--bg-inset #EFEEE7` | inputs, quiet code wells on porcelain |
| Hairline | `--line / --line-strong` | 1px borders (ink-tinted alpha) |
| Ink screen | `--canvas #1D292F` | visualization canvases |
| Ink raised | `--canvas-raised #24333B` | cards/nodes on ink |
| Ink well | `--canvas-inset #162025` | deepest layer of a screen |

## 4. Color system

Neutrals are derived from the ink hue (`#1D292F`), so borders and muted text
sit naturally on porcelain.

Semantic accents — each means exactly one thing everywhere:

| Token | Value | Meaning |
|---|---|---|
| `--teal #166D68` | primary | interactive elements, links, active state, **identifiers/names** |
| `--clay #C77950` | warm | **runtime/execution**, numbers, sampled data, DERIVED provenance |
| `--plum #84719B` | structural | **structure** (AST nodes, keywords, code objects) |
| `--moss #56794F` | verified | **strings/literals**, EXACT provenance, success |
| `--crimson #B0453B` | alert | errors, destructive/runtime-hot, BLOCKED |

Light variants (`--teal-l`, `--clay-l`, `--plum-l`, `--moss-l`, `--crimson-l`)
are the same hues lifted for contrast **on ink screens**. Dim tints
(`--teal-dim` etc.) are 10–13% alpha washes for backgrounds. Accent colors are
never used as large fills; they color text, 1px borders, small chips and thin
indicators.

Honesty mapping (maps to backend enums, never decorative):
`EXACT` → moss · `DERIVED`/`APPROXIMATE` → clay · `UNAVAILABLE`/`BLOCKED` →
dim gray + explained empty state.

Token categories (lexical visualization): keyword → plum · identifier → teal ·
number → clay · string → moss · operator/punctuation → ink-2 (quiet by
design) · layout tokens (INDENT/DEDENT/NEWLINE) → ghost style.

## 5. Typography

- **Display: Fraunces** (variable serif) — landing headline, chapter titles,
  page titles. Gives the product its printed-lab-notebook voice.
- **UI: Inter Variable** — body, controls, docks.
- **Code: JetBrains Mono** — all source, tokens, offsets, digests, metadata.

Scale: hero clamp(2.7rem→4.3rem) tight; section titles clamp(1.7rem→2.5rem);
body 15–16px/1.65; small labels 12–13px; technical metadata always mono
10.5–12.5px. Eyebrow labels: mono, uppercase, 0.14em tracking, teal.

## 6. Source-code typography

Read-only source and token canvases use JetBrains Mono 13px/1.7 minimum
(12.5px in the source dock), ligatures off, `white-space: pre` — whitespace is
data. Line numbers are 10.5px, right-aligned, muted, non-selectable.

## 7. Graph node styles (Syntax Tree / IR / object graph)

Ink screen; nodes are `--canvas-raised` cards with 1px category-colored
borders (structure → plum, lexical → teal, runtime → crimson, unavailable →
dashed gray). Labels mono 11px. Selection = 2px teal ring. Dimming (search
focus) = opacity 0.28. Edges: 1.4px strokes at 0.5–0.8 alpha in the hue of
their source category; animated draw-in on landing previews only.

## 8. Spacing, radii, density

- 4px base grid; panel padding 16/20/28; landing section rhythm 96–128px.
- **Radii are deliberately restrained** (anti "giant rounded rectangle"):
  `--r-s 6px` chips/inputs · `--r-m 10px` cards · `--r-l 14px` large panels ·
  instrument bezels 16px. No radius above 16px anywhere.
- Density: Explore mode is spacious (larger paddings, short labels);
  Technical mode compacts (`html[data-mode="technical"]` reduces panel
  padding and reveals provenance rows, digests, raw excerpts).

## 9. Motion principles

Motion is **explanatory, never decorative**: a transition may only show a
transformation the compiler actually performs (text → tokens → tree) or a
change of selection. Durations: `--t-fast 140ms` (hover/press), `--t-med
260ms` (state change), `--t-slow 480ms` (canvas reveals); easing
`cubic-bezier(.22,.61,.21,1)`. Landing hero cycles through its five phases on
a labeled timer (conceptual, on-screen labeled as such). No parallax, no
scroll hijacking, no glow pulses. `prefers-reduced-motion: reduce` collapses
all animation/transition durations globally and the hero jumps to its final
phase.

## 10. Navigation behavior

Sticky porcelain top bar, hairline-separated, with mono brand mark, plain
text links (active = ink text + hairline underline accent), and the
Explore/Technical mode switch on the right. The observatory keeps its own
Journey Navigator rail above the canvas; mode, program, stage, selection and
execution survive navigation (persisted in URL/localStorage).

## 11. Responsive behavior

- Landing: hero collapses to one column < 1080px; chapters stack; feature
  rows 2-col < 1080px, 1-col < 720px.
- Observatory: 3-column grid `minmax(330px,400px) | 1fr | minmax(280px,330px)`
  ≥ 1180px; below that, stacks to one column with bounded dock heights.
- Demo library: auto-fill card grid, 1-col < 720px.
- Mobile (390px): everything single column; canvases keep horizontal scroll
  for wide artifacts; no fixed-width element exceeds the viewport.

## 12. Accessibility

`prefers-reduced-motion` honored globally; `:focus-visible` 2px teal ring on
every interactive element; interactive graph nodes are buttons; color never
the sole carrier of meaning (paired with labels/badges/text); body text
contrast ≥ 4.5:1 on porcelain and on ink (ink-screen text uses the light
variants); canvases expose `role="list"`/`aria-label` structure.

## 13. Explore vs Technical mode

One website, two densities — never two designs. `html[data-mode]` +
`.tech-only`/`.explore-only` classes. Explore hides provenance rows, digests,
raw excerpts and dense tables; Technical reveals them and compacts spacing.
Mode is presentation-only: program, stage, selection, execution and scroll
context are untouched by the switch.
