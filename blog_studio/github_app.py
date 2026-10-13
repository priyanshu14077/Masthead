"""The Masthead GitHub App: reads a blog's config from its repo and opens a pull request per post.

The App authenticates as itself with a short-lived JWT signed by its private key, then exchanges that
for an installation token scoped to the repos a customer chose. Permissions needed: Contents (read
and write), Pull requests (read and write), Metadata (read).
"""

from __future__ import annotations

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import jwt

API = "https://api.github.com"


class GitHubError(Exception):
    pass


@dataclass(frozen=True)
class AppConfig:
    app_id: str
    private_key: str  # PEM
    slug: str  # for the install link: https://github.com/apps/<slug>/installations/new

    @property
    def install_url(self) -> str:
        return f"https://github.com/apps/{self.slug}/installations/new"


class GitHubApp:
    def __init__(self, config: AppConfig, http: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(timeout=20)):
        self.config = config
        self.http = http
        self._tokens: dict[int, tuple[str, float]] = {}

    def app_jwt(self) -> str:
        now = int(time.time())
        # Backdated a minute for clock drift; GitHub allows at most ten minutes.
        return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.config.app_id}, self.config.private_key, algorithm="RS256")

    async def installation_token(self, installation_id: int) -> str:
        cached = self._tokens.get(installation_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        async with self.http() as c:
            r = await c.post(f"{API}/app/installations/{installation_id}/access_tokens", headers=self._headers(self.app_jwt()))
        if r.status_code != 201:
            raise GitHubError(f"Couldn't get an installation token ({r.status_code}). Is the app still installed?")
        token = r.json()["token"]
        self._tokens[installation_id] = (token, time.time() + 3000)  # tokens last an hour
        return token

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"authorization": f"Bearer {token}", "accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28"}

    async def installation_account(self, installation_id: int) -> dict[str, str]:
        """Which GitHub account (user or organisation) installed the app."""
        async with self.http() as c:
            r = await c.get(f"{API}/app/installations/{installation_id}", headers=self._headers(self.app_jwt()))
        if r.status_code != 200:
            raise GitHubError("That installation doesn't exist, or the app was uninstalled.")
        account = r.json()["account"]
        return {"login": account["login"], "type": account["type"]}

    async def can_use(self, installation_id: int, login: str) -> bool:
        """True if `login` is the installing user, or a member of the installing organisation."""
        account = await self.installation_account(installation_id)
        if account["login"].lower() == login.lower():
            return True
        if account["type"] != "Organization":
            return False
        token = await self.installation_token(installation_id)
        async with self.http() as c:
            r = await c.get(f"{API}/orgs/{account['login']}/members/{login}", headers=self._headers(token))
        return r.status_code == 204  # needs the app's "Members: read" organisation permission

    async def repositories(self, installation_id: int) -> list[dict[str, str]]:
        token = await self.installation_token(installation_id)
        async with self.http() as c:
            r = await c.get(f"{API}/installation/repositories", headers=self._headers(token), params={"per_page": 100})
        if r.status_code != 200:
            raise GitHubError(f"Couldn't list repositories ({r.status_code}).")
        return [{"full_name": x["full_name"], "default_branch": x["default_branch"]} for x in r.json()["repositories"]]

    async def repo(self, installation_id: int, repo: str) -> RepoClient:
        return RepoClient(self, await self.installation_token(installation_id), repo)


class RepoClient:
    def __init__(self, app: GitHubApp, token: str, repo: str):
        self.app = app
        self.headers = GitHubApp._headers(token)
        self.repo = repo

    async def _call(self, method: str, path: str, ok: tuple[int, ...] = (200,), **kw):  # type: ignore[no-untyped-def]
        async with self.app.http() as c:
            r = await c.request(method, f"{API}/repos/{self.repo}{path}", headers=self.headers, **kw)
        if r.status_code not in ok:
            raise GitHubError(f"GitHub {method} {path} returned {r.status_code}: {r.text[:200]}")
        return r

    async def default_branch(self) -> str:
        return (await self._call("GET", "")).json()["default_branch"]

    async def read(self, path: str, ref: str) -> str | None:
        r = await self._call("GET", f"/contents/{path}", ok=(200, 404), params={"ref": ref})
        if r.status_code == 404:
            return None
        data = r.json()
        return base64.b64decode(data["content"]).decode() if isinstance(data, dict) and data.get("encoding") == "base64" else None

    async def list_dir(self, path: str, ref: str) -> list[str]:
        r = await self._call("GET", f"/contents/{path}", ok=(200, 404), params={"ref": ref})
        if r.status_code == 404 or not isinstance(r.json(), list):
            return []
        return [item["path"] for item in r.json() if item["type"] == "file"]

    async def publish(self, files: dict[str, str], branch: str, base: str, message: str, title: str, body: str) -> dict[str, str]:
        """One commit with every file on `branch` (created from `base`), then a pull request into `base`."""
        base_sha = (await self._call("GET", f"/git/ref/heads/{base}")).json()["object"]["sha"]
        base_tree = (await self._call("GET", f"/git/commits/{base_sha}")).json()["tree"]["sha"]
        tree = await self._call(
            "POST", "/git/trees", ok=(201,),
            json={"base_tree": base_tree, "tree": [{"path": p, "mode": "100644", "type": "blob", "content": c} for p, c in files.items()]},
        )
        commit = await self._call("POST", "/git/commits", ok=(201,), json={"message": message, "tree": tree.json()["sha"], "parents": [base_sha]})
        sha = commit.json()["sha"]
        exists = await self._call("GET", f"/git/ref/heads/{branch}", ok=(200, 404))
        if exists.status_code == 404:
            await self._call("POST", "/git/refs", ok=(201,), json={"ref": f"refs/heads/{branch}", "sha": sha})
        else:
            await self._call("PATCH", f"/git/refs/heads/{branch}", json={"sha": sha, "force": True})
        owner = self.repo.split("/")[0]
        open_prs = (await self._call("GET", "/pulls", params={"head": f"{owner}:{branch}", "state": "open"})).json()
        if open_prs:
            return {"sha": sha, "pr_url": open_prs[0]["html_url"]}
        pr = await self._call("POST", "/pulls", ok=(201,), json={"title": title, "head": branch, "base": base, "body": body})
        return {"sha": sha, "pr_url": pr.json()["html_url"]}
