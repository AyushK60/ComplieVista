# M8 Design System — "Computational Atlas"

Status: M8 visual redesign (Project Phoenix), Phase A. This document is the single
source of truth for the visual language. It constrains every M8 surface: landing,
observatory workspace, demo library, compare, error microscope.

## 1. Identity

**CompileVista — Computational Atlas.** A scientific computational observatory:
immersive dark canvases for the machine's data, precise ivory editorial surfaces
for human explanation, restrained luminous accents for semantics. Premium, calm,
technically credible. No developer-dashboard gray, no decorative glow.

## 2. Foundations (implementation: `frontend/src/styles/tokens.css`)

### 2.1 Color

Dark canvas (immersive surfaces — canvas, docks, visualizations):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#070a16` | app background (deep midnight indigo) |
| `--bg-raised` | `#0d1226` | raised panels, docks |
| `--bg-panel` | `#111731` | cards, canvases |
| `--bg-inset` | `#0a0e1e` | code surfaces, wells |
| `--line` | `rgba(148,163,255,.14)` | hairline borders |
| `--line-strong` | `rgba(148,163,255,.28)` | emphasized borders |
| `--ink` | `#e8ecff` | primary text |
| `--ink-2` | `#b7bfe0` | secondary text |
| `--ink-3` | `#7d87ad` | muted text |

Ivory editorial surface (explanatory chapters, guided narration):

| Token | Value |
|---|---|
| `--ivory` | `#f4f0e6` |
| `--ivory-ink` | `#1d2233` |
| `--ivory-ink-2` | `#5a607a` |

Semantic accents (used sparingly, consistently meaning the same thing everywhere):

| Token | Meaning |
|---|---|
| `--cyan #67e8f9` | lexical / text-derived artifacts, interactive highlights |
| `--violet #a78bfa` | structure (AST, code objects), primary action glow |
| `--mint #6ee7b7` | success, verified/EXACT provenance |
| `--coral #fb7185` | runtime execution, errors, destructors |
| `--amber #fbbf24` | caution, DERIVED provenance, sampled data |

Honesty colors (never decorative): `EXACT` → mint, `DERIVED` → amber,
`UNAVAILABLE`/`BLOCKED` → dim gray with explanation. These map directly to the
backend `mapping_confidence` / `availability` enums.

### 2.2 Typography

- UI: **Inter Variable** (`@fontsource-variable/inter`), system fallbacks.
- Code: **JetBrains Mono** (`@fontsource/jetbrains-mono`), monospace fallbacks.
- Display scale: hero clamp(2.6rem→4.5rem) tight (−0.03em); section titles
  clamp(1.8rem→2.6rem); body 15–16px/1.6. Numeric/technical metadata always mono.

### 2.3 Space, radius, depth, motion

- Space scale 4px base; panel padding 16/20/28; section rhythm 96–140px on landing.
- Radii: `--r-s 8px` (chips), `--r-m 12px` (cards), `--r-l 18px` (panels).
- Elevation via layered shadow tokens (`--shadow-1/2`), subtle; plus 1px hairlines.
- Motion: `--t-fast 140ms`, `--t-med 260ms`, `--t-slow 480ms`, easing
  `cubic-bezier(.22,.61,.21,1)`. All transitions honor `prefers-reduced-motion`
  (animation/transition durations collapse to near-zero via the global media rule).

## 3. Experience modes

`<html data-mode="explore|technical">`, persisted in `localStorage`
(`cv.mode`), toggled from the top bar. Explore hides technical provenance rows,
raw excerpts and dense tables (`.tech-only { display:none }` in explore);
Technical reveals them. Selected program/stage/selection/execution persist across
the switch — mode is presentation-only state.

## 4. Honesty rules baked into the UI kit

Every visualization component must render, for the data it shows:

1. a provenance line (tool, `mapping_confidence`, artifact digest) in Technical mode;
2. an explicit `EXACT`/`DERIVED`/`UNAVAILABLE` badge on derived structures (CFG
   edges, block inventories);
3. an *explained empty state* (`<Unavailable note>`) — never a blank panel —
   when the backend marks a stage unavailable/blocked.

No component may invent linkage. Edges/positions come from API records only.

## 5. Layout system

- **Landing**: full-bleed scroll narrative; hero (dark) → alternating ivory/dark
  chapters; max-width 1180px content column; sticky chapter margins allowed.
- **Observatory workspace**: CSS grid
  `source-dock 380px | canvas 1fr | inspector 320px` with the journey navigator
  as a rail above the canvas; execution dock slides over the bottom of the
  canvas region. Collapses to stacked single column < 1100px.
- **Demo library**: grouped gallery (Python-only / C-only / Pairs), concept-tag
  filter chips, detail overlay with guided story levels.

## 6. Accessibility

Keyboard focus visible on every interactive element (`:focus-visible` rings);
interactive nodes in canvases are buttons or `role=button`+tabindex; color never
the sole carrier of meaning (paired with labels/badges); reduced-motion honored;
contrast ≥ 4.5:1 for body text on both dark and ivory surfaces.
