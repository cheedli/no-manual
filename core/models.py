"""Project state. One dataclass, nested data as plain dicts (keys documented in docs/02 §3).

ponytail: nested items stay dicts so the whole project round-trips through JSON in one
sqlite column; promote one to a dataclass only when code starts poking at its fields a lot.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Optional

SCHEMA_VERSION = 1


def new_id() -> str:
    return uuid.uuid4().hex[:6]


@dataclass
class Project:
    id: str = field(default_factory=new_id)
    title: str = ""
    category: str = "other"
    mode: str = "unknown"            # unknown | manual | recorder | solver
    state: str = "intake"            # intake | identifying | recording | extracting | solved | coaching | done | blocked
    assembled: str = "unknown"       # assembled | in_pieces | unknown
    outer_dims_mm: Optional[dict] = None   # {"w","h","d"}
    safety_status: str = "ok"        # ok | blocked_child_or_load
    safety_reason: str = ""
    photos: list = field(default_factory=list)    # {id, path, kind, sha256, added_at, caption}
    stages: list = field(default_factory=list)    # recorder: {index, photo_ids, user_text, described}
    parts: list = field(default_factory=list)
    hardware: list = field(default_factory=list)
    plan: Optional[dict] = None      # {source, confidence, steps:[...], warnings:[...]}
    current_step: int = 1
    notes: list = field(default_factory=list)
    identity: Optional[dict] = None  # nm_identify result
    manual_source: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def blocked(self) -> bool:
        return self.safety_status != "ok"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Project":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    def summary(self) -> dict[str, Any]:
        steps = len((self.plan or {}).get("steps", []))
        return {"project_id": self.id, "title": self.title, "category": self.category,
                "mode": self.mode, "state": self.state, "safety_status": self.safety_status,
                "photos": len(self.photos), "stages": len(self.stages),
                "step": f"{min(self.current_step, steps)}/{steps}" if steps else None,
                "updated_at": self.updated_at}
