# Stage 5-B curated debug profile: analyzer toolchain + gdb, used ONLY for curated
# allowlisted fixtures (ADR-0008). gdb needs no capability expansion inside the
# restricted profile (verified: it traces its own child under cap-drop ALL,
# no-new-privileges, non-root). This image is NEVER used for pasted/untrusted code.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      clang-18 llvm-18 binutils libc6-dev python3 gdb \
 && rm -rf /var/lib/apt/lists/*

COPY c_build_worker.py c_debug_worker.py /opt/debug/
COPY c_trace_shim.c /opt/debug/
