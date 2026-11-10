import { describe, expect, it } from "vitest";
import { aggregate, aggArgSummary, buildTree, localsRepr, retRepr, stackAt } from "./traceModel";
import type { ExecutionEvent } from "../../api";

let seq = 0;
const ev = (kind: string, payload: Record<string, unknown>): ExecutionEvent =>
  ({ seq: ++seq, kind, payload, sha256: "x" });
const call = (fn: string, n?: number, line = 1) =>
  ev("call", { fn, line, locals: n === undefined ? {} : { n: { type: "int", repr: String(n) } } });
const ret = (fn: string, v: number) => ev("return", { fn, arg: { type: "int", repr: String(v) } });

// fib(2) = fib(1) + fib(0): call fib(2) { call fib(1) ret 1; call fib(0) ret 0 } ret 1
const FIB = [call("fib", 2), call("fib", 1), ret("fib", 1), call("fib", 0), ret("fib", 0), ret("fib", 1)];

describe("buildTree", () => {
  it("nests calls and attaches return values", () => {
    const roots = buildTree(FIB);
    expect(roots).toHaveLength(1);
    const root = roots[0];
    expect(root.fn).toBe("fib");
    expect(root.children.map((c) => c.ret)).toEqual(["1", "0"]);
    expect(root.ret).toBe("1");
    expect(root.depth).toBe(0);
    expect(root.children[0].depth).toBe(1);
    expect(root.eventCount).toBe(6);
    expect(root.children[0].parent).toBe(root);
  });

  it("keeps a call with no return (truncated trace) without inventing a value", () => {
    const roots = buildTree([call("main"), call("work")]);
    expect(roots[0].children[0].ret).toBeNull();
    expect(roots[0].children[0].retIdx).toBeNull();
  });

  it("handles an empty trace", () => {
    expect(buildTree([])).toEqual([]);
  });
});

describe("stackAt", () => {
  it("is the open frames before the cursor", () => {
    expect(stackAt(FIB, 0)).toEqual([]);
    expect(stackAt(FIB, 2).map((f) => f.fn)).toEqual(["fib", "fib"]);
    expect(stackAt(FIB, 3).map((f) => f.fn)).toEqual(["fib"]); // inner fib returned
    expect(stackAt(FIB, FIB.length)).toEqual([]);
  });

  it("tracks the current line of the top frame from line events", () => {
    const events = [call("f", undefined, 1), ev("line", { fn: "f", line: 7 })];
    expect(stackAt(events, 2)[0].line).toBe(7);
  });

  it("an exception unwinds a frame", () => {
    const events = [call("f"), ev("exception", { fn: "f", exc: "ValueError" })];
    expect(stackAt(events, 2)).toEqual([]);
  });
});

describe("value rendering", () => {
  it("renders recorded values honestly, never [object Object]", () => {
    expect(retRepr({ type: "int", repr: "5" })).toBe("5");
    expect(retRepr({ type: "list", len: 3 })).toBe("list len=3");
    expect(retRepr({ type: "object", identity: "id:42" })).toBe("id:42");
    expect(retRepr(null)).toBeNull();
    expect(localsRepr(undefined)).toBe("—");
    expect(localsRepr({ type: "dict", len: 2 })).toBe("dict len=2");
  });
});

describe("aggregate", () => {
  it("collapses runs of 3+ identical leaf calls and reports the changing argument", () => {
    const roots = buildTree([
      call("main"),
      ...[1, 2, 3, 4].flatMap((n) => [call("step", n), ret("step", n)]),
      ret("main", 0),
    ]);
    const agg = aggregate(roots[0].children);
    expect(agg).toHaveLength(1);
    const g = agg[0] as { agg: true; nodes: unknown[] };
    expect(g.agg).toBe(true);
    expect(g.nodes).toHaveLength(4);
    expect(aggArgSummary(g.nodes as never)).toBe("n: 1, 2, 3, 4");
  });

  it("leaves short runs alone", () => {
    const roots = buildTree([call("main"), call("a"), ret("a", 1), call("a"), ret("a", 1), ret("main", 0)]);
    expect(aggregate(roots[0].children)).toHaveLength(2);
  });
});
