# M2 pinned analyzer image (ADR-0005). Trusted, network-enabled BUILD; the built image
# then runs analyses with --network none, read-only rootfs, dropped capabilities.
FROM ubuntu:24.04

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      clang-18 llvm-18 binutils libc6-dev python3 \
 && rm -rf /var/lib/apt/lists/*

COPY worker_c.py worker_python.py /opt/analyzer/
# Non-root runtime user is applied via docker run --user (arbitrary UID works).
