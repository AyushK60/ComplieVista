"""Stage 5 curated fixture registry (ADR-0008).

The debug profile (gdb) is admitted ONLY for snapshots whose combined content hash
matches an entry here. The allowlist is computed from the fixture files at import
time - no user input can add entries. Pasted/untrusted code always receives an
explicit debugger-unavailable state instead (see execution.py).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.store.db import combined_hash

_REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/app/services -> repo root
FIXTURES = _REPO_ROOT / "sandbox" / "fixtures"
CURATED_DIR = _REPO_ROOT / "sandbox" / "fixtures" / "curated"
MANIFEST_PATH = CURATED_DIR / "manifest.json"

_CACHE: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
        for entry in manifest["fixtures"]:
            data = (CURATED_DIR / entry["file"]).read_bytes()
            files = {entry["filename_in_snapshot"]: data}
            _CACHE[combined_hash(files)] = entry
    return _CACHE


def curated_entry(combined_sha256: str) -> dict | None:
    """Curated manifest entry for a snapshot hash, or None."""
    return _load().get(combined_sha256)
