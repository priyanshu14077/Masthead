# Blog Studio

A local campaign manager for the blog. You give it an idea and your notes; it takes the post through outline, draft, confidentiality check, thumbnail, social copy and publishing, and commits the result to this repo. It runs only on your machine and is never deployed with the site.

## Start it

1. Add credentials once. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`.
2. From the `app` folder, run:

   ```bash
   npm run studio
   ```

3. Open http://127.0.0.1:8787. Keep `npm run dev` running too, so previews open on the dev server.

To try the interface without spending tokens, set `STUDIO_FAKE_AI=1` in `.env`.

## How a post moves

| Step | What happens | Model |
| --- | --- | --- |
| Idea | You write the idea, paste notes, and list the names allowed to appear. | none |
| Outline | Title, slug, summary, tags, TL;DR and sections, all editable. | Claude Sonnet 5.5 |
| Draft | The full MDX body streams in, using the site's components. Edit freely. | Claude Sonnet 5.5 |
| Check | Names outside your list, internal details, security weaknesses, personal data and numbers not in your notes. Local checks add secrets, internal hosts and links, and the MDX is compiled. | Claude Haiku 5.5 |
| Thumbnail | A diagram drawn in the style of the existing thumbnails. | Claude Sonnet 5.5 |
| Distribution | LinkedIn post, X thread and newsletter blurb to post by hand. | Claude Haiku 5.5 |
| Publish | Writes `content/blog/<slug>.mdx` and the thumbnail, and commits only those files. | none |

**Preview** writes the post with `draft: true`, so it appears on the dev server and stays hidden in production.

**Publishing never pushes.** It refuses to commit on `main` or `master`, because those deploy the live site. Push and merge yourself when you're ready.

**The publish gate** requires a check on the current text. High-severity findings and MDX errors must be fixed. Medium and low findings can be confirmed as reviewed.

## Campaigns

A campaign groups posts on the board. A **series** campaign writes `series` and `seriesOrder` into each post, so the site shows "Part 2 of 5" banners and links the parts.

Schedule a post for a date and the Studio publishes it once that date arrives, checking every minute while it runs. If the Studio was closed, use **Publish what's due** on the board.

## Where things live

- `studio/` holds the Python backend (FastAPI and SQLite) and the plain HTML, CSS and JavaScript interface in `ui/`.
- `studio/data/studio.db` holds ideas, drafts and the AI spend log. It's gitignored.
- AI spend is logged per call and shown in the sidebar.

## Tests

```bash
cd studio && uv run --group dev pytest
```

The tests use a throwaway git repo and the fake AI, so they never touch the site or spend tokens.
