"""Tool handlers: thin wrappers over core/. Always return a JSON string, never raise."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from . import schemas
from .core import photos as ph
from .core import recorder, render, safety, units, vision
from .core.models import Project
from .core.store import Store

log = logging.getLogger(__name__)

MEDIA_NOTE = ("To show the image on a messaging app or Hermes Desktop, write MEDIA:<image_path> on its "
              "own line, outside any code block or quote. In a terminal, follow the platform's file rule "
              "(give the plain path).")

# Injected in tests; built lazily from Hermes storage in the plugin.
_store: Store | None = None
_hermes_home: Path | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        from plugins.plugin_storage import plugin_data_dir, plugin_db
        _store = Store(plugin_db("no-manual"), plugin_data_dir("no-manual"))
    return _store


def hermes_home() -> Path:
    if _hermes_home is not None:
        return _hermes_home
    from hermes_constants import get_hermes_home
    return Path(get_hermes_home())


class ToolError(Exception):
    def __init__(self, error: str, hint: str = ""):
        super().__init__(error)
        self.error, self.hint = error, hint


def _ok(**kw) -> str:
    return json.dumps(kw, default=str)


def _load(args) -> Project:
    pid = (args.get("project_id") or "").strip()
    if not pid:
        raise ToolError("project_id is missing.", "Call nm_status to list projects, or nm_start_project.")
    p = get_store().get(pid)
    if not p:
        raise ToolError(f"No project with id '{pid}'.", "Call nm_status to list projects.")
    return p


def _paths(args, p: Project) -> list[str]:
    paths = [x for x in (args.get("image_paths") or []) if isinstance(x, str) and x.strip()]
    if not paths and args.get("recent"):
        since = max([x["added_at"] for x in p.photos] + [p.created_at - 600])
        paths = ph.recent_uploads(hermes_home(), since)
    return paths


def _guard(p: Project, tool: str):
    if p.blocked and tool in safety.GENERATING_TOOLS:
        raise ToolError(safety.BLOCK_MESSAGE,
                        "Offer to find the official manual (nm_identify + web_search), or suggest "
                        "contacting the manufacturer or a professional.")


# ---------------------------------------------------------------- handlers

def nm_start_project(ctx, args, **kw):
    category = safety.normalize_category(args.get("category"))
    p = Project(category=category, title=(args.get("title") or category.replace("_", " ")).strip(),
                assembled=args.get("state") or "unknown")
    if safety.is_blocked(category):
        p.safety_status, p.state = safety.BLOCKED_STATUS, "blocked"
        p.safety_reason = f"Category: {category.replace('_', ' ')}."
    get_store().save(p)
    if p.blocked:
        nxt = (f"Tell the user kindly: {safety.BLOCK_MESSAGE} Then ask for a photo of any label, "
               "sticker or stamped number and call nm_identify to find the official manual.")
    elif p.assembled == "unknown":
        nxt = "Ask: 'Is it still assembled, or already in pieces?' and ask for an overview photo."
    else:
        nxt = "Ask for photos (overview + any label or stamped number), then call nm_add_photos."
    return _ok(project_id=p.id, safety_status=p.safety_status,
               allowed_modes=safety.allowed_modes(p), next=nxt)


def nm_add_photos(ctx, args, **kw):
    p = _load(args)
    kind = args.get("kind") if args.get("kind") in ph.KINDS else "overview"
    paths = _paths(args, p)
    if not paths:
        raise ToolError("No image paths given and no recent photos found.",
                        "Ask the user to send the photos again, then pass their paths in image_paths.")
    rep = ph.add_photos(p, paths, kind, args.get("caption") or "", get_store().project_dir(p.id))
    get_store().save(p)
    nxt = ("Photos added." if rep["added"] else "No new photos were added (see skipped).")
    if args.get("recent") and rep["added"]:
        nxt += f" Confirm with the user: 'I got {rep['added']} photo(s), right?'"
    return _ok(project_id=p.id, **rep, next=nxt)


def nm_set_details(ctx, args, **kw):
    p = _load(args)
    if args.get("outer_dims"):
        try:
            p.outer_dims_mm = units.normalize_dims(args["outer_dims"])
        except ValueError as e:
            raise ToolError(str(e), "Ask the user to re-measure width, height and depth.")
    if args.get("state") in ("assembled", "in_pieces", "unknown"):
        p.assembled = args["state"]
    if args.get("notes"):
        p.notes.append(str(args["notes"]))
    get_store().save(p)
    return _ok(project_id=p.id, outer_dims_mm=p.outer_dims_mm, state=p.assembled,
               next="Saved. Continue with the No Manual flow.")


def nm_status(ctx, args, **kw):
    if args.get("project_id"):
        p = _load(args)
        return _ok(project=p.summary(), next="Continue with nm_get_step if a plan exists.")
    projects = [x.summary() for x in get_store().list()]
    return _ok(projects=projects, next=("Pick the matching project and continue."
                                        if projects else "No projects yet. Use nm_start_project."))


def nm_record_stage(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_finish_recording")
    paths = _paths(args, p)
    if not paths:
        raise ToolError("I need a photo of this stage.", "Ask the user to send one photo of the furniture now.")
    rep = ph.add_photos(p, paths, "stage", args.get("what_was_removed") or "", get_store().project_dir(p.id))
    if not rep["added"]:
        get_store().save(p)
        raise ToolError("That photo was already used for an earlier stage.",
                        "Ask for a new photo taken after removing the next part.")
    new = [x for x in p.photos if x["id"] in rep["photo_ids"]]
    stage = {"index": len(p.stages), "photo_ids": rep["photo_ids"], "photo_paths": [x["path"] for x in new],
             "user_text": (args.get("what_was_removed") or "").strip(), "described": None}
    p.mode, p.state = "recorder", "recording"

    if stage["index"] == 0:
        p.stages.append(stage)
        get_store().save(p)
        return _ok(project_id=p.id, stage_index=0,
                   next="Stage 0 (fully assembled) saved. Ask the user to remove ONE part or group of "
                        "parts, photograph the furniture again from the same angle, and tell you what "
                        "they removed. Then call nm_record_stage again.")

    prev = p.stages[-1]["photo_paths"][0]
    described, warn = None, None
    try:
        a, _ = ph.for_vision(prev)
        b, _ = ph.for_vision(stage["photo_paths"][0])
        r = ctx.llm.complete_structured(
            instructions=vision.STAGE_INSTRUCTIONS, input=vision.stage_input(a, b, stage["user_text"]),
            json_schema=vision.STAGE_SCHEMA, timeout=60, purpose="no-manual.describe_stage")
        described = r.parsed if r.content_type == "json" and isinstance(r.parsed, dict) else None
    except Exception as e:  # vision down: keep the user's words, lower confidence
        log.warning("describe_stage failed: %s", e)
        warn = "Couldn't read the photos; recorded the stage from your description only."
    if described is None:
        described = {"nothing_removed": False, "removed_parts": [], "hardware_removed": [],
                     "description": stage["user_text"], "assembly_instruction": "",
                     "orientation_notes": [], "confidence": 0.5}

    if safety.apply_vision_guess(p, described.get("category_guess"), float(described.get("confidence") or 0)):
        p.state = "blocked"
        get_store().save(p)
        raise ToolError(f"{p.safety_reason} {safety.BLOCK_MESSAGE}",
                        "Stop recording. Offer to find the official manual instead.")

    if described.get("nothing_removed") and not stage["user_text"]:
        get_store().save(p)  # keep the photo, don't create an empty step
        return _ok(project_id=p.id, stage_index=None, question="This looks the same as the last photo. "
                   "What did you remove?",
                   next="Ask the user what they removed, then call nm_record_stage again with "
                        "what_was_removed and a new photo.")

    stage["described"] = described
    p.stages.append(stage)
    get_store().save(p)
    out = {"removed_parts": described.get("removed_parts"), "hardware_removed": described.get("hardware_removed"),
           "orientation_notes": described.get("orientation_notes"), "confidence": described.get("confidence")}
    return _ok(project_id=p.id, stage_index=stage["index"], described=out, warning=warn,
               next="Saved. Ask the user to remove the next part and send a photo, or call "
                    "nm_finish_recording when everything is apart.")


def _render_plan_images(p: Project) -> list[str]:
    d = get_store().project_dir(p.id) / "steps"
    steps = p.plan["steps"]
    out = []
    for s in steps:
        s["image_path"] = render.letterbox_step(s.get("source_photo"), d / f"step_{s['index']:02d}.png",
                                                s["index"], len(steps), s["title"], s.get("hardware_used") or [],
                                                s.get("confidence", 1.0))
        out.append(s["image_path"])
    return out


def nm_finish_recording(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_finish_recording")
    if len(p.stages) < 2:
        raise ToolError("I need at least two stages: the assembled piece and one after removing a part.",
                        "Keep recording with nm_record_stage.")
    h = (p.outer_dims_mm or {}).get("h")
    steps = recorder.build_steps(p.stages, p.category, h)
    warnings = []
    if h is None and safety.needs_anti_tip(p.category, None):
        warnings.append("Height unknown: added a wall-anchoring step to be safe.")
    low = [s["index"] for s in steps if s.get("confidence", 1) < 0.75]
    if low:
        warnings.append(f"Steps {low} are less certain: ask for a photo check after them.")
    conf = round(min([0.85] + [s.get("confidence", 1) for s in steps]), 2)
    p.plan = {"source": "recorder", "confidence": conf, "steps": steps, "warnings": warnings}
    p.mode, p.state, p.current_step = "recorder", "coaching", 1
    images = _render_plan_images(p)
    get_store().save(p)
    return _ok(project_id=p.id, steps=len(steps), step_images=images, warnings=warnings,
               next="Tell the user the manual is ready (N steps). Then call nm_get_step to send step 1 "
                    "only. " + MEDIA_NOTE)


def nm_get_step(ctx, args, **kw):
    p = _load(args)
    if not p.plan or not p.plan.get("steps"):
        raise ToolError("This project has no steps yet.", "Finish recording, attach a manual, or solve first.")
    steps = p.plan["steps"]
    idx = int(args.get("index") or p.current_step or 1)
    if not 1 <= idx <= len(steps):
        raise ToolError(f"Step {idx} doesn't exist; there are {len(steps)} steps.", "Use a number in range.")
    s = steps[idx - 1]
    img = s.get("image_path") or ""
    if img and not Path(img).is_file():
        _render_plan_images(p)
        get_store().save(p)
        img = p.plan["steps"][idx - 1]["image_path"]
    if img:
        os.utime(img)  # fresh mtime: passes strict media-delivery recency checks
    if args.get("index"):
        p.current_step = idx
        get_store().save(p)
    return _ok(project_id=p.id, index=idx, total=len(steps), title=s["title"], instruction=s["instruction"],
               image_path=img, scene_path=s.get("scene_path"), hardware_used=s.get("hardware_used") or [],
               checks=s.get("checks") or [], confidence=s.get("confidence"),
               next=f"Send the title, the instruction and the hardware in a few words. {MEDIA_NOTE} "
                    "Ask the user to send a photo when the step is done.")


def nm_identify(ctx, args, **kw):
    p = _load(args)
    paths = _paths(args, p)
    if paths:
        ph.add_photos(p, paths, "label", "", get_store().project_dir(p.id))
    pics = sorted(p.photos, key=lambda x: {"label": 0, "overview": 1}.get(x["kind"], 2))
    pics = [x for x in pics if x["kind"] in ("label", "overview", "panel", "stage")][:6]
    if not pics:
        raise ToolError("I need a photo first.", "Ask for a photo of any label, sticker or stamped number "
                                                 "(often under a shelf, on the back panel or inside a door).")
    r = ctx.llm.complete_structured(
        instructions=vision.IDENTIFY_INSTRUCTIONS,
        input=vision.identify_input([ph.for_vision(x["path"])[0] for x in pics], args.get("user_text") or ""),
        json_schema=vision.IDENTIFY_SCHEMA, timeout=60, purpose="no-manual.identify")
    ident = r.parsed if r.content_type == "json" and isinstance(r.parsed, dict) else {}
    if not ident:
        raise ToolError("Couldn't read the photos.", "Ask for a closer, well-lit photo of the label.")
    p.identity = ident
    p.state = "identifying" if not p.blocked else p.state
    newly_blocked = safety.apply_vision_guess(p, ident.get("category_guess"), float(ident.get("confidence") or 0))
    if newly_blocked:
        p.state = "blocked"
    get_store().save(p)
    conf = float(ident.get("confidence") or 0)
    found_something = bool(ident.get("brand") or ident.get("article_numbers") or ident.get("product_name"))
    nxt = ("Run web_search with search_queries. Prefer the manufacturer's own site or its official "
           "assembly-instructions page; look for a direct https link to the PDF. When you find it, call "
           "nm_attach_manual with pdf_url and source_page. Don't attach manuals for a different product.")
    if not found_something or conf < 0.4:
        fallback = ("only the official manual is allowed for this piece; suggest contacting the manufacturer."
                    if p.blocked else "use the recorder (if assembled) or the solver (if in pieces).")
        nxt = ("Not identified with confidence. Ask for a photo of a label, sticker or stamped number (under "
               "shelves, back panel, inside doors). If the user named a brand, you may still run web_search "
               "with search_queries, but present any match as a possibility and ask the user to confirm it "
               "is their exact piece before attaching it. If nothing turns up: " + fallback)
    return _ok(project_id=p.id, brand=ident.get("brand", ""), product_name=ident.get("product_name", ""),
               article_numbers=ident.get("article_numbers") or [], category_guess=ident.get("category_guess"),
               confidence=conf, search_queries=ident.get("search_queries") or [],
               safety_status=p.safety_status,
               safety_note=(f"{p.safety_reason} {safety.BLOCK_MESSAGE}" if newly_blocked else None), next=nxt)


def nm_attach_manual(ctx, args, **kw):
    from urllib.parse import urlparse
    from .core import manual
    p = _load(args)
    d = get_store().project_dir(p.id) / "manual"
    url, local = (args.get("pdf_url") or "").strip(), (args.get("pdf_path") or "").strip()
    try:
        if url:
            pdf = manual.download(url, d / "manual.pdf")
            source = args.get("source_page") or url
        elif local:
            pdf = Path(local).expanduser()
            if not pdf.is_file():
                raise manual.ManualError("PDF file not found.")
            source = args.get("source_page") or "a PDF you provided"
        else:
            raise manual.ManualError("Give pdf_url (https) or pdf_path.")
        pages = manual.render_pages(pdf, d / "pages")
    except manual.ManualError as e:
        raise ToolError(str(e), "Look for a direct https link to the manufacturer's PDF, or ask the user "
                                "to download it and send the file.")
    if not pages:
        raise ToolError("The PDF has no pages.", "Find another copy of the manual.")
    domain = urlparse(source).hostname or source
    p.plan = {"source": "manual", "confidence": 0.95, "steps": manual.pages_to_steps(pages), "warnings": []}
    p.manual_source, p.mode, p.state, p.current_step = source, "manual", "coaching", 1
    get_store().save(p)
    return _ok(project_id=p.id, pages=len(pages), steps=len(pages), first_step_image=pages[0],
               source=source, next=f"Tell the user: 'Official manual from {domain}, {len(pages)} pages.' "
               "Then call nm_get_step to send page 1. Skip cover/warning pages if the user wants. " + MEDIA_NOTE)


TOOLS = [
    ("nm_start_project", schemas.NM_START_PROJECT, nm_start_project),
    ("nm_add_photos", schemas.NM_ADD_PHOTOS, nm_add_photos),
    ("nm_set_details", schemas.NM_SET_DETAILS, nm_set_details),
    ("nm_status", schemas.NM_STATUS, nm_status),
    ("nm_record_stage", schemas.NM_RECORD_STAGE, nm_record_stage),
    ("nm_finish_recording", schemas.NM_FINISH_RECORDING, nm_finish_recording),
    ("nm_get_step", schemas.NM_GET_STEP, nm_get_step),
    ("nm_identify", schemas.NM_IDENTIFY, nm_identify),
    ("nm_attach_manual", schemas.NM_ATTACH_MANUAL, nm_attach_manual),
]


def bind(fn, ctx):
    """Handler with Hermes's signature: (args, **kwargs) -> JSON str. Never raises."""
    def handler(args: dict, **kwargs) -> str:
        try:
            return fn(ctx, args if isinstance(args, dict) else {}, **kwargs)
        except ToolError as e:
            return json.dumps({"error": e.error, "hint": e.hint})
        except Exception as e:
            log.exception("%s failed", fn.__name__)
            return json.dumps({"error": f"Something went wrong: {type(e).__name__}: {e}",
                               "hint": "Explain plainly and offer the next best mode."})
    handler.__name__ = fn.__name__
    return handler


# ---------------------------------------------------------------- /nomanual

def slash(raw: str) -> str:
    try:
        words = (raw or "").split()
        store = get_store()
        if not words or words[0] == "list":
            ps = store.list()
            if not ps:
                return "No furniture projects yet. Tell me what you're building to start one."
            return "\n".join(f"{x.id}  {x.title} · {x.mode} · {x.state}"
                             + (f" · step {x.summary()['step']}" if x.summary()["step"] else "") for x in ps)
        cmd, pid = words[0], (words[1] if len(words) > 1 else "")
        p = store.get(pid) if pid else None
        if cmd in ("resume", "delete") and not p:
            return f"No project '{pid}'. Use /nomanual to list them."
        if cmd == "resume":
            s = p.summary()
            return (f"Project {p.id} ({p.title}): {p.mode}, {p.state}"
                    + (f", step {s['step']}" if s["step"] else "") + ". Say 'continue' and I'll pick up from there.")
        if cmd == "delete":
            if len(words) < 3 or words[2] != "yes":
                return f"This deletes project {pid} and all its photos. Type /nomanual delete {pid} yes"
            store.delete(pid)
            return f"Deleted project {pid}."
        return "Usage: /nomanual [list] | resume <id> | delete <id>"
    except Exception as e:
        return f"No Manual error: {e}"
