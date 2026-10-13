"""SQLite storage for campaigns, posts and an AI usage log. Lists and objects are stored as JSON text."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'series',          -- series | launch | theme
  description TEXT NOT NULL DEFAULT '',
  series_name TEXT,                              -- written to post frontmatter when kind = series
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'idea',           -- idea | outlined | drafted | checked | scheduled | published
  idea TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  allowed_names TEXT NOT NULL DEFAULT '[]',      -- company or product names allowed to appear
  outline TEXT,                                  -- JSON
  title TEXT, slug TEXT, subtitle TEXT, summary TEXT,
  tags TEXT NOT NULL DEFAULT '[]',
  tldr TEXT NOT NULL DEFAULT '[]',
  series_order INTEGER,
  body TEXT,
  check_result TEXT,                             -- JSON
  check_ack INTEGER NOT NULL DEFAULT 0,          -- 1 when the author accepted the remaining findings
  thumb_spec TEXT,                               -- JSON
  social TEXT,                                   -- JSON
  publish_at TEXT,                               -- ISO date
  published_at TEXT,
  commit_sha TEXT,
  written INTEGER NOT NULL DEFAULT 0,            -- 1 once the Studio has written this post into content/blog
  last_error TEXT,                               -- the scheduler's last failure, shown on the card
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_calls (
  id INTEGER PRIMARY KEY,
  post_id INTEGER,
  task TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  at TEXT NOT NULL
);
"""

JSON_FIELDS = {"allowed_names", "outline", "tags", "tldr", "check_result", "thumb_spec", "social"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    # Rows ----------------------------------------------------------------
    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        for key in JSON_FIELDS & out.keys():
            if out[key] is not None:
                out[key] = json.loads(out[key])
        return out

    @staticmethod
    def _encode(fields: dict[str, Any]) -> dict[str, Any]:
        return {k: (json.dumps(v) if k in JSON_FIELDS and v is not None else v) for k, v in fields.items()}

    # Campaigns -----------------------------------------------------------
    def campaigns(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM posts p WHERE p.campaign_id = c.id) AS post_count FROM campaigns c ORDER BY c.id"
        ).fetchall()
        return [dict(r) for r in rows]

    def campaign(self, cid: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone()
        return dict(row) if row else None

    def create_campaign(self, name: str, kind: str, description: str, series_name: str | None) -> dict[str, Any]:
        cur = self.conn.execute(
            "INSERT INTO campaigns (name, kind, description, series_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, kind, description, series_name, now()),
        )
        return self.campaign(cur.lastrowid)  # type: ignore[return-value]

    def update_campaign(self, cid: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {k: v for k, v in fields.items() if k in {"name", "kind", "description", "series_name"}}
        if allowed:
            sets = ", ".join(f"{k} = ?" for k in allowed)
            self.conn.execute(f"UPDATE campaigns SET {sets} WHERE id = ?", (*allowed.values(), cid))
        return self.campaign(cid)

    def delete_campaign(self, cid: int) -> None:
        self.conn.execute("DELETE FROM campaigns WHERE id = ?", (cid,))

    # Posts ---------------------------------------------------------------
    def posts(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM posts ORDER BY COALESCE(publish_at, '9999'), id").fetchall()
        return [self._decode(r) for r in rows]  # type: ignore[misc]

    def post(self, pid: int) -> dict[str, Any] | None:
        return self._decode(self.conn.execute("SELECT * FROM posts WHERE id = ?", (pid,)).fetchone())

    def create_post(self, idea: str, notes: str, campaign_id: int | None, allowed_names: list[str]) -> dict[str, Any]:
        ts = now()
        cur = self.conn.execute(
            "INSERT INTO posts (idea, notes, campaign_id, allowed_names, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (idea, notes, campaign_id, json.dumps(allowed_names), ts, ts),
        )
        return self.post(cur.lastrowid)  # type: ignore[return-value]

    def update_post(self, pid: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        if fields:
            enc = self._encode(fields)
            enc["updated_at"] = now()
            sets = ", ".join(f"{k} = ?" for k in enc)
            self.conn.execute(f"UPDATE posts SET {sets} WHERE id = ?", (*enc.values(), pid))
        return self.post(pid)

    def delete_post(self, pid: int) -> None:
        self.conn.execute("DELETE FROM posts WHERE id = ?", (pid,))

    def due_posts(self, today: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' AND publish_at IS NOT NULL AND publish_at <= ?", (today,)
        ).fetchall()
        return [self._decode(r) for r in rows]  # type: ignore[misc]

    # Usage ---------------------------------------------------------------
    def log_call(self, post_id: int | None, task: str, model: str, usage: dict[str, int], cost: float) -> None:
        self.conn.execute(
            "INSERT INTO ai_calls (post_id, task, model, input_tokens, output_tokens, cache_read_tokens, cost_usd, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (post_id, task, model, usage.get("input", 0), usage.get("output", 0), usage.get("cache_read", 0), cost, now()),
        )

    def spend(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT COALESCE(SUM(cost_usd), 0), COUNT(*) FROM ai_calls").fetchone()
        month = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_calls WHERE at >= ?", (now()[:7] + "-01",)
        ).fetchone()
        return {"total_usd": round(total[0], 4), "calls": total[1], "month_usd": round(month[0], 4)}

    def post_spend(self, pid: int) -> float:
        return round(self.conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM ai_calls WHERE post_id = ?", (pid,)).fetchone()[0], 4)
