"""3D scene JSON v1 for the Desktop step viewer (docs/07 §2)."""
from __future__ import annotations

from .render import EXPLODE, _role_key

VERSION = 1


def build(project_id: str, outer: dict, plan: dict) -> dict:
    P, roles = plan["placements"], plan["roles"]
    W = max((b["pos"][0] + b["size"][0] for b in P.values()), default=1)
    H = max((b["pos"][1] + b["size"][1] for b in P.values()), default=1)
    mag = round(0.25 * max(W, H), 1)
    parts = [{"id": k, "label": k.split(".")[0], "role": roles.get(k, "unknown"), "size": b["size"],
              "color_role": "back" if roles.get(k) == "back" else "panel"} for k, b in P.items()]
    steps = []
    for s in plan["steps"]:
        steps.append({
            "index": s["index"], "title": s["title"],
            "placed": [{"id": k, "pos": P[k]["pos"], "rot": [0, 0, 0]} for k in s.get("placed") or [] if k in P],
            "added": [k for k in s.get("parts_added") or [] if k in P],
            "explode_from": {k: [c * mag for c in EXPLODE.get(_role_key(roles[k], k, P, W), (0, 0, 1))]
                             for k in s.get("parts_added") or [] if k in P},
            "hardware": s.get("hardware_used") or [],
            "confidence": s.get("confidence", 1.0),
        })
    return {"version": VERSION, "units": "mm", "project_id": project_id,
            "outer_dims": {"w": outer["w"], "h": outer["h"], "d": outer["d"]}, "parts": parts, "steps": steps}


def validate(scene: dict) -> list[str]:
    """Return a list of problems ([] = valid)."""
    errs = []
    if scene.get("version") != VERSION or scene.get("units") != "mm":
        errs.append("version/units")
    ids = {p["id"] for p in scene.get("parts", [])}
    for p in scene.get("parts", []):
        if len(p.get("size", [])) != 3 or min(p["size"]) <= 0:
            errs.append(f"bad size {p.get('id')}")
    for s in scene.get("steps", []):
        for pl in s.get("placed", []):
            if pl["id"] not in ids or len(pl["pos"]) != 3 or len(pl["rot"]) != 3:
                errs.append(f"step {s.get('index')}: bad placement {pl.get('id')}")
        if not set(s.get("added", [])) <= {pl["id"] for pl in s.get("placed", [])}:
            errs.append(f"step {s.get('index')}: added part not placed")
    return errs
