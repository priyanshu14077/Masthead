"""Every feature and limit in plans.json is enforced by the app, plan by plan.

The matrix test fails when plans.json gains a feature that has no probe here, so a plan can't
promise something the app doesn't gate."""

import json
from pathlib import Path

import pytest

from blog_studio import plans
from blog_studio.config import Site
from blog_studio.tenancy import prompt_site

from . import test_cloud
from .test_cloud import event, sign_in, write_and_check

env = test_cloud.env  # the hosted-mode app fixture, shared

PLAN_IDS = [p.id for p in plans.catalogue().values()]
ALL_FEATURES = sorted({f for p in plans.catalogue().values() for f in p.features})


def workspace(env, plan_id, seats=10):
    """alice owns a workspace on plan_id with one blog; bob is already an editor (added directly, past the gates)."""
    db = env["db"]
    alice = sign_in(env, "alice", 1)
    wid = alice.get("/api/state").json()["workspace"]["id"]
    db.save_subscription(wid, {"plan": plan_id, "status": "active", "seats": seats})
    assert alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"}).status_code == 201
    bob_user = db.upsert_user(2, "bob", "Bob", None)
    with db.engine.begin() as c:
        from blog_studio.db import memberships, now
        c.execute(memberships.insert().values(workspace_id=wid, user_id=bob_user["id"], role="editor", created_at=now()))
    bob = sign_in(env, "bob", 2)
    return alice, bob, wid


def checked_post(c):
    pid = c.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    write_and_check(c, pid)
    return pid


def _draft(alice, bob, wid):
    pid = alice.post("/api/posts", json={"idea": "Rate limiting at the edge"}).json()["id"]
    alice.post(f"/api/posts/{pid}/outline")
    with alice.stream("POST", f"/api/posts/{pid}/draft") as res:
        res.read()
        return res.status_code


def _brand_voice(alice, bob, wid):
    site = Site(root=Path("/blog"), name="Blog", voice="Write like us.")
    plan_id = json.loads(alice.get("/api/state").content)["plan"]["id"]
    kept = prompt_site(site, plans.get(plan_id), local=False).voice == "Write like us."
    return 200 if kept else 402


PROBES = {
    "outline": lambda a, b, w: a.post(f"/api/posts/{a.post('/api/posts', json={'idea': 'An idea worth a post'}).json()['id']}/outline").status_code,
    "draft": _draft,
    "confidentiality_check": lambda a, b, w: a.post(f"/api/posts/{checked_post(a)}/check").status_code,
    "thumbnails": lambda a, b, w: a.post(f"/api/posts/{checked_post(a)}/thumbnail").status_code,
    "pull_requests": lambda a, b, w: a.post(f"/api/posts/{checked_post(a)}/publish").status_code,
    "review_workflow": lambda a, b, w: b.post(f"/api/posts/{checked_post(a)}/review", json={"decision": "approved"}).status_code,
    "roles": lambda a, b, w: a.patch(f"/api/members/{b.get('/api/state').json()['user']['id']}", json={"role": "reviewer"}).status_code,
    "scheduling": lambda a, b, w: a.post(f"/api/posts/{checked_post(a)}/schedule", json={"publish_at": "2099-01-01"}).status_code,
    "campaigns": lambda a, b, w: a.post("/api/campaigns", json={"name": "Launch week"}).status_code,
    "distribution_copy": lambda a, b, w: a.post(f"/api/posts/{checked_post(a)}/social").status_code,
    "brand_voice": _brand_voice,
    "approval_rules": lambda a, b, w: a.patch(f"/api/sites/{a.get('/api/state').json()['site']['id']}", json={"required_reviewers": 2}).status_code,
    "audit_log": lambda a, b, w: a.get("/api/audit").status_code,
}


def test_every_plan_feature_has_a_probe_or_is_coming_soon():
    coming = set(plans.coming_soon())
    assert coming <= set(plans.get("business").features), "coming-soon features must still be on a plan"
    missing = [f for f in ALL_FEATURES if f not in PROBES and f not in coming]
    assert not missing, f"plans.json features with no enforcement probe: {missing}"
    assert not (coming & set(PROBES)), "a feature can't be both enforced and coming soon"


@pytest.mark.parametrize("plan_id", PLAN_IDS)
@pytest.mark.parametrize("feature", sorted(PROBES))
def test_feature_is_gated_by_plan(env, plan_id, feature):
    alice, bob, wid = workspace(env, plan_id)
    status = PROBES[feature](alice, bob, wid)
    allowed = plans.get(plan_id).has(feature)
    assert status < 500, (feature, plan_id, status)
    assert (status == 402) == (not allowed), f"{feature} on {plan_id}: got {status}, expected {'allowed' if allowed else '402'}"


def test_repo_limit_and_duplicates(env):
    alice, _, _ = workspace(env, "team")  # acme/docs is connected
    assert alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/docs"}).status_code == 409
    for i in range(1, 5):
        assert alice.post("/api/sites", json={"installation_id": 1, "repo": f"acme/blog-{i}"}).status_code == 201
    res = alice.post("/api/sites", json={"installation_id": 1, "repo": "acme/blog-5"})
    assert res.status_code == 402 and res.headers["x-upgrade-to"] == "business"


def test_business_approval_rule_is_capped_and_enforced(env):
    alice, bob, _ = workspace(env, "business")
    sid = alice.get("/api/state").json()["site"]["id"]
    assert alice.patch(f"/api/sites/{sid}", json={"required_reviewers": 9}).status_code == 200
    pid = checked_post(alice)
    gate = alice.get(f"/api/posts/{pid}").json()["gate"]
    assert gate["review"]["required"] == plans.get("business").limit("reviewers_required")
    bob.post(f"/api/posts/{pid}/review", json={"decision": "approved"})
    assert alice.post(f"/api/posts/{pid}/publish").status_code == 409  # one approval of three


def test_cancelling_moves_back_to_free_features(env):
    alice, _, wid = workspace(env, "team")
    assert alice.post("/api/campaigns", json={"name": "Launch week"}).status_code == 201
    gone = event("evt_cancel", "customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1", "metadata": {"workspace_id": str(wid)}})
    env["client"].post("/api/stripe/webhook", content=gone, headers={"stripe-signature": "good"})
    assert alice.get("/api/state").json()["plan"]["id"] == "free"
    assert alice.post("/api/campaigns", json={"name": "Another"}).status_code == 402


def test_plan_catalogue_is_served_as_is(env):
    served = env["client"].get("/api/plans").json()
    assert served == json.loads(plans.PLANS_FILE.read_text())
    assert served["coming_soon"] == plans.coming_soon()
