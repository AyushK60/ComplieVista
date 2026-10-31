#!/bin/sh
# M2 smoke: restricted container run of the Python analyzer worker.
set -e
JOB=/home/khana/.cache/compilevista/jobs/m2smokepy
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/out"
printf 'def f(n):\n    if n<2: return n\n    return f(n-1)+f(n-2)\nprint(f(10))\n' > "$JOB/src/rec.py"
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m --cap-drop ALL \
  --security-opt no-new-privileges --user 1000:1000 --memory 512m --cpus 1 --pids-limit 128 \
  -v "$JOB/src:/work:ro" -v "$JOB/out:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/worker_python.py --file rec.py --out /out
python3 - <<'EOF'
import json
m = json.load(open("/home/khana/.cache/compilevista/jobs/m2smokepy/out/manifest.json"))
for s in m["stages"]:
    print(s["stage"], s["counts"])
EOF
