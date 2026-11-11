# Architecture

CompileVista is a local app: a FastAPI backend, a React frontend, and three Docker images
that run the real toolchains. Everything binds to `127.0.0.1`.

```text
Browser (React + Vite)
   |  /api  (proxied)
   v
FastAPI backend (backend/app)
   |-- routes/      HTTP endpoints: sources, analyses, executions, experiments, demos, system
   |-- services/    ingest, staging, analyzer, execution, graphs, linemap, experiments, demos
   |-- store/       SQLite metadata + content-addressed artifact files
   `-- Docker (sandbox/)
         analyzer image  clang/LLVM 18, CPython 3.12: tokens, AST, IR, assembly, objects, bytecode
         runtime image   restricted run of a program, recorded call/line/return events
         debug image     gdb-based stops for C memory and process views
```

## Data flow

1. **Source snapshot.** Pasted code, a ZIP, or a public GitHub repository is stored as an
   immutable snapshot with a SHA-256 manifest. Archives are checked for path traversal,
   symlinks and size limits.
2. **Staging.** On Windows with WSL, sources are copied into Linux-native per-job storage
   before analysis, because the Windows mount is slow and does not deliver file events.
3. **Analysis.** Pinned commands run inside the analyzer container with no network. Stdout,
   stderr and exit code are captured separately for every stage.
4. **Artifacts.** Raw tool output is stored by content hash. Each artifact records the tool,
   its version, the exact invocation, the exit code, counts and known limitations.
5. **Normalisation.** Tokens, AST nodes, IR and assembly instructions, and bytecode are parsed
   into typed records (`backend/app/contracts/models.py`). Links between representations are
   only created when the tool reports them (for example LLVM debug locations); otherwise the
   link is marked unavailable.
6. **Execution.** A program runs once in the runtime container. The recorded events are
   stored and replayed in the browser. They are never simulated.

## Rules the code follows

- C and Python are separate pipelines. Python bytecode is not machine code and Python has no
  LLVM optimisation levels.
- Static analysis never executes the analyzed code.
- If a tool cannot provide something, the API and UI say it is unavailable.
- Containers run without network, with a read-only root filesystem, dropped capabilities,
  resource limits and a non-root user. Access to the Docker socket is equivalent to host
  privilege, so only the backend uses it.

See [SECURITY.md](SECURITY.md) for the threat model, [API_CONTRACTS.md](API_CONTRACTS.md) for
the endpoints and [DECISIONS/](DECISIONS/) for the design decisions.
