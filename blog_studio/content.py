"""Posts as files: reading what a blog already has, building a new post's files, validating MDX.

Where the files go is the publisher's job (publisher.py): a local git repo, or a GitHub pull request.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from typing import Any

import yaml

from .config import STUDIO_DIR, Site

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VALIDATOR = STUDIO_DIR / "scripts" / "validate-mdx.mjs"


class ContentError(Exception):
    """A problem the author has to fix before the post can be written or published."""


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:80].strip("-")


def check_slug(slug: str | None) -> str:
    if not slug or not SLUG_RE.match(slug):
        raise ContentError("The slug must be lowercase words joined by hyphens, like designing-a-cache.")
    return slug


# What the blog already has ---------------------------------------------------
def parse_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", text)
    return (yaml.safe_load(match.group(1)) or {}) if match else {}


def summarise(name: str, text: str) -> dict[str, Any]:
    fm = parse_frontmatter(text)
    return {
        "file": name,
        "slug": fm.get("slug") or name.rsplit(".", 1)[0],
        "title": fm.get("title", name),
        "tags": fm.get("tags") or [],
        "series": fm.get("series"),
        "seriesOrder": fm.get("seriesOrder"),
        "draft": bool(fm.get("draft")),
        "date": str(fm.get("date", "")),
    }


def site_posts(site: Site) -> list[dict[str, Any]]:
    if site.remote:
        return list(site.known_posts)
    if not site.blog_dir.is_dir():
        return []
    return [summarise(p.name, p.read_text()) for p in sorted(site.blog_dir.glob("*.mdx")) if not p.name.startswith("_")]


def known_tags(site: Site) -> list[str]:
    return sorted({t for p in site_posts(site) for t in p["tags"]})


def style_reference(site: Site) -> str:
    """A published post, used as the house-style example in the drafting prompt."""
    if site.style_reference_text:
        return site.style_reference_text
    if site.remote:
        return ""
    if site.style_reference and (site.root / site.style_reference).is_file():
        return (site.root / site.style_reference).read_text()
    candidates = [p for p in sorted(site.blog_dir.glob("*.mdx")) if not p.name.startswith("_")] if site.blog_dir.is_dir() else []
    return candidates[0].read_text() if candidates else ""


# Building a post's files -------------------------------------------------------
def post_paths(site: Site, slug: str) -> tuple[str, str]:
    """Repo-relative paths of the post and its thumbnail."""
    return f"{site.posts_dir}/{slug}.mdx", f"{site.thumbnails_dir}/{slug}/thumbnail.svg"


def frontmatter(site: Site, post: dict[str, Any], campaign: dict[str, Any] | None, *, draft: bool, on: date) -> str:
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
        fm["thumbnail"] = site.thumbnail_url.replace("{slug}", post["slug"])
    fm["summary"] = post.get("summary") or ""
    if post.get("tldr"):
        fm["tldr"] = post["tldr"]
    fm["draft"] = draft
    fm = {k: v for k, v in fm.items() if v is not None}
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=10_000)
    return f"---\n{dumped}---\n\n"


def unknown_components(site: Site, body: str) -> list[str]:
    used = set(re.findall(r"<([A-Z][A-Za-z0-9]*)", body))
    return sorted(used - set(site.components))


def validate_mdx(site: Site, source: str) -> None:
    bad = unknown_components(site, source)
    if bad:
        raise ContentError(f"The draft uses components the site doesn't have: {', '.join(bad)}.")
    result = subprocess.run(["node", str(VALIDATOR)], input=source, capture_output=True, text=True, timeout=60, check=False, cwd=VALIDATOR.parent)
    if result.returncode != 0:
        raise ContentError(f"The draft isn't valid MDX: {result.stderr.strip() or 'unknown error'}")


def build_files(site: Site, post: dict[str, Any], campaign: dict[str, Any] | None, svg: str | None, *, draft: bool, on: date) -> dict[str, str]:
    """The files that make up this post, keyed by repo-relative path. Validates before returning."""
    slug = check_slug(post.get("slug"))
    if not post.get("title") or not post.get("body"):
        raise ContentError("The post needs a title and a draft body before it can be written.")
    mdx_path, svg_path = post_paths(site, slug)
    for existing in site_posts(site):
        if existing["slug"] == slug and existing["file"] != f"{slug}.mdx":
            raise ContentError(f"Another post already uses the slug '{slug}'.")
        if existing["file"] == f"{slug}.mdx" and not post.get("written"):
            raise ContentError(f"{mdx_path} already exists and wasn't written by Masthead.")
    source = frontmatter(site, post, campaign, draft=draft, on=on) + post["body"].strip() + "\n"
    validate_mdx(site, source)
    files = {mdx_path: source}
    if svg:
        files[svg_path] = svg
    return files
