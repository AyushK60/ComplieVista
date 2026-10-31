#!/bin/sh
set -e
JOB=/home/khana/.cache/compilevista/jobs/m4dbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/run"
printf 'print(1+1)\n' > "$JOB/src/t.py"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 python3 /opt/runtime/py_trace_harness.py --file t.py --out /out
echo "EXIT=$?"
head -3 "$JOB/run/trace.jsonl"
