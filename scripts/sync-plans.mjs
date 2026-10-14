// Copies plans.json, the pricing source of truth, into the marketing site.
// Run from anywhere: node scripts/sync-plans.mjs
import { readFile, writeFile } from "node:fs/promises"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const source = join(root, "plans.json")
const target = join(root, "marketing", "public", "plans.json")

const text = await readFile(source, "utf8")
const plans = JSON.parse(text) // fail loudly on invalid JSON instead of shipping it
if (!Array.isArray(plans.plans) || !plans.feature_labels) {
  throw new Error("plans.json needs a plans array and feature_labels")
}
await writeFile(target, text)
console.log(`Synced ${plans.plans.length} plans to ${target}`)
