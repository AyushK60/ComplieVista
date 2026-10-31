#!/bin/sh
set -e
JOB=/home/khana/.cache/compilevista/jobs/m4cbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/build"
printf '#include <stdio.h>\nint main(void) { return 0; }\n' > "$JOB/src/m.c"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/build:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/c_build_worker.py --file m.c --out /out
echo "EXIT=$?"
ls "$JOB/build"
