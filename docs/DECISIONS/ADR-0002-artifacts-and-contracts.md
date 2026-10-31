# ADR-0002 — Versioned artifact/evidence contracts

Status: Accepted (M0)

## Context

README §8 defines the evidence model: every claim must be traceable to a real tool
invocation with versions, hashes, availability states and honest mapping confidence.
M0 must implement the minimum typed contract that both pipelines share, without
conflating C and CPython representations.

## Decision

**Schema version `m0.v1`** implemented in `backend/app/contracts/models.py` (Pydantic v2):

- `Availability`: `AVAILABLE | PARTIAL | UNSUPPORTED | BLOCKED | ERROR | NOT_REQUESTED`
- `MappingConfidence`: `EXACT | DERIVED | APPROXIMATE | UNAVAILABLE`
- `ObservationClass`: `TOOL_OUTPUT | RUNTIME_OBSERVATION | DERIVED_VISUALIZATION | EDUCATIONAL_APPROXIMATION`
- `ToolInvocation`: argv array, tool name, exact version string, exit code, wall-clock ms,
  separate stdout/stderr digests.
- `StageArtifact`: stage id, artifact kind, path (repo-relative), SHA-256, byte size,
  availability, observation class, limitations (free text), optional counts.
- `AnalysisManifest`: schema version, language (`c` | `python` — distinct enums, never a
  shared "compilation" notion), session-local id (`m0-c`, `m0-python`), source snapshot
  SHA-256, tool versions, stage list.

Rules enforced by tests:

- IDs are session-local and deterministic for M0 fixtures.
- `EXACT` mapping is used only where the tool itself reports positions/structure (e.g.
  token start/end offsets, `dis` instruction `positions`); any cross-representation
  linkage in M0 is `UNAVAILABLE` unless mechanically derived and labeled `DERIVED`.
- Raw artifacts are content-addressed by SHA-256; the manifest references digests, and
  regenerating a fixture reproduces digests (oracle tests).
- Stage-name policy (clarified during M0 tests): the generic envelope names `tokens`,
  `ast`, `diagnostics` may appear in both pipelines because the *mechanisms and content*
  remain genuinely different (clang vs CPython stdlib); language-specific representation
  stages (`ir`/`assembly`/`object` for C; `code_object`/`bytecode` for Python) must never
  leak across pipelines. Enforced by `test_language_stage_vocabularies_distinct`.

## Consequences

- Later milestones extend the schema with additive, versioned fields; M0 consumers must
  tolerate unknown fields.
- The manifest is the single source the API serves; the UI never invents stage content.
