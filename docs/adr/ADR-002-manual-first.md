# ADR-002: Mode order — manual finder, then recorder, then solver
**Date:** 2026-11-06 · **Status:** Accepted

## Context
The official manual is always the most accurate and safest source; the
user's own disassembly photos are the next most reliable; solving from a pile
is the least reliable.

## Decision
The agent always tries identification + manual search first, then the
disassembly recorder if the piece is still assembled, and the solver only
when neither applies.

## Consequences
- Positive: best answer in most real cases; strong safety story.
- Negative: the flashiest mode (solver) is not the default; the demo shows it
  deliberately with an unbranded piece.
