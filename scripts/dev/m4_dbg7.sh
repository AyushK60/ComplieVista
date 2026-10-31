#!/bin/sh
JOB=/home/khana/.cache/compilevista/jobs/m4bdbg
rm -rf "$JOB" && mkdir -p "$JOB/src"
printf '#include <stdio.h>\nint main(void){return 0;}\n' > "$JOB/src/m.c"
docker run --name cvbuildtest --network none --read-only --tmpfs /tmp:rw,size=16m --tmpfs "/out:rw,size=16m,uid=1000,gid=1000" --cap-drop ALL --security-opt no-new-privileges --user 1000:1000 --memory 256m --pids-limit 64 -v "$JOB/src:/work:ro" compilevista/analyzer:m2 python3 /opt/analyzer/c_build_worker.py --file m.c --out /out
echo "EXIT=$?"
docker cp cvbuildtest:/out/. "$JOB/build/" && echo CP_OK
docker rm -f cvbuildtest
ls "$JOB/build"
