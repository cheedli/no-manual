# Submission — catalog PR, X post, form

## 0. Deadline and steps (from the official announcement)
Due **Wed 11 Nov 2026, 17:00 EST (22:00 UTC)**.
1. Open a PR that adds your plugin to the Hermes plugin catalog
   (guide: http://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).
2. Post a demo video on X (< 90 s, showing the plugin working) and tag @NousResearch.
3. Submit both links through the form: http://form.typeform.com/to/FwJLvOln
You can submit the form as soon as the PR is open. Catalog checks run when a
maintainer starts them; entries are reviewed every few days. Questions:
Nous Research Discord (http://discord.gg/nousresearch).

## 1. Catalog entry — `plugin-catalog/no-manual.yaml`
Fork `NousResearch/hermes-agent`, add exactly this one file. Field names
follow existing entries (check `plugin-catalog/README.md` "entry schema" at
the time you submit).
```yaml
name: no-manual
title: No Manual
repo: https://github.com/<you>/no-manual
sha: <full 40-character commit sha you tested>
description: "Furniture with no instructions? Send photos and Hermes finds the official manual, turns your disassembly photos into a manual in reverse, or works out flat-pack assembly (closets, bookcases, cabinets) from the parts, then coaches you step by step and checks a photo of each step. Steps arrive as images in chat; Hermes Desktop shows an interactive 3D step viewer. Never generates instructions for children's furniture or anything people sit, sleep or climb on. Disclosure — photos you add are sent to your own configured model provider through Hermes (ctx.llm) to read panels, labels and step photos; manual PDFs found by Hermes's web search are downloaded over https (max 30 MB); photos, manual pages and generated images are stored in <HERMES_HOME>/plugin-data/no-manual/ and deleted with /nomanual delete; the Desktop half bundles three.js (source in desktop/src/); no shell commands, no background processes, no telemetry, no credentials stored."
maintainer: <your GitHub handle>
tier: community
category: tools
requires_hermes: ">=<version you tested on>"
docs_url: https://github.com/<you>/no-manual#readme
version: "0.1.0"
capabilities:
  provides_tools:
    - nm_start_project
    - nm_add_photos
    - nm_set_details
    - nm_identify
    - nm_attach_manual
    - nm_record_stage
    - nm_finish_recording
    - nm_extract_parts
    - nm_confirm_parts
    - nm_solve
    - nm_render_steps
    - nm_get_step
    - nm_check_step
    - nm_status
  provides_hooks:
    - pre_llm_call
    - pre_tool_call
  provides_middleware: []
  requires_env: []
# optional, recommended:
# image: https://raw.githubusercontent.com/<you>/no-manual/<sha>/assets/banner.png
# screenshots: [ ... raw URLs at the pinned sha ... ]
```
Also put the same `requires_hermes` floor in `plugin.yaml` (rule 14).

## 2. PR description template
```
Adds No Manual (plugin-catalog/no-manual.yaml) — Hermes Agent Plugin Hackathon entry.

What it does
- Helps people assemble furniture that has no instructions: finds the official
  manual, turns disassembly photos into a reversed manual, or solves flat-pack
  carcass furniture from photos of the parts; then coaches step by step and
  checks a photo of each step.

Hermes surfaces used
- 14 tools (toolset no-manual), hooks pre_llm_call (skill hint) and
  pre_tool_call (safety guard), a bundled skill (no-manual:no-manual-guide),
  slash command /nomanual, ctx.llm structured calls with images,
  plugin_data_dir/plugin_db storage, MEDIA: delivery, Desktop tool media
  renderer (3D step viewer) + dashboard plugin_api.py route.

Disclosures (rule 13)
- <paste the disclosure block from docs/08 §4>

Safety
- Generated instructions are never produced for children's furniture or
  anything people sit, sleep or climb on (manual-only path). Tall furniture
  always ends with an anti-tip step.

Validation
- `hermes plugins validate <path> --install-deps` passes at the pinned sha
  (paste output summary).

Screenshots
- <overview image, step image, Desktop 3D viewer, step check "stop">
```

## 3. Submission description (for the form, if a text field exists)
Problem: people end up with furniture they can't assemble — lost manuals,
second-hand pieces, moves. Solution: a Hermes plugin that finds the manual,
records your disassembly, or solves flat-pack assembly from photos, then
checks each step from your photo. Tech: Python Hermes plugin (tools, hooks,
skill, ctx.llm vision), Pillow renderer, pypdfium2, three.js Desktop viewer.
Team: <you>. Demo: <X link>. Repo: <GitHub link>. Catalog PR: <PR link>.

## 4. Final checklist
- [ ] Repo public, MIT license, README with disclosures, results table, screenshots
- [ ] `hermes plugins validate . --install-deps` green at the pinned sha
- [ ] Catalog PR open, CI green (or requested), description complete
- [ ] Video < 90 s on X, tags @NousResearch, shows the plugin working
- [ ] Form submitted with PR link + X link
- [ ] No `[TBD]` left in README/PR
