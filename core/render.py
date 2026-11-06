"""Step images (docs/07). Pillow only, no downloaded fonts, no image generation.

Today: letterbox mode (recorder/manual: the user's own photo + header + hardware chips).
Line-art solver mode is added on Day 3.
"""
from __future__ import annotations

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


def _wrap(draw, text: str, font, width: int, max_lines: int = 2) -> list[str]:
    words, lines, line = text.split(), [], ""
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
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def hardware_label(kind: str) -> str:
    return kind.replace("_", " ")


def letterbox_step(photo_path: str | None, out_path: Path, index: int, total: int, title: str,
                   hardware: list[dict], confidence: float = 1.0) -> str:
    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)

    # Header: big step number (IKEA-style) + "Step k of n — title"
    num_font, title_font, small = _font(120), _font(40), _font(30)
    d.text((PAD, 25), str(index), font=num_font, fill=INK)
    num_w = d.textlength(str(index), font=num_font)
    tx = PAD + num_w + 30
    d.text((tx, 40), f"Step {index} of {total}", font=small, fill=(110, 110, 110))
    for i, line in enumerate(_wrap(d, title, title_font, W - tx - PAD)):
        d.text((tx, 85 + i * 48), line, font=title_font, fill=INK)
    if confidence < 0.75:
        badge = "Check this step"
        bw = d.textlength(badge, font=small) + 30
        d.rounded_rectangle((W - PAD - bw, 8, W - PAD, 52), radius=12, fill=AMBER)
        d.text((W - PAD - bw + 15, 14), badge, font=small, fill=INK)

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
        d.text((box[0] + 30, box[1] + 30), "(no photo)", font=small, fill=INK)
    d.rectangle(box, outline=INK, width=3)

    # Footer: hardware chips "×4 cam lock"
    x, y = PAD, H - FOOTER_H + 35
    chip_font = _font(34)
    for h in hardware[:6]:
        label = f"×{h.get('count', 1)} {hardware_label(h.get('kind', 'part'))}"
        cw = d.textlength(label, font=chip_font) + 40
        if x + cw > W - PAD:
            break
        d.rounded_rectangle((x, y, x + cw, y + 70), radius=35, outline=INK, width=3)
        d.text((x + 20, y + 15), label, font=chip_font, fill=INK)
        x += cw + 20

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG", optimize=True)
    return str(out_path)
