# ADR-006: SQLite via plugin_db + files in plugin_data_dir
**Date:** 2026-11-06 · **Status:** Accepted

## Context
Projects must survive sessions and restarts; Hermes provides a per-plugin
data root and SQLite helper that survive plugin updates.

## Decision
Store structured state in `plugin_db("no-manual")` and photos/images in
`plugin_data_dir("no-manual")/projects/<id>/`. Never write into the plugin
directory.

## Consequences
- Positive: resumable projects; easy deletion; catalog-compliant.
- Negative: schema migrations needed if fields change — keep a `schema_version`.
