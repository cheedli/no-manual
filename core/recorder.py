"""Disassembly recorder: stages [0..n] -> n assembly steps in reverse (docs/04 F4)."""
from __future__ import annotations

from .safety import ANTI_TIP_STEP, needs_anti_tip


def _title(described: dict, user_text: str) -> str:
    parts = [p for p in described.get("removed_parts") or [] if p]
    if parts:
        t = "Attach the " + ", ".join(parts[:3])
    elif user_text:
        t = "Put back: " + user_text
    else:
        t = "Reassemble this part"
    return t[:60]


def build_steps(stages: list[dict], category: str, height_mm: float | None) -> list[dict]:
    """Assembly step k reverses removal stage r = n-k+1 (state r -> state r-1).
    The step picture is the user's photo of stage r-1 (what it looks like when done)."""
    n = len(stages) - 1
    steps = []
    for k in range(1, n + 1):
        r = n - k + 1
        removal, after = stages[r], stages[r - 1]
        d = removal.get("described") or {}
        user_text = removal.get("user_text") or ""
        conf = float(d.get("confidence", 0.7) or 0.7)
        steps.append({
            "index": k,
            "title": _title(d, user_text),
            "instruction": d.get("assembly_instruction") or f"Reverse this: {d.get('description') or user_text}",
            "hardware_used": [h for h in d.get("hardware_removed") or [] if h.get("count")],
            "image_path": "",
            "source_photo": (after.get("photo_paths") or [""])[0],
            "expected_state": f"Same as the reference photo: {', '.join(d.get('removed_parts') or []) or user_text} back in place.",
            "checks": list(d.get("orientation_notes") or []),
            "confidence": round(min(conf, 0.85), 2),
            "from_stage": r,
        })
    if needs_anti_tip(category, height_mm):
        steps.append({**ANTI_TIP_STEP, "index": len(steps) + 1, "image_path": "",
                      "source_photo": (stages[0].get("photo_paths") or [""])[0],
                      "expected_state": "Furniture fixed to the wall."})
    return steps
