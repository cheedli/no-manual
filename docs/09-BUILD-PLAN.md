# Build plan — 6 → 11 November 2026 (solo)

Deadline: **Wed 11 Nov, 22:00 UTC** (17:00 EST). Internal deadline for the
form: **11 Nov, 20:00 UTC** (2 h safety margin).
Assumed capacity: ~44 focused hours. Buffer reserved: 7 h (16%).

Legend: ⛳ checkpoint · ✂ pre-agreed scope cut if the checkpoint fails ·
⚠ critical path.

---

## Day 0 — Fri 6 Nov (evening, ~3 h): environment + spikes
| ID | Task | h |
|----|------|---|
| T-01 | Install/update Hermes; `hermes --version` (note it for `requires_hermes`). Connect the Telegram gateway to your own bot. Create public GitHub repo `no-manual` (MIT). | 0.75 |
| T-02 ⚠ | **Spike S1 — photo paths.** Plugin with one tool `nm_echo(image_paths)` that returns what it received. Send 2 photos on Telegram and ask Hermes to call it. Does the model know the local paths (`cache/images/...`)? Record the answer in doc 03 §11. If not, implement the `recent: true` fallback (scan `<HERMES_HOME>/cache/images` by mtime). | 0.75 |
| T-03 ⚠ | **Spike S2 — vision via ctx.llm.** Call `ctx.llm.complete_structured` with one panel photo + a tiny JSON schema. Confirm `result.parsed`, latency, and that your configured model accepts images. | 0.5 |
| T-04 | **Spike S3 — MEDIA out.** Tool writes a PNG to plugin data dir; ask the agent to reply with `MEDIA:<path>`; confirm the photo arrives in Telegram. | 0.5 |
| T-05 | **Spike S4 — Desktop half.** Minimal `desktop/plugin.js` that registers a tool media renderer for `nm_echo` and shows "hello". Rescan in Capabilities → Plugins. | 0.5 |
⛳ **C0:** S1–S3 pass (S1 via paths or fallback). ✂ If S2 fails with your model, switch Hermes to a vision-capable model for the project; note it in README requirements.

## Day 1 — Sat 7 Nov (~9 h): skeleton + recorder mode end to end
| ID | Task | h |
|----|------|---|
| T-10 ⚠ | Repo skeleton per doc 02; `plugin.yaml`, `pyproject.toml`, `__init__.py`, tool table, `.gitignore` (`__pycache__/`, `*.pyc`, `node_modules/`). Remove the spike tool `nm_echo`. `hermes plugins doctor . --ci` green. | 1 |
| T-11 ⚠ | `core/models.py`, `core/store.py` (sqlite schema, migrations-by-version), unit tests. | 1.5 |
| T-12 | `core/safety.py` + `hooks.safety_guard` + tests (F2 AC1–AC2). | 1 |
| T-13 ⚠ | Tools: `nm_start_project`, `nm_add_photos`, `nm_set_details`, `nm_status`; `/nomanual`. | 1.5 |
| T-14 ⚠ | `core/recorder.py` + `nm_record_stage` + `nm_finish_recording` (vision describe + reverse + header images via `core/render.py` letterbox mode). | 2 |
| T-15 | Skill v1 `skills/no-manual-guide/SKILL.md` (flow from doc 04 F12) + `pre_llm_call` hint + keyword tests. | 1 |
| T-16 | E2E on Telegram: record a small real piece (≥ 5 stages) → receive the reversed manual. | 1 |
⛳ **C1:** recorder E2E works on a real piece. ✂ If not, cut F11 (Desktop viewer) now to free Day 4.

## Day 2 — Sun 8 Nov (~9 h): manual finder + solver core
| ID | Task | h |
|----|------|---|
| T-20 | `nm_identify` (vision → brand/article numbers/search queries) + skill section on running `web_search`. | 1.5 |
| T-21 | `core/manual.py` + `nm_attach_manual` (https download with limits, pypdfium2 render) + tests with a local PDF. | 1.5 |
| T-22 ⚠ | `fixtures/*.json` (5 fixtures, doc 06 §7) with expected step titles. | 1 |
| T-23 ⚠ | `core/geometry.py` + classification (doc 06 §2) + tests. | 1.5 |
| T-24 ⚠ | `core/solver.py` T1 + confidence (§5) + `core/hardware.py` count check + tests. Then T2/T3 if time. | 2.5 |
| T-25 | E2E: manual finder on 2 branded pieces (yours or friends'). | 1 |
⛳ **C2:** T1 fixtures pass; manual finder works on ≥ 1 real piece. ✂ If T2/T3 aren't done, ship T1 only (closets/bookcases/cabinets — still the demo).

## Day 3 — Mon 9 Nov (~10 h): extraction, rendering, step check, PR
| ID | Task | h |
|----|------|---|
| T-30 ⚠ | `core/vision.py` prompts + schemas; `nm_extract_parts` (batching ≤ 6 images, reconcile with outer dims, questions) + `nm_confirm_parts`. | 2.5 |
| T-31 ⚠ | `core/render.py` PNG renderer (doc 07 §1) + overview image + golden tests. | 2.5 |
| T-32 ⚠ | `core/scene.py` + `nm_solve`, `nm_render_steps`, `nm_get_step`. | 1 |
| T-33 ⚠ | `nm_check_step` (user photo + expected image + checks[]) + tests with mocked LLM. | 1.5 |
| T-34 ⚠ | E2E solver on a real flat-pack piece (take it apart → photograph pieces → solve → coach → check a deliberately wrong step). | 1.5 |
| T-35 ⚠ | README with disclosures (doc 08 §4), `hermes plugins validate . --install-deps` green, tag a commit, **open the catalog PR** (doc 12). | 1 |
⛳ **C3:** PR open with green CI. ✂ If extraction is unreliable on your real piece: keep the solver, but make `nm_extract_parts` lean on the user — it asks for each panel's length/width ("measure P1") and only uses vision for counting holes/hardware. Demo still works.

## Day 4 — Tue 10 Nov (~9 h): Desktop viewer, polish, proof
| ID | Task | h |
|----|------|---|
| T-40 | Desktop viewer (doc 07 §3): source in `desktop/src/`, esbuild bundle with three.js, tool media renderer, `plugin_api.py` scene route with path checks. | 3 |
| T-41 | Results table: run all modes on up to 5 pieces; record outcomes (incl. one honest failure) in README. | 2 |
| T-42 | Polish prompts/skill from E2E failures; wording of all user-facing messages (plain, short, friendly). | 1.5 |
| T-43 | Screenshots for PR and catalog `screenshots:`; banner image. | 0.5 |
| T-44 | Update the PR's pinned SHA to the latest tested commit; re-run validate. | 0.5 |
| T-45 | Demo rehearsal ×3 using doc 11 script; fix whatever breaks. | 1.5 |
⛳ **C4 (Tue 18:00 local):** 3 clean rehearsals. ✂ If the Desktop viewer isn't solid by 14:00, drop it from the demo (PNG steps only) and keep it out of the release commit.

## Day 5 — Wed 11 Nov (deadline day)
| Time (UTC) | Task |
|------------|------|
| 08:00–11:00 | Record the demo (doc 11). Edit to < 90 s. |
| 11:00–13:00 | Final validate at the pinned SHA; PR description complete; reply to any reviewer comments. |
| 13:00–14:00 | Post the video on X tagging @NousResearch (text in doc 12). |
| 14:00–15:00 | Submit the Typeform with PR link + X link. **Done by 15:00 UTC if possible.** |
| 15:00–22:00 | Buffer. Nothing new. |

## Milestones
| % of time | Date/time | Milestone |
|-----------|-----------|-----------|
| 25% | Sat 7 Nov evening | Recorder E2E (C1) |
| 50% | Sun 8 Nov evening | Finder + solver fixtures (C2) |
| 75% | Mon 9 Nov night | PR open, solver E2E (C3) |
| 90% | Tue 10 Nov evening | Rehearsed demo (C4) |

## Critical path
T-02 → T-10 → T-11 → T-13 → T-14 → T-22 → T-23 → T-24 → T-30 → T-31 → T-32 →
T-33 → T-34 → T-35 → (record) → submit.

## What you need physically
- One real flat-pack piece you can take apart and rebuild (bookcase, small
  cabinet or closet). This is the demo.
- A tape measure, good light, an A4 sheet (scale reference).
- Optional: 2–4 branded pieces (yours/friends') for the manual-finder table.
