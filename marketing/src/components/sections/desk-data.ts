// One sample post, carried through every step of the desk. Names and figures are illustrative.

export const POST_TITLE = "Streaming an agent's answer through three services"
export const BRANCH = "masthead/streaming-agent-answers"

export type StepId = "idea" | "outline" | "draft" | "check" | "thumbnail" | "social" | "publish"

export const STEPS: { id: StepId; name: string; model: string; status: string; does: string; ms: number }[] = [
  { id: "idea", name: "Idea", model: "You", status: "Idea", does: "An idea, the author's notes, and the names the post may mention.", ms: 3800 },
  { id: "outline", name: "Outline", model: "Sonnet 5.5", status: "Outlined", does: "Title, slug, tags and sections, drafted from the notes and editable.", ms: 4200 },
  { id: "draft", name: "Draft", model: "Sonnet 5.5", status: "Drafted", does: "The body streams in as MDX, in the blog's own components.", ms: 6400 },
  { id: "check", name: "Check", model: "Haiku 5.5", status: "Checked", does: "Read against the notes and the approved names. Pattern scans and an MDX compile run too.", ms: 5600 },
  { id: "thumbnail", name: "Thumbnail", model: "Sonnet 5.5", status: "Checked", does: "An architecture diagram of the system in the post, in the blog's palette.", ms: 4200 },
  { id: "social", name: "Distribution", model: "Haiku 5.5", status: "Checked", does: "A LinkedIn post, an X thread and a newsletter blurb, linked to the post.", ms: 5200 },
  { id: "publish", name: "Pull request", model: "GitHub App", status: "In review", does: "The post and its thumbnail land on their own branch. A reviewer approves.", ms: 7000 },
]

export const IDEA = {
  idea: "How we stream an agent's answer through three services without stalls",
  notes: [
    "Gateway buffered SSE until the response closed. Fixed by flushing per event.",
    "p95 time to first token: 2.1 s before, 380 ms after.",
    "Agent service holds no state; history lives in Postgres.",
  ],
  names: ["Anthropic", "Postgres"],
}

export const OUTLINE = {
  slug: "streaming-agent-answers",
  tags: ["streaming", "architecture", "sse"],
  sections: [
    ["Where the stall lived", "The gateway held every event until the response closed"],
    ["Flushing at every hop", "Per-event flush in the gateway"],
    ["Keeping the agent stateless", "History in Postgres, not in memory"],
    ["What changed for readers", "p95 first token: 2.1 s to 380 ms, from the notes"],
  ],
}

export const DRAFT = `The first token used to arrive after 2.1 seconds.
Most of that wait was a buffer we added ourselves.

<Callout kind="note">
  Every hop has to flush. One buffering proxy and
  the reader waits for the whole answer.
</Callout>

## Where the stall lived

<Mermaid chart={\`flowchart LR
  Client --> Gateway --> Agent --> Model\`} />

The gateway collected server-sent events until the
response closed, then sent them all at once.`

export const FINDINGS = [
  { severity: "medium", kind: "unverified-number", quote: "cut p99 latency by 80%", why: "No p99 figure appears in the notes.", fix: "Use the p95 numbers from the notes." },
  { severity: "low", kind: "claim", quote: "every load balancer closes idle SSE connections after 60 seconds", why: "A claim about third-party defaults that varies by provider.", fix: "Name the setting instead of a universal number." },
] as const

export const SOCIAL = {
  LinkedIn: "Our agent's first token took 2.1 seconds. The model wasn't slow. A gateway was holding every event until the answer finished. Part 2 of System Design 101 walks through the fix.",
  "X thread": "1/ Streaming only works if every hop flushes. Ours didn't.\n\n2/ The gateway buffered SSE until the response closed. p95 first token went from 2.1 s to 380 ms once it stopped.",
  Newsletter: "This week: where a streaming answer stalls, and why the fix was one flush call in the gateway.",
} as const

export const PR_CHECKS = [
  "Confidentiality check: clear on the current text",
  "MDX compiles with the blog's components",
  "Reviewer sign-off: Sam approved",
]
