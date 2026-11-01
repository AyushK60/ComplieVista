"""M8 Part-2 regression: the IR CFG extraction must carry each basic block's
verbatim instruction text (capped) so the CFG graph can offer instruction-level
inspection. Pure presentation extraction from the stored .ll artifact — the
compilation engine is untouched. Blocks are closed by '}' so module-level lines
never leak into the previous function's blocks."""
from __future__ import annotations

from app.services.normalize import _ir_summary

LL = """\
; ModuleID = '/work/demo.c'
target triple = "x86_64-pc-linux-gnu"

@.str = private constant [4 x i8] c"%d\0A\00"

define i32 @clamp(i32 %v) {
entry:
  %cmp = icmp slt i32 %v, 0
  br i1 %cmp, label %lo, label %hi

lo:                                               ; preds = %entry
  ret i32 0

hi:                                               ; preds = %entry
  ret i32 %v
}

declare i32 @printf(ptr, ...)

define i32 @main() {
entry:
  %call = call i32 (ptr, ...) @printf(
        ptr @.str,
        i32 3)
  switch i32 %call, label %done [
    i32 0, label %ok
    i32 1, label %bad
  ]

ok:
  ret i32 0

bad:
  ret i32 1

done:
  ret i32 2
}
"""


def test_ir_blocks_carry_instructions_and_edges():
    out = _ir_summary(LL)
    fns = {f["name"]: f for f in out["functions"]}
    assert set(fns) == {"clamp", "main"}  # declare is not a define

    clamp = fns["clamp"]["blocks"]
    assert [b["label"] for b in clamp] == ["entry", "lo", "hi"]
    assert clamp[0]["instructions"] == ["%cmp = icmp slt i32 %v, 0",
                                        "br i1 %cmp, label %lo, label %hi"]
    assert clamp[0]["successors"] == ["lo", "hi"]
    assert clamp[1]["instructions"] == ["ret i32 0"]
    assert clamp[1]["terminators"] == ["ret"]

    main_blocks = {b["label"]: b for b in fns["main"]["blocks"]}
    # the entry block merged its implicit <entry> label with the printed label
    assert "entry" in main_blocks
    # switch terminators accumulate across continuation lines (CV-02) and the
    # whole statement is kept as ONE instruction line
    sw = main_blocks["entry"]["instructions"][-1]
    assert sw.startswith("switch i32 %call") and "i32 1, label %bad" in sw
    assert main_blocks["entry"]["successors"] == ["done", "ok", "bad"]
    # module-level lines between functions must not leak into any block
    assert all("printf" not in ins or "call" in ins
               for b in fns["clamp"]["blocks"] for ins in b["instructions"])
    assert not any(ins.startswith("declare") for f in out["functions"]
                   for b in f["blocks"] for ins in b["instructions"])
    assert out["counts"]["cfg_edges_derived"] == 5


def test_ir_instruction_cap_is_honest():
    body = "\n".join(f"  %v{i} = add i32 1, 2" for i in range(300))
    out = _ir_summary(f"define i32 @big() {{\nentry:\n{body}\n  ret i32 0\n}}\n")
    b = out["functions"][0]["blocks"][0]
    assert len(b["instructions"]) == 200
    assert b["instructions_truncated"] is True
    assert b["terminators"] == ["ret"]  # the terminator is recorded even when capped
