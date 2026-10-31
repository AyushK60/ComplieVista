#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4netdbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/run"
printf 'import socket\ntry:\n    socket.create_connection(("93.184.216.34", 80), timeout=2)\n    print("NETWORK-OK")\nexcept Exception as e:\n    print("NET-BLOCKED", type(e).__name__)\n' > "$JOB/src/net.py"
docker run --rm --network none --read-only --cap-drop ALL --user 1000:1000 \
  -v "$JOB/src:/work:ro" -v "$JOB/run:/out" \
  compilevista/runtime:m4 python3 /opt/runtime/py_trace_harness.py --file net.py --out /out
echo "EXIT=$?"
cat "$JOB/run/stdout.txt"
