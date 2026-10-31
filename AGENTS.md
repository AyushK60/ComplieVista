# AGENTS.md — coding-agent rules (short)

Full contract: `README.md` (authoritative scope and acceptance gates). Do not narrow it.

1. Work only in this repository (`E:\ComplieVista` ↔ `/mnt/e/ComplieVista`). One repo, no
   renames, protect user files.
2. Linux tools via `wsl.exe -d Ubuntu-24.04 --` with argv arrays; never interpolate
   untrusted input into shell strings.
3. Static inspection never executes fixtures: no exec/eval/import of analyzed code.
4. Every artifact claim carries: tool + version, invocation, exit code, SHA-256, counts,
   limitations. Use the ADR-0002 enums. Never invent tokens/AST/IR/bytecode/events.
5. C and Python pipelines stay distinct. Python bytecode is not machine code; Python has
   no LLVM O-levels.
6. Docker socket access = host privilege; trusted orchestration only; never enter a
   container. Pasted-code execution stays BLOCKED until the M4 security gate passes.
7. No milestone auto-advance. Failed gate ⇒ record FAIL/BLOCKED with reproducer, then stop.
   No test is reported PASS unless it actually ran.
8. Keep `docs/PROJECT_STATUS.md`, `docs/milestones/*.json`, `docs/TEST_EVIDENCE/` current;
   commit checkpoints with meaningful messages.
9. No paid APIs, no secrets in git, no large generated binaries committed.
