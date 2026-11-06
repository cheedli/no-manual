# Hermes plugin reference (distilled for No Manual)

Distilled from the hermes-agent docs at commit
`ed1afb082eb3e46cf2edae9d8f68fb67b09ee4df` (4 Nov 2026). Full snapshots are in
`reference/hermes-docs/`. **Re-verify against the live repo before relying on
any detail**; record differences at the bottom of this file.

## 1. Discovery, validation, install
- A directory plugin = folder with `plugin.yaml` + `__init__.py` (and/or
  `desktop/plugin.js`). User plugins live in `~/.hermes/plugins/<name>/`.
- `hermes plugins doctor [path] --ci` — runs real discovery, manifest parse,
  import, `register(ctx)`, hook/tool registries; flags undeclared tools/hooks,
  callbacks without `**kwargs`. Blocks network during registration.
- `hermes plugins validate` — what catalog CI runs (manifest, `requires_hermes`,
  load, declared-vs-registered tools, install scanner). Use
  `--install-deps` to also resolve Python deps.
- New plugin tools load from the **next session** (prompt/tool schema is
  cache-stable). Hooks and gateway slash commands activate immediately.

## 2. Manifest (`plugin.yaml`)
```yaml
name: no-manual
version: 0.1.0
manifest_version: 2
api_version: 1
description: Furniture with no instructions? Find the manual, record your disassembly, or solve flat-pack assembly from photos, then get step-by-step coaching with photo checks.
author: <you>
license: MIT
homepage: https://github.com/<you>/no-manual
tags: [furniture, assembly, vision, home]
provides_tools:      # MUST match exactly what register() registers
  - nm_start_project
  - nm_add_photos
  - nm_set_details
  - nm_identify
  - nm_attach_manual
  - nm_record_stage
  - nm_finish_recording
  - nm_extract_parts
  - nm_confirm_parts
  - nm_solve
  - nm_render_steps
  - nm_get_step
  - nm_check_step
  - nm_status
provides_hooks:
  - pre_llm_call
  - pre_tool_call
config_schema:
  units: {type: str, default: "metric", description: "metric or imperial for displayed sizes"}
  max_photos_per_call: {type: int, default: 6, description: "images per vision call"}
```
- `requires_env` is not needed (no API keys of our own).
- Python deps: prefer `pyproject.toml` beside `plugin.yaml` (wins over
  `python_dependencies`). Always upper-bound: `pillow>=10,<12`,
  `pypdfium2>=4.20,<5`, `numpy>=1.26,<3`. Keep the list minimal.
- Capabilities (`capabilities:` list) are only for privileged host surfaces;
  we need none.

## 3. Registration (`__init__.py`)
```python
from pathlib import Path
from . import schemas, tools, hooks

def register(ctx):
    for name, schema, handler in tools.TOOLS:          # keep one table
        ctx.register_tool(name=name, toolset="no-manual",
                          schema=schema, handler=tools.bind(handler, ctx))
    ctx.register_hook("pre_llm_call", hooks.inject_hint)
    ctx.register_hook("pre_tool_call", hooks.safety_guard)
    skill = Path(__file__).parent / "skills" / "no-manual-guide" / "SKILL.md"
    ctx.register_skill("no-manual-guide", skill)
    ctx.register_command("nomanual", lambda raw: tools.slash(ctx, raw),
                         description="No Manual: list or resume furniture projects")
```
Context surface we use:
- `ctx.register_tool(name, toolset, schema, handler)`
- `ctx.register_hook(name, callback)` — callbacks must accept `**kwargs`
- `ctx.register_skill(name, path)` → agent loads with
  `skill_view("no-manual:no-manual-guide")`. Plugin skills are **not** listed in
  the system prompt's skill index — hence our `pre_llm_call` hint (below).
- `ctx.register_command(name, handler, description=...)` — `/nomanual`
- `ctx.dispatch_tool(name, arguments)` — call built-in tools with approvals
- `ctx.get_config(key, default=...)`, `ctx.state` (≤10 MiB, profile-scoped)
- `ctx.llm` — see §5

## 4. Tool handlers
```python
def nm_status(args: dict, **kwargs) -> str:
    try:
        ...
        return json.dumps({"ok": True, ...})
    except Exception as e:
        return json.dumps({"error": str(e), "hint": "..."})
```
Rules: return a JSON **string** always; never raise; accept `**kwargs`
(Hermes injects `task_id`, `session_id`, `user_task`, `parent_agent`, …).
Descriptions in schemas must say *when* to use the tool.

## 5. LLM + vision from plugin code: `ctx.llm`
```python
result = ctx.llm.complete_structured(
    instructions="Extract every flat panel visible ...",
    input=[{"type": "text", "text": "..."},
           {"type": "image", "data": img_bytes, "mime_type": "image/jpeg"}],
    json_schema=PARTS_SCHEMA,
    timeout=60,                       # default 15 s, capped at 60
    purpose="no-manual.extract_parts",
)
if result.content_type == "json": parts = result.parsed
else: fallback using result.text
```
- Runs on the user's active provider/model; vision is routed automatically to
  the configured vision model when images are supplied.
- **Do not** pass `provider=`/`model=` (trust gate raises `PluginLlmTrustError`
  without operator opt-in).
- Async variants: `acomplete`, `acomplete_structured`.
- Downscale images before sending (long edge ≤ 1600 px, JPEG q85).

## 6. Hooks we use
| Hook | Use | Return |
|------|-----|--------|
| `pre_llm_call(session_id, user_message, conversation_history, is_first_turn, model, platform, **kw)` | If the message looks like a furniture-assembly request (cheap keyword check: assemble, manual, instructions, closet, wardrobe, IKEA, flat-pack, screws, panels… plus a few common non-English words), return a short context string: "The No Manual plugin is installed. Load skill_view('no-manual:no-manual-guide') and follow it." Otherwise return None. | str or None |
| `pre_tool_call(tool_name, args, task_id, **kw)` | Safety guard: if tool is `nm_solve`/`nm_render_steps` and the project's safety_status is blocked → `{"action": "block", "message": "..."}` | directive or None |

## 7. Storage
```python
from plugins.plugin_storage import plugin_data_dir, plugin_db
root = plugin_data_dir("no-manual")          # <HERMES_HOME>/plugin-data/no-manual/
conn = plugin_db("no-manual")                # <root>/data.db, WAL
```
Never write into the plugin folder. Secrets never go here.

## 8. Images in and out
- **In:** messaging adapters stage inbound images in `<HERMES_HOME>/cache/images/`
  and attach them to the message (`MessageEvent.media_urls`). Whether the
  model sees the **local path** as text (so it can pass it to our tools) must
  be verified on Day 1 (spike S1, doc 09). Our tools accept `image_paths`; the
  fallback is `nm_add_photos {"recent": true}` which picks images in
  `cache/images/` newer than the project's last photo (max 20, same session
  window), and asks the user to confirm the count.
- **Out:** to send a file to the user on any surface, the agent writes a line
  `MEDIA:<absolute_path>` in its reply. Our tool results therefore return
  absolute paths and the skill instructs the agent to emit `MEDIA:` lines.

## 9. Desktop half (unified package)
- `desktop/plugin.js` default-exports `{ id: 'no-manual', name, register(ctx) }`.
- Only `@hermes/plugin-sdk`, `react`, `react/jsx-runtime` can be imported.
  Bundle three.js in with esbuild; mark those three as external.
- No JSX syntax in the loaded file (use `jsx()`/`jsxs()`); never hardcode
  colors (use `var(--ui-*)`); use `ctx.setTimeout/ctx.addEventListener`;
  canvas must track its container with `ResizeObserver`; module evaluation
  must finish < 10 s.
- **Tool media renderer:** `ctx.register({ id: 'step-viewer', area:
  sdk.TOOL_MEDIA_RENDERER_AREA, data: { tools: ['nm_render_steps','nm_get_step'],
  render: props => jsx(StepViewer, props) } })`. Props: `file` (path, kind,
  `resolveUrl()`), `args`, `result`, `sessionId`, `fallback`. Return
  `fallback` for anything we don't draw. Guard with
  `if (typeof sdk.TOOL_MEDIA_RENDERER_AREA !== 'string') return`.
- Backend routes: `dashboard/manifest.json` `{"name":"no-manual","api":"plugin_api.py"}`;
  `plugin_api.py` routes are reachable from the desktop half via
  `ctx.rest('/scene?project=...&step=...')`. See SDK doc §"The Python side".
- Unified package copy lands in `$HERMES_HOME/desktop-plugins/no-manual/`;
  use **Rescan** in Capabilities → Plugins after rebuilding plugin.js.

## 10. Common mistakes (from the docs)
- Returning a dict instead of a JSON string.
- Raising from a handler.
- Vague tool descriptions (model won't call the tool).
- Declared `provides_tools` not matching registered tools → validate fails.
- Bare `>=` dependency floors → reviewers flag them.

## 11. Verified differences (fill in as you go)
| Date | Item | Doc said | Live source says |
|------|------|----------|------------------|
| 2026-11-06 | Source checked | commit `ed1afb08` (4 Nov) | main `6b21d056` (7 Nov); installed stable = **Hermes Agent v0.23.0 (2026.9.24)**, local `2bd378ed1b8d` → `requires_hermes: ">=0.23.0"` (SemVer, rule 14) |
| 2026-11-06 | `plugins doctor` | `doctor [path] --ci` | Same: `doctor [target] --ci`, target defaults to `.`, may also be an installed plugin id |
| 2026-11-06 | `plugins validate` | `validate . --install-deps` | Same; `path` is required; `--json` also available for CI output |
| 2026-11-06 | `plugins install file://$(pwd)` | local install | `file://` is accepted but treated as a **Git URL** (security warning shown) → the plugin folder must be a git repo with a commit. Non-interactive flags: `--yes-deps`, `--enable`; `--ref <40-char sha>` to pin |
| 2026-11-07 | Spike S1 (CLI) — photo paths | must verify if model sees local paths | **Yes (CLI).** Model passed `~/.hermes/cache/documents/native-inputs/<sha256>/upload_*.jpg` to the tool unprompted; same file also staged in `~/.hermes/cache/images/upload_*.jpg`. `recent: true` fallback should scan both dirs. Telegram path still to confirm |
| 2026-11-07 | Handler kwargs | `task_id`, `session_id`, `user_task`, `parent_agent`… | Received: `session_id`, `task_id`, `user_task` |
| 2026-11-07 | Spike S2 — `ctx.llm.complete_structured` + image bytes | works | **Yes.** `content_type == "json"`, `parsed` matched schema, 3.4 s, provider `openai-codex` / `gpt-6.1-sol` |
| 2026-11-07 | Spike S3 — `MEDIA:` out | agent writes `MEDIA:<abs path>` | **Yes (CLI + gateway source).** Model emitted `MEDIA:/Users/…/plugin-data/no-manual/spike_media_out.png` on its own line. Gateway `extract_media` **masks MEDIA inside code blocks, quotes and JSON string values** → tool results can't self-deliver; the agent must write a bare line (skill must say so). `plugin-data/` is not deny-listed. In strict mode (`HERMES_MEDIA_DELIVERY_STRICT=1`) only cache dirs, `HERMES_MEDIA_ALLOW_DIRS` or *recently written* files pass → `nm_get_step` should re-touch/re-render the PNG it returns |
| 2026-11-07 | `MEDIA:` per platform | always emit `MEDIA:` | Hermes's platform prompt tells the model that in **CLI/TUI** `MEDIA:` is not intercepted → it gives the plain path instead (seen in E2E). Messaging + Desktop intercept it. Our skill/tool text defers to the platform rule |
| 2026-11-07 | Plugin install deps | — | `plugins install file://… --enable --yes-deps` only added pypdfium2: **Pillow is already in Hermes core**. Current releases: Pillow 13.0, pypdfium2 5.15 → bounds `pillow>=10.1,<14`, `pypdfium2>=4.20,<6` |
| 2026-11-07 | New plugin deps at runtime | — | **CLI chats run through the gateway process**: deps installed by `plugins install` aren't importable until `hermes gateway restart` (`ModuleNotFoundError: pypdfium2` in E2E). README must say to restart once; `nm_attach_manual` returns that hint |
| 2026-11-07 | Manual finder E2E | — | IKEA BILLY 80×28×106 named by user → `nm_identify` + agent web search found `ikea.com/.../billy-bookcase-white__AA-1844854-6-2.pdf`; agent asked the user to confirm the match (photo had a CD insert) before `nm_attach_manual`; 16 pages rendered |
| 2026-11-07 | Spike S4 — Desktop half | — | Not run: Hermes Desktop app not installed. Deferred to Day 4 (T-40), cut-able per C4 |
| 2026-11-07 | Plugin tools | load next session | Confirmed; `hermes plugins enable <name>` needed for user plugins (`--no-allow-tool-override` skips prompt) |
