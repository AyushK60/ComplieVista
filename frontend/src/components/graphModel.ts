/**
 * Pure graph helpers (no React): node categories, containment depths, framing depth
 * limits, labels and subtree collapse. Kept separate so they can be unit-tested.
 */

// ---- node categories (restrained, semantic — never a rainbow) ----
export function nodeCategory(raw: Record<string, unknown>): string {
  const k = String(raw.kind ?? "");
  if (raw.group === "cfg") return k === "function" ? "cat-decl" : "cat-block";
  if (/^Implicit/.test(k)) return "cat-synthetic";
  if (/Decl$/.test(k) || k === "Module" || k === "FunctionDef" || k === "ClassDef") return "cat-decl";
  if (/Literal$/.test(k) || k === "Constant" || k === "JoinedStr") return "cat-literal";
  if (k === "Name" || k === "arg" || k === "Load" || k === "Store" || k === "DeclRefExpr"
      || k === "Global" || k === "NonLocalDecl") return "cat-name";
  if (/Operator$/.test(k) || /^(BinOp|UnaryOp|Compare|BoolOp|Add|Sub|Mult|Div|Mod|Lt|Gt|LtE|GtE|Eq|NotEq|Is|In|Not|And|Or|UAdd|USub|Invert)$/.test(k))
    return "cat-op";
  if (/Stmt$/.test(k) || /^(If|For|While|Return|Assign|AugAssign|AnnAssign|Try|With|Raise|Break|Continue|Pass|Assert|Delete)$/.test(k))
    return "cat-stmt";
  if (/Expr$/.test(k) || k === "Call" || k === "Comprehension" || k === "arguments"
      || k === "keyword" || k === "Starred" || k === "Slice") return "cat-expr";
  return "cat-expr";
}

export const SYNTHETIC_KINDS = /^Implicit/;

export function node_depths(nodes: Array<Record<string, unknown>>,
                      edges: Array<Record<string, unknown>>): Map<string, number> {
  const incoming = new Map<string, number>();
  for (const n of nodes) incoming.set(n.id as string, 0);
  for (const e of edges) {
    if (e.kind === "containment") incoming.set(e.target as string, (incoming.get(e.target as string) ?? 0) + 1);
  }
  const depth = new Map<string, number>();
  const queue: Array<[string, number]> = [];
  for (const [id, d] of incoming) {
    if (d === 0) { depth.set(id, 0); queue.push([id, 0]); }
  }
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind !== "containment") continue;
    if (!adj.has(e.source as string)) adj.set(e.source as string, []);
    adj.get(e.source as string)!.push(e.target as string);
  }
  while (queue.length) {
    const [id, d] = queue.shift()!;
    for (const t of adj.get(id) ?? []) {
      if (!depth.has(t) || depth.get(t)! < d + 1) {
        depth.set(t, d + 1);
        queue.push([t, d + 1]);
      }
    }
  }
  return depth;
}

export function depth_limit(level: 0 | 1 | 2 | 3, language: string, stage: string): number {
  if (stage.startsWith("ir_")) return level === 0 ? 0 : 1;      // functions -> blocks
  if (stage === "bytecode") return level === 0 ? 0 : 1;          // code objects -> instructions
  return [0, 1, 2, 999][level];                                   // AST: fn -> stmts -> all (default = readable)
}

export const NODE_W = 212;
export const NODE_H = 60;

export function semanticLabel(n: Record<string, unknown>): { kind: string; value: string; line: number | null } {
  const kind = String(n.kind ?? "?");
  const name = n.name ? String(n.name) : "";
  const text = n.text != null && String(n.text).length ? String(n.text).slice(0, 18) : "";
  const value = name || text;
  return { kind, value, line: typeof n.line === "number" ? n.line : null };
}


// F01: subtree collapse follows CONTAINMENT edges only. CFG branch/fallthrough
// edges (which form cycles) must never pull the collapsed root or unrelated
// control flow into the hidden set.
export function g_descendants(edges: Array<Record<string, unknown>>, roots: Set<string>): Set<string> {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind !== "containment") continue;
    const s = e.source as string;
    if (!adj.has(s)) adj.set(s, []);
    adj.get(s)!.push(e.target as string);
  }
  const out = new Set<string>();
  const stack = [...roots];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const t of adj.get(cur) ?? []) {
      if (!out.has(t)) { out.add(t); stack.push(t); }
    }
  }
  return out; // strictly containment descendants; roots always stay visible
}
