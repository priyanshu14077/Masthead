# Masthead

Masthead takes an engineering blog post from an idea and the author's notes to a pull request: outline, draft, confidentiality check, thumbnail, distribution copy, publish. It runs in two modes. **Local** serves one person and one blog, with no sign-in, and commits into the blog's repo. **Cloud** is the hosted, multi-tenant service. The product is Masthead in every piece of copy. The Python package and CLI keep the old name, `blog_studio` and `blog-studio`.

## Rules

- **Git:** commit only when the owner asks. Pushing, opening pull requests and creating repos also wait for the owner.
- **Pricing:** propose changes to prices, limits or plan features, and apply them once the owner signs off. This covers `plans.json` and any pricing copy.
- **Secrets:** `.env` holds real keys. Read values in code and refer to keys by name in replies.
- **Scope:** finish the task you were given. List unrelated problems you notice at the end of your reply, and leave them unfixed.

## Done means

A change is done when its checks pass:

- Backend: `STUDIO_DATA_DIR=$(mktemp -d) uv run pytest -q` and `uvx ruff check blog_studio tests`
- Landing page: `npm run build` in `marketing/`

## House style

This applies to UI text, marketing copy, docs, comments and commit messages.

- British spelling: colour, organise, licence.
- Full stops and commas where a dash would go. No em dashes.
- One idea per sentence, plain and concrete. Name the system, the file, the number.
- Describe the product, not the page. Readers need no directions to scroll or click.
- A heading stands on its own. No sub-line that repeats or explains it.
- Claim only what the code does today. Prices, limits and features come from `plans.json`.

## How things work

- **Real data.** `data/field-notes.db` holds the owner's real posts, and `blogs/` holds personal blog settings. Both are gitignored. Tests and demos run on a scratch `STUDIO_DATA_DIR` and the throwaway blog repo built in `tests/conftest.py`. Local mode pointed at the owner's portfolio commits into that repo.
- **`.env` loads on every start.** `get_settings()` reads it from the repo root, so a real Anthropic key is live unless `STUDIO_FAKE_AI=1`.
- **Access control** lives in `blog_studio/tenancy.py`. A route calls `ctx.require(permission)` for a role check, which returns 403, and `ctx.feature(name)` for a plan check, which returns 402 and names the plan that includes the feature.
- **Plan features are enforced per route** with `ctx.feature`. `tests/test_plans.py` probes each plans.json feature on each plan; a new feature needs a probe there, or a place in `coming_soon`.
- **Previews** are rendered by Masthead itself (`blog_studio/preview.py` and `scripts/render-mdx.mjs`). The renderer never executes draft code: components map to plain elements, attribute values are read only as literals, and the output is sanitised.
- **Plans change only through Stripe.** A workspace's plan changes only in `billing.handle_event`, after a verified and de-duplicated webhook.
- **Schema.** SQLAlchemy Core tables are in `db.py`. `create_all` adds new tables but never new columns. A column on an existing table needs a hand-written upgrade step, in the style of `upgrade_legacy`. There is no Alembic.
- **Models.** `ai.py` pins `WRITER` (Sonnet 5.5, for outline, draft and thumbnail) and `REVIEWER` (Haiku 5.5, for the check and distribution copy).
- **MDX validation and previews** need `npm install` at the repo root, for the scripts in `scripts/`.
- **One address.** The server serves the landing page (`marketing/dist`) at `/` and the app (`ui/`) at `/app/`. Links into the product use `/app/` paths, never another domain. Rebuild the site after changing it.
- **Marketing site.** `marketing/` is Vite, React and Tailwind. It reads `../plans.json` at build time. `marketing/public/` holds the static pricing and brand pages, with a copy of `plans.json` that `node scripts/sync-plans.mjs` refreshes. The sample post in the desk demo, `desk-data.ts`, is illustrative.
