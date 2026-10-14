import { Check, KeyRound } from "lucide-react"
import { motion } from "motion/react"
import { useState } from "react"
import { app } from "../../lib/links"
import { annualMonths, byok, featureLabels, plans } from "../../lib/plans"
import { ButtonLink } from "../ui/button"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"

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
          const added = previous ? p.features.filter((f) => !previous.features.includes(f)) : p.features
          const price = yearly ? p.price_monthly * annualMonths : p.price_monthly
          const unit = p.per_seat ? (yearly ? "per seat a year" : "per seat a month") : yearly ? "a year" : "a month"
          const minimum = p.min_seats ? `From ${p.min_seats} seats, $${(price * p.min_seats).toLocaleString("en-GB")} ${yearly ? "a year" : "a month"}.` : "No card needed."
          return (
            <Reveal key={p.id} delay={i * 0.08}>
              <article className={`flex h-full flex-col rounded-2xl border p-7 ${featured ? "border-white/40 bg-gradient-to-b from-[#1a1a1a] to-[#0a0a0a] shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_30px_80px_-30px_rgba(255,255,255,0.15)]" : "border-line bg-gradient-to-b from-[#111] to-[#070707]"}`}>
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-[21px] font-medium">{p.name}</h3>
                  <span className={`rounded px-2 py-0.5 font-mono text-[11px] ${featured ? "bg-white text-black" : "border border-white/12 text-neutral-400"}`}>{AUDIENCE[p.id]}</span>
                </div>
                <p className="mt-3 text-[14.5px] text-muted">{p.pitch}</p>
                <p className="mt-7 flex items-baseline gap-2">
                  <span className="text-[44px] leading-none font-medium tracking-[-0.04em]">${price.toLocaleString("en-GB")}</span>
                  <span className="text-[14px] text-neutral-400">{unit}</span>
                </p>
                <p className="mt-2 text-[13.5px] text-neutral-500">{minimum}</p>
                <dl className="mt-6 grid grid-cols-2 gap-y-2 border-y border-line py-5 text-[14px]">
                  <dt className="text-neutral-400">Seats</dt><dd className="text-right">{limit(p.limits.seats)}</dd>
                  <dt className="text-neutral-400">Blogs</dt><dd className="text-right">{limit(p.limits.repos)}</dd>
                  <dt className="text-neutral-400">Posts a month</dt><dd className="text-right">{limit(p.limits.posts_per_month)}</dd>
                  <dt className="text-neutral-400">Required reviewers</dt><dd className="text-right">{p.limits.reviewers_required ? (p.limits.reviewers_required > 1 ? `Up to ${p.limits.reviewers_required}` : "1") : "None"}</dd>
                </dl>
                <p className="mt-5 text-[13.5px] font-medium text-neutral-300">{previous ? `Everything in ${previous.name}, plus` : "Includes"}</p>
                <ul className="mt-3 grid flex-1 content-start gap-2.5">
                  {added.map((f) => (
                    <li key={f} className="flex gap-2.5 text-[14px] text-neutral-300"><Check size={15} className="mt-0.5 shrink-0 text-neutral-400" aria-hidden="true" />{featureLabels[f]}</li>
                  ))}
                </ul>
                <ButtonLink href={app(`/signup?plan=${p.id}`)} variant={featured ? "solid" : "ghost"} className="mt-8 w-full">
                  {p.id === "free" ? "Start free" : `Choose ${p.name}`}
                </ButtonLink>
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
    </section>
  )
}
