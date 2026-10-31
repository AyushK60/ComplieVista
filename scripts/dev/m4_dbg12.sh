#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4cdbg2
# 1) without trace env
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/bin:/app:ro" compilevista/runtime:m4 /app/app
echo "NO-TRACE-EXIT=$?"
# 2) build without instrumentation to isolate
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=16m --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/build:/out" \
  compilevista/analyzer:m2 sh -c "clang-18 -g -O0 -o /out/plain m.c && echo BUILT"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/build:/app2:ro" compilevista/runtime:m4 /app2/plain
echo "PLAIN-EXIT=$?"
# 3) instrumented WITHOUT the shim object (link error expected) - skip
# 4) instrumented + shim, trace to /dev/stdout
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/dev/stdout -v "$JOB/bin:/app:ro" \
  compilevista/runtime:m4 /app/app 2>&1 | head -4
echo "STDOUT-TRACE-EXIT=$?"
