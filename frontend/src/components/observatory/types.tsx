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
  raw?: Record<string, unknown>;
}

export type Confidence = "EXACT" | "DERIVED" | "APPROXIMATE" | "UNAVAILABLE" | string;

export function confBadge(c: Confidence | undefined | null) {
  if (!c) return null;
  const cls = c === "EXACT" ? "exact" : c === "DERIVED" ? "derived"
    : c === "APPROXIMATE" ? "derived" : "unavailable";
  return <span className={`badge ${cls}`}>{c}</span>;
}

/** Educational blurbs per stage (UI copy only — never data claims). */
export const STAGE_BLURBS: Record<string, { name: string; what: string }> = {
  preprocess: {
    name: "Preprocessing",
    what: "The preprocessor expands #include directives and macros, producing one translation unit of pure C code. This is the text the compiler actually sees.",
  },
  tokens: {
    name: "Token Formation",
    what: "The lexer reads your characters and produces tokens: the smallest units with meaning — keywords, identifiers, literals, operators. Every chip below is a token the real tool reported, with its exact source position.",
  },
  ast: {
    name: "Syntax Tree",
    what: "The parser turns the flat token stream into a tree that captures the grammar of your program: expressions nest inside statements, statements inside functions. Each node knows exactly which source range produced it.",
  },
  code_object: {
    name: "Code Objects",
    what: "CPython compiles each scope — the module, each function, each class body — into a code object: the constants, names and variables that its bytecode will reference.",
  },
  bytecode: {
    name: "Bytecode",
    what: "CPython compiles your AST into bytecode: a list of stack-machine instructions executed by the interpreter loop. Offsets, opcodes and branch targets come from the disassembler of the running Python version.",
  },
  ir_o0: {
    name: "LLVM IR (-O0)",
    what: "Clang lowers the AST into LLVM's intermediate representation: functions containing basic blocks of instructions. Unoptimized — you can still see the shape of your source clearly.",
  },
  ir_o2: {
    name: "LLVM IR (-O2)",
    what: "The optimized intermediate representation. Compare with -O0 to watch the optimizer simplify, merge and eliminate code.",
  },
  assembly: {
    name: "Assembly",
    what: "The LLVM backend selects machine instructions and emits assembly for the target architecture — one function label per section below.",
  },
  disassembly: {
    name: "Disassembly",
    what: "The compiled object file, disassembled back into instructions with real addresses and machine bytes (objdump).",
  },
  object: {
    name: "Object File",
    what: "The compiled object code — the artifact the linker consumes. Its digest is recorded; the binary itself is never served or executed directly.",
  },
  symbols: {
    name: "Symbol Table",
    what: "The names the object file defines and expects: functions, globals, and their binding/type from the ELF symbol table.",
  },
  diagnostics: {
    name: "Diagnostics",
    what: "Warnings and errors the toolchain reported while analyzing your program, with exact source positions.",
  },
};
