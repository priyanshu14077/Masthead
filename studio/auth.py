"""Sign in with GitHub (OAuth 2.0 authorization code flow with PKCE).

Built step by step. Step 2: the login redirect, and a temporary callback that shows what came back.
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
STATE_COOKIE = "studio_oauth_state"
PENDING_TTL = 600  # seconds a login attempt stays valid


@dataclass
class Pending:
    """One login attempt in flight: created at /auth/login, consumed at /auth/callback."""

    verifier: str
    created: float


def pkce_pair() -> tuple[str, str]:
    """The PKCE verifier (kept here) and its challenge (sent to GitHub).

    The challenge is base64url(SHA-256(verifier)) with the padding stripped, per RFC 7636.
    """
    verifier = secrets.token_urlsafe(64)  # 86 characters, inside the spec's 43 to 128
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def router(port: int) -> APIRouter:
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
    # In memory on purpose: a restart simply cancels any login that was half way through.
    pending: dict[str, Pending] = {}

    r = APIRouter(prefix="/auth")

    @r.get("/login")
    def login() -> RedirectResponse:
        now = time.time()
        for key in [k for k, p in pending.items() if now - p.created > PENDING_TTL]:
            del pending[key]

        state = secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        pending[state] = Pending(verifier=verifier, created=now)

        query = urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "",  # no scope: the token can only read public profile data
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "allow_signup": "false",
        })
        response = RedirectResponse(f"{AUTHORIZE_URL}?{query}", status_code=302)
        # Ties this login attempt to this browser. Only sent back on /auth/* requests.
        response.set_cookie(STATE_COOKIE, state, max_age=PENDING_TTL, httponly=True, samesite="lax", path="/auth")
        return response

    @r.get("/callback")
    def callback(request: Request) -> HTMLResponse:
        # Temporary for step 2: show what arrived and whether the state checks pass. Step 3 replaces this.
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")
        cookie_state = request.cookies.get(STATE_COOKIE)
        attempt = pending.get(state or "")

        rows = [
            ("GitHub error", error or "none"),
            ("code received", f"yes, {len(code)} characters" if code else "no"),
            ("state in the URL", state or "missing"),
            ("state in your cookie", cookie_state or "missing"),
            ("they match", "yes" if state and state == cookie_state else "NO"),
            ("we started this attempt", "yes" if attempt else "NO"),
            ("attempt age", f"{time.time() - attempt.created:.0f}s" if attempt else "n/a"),
        ]
        # Everything here can come from a crafted URL, so it is escaped before it touches HTML.
        body = "".join(f"<tr><th>{k}</th><td>{html.escape(v)}</td></tr>" for k, v in rows)
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>Callback check</title>"
            "<body style='font:16px system-ui;padding:40px;background:#f2ede2;color:#26364f'>"
            "<h1 style='font-weight:500'>Step 2: what came back from GitHub</h1>"
            f"<table cellpadding=8>{body}</table>"
            "<p>The code hasn't been exchanged. That's step 3.</p></body>"
        )

    return r
