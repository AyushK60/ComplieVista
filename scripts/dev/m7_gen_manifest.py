"""Generate sandbox/fixtures/demos/manifest.json - exactly 20 real programs.

Hashes computed from the fixture files; expected outputs are the HOST-verified
values (scripts/dev/m7_verify_demos.sh + the stage 6 pair verification).
"""
import hashlib
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "sandbox" / "fixtures"
PAIRS = Path(__file__).resolve().parents[2] / "sandbox" / "fixtures" / "pairs"
ERR_DIR = Path(__file__).resolve().parents[2] / "sandbox" / "fixtures" / "errors"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def story(simple: str, detailed: str, technical: str) -> dict:
    return {"simple": simple, "detailed": detailed, "technical": technical}


def demo(id_, group, title, difficulty, concepts, files, primary, expected,
         guided, capabilities, limits, tus=None):
    return {
        "id": id_, "group": group, "title": title, "difficulty": difficulty,
        "concepts": concepts,
        "files": [{"path": f, "sha256": sha(FIXTURES / f)} for f in files],
        "primary_file": primary, "tus": tus or [],
        "expected_stdout": expected, "expected_exit": 0,
        "guided": guided, "capabilities": capabilities, "limits": limits,
    }


CAP_C = {"analysis": "AVAILABLE (clang-18 tokens/AST/IR-O0+O2/asm/object/symbols)",
         "execution": "AVAILABLE (restricted container, instrumented trace)",
         "trace": "AVAILABLE (call/return via -finstrument-functions)",
         "memory": "PARTIAL (C heap via allocator interposition; frame locals "
                   "unavailable outside the curated gdb profile)",
         "process": "AVAILABLE (container /proc sampling)",
         "optimization": "AVAILABLE (OptimizationLab -O0/-O1/-O2)"}
CAP_PY = {"analysis": "AVAILABLE (CPython 3.12 tokens/AST/symtable/code objects/bytecode)",
          "execution": "AVAILABLE (restricted container, sys.settrace harness)",
          "trace": "AVAILABLE (call/line/return/exception via sys.settrace)",
          "memory": "AVAILABLE (frame snapshots, id()-based aliases, bounded "
                    "object graph, tracemalloc/gc)",
          "process": "AVAILABLE (container /proc sampling)",
          "optimization": "UNAVAILABLE (Python has no LLVM -O levels; bytecode "
                          "comparison is version-pinned CPython)"}

demos = []

demos.append(demo(
    "PY-01", "A", "Fundamentals: variables, expressions, functions, branching",
    "introductory", ["variables", "expressions", "functions", "branching"],
    ["demos/PY-01.py"], "PY-01.py", "area=10\nscaled=7\nkind=valid",
    story("A tiny program computes a triangle area twice and checks the result is valid.",
          "Watch the recorded trace: `area` is called twice with different arguments, "
          "the branch inside it takes the same path both times, and each return value "
          "flows back to the module frame.",
          "Bytecode: CALL/RETURN under sys.settrace; locals snapshots show base/height "
          "per call. Python 3.12 bytecode is version-pinned; no LLVM IR exists here."),
    CAP_PY,
    ["Trace caps: 5000 events / 64 frames / 200 locals (not reached here)."]))

demos.append(demo(
    "PY-02", "A", "Loops and collections: accumulator with filtering",
    "introductory", ["loops", "collections", "accumulator", "bytecode jumps"],
    ["demos/PY-02.py"], "PY-02.py", "total=99\nevens=12,20,8\ncount=3",
    story("One loop walks a list, sums everything, and collects the even numbers.",
          "The line-event stream shows FOR_ITERATION jumps: the loop body runs 8 times "
          "and the branch appends only 3 values. Locals snapshots show the accumulator "
          "grow from call to call.",
          "Bytecode: FOR_ITER/COMPARE_OP/JUMP_ABSOLUTE pattern; list.append is a C "
          "builtin (no Python frame, hence no call events for it)."),
    CAP_PY,
    ["Output list order is deterministic (insertion order)."]))

demos.append(demo(
    "PY-03", "A", "True recursion: frame growth and unwinding",
    "intermediate", ["recursion", "call stack", "frame unwind"],
    ["demos/PY-03.py"], "PY-03.py", "fib12=144\ncalls=465",
    story("fib(12) calls itself 465 times; the trace shows the call stack grow and "
          "shrink.",
          "The replay timeline shows depth increasing to 12 and unwinding; each frame "
          "has its own `n` (see locals). The 465 count includes both leaf and inner "
          "calls (2*F(13)-1).",
          "Tree recursion: calls(fib)=2*F(13)-1=465. Depth cap is 64 - this program "
          "peaks at 12, so the full tree is recorded."),
    CAP_PY,
    ["Do not confuse CALLS (465) with max depth (12)."]))

demos.append(demo(
    "PY-04", "A", "Closure, generator suspension, exception scope",
    "intermediate", ["closures", "generators", "suspension", "exceptions", "finally"],
    ["demos/PY-04.py"], "PY-04.py",
    "counter=15,17\npairs=0,4\nsuspended=yes\ncaught=scope demo\nfinally=finally-ran",
    story("A closure keeps private state, a generator pauses twice, and an exception "
          "is caught with a finally block.",
          "The generator's frame_id stays STABLE across suspensions (Stage 5 review fix): a "
          "yield is a suspension, not a frame death. The manual next() consumes one "
          "value (pairs=0,4 - the 2 is skipped), demonstrating the iterator protocol "
          "vs the for-loop protocol. The closure's `count` survives between calls.",
          "Generator resumption re-fires 'call' events (CPython semantics); "
          "CO_GENERATOR frames are not popped at yield. Exception records name the "
          "instance; user __str__ is never evaluated by the tracer."),
    CAP_PY,
    ["Generator memory previews show identity, not contents of suspended frames."]))

demos.append(demo(
    "PY-05", "A", "Classes, imports, bounded concurrency",
    "advanced", ["classes", "imports", "threads", "scheduling limitations"],
    ["demos/PY-05.py"], "PY-05.py",
    'acc=15\nthreads=[{"double": 72, "input": 36, "sqrt": 6}, '
    '{"double": 20, "input": 10, "sqrt": 3}]',
    story("Two threads compute results into preassigned slots; a small class "
          "accumulates a total.",
          "join() makes the outcome deterministic because each thread writes its OWN "
          "slot - the output does not depend on scheduling. The recorded trace shows "
          "only the main thread (sys.settrace is per-thread) - an honest limitation.",
          "Worker threads are NOT traced (settrace is thread-local); results are "
          "index-addressed to avoid order dependence. GIL interleaving is not "
          "observed and not claimed."),
    CAP_PY,
    ["Thread interleaving is unobservable in the trace - scheduling limitations "
     "are declared, not hidden."]))

demos.append(demo(
    "C-01", "B", "Expressions, functions, branching → LLVM IR",
    "introductory", ["expressions", "functions", "branching", "LLVM IR"],
    ["demos/C-01.c"], "C-01.c", "r1=37 r2=2 r3=100",
    story("Two small functions clamp and average values; the IR shows the "
          "unoptimized bodies.",
          "At -O0 the IR loads/stores every local through the stack; OptimizationLab "
          "shows -O2 collapsing the arithmetic. The recorded trace shows call/return "
          "for clamp and weighted.",
          "Instrumented with -finstrument-functions (call/return events, no ptrace); "
          "clamp is inlined at -O2 (verify in OptimizationLab: the symbol disappears "
          "from the O2 build)."),
    CAP_C,
    ["Static assembly is not an executed-instruction count."]))

demos.append(demo(
    "C-02", "B", "Preprocessor, conditional build, loop → CFG",
    "intermediate", ["preprocessor", "macros", "conditional build", "CFG"],
    ["demos/C-02.c"], "C-02.c", "acc=85",
    story("Macros and #if select the build path at COMPILE time; the loop's CFG has "
          "a header, body and exit block.",
          "The preprocess stage shows SCALE(i) expanded to ((i) * 2); DEMO_MODE=2 "
          "makes the #else branch dead at compile time - the #else code is never "
          "compiled, which the IR/ASM absence shows.",
          "CFG: for-header → if → two successors → latch → exit. Basic-block "
          "inventory comes from real clang IR/ASM, not a generic diagram."),
    CAP_C,
    ["#if pruning is a compile-time effect - the trace cannot show it at runtime."]))

demos.append(demo(
    "C-03", "B", "Pointers and arrays on the stack",
    "intermediate", ["pointers", "arrays", "stack", "pointer arithmetic"],
    ["demos/C-03.c"], "C-03.c", "first=9 last=4 sum=23",
    story("swap() exchanges two array ends through pointers; a bounded slice sum "
          "walks the array.",
          "The IR shows pointer dereferences as loads/stores; swap's effects are "
          "visible in the output (first/last exchanged). Pointer arithmetic stays "
          "in bounds - the demo never walks past the array.",
          "Array decay: sum_slice receives int* - same machine representation as "
          "&arr[0]. Address instability (ASLR) applies to any recorded addresses."),
    CAP_C,
    ["Out-of-bounds arithmetic would be UB - this demo stays in bounds by design."]))

demos.append(demo(
    "C-04", "B", "Structs and dynamic memory (malloc/free, correct path)",
    "advanced", ["structs", "malloc", "free", "lifetimes"],
    ["demos/C-04.c"], "C-04.c", "total=66 last=ok",
    story("Three struct records are allocated on the heap, filled, summed and "
          "freed - correctly.",
          "The allocator interposition records the malloc(3*sizeof(record_t)) with "
          "its real size and the matching free: outstanding returns to zero. NULL is "
          "checked before use (no UB on OOM).",
          "sizeof(record_t) includes tail padding for the char[8] tag - check the "
          "interposed size (3*24) rather than assuming field sums."),
    CAP_C,
    ["Sanitizer availability varies; correct-path malloc/free here means NO "
     "diagnostics are expected - absence of findings is not proof of coverage."]))

demos.append(demo(
    "C-05", "B", "Multi-file C project: header + 2 translation units",
    "advanced", ["multi-file", "linkage", "symbols", "translation units"],
    ["demos/C-05/main.c", "demos/C-05/math_utils.c", "demos/C-05/math_utils.h"], "C-05/main.c",
    "series=95 gcd=12",
    story("One program in three files: a header declares, one TU implements, the "
          "main TU uses it. The LINKER connects them.",
          "Both TUs are compiled separately (two compile steps in the build record), "
          "then linked. The linked binary's symbol table contains math_sum_series "
          "and math_gcd defined (T) - that is the cross-TU resolution evidence.",
          "Analysis covers the primary TU's stages; the LINK step evidence (symbols "
          "of the final binary) is what proves cross-TU linkage - static analysis of "
          "one TU never assumes the other executes independently."),
    {"analysis": "AVAILABLE for the primary TU (main.c); the second TU is compiled "
                 "and linked, not independently analyzed",
     "execution": "AVAILABLE (linked binary, instrumented TUs)",
     "trace": "AVAILABLE (both TUs instrumented; call/return across TUs recorded)",
     "memory": "PARTIAL (allocator interposition)",
     "process": "AVAILABLE",
     "optimization": "AVAILABLE (OptimizationLab builds the primary file; "
                     "multi-file O-level builds are not wired)"},
    ["Multi-file linking is a curated-demo capability; pasted multi-file C still "
     "runs single-file only."],
    tus=["main.c", "math_utils.c"]))

# Group C: matched pairs (reuse the stage 6 pair fixtures - host-verified)
pair_meta = [
    ("PAIR-01", "add", "Addition and basic functions", "very easy",
     ["arithmetic", "functions"],
     "Same sum computed in both languages; compare the C IR against Python bytecode."),
    ("PAIR-02", "conditional", "Classification branches", "easy",
     ["branching", "conditions"],
     "Same classification; C shows branch blocks in IR, Python shows COMPARE_OP/JUMP "
     "in bytecode."),
    ("PAIR-03", "recursion", "Bounded tree recursion (fib 20)", "moderate",
     ["recursion", "call stack"],
     "fib(20): C call/return via instrumentation; Python via settrace; frame depths "
     "are language-specific."),
    ("PAIR-04", "arraysum", "Array/list aggregation", "advanced",
     ["arrays", "lists", "traversal"],
     "Same aggregation over 1000 values; C uses a fixed array, Python a list "
     "comprehension - concept match, not stage match."),
    ("PAIR-05", "sort", "Insertion sort with modulo checksum", "challenging",
     ["sorting", "algorithms"],
     "Same insertion sort; checksum uses % 1000000007 so C has NO signed overflow "
     "(UB) and Python big-int semantics stay in range."),
]
pair_expected = {p["id"]: p["expected_stdout"]
                 for p in json.loads((PAIRS / "manifest.json").read_text())["pairs"]}
for pid, base, title, difficulty, concepts, detail in pair_meta:
    c_file, py_file = f"{base}.c", f"{base}.py"
    expected = pair_expected[base]
    demos.append(demo(
        f"{pid}-C", "C", f"{title} (C side)", difficulty, concepts,
        [f"pairs/{c_file}"], f"pairs/{c_file}", expected,
        story(f"The C side of the {pid} pair. {detail}",
              f"Compare with the Python side via the Compare page: matched inputs, "
              f"expected output {expected.strip()!r} verified with host toolchains.",
              "Concepts synchronize across languages - stages do NOT (IR vs "
              "bytecode). Trace call/return pairs come from the same instrumentation "
              "as stage 4."),
        CAP_C,
        ["Paired with " + pid + "-PY; run both via the Compare page for the "
         "side-by-side view."]))
for pid, base, title, difficulty, concepts, detail in pair_meta:
    c_file, py_file = f"{base}.c", f"{base}.py"
    expected = pair_expected[base]
    demos.append(demo(
        f"{pid}-PY", "C", f"{title} (Python side)", difficulty, concepts,
        [f"pairs/{py_file}"], f"pairs/{py_file}", expected,
        story(f"The Python side of the {pid} pair. {detail}",
              f"Expected output {expected.strip()!r} - identical to the C side by "
              f"construction and verified against host toolchains.",
              "Group C demos use CPython 3.12 bytecode; specialization happens at "
              "runtime and is not part of static evidence."),
        CAP_PY,
        ["Paired with " + pid + "-C."]))

manifest = {
    "version": "m7.demos.v1",
    "policy": "Exactly 20 logical programs: 5 Python-only (A), 5 C-only (B), "
              "10 pair halves (C) forming 5 matched pairs. C-05 is ONE logical "
              "program across 3 files. Error fixtures are NOT counted. Expected "
              "outputs verified with host toolchains (scripts/dev/m7_verify_demos.sh).",
    "demos": demos,
    "error_fixtures": [
        {"id": "ERR-SYNTAX", "file": "err_syntax.c", "language": "c",
         "kind": "syntax", "expect": "clang parse diagnostic, exit != 0"},
        {"id": "ERR-SEMANTIC", "file": "err_semantic.c", "language": "c",
         "kind": "semantic", "expect": "undeclared identifier diagnostic"},
        {"id": "ERR-LINK", "file": "err_link.c", "language": "c",
         "kind": "link", "expect": "undefined reference at link step"},
        {"id": "ERR-RUNTIME", "file": "err_runtime.py", "language": "python",
         "kind": "runtime", "expect": "ZeroDivisionError termination, exit 1"},
    ],
}
out = FIXTURES / "demos" / "manifest.json"
out.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
print("demos:", len(demos))
print("groups:", {g: sum(1 for d in demos if d["group"] == g) for g in "ABC"})
print("written:", out)
