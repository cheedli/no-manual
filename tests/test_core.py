"""Pure core tests: store, units, safety, photos, recorder, render, hint."""
import sqlite3
import time

import pytest
from conftest import make_jpeg

from core import photos, recorder, render, safety, units
from core.hint import looks_like_furniture_request
from core.models import Project
from core.store import Store


def test_store_roundtrip_and_persistence(tmp_path):
    db = tmp_path / "d.db"
    s = Store(sqlite3.connect(db), tmp_path)
    p = s.save(Project(title="closet", category="closet"))
    assert (tmp_path / "projects" / p.id).is_dir()
    s2 = Store(sqlite3.connect(db), tmp_path)  # "restart"
    assert s2.get(p.id).title == "closet"
    assert [x.id for x in s2.list()] == [p.id]
    assert s2.delete(p.id) and s2.get(p.id) is None
    assert not (tmp_path / "projects" / p.id).exists()


@pytest.mark.parametrize("d,exp", [
    ({"width": 80, "height": 180, "depth": 30, "unit": "cm"}, {"w": 800, "h": 1800, "d": 300}),
    ({"width": 31.5, "height": 70.9, "depth": 11.8, "unit": "in"}, {"w": 800.1, "h": 1800.9, "d": 299.7}),
    ({"width": 800, "height": 1800, "depth": 300, "unit": "mm"}, {"w": 800, "h": 1800, "d": 300}),
])
def test_units(d, exp):
    assert units.normalize_dims(d) == exp


@pytest.mark.parametrize("bad", [{"width": 4, "height": 180, "depth": 30, "unit": "cm"},
                                 {"width": 80, "height": 400, "depth": 30, "unit": "cm"},
                                 {"width": 80, "height": 180, "unit": "cm"}])
def test_units_reject(bad):
    with pytest.raises(ValueError):
        units.normalize_dims(bad)


@pytest.mark.parametrize("cat", ["crib", "cot", "bunk_bed", "loft_bed", "bed", "high_chair",
                                 "changing_table", "playpen", "chair", "Bunk bed", "highchair", "bassinet"])
def test_blocked_categories(cat):
    assert safety.is_blocked(cat)


@pytest.mark.parametrize("cat", ["closet", "wardrobe", "bookcase", "cabinet", "nightstand", "desk", "other"])
def test_allowed_categories(cat):
    assert not safety.is_blocked(cat)


def test_vision_reclassifies_to_blocked():
    p = Project(category="other")
    assert not safety.apply_vision_guess(p, "crib", 0.4)
    assert safety.apply_vision_guess(p, "crib", 0.8) and p.blocked
    assert safety.allowed_modes(p) == ["manual"]


def test_anti_tip_rule():
    assert safety.needs_anti_tip("bookcase", 1800)
    assert not safety.needs_anti_tip("bookcase", 700)
    assert safety.needs_anti_tip("closet", None)        # unknown height fails closed
    assert not safety.needs_anti_tip("nightstand", None)


def test_photos_dedupe_reject(tmp_path):
    p = Project()
    a = make_jpeg(tmp_path / "in" / "a.jpg")
    txt = tmp_path / "in" / "notes.txt"
    txt.write_text("hello")
    big = tmp_path / "in" / "big.jpg"
    big.write_bytes(b"\xff\xd8\xff" + b"0" * (photos.MAX_BYTES + 1))
    rep = photos.add_photos(p, [a, a, txt, big, tmp_path / "missing.jpg"], "panel", "", tmp_path / "proj")
    assert rep["added"] == 1 and rep["total_by_kind"] == {"panel": 1}
    reasons = sorted(s["reason"] for s in rep["skipped"])
    assert reasons == ["duplicate of a photo already added", "file not found", "larger than 20 MB",
                       "not an image (jpg, png, webp, heic)"]
    assert photos.add_photos(p, [a], "panel", "", tmp_path / "proj")["added"] == 0


def test_recent_uploads_dedupes_two_cache_dirs(tmp_path):
    home = tmp_path / "home"
    make_jpeg(home / "cache/images/upload_1.jpg", (1, 2, 3))
    make_jpeg(home / "cache/documents/native-inputs/abc/upload_1.jpg", (1, 2, 3))  # same content
    make_jpeg(home / "cache/images/upload_2.jpg", (9, 9, 9))
    (home / "cache/images/readme.txt").write_text("x")
    assert len(photos.recent_uploads(home, since=time.time() - 60)) == 2
    assert photos.recent_uploads(home, since=time.time() + 60) == []


def _stage(i, parts=(), hw=(), conf=0.9, text=""):
    return {"index": i, "photo_paths": [f"/p/{i}.jpg"], "user_text": text,
            "described": None if i == 0 else {"removed_parts": list(parts), "hardware_removed": list(hw),
                                              "assembly_instruction": f"put back {parts}",
                                              "orientation_notes": ["hinges left"], "confidence": conf}}


def test_recorder_reverses_stages():
    stages = [_stage(0), _stage(1, ["doors"], [{"kind": "hinge", "count": 4}]),
              _stage(2, ["shelf"]), _stage(3, ["top"], conf=0.5)]
    steps = recorder.build_steps(stages, "closet", 1800)
    assert [s["title"] for s in steps] == ["Attach the top", "Attach the shelf", "Attach the doors",
                                           "Anchor it to the wall"]
    # step k shows the photo of stage n-k (state after putting part back)
    assert [s["source_photo"] for s in steps[:3]] == ["/p/2.jpg", "/p/1.jpg", "/p/0.jpg"]
    assert steps[0]["confidence"] == 0.5 and steps[2]["hardware_used"] == [{"kind": "hinge", "count": 4}]


def test_recorder_low_furniture_no_anti_tip():
    steps = recorder.build_steps([_stage(0), _stage(1, ["top"])], "nightstand", 550)
    assert len(steps) == 1


def test_letterbox_render(tmp_path):
    from PIL import Image
    src = make_jpeg(tmp_path / "s.jpg", size=(400, 800))
    out = render.letterbox_step(str(src), tmp_path / "o.png", 3, 9, "Attach the doors",
                                [{"kind": "cam_lock", "count": 4}], 0.6)
    with Image.open(out) as im:
        assert im.size == (1080, 1350) and im.mode == "RGB"
        assert im.getpixel((5, 5)) == render.PAPER and im.getpixel((540, 700)) != render.PAPER


@pytest.mark.parametrize("msg", ["I lost the manual for my IKEA wardrobe", "how do I reassemble my closet",
                                 "j'ai démonté mon armoire", "necesito armar un mueble",
                                 "كيف أركب خزانة", "help me put together this bookcase"])
def test_hint_positive(msg):
    assert looks_like_furniture_request(msg)


@pytest.mark.parametrize("msg", ["what's the weather tomorrow", "write a python function to sort a list",
                                 "translate hello to spanish", "", None])
def test_hint_negative(msg):
    assert not looks_like_furniture_request(msg)


def test_recorder_title_joins_parts():
    steps = recorder.build_steps([_stage(0), _stage(1, ["left door", "right door"])], "nightstand", 500)
    assert steps[0]["title"] == "Attach the left door and right door"


def test_recorder_keeps_zero_confidence():
    st = _stage(1, ["top"], conf=0)
    assert recorder.build_steps([_stage(0), st], "nightstand", 500)[0]["confidence"] == 0
    st["described"]["confidence"] = "high"
    assert recorder.build_steps([_stage(0), st], "nightstand", 500)[0]["confidence"] == 0.5


def test_duplicate_photo_is_retagged_not_dropped(tmp_path):
    p = Project()
    a = make_jpeg(tmp_path / "a.jpg")
    photos.add_photos(p, [a], "label", "", tmp_path / "proj")
    rep = photos.add_photos(p, [a], "panel", "", tmp_path / "proj")
    assert rep["added"] == 1 and p.photos[0]["kind"] == "panel" and len(p.photos) == 1
    assert photos.add_photos(p, [a], "panel", "", tmp_path / "proj")["added"] == 0
