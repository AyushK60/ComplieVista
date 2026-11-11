# ADR-0001 - Workspace, path spelling, and Linux-native job staging

Status: Accepted (Stage 0)
Supersedes: none

## Context

The project folder on Windows is `E:\ComplieVista` (the folder name has a typo). It is used
as it is and is not renamed.

Cross-OS operations over `/mnt/e` (9P protocol) are known to be slow for file-watching and
metadata-heavy workloads.

## Decision

1. **One authoritative repository: `E:\ComplieVista` ↔ `/mnt/e/ComplieVista`.** Verified in
   Stage 0 by direct listing. No rename, no move, no second checkout. The product name remains
   **CompileVista** regardless of the folder spelling. All milestone prompts, scripts and
   ADRs reference the verified path.
2. **Linux-native immutable job staging.** Analysis copies inputs once into
   `/home/khana/.cache/compilevista/jobs/<job-id>/src`, computes a SHA-256 manifest
   (per-file + combined), and performs all tool work there. The staging directory is
   disposable and excluded from version control; it is **not** a second repository.
3. **Snapshots are immutable and hashed.** Outputs associate with the snapshot's combined
   hash; re-staging the same input yields an identical combined hash (repeatability test).
4. **Atomicity & cleanup.** Files are written via temp-file + rename; jobs are removed on
   completion; path validation (traversal, absolute, non-regular files, size/count caps)
   rejects hostile input before any copy.
5. **Path conversion.** Windows↔WSL conversion is done with explicit, tested mapping
   (`E:\X` → `/mnt/e/X`), cross-checked with `wslpath` in tests; no untrusted filename is
   ever interpolated into a shell string - tools receive argv arrays only.

## Performance evidence

Measured early on: staged-copy of the fixture tree
`/mnt/e → /home` vs direct reads from `/mnt/e`, with timings. Decision fallback if Vite
watching over `/mnt/e` is inadequate: run the **frontend dev server** with chokidar polling
or a verified Windows-native Node - the authoritative repository still never moves.

## Consequences

- Tool I/O happens on ext4 (fast, consistent), while provenance still points at the
  immutable snapshot hash rather than a mutable working tree.
- Cost: one copy per job (bounded, measured); acceptable for analysis jobs.
- Risk: staging under `$HOME` consumes disk - bounded by per-job size caps and cleanup.
