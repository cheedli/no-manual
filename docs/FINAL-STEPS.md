# Final steps (need you) — deadline Wed 11 Nov 2026, 22:00 UTC

Everything below is outward-facing or needs your accounts, so it's yours. ~2 h total.

## 1. Telegram check (15 min)
1. In Telegram, send `/new` to @Octaversexhermesbot.
2. Send 2–3 photos of a real flat-pack piece's panels with the caption
   "this was a bookcase, 80 wide 180 tall 30 deep, no manual".
3. Confirm: Hermes calls `nm_add_photos` / `nm_extract_parts` with the photos (S1), and the
   overview + step images arrive as **photos** in the chat (S3).
4. Send a photo of a step done wrong → expect "Stop — …". Then a correct one → next step.
5. If photos don't attach: tell Claude; the `recent: true` fallback is there for that.

## 2. One real piece (30–60 min)
Run any one mode on real furniture and update the last row of the README results table.

## 3. Publish (20 min)
1. Create the public GitHub repo `no-manual` (MIT) and push `main`.
2. Fill `<owner>` in `README.md` (install line) and in `docs/catalog-entry.yaml`.
3. `hermes plugins validate . --install-deps` → green. Note the commit sha.
4. Fork `NousResearch/hermes-agent`, add `plugin-catalog/no-manual.yaml` from
   `docs/catalog-entry.yaml` with `<owner>`, `<sha>`, `maintainer` filled in.
5. Open the PR with `docs/PR-DESCRIPTION.md` as the body.

## 4. Video + form (45 min)
1. Record the < 90 s demo (`docs/11-DEMO-SCRIPT.md`). Wow moment = 3D viewer or the "Stop" check.
2. Post on X tagging @NousResearch (text in doc 11).
3. Submit PR link + X link: http://form.typeform.com/to/FwJLvOln

## Security housekeeping
- The Telegram bot token was pasted in a chat log: `/revoke` it in BotFather after the hackathon.
