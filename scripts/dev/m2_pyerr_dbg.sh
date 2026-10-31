#!/bin/sh
set -e
JOB=/home/khana/.cache/compilevista/jobs/m2pyerr
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/out"
printf 'def broken(:\n    pass\n' > "$JOB/src/broken.py"
set +e
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 1000:1000 -v "$JOB/src:/work:ro" -v "$JOB/out:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/worker_python.py --file broken.py --out /out
echo "CONTAINER_EXIT=$?"
ls "$JOB/out"
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path("/home/khana/.cache/compilevista/jobs/m2pyerr/out/manifest.json")
if p.is_file():
    m = json.loads(p.read_text())
    for s in m["stages"]:
        print(s["stage"], s.get("exit_code"), s.get("counts"))
else:
    print("NO MANIFEST")
EOF
