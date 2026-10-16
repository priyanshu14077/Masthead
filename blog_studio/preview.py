"""Masthead's own post preview: the draft as a reader would see it, rendered without the blog.

The body is rendered by scripts/render-mdx.mjs, which never runs code from the draft. Everything else
on the page comes from the post's fields, escaped here. Mermaid diagrams are drawn in the browser by
a pinned script, the only resource the page loads besides fonts.
"""

from __future__ import annotations

import html
import subprocess
from typing import Any

from .config import STUDIO_DIR, Site
from .content import ContentError

RENDERER = STUDIO_DIR / "scripts" / "render-mdx.mjs"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
CSP = (
    "default-src 'none'; img-src https: data:; media-src https:; "
    "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    "script-src https://cdn.jsdelivr.net; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"
)


def render_body(body: str) -> str:
    result = subprocess.run(["node", str(RENDERER)], input=body, capture_output=True, text=True, timeout=60, check=False, cwd=RENDERER.parent)
    if result.returncode != 0:
        raise ContentError(f"The draft can't be previewed: {result.stderr.strip() or 'unknown error'}")
    return result.stdout


def page(site: Site, post: dict[str, Any], campaign: dict[str, Any] | None, thumbnail_svg: str | None) -> str:
    e = html.escape
    accent = site.theme.get("accent", "#b4673d")
    series = ""
    if campaign and campaign.get("kind") == "series" and campaign.get("series_name"):
        part = f" · Part {int(post['series_order'])}" if post.get("series_order") else ""
        series = f'<p class="kicker">{e(campaign["series_name"])}{part}</p>'
    tags = "".join(f"<li>#{e(t)}</li>" for t in post.get("tags") or [])
    tldr = "".join(f"<li>{e(t)}</li>" for t in post.get("tldr") or [])
    has_mermaid = 'class="mermaid"' in (body := render_body(post.get("body") or ""))
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="robots" content="noindex" />
<title>Preview · {e(post.get("title") or post.get("idea") or "Post")}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
<style>
:root {{ --accent: {e(accent)}; --ink: #1f2937; --muted: #6b7280; --line: #e5e1d8; --paper: #fbfaf7; --soft: #f3f0e8; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 17px/1.7 Inter, system-ui, sans-serif; }}
.bar {{ position: sticky; top: 0; display: flex; justify-content: space-between; gap: 12px; padding: 10px 20px; background: #0b0b0b; color: #e5e5e5; font: 12.5px/1.4 "JetBrains Mono", monospace; z-index: 2; }}
.bar strong {{ color: #fff; font-weight: 500; }}
main {{ max-width: 720px; margin: 0 auto; padding: 56px 20px 96px; }}
.kicker {{ margin: 0 0 12px; font: 500 13px/1.4 "JetBrains Mono", monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }}
h1 {{ margin: 0; font: 400 clamp(2.2rem, 6vw, 3.4rem)/1.05 "Instrument Serif", Georgia, serif; letter-spacing: -.01em; }}
.subtitle {{ margin: 14px 0 0; font-size: 20px; color: var(--muted); }}
.tags {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 18px 0 0; padding: 0; list-style: none; font: 13px "JetBrains Mono", monospace; color: var(--muted); }}
.thumb {{ margin: 32px 0 0; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); }}
.thumb svg {{ display: block; width: 100%; height: auto; }}
.tldr {{ margin: 32px 0 0; padding: 18px 22px; border-left: 3px solid var(--accent); background: var(--soft); border-radius: 0 8px 8px 0; }}
.tldr p {{ margin: 0 0 6px; font: 600 13px "JetBrains Mono", monospace; text-transform: uppercase; letter-spacing: .08em; }}
.tldr ul {{ margin: 0; padding-left: 20px; }}
article {{ margin-top: 40px; }}
article h2 {{ margin: 2.2em 0 .5em; font: 400 2rem/1.15 "Instrument Serif", Georgia, serif; }}
article h3 {{ margin: 1.8em 0 .4em; font-size: 1.15rem; }}
article a {{ color: var(--accent); }}
article img, article video {{ max-width: 100%; border-radius: 8px; }}
article pre {{ overflow-x: auto; padding: 16px 18px; background: #111; color: #e5e5e5; border-radius: 8px; font: 13.5px/1.6 "JetBrains Mono", monospace; }}
article code {{ font: .88em "JetBrains Mono", monospace; background: var(--soft); padding: .1em .35em; border-radius: 4px; }}
article pre code {{ background: none; padding: 0; }}
article pre.mermaid {{ background: #fff; color: var(--ink); border: 1px solid var(--line); text-align: center; }}
article table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
article th, article td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; }}
article blockquote {{ margin: 1.5em 0; padding-left: 18px; border-left: 3px solid var(--line); color: var(--muted); }}
.callout {{ margin: 1.6em 0; padding: 14px 18px; border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: 8px; background: #fff; }}
.callout p {{ margin: .3em 0; }}
.callout-title, .box-label, .step-title, .tradeoffs-side {{ font-weight: 600; }}
.box {{ margin: 1.6em 0; padding: 14px 18px; background: var(--soft); border-radius: 8px; }}
.box-label {{ margin: 0 0 6px; font: 600 13px "JetBrains Mono", monospace; text-transform: uppercase; letter-spacing: .08em; }}
.steps {{ padding-left: 22px; }} .step {{ margin: .6em 0; }} .step-title {{ margin: 0; }}
figure {{ margin: 1.6em 0; }} figcaption {{ margin-top: 8px; font-size: 14px; color: var(--muted); }}
.mdx-component {{ display: block; margin: 1.2em 0; padding: 10px 14px; border: 1px dashed var(--line); border-radius: 8px; }}
span.mdx-component {{ display: inline; margin: 0; padding: 0 4px; }}
.mdx-component-name {{ display: block; font: 12px "JetBrains Mono", monospace; color: var(--muted); }}
span .mdx-component-name {{ display: inline; margin-right: 4px; }}
.mdx-expression {{ color: var(--muted); }}
.mdx-placeholder {{ padding: 24px; text-align: center; background: var(--soft); border-radius: 8px; color: var(--muted); }}
</style>
</head>
<body>
<div class="bar"><span><strong>Masthead preview</strong> · {e(site.name)}</span><span>{e(post.get("slug") or "no slug yet")}</span></div>
<main>
<header>
{series}
<h1>{e(post.get("title") or post.get("idea") or "Untitled")}</h1>
{f'<p class="subtitle">{e(post["subtitle"])}</p>' if post.get("subtitle") else ""}
{f'<ul class="tags">{tags}</ul>' if tags else ""}
{f'<div class="thumb">{thumbnail_svg}</div>' if thumbnail_svg else ""}
{f'<section class="tldr"><p>TL;DR</p><ul>{tldr}</ul></section>' if tldr else ""}
</header>
<article>
{body}
</article>
</main>
{f'<script src="{MERMAID}"></script>' if has_mermaid else ""}
</body>
</html>"""
