# ADR-005: Vision (ctx.llm) for perception only
**Date:** 2026-11-06 · **Status:** Accepted

## Context
LLMs are good at reading photos into rough structure, weak at precise
geometry and consistent ordering.

## Decision
Use `ctx.llm.complete_structured` with images only to extract labels, parts,
hardware counts, stage changes and step-check verdicts, always into JSON
schemas. All geometry, ordering, counting and safety decisions are code.
User-provided outer dimensions anchor the scale.

## Consequences
- Positive: host-owned credentials (no keys), follows the user's provider,
  testable with a fake LLM.
- Negative: requires a vision-capable model; documented in README.
