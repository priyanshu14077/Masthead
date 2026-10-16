import { AnimatePresence, motion } from "motion/react"
import { useState } from "react"
import { FEATURES, GROUPS, type Group } from "../../lib/features"
import { comingSoon, planFor } from "../../lib/plans"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { SpotlightCard } from "../ui/spotlight-card"

function Tag({ feature }: { feature?: string }) {
  if (feature && comingSoon.includes(feature)) {
    return <span className="rounded border border-white/15 px-2 py-0.5 font-mono text-[11px] text-neutral-400">{planFor(feature)?.name} · coming</span>
  }
  const plan = feature ? planFor(feature) : undefined
  const every = !plan || plan.price_monthly === 0
  return (
    <span className={`rounded px-2 py-0.5 font-mono text-[11px] ${every ? "bg-ok/10 text-ok" : "border border-white/20 text-neutral-200"}`}>
      {every ? "All plans" : plan.name}
    </span>
  )
}

export function Features() {
  const [group, setGroup] = useState<Group | "All">("All")
  const shown = FEATURES.filter((f) => group === "All" || f.group === group)
  return (
    <section aria-labelledby="features" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="Features" id="features">
        Everything on the <em className="accent">desk</em>.
      </SectionHead>
      <div className="mt-10 flex justify-center">
        <div role="tablist" aria-label="Feature group" className="inline-flex max-w-full flex-wrap justify-center gap-1 rounded-lg border border-line bg-white/[0.03] p-1">
          {(["All", ...GROUPS] as const).map((g) => (
            <button key={g} role="tab" aria-selected={group === g} onClick={() => setGroup(g)} className="relative rounded-md px-3.5 py-1.5 font-mono text-[12.5px]">
              {group === g && <motion.span layoutId="feature-group" className="absolute inset-0 rounded-md bg-white" transition={{ type: "spring", bounce: 0.15, duration: 0.4 }} />}
              <span className={`relative ${group === g ? "text-black" : "text-neutral-400 hover:text-white"}`}>{g}</span>
            </button>
          ))}
        </div>
      </div>
      <Reveal className="mx-auto mt-12 max-w-7xl">
        <motion.ul layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence mode="popLayout">
            {shown.map((f) => (
              <motion.li key={f.title} layout initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }} transition={{ duration: 0.25 }}>
                <SpotlightCard className="h-full">
                  <div className="flex h-full flex-col p-6">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[11px] tracking-[0.14em] text-neutral-500 uppercase">{f.group}</span>
                      <Tag feature={f.plan} />
                    </div>
                    <h3 className="mt-5 text-[18px] font-medium tracking-[-0.01em]">{f.title}</h3>
                    <p className="mt-2 text-[14.5px] leading-relaxed text-muted">{f.body}</p>
                  </div>
                </SpotlightCard>
              </motion.li>
            ))}
          </AnimatePresence>
        </motion.ul>
      </Reveal>
    </section>
  )
}
