# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Mixed audience: evaluators (graders, reviewers, portfolio/thesis judges), students learning compilers, and professors teaching them. They arrive at a local-first tool (served on 127.0.0.1) and need to grasp in seconds what it shows and try one demo program.

## Product Purpose
CompileVista is a local-first observatory that shows the real artifacts a toolchain produces for code you bring: tokens, syntax trees, LLVM IR, assembly and objects for C (Clang/LLVM 18); tokens, AST, code objects and bytecode for Python (CPython 3.12); plus a recorded, replayable run in a sandbox. Success: a visitor understands "see how code becomes execution" and opens a demo or pastes code.

## Positioning
Nothing is simulated. Every artifact carries tool and version, invocation, exit code and SHA-256; when a tool cannot provide something the UI says "unavailable". C and Python pipelines stay distinct (Python has no LLVM O-levels; bytecode is not machine code).

## Operating Context
Windows 11 + WSL2 + Docker Desktop; Setup.cmd / Start.cmd. Everything binds to 127.0.0.1. Pages: Home, Workspace, Demo Library (20 programs), Compare, About.

## Capabilities and Constraints
React + TypeScript + Vite, React Flow, CodeMirror 6. Existing facts to preserve on the landing: 76/76 metrics match an independent oracle, 20 real programs, 0 bytes leave the machine; media in frontend/public/media (real output screenshots). No invented claims, customers or benchmarks.

## Brand Commitments
Name: CompileVista. Honest-evidence voice. No paid APIs or hosted fonts at runtime (fonts via @fontsource).

## Evidence on Hand
Real captures: frontend/public/media/{tokens,ast,bytecode,run-light,run-dark}.jpg; docs/media/*.gif; 20 curated demos.

## Product Principles
1. Real artifacts only; label anything unavailable.
2. Show the mechanism immediately, before explaining it.
3. C and Python are distinct pipelines.
4. Local-first and private by default.

## Accessibility & Inclusion
axe-core scan of 12 screens and layout test at seven widths already exist; keep them passing; honour prefers-reduced-motion.
