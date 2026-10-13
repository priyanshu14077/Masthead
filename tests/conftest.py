import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio.ai import FakeAI
from studio.config import Settings
from studio.server import create_app

EXISTING = """---
title: "Designing a URL shortener"
slug: designing-a-url-shortener
date: 2026-10-06
tags: [system-design, databases]
summary: "An existing post."
draft: false
---

## The problem

Existing body.
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "site"
    (root / "content" / "blog").mkdir(parents=True)
    (root / "public" / "blog").mkdir(parents=True)
    (root / "content" / "blog" / "designing-a-url-shortener.mdx").write_text(EXISTING)
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.email", "studio@test.local")
    git(root, "config", "user.name", "Studio Test")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def client(repo: Path, tmp_path: Path):
    os.environ["STUDIO_SCHEDULER"] = "0"
    settings = Settings(repo_root=repo, db_path=tmp_path / "studio.db", port=8787, site_url="https://example.test", fake_ai=True)
    app = create_app(settings, ai=FakeAI())
    with TestClient(app) as c:
        c.app_ref = app  # type: ignore[attr-defined]
        yield c
