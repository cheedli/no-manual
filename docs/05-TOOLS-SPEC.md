# Tools spec — No Manual

All tools live in toolset `no-manual`, return JSON strings, never raise.
Every result includes `"project_id"` and a short `"next"` hint for the agent.
Errors: `{"error": "<plain sentence>", "hint": "<what to do next>"}`.
Paths in results are **absolute** so the agent can emit `MEDIA:<path>` lines.

Write each schema's `description` for the model: what it does + when to call.

---

## nm_start_project
Create a furniture project. Call first, as soon as the user wants help
assembling or reassembling furniture.
```json
{"type":"object","properties":{
  "category":{"type":"string","enum":["closet","wardrobe","bookcase","cabinet","nightstand","desk","crib","bunk_bed","loft_bed","bed","high_chair","changing_table","chair","sofa","other"],
              "description":"What the user says it is. Use 'other' if unclear."},
  "state":{"type":"string","enum":["assembled","in_pieces","unknown"]},
  "title":{"type":"string","description":"Short name, e.g. 'bedroom closet'"}
},"required":["category"]}
```
Returns: `{project_id, safety_status, allowed_modes[], next}`
- Runs the safety gate (doc 08). Blocked categories → `allowed_modes:["manual"]`.

## nm_add_photos
Attach photos to the project. Call whenever the user sends photos for it.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "image_paths":{"type":"array","items":{"type":"string"},"description":"Local paths of images the user sent"},
  "recent":{"type":"boolean","description":"If paths are unknown, take images received in this chat since the last call"},
  "kind":{"type":"string","enum":["overview","panel","hardware","label","stage","check"]},
  "caption":{"type":"string"}
},"required":["project_id","kind"]}
```
Returns: `{added: n, photo_ids[], total_by_kind{}, next}`
- Copies files into the project dir, records sha256, rejects non-images and
  files > 20 MB, de-duplicates by hash.

## nm_set_details
Store facts the user gives: outer dimensions, counts, corrections.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "outer_dims":{"type":"object","properties":{"width":{"type":"number"},"height":{"type":"number"},"depth":{"type":"number"},"unit":{"type":"string","enum":["mm","cm","in"]}}},
  "notes":{"type":"string"}
},"required":["project_id"]}
```

## nm_identify
Read labels/stamps/shape from photos and propose search queries for the
official manual. Call before any other mode.
```json
{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}
```
Returns: `{brand, product_name, article_numbers[], confidence, search_queries[], next}`
- `next` tells the agent to run `web_search` with the queries and look for a
  PDF manual from the manufacturer or a reputable manual archive.

## nm_attach_manual
Attach the official manual once found.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "pdf_url":{"type":"string","description":"https URL of the PDF manual"},
  "pdf_path":{"type":"string","description":"Local PDF path if already downloaded"},
  "source_page":{"type":"string","description":"Where it was found, for attribution"}
},"required":["project_id"]}
```
Returns: `{pages: n, steps: n, first_step_image, next}`
- https only, ≤ 30 MB, must be `application/pdf`. Renders pages to PNG
  (`pypdfium2`, 150 dpi). Plan source = `manual`, confidence 0.95.

## nm_record_stage
Disassembly recorder: call once per stage while the user takes the furniture
apart. Stage 0 = fully assembled.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "image_paths":{"type":"array","items":{"type":"string"}},
  "recent":{"type":"boolean"},
  "what_was_removed":{"type":"string","description":"User's words, e.g. 'took off the doors'"}
},"required":["project_id"]}
```
Returns: `{stage_index, described: {...}, next}` — vision compares with the
previous stage and records removed parts/hardware and orientation notes.

## nm_finish_recording
Turn recorded stages into an assembly manual (reverse order).
```json
{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}
```
Returns: `{steps: n, step_images[], warnings[], next}`
- Each step image = the "after" photo for that assembly step with a header
  bar ("Step 3 of 9 — Attach the doors"), hardware callout chips, and arrows
  if available. Plan source = `recorder`, confidence 0.85.

## nm_extract_parts
Solver mode: read panels and hardware from photos.
```json
{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}
```
Returns: `{parts:[{id, role_guess, dims_mm, holes_summary, confidence}], hardware:[...], questions[], next}`
- Requires `outer_dims` set (else returns error asking for them).
- `questions` are the minimal confirmations needed (e.g. "Is P2 the same
  height as the closet (180 cm)? yes/no").

## nm_confirm_parts
Apply the user's answers/corrections to parts.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "updates":{"type":"array","items":{"type":"object","properties":{
    "part_id":{"type":"string"},"role":{"type":"string"},"quantity":{"type":"integer"},
    "length_mm":{"type":"number"},"width_mm":{"type":"number"},"thickness_mm":{"type":"number"}}}},
  "hardware":{"type":"array","items":{"type":"object","properties":{"kind":{"type":"string"},"count":{"type":"integer"}}}}
},"required":["project_id"]}
```

## nm_solve
Run the template solver (doc 06). Blocked by the safety guard for blocked
projects.
```json
{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}
```
Returns: `{confidence, steps:n, hardware_check:{ok, lines[]}, warnings[], questions[], next}`
- confidence < 0.6 → `questions` non-empty and `next` says ask the user.

## nm_render_steps
Render all steps (PNG for chat + scene JSON for Desktop).
```json
{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}
```
Returns: `{overview_image, scene_path, step_images[], next}`
- `next`: "Send overview_image with MEDIA:, then step 1 only."

## nm_get_step
Get one step to send to the user.
```json
{"type":"object","properties":{"project_id":{"type":"string"},"index":{"type":"integer","description":"1-based; omit for current step"}},"required":["project_id"]}
```
Returns: `{index, total, title, instruction, image_path, scene_path, hardware_used[], checks[], next}`

## nm_check_step
Check the user's photo of a completed step.
```json
{"type":"object","properties":{
  "project_id":{"type":"string"},
  "index":{"type":"integer"},
  "image_paths":{"type":"array","items":{"type":"string"}},
  "recent":{"type":"boolean"}
},"required":["project_id"]}
```
Returns: `{ok, issues:[{severity:"stop"|"warn"|"info", text}], confidence, advance:bool, next}`
- `ok && confidence ≥ 0.6` → advance current_step. Any `stop` issue → do not
  advance; `next` says explain the fix and ask for a new photo.
- Low confidence → ask for a clearer/closer photo, don't guess.

## nm_status
List or inspect projects (also used by `/nomanual`).
```json
{"type":"object","properties":{"project_id":{"type":"string"}}}
```
Returns: projects list or one project's summary (mode, state, step x/y).

---

## Slash command `/nomanual`
- `/nomanual` → list projects for this user.
- `/nomanual resume <id>` → summary + current step (returns text; the agent
  continues).
- `/nomanual delete <id>` → deletes project data (confirm first via the
  host's pick-option API if available; otherwise require `delete <id> yes`).
