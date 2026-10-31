#!/bin/sh
# M0 dev helper: measure Vite HMR detection latency on the authoritative /mnt/e repo.
# Usage: watch_probe.sh <vite-log> <file-to-touch>
LOG="$1"
FILE="$2"
grep -q "hmr update" "$LOG" 2>/dev/null && echo "note: log already contains hmr events"
S=$(date +%s)
i=0
while [ $i -lt 60 ]; do
    if grep -q "hmr update" "$LOG" 2>/dev/null; then
        break
    fi
    sleep 0.25
    i=$((i + 1))
done
E=$(date +%s)
grep "hmr update" "$LOG" | tail -1
echo "HMR_DETECTED_WITHIN_MS=$(( (E - S) * 1000 )) (poll granularity 250ms)"
