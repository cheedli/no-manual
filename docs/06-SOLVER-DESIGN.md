# Solver design — template solver for carcass furniture

Goal: from a list of boards (dims + hole hints + hardware counts) and the
outer dimensions, produce a **correct, ordered** set of assembly steps for
box-shaped ("carcass") flat-pack furniture, with an honest confidence.

We deliberately do **not** do general 3D assembly search. Flat-pack carcass
furniture follows a small number of construction patterns; we encode those
as templates and fit the parts to them. This is reliable, explainable, and
buildable in two days.

## 1. Coordinate system and units
- Millimetres everywhere. Right-handed: X = width (left→right), Y = height
  (floor→up), Z = depth (back→front). Origin at back-left-bottom outer corner.
- Outer dims from the user: W × H × D (mm).
- Typical board thickness t: 12–19 mm (default 16 if unknown, 18 if the user
  says "thick"). Back panels: 3–5 mm hardboard.

## 2. Part roles and classification
Classify each board by its two large dimensions (a ≥ b) relative to W, H, D:

| Role | Signature (tolerance ±3% or ±8 mm, whichever larger) |
|------|-------------------------------------------------------|
| side | a ≈ H, b ≈ D (or D − back recess) ; quantity usually 2 |
| top / bottom | a ≈ W − 2t (between sides) or ≈ W (on top of sides), b ≈ D |
| fixed shelf | a ≈ W − 2t, b ≈ D − (0…30), has cam/dowel holes on short edges |
| loose shelf | like fixed shelf but no edge holes (sits on shelf pins) |
| back | thickness ≤ 6 mm, a ≈ H − (0…20), b ≈ W − (0…20) |
| door | a ≈ H − (0…40) or ≈ (H − plinth), b ≈ W/2 or ≈ W, has hinge cup holes (35 mm) |
| plinth / kick board | a ≈ W − 2t, b ≈ 50–120 |
| divider | a ≈ H − 2t, b ≈ D, placed between top and bottom |

Disambiguation rules:
- top vs bottom: identical boards → interchangeable (say so); if one has
  extra holes for plinth/rail/hanging, that's the top (rail) or bottom (plinth).
- fixed vs loose shelf: edge holes (cam/dowel/confirmat) → fixed.
- sides left vs right: mirror images; distinguished by hole pattern on the
  inner face (holes face inward). Edge banding faces front.
- Anything unmatched → role `unknown`, warning, question to the user.

## 3. Templates
Each template is an ordered list of **operations** with preconditions.

### T1 — "Sides embrace top/bottom" (most bookcases, closets, cabinets)
Top and bottom sit **between** the sides (a ≈ W − 2t). Cam locks or
confirmat screws join them.
1. Sort and count parts and hardware.
2. Insert cam bolts and dowels into the **sides'** inner faces (or
   wherever bolt holes are) — hand-tight.
3. Insert cam lock housings into top/bottom/fixed shelves, arrows toward the
   edge.
4. Lay the **left side** flat, inner face up.
5. Attach **bottom**, then **top**, then **fixed shelves** onto the left side.
6. Attach **plinth** if present (between sides, at the bottom front).
7. Lower the **right side** onto the assembly; turn all cam locks
   clockwise until tight.
8. Square the carcass (measure diagonals; equal within 3 mm).
9. Attach **back panel**: slide into grooves (if sides have grooves) or nail
   onto the back edges.
10. Stand upright (two people for H ≥ 150 cm).
11. Insert shelf pins and place loose shelves.
12. Doors (stretch): hinges → doors → adjust.
13. Hanging rail (closet/wardrobe): rail supports → rail.
14. **Anti-tip: fix to the wall** (always for H ≥ 75 cm).

### T2 — "Top/bottom cap the sides" (some nightstands, low cabinets)
Top and bottom overlap the sides (a ≈ W). Screws/dowels from top into sides.
Order: sides + fixed shelves first as a frame, then cap with bottom, flip,
cap with top, back, then drawers/doors are out of scope.

### T3 — "Divider" variant
T1 plus a vertical divider between top and bottom: attach divider to the
bottom after step 5, before the top.

Template choice:
- If top width ≈ W − 2t → T1; if ≈ W → T2; if a divider exists → T3 (on T1).
- If neither fits within tolerance → confidence ≤ 0.4 and ask the user to
  send a photo of the top's edge or describe how the top meets the sides.

## 4. Hole patterns as evidence
Use holes as **supporting evidence**, not as the primary model (vision is
weak at exact hole positions):
- cam housings (≈15 mm Ø, on a face near an edge) → that edge meets another
  part's face; the part with cam housings is the "horizontal" member in T1.
- dowel holes on an edge ↔ dowel holes on another part's face.
- rows of small holes (≈5 mm) along a side → shelf pins → loose shelves exist.
- 35 mm hinge cups → doors.
- groove along an inner face edge → back panel slides in (no nails).
Each satisfied expectation raises confidence; each contradiction lowers it.

## 5. Confidence scoring
```
start 1.0
× 0.85 per part with role 'unknown'
× 0.9  per role decided only by dimensions (no hole evidence)
× 0.7  if template fit is marginal (any dim outside tolerance but < 2×)
× 0.8  per hardware mismatch (holes vs counts)
× 1.0  for each part confirmed by the user (resets that part's penalty)
clamp to [0, 1]
```
- ≥ 0.75 → proceed.
- 0.6–0.75 → proceed, but flag the uncertain steps (step.confidence) and add
  an explicit photo check after them.
- < 0.6 → do not render; return `questions` (max 4) that would raise it.

## 6. Output: Plan + per-step state
For each step, the solver outputs:
- `parts_added`, `hardware_used`, `instruction`, `checks[]` (what the step
  checker must verify, e.g. "cam lock arrows point to the edge",
  "finished edge faces front", "holes face inward"),
- the **assembly state** after the step: a list of placed parts with
  transforms (position + rotation) used by the renderer and the scene JSON.

Placement uses the template's canonical positions:
- left side at x=0; right side at x=W−t; bottom at y=plinth_h (or 0);
  top at y=H−t; back at z=0 (or in groove at z=g); shelves at evenly spaced
  heights unless hole evidence says otherwise; doors at z=D.

## 7. Fixtures (write these first, Day 2)
`fixtures/*.json` with parts, hardware, outer dims and the **expected step
titles**:
1. `bookcase_80x180.json` — T1, 2 sides, top, bottom, 1 fixed shelf, 3 loose shelves, back nailed.
2. `closet_100x200.json` — T1 + plinth + hanging rail, back in grooves, 2 doors (stretch).
3. `nightstand_45x55.json` — T2, top caps sides, back.
4. `cabinet_divider_120x90.json` — T3.
5. `ambiguous.json` — top/bottom/shelf all same size, no holes → expects questions.

## 8. What the solver must never do
- Never invent parts the user doesn't have.
- Never output a plan for a safety-blocked project.
- Never drop the anti-tip step for tall furniture.
- Never claim ≥ 0.75 confidence when any part is `unknown`.
