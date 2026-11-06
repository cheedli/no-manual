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
