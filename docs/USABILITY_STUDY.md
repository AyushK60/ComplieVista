# Usability study protocol (planned — no data collected yet)

**Purpose.** Test whether CompileVista helps a student answer concrete questions about how a
program is compiled and run, compared with working without it. This is a *protocol*; nothing
in this document is a result.

**Participants.** 6–10 undergraduates who have taken an introductory programming course and
have not taken a compilers course. Recruit by invitation; participation is voluntary and
can stop at any time. No personal data beyond a participant code is recorded.

**Design.** Within-subject, two conditions (order counterbalanced):
- *Tool*: CompileVista, 5-minute orientation.
- *Baseline*: their usual means (editor, documentation, search) — no CompileVista.

Two matched task sets (A, B) of similar difficulty, assigned to conditions in alternating order.

**Tasks (example set A, C program).**
1. Which source line does the first `call` instruction in the assembly come from?
2. After optimization, does the line `int unused = 42;` still produce any code? Why might that be?
3. What does the syntax tree look like for the loop condition?
4. In what order are the functions called when the program runs?
5. A Python variant: how many bytecode instructions does the function body compile to, and which one performs the addition?

Task sets use a fixed answer key checked against the real toolchain (not against the tool).

**Measures.** Per task: correct / incorrect / gave up; time to answer (stopwatch); self-rated
confidence (1–5). Per condition: System Usability Scale (10 items), and two open questions
(what was most useful / most confusing).

**Analysis plan.** Report counts and medians with the individual points; with this sample size
use paired descriptive statistics and effect sizes, not significance claims. Report every
participant, including failures and abandoned tasks.

**Threats to validity.** Small convenience sample; practice effects despite counterbalancing;
task sets not proven equivalent; the first author is the facilitator; the answer key
depends on one compiler version.

**Ethics.** Check whether the institution requires review for classroom-style usability
testing before recruiting; obtain informed consent; store only participant codes.

**Status.** Not started. Needs: final task sets with answer keys, consent text, a facilitator
script, and ethics clearance if required.
