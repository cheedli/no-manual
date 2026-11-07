"""Prompts + JSON schemas for ctx.llm structured calls. Perception only (ADR-005)."""
from __future__ import annotations

HARDWARE_KINDS = ["cam_lock", "cam_bolt", "dowel", "wood_screw", "confirmat", "shelf_pin", "nail",
                  "hinge", "handle", "rail", "wall_anchor", "bracket", "bolt", "other"]

_HW = {"type": "array", "items": {"type": "object", "properties": {
    "kind": {"type": "string", "enum": HARDWARE_KINDS}, "count": {"type": "integer"}},
    "required": ["kind", "count"]}}

STAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "nothing_removed": {"type": "boolean",
                            "description": "true if the two photos show the same state"},
        "removed_parts": {"type": "array", "items": {"type": "string"},
                          "description": "short names, e.g. 'left door', 'top shelf'"},
        "hardware_removed": _HW,
        "description": {"type": "string",
                        "description": "one sentence: what was taken off and from where"},
        "assembly_instruction": {"type": "string",
                                 "description": "one or two sentences telling someone how to PUT IT BACK"},
        "orientation_notes": {"type": "array", "items": {"type": "string"},
                              "description": "cues to get it the right way round, e.g. 'hinges on the left'"},
        "category_guess": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["nothing_removed", "removed_parts", "description", "assembly_instruction", "confidence"],
}

STAGE_INSTRUCTIONS = (
    "You compare two photos of the same piece of furniture during disassembly. Photo A is the "
    "earlier stage, photo B is the later stage after the user removed something. Say exactly what "
    "was removed between A and B, which hardware came out (count only what you can see or what the "
    "user says), and write the assembly instruction for putting it back (the reverse). Note any "
    "orientation cues (which way holes, hinges, finished edges or arrows face). If A and B show the "
    "same state, set nothing_removed=true. Use the user's words when they describe the removal. "
    "Name the kind of furniture in category_guess (e.g. bookcase, wardrobe, crib, bunk_bed, chair). "
    "confidence is 0-1 for how sure you are about removed_parts.")


_HOLES = {"type": "object", "description": "Counts of holes visible on this panel, by kind", "properties": {
    "cam_housing": {"type": "integer", "description": "≈15 mm round holes on a FACE near an edge (cam lock seats)"},
    "cam_bolt": {"type": "integer", "description": "small holes on a face where cam bolts screw in"},
    "dowel_edge": {"type": "integer", "description": "≈8 mm holes drilled into the panel's EDGE"},
    "dowel_face": {"type": "integer", "description": "≈8 mm holes on a FACE (not the shelf-pin rows)"},
    "shelf_pin": {"type": "integer", "description": "≈5 mm holes in vertical rows on a face"},
    "hinge_cup": {"type": "integer", "description": "35 mm shallow round cups (doors)"},
    "screw": {"type": "integer", "description": "pilot holes for screws (e.g. rail supports)"}}}

PARTS_SCHEMA = {
    "type": "object",
    "properties": {
        "parts": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string", "description": "letter/number written or stuck on it, '' if none"},
            "length_mm": {"type": "number"}, "width_mm": {"type": "number"},
            "thickness_mm": {"type": "number", "description": "board thickness; thin hardboard ≈ 3 mm"},
            "quantity": {"type": "integer", "description": "identical panels of this size"},
            "holes": _HOLES,
            "groove": {"type": "boolean", "description": "a long narrow groove near one long edge (back panel slot)"},
            "description": {"type": "string", "description": "short, e.g. 'long panel with rows of small holes'"},
            "confidence": {"type": "number"}},
            "required": ["length_mm", "width_mm", "thickness_mm", "quantity", "holes", "confidence"]}},
        "hardware": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": HARDWARE_KINDS}, "count": {"type": "integer"},
            "size_hint": {"type": "string"}}, "required": ["kind", "count"]}},
        "scale_reference_seen": {"type": "boolean", "description": "an A4 sheet or tape measure is visible"},
        "category_guess": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["parts", "hardware", "uncertainties"],
}

PARTS_INSTRUCTIONS = (
    "You read photos of flat-pack furniture panels and hardware laid out on the floor so a program can "
    "work out how they assemble. Outer size of the assembled piece (from the user's tape measure): "
    "{dims}. If an A4 sheet (297 × 210 mm) is visible, use it as the scale reference. List every DISTINCT "
    "panel once (identical panels: one entry with quantity). The same panel may appear in several photos: "
    "don't count it twice. Estimate length, width and thickness in mm; panels usually relate to the outer "
    "size (sides ≈ height × depth, top/bottom ≈ width minus two board thicknesses, back ≈ height × width "
    "and ≈ 3 mm thick). Count holes by kind as defined in the schema; 0 if none visible. Count loose "
    "hardware by kind. Put anything you're unsure about in uncertainties. Never invent panels you can't "
    "see. Name the kind of furniture in category_guess.")


def parts_input(images: list[bytes], dims_text: str, note: str = "") -> list[dict]:
    blocks: list[dict] = [{"type": "text", "text": f"Outer size: {dims_text}. {note}".strip()}]
    blocks += [{"type": "image", "data": b, "mime_type": "image/jpeg"} for b in images]
    return blocks


CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean", "description": "the user's photo shows the expected result of this step"},
        "issues": {"type": "array", "items": {"type": "object", "properties": {
            "severity": {"type": "string", "enum": ["stop", "warn", "info"],
                         "description": "stop = wrong and must be fixed before continuing"},
            "text": {"type": "string", "description": "plain words: what's wrong and how to fix it"}},
            "required": ["severity", "text"]}},
        "what_i_see": {"type": "string"},
        "photo_quality": {"type": "string", "enum": ["good", "blurry", "dark", "too_far", "wrong_subject"]},
        "confidence": {"type": "number", "description": "0-1: how sure you are about matches"},
    },
    "required": ["matches", "issues", "photo_quality", "confidence"],
}

CHECK_INSTRUCTIONS = (
    "You check one furniture assembly step from the user's photo. Image 1 is the REFERENCE for how it "
    "should look after this step (a drawing, a manual page, or a photo). The other image(s) are the "
    "user's photo(s). Step: {title}. Instruction: {instruction}. Things to verify: {checks}. Compare "
    "carefully: wrong panel, panel upside down or back to front (holes must face inward, finished edges "
    "to the front, cam lock arrows toward the edge), missing hardware, missing part, wrong position. "
    "Report each problem as an issue: severity 'stop' if it must be fixed before continuing, 'warn' if "
    "worth a look, 'info' otherwise; say how to fix it in plain words. If the photo is blurry, dark, too "
    "far or doesn't show the furniture, set photo_quality accordingly and confidence low. Don't approve "
    "what you can't see.")


IDENTIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": {"type": "string", "description": "Brand or maker, '' if not visible"},
        "product_name": {"type": "string", "description": "Product/model name, '' if not visible"},
        "article_numbers": {"type": "array", "items": {"type": "string"},
                            "description": "Article/model/part numbers exactly as printed"},
        "visible_text": {"type": "string", "description": "Other text on labels or stamps"},
        "category_guess": {"type": "string",
                           "description": "bookcase, wardrobe, closet, cabinet, nightstand, desk, crib, "
                                          "bunk_bed, bed, high_chair, chair, sofa, other"},
        "confidence": {"type": "number", "description": "0-1: how sure the identification is"},
        "search_queries": {"type": "array", "items": {"type": "string"},
                           "description": "2-4 web searches most likely to find the official assembly "
                                          "instructions PDF"},
    },
    "required": ["brand", "product_name", "article_numbers", "category_guess", "confidence", "search_queries"],
}

IDENTIFY_INSTRUCTIONS = (
    "Identify this piece of furniture so we can find its official assembly manual. Read every label, "
    "sticker, stamp and printed number exactly as written (article numbers like 'AA-2289541-3' or "
    "'802.758.87' are gold). Recognise the brand from logos or typical design if you can, but don't "
    "invent model names: leave fields empty if not visible. Then propose web searches, e.g. "
    "'<brand> <article number> assembly instructions pdf'.")


def identify_input(images: list[bytes], user_text: str) -> list[dict]:
    blocks: list[dict] = [{"type": "text", "text": f"User says: {user_text or '(nothing)'}"}]
    blocks += [{"type": "image", "data": b, "mime_type": "image/jpeg"} for b in images]
    return blocks


def stage_input(prev_jpeg: bytes, cur_jpeg: bytes, user_text: str) -> list[dict]:
    return [
        {"type": "text", "text": f"User says they removed: {user_text or '(not stated)'}"},
        {"type": "text", "text": "Photo A (earlier stage):"},
        {"type": "image", "data": prev_jpeg, "mime_type": "image/jpeg"},
        {"type": "text", "text": "Photo B (later stage):"},
        {"type": "image", "data": cur_jpeg, "mime_type": "image/jpeg"},
    ]
