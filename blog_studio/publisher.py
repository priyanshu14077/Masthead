"""Where a post's files go. Local mode: commit to the repo on disk. Hosted mode: a GitHub pull request."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Site
from .content import ContentError
from .github_app import GitHubApp, GitHubError


@dataclass
class Published:
    sha: str
    pr_url: str | None = None


class Publisher(Protocol):
    async def write_draft(self, files: dict[str, str]) -> None: ...
    async def publish(self, files: dict[str, str], slug: str, title: str, message: str) -> Published: ...
    def branch(self) -> str: ...


class LocalGitPublisher:
    """Writes into a repo on this machine and commits exactly those files. Never pushes."""

    def __init__(self, site: Site):
        self.site = site
        self.root = site.root

    def _git(self, *args: str) -> str:
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, timeout=60, check=False)
        if r.returncode != 0:
            raise ContentError(f"git {args[0]} failed: {r.stderr.strip() or r.stdout.strip()}")
        return r.stdout.strip()

    def branch(self) -> str:
        try:
            return self._git("branch", "--show-current")
        except ContentError:
            return ""

    def _write(self, files: dict[str, str]) -> list[Path]:
        written = []
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            written.append(path)
        return written

    async def write_draft(self, files: dict[str, str]) -> None:
        self._write(files)

    async def publish(self, files: dict[str, str], slug: str, title: str, message: str) -> Published:
        branch = self.branch()
        if not branch:
            raise ContentError("The repository isn't on a branch, so nothing was committed.")
        if branch in self.site.protected_branches:
            raise ContentError(f"You're on {branch}, which deploys the live site. Switch to a working branch first.")
        rel = [str(p.relative_to(self.root)) for p in self._write(files)]
        self._git("add", "--", *rel)
        self._git("commit", "-m", message, "--only", "--", *rel)
        return Published(sha=self._git("rev-parse", "--short", "HEAD"))


class GitHubPublisher:
    """Opens (or updates) a pull request with the post on branch masthead/<slug>."""

    def __init__(self, app: GitHubApp, site: Site, installation_id: int, repo: str, base: str):
        self.app, self.site, self.installation_id, self.repo, self.base = app, site, installation_id, repo, base

    def branch(self) -> str:
        return self.base

    async def write_draft(self, files: dict[str, str]) -> None:
        # Hosted previews go on the pull request branch; the blog's own preview deploys show them.
        await self.publish(files, slug=_slug_of(files), title="Draft", message="Masthead draft preview")

    async def publish(self, files: dict[str, str], slug: str, title: str, message: str) -> Published:
        try:
            client = await self.app.repo(self.installation_id, self.repo)
            out = await client.publish(
                files, branch=f"masthead/{slug}", base=self.base, message=message, title=title,
                body="Opened by Masthead. Merge to publish.",
            )
        except GitHubError as e:
            raise ContentError(str(e)) from e
        return Published(sha=out["sha"][:7], pr_url=out["pr_url"])


def _slug_of(files: dict[str, str]) -> str:
    first = next(iter(files))
    return first.rsplit("/", 1)[-1].removesuffix(".mdx")
