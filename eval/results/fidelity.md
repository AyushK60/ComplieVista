# Artifact fidelity study

Ubuntu clang version 18.1.3 (1ubuntu1) · CPython 3.12.3 · 19 programs · **0 mismatching metrics/errors**

| program | lang | metric | app | oracle | match |
|---|---|---|---|---|---|
| C-01 | c | tokens | 3074 | 3074 | yes |
| C-01 | c | ir_o0_functions | 3 | 3 | yes |
| C-01 | c | ir_o2_functions | 1 | 1 | yes |
| C-01 | c | assembly_lines | 555 | 555 | yes |
| C-02 | c | tokens | 3018 | 3018 | yes |
| C-02 | c | ir_o0_functions | 1 | 1 | yes |
| C-02 | c | ir_o2_functions | 1 | 1 | yes |
| C-02 | c | assembly_lines | 358 | 358 | yes |
| C-03 | c | tokens | 3113 | 3113 | yes |
| C-03 | c | ir_o0_functions | 3 | 3 | yes |
| C-03 | c | ir_o2_functions | 1 | 1 | yes |
| C-03 | c | assembly_lines | 658 | 658 | yes |
| C-04 | c | tokens | 8000 | 8000 | yes |
| C-04 | c | ir_o0_functions | 1 | 1 | yes |
| C-04 | c | ir_o2_functions | 1 | 1 | yes |
| C-04 | c | assembly_lines | 588 | 588 | yes |
| PY-01 | python | tokens | 125 | 125 | yes |
| PY-01 | python | ast_nodes | 117 | 117 | yes |
| PY-01 | python | bytecode_instructions | 87 | 87 | yes |
| PY-01 | python | code_objects | 2 | 2 | yes |
| PY-02 | python | tokens | 166 | 166 | yes |
| PY-02 | python | ast_nodes | 141 | 141 | yes |
| PY-02 | python | bytecode_instructions | 117 | 117 | yes |
| PY-02 | python | code_objects | 3 | 3 | yes |
| PY-03 | python | tokens | 93 | 93 | yes |
| PY-03 | python | ast_nodes | 79 | 79 | yes |
| PY-03 | python | bytecode_instructions | 63 | 63 | yes |
| PY-03 | python | code_objects | 2 | 2 | yes |
| PY-04 | python | tokens | 263 | 263 | yes |
| PY-04 | python | ast_nodes | 213 | 213 | yes |
| PY-04 | python | bytecode_instructions | 223 | 223 | yes |
| PY-04 | python | code_objects | 5 | 5 | yes |
| PY-05 | python | tokens | 237 | 237 | yes |
| PY-05 | python | ast_nodes | 183 | 183 | yes |
| PY-05 | python | bytecode_instructions | 179 | 179 | yes |
| PY-05 | python | code_objects | 5 | 5 | yes |
| pair-add.c | c | tokens | 2997 | 2997 | yes |
| pair-add.c | c | ir_o0_functions | 1 | 1 | yes |
| pair-add.c | c | ir_o2_functions | 1 | 1 | yes |
| pair-add.c | c | assembly_lines | 334 | 334 | yes |
| pair-add.py | python | tokens | 56 | 56 | yes |
| pair-add.py | python | ast_nodes | 44 | 44 | yes |
| pair-add.py | python | bytecode_instructions | 41 | 41 | yes |
| pair-add.py | python | code_objects | 2 | 2 | yes |
| pair-arraysum.c | c | tokens | 3029 | 3029 | yes |
| pair-arraysum.c | c | ir_o0_functions | 1 | 1 | yes |
| pair-arraysum.c | c | ir_o2_functions | 1 | 1 | yes |
| pair-arraysum.c | c | assembly_lines | 401 | 401 | yes |
| pair-arraysum.py | python | tokens | 70 | 70 | yes |
| pair-arraysum.py | python | ast_nodes | 58 | 58 | yes |
| pair-arraysum.py | python | bytecode_instructions | 62 | 62 | yes |
| pair-arraysum.py | python | code_objects | 2 | 2 | yes |
| pair-conditional.c | c | tokens | 3074 | 3074 | yes |
| pair-conditional.c | c | ir_o0_functions | 2 | 2 | yes |
| pair-conditional.c | c | ir_o2_functions | 1 | 1 | yes |
| pair-conditional.c | c | assembly_lines | 485 | 485 | yes |
| pair-conditional.py | python | tokens | 144 | 144 | yes |
| pair-conditional.py | python | ast_nodes | 114 | 114 | yes |
| pair-conditional.py | python | bytecode_instructions | 92 | 92 | yes |
| pair-conditional.py | python | code_objects | 3 | 3 | yes |
| pair-recursion.c | c | tokens | 3006 | 3006 | yes |
| pair-recursion.c | c | ir_o0_functions | 2 | 2 | yes |
| pair-recursion.c | c | ir_o2_functions | 2 | 2 | yes |
| pair-recursion.c | c | assembly_lines | 375 | 375 | yes |
| pair-recursion.py | python | tokens | 74 | 74 | yes |
| pair-recursion.py | python | ast_nodes | 57 | 57 | yes |
| pair-recursion.py | python | bytecode_instructions | 49 | 49 | yes |
| pair-recursion.py | python | code_objects | 3 | 3 | yes |
| pair-sort.c | c | tokens | 3110 | 3110 | yes |
| pair-sort.c | c | ir_o0_functions | 1 | 1 | yes |
| pair-sort.c | c | ir_o2_functions | 1 | 1 | yes |
| pair-sort.c | c | assembly_lines | 535 | 535 | yes |
| pair-sort.py | python | tokens | 146 | 146 | yes |
| pair-sort.py | python | ast_nodes | 146 | 146 | yes |
| pair-sort.py | python | bytecode_instructions | 124 | 124 | yes |
| pair-sort.py | python | code_objects | 2 | 2 | yes |

Notes: C-04: tokens capped at 8000 by design (clang emitted 9169)

Skipped: C-05 (multi-file program; not covered by this single-file study)
