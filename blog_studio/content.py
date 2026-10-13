"""Reading the site's existing posts, building post files, validating MDX, and committing to git."""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .config import Settings

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ContentError(Exception):
    """A problem the author has to fix before the post can be written or published."""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:80].strip("-")


def check_slug(slug: str | None) -> str:
    if not slug or not SLUG_RE.match(slug):
        raise ContentError("The slug must be lowercase words joined by hyphens, like designing-a-cache.")
    return slug


# Existing posts ----------------------------------------------------------
def read_frontmatter(path: Path) -> dict[str, Any]:
    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", path.read_text())
    return yaml.safe_load(match.group(1)) or {} if match else {}


def site_posts(settings: Settings) -> list[dict[str, Any]]:
    posts = []
    for path in sorted(settings.blog_dir.glob("*.mdx")):
        if path.name.startswith("_"):
            continue
        fm = read_frontmatter(path)
        posts.append({
            "file": path.name,
            "slug": fm.get("slug") or path.stem,
            "title": fm.get("title", path.stem),
            "tags": fm.get("tags") or [],
            "series": fm.get("series"),
            "seriesOrder": fm.get("seriesOrder"),
            "draft": bool(fm.get("draft")),
            "date": str(fm.get("date", "")),
        })
    return posts


def known_tags(settings: Settings) -> list[str]:
    return sorted({t for p in site_posts(settings) for t in p["tags"]})


def style_reference(settings: Settings) -> str:
    """One published post, used as the house-style example in the drafting prompt."""
    path = settings.repo_root / settings.site.style_reference if settings.site.style_reference else settings.blog_dir / "-"
    if not path.is_file():
        candidates = [p for p in sorted(settings.blog_dir.glob("*.mdx")) if not p.name.startswith("_")]
        if not candidates:
            return ""
        path = candidates[0]
    return path.read_text()


# Building the file -------------------------------------------------------
def post_paths(settings: Settings, slug: str) -> tuple[Path, Path]:
    return settings.blog_dir / f"{slug}.mdx", settings.thumbs_dir / slug / "thumbnail.svg"


def frontmatter(settings: Settings, post: dict[str, Any], campaign: dict[str, Any] | None, *, draft: bool, on: date) -> str:
    fm: dict[str, Any] = {
        "title": post["title"],
        "subtitle": post.get("subtitle") or None,
        "slug": post["slug"],
        "date": on,
        "tags": post.get("tags") or [],
    }
    if campaign and campaign.get("kind") == "series" and campaign.get("series_name"):
        fm["series"] = campaign["series_name"]
        if post.get("series_order"):
            fm["seriesOrder"] = int(post["series_order"])
    if post.get("thumb_spec"):
        fm["thumbnail"] = settings.site.thumbnail_url.replace("{slug}", post["slug"])
    fm["summary"] = post.get("summary") or ""
    if post.get("tldr"):
        fm["tldr"] = post["tldr"]
    fm["draft"] = draft
    fm = {k: v for k, v in fm.items() if v is not None}
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{dumped}---\n\n"


def unknown_components(settings: Settings, body: str) -> list[str]:
    used = set(re.findall(r"<([A-Z][A-Za-z0-9]*)", body))
    return sorted(used - set(settings.site.components))


def validate_mdx(settings: Settings, source: str) -> None:
    bad = unknown_components(settings, source)
    if bad:
        raise ContentError(f"The draft uses components the site doesn't have: {', '.join(bad)}.")
    result = subprocess.run(
        ["node", str(settings.validator)], input=source, capture_output=True, text=True, timeout=60,
        cwd=settings.validator.parent,
    )
    if result.returncode != 0:
        raise ContentError(f"The draft isn't valid MDX: {result.stderr.strip() or 'unknown error'}")


def write_post(settings: Settings, post: dict[str, Any], campaign: dict[str, Any] | None, svg: str | None, *, draft: bool, on: date) -> list[Path]:
    """Writes the post (and its thumbnail) into the site. Returns the paths written."""
    slug = check_slug(post.get("slug"))
    if not post.get("title") or not post.get("body"):
        raise ContentError("The post needs a title and a draft body before it can be written.")
    mdx_path, svg_path = post_paths(settings, slug)

    # Never overwrite a post the Studio didn't create.
    for existing in site_posts(settings):
        if existing["slug"] == slug and existing["file"] != mdx_path.name:
            raise ContentError(f"Another post already uses the slug '{slug}'.")
    if mdx_path.exists() and not post.get("written"):
        raise ContentError(f"{mdx_path.relative_to(settings.repo_root)} already exists and wasn't written by the Studio.")

    source = frontmatter(settings, post, campaign, draft=draft, on=on) + post["body"].strip() + "\n"
    validate_mdx(settings, source)

    mdx_path.parent.mkdir(parents=True, exist_ok=True)
    mdx_path.write_text(source)
    written = [mdx_path]
    if svg:
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg)
        written.append(svg_path)
    return written


# Git ---------------------------------------------------------------------
def git(settings: Settings, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=settings.repo_root, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ContentError(f"git {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def current_branch(settings: Settings) -> str:
    try:
        return git(settings, "branch", "--show-current")
    except ContentError:
        return ""


def commit(settings: Settings, paths: list[Path], message: str) -> str:
    """Commits exactly these paths, leaving anything else staged or modified alone. Never pushes."""
    branch = current_branch(settings)
    if not branch:
        raise ContentError("The repository isn't on a branch, so nothing was committed.")
    if branch in settings.site.protected_branches:
        raise ContentError(f"You're on {branch}, which deploys the live site. Switch to a working branch first.")
    rel = [str(p.relative_to(settings.repo_root)) for p in paths]
    git(settings, "add", "--", *rel)
    git(settings, "commit", "-m", message, "--only", "--", *rel)
    return git(settings, "rev-parse", "--short", "HEAD")
