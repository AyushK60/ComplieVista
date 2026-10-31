"""One-shot, cached tool availability probes for /api/v1/capabilities."""
from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

_PROBE_TIMEOUT_S = 15


def _first_line(argv: list[str]) -> str | None:
    exe = shutil.which(argv[0])
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, *argv[1:]], capture_output=True, timeout=_PROBE_TIMEOUT_S)
        line = out.stdout.decode("utf-8", "replace").splitlines()
        return line[0].strip() if line else None
    except (OSError, subprocess.TimeoutExpired):
        return None


@lru_cache(maxsize=1)
def probe_tools() -> dict:
    tools = {}
    for name, argv in {
        "clang": ["clang", "--version"],
        "llvm": ["clang", "--version"],
        "python": ["/usr/bin/python3", "--version"],
        "gdb": ["gdb", "--version"],
        "strace": ["strace", "--version"],
        "node": ["node", "--version"],
        "docker": ["docker", "--version"],
        "objdump": ["objdump", "--version"],
    }.items():
        ver = _first_line(argv)
        if name == "python" and ver and ver.startswith("Python "):
            ver = ver[len("Python "):]
        tools[name] = {"available": ver is not None, "version": ver or "unavailable"}
    return tools
