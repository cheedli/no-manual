# ADR-004: Draw steps from geometry (Pillow), never with image generation
**Date:** 2026-11-06 · **Status:** Accepted

## Context
Generated images hallucinate parts and holes; reviewers and judges will ask
where pictures come from.

## Decision
Render IKEA-style line art from the solver's assembly states with a small
axonometric renderer in Pillow (painter's algorithm), plus scene JSON for the
Desktop viewer. Recorder steps reuse the user's own photos.

## Consequences
- Positive: pictures always match the real parts; no extra provider or cost.
- Negative: simpler visuals than a CAD tool; acceptable for flat boxes.
