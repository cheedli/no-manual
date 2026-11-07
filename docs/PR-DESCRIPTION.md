Adds No Manual (`plugin-catalog/no-manual.yaml`) — Hermes Agent Plugin Hackathon entry.

**What it does**
- Helps people assemble furniture that has no instructions: finds the official manual, turns
  disassembly photos into a reversed manual, or solves flat-pack carcass furniture (closets,
  wardrobes, bookcases, cabinets, nightstands) from photos of the parts; then coaches step by step
  and checks a photo of each step before moving on.

**Hermes surfaces used**
- 14 tools (toolset `no-manual`), hooks `pre_llm_call` (skill hint) and `pre_tool_call` (safety
  guard), a bundled skill (`no-manual:no-manual-guide`), slash command `/nomanual`, `ctx.llm`
  structured calls with images, `plugin_data_dir` / `plugin_db` storage, `MEDIA:` delivery, Desktop
  tool media renderer (3D step viewer, three.js bundled, source in `desktop/src/`) + dashboard
  `plugin_api.py` route (`/scene`, path-guarded to the plugin's data folder).

**Disclosures (rule 13)**
> No Manual sends the photos you add to a project to your own configured model provider through
> Hermes (`ctx.llm`) to read panels, labels and step photos. When you ask it to find a manual,
> Hermes's web search tool runs searches, and the plugin downloads the chosen PDF over https (max
> 30 MB, public hosts only) into the plugin's data folder. Photos, manual pages and generated images
> are stored in `<HERMES_HOME>/plugin-data/no-manual/` and deleted with `/nomanual delete`. A Desktop
> half renders a 3D step viewer (three.js bundled; source in `desktop/src/`). No shell commands, no
> background processes, no telemetry, no credentials stored. Generated instructions are a best effort
> and are never produced for children's furniture or anything people sit, sleep or climb on.

**Safety**
- Generated instructions are never produced for children's furniture or anything people sit, sleep,
  stand or climb on (manual-only path), enforced in the handlers and again in `pre_tool_call`; a
  vision guess of blocked furniture also blocks the project (fail closed). Tall furniture always ends
  with an anti-tip step.

**Validation**
- `hermes plugins validate <path> --install-deps` passes at the pinned sha on Hermes v0.23.0:
  manifest, requires_hermes, loadable (`__init__.py`, `desktop/plugin.js`), declared tools/hooks
  match, security scan safe, no core override, desktop surface stays inside the SDK.
- 87 unit/contract tests (`pytest -q`), including solver fixtures, golden images and the safety gate.

**Screenshots**
- `assets/solver-overview.png`, `assets/solver-step.png`, `assets/recorder-step.png`,
  `assets/desktop-3d-viewer.png`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
