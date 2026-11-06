# Rendering — IKEA-style steps (PNG) + 3D scene (Desktop)

Two outputs from the same assembly states:
1. **PNG per step** (for chat on any platform) — pure Python, Pillow only.
2. **Scene JSON** (for the Desktop 3D viewer) — three.js builds boxes from it.

No image-generation models. Pictures are drawn from geometry so they always
match the user's real parts (key reliability + judge argument).

## 1. PNG renderer (core/render.py)
Canvas 1080 × 1350 (4:5, good on phones), white background.

### Projection
- Isometric-ish axonometric: rotate scene −35° around Y, +25° around X, then
  orthographic projection. Fit the bounding box of the final assembly to the
  drawing area (keep the same scale for all steps of a plan so parts don't
  "jump" between steps).
- Each board = box with 8 vertices, 6 faces.

### Hidden surfaces
- Painter's algorithm: sort faces by depth (average of projected z), draw
  back-to-front. Good enough for non-intersecting boxes (our case).
- Face fill: white for existing parts, light grey (#E6E6E6) for the part(s)
  added in this step; outline black 3 px; back-facing faces skipped.

### Annotations
- Step number: large bold digit top-left (like IKEA), e.g. "4".
- Title line under it, 1 line, ≤ 48 chars (wrap if needed).
- New-part motion arrow: from an offset ("exploded") position to the final
  position along the joining axis; drawn as a thick arrow.
- Hardware callouts bottom strip: icon + "×4" for each `hardware_used`
  (simple vector icons drawn with Pillow: cam lock = circle with arrow,
  dowel = rounded rectangle, screw = line with head, pin = small circle,
  nail = thin line, anchor = L-bracket).
- Orientation hints from `checks[]`: small text badges ("holes face in",
  "finished edge → front") placed near the relevant part.
- Low-confidence step: amber "Check this step" badge top-right.
- People icon "2×" for steps that need two people (standing up tall pieces).

### Fonts
Use a bundled-with-Pillow default or a font from the system; **do not
download fonts at runtime**. If shipping a font file, include its license
(e.g. DejaVu Sans, permissive) — it's data, not executable.

### Overview image
One extra PNG: all parts laid out flat with their labels (P1, P2…) and
dimensions, plus the hardware inventory. This is the first thing the user
receives in solver mode ("Here's what you have").

### Recorder images
For recorder plans, the "picture" is the user's own photo: letterbox it into
the 1080×1350 canvas, add the header (step number + title) and the hardware
chips. No geometry needed.

### Manual images
Manual pages are sent as rendered (150 dpi PNG), optionally cropped to the
step region if the agent identified it (stretch).

## 2. Scene JSON (core/scene.py) — schema v1
```json
{
  "version": 1,
  "units": "mm",
  "project_id": "ab12cd",
  "outer_dims": {"w": 800, "h": 1800, "d": 300},
  "parts": [
    {"id": "P1", "role": "side", "size": [16, 1800, 300], "color_role": "panel"}
  ],
  "steps": [
    {"index": 1, "title": "Insert cam bolts into the sides",
     "placed": [{"id": "P1", "pos": [0, 0, 0], "rot": [0, 0, 0]}],
     "added": ["P1"],
     "explode_from": {"P1": [-200, 0, 0]},
     "hardware": [{"kind": "cam_bolt", "count": 8}],
     "confidence": 0.9}
  ]
}
```
- `size` = [x, y, z] extents in mm in the part's own frame; `pos` = min corner
  in world mm; `rot` = Euler degrees XYZ (mostly 0/90).
- The viewer animates `added` parts from `pos + explode_from[id]` to `pos`.

## 3. Desktop viewer (desktop/src/plugin.src.js)
- three.js scene: ambient + directional light, `MeshStandardMaterial` with
  colors from CSS variables read at mount (`getComputedStyle(...)
  .getPropertyValue('--ui-…')`), `EdgesGeometry` black outlines for the
  IKEA line-art look.
- Controls: implement a tiny orbit (pointer drag rotates, wheel zooms)
  instead of importing OrbitControls (keeps the bundle small and avoids
  extra imports).
- UI: step title, ◀ ▶ buttons, "Explode" toggle, "Fit" button.
- Data: fetch scene JSON via `ctx.rest('/scene?path=<encoded>')` served by
  `dashboard/plugin_api.py` (which only serves files inside
  `plugin_data_dir("no-manual")` — path traversal check!).
- Resize with `ResizeObserver`; dispose renderer/geometries in `ctx.onDispose`.

## 4. Performance targets
- 12-step PNG plan < 10 s; scene JSON < 200 KB; plugin.js bundle < 1.5 MB.
