import { ExecutionEvent } from "../../api";

/**
 * Pure trace model: turns a recorded event list into a call tree and a stack at a
 * cursor. No React, no I/O — every value comes straight from the recorded events.
 */

export interface Frame {
  fn: string;
  line: number | null;
  callIdx: number;
  locals: Record<string, unknown> | null;
}

export type Locals = Record<string, Record<string, unknown>>;

export interface TreeNode {
  idx: number;              // index of the call event
  fn: string;
  line: number | null;
  args: Locals;             // locals recorded AT the call
  children: TreeNode[];
  ret: string | null;       // return value repr (from return event)
  retIdx: number | null;    // index of the matching return event
  depth: number;
  parent: TreeNode | null;
  eventCount: number;       // events from call to return (inclusive)
  agg?: false;
}

/** Trace values are typed records ({type,repr}|{type,identity}|{type,len}) —
 * render the honest repr, never "[object Object]". */
export function retRepr(arg: unknown): string | null {
  if (arg == null) return null;
  if (typeof arg === "string") return arg;
  if (typeof arg === "object") {
    const a = arg as Record<string, unknown>;
    if (typeof a.repr === "string") return a.repr;
    if (typeof a.identity === "string") return a.identity;
    if (a.len != null) return `${String(a.type ?? "object")} len=${String(a.len)}`;
    if (a.type != null) return String(a.type);
  }
  return String(arg);
}

export function localsRepr(v: Record<string, unknown> | undefined): string {
  if (!v) return "—";
  if (typeof v.repr === "string") return v.repr;
  if (typeof v.identity === "string") return v.identity;
  if (v.len != null) return `${String(v.type ?? "object")} len=${String(v.len)}`;
  return String(v.type ?? "—");
}

export function buildTree(events: ExecutionEvent[]): TreeNode[] {
  const roots: TreeNode[] = [];
  const stack: TreeNode[] = [];
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.kind === "call") {
      const node: TreeNode = {
        idx: i, fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        args: (e.payload.locals as Locals) ?? {},
        children: [], ret: null, retIdx: null, depth: stack.length,
        parent: stack.length ? stack[stack.length - 1] : null, eventCount: 0,
      };
      (stack.length ? stack[stack.length - 1].children : roots).push(node);
      stack.push(node);
    } else if (e.kind === "return") {
      const n = stack.pop();
      if (n) { n.ret = retRepr(e.payload.arg); n.retIdx = i; n.eventCount = i - n.idx + 1; }
    } else if (e.kind === "exception") {
      const n = stack[stack.length - 1];
      if (n) { n.ret = `✗ ${String(e.payload.exc ?? "exception")}`; n.retIdx = i; n.eventCount = i - n.idx + 1; }
    }
  }
  // unterminated frames (trace truncated): count to end
  for (const n of stack) n.eventCount = events.length - n.idx;
  return roots;
}

/** Merge consecutive same-name siblings (×N) to keep huge traces navigable.
 * The group reports the range of the argument that changed across calls, so
 * recursion (fib ×2: n=4, n=3) reads as changing arguments, not a wall of rows. */
export function aggregate(children: TreeNode[]): Array<TreeNode | AggNode> {
  const out: Array<TreeNode | AggNode> = [];
  let i = 0;
  while (i < children.length) {
    let j = i;
    while (j < children.length && children[j].fn === children[i].fn) j++;
    if (j - i > 2 && children[i].children.length === 0) {
      out.push({ agg: true, fn: children[i].fn, nodes: children.slice(i, j) });
    } else {
      for (let k = i; k < j; k++) out.push(children[k]);
    }
    i = j;
  }
  return out;
}
export interface AggNode { agg: true; fn: string; nodes: TreeNode[] }

/** The argument that varies across an aggregate group (for recursion: n). */
export function aggArgSummary(nodes: TreeNode[]): string | null {
  const names = new Set<string>();
  for (const n of nodes.slice(0, 8)) {
    for (const k of Object.keys(n.args)) {
      const v = n.args[k];
      if (v && (typeof v.repr === "string" || typeof v.type === "string")) names.add(k);
    }
  }
  for (const name of names) {
    const vals = nodes.slice(0, 6).map((n) => localsRepr(n.args[name]));
    if (vals.length > 1 && new Set(vals).size > 1) return `${name}: ${vals.slice(0, 4).join(", ")}${nodes.length > 4 ? "…" : ""}`;
  }
  return null;
}

export function stackAt(events: ExecutionEvent[], cursor: number): Frame[] {
  const frames: Frame[] = [];
  for (let i = 0; i < cursor; i++) {
    const e = events[i];
    if (e.kind === "call") {
      frames.push({ fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        callIdx: i, locals: (e.payload.locals as Record<string, unknown>) ?? null });
    } else if (e.kind === "return" || e.kind === "exception") {
      frames.pop();
    } else if (e.kind === "line" && frames.length) {
      frames[frames.length - 1].line = (e.payload.line as number) ?? frames[frames.length - 1].line;
    }
  }
  return frames;
}

export const EVENT_KINDS = ["call", "line", "return", "exception"] as const;

export interface TraceFrame { fn: string; line: number | null; callIdx: number; locals: Record<string, unknown> | null }
export interface TreeNodeInfo extends TreeNode {}
