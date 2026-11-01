import GraphView, { GraphSelection } from "../GraphView";
import { Selection } from "./types";

/** Bridges the M3 graph engine (xyflow) into the M8 inspector Selection shape.
 * Explanations are derived only from recorded fields (CV-07 rule preserved). */
export default function GraphViewWithSel({ analysisId, stage, onSelect, onSelectLine }: {
  analysisId: string;
  stage: string;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
}) {
  return (
    <GraphView
      analysisId={analysisId}
      stage={stage}
      onSelectLine={(l) => { if (l != null) onSelectLine(l); }}
      onSelectNode={(sel: GraphSelection) => {
        if (!sel) return;
        const n = sel.node;
        const kind = String(n.kind ?? "?");
        const name = n.name ? String(n.name) : "";
        const conf = String(n.confidence ?? "UNAVAILABLE");
        const line = n.line as number | null;
        const what = stage.startsWith("ir_")
          ? IR_WHAT(kind)
          : stage === "bytecode"
            ? "A bytecode instruction node in its code-object group. The lanes view offers a linear reading of the same instructions."
            : AST_WHAT(kind);
        onSelect({
          id: `g:${n.id}`,
          title: name ? `${kind} · ${name}` : kind,
          subtitle: `graph node · ${stage}`,
          stage,
          language: String(n.language ?? ""),
          what,
          fields: [
            ["id", String(n.id)],
            ["kind", kind],
            ...(name ? [["name", name] as [string, string]] : []),
            ["source position", line ? `:${line}:${String(n.col ?? "?")}` : "—"],
            ["mapping", conf],
            ["incoming edges", sel.incoming.map((e) => String(e.kind)).join(", ") || "—"],
            ["outgoing edges", sel.outgoing.map((e) => String(e.kind)).join(", ") || "—"],
            ...(n.opname != null ? [["opcode", String(n.opname)] as [string, string]] : []),
            ...(n.argval != null && n.argval !== "None" ? [["argval", String(n.argval)] as [string, string]] : []),
          ],
          sourceLine: typeof line === "number" ? line : null,
          confidence: conf,
          relations: [
            { label: "incoming", items: sel.incoming.map((e) => `${e.kind} → ${String(e.target)}`) },
            { label: "outgoing", items: sel.outgoing.map((e) => `${e.kind} → ${String(e.target)}`) },
          ],
          raw: n,
        });
      }}
    />
  );
}

function AST_WHAT(kind: string): string {
  if (/Decl$/.test(kind)) return "A declaration: this node introduces a name (function, variable, type) to the rest of the program. Clang reports its exact source range.";
  if (/Stmt$/.test(kind) || kind === "If" || kind === "For" || kind === "While" || kind === "Return" || kind === "Compound")
    return "A statement: one step of control flow. Its children are the expressions and sub-statements it contains.";
  if (/Expr$/.test(kind) || kind === "Call" || kind === "BinaryOperator" || kind === "UnaryOperator" || kind === "ImplicitCastExpr" || kind === "DeclRefExpr" || kind === "Literal")
    return "An expression: computes a value. The compiler folds these into IR instructions; the source link shows exactly which text produced it.";
  return "A node of the real parse tree, with the source range the tool reported for it.";
}

function IR_WHAT(kind: string): string {
  if (kind === "function") return "One function of the LLVM module at this optimization level. Its basic blocks and terminator-derived successors are DERIVED from the .ll text — labeled honestly, not a verified compiler CFG dump.";
  if (kind === "block") return "A basic block: a straight-line run of IR instructions ending in a terminator (branch or return). Successor edges come from the terminator operands.";
  return "An element of the LLVM IR summary derived from the .ll artifact.";
}
