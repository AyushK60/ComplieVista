import { describe, expect, it } from "vitest";
import { asmSentence, irSentence, kindOf, lessonSteps, quizRows, Cmp } from "./optLearnModel";

// shaped like a real compare_O0_O2 payload (C-02)
const cmp: Cmp = {
  rows: [
    { line: 9, ir: [0, 0], asm: [4, 2] },
    { line: 10, ir: [2, 0], asm: [1, 0] },
    { line: 12, ir: [6, 0], asm: [7, 0] },
    { line: 22, ir: [3, 3], asm: [4, 4] },
    { line: 30, ir: [0, 1], asm: [0, 3] },
    { line: 31, ir: [1, 1], asm: [0, 0] },
  ],
  removed: [10, 12], grown: [], shrunk: [9], new: [30],
};

describe("optLearnModel", () => {
  it("classifies each line from the compare payload", () => {
    expect(kindOf(cmp, 10)).toBe("removed");
    expect(kindOf(cmp, 9)).toBe("shrunk");
    expect(kindOf(cmp, 30)).toBe("new");
    expect(kindOf(cmp, 22)).toBe("same");
  });
  it("orders lesson steps by source line after picking the biggest changes", () => {
    const s = lessonSteps(cmp, 3).map((r) => r.line);
    expect(s).toEqual([9, 12, 30]);          // deltas 2, 7, 3 beat 1; shown in source order
    expect(lessonSteps(cmp).every((r) => kindOf(cmp, r.line) !== "same")).toBe(true);
  });
  it("quizzes only on lines that have assembly somewhere", () => {
    expect(quizRows(cmp).map((r) => r.line)).not.toContain(31);
  });
  it("does not say '0 IR instructions' for lines the compiler gave no IR location", () => {
    expect(irSentence(cmp.rows[0])).toMatch(/No LLVM IR instruction is linked/);
    expect(irSentence(cmp.rows[1])).toBe("At -O0 this line links to 2 LLVM IR instruction(s); at -O2 it links to 0.");
  });
  it("states counts and the kind label for assembly", () => {
    expect(asmSentence(cmp.rows[1], "removed")).toContain("1 instruction(s) at -O0 and 0 at -O2 — no code at -O2");
  });
});
