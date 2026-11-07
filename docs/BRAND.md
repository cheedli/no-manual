# No Manual — identity

**Name:** No Manual · **Line:** "Build it anyway." · **Voice:** calm, short, practical, never cute.

| Token | Value | Use |
|-------|-------|-----|
| Paper | `#F6F5F1` | background behind every card |
| Card | `#FFFFFF` | step / overview cards (radius 40, soft offset shadow) |
| Ink | `#1A1A1A` | outlines (4 px), numbers, titles |
| Ink soft | `#6E6C66` | secondary text |
| Blueprint | `#2F5BFF` | logo, bullet dots, accent |
| Blueprint tint | `#DCE5FF` | the part added in this step |
| Green / Red / Amber | `#1F9D55` / `#E5484D` / `#F5A524` | hardware complete / stop / "Check this step" |

- **Type:** Atkinson Hyperlegible (OFL, `assets/fonts/`), chosen for legibility on a phone in a
  dusty room. Bold for numbers and titles.
- **Mark:** a white hex (Allen) key bent into an L, inside a blueprint-blue rounded square
  (`core/render.draw_logo`). Every shared step image carries it bottom-right.
- **Drawings:** axonometric line art, heavy ink outlines, faces shaded 85–100 %, a soft ground
  shadow, circled part ids, solid arrowheads from the direction the part comes in, hardware in
  boxed chips (`4×` + icon).
- **Desktop:** the 3D viewer keeps the app theme (`--ui-*` variables); new parts use a light tint
  of the theme accent and sit on a soft ground shadow, echoing the cards.
- Inspired by the paper-manual look of flat-pack instructions (and projects like Bygga), but our
  own palette, mark and type. No retailer branding anywhere.
