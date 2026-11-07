# No Manual — a Hermes Agent plugin

**Furniture with no instructions? Send Hermes a few photos.**
No Manual finds the official manual, turns your disassembly photos into a manual in reverse, or
works out flat-pack assembly from the parts. Then it coaches you step by step and checks a photo of
each step before you move on.

## What it does
- 🔎 **Finds the real manual** from labels, stamped article numbers and shape, using Hermes's web
  search. It asks you to confirm the match before using it.
- 📸 **Records your disassembly** (moving house?) and reverses it into instructions made from your
  own photos.
- 🧩 **Solves flat-pack furniture** (closets, wardrobes, bookcases, cabinets, nightstands) from
  photos of the parts and your tape-measure dimensions, and draws IKEA-style step images from the
  geometry.
- ✅ **Checks every step** from your photo and stops you before a mistake costs an hour ("Stop —
  that panel is face down; the holes should face up").
- 🧮 **Counts hardware**: "Holes for 8 cam locks, but 6 found. Missing 2 × cam lock (≈15 mm)."
- 🖥️ **3D step viewer** in Hermes Desktop; step images in Telegram, WhatsApp and the other
  messaging apps.

## Safety
Generated instructions are a best effort. Follow the official manual whenever one exists.
No Manual **never** generates instructions for children's furniture (cribs, cots, bunk and loft
beds, high chairs, changing tables, playpens) or anything people sit, sleep, stand or climb on, or
wall-mounted pieces that hold weight. For those it only finds the official manual. This is enforced
twice in code: in the tool handlers and in a `pre_tool_call` hook. If the photos *look* like a crib
partway through, the project is blocked too (fail closed). Tall furniture (≥ 75 cm) always ends
with a wall-anchoring step.

## Install
```bash
hermes plugins install <owner>/no-manual --enable
hermes gateway restart        # once, so the PDF renderer dependency is loaded
```
Requires a **vision-capable model** in Hermes (tested with `gpt-6.1-sol` via ChatGPT sign-in).
Hermes v0.23.0 or newer.

## Use
Just talk to Hermes: *"I lost the manual for my bookcase"* + photos. The plugin's skill loads by
itself. `/nomanual` lists your projects; `/nomanual resume <id>` and `/nomanual delete <id>` do what
they say.

Mode order (ADR-002): **official manual → disassembly recorder → solver**.

## Results (real runs in Hermes, 7 Nov 2026)
| Piece | Mode | Outcome | Notes |
|-------|------|---------|-------|
| IKEA BILLY 80×28×106 (photo + model name from the seller) | manual | ✅ Official PDF found on ikea.com, 16 pages turned into steps | Asked the user to confirm the match first (the photo had a CD insert) |
| Same photo, no name, no label visible | manual | ⚠️ Not identified (confidence 0.35) → asked for a label photo | Honest by design: no guessing |
| Wardrobe 90×200, 3 disassembly stages | recorder | ✅ 3 steps in reverse (shelf → doors → anchor), hinges counted | Stage pictures were drawings, not photos |
| Bookcase 80×180, 4 panel photos with an A4 sheet | solver | ✅ 9/9 panels, exact hardware counts, 13 steps, no questions needed | Panel pictures were to-scale drawings |
| Step 4 photo: side panel face down | step check | ✅ "Turn P1 over so its holes face up" (stop, 0.83); approved after flipping (0.88) | Drawn photos |
| Ambiguous pile: identical boards, no holes visible | solver | ✅ Confidence < 0.6 → asks which boards have holes on their short ends; no steps until answered | Unit fixture |
| Real flat-pack piece on Telegram | all | ⏳ To be run before submission | |

Unit and contract tests: 86 passing (`pytest -q`), including all solver fixtures, golden images
and the safety gate. `hermes plugins validate . --install-deps` passes.

## Disclosure
> **Disclosure** — No Manual sends the photos you add to a project to your own configured model
> provider through Hermes (`ctx.llm`) to read panels, labels and step photos. When you ask it to
> find a manual, Hermes's web search tool runs searches, and the plugin downloads the chosen PDF
> over https (max 30 MB, public hosts only) into the plugin's data folder. Photos, manual pages and
> generated images are stored in `<HERMES_HOME>/plugin-data/no-manual/` and deleted with
> `/nomanual delete`. A Desktop half renders a 3D step viewer (three.js bundled; source in
> `desktop/src/`). No shell commands, no background processes, no telemetry, no credentials stored.
> Generated instructions are a best effort and are never produced for children's furniture or
> anything people sit, sleep or climb on.

## How it works
Vision (through your own provider via Hermes) only *reads* photos into structured data: labels,
panel sizes, hole counts, what changed between two disassembly photos, whether a step photo matches.
Everything else is deterministic, unit-tested code: the safety gate, panel classification,
assembly order (template solver for carcass furniture), hardware counts, confidence scores and the
drawings. Step pictures are drawn from geometry with Pillow, never generated by an image model, so
they always match your real parts.

| Piece | Where |
|-------|-------|
| 14 tools, 2 hooks, skill, `/nomanual` | `__init__.py`, `tools.py`, `schemas.py`, `hooks.py`, `skills/` |
| Template solver + classification + hardware check | `core/solver.py`, `core/geometry.py`, `core/hardware.py` |
| Step drawings + overview | `core/render.py` |
| 3D scene JSON + Desktop viewer | `core/scene.py`, `desktop/`, `dashboard/` |
| Design docs and decisions | `docs/`, `docs/adr/` |

Every step carries a confidence. Below 0.6 the solver asks targeted questions instead of answering;
between 0.6 and 0.75 the step image gets an amber "Check this step" badge and the agent asks for a
photo.

## Roadmap
AR overlay on the phone camera · drawers with runners and hinged-door tuning in the solver ·
replacement-part finder.

## Development
```bash
uv venv .venv && uv pip install --python .venv/bin/python 'pillow>=10.1,<14' 'pypdfium2>=4.20,<6' pytest
.venv/bin/python -m pytest -q
hermes plugins doctor . --ci && hermes plugins validate . --install-deps
```

## License
MIT
