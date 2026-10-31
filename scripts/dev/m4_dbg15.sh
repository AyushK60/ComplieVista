#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4cdbg2
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/dev/stdout -v "$JOB/bin:/app:ro" \
  compilevista/runtime:m4 /app/app
echo "TRUE-EXIT=$?"
