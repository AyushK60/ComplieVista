# API Contracts — M0 surface (`/api/v1`)

Versioned contracts per README §12; only the M0 subset is implemented. All responses are
JSON, bounded (large bodies truncated with explicit `truncated: true` + digest of the full
artifact), and never contain raw local absolute paths.

## GET /api/v1/health
`{"status": "ok", "time_utc": "...", "python_version": "3.12.3", "schema_version": "m0.v1"}`

## GET /api/v1/capabilities
Observed tool availability, probed once at startup with timeouts:
`{"tools": {"clang": {"version": "18.1.3", "available": true}, "python": {...},
"docker": {...}, "objdump": {...}}, "modes": {"read_only_analysis": "AVAILABLE",
"curated_execution": "PARTIAL", "pasted_execution": "BLOCKED"}, "notes": [...]}`
Availability values use the ADR-0002 enum; honest `BLOCKED`/`UNSUPPORTED` labels are
mandatory (e.g. pasted execution is `BLOCKED` until the M4 gate).

## GET /api/v1/analyses
List of registered M0 proof analyses: `[{"id": "m0-c", "language": "c", ...}, {"id": "m0-python", "language": "python", ...}]`

## GET /api/v1/analyses/{id}
Manifest header: schema version, language, source snapshot SHA-256, tool versions, stage
list with per-stage `availability` + `observation_class` + limitations.

## GET /api/v1/analyses/{id}/stages/{stage}
Typed stage view, e.g.:
- `m0-c` stages: `preprocess, tokens, ast, ir, assembly, object, symbols, diagnostics`
- `m0-python` stages: `tokens, ast, code_object, bytecode, diagnostics`
Response: `{"analysis_id", "stage", "availability", "counts": {...}, "items": [...],
"artifact": {"sha256", "path", "bytes"}, "limitations": [...], "truncated": false}`

`items` are normalized typed records (tokens with exact source offsets; IR function/block
inventory; dis instructions with positions). Where a mapping cannot be substantiated the
record says `UNAVAILABLE` — the API never fabricates linkage.

## Errors
Structured, non-leaf paths: `404 {"error": {"code": "NOT_FOUND", "message": "unknown analysis id"}}`,
`400` for malformed stage names, `503` when a backing tool is unavailable. No stack traces.

## Out of M0 scope (must not be faked)
`POST /api/v1/sources`, `/imports/github`, `/executions`, `/comparisons`, `/sessions` —
remain unimplemented; the README job lifecycle governs their later design.
