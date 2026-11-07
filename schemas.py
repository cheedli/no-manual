"""Tool schemas: what the model reads. Descriptions say what + when (docs/05)."""
from .core.photos import KINDS
from .core.safety import CATEGORIES

_PID = {"type": "string", "description": "Project id returned by nm_start_project"}
_PATHS = {"type": "array", "items": {"type": "string"},
          "description": "Local file paths of the images the user sent (absolute paths)"}
_RECENT = {"type": "boolean",
           "description": "Set true only if you don't know the image paths: takes the images the "
                          "user sent recently instead"}


def _s(name, description, properties, required=("project_id",)):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}


NM_START_PROJECT = _s(
    "nm_start_project",
    "Create a No Manual furniture project. Call this FIRST as soon as the user wants help "
    "assembling or reassembling furniture without instructions. Runs the safety check and returns "
    "project_id and which modes are allowed.",
    {"category": {"type": "string", "enum": CATEGORIES,
                  "description": "What the user says it is. Use 'other' if unclear."},
     "state": {"type": "string", "enum": ["assembled", "in_pieces", "unknown"],
               "description": "Is it still assembled, or already in pieces?"},
     "title": {"type": "string", "description": "Short name, e.g. 'bedroom closet'"}},
    required=("category",))

NM_ADD_PHOTOS = _s(
    "nm_add_photos",
    "Attach photos the user sent to a No Manual project (overview, labels, panels, hardware). "
    "Call whenever the user sends photos for the project, except disassembly stage photos "
    "(use nm_record_stage) and step check photos (use nm_check_step).",
    {"project_id": _PID, "image_paths": _PATHS, "recent": _RECENT,
     "kind": {"type": "string", "enum": list(KINDS)},
     "caption": {"type": "string"}},
    required=("project_id", "kind"))

NM_SET_DETAILS = _s(
    "nm_set_details",
    "Store facts the user gives about a No Manual project: outer dimensions from a tape measure, "
    "whether it is assembled or in pieces, notes and corrections.",
    {"project_id": _PID,
     "outer_dims": {"type": "object", "description": "Outer size of the assembled furniture",
                    "properties": {"width": {"type": "number"}, "height": {"type": "number"},
                                   "depth": {"type": "number"},
                                   "unit": {"type": "string", "enum": ["mm", "cm", "in"]}}},
     "state": {"type": "string", "enum": ["assembled", "in_pieces", "unknown"]},
     "notes": {"type": "string"}})

NM_STATUS = _s(
    "nm_status",
    "List the user's No Manual furniture projects, or show one project's progress. Use it when "
    "the user wants to continue or resume a furniture project ('continue my closet').",
    {"project_id": {"type": "string", "description": "Omit to list all projects"}},
    required=())

NM_RECORD_STAGE = _s(
    "nm_record_stage",
    "Disassembly recorder. Call once per stage while the user takes still-assembled furniture "
    "apart: stage 0 is a photo of it fully assembled, then one call after each part is removed, "
    "with the new photo and what they removed. Builds a manual in reverse.",
    {"project_id": _PID, "image_paths": _PATHS, "recent": _RECENT,
     "what_was_removed": {"type": "string",
                          "description": "The user's words, e.g. 'took off the doors'. Empty for stage 0."}})

NM_FINISH_RECORDING = _s(
    "nm_finish_recording",
    "Disassembly recorder: call when the user has finished taking the furniture apart. Turns the "
    "recorded stages into a step-by-step assembly manual (reverse order) with step images.",
    {"project_id": _PID})

NM_GET_STEP = _s(
    "nm_get_step",
    "Get one assembly step (title, instruction, hardware, image path) to send to the user. Omit "
    "index for the current step. Send ONE step at a time.",
    {"project_id": _PID, "index": {"type": "integer", "description": "1-based step number; omit for current"}})

NM_IDENTIFY = _s(
    "nm_identify",
    "Identify the furniture from photos (labels, stickers, stamped article numbers, brand marks, shape) "
    "and get web searches for its official assembly manual. Call this early for every project: the "
    "official manual is always the best answer. Pass new label photos in image_paths if the user just "
    "sent them.",
    {"project_id": _PID, "image_paths": _PATHS, "recent": _RECENT,
     "user_text": {"type": "string", "description": "Anything the user knows: brand, store, model name"}})

NM_ATTACH_MANUAL = _s(
    "nm_attach_manual",
    "Attach the official assembly manual once you found it (after nm_identify + web_search), or a PDF "
    "the user sent. Downloads the PDF (https only, max 30 MB) and turns its pages into steps.",
    {"project_id": _PID,
     "pdf_url": {"type": "string", "description": "Direct https URL of the PDF manual"},
     "pdf_path": {"type": "string", "description": "Local PDF path if the user sent the file"},
     "source_page": {"type": "string", "description": "Page where you found it, for attribution"}})

NM_EXTRACT_PARTS = _s(
    "nm_extract_parts",
    "Solver mode (furniture already in pieces, no manual): read every panel and the hardware from the "
    "photos the user sent (panels laid flat with an A4 sheet, hardware spread out). Needs the outer size "
    "set first with nm_set_details. Pass new panel photos in image_paths.",
    {"project_id": _PID, "image_paths": _PATHS, "recent": _RECENT})

NM_CONFIRM_PARTS = _s(
    "nm_confirm_parts",
    "Solver mode: apply the user's answers and corrections to the parts list (roles, sizes, quantities, "
    "missing or extra panels) and hardware counts. Call after asking the questions nm_extract_parts or "
    "nm_solve returned.",
    {"project_id": _PID,
     "updates": {"type": "array", "items": {"type": "object", "properties": {
         "part_id": {"type": "string", "description": "e.g. P3; a new id adds a panel vision missed"},
         "role": {"type": "string", "description": "side, top, bottom, shelf_fixed, shelf_loose, back, door, "
                                                   "plinth, divider, unknown"},
         "quantity": {"type": "integer"},
         "length_mm": {"type": "number"}, "width_mm": {"type": "number"}, "thickness_mm": {"type": "number"},
         "remove": {"type": "boolean", "description": "true if this isn't a real panel"},
         "groove": {"type": "boolean"},
         "holes": {"type": "object", "description": "hole counts by kind, e.g. {\"cam_housing\": 4}"}},
         "required": ["part_id"]}},
     "hardware": {"type": "array", "items": {"type": "object", "properties": {
         "kind": {"type": "string"}, "count": {"type": "integer"}}, "required": ["kind", "count"]},
         "description": "Corrected hardware counts (replaces the count for that kind)"},
     "confirm_all": {"type": "boolean", "description": "true when the user says the whole list is right"}})

NM_SOLVE = _s(
    "nm_solve",
    "Solver mode: work out the assembly order from the confirmed parts. Returns confidence, hardware check "
    "and questions. If it returns questions, ask them, apply with nm_confirm_parts and solve again.",
    {"project_id": _PID})

NM_RENDER_STEPS = _s(
    "nm_render_steps",
    "Solver mode: draw the step images (IKEA-style, from the solved geometry), the overview of all parts "
    "and the 3D scene for Hermes Desktop. Call right after nm_solve succeeds.",
    {"project_id": _PID})

NM_CHECK_STEP = _s(
    "nm_check_step",
    "Check the user's photo of a finished step against the expected result before moving on. Call "
    "whenever the user sends a photo during step-by-step coaching (any mode). Omit index for the current step.",
    {"project_id": _PID, "index": {"type": "integer", "description": "1-based step; omit for current"},
     "image_paths": _PATHS, "recent": _RECENT})
