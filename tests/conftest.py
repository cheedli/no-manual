"""Load the plugin package under the name `no_manual` (the repo folder name isn't importable)."""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # `import core...` for pure tests

if "no_manual" not in sys.modules:
    spec = importlib.util.spec_from_file_location("no_manual", ROOT / "__init__.py",
                                                  submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["no_manual"] = mod
    spec.loader.exec_module(mod)


class FakeLlm:
    def __init__(self, responses=()):
        self.responses, self.calls = list(responses), []

    def complete_structured(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return type("R", (), {"parsed": r, "text": json.dumps(r), "content_type": "json"})()


class FakeCtx:
    def __init__(self, llm=None):
        self.llm = llm or FakeLlm()
        self.tools, self.hooks, self.skills, self.commands = {}, {}, {}, {}

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = handler

    def register_hook(self, name, cb, **kw):
        self.hooks[name] = cb

    def register_skill(self, name, path, **kw):
        self.skills[name] = path

    def register_command(self, name, handler, **kw):
        self.commands[name] = handler

    def get_config(self, key, default=None):
        return default


@pytest.fixture
def plugin(tmp_path):
    """Registered plugin with a temp store. Returns (ctx, call) where call(tool, **args) -> dict."""
    from no_manual import register, tools
    from no_manual.core.store import Store
    tools._store = Store(sqlite3.connect(tmp_path / "data.db"), tmp_path / "data")
    tools._hermes_home = tmp_path / "home"
    ctx = FakeCtx()
    register(ctx)

    def call(name, **args):
        out = ctx.tools[name](args)
        assert isinstance(out, str)
        return json.loads(out)
    yield ctx, call
    tools._store = None
    tools._hermes_home = None


def make_jpeg(path: Path, color=(200, 50, 50), size=(64, 48)) -> Path:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG")
    return path
