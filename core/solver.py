"""Template solver for carcass furniture (docs/06). Pure Python, deterministic.

solve(parts, hardware, outer, category) -> plan dict with ordered steps, per-step placed parts,
world placements (for rendering), confidence, warnings and questions.

ponytail: placements are world-axis boxes (pos = min corner, size = extents), no rotations;
every board in a carcass is axis-aligned. Shelves + divider together aren't split per bay yet.
"""
from __future__ import annotations

from . import hardware as hw
from .geometry import ROLE_NAMES, ab, board_thickness, candidates, edge_joinery, expand, holes
from .safety import ANTI_TIP_STEP, needs_anti_tip

T1_ROLES = {"side", "divider", "horizontal_between", "plinth", "back", "door"}
T2_ROLES = {"side_capped", "horizontal_cap", "horizontal_between", "back", "door", "plinth"}
CONF_PROCEED, CONF_ASK = 0.75, 0.6


def _cm(x: float) -> str:
    return f"{x / 10:g}"


def _pick(p: dict, allowed: set, W, H, D, t):
    cands = [c for c in candidates(p, W, H, D, t) if c[0] in allowed]
    return cands[0] if cands else ("unknown", 99.0, False)


def _has_hw(hardware, kind) -> int:
    return sum(int(h.get("count") or 0) for h in hardware if h.get("kind") == kind)


def solve(parts: list[dict], hardware: list[dict], outer: dict, category: str = "other") -> dict:
    W, H, D = float(outer["w"]), float(outer["h"]), float(outer["d"])
    inst = expand(parts)
    t = board_thickness(inst)
    warnings: list[str] = []
    questions: list[str] = []

    # ---- 1. template from the horizontals: between the sides (T1) or capping them (T2)
    first = {p["id"]: candidates(p, W, H, D, t)[0] for p in inst if not p.get("role")}
    n_between = sum(1 for c in first.values() if c[0] == "horizontal_between")
    n_cap = sum(1 for c in first.values() if c[0] == "horizontal_cap")
    confirmed_cap = any(p.get("role") in ("top", "bottom") and abs(ab(p)[0] - W) < abs(ab(p)[0] - (W - 2 * t))
                        for p in inst)
    template = "T2" if (n_cap > n_between or confirmed_cap) else "T1"
    allowed = T2_ROLES if template == "T2" else T1_ROLES

    # ---- 2. roles
    roles, perr, evidence = {}, {}, {}
    for p in inst:
        if p.get("role") and p["role"] != "unknown":
            roles[p["id"]], perr[p["id"]], evidence[p["id"]] = p["role"], 0.0, True
            continue
        role, e, ev = _pick(p, allowed, W, H, D, t)
        if e > 2.0:
            role = "unknown"
        roles[p["id"]] = {"side_capped": "side"}.get(role, role)
        perr[p["id"]], evidence[p["id"]] = e, ev
    by = lambda r: [p for p in inst if roles[p["id"]] == r]

    # horizontals -> top / bottom / fixed / loose shelves
    cap_role = "horizontal_cap" if template == "T2" else "horizontal_between"
    caps = by(cap_role)
    shelves = by("horizontal_between") if template == "T2" else []
    ambiguous_tb = False
    if template == "T1":
        joined = [p for p in caps if edge_joinery(p)]
        loose = [p for p in caps if not edge_joinery(p)]
        joined.sort(key=lambda p: ab(p)[1], reverse=True)  # deepest joined boards = top/bottom
        have_tb = sum(1 for p in inst if p.get("role") in ("top", "bottom"))  # user-confirmed already
        if len(joined) + have_tb < 2 and caps:
            ambiguous_tb = True
            need = 2 - len(joined) - have_tb
            joined, loose = joined + loose[:need], loose[need:]
        tb, fixed = joined[:2], joined[2:]
    else:
        tb, fixed, loose = caps[:2], [p for p in shelves if edge_joinery(p)], [p for p in shelves if not edge_joinery(p)]
    has_plinth, has_rail = bool(by("plinth")), _has_hw(hardware, "rail") > 0
    if len(tb) == 2:
        # Rail-support screw holes mark the top; with a plinth, extra holes mark the bottom.
        scr = lambda p: holes(p)["screw"]
        tot = lambda p: sum(holes(p).values())
        if has_rail and scr(tb[0]) != scr(tb[1]):
            top, bottom = sorted(tb, key=scr, reverse=True)
        elif has_plinth and tot(tb[0]) != tot(tb[1]):
            bottom, top = sorted(tb, key=tot, reverse=True)
        else:
            bottom, top = tb
        roles[bottom["id"]], roles[top["id"]] = "bottom", "top"
        if sum(holes(tb[0]).values()) == sum(holes(tb[1]).values()):
            warnings.append(f"{tb[0]['id']} and {tb[1]['id']} look identical: either can be the top or the bottom.")
    for p in fixed:
        roles[p["id"]] = "shelf_fixed"
    for p in loose:
        roles[p["id"]] = "shelf_loose"
    for pid, r in roles.items():  # leftover horizontals that fit no slot
        if r.startswith("horizontal"):
            roles[pid] = "unknown"
    for p in inst:  # user-confirmed roles win over the split above
        if p.get("role") and p["role"] != "unknown":
            roles[p["id"]] = p["role"]
    side_pin = any(holes(p)["shelf_pin"] for p in by("side"))
    for p in by("shelf_loose"):
        evidence[p["id"]] = evidence[p["id"]] or side_pin

    sides, tops, bottoms = by("side"), by("top"), by("bottom")
    unknown = by("unknown")

    # ---- 3. confidence (docs/06 §5)
    conf, part_conf = 1.0, {}
    for p in inst:
        pc = 1.0
        if roles[p["id"]] == "unknown":
            conf *= 0.85
            pc = 0.4
        elif not p.get("confirmed") and not evidence.get(p["id"]):
            conf *= 0.9
            pc = 0.9
        if 1.0 < perr.get(p["id"], 0) <= 2.0 and not p.get("confirmed"):
            pc = min(pc, 0.6)
        part_conf[p["id"]] = pc
    if any(1.0 < perr.get(p["id"], 0) <= 2.0 and not p.get("confirmed") for p in inst):
        conf *= 0.7
    tall = needs_anti_tip(category, H)
    check = hw.check(inst, hardware, len(by("shelf_loose")), tall)
    conf *= 0.8 ** check["mismatches"]
    if not check["ok"]:
        warnings += [line for line in check["lines"] if "Missing" in line]

    # structural sanity
    if len(sides) != 2 or not tops or not bottoms:
        conf = min(conf, 0.4)
        if len(sides) != 2:
            questions.append(f"I found {len(sides)} side panels about {_cm(H)} cm tall; a carcass has 2. "
                             "Which panels are the sides?")
        if not (tops and bottoms):
            questions.append("How does the top meet the sides: does it sit between them, or on top of them "
                             "covering their edges? A photo of the top's edge would help.")
    if unknown:
        conf = min(conf, 0.74)
        for p in unknown[:3]:
            a, b, _ = ab(p)
            questions.append(f"What is {p['id']} ({_cm(a)} × {_cm(b)} cm)? A side, shelf, top/bottom, back, door, "
                             "or something else?")
    if ambiguous_tb:
        conf = min(conf, 0.55)  # top/bottom were guessed from boards without joinery: ask first
        ids = ", ".join(p["id"] for p in caps)
        questions.append(f"Which of {ids} have holes on their short ends (for cam locks or dowels)? "
                         "Those are the top and bottom.")
    for p in inst:
        if 1.0 < perr.get(p["id"], 0) <= 2.0 and not p.get("confirmed"):
            a, b, _ = ab(p)
            questions.append(f"Can you re-measure {p['id']}? I have {_cm(a)} × {_cm(b)} cm, a bit off for a "
                             f"{ROLE_NAMES.get(roles[p['id']], roles[p['id']])}.")
    conf = round(max(0.0, min(1.0, conf)), 2)

    steps, placements = _build(template, inst, roles, part_conf, hardware, check, W, H, D, t, category)
    return {"source": "solver", "template": template, "confidence": conf, "thickness_mm": t,
            "roles": roles, "steps": steps, "placements": placements, "warnings": warnings,
            "questions": questions[:4], "hardware_check": {"ok": check["ok"], "lines": check["lines"]},
            "ready": conf >= CONF_ASK}


# ------------------------------------------------------------------ placement + steps

def _place(template, inst, roles, W, H, D, t) -> dict:
    P = {}
    get = lambda r: [p for p in inst if roles[p["id"]] == r]
    backs = get("back")
    groove = any(p.get("groove") for p in get("side"))
    bt = ab(backs[0])[2] if backs else 0
    z0 = 0 if groove else bt
    sides = get("side")
    Ds = ab(sides[0])[1] if sides else D - z0
    plinths = get("plinth")
    ph = ab(plinths[0])[1] if plinths and template == "T1" else 0.0

    def box(pid, x, y, z, sx, sy, sz):
        P[pid] = {"pos": [round(x, 1), round(y, 1), round(z, 1)], "size": [round(sx, 1), round(sy, 1), round(sz, 1)]}

    if template == "T1":
        for i, p in enumerate(sides[:2]):
            box(p["id"], 0 if i == 0 else W - t, 0, z0, t, H, Ds)
        for p in get("bottom"):
            box(p["id"], t, ph, z0, W - 2 * t, t, ab(p)[1])
        for p in get("top"):
            box(p["id"], t, H - t, z0, W - 2 * t, t, ab(p)[1])
        for p in plinths:
            box(p["id"], t, 0, z0 + Ds - t - 20, W - 2 * t, ph, ab(p)[2] or t)
        for p in get("divider"):
            box(p["id"], (W - t) / 2, ph + t, z0, t, H - 2 * t - ph, ab(p)[1])
        y_lo, y_hi, inner_w, x0 = ph + t, H - t, W - 2 * t, t
    else:
        for p in get("bottom"):
            box(p["id"], 0, 0, z0, W, t, ab(p)[1])
        for p in get("top"):
            box(p["id"], 0, H - t, z0, W, t, ab(p)[1])
        for i, p in enumerate(sides[:2]):
            box(p["id"], 0 if i == 0 else W - t, t, z0, t, H - 2 * t, Ds)
        y_lo, y_hi, inner_w, x0 = t, H - t, W - 2 * t, t

    shelves = get("shelf_fixed") + get("shelf_loose")
    n = len(shelves)
    if n:
        gap = (y_hi - y_lo) / (n + 1)
        slots = [y_lo + gap * (i + 1) - t / 2 for i in range(n)]
        mid = sorted(range(n), key=lambda i: abs(i - (n - 1) / 2))  # fixed shelves take the middle slots
        order = {p["id"]: slots[mid[k]] for k, p in enumerate(get("shelf_fixed"))}
        free = [slots[i] for i in range(n) if slots[i] not in order.values()]
        for k, p in enumerate(get("shelf_loose")):
            order[p["id"]] = free[k]
        for p in shelves:
            box(p["id"], x0, order[p["id"]], z0, inner_w, t, ab(p)[1])
    for p in backs:
        a, b, th = ab(p)
        sx, sy = (b, a) if abs(a - H) <= abs(a - W) else (a, b)  # wide cabinets: long side horizontal
        box(p["id"], (W - sx) / 2, (H - sy) / 2 if groove else 0, 8 if groove else 0, sx, sy, th)
    doors = get("door")
    x = 0.0
    for p in doors:
        a, b, th = ab(p)
        box(p["id"], x, (H - a) / 2 if not ph else ph + (H - ph - a) / 2, z0 + Ds, b, a, th or t)
        x += b
    return P


def _ids(ps):
    return [p["id"] for p in ps]


def _names(ps):
    return ", ".join(p["id"] for p in ps)


def _build(template, inst, roles, part_conf, hardware, check, W, H, D, t, category):
    get = lambda r: [p for p in inst if roles[p["id"]] == r]
    P = _place(template, inst, roles, W, H, D, t)
    sides, top, bottom = get("side"), get("top"), get("bottom")
    fixed, loose, backs, doors = get("shelf_fixed"), get("shelf_loose"), get("back"), get("door")
    plinths, dividers = get("plinth"), get("divider")
    total = {k: sum(holes(p)[k] for p in inst) for k in ("cam_housing", "cam_bolt", "dowel_edge", "dowel_face")}
    cams = max(total["cam_housing"], _has_hw(hardware, "cam_lock"))
    bolts = max(total["cam_bolt"], _has_hw(hardware, "cam_bolt"))
    dowels = max(min(total["dowel_edge"], total["dowel_face"]) or max(total["dowel_edge"], total["dowel_face"]),
                 _has_hw(hardware, "dowel"))
    groove = any(p.get("groove") for p in sides)
    steps, placed = [], []

    def add(title, instruction, parts=(), hardware_used=(), checks=(), two_people=False):
        placed.extend(_ids(parts))
        c = min([part_conf.get(p["id"], 1.0) for p in parts] or [1.0])
        steps.append({"index": len(steps) + 1, "title": title, "instruction": instruction,
                      "parts_added": _ids(parts), "placed": list(placed),
                      "hardware_used": [h for h in hardware_used if h["count"]], "checks": list(checks),
                      "two_people": two_people, "confidence": round(c, 2), "image_path": "", "scene_path": None,
                      "expected_state": instruction})

    inv = ", ".join(f"{p['id']} {ROLE_NAMES.get(roles[p['id']], roles[p['id']])}" for p in inst)
    hw_inv = ", ".join(f"{h['count']} × {h['kind'].replace('_', ' ')}" for h in hardware if h.get("count")) or "none listed"
    unknown = [p for p in inst if roles[p["id"]] == "unknown"]
    add("Sort the parts and hardware", f"Lay out every panel and label it: {inv}. Hardware: {hw_inv}." +
        (f" Set aside {_names(unknown)}: I don't know where it goes yet; tell me what it is." if unknown else ""),
        checks=["all panels and hardware counted"])
    if unknown:
        steps[-1]["confidence"] = 0.4

    prep = [{"kind": "cam_bolt", "count": bolts}, {"kind": "dowel", "count": dowels}]
    if bolts or dowels:
        what = " and ".join(w for w, n in (("cam bolts", bolts), ("dowels", dowels)) if n)
        add(f"Insert {what} into the sides" if template == "T1" else f"Insert {what}",
            f"Screw the cam bolts in by hand until snug and tap the dowels in halfway, into the holes on the "
            f"inner faces of the sides ({_names(sides)})." if template == "T1" else
            f"Tap the dowels into their holes.",
            hardware_used=prep, checks=["bolts hand-tight, not over-screwed", "dowels stick out evenly"])
    if cams:
        targets = [w for w, ps in (("top", top), ("bottom", bottom), ("shelves", fixed)) if ps]
        tgt = ", ".join(targets[:-1]) + " and " + targets[-1] if len(targets) > 1 else (targets[0] if targets else "panels")
        add(f"Insert cam locks into the {tgt}",
            "Press a cam lock into each large round hole, with the arrow pointing toward the edge hole.",
            hardware_used=[{"kind": "cam_lock", "count": cams}], checks=["cam lock arrows point to the edge"])

    tall_two = H >= 1500
    if template == "T1":
        left, right = sides[:1], sides[1:2]
        add("Lay the left side flat, inner face up",
            f"Lay {_names(left)} on a soft surface with the holes facing up and the finished front edge "
            "toward you.", left, checks=["holes face up (inward)", "finished edge faces front"])
        add("Attach the bottom", f"Fit {_names(bottom)} onto the bolts/dowels at the bottom of the side.",
            bottom, checks=["edge holes line up", "finished edge faces front"])
        if dividers:
            add("Attach the divider", f"Fit {_names(dividers)} upright onto the middle of the bottom.", dividers,
                checks=["divider centred and square"])
        add("Attach the top", f"Fit {_names(top)} at the top of the side.", top,
            checks=["edge holes line up", "finished edge faces front"])
        if fixed:
            add("Attach the fixed shelf" if len(fixed) == 1 else "Attach the fixed shelves",
                f"Fit {_names(fixed)} onto the side's bolts/dowels.", fixed, checks=["shelf level"])
        if plinths:
            add("Attach the plinth", f"Fit {_names(plinths)} under the bottom at the front.", plinths)
        if groove:
            for b in backs:
                add("Slide in the back panel", f"Slide {b['id']} into the grooves of the left side, top and "
                    "bottom, finished side facing in.", [b], checks=["back panel fully in the grooves"])
        add("Add the right side and tighten the cam locks" if cams else "Add the right side",
            f"Lower {_names(right)} onto the free ends" + (", then turn every cam lock clockwise until tight."
                                                           if cams else "."),
            right, checks=["all joints flush", "cam locks tight"] if cams else ["all joints flush"])
        add("Square the frame", "Measure both diagonals; nudge the frame until they're equal within 3 mm.",
            checks=["diagonals equal within 3 mm"])
    else:
        if fixed:
            add("Join the sides and fixed shelves", f"Join {_names(sides)} with {_names(fixed)} to make a frame.",
                sides + fixed, checks=["finished edges face front"])
            add("Fit the bottom", f"Fit {_names(bottom)} onto the frame.", bottom, checks=["edges flush"])
            add("Turn it over and fit the top", f"Turn it over and fit {_names(top)}.", top, checks=["edges flush"])
        else:
            add("Fit the sides to the bottom", f"Fit {_names(sides)} onto {_names(bottom)}.", bottom + sides,
                checks=["sides square to the bottom", "finished edges face front"])
            add("Fit the top", f"Fit {_names(top)} onto the sides.", top, checks=["edges flush"])
    for b in backs:
        if groove and template == "T1":
            continue  # already slid in before the right side
        if groove:
            add("Slide in the back panel", f"Slide {b['id']} into the grooves, finished side facing in.", [b],
                checks=["back panel fully in the grooves"])
        else:
            add("Nail on the back panel", f"Place {b['id']} on the back edges, check the frame is square, then "
                "nail it every 10–15 cm.", [b], hardware_used=[{"kind": "nail", "count": _has_hw(hardware, "nail")}],
                checks=["frame square before nailing", "nails go into the panel edges"])
    if template == "T1" or fixed:
        add("Stand it upright", "Stand it up carefully" + (" with a second person." if tall_two else "."),
            two_people=tall_two, checks=["standing on its feet, not on the back"])
    if loose:
        add("Place the loose shelves on shelf pins" if len(loose) > 1 else "Place the loose shelf on shelf pins",
            f"Push 4 shelf pins per shelf into the holes at the height you want, then lay {_names(loose)} on them.",
            loose, hardware_used=[{"kind": "shelf_pin", "count": 4 * len(loose)}],
            checks=["4 pins per shelf at the same height"])
    if doors:
        add("Hang the doors", f"Screw the hinges to the sides, clip on {_names(doors)}, then adjust the gaps.",
            doors, hardware_used=[{"kind": "hinge", "count": sum(holes(p)["hinge_cup"] for p in doors)
                                    or _has_hw(hardware, "hinge")}],
            checks=["doors level, even gaps"])
    if _has_hw(hardware, "rail"):
        add("Fit the hanging rail", "Screw the rail supports under the top, then drop the rail in.",
            hardware_used=[{"kind": "rail", "count": _has_hw(hardware, "rail")}], checks=["rail level"])
    if needs_anti_tip(category, H):
        a = {k: v for k, v in ANTI_TIP_STEP.items()}
        add(a["title"], a["instruction"], hardware_used=a["hardware_used"], checks=a["checks"])
        steps[-1]["safety"] = True
    return steps, P
