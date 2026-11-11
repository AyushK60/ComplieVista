"""Stage 0 Deliverable D - Windows/WSL source-staging bridge (ADR-0001).

Copies a source tree ONCE into an immutable, hashed per-job directory under
Linux-native storage (~/.cache/compilevista/jobs/<job-id>/src), records a
SHA-256 manifest atomically, and cleans up. Never executes or imports source during
static file discovery; never interpolates untrusted filenames into shell strings.

Run inside WSL Ubuntu. Paths of the authoritative repo arrive as /mnt/e/...
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

# Linux-native staging area; follows the current user's home so a fresh clone works
# on any machine. Override with COMPILEVISTA_JOBS_ROOT.
DEFAULT_JOBS_ROOT = Path.home() / ".cache" / "compilevista" / "jobs"
MAX_FILE_BYTES = 2 * 1024 * 1024       # per-file cap (Stage 0 fixtures are tiny)
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_FILES = 2000

_DRIVE_RE = re.compile(r"^[A-Za-z]:", re.ASCII)


class StagingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def jobs_root() -> Path:
    root = os.environ.get("COMPILEVISTA_JOBS_ROOT")
    return Path(root) if root else DEFAULT_JOBS_ROOT


def windows_to_wsl_path(win_path: str) -> Path:
    """Map 'E:\\dir\\file' -> '/mnt/e/dir/file'. Explicit, tested, no shell out."""
    s = win_path.strip()
    m = _DRIVE_RE.match(s)
    if not m:
        raise StagingError("INVALID_PATH", f"not an absolute Windows drive path: {s!r}")
    if s[2:3] not in ("/", "\\"):
        raise StagingError("INVALID_PATH", f"drive-relative path rejected: {s!r}")
    drive = m.group(0)[0].lower()
    rest = s[2:].replace("\\", "/").lstrip("/")
    if not rest:
        raise StagingError("INVALID_PATH", "bare drive without a path segment")
    return Path(f"/mnt/{drive}") / rest


def validate_relative_path(rel: str) -> PurePosixPath:
    """Reject traversal/absolute/odd paths BEFORE any filesystem use."""
    if "\x00" in rel:
        raise StagingError("INVALID_PATH", "NUL byte in path")
    if "\\" in rel:
        raise StagingError("INVALID_PATH", f"backslash in relative path: {rel!r}")
    p = PurePosixPath(rel)
    if p.is_absolute() or rel.startswith("/"):
        raise StagingError("INVALID_PATH", f"absolute path rejected: {rel!r}")
    if _DRIVE_RE.match(rel):
        raise StagingError("INVALID_PATH", f"drive-letter path rejected: {rel!r}")
    if rel.startswith("./") or "/./" in rel or rel.endswith("/."):
        raise StagingError("INVALID_PATH", f"dot-segment path rejected: {rel!r}")
    parts = p.parts
    if not parts:
        raise StagingError("INVALID_PATH", "empty path")
    if any(part in ("..", ".") for part in parts):
        raise StagingError("INVALID_PATH", f"path traversal rejected: {rel!r}")
    return p


def _sha256_file(p: Path, buf_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(buf_size):
            h.update(chunk)
    return h.hexdigest()


def snapshot_tree(source_dir: Path, job_id: str, dest_root: Path | None = None,
                  max_file_bytes: int = MAX_FILE_BYTES,
                  max_total_bytes: int = MAX_TOTAL_BYTES,
                  max_files: int = MAX_FILES) -> dict:
    """Copy regular files from source_dir into jobs/<job_id>/src and hash them.

    Atomic: files are staged into a temp dir, then renamed into place; the manifest
    is written via temp + rename. Returns manifest dict with timings. Symlinks,
    devices and anything non-regular are rejected (no silent following).
    """
    if not job_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        raise StagingError("INVALID_JOB_ID", f"job id rejected: {job_id!r}")
    src_root = Path(source_dir)
    if not src_root.is_dir():
        raise StagingError("SOURCE_NOT_FOUND", f"source dir missing: {src_root}")
    root = (dest_root or jobs_root()) / job_id
    if root.exists():
        raise StagingError("JOB_EXISTS", f"job id already staged: {job_id}")
    root.mkdir(parents=True)
    tmp_root = root.with_name(root.name + ".tmp")
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_src = tmp_root / "src"
    tmp_src.mkdir(parents=True)

    t0 = time.perf_counter()
    files: list[dict] = []
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(src_root):
            # Never follow symlinked directories.
            dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
            for name in sorted(filenames):
                rel = os.path.relpath(os.path.join(dirpath, name), src_root)
                rel_posix = PurePosixPath(Path(rel).as_posix())
                validate_relative_path(rel_posix.as_posix())
                f = Path(dirpath) / name
                if f.is_symlink() or not f.is_file():
                    raise StagingError("NON_REGULAR_FILE", f"non-regular file rejected: {rel!r}")
                size = f.stat().st_size
                if size > max_file_bytes:
                    raise StagingError("FILE_TOO_LARGE", f"{rel!r} exceeds per-file cap")
                total += size
                if total > max_total_bytes:
                    raise StagingError("TOTAL_TOO_LARGE", "total size cap exceeded")
                if len(files) >= max_files:
                    raise StagingError("TOO_MANY_FILES", "file count cap exceeded")
                dst = tmp_src / rel_posix
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                files.append({"path": rel_posix.as_posix(), "sha256": _sha256_file(dst),
                              "bytes": size})
        combined = hashlib.sha256(
            "\n".join(f"{rec['sha256']}  {rec['path']}" for rec in sorted(files, key=lambda r: r["path"])).encode()
        ).hexdigest()
        manifest = {
            "job_id": job_id,
            "source_dir_wsl": str(src_root),
            "staged_dir": str(root / "src"),
            "file_count": len(files),
            "total_bytes": total,
            "files": files,
            "combined_sha256": combined,
            "copy_duration_ms": int((time.perf_counter() - t0) * 1000),
        }
        # Atomic manifest write inside the tmp tree, then rename the whole tree in.
        mpath = tmp_root / "manifest.json"
        with tempfile.NamedTemporaryFile("w", dir=tmp_root, delete=False) as tf:
            tf.write(json.dumps(manifest, indent=1))
            tmp_name = tf.name
        os.replace(tmp_name, mpath)
        os.rename(tmp_root, root)  # atomic publish
        return manifest
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)
        raise


def load_job_manifest(job_id: str, dest_root: Path | None = None) -> dict:
    p = (dest_root or jobs_root()) / job_id / "manifest.json"
    if not p.is_file():
        raise StagingError("JOB_NOT_FOUND", f"no staged job: {job_id}")
    return json.loads(p.read_text())


def cleanup_job(job_id: str, dest_root: Path | None = None) -> bool:
    root = (dest_root or jobs_root()) / job_id
    if root.exists():
        shutil.rmtree(root)
        return True
    return False


def remove_disposable_dir(job_dir: Path, fallback_image: str) -> None:
    """Remove a disposable per-job directory after a container used it.

    Robust against two observed failure modes (Stage 4 review):
      1. EBUSY/race right after `docker run --rm` exits while the daemon is still
         tearing down the bind mount - retried briefly.
      2. Docker Desktop chowning container-written dirs to root - fall back to a
         one-off privileged container bounded to the jobs parent (trusted
         orchestration only; fixed argv, internally generated paths).
    A failed fallback is reported loudly instead of disappearing silently
    (Stage 4-era leftovers proved the silent failure).
    """
    for _ in range(4):
        shutil.rmtree(job_dir, ignore_errors=True)
        if not job_dir.exists():
            return
        time.sleep(0.25)
    jobs_parent = job_dir.parent.parent  # .../compilevista
    r = subprocess.run(
        ["docker", "run", "--rm", "--user", "0",
         "-v", f"{jobs_parent}:/jobs",
         fallback_image, "rm", "-rf", f"/jobs/{job_dir.parent.name}/{job_dir.name}"],
        capture_output=True, timeout=120)
    if r.returncode != 0 and job_dir.exists():
        print(f"[compilevista] WARNING: job-dir cleanup failed for {job_dir}: "
              f"{r.stderr.decode('utf-8', 'replace')[:200]}", file=sys.stderr)
