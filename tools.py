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


def _num(x, default: float = 0.0) -> float:
    """Model output can say 0.8, "0.8" or "high": never let parsing lose the user's data."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _guard(p: Project, tool: str):
    if p.blocked and (tool in safety.GENERATING_TOOLS or
                      (tool in safety.STEP_TOOLS and (p.plan or {}).get("source") not in (None, "manual"))):
        raise ToolError(safety.BLOCK_MESSAGE,
                        "Offer to find the official manual (nm_identify + web_search), or suggest "
                        "contacting the manufacturer or a professional.")


# ---------------------------------------------------------------- handlers

def nm_start_project(ctx, args, **kw):
    category = safety.normalize_category(args.get("category"))
    p = Project(category=category, title=(args.get("title") or category.replace("_", " ")).strip(),
                assembled=args.get("state") or "unknown")
    if safety.is_blocked(category) or safety.mentions_blocked(args.get("category"), args.get("title")):
        safety.block(p, f"Category: {category.replace('_', ' ') if safety.is_blocked(category) else p.title}.")
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

    if safety.apply_vision_guess(p, described.get("category_guess"), _num(described.get("confidence"), 0.5)):
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
    if (p.plan or {}).get("source") == "solver":
        return _render_solver(p)["step_images"]
    if (p.plan or {}).get("source") == "manual":  # pages are their own images
        return [s["image_path"] for s in p.plan["steps"]]
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
    _guard(p, "nm_get_step")
    if not p.plan or not p.plan.get("steps"):
        raise ToolError("This project has no steps yet.", "Finish recording, attach a manual, or solve first.")
    steps = p.plan["steps"]
    if not args.get("index") and p.current_step > len(steps):
        return _ok(project_id=p.id, done=True, total=len(steps),
                   next="All steps are done. Congratulate the user; offer to show any step again by number.")
    idx = int(_num(args.get("index"), 0) or p.current_step or 1)
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
    newly_blocked = safety.apply_vision_guess(p, ident.get("category_guess"), _num(ident.get("confidence")))
    if not p.blocked and safety.mentions_blocked(ident.get("product_name"), ident.get("category_guess")):
        safety.block(p, f"Identified as: {ident.get('product_name') or ident.get('category_guess')}.")
        newly_blocked = True
    get_store().save(p)
    conf = _num(ident.get("confidence"))
    found_something = bool(ident.get("brand") or ident.get("article_numbers") or ident.get("product_name"))
    nxt = ("Run web_search with search_queries. Prefer the manufacturer's own site or its official "
           "assembly-instructions page; look for a direct https link to the PDF. When you find it, call "
           "nm_attach_manual with pdf_url and source_page. Don't attach manuals for a different product.")
    if not found_something or conf < 0.4:
        fallback = ("only the official manual is allowed for this piece; suggest contacting the manufacturer."
                    if p.blocked else "use the recorder (if assembled) or the solver (if in pieces).")
        if ident.get("search_queries") and conf >= 0.5:
            nxt = ("Not confirmed (no label read), but the shape suggests a known product. Run web_search with "
                   "search_queries now. If it returns the official PDF, present it as a possible match (\"It "
                   "looks like <product>; is that yours?\") and attach it only after the user confirms. Also ask "
                   "for a photo of any label to be sure. If nothing turns up: " + fallback)
        else:
            nxt = ("Not identified with confidence. Ask for a photo of a label, sticker or stamped number "
                   "(under shelves, back panel, inside doors). If the user named a brand, you may still run "
                   "web_search with search_queries, but present any match as a possibility and ask the user to "
                   "confirm it is their exact piece before attaching it. If nothing turns up: " + fallback)
    # ponytail: the model once claimed "I found the manual" without searching; say it in every branch.
    nxt += " Never say you found a manual unless web_search returned its link in this conversation."
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


# ---------------------------------------------------------------- solver mode

def _structured(ctx, purpose, instructions, blocks, schema, required_key):
    """complete_structured with one stricter retry when the JSON is missing/invalid (F5 AC2)."""
    for attempt in range(2):
        r = ctx.llm.complete_structured(
            instructions=instructions if attempt == 0 else
            instructions + " Reply with ONLY a JSON object that matches the schema exactly.",
            input=blocks, json_schema=schema, timeout=60, purpose=purpose)
        if r.content_type == "json" and isinstance(r.parsed, dict) and required_key in r.parsed:
            return r.parsed
    raise ToolError("Couldn't read the photos into a parts list.",
                    "Ask for clearer photos (good light, panels flat, A4 sheet visible), or ask the user to "
                    "measure each panel and pass the sizes with nm_confirm_parts.")


def _dry_solve(p: Project) -> dict:
    from .core import solver
    return solver.solve(p.parts, p.hardware, p.outer_dims_mm, p.category)


def _parts_view(p: Project, roles: dict) -> list[dict]:
    from .core.geometry import ROLE_NAMES, holes
    out = []
    for x in p.parts:
        h = {k: v for k, v in holes(x).items() if v}
        d = x["dims_mm"]
        out.append({"id": x["id"], "role_guess": ROLE_NAMES.get(roles.get(x["id"], "unknown"), "unknown part"),
                    "size_cm": f"{d['length'] / 10:g} × {d['width'] / 10:g} × {d.get('thickness', 0) / 10:g}",
                    "quantity": x.get("quantity", 1), "holes": h, "confirmed": bool(x.get("confirmed")),
                    "confidence": x.get("confidence")})
    return out


def nm_extract_parts(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_solve")
    if not p.outer_dims_mm:
        raise ToolError("I need the outer size first.", "Ask for width, height and depth of the assembled piece "
                        "(tape measure), then call nm_set_details.")
    paths = _paths(args, p)
    if paths:
        ph.add_photos(p, paths, "panel", "", get_store().project_dir(p.id))
    pics = [x for x in p.photos if x["kind"] in ("panel", "hardware", "overview", "label")]
    if not pics:
        raise ToolError("No panel photos in this project yet.",
                        "If the user already sent panel photos, call nm_extract_parts again on the SAME project "
                        "with their paths in image_paths (don't start a new project). Otherwise ask for photos of "
                        "every panel laid flat with an A4 sheet in view, and one of the hardware spread out.")
    per_call = int(ctx.get_config("max_photos_per_call", default=6) or 6)
    o = p.outer_dims_mm
    dims_text = f"width {o['w']:g} mm, height {o['h']:g} mm, depth {o['d']:g} mm"
    parts, hw_max, uncertain, guesses = [], {}, [], []
    for i in range(0, len(pics), per_call):
        batch = pics[i:i + per_call]
        res = _structured(ctx, "no-manual.extract_parts", vision.PARTS_INSTRUCTIONS.format(dims=dims_text),
                          vision.parts_input([ph.for_vision(x["path"])[0] for x in batch], dims_text),
                          vision.PARTS_SCHEMA, "parts")
        parts += res.get("parts") or []
        for h in res.get("hardware") or []:
            hw_max[h["kind"]] = max(hw_max.get(h["kind"], 0), int(h.get("count") or 0))
        uncertain += res.get("uncertainties") or []
        if res.get("category_guess"):
            guesses.append(res["category_guess"])
    if len(pics) > per_call:
        uncertain.append("Photos were read in batches: a panel shown in two batches may be listed twice.")
    for g in guesses:
        if safety.apply_vision_guess(p, g, 0.6):
            p.state = "blocked"
            get_store().save(p)
            raise ToolError(f"{p.safety_reason} {safety.BLOCK_MESSAGE}", "Offer to find the official manual instead.")
    p.parts = [{"id": f"P{k}", "label": x.get("label") or "",
                "dims_mm": {"length": float(x.get("length_mm") or 0), "width": float(x.get("width_mm") or 0),
                            "thickness": float(x.get("thickness_mm") or 0)},
                "quantity": max(1, int(x.get("quantity") or 1)), "holes": x.get("holes") or {},
                "groove": bool(x.get("groove")), "description": x.get("description") or "",
                "confidence": x.get("confidence"), "confirmed": False}
               for k, x in enumerate(parts, 1) if x.get("length_mm") and x.get("width_mm")]
    p.hardware = [{"kind": k, "count": n} for k, n in hw_max.items() if n]
    p.mode, p.state = "solver", "extracting"
    get_store().save(p)
    if not p.parts:
        raise ToolError("I couldn't see any panels.", "Ask for photos of the panels laid flat, one or two per photo.")
    plan = _dry_solve(p)
    return _ok(project_id=p.id, parts=_parts_view(p, plan["roles"]), hardware=p.hardware,
               questions=plan["questions"][:4], uncertainties=uncertain[:4],
               hardware_check=plan["hardware_check"]["lines"],
               next="Show the parts list briefly (id, what it is, size). Ask the questions (max 4, one message), "
                    "and ask the user to check the sizes and hardware counts. Apply answers with "
                    "nm_confirm_parts, then call nm_solve." if plan["questions"] else
                    "Show the parts list briefly and ask the user to confirm it looks right (or correct sizes "
                    "and counts with nm_confirm_parts). Then call nm_solve.")


SINGLE_ROLES = {"top", "bottom", "plinth", "divider"}


def nm_confirm_parts(ctx, args, **kw):
    from .core.geometry import ROLES
    p = _load(args)
    byid = {x["id"]: x for x in p.parts}
    changed = []
    for u in args.get("updates") or []:
        pid = (u.get("part_id") or "").strip()
        if not pid:
            continue
        x = byid.get(pid)
        role_req = (u.get("role") or "").strip().lower().replace(" ", "_")
        base_id = pid.split(".")[0]
        # "P2.2" (an instance of P2 x3), or a one-of-a-kind role on a multi-quantity part:
        # split one board off as its own part so ids stay unique and roles don't apply to all copies.
        if (x is None and "." in pid and base_id in byid) or (
                x is not None and x.get("quantity", 1) > 1 and role_req in SINGLE_ROLES and not u.get("quantity")):
            base = byid[base_id]
            if base.get("quantity", 1) > 1:
                n = 1 + max(int(y["id"][1:]) for y in p.parts if y["id"][1:].isdigit())
                x = {**base, "id": f"P{n}", "quantity": 1, "holes": dict(base.get("holes") or {}),
                     "dims_mm": dict(base["dims_mm"]), "role": None}
                base["quantity"] -= 1
                p.parts.append(x)
                byid[x["id"]] = x
                changed.append(f"{pid} is now {x['id']}")
            else:
                x = base
        if u.get("remove"):
            if x:
                p.parts.remove(x)
                changed.append(f"removed {pid}")
            continue
        if x is None:  # a panel vision missed
            if not (u.get("length_mm") and u.get("width_mm")):
                raise ToolError(f"New part {pid} needs length_mm and width_mm.", "Ask the user to measure it.")
            x = {"id": pid, "dims_mm": {"length": 0, "width": 0, "thickness": 0}, "quantity": 1, "holes": {},
                 "confirmed": False}
            p.parts.append(x)
            byid[pid] = x
        for key, dim in (("length_mm", "length"), ("width_mm", "width"), ("thickness_mm", "thickness")):
            if u.get(key):
                x["dims_mm"][dim] = float(u[key])
        if u.get("quantity"):
            x["quantity"] = max(1, int(u["quantity"]))
        role = (u.get("role") or "").strip().lower().replace(" ", "_")
        role = {"shelf": "shelf_loose", "loose_shelf": "shelf_loose", "fixed_shelf": "shelf_fixed",
                "back_panel": "back", "kick_board": "plinth"}.get(role, role)
        if role:
            if role not in ROLES:
                raise ToolError(f"Unknown role '{role}'.", f"Use one of: {', '.join(ROLES)}.")
            x["role"] = role
        if u.get("holes"):
            x["holes"] = {**(x.get("holes") or {}), **u["holes"]}
        if "groove" in u:
            x["groove"] = bool(u["groove"])
        x["confirmed"] = True
        changed.append(pid)
    if args.get("confirm_all"):
        for x in p.parts:
            x["confirmed"] = True
        changed.append("all parts confirmed")
    for h in args.get("hardware") or []:
        if h.get("kind"):
            p.hardware = [y for y in p.hardware if y["kind"] != h["kind"]]
            if int(h.get("count") or 0) > 0:
                p.hardware.append({"kind": h["kind"], "count": int(h["count"])})
            changed.append(f"{h['kind']}={h.get('count')}")
    get_store().save(p)
    if not p.outer_dims_mm or not p.parts:
        return _ok(project_id=p.id, changed=changed, next="Saved. Extract parts first (nm_extract_parts).")
    plan = _dry_solve(p)
    return _ok(project_id=p.id, changed=changed, parts=_parts_view(p, plan["roles"]),
               questions=plan["questions"][:4], confidence=plan["confidence"],
               next="Ask the remaining questions, or call nm_solve." if plan["questions"] else "Call nm_solve.")


def nm_solve(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_solve")
    if not p.outer_dims_mm or not p.parts:
        raise ToolError("I need the outer size and the parts list first.",
                        "Call nm_set_details (outer_dims) and nm_extract_parts.")
    plan = _dry_solve(p)
    out = {"confidence": plan["confidence"], "template": plan["template"],
           "hardware_check": plan["hardware_check"], "warnings": plan["warnings"], "questions": plan["questions"]}
    if not plan["ready"]:
        get_store().save(p)
        return _ok(project_id=p.id, steps=0, **out,
                   next="Not sure enough to give steps yet. Ask these questions (one message), apply the answers "
                        "with nm_confirm_parts, then call nm_solve again. Don't invent steps.")
    p.plan = plan
    p.mode, p.state, p.current_step = "solver", "solved", 1
    low = [s["index"] for s in plan["steps"] if s["confidence"] < 0.75]
    if low:
        plan["warnings"].append(f"Steps {low} are less certain: check a photo after each.")
    get_store().save(p)
    return _ok(project_id=p.id, steps=len(plan["steps"]), uncertain_steps=low, **out,
               disclaimer=safety.DISCLAIMER,
               next="Call nm_render_steps, then send the overview image first." +
                    (" Mention the hardware problems in one line." if not plan["hardware_check"]["ok"] else ""))


def _group_role(roles: dict, base_id: str) -> str:
    """Identical boards can play different roles (P2 x3 = top, bottom, fixed shelf): name them all."""
    from .core.geometry import ROLE_NAMES
    seen = []
    for pid, r in roles.items():
        if (pid == base_id or pid.startswith(base_id + ".")) and ROLE_NAMES.get(r, r) not in seen:
            seen.append(ROLE_NAMES.get(r, r))
    return " / ".join(seen) or "unknown part"


def nm_render_steps(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_render_steps")
    plan = p.plan or {}
    if plan.get("source") != "solver" or not plan.get("steps"):
        raise ToolError("Nothing to render yet.", "Call nm_solve first (solver mode only).")
    out = _render_solver(p)
    p.state = "coaching"
    get_store().save(p)
    return _ok(project_id=p.id, **out,
               next="Send the overview image first ('Here's what you have') with the hardware check in one line, "
                    "say the disclaimer once, then send step 1 only (nm_get_step). " + MEDIA_NOTE +
                    " On Hermes Desktop you can also send MEDIA:<scene_path> to open the 3D step viewer.")


def _render_solver(p: Project) -> dict:
    from .core import scene
    from .core.geometry import ab
    plan = p.plan
    d = get_store().project_dir(p.id) / "steps"
    plan["parts_list"] = [{"id": x["id"], "a": ab(x)[0], "b": ab(x)[1], "qty": x.get("quantity", 1),
                           "role": _group_role(plan["roles"], x["id"])} for x in p.parts]
    overview = render.overview(plan, p.hardware, d / "overview.png", plan["hardware_check"]["lines"])
    sc = scene.build(p.id, p.outer_dims_mm, plan)
    scene_path = d / "scene.json"
    scene_path.write_text(json.dumps(sc))
    images = []
    for s in plan["steps"]:
        s["image_path"] = render.line_art_step(plan, s, d / f"step_{s['index']:02d}.png")
        s["scene_path"] = str(scene_path)
        images.append(s["image_path"])
    plan["overview_image"], plan["scene_path"] = overview, str(scene_path)
    return {"overview_image": overview, "scene_path": str(scene_path), "step_images": images}


def nm_check_step(ctx, args, **kw):
    p = _load(args)
    _guard(p, "nm_check_step")
    if not p.plan or not p.plan.get("steps"):
        raise ToolError("This project has no steps yet.", "Finish recording, attach a manual, or solve first.")
    steps = p.plan["steps"]
    idx = int(_num(args.get("index"), 0) or min(p.current_step, len(steps)) or 1)
    if not 1 <= idx <= len(steps):
        raise ToolError(f"Step {idx} doesn't exist.", f"Use 1-{len(steps)}.")
    s = steps[idx - 1]
    paths = _paths(args, p)
    if not paths:
        raise ToolError("I need a photo of the finished step.", "Ask the user to send one clear photo.")
    rep = ph.add_photos(p, paths, "check", f"step {idx}", get_store().project_dir(p.id))
    photo_paths = [x["path"] for x in p.photos if x["id"] in rep["photo_ids"]] or [
        x for x in paths if Path(x).is_file()]
    if not photo_paths:
        raise ToolError("I couldn't open that photo.", "Ask the user to send it again.")
    ref = s.get("image_path") or s.get("source_photo")
    blocks = []
    if ref and Path(ref).is_file():
        blocks += [{"type": "text", "text": "Image 1 — REFERENCE (expected result):"},
                   {"type": "image", "data": ph.for_vision(ref)[0], "mime_type": "image/jpeg"}]
    blocks += [{"type": "text", "text": "User's photo(s):"}]
    blocks += [{"type": "image", "data": ph.for_vision(x)[0], "mime_type": "image/jpeg"} for x in photo_paths[:3]]
    instructions = vision.CHECK_INSTRUCTIONS.format(
        title=s["title"], instruction=s["instruction"], checks="; ".join(s.get("checks") or []) or "general fit")
    v = _structured(ctx, "no-manual.check_step", instructions, blocks, vision.CHECK_SCHEMA, "matches")
    issues = [i for i in v.get("issues") or [] if i.get("text")]
    conf = _num(v.get("confidence"))
    stop = any(i.get("severity") == "stop" for i in issues)
    quality = v.get("photo_quality") or "unclear"  # no verdict = not checked
    ok = bool(v.get("matches")) and not stop
    advance = ok and conf >= 0.6 and quality == "good"
    s.setdefault("check_log", []).append({"at": time.time(), "ok": ok, "confidence": conf, "issues": issues})
    if advance:
        p.current_step = max(p.current_step, idx + 1)
        if idx == len(steps):
            p.state = "done"
    get_store().save(p)
    if advance:
        nxt = ("All steps done! Congratulate the user and ask if everything feels solid." if idx == len(steps)
               else f"Step {idx} looks right. Say so in a few words, then send step {idx + 1} (nm_get_step).")
    elif stop:
        nxt = "Tell the user to stop and explain the fix from the 'stop' issues in plain words. Ask for a new photo."
    elif quality != "good" or conf < 0.6:
        nxt = (f"Not sure from this photo ({quality}). Ask for a clearer, closer photo in good light showing the "
               "whole step. Don't approve the step.")
    else:
        nxt = "Mention the issues briefly and ask the user to check them, then send a new photo."
    return _ok(project_id=p.id, index=idx, ok=ok, advance=advance, issues=issues, confidence=conf,
               photo_quality=quality, what_i_see=v.get("what_i_see", ""), next=nxt)


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
    ("nm_extract_parts", schemas.NM_EXTRACT_PARTS, nm_extract_parts),
    ("nm_confirm_parts", schemas.NM_CONFIRM_PARTS, nm_confirm_parts),
    ("nm_solve", schemas.NM_SOLVE, nm_solve),
    ("nm_render_steps", schemas.NM_RENDER_STEPS, nm_render_steps),
    ("nm_check_step", schemas.NM_CHECK_STEP, nm_check_step),
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
