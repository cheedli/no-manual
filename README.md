# No Manual — build kit for Claude Code

Everything Claude Code needs to build **No Manual**, a Hermes Agent plugin for
the Nous Research Hermes Agent Plugin Hackathon (deadline **11 Nov 2026,
17:00 EST / 22:00 UTC**).

## How to use
1. Create an empty folder for the plugin repo, e.g. `no-manual/`.
2. Unzip this kit **into that folder** (CLAUDE.md, docs/, templates/ and
   reference/ land at the repo root; all paths in the docs assume this).
3. Open Claude Code in that folder and paste the first prompt below.
4. Before publishing, you can keep `docs/` (nice for reviewers) and delete
   `templates/` and `reference/` (or keep them; they're MIT/your own text).

### First prompt for Claude Code
```
Read CLAUDE.md, then the docs in the read order it lists.
Today is Day 0 of docs/09-BUILD-PLAN.md. Start with tasks T-01 to T-05
(environment + spikes S1–S4). Before writing integration code, clone
https://github.com/NousResearch/hermes-agent into a separate folder and
verify the APIs in docs/03-HERMES-PLUGIN-REFERENCE.md against the live docs;
record any differences in §11 of that file. Report the spike results to me
before moving to Day 1.
```

## What's inside
| File | Purpose |
|------|---------|
| `CLAUDE.md` | Master instructions, rules, commands, definition of done |
| `docs/01-PRD.md` | Problem, users, features, non-goals, metrics |
| `docs/02-ARCHITECTURE.md` | Package layout, data flow, data model, storage |
| `docs/03-HERMES-PLUGIN-REFERENCE.md` | The Hermes APIs we use, distilled + verified-differences table |
| `docs/04-FEATURE-SPECS.md` | F1–F12 with testable acceptance criteria |
| `docs/05-TOOLS-SPEC.md` | 14 tool schemas + `/nomanual` |
| `docs/06-SOLVER-DESIGN.md` | Template solver for flat-pack carcass furniture |
| `docs/07-RENDERING.md` | IKEA-style PNG renderer + 3D scene JSON + Desktop viewer |
| `docs/08-SAFETY-AND-RULES.md` | Safety gate, privacy, catalog rules checklist, disclosure text |
| `docs/09-BUILD-PLAN.md` | Day-by-day plan 6→11 Nov with spikes, checkpoints, scope cuts |
| `docs/10-TESTING.md` | Unit/contract/E2E tests, fake ctx, results table |
| `docs/11-DEMO-SCRIPT.md` | 90-second video shot list, checklist, X post |
| `docs/12-SUBMISSION.md` | Catalog entry YAML, PR template, form steps |
| `docs/adr/` | 7 architecture decision records |
| `templates/` | Drafts: `SKILL.md`, `plugin.yaml`, `pyproject.toml`, `README.md` |
| `reference/hermes-docs/` | Offline snapshot of the relevant hermes-agent docs (MIT) |

## Things only you can do
- Have one real flat-pack piece to take apart and rebuild (the demo).
- Connect Hermes to your Telegram (or WhatsApp) and use a vision-capable model.
- Create the public GitHub repo, record the video, post on X, submit the form.
