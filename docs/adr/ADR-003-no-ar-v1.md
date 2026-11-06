# ADR-003: No AR in v1 — step images in chat + 3D viewer in Desktop
**Date:** 2026-11-06 · **Status:** Accepted

## Context
Mobile AR needs native apps or WebXR (poor iOS browser support) and would
consume most of the build time. Users already talk to Hermes in messaging apps.

## Decision
Deliver steps as PNG images through the Hermes gateway (`MEDIA:` lines) and
an interactive three.js viewer in Hermes Desktop. AR goes on the roadmap.

## Consequences
- Positive: works on every Hermes surface; feasible in time.
- Negative: less "magic" than AR; mitigated by the 3D viewer wow moment.
