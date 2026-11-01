#!/bin/bash
# M6/M7: independently verify pair expected outputs with the HOST toolchain.
# Reproducibility oracle documented in docs/TEST_EVIDENCE/M6.md and M7.md.
set -e
cd /mnt/e/ComplieVista/sandbox/fixtures/pairs
for f in add conditional recursion arraysum sort; do
  clang-18 -O2 -o "/tmp/m6_$f" "$f.c"
  echo "$f C: $(/tmp/m6_$f)"
  echo "$f PY: $(python3 "$f.py")"
done
