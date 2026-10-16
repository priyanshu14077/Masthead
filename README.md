# Masthead

The publishing desk for engineering teams. You give it an idea and your notes. It takes the post through outline, draft, confidentiality check, thumbnail and distribution copy, then puts the MDX into your blog's repository.

Masthead runs two ways.

- **Local** is one person and one blog on their own machine. It binds to 127.0.0.1, needs no sign-in, commits into the repository and never pushes.
- **Hosted** is the multi-tenant service. People sign in with GitHub and work in shared workspaces with roles. Blogs connect through the Masthead GitHub App, and publishing opens a pull request. Each workspace brings its own Anthropic API key, and Stripe handles plans.

Both work on any blog whose posts are MDX files in a git repository.

## Local quick start

```bash
# 1. Install
uv sync
npm install                      # Node packages used to compile post MDX before it's written

# 2. Set up a blog. Its settings live here in blogs/, so the blog's repository stays untouched.
uv run blog-studio init --site ../my-blog --config blogs/my-blog/blog-studio.toml
#    edit blogs/my-blog/blog-studio.toml and blogs/my-blog/.blog-studio/*.md

# 3. Add credentials and pick the blog
cp .env.example .env             # set ANTHROPIC_API_KEY (or run `ant auth login`) and BLOG_STUDIO_CONFIG

# 4. Run
uv run blog-studio
```

Open http://127.0.0.1:8787. The landing page is at the root and the app at `/app/`, both served by the same Masthead server. Build the landing page once with `cd marketing && npm install && npm run build`; until then the root goes straight to the app. Masthead renders its own previews, so the blog's dev server doesn't need to run.

`blogs/` is gitignored, because voice files describe your own writing. To keep the settings inside the blog's repository instead, leave out `--config` and run `uv run blog-studio --site ../my-blog`.

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

**Preview** renders the draft inside Masthead: title, thumbnail, TL;DR and body, with your components drawn as plain callouts, figures, steps and diagrams. Nothing from the draft runs, and nothing is written to the blog. **Copy draft into the blog** writes the post with `draft: true` locally, or pushes it to the post's pull request when hosted, for teams that also want the blog's own build.

**The publish gate** requires a check on the current text. High-severity findings and MDX errors must be fixed. Medium and low findings can be confirmed as reviewed. Publishing refuses to commit on protected branches such as `main`.

## Configuring a blog

A blog's settings are one TOML file plus two prompt files, kept in `blogs/<name>/` or in the blog's own repository. Paths under `[paths]` are relative to the blog's repository. Prompt files are relative to the settings file. Hosted Masthead reads the same file from the repository when a blog is connected, and again on every sync.

`blog-studio.toml`:

```toml
repo = "../../../my-blog"     # only when the file lives outside the blog; relative to this file
name = "Engineering notes"
author = "Your name"
site_url = "https://example.com"

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

A campaign groups posts on the board. A **series** campaign writes `series` and `seriesOrder` into each post. Schedule a post for a date and Masthead publishes it once that date arrives, checking every minute. Locally that only happens while Masthead is running, so use **Publish what's due** on the board after it was closed.

## Hosted setup

```bash
uv sync --extra postgres
MASTHEAD_MODE=cloud uv run blog-studio
```

Every setting is an environment variable. `.env.example` lists them all.

| Variable | What it's for |
| --- | --- |
| `MASTHEAD_MODE` | `cloud` for the hosted service. |
| `MASTHEAD_BASE_URL` | The public origin, such as `https://app.example.com`. Used for OAuth and Stripe return URLs and the host check. |
| `DATABASE_URL` | Postgres, as `postgresql+psycopg://user:pass@host/db`. SQLite is the default. |
| `MASTHEAD_SECRET_KEY` | At least 32 random characters. Encrypts each workspace's Anthropic key. Changing it makes stored keys unreadable. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | The OAuth App used for sign-in. |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_SLUG` | The GitHub App that reads blogs and opens pull requests. |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing. Without them, every workspace stays on its current plan. |
| `STRIPE_AUTOMATIC_TAX` | `1` to turn on Stripe Tax at checkout. |
| `PORT` | The port to listen on. Most hosts set it. |

**Sign-in.** Create a GitHub OAuth App with the callback `<MASTHEAD_BASE_URL>/auth/callback`. Masthead asks for no scopes, so it reads the public profile only. The flow uses PKCE and a single-use state, and checks the issuer.

**The GitHub App.** Create one with these permissions:

- Repository contents: read and write
- Pull requests: read and write
- Metadata: read
- Organisation members: read, so Masthead can confirm a person belongs to the organisation that installed the app

Set its Setup URL to `<MASTHEAD_BASE_URL>/github/setup`. Paste the private key into `GITHUB_APP_PRIVATE_KEY`, with newlines written as `\n` if your host needs a single line.

**Stripe.** Create the Team and Business products with four recurring per-seat prices. Give them the lookup keys `team_monthly`, `team_yearly`, `business_monthly` and `business_yearly`. Masthead finds prices by lookup key, so prices can change in Stripe without a deploy. Point a webhook at `<MASTHEAD_BASE_URL>/api/stripe/webhook` with these events:

- `checkout.session.completed`
- `customer.subscription.created`, `customer.subscription.updated` and `customer.subscription.deleted`
- `invoice.paid` and `invoice.payment_failed`

A workspace's plan changes only when a signed webhook arrives, never because the browser said so. Each event is applied once.

## Plans and roles

`plans.json` is the single source of truth for prices, limits and features. The server, the app and the marketing site all read it. Run `node scripts/sync-plans.mjs` after editing it to update the marketing copy.

| Plan | Price | Seats | Blogs | Posts a month |
| --- | --- | --- | --- | --- |
| Free | $0 | 1 | 1 | 5 |
| Team | $19 per seat a month, from 2 seats | up to 50 | 5 | unlimited |
| Business | $39 per seat a month, from 5 seats | unlimited | unlimited | unlimited |

Yearly billing charges ten months. A blocked feature returns HTTP 402 with the plan that includes it. Features listed in `coming_soon` show on the site and in the app as coming, and aren't enforced. `tests/test_plans.py` probes every feature on every plan, and fails when `plans.json` gains a feature the app doesn't gate.

| Role | Can |
| --- | --- |
| Owner | Everything, including members, blogs, the API key and billing |
| Editor | Write, review and publish |
| Writer | Write and run the AI steps |
| Reviewer | Approve or ask for changes |

On Team and Business, a post needs an approval from someone other than its author before it can be published. Any edit after an approval needs approving again.

## Data

Locally, ideas, drafts and the AI spend log live in `data/<blog-name>.db`, one SQLite file per blog. It's gitignored. A database from Blog Studio is upgraded in place on first start, after a timestamped backup is written next to it.

Hosted, everything lives in the database at `DATABASE_URL`, scoped by workspace and blog.

## Marketing site

`marketing/` is the landing page: Vite, React, TypeScript and Tailwind. The Masthead server serves its build at `/` and the app at `/app/`, so every "Start free" and plan button leads into the app on the same address. Prices are read from `plans.json` at build time.

```bash
cd marketing
npm install
npm run build    # served by Masthead at / from marketing/dist
npm run dev      # http://localhost:5173 while editing; /app, /api and /auth are proxied to Masthead on 8787
```

The pricing comparison and brand pages are plain HTML in `marketing/public/` and are copied into the build as they are. Run `node scripts/sync-plans.mjs` after editing `plans.json` to update their copy of it.

## Development

```bash
uv run --group dev pytest
```

The tests build a throwaway blog repository and use the fake AI, so they never touch a real site or spend tokens. Hosted-mode tests fake GitHub and Stripe, and run the OAuth flow against a mock transport.
