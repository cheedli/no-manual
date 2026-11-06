# Testing — No Manual

Reliability is a judging axis. Tests protect the demo.

## 1. Layers
| Layer | Tool | Scope |
|-------|------|-------|
| Unit | `pytest` | everything in `core/` (no Hermes needed) |
| Contract | `pytest` with a fake `ctx` | tool handlers: JSON-string returns, never raise, error shapes |
| Plugin | `hermes plugins doctor . --ci`, `hermes plugins validate . --install-deps` | manifest, registration, declared tools/hooks, scanner, desktop rules |
| E2E | Hermes CLI + Telegram | real photos, real model, real furniture |

## 2. Fake ctx for contract tests
`tests/fakes.py`:
```python
class FakeLlm:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def complete_structured(self, **kw):
        self.calls.append(kw)
        parsed = self.responses.pop(0)
        return type("R", (), {"parsed": parsed, "text": json.dumps(parsed),
                              "content_type": "json"})()
class FakeCtx:
    def __init__(self, llm): self.llm = llm; self.tools = {}; self.hooks = {}
    def register_tool(self, name, toolset, schema, handler, **kw): self.tools[name] = handler
    def register_hook(self, name, cb): self.hooks[name] = cb
    def register_skill(self, *a, **k): pass
    def register_command(self, *a, **k): pass
    def get_config(self, key, default=None): return default
```
Inject a temp sqlite connection and temp data dir into `core/store.py` (the
handlers must not import `plugins.plugin_storage` at module level — import
inside a factory so tests can substitute).

## 3. Must-have unit tests
- `test_store.py` — create/load/update project; persistence across connections.
- `test_safety.py` — every blocked category; vision re-classification; guard directive shape.
- `test_units.py` — cm/in → mm; bounds.
- `test_photos.py` — dedupe by hash; reject non-images and > 20 MB.
- `test_recorder.py` — reversal order; empty-stage handling.
- `test_manual.py` — local PDF → N PNGs; URL validation (https, type, size) with a mocked fetcher.
- `test_classify.py` — role assignment on fixtures; tolerance edges.
- `test_solver.py` — expected step titles per fixture; anti-tip present when H ≥ 750; ambiguous fixture → questions & conf < 0.6.
- `test_hardware.py` — matching and mismatch messages.
- `test_render.py` — PNG size/mode; golden images (pixel diff < 2%); 12 steps < 10 s.
- `test_scene.py` — schema validation; transforms within outer dims.
- `test_check_step.py` — stop/warn/ok logic with FakeLlm.
- `test_hint.py` — keyword matcher positives/negatives (EN/FR/AR/ES).
- `test_tools_contract.py` — every tool returns a JSON string, including on bad input; never raises.

## 4. E2E script (run before every rehearsal)
1. New chat on Telegram: "I took my bookcase apart and lost the manual" + photos.
2. Expect: project created, asks assembled/in pieces (or infers), asks for outer dims.
3. Provide dims → extraction → ≤ 4 questions → answers → solve → overview image + step 1.
4. Send correct photo for step 1 → advance. Send wrong photo for step 3 → "stop" with a fix.
5. "Show me the whole thing" in Desktop → 3D viewer with steps.
6. New session: "continue my bookcase" → resumes at the right step.
7. Crib test: "help me assemble this crib" → manual-only path, polite refusal of generated steps.

## 5. Results table (publish in README)
| Piece | Mode | Outcome | Notes |
|-------|------|---------|-------|
| e.g. Bookcase 80×180 (no brand) | solver | ✅ correct order, 1 question | |
| e.g. Branded wardrobe | manual | ✅ official PDF found | |
| e.g. Nightstand | recorder | ✅ 7 steps | |
| e.g. Desk with drawers | solver | ❌ out of scope (drawers) — fell back to recorder | honest failure |
