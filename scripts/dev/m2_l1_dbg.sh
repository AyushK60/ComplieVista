#!/bin/sh
set -e
JOB=/home/khana/.cache/compilevista/jobs/m2l1dbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/out"
printf 'def caf\xc3\xa9():\n    return 1\n' > "$JOB/src/l1.py"
docker run --rm --network none --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/out:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/worker_python.py --file l1.py --out /out
echo "EXIT=$?"
ls "$JOB/out"
python3 - <<'EOF'
import pathlib
p = pathlib.Path("/home/khana/.cache/compilevista/jobs/m2l1dbg/out/manifest.json")
print("manifest exists:", p.is_file())
EOF
