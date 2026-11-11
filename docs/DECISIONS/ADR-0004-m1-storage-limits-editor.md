# ADR-0004 - stage 1 storage, intake limits, and frontend editor choice

Status: Accepted (Stage 1)

## Context

Stage 1 introduces persistent projects/snapshots/targets, bounded archive intake, and a
functional workspace UI. the project notes suggested SQLAlchemy/Alembic and Monaco; stage 1 must stay
bounded and reviewable.

## Decision

1. **Storage: stdlib `sqlite3` (WAL) + content-addressed artifact files.** One guarded
   `schema_version` upgrade point in `app/store/db.py` (`m1.v1`). Exact source bytes are
   stored under `data/artifacts/<sha[:2]>/<sha>` (atomic publish, immutable); the DB
   references SHA-256 digests. SQLAlchemy/Alembic are deferred until schema complexity
   justifies them - a later ADR will govern the migration.
2. **Idempotency:** `UNIQUE(project_id, combined_sha256)` on snapshots - re-importing an
   identical archive/GitHub revision into the same project returns the existing snapshot
   (`existed: true`). Each paste creates a new project (a new investigation).
3. **Intake limits** (all explicit in `app/core/config.py`, disclosed via `GET /api/v1/limits`):
   paste ≤ 512 KB; ≤ 50 uploaded files; ≤ 2 MB/file; ≤ 16 MB snapshot total; ≤ 2000 files;
   depth ≤ 12; archive ≤ 25 MB compressed / ≤ 64 MB expanded / ratio ≤ 100; GitHub archive
   ≤ 25 MB; API responses ≤ 500 items; editor text ≤ 200 KB excerpt in responses.
4. **Extraction is validator-shared:** one safe extractor (`app/services/archive.py`) serves
   both ZIP uploads and GitHub tarballs; nothing extracts to disk; every rejected entry is
   recorded with a typed reason code.
5. **Frontend editor: read-only line-numbered `CodeView` component now; full Monaco in stage 3.**
   The stage 1 prompt allows an "equivalent read-only/edit mode"; Monaco's bundle and editor
   integration belong with stage 3's editor-stage synchronization work. UI routes use
   `react-router-dom@6.28.0`.
6. **Classification honesty:** every reason carries `verified: true|false`; lexical
   detections (e.g. `main(` found by regex - including inside comments) are labeled
   `detected`. `READY_FOR_CONTROLLED_EXECUTION` is never emitted in stage 1; the UI shows
   "execution: gated by stage 4" and a disabled Analyze action.

## Consequences

- Fresh checkout gets a working workspace with zero migrations (`Store` creates schema).
- Binary/asset-heavy repos are partially imported (binary entries rejected and recorded) -
  acceptable for a source observatory; full binary handling is out of scope.
- GitHub import is unauthenticated: 60 requests/hour per IP applies; typed `RATE_LIMITED`
  errors are surfaced rather than retried blindly.
