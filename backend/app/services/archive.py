"""Stage 1-B safe archive extraction (shared by ZIP upload and GitHub tarballs).

Everything is validated in memory; nothing is extracted to disk here. Every
rejected entry is recorded with a machine-readable reason. Security rules:
 - reject absolute paths, '..' traversal, drive prefixes, backslash names,
   NUL/control characters, over-deep paths
 - reject non-regular entries (symlink/hardlink/device) and encrypted entries
 - reject nested archives and known executable/binary payloads (plus NUL sniff)
 - reject case/Unicode-normalization collisions
 - enforce file count, per-file size, total expanded size and compression-ratio caps
"""
from __future__ import annotations

import io
import tarfile
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from app.core.config import LIMITS

_REJECT_SUFFIXES = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".com", ".msi", ".apk",
    ".pyc", ".pyo", ".class", ".jar", ".o", ".a", ".out",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".zst",
}


class ArchiveError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ExtractionResult:
    files: dict[str, bytes] = field(default_factory=dict)
    rejected: list[dict] = field(default_factory=list)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def _reject(result: ExtractionResult, entry: str, code: str, detail: str = "") -> None:
    result.rejected.append({"entry": entry[:300], "reason_code": code, "detail": detail[:200]})


def _clean_name(raw: str, result: ExtractionResult, limits: dict) -> str | None:
    """Return a safe normalized posix relative path, or None if rejected (recorded)."""
    name = raw
    if "\x00" in name or any(ord(c) < 32 and c not in "\t" for c in name):
        _reject(result, raw, "PATH_CONTROL_CHARS")
        return None
    if "\\" in name:
        _reject(result, raw, "PATH_BACKSLASH")
        return None
    if name.startswith("/") or PurePosixPath(name).is_absolute():
        _reject(result, raw, "PATH_ABSOLUTE")
        return None
    if len(name) > 2 and name[1] == ":":
        _reject(result, raw, "PATH_DRIVE_PREFIX")
        return None
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        _reject(result, raw, "PATH_TRAVERSAL")
        return None
    if not parts:
        return None  # directory-only entry
    if len(parts) > limits["snapshot_max_depth"]:
        _reject(result, raw, "PATH_TOO_DEEP", f"depth {len(parts)}")
        return None
    return "/".join(parts)


def _validate_payload(name: str, data: bytes, result: ExtractionResult, limits,
                      seen_norm: dict[str, str], files: dict[str, bytes]) -> None:
    suffix = Path(name).suffix.lower()
    if suffix in _REJECT_SUFFIXES:
        _reject(result, name, "ARCHIVE_OR_BINARY_SUFFIX")
        return
    if b"\x00" in data[:8192]:
        _reject(result, name, "BINARY_NOT_SOURCE")
        return
    norm = unicodedata.normalize("NFC", name).casefold()
    if norm in seen_norm:
        _reject(result, name, "COLLISION", f"collides with {seen_norm[norm]!r}")
        return
    if len(files) >= limits["snapshot_max_files"]:
        raise ArchiveError("TOO_MANY_FILES", f"more than {limits['snapshot_max_files']} files")
    seen_norm[norm] = name
    files[name] = data


def extract_zip(data: bytes, limits: dict | None = None) -> ExtractionResult:
    limits = {**LIMITS, **(limits or {})}
    result = ExtractionResult()
    if len(data) > limits["zip_max_compressed_bytes"]:
        raise ArchiveError("ARCHIVE_TOO_LARGE",
                           f"compressed archive exceeds {limits['zip_max_compressed_bytes']} bytes")
    files: dict[str, bytes] = {}
    seen_norm: dict[str, str] = {}
    total_expanded = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            expanded_nominal = sum(i.file_size for i in infos)
            if (limits["zip_max_ratio"] and len(data) > 0
                    and expanded_nominal / max(len(data), 1) > limits["zip_max_ratio"]):
                raise ArchiveError("BOMB_RATIO",
                                   f"expansion ratio {expanded_nominal // max(len(data), 1)} exceeds cap")
            if expanded_nominal > limits["zip_max_expanded_bytes"]:
                raise ArchiveError("EXPANSION_CAP", "total expanded size exceeds cap")
            for info in infos:
                mode = info.external_attr >> 16
                fmt = mode & 0o170000
                if fmt not in (0, 0o100000):  # 0 = attr absent (common); regular = 100000
                    _reject(result, info.filename, "NON_REGULAR_ENTRY", oct(fmt))
                    continue
                if info.flag_bits & 0x1:
                    _reject(result, info.filename, "ENCRYPTED_ENTRY")
                    continue
                name = _clean_name(info.filename, result, limits)
                if name is None:
                    continue
                if info.file_size > limits["file_max_bytes"]:
                    _reject(result, name, "OVERSIZE_FILE", str(info.file_size))
                    continue
                payload = zf.read(info)
                total_expanded += len(payload)
                if total_expanded > limits["zip_max_expanded_bytes"]:
                    raise ArchiveError("EXPANSION_CAP", "total expanded size exceeds cap")
                _validate_payload(name, payload, result, limits, seen_norm, files)
    except zipfile.BadZipFile as e:
        raise ArchiveError("MALFORMED_ARCHIVE", f"bad zip: {e}") from e
    result.files = files
    return result


def extract_tar_gz(data: bytes, limits: dict | None = None,
                   strip_common_prefix: bool = True) -> ExtractionResult:
    limits = {**LIMITS, **(limits or {})}
    result = ExtractionResult()
    if len(data) > limits["github_archive_max_compressed_bytes"]:
        raise ArchiveError("ARCHIVE_TOO_LARGE",
                           f"archive exceeds {limits['github_archive_max_compressed_bytes']} bytes")
    files: dict[str, bytes] = {}
    seen_norm: dict[str, str] = {}
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = [m for m in tf.getmembers()
                       if m.isfile() or m.issym() or m.islnk() or m.isdev()]
            # GitHub tarballs wrap everything in "<repo>-<sha>/"; strip when uniform.
            prefix = None
            if strip_common_prefix and members:
                firsts = {m.name.split("/", 1)[0] for m in members}
                if len(firsts) == 1:
                    prefix = f"{next(iter(firsts))}/"
            for m in members:
                name = m.name[len(prefix):] if prefix and m.name.startswith(prefix) else m.name
                if m.issym() or m.islnk() or m.isdev():
                    _reject(result, name, "NON_REGULAR_ENTRY")
                    continue
                safe = _clean_name(name, result, limits)
                if safe is None:
                    continue
                if m.size > limits["file_max_bytes"]:
                    _reject(result, safe, "OVERSIZE_FILE", str(m.size))
                    continue
                fobj = tf.extractfile(m)
                payload = fobj.read() if fobj else b""
                total += len(payload)
                if total > limits["zip_max_expanded_bytes"]:
                    raise ArchiveError("EXPANSION_CAP", "total expanded size exceeds cap")
                _validate_payload(safe, payload, result, limits, seen_norm, files)
    except tarfile.TarError as e:
        raise ArchiveError("MALFORMED_ARCHIVE", f"bad tar.gz: {e}") from e
    result.files = files
    return result
