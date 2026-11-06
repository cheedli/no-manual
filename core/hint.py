"""Cheap keyword matcher for the pre_llm_call skill hint (EN/FR/AR/ES)."""
from __future__ import annotations

import re

KEYWORDS = [
    # English
    "assemble", "assembly", "reassemble", "put together", "manual", "instructions", "flat-pack",
    "flatpack", "flat pack", "closet", "wardrobe", "bookcase", "bookshelf", "cabinet", "nightstand",
    "dresser", "ikea", "cam lock", "dowel", "allen key", "furniture", "disassemble", "took apart",
    "take apart", "nomanual", "no manual",
    # French
    "monter", "montage", "notice de montage", "meuble", "armoire", "étagère", "etagere", "placard", "commode",
    "démonter", "demonter", "remonter", "chevilles",
    # Spanish
    "montar", "armar", "mueble", "instrucciones", "armario", "estantería", "estanteria", "manual de",
    "desmontar", "tornillos",
    # Arabic
    "تركيب", "أثاث", "اثاث", "خزانة", "دليل", "تعليمات", "مكتبة", "تفكيك", "براغي",
]

_PATTERNS = [re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)", re.IGNORECASE) for k in KEYWORDS]

HINT = ("The No Manual plugin is installed. If the user wants help assembling or reassembling "
        "furniture, load skill_view('no-manual:no-manual-guide') and follow it.")


def looks_like_furniture_request(text: str | None) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _PATTERNS)
