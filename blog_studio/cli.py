"""Command line: `blog-studio --site PATH` serves the Studio for one blog; `blog-studio init --site PATH` sets a blog up."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import CONFIG_NAME, ConfigError, get_settings

STARTER_CONFIG = """\
# Blog Studio settings for this blog. Paths are relative to this file.
name = "{name}"
author = ""
site_url = ""                                   # public origin, e.g. https://example.com
preview_url = "http://localhost:5173/blog/{{slug}}"  # where your dev server shows a post

[paths]
posts = "content/blog"                          # where .mdx posts live
thumbnails = "public/blog"                      # thumbnails go to <thumbnails>/<slug>/thumbnail.svg
thumbnail_url = "/blog/{{slug}}/thumbnail.svg"   # how a post's frontmatter refers to it
style_reference = ""                            # a published post the writer should match

[prompts]
voice = ".blog-studio/voice.md"                 # house style for every prompt
components = ".blog-studio/components.md"       # how to use your MDX components

[mdx]
components = []                                 # component names your posts may use, e.g. ["Callout"]

[git]
protected_branches = ["main", "master"]         # never commit to these

[theme]                                         # thumbnail palette; omit to use the defaults
"""

STARTER_VOICE = """\
You write for an engineering blog. Readers are working engineers.
Short sentences with one idea each. Active voice. Explain the trade-offs.
Use only figures from the author's notes; never invent metrics, people or quotes.
"""

STARTER_COMPONENTS = """\
The post body is MDX. Use GitHub-flavoured Markdown: headings, lists, tables and fenced code blocks.
Start with the first "## " section. Do not write frontmatter, a title or a TL;DR.
"""


def init(site: Path) -> int:
    site = site.resolve()
    config = site / CONFIG_NAME
    if config.exists():
        print(f"{config} already exists; nothing changed.")
        return 1
    folder = site / ".blog-studio"
    folder.mkdir(exist_ok=True)
    config.write_text(STARTER_CONFIG.format(name=site.name))
    for name, text in (("voice.md", STARTER_VOICE), ("components.md", STARTER_COMPONENTS)):
        if not (folder / name).exists():
            (folder / name).write_text(text)
    print(f"Created {config.relative_to(site.parent)} and .blog-studio/. Edit them, then run: blog-studio --site {site}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="blog-studio", description="Masthead: the publishing desk for engineering teams.")
    parser.add_argument("command", nargs="?", choices=["serve", "init"], default="serve")
    parser.add_argument("--site", help="path to the blog's repository (or set BLOG_STUDIO_SITE)")
    args = parser.parse_args()

    if args.command == "init":
        if not args.site:
            parser.error("init needs --site PATH")
        sys.exit(init(Path(args.site)))

    import uvicorn

    from .server import create_app

    try:
        settings = get_settings(args.site)
    except ConfigError as e:
        print(f"blog-studio: {e}", file=sys.stderr)
        sys.exit(2)
    if settings.cloud:
        # Hosted: listen on every interface behind the platform's proxy; the host check uses MASTHEAD_BASE_URL.
        host = os.environ.get("HOST", "0.0.0.0")
        print(f"Masthead (hosted) on {settings.base_url}")
        uvicorn.run(create_app(settings), host=host, port=settings.port, log_level="info", proxy_headers=True)
        return
    assert settings.site is not None
    print(f"Masthead for {settings.site.name} on http://127.0.0.1:{settings.port}  (site: {settings.site.root})")
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
