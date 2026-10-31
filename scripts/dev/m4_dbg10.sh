#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4cdbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/build" "$JOB/bin" "$JOB/run"
printf '#include <stdio.h>\nstatic int adjust(int b, int l){ return b > l ? l : b; }\nint main(void) { return adjust(4, 2); }\n' > "$JOB/src/m.c"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/build:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/c_build_worker.py --file m.c --out /out
docker cp $(docker create compilevista/analyzer:m2 true) 2>/dev/null || true
# extract binary from build dir
cp "$JOB/build/app.bin" "$JOB/bin/app" && chmod +x "$JOB/bin/app"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -e CV_TRACE_OUT=/out/trace.jsonl -v "$JOB/bin:/app:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 /app/app
echo "EXIT=$?"
head -5 "$JOB/run/trace.jsonl"
