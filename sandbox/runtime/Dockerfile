# M4 runtime image: executes binaries/harness produced by the analyzer container.
# Deliberately MINIMAL: no compiler, no shell tools beyond the base image, no network.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*

COPY py_trace_harness.py bench_worker.py /opt/runtime/
# Runs: --network none --read-only --cap-drop ALL --no-new-privileges --user 1000:1000
