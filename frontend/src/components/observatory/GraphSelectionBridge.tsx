import GraphView, { GraphSelection } from "../GraphView";
import { Selection } from "./types";

/** Bridges the M3 graph engine (xyflow) into the M8 inspector Selection shape.
 * Explanations are derived only from recorded fields (CV-07 rule preserved). */
export default function GraphViewWithSel({ analysisId, stage, onSelect, onSelectLine, focusLine, guided, onNavigateStage, fullscreen }: {
  analysisId: string;
  stage: string;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
  focusLine?: number | null;
  guided?: boolean;
  onNavigateStage?: (stage: string) => void;
  fullscreen?: boolean;
}) {
  return (
    <GraphView
      analysisId={analysisId}
      stage={stage}
      focusLine={focusLine ?? null}
      guided={guided}
      onNavigateStage={onNavigateStage}
      fullscreen={fullscreen}
      onSelectLine={(l) => { if (l != null) onSelectLine(l); }}
      onSelectNode={(sel: GraphSelection) => {
        if (!sel) return;
        const n = sel.node;
        const kind = String(n.kind ?? "?");
        const name = n.name ? String(n.name) : "";
        const conf = String(n.confidence ?? "UNAVAILABLE");
        const line = n.line as number | null;
        const what = stage.startsWith("ir_")
          ? IR_WHAT(kind, n)
          : stage === "bytecode"
            ? "A bytecode instruction node in its code-object group. The lanes view offers a linear reading of the same instructions."
            : AST_WHAT(kind);
        const fields: Array<[string, string]> = [
          ["id", String(n.id)],
          ["kind", kind],
          ...(name ? [["name", name] as [string, string]] : []),
          ["source position", line ? `:${line}:${String(n.col ?? "?")}` : "—"],
          ["mapping", conf],
          ["incoming edges", sel.incoming.map((e) => String(e.kind)).join(", ") || "—"],
          ["outgoing edges", sel.outgoing.map((e) => String(e.kind)).join(", ") || "—"],
          ...(n.opname != null ? [["opcode", String(n.opname)] as [string, string]] : []),
          ...(n.argval != null && n.argval !== "None" ? [["argval", String(n.argval)] as [string, string]] : []),
        ];
        // IR blocks now carry their verbatim instruction text (backend extraction)
        const instrs = n.instructions as string[] | undefined;
        if (instrs?.length) fields.push(["instructions", `${instrs.length} (see below)`]);
        onSelect({
          id: `g:${n.id}`,
          title: name ? `${kind} · ${name}` : kind,
          subtitle: `graph node · ${stage}`,
          stage,
          language: String(n.language ?? ""),
          what,
          fields,
          sourceLine: typeof line === "number" ? line : null,
          confidence: conf,
          relations: [
            // incoming edges are listed by the node they come FROM, outgoing by the node they go TO
            { label: "incoming", items: sel.incoming.map((e) => `${e.kind} ← ${sel.labels[String(e.source)] ?? String(e.source)}`) },
            { label: "outgoing", items: sel.outgoing.map((e) => `${e.kind} → ${sel.labels[String(e.target)] ?? String(e.target)}`) },
          ],
          raw: n,
          excerpt: instrs?.length ? instrs.slice(0, 40).join("\n") : undefined,
        });
      }}
    />
  );
}

function AST_WHAT(kind: string): string {
  if (/^Implicit/.test(kind)) return "Inserted by the compiler, not written by you: an implicit conversion between types. The graph labels it honestly and you can filter these nodes out.";
  if (/Decl$/.test(kind) || kind === "FunctionDef" || kind === "ClassDef") return "A declaration: this node introduces a name (function, variable, type) to the rest of the program. Clang reports its exact source range.";
  if (/Stmt$/.test(kind) || kind === "If" || kind === "For" || kind === "While" || kind === "Return" || kind === "Compound")
    return "A statement: one step of control flow. Its children are the expressions and sub-statements it contains.";
  if (/Expr$/.test(kind) || kind === "Call" || kind === "BinaryOperator" || kind === "UnaryOperator" || kind === "DeclRefExpr" || kind === "Literal")
    return "An expression: computes a value. The compiler folds these into IR instructions; the source link shows exactly which text produced it.";
  return "A node of the real parse tree, with the source range the tool reported for it.";
}

function IR_WHAT(kind: string, n: Record<string, unknown>): string {
  if (kind === "function") return "One function of the LLVM module at this optimization level. Its basic blocks and terminator-derived successors are DERIVED from the .ll text — labeled honestly, not a verified compiler CFG dump.";
  if (kind === "basic_block") {
    const nin = (n.n_instructions as number | undefined) ?? 0;
    return `A basic block: a straight-line run of ${nin || "its"} IR instruction${nin === 1 ? "" : "s"} ending in a terminator (branch or return). Successor edges come from the terminator operands; the instructions themselves are extracted verbatim from the .ll artifact.`;
  }
  return "An element of the LLVM IR summary derived from the .ll artifact.";
}
