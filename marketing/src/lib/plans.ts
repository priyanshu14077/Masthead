// The app enforces these plans; the page renders them. One file, so they can't drift.
import raw from "../../../plans.json"

export type Plan = (typeof raw.plans)[number] & { min_seats?: number }
export const plans = raw.plans as Plan[]
export const featureLabels = raw.feature_labels as Record<string, string>
export const annualMonths = raw.annual_months_charged
export const byok = raw.byok
