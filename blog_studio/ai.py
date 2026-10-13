"""Model calls. Sonnet 5.5 plans and writes; Haiku 5.5 reviews and writes social copy.

The backend runs locally; only these requests leave the machine.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError

from .prompts import Prompts
from .thumbnail import DiagramSpec

WRITER = "claude-sonnet-5-5"
REVIEWER = "claude-haiku-5-5"

# USD per million tokens: input, output, cache read, cache write (5-minute TTL).
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}

# Server-side refusal fallback on the writer (Claude API only); Haiku 5.5 has no fallback.
FALLBACK = {
    "extra_headers": {"anthropic-beta": "server-side-fallback-2026-07-01"},
    "extra_body": {"fallbacks": "default"},
}


# Structured outputs ------------------------------------------------------
class Section(BaseModel):
    heading: str
    level: Literal[2, 3]
    points: list[str]


class Outline(BaseModel):
    title: str
    subtitle: str
    slug: str
    summary: str
    tags: list[str]
    tldr: list[str]
    sections: list[Section]
    diagram_ideas: list[str]


class Finding(BaseModel):
    severity: Literal["high", "medium", "low"]
    kind: Literal["confidential", "security", "personal", "secret", "unverified-number", "claim"]
    quote: str = Field(description="The exact text from the draft.")
    why: str
    suggestion: str


class CheckResult(BaseModel):
    verdict: Literal["clear", "review", "block"]
    findings: list[Finding]


class Social(BaseModel):
    linkedin: str
    x_thread: list[str]
    newsletter: str


@dataclass
class Usage:
    model: str
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def cost(self) -> float:
        pin, pout, pread, pwrite = PRICES.get(self.model, PRICES[WRITER])
        return (self.input * pin + self.output * pout + self.cache_read * pread + self.cache_write * pwrite) / 1_000_000

    def as_dict(self) -> dict[str, int]:
        return {"input": self.input, "output": self.output, "cache_read": self.cache_read}


class AIError(Exception):
    """A model call failed in a way the author should see."""


def _usage(message: Any) -> Usage:
    u = message.usage
    return Usage(
        model=getattr(message, "model", WRITER) or WRITER,
        input=u.input_tokens or 0,
        output=u.output_tokens or 0,
        cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
        cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
    )


def _check_stop(message: Any, task: str) -> None:
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        why = getattr(details, "explanation", None) or "no explanation given"
        raise AIError(f"The model declined to {task}: {why}.")
    if message.stop_reason == "max_tokens":
        raise AIError(f"The {task} ran out of room before finishing. Try a narrower idea or shorter notes.")


def _cached(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _brief(post: dict[str, Any], known_tags: list[str]) -> str:
    allowed = ", ".join(post.get("allowed_names") or []) or "none: describe every company and product generically"
    return (
        f"Idea:\n{post['idea']}\n\n"
        f"Author's notes and source material:\n{post.get('notes') or '(none)'}\n\n"
        f"Names allowed to appear: {allowed}\n"
        f"Existing tags on the blog: {', '.join(known_tags) or '(none yet)'}"
    )


class AI:
    def __init__(self, prompts: Prompts) -> None:
        self.prompts = prompts
        self.client = anthropic.AsyncAnthropic()

    async def outline(self, post: dict[str, Any], known_tags: list[str]) -> tuple[Outline, Usage]:
        try:
            msg = await self.client.messages.parse(
                model=WRITER,
                max_tokens=16000,
                system=_cached(self.prompts.outline),
                messages=[{"role": "user", "content": _brief(post, known_tags)}],
                output_format=Outline,
                **FALLBACK,
            )
        except anthropic.APIError as e:
            raise AIError(_api_message(e)) from e
        _check_stop(msg, "outline this post")
        if msg.parsed_output is None:
            raise AIError("The outline came back in an unexpected shape. Try again.")
        return msg.parsed_output, _usage(msg)

    async def draft(self, post: dict[str, Any], reference: str, sink: list[Usage]) -> AsyncIterator[str]:
        outline = json.dumps(post["outline"], indent=2)
        user = (
            _brief(post, [])
            + f"\n\nApproved outline (JSON):\n{outline}\n\nWrite the full post body now."
        )
        try:
            async with self.client.messages.stream(
                model=WRITER,
                max_tokens=64000,
                system=_cached(self.prompts.draft.replace("{reference}", reference)),
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "high"},
                **FALLBACK,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            raise AIError(_api_message(e)) from e
        sink.append(_usage(final))
        _check_stop(final, "write this post")

    async def check(self, post: dict[str, Any]) -> tuple[CheckResult, Usage]:
        allowed = ", ".join(post.get("allowed_names") or []) or "(none)"
        user = (
            f"Allowed names: {allowed}\n\nAuthor's notes (the source of truth for numbers):\n{post.get('notes') or '(none)'}\n\n"
            f"Draft title: {post.get('title')}\nSummary: {post.get('summary')}\n\n<draft>\n{post.get('body')}\n</draft>"
        )
        try:
            msg = await self.client.messages.parse(
                model=REVIEWER,
                max_tokens=16000,
                system=_cached(self.prompts.check),
                messages=[{"role": "user", "content": user}],
                output_format=CheckResult,
            )
        except anthropic.APIError as e:
            raise AIError(_api_message(e)) from e
        _check_stop(msg, "review this draft")
        if msg.parsed_output is None:
            raise AIError("The review came back in an unexpected shape. Try again.")
        return msg.parsed_output, _usage(msg)

    async def thumbnail(self, post: dict[str, Any]) -> tuple[DiagramSpec, Usage]:
        ideas = "\n".join(f"- {d}" for d in (post.get("outline") or {}).get("diagram_ideas", []))
        user = f"Post title: {post.get('title')}\nSummary: {post.get('summary')}\nDiagram ideas:\n{ideas or '(none)'}\n\nPost body:\n{post.get('body') or ''}"
        try:
            msg = await self.client.messages.parse(
                model=WRITER,
                max_tokens=16000,
                system=_cached(self.prompts.thumbnail),
                messages=[{"role": "user", "content": user}],
                output_format=DiagramSpec,
                **FALLBACK,
            )
        except anthropic.APIError as e:
            raise AIError(_api_message(e)) from e
        except ValidationError as e:
            raise AIError(f"The diagram didn't fit the grid ({e.errors()[0]['msg']}). Generate it again.") from e
        _check_stop(msg, "design the thumbnail")
        if msg.parsed_output is None:
            raise AIError("The diagram came back in an unexpected shape. Try again.")
        return msg.parsed_output, _usage(msg)

    async def social(self, post: dict[str, Any], url: str) -> tuple[Social, Usage]:
        user = f"Post URL: {url}\nTitle: {post.get('title')}\nSummary: {post.get('summary')}\n\n<post>\n{post.get('body')}\n</post>"
        try:
            msg = await self.client.messages.parse(
                model=REVIEWER,
                max_tokens=8000,
                system=_cached(self.prompts.social),
                messages=[{"role": "user", "content": user}],
                output_format=Social,
            )
        except anthropic.APIError as e:
            raise AIError(_api_message(e)) from e
        _check_stop(msg, "write the social copy")
        if msg.parsed_output is None:
            raise AIError("The social copy came back in an unexpected shape. Try again.")
        return msg.parsed_output, _usage(msg)


def _api_message(e: anthropic.APIError) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "The Anthropic API rejected the credentials. Set ANTHROPIC_API_KEY in studio/.env or run `ant auth login`."
    if isinstance(e, anthropic.RateLimitError):
        return "Rate limited by the Anthropic API. Wait a minute and try again."
    if isinstance(e, anthropic.APIConnectionError):
        return "Couldn't reach the Anthropic API. Check your connection."
    if isinstance(e, anthropic.APIStatusError):
        return f"The Anthropic API returned {e.status_code}: {e.message}"
    return str(e)


# Canned responses for trying the UI without credentials ------------------
class FakeAI(AI):
    def __init__(self, prompts: Prompts | None = None) -> None:  # no client
        self.prompts = prompts  # type: ignore[assignment]

    async def outline(self, post: dict[str, Any], known_tags: list[str]) -> tuple[Outline, Usage]:
        title = post["idea"].strip().split("\n")[0][:60].rstrip(".") or "Untitled idea"
        return Outline(
            title=title,
            subtitle="A sample subtitle from the Studio's fake AI mode.",
            slug="-".join(title.lower().split())[:60],
            summary="This outline was generated without calling a model. Turn off STUDIO_FAKE_AI to use Claude.",
            tags=(known_tags[:2] or ["system-design"]),
            tldr=["Fake mode lets you try the workflow.", "No tokens are spent."],
            sections=[
                Section(heading="The problem", level=2, points=["Why it matters"]),
                Section(heading="The design", level=2, points=["Components", "Trade-offs"]),
            ],
            diagram_ideas=["Client to API to store"],
        ), Usage(model=WRITER)

    async def draft(self, post: dict[str, Any], reference: str, sink: list[Usage]) -> AsyncIterator[str]:
        body = (
            "## The problem\n\nThis draft came from fake AI mode, so the Studio can be tried without credentials.\n\n"
            "## The design\n\n<Callout type=\"note\">Turn off STUDIO_FAKE_AI to write real drafts.</Callout>\n\n"
            "<Figure caption=\"A placeholder diagram.\">\n  <Mermaid label=\"Placeholder\" chart={`\nflowchart LR\n  A[\"Client\"] --> B[\"API\"] --> C[(\"Store\")]\n`} />\n</Figure>\n\n"
            "<Takeaways>\n- Fake mode is for trying the workflow.\n</Takeaways>\n"
        )
        for i in range(0, len(body), 40):
            yield body[i : i + 40]
        sink.append(Usage(model=WRITER))

    async def check(self, post: dict[str, Any]) -> tuple[CheckResult, Usage]:
        return CheckResult(verdict="clear", findings=[]), Usage(model=REVIEWER)

    async def thumbnail(self, post: dict[str, Any]) -> tuple[DiagramSpec, Usage]:
        from .thumbnail import Edge, Node

        return DiagramSpec(
            title=f"Placeholder diagram for {post.get('title')}",
            nodes=[
                Node(id="c", label="Client", kind="node", col=0, row=1),
                Node(id="a", label="API", sub="stateless", kind="hot", col=2, row=1),
                Node(id="s", label="Store", kind="store", col=4, row=1),
            ],
            edges=[Edge(source="c", target="a", style="normal"), Edge(source="a", target="s", style="accent", label="write")],
            footnote="fake AI mode",
        ), Usage(model=WRITER)

    async def social(self, post: dict[str, Any], url: str) -> tuple[Social, Usage]:
        return Social(
            linkedin=f"{post.get('title')}\n\nSample LinkedIn copy from fake AI mode.\n\n{url}",
            x_thread=[f"{post.get('title')}: sample thread from fake AI mode.", f"Read it here: {url}"],
            newsletter=f"This week: {post.get('title')}. {url}",
        ), Usage(model=REVIEWER)
