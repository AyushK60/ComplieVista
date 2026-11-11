---
name: CompileVista
description: A local-first compiler observatory dressed as a film title sequence; flat drenched screen-print fields, one heavy condensed face, one hot vermilion signal.
colors:
  vermilion: "#ff3d17"
  vermilion-on-dark: "#ff5a3a"
  vermilion-text: "#b3240a"
  ink: "#100d0b"
  cream: "#f3ecdc"
  paper: "#faf5e8"
  sand: "#e8dfc8"
  ink-2: "#433c32"
  ink-3: "#5a5246"
  cobalt: "#1f3fff"
  saffron: "#ffb81c"
  plate: "#15110e"
  plate-raised: "#1f1a15"
  plate-inset: "#0c0907"
  plate-ink: "#e9eff1"
  dark-bg: "#14100d"
  dark-surface: "#1d1814"
  dark-ink: "#f3ecdc"
  sky: "#0a5f8c"
  violet: "#6b46b5"
  apricot: "#944e00"
  mint: "#165c3e"
  amber: "#704a00"
  crimson: "#b0243a"
typography:
  display:
    fontFamily: "Big Shoulders Display Variable, Archivo Narrow, Impact, sans-serif"
    fontSize: "clamp(3rem, 1rem + 6vw, 6rem)"
    fontWeight: 900
    lineHeight: 0.88
    letterSpacing: "-0.005em"
  headline:
    fontFamily: "Big Shoulders Display Variable, Archivo Narrow, Impact, sans-serif"
    fontSize: "clamp(2.4rem, 1rem + 4.4vw, 4.6rem)"
    fontWeight: 900
    lineHeight: 0.95
  title:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  lead:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(1.05rem, 0.9rem + 0.5vw, 1.3rem)"
    fontWeight: 500
    lineHeight: 1.45
  label:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "12.5px"
    fontWeight: 600
    letterSpacing: "0.005em"
  code:
    fontFamily: "IBM Plex Mono, ui-monospace, Cascadia Code, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 500
    lineHeight: 1.55
rounded:
  s: "2px"
  m: "4px"
  l: "8px"
  bezel: "6px"
spacing:
  sp-1: "4px"
  sp-2: "8px"
  sp-3: "12px"
  sp-4: "16px"
  sp-5: "24px"
  sp-6: "32px"
  sp-7: "48px"
  sp-8: "72px"
  sp-9: "112px"
components:
  button-primary:
    backgroundColor: "{colors.vermilion}"
    textColor: "{colors.ink}"
    rounded: "{rounded.s}"
    padding: "0 14px"
    height: "32px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.s}"
    padding: "0 14px"
    height: "32px"
  button-hero-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.cream}"
    rounded: "{rounded.s}"
    padding: "0 24px"
    height: "48px"
  button-hero-primary-hover:
    backgroundColor: "{colors.cobalt}"
    textColor: "#ffffff"
  title-card-cobalt:
    backgroundColor: "{colors.cobalt}"
    textColor: "#ffffff"
    padding: "72px 0"
    height: "100svh"
  token-block:
    backgroundColor: "{colors.saffron}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    padding: "6px 10px"
  badge-honesty:
    textColor: "{colors.mint}"
    typography: "{typography.code}"
    rounded: "{rounded.s}"
    padding: "1px 7px"
  panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.m}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.m}"
    padding: "6px 12px"
    height: "36px"
---

# Design System: CompileVista

## Overview

**Creative North Star: "The Title Sequence"**

Compilation is staged as a film title sequence. Each stage of the toolchain is a full-bleed card in one flat, drenched field (vermilion, ink, cream, cobalt, saffron), set in a single heavy condensed grotesque, and the cards wipe over one another as the visitor scrolls. The shapes on screen are never decoration: a coral or saffron block is a real token, a rotated cream plate is a real syntax-tree node, and the 2px-bordered screenshots are real captures of the product's output.

The landing is loud and poster-like; the application behind it is the same instrument with the lights down. App pages keep the cream paper and warm ink (or warm black in dark theme), reserve vermilion for the single thing you are looking at (selection, active stage, the primary action), and put code and graphs on a warm-black plate in both themes. The landing uses fixed screen-print colours; the app uses the global tokens in `tokens.css`. The two share hue, face, and flatness, not saturation.

The build rejects the dark dev-tool hero with a gradient headline over a screenshot, and every form of glow, glass, and blur on the surfaces it owns.

**Key Characteristics:**
- Flat drenched colour fields; depth comes from stacking, rotation, and 2-3px ink rules, never from gradients or blur.
- One display face (Big Shoulders Display, weight 900, uppercase, line-height about 0.9) carries every headline.
- Mono is reserved for artifact text: tokens, node labels, tool/version credits, hashes.
- Vermilion is the signal; data hues carry meaning in code and status only.
- Sharp corners (2px to 4px); the only larger radius is 8px on app surfaces.

## Colors

A screen-print palette: five saturated fields on landing, a warm cream/ink neutral pair in the app, and one signal.

### Primary
- **Vermilion** (`vermilion`): the hero field, the closing title card, poster-row hover fill, and, in the app, `--signal` for the primary button, selected mark, and highlighter. Text on a vermilion fill is always ink.
- **Vermilion on Dark** (`vermilion-on-dark`): the same signal tuned for dark theme and on plates (selection).
- **Vermilion Text** (`vermilion-text`): coral as text or border on paper; a darker value so it holds AA on cream. Links use it.

### Secondary
- **Cobalt** (`cobalt`): a stage title card field and the hover state of landing buttons; also the smaller rotated plate behind the hero tree. Text on cobalt is white.
- **Saffron** (`saffron`): a stage title card field, the larger rotated plate behind the hero tree, operator token blocks, and the emphasised word in the closing roll.

### Neutral
- **Ink** (`ink`): text, the opening credits strip, hero buttons, closing roll and footer, 2-3px rules, and the border on every cut plate.
- **Cream** (`cream`): the page background (`--bg`), cream title cards, and plate text on ink.
- **Paper** (`paper`) and **Sand** (`sand`): app panel surface and inset/sunk surface.
- **Ink 2 / Ink 3** (`ink-2`, `ink-3`): secondary text; `ink-3` is for meta and large text only.
- **Plate** family (`plate`, `plate-raised`, `plate-inset`, `plate-ink`): the warm-black surface that holds code, graphs, and the run viewer in both themes.
- **Dark theme** (`dark-bg`, `dark-surface`, `dark-ink`): the same instrument with the lights off; data hues and the signal are re-tuned lighter.

### Data hues
`sky`, `violet`, `apricot`, `mint`, `amber`, `crimson` are chosen to hold AA on paper, with lighter `-l` twins for plates. Semantic roles: mint is ok/exact, amber is warn/derived, crimson is error/blocked, sky is info. Status is always colour plus text.

### Named Rules
**The One Signal Rule.** Vermilion marks what the visitor is looking at or about to act on. In the app it is never a decorative fill.
**The Flat Field Rule.** A surface is one solid colour. If it needs separation, use a 2-3px ink rule, a rotation, or a different field, not a gradient or tint ramp.
**The Real Shape Rule.** A coloured block on the landing must stand for a real token or node from recorded output.

## Typography

**Display Font:** Big Shoulders Display Variable (with Archivo Narrow, Impact)
**Body Font:** Archivo Variable (with Helvetica Neue, Arial)
**Label/Mono Font:** IBM Plex Mono (400/500/600), ligatures disabled

**Character:** A heavy condensed poster face against a plain, sturdy grotesque; mono appears only where the text is itself compiler output.

### Hierarchy
- **Display** (900, clamp 3rem to 6rem, 0.88): stage card titles, closing title, roll lines. Uppercase.
- **Headline** (900, clamp 2.4rem to 4.6rem, 0.95): section headings on landing (strips, ways in). Uppercase. The hero h1 is the one step smaller (clamp 3.2rem to 5.6rem, 0.88, nowrap on wide screens).
- **Title** (650, 18px, 1.15): app panel and stage titles; page titles step up to 24px in the display face.
- **Body** (400, 14px app, 15px base, 1.6): running text; card and hero copy are 500 at clamp 1.05rem to 1.3rem, held to 34-38ch.
- **Label** (600, 12.5px): buttons, tabs, chips, table heads.
- **Code** (500, 12.5px mono): tokens, node labels, credits, provenance (11px for captions).

### Named Rules
**The Mono Is Evidence Rule.** Mono type appears only for artifact text: source lines, tokens, node and tool names, versions, hashes, captions of real captures.
**The One Face Rule.** Headlines on any surface use the display face at weight 900; do not mix a second display voice.

## Layout

A 4/8 spacing grid (4 to 112px) inside a 1240px container with a fluid gutter (clamp 1.25rem to 3rem). Landing sections use an `--edge` inset that aligns every band to the same left margin and lets rotated plates bleed off the right edge. The first viewport is a 100svh title card: a 6/6 grid with copy left and the token-to-tree stage right, and a full-width ink credits strip pinned to the bottom edge. Stage cards are 4/7 splits (copy to capture) that alternate sides, are `position: sticky` and 100svh tall, and wipe in via a scroll-linked clip-path where supported. Below 960px the grid collapses to one column, cards become static, and the hero stage drops to 360-440px tall. Honour `prefers-reduced-motion`: the sequence rests on its final step and cards show static.

## Elevation & Depth

Flat. There are no shadows, gradients, glass, or blur on landing surfaces. Depth is carried by stacking and rotation: saffron and cobalt plates tilt 2.5deg and -3deg behind the stage, node blocks sit at alternating -1.6deg and 1.4deg tilts, and every cut shape wears a 2px ink border. Rules (2-3px ink lines) separate poster rows and filmstrip frames. App surfaces use a 1px hairline and, only for floating layers, a soft two-part shadow token (`--shadow-2`).

### Named Rules
**The Cut Paper Rule.** Layering is shown with a flat shape, a tilt, and a hard border; never with a blur or glow.

## Shapes

Hard-edged. Corners are 2px on buttons and tags, 4px on panels and inputs, 6px on instrument bezels, 8px only on large app surfaces. Landing plates and cards are plain rectangles, rotated by a few degrees. Borders are 2px on landing controls and plates (3px on poster-row rules), 1px hairlines in the app. Implied nodes (no token of their own) use a dashed border. The filmstrip perforation is a flat hard-stop repeating dash, not a soft gradient.

## Components

### Buttons
- **Shape:** squared (2px radius), 32px high in the app, 48-52px on landing.
- **Primary (app):** vermilion fill and border, ink text, 14px side padding; hover lightens the fill 12%, lifts 1px.
- **Primary (hero and closing card):** ink fill, cream text, 2px ink border; hover flips to cobalt with white text.
- **Secondary:** transparent, 2px ink border on landing (1px strong line in the app); hover fills cream on landing.
- **Ghost:** borderless, ink-2 text, sand hover. Disabled drops to 50% opacity.
- **Focus:** 2px outline, offset 2px; ink on coloured fields, coral text colour on paper, light coral on plates.

### Cards / Containers
- **Stage title card:** full-bleed field (cream, ink, cobalt, or saffron), 100svh, 4/7 copy and capture split, display-face title, one short sentence of copy.
- **Capture figure:** the real screenshot with a 2px border in the card's text colour and a mono caption; no shadow, no radius.
- **Panel:** paper fill, 1px hairline, 4px radius, header row at 12.5px 650.
- **Bezel and screen:** framed warm-black plate for code, graphs, and runs.

### Inputs / Fields
- Paper fill, 1px strong line, 4px radius, 36px high. Hover darkens the border to ink-3; focus is a 2px coral-text outline. Selects use a pure-CSS chevron.

### Tags
- **Honesty badge:** rectangular mono, 1px border, 2px radius; exact is mint, derived is amber, blocked is crimson, unavailable is ink-3. Always text plus colour.

### Navigation
- **Poster rows ("ways in"):** 3px ink rules, a display-face title, a one-line description, and a square-cap arrow; hover floods the row vermilion and nudges its padding in.

### Signature: Title Sequence stage
One real line of C is shown as source, cut into token blocks, then re-formed as the tree Clang produced. Blocks are rotated flat rectangles with a 2px ink border in ink, cream, saffron, or cobalt; implied nodes are vermilion with a dashed border. Wires are 7px ink lines. Plays once (about 1.1s, 2.7s), rests on the tree, and a three-button step control replays any step.

### Filmstrip
Each pipeline is a row of ink frames with cream 2px dividers and perforated edges; frame labels cycle saffron, cream, vermilion, and a light cobalt tint.

## Do's and Don'ts

### Do:
- **Do** set every headline in the display face at weight 900, uppercase, line-height 0.88-0.95.
- **Do** give each stage card one solid field and let it wipe over the previous one.
- **Do** keep vermilion for the active or primary thing; use `vermilion-text` (not the fill colour) for coral text on paper.
- **Do** make every coloured block on landing correspond to a real token, node, or capture, and label implied nodes with a dashed border.
- **Do** border cut plates and captures with 2px in the text colour; separate rows with 2-3px ink rules.
- **Do** put code and graphs on the warm-black plate in both themes, with data hues from the `-l` set.
- **Do** keep the reduced-motion path static and complete.

### Don't:
- **Don't** use gradients, glass, blur, or glow on landing surfaces; depth is stacking, tilt, and borders.
- **Don't** return to the dark dev-tool hero with a screenshot beneath a gradient headline.
- **Don't** set body or UI text in the display face, or headlines in the grotesque.
- **Don't** use mono for decoration; it is for artifact text only.
- **Don't** use `ink-3` for small body text, or vermilion fill colour as text on cream.
- **Don't** invent a token, node, or capture to fill a plate; show "unavailable" instead.
