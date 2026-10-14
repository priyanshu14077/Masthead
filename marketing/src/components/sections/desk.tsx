import { AnimatePresence, motion, useInView } from "motion/react"
import { Check, CircleDot, FileCode2, GitPullRequest, Pause, Play, RotateCcw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { BRANCH, DRAFT, FINDINGS, IDEA, OUTLINE, POST_TITLE, PR_CHECKS, SOCIAL, STEPS, type StepId } from "./desk-data"

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches

/**
 * Masthead's editor, running on a sample post. It plays the seven steps on its own once it scrolls
 * into view; choosing a step pauses it there.
 */
export function Desk() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.35 })
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [started, setStarted] = useState(false)

  useEffect(() => {
    if (inView && !started && !reduced()) { setStarted(true); setPlaying(true) }
  }, [inView, started])

  useEffect(() => {
    if (!playing || !inView) return
    const id = window.setTimeout(() => {
      if (step === STEPS.length - 1) setPlaying(false)
      else setStep(step + 1)
    }, STEPS[step].ms)
    return () => window.clearTimeout(id)
  }, [playing, inView, step])

  const choose = (i: number) => { setStep(i); setPlaying(false) }
  const replay = () => { setStep(0); setPlaying(true) }
  const current = STEPS[step]
  const done = step === STEPS.length - 1 && !playing

  return (
    <section aria-labelledby="desk" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="The desk" id="desk">
        One post, every step, <em className="accent">running</em>.
      </SectionHead>
      <Reveal className="mx-auto mt-16 max-w-7xl">
        <div ref={ref} className="overflow-hidden rounded-2xl border border-white/15 bg-[#060606] shadow-[0_40px_120px_-40px_rgba(255,255,255,0.12)]">
          {/* Window bar */}
          <div className="flex items-center gap-4 border-b border-line px-4 py-3 sm:px-5">
            <span className="flex gap-1.5" aria-hidden="true">
              {[0, 1, 2].map((i) => <span key={i} className="size-2.5 rounded-full bg-white/20" />)}
            </span>
            <span className="hidden h-4 w-px bg-line sm:block" aria-hidden="true" />
            <span className="truncate font-mono text-[12.5px] text-neutral-400">masthead / Developer relations / Docs blog</span>
            <span className="ml-auto hidden items-center gap-2 font-mono text-[12px] text-neutral-400 md:flex">
              <span className="size-1.5 rounded-full bg-ok" aria-hidden="true" /> Claude on your key
            </span>
            <button
              onClick={done ? replay : () => setPlaying(!playing)}
              className="inline-flex items-center gap-1.5 rounded-md border border-white/15 bg-white/[0.05] px-2.5 py-1.5 font-mono text-[12px] text-neutral-200 hover:bg-white/10"
            >
              {done ? <RotateCcw size={12} /> : playing ? <Pause size={12} /> : <Play size={12} />}
              {done ? "Replay" : playing ? "Pause" : "Play"}
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)]">
            {/* Steps */}
            <div className="border-b border-line p-3 lg:border-r lg:border-b-0 lg:p-4">
              <p className="mb-3 hidden px-2 font-mono text-[11px] tracking-[0.16em] text-neutral-500 uppercase lg:block">Steps</p>
              <ol className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
                {STEPS.map((s, i) => {
                  const state = i < step ? "done" : i === step ? "active" : "next"
                  return (
                    <li key={s.id} className="shrink-0">
                      <button
                        onClick={() => choose(i)}
                        aria-current={state === "active" ? "step" : undefined}
                        className={`relative flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${state === "active" ? "border-white/20 bg-white/[0.07]" : "border-transparent hover:bg-white/[0.04]"}`}
                      >
                        <span className={`flex size-7 shrink-0 items-center justify-center rounded-md border font-mono text-[12px] ${state === "done" ? "border-ok/40 text-ok" : state === "active" ? "border-white/40 text-white" : "border-white/10 text-neutral-500"}`}>
                          {state === "done" ? <Check size={13} /> : i + 1}
                        </span>
                        <span className="min-w-0">
                          <span className={`block text-[14.5px] ${state === "next" ? "text-neutral-400" : "text-white"}`}>{s.name}</span>
                          <span className="hidden font-mono text-[11.5px] text-neutral-500 lg:block">{s.model}</span>
                        </span>
                        {state === "active" && playing && (
                          <motion.span className="absolute inset-x-3 bottom-0 h-px origin-left bg-white/60" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: s.ms / 1000, ease: "linear" }} key={`p-${step}`} />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ol>
            </div>

            {/* Panel */}
            <div className="min-w-0 p-5 sm:p-7">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/[0.04]"><FileCode2 size={17} aria-hidden="true" /></span>
                  <div className="min-w-0">
                    <p className="truncate text-[16px] font-medium">{POST_TITLE}</p>
                    <p className="text-[13.5px] text-neutral-400">{current.does}</p>
                  </div>
                </div>
                <span className="rounded border border-ok/30 bg-ok/10 px-2 py-0.5 font-mono text-[11.5px] text-ok">{current.status}</span>
              </div>
              <div className="min-h-[420px] pt-6 lg:min-h-[540px]" aria-live="polite">
                <AnimatePresence mode="wait">
                  <motion.div key={current.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.3 }}>
                    <Panel id={current.id} playing={playing} />
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-between gap-2 border-t border-line px-5 py-3 font-mono text-[12px] text-neutral-500">
            <span>Branch {BRANCH}</span>
            <span>Nothing pushes to main</span>
          </div>
        </div>
      </Reveal>
    </section>
  )
}

function Panel({ id, playing }: { id: StepId; playing: boolean }) {
  switch (id) {
    case "idea": return <IdeaPanel />
    case "outline": return <OutlinePanel />
    case "draft": return <DraftPanel animate={playing} />
    case "check": return <CheckPanel />
    case "thumbnail": return <ThumbnailPanel />
    case "social": return <SocialPanel />
    case "publish": return <PublishPanel />
  }
}

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <div>
    <p className="mb-2 font-mono text-[11px] tracking-[0.14em] text-neutral-500 uppercase">{label}</p>
    <div className="rounded-lg border border-line bg-white/[0.02] px-4 py-3 text-[14.5px] leading-relaxed text-neutral-200">{children}</div>
  </div>
)

function IdeaPanel() {
  return (
    <div className="grid gap-5">
      <Field label="The idea">{IDEA.idea}</Field>
      <Field label="Notes and source material">
        <ul className="space-y-1.5">{IDEA.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </Field>
      <Field label="Names allowed to appear">
        <span className="flex flex-wrap gap-2">{IDEA.names.map((n) => <span key={n} className="rounded border border-white/15 px-2 py-0.5 font-mono text-[12.5px]">{n}</span>)}</span>
      </Field>
    </div>
  )
}

function OutlinePanel() {
  return (
    <div className="grid gap-5">
      <div className="grid gap-5 sm:grid-cols-[1fr_auto]">
        <Field label="Slug"><span className="font-mono text-[13.5px]">{OUTLINE.slug}</span></Field>
        <Field label="Tags"><span className="flex gap-2">{OUTLINE.tags.map((t) => <span key={t} className="font-mono text-[13px] text-neutral-300">#{t}</span>)}</span></Field>
      </div>
      <div>
        <p className="mb-2 font-mono text-[11px] tracking-[0.14em] text-neutral-500 uppercase">Sections</p>
        <ol className="grid gap-2">
          {OUTLINE.sections.map(([h, sub], i) => (
            <motion.li key={h} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.25 }} className="flex gap-4 rounded-lg border border-line bg-white/[0.02] px-4 py-3">
              <span className="font-mono text-[12.5px] text-neutral-500">{String(i + 1).padStart(2, "0")}</span>
              <span><span className="block text-[15px] text-white">{h}</span><span className="text-[13.5px] text-neutral-400">{sub}</span></span>
            </motion.li>
          ))}
        </ol>
      </div>
    </div>
  )
}

function DraftPanel({ animate }: { animate: boolean }) {
  const [n, setN] = useState(animate ? 0 : DRAFT.length)
  useEffect(() => {
    if (!animate) { setN(DRAFT.length); return }
    const id = window.setInterval(() => setN((v) => (v >= DRAFT.length ? v : v + 7)), 28)
    return () => window.clearInterval(id)
  }, [animate])
  const text = DRAFT.slice(0, n)
  const writing = n < DRAFT.length
  return (
    <div>
      <div className="mb-3 flex items-center justify-between font-mono text-[12px] text-neutral-500">
        <span className="flex items-center gap-2">{writing && <CircleDot size={12} className="animate-pulse text-ok" />}{writing ? "Writing with Claude Sonnet 5.5" : "Draft written"}</span>
        <span>{text.split(/\s+/).filter(Boolean).length} words</span>
      </div>
      <pre className="h-[340px] overflow-hidden rounded-lg border border-line bg-black p-5 font-mono text-[13px] leading-6 whitespace-pre-wrap text-neutral-300">
        {text}
        {writing && <span className="ml-px inline-block h-4 w-2 translate-y-0.5 animate-pulse bg-white/70" />}
      </pre>
    </div>
  )
}

function CheckPanel() {
  const [ready, setReady] = useState(false)
  useEffect(() => { const id = window.setTimeout(() => setReady(true), 1100); return () => window.clearTimeout(id) }, [])
  if (!ready) return <p className="flex items-center gap-2 font-mono text-[13px] text-neutral-400"><CircleDot size={13} className="animate-pulse" /> Reading the draft against the notes and approved names</p>
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded border border-warn/40 bg-warn/10 px-2 py-0.5 font-mono text-[12px] text-warn">Needs your review</span>
        <span className="font-mono text-[12.5px] text-neutral-400">2 findings</span>
      </div>
      {FINDINGS.map((f, i) => (
        <motion.div key={f.quote} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.2 }} className={`rounded-lg border border-line border-l-2 bg-white/[0.02] px-4 py-3 ${f.severity === "medium" ? "border-l-warn" : "border-l-neutral-500"}`}>
          <p className="flex gap-2 font-mono text-[11.5px] text-neutral-400"><span className={f.severity === "medium" ? "text-warn" : ""}>{f.severity}</span><span>{f.kind}</span></p>
          <p className="mt-2 rounded bg-white/[0.05] px-2 py-1 font-mono text-[13px] text-white">{f.quote}</p>
          <p className="mt-2 text-[14px] text-neutral-300">{f.why} <span className="text-neutral-500">Suggestion: {f.fix}</span></p>
        </motion.div>
      ))}
      <p className="mt-1 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[12px] text-neutral-500">
        <span><span className="text-ok">✓</span> No secrets or internal hosts</span>
        <span><span className="text-ok">✓</span> MDX compiles</span>
      </p>
    </div>
  )
}

function ThumbnailPanel() {
  const box = (x: number, y: number, label: string, sub?: string) => (
    <g>
      <rect x={x} y={y} width="118" height="54" rx="8" fill="#14213a" stroke="#a9c1d6" strokeOpacity="0.5" />
      <text x={x + 59} y={y + (sub ? 25 : 32)} textAnchor="middle" fill="#f2ede2" fontSize="14" fontFamily="Inter">{label}</text>
      {sub && <text x={x + 59} y={y + 42} textAnchor="middle" fill="#a9c1d6" fontSize="11" fontFamily="JetBrains Mono">{sub}</text>}
    </g>
  )
  return (
    <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }} className="overflow-hidden rounded-lg border border-line">
      <svg viewBox="0 0 640 360" role="img" aria-label="Thumbnail diagram: client, gateway, agent and model in a row, with Postgres under the agent" className="block w-full">
        <rect width="640" height="360" fill="#0c1528" />
        <text x="32" y="44" fill="#d39062" fontSize="12" letterSpacing="2" fontFamily="JetBrains Mono">SYSTEM DESIGN 101 · PART 2</text>
        <text x="32" y="78" fill="#f2ede2" fontSize="24" fontFamily="Instrument Serif">Flush at every hop</text>
        {[[150, 186], [298, 334], [446, 482]].map(([a, b]) => <line key={a} x1={a} y1="160" x2={b} y2="160" stroke="#d39062" strokeWidth="2" />)}
        {box(32, 133, "Client")}
        {box(184, 133, "Gateway", "flush per event")}
        {box(332, 133, "Agent", "stateless")}
        {box(480, 133, "Model")}
        <line x1="391" y1="187" x2="391" y2="236" stroke="#a9c1d6" strokeDasharray="4 4" />
        {box(332, 236, "Postgres", "history")}
      </svg>
    </motion.div>
  )
}

function SocialPanel() {
  const tabs = Object.keys(SOCIAL) as (keyof typeof SOCIAL)[]
  const [tab, setTab] = useState<keyof typeof SOCIAL>(tabs[0])
  return (
    <div>
      <div role="tablist" aria-label="Channel" className="inline-flex rounded-lg border border-line bg-white/[0.03] p-1">
        {tabs.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className="relative rounded-md px-3.5 py-1.5 font-mono text-[12.5px]">
            {tab === t && <motion.span layoutId="social-tab" className="absolute inset-0 rounded-md bg-white" transition={{ type: "spring", bounce: 0.15, duration: 0.4 }} />}
            <span className={`relative ${tab === t ? "text-black" : "text-neutral-400"}`}>{t}</span>
          </button>
        ))}
      </div>
      <p role="tabpanel" className="mt-5 rounded-lg border border-line bg-white/[0.02] px-5 py-4 text-[15px] leading-relaxed whitespace-pre-line text-neutral-200">{SOCIAL[tab]}</p>
    </div>
  )
}

function PublishPanel() {
  return (
    <div className="rounded-lg border border-line bg-white/[0.02]">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-ok/15 px-2.5 py-1 text-[12.5px] text-ok"><GitPullRequest size={13} /> Open</span>
        <span className="text-[15px]">Post: {POST_TITLE}</span>
      </div>
      <div className="grid gap-4 px-5 py-4">
        <p className="font-mono text-[12.5px] text-neutral-400">{BRANCH} <span className="text-neutral-600">into</span> main</p>
        <ul className="grid gap-1.5 font-mono text-[12.5px] text-neutral-300">
          <li>content/blog/streaming-agent-answers.mdx <span className="text-ok">new file</span></li>
          <li>public/blog/streaming-agent-answers/thumbnail.svg <span className="text-ok">new file</span></li>
        </ul>
        <ul className="grid gap-2 border-t border-line pt-4">
          {PR_CHECKS.map((c, i) => (
            <motion.li key={c} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 + i * 0.7 }} className="flex items-center gap-2.5 text-[14px] text-neutral-200">
              <span className="flex size-5 items-center justify-center rounded-full bg-ok/15 text-ok"><Check size={12} /></span>{c}
            </motion.li>
          ))}
        </ul>
        <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 + PR_CHECKS.length * 0.7 }} className="rounded-md border border-ok/30 bg-ok/10 px-3 py-2 text-[14px] text-ok">
          Ready to merge. Your CI and preview builds run on this branch like any other.
        </motion.p>
      </div>
    </div>
  )
}
