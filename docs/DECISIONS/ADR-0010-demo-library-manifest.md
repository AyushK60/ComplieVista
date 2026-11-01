# ADR-0010 — Curated demo library: manifest-pinned 20-program suite (M7, recorded retroactively)

Status: Accepted (recorded retroactively during M8-G0; the M7 code has referenced
"ADR-0010" since the demo library was built, but the record itself was missing).

## Decision

1. The demo inventory is exactly **20 real programs** defined by the versioned,
   hash-pinned manifest `sandbox/fixtures/demos/manifest.json` (5 Python-only,
   5 C-only, 5 matched C/Python pairs = 10 more implementations). The manifest
   loader refuses any count other than 20 (`demos.load_manifest`).
2. Demo snapshots are created from manifest content with origin `curated`,
   idempotent on content hash, and run through the REAL M4 execution pipeline.
   Multi-file C-05 uses the `demo-link` profile: the TU list comes from the
   manifest, never from user input.
3. Error Microscope fixtures live outside the manifest and do not count toward
   the 20.
4. Because origin is `curated`, M8-G0's trace trust contract (ADR-0011) labels
   demo executions `CURATED_COOPERATIVE`; pasted/uploaded code is labeled
   `UNTRUSTED_TARGET`.

## Consequences

- Demo behavior is fully reproducible from the manifest; adding/removing demos
  is a manifest + fixture change with tests, not a code change.
- The M8-G0 trace trust allowlisting keys off this origin value.

## Rollback

None needed; this ADR records existing behavior.
