# ADR-001: Template solver instead of general 3D assembly search
**Date:** 2026-11-06 · **Status:** Accepted

## Context
Solving an arbitrary assembly from photos (pose estimation, hole matching in
3D, search over orderings) is a research problem and would not be reliable
in five days. Reliability is a judging axis and a wrong-but-confident answer
is worse than none.

## Decision
Model every part as a rectangular board and fit parts to a small set of
carcass templates (T1 sides-embrace, T2 top-caps, T3 divider). Holes are
supporting evidence; dimensions + outer dims drive classification.

## Consequences
- Positive: deterministic, explainable, unit-testable; covers closets,
  bookcases, cabinets, nightstands.
- Negative: no drawers with runners, chairs, beds, unusual designs.
- Risk: users bring out-of-scope pieces → solver returns low confidence and
  the agent falls back to recorder/manual modes.
