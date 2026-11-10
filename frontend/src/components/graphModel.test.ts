import { describe, expect, it } from "vitest";
import { depth_limit, g_descendants, node_depths, nodeCategory, semanticLabel } from "./graphModel";

const contain = (s: string, t: string) => ({ kind: "containment", source: s, target: t });

describe("nodeCategory", () => {
  it("classifies Clang and CPython kinds", () => {
    expect(nodeCategory({ kind: "FunctionDecl" })).toBe("cat-decl");
    expect(nodeCategory({ kind: "FunctionDef" })).toBe("cat-decl");
    expect(nodeCategory({ kind: "IntegerLiteral" })).toBe("cat-literal");
    expect(nodeCategory({ kind: "Constant" })).toBe("cat-literal");
    expect(nodeCategory({ kind: "Name" })).toBe("cat-name");
    expect(nodeCategory({ kind: "BinaryOperator" })).toBe("cat-op");
    expect(nodeCategory({ kind: "IfStmt" })).toBe("cat-stmt");
    expect(nodeCategory({ kind: "ImplicitCastExpr" })).toBe("cat-synthetic");
    expect(nodeCategory({ kind: "CallExpr" })).toBe("cat-expr");
  });
  it("separates CFG functions from blocks", () => {
    expect(nodeCategory({ group: "cfg", kind: "function" })).toBe("cat-decl");
    expect(nodeCategory({ group: "cfg", kind: "block" })).toBe("cat-block");
  });
});

describe("node_depths", () => {
  it("assigns depth along containment edges from the roots", () => {
    const nodes = [{ id: "a" }, { id: "b" }, { id: "c" }, { id: "d" }];
    const depths = node_depths(nodes, [contain("a", "b"), contain("b", "c"), contain("a", "d")]);
    expect(["a", "b", "c", "d"].map((i) => depths.get(i))).toEqual([0, 1, 2, 1]);
  });
  it("uses the longest path when a node is reachable twice", () => {
    const nodes = [{ id: "a" }, { id: "b" }, { id: "c" }];
    const depths = node_depths(nodes, [contain("a", "b"), contain("b", "c"), contain("a", "c")]);
    expect(depths.get("c")).toBe(2);
  });
});

describe("depth_limit", () => {
  it("frames AST levels, IR and bytecode differently", () => {
    expect([0, 1, 2, 3].map((l) => depth_limit(l as 0 | 1 | 2 | 3, "c", "ast"))).toEqual([0, 1, 2, 999]);
    expect(depth_limit(2, "c", "ir_o0")).toBe(1);
    expect(depth_limit(0, "python", "bytecode")).toBe(0);
  });
});

describe("g_descendants", () => {
  it("follows containment only, so CFG cycles cannot hide unrelated nodes", () => {
    const edges = [
      contain("root", "x"), contain("x", "y"),
      { kind: "branch", source: "y", target: "root" }, // CFG back edge: must be ignored
      { kind: "fallthrough", source: "root", target: "other" },
    ];
    expect([...g_descendants(edges, new Set(["x"]))].sort()).toEqual(["y"]);
    expect(g_descendants(edges, new Set(["root"])).has("other")).toBe(false);
  });
});

describe("semanticLabel", () => {
  it("prefers the name, then a short text, and passes the line through", () => {
    expect(semanticLabel({ kind: "FunctionDecl", name: "main", line: 3 }))
      .toEqual({ kind: "FunctionDecl", value: "main", line: 3 });
    expect(semanticLabel({ kind: "Constant", text: "a-very-long-literal-value-here" }).value).toHaveLength(18);
    expect(semanticLabel({ kind: "X" }).line).toBeNull();
  });
});
