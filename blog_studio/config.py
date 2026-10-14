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
    # Hosted sites live in a GitHub repo, not on this disk; these are read from the repo when it's synced.
    remote: bool = False
    known_posts: list[dict] = field(default_factory=list)
    style_reference_text: str = ""

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


def parse_config(raw: dict, root: Path, read) -> dict:  # type: ignore[no-untyped-def]
    """The Site fields from a parsed blog-studio.toml. `read` loads a prompt file by relative path."""
    paths = raw.get("paths", {})
    prompts = raw.get("prompts", {})
    return dict(
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


def site_from_snapshot(snapshot: dict, name: str) -> Site:
    """A hosted site, rebuilt from the config snapshot stored when its repo was synced."""
    fields = {k: v for k, v in snapshot.items() if k in Site.__dataclass_fields__ and k not in {"root"}}
    fields.setdefault("name", name)
    return Site(root=Path("/remote") / snapshot.get("repo", name), remote=True, **fields)


def load_site(root: Path | None = None, config: Path | None = None) -> Site:
    """A local blog. Its settings sit in the blog's repo (`root/blog-studio.toml`), or in a file kept
    outside it (`config`), so the blog's repository needs no Masthead files at all.

    An outside config names the repo with `repo = "path"`, relative to the config file, unless `root` is given.
    Prompt files are read relative to the config file in both cases.
    """
    if config is not None:
        path = config.resolve()
        if not path.is_file():
            raise ConfigError(f"No settings file at {path}.")
    elif root is not None:
        path = root.resolve() / CONFIG_NAME
        if not path.is_file():
            raise ConfigError(f"No {CONFIG_NAME} in {root.resolve()}. Run `blog-studio init --site {root}` to create one, or pass --config.")
    else:
        raise ConfigError("Tell Masthead which blog to open: --config FILE or --site PATH.")
    base = path.parent
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    if root is None:
        if not raw.get("repo"):
            raise ConfigError(f"{path} needs `repo = \"path/to/the/blog\"`, relative to the file.")
        root = base / raw["repo"]
    root = root.resolve()
    if not root.is_dir():
        raise ConfigError(f"The blog repository {root} doesn't exist.")

    def read(rel: str | None) -> str:
        if not rel:
            return ""
        f = base / rel
        if not f.is_file():
            raise ConfigError(f"{path.name} points to {rel}, which doesn't exist.")
        return f.read_text()

    return Site(root=root, **parse_config(raw, root, read))


@dataclass(frozen=True)
class Settings:
    """`local`: one person, one blog on this machine (no sign-in). `cloud`: the hosted, multi-tenant app."""

    mode: str
    db_url: str
    port: int
    fake_ai: bool
    base_url: str  # where the app is served; used for OAuth redirects, Stripe return URLs and the host check
    site: Site | None = None  # local mode's blog

    @property
    def cloud(self) -> bool:
        return self.mode == "cloud"

    @property
    def db_path(self) -> Path | None:
        return Path(self.db_url.split("///", 1)[1]) if self.db_url.startswith("sqlite:///") else None


def _env_path(name: str) -> Path | None:
    """A path from .env, relative to the Masthead folder that holds the .env file."""
    value = os.environ.get(name)
    return (STUDIO_DIR / value) if value else None


def get_settings(site_root: str | Path | None = None, config: str | Path | None = None) -> Settings:
    load_dotenv(STUDIO_DIR / ".env")
    mode = os.environ.get("MASTHEAD_MODE", "local")
    port = int(os.environ.get("STUDIO_PORT") or os.environ.get("PORT") or "8787")  # PORT is what most hosts set
    base_url = os.environ.get("MASTHEAD_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    data_dir = Path(os.environ.get("STUDIO_DATA_DIR", STUDIO_DIR / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    site = None
    if mode == "local":
        cfg = Path(config) if config else (None if site_root else _env_path("BLOG_STUDIO_CONFIG"))
        root = Path(site_root) if site_root else (None if cfg else _env_path("BLOG_STUDIO_SITE"))
        if not cfg and not root:
            raise ConfigError("Tell Masthead which blog to open: --config FILE or --site PATH, or set BLOG_STUDIO_CONFIG in .env.")
        site = load_site(root, cfg)
        default_db = f"sqlite:///{data_dir / f'{site.slug}.db'}"  # one database per blog
    elif mode == "cloud":
        default_db = f"sqlite:///{data_dir / 'masthead.db'}"
    else:
        raise ConfigError("MASTHEAD_MODE must be local or cloud.")
    return Settings(
        mode=mode,
        db_url=os.environ.get("DATABASE_URL", default_db),
        port=port,
        fake_ai=os.environ.get("STUDIO_FAKE_AI", "0") == "1",
        base_url=base_url,
        site=site,
    )
