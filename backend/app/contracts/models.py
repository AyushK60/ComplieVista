"""Typed M0 evidence contracts (schema m0.v1) — see docs/DECISIONS/ADR-0002.

C and Python pipelines share only this metadata envelope; their stage vocabularies
are distinct (see API_CONTRACTS.md). Unknown manifest fields are tolerated
(additive versioning), but enum values are validated strictly.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"
    NOT_REQUESTED = "NOT_REQUESTED"


class MappingConfidence(str, Enum):
    EXACT = "EXACT"
    DERIVED = "DERIVED"
    APPROXIMATE = "APPROXIMATE"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationClass(str, Enum):
    TOOL_OUTPUT = "TOOL_OUTPUT"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    DERIVED_VISUALIZATION = "DERIVED_VISUALIZATION"
    EDUCATIONAL_APPROXIMATION = "EDUCATIONAL_APPROXIMATION"


class Language(str, Enum):
    C = "c"
    PYTHON = "python"


class ToolInvocation(BaseModel):
    model_config = {"extra": "allow"}

    argv: list[str]
    exit_code: int
    duration_ms: int = 0
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stdout_sha256: Optional[str] = None
    stderr_sha256: Optional[str] = None
    version: Optional[str] = None
    tool: Optional[str] = None


class ArtifactRef(BaseModel):
    model_config = {"extra": "allow"}

    path: str
    sha256: str
    bytes: int
    kind: str = "raw"


class SourceFileRecord(BaseModel):
    path: str
    sha256: str


class SourceSnapshot(BaseModel):
    model_config = {"extra": "allow"}

    files: list[SourceFileRecord]
    combined_sha256: str


class StageRecord(BaseModel):
    model_config = {"extra": "allow"}

    stage: str
    availability: Availability
    observation_class: ObservationClass
    invocation: ToolInvocation
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    counts: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class AnalysisManifest(BaseModel):
    model_config = {"extra": "allow"}

    schema_version: str
    analysis_id: str
    language: Language
    source_snapshot: SourceSnapshot
    tools: dict[str, Any]
    stages: list[StageRecord]

    def stage(self, name: str) -> Optional[StageRecord]:
        for s in self.stages:
            if s.stage == name:
                return s
        return None


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ------------------------- M1 additions (m1.v1) -------------------------

class ClassificationReason(BaseModel):
    code: str
    detail: str
    verified: bool


class ProjectModel(BaseModel):
    id: str
    name: str
    created_utc: str


class SourceSnapshotModel(BaseModel):
    id: str
    project_id: Optional[str] = None
    origin: str
    combined_sha256: str
    created_utc: str


class SourceFileModel(BaseModel):
    id: str
    rel_path: str
    content_sha256: str
    size: int
    encoding: str
    language: str


class CompilationTargetModel(BaseModel):
    target_id: str
    snapshot_id: str
    kind: str
    primary_file: str
    status: str
    ready_for_controlled_execution: bool
    reasons: list[ClassificationReason]


class ImportManifestModel(BaseModel):
    import_id: str
    project_id: str
    snapshot_id: str
    canonical_owner: str
    canonical_repo: str
    commit_sha: str
    archive_sha256: str
    file_count: int
    rejected_count: int
    policy_version: str
