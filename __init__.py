"""No Manual: Hermes plugin registration."""
from pathlib import Path


def register(ctx):
    # Imported here so pytest can collect this root package without a parent package.
    from . import hooks, tools

    for name, schema, fn in tools.TOOLS:
        ctx.register_tool(name=name, toolset="no-manual", schema=schema, handler=tools.bind(fn, ctx))
    ctx.register_hook("pre_llm_call", hooks.inject_hint)
    ctx.register_hook("pre_tool_call", hooks.safety_guard)
    ctx.register_skill("no-manual-guide", Path(__file__).parent / "skills" / "no-manual-guide" / "SKILL.md")
    ctx.register_command("nomanual", tools.slash,
                         description="No Manual: list, resume or delete furniture projects")
