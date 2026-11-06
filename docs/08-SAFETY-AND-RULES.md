# Safety, privacy and catalog rules — non-negotiable

## 1. Product safety
Furniture that fails can hurt people. Judges and catalog reviewers will ask.

### 1.1 Blocked categories (solver and recorder output never generated)
`crib`, `cot`, `bunk_bed`, `loft_bed`, any `bed`, `high_chair`,
`changing_table`, `playpen`, `stair_gate`, anything a person sits, stands,
sleeps or climbs on, and anything wall-mounted that holds weight
(wall shelves, wall cabinets).
- Allowed for these: **manual finder only** (official manufacturer manual).
- If no official manual is found: say so clearly and recommend contacting the
  manufacturer or a professional. Do not improvise steps.
- Detection: category from the user **and** vision `category_guess` during
  identify/extract. Either one blocked → blocked (fail closed).
- Enforced in code twice: in the tool handlers and in the `pre_tool_call` hook.

### 1.2 Always-on safety content
- **Anti-tip:** tall furniture (H ≥ 75 cm) always ends with a wall-anchoring
  step that says to use the anchor hardware and wall fixings suited to the
  wall type, and to ask for help if unsure.
- **Two-person steps:** standing up or lifting pieces with H ≥ 150 cm.
- **Missing hardware:** never suggest skipping a cam lock, dowel or screw;
  name the missing part and size instead.
- **Uncertain steps:** confidence badge + mandatory photo check.

### 1.3 Disclaimer (README + first message in solver mode)
"Instructions generated from photos are a best effort. Follow the official
manual whenever one exists. Don't use generated instructions for children's
furniture or anything people sit, sleep or climb on."

## 2. Privacy
- Photos are copied into `<HERMES_HOME>/plugin-data/no-manual/projects/<id>/`
  on the user's machine. Nothing leaves the machine except:
  - images sent to the **user's own configured LLM provider** through
    `ctx.llm` (vision calls),
  - manual PDF downloads from URLs the agent found (https only),
  - web searches run by Hermes's own `web_search` tool (agent-driven).
- No telemetry. No third-party services of our own.
- `/nomanual delete <id>` deletes a project's rows and files.

## 3. Catalog admission rules — our compliance checklist
Source: `reference/hermes-docs/catalog-submission.md` (18 rules). Mapped:

| Rule | What it means for us | How we comply |
|------|----------------------|---------------|
| 1 Human-merged gate | Only via PR to hermes-agent | One file `plugin-catalog/no-manual.yaml` |
| 2 Exact SHA pins | 40-char commit SHA | Pin the commit you tested |
| 3 No self-updating code | Never fetch/replace our own code | We only fetch PDFs (data) |
| 4 SHA bumps are new PRs | Plan one bump max | Keep the PR focused |
| 5 Owner submits | You submit your own repo | ✔ |
| 6 Capabilities match reality | `provides_tools/hooks` exact | Doctor + validate green |
| 7 Install scanner | Runs in validate | Fix all warnings |
| 8 Desktop stays in SDK | No eval, no extra imports, no DOM reach-in | Bundle three.js; only SDK/react imports; no prototype patching by our code |
| 9 No core overrides | Public surfaces only | Hooks + register_* only |
| 10 Dependency policy | Upper bounds | `pyproject.toml` bounded |
| 11 Credentials via Hermes | No key files | We need none; vision via ctx.llm |
| 12 Approvals/unattended respected | Never route around approvals | No shell commands; nothing runs unattended |
| 13 Disclose risky behaviour | README + PR description | Disclosure block below |
| 14 Truthful `requires_hermes` | SemVer floor ≤ current release, also in plugin.yaml | Use the version you tested on |
| 15 No forks of bundled plugins | — | Original |
| 16 One listing per lineage | — | Original |
| 17 No unscannable payloads | No binaries, no .pyc, no opaque archives | Bundled plugin.js is readable JS; also commit `desktop/src/` + build script; `.gitignore` `__pycache__/` |
| 18 Password managers | — | N/A |

## 4. Disclosure block (paste into README and PR description)
> **Disclosure** — No Manual sends the photos you add to a project to your
> own configured model provider through Hermes (`ctx.llm`) to read panels,
> labels and step photos. When you ask it to find a manual, Hermes's web
> search tool runs searches, and the plugin downloads the chosen PDF over
> https (max 30 MB) into the plugin's data folder. Photos, manual pages and
> generated images are stored in `<HERMES_HOME>/plugin-data/no-manual/` and
> deleted with `/nomanual delete`. A Desktop half renders a 3D step viewer
> (three.js bundled; source in `desktop/src/`). No shell commands, no
> background processes, no telemetry, no credentials stored. Generated
> instructions are a best effort and are never produced for children's
> furniture or anything people sit, sleep or climb on.
