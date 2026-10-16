"""Hosted mode: sign-in, workspaces and roles, plan gates, billing webhooks, API keys, GitHub pull requests."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from blog_studio import billing, crypto
from blog_studio.ai import FakeAI
from blog_studio.auth import SESSION_COOKIE
from blog_studio.config import Settings
from blog_studio.db import DB
from blog_studio.server import create_app

from .conftest import EXISTING

BASE = "http://testserver"
CONFIG = 'name = "Docs blog"\nsite_url = "https://docs.example"\n[paths]\nposts = "content/blog"\n'


class FakeRepo:
    def __init__(self) -> None:
        self.files = {"blog-studio.toml": CONFIG, "content/blog/designing-a-url-shortener.mdx": EXISTING}
        self.published: list[dict] = []

    async def read(self, path, ref):
        return self.files.get(path)

    async def list_dir(self, path, ref):
        return [p for p in self.files if p.startswith(path + "/")]

    async def publish(self, files, branch, base, message, title, body):
        self.published.append({"files": files, "branch": branch, "base": base, "title": title})
        return {"sha": "abc1234def", "pr_url": f"https://github.com/acme/docs/pull/{len(self.published)}"}


class FakeGitHub:
    """Installation 1 belongs to the acme org; alice and bob are members, mallory isn't."""

    class config:
        install_url = "https://github.com/apps/masthead/installations/new"

    def __init__(self) -> None:
        self.repo_client = FakeRepo()

    async def can_use(self, installation_id, login):
        return installation_id == 1 and login in {"alice", "bob"}

    async def repositories(self, installation_id):
        names = ["acme/docs", *(f"acme/blog-{i}" for i in range(1, 8))]
        return [{"full_name": n, "default_branch": "main"} for n in names]

    async def repo(self, installation_id, repo):
        return self.repo_client


class FakeGateway:
    def __init__(self) -> None:
        self.checkouts: list[dict] = []

    def checkout(self, **kw):
        self.checkouts.append(kw)
        return {"url": "https://checkout.stripe.test/s/1", "customer": kw["customer"] or "cus_1"}

    def portal(self, *, customer, return_url):
        return "https://billing.stripe.test/p/1"

    def verify(self, payload, signature):
        if signature != "good":
            raise billing.BillingError("Webhook signature check failed.")
        return json.loads(payload)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_SCHEDULER", "0")
    monkeypatch.setenv("MASTHEAD_SECRET_KEY", "x" * 40)
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    settings = Settings(mode="cloud", db_url=f"sqlite:///{tmp_path / 'cloud.db'}", port=8787, fake_ai=True, base_url=BASE)
    github, gateway = FakeGitHub(), FakeGateway()
    app = create_app(settings, ai=FakeAI(), gateway=gateway, github=github)  # type: ignore[arg-type]
    with TestClient(app) as c:
        yield {"app": app, "db": app.state.db, "github": github, "gateway": gateway, "client": c}


def sign_in(env, login: str, github_id: int) -> TestClient:
    """A browser signed in as `login` (the OAuth flow itself is tested separately)."""
    db: DB = env["db"]
    user = db.upsert_user(github_id, login, login.title(), None)
    db.accept_invites(user)
    if not db.workspaces_for(user["id"]):
        db.create_workspace(f"{login}'s workspace", user["id"])
    c = TestClient(env["app"])
    c.cookies.set(SESSION_COOKIE, db.create_session(user["id"]))
    return c


def make_team(env, plan="team", seats=5):
    """alice owns a workspace on `plan` with acme/docs connected."""
    alice = sign_in(env, "alice", 1)
    wid = alice.get("/api/state").json()["workspace"]["id"]
    env["db"].save_subscription(wid, {"plan": plan, "status": "active", "seats": seats})
    assert alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"}).status_code == 201
    return alice, wid


def write_and_check(c, pid):
    assert c.post(f"/api/posts/{pid}/outline").status_code == 200
    with c.stream("POST", f"/api/posts/{pid}/draft") as res:
        assert "event: done" in res.read().decode()
    assert c.post(f"/api/posts/{pid}/check").status_code == 200


# Sign-in -------------------------------------------------------------------------
def test_api_needs_a_session(env):
    assert env["client"].get("/api/state").status_code == 401
    assert env["client"].get("/api/me").json() == {"mode": "cloud", "user": None, "workspaces": [], "sign_in": "/auth/login"}


def test_oauth_flow_signs_in_with_pkce_and_creates_a_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_SCHEDULER", "0")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "cid")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "csecret")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            seen["token_form"] = parse_qs(request.content.decode())
            return httpx.Response(200, json={"access_token": "gho_test"})
        assert request.headers["authorization"] == "Bearer gho_test"
        return httpx.Response(200, json={"id": 42, "login": "octo", "name": "Octo Cat", "avatar_url": None})

    settings = Settings(mode="cloud", db_url=f"sqlite:///{tmp_path / 'o.db'}", port=8787, fake_ai=True, base_url=BASE)
    app = create_app(settings, ai=FakeAI(), oauth_http=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with TestClient(app, follow_redirects=False) as c:
        res = c.get("/auth/login?next=/app/%23/posts")
        q = parse_qs(urlparse(res.headers["location"]).query)
        assert q["code_challenge_method"] == ["S256"] and q["client_id"] == ["cid"]
        state = q["state"][0]
        res = c.get(f"/auth/callback?code=abc&state={state}&iss=https://github.com/login/oauth")
        assert res.status_code == 302 and res.headers["location"] == "/app/#/posts"
        verifier = seen["token_form"]["code_verifier"][0]
        assert hashlib.sha256(verifier.encode()).digest()  # the verifier went to GitHub, not the challenge
        assert verifier != q["code_challenge"][0]
        state_json = c.get("/api/state").json()
        assert state_json["user"]["login"] == "octo" and state_json["role"] == "owner" and state_json["plan"]["id"] == "free"
        # The state is single use, and a mismatched or foreign issuer is refused.
        assert c.get(f"/auth/callback?code=abc&state={state}").headers["location"].endswith("error=state")
        q = parse_qs(urlparse(c.get("/auth/login").headers["location"]).query)
        assert c.get(f"/auth/callback?code=abc&state={q['state'][0]}&iss=https://evil.example").headers["location"].endswith("error=issuer")
        c.get("/auth/login")
        assert c.get("/auth/callback?code=abc&state=wrong").headers["location"].endswith("error=state")


# Workspaces, roles and isolation -------------------------------------------------
def test_workspaces_are_isolated(env):
    alice, _ = make_team(env)
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    mallory = sign_in(env, "mallory", 3)
    assert mallory.get("/api/posts").json() == []
    assert mallory.get(f"/api/posts/{pid}").status_code in {404, 409}
    assert mallory.patch(f"/api/posts/{pid}", json={"title": "pwned"}).status_code in {404, 409}
    # Naming alice's workspace in a header doesn't help: only your own memberships count.
    wid = alice.get("/api/state").json()["workspace"]["id"]
    assert mallory.get("/api/state", headers={"x-masthead-workspace": str(wid)}).json()["workspace"]["id"] != wid


def test_cannot_connect_someone_elses_installation(env):
    mallory = sign_in(env, "mallory", 3)
    assert mallory.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"}).status_code == 403


def test_invites_roles_and_seat_limits(env):
    alice, wid = make_team(env, seats=2)
    assert alice.post("/api/invites", json={"login": "bob", "role": "writer"}).status_code == 201
    assert alice.post("/api/invites", json={"login": "carol", "role": "writer"}).status_code == 402  # both seats used
    bob = sign_in(env, "bob", 2)
    state = bob.get("/api/state").json()
    assert state["workspace"]["id"] == wid and state["role"] == "writer"
    assert bob.post("/api/invites", json={"login": "dan"}).status_code == 403
    assert bob.get("/api/members").status_code == 200
    assert bob.put("/api/credentials/anthropic", json={"key": "sk-ant-" + "a" * 30}).status_code == 403
    me = alice.get("/api/state").json()["user"]["id"]
    assert alice.patch(f"/api/members/{me}", json={"role": "writer"}).status_code == 409  # the last owner stays


def test_free_plan_gates(env):
    alice = sign_in(env, "alice", 1)
    assert alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"}).status_code == 201
    res = alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"})
    assert res.status_code == 402 and res.headers["x-upgrade-to"] == "team"
    res = alice.post("/api/campaigns", json={"name": "Launch week"})
    assert res.status_code == 402 and "Team plan" in res.json()["detail"]
    assert alice.post("/api/invites", json={"login": "bob", "role": "editor"}).status_code == 402
    assert alice.get("/api/audit").status_code == 402
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(alice, pid)
    assert alice.post(f"/api/posts/{pid}/schedule", json={"publish_at": "2099-01-01"}).status_code == 402


# Review and publishing -----------------------------------------------------------
def test_team_needs_a_reviewer_and_publishes_as_a_pull_request(env):
    alice, _ = make_team(env)
    alice.post("/api/invites", json={"login": "bob", "role": "reviewer"})
    bob = sign_in(env, "bob", 2)
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(alice, pid)
    post = alice.get(f"/api/posts/{pid}").json()
    assert post["gate"]["missing"] == ["Needs 1 more reviewer approval."]
    assert alice.post(f"/api/posts/{pid}/review", json={"decision": "approved"}).status_code == 409  # not your own
    assert bob.post(f"/api/posts/{pid}", json={}).status_code in {404, 405}
    assert bob.patch(f"/api/posts/{pid}", json={"title": "x"}).status_code == 403
    assert bob.post(f"/api/posts/{pid}/review", json={"decision": "approved"}).status_code == 200
    res = alice.post(f"/api/posts/{pid}/publish")
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "published" and out["pr_url"] == "https://github.com/acme/docs/pull/1"
    sent = env["github"].repo_client.published[0]
    assert sent["branch"] == f"masthead/{out['slug']}" and sent["base"] == "main"
    assert any(path.endswith(".mdx") for path in sent["files"])


def test_an_edit_after_approval_needs_a_new_approval(env):
    alice, _ = make_team(env)
    alice.post("/api/invites", json={"login": "bob", "role": "reviewer"})
    bob = sign_in(env, "bob", 2)
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(alice, pid)
    bob.post(f"/api/posts/{pid}/review", json={"decision": "approved"})
    alice.patch(f"/api/posts/{pid}", json={"body": "## Changed\n\nA different body."})
    alice.post(f"/api/posts/{pid}/check")
    missing = alice.get(f"/api/posts/{pid}").json()["gate"]["missing"]
    assert "Needs 1 more reviewer approval." in missing


def test_requested_changes_block_publishing(env):
    alice, _ = make_team(env)
    alice.post("/api/invites", json={"login": "bob", "role": "editor"})
    bob = sign_in(env, "bob", 2)
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(alice, pid)
    bob.post(f"/api/posts/{pid}/review", json={"decision": "changes", "note": "Cut the intro."})
    assert alice.post(f"/api/posts/{pid}/publish").status_code == 409


# API keys ------------------------------------------------------------------------
def test_anthropic_key_is_encrypted_and_never_returned(env, tmp_path):
    alice, wid = make_team(env)
    key = "sk-ant-api03-" + "k" * 40 + "WXYZ"
    assert alice.put("/api/credentials/anthropic", json={"key": "not-a-key-" + "x" * 20}).status_code == 422
    assert alice.put("/api/credentials/anthropic", json={"key": key}).json() == {"last4": "WXYZ"}
    stored = env["db"].credential(wid, "anthropic")
    assert key not in json.dumps(stored) and crypto.decrypt(stored["ciphertext"]) == key
    state = alice.get("/api/state").json()
    assert state["key_last4"] == "WXYZ" and key not in json.dumps(state)


def test_hosted_ai_needs_the_workspace_key(env, tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_SCHEDULER", "0")
    settings = Settings(mode="cloud", db_url=f"sqlite:///{tmp_path / 'k.db'}", port=8787, fake_ai=False, base_url=BASE)
    app = create_app(settings, github=FakeGitHub())  # type: ignore[arg-type]
    with TestClient(app):
        db = app.state.db
        user = db.upsert_user(1, "alice", "Alice", None)
        db.create_workspace("Acme", user["id"])
        c = TestClient(app)
        c.cookies.set(SESSION_COOKIE, db.create_session(user["id"]))
        c.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"})
        pid = c.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
        res = c.post(f"/api/posts/{pid}/outline")
        assert res.status_code == 409 and "Anthropic API key" in res.json()["detail"]


# Billing -------------------------------------------------------------------------
def event(eid, kind, obj):
    return json.dumps({"id": eid, "type": kind, "data": {"object": obj}})


def test_checkout_uses_lookup_keys_and_minimum_seats(env):
    alice = sign_in(env, "alice", 1)
    res = alice.post("/api/billing/checkout", json={"plan": "business", "interval": "yearly"})
    assert res.json() == {"url": "https://checkout.stripe.test/s/1"}
    sent = env["gateway"].checkouts[0]
    assert sent["lookup_key"] == "business_yearly" and sent["seats"] == 5 and sent["trial"] is False
    alice.post("/api/billing/checkout", json={"plan": "team"})
    assert env["gateway"].checkouts[1]["seats"] == 2


def test_webhooks_set_the_plan_once_and_only_when_signed(env):
    alice = sign_in(env, "alice", 1)
    wid = alice.get("/api/state").json()["workspace"]["id"]
    sub = {
        "id": "sub_1", "customer": "cus_1", "status": "active", "metadata": {"workspace_id": str(wid)},
        "items": {"data": [{"quantity": 3, "price": {"lookup_key": "team_monthly"}, "current_period_end": 1900000000}]},
    }
    body = event("evt_1", "customer.subscription.updated", sub)
    c = env["client"]
    assert c.post("/api/stripe/webhook", content=body, headers={"stripe-signature": "forged"}).status_code == 400
    assert alice.get("/api/state").json()["plan"]["id"] == "free"
    assert c.post("/api/stripe/webhook", content=body, headers={"stripe-signature": "good"}).json()["result"].startswith("team")
    assert c.post("/api/stripe/webhook", content=body, headers={"stripe-signature": "good"}).json()["result"] == "duplicate, ignored"
    state = alice.get("/api/state").json()
    assert state["plan"]["id"] == "team" and state["plan"]["seats"] == 3
    gone = event("evt_2", "customer.subscription.deleted", sub)
    c.post("/api/stripe/webhook", content=gone, headers={"stripe-signature": "good"})
    assert alice.get("/api/state").json()["plan"]["id"] == "free"


def test_lapsed_subscription_falls_back_to_free():
    assert billing.effective_plan({"plan": "business", "status": "unpaid"}).id == "free"
    assert billing.effective_plan({"plan": "team", "status": "past_due"}).id == "team"


def test_stripe_gateway_verifies_real_signatures():
    gw = billing.StripeGateway("sk_test_x", "whsec_test")
    payload = event("evt_9", "invoice.paid", {"id": "in_1"}).encode()
    t = int(time.time())
    sig = hmac.new(b"whsec_test", f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    assert gw.verify(payload, f"t={t},v1={sig}")["id"] == "evt_9"
    with pytest.raises(billing.BillingError):
        gw.verify(payload, f"t={t},v1={'0' * 64}")


def test_free_plan_starts_five_posts_a_month(env):
    alice = sign_in(env, "alice", 1)
    alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"})
    for i in range(5):
        assert alice.post("/api/posts", json={"idea": f"Post number {i}"}).status_code == 201
    res = alice.post("/api/posts", json={"idea": "One too many"})
    assert res.status_code == 402 and res.headers["x-upgrade-to"] == "team"


def test_preview_is_scoped_to_the_workspace(env):
    alice, wid = make_team(env)
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(alice, pid)
    url = alice.get(f"/api/posts/{pid}").json()["preview_url"]
    assert url.startswith(f"/api/posts/{pid}/preview.html?w={wid}&s=")
    assert alice.get(url).status_code == 200
    mallory = sign_in(env, "mallory", 3)
    assert mallory.get(url).status_code in {404, 409}
