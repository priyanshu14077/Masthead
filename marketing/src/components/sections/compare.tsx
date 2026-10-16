import { Check, Minus } from "lucide-react"
import { comingSoon, featureLabels, plans } from "../../lib/plans"
import { Reveal } from "../ui/reveal"

const LIMITS: [string, keyof (typeof plans)[number]["limits"]][] = [
  ["Seats", "seats"],
  ["Blogs", "repos"],
  ["Posts a month", "posts_per_month"],
  ["Required reviewers", "reviewers_required"],
]

const limit = (key: string, v: number | null) => (v == null ? "Unlimited" : key === "reviewers_required" ? (v === 0 ? "None" : v > 1 ? `Up to ${v}` : "1") : String(v))
const features = [...new Set(plans.flatMap((p) => p.features))]

/** Every limit and feature, plan by plan, straight from plans.json. */
export function Compare() {
  const cell = "px-2 py-3 text-center text-[13px] sm:px-4 sm:text-[14px]"
  return (
    <Reveal className="mx-auto mt-16 max-w-5xl">
      <h3 className="text-center text-[22px] font-medium tracking-[-0.02em]">Every plan, line by line</h3>
      <div className="mt-8 overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[460px] border-collapse">
          <caption className="sr-only">Plan comparison</caption>
          <thead>
            <tr className="border-b border-line bg-white/[0.03]">
              <th scope="col" className="sticky left-0 bg-[#0b0b0b] px-4 py-3 text-left font-mono text-[11.5px] tracking-[0.12em] text-neutral-400 uppercase">Plan</th>
              {plans.map((p) => <th key={p.id} scope="col" className="px-2 py-3 text-center text-[14px] font-medium sm:px-4 sm:text-[15px]">{p.name}</th>)}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line">
              <th scope="row" className="sticky left-0 w-[40%] bg-black px-3 py-3 text-left text-[13px] font-normal text-neutral-300 sm:px-4 sm:text-[14px]">Price a month</th>
              {plans.map((p) => <td key={p.id} className={cell}>{p.price_monthly === 0 ? "$0" : `$${p.price_monthly} a seat`}</td>)}
            </tr>
            <tr className="border-b border-line">
              <th scope="row" className="sticky left-0 w-[40%] bg-black px-3 py-3 text-left text-[13px] font-normal text-neutral-300 sm:px-4 sm:text-[14px]">Minimum seats</th>
              {plans.map((p) => <td key={p.id} className={cell}>{p.min_seats ?? 1}</td>)}
            </tr>
            {LIMITS.map(([label, key]) => (
              <tr key={key} className="border-b border-line">
                <th scope="row" className="sticky left-0 w-[40%] bg-black px-3 py-3 text-left text-[13px] font-normal text-neutral-300 sm:px-4 sm:text-[14px]">{label}</th>
                {plans.map((p) => <td key={p.id} className={cell}>{limit(key, p.limits[key] ?? null)}</td>)}
              </tr>
            ))}
            {features.map((f) => (
              <tr key={f} className="border-b border-line last:border-0">
                <th scope="row" className="sticky left-0 w-[40%] bg-black px-3 py-3 text-left text-[13px] font-normal text-neutral-300 sm:px-4 sm:text-[14px]">{featureLabels[f]}</th>
                {plans.map((p) => (
                  <td key={p.id} className={cell}>
                    {!p.features.includes(f) ? <Minus size={15} className="mx-auto text-neutral-600" aria-label="Not included" />
                      : comingSoon.includes(f) ? <span className="font-mono text-[12px] text-neutral-400">Coming</span>
                      : <Check size={16} className="mx-auto text-ok" aria-label="Included" />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Reveal>
  )
}
