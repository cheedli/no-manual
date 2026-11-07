"""Step images (docs/07). Pillow only, no downloaded fonts, no image generation.

Today: letterbox mode (recorder/manual: the user's own photo + header + hardware chips).
Line-art solver mode is added on Day 3.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1350
INK, GREY, AMBER, WHITE = (20, 20, 20), (230, 230, 230), (232, 160, 0), (255, 255, 255)
HEADER_H, FOOTER_H, PAD = 190, 150, 40


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1, bundled font
    except TypeError:
        return ImageFont.load_default()


_GLYPHS = str.maketrans({"×": "x", "•": "-", "—": "-", "–": "-", "≈": "~", "…": "...", "✓": "v", "→": "->"})


def _t(text) -> str:
    """The bundled Pillow font lacks a few symbols; map them to ASCII."""
    return str(text).translate(_GLYPHS)


def _txt(d, xy, text, font, fill):
    d.text(xy, _t(text), font=font, fill=fill)


def _wrap(draw, text: str, font, width: int, max_lines: int = 2) -> list[str]:
    words, lines, line = _t(text).split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,") + "..."
    return lines


def hardware_label(kind: str) -> str:
    return kind.replace("_", " ")


def letterbox_step(photo_path: str | None, out_path: Path, index: int, total: int, title: str,
                   hardware: list[dict], confidence: float = 1.0) -> str:
    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)

    # Header: big step number (IKEA-style) + "Step k of n — title"
    num_font, title_font, small = _font(120), _font(40), _font(30)
    _txt(d, (PAD, 25), str(index), font=num_font, fill=INK)
    num_w = d.textlength(str(index), font=num_font)
    tx = PAD + num_w + 30
    _txt(d, (tx, 40), f"Step {index} of {total}", font=small, fill=(110, 110, 110))
    for i, line in enumerate(_wrap(d, title, title_font, W - tx - PAD)):
        _txt(d, (tx, 85 + i * 48), line, font=title_font, fill=INK)
    if confidence < 0.75:
        badge = "Check this step"
        bw = d.textlength(badge, font=small) + 30
        d.rounded_rectangle((W - PAD - bw, 8, W - PAD, 52), radius=12, fill=AMBER)
        _txt(d, (W - PAD - bw + 15, 14), badge, font=small, fill=INK)

    # Photo, letterboxed
    box = (PAD, HEADER_H, W - PAD, H - FOOTER_H)
    bw, bh = box[2] - box[0], box[3] - box[1]
    if photo_path and Path(photo_path).is_file():
        with Image.open(photo_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((bw, bh))
            canvas.paste(im, (box[0] + (bw - im.width) // 2, box[1] + (bh - im.height) // 2))
    else:
        d.rectangle(box, fill=GREY)
        _txt(d, (box[0] + 30, box[1] + 30), "(no photo)", font=small, fill=INK)
    d.rectangle(box, outline=INK, width=3)

    _chips(d, hardware, H - FOOTER_H + 35)  # footer: icon + count per hardware kind

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return str(out_path)


# ================================================================== solver line art (docs/07 §1)

NEW_FILL, OLD_FILL, LINE_W = (226, 226, 226), (255, 255, 255), 3
_A, _B = math.radians(-35), math.radians(25)
_R = [  # Rx(25°) · Ry(-35°)
    [math.cos(_A), 0, math.sin(_A)],
    [math.sin(_B) * math.sin(_A), math.cos(_B), -math.sin(_B) * math.cos(_A)],
    [-math.cos(_B) * math.sin(_A), math.sin(_B), math.cos(_B) * math.cos(_A)],
]
_EYE = _R[2]  # direction toward the camera, in world coordinates

# exploded-view direction per role (unit vector the part comes from)
EXPLODE = {"side_left": (-1, 0, 0), "side_right": (1, 0, 0), "top": (0, 1, 0), "bottom": (0, 0, 1),
           "shelf_fixed": (0, 0, 1), "shelf_loose": (0, 0, 1), "back": (0, 0, -1), "door": (0, 0, 1),
           "plinth": (0, 0, 1), "divider": (0, 1, 0)}


def _proj(p):
    x, y, z = p
    return (_R[0][0] * x + _R[0][1] * y + _R[0][2] * z,
            _R[1][0] * x + _R[1][1] * y + _R[1][2] * z,
            _R[2][0] * x + _R[2][1] * y + _R[2][2] * z)


def _corners(pos, size):
    (x, y, z), (sx, sy, sz) = pos, size
    return [(x + i * sx, y + j * sy, z + k * sz) for i in (0, 1) for j in (0, 1) for k in (0, 1)]


# faces as corner indices (i,j,k bits -> index 4i+2j+k) with outward normals
_FACES = [((0, 1, 3, 2), (-1, 0, 0)), ((4, 6, 7, 5), (1, 0, 0)), ((0, 4, 5, 1), (0, -1, 0)),
          ((2, 3, 7, 6), (0, 1, 0)), ((0, 2, 6, 4), (0, 0, -1)), ((1, 5, 7, 3), (0, 0, 1))]


class _Cam:
    """Same scale and offset for every step of a plan, so parts never jump between steps."""

    def __init__(self, boxes, box_px):
        pts = [_proj(c) for b in boxes for c in _corners(b["pos"], b["size"])]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0, x1, y1 = box_px
        self.s = min((x1 - x0) / max(1, max(xs) - min(xs)), (y1 - y0) / max(1, max(ys) - min(ys)))
        self.ox = x0 + ((x1 - x0) - (max(xs) - min(xs)) * self.s) / 2 - min(xs) * self.s
        self.oy = y1 - ((y1 - y0) - (max(ys) - min(ys)) * self.s) / 2 + min(ys) * self.s

    def xy(self, p):
        q = _proj(p)
        return (self.ox + q[0] * self.s, self.oy - q[1] * self.s)


def _draw_box(d, cam, pos, size, fill, width=LINE_W):
    cs = _corners(pos, size)
    for idx, n in _FACES:
        if n[0] * _EYE[0] + n[1] * _EYE[1] + n[2] * _EYE[2] <= 1e-9:
            continue  # back-facing
        d.polygon([cam.xy(cs[i]) for i in idx], fill=fill, outline=INK, width=width)


def _arrow(d, a, b, width=6):
    d.line([a, b], fill=INK, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (-0.5, 0.5):
        d.line([b, (b[0] - 26 * math.cos(ang + s), b[1] - 26 * math.sin(ang + s))], fill=INK, width=width)


def draw_icon(d, kind, x, y, s=40):
    """Tiny vector hardware icons (doc 07): cam lock, dowel, screw, pin, nail, anchor…"""
    c = (x + s / 2, y + s / 2)
    if kind == "cam_lock":
        d.ellipse((x + 4, y + 4, x + s - 4, y + s - 4), outline=INK, width=3)
        _arrow(d, (c[0] - 8, c[1] + 6), (c[0] + 8, c[1] - 6), width=3)
    elif kind == "dowel":
        d.rounded_rectangle((x + 4, y + s * 0.35, x + s - 4, y + s * 0.65), radius=6, outline=INK, width=3)
    elif kind in ("wood_screw", "confirmat", "cam_bolt", "bolt", "screw"):
        d.line((x + 10, c[1], x + s - 2, c[1]), fill=INK, width=4)
        d.rectangle((x + 2, c[1] - 9, x + 10, c[1] + 9), outline=INK, width=3)
    elif kind == "shelf_pin":
        d.ellipse((c[0] - 7, c[1] - 7, c[0] + 7, c[1] + 7), outline=INK, width=3)
        d.line((c[0] + 7, c[1], x + s - 4, c[1]), fill=INK, width=3)
    elif kind == "nail":
        d.line((x + 4, c[1], x + s - 2, c[1]), fill=INK, width=2)
        d.line((x + 4, c[1] - 7, x + 4, c[1] + 7), fill=INK, width=3)
    elif kind in ("wall_anchor", "bracket"):
        d.line((x + 8, y + 4, x + 8, y + s - 8, x + s - 4, y + s - 8), fill=INK, width=4, joint="curve")
    elif kind == "hinge":
        d.ellipse((x + 2, y + 8, x + s * 0.55, y + s - 8), outline=INK, width=3)
        d.rectangle((x + s * 0.55, c[1] - 5, x + s - 2, c[1] + 5), outline=INK, width=3)
    else:
        d.rectangle((x + 6, y + 6, x + s - 6, y + s - 6), outline=INK, width=3)


def _chips(d, hardware, y):
    x, f = PAD, _font(34)
    for h in hardware[:6]:
        label = f"×{h.get('count', 1)}"
        w = 40 + 14 + d.textlength(_t(label), font=f) + 30
        if x + w > W - PAD:
            break
        d.rounded_rectangle((x, y, x + w, y + 70), radius=35, outline=INK, width=3)
        draw_icon(d, h.get("kind", "other"), x + 16, y + 15)
        _txt(d, (x + 16 + 40 + 14, y + 15), label, font=f, fill=INK)
        x += w + 16
    return x


def _header(d, index, total, title, confidence, two_people=False):
    num_font, title_font, small = _font(120), _font(40), _font(30)
    _txt(d, (PAD, 25), str(index), font=num_font, fill=INK)
    tx = PAD + d.textlength(str(index), font=num_font) + 30
    _txt(d, (tx, 40), f"Step {index} of {total}", font=small, fill=(110, 110, 110))
    for i, line in enumerate(_wrap(d, title, title_font, W - tx - PAD - 40)):
        _txt(d, (tx, 85 + i * 48), line, font=title_font, fill=INK)
    bx = W - PAD
    if confidence < 0.75:
        badge = "Check this step"
        bw = d.textlength(badge, font=small) + 30
        d.rounded_rectangle((bx - bw, 8, bx, 52), radius=12, fill=AMBER)
        _txt(d, (bx - bw + 15, 14), badge, font=small, fill=INK)
    if two_people:
        d.rounded_rectangle((bx - 150, 120, bx, 170), radius=12, outline=INK, width=3)
        _txt(d, (bx - 135, 128), "2 people", font=small, fill=INK)


def _role_key(role, pid, placements, W_total):
    if role == "side":
        return "side_left" if placements[pid]["pos"][0] < W_total / 2 else "side_right"
    return role


def line_art_step(plan: dict, step: dict, out_path: Path, labels: bool = True) -> str:
    placements, roles = plan["placements"], plan["roles"]
    allbox = list(placements.values())
    W_total = max(b["pos"][0] + b["size"][0] for b in allbox) if allbox else 1
    H_total = max(b["pos"][1] + b["size"][1] for b in allbox) if allbox else 1
    mag = 0.25 * max(W_total, H_total)
    # camera fit includes exploded positions so arrows stay on the canvas
    fit = allbox + [{"pos": [b["pos"][i] + EXPLODE.get(_role_key(roles[k], k, placements, W_total), (0, 0, 1))[i] * mag
                             for i in range(3)], "size": b["size"]} for k, b in placements.items()]
    cam = _Cam(fit, (PAD + 20, HEADER_H + 30, W - PAD - 20, H - FOOTER_H - 90))

    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)
    _header(d, step["index"], len(plan["steps"]), step["title"], step.get("confidence", 1.0), step.get("two_people"))
    placed, new = step.get("placed") or [], set(step.get("parts_added") or [])
    if not placed:
        _overview_body(d, plan, (PAD, HEADER_H + 10, W - PAD, H - FOOTER_H - 20))
    else:
        order = sorted(placed, key=lambda k: _proj([placements[k]["pos"][i] + placements[k]["size"][i] / 2
                                                    for i in range(3)])[2])
        for k in order:
            b = placements[k]
            _draw_box(d, cam, b["pos"], b["size"], NEW_FILL if k in new else OLD_FILL)
        f = _font(30)
        for k in new:
            b = placements[k]
            c = [b["pos"][i] + b["size"][i] / 2 for i in range(3)]
            ex = EXPLODE.get(_role_key(roles[k], k, placements, W_total), (0, 0, 1))
            start = cam.xy([c[i] + ex[i] * mag for i in range(3)])
            end = cam.xy([c[i] + ex[i] * mag * 0.25 for i in range(3)])
            _arrow(d, start, end)
            if labels:
                tx, ty = cam.xy(c)
                tag = k.split(".")[0]
                tw = d.textlength(tag, font=f)
                d.rounded_rectangle((tx - tw / 2 - 10, ty - 22, tx + tw / 2 + 10, ty + 22), radius=10,
                                    fill=WHITE, outline=INK, width=2)
                _txt(d, (tx - tw / 2, ty - 17), tag, font=f, fill=INK)
    # orientation hints from checks[]
    f = _font(28)
    for i, c in enumerate((step.get("checks") or [])[:2]):
        _txt(d, (PAD, H - FOOTER_H - 80 + i * 36), f"• {c}", font=f, fill=(60, 60, 60))
    _chips(d, step.get("hardware_used") or [], H - FOOTER_H + 35)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return str(out_path)


def _overview_body(d, plan, box):
    """Every distinct panel drawn flat to scale with its label, size and count."""
    from .geometry import ROLE_NAMES
    parts = plan.get("parts_list") or []
    x0, y0, x1, y1 = box
    if not parts:
        return
    cols = 3 if len(parts) > 4 else 2
    cw = (x1 - x0) / cols
    rows = math.ceil(len(parts) / cols)
    rh = (y1 - y0) / rows
    s = min((cw - 40) / max(p["b"] for p in parts), (rh - 100) / max(p["a"] for p in parts))  # one scale for all
    f, fs = _font(30), _font(24)
    for i, p in enumerate(parts):
        cx, cy = x0 + (i % cols) * cw, y0 + (i // cols) * rh
        lw, lh = max(6, p["b"] * s), max(6, p["a"] * s)  # stand boards up: long side vertical
        rx = cx + (cw - lw) / 2
        d.rectangle((rx, cy + 10, rx + lw, cy + 10 + lh), fill=OLD_FILL, outline=INK, width=3)
        label = f"{p['id']}" + (f" ×{p['qty']}" if p["qty"] > 1 else "")
        _txt(d, (cx + 10, cy + lh + 18), label, font=f, fill=INK)
        _txt(d, (cx + 10, cy + lh + 52), f"{ROLE_NAMES.get(p['role'], p['role'])} · {p['a'] / 10:g}×{p['b'] / 10:g} cm",
               font=fs, fill=(90, 90, 90))


def overview(plan: dict, hardware: list[dict], out_path: Path, hardware_lines: list[str]) -> str:
    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)
    _txt(d, (PAD, 40), "Here's what you have", font=_font(56), fill=INK)
    ok = all("Missing" not in line for line in hardware_lines)
    _txt(d, (PAD, 115), "Hardware complete" if ok else "Hardware: something is missing", font=_font(32),
           fill=(30, 120, 60) if ok else (190, 90, 0))
    _overview_body(d, plan, (PAD, HEADER_H + 10, W - PAD, H - FOOTER_H - 20))
    _chips(d, hardware, H - FOOTER_H + 35)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return str(out_path)
