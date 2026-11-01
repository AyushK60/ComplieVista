# CompileVista

> **Explore How Code Becomes Execution.**  
> A real-artifact compiler, runtime, memory, and operating-system observatory for C and Python.

**Document type:** Master product specification + proposed engineering architecture + milestone acceptance contract  
**Specification version:** 1.0 — 31 October 2026  
**Status:** Specification v1.0 unchanged. **Implementation status (1 November 2026, M8-G0):** M0–M7 implemented and passing their internal gates — 20 real programs, static pipelines (Clang 18.1.3 / CPython 3.12.3), restricted-container execution with recorded traces, MemoryScope/ProcessScope, OptimizationLab and pair comparisons. **M8-G0 (technical integrity repairs + one-click local launcher) DONE**: trace trust/channel hardening, immutable image-ID pinning, benchmark checksum correctness, Demo Library error recovery (ADR-0010..0012, `docs/TEST_EVIDENCE/M8G0.md`). **M8 visual polish and M9 (independent audit/release) are NOT started**; this remains the developer agent's self-assessment, not an independent audit. Local run: double-click `Start.cmd` (`docs/LOCAL_RUN_GUIDE.md`).  
**Primary development environment:** ZCode/Jet **Windows desktop local project** using available promotional GLM models  
**Canonical repository:** `E:\ComplieVista` (Windows)  
**Linux tool environment:** Ubuntu 24.04 LTS, WSL2; exposed to ZCode via `wsl.exe`  
**Initial languages:** **C and Python** — both are mandatory  
**Cost constraint:** No paid API or mandatory cloud dependency for the core application  
**Delivery:** Local-first; later an authenticated, private HTTPS demonstration

> **IMPORTANT FOR CODING AGENTS:** This file is the scope and acceptance contract, **not** proof that any feature exists. Do not mark a feature complete because a diagram, stub, mocked endpoint, screenshot, or fixture appears plausible. Preserve the C/Python distinctions, execute tests, record raw artifact provenance, and stop at a failed gate. Never treat external repository code as trusted. Do not silently weaken isolation to make a demonstration work.

---

## 1. Vision, motivation, and intended audience

CompileVista is an exploratory instrument for students, compiler engineers, programming-languages researchers, systems developers, and instructors. The motivation is straightforward: compiler education commonly teaches tokens, syntax trees, intermediate representations, code generation, runtime execution, and memory through disconnected static diagrams. CompileVista connects them using **actual artifacts produced by real toolchains and recorded observations from real program runs**.

A user should be able to paste code, upload files, or import a public GitHub repository; select a valid C or Python target; investigate the genuine representations that exist for that language; execute a supported program under controlled conditions; replay an observed trace; and inspect what the system **does and does not know** about source-to-execution relationships.

The purpose of the portfolio project is to demonstrate engineering strength in compilers, programming languages, runtimes, operating systems, computer architecture, program analysis, developer tools, and high-quality interaction design. It should be credible in discussions with professors considering research-focused master's or doctoral applicants. The software itself is **not automatically publishable scientific research**: claims of educational effectiveness or user benefits require separate empirical evaluation.

### Product promises

1. **Technical truth:** never invent compiler passes, tokens, AST nodes, LLVM IR, assembly, machine code, runtime events, stack frames, allocations, system calls, optimization results, or measurements.
2. **Two genuine languages:** meaningful C **and** CPython functionality from early milestones. Do not invent an identical pipeline for both.
3. **Deep visual exploration:** a navigable observatory, not cards linked by decorative arrows, a static slideshow, or an AST JSON dump marketed as visualization.
4. **Working execution:** the first substantial version must perform genuine static analysis **and** controlled execution for supported pasted C/Python code; unsafe modes remain blocked until their security gate passes.
5. **Reproducibility:** record the source, toolchain versions, commands, environment, hashes, errors, and uncertainty behind every claim.
6. **Premium product quality:** the internal technical workspace deserves at least as much care as the landing page.
7. **Free-tier reproducibility:** core results require no paid LLM API. Optional AI explanations must never be authoritative.

### Non-goals

- Reimplement Clang, LLVM, or CPython from scratch.
- Claim all language/compiler internals are exposed through public tools.
- Provide unlimited public arbitrary-code execution.
- Infer full C heap contents or instruction-by-instruction CPU history without supporting instrumentation.
- Claim animations are execution evidence or that backward trace replay rewinds a real process.
- Pretend C optimization levels correspond to Python's compilation pipeline.
- Build an empty-looking generic admin dashboard or a chatbot-only code explanation tool.

## 2. Mandatory user journeys

**J1 — Python recursion:** open a curated Python program; inspect real tokens, genuine Python AST, code objects, `dis` bytecode, call/line/return events, frame/variable changes; play, pause, and step through the **recorded** trace; follow selected source locations to the applicable bytecode and trace events.

**J2 — C pointers and arrays:** inspect preprocessing, tokens, Clang AST, genuine LLVM IR, control flow, assembly, machine-code bytes where supported; compare real `-O0` and `-O2` outputs; run the approved executable and inspect supported stack/pointer/memory observations.

**J3 — GitHub import:** paste a public repository URL; identify immutable revision, discover meaningful supported source files/build targets, show why a target is analyzable/compilable/executable/blocked; perform read-only analysis by default; never trust build scripts automatically.

**J4 — Cross-language comparison:** display matched C/Python algorithms in two aligned but independent pipelines; compare actual output, representations, control-flow concepts, runtime calls, memory and measurements without claiming semantic equivalence where it does not exist.

**J5 — Large visual exploration:** expand and collapse genuine AST branches; inspect source, syntax, IR, basic blocks and runtime timeline through smooth pan/zoom, semantic zoom, filtering, search, minimap, and keyboard navigation without excessive latency.

**J6 — Failure analysis:** present actual parser/semantic/compiler/linker/runtime/sanitizer diagnostics, including source ranges, stage identification, cause and practical explanation; never convert an unsupported operation into a fake successful run.

**J7 — Reproducible investigation:** save a session; reopen its captured evidence without rerunning code; export a sanitized, reproducible investigation bundle; disclose unavailable stages and tooling limitations.

## 3. Confirmed host setup and architectural decision

### Verified on the user's actual development machine

| Component | Verified state |
|---|---|
| Host | Windows 11; Intel i7-13650HX, 24 GB RAM, NVIDIA RTX 5050 Laptop GPU (GPU not required) |
| Agent | ZCode/Jet Windows desktop, **normal local project**, promotional GLM model appears |
| Project path | **`E:\ComplieVista`** — actual verified spelling (intended name `E:\CompileVista`; see Path Note) — **one source-of-truth repository** |
| WSL distro | Ubuntu 24.04 LTS on WSL2 |
| C toolchain | Clang 18.1.3, LLVM 18.1.3 |
| Debugger / tracing | GDB 15.1, strace 6.8; package installation completed; advanced capabilities not yet proven |
| Python | CPython 3.12.3 inside Ubuntu; Windows also has Python 3.11.9 |
| JS toolchain | Node.js 24.22.2, npm 11.19.1 inside Ubuntu (`/usr/bin/node`) |
| Docker | Docker Desktop 4.97.0, Engine 29.9.2; Linux engine reachable from Ubuntu without `sudo`; `hello-world` passed |
| Agent integration | **Actual ZCode agent** successfully invoked WSL Clang, Python and `docker ps` from the Windows workspace |
| Not yet proven | Full compiler/debugger pipeline, frontend watching, cross-filesystem build speed, debugger/container compatibility, production-quality isolation |

### Deliberate non-negotiable workflow decision

**Path note:** `E:\CompileVista` is the documented intended folder convention. If the real Windows directory uses a space or another spelling, use its actual verified path consistently; do not rename or move the user’s folder without permission. **M0 verification:** the actual directory is `E:\ComplieVista` (↔ `/mnt/e/ComplieVista`); this correction is recorded in `docs/DECISIONS/ADR-0001-workspace-and-linux-staging.md`. The product name remains CompileVista.

**Do not move the main ZCode project to a remote WSL workspace merely for convenience.** The promotional GLM model is available in normal Windows ZCode, but was unavailable in the remote WSL chat. Keep the working Windows-local agent and use the Linux tools through `wsl.exe`. Do not recommend dual boot, Zorin, Kubuntu, or a separate Linux installation without a **reproducible demonstrated blocker**. Do not create two divergent source repositories.

`E:\ComplieVista` maps to `/mnt/e/ComplieVista` under Ubuntu. Cross-filesystem operations may be expensive. Implement **immutable per-job snapshots** into Linux-native staging under `/home/khana/.cache/compilevista/jobs/<job-id>` or another configured native Linux location. Compute SHA-256 of the staged snapshot and associate outputs with it; capture artifacts back into the canonical repository-managed state store or a configured results directory. The staging directory is **not a second development repository**. Never execute arbitrary shell composed from user filenames. Use argument arrays, validated paths, `wslpath`, deterministic working directories, and atomic staging/cleanup.

**Frontend development strategy:** test whether Vite dev-server/file watching performs adequately using Windows source and Linux Node. If not, use a verified Windows-native Node runtime for frontend development or controlled workspace synchronization; benchmark the options. **Backend execution strategy:** run the Python analysis worker inside WSL to access Clang/GDB and Docker. Test Windows-browser-to-WSL localhost API access explicitly. Do not presuppose port forwarding behavior or cross-OS filesystem performance.

All significant architectural changes require a recorded decision (ADR), evidence, tradeoffs, and rollback instructions.

## 4. High-level architecture

```text
USER'S BROWSER (Windows, local-first)
  React / TypeScript / Vite
  Monaco Editor | source explorer | pipeline rail
  @xyflow/react + ELK layout | trace timeline | inspectors
                |
         HTTP / JSON + SSE (localhost)
                v
FASTAPI CONTROL PLANE (WSL Ubuntu)
  Auth/local mode • input validation • API contracts • session store
  source and revision manager • provenance registry • job controller
  staged-source copier • bounded job scheduler • artifact catalog
                |
   +------------+-----------+----------------+
   |                        |                |
STATIC ANALYSIS WORKERS   BUILD/EXECUTION   READ-ONLY REPOSITORY
 (bounded, isolated)       CONTROLLER         IMPORTER
   |                        |                |
   +-- C adapter            +-- Docker       +-- pinned GitHub SHA
   |   clang/LLVM               execution     +-- archive validation
   |   objdump/readelf          profiles      +-- target classifier
   |                        +-- trace hooks
   +-- CPython adapter      +-- resource guards
       tokenize/ast/dis     +-- artifact capture
                |
                v
NORMALIZED VERSIONED EVIDENCE MODEL
 Source snapshots • stage artifacts • source mappings • graphs
 event chunks • variable/memory/process observations • diagnostics
 toolchain/runtime metadata • evidence ledger • uncertainty flags
                |
                v
SQLite (sessions/metadata) + content-addressed artifact files
```

**Trust boundaries:** browser is untrusted; imported source is untrusted; compiler/debugger inputs are untrusted; tool outputs must be parsed as bounded data; Docker control plane and socket are privileged and must not enter an execution container; no frontend value is proof of actual execution.

### Suggested technology selections (subject to M0 proof)

| Layer | Primary choice | Reason / constraint |
|---|---|---|
| Frontend | React, TypeScript, Vite | Local-first SPA, explicit complexity |
| Source editor | Monaco Editor | Language services, ranges, synchronized highlighting |
| Graphs | `@xyflow/react` plus ELK.js layout | Pan/zoom, custom typed nodes; worker-based layout, collapse/filter |
| State/data | TanStack Query; small local UI store (Zustand if useful) | Separate server state from transient selection/playback state |
| UI | Tailwind CSS + accessible component primitives + design tokens | Consistent precision-engineering visual system |
| Timeline | Custom virtualized SVG/Canvas timeline | Large trace streams, time navigation and filtering |
| API | Python 3.12, FastAPI, Pydantic v2 | Typed API boundary and OpenAPI contract |
| Persistence | SQLite + SQLAlchemy/Alembic + content-hash artifact directory | No distributed infrastructure needed |
| Background jobs | Dedicated bounded worker processes, persistent job records | Avoid unbounded work inside HTTP handlers; cancellation, recovery |
| C | Clang/LLVM 18, GNU binutils/LLVM utilities, GDB; optional sanitizers | Actual toolchain outputs, version-pinned |
| Python | CPython 3.12 `tokenize`, `ast`, `symtable`, `dis`, `sys.settrace` or `sys.monitoring`, `tracemalloc`, `gc` | Native CPython representations, observed events |
| Process tracing | `strace`, `/proc`, `psutil` where appropriate | Capability-gated, Linux environment clearly disclosed |
| Controlled execution | Docker Linux containers with restricted per-mode profiles | Necessary infrastructure, **not proof of strong isolation** |
| Testing | pytest, Vitest, Playwright, security/failure fixtures | Unit → contract → integration → browser → independent audit |
| Packaging | Local dev scripts and reproducible containers/tooling lockfiles | Repeatable without paid cloud services |

**Avoid premature distributed services** (Kubernetes, Kafka, message brokers, microservices, mandatory cloud DB). If a tool/version cannot provide a stated stage, record `unsupported`, rather than replacing it with fictional data.

## 5. Input processing and job lifecycle

### Input types

1. **Paste** C/Python source; capture language, filename, encoding, source SHA, entry point and optional deterministic stdin/args.
2. **Upload** individual `.c`, `.h`, `.py` files or bounded source `.zip`; validate paths, contents, archive expansion, encoding, size and nested file counts.
3. **Public GitHub import** as an explicit read-only operation; record canonical repository, commit SHA, selected path, discovery method and import timestamp.

### Workflow

`RECEIVED → VALIDATED → SNAPSHOTTED → CLASSIFIED → ANALYSIS_QUEUED → ANALYZING → ARTIFACTS_READY → (EXECUTION_REQUESTED → SECURITY_GATE → RUNNING → TRACE_READY) → SAVED`.

Failed and canceled jobs have separate terminal states. Every transition records timestamp, reason and structured diagnostic; invalid transitions are rejected. Every stage is independently available/unavailable/error, not a giant all-or-nothing blob. Compilation and execution are separate consented operations. Never launch code automatically on paste/import.

**Preflight classification:** `STATIC_ANALYZABLE`, `COMPILATION_CANDIDATE`, `EXECUTABLE_CANDIDATE`, `READY_FOR_CONTROLLED_EXECUTION`, or `BLOCKED/UNSUPPORTED`, with machine-readable reasons. Python `__main__`, imports and dependencies require inspection; C headers, translation units, `main`, link dependencies and `compile_commands.json` require separate handling. Treat target readiness as proven only after actual toolchain/environment checks.

## 6. Genuine C analysis pipeline (Clang/LLVM)

Each UI station represents a conceptual investigation, **not** a claim that Clang internally runs a separate executable for every label.

| Station | Source and output | UI representation | Correctness constraint |
|---|---|---|---|
| C1 — Source/preprocessing | Original source, `#include`, macros; Clang `-E`; preprocessing diagnostics | Source/preprocessed diff, include/macro navigator | Do not claim full preprocessing provenance if not captured |
| C2 — Lexing | Compiler-compatible token output including locations, categories | Token ribbon + linked source ranges | Display the exact tool output and source mapping limitations |
| C3 — Parse/semantics | Clang AST (structured dump where supported), declarations, types, implicit conversions and diagnostics | Expandable AST, scope/type inspector | Avoid mistaking diagnostic text or AST addresses for stable semantic IDs |
| C4 — LLVM IR | Real `-S -emit-llvm` IR with functions, instructions, operands, basic blocks | IR listing + CFG/dependency explorer | Source→IR is partial, particularly after optimization |
| C5 — Optimization | Separate builds for `-O0`, `-O1`, `-O2`; real remarks if supported | Source-aligned IR/assembly diff; optimization evidence | Never invent pass-by-pass traces based on text diffs |
| C6 — Assembly | Real target-specific `clang -S` output; target triple, flags | Assembly explorer, register/call links | Assembly mnemonics are not raw machine code |
| C7 — Objects/linking | `.o`, symbol table, relocations where supported, linked binary; disassembly + byte columns | Symbol/link graph + bytes-to-instruction inspection | Multi-translation-unit builds must be real, not simulated |
| C8 — Runtime | Controlled executable; actual output, exit, calls/frames, selected GDB and process observations | Trace/player, call stack, memory/process panels | Only claim variables/addresses actually collected |

M0 must prove concrete Clang invocation capabilities on installed version 18.1.3. Prototype command families for *trusted fixture code* include `clang -E`, `clang -Xclang -ast-dump=json -fsyntax-only`, `clang -S -emit-llvm -g -O0`, `clang -S -O2`, `clang -c`, and a bounded link/disassemble command. Actual flags and output parsers must be tested per tool version and input type, with stdout/stderr/exit status captured separately. Never feed arbitrary imported compiler flags, environment variables, makefiles, CMake scripts, or plugin loading directly to the host.

**Runtime C caution:** `-O0 -g` is generally preferable for variable-oriented debugger visualization; optimized debug views may have inlined or eliminated variables. Show this as a limitation. Stack frames and pointer addresses are run-specific; do not persist them as cross-run absolute identities. For memory safety, instrument trusted/sample programs with sanitizers when appropriate; an ASan diagnostic is not a complete heap ledger. Debugger privileges and `ptrace` availability must be explicitly capability-tested; untrusted execution must not receive broad debugger privileges merely to populate visuals.

## 7. Genuine Python pipeline (CPython-specific)

| Station | Real mechanism | UI and limits |
|---|---|---|
| P1 — Source/tokenization | `tokenize`; positions; indentation, names, strings, operators | Accurate token stream and source ranges |
| P2 — Parser/diagnostics | `ast.parse`/`compile` syntax diagnostics and locations | Syntax error explorer. **Do not invent a separate public CPython parse-tree artifact** |
| P3 — AST/scopes | `ast`, `symtable`; functions, classes, loops, comprehensions, name/scope info | Collapsible AST and lexical/scope inspector |
| P4 — Compilation | `compile` code objects; `dis`, constants, nested code objects and source position metadata | Bytecode/control-flow exploration with CPython version |
| P5 — Execution | In-container `sys.settrace` and/or `sys.monitoring` with event capability checks | Real call, line, return, exception, optional instruction observations; bounded frames |
| P6 — Memory/process | In-container `tracemalloc`, `gc`, optional `psutil`/`/proc`/`strace` | Supported allocation summaries, object/ref snapshots, process facts and limitations |

**Python bytecode is not CPU machine code.** Trace events are not automatically one-to-one with bytecode instructions. Record the exact interpreter build and optimization settings; do not assume adaptive/specialized execution state is visible because `dis` produced a listing. Tracing is subject to sampling, dropped events, other threads and instrumentation overhead; preserve such caveats.

**Safe variable snapshots:** serialize approved primitive types and bounded structure metadata rather than evaluating arbitrary expressions, calling user-defined `repr`/properties, or recursively traversing objects without limits. Avoid exposing secrets, host environment variables and host filesystem contents. In-container trace collection is also untrusted and must be size-limited.

## 8. Source/representation links and the evidence model

CompileVista's differentiator is interconnected provenance-aware navigation.

### Versioned data contract entities

`Project`, `SourceSnapshot`, `SourceFile`, `CompilationTarget`, `AnalysisSession`, `PipelineStage`, `ToolInvocation`, `StageArtifact`, `Token`, `SyntaxNode`, `Symbol`, `Scope`, `GraphNode`, `GraphEdge`, `BasicBlock`, `IntermediateInstruction`, `Diagnostic`, `SourceRange`, `SourceMapping`, `RuntimeEvent`, `StackFrame`, `VariableObservation`, `MemoryObservation`, `ProcessObservation`, `BenchmarkRun`, `Comparison`, and `EvidenceRecord`.

Each record requires at minimum:
- Stable **session-local** ID and typed schema version.
- Language, tool and exact version; source snapshot SHA-256 and stage input hashes.
- Raw artifact digest or trace/evidence link; exact tool invocation/flags and exit state when meaningful.
- Observation class: `TOOL_OUTPUT`, `RUNTIME_OBSERVATION`, `DERIVED_VISUALIZATION`, or `EDUCATIONAL_APPROXIMATION`.
- Capability/availability: `AVAILABLE`, `PARTIAL`, `UNSUPPORTED`, `ERROR`, `BLOCKED`, `NOT_REQUESTED`.
- Mappings with `EXACT`, `DERIVED`, `APPROXIMATE`, `UNAVAILABLE`; reason and method. `EXACT` is **not** a generic high-confidence badge.
- Optional source ranges with file identity, line/column basis and byte/Unicode offset convention.
- Explicit uncertainty/limitations; never silently omit unsupported relationships.

### Nonfabrication examples

- A Clang AST node and source span can be observed; mapping the node to an optimized IR instruction often cannot be established exactly.
- Two C assembly statements may replace many IR instructions; one-to-one lines should disappear or be marked unavailable instead of invented.
- A replay event is linked to the source and observation timestamp; replay backward only navigates **recorded history** and does not reverse process side effects.
- `sys.getsizeof` is not complete transitive memory usage. A `tracemalloc` snapshot is not necessarily all process memory.
- Static assembly instruction count is not dynamic CPU instruction count. Bytecode instruction count is different again.

## 9. UI/UX — Compiler Observatory / Precision Engineering / Computational Atlas

### Design principles

- Premium, restrained, scientific, high-contrast design; coherent dark-first palette with optional light mode, distinct semantic colors for stages and statuses; typography and spacing tokens.
- Responsive desktop-first workspace; usable at typical laptop dimensions and 390px width through intentional rearrangement (not squeezed microscopic labels).
- Micro-interactions support real data exploration, never fake execution. Reduced-motion and keyboard navigation are first-class.
- The landing page must feel like a serious software product: compelling *conceptually accurate* source-to-execution journey, relevant product use cases, available tools, demos, documentation, launch CTA. **No empty giant hero, generic gradient-card wall, fake live compiler visualization, or decorative irrelevant graphics.**
- **Internal workspaces equal or surpass the landing page in polish.** Every module shares the same nav, typography, colors, panels, empty states, dialogs and interactions.

### Main workspace regions

1. **Project/source navigator:** repository/file/target filters, stage readiness badges, functions, line-numbered Monaco editor, source selection and diagnostics.
2. **Language-aware pipeline rail:** C and Python get different stations with live availability and conceptual relationships.
3. **Primary graph/canvas:** interactive AST, CFG, LLVM/basic-block view, Python bytecode view, symbol graph, memory graph, process timeline depending on stage.
4. **Technical inspector:** exact selected token/node/instruction properties, incoming/outgoing edges, source mapping quality, provenance and explanation level.
5. **Execution timeline:** play/pause/step ±/scrub/speed/filter/jump/event count and current frame; recorded trace only.
6. **Explanation layers:** Simple (what), Detailed (why), Technical (actual data/mechanism), all tied to evidence with uncertainty visible.
7. **Context/status rail:** tool versions, warnings, blocked capabilities, errors, current run/build and performance data.

### Interactions — mandatory

Smooth pan/zoom, semantic zoom, hover/click selection, expand/collapse AST, focus and fit, minimap, large-graph search/filter, graph↔source highlight, selected node's associated data on stage transitions, keyboard shortcuts and accessibility labeling. At far zoom prefer function/module level; mid zoom major branches/basic blocks; near zoom expressions/instructions; closest show exact operands and metadata. A zoom level must change *content meaningfully*, not just scale a huge static drawing.

For big graphs use worker-based ELK layout, structure-specific layouts, node clustering, progressive disclosure, virtualization, capped render budgets and performance telemetry. Never replace analysis with decorative three-node samples. Offer an accessible tabular/text representation of each diagram.

### Visual modules

- **Compiler Atlas:** real stages, tokens/AST/IR/assembly and navigation.
- **Runtime Replay:** event timeline, output, stack and variables.
- **MemoryScope:** C addresses/pointers/allocations where observed; Python frames, references, object identity, GC/allocation summaries. **Python references are not C pointers.**
- **ProcessScope:** real PID/lifetime, exit, stdout/stderr, threads, selected file/system-call/memory/process observations. Label OS/kernel as Linux within WSL2/Docker, not native Windows.
- **OptimizationLab:** real C `-O0/-O1/-O2` IR, binary and assembly diffs, documented optimizer evidence, controlled benchmarks. Python gets its own bytecode/runtime comparisons, **not** LLVM O-levels.
- **Cross-Language Workbench:** side-by-side aligned **concepts**, separate real stages, matched deterministic inputs and documented semantics.
- **Error Microscope:** syntax/semantic/linker/runtime/sanitizer diagnosis with exact source spans.
- **Control Flow Explorer:** genuine basic-block edges, branches, reachability and observed branch coverage when available.
- **Symbol & Scope Explorer:** real declarations, binding rules, type/scope and shadowing with language-specific semantics.
- **Session History / Comparison:** source versions, inputs, optimized builds, saved evidence, exports.

### Two added value features

**Evidence Ledger (core):** click any visualization claim to reveal the originating source snapshot, tool invocation/version, raw artifact excerpt/hash, mapping method, collection time, availability, uncertainty, and limits. It must be possible for an independent reviewer to challenge a claimed connection.

**Prediction Lab (optional educational enhancement, after the core works):** users predict which branch, return value, stack depth, or variable change a curated program will produce, run a real trace, and compare prediction versus observation. No claims about learning efficacy without a user study. Never let this displace essential compiler/runtime functionality.

## 10. Security architecture: separate source analysis from execution

> **Security requirement:** User-provided source and public repositories are adversarial until proven otherwise. Docker, WSL2 and `subprocess` are **not** magic sandboxes. The local proof of `docker run hello-world` establishes connectivity, not secure arbitrary-code execution.

### Three operating modes

| Mode | Allowed | Disallowed by default |
|---|---|---|
| A. Read-only analysis | Input validation, compiler/parser operations in bounded analysis workers | Import side effects, package install, repo scripts, runtime execution |
| B. Curated execution | Approved 20 demos and verified fixtures in restricted containers | Network, privileged capabilities, unapproved commands, unrestricted mounts |
| C. Pasted/user-code execution | Explicit run action **only after** sandbox threat-model/security gate passes; stricter limits and allowlisted images | Automatic execution, host access, arbitrary dependencies, docker socket, privileged debugging |

### Minimum local sandbox baseline to implement and test

- Worker uses fixed, pre-built, pinned container images (no `latest` in reproducibility-sensitive runs) and an argument-vector API, **never a shell command built from user input**.
- Non-root user in container; read-only root filesystem; bounded writable `/tmp` as `tmpfs`; source imported as validated, non-executable-by-default snapshot if appropriate; separate bounded output capture.
- No published ports; `--network none` where possible; drop all Linux capabilities; `no-new-privileges`; default or stricter tested seccomp profile; AppArmor/LSM if supported; no host PID/IPC privileges; no Docker socket, Docker CLI privileges, broad host volumes, or `--privileged`.
- CPU, memory, pids, disk/workspace and output byte ceilings; wall-clock timeouts; bounded stdin; process-tree termination; lifecycle cleanup; concurrency rate limits; execution accounting.
- Analyze untrusted C **inside constrained worker/container boundaries too**; static compilers can be attacked by malicious input or consume unlimited resources.
- Allowlisted compiler flags, macros, import paths and build targets; refuse toolchain plugins, arbitrary linkers, `-Xclang` injection via supplied flags, `make`, CMake commands, setup scripts, `pip install`, `requirements.txt` execution and repository hooks by default.
- Treat zip slip, symlink escape, zip bombs, oversized archives, GitHub redirect targets/SSRF, Unicode/path normalization, executable file disguise, huge token/AST/trace explosions and malformed tool outputs as threats.
- Trust-sensitive job orchestration belongs outside execution containers; only a narrow privileged orchestrator may access Docker. **Never pass Docker control credentials or socket into an untrusted run.**
- Trace/debug profiles requiring `ptrace` are distinct from the strict untrusted default. If policy-compliant debugger instrumentation cannot be achieved, declare the advanced trace unavailable for that mode, but keep ordinary execution safe.
- A local private demo may run curated samples while arbitrary external execution remains feature-gated pending additional isolation review. Public-facing exposure raises the bar; auth/HTTPS do not themselves isolate computation.

**Admission criterion for pasted code:** demonstrate actual contained Python and C execution **and** test rejection/limits on infinite loops, fork/process bombs, network attempts, filesystem access, attempts to access credentials, abnormal signals, excessive output, malformed inputs, debugger escapes, resource limits and container cleanup. Document residual risk. If independent audit cannot defend the boundary, M4 fails; do not relabel a subprocess or unrestricted container as safe.

### Web/demo safety

Local backend binds to loopback by default. For a private web demo require TLS/HTTPS, authenticated access, secure sessions, CSRF/CORS policy, rate limits, request quotas, logs without secrets, size caps, default no external arbitrary-code execution until explicitly cleared, deployment threat review and a clear revocation/shutdown path. Do not place the Docker socket behind an exposed HTTP API.

## 11. GitHub importer design

A valid public URL must be parsed structurally, not interpolated into a shell command. Resolve `github.com` owner/repository to commit SHA using allowlisted GitHub APIs; acquire archive from trusted allowlisted hosts with redirect validation, short timeouts, streaming size limits, decompression limits, file count limits and safe extraction. Keep source provenance and immutable commit pin. Skip symlinks/submodules/LFS/large generated files unless explicitly supported. Handle rate limits and offline mode cleanly.

Discovery should recognize `.c`, `.h`, `.py`, package `__main__.py`, entry-point candidates, `compile_commands.json`, and harmless metadata; analyze `pyproject.toml`/`CMakeLists.txt`/`Makefile` as **data only**, never execute them automatically. Show curated relevant targets first, full tree optionally. Mark target readiness and why; a `.c` or `.py` file is not automatically a standalone executable.

No authentication token is required for public-repository happy-path. Never store repository credentials in evidence exports. Imported code is read-only unless an explicit snapshot/experiment edit is created in the user's local CompileVista workspace.

## 12. API and storage contracts

All endpoints use versioned contracts (e.g. `/api/v1`). Initial proposed shape, subject to contract tests:

| Operation | Endpoint | Purpose |
|---|---|---|
| Register paste/upload | `POST /api/v1/sources` | Validate, snapshot, classify |
| Import GitHub | `POST /api/v1/imports/github` | Resolve pinned revision and parse safe files |
| List targets | `GET /api/v1/projects/{id}/targets` | Readiness and diagnostics |
| Create analysis | `POST /api/v1/analyses` | Enqueue bounded static analysis |
| Get analysis | `GET /api/v1/analyses/{id}` | Status, available stages, versions |
| Stage artifacts | `GET /api/v1/analyses/{id}/stages/{stage}` | Typed graph/listing/artifact references |
| Provenance | `GET /api/v1/evidence/{id}` | Evidence Ledger record |
| Request execution | `POST /api/v1/executions` | Explicit security/admission check; queue execution |
| Run status/events | `GET /api/v1/executions/{id}` and `/events` | Bounded replay/event chunks |
| Compare | `POST /api/v1/comparisons` | Artifact-aligned language/settings comparison |
| Sessions | `GET /api/v1/sessions`, `POST /api/v1/sessions/{id}/export` | Persistence and reproducible export |
| Health / capabilities | `GET /api/v1/health`, `GET /api/v1/capabilities` | Tool versions, available instrumentation |

Use SSE for job updates where warranted; keep large traces paginated/chunked rather than dumping full JSON into a single browser response. Define idempotent stage-retry semantics, structured errors and cancellation endpoint. Never return raw local absolute paths or secrets unnecessarily. Raw artifacts can be fetched via authorized bounded endpoints.

### Artifact persistence

- SQLite metadata holds projects, sessions, revision/import manifests, job lifecycle, stage availability, provenance edges, limits, run metadata and comparison links.
- Content-addressed artifact storage holds immutable source snapshots, stdout/stderr, AST/IR/disassembly, mapped graph indexes, trace chunks, diagrams/layout caches, benchmark observations and export manifests.
- Use bounded retention policies, checksums, atomic writes, schema migrations, and recovery after abrupt worker restarts. Do not persist user data to a paid or remote service by default.
- Resume of a saved investigation reads immutable previously generated artifacts; rerunning requires a new run ID.

## 13. Performance, measurement and reproducibility

**Measured ≠ estimated.** Capture toolchain/runtime versions, CPU/OS target, compiler flags, source hash, build environment and benchmark context. Distinguish: setup/staging time, compilation, instrumentation overhead, normal execution, frontend layout time, and visualization processing.

Collect genuine available metrics: token and AST counts; C IR/basic block and assembly counts; Python bytecode counts; object/binary sizes; compile durations; execution durations; maximum observed memory/peak RSS definition; trace-event counts; verified calls and selected syscall counts. Show which are static estimates vs sampled vs measured runtime values. No unsupported dynamic CPU instruction count claims.

Benchmark with repeat runs (initial target at least 5 after warmup where reasonable), median and range/variability; record input and environment. Run instrumented and uninstrumented separately. C/Python performance comparisons must explain language semantics and measurement limitations. For graph performance, set measurable budgets for moderate and large fixture sizes, capture render time/memory and preserve selection responsiveness; if graph exceeds a limit, cluster/paginate rather than crash.

## 14. Exactly 20 mandatory real demonstration programs

**Inventory rule:** 5 standalone Python + 5 standalone C + 5 matched Python/C pairs (10 distinct implementations) = **20 individual programs**. A multi-file C target counts as **one program**, not as one program per file. All must have sources, run/analysis manifests, deterministic inputs, expected outputs, provenance and E2E test journeys; no dummy fixtures or mock-only stage completion.

### Group A: 5 Python-only programs

| ID | Program | Must exercise |
|---|---|---|
| PY-01 | Fundamentals | Variables, expressions, functions, branches, tokens/AST/bytecode/trace |
| PY-02 | Iteration and branching | Loops, collections, jumps, variable history |
| PY-03 | Recursion and stack | Actual frame growth/unwind, calls and returns |
| PY-04 | Closures, generators, exceptions | Scope, nested code objects, generator suspension, exceptions |
| PY-05 | Complex bounded execution | Classes, imports and controlled concurrency/async behavior, multiple frames; deterministic fixtures |

### Group B: 5 C-only programs

| ID | Program | Must exercise |
|---|---|---|
| C-01 | Fundamentals | Tokens, Clang AST, LLVM IR and assembly |
| C-02 | Preprocessing/control flow | Macros, conditional compilation, loops, real CFG/optimization |
| C-03 | Pointers and arrays | Pointer expressions, stack/address observations where available |
| C-04 | Structures/dynamic allocation | Real allocation/free, structure layout and selected lifetime evidence |
| C-05 | **Multi-file C project** | Headers, multiple translation units, link symbols, call graph, meaningful execution |

### Group C: 5 matched pairs — 10 additional implementations

| Pair | C program ID | Python program ID | Difficulty | Teaching focus |
|---|---|---|---|---|
| PAIR-01 | PAIR-01-C | PAIR-01-PY | Very easy | Addition, functions, representation |
| PAIR-02 | PAIR-02-C | PAIR-02-PY | Easy | Conditional classification, branches |
| PAIR-03 | PAIR-03-C | PAIR-03-PY | Moderate | Recursive factorial/Fibonacci, call frames and numeric limits |
| PAIR-04 | PAIR-04-C | PAIR-04-PY | Advanced | Array/list aggregation, memory models |
| PAIR-05 | PAIR-05-C | PAIR-05-PY | Challenging | Bounded sorting or matrix computation, control flow/optimization/runtime |

For matched inputs, document C integer overflow boundaries, signedness, object/list versus array semantics, memory management and any unavoidable non-equivalence. C demonstrations must not rely on undefined behavior for their successful paths. Intentionally invalid error examples are separate testing fixtures and do not count toward the 20.

## 15. Testing and scientific correctness gates

### Automated test layers

1. **Schemas and parser unit tests:** IDs, offsets, token values, source spans, AST relations, CFG edges, tool stderr, version differences, mapping-class labels and bad outputs.
2. **Independent toolchain oracles:** separately run actual Clang/LLVM/CPython invocations; compare raw stage artifacts to normalized outputs, not merely frontend snapshots.
3. **Runtime trace correctness:** known outputs, calls/returns, stack and variable snapshots, selected bytecode mappings, exception paths and trace completeness/limits.
4. **Execution security:** blocked network/filesystem/privilege attacks; time, CPU/memory/pids/output limits; untrusted archives; malformed builds; job cancellation, cleanup, container escape probes appropriate to threat model.
5. **Contract/integration:** whole API job lifecycle, snapshot consistency, stale/canceled jobs, corrupted cache, import revisions, backend process crashes.
6. **Frontend component/browser E2E:** upload/import/classification, code selection, AST expansion, graph linking, stages, trace controls, comparison, mobile/desktop layouts, keyboard/reduced motion.
7. **All 20 E2E journeys:** inspect at least each declared important real stage; run approved examples and compare verified outputs, with blocked/partial states tested.
8. **Independent release audit:** fresh checkout, independent command execution and screenshot inspection, severity-ranked findings, regression repair and PASS/FAIL with residual risks.

**Evidence requirement:** every milestone report shows exact commands, tool versions, tests executed, counts/pass/fail, notable logs/screenshots, known issues, source files changed, git commit and the explicit acceptance verdict. Do not report PASS for an unexecuted test, a fixture-only fake backend or a non-reproducible screenshot.

## 16. Milestone-gated roadmap — autonomous but never blind

Intended pace: **intensive development over a few days**, but this is not a guarantee that all advanced systems instrumentation can be responsibly completed on that timescale. Do not hide incompleteness to meet a day count. Both languages and controlled execution must be real in the first substantial version. A milestone can contain implementation/verify/repair iterations, but do not quietly skip failed gates.

| Milestone | Scope | Non-negotiable exit gate |
|---|---|---|
| **M0 — Architecture & toolchain proof** | Detect actual ZCode/WSL/Clang/LLVM/Node/Python/Docker, write ADRs/contracts, C+Python sample analysis, isolated execution feasibility, latency/path tests | Both languages emit raw verifiable artifacts; agent tools work; execution risk/limitations documented |
| **M1 — Source workspace & GitHub import** | Paste, upload, ZIP, public commit-pinned import, file/target discovery, readiness classification, source snapshots | Real public repo import with no code execution; rejection tests for malicious inputs |
| **M2 — Core analyzers** | C preprocess/tokens/Clang AST/LLVM IR/assembly/object info; Python tokens/AST/scopes/bytecode; typed normalized outputs | Independent toolchain oracle tests for both languages; no fake mappings |
| **M3 — Visual observatory engine** | Monaco stage sync, real AST/CFG, graph navigation, semantic zoom, inspectors, minimap, error views, provenance UI | Moderately complex fixture is navigable, source-linked and legible; Playwright checks |
| **M4 — Safe execution & replay** | Docker admission gates, curated execution, **supported pasted-code execution after security verification**, Python/C runtime traces and timeline | Contained real C/Python runs, actual trace correctness, negative sandbox tests and cleanup PASS; otherwise FAIL/blocked |
| **M5 — MemoryScope & ProcessScope** | C frame/pointer/heap evidence, Python frame/object/GC samples, process lifetime/threads/syscalls as supported | Recorded data and limits shown; unsupported tracing unavailable, not fabricated |
| **M6 — OptimizationLab & comparison** | `-O0/O1/O2`, C IR/assembly diffs, independent Python bytecode comparison, 5 paired language journeys, controlled benchmarks | Real distinct compiler builds and comparable run inputs with caveats |
| **M7 — 20-demo suite & learning** | All 5+5+10 programs, guided journeys, 3 explanation levels, errors, optional Prediction Lab | Exactly 20 actual programs with automated relevant E2E checks |
| **M8 — Premium product polish** | Cohesive landing and all internal panels, responsive graph performance, accessibility, export/history, profiling | Real desktop/mobile browser screenshots; performance and accessibility acceptance |
| **M9 — Independent audit, targeted repairs & release** | Fresh source audit, security review, full real execution/visual verification, 20-demo regression, docs, release report | Evidence-backed PASS/FAIL and known limitations; release only if critical gates pass |

### Recommended execution sequencing within an intensive sprint

- **Early:** M0–M2 first; treat compiler truth, source snapshots and threat model as foundational. The landing page should not consume most of the initial effort.
- **Middle:** M3/M4; connect the first genuine end-to-end user journeys and safely run pasted input. Frontend polish and correctness testing proceed in parallel, not as replacement for M4.
- **Then:** M5–M7 and scientific comparison; scope the *instrumentation depth* to what is actually observable while retaining the documented feature intent.
- **Final:** M8/M9 independently inspect and repair, don't just trust the developer agent's self-assessment.

### Autonomous ZCode/Jet policy

- **Model:** use promotional GLM-5.3 Flash Max (or another accessible equivalent); do not assume GLM-5.3 Plus is available for free or in remote WSL. High reasoning for M0 security/contracts and difficult instrumentation; medium for bounded implementation; lower for cosmetic work if available. Monitor quota.
- Work in **normal Windows ZCode local project**, invoking WSL tools via `wsl.exe`. Do not move to remote WSL to solve a model configuration symptom.
- **One prompt per milestone** will be authored separately **after this README is approved**. Prompts must refer to this contract, include entry/exit gates, validation steps, skill discovery, failure behavior and git checkpoints.
- Before changing files: inspect working tree, existing status, previous ADRs and tests; create checkpoint; protect user changes.
- No auto-advance when an essential gate fails; record blocker and required human intervention. Do not bypass a test or security policy for a green badge.
- Keep `docs/PROJECT_STATUS.md`, `docs/DECISIONS/`, `docs/TEST_EVIDENCE/`, and a machine-readable milestone manifest with last pass state, hash and git revision to survive context compaction.
- Discover installed ZCode skills/plugins **before** naming or invoking them. Desired capability categories: architecture review, compiler integration, secure execution, browser E2E, frontend product quality, performance, contract tests, checkpoint/recovery, security audit and token discipline. Never invent skill IDs.
- Each milestone report includes: accomplishments; changed files; exact tests and pass/fail counts; screenshots if visual; versions; blockers; source-hash provenance; risks; security status; Git checkpoint; reproducible run steps; and explicit PASS/FAIL.
- Protect promotional token budget: narrow scopes, clear acceptance tests, no redundant rewrite loops, separate implementation and independent audit sessions, and concise context handoffs.

## 17. First-version delivery contract vs complete final scope

**First substantial working version (no partial-language façade):** C/Python paste, true tokens/AST and C LLVM IR/Python bytecode, meaningful interactive source-to-representation view, actual controlled run and output for supported pasted code once sandbox security passes, real Python call/line/return trace and available C debug observations, deterministic example journeys, import/readiness UI and reproducible artifact storage. Do not call it complete if source code execution is just mock output.

**Full target:** all modules, public-repository import, advanced graphs, C machine-code and link inspection, supported MemoryScope/ProcessScope, OptimizationLab, paired comparison, all 20 tested programs, polished product, secure private web demo plan, independent audit. Capability restrictions must be explicitly and honestly documented, not silently replaced by approximations.

## 18. Initial repository structure (proposed, adjust with ADR)

```text
E:\ComplieVista\                    # actual verified path (product name: CompileVista)
  README.md                         # This authoritative specification
  AGENTS.md                         # Short coding-agent rules; links to README
  .gitignore
  .env.example                      # No secrets or API keys
  frontend/
    src/{app,components,features,graphs,editor,timeline,styles,types}/
    tests/
  backend/
    app/{api,core,models,contracts,services,workers,adapters,security}/
    tests/{unit,contract,integration,security}/
  toolchains/
    c/                              # Clang/LLVM invocations and parsers
    python/                         # CPython artifact and trace collectors
  sandbox/
    images/                         # Pinned Dockerfiles and execution policy
    policies/                       # Allowlisted execution profiles
    fixtures/                       # Adversarial and security tests
  demos/
    python/                         # PY-01..PY-05
    c/                              # C-01..C-05
    pairs/                          # PAIR-01..PAIR-05, 10 programs
    manifests/
  docs/
    ARCHITECTURE.md
    SECURITY.md
    API_CONTRACTS.md
    TOOLCHAIN_PROVENANCE.md
    BENCHMARKS.md
    VISUAL_SYSTEM.md
    DEMO_MATRIX.md
    PROJECT_STATUS.md
    DECISIONS/
    TEST_EVIDENCE/
    AUDITS/
  scripts/
    dev/                            # Windows/WSL launch & verify helpers
    ci/                             # Test/format/security runners
  .github/workflows/
```

The README is the **canonical scope**; detailed operational docs may be split out if its size impairs readability, but no critical requirement may disappear during refactoring. The repository is initially local; GitHub push happens after release audit and secret review.

## 19. Risk register and architecture-change triggers

| Risk | Severity | Mitigation / decisive evidence |
|---|---|---|
| Untrusted code escape or host damage | **Critical** | Threat model, narrow container profiles, negative adversarial tests, independent review; disable unsafe execution if gate fails |
| C AST→optimized IR mismatch | High | Separate exact vs derived links, preserved raw artifacts, fallback to source/IR navigation without fabricated edges |
| Python bytecode/trace mismatch | High | Version pin and independent `dis`/trace checks; no invented opcode event correspondence |
| GDB `ptrace`/debugger policy conflicts | High | Capability probes with curated fixtures; separate restricted debugger profiles; show unavailable when unsupported |
| Memory/OS observations incomplete in WSL2 | High | Capability matrix by environment; use verified `/proc`/`strace`/tracemalloc/GDB data only |
| External repo/build complexity | High | Commit pin, target classifier, dependency gating, no auto builds/scripts |
| Windows↔Linux filesystem slowness | Medium–High | Native Linux job staging, measured benchmarks; alter layout only on measured blocker |
| Huge graph/trace makes browser unusable | High | ELK workers, progressive disclosure, trace chunking, render benchmarks, tests |
| Toolchain version changes | Medium | Version pins, schema-versioned parsers, provenance, fixture regression |
| Localhost/WSL interop failure | Medium | M0 explicit API/connectivity probe and alternate routing |
| Long autonomous agent context/quotas | High | Narrow milestone prompts, independent gates, Git checkpoint/status persistence |
| Attractive UI masking missing backend | High | Browser E2E uses real saved artifacts; release audit inspects active source and endpoints |
| Unsupported private HTTPS deployment/exposure | High | Authenticate, enforce TLS and quotas, security gate; no public arbitrary execution by default |

**Trigger to revisit the current Windows+WSL architecture:** repeated measured cross-filesystem bottlenecks not solved by staging; inability of the ZCode local agent to operate required tools; required debugger observability unavailable in WSL; or demonstrated sandbox limitations for a requested release scope. Escalate narrowly (native Linux storage, dedicated VM/host, or stricter external sandbox), with cost/benefit evidence. A different Linux desktop theme is not itself a reason.

## 20. Definition of done and release criteria

The product is not release-ready unless:

- Both languages are genuinely analyzed using authoritative tools; C native stages and Python bytecode stages are not falsely conflated.
- Every displayed token/AST/IR/instruction/trace/memory measurement is supported by real artifact/observation or visibly marked explanatory/approximate.
- Pasted-code execution uses an independently tested confinement boundary; unsafe mode is disabled rather than mislabeled secure.
- All 20 mandatory programs have their declared E2E analyses and expected-output checks.
- Real public-repository import works with safe pinned metadata and appropriate unsupported states.
- Main workspace is fully interactive, keyboard accessible, performant, and as visually finished as the landing page.
- Optimization comparisons and benchmarks are genuine and appropriately qualified.
- All critical and high severity defects are resolved or explicitly block release; no secrets in Git.
- A clean checkout can be set up using documented free tooling; private HTTPS deployment has a distinct security plan.
- Final independent audit documents raw evidence, executed tests, versions, screenshots, limits and an explicit verdict.

**First action when implementation is authorized:** implement **M0 only**—toolchain and sandbox feasibility proofs, contracts, baseline tests, repository scaffolding, status/ADR files. Do not generate M1–M9 implementation code from a one-shot kickoff; queue later prompts only after prior acceptance gates are recorded.

## 21. Private HTTPS deployment architecture (future phase)

The local prototype remains the first delivery. A later **private authenticated demonstration** should run on a separately provisioned, supported Linux host or VM, not by simply exposing Windows/WSL Docker's local control API to the internet. A defensible deployment design is:

```text
Invited browser → HTTPS reverse proxy/TLS → authenticated web frontend/API
                                                |
                                      bounded job coordinator
                                                |
                              isolated worker host / execution boundary
                                                |
                                     sanitized evidence and results
```

Require authentication with authorized invited accounts, rate/size quotas, short-lived sessions, security headers, CSRF protection where relevant, audit logs, artifact retention limits, request cancellation, worker/network egress limits, and HTTPS certificate management. Place the container orchestrator on a private administrative surface; never grant a browser session arbitrary Docker command execution. Do not expose local home directories, repository paths, debugger ports, or the Docker daemon. Consider a separate worker host if threat modeling shows Docker-in-WSL is unsuitable for remote users. **No paid hosting is presumed:** choose hosting only after checking free-tier resource, policy and isolation constraints; an unavailable suitable free option means private local-only demonstration until an adequate host is obtained. Add a documented emergency disable switch for code execution and a complete deployment reproducibility test.

The production/private-demo security review is **independent of** the successful local `hello-world` test and local execution gate. A private URL with login does not make unsafe execution safe.

## 22. Academic positioning and possible future evaluation

Appropriate research themes include programming-language education, visual program analysis, mapping quality across compiler optimization levels, trace-overhead analysis, graph interaction scalability, and differences between C and CPython execution semantics. An eventual controlled learning study could compare student understanding with/without synchronized visualizations; its design, consent and evaluation are separate from routine application testing. Benchmark results must not be misrepresented as scientific causal findings.

## 23. Authoritative reference documentation

These external references inform choices; live APIs/version details must be tested in M0 and pinned to observed capabilities:

- Clang toolchain stages: https://clang.llvm.org/docs/Toolchain.html
- Clang AST: https://clang.llvm.org/docs/IntroductionToTheClangAST.html
- Clang command reference: https://clang.llvm.org/docs/ClangCommandLineReference.html
- LLVM getting started: https://llvm.org/docs/GettingStarted.html
- Python 3.12 tracing: https://docs.python.org/3.12/library/sys.html#sys.settrace
- Python monitoring: https://docs.python.org/3.12/library/sys.monitoring.html
- CPython bytecode: https://docs.python.org/3.12/library/dis.html
- WSL filesystem interoperability/performance: https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop
- Docker resource limits: https://docs.docker.com/engine/containers/resource_constraints/
- Docker CLI/security controls: https://docs.docker.com/reference/cli/docker/container/run/
- Docker rootless security discussion: https://docs.docker.com/engine/security/rootless/
- GitHub repository API: https://docs.github.com/en/rest/repos/contents
- React Flow: https://reactflow.dev/

---

### The success criterion in one sentence

**CompileVista must let a person explore genuine C and Python source-to-execution evidence through a beautiful, interactive, reproducible and security-conscious observatory—without confusing educational explanation with an observed fact.**
