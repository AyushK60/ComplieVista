#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4cdbg2
echo "--- A: no /out mount, trace to /tmp"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/tmp/trace.jsonl -v "$JOB/bin:/app:ro" \
  compilevista/runtime:m4 /app/app; echo "A-EXIT=$?"
echo "--- B: /out mount, trace to /tmp"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/tmp/trace.jsonl -v "$JOB/bin:/app:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 /app/app; echo "B-EXIT=$?"
echo "--- C: /out mount + trace file (crash case)"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/out/trace.jsonl -v "$JOB/bin:/app:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 /app/app; echo "C-EXIT=$?"
