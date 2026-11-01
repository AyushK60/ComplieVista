# CompileVista Demo Catalog — exactly 20 real programs (M7)

Generated from `sandbox/fixtures/demos/manifest.json` (hash-pinned; validator:
`backend/tests/test_m7_demos.py::test_g1_manifest_exactly_20_valid`).
Expected outputs verified with host toolchains (`scripts/dev/m7_verify_demos.sh`).
Error Microscope fixtures (4) are OUTSIDE the 20 count.

| ID | Group | Title | Difficulty | Expected stdout |
|---|---|---|---|---|
| PY-01 | A | Fundamentals: variables, expressions, functions, branching | introductory | `area=10 ⏎ scaled=7 ⏎ kind=valid` |
| PY-02 | A | Loops and collections: accumulator with filtering | introductory | `total=99 ⏎ evens=12,20,8 ⏎ count=3` |
| PY-03 | A | True recursion: frame growth and unwinding | intermediate | `fib12=144 ⏎ calls=465` |
| PY-04 | A | Closure, generator suspension, exception scope | intermediate | `counter=15,17 ⏎ pairs=0,4 ⏎ suspended=yes ⏎ caught=scope demo ⏎ finally=finally-ran` |
| PY-05 | A | Classes, imports, bounded concurrency | advanced | `acc=15 ⏎ threads=[{"double": 72, "input": 36, "sqrt": 6}, {"double": 20, "input": 10, "sqrt": 3}]` |
| C-01 | B | Expressions, functions, branching → LLVM IR | introductory | `r1=37 r2=2 r3=100` |
| C-02 | B | Preprocessor, conditional build, loop → CFG | intermediate | `acc=85` |
| C-03 | B | Pointers and arrays on the stack | intermediate | `first=9 last=4 sum=23` |
| C-04 | B | Structs and dynamic memory (malloc/free, correct path) | advanced | `total=66 last=ok` |
| C-05 | B | Multi-file C project: header + 2 translation units | advanced | `series=95 gcd=12` |
| PAIR-01-C | C | Addition and basic functions (C side) | very easy | `sum=299995` |
| PAIR-02-C | C | Classification branches (C side) | easy | `c0=16 c1=8 c2=4 c3=2` |
| PAIR-03-C | C | Bounded tree recursion (fib 20) (C side) | moderate | `fib20=6765` |
| PAIR-04-C | C | Array/list aggregation (C side) | advanced | `total=50010` |
| PAIR-05-C | C | Insertion sort with modulo checksum (C side) | challenging | `sorted=471613008` |
| PAIR-01-PY | C | Addition and basic functions (Python side) | very easy | `sum=299995` |
| PAIR-02-PY | C | Classification branches (Python side) | easy | `c0=16 c1=8 c2=4 c3=2` |
| PAIR-03-PY | C | Bounded tree recursion (fib 20) (Python side) | moderate | `fib20=6765` |
| PAIR-04-PY | C | Array/list aggregation (Python side) | advanced | `total=50010` |
| PAIR-05-PY | C | Insertion sort with modulo checksum (Python side) | challenging | `sorted=471613008` |

## Capability highlights

- **PY-01**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PY-02**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PY-03**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PY-04**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PY-05**: optimization — UNAVAILABLE; memory — AVAILABLE
- **C-01**: optimization — AVAILABLE; memory — PARTIAL
- **C-02**: optimization — AVAILABLE; memory — PARTIAL
- **C-03**: optimization — AVAILABLE; memory — PARTIAL
- **C-04**: optimization — AVAILABLE; memory — PARTIAL
- **C-05**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-01-C**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-02-C**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-03-C**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-04-C**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-05-C**: optimization — AVAILABLE; memory — PARTIAL
- **PAIR-01-PY**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PAIR-02-PY**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PAIR-03-PY**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PAIR-04-PY**: optimization — UNAVAILABLE; memory — AVAILABLE
- **PAIR-05-PY**: optimization — UNAVAILABLE; memory — AVAILABLE

## Guided story levels

### PY-01 — Fundamentals: variables, expressions, functions, branching
- **Simple:** A tiny program computes a triangle area twice and checks the result is valid.
- **Detailed:** Watch the recorded trace: `area` is called twice with different arguments, the branch inside it takes the same path both times, and each return value flows back to the module frame.
- **Technical:** Bytecode: CALL/RETURN under sys.settrace; locals snapshots show base/height per call. Python 3.12 bytecode is version-pinned; no LLVM IR exists here.
- **Limits:** Trace caps: 5000 events / 64 frames / 200 locals (not reached here).

### PY-02 — Loops and collections: accumulator with filtering
- **Simple:** One loop walks a list, sums everything, and collects the even numbers.
- **Detailed:** The line-event stream shows FOR_ITERATION jumps: the loop body runs 8 times and the branch appends only 3 values. Locals snapshots show the accumulator grow from call to call.
- **Technical:** Bytecode: FOR_ITER/COMPARE_OP/JUMP_ABSOLUTE pattern; list.append is a C builtin (no Python frame, hence no call events for it).
- **Limits:** Output list order is deterministic (insertion order).

### PY-03 — True recursion: frame growth and unwinding
- **Simple:** fib(12) calls itself 465 times; the trace shows the call stack grow and shrink.
- **Detailed:** The replay timeline shows depth increasing to 12 and unwinding; each frame has its own `n` (see locals). The 465 count includes both leaf and inner calls (2*F(13)-1).
- **Technical:** Tree recursion: calls(fib)=2*F(13)-1=465. Depth cap is 64 — this program peaks at 12, so the full tree is recorded.
- **Limits:** Do not confuse CALLS (465) with max depth (12).

### PY-04 — Closure, generator suspension, exception scope
- **Simple:** A closure keeps private state, a generator pauses twice, and an exception is caught with a finally block.
- **Detailed:** The generator's frame_id stays STABLE across suspensions (M5QA fix): a yield is a suspension, not a frame death. The manual next() consumes one value (pairs=0,4 — the 2 is skipped), demonstrating the iterator protocol vs the for-loop protocol. The closure's `count` survives between calls.
- **Technical:** Generator resumption re-fires 'call' events (CPython semantics); CO_GENERATOR frames are not popped at yield. Exception records name the instance; user __str__ is never evaluated by the tracer.
- **Limits:** Generator memory previews show identity, not contents of suspended frames.

### PY-05 — Classes, imports, bounded concurrency
- **Simple:** Two threads compute results into preassigned slots; a small class accumulates a total.
- **Detailed:** join() makes the outcome deterministic because each thread writes its OWN slot — the output does not depend on scheduling. The recorded trace shows only the main thread (sys.settrace is per-thread) — an honest limitation.
- **Technical:** Worker threads are NOT traced (settrace is thread-local); results are index-addressed to avoid order dependence. GIL interleaving is not observed and not claimed.
- **Limits:** Thread interleaving is unobservable in the trace — scheduling limitations are declared, not hidden.

### C-01 — Expressions, functions, branching → LLVM IR
- **Simple:** Two small functions clamp and average values; the IR shows the unoptimized bodies.
- **Detailed:** At -O0 the IR loads/stores every local through the stack; OptimizationLab shows -O2 collapsing the arithmetic. The recorded trace shows call/return for clamp and weighted.
- **Technical:** Instrumented with -finstrument-functions (call/return events, no ptrace); clamp is inlined at -O2 (verify in OptimizationLab: the symbol disappears from the O2 build).
- **Limits:** Static assembly is not an executed-instruction count.

### C-02 — Preprocessor, conditional build, loop → CFG
- **Simple:** Macros and #if select the build path at COMPILE time; the loop's CFG has a header, body and exit block.
- **Detailed:** The preprocess stage shows SCALE(i) expanded to ((i) * 2); DEMO_MODE=2 makes the #else branch dead at compile time — the #else code is never compiled, which the IR/ASM absence shows.
- **Technical:** CFG: for-header → if → two successors → latch → exit. Basic-block inventory comes from real clang IR/ASM, not a generic diagram.
- **Limits:** #if pruning is a compile-time effect — the trace cannot show it at runtime.

### C-03 — Pointers and arrays on the stack
- **Simple:** swap() exchanges two array ends through pointers; a bounded slice sum walks the array.
- **Detailed:** The IR shows pointer dereferences as loads/stores; swap's effects are visible in the output (first/last exchanged). Pointer arithmetic stays in bounds — the demo never walks past the array.
- **Technical:** Array decay: sum_slice receives int* — same machine representation as &arr[0]. Address instability (ASLR) applies to any recorded addresses.
- **Limits:** Out-of-bounds arithmetic would be UB — this demo stays in bounds by design.

### C-04 — Structs and dynamic memory (malloc/free, correct path)
- **Simple:** Three struct records are allocated on the heap, filled, summed and freed — correctly.
- **Detailed:** The allocator interposition records the malloc(3*sizeof(record_t)) with its real size and the matching free: outstanding returns to zero. NULL is checked before use (no UB on OOM).
- **Technical:** sizeof(record_t) includes tail padding for the char[8] tag — check the interposed size (3*24) rather than assuming field sums.
- **Limits:** Sanitizer availability varies; correct-path malloc/free here means NO diagnostics are expected — absence of findings is not proof of coverage.

### C-05 — Multi-file C project: header + 2 translation units
- **Simple:** One program in three files: a header declares, one TU implements, the main TU uses it. The LINKER connects them.
- **Detailed:** Both TUs are compiled separately (two compile steps in the build record), then linked. The linked binary's symbol table contains math_sum_series and math_gcd defined (T) — that is the cross-TU resolution evidence.
- **Technical:** Analysis covers the primary TU's stages; the LINK step evidence (symbols of the final binary) is what proves cross-TU linkage — static analysis of one TU never assumes the other executes independently.
- **Limits:** Multi-file linking is a curated-demo capability; pasted multi-file C still runs single-file only.

### PAIR-01-C — Addition and basic functions (C side)
- **Simple:** The C side of the PAIR-01 pair. Same sum computed in both languages; compare the C IR against Python bytecode.
- **Detailed:** Compare with the Python side via the Compare page: matched inputs, expected output 'sum=299995' verified with host toolchains.
- **Technical:** Concepts synchronize across languages — stages do NOT (IR vs bytecode). Trace call/return pairs come from the same instrumentation as M4.
- **Limits:** Paired with PAIR-01-PY; run both via the Compare page for the side-by-side view.

### PAIR-02-C — Classification branches (C side)
- **Simple:** The C side of the PAIR-02 pair. Same classification; C shows branch blocks in IR, Python shows COMPARE_OP/JUMP in bytecode.
- **Detailed:** Compare with the Python side via the Compare page: matched inputs, expected output 'c0=16 c1=8 c2=4 c3=2' verified with host toolchains.
- **Technical:** Concepts synchronize across languages — stages do NOT (IR vs bytecode). Trace call/return pairs come from the same instrumentation as M4.
- **Limits:** Paired with PAIR-02-PY; run both via the Compare page for the side-by-side view.

### PAIR-03-C — Bounded tree recursion (fib 20) (C side)
- **Simple:** The C side of the PAIR-03 pair. fib(20): C call/return via instrumentation; Python via settrace; frame depths are language-specific.
- **Detailed:** Compare with the Python side via the Compare page: matched inputs, expected output 'fib20=6765' verified with host toolchains.
- **Technical:** Concepts synchronize across languages — stages do NOT (IR vs bytecode). Trace call/return pairs come from the same instrumentation as M4.
- **Limits:** Paired with PAIR-03-PY; run both via the Compare page for the side-by-side view.

### PAIR-04-C — Array/list aggregation (C side)
- **Simple:** The C side of the PAIR-04 pair. Same aggregation over 1000 values; C uses a fixed array, Python a list comprehension — concept match, not stage match.
- **Detailed:** Compare with the Python side via the Compare page: matched inputs, expected output 'total=50010' verified with host toolchains.
- **Technical:** Concepts synchronize across languages — stages do NOT (IR vs bytecode). Trace call/return pairs come from the same instrumentation as M4.
- **Limits:** Paired with PAIR-04-PY; run both via the Compare page for the side-by-side view.

### PAIR-05-C — Insertion sort with modulo checksum (C side)
- **Simple:** The C side of the PAIR-05 pair. Same insertion sort; checksum uses % 1000000007 so C has NO signed overflow (UB) and Python big-int semantics stay in range.
- **Detailed:** Compare with the Python side via the Compare page: matched inputs, expected output 'sorted=471613008' verified with host toolchains.
- **Technical:** Concepts synchronize across languages — stages do NOT (IR vs bytecode). Trace call/return pairs come from the same instrumentation as M4.
- **Limits:** Paired with PAIR-05-PY; run both via the Compare page for the side-by-side view.

### PAIR-01-PY — Addition and basic functions (Python side)
- **Simple:** The Python side of the PAIR-01 pair. Same sum computed in both languages; compare the C IR against Python bytecode.
- **Detailed:** Expected output 'sum=299995' — identical to the C side by construction and verified against host toolchains.
- **Technical:** Group C demos use CPython 3.12 bytecode; specialization happens at runtime and is not part of static evidence.
- **Limits:** Paired with PAIR-01-C.

### PAIR-02-PY — Classification branches (Python side)
- **Simple:** The Python side of the PAIR-02 pair. Same classification; C shows branch blocks in IR, Python shows COMPARE_OP/JUMP in bytecode.
- **Detailed:** Expected output 'c0=16 c1=8 c2=4 c3=2' — identical to the C side by construction and verified against host toolchains.
- **Technical:** Group C demos use CPython 3.12 bytecode; specialization happens at runtime and is not part of static evidence.
- **Limits:** Paired with PAIR-02-C.

### PAIR-03-PY — Bounded tree recursion (fib 20) (Python side)
- **Simple:** The Python side of the PAIR-03 pair. fib(20): C call/return via instrumentation; Python via settrace; frame depths are language-specific.
- **Detailed:** Expected output 'fib20=6765' — identical to the C side by construction and verified against host toolchains.
- **Technical:** Group C demos use CPython 3.12 bytecode; specialization happens at runtime and is not part of static evidence.
- **Limits:** Paired with PAIR-03-C.

### PAIR-04-PY — Array/list aggregation (Python side)
- **Simple:** The Python side of the PAIR-04 pair. Same aggregation over 1000 values; C uses a fixed array, Python a list comprehension — concept match, not stage match.
- **Detailed:** Expected output 'total=50010' — identical to the C side by construction and verified against host toolchains.
- **Technical:** Group C demos use CPython 3.12 bytecode; specialization happens at runtime and is not part of static evidence.
- **Limits:** Paired with PAIR-04-C.

### PAIR-05-PY — Insertion sort with modulo checksum (Python side)
- **Simple:** The Python side of the PAIR-05 pair. Same insertion sort; checksum uses % 1000000007 so C has NO signed overflow (UB) and Python big-int semantics stay in range.
- **Detailed:** Expected output 'sorted=471613008' — identical to the C side by construction and verified against host toolchains.
- **Technical:** Group C demos use CPython 3.12 bytecode; specialization happens at runtime and is not part of static evidence.
- **Limits:** Paired with PAIR-05-C.
