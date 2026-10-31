"""M1-B ingestion: paste / uploaded files / archives → projects, snapshots, targets.

Classification uses bounded static parsing only (ast.parse / lexical checks on
size-capped text). NOTHING is executed or imported here — adversarial fixtures
with top-level side effects are used in tests to prove that invariant.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.core.config import LIMITS
from app.services import archive as archive_mod
from app.services.classify import classify_files, classify_multi_file_hint
from app.store.db import Store, StoreError, new_id, now_utc


class IngestError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._ +-]{1,120}$")


def _check_paste_name(filename: str) -> str:
    if not _SAFE_FILENAME.match(filename):
        raise IngestError("INVALID_FILENAME", f"filename rejected: {filename!r}")
    return filename


def combined_hash(files: dict[str, bytes]) -> str:
    return hashlib.sha256(
        "\n".join(f"{hashlib.sha256(d).hexdigest()}  {p}" for p, d in sorted(files.items())).encode()
    ).hexdigest()


def _persist(store: Store, project_name: str, origin: str, files: dict[str, bytes],
             rejected: list[dict], import_id: str | None = None) -> dict:
    project_id = new_id()
    store.execute("INSERT INTO projects (id, name, created_utc) VALUES (?,?,?)",
                  (project_id, project_name[:200], now_utc()))
    snap_id, existed = store.insert_snapshot(project_id, origin, files, import_id)
    classify_files(store, snap_id, files)
    classify_multi_file_hint(store, snap_id, files)
    for d in rejected:
        store.execute(
            "INSERT INTO snapshot_diagnostics (id, snapshot_id, file_path, severity, code, detail)"
            " VALUES (?,?,?,?,?,?)",
            (new_id(), snap_id, d.get("entry", "")[:300], "info", d["reason_code"],
             d.get("detail", "")))
    return {"project_id": project_id, "snapshot_id": snap_id, "existed": existed,
            "file_count": len(files), "rejected": rejected[:100],
            "rejected_count": len(rejected)}


def ingest_paste(store: Store, language: str, filename: str, content: bytes) -> dict:
    if language not in ("python", "c"):
        raise IngestError("UNSUPPORTED_LANGUAGE", f"language {language!r} not supported for paste")
    _check_paste_name(filename)
    if not filename.lower().endswith((".py", ".c", ".h")):
        filename = filename + (".py" if language == "python" else ".c")
    if len(content) > LIMITS["paste_max_bytes"]:
        raise IngestError("PAYLOAD_TOO_LARGE",
                          f"paste exceeds {LIMITS['paste_max_bytes']} bytes")
    if b"\x00" in content[:8192]:
        raise IngestError("BINARY_CONTENT", "paste content is not text")
    files = {filename: content}
    return _persist(store, f"paste: {filename}", "paste", files, [])


def ingest_files(store: Store, uploads: list[tuple[str, bytes]]) -> dict:
    """Multipart upload of individual source files, or one bounded .zip."""
    if not uploads:
        raise IngestError("EMPTY_UPLOAD", "no files provided")
    if len(uploads) > LIMITS["upload_max_files"]:
        raise IngestError("TOO_MANY_FILES", f"more than {LIMITS['upload_max_files']} uploads")
    if len(uploads) == 1 and uploads[0][0].lower().endswith(".zip"):
        return ingest_zip(store, uploads[0][1])
    files: dict[str, bytes] = {}
    total = 0
    for name, data in uploads:
        _check_paste_name(Path(name).name)
        if Path(name).suffix.lower() not in (".c", ".h", ".py"):
            raise IngestError("UNSUPPORTED_FILE_TYPE", f"{name!r}: only .c/.h/.py files")
        if len(data) > LIMITS["file_max_bytes"]:
            raise IngestError("PAYLOAD_TOO_LARGE", f"{name} exceeds per-file cap")
        total += len(data)
        if total > LIMITS["snapshot_total_max_bytes"]:
            raise IngestError("PAYLOAD_TOO_LARGE", "total upload size exceeds cap")
        if name in files:
            raise IngestError("DUPLICATE_NAME", f"duplicate upload name {name!r}")
        files[name] = data
    return _persist(store, f"upload: {len(files)} file(s)", "upload", files, [])


def ingest_zip(store: Store, data: bytes) -> dict:
    result = archive_mod.extract_zip(data)
    if not result.files:
        raise IngestError("NO_ACCEPTABLE_FILES",
                          f"archive had no acceptable source files "
                          f"({result.rejected_count} entries rejected)")
    name_hint = "zip"
    return _persist(store, f"upload: {name_hint}", "zip", result.files, result.rejected)
