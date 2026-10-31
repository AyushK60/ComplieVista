# API Contracts — M0 surface (`/api/v1`) + M1 source workspace

Versioned contracts per README §12; M0 endpoints unchanged, M1 adds the source workspace.
All responses are JSON, bounded (large bodies truncated with explicit flags), and never
contain raw local absolute paths.

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
`POST /api/v1/executions`, `/comparisons`, `/sessions` — remain unimplemented; the README
job lifecycle governs their later design.

---

# M1 additions (schema `m1.v1`, ADR-0004)

## GET /api/v1/limits
Discloses every bounded intake limit (bytes, counts, ratios, timeouts) for UI and tests.

## POST /api/v1/sources
Two forms:
- JSON `{"kind": "paste", "language": "python"|"c", "filename", "content"}` → creates a
  project + immutable snapshot.
- `multipart/form-data` with file parts (`.c`/`.h`/`.py`, or one `.zip` ≤ 25 MB) →
  archive validated by the shared safe extractor; rejected entries are returned and
  persisted as snapshot diagnostics.
Response: `{project_id, snapshot_id, existed, file_count, rejected[], rejected_count}`.
Idempotent per `(project, combined_sha256)`.

## POST /api/v1/imports/github
`{"url": "https://github.com/OWNER/REPO", "ref"?: "branch|tag|sha"}` — strict URL
validation (https, exact github.com host, no userinfo/port/query/fragment/traversal),
metadata + full commit SHA via api.github.com, tarball only from codeload.github.com
pinned to the SHA, redirect-host allowlist, streaming byte caps, rate-limit typed errors.
Response adds `{canonical_owner, canonical_repo, commit_sha, archive_sha256,
policy_version, download_ms}`. Nothing retrieved is executed or built.

## GET /api/v1/projects · /projects/{id} · /projects/{id}/targets
Project listing with snapshot identities; targets carry `status`
(`STATIC_ANALYZABLE | COMPILATION_CANDIDATE | EXECUTABLE_CANDIDATE | BLOCKED |
UNSUPPORTED`; `READY_FOR_CONTROLLED_EXECUTION` is never emitted in M1), machine-readable
`reasons[]` each tagged `verified: true|false`, and `ready_for_controlled_execution:
false` always in M1.

## GET /api/v1/projects/{id}/snapshots/{sid} · …/files/{fid}
Snapshot files (rel paths, sizes, encodings, digests, intake diagnostics) and bounded
file text (`text` ≤ 200 KB with `text_truncated`; binary files return `text: null`).

## Errors
All M1 failures return `{"error": {"code", "message"}}` with typed codes, e.g.
`INVALID_URL, REPO_NOT_FOUND, RATE_LIMITED, REDIRECT_DISALLOWED, ARCHIVE_TOO_LARGE,
BOMB_RATIO, PATH_TRAVERSAL, PAYLOAD_TOO_LARGE, NO_ACCEPTABLE_FILES, MALFORMED_ARCHIVE`.


---

# M4 execution endpoints

## POST /api/v1/executions
`{"snapshot_id", "target_id"}` → admission (eligibility + origin); returns
`{execution_id, status, existed}` or typed error (NOT_EXECUTABLE,
EXECUTION_ORIGIN_BLOCKED, BLOCKED/DOCKER_*).

## GET /api/v1/executions/{id}
Full execution record: status, exit_code, stdout/stderr/trace/binary SHA-256s,
events_count, truncation flags, image_id, duration.

## GET /api/v1/executions/{id}/events?after=0&limit=200
Ordered, checksummed event pages (kind, payload, sha256). Caps: 5000 events.

## GET /api/v1/executions/{id}/output
Bounded stdout/stderr text (≤60 KB excerpt) with truncation flag.

## POST /api/v1/executions/{id}/cancel
Active cancellation: QUEUED → CANCELLED; RUNNING → `docker rm -f` + CANCEL_REQUESTED.

## Limits
Body ≤ 32 MB (streaming cap on raw ASGI receive); runtime 30 s; build 90 s;
memory 256 MB; pids 64; cpus 0.5; stdout/stderr 1 MB each.
