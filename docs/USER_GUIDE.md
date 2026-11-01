# CompileVista User Guide — the observatory

CompileVista shows how your code becomes execution. Every view is built from
real compiler/interpreter artifacts recorded in restricted containers; nothing
is simulated, and anything the tools cannot tell you is labeled as such.

## Two modes (top-right switch)

- **Explore** — the journey: big visuals, plain-language explanations,
  provenance hidden.
- **Technical** — everything above plus provenance rows (tool + version, exit
  code, durations, artifact SHA-256 digests, observation class, limitations)
  and raw tool output views.

The selected program, stage, selection and run persist across the switch and
across page reloads (state lives in the URL).

## Three ways in

1. **Demo Library** (`/demos`) — twenty curated programs grouped Python / C /
   matched pairs, filterable by concept and difficulty. Each demo page has
   three story levels (The idea / How it works / Under the hood) and an honest
   capability matrix. "Explore this program" runs the static analysis;
   "Run & replay execution" runs it in a restricted container and opens the
   replay.
2. **Source Workspace** (`/workspace`) — paste code, upload `.c/.h/.py/.zip`,
   or import a public GitHub repo (read-only, pinned to a commit SHA; imported
   code is never executed).
3. **Compare** (`/compare`) — run a matched C/Python pair through both real
   pipelines; stages are synchronized by concept, never pretended equivalent.

## The observatory (workspace)

- **Left — Source Dock**: your file, read-only, line-numbered. Lines light up
  mint when an artifact links to them, cyan when you click them.
- **Center — Journey Navigator**: the real pipeline of your language (Clang/LLVM
  for C, CPython for Python), showing only stages the analysis actually
  produced, with availability badges. "Guided journey" narrates stage by
  stage; exit any time and keep exploring manually.
- **Center — Visual Canvas**: one visualization per stage:
  - *Token Formation*: your source dissolved into the exact tokens the lexer
    reported (whitespace shown as gaps). Click a token to inspect it.
  - *Syntax Tree / LLVM IR*: pan/zoom graph with search, detail levels,
    subtree collapse. CFG edges are labeled DERIVED honestly.
  - *Bytecode*: instructions grouped by code object with branch arcs drawn
    only from the disassembler's own branch targets.
  - *Assembly / Disassembly / Symbols / Object*: static artifacts with
    addresses and machine bytes where objdump provides them.
- **Right — Inspector**: what the selected thing is, why it exists, which
  source line produced it, and its verbatim recorded fields.
- **Execution & Systems dock** (after "Run in restricted container"):
  - *Trace theater*: the recorded call tree (click any call to jump), the
    stack tower with the active frame's variables, playhead event card, and a
    timeline scrubber with speeds. Browsing never re-runs the program.
  - *MemoryScope*: C heap lifetimes (alloc→free ladder; outstanding
    allocations marked as observations, not accusations), Python frame cards,
    alias groups, object graph, tracemalloc and gc records.
  - *ProcessScope*: sampled /proc lanes (RSS/threads/fds — sampled, not
    events), observed children, exit threads; syscall timelines are
    unavailable by policy and shown as an explained gap.
  - *Output*: stdout/stderr with digests.
- **Optimization Explorer** (C targets): build -O0/-O1/-O2 with recorded
  flags, compare assembly or IR side by side, and benchmark uninstrumented
  (checksum-guarded, container-throttled). Python has no O-levels — shown
  honestly instead of faked.

## Honesty rules you can rely on

Every view labels its data: EXACT (tool-reported), DERIVED (computed by
CompileVista from tool output), UNAVAILABLE (explained, never faked). Traces
carry trust labels (CURATED_COOPERATIVE vs UNTRUSTED_TARGET) and integrity
verdicts. Benchmarks describe this container on this machine only.
