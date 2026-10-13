"""Sign in with GitHub: the OAuth 2.0 authorization code flow with PKCE, then a server-side session.

Steps, as built in the walkthrough:
  2. /auth/login sends the browser to GitHub with `state` and a PKCE challenge.
  3. /auth/callback checks `state` (URL, cookie and our pending list must agree) and that the
     response came from GitHub (`iss`), then exchanges the code plus the PKCE verifier for a token.
  4. The token is used once, server to server, to read who signed in (GET /user). It is not stored:
     Masthead only needs your identity, not ongoing access to your GitHub account.
  5. We create a session row and give the browser an opaque, HttpOnly session cookie.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .db import DB

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
ISSUER = "https://github.com/login/oauth"
STATE_COOKIE = "masthead_oauth_state"
SESSION_COOKIE = "masthead_session"
PENDING_TTL = 600


@dataclass
class Pending:
    verifier: str
    created: float
    next_path: str


@dataclass(frozen=True)
class AuthConfig:
    client_id: str
    client_secret: str
    base_url: str  # where the app is served, e.g. http://127.0.0.1:8787 or https://app.masthead.example

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}/auth/callback"

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _safe_next(path: str | None) -> str:
    # Only same-site relative paths, so the login can't be used as an open redirect.
    return path if path and path.startswith("/") and not path.startswith("//") else "/"


def router(
    config: AuthConfig,
    db: DB,
    on_sign_in: Callable[[dict[str, Any]], None],
    http: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(timeout=15),
) -> APIRouter:
    pending: dict[str, Pending] = {}
    r = APIRouter(prefix="/auth")
    canonical_host = config.base_url.split("://", 1)[1].split("/")[0]

    @r.get("/login")
    def login(request: Request, next: str | None = None) -> RedirectResponse:
        # The state cookie belongs to one host, and GitHub returns to the registered one: start there.
        if request.headers.get("host", canonical_host) != canonical_host and "testserver" not in request.headers.get("host", ""):
            return RedirectResponse(f"{config.base_url}/auth/login?{urlencode({'next': _safe_next(next)})}", status_code=302)
        now = time.time()
        for key in [k for k, p in pending.items() if now - p.created > PENDING_TTL]:
            del pending[key]
        state = secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        pending[state] = Pending(verifier=verifier, created=now, next_path=_safe_next(next))
        query = urlencode({
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": "",  # identity only: public profile
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        response = RedirectResponse(f"{AUTHORIZE_URL}?{query}", status_code=302)
        response.set_cookie(STATE_COOKIE, state, max_age=PENDING_TTL, httponly=True, samesite="lax", secure=config.secure_cookies, path="/auth")
        return response

    def fail(reason: str) -> RedirectResponse:
        response = RedirectResponse(f"/#/signin?error={reason}", status_code=302)
        response.delete_cookie(STATE_COOKIE, path="/auth")
        return response

    @r.get("/callback")
    async def callback(request: Request) -> RedirectResponse:
        q = request.query_params
        state, code = q.get("state"), q.get("code")
        if q.get("error"):
            return fail("denied")
        # Step 3a: the same browser that started this login, and an attempt we issued (used once).
        if not state or state != request.cookies.get(STATE_COOKIE):
            return fail("state")
        attempt = pending.pop(state, None)
        if not attempt or time.time() - attempt.created > PENDING_TTL:
            return fail("expired")
        # Step 3b: the response names its issuer (RFC 9207); it must be GitHub.
        if q.get("iss") and q.get("iss") != ISSUER:
            return fail("issuer")
        if not code:
            return fail("code")
        async with http() as client:
            # Step 3c: code + client secret + PKCE verifier -> access token, server to server.
            res = await client.post(
                TOKEN_URL,
                headers={"accept": "application/json"},
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "redirect_uri": config.redirect_uri,
                    "code_verifier": attempt.verifier,
                },
            )
            token = res.json().get("access_token") if res.status_code == 200 else None
            if not token:
                return fail("exchange")
            # Step 4: who is this?
            me = await client.get(USER_URL, headers={"authorization": f"Bearer {token}", "accept": "application/vnd.github+json"})
            if me.status_code != 200:
                return fail("profile")
            profile = me.json()
        user = db.upsert_user(int(profile["id"]), profile["login"], profile.get("name"), profile.get("avatar_url"))
        on_sign_in(user)
        # Step 5: our own session; GitHub's token is discarded here.
        sid = db.create_session(user["id"])
        response = RedirectResponse(attempt.next_path, status_code=302)
        response.delete_cookie(STATE_COOKIE, path="/auth")
        response.set_cookie(SESSION_COOKIE, sid, max_age=30 * 86400, httponly=True, samesite="lax", secure=config.secure_cookies, path="/")
        return response

    @r.post("/logout")
    def logout(request: Request) -> RedirectResponse:
        sid = request.cookies.get(SESSION_COOKIE)
        if sid:
            db.delete_session(sid)
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    return r
