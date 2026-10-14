import { AnimatePresence, motion } from "motion/react"
import { Play, RotateCcw } from "lucide-react"
import { useEffect, useState } from "react"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"

type Severity = "high" | "medium"
type Scenario = {
  name: string
  before: string
  hit: string
  after: string
  sources: string[]
  stages: [string, string, string][] // [source, title, detail]
  severity: Severity
  kind: string
  fix: string
}

const SCENARIOS: Scenario[] = [
  {
    name: "Internal hostname",
    before: "Every read went to ",
    hit: "orders-api.internal:8080",
    after: " before the cache warmed.",
    sources: ["Pattern scan", "Claude Haiku 5.5"],
    stages: [
      ["Draft", "Read the sentence", "Every sentence is checked, including code blocks and captions."],
      ["Pattern scan", "Match internal hosts", "Internal hostnames, IP addresses and service URLs."],
      ["Severity", "Grade it", "An internal address names infrastructure readers shouldn't see."],
      ["Suggestion", "Offer a rewrite", "The writer accepts it, or confirms the original on purpose."],
    ],
    severity: "medium",
    kind: "confidential",
    fix: "the orders service",
  },
  {
    name: "Number not in notes",
    before: "The change ",
    hit: "cut p99 latency by 80%",
    after: " across every region.",
    sources: ["Author's notes", "Claude Haiku 5.5"],
    stages: [
      ["Draft", "Read the sentence", "A figure is a claim, so every one is traced."],
      ["Author's notes", "Look for its source", "The notes give p95 first-token times. They have no p99 figure."],
      ["Severity", "Grade it", "A number readers will quote, with nothing behind it."],
      ["Suggestion", "Offer a rewrite", "Use the figures the notes do contain."],
    ],
    severity: "medium",
    kind: "unverified-number",
    fix: "p95 first token went from 2.1 s to 380 ms",
  },
  {
    name: "Unapproved name",
    before: "We learned this during ",
    hit: "the Northwind rollout",
    after: " last spring.",
    sources: ["Approved names", "Claude Haiku 5.5"],
    stages: [
      ["Draft", "Read the sentence", "Company, customer and product names are picked out."],
      ["Approved names", "Compare with the post's list", "This post may name Anthropic and Postgres. Northwind isn't on it."],
      ["Severity", "Grade it", "A customer named without sign-off. The post can't ship like this."],
      ["Suggestion", "Offer a rewrite", "Describe the customer instead of naming them."],
    ],
    severity: "high",
    kind: "confidential",
    fix: "a logistics customer's rollout",
  },
  {
    name: "Secret in a snippet",
    before: "export ANTHROPIC_API_KEY=",
    hit: "sk-ant-api03-Xq7…",
    after: "",
    sources: ["Pattern scan"],
    stages: [
      ["Draft", "Read the code block", "Snippets are scanned as closely as prose."],
      ["Pattern scan", "Match key formats", "API keys, tokens, private keys and database URLs with passwords."],
      ["Severity", "Grade it", "A credential. Blocked until it's gone, whatever the model thinks."],
      ["Suggestion", "Offer a rewrite", "Use a placeholder, and rotate the key if it was ever real."],
    ],
    severity: "high",
    kind: "secret",
    fix: "export ANTHROPIC_API_KEY=your-key",
  },
]

const STAGE_MS = 650

export function CheckSandbox() {
  const [pick, setPick] = useState(0)
  const [stage, setStage] = useState(-1) // -1: not run; 0..3: revealed through; 4: verdict
  const s = SCENARIOS[pick]
  const running = stage >= 0 && stage < 4

  useEffect(() => {
    if (!running) return
    const id = window.setTimeout(() => setStage(stage + 1), STAGE_MS)
    return () => window.clearTimeout(id)
  }, [running, stage])

  const run = () => setStage(0)
  const choose = (i: number) => { setPick(i); setStage(-1) }
  const high = s.severity === "high"

  return (
    <section aria-labelledby="check" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="The check" id="check">
        Catch the internal detail <em className="accent">before the internet does</em>.
      </SectionHead>
      <Reveal className="mx-auto mt-16 max-w-7xl">
        <div className="rounded-2xl border border-white/15 bg-[#070707] p-4 sm:p-7">
          <div className="flex flex-wrap items-center gap-2 border-b border-line pb-5">
            <div role="tablist" aria-label="Example" className="flex flex-wrap gap-2">
              {SCENARIOS.map((x, i) => (
                <button key={x.name} role="tab" aria-selected={i === pick} onClick={() => choose(i)}
                  className={`rounded-md border px-3 py-1.5 font-mono text-[12.5px] transition-colors ${i === pick ? "border-white bg-white text-black" : "border-white/12 bg-white/[0.03] text-neutral-400 hover:text-white"}`}>
                  {x.name}
                </button>
              ))}
            </div>
            <button onClick={run} disabled={running}
              className="ml-auto inline-flex items-center gap-2 rounded-md bg-white px-4 py-2 text-[14px] font-medium text-black disabled:opacity-60">
              {stage === 4 ? <RotateCcw size={14} /> : <Play size={14} fill="currentColor" />}
              {stage === 4 ? "Run again" : running ? "Checking" : "Run the check"}
            </button>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-white/[0.02] px-4 py-3.5">
            <span className="font-mono text-[12.5px] text-neutral-500">Draft:</span>
            <p className="min-w-0 flex-1 font-mono text-[14px] text-neutral-200">
              “{s.before}
              <mark className={`rounded px-1 transition-colors duration-500 ${stage >= 1 ? (high ? "bg-bad/25 text-white" : "bg-warn/25 text-white") : "bg-transparent text-neutral-200"}`}>{s.hit}</mark>
              {s.after}”
            </p>
            <span className="flex gap-2">{s.sources.map((x) => <span key={x} className="rounded border border-white/12 px-2 py-0.5 font-mono text-[11px] text-neutral-400">{x}</span>)}</span>
          </div>

          <ol className="mt-5 grid gap-3 md:grid-cols-4">
            {s.stages.map(([source, title, detail], i) => {
              const on = stage >= i
              return (
                <li key={title} className={`rounded-lg border px-4 py-4 transition-colors duration-300 ${on ? "border-white/20 bg-white/[0.04]" : "border-line bg-transparent"}`}>
                  <span className="rounded border border-white/12 px-2 py-0.5 font-mono text-[10.5px] tracking-[0.1em] text-neutral-400 uppercase">{source}</span>
                  <p className={`mt-3 text-[15px] font-medium ${on ? "text-white" : "text-neutral-500"}`}>{i + 1}. {title}</p>
                  <p className={`mt-1.5 text-[13.5px] leading-relaxed ${on ? "text-neutral-400" : "text-neutral-600"}`}>{detail}</p>
                  {i === 2 && on && (
                    <p className={`mt-3 font-mono text-[12px] ${high ? "text-bad" : "text-warn"}`}>{s.severity} · {s.kind}</p>
                  )}
                  {i === 3 && on && <p className="mt-3 font-mono text-[12px] text-ok">“{s.fix}”</p>}
                </li>
              )
            })}
          </ol>

          <AnimatePresence>
            {stage === 4 && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className={`mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 ${high ? "border-bad/40 bg-bad/10" : "border-warn/40 bg-warn/10"}`}>
                <span className={`font-mono text-[13px] ${high ? "text-bad" : "text-warn"}`}>{high ? "Blocked" : "Needs your review"}</span>
                <span className="text-[14px] text-neutral-200">
                  {high ? "High-severity findings have to be fixed before the post can ship." : "A person confirms medium findings before the post can ship."}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Reveal>
    </section>
  )
}
