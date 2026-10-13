import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blog_studio.ai import FakeAI
from blog_studio.config import DEFAULT_COMPONENTS, Settings, load_site
from blog_studio.server import create_app

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
    (root / "blog-studio.toml").write_text(
        'name = "Test blog"\n'
        'site_url = "https://example.test"\n'
        'preview_url = "http://localhost:5173/blog/{slug}"\n'
        '[paths]\nstyle_reference = "content/blog/designing-a-url-shortener.mdx"\n'
        f"[mdx]\ncomponents = {DEFAULT_COMPONENTS!r}\n".replace("'", '"')
    )
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.email", "studio@test.local")
    git(root, "config", "user.name", "Studio Test")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def client(repo: Path, tmp_path: Path):
    os.environ["STUDIO_SCHEDULER"] = "0"
    settings = Settings(site=load_site(repo), db_path=tmp_path / "studio.db", port=8787, fake_ai=True)
    app = create_app(settings, ai=FakeAI())
    with TestClient(app) as c:
        c.app_ref = app  # type: ignore[attr-defined]
        yield c
