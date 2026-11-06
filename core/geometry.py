"""Board classification for carcass furniture (docs/06 §2). Pure Python.

Part dict (from extraction / user confirmation):
  {"id": "P1", "dims_mm": {"length", "width", "thickness"}, "quantity": 1,
   "holes": {"cam_housing", "cam_bolt", "dowel_edge", "dowel_face", "shelf_pin", "hinge_cup", "screw"},
   "groove": bool, "role": optional (user-confirmed), "confirmed": bool}

ponytail: holes are per-kind counts, not positions; vision can't place holes reliably (ADR-005)
and the templates only need "has edge joinery / shelf-pin rows / hinge cups".
"""
from __future__ import annotations

from statistics import median

ROLE_NAMES = {"side": "side", "top": "top", "bottom": "bottom", "shelf_fixed": "fixed shelf",
              "shelf_loose": "loose shelf", "back": "back panel", "door": "door", "plinth": "plinth",
              "divider": "divider", "unknown": "unknown part"}
ROLES = ("side", "top", "bottom", "shelf_fixed", "shelf_loose", "back", "door", "plinth", "divider", "unknown")
HORIZONTAL = ("top", "bottom", "shelf_fixed", "shelf_loose")


def tol(x: float) -> float:
    """±3% or ±8 mm, whichever is larger."""
    return max(0.03 * x, 8.0)


def err(value: float, lo: float, hi: float | None = None) -> float:
    """Distance from [lo, hi] in tolerance units (0 = inside, 1 = at tolerance edge)."""
    hi = lo if hi is None else hi
    if lo <= value <= hi:
        return 0.0
    edge = lo if value < lo else hi
    return abs(value - edge) / tol(edge)


def holes(p: dict) -> dict:
    h = p.get("holes") or {}
    return {k: int(h.get(k) or 0) for k in ("cam_housing", "cam_bolt", "dowel_edge", "dowel_face",
                                             "shelf_pin", "hinge_cup", "screw")}


def ab(p: dict) -> tuple[float, float, float]:
    d = p["dims_mm"]
    a, b = sorted((float(d["length"]), float(d["width"])), reverse=True)
    return a, b, float(d.get("thickness") or 0)


def board_thickness(parts: list[dict]) -> float:
    ts = [ab(p)[2] for p in parts if ab(p)[2] > 6]
    return median(ts) if ts else 16.0


def edge_joinery(p: dict) -> bool:
    h = holes(p)
    return h["cam_housing"] > 0 or h["dowel_edge"] > 0


def candidates(p: dict, W: float, H: float, D: float, t: float) -> list[tuple[str, float, bool]]:
    """[(role, error, hole_evidence)] sorted by error. Horizontal roles are returned as
    'horizontal_between' / 'horizontal_cap'; the solver splits them into top/bottom/shelves."""
    a, b, th = ab(p)
    h = holes(p)
    out = []
    if th and th <= 6:
        # either orientation: a wide low cabinet's back is longer than it is tall
        out.append(("back", min(max(err(a, H - 20, H), err(b, W - 20, W)),
                                max(err(a, W - 20, W), err(b, H - 20, H))), True))
        return sorted(out, key=lambda x: x[1])
    out.append(("side", max(err(a, H), err(b, D - 30, D)), h["shelf_pin"] > 0 or h["cam_bolt"] > 0 or h["dowel_face"] > 0))
    out.append(("side_capped", max(err(a, H - 2 * t), err(b, D - 30, D)),
                h["shelf_pin"] > 0 or h["dowel_face"] > 0 or h["dowel_edge"] > 0))
    out.append(("divider", max(err(a, H - 2 * t), err(b, D - 30, D)), edge_joinery(p)))
    # shelves are often a few cm shallower than the sides (back panel, door clearance)
    out.append(("horizontal_between", max(err(a, W - 2 * t), err(b, D - 80, D)), edge_joinery(p)))
    out.append(("horizontal_cap", max(err(a, W), err(b, D - 30, D)), h["dowel_face"] > 0 or h["screw"] > 0))
    out.append(("plinth", max(err(a, W - 2 * t), err(b, 50, 120)), edge_joinery(p)))
    # doors run full height, or stop above a plinth (≤ 130 mm)
    door_e = max(err(a, H - 130, H), min(err(b, W / 2 - 10, W / 2), err(b, W - 10, W)))
    if h["hinge_cup"] > 0:
        out.append(("door", door_e, True))
    else:
        out.append(("door", door_e + 0.5, False))  # doors without hinge cups are unlikely
    return sorted(out, key=lambda x: x[1])


def expand(parts: list[dict]) -> list[dict]:
    """quantity n -> n instances ("P4", "P4.2", ...), each a shallow copy."""
    out = []
    for p in parts:
        q = max(1, int(p.get("quantity") or 1))
        for k in range(q):
            out.append({**p, "id": p["id"] if k == 0 else f"{p['id']}.{k + 1}", "base_id": p["id"], "quantity": 1})
    return out
