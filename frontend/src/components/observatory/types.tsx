/** Shared types for the M8 observatory components. */

/** One normalized token item as returned by the `tokens` stage
 * (identical field names for C and Python after backend normalization:
 * kind, text, line, col, mapping_confidence). C `col` is 1-based (clang),
 * Python `col` is 0-based (CPython tokenize). */
export interface TokenItem {
  kind: string;
  text: string;
  line: number;
  col: number;
  mapping_confidence?: string;
}

/** A generic inspector selection. Every canvas maps its domain objects into
 * this; the Inspector renders explanations + exact fields, never invention. */
export interface Selection {
  id: string;
  title: string;
  subtitle?: string;
  stage: string;
  language: string;
  /** what the thing is / why it exists (educational copy, data-independent) */
  what: string;
  /** exact recorded fields, shown verbatim */
  fields: Array<[string, string]>;
  sourceLine?: number | null;
  sourceLabel?: string;
  confidence?: string;
  relations?: Array<{ label: string; items: string[] }>;
  /** verbatim excerpt shown under the explanation (e.g. a basic block's instructions) */
  excerpt?: string;
  raw?: Record<string, unknown>;
}

export type Confidence = "EXACT" | "DERIVED" | "APPROXIMATE" | "UNAVAILABLE" | string;

export function confBadge(c: Confidence | undefined | null) {
  if (!c) return null;
  const cls = c === "EXACT" ? "exact" : c === "DERIVED" ? "derived"
    : c === "APPROXIMATE" ? "derived" : "unavailable";
  return <span className={`badge ${cls}`}>{c}</span>;
}

/** Educational blurbs per stage (UI copy only — never data claims).
 * Explore Mode keeps each to one short sentence; Technical Mode adds the
 * provenance rows underneath the canvas. */
export const STAGE_BLURBS: Record<string, { name: string; what: string }> = {
  preprocess: {
    name: "Preprocessing",
    what: "All the #include files and macros are expanded — this is the text the compiler actually reads.",
  },
  tokens: {
    name: "Token Formation",
    what: "Your characters become tokens: keywords, names, literals, operators — each with its exact source position.",
  },
  ast: {
    name: "Syntax Tree",
    what: "The parser nests tokens into a tree. Click a node to see the line that produced it.",
  },
  code_object: {
    name: "Code Objects",
    what: "CPython compiles each scope — the module, every function — into a code object: its constants, names and locals.",
  },
  bytecode: {
    name: "Bytecode",
    what: "Your AST becomes stack-machine instructions. The arcs are real jumps recorded by the disassembler.",
  },
  ir_o0: {
    name: "LLVM IR (-O0)",
    what: "Clang lowers the tree into LLVM IR: functions, basic blocks, branches. Unoptimized — your code's shape is still visible.",
  },
  ir_o2: {
    name: "LLVM IR (-O2)",
    what: "The optimized IR. Compare with -O0 to watch the optimizer simplify and eliminate code.",
  },
  assembly: {
    name: "Assembly",
    what: "The backend picks real machine instructions for each function — one label per section below.",
  },
  disassembly: {
    name: "Disassembly",
    what: "The compiled object file, read back: addresses, encoded bytes, instructions.",
  },
  object: {
    name: "Object File",
    what: "The compiled object the linker consumes — digest-recorded, never served for execution.",
  },
  symbols: {
    name: "Symbol Table",
    what: "The names this object file defines and expects, from the ELF symbol table.",
  },
  diagnostics: {
    name: "Diagnostics",
    what: "Warnings and errors the toolchain reported, with exact positions.",
  },
};
