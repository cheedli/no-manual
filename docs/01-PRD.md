# PRD — No Manual

**Status:** Locked for hackathon MVP · **Date:** 6 Nov 2026 · **Owner:** [TBD: your name]

## 1. Problem
People regularly end up with furniture they cannot assemble:
- they took it apart to move and can't remember how it goes back;
- they bought it second-hand, or it was a hand-me-down, without the manual;
- the brand closed, the label is gone, or the manual was never in the box.

Real examples (collected during research): a parent with a second-hand crib
whose maker went into administration; a buyer who disassembled a desk to move
and lost the instructions; a loft-bed owner facing "a pile of wood and a pile
of screws"; volunteers assembling donated returns that arrived without
instructions. Today's options: search forums, guess, or pay a handyman.

## 2. Users
Everyday, non-technical people. They talk to Hermes from their phone
(Telegram/WhatsApp via the Hermes gateway) or from Hermes Desktop. They can
take photos and measure with a tape. They will not install anything beyond
the plugin.

## 3. Solution
A Hermes plugin with three modes, tried in this order:

1. **Manual finder.** Identify the product from photos (labels, stamped part
   numbers, brand marks, shape) and find the official manual online. Present
   its pages step by step.
2. **Disassembly recorder.** If the furniture is still assembled, the user
   photographs each stage while taking it apart. Hermes reverses the sequence
   into an assembly manual made from the user's own photos, annotated.
3. **Flat-pack solver.** If it is already in pieces and no manual exists, the
   user photographs every panel and the hardware, gives the outer dimensions,
   and Hermes models the panels as simple boards, infers the assembly with a
   template-based solver, and renders IKEA-style steps.

In every mode, **live coaching**: after each step the user sends a photo and
Hermes checks it against the expected state before moving on.

## 4. MVP features (must ship)
| # | Feature | Mode |
|---|---------|------|
| F1 | Intake: start a project, collect photos, ask "assembled or in pieces?", collect category and outer dimensions | all |
| F2 | Safety gate for child/person-load-bearing furniture | all |
| F3 | Product identification + manual search + manual PDF to step pages | 1 |
| F4 | Disassembly recorder → reversed, annotated assembly manual | 2 |
| F5 | Part extraction from photos (panels, holes, hardware counts) with user confirmation | 3 |
| F6 | Template solver for carcass furniture (closet, wardrobe, bookcase, cabinet, nightstand) | 3 |
| F7 | Hardware count check ("8 cam locks, 8 holes — complete") | 3 |
| F8 | Step renderer: IKEA-style PNG per step + 3D scene JSON | 3 |
| F9 | Live step check from the user's photo | all |
| F10 | Project state saved per user, resumable across sessions | all |
| F11 | Desktop: interactive 3D step viewer (tool media renderer) | 3 |
| F12 | Bundled skill that teaches the agent the end-to-end flow | all |

## 5. Non-goals (out of scope for the hackathon)
- AR camera overlay (roadmap slide only).
- Photogrammetry / photorealistic 3D scans.
- Upholstered furniture, chairs, sofas, beds of any kind, anything with
  mechanisms (recliners, sofa beds), outdoor furniture, metal frames.
- Drawers with runners in the solver (finder and recorder still cover them).
  Hinged doors are a stretch goal (see build plan).
- Ordering replacement parts automatically (we only name the part and size).

## 6. Success metrics (estimates, for the demo and README)
- Manual finder: finds the official manual for ≥ 3 of 5 branded test pieces.
- Recorder: produces a complete, correctly ordered manual for 1 real piece.
- Solver: correct assembly order for ≥ 2 of 3 carcass test fixtures; never
  wrong-but-confident (confidence < 0.6 must trigger a question to the user).
- Step check: flags a deliberately wrong step in ≥ 4 of 5 trials.
- End-to-end demo flow runs without manual intervention, 3 rehearsals in a row.

## 7. Demo moment (what judges must remember)
A messy pile of unlabeled panels → the same panels flying together in 3D →
a phone buzzing "Step 4 done. Next: the back panel." → the user sends a photo
with a panel upside down → Hermes: "Stop — that panel is upside down; the
holes should face inward."

## 8. Risks
| Risk | Mitigation |
|------|-----------|
| Vision misreads panels/holes | Ask for outer dimensions; confirm part roles with the user; confidence gating |
| Incoming photo paths not reachable from tools | Day-1 spike S1 with fallback (doc 09) |
| Solver too ambitious | Template solver, carcass only; recorder + finder still deliver value |
| Safety objections | Hard safety gate (doc 08); anti-tip step always included |
| Time | Daily checkpoints with pre-agreed scope cuts (doc 09) |
