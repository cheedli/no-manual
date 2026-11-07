"""Step images (docs/07) in the No Manual "blueprint" identity (docs/BRAND.md).

Pillow only, drawn from geometry, never generated. Bundled font: Atkinson Hyperlegible (OFL,
assets/fonts/), falling back to Pillow's default font.

- letterbox_step: recorder / manual steps (the user's own photo inside a step card)
- line_art_step: solver steps (axonometric line art of the real boards)
- overview: "Here's what you have" (every panel to scale + hardware)
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1080, 1350
# ---- brand palette (docs/BRAND.md)
PAPER = (246, 245, 241)
CARD = (255, 255, 255)
CARD_EDGE = (226, 223, 215)
INK = (26, 26, 26)
INK_SOFT = (110, 108, 102)
BLUE = (47, 91, 255)
BLUE_TINT = (220, 229, 255)
SHADOW = (228, 225, 217)
AMBER = (245, 165, 36)
GREEN = (31, 157, 85)
RED = (229, 72, 77)
WHITE, GREY = CARD, (236, 234, 228)  # kept for callers/tests

M = 24                      # card margin on the paper
PAD = M + 40                # content padding inside the card
HEADER_H, FOOTER_H = 230, 170
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


@lru_cache(maxsize=None)
def _font(size: int, bold: bool = False):
    name = "AtkinsonHyperlegible-Bold.ttf" if bold else "AtkinsonHyperlegible-Regular.ttf"
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)  # Pillow >= 10.1
        except TypeError:
            return ImageFont.load_default()


_GLYPHS = str.maketrans({"≈": "~", "…": "...", "✓": "v", "→": "->"})


def _t(text) -> str:
    """Map the few symbols the fonts lack to ASCII."""
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


# ================================================================== brand pieces

def draw_logo(d, x, y, s=44):
    """No Manual mark: a blue rounded square with a white hex (Allen) key."""
    d.rounded_rectangle((x, y, x + s, y + s), radius=s * 0.26, fill=BLUE)
    w = max(3, round(s * 0.13))
    d.line([(x + s * 0.30, y + s * 0.24), (x + s * 0.30, y + s * 0.70), (x + s * 0.74, y + s * 0.70)],
           fill=CARD, width=w, joint="curve")
    r = w / 2
    for cx, cy in ((x + s * 0.30, y + s * 0.24), (x + s * 0.74, y + s * 0.70)):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CARD)


def _card():
    canvas = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((M + 2, M + 6, W - M + 2, H - M + 6), radius=40, fill=SHADOW)  # soft card shadow
    d.rounded_rectangle((M, M, W - M, H - M), radius=40, fill=CARD, outline=CARD_EDGE, width=2)
    # footer brand
    f = _font(26, True)
    label = "No Manual"
    tw = d.textlength(label, font=f)
    draw_logo(d, W - PAD - tw - 46, H - M - 66, 34)
    _txt(d, (W - PAD - tw, H - M - 64), label, f, INK_SOFT)
    return canvas, d


def _pill(d, x_right, y, text, fill, fg=CARD):
    f = _font(28, True)
    w = d.textlength(_t(text), font=f) + 36
    d.rounded_rectangle((x_right - w, y, x_right, y + 48), radius=24, fill=fill)
    _txt(d, (x_right - w + 18, y + 9), text, f, fg)
    return x_right - w - 12


def _header(d, index, total, title, confidence, two_people=False):
    num = str(index)
    nf = _font(150, True)
    _txt(d, (PAD - 6, M + 22), num, nf, INK)
    tx = PAD + d.textlength(num, font=nf) + 28
    _txt(d, (tx, M + 54), f"Step {index} of {total}", _font(30), INK_SOFT)
    for i, line in enumerate(_wrap(d, title, _font(46, True), W - tx - PAD, 2)):
        _txt(d, (tx, M + 94 + i * 54), line, _font(46, True), INK)
    x = W - PAD
    if confidence < 0.75:
        x = _pill(d, x, M + 30, "Check this step", AMBER, INK)
    if two_people:
        _pill(d, x, M + 30, "2 people", INK)


# ================================================================== hardware icons + chips

def _arrow(d, a, b, width=7, head=30):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    base = (b[0] - head * 0.8 * math.cos(ang), b[1] - head * 0.8 * math.sin(ang))
    d.line([a, base], fill=INK, width=width)
    pts = [b] + [(b[0] - head * math.cos(ang + s), b[1] - head * math.sin(ang + s)) for s in (-0.45, 0.45)]
    d.polygon(pts, fill=INK)


def draw_icon(d, kind, x, y, s=44):
    """Tiny vector hardware icons: cam lock, dowel, screw, pin, nail, anchor, hinge…"""
    c = (x + s / 2, y + s / 2)
    if kind == "cam_lock":
        d.ellipse((x + 4, y + 4, x + s - 4, y + s - 4), fill=CARD, outline=INK, width=3)
        d.line((c[0] - 9, c[1] + 7, c[0] + 9, c[1] - 7), fill=INK, width=4)
    elif kind == "dowel":
        d.rounded_rectangle((x + 4, y + s * 0.34, x + s - 4, y + s * 0.66), radius=7, fill=(239, 224, 196),
                            outline=INK, width=3)
    elif kind in ("wood_screw", "confirmat", "cam_bolt", "bolt", "screw"):
        d.line((x + 12, c[1], x + s - 2, c[1]), fill=INK, width=4)
        for k in range(3):
            xx = x + 18 + k * 8
            d.line((xx, c[1] - 5, xx + 4, c[1] + 5), fill=INK, width=2)
        d.rectangle((x + 2, c[1] - 10, x + 12, c[1] + 10), fill=CARD, outline=INK, width=3)
    elif kind == "shelf_pin":
        d.ellipse((c[0] - 9, c[1] - 9, c[0] + 5, c[1] + 5), fill=CARD, outline=INK, width=3)
        d.line((c[0] + 4, c[1] - 2, x + s - 4, c[1] - 2), fill=INK, width=4)
    elif kind == "nail":
        d.line((x + 6, c[1], x + s - 2, c[1]), fill=INK, width=2)
        d.line((x + 6, c[1] - 8, x + 6, c[1] + 8), fill=INK, width=4)
    elif kind in ("wall_anchor", "bracket"):
        d.line((x + 10, y + 4, x + 10, y + s - 10, x + s - 4, y + s - 10), fill=INK, width=5, joint="curve")
    elif kind == "hinge":
        d.ellipse((x + 2, y + 9, x + s * 0.56, y + s - 9), fill=CARD, outline=INK, width=3)
        d.rectangle((x + s * 0.56, c[1] - 6, x + s - 2, c[1] + 6), fill=CARD, outline=INK, width=3)
    else:
        d.rounded_rectangle((x + 6, y + 6, x + s - 6, y + s - 6), radius=6, outline=INK, width=3)


def _chips(d, hardware, y):
    """IKEA-style hardware boxes: icon + '4×'."""
    x, f = PAD, _font(34, True)
    for h in hardware[:6]:
        label = f"{h.get('count', 1)}×"
        w = 16 + 44 + 12 + d.textlength(_t(label), font=f) + 22
        if x + w > W - PAD - 220:  # keep clear of the footer brand
            break
        d.rounded_rectangle((x, y, x + w, y + 72), radius=18, fill=CARD, outline=INK, width=3)
        draw_icon(d, h.get("kind", "other"), x + 16, y + 14)
        _txt(d, (x + 16 + 44 + 12, y + 16), label, f, INK)
        x += w + 14
    return x


def _checks(d, checks, y):
    f = _font(28)
    for i, c in enumerate((checks or [])[:2]):
        yy = y + i * 40
        d.ellipse((PAD, yy + 11, PAD + 12, yy + 23), fill=BLUE)
        _txt(d, (PAD + 24, yy), c, f, INK_SOFT)


def _save(canvas, out_path: Path) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return str(out_path)


# ================================================================== recorder / manual steps

def letterbox_step(photo_path: str | None, out_path: Path, index: int, total: int, title: str,
                   hardware: list[dict], confidence: float = 1.0) -> str:
    canvas, d = _card()
    _header(d, index, total, title, confidence)
    box = (PAD, M + HEADER_H, W - PAD, H - M - FOOTER_H)
    bw, bh = box[2] - box[0], box[3] - box[1]
    if photo_path and Path(photo_path).is_file():
        with Image.open(photo_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((bw, bh))
            px, py = box[0] + (bw - im.width) // 2, box[1] + (bh - im.height) // 2
            mask = Image.new("L", im.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=24, fill=255)
            canvas.paste(im, (px, py), mask)
            d.rounded_rectangle((px, py, px + im.width - 1, py + im.height - 1), radius=24, outline=CARD_EDGE, width=2)
    else:
        d.rounded_rectangle(box, radius=24, fill=GREY)
        _txt(d, (box[0] + 30, box[1] + 30), "(no photo)", _font(30), INK_SOFT)
    _chips(d, hardware, H - M - FOOTER_H + 40)
    return _save(canvas, out_path)


# ================================================================== solver line art

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


# faces as corner indices (i,j,k bits -> index 4i+2j+k), outward normal, light factor
_FACES = [((0, 1, 3, 2), (-1, 0, 0), 0.90), ((4, 6, 7, 5), (1, 0, 0), 0.90), ((0, 4, 5, 1), (0, -1, 0), 0.85),
          ((2, 3, 7, 6), (0, 1, 0), 1.00), ((0, 2, 6, 4), (0, 0, -1), 0.95), ((1, 5, 7, 3), (0, 0, 1), 0.96)]


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


def _shade(rgb, k):
    return tuple(max(0, min(255, round(c * k))) for c in rgb)


def _draw_box(d, cam, pos, size, fill, width=4):
    cs = _corners(pos, size)
    for idx, n, light in _FACES:
        if n[0] * _EYE[0] + n[1] * _EYE[1] + n[2] * _EYE[2] <= 1e-9:
            continue  # back-facing
        d.polygon([cam.xy(cs[i]) for i in idx], fill=_shade(fill, light), outline=INK, width=width)


def _ground_shadow(canvas, cam, placements):
    """Soft ellipse under the finished footprint (y = 0)."""
    if not placements:
        return
    xs = [b["pos"][0] for b in placements.values()] + [b["pos"][0] + b["size"][0] for b in placements.values()]
    zs = [b["pos"][2] for b in placements.values()] + [b["pos"][2] + b["size"][2] for b in placements.values()]
    pts = [cam.xy((x, 0, z)) for x in (min(xs), max(xs)) for z in (min(zs), max(zs))]
    px, py = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(px) + max(px)) / 2, max(py) - (max(py) - min(py)) * 0.35
    rx, ry = (max(px) - min(px)) * 0.62, max(18, (max(py) - min(py)) * 0.42)
    layer = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(layer).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    canvas.paste(Image.new("RGB", canvas.size, SHADOW), (0, 0), layer)


def _role_key(role, pid, placements, W_total):
    if role == "side":
        return "side_left" if placements[pid]["pos"][0] < W_total / 2 else "side_right"
    return role


def _id_badge(d, x, y, tag):
    f = _font(30, True)
    tw = d.textlength(tag, font=f)
    r = max(26, tw / 2 + 14)
    d.ellipse((x - r, y - 26, x + r, y + 26), fill=CARD, outline=INK, width=3)
    _txt(d, (x - tw / 2, y - 19), tag, f, INK)


def line_art_step(plan: dict, step: dict, out_path: Path, labels: bool = True) -> str:
    placements, roles = plan["placements"], plan["roles"]
    allbox = list(placements.values())
    W_total = max(b["pos"][0] + b["size"][0] for b in allbox) if allbox else 1
    H_total = max(b["pos"][1] + b["size"][1] for b in allbox) if allbox else 1
    mag = 0.25 * max(W_total, H_total)
    # camera fit includes exploded positions so arrows stay on the canvas
    fit = allbox + [{"pos": [b["pos"][i] + EXPLODE.get(_role_key(roles[k], k, placements, W_total), (0, 0, 1))[i] * mag
                             for i in range(3)], "size": b["size"]} for k, b in placements.items()]
    cam = _Cam(fit, (PAD + 20, M + HEADER_H + 20, W - PAD - 20, H - M - FOOTER_H - 70))

    canvas, d = _card()
    _header(d, step["index"], len(plan["steps"]), step["title"], step.get("confidence", 1.0), step.get("two_people"))
    placed, new = step.get("placed") or [], set(step.get("parts_added") or [])
    if not placed:
        _overview_body(d, plan, (PAD, M + HEADER_H, W - PAD, H - M - FOOTER_H - 70))
    else:
        _ground_shadow(canvas, cam, {k: placements[k] for k in placed})
        d = ImageDraw.Draw(canvas)
        order = sorted(placed, key=lambda k: _proj([placements[k]["pos"][i] + placements[k]["size"][i] / 2
                                                    for i in range(3)])[2])
        for k in order:
            b = placements[k]
            _draw_box(d, cam, b["pos"], b["size"], BLUE_TINT if k in new else CARD)
        for k in new:
            b = placements[k]
            c = [b["pos"][i] + b["size"][i] / 2 for i in range(3)]
            ex = EXPLODE.get(_role_key(roles[k], k, placements, W_total), (0, 0, 1))
            _arrow(d, cam.xy([c[i] + ex[i] * mag for i in range(3)]), cam.xy([c[i] + ex[i] * mag * 0.22 for i in range(3)]))
            if labels:
                _id_badge(d, *cam.xy(c), k.split(".")[0])
    _checks(d, step.get("checks"), H - M - FOOTER_H - 60)
    _chips(d, step.get("hardware_used") or [], H - M - FOOTER_H + 40)
    return _save(canvas, out_path)


# ================================================================== overview

def _overview_body(d, plan, box):
    """Every distinct panel drawn flat to one scale with its id, role, size and count."""
    from .geometry import ROLE_NAMES
    parts = plan.get("parts_list") or []
    x0, y0, x1, y1 = box
    if not parts:
        return
    cols = 3 if len(parts) > 4 else 2
    cw = (x1 - x0) / cols
    rows = math.ceil(len(parts) / cols)
    rh = (y1 - y0) / rows
    s = min((cw - 50) / max(p["b"] for p in parts), (rh - 110) / max(p["a"] for p in parts))  # one scale for all
    fs = _font(24)
    for i, p in enumerate(parts):
        cx, cy = x0 + (i % cols) * cw, y0 + (i // cols) * rh
        lw, lh = max(8, p["b"] * s), max(8, p["a"] * s)  # stand boards up: long side vertical
        rx = cx + (cw - lw) / 2
        d.rectangle((rx + 6, cy + 16, rx + lw + 6, cy + 16 + lh), fill=SHADOW)
        d.rectangle((rx, cy + 10, rx + lw, cy + 10 + lh), fill=CARD, outline=INK, width=3)
        if lh > 90 and lw > 80:  # only where the badge fits inside the board
            _id_badge(d, rx + lw / 2, cy + 10 + lh / 2, p["id"])
        label = p["id"] + (f"  {p['qty']}×" if p["qty"] > 1 else "")
        _txt(d, (cx + 10, cy + lh + 24), label, _font(30, True), INK)
        _txt(d, (cx + 10, cy + lh + 60), ROLE_NAMES.get(p["role"], p["role"]), fs, INK_SOFT)
        _txt(d, (cx + 10, cy + lh + 88), f"{p['a'] / 10:g} × {p['b'] / 10:g} cm", fs, INK_SOFT)


def overview(plan: dict, hardware: list[dict], out_path: Path, hardware_lines: list[str]) -> str:
    canvas, d = _card()
    _txt(d, (PAD, M + 44), "Here's what you have", _font(62, True), INK)
    ok = all("Missing" not in line for line in hardware_lines)
    color, msg = (GREEN, "Hardware complete") if ok else (RED, "Something is missing: see the list")
    d.ellipse((PAD, M + 146, PAD + 18, M + 164), fill=color)
    _txt(d, (PAD + 30, M + 136), msg, _font(32, True), color)
    _overview_body(d, plan, (PAD, M + HEADER_H, W - PAD, H - M - FOOTER_H - 20))
    _chips(d, hardware, H - M - FOOTER_H + 40)
    return _save(canvas, out_path)
