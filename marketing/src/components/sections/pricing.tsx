import { Check, KeyRound } from "lucide-react"
import { motion } from "motion/react"
import { useState } from "react"
import { app } from "../../lib/links"
import { FEATURES, GROUPS } from "../../lib/features"
import { annualMonths, byok, comingSoon, plans } from "../../lib/plans"
import { ButtonLink } from "../ui/button"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { Compare } from "./compare"

const AUDIENCE: Record<string, string> = { free: "Solo", team: "Teams", business: "Companies" }
const limit = (v: number | null | undefined) => (v == null ? "Unlimited" : String(v))

export function Pricing() {
  const [yearly, setYearly] = useState(false)
  const freeMonths = 12 - annualMonths
  return (
    <section aria-labelledby="pricing" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="Pricing" id="pricing">
        Priced per seat. Model usage stays <em className="accent">on your key</em>.
      </SectionHead>

      <div className="mt-10 flex justify-center">
        <div role="radiogroup" aria-label="Billing period" className="inline-flex rounded-lg border border-line bg-white/[0.03] p-1">
          {([false, true] as const).map((y) => (
            <button key={String(y)} role="radio" aria-checked={yearly === y} onClick={() => setYearly(y)} className="relative rounded-md px-4 py-2 font-mono text-[13px]">
              {yearly === y && <motion.span layoutId="billing" className="absolute inset-0 rounded-md bg-white" transition={{ type: "spring", bounce: 0.15, duration: 0.4 }} />}
              <span className={`relative flex items-center gap-2 ${yearly === y ? "text-black" : "text-neutral-400"}`}>
                {y ? "Billed yearly" : "Billed monthly"}
                {y && <span className="rounded bg-ok/20 px-1.5 py-0.5 text-[11px] text-emerald-600">{freeMonths} months free</span>}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto mt-12 grid max-w-7xl gap-5 lg:grid-cols-3">
        {plans.map((p, i) => {
          const featured = p.id === "team"
          const previous = plans[i - 1]
          const next = plans[i + 1]
          const price = yearly ? p.price_monthly * annualMonths : p.price_monthly
          const unit = p.per_seat ? (yearly ? "per seat a year" : "per seat a month") : yearly ? "a year" : "a month"
          const minimum = p.min_seats ? `From ${p.min_seats} seats, $${(price * p.min_seats).toLocaleString("en-GB")} ${yearly ? "a year" : "a month"}.` : "No card needed."
          const nextAdds = next ? FEATURES.filter((f) => f.plan && next.features.includes(f.plan) && !p.features.includes(f.plan)).map((f) => f.title) : []
          return (
            <Reveal key={p.id} delay={i * 0.08}>
              <article aria-labelledby={`plan-${p.id}`} className={`flex h-full flex-col rounded-2xl border p-7 ${featured ? "border-white/40 bg-gradient-to-b from-[#1a1a1a] to-[#0a0a0a] shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_30px_80px_-30px_rgba(255,255,255,0.15)]" : "border-line bg-gradient-to-b from-[#111] to-[#070707]"}`}>
                <div className="flex items-start justify-between gap-3">
                  <h3 id={`plan-${p.id}`} className="text-[21px] font-medium">{p.name}</h3>
                  <span className={`rounded px-2 py-0.5 font-mono text-[11px] ${featured ? "bg-white text-black" : "border border-white/12 text-neutral-400"}`}>{AUDIENCE[p.id]}</span>
                </div>
                <p className="mt-3 text-[14.5px] text-muted">{p.pitch}</p>
                <p className="mt-7 flex items-baseline gap-2">
                  <span className="text-[44px] leading-none font-medium tracking-[-0.04em]">${price.toLocaleString("en-GB")}</span>
                  <span className="text-[14px] text-neutral-400">{unit}</span>
                </p>
                <p className="mt-2 text-[13.5px] text-neutral-500">{minimum}</p>
                <ButtonLink href={p.id === "free" ? app() : app("#/settings/billing")} variant={featured ? "solid" : "ghost"} className="mt-6 w-full">
                  {p.id === "free" ? "Start free" : `Choose ${p.name}`}
                </ButtonLink>
                <dl className="mt-6 grid grid-cols-2 gap-y-2 border-y border-line py-5 text-[14px]">
                  <dt className="text-neutral-400">Seats</dt><dd className="text-right">{limit(p.limits.seats)}</dd>
                  <dt className="text-neutral-400">Blogs</dt><dd className="text-right">{limit(p.limits.repos)}</dd>
                  <dt className="text-neutral-400">Posts a month</dt><dd className="text-right">{limit(p.limits.posts_per_month)}</dd>
                  <dt className="text-neutral-400">Required reviewers</dt><dd className="text-right">{p.limits.reviewers_required ? (p.limits.reviewers_required > 1 ? `Up to ${p.limits.reviewers_required}` : "1") : "None"}</dd>
                </dl>
                <div className="mt-5 grid flex-1 content-start gap-5">
                  {GROUPS.map((g) => {
                    const items = FEATURES.filter((f) => f.group === g && (!f.plan || p.features.includes(f.plan)))
                    if (!items.length) return null
                    return (
                      <div key={g}>
                        <p className="font-mono text-[11px] tracking-[0.14em] text-neutral-500 uppercase">{g}</p>
                        <ul className="mt-2.5 grid gap-2">
                          {items.map((f) => {
                            const isNew = previous && f.plan && !previous.features.includes(f.plan)
                            const soon = f.plan && comingSoon.includes(f.plan)
                            return (
                              <li key={f.title} className={`flex items-start gap-2.5 text-[14px] ${isNew && !soon ? "text-white" : "text-neutral-400"}`}>
                                <Check size={15} className={`mt-0.5 shrink-0 ${isNew && !soon ? "text-ok" : "text-neutral-600"}`} aria-hidden="true" />
                                <span className="flex-1">{f.title}</span>
                                {soon ? <span className="shrink-0 rounded border border-white/15 px-1.5 font-mono text-[11px] text-neutral-400">Coming</span>
                                  : isNew ? <span className="shrink-0 rounded bg-ok/10 px-1.5 font-mono text-[11px] text-ok">New in {p.name}</span> : null}
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    )
                  })}
                </div>
                {nextAdds.length > 0 && (
                  <p className="mt-6 border-t border-line pt-4 text-[13px] leading-relaxed text-neutral-500">
                    <span className="text-neutral-300">{next!.name} adds</span> {nextAdds.join(", ").toLowerCase()}.
                  </p>
                )}
              </article>
            </Reveal>
          )
        })}
      </div>

      <Reveal className="mx-auto mt-6 max-w-7xl">
        <p className="flex items-center gap-3 rounded-xl border border-line bg-white/[0.02] px-5 py-4 text-[14.5px] text-neutral-300">
          <KeyRound size={17} className="shrink-0 text-copper" aria-hidden="true" /> {byok}
        </p>
      </Reveal>
      <Compare />
    </section>
  )
}
