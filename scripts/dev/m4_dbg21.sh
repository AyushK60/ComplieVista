#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4simple
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/run"
printf 'print("HELLO")\n' > "$JOB/src/s.py"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 python3 /opt/runtime/py_trace_harness.py --file s.py --out /out
echo "EXIT=$?"
echo "stdout bytes: $(wc -c < $JOB/run/stdout.txt)"
cat "$JOB/run/stdout.txt"
