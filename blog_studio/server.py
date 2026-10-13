"""The Studio's local web server. Bound to 127.0.0.1; never deployed with the site."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, checks, content
from . import prompts as prompt_builder
from .ai import AI, AIError, FakeAI, Usage
from .config import STUDIO_DIR, Settings, get_settings
from .db import DB
from .thumbnail import DiagramSpec, render

SCHEDULER_INTERVAL = 60  # seconds


# Request bodies ----------------------------------------------------------
class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["series", "launch", "theme"] = "series"
    description: str = ""
    series_name: str | None = None


class CampaignPatch(BaseModel):
    name: str | None = None
    kind: Literal["series", "launch", "theme"] | None = None
    description: str | None = None
    series_name: str | None = None


class PostIn(BaseModel):
    idea: str = Field(min_length=3)
    notes: str = ""
    campaign_id: int | None = None
    allowed_names: list[str] = []


class PostPatch(BaseModel):
    idea: str | None = None
    notes: str | None = None
    campaign_id: int | None = None
    allowed_names: list[str] | None = None
    title: str | None = None
    slug: str | None = None
    subtitle: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    tldr: list[str] | None = None
    series_order: int | None = None
    body: str | None = None
    outline: dict[str, Any] | None = None
    social: dict[str, Any] | None = None


class ScheduleIn(BaseModel):
    publish_at: date


class AckIn(BaseModel):
    acknowledged: bool


# App ---------------------------------------------------------------------
def body_hash(post: dict[str, Any]) -> str:
    source = json.dumps([post.get("title"), post.get("summary"), post.get("subtitle"), post.get("tldr"), post.get("body")])
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def create_app(settings: Settings | None = None, ai: AI | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = DB(settings.db_path)
    built = prompt_builder.build(settings.site)
    model = ai or (FakeAI(built) if settings.fake_ai else AI(built))
    allowed_hosts = {f"127.0.0.1:{settings.port}", f"localhost:{settings.port}", "testserver"}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(scheduler_loop()) if os.environ.get("STUDIO_SCHEDULER", "1") == "1" else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Blog Studio", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings

    @app.middleware("http")
    async def local_only(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Blocks DNS-rebinding and cross-site requests from other pages open in the browser.
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if host not in allowed_hosts:
            return JSONResponse({"detail": "The Studio only answers on localhost."}, status_code=403)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin.split("://", 1)[-1] not in allowed_hosts:
            return JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
        return await call_next(request)

    # Helpers -------------------------------------------------------------
    def get_post(pid: int) -> dict[str, Any]:
        post = db.post(pid)
        if not post:
            raise HTTPException(404, "No such post.")
        return post

    def campaign_of(post: dict[str, Any]) -> dict[str, Any] | None:
        return db.campaign(post["campaign_id"]) if post.get("campaign_id") else None

    def log(pid: int | None, task: str, usage: Usage) -> None:
        db.log_call(pid, task, usage.model, usage.as_dict(), usage.cost)

    def view(post: dict[str, Any]) -> dict[str, Any]:
        out = dict(post)
        out["gate"] = publish_gate(post)
        out["spend_usd"] = db.post_spend(post["id"])
        out["preview_url"] = settings.site.preview(post["slug"]) if post.get("written") and post.get("slug") else None
        out["public_url"] = settings.site.public(post["slug"]) if post.get("slug") else None
        return out

    def publish_gate(post: dict[str, Any]) -> dict[str, Any]:
        """What still stands between this post and publishing."""
        missing = []
        if not post.get("body"):
            missing.append("Write the draft.")
        if not post.get("slug") or not content.SLUG_RE.match(post.get("slug") or ""):
            missing.append("Set a valid slug.")
        result = post.get("check_result")
        if not result or result.get("hash") != body_hash(post):
            missing.append("Run the confidentiality check on the current draft.")
        elif result["verdict"] != "clear" and not post.get("check_ack"):
            missing.append("Resolve the check's findings, or confirm you've reviewed them.")
        return {"ready": not missing, "missing": missing}

    def require_gate(post: dict[str, Any]) -> None:
        gate = publish_gate(post)
        if not gate["ready"]:
            raise HTTPException(409, " ".join(gate["missing"]))

    def thumbnail_svg(post: dict[str, Any]) -> str | None:
        return render(DiagramSpec.model_validate(post["thumb_spec"]), settings.site.theme) if post.get("thumb_spec") else None

    def do_publish(post: dict[str, Any], on: date) -> dict[str, Any]:
        require_gate(post)
        try:
            paths = content.write_post(settings, post, campaign_of(post), thumbnail_svg(post), draft=False, on=on)
            verb = "Update" if post["status"] == "published" else "Publish"
            sha = content.commit(settings, paths, f"{verb} the post: {post['title']}")
        except content.ContentError as e:
            raise HTTPException(409, str(e)) from e
        return db.update_post(post["id"], {
            "status": "published", "written": 1, "published_at": on.isoformat(), "commit_sha": sha, "last_error": None,
        })  # type: ignore[return-value]

    async def scheduler_loop() -> None:
        while True:
            await asyncio.sleep(SCHEDULER_INTERVAL)
            run_due()

    def run_due() -> list[int]:
        published = []
        for post in db.due_posts(date.today().isoformat()):
            try:
                do_publish(post, date.today())
                published.append(post["id"])
            except HTTPException as e:
                db.update_post(post["id"], {"last_error": str(e.detail)})
        return published

    app.state.run_due = run_due

    # State ---------------------------------------------------------------
    @app.get("/api/state")
    def state() -> dict[str, Any]:
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        has_profile = (Path.home() / ".config" / "anthropic").exists()
        return {
            "ai": "fake" if settings.fake_ai else ("ready" if has_key or has_profile else "missing"),
            "branch": content.current_branch(settings),
            "protected_branch": content.current_branch(settings) in settings.site.protected_branches,
            "site_name": settings.site.name,
            "site_root": str(settings.repo_root),
            "blog_preview": (settings.site.preview("") or "").rstrip("/") or None,
            "posts_dir": settings.site.posts_dir,
            "repo_root": str(settings.repo_root),
            "site_url": settings.site_url,
            "tags": content.known_tags(settings),
            "site_posts": content.site_posts(settings),
            "spend": db.spend(),
            "models": {"writer": "claude-sonnet-5-5", "reviewer": "claude-haiku-5-5"},
        }

    # Campaigns -----------------------------------------------------------
    @app.get("/api/campaigns")
    def list_campaigns() -> list[dict[str, Any]]:
        return db.campaigns()

    @app.post("/api/campaigns", status_code=201)
    def create_campaign(body: CampaignIn) -> dict[str, Any]:
        series = body.series_name or (body.name if body.kind == "series" else None)
        return db.create_campaign(body.name, body.kind, body.description, series)

    @app.patch("/api/campaigns/{cid}")
    def update_campaign(cid: int, body: CampaignPatch) -> dict[str, Any]:
        if not db.campaign(cid):
            raise HTTPException(404, "No such campaign.")
        return db.update_campaign(cid, body.model_dump(exclude_unset=True))  # type: ignore[return-value]

    @app.delete("/api/campaigns/{cid}", status_code=204)
    def delete_campaign(cid: int) -> Response:
        db.delete_campaign(cid)
        return Response(status_code=204)

    # Posts ---------------------------------------------------------------
    @app.get("/api/posts")
    def list_posts() -> list[dict[str, Any]]:
        return [view(p) for p in db.posts()]

    @app.post("/api/posts", status_code=201)
    def create_post(body: PostIn) -> dict[str, Any]:
        if body.campaign_id and not db.campaign(body.campaign_id):
            raise HTTPException(404, "No such campaign.")
        names = [n.strip() for n in body.allowed_names if n.strip()]
        return view(db.create_post(body.idea.strip(), body.notes, body.campaign_id, names))

    @app.get("/api/posts/{pid}")
    def read_post(pid: int) -> dict[str, Any]:
        return view(get_post(pid))

    @app.patch("/api/posts/{pid}")
    def update_post(pid: int, body: PostPatch) -> dict[str, Any]:
        post = get_post(pid)
        fields = body.model_dump(exclude_unset=True)
        if "slug" in fields and fields["slug"]:
            fields["slug"] = content.slugify(fields["slug"])
            if post.get("written") and fields["slug"] != post.get("slug"):
                raise HTTPException(409, "This post is already in the site under its current slug, so the slug can't change here.")
        if "allowed_names" in fields and fields["allowed_names"] is not None:
            fields["allowed_names"] = [n.strip() for n in fields["allowed_names"] if n.strip()]
        updated = db.update_post(pid, fields)
        # Any content change invalidates the check; a scheduled post drops back to review.
        if updated and body_hash(updated) != body_hash(post) and post["status"] in {"checked", "scheduled"}:
            updated = db.update_post(pid, {"status": "drafted", "check_ack": 0})
        return view(updated)  # type: ignore[arg-type]

    @app.delete("/api/posts/{pid}", status_code=204)
    def delete_post(pid: int) -> Response:
        post = get_post(pid)
        if post.get("written"):
            raise HTTPException(409, f"This post is already in the site. Delete its file from {settings.site.posts_dir} yourself if you mean to remove it.")
        db.delete_post(pid)
        return Response(status_code=204)

    # AI steps ------------------------------------------------------------
    @app.post("/api/posts/{pid}/outline")
    async def outline(pid: int) -> dict[str, Any]:
        post = get_post(pid)
        try:
            result, usage = await model.outline(post, content.known_tags(settings))
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(pid, "outline", usage)
        fields: dict[str, Any] = {
            "outline": result.model_dump(), "title": result.title, "subtitle": result.subtitle,
            "summary": result.summary, "tags": result.tags, "tldr": result.tldr,
            "status": "outlined" if post["status"] == "idea" else post["status"],
        }
        if not post.get("written"):
            fields["slug"] = content.slugify(result.slug or result.title)
        return view(db.update_post(pid, fields))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/draft")
    async def draft(pid: int) -> StreamingResponse:
        post = get_post(pid)
        if not post.get("outline"):
            raise HTTPException(409, "Generate or write an outline first.")
        reference = content.style_reference(settings)

        async def events() -> AsyncIterator[str]:
            usages: list[Usage] = []
            text = ""
            try:
                async for delta in model.draft(post, reference, usages):
                    text += delta
                    yield f"event: delta\ndata: {json.dumps({'text': delta})}\n\n"
            except AIError as e:
                for u in usages:
                    log(pid, "draft", u)
                if text:
                    db.update_post(pid, {"body": text})
                yield f"event: error\ndata: {json.dumps({'message': str(e), 'partial': bool(text)})}\n\n"
                return
            for u in usages:
                log(pid, "draft", u)
            body = text.strip()
            if body.startswith("```"):
                body = body.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            updated = db.update_post(pid, {"body": body, "status": "drafted", "check_result": None, "check_ack": 0})
            yield f"event: done\ndata: {json.dumps(view(updated))}\n\n"  # type: ignore[arg-type]

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/posts/{pid}/check")
    async def check(pid: int) -> dict[str, Any]:
        post = get_post(pid)
        if not post.get("body"):
            raise HTTPException(409, "There's no draft to check yet.")
        try:
            result, usage = await model.check(post)
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(pid, "check", usage)
        text = "\n".join(str(post.get(k) or "") for k in ("title", "subtitle", "summary", "body"))
        found = [f.model_dump() for f in result.findings] + checks.scan(text, settings.site_url)
        verdict = "block" if any(f["severity"] == "high" for f in found) else ("review" if any(f["severity"] == "medium" for f in found) else "clear")
        try:
            frontmatter = content.frontmatter(settings, post, campaign_of(post), draft=True, on=date.today())
            content.validate_mdx(settings, frontmatter + post["body"])
            mdx_error = None
        except content.ContentError as e:
            mdx_error = str(e)
            verdict = "block"
        payload = {"verdict": verdict, "findings": found, "mdx_error": mdx_error, "hash": body_hash(post)}
        status = post["status"] if post["status"] in {"scheduled", "published"} else "checked"
        return view(db.update_post(pid, {"check_result": payload, "check_ack": 0, "status": status}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/check/ack")
    def acknowledge(pid: int, body: AckIn) -> dict[str, Any]:
        post = get_post(pid)
        result = post.get("check_result") or {}
        if result.get("mdx_error") or any(f["severity"] == "high" for f in result.get("findings", [])):
            raise HTTPException(409, "High-severity findings and MDX errors have to be fixed, not confirmed.")
        return view(db.update_post(pid, {"check_ack": 1 if body.acknowledged else 0}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/thumbnail")
    async def thumbnail(pid: int) -> dict[str, Any]:
        post = get_post(pid)
        if not post.get("body"):
            raise HTTPException(409, "Write the draft first; the diagram is drawn from it.")
        try:
            spec, usage = await model.thumbnail(post)
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(pid, "thumbnail", usage)
        return view(db.update_post(pid, {"thumb_spec": spec.model_dump()}))  # type: ignore[arg-type]

    @app.get("/api/posts/{pid}/thumbnail.svg")
    def thumbnail_file(pid: int) -> Response:
        svg = thumbnail_svg(get_post(pid))
        if not svg:
            raise HTTPException(404, "No thumbnail yet.")
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

    @app.post("/api/posts/{pid}/social")
    async def social(pid: int) -> dict[str, Any]:
        post = get_post(pid)
        if not post.get("body") or not post.get("slug"):
            raise HTTPException(409, "Write the draft first.")
        try:
            result, usage = await model.social(post, settings.site.public(post["slug"]) or post["slug"])
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(pid, "social", usage)
        return view(db.update_post(pid, {"social": result.model_dump()}))  # type: ignore[arg-type]

    # Writing to the site -------------------------------------------------
    @app.post("/api/posts/{pid}/preview")
    def preview(pid: int) -> dict[str, Any]:
        """Writes the post as a draft, which the dev server shows and production hides."""
        post = get_post(pid)
        if post["status"] == "published":
            raise HTTPException(409, "This post is live. Use Publish to update it.")
        try:
            content.write_post(settings, post, campaign_of(post), thumbnail_svg(post), draft=True, on=date.today())
        except content.ContentError as e:
            raise HTTPException(409, str(e)) from e
        return view(db.update_post(pid, {"written": 1}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/schedule")
    def schedule(pid: int, body: ScheduleIn) -> dict[str, Any]:
        post = get_post(pid)
        require_gate(post)
        if body.publish_at < date.today():
            raise HTTPException(422, "Pick today or a future date.")
        return view(db.update_post(pid, {"status": "scheduled", "publish_at": body.publish_at.isoformat(), "last_error": None}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/unschedule")
    def unschedule(pid: int) -> dict[str, Any]:
        post = get_post(pid)
        if post["status"] != "scheduled":
            raise HTTPException(409, "This post isn't scheduled.")
        return view(db.update_post(pid, {"status": "checked", "publish_at": None}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/publish")
    def publish(pid: int) -> dict[str, Any]:
        return view(do_publish(get_post(pid), date.today()))

    @app.post("/api/scheduler/run")
    def scheduler_run() -> dict[str, Any]:
        return {"published": run_due()}

    app.include_router(auth.router(settings.port))
    app.mount("/", StaticFiles(directory=STUDIO_DIR / "ui", html=True), name="ui")
    return app
