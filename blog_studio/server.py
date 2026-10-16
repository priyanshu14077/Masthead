"""Masthead's web server.

Local mode: one person, one blog on this machine; bound to 127.0.0.1, no sign-in.
Cloud mode: GitHub sign-in, workspaces with roles, blogs connected through the GitHub App,
each workspace's own Anthropic key, and Stripe billing. Same routes, same UI.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, billing, checks, content, crypto, plans
from . import prompts as prompt_builder
from .ai import AI, AIError, FakeAI, Usage
from .config import CONFIG_NAME, STUDIO_DIR, ConfigError, Settings, get_settings, parse_config, site_from_snapshot
from .db import DB
from .github_app import AppConfig, GitHubApp, GitHubError
from .publisher import GitHubPublisher, LocalGitPublisher, Publisher
from .tenancy import Ctx, Upgrade, prompt_site
from .thumbnail import DiagramSpec, render

SCHEDULER_INTERVAL = 60  # seconds
LOCAL_GITHUB_ID = 0  # the synthetic user that owns everything in local mode


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


class ReviewIn(BaseModel):
    decision: Literal["approved", "changes"]
    note: str = ""


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class InviteIn(BaseModel):
    login: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9-]+$")
    role: Literal["owner", "editor", "writer", "reviewer"] = "writer"


class RoleIn(BaseModel):
    role: Literal["owner", "editor", "writer", "reviewer"]


class SiteIn(BaseModel):
    installation_id: int
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class SitePatch(BaseModel):
    required_reviewers: int = Field(ge=0, le=10)


class KeyIn(BaseModel):
    key: str = Field(min_length=20, max_length=300)


class CheckoutIn(BaseModel):
    plan: Literal["team", "business"]
    interval: Literal["monthly", "yearly"] = "monthly"


def body_hash(post: dict[str, Any]) -> str:
    source = json.dumps([post.get("title"), post.get("summary"), post.get("subtitle"), post.get("tldr"), post.get("body")])
    return hashlib.sha256(source.encode()).hexdigest()[:16]


def create_app(
    settings: Settings | None = None,
    ai: AI | None = None,
    gateway: billing.Gateway | None = None,
    github: GitHubApp | None = None,
    oauth_http: Any = None,
) -> FastAPI:
    settings = settings or get_settings()
    db = DB(settings.db_url)
    gateway = gateway or billing.gateway_from_env()
    if github is None and os.environ.get("GITHUB_APP_ID") and os.environ.get("GITHUB_APP_PRIVATE_KEY"):
        github = GitHubApp(AppConfig(os.environ["GITHUB_APP_ID"], os.environ["GITHUB_APP_PRIVATE_KEY"].replace("\\n", "\n"), os.environ.get("GITHUB_APP_SLUG", "masthead")))
    host = settings.base_url.split("://", 1)[1].split("/")[0]
    allowed_hosts = {host, "testserver"} | ({f"127.0.0.1:{settings.port}", f"localhost:{settings.port}"} if not settings.cloud else set())
    models: dict[tuple[Any, ...], AI] = {}

    # Local mode: one owner, one workspace, one site, every feature.
    local_ctx: dict[str, Any] = {}
    if not settings.cloud:
        assert settings.site is not None
        user = db.upsert_user(LOCAL_GITHUB_ID, "local", "You", None)
        spaces = db.workspaces_for(user["id"])
        ws = spaces[0] if spaces else db.create_workspace("Local", user["id"])
        db.save_subscription(ws["id"], {"plan": "business", "status": "active", "seats": 1})
        row = next((s for s in db.sites_for(ws["id"]) if s.get("local_root") == str(settings.site.root)), None)
        row = row or db.create_site(ws["id"], settings.site.name, local_root=str(settings.site.root))
        db.adopt_orphans(row["id"])
        local_ctx = {"user": user, "workspace": db.workspace(ws["id"]), "site_row": row}

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(scheduler_loop()) if os.environ.get("STUDIO_SCHEDULER", "1") == "1" else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Masthead", lifespan=lifespan)
    app.state.db = db
    app.state.settings = settings

    @app.middleware("http")
    async def guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Blocks DNS rebinding and cross-site requests made by other pages open in the browser.
        if request.headers.get("host", "") not in allowed_hosts:
            return JSONResponse({"detail": "Wrong host."}, status_code=403)
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin.split("://", 1)[-1] not in allowed_hosts:
            return JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
        return await call_next(request)

    # Context -------------------------------------------------------------
    def site_for(row: dict[str, Any] | None) -> Any:
        if not row:
            return None
        if row.get("local_root"):
            return settings.site
        return site_from_snapshot(row.get("config") or {}, row["name"])

    def ctx(request: Request) -> Ctx:
        if not settings.cloud:
            row = local_ctx["site_row"]
            wid = local_ctx["workspace"]["id"]
            sub = db.subscription(wid)
            return Ctx(local_ctx["user"], local_ctx["workspace"], "owner", sub, billing.effective_plan(sub), True, row, settings.site, db.for_site(row["id"]))
        user = db.session_user(request.cookies.get(auth.SESSION_COOKIE))
        if not user:
            raise HTTPException(401, "Sign in to continue.")
        spaces = db.workspaces_for(user["id"])
        if not spaces:
            raise HTTPException(409, "You're not in a workspace yet.")
        wanted = request.headers.get("x-masthead-workspace")
        ws = next((w for w in spaces if str(w["id"]) == wanted), spaces[0])
        sub = db.subscription(ws["id"])
        site_rows = db.sites_for(ws["id"])
        wanted_site = request.headers.get("x-masthead-site")
        row = next((s for s in site_rows if str(s["id"]) == wanted_site), site_rows[0] if site_rows else None)
        return Ctx(user, ws, ws["role"], sub, billing.effective_plan(sub), False, row, site_for(row), db.for_site(row["id"]) if row else None)

    def model_for(c: Ctx) -> AI:
        site, _ = c.need_site()
        if ai is not None:
            return ai
        built = prompt_builder.build(prompt_site(site, c.plan, c.local))
        if settings.fake_ai:
            return FakeAI(built)
        key = None
        if settings.cloud:
            cred = db.credential(c.wid, "anthropic")
            if not cred:
                raise HTTPException(409, "Add your workspace's Anthropic API key in Settings, API key.")
            try:
                key = crypto.decrypt(cred["ciphertext"])
            except crypto.SecretError as e:
                raise HTTPException(500, str(e)) from e
        cache_key = (c.wid, hashlib.sha256((key or "").encode()).hexdigest(), hash(built))
        if cache_key not in models:
            models[cache_key] = AI(built, api_key=key)
        return models[cache_key]

    def publisher_for(row: dict[str, Any], site: Any) -> Publisher:
        if row.get("local_root"):
            return LocalGitPublisher(site)
        if not github:
            raise HTTPException(503, "The GitHub App isn't configured on this server.")
        return GitHubPublisher(github, site, int(row["installation_id"]), row["repo_full_name"], row.get("default_branch") or "main")

    def log(c: Ctx, pid: int | None, task: str, usage: Usage) -> None:
        db.log_call(c.wid, c.uid, pid, task, usage.model, usage.as_dict(), usage.cost)

    # Posts helpers -------------------------------------------------------
    def get_post(c: Ctx, pid: int) -> dict[str, Any]:
        _, store = c.need_site()
        post = store.post(pid)
        if not post:
            raise HTTPException(404, "No such post.")
        return post

    def campaign_of(c: Ctx, post: dict[str, Any]) -> dict[str, Any] | None:
        return c.store.campaign(post["campaign_id"]) if c.store and post.get("campaign_id") else None

    def required_reviewers(c: Ctx) -> int:
        if c.local or not c.plan.has("review_workflow"):
            return 0
        cap = c.plan.limit("reviewers_required") or 0
        wanted = ((c.site_row or {}).get("config") or {}).get("required_reviewers", 1)
        return min(int(wanted), cap) if c.plan.has("approval_rules") else min(1, cap)

    def review_state(c: Ctx, post: dict[str, Any]) -> dict[str, Any]:
        current = body_hash(post)
        entries = [a for a in db.approvals_for(post["id"]) if a["body_hash"] == current and a["user_id"] != post.get("author_id")]
        return {
            "required": required_reviewers(c),
            "approved": [a["login"] for a in entries if a["decision"] == "approved"],
            "changes": [{"login": a["login"], "note": a["note"]} for a in entries if a["decision"] == "changes"],
        }

    def publish_gate(c: Ctx, post: dict[str, Any]) -> dict[str, Any]:
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
        review = review_state(c, post)
        if review["changes"]:
            missing.append("A reviewer asked for changes.")
        elif len(review["approved"]) < review["required"]:
            n = review["required"] - len(review["approved"])
            missing.append(f"Needs {n} more reviewer approval{'s' if n > 1 else ''}.")
        return {"ready": not missing, "missing": missing, "review": review}

    def view(c: Ctx, post: dict[str, Any]) -> dict[str, Any]:
        out = dict(post)
        out["gate"] = publish_gate(c, post)
        out["spend_usd"] = db.post_spend(post["id"])
        site = c.site
        out["preview_url"] = (post.get("pr_url") if not c.local else site.preview(post["slug"])) if post.get("written") and post.get("slug") and site else None
        out["public_url"] = site.public(post["slug"]) if site and post.get("slug") else None
        return out

    def require_gate(c: Ctx, post: dict[str, Any]) -> None:
        gate = publish_gate(c, post)
        if not gate["ready"]:
            raise HTTPException(409, " ".join(gate["missing"]))

    def thumbnail_svg(c: Ctx, post: dict[str, Any]) -> str | None:
        return render(DiagramSpec.model_validate(post["thumb_spec"]), c.site.theme) if post.get("thumb_spec") and c.site else None

    async def do_publish(c: Ctx, post: dict[str, Any], on: date) -> dict[str, Any]:
        site, store = c.need_site()
        require_gate(c, post)
        try:
            files = content.build_files(site, post, campaign_of(c, post), thumbnail_svg(c, post), draft=False, on=on)
            verb = "Update" if post["status"] == "published" else "Publish"
            out = await publisher_for(c.site_row, site).publish(files, post["slug"], post["title"], f"{verb} the post: {post['title']}")  # type: ignore[arg-type]
        except content.ContentError as e:
            raise HTTPException(409, str(e)) from e
        db.audit(c.wid, c.uid, "post.published", post["title"], {"sha": out.sha, "pr_url": out.pr_url})
        return store.update_post(post["id"], {
            "status": "published", "written": 1, "published_at": on.isoformat(), "commit_sha": out.sha, "pr_url": out.pr_url, "last_error": None,
        })  # type: ignore[return-value]

    async def scheduler_loop() -> None:
        while True:
            await asyncio.sleep(SCHEDULER_INTERVAL)
            await run_due()

    async def run_due(c: Ctx | None = None) -> list[int]:
        published = []
        for post in db.due_posts(date.today().isoformat()):
            row = db.site(post["site_id"]) if post.get("site_id") else None
            if not row or (c and row["workspace_id"] != c.wid):
                continue
            ws = db.workspace(row["workspace_id"])
            sub = db.subscription(row["workspace_id"])
            system = Ctx({"id": None}, ws, "owner", sub, billing.effective_plan(sub), not settings.cloud, row, site_for(row), db.for_site(row["id"]))  # type: ignore[arg-type]
            try:
                if not system.local:
                    system.feature("scheduling")
                await do_publish(system, post, date.today())
                published.append(post["id"])
            except HTTPException as e:
                system.store.update_post(post["id"], {"last_error": str(e.detail)})  # type: ignore[union-attr]
        return published

    app.state.run_due = run_due

    # Account -------------------------------------------------------------
    @app.get("/api/me")
    def me(request: Request) -> dict[str, Any]:
        if not settings.cloud:
            return {"mode": "local", "user": local_ctx["user"], "workspaces": db.workspaces_for(local_ctx["user"]["id"])}
        user = db.session_user(request.cookies.get(auth.SESSION_COOKIE))
        return {"mode": "cloud", "user": user, "workspaces": db.workspaces_for(user["id"]) if user else [], "sign_in": "/auth/login"}

    @app.post("/api/workspaces", status_code=201)
    def create_workspace(body: WorkspaceIn, request: Request) -> dict[str, Any]:
        user = db.session_user(request.cookies.get(auth.SESSION_COOKIE)) if settings.cloud else local_ctx["user"]
        if not user:
            raise HTTPException(401, "Sign in to continue.")
        ws = db.create_workspace(body.name.strip(), user["id"])
        db.audit(ws["id"], user["id"], "workspace.created", ws["name"])
        return ws

    @app.get("/api/state")
    def state(c: Ctx = Depends(ctx)) -> dict[str, Any]:
        site = c.site
        local_branch = LocalGitPublisher(site).branch() if site and c.local else ""
        has_env_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")) or (Path.home() / ".config" / "anthropic").exists()
        cred = db.credential(c.wid, "anthropic")
        ai_state = "fake" if settings.fake_ai else ("ready" if (cred if settings.cloud else has_env_key) else "missing")
        limits = {
            "seats": {"used": db.seat_count(c.wid), "limit": seat_limit(c)},
            "repos": {"used": len(db.sites_for(c.wid)), "limit": c.plan.limit("repos")},
            "posts_per_month": {"used": db.posts_this_month(c.wid), "limit": c.plan.limit("posts_per_month")},
        }
        return {
            "mode": settings.mode,
            "user": {k: c.user.get(k) for k in ("id", "login", "name", "avatar_url")},
            "workspace": {"id": c.wid, "name": c.workspace["name"]},
            "role": c.role,
            "permissions": sorted(p for p in ("write", "review", "publish", "use_ai", "campaigns", "manage_members", "manage_sites", "manage_billing", "manage_keys", "view_audit") if c.can(p)),
            "plan": {"id": c.plan.id, "name": c.plan.name, "features": sorted(c.plan.features), "status": c.sub.get("status"), "seats": c.sub.get("seats"), "cancel_at_period_end": bool(c.sub.get("cancel_at_period_end"))},
            "limits": limits,
            "sites": [{"id": s["id"], "name": s["name"], "repo": s.get("repo_full_name")} for s in db.sites_for(c.wid)],
            "site": {"id": c.site_row["id"], "name": c.site_row["name"]} if c.site_row else None,
            "ai": ai_state,
            "key_last4": cred["last4"] if cred else None,
            "billing_enabled": gateway is not None,
            "github_app": {"install_url": github.config.install_url} if github else None,
            "branch": local_branch,
            "protected_branch": bool(site and local_branch in site.protected_branches),
            "site_name": site.name if site else None,
            "blog_preview": (site.preview("") or "").rstrip("/") or None if site and c.local else None,
            "posts_dir": site.posts_dir if site else None,
            "site_url": site.site_url if site else None,
            "tags": content.known_tags(site) if site else [],
            "site_posts": content.site_posts(site) if site else [],
            "spend": db.spend(c.wid),
            "models": {"writer": "claude-sonnet-5-5", "reviewer": "claude-haiku-5-5"},
        }

    @app.get("/api/plans")
    def plan_catalogue() -> dict[str, Any]:
        """plans.json as is, so the app's upgrade cards show the same prices the server enforces."""
        return json.loads(plans.PLANS_FILE.read_text())

    # Members ---------------------------------------------------------------
    def seat_limit(c: Ctx) -> int | None:
        if c.local:
            return None
        plan_cap = c.plan.limit("seats")
        if not c.plan.per_seat:
            return plan_cap
        bought = int(c.sub.get("seats") or 1)
        return min(bought, plan_cap) if plan_cap else bought

    @app.get("/api/members")
    def list_members(c: Ctx = Depends(ctx)) -> dict[str, Any]:
        return {"members": db.members(c.wid), "invites": db.pending_invites(c.wid), "seats": {"used": db.seat_count(c.wid), "limit": seat_limit(c)}}

    @app.post("/api/invites", status_code=201)
    def invite(body: InviteIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_members")
        if body.role in {"editor", "reviewer"}:
            c.feature("roles")
        limit = seat_limit(c)
        if limit is not None and db.seat_count(c.wid) >= limit:
            if c.plan.per_seat:
                raise Upgrade("Every seat you've bought is in use. Add seats in Settings, Billing.", None)
            raise Upgrade("Your plan has one seat.", plans.get("team"))
        inv = db.create_invite(c.wid, body.login, body.role, c.uid)
        db.audit(c.wid, c.uid, "member.invited", body.login, {"role": body.role})
        return inv

    @app.delete("/api/invites/{iid}", status_code=204)
    def revoke(iid: int, c: Ctx = Depends(ctx)) -> Response:
        c.require("manage_members")
        db.revoke_invite(c.wid, iid)
        return Response(status_code=204)

    @app.patch("/api/members/{uid}")
    def set_role(uid: int, body: RoleIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_members")
        if body.role in {"editor", "reviewer"}:
            c.feature("roles")
        target = db.membership(c.wid, uid)
        if not target:
            raise HTTPException(404, "Not a member of this workspace.")
        if target["role"] == "owner" and body.role != "owner" and db.owners(c.wid) == 1:
            raise HTTPException(409, "A workspace needs at least one owner.")
        db.set_role(c.wid, uid, body.role)
        db.audit(c.wid, c.uid, "member.role_changed", str(uid), {"role": body.role})
        return {"ok": True}

    @app.delete("/api/members/{uid}", status_code=204)
    def remove_member(uid: int, c: Ctx = Depends(ctx)) -> Response:
        c.require("manage_members")
        target = db.membership(c.wid, uid)
        if target and target["role"] == "owner" and db.owners(c.wid) == 1:
            raise HTTPException(409, "A workspace needs at least one owner.")
        db.remove_member(c.wid, uid)
        db.audit(c.wid, c.uid, "member.removed", str(uid))
        return Response(status_code=204)

    # Blogs (sites) -------------------------------------------------------
    async def snapshot(installation_id: int, repo: str, branch: str) -> dict[str, Any]:
        """Reads a blog's config, prompt files, style reference and existing posts from GitHub."""
        assert github
        client = await github.repo(installation_id, repo)
        raw_text = await client.read(CONFIG_NAME, branch) or await client.read("masthead.toml", branch)
        if raw_text is None:
            raise HTTPException(409, f"{repo} has no {CONFIG_NAME}. Add one (see the docs), then connect it again.")
        try:
            raw = tomllib.loads(raw_text)
        except tomllib.TOMLDecodeError as e:
            raise HTTPException(409, f"{CONFIG_NAME}: {e}") from e
        prompt_paths = raw.get("prompts", {})
        texts = {}
        for key in ("voice", "components"):
            rel = prompt_paths.get(key)
            texts[rel] = (await client.read(rel, branch) or "") if rel else ""
        fields = parse_config(raw, Path(repo), lambda rel: texts.get(rel, "") if rel else "")
        posts_dir = fields["posts_dir"]
        known = []
        for path in (await client.list_dir(posts_dir, branch))[:200]:
            name = path.rsplit("/", 1)[-1]
            if name.endswith(".mdx") and not name.startswith("_"):
                known.append(content.summarise(name, await client.read(path, branch) or ""))
        ref = fields.get("style_reference")
        style = (await client.read(ref, branch) or "") if ref else ""
        fields["name"] = raw.get("name") or repo.split("/")[1]
        return {**fields, "repo": repo, "known_posts": known, "style_reference_text": style}

    @app.get("/github/setup")
    def github_setup(installation_id: int | None = None) -> RedirectResponse:
        # The GitHub App's "Setup URL": back to the Blogs settings with the new installation.
        return RedirectResponse(f"/#/settings/sites?installation_id={installation_id or ''}", status_code=302)

    @app.get("/api/github/repositories")
    async def repositories(installation_id: int, c: Ctx = Depends(ctx)) -> list[dict[str, str]]:
        c.require("manage_sites")
        if not github:
            raise HTTPException(503, "The GitHub App isn't configured on this server.")
        try:
            if not await github.can_use(installation_id, c.user["login"]):
                raise HTTPException(403, "That installation belongs to an account you're not part of.")
            return await github.repositories(installation_id)
        except GitHubError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/sites", status_code=201)
    async def connect_site(body: SiteIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_sites")
        if not github:
            raise HTTPException(503, "The GitHub App isn't configured on this server.")
        limit = c.plan.limit("repos")
        if limit is not None and len(db.sites_for(c.wid)) >= limit:
            raise Upgrade(f"Your plan connects {limit} blog{'s' if limit != 1 else ''}.", plans.get("team" if c.plan.id == "free" else "business"))
        try:
            if not await github.can_use(body.installation_id, c.user["login"]):
                raise HTTPException(403, "That installation belongs to an account you're not part of.")
            repos = {r["full_name"]: r for r in await github.repositories(body.installation_id)}
            if body.repo not in repos:
                raise HTTPException(404, "The app isn't installed on that repository.")
            if any(s.get("repo_full_name") == body.repo for s in db.sites_for(c.wid)):
                raise HTTPException(409, "That repository is already connected to this workspace.")
            branch = repos[body.repo]["default_branch"]
            snap = await snapshot(body.installation_id, body.repo, branch)
        except GitHubError as e:
            raise HTTPException(502, str(e)) from e
        row = db.create_site(c.wid, snap["name"], repo_full_name=body.repo, installation_id=body.installation_id, default_branch=branch, config=snap)
        db.audit(c.wid, c.uid, "site.connected", body.repo)
        return {"id": row["id"], "name": row["name"], "repo": body.repo}

    @app.post("/api/sites/{sid}/sync")
    async def sync_site(sid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_sites")
        row = db.site(sid)
        if not row or row["workspace_id"] != c.wid or not row.get("repo_full_name"):
            raise HTTPException(404, "No such hosted blog.")
        try:
            snap = await snapshot(int(row["installation_id"]), row["repo_full_name"], row.get("default_branch") or "main")
        except GitHubError as e:
            raise HTTPException(502, str(e)) from e
        keep = {"required_reviewers": (row.get("config") or {}).get("required_reviewers", 1)}
        db.update_site(sid, {"config": {**snap, **keep}})
        return {"ok": True, "posts": len(snap["known_posts"])}

    @app.patch("/api/sites/{sid}")
    def update_site(sid: int, body: SitePatch, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_sites")
        c.feature("approval_rules")
        row = db.site(sid)
        if not row or row["workspace_id"] != c.wid:
            raise HTTPException(404, "No such blog.")
        cap = c.plan.limit("reviewers_required") or 0
        db.update_site(sid, {"config": {**(row.get("config") or {}), "required_reviewers": min(body.required_reviewers, cap)}})
        db.audit(c.wid, c.uid, "site.approval_rule", row["name"], {"required_reviewers": min(body.required_reviewers, cap)})
        return {"ok": True}

    @app.delete("/api/sites/{sid}", status_code=204)
    def disconnect_site(sid: int, c: Ctx = Depends(ctx)) -> Response:
        c.require("manage_sites")
        row = db.site(sid)
        if not row or row["workspace_id"] != c.wid or row.get("local_root"):
            raise HTTPException(404, "No such hosted blog.")
        db.delete_site(sid)
        db.audit(c.wid, c.uid, "site.disconnected", row["name"])
        return Response(status_code=204)

    # API key (bring your own) -------------------------------------------------
    @app.put("/api/credentials/anthropic")
    def set_key(body: KeyIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("manage_keys")
        if not body.key.startswith("sk-ant-"):
            raise HTTPException(422, "That doesn't look like an Anthropic API key.")
        try:
            db.save_credential(c.wid, "anthropic", crypto.encrypt(body.key.strip()), crypto.last4(body.key.strip()), c.uid)
        except crypto.SecretError as e:
            raise HTTPException(500, str(e)) from e
        models.clear()
        db.audit(c.wid, c.uid, "key.saved", "anthropic")
        return {"last4": crypto.last4(body.key.strip())}

    @app.delete("/api/credentials/anthropic", status_code=204)
    def delete_key(c: Ctx = Depends(ctx)) -> Response:
        c.require("manage_keys")
        db.delete_credential(c.wid, "anthropic")
        models.clear()
        db.audit(c.wid, c.uid, "key.deleted", "anthropic")
        return Response(status_code=204)

    # Billing ---------------------------------------------------------------------
    @app.get("/api/billing")
    def billing_state(c: Ctx = Depends(ctx)) -> dict[str, Any]:
        sub = c.sub
        return {
            "enabled": gateway is not None,
            "plan": c.plan.id,
            "status": sub.get("status"),
            "seats": sub.get("seats"),
            "current_period_end": sub.get("current_period_end"),
            "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
            "has_customer": bool(sub.get("stripe_customer_id")),
            "can_manage": c.can("manage_billing"),
        }

    @app.post("/api/billing/checkout")
    def checkout(body: CheckoutIn, c: Ctx = Depends(ctx)) -> dict[str, str]:
        c.require("manage_billing")
        if not gateway:
            raise HTTPException(503, "Billing isn't configured on this server.")
        plan = plans.get(body.plan)
        seats = max(plan.min_seats, db.seat_count(c.wid))
        first_time = not c.sub.get("stripe_subscription_id")
        try:
            out = gateway.checkout(
                customer=c.sub.get("stripe_customer_id"), workspace_id=c.wid, email_hint=None,
                lookup_key=f"{plan.id}_{body.interval}", seats=seats, trial=first_time and plan.id == "team",
                success_url=f"{settings.base_url}/#/settings/billing?checkout=done", cancel_url=f"{settings.base_url}/#/settings/billing",
            )
        except billing.BillingError as e:
            raise HTTPException(502, str(e)) from e
        db.save_subscription(c.wid, {"stripe_customer_id": out["customer"]})
        db.audit(c.wid, c.uid, "billing.checkout_started", plan.id, {"interval": body.interval, "seats": seats})
        return {"url": out["url"]}

    @app.post("/api/billing/portal")
    def portal(c: Ctx = Depends(ctx)) -> dict[str, str]:
        c.require("manage_billing")
        if not gateway or not c.sub.get("stripe_customer_id"):
            raise HTTPException(409, "There's no subscription to manage yet.")
        return {"url": gateway.portal(customer=c.sub["stripe_customer_id"], return_url=f"{settings.base_url}/#/settings/billing")}

    @app.post("/api/stripe/webhook")
    async def stripe_webhook(request: Request) -> dict[str, str]:
        if not gateway:
            raise HTTPException(503, "Billing isn't configured.")
        try:
            event = gateway.verify(await request.body(), request.headers.get("stripe-signature"))
        except billing.BillingError as e:
            raise HTTPException(400, str(e)) from e
        return {"result": billing.handle_event(db, event)}

    # Audit log -------------------------------------------------------------------
    @app.get("/api/audit")
    def audit(c: Ctx = Depends(ctx)) -> list[dict[str, Any]]:
        c.require("view_audit")
        c.feature("audit_log")
        return db.audit_entries(c.wid)

    # Campaigns -------------------------------------------------------------------
    @app.get("/api/campaigns")
    def list_campaigns(c: Ctx = Depends(ctx)) -> list[dict[str, Any]]:
        return c.store.campaigns() if c.store else []

    @app.post("/api/campaigns", status_code=201)
    def create_campaign(body: CampaignIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("campaigns")
        c.feature("campaigns")
        _, store = c.need_site()
        series = body.series_name or (body.name if body.kind == "series" else None)
        return store.create_campaign(body.name, body.kind, body.description, series)

    @app.patch("/api/campaigns/{cid}")
    def update_campaign(cid: int, body: CampaignPatch, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("campaigns")
        _, store = c.need_site()
        if not store.campaign(cid):
            raise HTTPException(404, "No such campaign.")
        return store.update_campaign(cid, body.model_dump(exclude_unset=True))  # type: ignore[return-value]

    @app.delete("/api/campaigns/{cid}", status_code=204)
    def delete_campaign(cid: int, c: Ctx = Depends(ctx)) -> Response:
        c.require("campaigns")
        _, store = c.need_site()
        store.delete_campaign(cid)
        return Response(status_code=204)

    # Posts -----------------------------------------------------------------------
    @app.get("/api/posts")
    def list_posts(c: Ctx = Depends(ctx)) -> list[dict[str, Any]]:
        return [view(c, p) for p in c.store.posts()] if c.store else []

    @app.post("/api/posts", status_code=201)
    def create_post(body: PostIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("write")
        _, store = c.need_site()
        if body.campaign_id and not store.campaign(body.campaign_id):
            raise HTTPException(404, "No such campaign.")
        cap = None if c.local else c.plan.limit("posts_per_month")
        if cap is not None and db.posts_this_month(c.wid) >= cap:
            raise Upgrade(f"Your plan starts {cap} posts a month, and this month's are used.", plans.get("team"))
        names = [n.strip() for n in body.allowed_names if n.strip()]
        post = store.create_post(body.idea.strip(), body.notes, body.campaign_id, names, author_id=c.uid)
        db.audit(c.wid, c.uid, "post.created", body.idea.strip()[:80])
        return view(c, post)

    @app.get("/api/posts/{pid}")
    def read_post(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        return view(c, get_post(c, pid))

    @app.patch("/api/posts/{pid}")
    def update_post(pid: int, body: PostPatch, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("write")
        post = get_post(c, pid)
        fields = body.model_dump(exclude_unset=True)
        if fields.get("slug"):
            fields["slug"] = content.slugify(fields["slug"])
            if post.get("written") and fields["slug"] != post.get("slug"):
                raise HTTPException(409, "This post is already in the site under its current slug, so the slug can't change here.")
        if "allowed_names" in fields and fields["allowed_names"] is not None:
            fields["allowed_names"] = [n.strip() for n in fields["allowed_names"] if n.strip()]
        updated = c.store.update_post(pid, fields)  # type: ignore[union-attr]
        # Any content change invalidates the check and earlier approvals; a scheduled post drops back.
        if updated and body_hash(updated) != body_hash(post) and post["status"] in {"checked", "scheduled"}:
            updated = c.store.update_post(pid, {"status": "drafted", "check_ack": 0})  # type: ignore[union-attr]
        return view(c, updated)  # type: ignore[arg-type]

    @app.delete("/api/posts/{pid}", status_code=204)
    def delete_post(pid: int, c: Ctx = Depends(ctx)) -> Response:
        c.require("write")
        post = get_post(c, pid)
        if post.get("written"):
            raise HTTPException(409, "This post is already in the blog's repository. Remove it there if you mean to delete it.")
        c.store.delete_post(pid)  # type: ignore[union-attr]
        return Response(status_code=204)

    # AI steps --------------------------------------------------------------------
    @app.post("/api/posts/{pid}/outline")
    async def outline(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("use_ai")
        post = get_post(c, pid)
        try:
            result, usage = await model_for(c).outline(post, content.known_tags(c.site))  # type: ignore[arg-type]
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(c, pid, "outline", usage)
        fields: dict[str, Any] = {
            "outline": result.model_dump(), "title": result.title, "subtitle": result.subtitle,
            "summary": result.summary, "tags": result.tags, "tldr": result.tldr,
            "status": "outlined" if post["status"] == "idea" else post["status"],
        }
        if not post.get("written"):
            fields["slug"] = content.slugify(result.slug or result.title)
        return view(c, c.store.update_post(pid, fields))  # type: ignore[union-attr, arg-type]

    @app.post("/api/posts/{pid}/draft")
    async def draft(pid: int, c: Ctx = Depends(ctx)) -> StreamingResponse:
        c.require("use_ai")
        post = get_post(c, pid)
        if not post.get("outline"):
            raise HTTPException(409, "Generate or write an outline first.")
        reference = content.style_reference(c.site)  # type: ignore[arg-type]
        writer = model_for(c)
        store = c.store

        async def events() -> AsyncIterator[str]:
            usages: list[Usage] = []
            text = ""
            try:
                async for delta in writer.draft(post, reference, usages):
                    text += delta
                    yield f"event: delta\ndata: {json.dumps({'text': delta})}\n\n"
            except AIError as e:
                for u in usages:
                    log(c, pid, "draft", u)
                if text:
                    store.update_post(pid, {"body": text})  # type: ignore[union-attr]
                yield f"event: error\ndata: {json.dumps({'message': str(e), 'partial': bool(text)})}\n\n"
                return
            for u in usages:
                log(c, pid, "draft", u)
            body = text.strip()
            if body.startswith("```"):
                body = body.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            updated = store.update_post(pid, {"body": body, "status": "drafted", "check_result": None, "check_ack": 0})  # type: ignore[union-attr]
            yield f"event: done\ndata: {json.dumps(view(c, updated))}\n\n"  # type: ignore[arg-type]

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/api/posts/{pid}/check")
    async def check(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("use_ai")
        site, store = c.need_site()
        post = get_post(c, pid)
        if not post.get("body"):
            raise HTTPException(409, "There's no draft to check yet.")
        try:
            result, usage = await model_for(c).check(post)
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(c, pid, "check", usage)
        text = "\n".join(str(post.get(k) or "") for k in ("title", "subtitle", "summary", "body"))
        found = [f.model_dump() for f in result.findings] + checks.scan(text, site.site_url)
        verdict = "block" if any(f["severity"] == "high" for f in found) else ("review" if any(f["severity"] == "medium" for f in found) else "clear")
        try:
            fm = content.frontmatter(site, post, campaign_of(c, post), draft=True, on=date.today())
            content.validate_mdx(site, fm + post["body"])
            mdx_error = None
        except content.ContentError as e:
            mdx_error = str(e)
            verdict = "block"
        payload = {"verdict": verdict, "findings": found, "mdx_error": mdx_error, "hash": body_hash(post)}
        status = post["status"] if post["status"] in {"scheduled", "published"} else "checked"
        db.audit(c.wid, c.uid, "post.checked", post.get("title") or post["idea"][:80], {"verdict": verdict, "findings": len(found)})
        return view(c, store.update_post(pid, {"check_result": payload, "check_ack": 0, "status": status}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/check/ack")
    def acknowledge(pid: int, body: AckIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("write")
        post = get_post(c, pid)
        result = post.get("check_result") or {}
        if result.get("mdx_error") or any(f["severity"] == "high" for f in result.get("findings", [])):
            raise HTTPException(409, "High-severity findings and MDX errors have to be fixed, not confirmed.")
        return view(c, c.store.update_post(pid, {"check_ack": 1 if body.acknowledged else 0}))  # type: ignore[union-attr, arg-type]

    @app.post("/api/posts/{pid}/review")
    def review(pid: int, body: ReviewIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("review")
        c.feature("review_workflow")
        post = get_post(c, pid)
        if post.get("author_id") == c.uid:
            raise HTTPException(409, "Someone other than the author has to review a post.")
        db.set_approval(pid, c.uid, body.decision, body.note, body_hash(post))
        db.audit(c.wid, c.uid, f"post.review_{body.decision}", post.get("title") or "", {"note": body.note})
        return view(c, get_post(c, pid))

    @app.post("/api/posts/{pid}/thumbnail")
    async def thumbnail(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("use_ai")
        post = get_post(c, pid)
        if not post.get("body"):
            raise HTTPException(409, "Write the draft first; the diagram is drawn from it.")
        try:
            spec, usage = await model_for(c).thumbnail(post)
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(c, pid, "thumbnail", usage)
        return view(c, c.store.update_post(pid, {"thumb_spec": spec.model_dump()}))  # type: ignore[union-attr, arg-type]

    @app.get("/api/posts/{pid}/thumbnail.svg")
    def thumbnail_file(pid: int, c: Ctx = Depends(ctx)) -> Response:
        svg = thumbnail_svg(c, get_post(c, pid))
        if not svg:
            raise HTTPException(404, "No thumbnail yet.")
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

    @app.post("/api/posts/{pid}/social")
    async def social(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("use_ai")
        c.feature("distribution_copy")
        post = get_post(c, pid)
        if not post.get("body") or not post.get("slug"):
            raise HTTPException(409, "Write the draft first.")
        try:
            result, usage = await model_for(c).social(post, c.site.public(post["slug"]) or post["slug"])  # type: ignore[union-attr]
        except AIError as e:
            raise HTTPException(502, str(e)) from e
        log(c, pid, "social", usage)
        return view(c, c.store.update_post(pid, {"social": result.model_dump()}))  # type: ignore[union-attr, arg-type]

    # Writing to the blog ---------------------------------------------------------
    @app.post("/api/posts/{pid}/preview")
    async def preview(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        """Writes the post as a draft: into the local repo, or onto its pull request branch."""
        c.require("write")
        site, store = c.need_site()
        post = get_post(c, pid)
        if post["status"] == "published":
            raise HTTPException(409, "This post is live. Use Publish to update it.")
        try:
            files = content.build_files(site, post, campaign_of(c, post), thumbnail_svg(c, post), draft=True, on=date.today())
            pub = publisher_for(c.site_row, site)  # type: ignore[arg-type]
            if c.local:
                await pub.write_draft(files)
                pr_url = None
            else:
                pr_url = (await pub.publish(files, post["slug"], f"Draft: {post['title']}", f"Draft: {post['title']}")).pr_url
        except content.ContentError as e:
            raise HTTPException(409, str(e)) from e
        return view(c, store.update_post(pid, {"written": 1, "pr_url": pr_url} if pr_url else {"written": 1}))  # type: ignore[arg-type]

    @app.post("/api/posts/{pid}/schedule")
    def schedule(pid: int, body: ScheduleIn, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("publish")
        c.feature("scheduling")
        post = get_post(c, pid)
        require_gate(c, post)
        if body.publish_at < date.today():
            raise HTTPException(422, "Pick today or a future date.")
        db.audit(c.wid, c.uid, "post.scheduled", post.get("title") or "", {"publish_at": body.publish_at.isoformat()})
        return view(c, c.store.update_post(pid, {"status": "scheduled", "publish_at": body.publish_at.isoformat(), "last_error": None}))  # type: ignore[union-attr, arg-type]

    @app.post("/api/posts/{pid}/unschedule")
    def unschedule(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("publish")
        post = get_post(c, pid)
        if post["status"] != "scheduled":
            raise HTTPException(409, "This post isn't scheduled.")
        return view(c, c.store.update_post(pid, {"status": "checked", "publish_at": None}))  # type: ignore[union-attr, arg-type]

    @app.post("/api/posts/{pid}/publish")
    async def publish(pid: int, c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("publish")
        return view(c, await do_publish(c, get_post(c, pid), date.today()))

    @app.post("/api/scheduler/run")
    async def scheduler_run(c: Ctx = Depends(ctx)) -> dict[str, Any]:
        c.require("publish")
        return {"published": await run_due(c)}

    # Sign-in -------------------------------------------------------------------------
    def on_sign_in(user: dict[str, Any]) -> None:
        for wid in db.accept_invites(user):
            db.audit(wid, user["id"], "member.joined", user["login"])
        if not db.workspaces_for(user["id"]):
            db.create_workspace(f"{user['login']}'s workspace", user["id"])

    client_id, client_secret = os.environ.get("GITHUB_CLIENT_ID"), os.environ.get("GITHUB_CLIENT_SECRET")
    if settings.cloud and client_id and client_secret:
        cfg = auth.AuthConfig(client_id, client_secret, settings.base_url)
        app.include_router(auth.router(cfg, db, on_sign_in, http=oauth_http) if oauth_http else auth.router(cfg, db, on_sign_in))

    app.mount("/", StaticFiles(directory=STUDIO_DIR / "ui", html=True), name="ui")
    return app


def main() -> None:  # kept for `python -m blog_studio.server`
    from .cli import main as cli_main

    cli_main()


__all__ = ["ConfigError", "create_app"]
