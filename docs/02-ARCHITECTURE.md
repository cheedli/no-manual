# Architecture — No Manual

## 1. Shape of the package
One **unified Hermes package** (agent half + desktop half in one folder),
installed from a public GitHub repo pinned by the catalog entry.

```
no-manual/                         # repo root = plugin root
├── plugin.yaml                    # manifest (tools, hooks, deps, metadata)
├── pyproject.toml                 # Python deps with upper bounds
├── __init__.py                    # register(ctx): tools, hooks, skill, slash cmd
├── schemas.py                     # tool JSON schemas (what the model reads)
├── tools.py                       # tool handlers (thin; call into core/)
├── hooks.py                       # pre_tool_call safety guard, etc.
├── core/                          # PURE PYTHON — no Hermes imports, unit-tested
│   ├── models.py                  # dataclasses: Project, Photo, Part, Hardware, Plan, Step
│   ├── store.py                   # persistence (sqlite via an injected connection)
│   ├── safety.py                  # category gate (doc 08)
│   ├── vision.py                  # prompt builders + JSON schemas for ctx.llm calls
│   ├── manual.py                  # manual PDF → page images (pypdfium2)
│   ├── recorder.py                # disassembly log → reversed assembly steps
│   ├── geometry.py                # boards, holes, transforms, bounding boxes
│   ├── solver.py                  # template solver (doc 06)
│   ├── hardware.py                # hardware taxonomy + count check
│   ├── render.py                  # IKEA-style PNG renderer (Pillow) (doc 07)
│   └── scene.py                   # 3D scene JSON for the Desktop viewer
├── skills/
│   └── no-manual-guide/SKILL.md   # agent playbook for the whole flow
├── dashboard/
│   ├── manifest.json              # {"name": "no-manual", "api": "plugin_api.py"}
│   └── plugin_api.py              # serves scene JSON to the desktop half
├── desktop/
│   ├── src/plugin.src.js          # source (readable, reviewed)
│   └── plugin.js                  # esbuild bundle incl. three.js (built artefact)
├── tests/                         # pytest: geometry, solver, render, recorder, safety
├── fixtures/                      # synthetic furniture JSON + sample photos (own photos only)
├── scripts/build_desktop.sh       # esbuild command (reproducible bundle)
├── README.md                      # user-facing, with disclosures
└── LICENSE                        # MIT
```

## 2. Runtime data flow

```
User (Telegram/WhatsApp/Desktop/CLI)
  │  photos + "this is a closet"
  ▼
Hermes agent (user's model)  ── loads skill no-manual:no-manual-guide
  │  calls our tools with image paths (cache/images/…)
  ▼
tools.py ──► core/* (pure python) ──► ctx.llm.complete_structured(images…)
  │                                       (vision on the user's provider)
  │  writes project state ──► plugin_db("no-manual") / plugin_data_dir
  │  writes step PNGs + scene JSON ──► plugin_data_dir/projects/<id>/
  ▼
tool result JSON (includes file paths) → agent replies with `MEDIA:<path>` lines
  │
  ├─► gateway delivers PNGs as native photos (Telegram/WhatsApp)
  └─► Desktop: tool media renderer claims our tool's scene file → 3D viewer
```

### Where the model ends and code begins
- **The model** converses, decides which mode, asks the user questions,
  narrates, and calls tools. Guided by the bundled skill.
- **Our code** does everything that must be deterministic: storage, safety
  gate, geometry, solving, counting, rendering, file output.
- **ctx.llm (vision)** is used for perception only: reading photos into
  structured JSON (parts, holes, labels, step-check verdicts). Never for
  geometry or ordering decisions.

## 3. Data model (core/models.py)

```python
Project:
  id: str                 # short uuid
  created_at, updated_at
  category: str           # closet | wardrobe | bookcase | cabinet | nightstand | desk | other
  mode: str               # unknown | manual | recorder | solver
  state: str              # intake | identifying | recording | extracting | solved | coaching | done | blocked
  outer_dims_mm: {w, h, d} | None   # from the user's tape measure
  safety_status: str      # ok | blocked_child | blocked_load | unknown
  photos: [Photo]
  parts: [Part]
  hardware: [Hardware]
  plan: Plan | None
  current_step: int
  notes: [str]

Photo:
  id, path (absolute, copied into project dir), kind: overview|panel|hardware|label|stage|check
  sha256, added_at, caption

Part:                       # a flat board (panel) — all solver parts are boards
  id: "P1"…               # stable label shown to the user ("panel P3")
  role: side|top|bottom|back|shelf|door|plinth|divider|unknown
  dims_mm: {length, width, thickness}
  quantity: int
  holes: [Hole]
  edge_banding: [edges]   # which edges are finished (visible) — orientation cue
  photo_ids: [str]
  confidence: float       # 0..1 from extraction + user confirmation (1.0)

Hole:
  face: A|B|edge_top|edge_bottom|edge_left|edge_right
  kind: cam_housing|cam_bolt|dowel|shelf_pin|screw|hinge_cup|nail
  position_mm: {u, v}     # in the face's 2D coordinates
  diameter_mm: float|None

Hardware:
  kind: cam_lock|cam_bolt|dowel|wood_screw|confirmat|shelf_pin|nail|hinge|handle|rail|wall_anchor|other
  count: int
  size_hint: str          # e.g. "8x30 dowel", "M6 cam bolt"

Plan:
  source: manual|recorder|solver
  confidence: float
  steps: [Step]
  warnings: [str]

Step:
  index: int
  title: str              # "Fix the bottom panel to the left side"
  instruction: str        # plain-language sentence(s)
  parts_added: [part ids]
  hardware_used: [{kind, count}]
  image_path: str         # PNG for chat
  scene_path: str|None    # 3D scene JSON (solver only)
  expected_state: str     # description used by step check
  confidence: float
  checks: [str]           # things the step checker must verify ("holes face inward")
```

## 4. Storage
- `plugin_db("no-manual")` (SQLite, WAL) — tables `projects`, `photos`,
  `parts`, `hardware`, `steps`, `events`. JSON columns are fine for nested
  data. One row per project keyed by `id`; `session_ref` column stores the
  Hermes session/user identity so "resume my closet" works.
- `plugin_data_dir("no-manual")/projects/<id>/` — copied photos, manual page
  images, rendered PNGs, scene JSON.
- Nothing is written in the plugin install directory.

## 5. LLM usage (all via ctx.llm)
| Call | Method | Input | Output |
|------|--------|-------|--------|
| Identify product | `complete_structured` | label/overview photos | `{brand, product_name, article_numbers[], category_guess, search_queries[]}` |
| Extract parts | `complete_structured` | panel photos (≤ 6 per call) + reference object | `{parts:[…], hardware:[…], uncertainties:[…]}` |
| Describe disassembly stage | `complete_structured` | stage photo + previous stage photo | `{removed_parts, hardware_removed, description, orientation_notes}` |
| Check a step | `complete_structured` | user photo + rendered expected image (or manual page) + expected_state text | `{ok: bool, issues:[{severity, text}], confidence}` |

Timeouts: `ctx.llm` defaults to 15 s, capped at 60 s. Batch images and pass
`timeout=60` for vision calls. Use `purpose="no-manual.<call>"` for audit.

## 6. Manual search
The manual finder is **agent-driven**: the skill tells the agent to use
Hermes's built-in `web_search` (and fetch/browse tools if present) with the
queries our `nm_identify` tool returns, then call `nm_attach_manual` with the
PDF URL or a local PDF path. Our code downloads the PDF (https only, size cap
30 MB, content-type check), renders pages to PNG with `pypdfium2`, and stores
them as steps (one manual page = one step by default; the agent may merge).

## 7. Desktop half
- `desktop/plugin.js` registers a **tool media renderer** for `nm_render_steps`
  and `nm_get_step`: when the agent's reply includes `MEDIA:` with our scene
  JSON or PNG, the Desktop shows an interactive three.js viewer with
  previous/next step buttons and exploded-view animation.
- Allowed imports are only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime`.
  three.js must be **bundled into plugin.js** by esbuild with those three
  marked external. No JSX syntax in the shipped file (use `jsx()`).
- Large scene files are fetched via `ctx.rest` from `dashboard/plugin_api.py`
  rather than `file.resolveUrl()`.

## 8. Failure behaviour
- Any tool error → JSON `{error, hint}`; the skill tells the agent to explain
  plainly and offer the next best mode.
- Low confidence (< 0.6) at any stage → ask the user a targeted question,
  never proceed silently.
- Safety block → stop the solver path permanently for that project.
