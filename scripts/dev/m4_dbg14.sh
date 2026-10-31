#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4cdbg2
echo "--- in analyzer container:"
docker run --rm --network none --cap-drop ALL --user 1000:1000 \
  -v "$JOB/bin:/app:ro" -e CV_TRACE_OUT=/tmp/t.jsonl \
  compilevista/analyzer:m2 /app/app; echo "EXIT=$?"
echo "--- gdb backtrace in analyzer container:"
docker run --rm --network none --cap-drop ALL --user 1000:1000 \
  -v "$JOB/bin:/app:ro" -e CV_TRACE_OUT=/tmp/t.jsonl \
  compilevista/analyzer:m2 sh -c "gdb -batch -ex run -ex bt /app/app 2>&1 | tail -12 || echo GDB-UNAVAILABLE"
