"""Paths and settings. Everything is resolved relative to the portfolio app folder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines, existing environment wins."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and key.strip() not in os.environ:
            os.environ[key.strip()] = value


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    db_path: Path
    port: int
    site_url: str
    fake_ai: bool

    @property
    def blog_dir(self) -> Path:
        return self.repo_root / "content" / "blog"

    @property
    def thumbs_dir(self) -> Path:
        return self.repo_root / "public" / "blog"

    @property
    def validator(self) -> Path:
        return STUDIO_DIR / "scripts" / "validate-mdx.mjs"


def get_settings() -> Settings:
    load_dotenv(STUDIO_DIR / ".env")
    repo_root = Path(os.environ.get("STUDIO_REPO_ROOT", STUDIO_DIR.parent)).resolve()
    data_dir = Path(os.environ.get("STUDIO_DATA_DIR", STUDIO_DIR / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        repo_root=repo_root,
        db_path=data_dir / "studio.db",
        port=int(os.environ.get("STUDIO_PORT", "8787")),
        site_url=os.environ.get("SITE_URL", "https://priyanshukumarsingh.vercel.app").rstrip("/"),
        fake_ai=os.environ.get("STUDIO_FAKE_AI", "0") == "1",
    )
