# CLAUDE.md — No Manual (Hermes Agent plugin)

You are building **No Manual**, a Hermes Agent plugin for the Nous Research
Hermes Agent Plugin Hackathon. Read this file fully, then read the docs in the
order listed under "Read order". Do not start coding until you have done the
Day-1 spikes in `docs/09-BUILD-PLAN.md`.

## One-line pitch
Photograph any furniture that has no instructions, and Hermes finds the
manual, writes one from your disassembly, or works out the assembly, then
coaches you step by step, checking a photo of each step, until it's built.

## Hard deadline
Submissions close **Wednesday 11 November 2026, 17:00 EST (22:00 UTC)**.
To enter, three things must exist before then:
1. An open pull request adding `plugin-catalog/no-manual.yaml` to
   `NousResearch/hermes-agent` (see `docs/12-SUBMISSION.md`).
2. A demo video under 90 seconds posted on X, tagging @NousResearch.
3. Both links submitted through the hackathon form.
Target: catalog PR open by **9 November**. Everything after that is polish.

## Judging criteria (from the official announcement)
Usefulness, reliability, polish and creativity. Judges favour plugins that do
more than a prompt or a skill could. Every design choice should serve one of
these four, and reliability on camera beats feature count.

## Read order
1. `docs/01-PRD.md` — what we build and what we do NOT build
2. `docs/02-ARCHITECTURE.md` — components, data flow, data model
3. `docs/03-HERMES-PLUGIN-REFERENCE.md` — the Hermes APIs we use (verified
   against the hermes-agent docs snapshot in `reference/hermes-docs/`)
4. `docs/05-TOOLS-SPEC.md` — exact tool names, schemas, return shapes
5. `docs/04-FEATURE-SPECS.md` — acceptance criteria per feature
6. `docs/06-SOLVER-DESIGN.md` and `docs/07-RENDERING.md`
7. `docs/08-SAFETY-AND-RULES.md` — non-negotiable rules
8. `docs/09-BUILD-PLAN.md` — day-by-day plan with spikes and checkpoints
9. `docs/10-TESTING.md`, `docs/11-DEMO-SCRIPT.md`, `docs/12-SUBMISSION.md`
10. `docs/adr/` — architecture decisions already taken (don't relitigate them
    without a concrete reason; if you must, write a new ADR)
11. `templates/` — drafts to turn into real files: `SKILL.md.draft` →
    `skills/no-manual-guide/SKILL.md`, `plugin.yaml.draft`, `pyproject.toml.draft`,
    `README.md.draft` → replaces this kit's root `README.md` once the plugin
    works (keep the disclosure block and results table).
12. `reference/hermes-docs/` — offline snapshot of the hermes-agent docs we
    rely on (MIT). Live docs win if they differ.

## Working rules for you (Claude Code)
- **Verify APIs before relying on them.** The reference doc distils the
  hermes-agent docs at commit `ed1afb08` (4 Nov 2026). Hermes moves fast.
  Before writing integration code, check the live docs/source in a clone of
  `https://github.com/NousResearch/hermes-agent` (and
  `https://github.com/NousResearch/hermes-example-plugins` for ctx.llm image
  examples). If something differs, the live source wins; note it in
  `docs/03-HERMES-PLUGIN-REFERENCE.md` under "Verified differences".
- **Tool handlers:** signature `def handler(args: dict, **kwargs) -> str`,
  always return a JSON string, never raise (catch and return `{"error": ...}`).
- **Small, testable modules.** Geometry, solver and renderer are pure Python
  with unit tests and no Hermes imports, so they run in plain `pytest`.
- **Pin dependencies with upper bounds** (`pkg>=x,<y`). Keep the list short.
- **No bundled binaries, no downloaded executables, no self-updating code.**
- **Never write runtime data into the plugin directory.** Use
  `plugin_data_dir("no-manual")` / `plugin_db("no-manual")`.
- **All LLM calls go through `ctx.llm`** (host-owned credentials). No API keys
  of our own, no direct provider SDKs.
- **Safety rule is absolute:** never generate solver-based instructions for
  cribs, cots, bunk/loft beds, high chairs, baby changing tables or anything
  load-bearing for a person. Official manual or a clear refusal. See doc 08.
- **Honesty in output:** every generated step carries a confidence; uncertain
  steps say so and ask for a photo. Never present a guess as certain.
- Commit early and often with clear messages. Keep `main` runnable.
- When a day's checkpoint in the build plan fails, stop and cut scope as the
  plan says instead of pushing on.

## Commands you will use
```bash
hermes plugins doctor . --ci              # load + registration check
hermes plugins validate . --install-deps  # same checks catalog CI runs
pytest -q                                 # pure-Python unit tests
hermes plugins install file://$(pwd)      # local install for manual testing
hermes chat                               # try it in the CLI
```
(Confirm exact flags with `hermes plugins --help`; they may have changed.)

## Definition of done (for the hackathon)
- Plugin installs from the catalog PR's pinned SHA and passes
  `hermes plugins validate`.
- The three modes work end to end on at least one real piece of furniture:
  manual finder, disassembly recorder, flat-pack solver (cabinet/closet).
- Step images arrive in Telegram (or the CLI) via `MEDIA:` lines; the Desktop
  shows an interactive 3D step viewer for solver output.
- Live step check catches a deliberately wrong step on camera.
- README with disclosures, catalog entry, demo video, form submitted.
