/** Pure logic for the -O0 vs -O2 learning layer, kept apart from the UI so it can be unit-tested. */
export interface CmpRow { line: number; ir: number[]; asm: number[] }
export interface Cmp {
  rows: CmpRow[]; removed: number[]; grown: number[]; shrunk: number[]; new: number[];
}
export type Kind = "removed" | "shrunk" | "grown" | "new" | "same";

export function kindOf(c: Cmp, line: number): Kind {
  if (c.removed.includes(line)) return "removed";
  if (c.new.includes(line)) return "new";
  if (c.grown.includes(line)) return "grown";
  if (c.shrunk.includes(line)) return "shrunk";
  return "same";
}

export const KIND_LABEL: Record<Kind, string> = {
  removed: "no code at -O2", shrunk: "fewer asm at -O2", grown: "more asm at -O2",
  new: "only at -O2", same: "same asm count",
};

/** Lines whose assembly count changed, most-changed first, capped, then back in source order. */
export function lessonSteps(c: Cmp, max = 8): CmpRow[] {
  const changed = c.rows.filter((r) => kindOf(c, r.line) !== "same");
  return [...changed]
    .sort((a, b) => Math.abs(b.asm[1] - b.asm[0]) - Math.abs(a.asm[1] - a.asm[0]) || a.line - b.line)
    .slice(0, max)
    .sort((a, b) => a.line - b.line);
}

/** Lines worth quizzing on: they have assembly at at least one level. */
export function quizRows(c: Cmp): CmpRow[] {
  return c.rows.filter((r) => r.asm[0] > 0 || r.asm[1] > 0);
}

/** IR sentence. States counts only; a line with no IR at either level is a line the compiler
 * attached no debug location to (for example a function header), not "zero instructions". */
export function irSentence(r: CmpRow): string {
  if (r.ir[0] === 0 && r.ir[1] === 0) {
    return "No LLVM IR instruction is linked to this line by the compiler's debug info (a function header, for example, is described by metadata, not by an instruction).";
  }
  return `At -O0 this line links to ${r.ir[0]} LLVM IR instruction(s); at -O2 it links to ${r.ir[1]}.`;
}

export function asmSentence(r: CmpRow, kind: Kind): string {
  return `In assembly the line links to ${r.asm[0]} instruction(s) at -O0 and ${r.asm[1]} at -O2 — ${KIND_LABEL[kind]}.`;
}
