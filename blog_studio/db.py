"""Storage. SQLAlchemy Core over SQLite (local, tests) or Postgres (hosted), chosen by URL.

Tenancy: users belong to workspaces through memberships; a workspace has sites (blogs);
campaigns and posts belong to a site. Every query that reads posts is scoped by site_id.
Lists and objects in post rows are stored as JSON text so both databases behave the same.
"""

from __future__ import annotations

import json
import secrets
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    create_engine,
    delete,
    func,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine

ROLES = ("owner", "editor", "writer", "reviewer")

meta = MetaData()

users = Table(
    "users", meta,
    Column("id", Integer, primary_key=True),
    Column("github_id", Integer, unique=True),
    Column("login", String(100), nullable=False),
    Column("name", String(200)),
    Column("avatar_url", Text),
    Column("created_at", String(40), nullable=False),
)

sessions = Table(
    "sessions", meta,
    Column("id", String(64), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", String(40), nullable=False),
)

workspaces = Table(
    "workspaces", meta,
    Column("id", Integer, primary_key=True),
    Column("name", String(120), nullable=False),
    Column("slug", String(120), unique=True, nullable=False),
    Column("created_at", String(40), nullable=False),
)

memberships = Table(
    "memberships", meta,
    Column("id", Integer, primary_key=True),
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("workspace_id", "user_id"),
)

invites = Table(
    "invites", meta,
    Column("id", Integer, primary_key=True),
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("github_login", String(100), nullable=False),
    Column("role", String(20), nullable=False),
    Column("created_by", Integer, ForeignKey("users.id")),
    Column("created_at", String(40), nullable=False),
    Column("accepted_at", String(40)),
    UniqueConstraint("workspace_id", "github_login"),
)

sites = Table(
    "sites", meta,
    Column("id", Integer, primary_key=True),
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(120), nullable=False),
    Column("repo_full_name", String(200)),  # owner/repo, for hosted sites
    Column("installation_id", Integer),  # the GitHub App installation that can write to it
    Column("default_branch", String(100)),
    Column("local_root", Text),  # a path on disk, for local sites
    Column("config", Text),  # the site's blog-studio.toml settings and prompt files, as JSON (hosted)
    Column("created_at", String(40), nullable=False),
)

subscriptions = Table(
    "subscriptions", meta,
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
    Column("stripe_customer_id", String(100)),
    Column("stripe_subscription_id", String(100)),
    Column("plan", String(20), nullable=False, default="free"),
    Column("status", String(30), nullable=False, default="none"),
    Column("seats", Integer, nullable=False, default=1),
    Column("current_period_end", String(40)),
    Column("cancel_at_period_end", Integer, nullable=False, default=0),
    Column("updated_at", String(40), nullable=False),
)

stripe_events = Table(
    "stripe_events", meta,
    Column("id", String(100), primary_key=True),  # webhook idempotency
    Column("type", String(80), nullable=False),
    Column("received_at", String(40), nullable=False),
)

credentials = Table(
    "credentials", meta,
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
    Column("provider", String(30), primary_key=True),
    Column("ciphertext", Text, nullable=False),
    Column("last4", String(8), nullable=False),
    Column("created_by", Integer, ForeignKey("users.id")),
    Column("created_at", String(40), nullable=False),
)

audit_log = Table(
    "audit_log", meta,
    Column("id", Integer, primary_key=True),
    Column("workspace_id", Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("action", String(60), nullable=False),
    Column("target", String(200)),
    Column("detail", Text),
    Column("at", String(40), nullable=False),
)

campaigns = Table(
    "campaigns", meta,
    Column("id", Integer, primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id", ondelete="CASCADE")),
    Column("name", Text, nullable=False),
    Column("kind", String(20), nullable=False, default="series"),
    Column("description", Text, nullable=False, default=""),
    Column("series_name", Text),
    Column("created_at", String(40), nullable=False),
)

posts = Table(
    "posts", meta,
    Column("id", Integer, primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id", ondelete="CASCADE")),
    Column("author_id", Integer, ForeignKey("users.id")),
    Column("campaign_id", Integer, ForeignKey("campaigns.id", ondelete="SET NULL")),
    Column("status", String(20), nullable=False, default="idea"),
    Column("idea", Text, nullable=False),
    Column("notes", Text, nullable=False, default=""),
    Column("allowed_names", Text, nullable=False, default="[]"),
    Column("outline", Text),
    Column("title", Text),
    Column("slug", Text),
    Column("subtitle", Text),
    Column("summary", Text),
    Column("tags", Text, nullable=False, default="[]"),
    Column("tldr", Text, nullable=False, default="[]"),
    Column("series_order", Integer),
    Column("body", Text),
    Column("check_result", Text),
    Column("check_ack", Integer, nullable=False, default=0),
    Column("thumb_spec", Text),
    Column("social", Text),
    Column("publish_at", String(40)),
    Column("published_at", String(40)),
    Column("commit_sha", String(80)),
    Column("pr_url", Text),
    Column("written", Integer, nullable=False, default=0),
    Column("last_error", Text),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

approvals = Table(
    "approvals", meta,
    Column("id", Integer, primary_key=True),
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("decision", String(20), nullable=False),  # approved | changes
    Column("note", Text, nullable=False, default=""),
    Column("body_hash", String(32), nullable=False),  # approvals only count for the text they saw
    Column("at", String(40), nullable=False),
    UniqueConstraint("post_id", "user_id"),
)

ai_calls = Table(
    "ai_calls", meta,
    Column("id", Integer, primary_key=True),
    Column("workspace_id", Integer),
    Column("user_id", Integer),
    Column("post_id", Integer),
    Column("task", String(30), nullable=False),
    Column("model", String(60), nullable=False),
    Column("input_tokens", Integer, nullable=False, default=0),
    Column("output_tokens", Integer, nullable=False, default=0),
    Column("cache_read_tokens", Integer, nullable=False, default=0),
    Column("cost_usd", Float, nullable=False, default=0),
    Column("at", String(40), nullable=False),
)

POST_JSON = {"allowed_names", "outline", "tags", "tldr", "check_result", "thumb_spec", "social"}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _later(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat(timespec="seconds")


def _decode_post(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row._mapping)
    for key in POST_JSON & out.keys():
        if out[key] is not None:
            out[key] = json.loads(out[key])
    return out


def _encode_post(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: (json.dumps(v) if k in POST_JSON and v is not None else v) for k, v in fields.items()}


def _row(row: Any) -> dict[str, Any] | None:
    return dict(row._mapping) if row is not None else None


# Upgrading a database from the single-blog Studio ---------------------------
LEGACY_COLUMNS = {
    "posts": [("site_id", "INTEGER"), ("author_id", "INTEGER"), ("pr_url", "TEXT")],
    "campaigns": [("site_id", "INTEGER")],
    "ai_calls": [("workspace_id", "INTEGER"), ("user_id", "INTEGER")],
}


def upgrade_legacy(engine: Engine, db_path: Path | None) -> bool:
    """Adds the tenancy columns to a database created by the single-blog Studio.
    Backs the file up first. Returns True if anything changed."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    todo = []
    for table, cols in LEGACY_COLUMNS.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        todo += [(table, name, kind) for name, kind in cols if name not in have]
    if not todo:
        return False
    if db_path and db_path.exists():
        shutil.copy2(db_path, db_path.with_suffix(db_path.suffix + f".bak-{datetime.now():%Y%m%d-%H%M%S}"))
    with engine.begin() as conn:
        for table, name, kind in todo:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {kind}'))
    return True


class DB:
    def __init__(self, url: str):
        self.url = url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args, future=True)
        if url.startswith("sqlite"):
            with self.engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON"))
            path = Path(url.split("///", 1)[1]) if "///" in url else None
            self.upgraded = upgrade_legacy(self.engine, path)
        else:
            self.upgraded = False
        meta.create_all(self.engine)

    # Users and sessions -----------------------------------------------------
    def upsert_user(self, github_id: int, login: str, name: str | None, avatar_url: str | None) -> dict[str, Any]:
        with self.engine.begin() as c:
            row = c.execute(select(users).where(users.c.github_id == github_id)).first()
            if row:
                c.execute(update(users).where(users.c.id == row.id).values(login=login, name=name, avatar_url=avatar_url))
                uid = row.id
            else:
                uid = c.execute(insert(users).values(github_id=github_id, login=login, name=name, avatar_url=avatar_url, created_at=now())).inserted_primary_key[0]
            return _row(c.execute(select(users).where(users.c.id == uid)).first())  # type: ignore[return-value]

    def user(self, uid: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _row(c.execute(select(users).where(users.c.id == uid)).first())

    def create_session(self, user_id: int, days: int = 30) -> str:
        sid = secrets.token_urlsafe(32)
        with self.engine.begin() as c:
            c.execute(insert(sessions).values(id=sid, user_id=user_id, created_at=now(), expires_at=_later(days)))
        return sid

    def session_user(self, sid: str | None) -> dict[str, Any] | None:
        if not sid:
            return None
        with self.engine.connect() as c:
            row = c.execute(
                select(users).join(sessions, sessions.c.user_id == users.c.id).where(and_(sessions.c.id == sid, sessions.c.expires_at > now()))
            ).first()
            return _row(row)

    def delete_session(self, sid: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(sessions).where(sessions.c.id == sid))

    # Workspaces, members, invites --------------------------------------------
    def create_workspace(self, name: str, owner_id: int) -> dict[str, Any]:
        base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")[:60] or "workspace"
        with self.engine.begin() as c:
            slug, n = base, 1
            while c.execute(select(workspaces.c.id).where(workspaces.c.slug == slug)).first():
                n += 1
                slug = f"{base}-{n}"
            wid = c.execute(insert(workspaces).values(name=name, slug=slug, created_at=now())).inserted_primary_key[0]
            c.execute(insert(memberships).values(workspace_id=wid, user_id=owner_id, role="owner", created_at=now()))
            c.execute(insert(subscriptions).values(workspace_id=wid, plan="free", status="none", seats=1, updated_at=now()))
            return _row(c.execute(select(workspaces).where(workspaces.c.id == wid)).first())  # type: ignore[return-value]

    def workspaces_for(self, user_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(
                select(workspaces, memberships.c.role).join(memberships, memberships.c.workspace_id == workspaces.c.id).where(memberships.c.user_id == user_id).order_by(workspaces.c.id)
            ).all()
            return [_row(r) for r in rows]  # type: ignore[misc]

    def workspace(self, wid: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _row(c.execute(select(workspaces).where(workspaces.c.id == wid)).first())

    def membership(self, wid: int, user_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _row(c.execute(select(memberships).where(and_(memberships.c.workspace_id == wid, memberships.c.user_id == user_id))).first())

    def members(self, wid: int) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(
                select(users.c.id, users.c.login, users.c.name, users.c.avatar_url, memberships.c.role).join(memberships, memberships.c.user_id == users.c.id).where(memberships.c.workspace_id == wid).order_by(memberships.c.id)
            ).all()
            return [_row(r) for r in rows]  # type: ignore[misc]

    def seat_count(self, wid: int) -> int:
        """Members plus pending invites: a seat is anyone who can write or review."""
        with self.engine.connect() as c:
            m = c.execute(select(func.count()).select_from(memberships).where(memberships.c.workspace_id == wid)).scalar_one()
            i = c.execute(select(func.count()).select_from(invites).where(and_(invites.c.workspace_id == wid, invites.c.accepted_at.is_(None)))).scalar_one()
            return int(m) + int(i)

    def set_role(self, wid: int, user_id: int, role: str) -> None:
        with self.engine.begin() as c:
            c.execute(update(memberships).where(and_(memberships.c.workspace_id == wid, memberships.c.user_id == user_id)).values(role=role))

    def remove_member(self, wid: int, user_id: int) -> None:
        with self.engine.begin() as c:
            c.execute(delete(memberships).where(and_(memberships.c.workspace_id == wid, memberships.c.user_id == user_id)))

    def owners(self, wid: int) -> int:
        with self.engine.connect() as c:
            return int(c.execute(select(func.count()).select_from(memberships).where(and_(memberships.c.workspace_id == wid, memberships.c.role == "owner"))).scalar_one())

    def create_invite(self, wid: int, login: str, role: str, by: int) -> dict[str, Any]:
        with self.engine.begin() as c:
            c.execute(delete(invites).where(and_(invites.c.workspace_id == wid, invites.c.github_login == login.lower())))
            iid = c.execute(insert(invites).values(workspace_id=wid, github_login=login.lower(), role=role, created_by=by, created_at=now())).inserted_primary_key[0]
            return _row(c.execute(select(invites).where(invites.c.id == iid)).first())  # type: ignore[return-value]

    def pending_invites(self, wid: int) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            return [_row(r) for r in c.execute(select(invites).where(and_(invites.c.workspace_id == wid, invites.c.accepted_at.is_(None)))).all()]  # type: ignore[misc]

    def revoke_invite(self, wid: int, iid: int) -> None:
        with self.engine.begin() as c:
            c.execute(delete(invites).where(and_(invites.c.workspace_id == wid, invites.c.id == iid)))

    def accept_invites(self, user: dict[str, Any]) -> list[int]:
        """Joins every workspace that invited this GitHub login. Returns the workspace ids."""
        joined = []
        with self.engine.begin() as c:
            for inv in c.execute(select(invites).where(and_(invites.c.github_login == user["login"].lower(), invites.c.accepted_at.is_(None)))).all():
                exists = c.execute(select(memberships.c.id).where(and_(memberships.c.workspace_id == inv.workspace_id, memberships.c.user_id == user["id"]))).first()
                if not exists:
                    c.execute(insert(memberships).values(workspace_id=inv.workspace_id, user_id=user["id"], role=inv.role, created_at=now()))
                c.execute(update(invites).where(invites.c.id == inv.id).values(accepted_at=now()))
                joined.append(inv.workspace_id)
        return joined

    # Sites -----------------------------------------------------------------
    def create_site(self, wid: int, name: str, **fields: Any) -> dict[str, Any]:
        if "config" in fields and not isinstance(fields["config"], (str, type(None))):
            fields["config"] = json.dumps(fields["config"])
        with self.engine.begin() as c:
            sid = c.execute(insert(sites).values(workspace_id=wid, name=name, created_at=now(), **fields)).inserted_primary_key[0]
        return self.site(sid)  # type: ignore[return-value]

    def site(self, sid: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = _row(c.execute(select(sites).where(sites.c.id == sid)).first())
        if row and row.get("config"):
            row["config"] = json.loads(row["config"])
        return row

    def sites_for(self, wid: int) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            ids = [r.id for r in c.execute(select(sites.c.id).where(sites.c.workspace_id == wid).order_by(sites.c.id)).all()]
        return [self.site(i) for i in ids]  # type: ignore[misc]

    def update_site(self, sid: int, fields: dict[str, Any]) -> None:
        if "config" in fields and not isinstance(fields["config"], (str, type(None))):
            fields["config"] = json.dumps(fields["config"])
        with self.engine.begin() as c:
            c.execute(update(sites).where(sites.c.id == sid).values(**fields))

    def delete_site(self, sid: int) -> None:
        with self.engine.begin() as c:
            c.execute(delete(sites).where(sites.c.id == sid))

    def adopt_orphans(self, site_id: int) -> int:
        """Gives posts and campaigns from the single-blog Studio a home site."""
        with self.engine.begin() as c:
            n = c.execute(update(posts).where(posts.c.site_id.is_(None)).values(site_id=site_id)).rowcount
            c.execute(update(campaigns).where(campaigns.c.site_id.is_(None)).values(site_id=site_id))
            return int(n or 0)

    # Subscriptions -----------------------------------------------------------
    def subscription(self, wid: int) -> dict[str, Any]:
        with self.engine.connect() as c:
            row = _row(c.execute(select(subscriptions).where(subscriptions.c.workspace_id == wid)).first())
        return row or {"workspace_id": wid, "plan": "free", "status": "none", "seats": 1, "stripe_customer_id": None, "stripe_subscription_id": None, "current_period_end": None, "cancel_at_period_end": 0}

    def save_subscription(self, wid: int, fields: dict[str, Any]) -> None:
        fields = {**fields, "updated_at": now()}
        with self.engine.begin() as c:
            if c.execute(select(subscriptions.c.workspace_id).where(subscriptions.c.workspace_id == wid)).first():
                c.execute(update(subscriptions).where(subscriptions.c.workspace_id == wid).values(**fields))
            else:
                c.execute(insert(subscriptions).values(workspace_id=wid, **{"plan": "free", "status": "none", "seats": 1, **fields}))

    def workspace_by_customer(self, customer_id: str) -> int | None:
        with self.engine.connect() as c:
            row = c.execute(select(subscriptions.c.workspace_id).where(subscriptions.c.stripe_customer_id == customer_id)).first()
            return row.workspace_id if row else None

    def first_time_event(self, event_id: str, kind: str) -> bool:
        """Records a Stripe event id; False if it was already processed."""
        with self.engine.begin() as c:
            if c.execute(select(stripe_events.c.id).where(stripe_events.c.id == event_id)).first():
                return False
            c.execute(insert(stripe_events).values(id=event_id, type=kind, received_at=now()))
            return True

    # Credentials -------------------------------------------------------------
    def save_credential(self, wid: int, provider: str, ciphertext: str, last4: str, by: int | None) -> None:
        with self.engine.begin() as c:
            c.execute(delete(credentials).where(and_(credentials.c.workspace_id == wid, credentials.c.provider == provider)))
            c.execute(insert(credentials).values(workspace_id=wid, provider=provider, ciphertext=ciphertext, last4=last4, created_by=by, created_at=now()))

    def credential(self, wid: int, provider: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _row(c.execute(select(credentials).where(and_(credentials.c.workspace_id == wid, credentials.c.provider == provider))).first())

    def delete_credential(self, wid: int, provider: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(credentials).where(and_(credentials.c.workspace_id == wid, credentials.c.provider == provider)))

    # Audit log -------------------------------------------------------------------
    def audit(self, wid: int, user_id: int | None, action: str, target: str = "", detail: dict[str, Any] | None = None) -> None:
        with self.engine.begin() as c:
            c.execute(insert(audit_log).values(workspace_id=wid, user_id=user_id, action=action, target=target, detail=json.dumps(detail or {}), at=now()))

    def audit_entries(self, wid: int, limit: int = 200) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(
                select(audit_log, users.c.login).outerjoin(users, users.c.id == audit_log.c.user_id).where(audit_log.c.workspace_id == wid).order_by(audit_log.c.id.desc()).limit(limit)
            ).all()
        out = []
        for r in rows:
            d = _row(r)
            d["detail"] = json.loads(d["detail"] or "{}")  # type: ignore[index]
            out.append(d)
        return out  # type: ignore[return-value]

    # Approvals ---------------------------------------------------------------
    def set_approval(self, post_id: int, user_id: int, decision: str, note: str, body_hash: str) -> None:
        with self.engine.begin() as c:
            c.execute(delete(approvals).where(and_(approvals.c.post_id == post_id, approvals.c.user_id == user_id)))
            c.execute(insert(approvals).values(post_id=post_id, user_id=user_id, decision=decision, note=note, body_hash=body_hash, at=now()))

    def approvals_for(self, post_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(select(approvals, users.c.login).join(users, users.c.id == approvals.c.user_id).where(approvals.c.post_id == post_id).order_by(approvals.c.id)).all()
            return [_row(r) for r in rows]  # type: ignore[misc]

    # Campaigns and posts, scoped to a site ------------------------------------
    def for_site(self, site_id: int) -> SiteStore:
        return SiteStore(self, site_id)

    def due_posts(self, today: str) -> list[dict[str, Any]]:
        """Scheduled posts due today or earlier, across every site (the scheduler's view)."""
        with self.engine.connect() as c:
            rows = c.execute(select(posts).where(and_(posts.c.status == "scheduled", posts.c.publish_at.is_not(None), posts.c.publish_at <= today))).all()
            return [_decode_post(r) for r in rows]  # type: ignore[misc]

    def posts_this_month(self, wid: int) -> int:
        start = now()[:7] + "-01"
        with self.engine.connect() as c:
            return int(
                c.execute(
                    select(func.count()).select_from(posts).join(sites, sites.c.id == posts.c.site_id).where(and_(sites.c.workspace_id == wid, posts.c.created_at >= start))
                ).scalar_one()
            )

    # Usage ---------------------------------------------------------------------
    def log_call(self, wid: int | None, user_id: int | None, post_id: int | None, task: str, model: str, usage: dict[str, int], cost: float) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(ai_calls).values(
                    workspace_id=wid, user_id=user_id, post_id=post_id, task=task, model=model,
                    input_tokens=usage.get("input", 0), output_tokens=usage.get("output", 0), cache_read_tokens=usage.get("cache_read", 0),
                    cost_usd=cost, at=now(),
                )
            )

    def spend(self, wid: int | None) -> dict[str, Any]:
        cond = ai_calls.c.workspace_id == wid if wid is not None else text("1=1")
        with self.engine.connect() as c:
            total, calls = c.execute(select(func.coalesce(func.sum(ai_calls.c.cost_usd), 0), func.count()).where(cond)).one()
            month = c.execute(select(func.coalesce(func.sum(ai_calls.c.cost_usd), 0)).where(and_(cond, ai_calls.c.at >= now()[:7] + "-01"))).scalar_one()
        return {"total_usd": round(float(total), 4), "calls": int(calls), "month_usd": round(float(month), 4)}

    def post_spend(self, pid: int) -> float:
        with self.engine.connect() as c:
            return round(float(c.execute(select(func.coalesce(func.sum(ai_calls.c.cost_usd), 0)).where(ai_calls.c.post_id == pid)).scalar_one()), 4)


class SiteStore:
    """Campaigns and posts for one site. Every read and write is filtered by site_id."""

    def __init__(self, db: DB, site_id: int):
        self.db = db
        self.site_id = site_id
        self.engine = db.engine

    def campaigns(self) -> list[dict[str, Any]]:
        count = select(func.count()).select_from(posts).where(posts.c.campaign_id == campaigns.c.id).scalar_subquery()
        with self.engine.connect() as c:
            rows = c.execute(select(campaigns, count.label("post_count")).where(campaigns.c.site_id == self.site_id).order_by(campaigns.c.id)).all()
            return [_row(r) for r in rows]  # type: ignore[misc]

    def campaign(self, cid: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _row(c.execute(select(campaigns).where(and_(campaigns.c.id == cid, campaigns.c.site_id == self.site_id))).first())

    def create_campaign(self, name: str, kind: str, description: str, series_name: str | None) -> dict[str, Any]:
        with self.engine.begin() as c:
            cid = c.execute(insert(campaigns).values(site_id=self.site_id, name=name, kind=kind, description=description, series_name=series_name, created_at=now())).inserted_primary_key[0]
        return self.campaign(cid)  # type: ignore[return-value]

    def update_campaign(self, cid: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {k: v for k, v in fields.items() if k in {"name", "kind", "description", "series_name"}}
        if allowed:
            with self.engine.begin() as c:
                c.execute(update(campaigns).where(and_(campaigns.c.id == cid, campaigns.c.site_id == self.site_id)).values(**allowed))
        return self.campaign(cid)

    def delete_campaign(self, cid: int) -> None:
        with self.engine.begin() as c:
            c.execute(update(posts).where(posts.c.campaign_id == cid).values(campaign_id=None))
            c.execute(delete(campaigns).where(and_(campaigns.c.id == cid, campaigns.c.site_id == self.site_id)))

    def posts(self) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            rows = c.execute(select(posts).where(posts.c.site_id == self.site_id).order_by(func.coalesce(posts.c.publish_at, "9999"), posts.c.id)).all()
            return [_decode_post(r) for r in rows]  # type: ignore[misc]

    def post(self, pid: int) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            return _decode_post(c.execute(select(posts).where(and_(posts.c.id == pid, posts.c.site_id == self.site_id))).first())

    def create_post(self, idea: str, notes: str, campaign_id: int | None, allowed_names: list[str], author_id: int | None = None) -> dict[str, Any]:
        ts = now()
        with self.engine.begin() as c:
            pid = c.execute(
                insert(posts).values(site_id=self.site_id, author_id=author_id, idea=idea, notes=notes, campaign_id=campaign_id, allowed_names=json.dumps(allowed_names), created_at=ts, updated_at=ts)
            ).inserted_primary_key[0]
        return self.post(pid)  # type: ignore[return-value]

    def update_post(self, pid: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        if fields:
            enc = _encode_post(fields)
            enc["updated_at"] = now()
            with self.engine.begin() as c:
                c.execute(update(posts).where(and_(posts.c.id == pid, posts.c.site_id == self.site_id)).values(**enc))
        return self.post(pid)

    def delete_post(self, pid: int) -> None:
        with self.engine.begin() as c:
            c.execute(delete(posts).where(and_(posts.c.id == pid, posts.c.site_id == self.site_id)))
