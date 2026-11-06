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
