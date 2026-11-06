"""Unit normalisation for user-measured dimensions."""
from __future__ import annotations

FACTOR = {"mm": 1.0, "cm": 10.0, "in": 25.4}
MIN_MM, MAX_MM = 50.0, 3000.0


def to_mm(value: float, unit: str) -> float:
    if unit not in FACTOR:
        raise ValueError(f"Unknown unit '{unit}'. Use mm, cm or in.")
    return round(float(value) * FACTOR[unit], 1)


def normalize_dims(d: dict) -> dict:
    """{"width","height","depth","unit"} -> {"w","h","d"} in mm, each within 50-3000 mm."""
    unit = d.get("unit") or "cm"
    out = {}
    for key, short in (("width", "w"), ("height", "h"), ("depth", "d")):
        if d.get(key) is None:
            raise ValueError("I need all three: width, height and depth.")
        mm = to_mm(d[key], unit)
        if not MIN_MM <= mm <= MAX_MM:
            raise ValueError(f"{key.capitalize()} {d[key]} {unit} = {mm:g} mm is outside 5-300 cm. "
                             "Please re-measure (outer size of the assembled piece).")
        out[short] = mm
    return out
