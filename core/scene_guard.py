"""Path-traversal guard for the Desktop scene route (no package imports)."""
from __future__ import annotations


def safe_scene_path(path: str, root, max_bytes: int = 2 * 1024 * 1024):
    """Resolve `path` and return it only if it's a scene.json inside `root` (path-traversal guard)."""
    from pathlib import Path
    try:
        p = Path(path).expanduser().resolve(strict=True)
        r = Path(root).resolve()
    except (OSError, RuntimeError, TypeError):
        return None
    if not p.is_relative_to(r) or p.name != "scene.json" or not p.is_file() or p.stat().st_size > max_bytes:
        return None
    return p
