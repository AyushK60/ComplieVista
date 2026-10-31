# M4 execution build worker additions: the analyzer image gains the C trace shim
# and a build worker so untrusted C can be compiled with -finstrument-functions.
# Runtime image (separate privilege domain) executes the produced binary.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      clang-18 llvm-18 binutils libc6-dev python3 \
 && rm -rf /var/lib/apt/lists/*

COPY worker_c.py worker_python.py c_build_worker.py /opt/analyzer/
COPY c_trace_shim.c /opt/analyzer/
# Non-root runtime user is applied via docker run --user (arbitrary UID works).
