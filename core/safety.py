"""Safety gate (docs/08 §1). Fails closed: user category OR vision guess blocked -> blocked."""
from __future__ import annotations

import re

BLOCKED_STATUS = "blocked_child_or_load"

# Children's furniture and anything a person sits, sleeps, stands or climbs on,
# plus wall-mounted pieces that hold weight.
BLOCKED_CATEGORIES = frozenset({
    "crib", "cot", "bunk_bed", "loft_bed", "bed", "high_chair", "changing_table", "playpen",
    "stair_gate", "chair", "sofa", "stool", "bench", "step_stool", "wall_shelf", "wall_cabinet",
})

CATEGORIES = ["closet", "wardrobe", "bookcase", "cabinet", "nightstand", "desk", "table",
              *sorted(BLOCKED_CATEGORIES), "other"]

# Tools that produce generated instructions; never for blocked projects.
GENERATING_TOOLS = frozenset({"nm_solve", "nm_render_steps", "nm_finish_recording", "nm_extract_parts",
                              "nm_record_stage"})
# Tools that serve steps: allowed for blocked projects only when the steps are the official manual.
STEP_TOOLS = frozenset({"nm_get_step", "nm_check_step"})

BLOCK_MESSAGE = (
    "For children's furniture and anything people sit, sleep or climb on, No Manual only uses "
    "the official manufacturer manual. I won't generate assembly steps for this piece.")

DISCLAIMER = (
    "Instructions generated from photos are a best effort. Follow the official manual whenever "
    "one exists. Don't use generated instructions for children's furniture or anything people "
    "sit, sleep or climb on.")


def normalize_category(raw: str | None) -> str:
    c = (raw or "other").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"baby_bed": "crib", "bassinet": "crib", "bunk": "bunk_bed", "loft": "loft_bed",
               "highchair": "high_chair", "changing_unit": "changing_table", "couch": "sofa",
               "armchair": "chair", "shelf": "bookcase", "bookshelf": "bookcase",
               "dresser": "cabinet", "chest_of_drawers": "cabinet", "bedside_table": "nightstand",
               "playard": "playpen", "baby_gate": "stair_gate"}
    c = aliases.get(c, c)
    return c if c in CATEGORIES else "other"


_BLOCK_WORDS = re.compile(
    r"\b(crib|cribs|cot|cots|bassinet|cradle|bunk|loft[ _-]?bed|bed|beds|bed[ _-]?frame|daybed|"
    r"high[ _-]?chair|highchair|changing[ _-]?(table|unit)|playpen|play[ _-]?yard|stair[ _-]?gate|"
    r"baby[ _-]?gate|chair|chairs|armchair|stool|bench|sofa|couch|wall[ _-]?(shelf|cabinet|unit))\b",
    re.IGNORECASE)


def mentions_blocked(*texts) -> bool:
    """Fail closed on free text too (title, raw category, product name): 'toddler bed' -> blocked."""
    return any(t and _BLOCK_WORDS.search(str(t).replace("_", " ")) for t in texts)


def is_blocked(category: str | None) -> bool:
    return normalize_category(category) in BLOCKED_CATEGORIES


def apply_vision_guess(project, guess: str | None, confidence: float) -> bool:
    """Re-classify a project as blocked if vision sees blocked furniture (conf >= 0.5).
    Returns True if the project was newly blocked."""
    if project.blocked or not guess or confidence < 0.5 or not is_blocked(guess):
        return False
    block(project, f"Photos look like a {normalize_category(guess).replace('_', ' ')}.")
    return True


def block(project, reason: str) -> None:
    """Mark blocked and drop any generated (non-manual) plan so it can never be served."""
    project.safety_status, project.safety_reason, project.state = BLOCKED_STATUS, reason, "blocked"
    if project.plan and project.plan.get("source") != "manual":
        project.plan, project.current_step = None, 1


def allowed_modes(project) -> list[str]:
    return ["manual"] if project.blocked else ["manual", "recorder", "solver"]


def needs_anti_tip(category: str, height_mm: float | None) -> bool:
    """Tall furniture (>= 75 cm) gets a wall-anchoring step. Unknown height fails closed,
    except for categories that are almost always low."""
    if height_mm is not None:
        return height_mm >= 750
    return normalize_category(category) not in {"nightstand", "table", "desk"}


ANTI_TIP_STEP = {
    "title": "Anchor it to the wall",
    "instruction": ("Fix the furniture to the wall with the anti-tip hardware. Use screws and plugs "
                    "suited to your wall type (drywall, brick, wood). If you're unsure, ask for help."),
    "hardware_used": [{"kind": "wall_anchor", "count": 1}],
    "checks": ["anti-tip strap or bracket fixed to the wall"],
    "confidence": 1.0,
    "safety": True,
}
