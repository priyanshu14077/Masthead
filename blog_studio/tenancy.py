"""Who is asking, in which workspace, with which role and plan, on which blog.

Every API route receives a Ctx. Routes state their rule in one line: `ctx.require("publish")`
for a role permission, `ctx.feature("scheduling")` for a plan feature.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from fastapi import HTTPException

from . import plans
from .config import Site
from .db import SiteStore

PERMISSIONS: dict[str, set[str]] = {
    "owner": {"write", "review", "publish", "use_ai", "campaigns", "manage_members", "manage_sites", "manage_billing", "manage_keys", "view_audit"},
    "editor": {"write", "review", "publish", "use_ai", "campaigns"},
    "writer": {"write", "use_ai", "campaigns"},
    "reviewer": {"review"},
}

ROLE_NAMES = {"owner": "owners", "editor": "editors", "writer": "writers", "reviewer": "reviewers"}


def prompt_site(site: Site, plan: plans.Plan, local: bool) -> Site:
    """The site as the prompts see it. The shared voice guide is the brand_voice feature; without it,
    drafts use Masthead's neutral house voice."""
    return site if local or plan.has("brand_voice") else replace(site, voice="")


class Upgrade(HTTPException):
    """402: the workspace's plan doesn't include this. Names the plan that does."""

    def __init__(self, message: str, plan: plans.Plan | None):
        suffix = f" It's on the {plan.name} plan." if plan else ""
        super().__init__(402, message + suffix, headers={"x-upgrade-to": plan.id if plan else ""})


@dataclass
class Ctx:
    user: dict[str, Any]
    workspace: dict[str, Any]
    role: str
    sub: dict[str, Any]
    plan: plans.Plan
    local: bool
    site_row: dict[str, Any] | None = None
    site: Site | None = None
    store: SiteStore | None = None

    def can(self, perm: str) -> bool:
        return perm in PERMISSIONS.get(self.role, set())

    def require(self, perm: str) -> None:
        if not self.can(perm):
            allowed = [ROLE_NAMES[r] for r, perms in PERMISSIONS.items() if perm in perms]
            raise HTTPException(403, f"Only {' and '.join(allowed)} can do that.")

    def feature(self, feature: str) -> None:
        if not self.plan.has(feature):
            raise Upgrade(f"{plans.feature_label(feature)} isn't included in your plan.", plans.cheapest_with(feature))

    def need_site(self) -> tuple[Site, SiteStore]:
        if not self.site or not self.store:
            raise HTTPException(409, "Connect a blog first, in Settings, Blogs.")
        return self.site, self.store

    @property
    def wid(self) -> int:
        return int(self.workspace["id"])

    @property
    def uid(self) -> int | None:
        # None for the scheduler, which acts for the workspace rather than a person.
        return int(self.user["id"]) if self.user.get("id") is not None else None
