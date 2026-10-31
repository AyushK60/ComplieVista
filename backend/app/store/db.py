"""M1 metadata store: SQLite (stdlib sqlite3) + content-addressed artifact files.

ADR-0004: stdlib sqlite3 with an explicit schema_version table instead of
SQLAlchemy/Alembic for M1 — the schema is small, versioned and migrated by a
single guarded upgrade function; ORM/migrations are deferred to a later ADR if
the schema grows. Content-addressed artifact store keeps exact source bytes
immutable; the DB references digests, never host paths, toward the API/UI.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import DEFAULT_DATA_DIR, SCHEMA_VERSION

_LOCK = threading.Lock()


class StoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def file_id_for(rel_path: str) -> str:
    """Stable file identity within (and across identical) snapshots."""
    return hashlib.sha256(rel_path.encode("utf-8")).hexdigest()[:16]


_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, created_utc TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS imports (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, input_url TEXT NOT NULL,
        ref_requested TEXT, canonical_owner TEXT, canonical_repo TEXT, commit_sha TEXT,
        archive_sha256 TEXT, retrieval_utc TEXT, policy_version TEXT, status TEXT NOT NULL,
        error_code TEXT, file_count INTEGER, rejected_count INTEGER, created_utc TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS source_snapshots (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, origin TEXT NOT NULL,
        combined_sha256 TEXT NOT NULL, import_id TEXT, created_utc TEXT NOT NULL,
        UNIQUE (project_id, combined_sha256))""",
    """CREATE TABLE IF NOT EXISTS source_files (
        id TEXT NOT NULL, snapshot_id TEXT NOT NULL, rel_path TEXT NOT NULL,
        content_sha256 TEXT NOT NULL, size INTEGER NOT NULL, encoding TEXT NOT NULL,
        language TEXT NOT NULL, PRIMARY KEY (snapshot_id, id),
        UNIQUE (snapshot_id, rel_path))""",
    """CREATE TABLE IF NOT EXISTS compilation_targets (
        id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, kind TEXT NOT NULL,
        primary_file TEXT NOT NULL, status TEXT NOT NULL, reasons_json TEXT NOT NULL,
        created_utc TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS snapshot_diagnostics (
        id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, file_path TEXT NOT NULL,
        severity TEXT NOT NULL, code TEXT NOT NULL, detail TEXT NOT NULL)""",
    # --- m2.v1: analysis jobs ---
    """CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, target_id TEXT NOT NULL,
        language TEXT NOT NULL, primary_file TEXT NOT NULL, status TEXT NOT NULL,
        fingerprint TEXT NOT NULL, source_combined_sha256 TEXT NOT NULL,
        tool_fingerprint TEXT, image_id TEXT, error_code TEXT, cancel_requested INTEGER DEFAULT 0,
        created_utc TEXT NOT NULL, started_utc TEXT, finished_utc TEXT,
        duration_ms INTEGER)""",
    """CREATE TABLE IF NOT EXISTS analysis_stages (
        id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, stage TEXT NOT NULL,
        availability TEXT NOT NULL, observation_class TEXT NOT NULL, exit_code INTEGER,
        counts_json TEXT, items_json TEXT, limitations_json TEXT,
        raw_artifact TEXT, stderr_artifact TEXT, truncated INTEGER DEFAULT 0,
        duration_ms INTEGER, UNIQUE (analysis_id, stage))""",
]


class Store:
    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self.db_path = self.data_dir / "compilevista.db"
        self.artifacts = self.data_dir / "artifacts"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self) -> None:
        with _LOCK:
            for stmt in _SCHEMA:
                self._conn.execute(stmt)
            row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is None:
                self._conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
            elif row["value"] == "m1.v1" and SCHEMA_VERSION == "m2.v1":
                # Guarded additive upgrade: m2 only adds analyses tables (all IF NOT EXISTS).
                self._conn.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                                   (SCHEMA_VERSION,))
            elif row["value"] != SCHEMA_VERSION:
                raise StoreError("SCHEMA_MISMATCH",
                                 f"db schema {row['value']} != application schema {SCHEMA_VERSION}")
            self._conn.commit()

    # --- content-addressed artifacts -------------------------------------
    def put_artifact(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        sub = self.artifacts / sha[:2]
        sub.mkdir(parents=True, exist_ok=True)
        p = sub / sha
        if not p.exists():  # immutable: same digest => same bytes
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(p)  # atomic publish
        return sha

    def get_artifact(self, sha: str) -> bytes:
        p = self.artifacts / sha[:2] / sha
        if not p.is_file():
            raise StoreError("ARTIFACT_MISSING", f"artifact {sha[:12]} not found")
        return p.read_bytes()

    # --- generic helpers --------------------------------------------------
    def execute(self, stmt: str, params: tuple = ()) -> None:
        with _LOCK:
            self._conn.execute(stmt, params)
            self._conn.commit()

    def query(self, stmt: str, params: tuple = ()) -> list[sqlite3.Row]:
        with _LOCK:
            return self._conn.execute(stmt, params).fetchall()

    def query_one(self, stmt: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self.query(stmt, params)
        return rows[0] if rows else None

    def insert_snapshot(self, project_id: str, origin: str, files: dict[str, bytes],
                        import_id: str | None = None) -> tuple[str, bool]:
        """Create (or idempotently return) a snapshot. files: rel_path -> bytes."""
        if not files:
            raise StoreError("EMPTY_SNAPSHOT", "no acceptable source files")
        combined = hashlib.sha256(
            "\n".join(
                f"{hashlib.sha256(data).hexdigest()}  {path}"
                for path, data in sorted(files.items())
            ).encode()
        ).hexdigest()

        existing = self.query_one(
            "SELECT id FROM source_snapshots WHERE project_id=? AND combined_sha256=?",
            (project_id, combined))
        if existing:
            return existing["id"], True

        snap_id = new_id()
        self.execute(
            "INSERT INTO source_snapshots (id, project_id, origin, combined_sha256, import_id, created_utc)"
            " VALUES (?,?,?,?,?,?)",
            (snap_id, project_id, origin, combined, import_id, now_utc()))
        for rel_path, data in sorted(files.items()):
            sha = self.put_artifact(data)
            enc = detect_encoding(data)
            self.execute(
                "INSERT INTO source_files (id, snapshot_id, rel_path, content_sha256, size, encoding, language)"
                " VALUES (?,?,?,?,?,?,?)",
                (file_id_for(rel_path), snap_id, rel_path, sha, len(data), enc,
                 language_for(rel_path)))
        return snap_id, False

    def close(self) -> None:
        self._conn.close()


_TEXT_EXTENSIONS = {".c", ".h", ".py", ".json", ".toml", ".cfg", ".ini", ".md", ".txt",
                    ".yml", ".yaml", ".rst", ".cfg", ".gitignore", ".cmake", ".in"}
_LANGUAGE_MAP = {".c": "c", ".h": "c", ".py": "python"}


def language_for(rel_path: str) -> str:
    suffix = Path(rel_path).suffix.lower()
    return _LANGUAGE_MAP.get(suffix, "other")


def detect_encoding(data: bytes) -> str:
    if b"\x00" in data[:8192]:
        return "binary"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "utf-8-replaced"


def reasons_to_json(reasons: list[dict]) -> str:
    return json.dumps(reasons)
