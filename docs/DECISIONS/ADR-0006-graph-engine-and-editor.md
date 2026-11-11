# ADR-0006 - stage 3 graph engine, layout, and editor substitution

Status: Accepted (Stage 3)

## Decisions

1. **Graph contracts (`m3.graph.v1`)**: `GET /api/v1/analyses/{id}/stages/{stage}/graph`
   derives nodes/edges ONLY from stored stage 2.5 normalized items. AST containment edges are
   EXACT (tree-structured, enforced by test); CFG branch edges are DERIVED from real
   terminator data; bytecode jump edges are DERIVED from real jump targets. Source→IR /
   source→assembly mapping stays UNAVAILABLE - no such edges are generated. Caps:
   2000 nodes / 4000 edges with explicit `truncated` flags.
2. **Canvas**: `@xyflow/react@12.3.5` (MIT) - maintained React graph engine with
   minimap/controls/virtualization (`onlyRenderVisibleElements`) built in.
3. **Layout**: ELK was attempted (`elkjs@0.9.3`) and **failed inside a module worker**
   (`_Worker is not a constructor` - ELK bundled spawns a nested Worker; Vite dev worker
   environment rejects it). Replaced with a dependency-free deterministic layered layout
   (longest-path layering, Kahn-style, ordered within layers) executed in the same Web
   Worker - never on the main thread. Layout time is measured and displayed; reconsider
   ELK (e.g. main-thread with chunking or fixed worker packaging) in stage 8 if richer
   layouts are needed.
4. **Editor**: Monaco was attempted and **deferred to stage 8**: even with static `?worker`
   imports the Vite dev runtime raised `_Worker is not a constructor` on editor worker
   startup (both dynamic package URLs and static imports attempted; dependencies
   removed to avoid dead weight). The equivalent read-only mode per the stage 3 prompt is
   implemented in `CodeView`: keyword/string/comment coloring, line highlight,
   `scrollIntoView` for graph→source navigation, browser-native search, and an explicit
   read-only/immutable-snapshot label. Editing continues to require a new snapshot (Stage 4+
   policy); no visible editor may diverge from artifact hashes.
5. **Fix surfaced by the graph tests (Stage 2-era latent bug)**: `_clang_ast_nodes` appended
   child ids to `nodes[-1]` AFTER the recursive walk had appended descendants, corrupting
   the children lists (audit CV-01's tree test exposed it). Fixed by capturing the parent
   index before recursion; AST containment is now provably a tree.

## Consequences

- Graph adapters are pure transforms of stored stage items - backend changes were not
  needed beyond the endpoint and the tree fix (which has its own regression test).
- The frontend never renders a node that does not exist in `m3.graph.v1`; semantic zoom
  changes information density only, with deterministic thresholds (0.35/0.8/1.4).
- Table/raw views remain for every graphable stage (accessibility + fallback), and
  non-graphable stages keep their stage 2 views.
