"""Hardware count check (docs/04 F7): holes in panels vs hardware the user has."""
from __future__ import annotations

from .geometry import holes

SIZE_HINT = {"cam_lock": "≈15 mm", "cam_bolt": "M6", "dowel": "8×30 mm", "shelf_pin": "5 mm",
             "hinge": "35 mm cup", "wall_anchor": "for your wall type"}


def _have(hardware: list[dict], kind: str) -> int:
    return sum(int(h.get("count") or 0) for h in hardware if h.get("kind") == kind)


def _name(kind: str, n: int) -> str:
    base = kind.replace("_", " ")
    return base if n == 1 else base + "s"


def check(parts: list[dict], hardware: list[dict], loose_shelves: int, tall: bool) -> dict:
    """parts must be expanded instances. Returns {ok, lines, mismatches}."""
    total = {k: 0 for k in ("cam_housing", "cam_bolt", "dowel_edge", "dowel_face", "shelf_pin", "hinge_cup")}
    for p in parts:
        q = max(1, int(p.get("quantity") or 1))
        for k, v in holes(p).items():
            if k in total:
                total[k] += v * q
    edge, face = total["dowel_edge"], total["dowel_face"]
    need = {
        "cam_lock": total["cam_housing"],
        "cam_bolt": total["cam_bolt"],
        # one dowel per pair of mating holes (edge hole ↔ face hole)
        "dowel": min(edge, face) if edge and face else max(edge, face),
        "shelf_pin": 4 * loose_shelves if loose_shelves else 0,
        "hinge": total["hinge_cup"],
    }
    lines, mismatches = [], 0
    for kind, n in need.items():
        have = _have(hardware, kind)
        if n == 0 and have == 0:
            continue
        what = "Holes for" if kind != "shelf_pin" else "Shelves need"
        if have == n:
            lines.append(f"{what} {n} {_name(kind, n)}, {have} found — complete.")
        elif have < n:
            mismatches += 1
            lines.append(f"{what} {n} {_name(kind, n)}, but {have} found. Missing {n - have} × "
                         f"{kind.replace('_', ' ')} ({SIZE_HINT.get(kind, '')}).")
        elif n == 0:
            lines.append(f"{have} {_name(kind, have)} found but no matching holes seen — check the panels.")
        else:
            lines.append(f"{what} {n} {_name(kind, n)}; you have {have} (spares are fine).")
    if tall and _have(hardware, "wall_anchor") == 0:
        lines.append("No wall anchor found. Get an anti-tip kit suited to your wall before standing it up.")
    return {"ok": mismatches == 0, "lines": lines, "mismatches": mismatches}
