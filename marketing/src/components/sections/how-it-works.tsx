import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { SpotlightCard } from "../ui/spotlight-card"

const STEPS = [
  {
    n: "01",
    tag: "Connect",
    title: "Install the GitHub App on your blog",
    body: "Pick the repository. One settings file tells Masthead where posts and thumbnails live and which MDX components your blog has.",
    code: ['[paths] posts = "content/blog"', '[mdx] components = ["Callout", "Mermaid"]'],
  },
  {
    n: "02",
    tag: "Write",
    title: "Bring an idea and your notes",
    body: "Claude outlines, drafts in your components and draws the thumbnail. The notes are the only source of facts and numbers. Writers edit every step.",
    code: ['idea: "How we stream an agent\'s answer"', "notes: p95 first token 2.1 s to 380 ms"],
  },
  {
    n: "03",
    tag: "Ship",
    title: "Check, approve, merge",
    body: "The draft is checked for names, internal details, secrets and unsourced numbers. A reviewer approves, and the post opens as a pull request.",
    code: ["check: clear   reviewer: Sam approved", "PR opened on masthead/streaming-agent-answers"],
  },
]

export function HowItWorks() {
  return (
    <section aria-labelledby="flow" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="How it works" id="flow">
        From notes to <em className="accent">pull request</em> in three steps.
      </SectionHead>
      <ol className="mx-auto mt-16 grid max-w-7xl gap-5 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <Reveal as="li" key={s.n} delay={i * 0.08}>
            <SpotlightCard className="h-full">
              <div className="flex h-full flex-col p-7">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[22px] text-neutral-500">{s.n}</span>
                  <span className="rounded border border-white/15 px-2 py-1 font-mono text-[11px] tracking-[0.12em] text-neutral-300 uppercase">{s.tag}</span>
                </div>
                <h3 className="mt-7 text-[19px] font-medium tracking-[-0.01em]">{s.title}</h3>
                <p className="mt-3 flex-1 text-[15px] leading-relaxed text-muted">{s.body}</p>
                <pre className="mt-7 overflow-x-auto rounded-lg border border-line bg-black/60 px-4 py-3 font-mono text-[12.5px] leading-6 break-words whitespace-pre-wrap text-neutral-300">
                  {s.code.map((line) => (
                    <div key={line}><span className="text-ok">$</span> {line}</div>
                  ))}
                </pre>
              </div>
            </SpotlightCard>
          </Reveal>
        ))}
      </ol>
    </section>
  )
}
