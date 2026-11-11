#!/bin/bash
# Stage 6/Stage 7: independently verify pair expected outputs with the HOST toolchain.
# Reproducibility oracle documented in the stage 6 notes.
set -e
cd /mnt/e/ComplieVista/sandbox/fixtures/pairs
for f in add conditional recursion arraysum sort; do
  clang-18 -O2 -o "/tmp/m6_$f" "$f.c"
  echo "$f C: $(/tmp/m6_$f)"
  echo "$f PY: $(python3 "$f.py")"
done
