# ADR-007: Safety gate fails closed for child and load-bearing furniture
**Date:** 2026-11-06 · **Status:** Accepted

## Context
Incorrect assembly of cribs, bunk beds, high chairs or anything people sit,
sleep or climb on can cause injury.

## Decision
If either the user's category or vision's category guess is in the blocked
set, only the manual finder is allowed. Enforced in handlers and in a
`pre_tool_call` hook. Tall furniture always gets an anti-tip step.

## Consequences
- Positive: answers the obvious reviewer/judge objection; responsible product.
- Negative: some legitimate users are turned away from generated steps.
