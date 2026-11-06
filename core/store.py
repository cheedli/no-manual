"""Persistence: one sqlite table (JSON blob per project) + a files dir per project.

The connection and data root are injected, so tests use a temp dir and the plugin uses
plugin_db("no-manual") / plugin_data_dir("no-manual").
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import SCHEMA_VERSION, Project


class Store:
    def __init__(self, conn: sqlite3.Connection, root: Path):
        self.conn = conn
        self.root = Path(root)
        self.conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, updated_at REAL, data TEXT)")
        self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        self.conn.commit()

    def project_dir(self, project_id: str) -> Path:
        d = self.root / "projects" / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, p: Project) -> Project:
        p.updated_at = time.time()
        self.conn.execute("INSERT OR REPLACE INTO projects VALUES (?, ?, ?)",
                          (p.id, p.updated_at, json.dumps(p.to_dict())))
        self.conn.commit()
        self.project_dir(p.id)
        return p

    def get(self, project_id: str) -> Optional[Project]:
        row = self.conn.execute("SELECT data FROM projects WHERE id = ?", (project_id,)).fetchone()
        return Project.from_dict(json.loads(row[0])) if row else None

    def list(self) -> list[Project]:
        rows = self.conn.execute("SELECT data FROM projects ORDER BY updated_at DESC").fetchall()
        return [Project.from_dict(json.loads(r[0])) for r in rows]

    def delete(self, project_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()
        shutil.rmtree(self.root / "projects" / project_id, ignore_errors=True)
        return cur.rowcount > 0
