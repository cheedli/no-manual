"""Backend route for the Desktop step viewer: serves scene JSON from our own data folder only."""
import importlib.util
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Load core/scene.py by path: this file is imported by the dashboard host, not as part of our package.
_spec = importlib.util.spec_from_file_location("no_manual_scene_guard", Path(__file__).resolve().parents[1] / "core" / "scene_guard.py")
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)


@router.get("/scene")
async def scene(path: str):
    from plugins.plugin_storage import plugin_data_dir
    p = _guard.safe_scene_path(path, plugin_data_dir("no-manual"))
    if p is None:
        raise HTTPException(403, "not a No Manual scene file")
    return json.loads(p.read_text())
