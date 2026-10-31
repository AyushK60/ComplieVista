#!/bin/sh
# M2 smoke: one restricted container analyzer run over a tiny C fixture.
set -e
JOB=/home/khana/.cache/compilevista/jobs/m2smoke
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/out"
printf '#include <stdio.h>\n#define M 3\nint main(void){int a[2]={1,2};return a[0]*M;}\n' > "$JOB/src/demo.c"
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=64m --cap-drop ALL \
  --security-opt no-new-privileges --user 1000:1000 --memory 512m --cpus 1 --pids-limit 128 \
  -v "$JOB/src:/work:ro" -v "$JOB/out:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/worker_c.py --file demo.c --out /out
python3 - <<'EOF'
import json
m = json.load(open("/home/khana/.cache/compilevista/jobs/m2smoke/out/manifest.json"))
for s in m["stages"]:
    print(s["stage"], s.get("exit_code"), [a["file"] for a in s["artifacts"]])
print("clang:", m["tool_versions"]["clang"])
EOF
