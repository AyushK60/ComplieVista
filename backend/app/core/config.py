"""M1 bounded intake limits (ADR-0004). All values are explicit, documented and tested."""
from __future__ import annotations

import os

LIMITS: dict[str, int] = {
    "paste_max_bytes": 512 * 1024,
    "upload_max_files": 50,
    "file_max_bytes": 2 * 1024 * 1024,          # per source file (matches M0 staging cap)
    "snapshot_total_max_bytes": 16 * 1024 * 1024,
    "snapshot_max_files": 2000,
    "snapshot_max_depth": 12,
    "zip_max_compressed_bytes": 25 * 1024 * 1024,
    "zip_max_expanded_bytes": 64 * 1024 * 1024,
    "zip_max_ratio": 100,                        # expanded/compressed; 0 disables
    "github_archive_max_compressed_bytes": 25 * 1024 * 1024,
    "github_api_timeout_s": 20,
    "github_download_timeout_s": 90,
    "api_max_response_items": 500,               # per M0 convention
}

DEFAULT_DATA_DIR = os.environ.get(
    "COMPILEVISTA_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"),
)

SCHEMA_VERSION = "m2.v1"
IMPORT_POLICY_VERSION = "m1.github.v1"
ANALYSIS_POLICY_VERSION = "m2.analyzer.v1"
ANALYZER_IMAGE = os.environ.get("COMPILEVISTA_ANALYZER_IMAGE", "compilevista/analyzer:m2")
ANALYSIS_TIMEOUT_S = int(os.environ.get("COMPILEVISTA_ANALYSIS_TIMEOUT_S", "180"))
ANALYSIS_MAX_CONCURRENT = 1          # single bounded worker for local M2
