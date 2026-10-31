#!/bin/sh
# Debug: compare container vs host token dumps for the same source.
set -e
JOB=/home/khana/.cache/compilevista/jobs/m2tokdbg
rm -rf "$JOB" && mkdir -p "$JOB/src" "$JOB/out"
cat > "$JOB/src/oracle.c" <<'EOF'
#include <stdio.h>
#define M0_SCALE 3
static int scale(int base, int limit) {
    int scaled = base * M0_SCALE;
    if (scaled > limit) { return limit; }
    return scaled;
}
int main(void) {
    int values[4] = {1, 2, 3, 4};
    int total = 0;
    for (int i = 0; i < 4; i++) { total += scale(values[i], 10); }
    printf("total=%d\n", total);
    return 0;
}
EOF
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 1000:1000 -v "$JOB/src:/work:ro" -v "$JOB/out:/out" \
  compilevista/analyzer:m2 python3 /opt/analyzer/worker_c.py --file oracle.c --out /out
clang -fsyntax-only -Xclang -dump-tokens "$JOB/src/oracle.c" 2> /tmp/host_dump.txt || true
python3 - <<'EOF'
cont = open("/home/khana/.cache/compilevista/jobs/m2tokdbg/out/tokens_stderr.txt").read()
host = open("/tmp/host_dump.txt").read()
import re
def locs(t):
    out = {}
    for l in t.splitlines():
        if "Loc=<" in l:
            m = re.search(r"Loc=<([^:>]+):", l)
            key = m.group(1).rsplit("/", 1)[-1] if m else "?"
            out[key] = out.get(key, 0) + 1
    return out
print("container total:", cont.count("Loc=<"), "| host total:", host.count("Loc=<"))
print("container per-file:", locs(cont))
print("host per-file:     ", locs(host))
EOF
