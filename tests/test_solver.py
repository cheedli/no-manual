"""Solver fixtures (docs/06 §7), confidence gating, hardware check, placements."""
import json
from pathlib import Path

import pytest

from core import hardware, solver

FIX = Path(__file__).resolve().parents[1] / "fixtures"
ORDERED = ["bookcase_80x180", "closet_100x200", "nightstand_45x55", "cabinet_divider_120x90"]


def load(name):
    return json.loads((FIX / f"{name}.json").read_text())


def run(fx):
    return solver.solve(fx["parts"], fx["hardware"], fx["outer"], fx["category"])


@pytest.mark.parametrize("name", ORDERED)
def test_fixture_step_order(name):
    fx = load(name)
    plan = run(fx)
    assert plan["template"] == fx["template"]
    assert [s["title"] for s in plan["steps"]] == fx["expected_titles"]
    assert plan["confidence"] >= 0.75, (plan["confidence"], plan["questions"], plan["roles"])
    assert plan["hardware_check"]["ok"], plan["hardware_check"]


def test_roles_bookcase():
    r = run(load("bookcase_80x180"))["roles"]
    assert r["P1"] == r["P1.2"] == "side" and {r["P2"], r["P3"]} == {"top", "bottom"}
    assert r["P4"] == "shelf_fixed" and r["P5"] == r["P5.3"] == "shelf_loose" and r["P6"] == "back"


def test_closet_top_is_rail_board():
    r = run(load("closet_100x200"))["roles"]
    assert r["P2"] == "top" and r["P3"] == "bottom" and r["P4"] == "plinth" and r["P7"] == "door"


def test_ambiguous_asks():
    plan = run(load("ambiguous"))
    assert plan["confidence"] < 0.6 and not plan["ready"]
    assert any("short ends" in q for q in plan["questions"]) and len(plan["questions"]) <= 4


def test_confirmation_raises_confidence():
    fx = load("ambiguous")
    sides, boards, back = fx["parts"]
    fx["parts"] = [{**sides, "confirmed": True}, {**back, "confirmed": True},
                   {**boards, "id": "P2", "quantity": 2, "confirmed": True},
                   {**boards, "id": "P4", "quantity": 1, "role": "top", "confirmed": True},
                   {**boards, "id": "P5", "quantity": 1, "role": "bottom", "confirmed": True}]
    fx["hardware"] = [{"kind": "shelf_pin", "count": 8}, {"kind": "wall_anchor", "count": 1}]
    plan = run(fx)
    assert plan["confidence"] >= 0.75 and plan["roles"]["P4"] == "top" and plan["roles"]["P2"] == "shelf_loose"


def test_confirm_all_alone_does_not_resolve_ambiguity():
    fx = load("ambiguous")
    for p in fx["parts"]:
        p["confirmed"] = True
    assert run(fx)["confidence"] < 0.6


def test_unknown_part_flags_first_step():
    fx = load("bookcase_80x180")
    fx["parts"].append({"id": "P9", "dims_mm": {"length": 400, "width": 120, "thickness": 16}})
    s1 = run(fx)["steps"][0]
    assert s1["confidence"] == 0.4 and "P9" in s1["instruction"]


def test_anti_tip_and_two_people():
    s = run(load("bookcase_80x180"))["steps"]
    assert s[-1]["title"] == "Anchor it to the wall" and s[-1].get("safety")
    assert next(x for x in s if x["title"] == "Stand it upright")["two_people"]
    assert run(load("nightstand_45x55"))["steps"][-1]["title"] != "Anchor it to the wall"


def test_unknown_part_warns_not_crash():
    fx = load("bookcase_80x180")
    fx["parts"].append({"id": "P9", "dims_mm": {"length": 400, "width": 120, "thickness": 16}})
    plan = run(fx)
    assert plan["roles"]["P9"] == "unknown" and plan["confidence"] <= 0.74
    assert any("P9" in q for q in plan["questions"])


def test_never_invents_parts():
    fx = load("bookcase_80x180")
    plan = run(fx)
    ids = {f"P{i}" for i in range(1, 7)} | {"P1.2", "P5.2", "P5.3"}
    assert set(plan["placements"]) == ids
    assert {pid for s in plan["steps"] for pid in s["parts_added"]} == ids


@pytest.mark.parametrize("name", ORDERED)
def test_placements_inside_outer(name):
    fx = load(name)
    W, H, D = fx["outer"]["w"], fx["outer"]["h"], fx["outer"]["d"]
    for pid, b in run(fx)["placements"].items():
        x, y, z = b["pos"]
        sx, sy, sz = b["size"]
        assert -1 <= x and x + sx <= W + 1 and -1 <= y and y + sy <= H + 1, (pid, b)
        assert -1 <= z and z + sz <= D + 25, (pid, b)  # doors sit on the front face


def test_hardware_mismatch_message():
    parts = [{"id": "P1", "dims_mm": {"length": 768, "width": 290, "thickness": 16}, "quantity": 2,
              "holes": {"cam_housing": 4}}]
    out = hardware.check(parts, [{"kind": "cam_lock", "count": 6}], 0, False)
    assert not out["ok"]
    assert "Holes for 8 cam locks, but 6 found. Missing 2 × cam lock (≈15 mm)." in out["lines"]


def test_dowels_counted_as_pairs():
    parts = [{"id": "A", "dims_mm": {"length": 1, "width": 1}, "holes": {"dowel_edge": 4}},
             {"id": "B", "dims_mm": {"length": 1, "width": 1}, "holes": {"dowel_face": 4}}]
    assert hardware.check(parts, [{"kind": "dowel", "count": 4}], 0, False)["ok"]
