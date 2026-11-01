#!/bin/bash
# M7: compute expected outputs for all demo fixtures with the HOST toolchain
# (independent oracle). C compiled with the recorded worker flags.
set -e
D=/mnt/e/ComplieVista/sandbox/fixtures/demos
E=/mnt/e/ComplieVista/sandbox/fixtures/errors
for f in PY-01 PY-02 PY-03 PY-04 PY-05; do
  echo "== $f"; python3 "$D/$f.py"
done
for f in C-01 C-02 C-03 C-04; do
  clang-18 -O0 -o "/tmp/m7_$f" "$D/$f.c"
  echo "== $f"; "/tmp/m7_$f"
done
# C-05: two TUs + header, linked (independent host oracle of the link step)
clang-18 -O0 -o /tmp/m7_C05 "$D/C-05/main.c" "$D/C-05/math_utils.c" -I"$D"
echo "== C-05"; /tmp/m7_C05
echo "== err_runtime (expected nonzero)"; python3 "$E/err_runtime.py" || echo "rc=$?"
nm /tmp/m7_C05 | grep -c " T " || true
