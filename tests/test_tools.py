"""Contract tests: handlers return JSON strings, never raise; recorder flow end to end with a fake LLM."""
import json
import time

import pytest
from conftest import make_jpeg

STAGE = {"nothing_removed": False, "removed_parts": ["doors"], "hardware_removed": [{"kind": "hinge", "count": 4}],
         "description": "took off doors", "assembly_instruction": "Hang both doors on the hinges.",
         "orientation_notes": ["hinge cups face inward"], "category_guess": "wardrobe", "confidence": 0.9}




def test_every_tool_survives_bad_input(plugin):
    ctx, _ = plugin
    for name, handler in ctx.tools.items():
        for bad in ({}, {"project_id": "nope"}, {"project_id": None, "index": "x"}, None):
            out = handler(bad)
            assert isinstance(out, str)
            json.loads(out)


def test_start_and_details(plugin):
    _, call = plugin
    r = call("nm_start_project", category="closet", state="assembled")
    assert r["safety_status"] == "ok" and r["allowed_modes"] == ["manual", "recorder", "solver"]
    d = call("nm_set_details", project_id=r["project_id"],
             outer_dims={"width": 100, "height": 200, "depth": 60, "unit": "cm"})
    assert d["outer_dims_mm"] == {"w": 1000, "h": 2000, "d": 600}
    bad = call("nm_set_details", project_id=r["project_id"], outer_dims={"width": 1, "height": 2, "depth": 3})
    assert "error" in bad
    s = call("nm_status")
    assert s["projects"][0]["project_id"] == r["project_id"]


def test_crib_is_manual_only_and_guarded(plugin):
    ctx, call = plugin
    r = call("nm_start_project", category="crib")
    assert r["safety_status"] == "blocked_child_or_load" and r["allowed_modes"] == ["manual"]
    for tool in ("nm_finish_recording", "nm_record_stage"):
        assert "error" in call(tool, project_id=r["project_id"], image_paths=[])
    guard = ctx.hooks["pre_tool_call"]
    assert guard(tool_name="nm_finish_recording", args={"project_id": r["project_id"]}, task_id="t")["action"] == "block"
    assert guard(tool_name="nm_solve", args={"project_id": r["project_id"]}, task_id="t")["action"] == "block"
    assert guard(tool_name="nm_status", args={"project_id": r["project_id"]}, task_id="t") is None


def test_add_photos_paths_and_recent(plugin, tmp_path):
    _, call = plugin
    pid = call("nm_start_project", category="bookcase")["project_id"]
    a = make_jpeg(tmp_path / "a.jpg")
    r = call("nm_add_photos", project_id=pid, kind="label", image_paths=[str(a)])
    assert r["added"] == 1
    from no_manual import tools
    make_jpeg(tools._hermes_home / "cache/images/upload_x.jpg", (0, 255, 0))
    r = call("nm_add_photos", project_id=pid, kind="overview", recent=True)
    assert r["added"] == 1 and "Confirm" in r["next"]


def _record(call, pid, tmp_path, i, text="", color=None):
    img = make_jpeg(tmp_path / f"s{i}.jpg", color or (i * 40, 10, 10))
    return call("nm_record_stage", project_id=pid, image_paths=[str(img)], what_was_removed=text)


def test_recorder_flow(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [STAGE, {**STAGE, "removed_parts": ["shelf"], "hardware_removed": [],
                                 "orientation_notes": []}]
    pid = call("nm_start_project", category="wardrobe", state="assembled")["project_id"]
    assert "error" in call("nm_finish_recording", project_id=pid)  # no stages yet
    assert _record(call, pid, tmp_path, 0)["stage_index"] == 0
    r1 = _record(call, pid, tmp_path, 1, "took off the doors")
    assert r1["stage_index"] == 1 and r1["described"]["removed_parts"] == ["doors"]
    assert _record(call, pid, tmp_path, 2, "removed the shelf")["stage_index"] == 2
    # vision got two images for the stage comparison
    assert sum(1 for x in ctx.llm.calls[0]["input"] if x["type"] == "image") == 2

    f = call("nm_finish_recording", project_id=pid)
    assert f["steps"] == 3 and len(f["step_images"]) == 3  # 2 reversed + anti-tip (height unknown)
    assert any("Height unknown" in w for w in f["warnings"])
    s1 = call("nm_get_step", project_id=pid)
    assert s1["index"] == 1 and s1["title"] == "Attach the shelf" and s1["image_path"].endswith(".png")
    assert "MEDIA:" in s1["next"]
    s2 = call("nm_get_step", project_id=pid, index=2)
    assert s2["title"] == "Attach the doors" and s2["hardware_used"] == [{"kind": "hinge", "count": 4}]
    assert call("nm_get_step", project_id=pid, index=3)["title"] == "Anchor it to the wall"
    assert "error" in call("nm_get_step", project_id=pid, index=9)


def test_recorder_nothing_removed_asks(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [{**STAGE, "nothing_removed": True, "removed_parts": []}]
    pid = call("nm_start_project", category="bookcase")["project_id"]
    _record(call, pid, tmp_path, 0)
    r = _record(call, pid, tmp_path, 1)
    assert r["stage_index"] is None and "What did you remove" in r["question"]


def test_recorder_vision_detects_crib(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [{**STAGE, "category_guess": "crib", "confidence": 0.8}]
    pid = call("nm_start_project", category="other")["project_id"]
    _record(call, pid, tmp_path, 0)
    r = _record(call, pid, tmp_path, 1, "took off a side rail")
    assert "error" in r and "official manufacturer manual" in r["error"]
    assert call("nm_status", project_id=pid)["project"]["safety_status"] == "blocked_child_or_load"


def test_recorder_vision_failure_falls_back(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [RuntimeError("provider down")]
    pid = call("nm_start_project", category="bookcase")["project_id"]
    _record(call, pid, tmp_path, 0)
    r = _record(call, pid, tmp_path, 1, "took off the top")
    assert r["stage_index"] == 1 and r["warning"]


def test_hint_hook(plugin):
    ctx, _ = plugin
    h = ctx.hooks["pre_llm_call"]
    assert "no-manual:no-manual-guide" in h(session_id="s", user_message="I lost my IKEA manual",
                                            conversation_history=[], is_first_turn=True, model="m", platform="cli")
    assert h(session_id="s", user_message="what's 2+2", conversation_history=[], is_first_turn=True,
             model="m", platform="cli") is None


def test_slash(plugin):
    ctx, call = plugin
    slash = ctx.commands["nomanual"]
    assert "No furniture projects" in slash("")
    pid = call("nm_start_project", category="closet", title="hall closet")["project_id"]
    assert pid in slash("") and "hall closet" in slash(f"resume {pid}")
    assert "yes" in slash(f"delete {pid}")
    assert slash(f"delete {pid} yes") == f"Deleted project {pid}."
    assert "No furniture projects" in slash("list")


def test_manifest_matches_registration(plugin):
    """provides_tools in plugin.yaml must equal what register() registers (catalog rule 6)."""
    import re
    from pathlib import Path
    ctx, _ = plugin
    text = (Path(__file__).resolve().parents[1] / "plugin.yaml").read_text()
    block = text.split("provides_tools:")[1].split("provides_hooks:")[0]
    assert set(re.findall(r"-\s+(\w+)", block)) == set(ctx.tools)
    hooks = text.split("provides_hooks:")[1].split("config_schema:")[0]
    assert set(re.findall(r"-\s+(\w+)", hooks)) == set(ctx.hooks)


def test_recorder_non_numeric_confidence_keeps_stage(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [{**STAGE, "confidence": "high"}]
    pid = call("nm_start_project", category="wardrobe")["project_id"]
    _record(call, pid, tmp_path, 0)
    assert _record(call, pid, tmp_path, 1, "took off the doors")["stage_index"] == 1
