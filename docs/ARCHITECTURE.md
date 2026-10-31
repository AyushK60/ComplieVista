# CompileVista Architecture (M0 baseline)

Status: M0 — foundation proof. This document describes the implemented M0 system and the
architecture it validates. The authoritative product scope is `README.md`; this document
never narrows it.

## Component diagram (implemented in M0)

```text
Windows 11 host
  ZCode agent (this session, promotional GLM-5.3 Flash, normal Windows-local project)
    |  wsl.exe -d Ubuntu-24.04 -- <argv array>     (never shell strings from untrusted input)
    v
Ubuntu 24.04 (WSL2) -----------------------------------------------
  |  FastAPI control plane (backend/, uvicorn, binds 127.0.0.1)
  |    /api/v1/health /capabilities /analyses[...]
  |  toolchain adapters (toolchains/c, toolchains/python)
  |    C:   clang 18.1.3  -E | -dump-tokens | -ast-dump=json | -S -emit-llvm | -c | objdump
  |    Py:  CPython 3.12.3 tokenize | ast | compile | dis            (never executes fixtures)
  |  staging bridge (backend/app/services/staging.py)
  |    E:\ComplieVista  ->  /mnt/e/ComplieVista  ->  immutable copy at
  |    /home/khana/.cache/compilevista/jobs/<job-id>/src  (+ SHA-256 manifest)
  |  Docker 29.9.2 (curated execution feasibility, sandbox/feasibility_m0.py)
  |    restrictive baseline: no network, read-only rootfs, cap-drop ALL,
  |    no-new-privileges, non-root UID, cpu/mem/pids/wall-time ceilings
  |  React/Vite dev server (frontend/, Node 24.22.2) -> proxies /api to FastAPI
-------------------------------------------------------------------
  Evidence: content-hashed raw artifacts + manifests under evidence/m0/
  (text artifacts committed; regenerable binaries excluded by .gitignore)
```

## Dataflow (M0 analysis path)

1. **Fixture snapshot.** Checked-in deterministic fixtures (`demos/m0/`) are read as bytes;
   SHA-256 recorded. For staging tests, the same mechanism copies a source tree from
   `/mnt/e/ComplieVista` into Linux-native per-job storage.
2. **Tool invocation.** Adapters run pinned argv arrays (`subprocess.run([...], timeout=…)`)
   against the staged snapshot, capturing **stdout, stderr and exit code separately**.
3. **Artifact capture.** Raw outputs are written to `evidence/m0/<pipeline>/<stage>/` with
   SHA-256 digests; `manifest.json` records the exact invocation, version, exit status,
   counts, digests and per-stage limitations.
4. **Normalization.** Selected structure (C tokens / AST summary / IR function+block
   inventory; Python tokens / AST node summary / code-object metadata / dis instruction
   list) is parsed into typed records (`backend/app/contracts/models.py`) without inventing
   relationships. Mapping confidence is `EXACT` only for positions the tool itself reports;
   cross-representation links are `UNAVAILABLE` in M0 unless derived mechanically.
5. **API exposure.** FastAPI reads manifests and serves bounded typed views; oversized
   bodies are truncated with an explicit `truncated: true` flag plus the artifact digest.
6. **Frontend smoke.** The Vite app fetches `/api/v1/capabilities` and the two M0 analyses
   and renders genuine artifacts (token ribbon, bytecode table) — no decorative pipeline.

## Failure handling

- Every tool call has a wall-clock timeout; failures produce `ERROR` stage records with the
  captured stderr, never silent omission and never a fabricated substitute.
- The API returns structured errors (`{"error": {"code", "message"}}`), never raw paths.
- Staging operations are atomic (write-to-temp + rename) and cleaned up; invalid paths
  (traversal, absolute, symlink escape, oversized) are rejected before any copy.
- Docker feasibility runs use `--rm`, external `timeout`, and pre/post container-count
  checks to prove cleanup.
- A failed stage is reported `FAIL`/`BLOCKED` in `docs/milestones/M0.json`; no auto-advance.

## Trust boundaries (restated; details in docs/SECURITY.md)

Browser is untrusted; fixture/source bytes are untrusted; Docker socket access is
host-equivalent privilege held only by trusted orchestration. M0 does **not** claim a
secure sandbox — it only proves the restrictive-flag baseline is accepted by the installed
Docker and that curated trivial programs run contained.
