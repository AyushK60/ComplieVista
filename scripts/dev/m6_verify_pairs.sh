#!/bin/bash
# M6: independently verify pair expected outputs with the host toolchain.
set -e
cd /mnt/e/ComplieVista/sandbox/fixtures/pairs
for f in add conditional recursion arraysum sort; do
  clang-18 -O2 -o "/tmp/m6_$f" "$f.c"
  echo "$f C: $(/tmp/m6_$f)"
  echo "$f PY: $(python3 "$f.py")"
done
