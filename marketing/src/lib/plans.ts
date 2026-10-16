// The app enforces these plans; the page renders them. One file, so they can't drift.
import raw from "../../../plans.json"

export type Plan = (typeof raw.plans)[number] & { min_seats?: number }
export const plans = raw.plans as Plan[]
export const featureLabels = raw.feature_labels as Record<string, string>
export const annualMonths = raw.annual_months_charged
export const byok = raw.byok
export const comingSoon = raw.coming_soon as string[]

/** The cheapest plan that includes a feature: what a feature card is tagged with. */
export const planFor = (feature: string) => plans.find((p) => p.features.includes(feature))
