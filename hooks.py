"""Hooks: skill hint (pre_llm_call) and safety guard (pre_tool_call)."""
from __future__ import annotations

import logging

from . import tools
from .core import hint, safety

log = logging.getLogger(__name__)


def inject_hint(user_message=None, **kwargs):
    try:
        return hint.HINT if hint.looks_like_furniture_request(user_message) else None
    except Exception:
        return None


def safety_guard(tool_name=None, args=None, **kwargs):
    """Second enforcement layer (handlers check too). Fails closed on a blocked project."""
    if tool_name not in safety.GENERATING_TOOLS:
        return None
    try:
        pid = (args or {}).get("project_id")
        p = tools.get_store().get(pid) if pid else None
    except Exception as e:
        log.warning("safety_guard could not load project: %s", e)
        return None  # the handler re-checks and refuses on its own
    if p and p.blocked:
        return {"action": "block", "message": safety.BLOCK_MESSAGE}
    return None
