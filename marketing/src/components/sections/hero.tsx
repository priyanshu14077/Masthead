import { Sparkle } from "lucide-react"
import { motion } from "motion/react"
import { app } from "../../lib/links"
import { ButtonLink } from "../ui/button"
import { ParticleWave } from "./particle-wave"

const FACTS = [
  ["7 steps", "From an idea to a pull request"],
  ["No markup", "Model usage stays on your Anthropic key"],
  ["1 branch per post", "Nothing pushes to main"],
] as const

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden pt-16">
      <ParticleWave className="absolute inset-x-0 top-0 h-[78vh] min-h-[520px] w-full" />
      <div className="pointer-events-none absolute inset-x-0 top-[40vh] h-[50vh] bg-gradient-to-b from-transparent via-black/70 to-black" aria-hidden="true" />
      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-4 pt-[30vh] text-center sm:px-8">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 rounded-md border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[13px] text-neutral-200 backdrop-blur"
        >
          <Sparkle size={13} aria-hidden="true" /> The publishing desk for engineering teams
        </motion.span>
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mt-7 text-[clamp(2.4rem,6.4vw,4.6rem)] leading-[1.02] font-medium tracking-[-0.045em] text-balance"
        >
          Engineering posts, from your <em className="accent">notes</em> to a pull request.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mt-6 max-w-xl text-[17px] leading-relaxed text-muted"
        >
          Claude takes each post through outline, draft, a confidentiality check, a thumbnail and distribution copy. Your team reviews it and merges.
        </motion.p>
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.45 }} className="mt-9 flex flex-wrap justify-center gap-3">
          <ButtonLink href={app()}>Start free</ButtonLink>
          <ButtonLink href="#desk" variant="ghost">Watch the desk work</ButtonLink>
        </motion.div>
      </div>
      <dl className="relative mx-auto mt-20 grid max-w-6xl grid-cols-1 gap-y-4 border-t border-line px-4 py-7 sm:grid-cols-3 sm:px-8">
        {FACTS.map(([value, label]) => (
          <div key={value} className="flex flex-col items-center gap-1 text-center text-[15px]">
            <dt className="font-medium whitespace-nowrap text-white">{value}</dt>
            <dd className="text-dim">{label}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
