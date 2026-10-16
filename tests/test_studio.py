import json
from datetime import date

import pytest
import yaml
from pydantic import ValidationError

from blog_studio.thumbnail import DiagramSpec, render

from .conftest import git


def make_post(client, **extra):
    body = {"idea": "How a write-through cache keeps reads fast", "notes": "p99 was 40 ms", **extra}
    return client.post("/api/posts", json=body).json()


def drive_to_checked(client, pid):
    assert client.post(f"/api/posts/{pid}/outline").status_code == 200
    with client.stream("POST", f"/api/posts/{pid}/draft") as res:
        events = res.read().decode()
    assert "event: done" in events, events
    res = client.post(f"/api/posts/{pid}/check")
    assert res.status_code == 200, res.text
    return res.json()


def test_refuses_other_hosts_and_cross_site_posts(client):
    assert client.get("/api/state", headers={"host": "evil.example"}).status_code == 403
    res = client.post("/api/posts", json={"idea": "x" * 5}, headers={"origin": "https://evil.example"})
    assert res.status_code == 403
    assert client.post("/api/posts", json={"idea": "fine idea"}, headers={"origin": "http://testserver"}).status_code == 201


def test_state_reads_the_site(client):
    info = client.get("/api/state").json()
    assert info["ai"] == "fake"
    assert info["branch"] == "work"
    assert info["tags"] == ["databases", "system-design"]


def test_full_flow_publishes_and_commits(client, repo):
    campaign = client.post("/api/campaigns", json={"name": "Caching 101", "kind": "series"}).json()
    post = make_post(client, campaign_id=campaign["id"])
    client.patch(f"/api/posts/{post['id']}", json={"series_order": 1})
    checked = drive_to_checked(client, post["id"])
    assert checked["status"] == "checked"
    assert checked["gate"]["ready"], checked["gate"]

    assert client.post(f"/api/posts/{post['id']}/thumbnail").status_code == 200
    social = client.post(f"/api/posts/{post['id']}/social").json()["social"]
    assert "https://example.test/blog/" in social["linkedin"]

    preview = client.post(f"/api/posts/{post['id']}/preview").json()
    slug = preview["slug"]
    mdx = repo / "content" / "blog" / f"{slug}.mdx"
    assert yaml.safe_load(mdx.read_text().split("---")[1])["draft"] is True
    assert preview["preview_url"] == f"/api/posts/{post['id']}/preview.html"
    rendered = client.get(preview["preview_url"]).text
    assert "Caching 101 · Part 1" in rendered and "<svg" in rendered  # series label and thumbnail

    published = client.post(f"/api/posts/{post['id']}/publish").json()
    assert published["status"] == "published"
    fm = yaml.safe_load(mdx.read_text().split("---")[1])
    assert fm["draft"] is False
    assert fm["series"] == "Caching 101" and fm["seriesOrder"] == 1
    assert fm["thumbnail"] == f"/blog/{slug}/thumbnail.svg"
    assert fm["date"] == date.today()
    assert (repo / "public" / "blog" / slug / "thumbnail.svg").read_text().startswith("<svg")
    assert published["commit_sha"] == git(repo, "rev-parse", "--short", "HEAD")
    assert "Publish the post" in git(repo, "log", "-1", "--format=%s")
    assert git(repo, "status", "--porcelain") == ""


def test_publish_commits_only_the_post(client, repo):
    (repo / "unrelated.txt").write_text("work in progress")
    git(repo, "add", "unrelated.txt")
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.post(f"/api/posts/{post['id']}/publish")
    assert "unrelated.txt" not in git(repo, "show", "--name-only", "--format=", "HEAD")
    assert "A  unrelated.txt" in git(repo, "status", "--porcelain")


def test_gate_requires_a_current_check(client):
    post = make_post(client)
    client.post(f"/api/posts/{post['id']}/outline")
    with client.stream("POST", f"/api/posts/{post['id']}/draft") as res:
        res.read()
    res = client.post(f"/api/posts/{post['id']}/publish")
    assert res.status_code == 409 and "confidentiality check" in res.json()["detail"]

    client.post(f"/api/posts/{post['id']}/check")
    edited = client.patch(f"/api/posts/{post['id']}", json={"body": "## Changed\n\nNew text."}).json()
    assert edited["status"] == "drafted"
    assert not edited["gate"]["ready"]


def test_secrets_block_and_cannot_be_acknowledged(client):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.patch(f"/api/posts/{post['id']}", json={"body": "## Setup\n\nUse key sk-ant-api03-abcdefghijklmnop to connect."})
    checked = client.post(f"/api/posts/{post['id']}/check").json()
    assert checked["check_result"]["verdict"] == "block"
    assert client.post(f"/api/posts/{post['id']}/check/ack", json={"acknowledged": True}).status_code == 409
    assert client.post(f"/api/posts/{post['id']}/publish").status_code == 409


def test_links_need_review_and_can_be_acknowledged(client):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.patch(f"/api/posts/{post['id']}", json={"body": "## Read more\n\nSee [the docs](https://www.postgresql.org/docs/) and email me@private.dev."})
    checked = client.post(f"/api/posts/{post['id']}/check").json()
    kinds = {f["kind"] for f in checked["check_result"]["findings"]}
    assert {"unverified-link", "personal"} <= kinds
    assert checked["check_result"]["verdict"] == "review"
    acked = client.post(f"/api/posts/{post['id']}/check/ack", json={"acknowledged": True}).json()
    assert acked["gate"]["ready"]


def test_broken_mdx_and_unknown_components_are_caught(client):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.patch(f"/api/posts/{post['id']}", json={"body": "## Hi\n\n<Chart data={[1,2]} />"})
    result = client.post(f"/api/posts/{post['id']}/check").json()["check_result"]
    assert result["verdict"] == "block" and "Chart" in result["mdx_error"]

    client.patch(f"/api/posts/{post['id']}", json={"body": "## Hi\n\n<Callout type=\"note\">unclosed"})
    result = client.post(f"/api/posts/{post['id']}/check").json()["check_result"]
    assert result["verdict"] == "block" and "valid MDX" in result["mdx_error"]


def test_refuses_to_publish_on_master(client, repo):
    git(repo, "checkout", "-q", "-b", "master")
    post = make_post(client)
    drive_to_checked(client, post["id"])
    res = client.post(f"/api/posts/{post['id']}/publish")
    assert res.status_code == 409 and "master" in res.json()["detail"]


def test_never_overwrites_an_existing_post(client):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.patch(f"/api/posts/{post['id']}", json={"slug": "designing-a-url-shortener"})
    res = client.post(f"/api/posts/{post['id']}/preview")
    assert res.status_code == 409 and "already" in res.json()["detail"]


def test_scheduler_publishes_due_posts(client, repo):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    scheduled = client.post(f"/api/posts/{post['id']}/schedule", json={"publish_at": date.today().isoformat()}).json()
    assert scheduled["status"] == "scheduled"
    assert client.post("/api/scheduler/run").json()["published"] == [post["id"]]
    assert client.get(f"/api/posts/{post['id']}").json()["status"] == "published"


def test_cannot_delete_a_post_that_is_in_the_site(client):
    post = make_post(client)
    drive_to_checked(client, post["id"])
    client.post(f"/api/posts/{post['id']}/preview")
    assert client.delete(f"/api/posts/{post['id']}").status_code == 409


def test_draft_stream_keeps_partial_text_on_error(client):
    from blog_studio.ai import AIError

    post = make_post(client)
    client.post(f"/api/posts/{post['id']}/outline")

    async def failing(post, reference, sink):
        yield "## Half"
        raise AIError("The write this post ran out of room.")

    client.fake_ai.draft = failing
    with client.stream("POST", f"/api/posts/{post['id']}/draft") as res:
        events = res.read().decode()
    assert "event: error" in events and json.loads(events.split("data: ")[-1])["partial"] is True
    assert client.get(f"/api/posts/{post['id']}").json()["body"] == "## Half"


def test_thumbnail_spec_validation_and_render():
    spec = {
        "title": "A",
        "nodes": [
            {"id": "a", "label": "Client", "kind": "node", "col": 0, "row": 1},
            {"id": "b", "label": "API", "sub": "stateless", "kind": "hot", "col": 2, "row": 1},
            {"id": "c", "label": "Store", "kind": "store", "col": 9, "row": 9},
        ],
        "edges": [{"source": "a", "target": "b", "style": "accent", "label": "req"}, {"source": "b", "target": "missing", "style": "normal"}],
        "groups": [{"label": "core", "col": 2, "row": 1, "cols": 9, "rows": 1}],
    }
    parsed = DiagramSpec.model_validate(spec)
    assert (parsed.nodes[2].col, parsed.nodes[2].row) == (4, 3)
    assert len(parsed.edges) == 1 and parsed.groups[0].cols == 3
    svg = render(parsed)
    assert svg.startswith("<svg") and "stateless" in svg and "<title>A</title>" in svg

    spec["nodes"][2].update(col=0, row=1)
    with pytest.raises(ValidationError):
        DiagramSpec.model_validate(spec)


def test_config_and_init(tmp_path):
    from blog_studio.cli import init
    from blog_studio.config import ConfigError, load_site

    with pytest.raises(ConfigError, match="blog-studio init"):
        load_site(tmp_path)
    assert init(tmp_path) == 0
    site = load_site(tmp_path)
    assert site.name == tmp_path.name and site.voice and site.components_guide
    assert site.preview("hello") == "http://localhost:5173/blog/hello"
    assert init(tmp_path) == 1  # never overwrites


def test_settings_can_live_outside_the_blog(repo, tmp_path):
    """The blog's repository needs no Masthead files: settings and prompts sit in their own folder."""
    from blog_studio.cli import init
    from blog_studio.config import load_site

    (repo / "blog-studio.toml").unlink()
    git(repo, "commit", "-qam", "drop settings")
    cfg = tmp_path / "blogs" / "test" / "blog-studio.toml"
    assert init(repo, cfg) == 0
    assert not (repo / ".blog-studio").exists() and not (repo / "blog-studio.toml").exists()
    site = load_site(config=cfg)
    assert site.root == repo.resolve() and site.voice
    assert git(repo, "status", "--porcelain") == ""


def test_prompts_use_the_blogs_voice(repo):
    from blog_studio.config import load_site
    from blog_studio.prompts import build

    (repo / "voice.md").write_text("Write like a pirate.")
    (repo / "blog-studio.toml").write_text((repo / "blog-studio.toml").read_text().replace("[paths]", '[prompts]\nvoice = "voice.md"\n[paths]'))
    p = build(load_site(repo))
    assert p.outline.startswith("Write like a pirate.") and "{reference}" in p.draft


def test_preview_renders_without_the_blog_and_runs_nothing(client, repo):
    """Masthead previews a draft itself: no dev server, no files written, no code from the draft run."""
    post = make_post(client)
    pid = post["id"]
    client.post(f"/api/posts/{pid}/outline")
    hostile = (
        'import fs from "fs"\nexport const leak = process.env\n\n'
        "Read [the docs](https://example.com) or [this](javascript:alert(1)).\n\n"
        '<Callout kind="note" title="Flush">Every hop flushes. {process.exit(3)}</Callout>\n\n'
        "<script>alert(1)</script>\n"
    )
    client.patch(f"/api/posts/{pid}", json={"body": hostile})
    viewed = client.get(f"/api/posts/{pid}").json()
    assert viewed["preview_url"] == f"/api/posts/{pid}/preview.html"
    res = client.get(viewed["preview_url"])
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/html")
    assert "script-src https://cdn.jsdelivr.net" in res.headers["content-security-policy"]
    page = res.text
    assert viewed["title"] in page
    assert 'class="callout callout-note"' in page and "{process.exit(3)}" in page  # shown, not run
    assert "javascript:" not in page and "alert(1)</script>" not in page and "process.env" not in page
    assert git(repo, "status", "--porcelain") == ""  # nothing written into the blog


def test_preview_needs_a_draft(client):
    post = make_post(client)
    assert client.get(f"/api/posts/{post['id']}/preview.html").status_code == 409

