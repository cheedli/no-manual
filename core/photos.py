"""Photo intake: validate, copy into the project dir, de-duplicate, find recent uploads."""
from __future__ import annotations

import hashlib
import io
import shutil
import time
from pathlib import Path

from .models import new_id

MAX_BYTES = 20 * 1024 * 1024
KINDS = ("overview", "panel", "hardware", "label", "stage", "check")

# Where Hermes stages inbound images (verified 2026-11-07, docs/03 §11).
INBOUND_DIRS = ("cache/images", "cache/documents/native-inputs")


def sniff_image(head: bytes) -> str | None:
    """Return an extension for known image magic bytes, else None."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        return ".heic"
    return None


def add_photos(project, paths, kind: str, caption: str, project_dir: Path) -> dict:
    """Copy valid images into project_dir. Mutates project.photos. Returns a report."""
    known = {p["sha256"] for p in project.photos}
    added, skipped, retagged = [], [], []
    for raw in paths:
        src = Path(str(raw)).expanduser()
        if not src.is_file():
            skipped.append({"path": str(raw), "reason": "file not found"})
            continue
        size = src.stat().st_size
        if size > MAX_BYTES:
            skipped.append({"path": str(raw), "reason": "larger than 20 MB"})
            continue
        data = src.read_bytes()
        ext = sniff_image(data[:16])
        if not ext:
            skipped.append({"path": str(raw), "reason": "not an image (jpg, png, webp, heic)"})
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in known:
            prev = next(x for x in project.photos if x["sha256"] == sha)
            if kind in ("panel", "hardware", "stage", "check") and prev["kind"] in ("label", "overview") \
                    and kind != prev["kind"]:
                prev["kind"] = kind  # same photo, now known to be more specific: re-tag, don't drop it
                retagged.append(prev["id"])
            else:
                skipped.append({"path": str(raw), "reason": "duplicate of a photo already added"})
            continue
        pid = "ph_" + new_id()
        dest = project_dir / "photos" / f"{pid}{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        project.photos.append({"id": pid, "path": str(dest), "kind": kind, "sha256": sha,
                               "added_at": time.time(), "caption": caption or ""})
        known.add(sha)
        added.append(pid)
    by_kind: dict[str, int] = {}
    for p in project.photos:
        by_kind[p["kind"]] = by_kind.get(p["kind"], 0) + 1
    return {"added": len(added) + len(retagged), "photo_ids": added + retagged, "skipped": skipped,
            "total_by_kind": by_kind}


def recent_uploads(hermes_home: Path, since: float, limit: int = 20, window_s: float = 1800) -> list[str]:
    """Images Hermes staged after `since` (and within the last `window_s`), newest last,
    de-duplicated by content (the same upload lands in two cache dirs)."""
    floor = max(since, time.time() - window_s)
    found = []
    for d in INBOUND_DIRS:
        base = Path(hermes_home) / d
        if base.is_dir():
            for f in base.rglob("*"):
                try:
                    if f.is_file() and f.stat().st_mtime > floor:
                        found.append(f)
                except OSError:
                    continue
    found.sort(key=lambda f: f.stat().st_mtime)
    seen, out = set(), []
    for f in found:
        try:
            data = f.read_bytes()
        except OSError:
            continue
        if not sniff_image(data[:16]):
            continue
        h = hashlib.sha256(data).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(str(f))
    return out[-limit:]


def for_vision(path: str, long_edge: int = 1600) -> tuple[bytes, str]:
    """Downscale to long edge <= 1600 px, JPEG q85 (docs/03 §5). Falls back to raw bytes."""
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((long_edge, long_edge))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            return buf.getvalue(), "image/jpeg"
    except Exception:
        data = Path(path).read_bytes()
        ext = sniff_image(data[:16])
        return data, {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
