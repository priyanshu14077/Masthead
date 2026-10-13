"""Settings. Blog Studio's own settings come from its .env; everything about a blog comes from the
blog's `blog-studio.toml`, so one Studio can work on any static blog."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

STUDIO_DIR = Path(__file__).resolve().parent.parent
CONFIG_NAME = "blog-studio.toml"

DEFAULT_COMPONENTS = ["Callout", "Figure", "Mermaid", "Steps", "Step", "Tradeoffs", "TLDR", "Takeaways", "References", "Video"]

# Thumbnail palette: background, box, text, light box, accent, secondary.
DEFAULT_THEME = {
    "background": "#14213a",
    "box": "#24375a",
    "text": "#f2ede2",
    "box_light": "#e6dfcf",
    "accent": "#b4673d",
    "secondary": "#a9c1d6",
}


class ConfigError(Exception):
    """The blog's configuration is missing or invalid."""


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
class Site:
    """One blog the Studio writes into, read from its blog-studio.toml."""

    root: Path
    name: str
    author: str = ""
    site_url: str = ""
    preview_url: str = ""  # e.g. http://localhost:5173/blog/{slug}
    posts_dir: str = "content/blog"
    thumbnails_dir: str = "public/blog"  # a thumbnail goes to <thumbnails_dir>/<slug>/thumbnail.svg
    thumbnail_url: str = "/blog/{slug}/thumbnail.svg"  # how posts reference it
    style_reference: str = ""  # a published post the writer should match
    voice: str = ""  # house style for every prompt, from a Markdown file
    components_guide: str = ""  # how to use the blog's MDX components, from a Markdown file
    components: list[str] = field(default_factory=lambda: list(DEFAULT_COMPONENTS))
    protected_branches: list[str] = field(default_factory=lambda: ["main", "master"])
    theme: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_THEME))

    @property
    def blog_dir(self) -> Path:
        return self.root / self.posts_dir

    @property
    def thumbs_dir(self) -> Path:
        return self.root / self.thumbnails_dir

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-") or "blog"

    def preview(self, slug: str) -> str | None:
        return self.preview_url.replace("{slug}", slug) if self.preview_url else None

    def public(self, slug: str) -> str | None:
        return f"{self.site_url.rstrip('/')}/{self.posts_route}/{slug}" if self.site_url else None

    @property
    def posts_route(self) -> str:
        # The public path segment for posts, taken from the thumbnail URL's first segment ("/blog/...").
        return self.thumbnail_url.strip("/").split("/")[0] or "blog"


def load_site(root: Path) -> Site:
    root = root.resolve()
    path = root / CONFIG_NAME
    if not path.is_file():
        raise ConfigError(f"No {CONFIG_NAME} in {root}. Run `blog-studio init --site {root}` to create one.")
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e

    paths = raw.get("paths", {})
    prompts = raw.get("prompts", {})

    def read(rel: str | None) -> str:
        if not rel:
            return ""
        f = root / rel
        if not f.is_file():
            raise ConfigError(f"{CONFIG_NAME} points to {rel}, which doesn't exist.")
        return f.read_text()

    return Site(
        root=root,
        name=raw.get("name") or root.name,
        author=raw.get("author", ""),
        site_url=raw.get("site_url", "").rstrip("/"),
        preview_url=raw.get("preview_url", ""),
        posts_dir=paths.get("posts", "content/blog"),
        thumbnails_dir=paths.get("thumbnails", "public/blog"),
        thumbnail_url=paths.get("thumbnail_url", "/blog/{slug}/thumbnail.svg"),
        style_reference=paths.get("style_reference", ""),
        voice=read(prompts.get("voice")),
        components_guide=read(prompts.get("components")),
        components=raw.get("mdx", {}).get("components", list(DEFAULT_COMPONENTS)),
        protected_branches=raw.get("git", {}).get("protected_branches", ["main", "master"]),
        theme={**DEFAULT_THEME, **raw.get("theme", {})},
    )


@dataclass(frozen=True)
class Settings:
    site: Site
    db_path: Path
    port: int
    fake_ai: bool

    # Short aliases used across the code.
    @property
    def repo_root(self) -> Path:
        return self.site.root

    @property
    def blog_dir(self) -> Path:
        return self.site.blog_dir

    @property
    def thumbs_dir(self) -> Path:
        return self.site.thumbs_dir

    @property
    def site_url(self) -> str:
        return self.site.site_url

    @property
    def validator(self) -> Path:
        return STUDIO_DIR / "scripts" / "validate-mdx.mjs"


def get_settings(site_root: str | Path | None = None) -> Settings:
    load_dotenv(STUDIO_DIR / ".env")
    root = site_root or os.environ.get("BLOG_STUDIO_SITE")
    if not root:
        raise ConfigError("Tell the Studio which blog to open: `blog-studio --site PATH`, or set BLOG_STUDIO_SITE in .env.")
    site = load_site(Path(root))
    data_dir = Path(os.environ.get("STUDIO_DATA_DIR", STUDIO_DIR / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        site=site,
        db_path=data_dir / f"{site.slug}.db",  # one database per blog
        port=int(os.environ.get("STUDIO_PORT", "8787")),
        fake_ai=os.environ.get("STUDIO_FAKE_AI", "0") == "1",
    )
