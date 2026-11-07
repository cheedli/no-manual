"""Solver mode end to end with a fake LLM: extract -> confirm -> solve -> render -> coach -> check."""
import json
import time
from pathlib import Path

import pytest
from conftest import make_jpeg

from core import render, scene, solver
from core.geometry import ab

FIX = Path(__file__).resolve().parents[1] / "fixtures"
GOLD = Path(__file__).resolve().parent / "golden"


def vision_parts(fx):
    """Turn a fixture into what the vision model would return."""
    return {"parts": [{"length_mm": p["dims_mm"]["length"], "width_mm": p["dims_mm"]["width"],
                       "thickness_mm": p["dims_mm"]["thickness"], "quantity": p.get("quantity", 1),
                       "holes": p.get("holes", {}), "groove": p.get("groove", False), "confidence": 0.8}
                      for p in fx["parts"]],
            "hardware": fx["hardware"], "uncertainties": [], "category_guess": fx["category"]}


@pytest.fixture
def bookcase(plugin, tmp_path):
    ctx, call = plugin
    fx = json.loads((FIX / "bookcase_80x180.json").read_text())
    pid = call("nm_start_project", category="bookcase", state="in_pieces")["project_id"]
    call("nm_set_details", project_id=pid, outer_dims={"width": 80, "height": 180, "depth": 30, "unit": "cm"})
    call("nm_add_photos", project_id=pid, kind="panel", image_paths=[str(make_jpeg(tmp_path / "p1.jpg"))])
    ctx.llm.responses = [vision_parts(fx)]
    return ctx, call, pid, fx


def test_extract_requires_dims(plugin, tmp_path):
    _, call = plugin
    pid = call("nm_start_project", category="bookcase")["project_id"]
    r = call("nm_extract_parts", project_id=pid, image_paths=[str(make_jpeg(tmp_path / "a.jpg"))])
    assert "outer size" in r["error"]


def test_extract_retries_bad_json(bookcase):
    ctx, call, pid, fx = bookcase
    ctx.llm.responses = [{"oops": 1}, vision_parts(fx)]
    r = call("nm_extract_parts", project_id=pid)
    assert len(r["parts"]) == 6 and len(ctx.llm.calls) == 2
    assert "ONLY a JSON" in ctx.llm.calls[1]["instructions"]
    ctx.llm.responses = [{"oops": 1}, {"still": "bad"}]
    assert "error" in call("nm_extract_parts", project_id=pid)


def test_full_solver_flow(bookcase):
    ctx, call, pid, fx = bookcase
    r = call("nm_extract_parts", project_id=pid)
    assert [p["role_guess"] for p in r["parts"]][:2] == ["side", "bottom"]
    assert len(r["questions"]) <= 4
    s = call("nm_solve", project_id=pid)
    assert s["steps"] == 13 and s["confidence"] >= 0.75 and s["hardware_check"]["ok"]
    out = call("nm_render_steps", project_id=pid)
    assert Path(out["overview_image"]).is_file() and len(out["step_images"]) == 13
    sc = json.loads(Path(out["scene_path"]).read_text())
    assert scene.validate(sc) == []
    st = call("nm_get_step", project_id=pid)
    assert st["index"] == 1 and st["scene_path"] == out["scene_path"]

    photo = str(make_jpeg(Path(out["scene_path"]).parent / "u1.jpg", (9, 9, 9)))
    ctx.llm.responses = [{"matches": True, "issues": [], "photo_quality": "good", "confidence": 0.9}]
    c = call("nm_check_step", project_id=pid, image_paths=[photo])
    assert c["advance"] and call("nm_status", project_id=pid)["project"]["step"] == "2/13"
    # reference image is sent first, then the user's photo
    imgs = [b for b in ctx.llm.calls[-1]["input"] if b["type"] == "image"]
    assert len(imgs) == 2

    ctx.llm.responses = [{"matches": False, "photo_quality": "good", "confidence": 0.85,
                          "issues": [{"severity": "stop", "text": "That panel is upside down; holes should face inward."}]}]
    c = call("nm_check_step", project_id=pid, image_paths=[str(make_jpeg(Path(photo).parent / "u2.jpg", (1, 1, 1)))])
    assert not c["advance"] and "stop" in c["next"].lower()
    assert call("nm_status", project_id=pid)["project"]["step"] == "2/13"

    ctx.llm.responses = [{"matches": True, "issues": [], "photo_quality": "blurry", "confidence": 0.3}]
    c = call("nm_check_step", project_id=pid, image_paths=[str(make_jpeg(Path(photo).parent / "u3.jpg", (2, 2, 2)))])
    assert not c["advance"] and "clearer" in c["next"]


def test_low_confidence_does_not_render(plugin, tmp_path):
    ctx, call = plugin
    fx = json.loads((FIX / "ambiguous.json").read_text())
    pid = call("nm_start_project", category="bookcase")["project_id"]
    call("nm_set_details", project_id=pid, outer_dims={"width": 800, "height": 1800, "depth": 300, "unit": "mm"})
    call("nm_add_photos", project_id=pid, kind="panel", image_paths=[str(make_jpeg(tmp_path / "a.jpg"))])
    ctx.llm.responses = [vision_parts(fx)]
    call("nm_extract_parts", project_id=pid)
    s = call("nm_solve", project_id=pid)
    assert s["steps"] == 0 and s["questions"] and "error" in call("nm_render_steps", project_id=pid)
    # user answers: P2 boards — the first two are top/bottom, all confirmed
    c = call("nm_confirm_parts", project_id=pid, confirm_all=True,
             hardware=[{"kind": "shelf_pin", "count": 8}, {"kind": "wall_anchor", "count": 1}])
    assert c["confidence"] >= 0.75
    assert call("nm_solve", project_id=pid)["steps"] > 0


def test_crib_cannot_extract_or_solve(plugin):
    _, call = plugin
    pid = call("nm_start_project", category="bunk_bed")["project_id"]
    for t in ("nm_extract_parts", "nm_solve", "nm_render_steps"):
        assert "official manufacturer manual" in call(t, project_id=pid)["error"]


def _plan(name):
    fx = json.loads((FIX / f"{name}.json").read_text())
    plan = solver.solve(fx["parts"], fx["hardware"], fx["outer"], fx["category"])
    plan["parts_list"] = [{"id": p["id"], "a": ab(p)[0], "b": ab(p)[1], "qty": p.get("quantity", 1),
                           "role": plan["roles"][p["id"]]} for p in fx["parts"]]
    return plan


def test_render_size_and_speed(tmp_path):
    from PIL import Image
    plan = _plan("closet_100x200")
    t = time.time()
    for s in plan["steps"]:
        render.line_art_step(plan, s, tmp_path / f"{s['index']}.png")
    assert time.time() - t < 10
    with Image.open(tmp_path / "5.png") as im:
        assert im.size == (1080, 1350) and im.getpixel((5, 600)) == (255, 255, 255)


@pytest.mark.parametrize("name,step", [("bookcase_80x180", 6), ("nightstand_45x55", 4)])
def test_golden(tmp_path, name, step):
    from PIL import Image, ImageChops
    plan = _plan(name)
    out = render.line_art_step(plan, plan["steps"][step - 1], tmp_path / "o.png")
    gold = GOLD / f"{name}_step{step}.png"
    if not gold.exists():  # first run writes the golden; commit it
        gold.parent.mkdir(exist_ok=True)
        Path(out).replace(gold)
        pytest.skip("golden written")
    with Image.open(out) as a, Image.open(gold) as b:
        diff = ImageChops.difference(a.convert("L"), b.convert("L")).point(lambda v: 255 if v > 40 else 0)
        frac = (diff.histogram()[255]) / (a.width * a.height)
    assert frac < 0.02, frac
