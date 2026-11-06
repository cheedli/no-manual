# Feature specs — No Manual

Each feature lists acceptance criteria (AC) as testable conditions.
"Unit" = pytest without Hermes; "E2E" = manual run in Hermes (CLI or Telegram).

---

## F1 — Intake
The agent creates a project, collects photos, asks whether the furniture is
assembled or in pieces, and records category and outer dimensions.

- AC1 (unit): `nm_start_project` creates a row and a project dir; returns `project_id`.
- AC2 (unit): `nm_add_photos` copies files, de-duplicates identical images by sha256, rejects non-image files and files > 20 MB with a plain error.
- AC3 (E2E): sending 3 photos on Telegram results in 3 photos attached (via paths, or via `recent: true` fallback).
- AC4 (E2E): if state is unknown, the agent asks "Is it still assembled or already in pieces?" before choosing a mode.
- AC5 (unit): `nm_set_details` normalises dims to mm (cm×10, in×25.4) and rejects values outside 50–3000 mm.

## F2 — Safety gate
- AC1 (unit): categories `crib, bunk_bed, loft_bed, bed, high_chair, changing_table` → `safety_status = blocked_child_or_load`, `allowed_modes = ["manual"]`.
- AC2 (unit): `pre_tool_call` guard blocks `nm_solve`, `nm_render_steps`, `nm_finish_recording` for blocked projects with a plain message.
- AC3 (unit): if vision during identify/extract detects child furniture (`category_guess` in blocked set, confidence ≥ 0.5) on a non-blocked project, the project is re-classified to blocked and the tool result explains why.
- AC4 (unit): every solver/recorder plan for tall furniture (height ≥ 75 cm) ends with an **anti-tip wall-anchoring step**.
- AC5 (E2E): asking to solve a crib yields a polite refusal plus an offer to find the official manual.

## F3 — Manual finder
- AC1 (E2E): `nm_identify` on a photo of a label with a visible article number returns that number in `article_numbers`.
- AC2 (unit): `nm_attach_manual` with a local 12-page PDF produces 12 PNG pages and a plan with source `manual`.
- AC3 (unit): rejects http (non-https) URLs, non-PDF content types, and > 30 MB downloads.
- AC4 (E2E): for ≥ 3 of 5 branded test pieces the agent finds and attaches the official manual without user help beyond photos.
- AC5: the manual's source URL is stored and shown to the user ("Official manual from <domain>").

## F4 — Disassembly recorder
- AC1 (unit): stages [0..n] reverse into n steps; step k uses stage n−k+1 → n−k transition.
- AC2 (unit): each step image has a header "Step k of n — <title>", hardware chips, and the user's photo; renders at 1080 px wide.
- AC3 (E2E): recording a real piece in ≥ 5 stages yields a manual a second person can follow.
- AC4: if a stage photo looks identical to the previous one (vision says nothing removed), the tool asks what was removed instead of creating an empty step.

## F5 — Part extraction (solver mode)
- AC1: requires outer dims; otherwise returns an error asking for width/height/depth.
- AC2 (unit, with a mocked LLM): parses the structured response into `Part`/`Hardware` objects; invalid JSON → retry once with a stricter prompt, then return a clear error.
- AC3 (unit): dimensions are reconciled against outer dims (e.g. a part within 3% of the height is a candidate side/door/back); conflicts produce `questions`.
- AC4: at most 4 questions per round, each answerable with yes/no or a number.
- AC5 (E2E): on a real 6–10 panel cabinet, after ≤ 2 rounds of questions, all parts have a role.

## F6 — Template solver
Details in doc 06.
- AC1 (unit): for each fixture in `fixtures/` (bookcase, closet, nightstand, cabinet), the solver outputs the expected step order.
- AC2 (unit): unknown/extra parts produce a warning, not a crash.
- AC3 (unit): confidence < 0.6 when roles are ambiguous; `questions` explain the ambiguity.
- AC4 (unit): the plan always starts with "sort parts and hardware" and ends with anti-tip anchoring for tall furniture.

## F7 — Hardware count check
- AC1 (unit): cam housings in panels vs cam locks in hardware → `ok` when equal; otherwise a line like "Holes for 8 cam locks, but 6 cam locks found. Missing 2 × cam lock (≈15 mm)."
- AC2 (unit): dowel holes are counted as pairs across mating faces (one dowel per pair).
- AC3: mismatches never block solving; they appear as warnings and in step text where the missing part is used.

## F8 — Step renderer
Details in doc 07.
- AC1 (unit): each step PNG is 1080×1350, white background, black line art, new parts highlighted, step number top-left, hardware callouts bottom.
- AC2 (unit): golden-image test on 2 fixtures (tolerance: pixel diff < 2%).
- AC3 (unit): scene JSON validates against `core/scene.py` schema (version, units, parts[], steps[] with transforms).
- AC4: rendering a 12-step plan takes < 10 s on a laptop.

## F9 — Live step check
- AC1 (unit, mocked LLM): `stop` issue → `advance=false`; ok + conf ≥ 0.6 → advance.
- AC2 (E2E): a deliberately upside-down panel is flagged in ≥ 4 of 5 trials.
- AC3: blurry/dark photo → asks for a better photo (confidence < 0.6), never passes.
- AC4: the check prompt includes the expected image and the step's `checks[]`.

## F10 — Project state
- AC1 (unit): project survives process restart (sqlite).
- AC2 (E2E): "Let's continue the closet" in a new session finds the project via `nm_status` and resumes at the right step.
- AC3: `/nomanual delete <id>` removes rows and the project directory.

## F11 — Desktop 3D step viewer
- AC1: Desktop shows an interactive viewer when a `MEDIA:` line references our scene JSON (or a step PNG whose result includes `scene_path`).
- AC2: orbit (drag), zoom (wheel), previous/next step, "explode" toggle; resizes with the pane.
- AC3: uses theme variables only; no console errors; loads < 10 s.
- AC4: falls back to the built-in renderer for any file we don't own.

## F12 — Bundled skill
- AC1: `skill_view("no-manual:no-manual-guide")` loads.
- AC2: the `pre_llm_call` hint fires on furniture-assembly messages (EN + FR + AR + ES keywords) and not on unrelated messages (unit-tested keyword matcher).
- AC3 (E2E): with only the skill as guidance, the agent runs the full flow in the right mode order: safety → identify/manual → recorder or solver → coaching.
