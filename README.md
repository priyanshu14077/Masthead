# Blog Studio

A local campaign manager for a static blog. You give it an idea and your notes. It takes the post through outline, draft, confidentiality check, thumbnail and social copy, then writes the MDX into your blog's repository and commits it. It never pushes.

It runs on your machine, binds to 127.0.0.1, and works on any blog whose posts are MDX files in a git repository.

## Quick start

```bash
# 1. Install
uv sync
npm install                      # Node packages used to compile post MDX before it's written

# 2. Point it at a blog
uv run blog-studio init --site ../my-blog
#    edit ../my-blog/blog-studio.toml and ../my-blog/.blog-studio/*.md

# 3. Add credentials
cp .env.example .env             # set ANTHROPIC_API_KEY, or run `ant auth login`

# 4. Run
uv run blog-studio --site ../my-blog
```

Open http://127.0.0.1:8787. Keep your blog's dev server running so previews open.

To try it without spending tokens, set `STUDIO_FAKE_AI=1` in `.env`.

## How a post moves

| Step | What happens | Model |
| --- | --- | --- |
| Idea | You write the idea, paste notes, and list the names allowed to appear. | none |
| Outline | Title, slug, summary, tags, TL;DR and sections, all editable. | Claude Sonnet 5.5 |
| Draft | The full MDX body streams in, using your blog's components. | Claude Sonnet 5.5 |
| Check | Names outside your list, internal details, security weaknesses, personal data and numbers not in your notes. Local checks add secrets, internal hosts and links, and the MDX is compiled. | Claude Haiku 5.5 |
| Thumbnail | An architecture diagram drawn in your blog's palette. | Claude Sonnet 5.5 |
| Distribution | LinkedIn post, X thread and newsletter blurb to post by hand. | Claude Haiku 5.5 |
| Publish | Writes the post and thumbnail, and commits only those files. | none |

**Preview** writes the post with `draft: true`, so your dev server shows it and production hides it, if your blog filters drafts.

**The publish gate** requires a check on the current text. High-severity findings and MDX errors must be fixed. Medium and low findings can be confirmed as reviewed. Publishing refuses to commit on protected branches such as `main`.

## Configuring a blog

Everything about a blog lives in that blog's repository, so the Studio itself holds no site details.

`blog-studio.toml`:

```toml
name = "Field notes"
author = "Your name"
site_url = "https://example.com"
preview_url = "http://localhost:5173/blog/{slug}"

[paths]
posts = "content/blog"
thumbnails = "public/blog"
thumbnail_url = "/blog/{slug}/thumbnail.svg"
style_reference = "content/blog/my-best-post.mdx"

[prompts]
voice = ".blog-studio/voice.md"            # house style used in every prompt
components = ".blog-studio/components.md"  # how to use your MDX components

[mdx]
components = ["Callout", "Figure", "Mermaid"]

[git]
protected_branches = ["main", "master"]

[theme]   # thumbnail palette
background = "#14213a"
accent = "#b4673d"
```

Posts are written with frontmatter fields `title`, `subtitle`, `slug`, `date`, `tags`, `series`, `seriesOrder`, `thumbnail`, `summary`, `tldr` and `draft`. Your blog reads whichever of those it needs.

## Campaigns

A campaign groups posts on the board. A **series** campaign writes `series` and `seriesOrder` into each post. Schedule a post for a date and the Studio publishes it once that date arrives, checking every minute while it runs. If the Studio was closed, use **Publish what's due** on the board.

## Data

Ideas, drafts and the AI spend log live in `data/<blog-name>.db`, one SQLite file per blog. It's gitignored.

## Development

```bash
uv run --group dev pytest
```

The tests build a throwaway blog repository and use the fake AI, so they never touch a real site or spend tokens.
