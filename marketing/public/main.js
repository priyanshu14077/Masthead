// Masthead marketing site. Plain DOM, no framework, no build step.

const APP_URL = "https://app.masthead.example" // TODO: real domain
const DEMO_URL = "mailto:hello@masthead.example" // TODO: real domain

document.documentElement.classList.add("js")
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches

// Links ---------------------------------------------------------------------
// <a data-app-link="/signup?plan=team"> and <a data-demo-link> get their href here, so the
// domain lives in one place.
function wireLinks() {
  for (const a of document.querySelectorAll("[data-app-link]")) a.href = APP_URL + (a.dataset.appLink || "")
  for (const a of document.querySelectorAll("[data-demo-link]")) a.href = DEMO_URL
}

// Header menu (narrow screens) -----------------------------------------------
function wireMenu() {
  const header = document.querySelector(".site-header")
  const toggle = header?.querySelector(".menu-toggle")
  if (!toggle) return
  toggle.addEventListener("click", () => {
    const open = header.classList.toggle("open")
    toggle.setAttribute("aria-expanded", String(open))
    toggle.textContent = open ? "Close" : "Menu"
  })
  header.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && header.classList.contains("open")) { toggle.click(); toggle.focus() }
  })
}

// Seven-step tabs --------------------------------------------------------------
function wireSteps() {
  const tabs = [...document.querySelectorAll(".step-tab")]
  if (!tabs.length) return
  const panels = tabs.map((t) => document.getElementById(t.getAttribute("aria-controls")))
  function select(i, focus) {
    tabs.forEach((t, j) => {
      const on = i === j
      t.setAttribute("aria-selected", String(on))
      t.tabIndex = on ? 0 : -1
      panels[j].hidden = !on
    })
    if (focus) tabs[i].focus()
    if (panels[i].querySelector("[data-stream]")) streamDraft(panels[i].querySelector("[data-stream]"))
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => select(i, false))
    t.addEventListener("keydown", (e) => {
      const n = tabs.length
      const next = { ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: n - 1 }[e.key]
      if (next === undefined) return
      e.preventDefault()
      select((next + n) % n, true)
    })
  })
  select(0, false)
}

// The draft panel types its MDX out, like the real streaming draft.
const streamed = new WeakSet()
function streamDraft(pre) {
  if (streamed.has(pre)) return
  streamed.add(pre)
  const full = pre.dataset.full ?? pre.textContent
  pre.dataset.full = full
  if (reduceMotion) { pre.textContent = full; return }
  const caret = document.createElement("span")
  caret.className = "caret"
  caret.setAttribute("aria-hidden", "true")
  const text = document.createTextNode("")
  pre.replaceChildren(text, caret)
  let i = 0
  const tick = () => {
    i = Math.min(full.length, i + 3 + Math.floor(Math.random() * 6))
    text.data = full.slice(0, i)
    if (i < full.length) setTimeout(tick, 28)
    else setTimeout(() => caret.remove(), 1600)
  }
  tick()
}

// Reveal on view ------------------------------------------------------------------
function wireReveal() {
  const els = document.querySelectorAll(".reveal")
  if (reduceMotion || !("IntersectionObserver" in window)) { els.forEach((el) => el.classList.add("in")); return }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target) }
  }, { rootMargin: "0px 0px -8% 0px" })
  els.forEach((el) => io.observe(el))
}

// Plans ----------------------------------------------------------------------------
// plans.json is copied from the repo root by scripts/sync-plans.mjs. Every price on the
// site comes from it.
let plansPromise
function loadPlans() {
  plansPromise ??= fetch("plans.json", { cache: "no-cache" }).then((r) => {
    if (!r.ok) throw new Error(`plans.json: ${r.status}`)
    return r.json()
  })
  return plansPromise
}

function money(amount, currency) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase(), maximumFractionDigits: amount % 1 ? 2 : 0 }).format(amount)
}

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue
    if (k === "class") el.className = v
    else if (k === "text") el.textContent = v
    else el.setAttribute(k, v === true ? "" : v)
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c))
  return el
}

// One plan's price for a billing period: { amount, per, note }.
function priceFor(plan, data, billing) {
  const cur = data.currency
  const months = data.annual_months_charged
  if (plan.price_monthly === 0) return { amount: money(0, cur), per: "", note: "" }
  const unit = plan.per_seat ? " per seat" : ""
  if (billing === "annual") {
    const yearly = plan.price_monthly * months
    const minimum = plan.min_seats ? ` Minimum ${plan.min_seats} seats, ${money(yearly * plan.min_seats, cur)} a year.` : ""
    return { amount: money(yearly, cur), per: `${unit} / year`, note: `${months} months charged for 12.${minimum}` }
  }
  const minimum = plan.min_seats ? `Minimum ${plan.min_seats} seats, ${money(plan.price_monthly * plan.min_seats, cur)} a month.` : ""
  return { amount: money(plan.price_monthly, cur), per: `${unit} / month`, note: minimum }
}

function limitText(key, value) {
  if (value === null) return "Unlimited"
  if (key === "reviewers_required") return value === 0 ? "None" : String(value)
  return String(value)
}
const LIMIT_LABELS = { seats: "Seats", repos: "Blog repos", posts_per_month: "Posts a month", reviewers_required: "Required reviewers" }

// Landing page teaser: three prices, one line each.
async function renderTeaser() {
  const box = document.querySelector("[data-plans-teaser]")
  if (!box) return
  try {
    const data = await loadPlans()
    box.replaceChildren(...data.plans.map((p) => {
      const pr = priceFor(p, data, "monthly")
      return h("div", {},
        h("p", { class: "label" }, p.name),
        h("p", { class: "amount" }, pr.amount, h("span", { class: "sr-only" }, pr.per)),
        h("p", {}, p.per_seat ? `A seat a month, from ${p.min_seats} seats.` : "One seat."),
        h("p", {}, p.pitch))
    }))
  } catch (err) {
    console.warn(err)
  }
}

// Feature chips name the cheapest plan that includes the feature.
async function renderFeaturePlans() {
  const chips = document.querySelectorAll("[data-feature-plan]")
  if (!chips.length) return
  try {
    const data = await loadPlans()
    for (const chip of chips) {
      const plan = data.plans.find((p) => p.features.includes(chip.dataset.featurePlan))
      if (!plan) continue
      const last = plan === data.plans.at(-1)
      chip.textContent = plan.price_monthly === 0 ? "Every plan" : last ? plan.name : `${plan.name} and up`
    }
  } catch (err) {
    console.warn(err)
  }
}

// Pricing page: tier cards, billing toggle and the comparison table.
async function renderPricing() {
  const tiers = document.querySelector("[data-tiers]")
  if (!tiers) return
  let data
  try { data = await loadPlans() } catch (err) {
    tiers.replaceChildren(h("p", { class: "tier-note" }, "Prices didn't load. Email hello@masthead.example for the current price list."))
    console.error(err)
    return
  }
  const featured = "team"
  const cta = (p) => p.price_monthly === 0
    ? h("a", { class: "btn", "data-app-link": `/signup?plan=${p.id}` }, "Start free")
    : h("a", { class: "btn", "data-app-link": `/signup?plan=${p.id}` }, `Start ${p.name}`)

  const cards = data.plans.map((p, i) => {
    const prev = data.plans[i - 1]
    const added = prev ? p.features.filter((f) => !prev.features.includes(f)) : p.features
    const amount = h("span", { class: "amount" })
    const per = h("span", { class: "per" })
    const note = h("p", { class: "tier-note" })
    const card = h("article", { class: `tier ${p.id === featured ? "featured" : ""}`, "aria-labelledby": `tier-${p.id}` },
      h("p", { class: "label" }, { free: "Solo", team: "Teams", business: "Companies" }[p.id] ?? p.name),
      h("h3", { id: `tier-${p.id}` }, p.name),
      h("p", { class: "tier-pitch" }, p.pitch),
      h("p", { class: "price" }, amount, per),
      note,
      cta(p),
      h("dl", { class: "limits" }, ...Object.entries(LIMIT_LABELS).flatMap(([k, label]) => [h("dt", {}, label), h("dd", {}, limitText(k, p.limits[k]))])),
      h("ul", { class: "tier-list", "aria-label": prev ? `Added in ${p.name}` : `In ${p.name}` },
        prev ? h("li", { class: "plain" }, `Everything in ${prev.name}, plus:`) : null,
        ...added.map((f) => h("li", {}, data.feature_labels[f] ?? f))))
    return { plan: p, amount, per, note, card }
  })
  tiers.replaceChildren(...cards.map((c) => c.card))
  // The "Everything in X" line takes no square bullet.
  for (const li of tiers.querySelectorAll("li.plain")) { li.style.display = "block"; li.style.fontWeight = "600" }

  function setBilling(billing) {
    for (const c of cards) {
      const pr = priceFor(c.plan, data, billing)
      c.amount.textContent = pr.amount
      c.per.textContent = pr.per
      c.note.textContent = pr.note
    }
    for (const b of document.querySelectorAll("[data-billing]")) b.setAttribute("aria-pressed", String(b.dataset.billing === billing))
    const status = document.querySelector("[data-billing-status]")
    if (status) status.textContent = billing === "annual"
      ? `Annual billing: ${data.annual_months_charged} months charged for 12.`
      : "Monthly billing."
  }
  for (const b of document.querySelectorAll("[data-billing]")) b.addEventListener("click", () => setBilling(b.dataset.billing))
  setBilling("monthly")

  const annualNote = document.querySelector("[data-annual-note]")
  if (annualNote) annualNote.textContent = `Annual: ${data.annual_months_charged} months charged for 12`

  for (const el of document.querySelectorAll("[data-annual-months]")) el.textContent = String(data.annual_months_charged)
  for (const el of document.querySelectorAll("[data-min-seats]")) {
    const plan = data.plans.find((p) => p.id === el.dataset.minSeats)
    if (plan?.min_seats) el.textContent = String(plan.min_seats)
  }

  const byok = document.querySelector("[data-byok]")
  if (byok) byok.textContent = data.byok

  renderCompare(data)
  wireLinks()
}

function renderCompare(data) {
  const table = document.querySelector("[data-compare]")
  if (!table) return
  const plans = data.plans
  const head = h("thead", {}, h("tr", {}, h("th", { scope: "col" }, h("span", { class: "sr-only" }, "Feature")), ...plans.map((p) => h("th", { scope: "col" }, p.name))))
  const group = (label) => h("tr", { class: "group" }, h("th", { scope: "colgroup", colspan: String(plans.length + 1) }, label))
  const priceRow = h("tr", {}, h("th", { scope: "row" }, "Price a month"),
    ...plans.map((p) => h("td", {}, p.price_monthly === 0 ? money(0, data.currency) : `${money(p.price_monthly, data.currency)}${p.per_seat ? " a seat" : ""}`)))
  const minRow = h("tr", {}, h("th", { scope: "row" }, "Minimum seats"), ...plans.map((p) => h("td", {}, String(p.min_seats ?? 1))))
  const limitRows = Object.entries(LIMIT_LABELS).map(([k, label]) =>
    h("tr", {}, h("th", { scope: "row" }, label), ...plans.map((p) => h("td", {}, limitText(k, p.limits[k])))))
  const featureRows = Object.entries(data.feature_labels).map(([key, label]) =>
    h("tr", {}, h("th", { scope: "row" }, label), ...plans.map((p) => {
      const has = p.features.includes(key)
      return h("td", {}, h("span", { class: has ? "yes" : "no", "aria-hidden": "true" }), h("span", { class: "sr-only" }, has ? "Included" : "Not included"))
    })))
  const colgroup = h("colgroup", {}, h("col", { class: "feat" }), ...plans.map(() => h("col", {})))
  table.replaceChildren(
    h("caption", { class: "sr-only" }, "Every Masthead plan, compared"),
    colgroup, head,
    h("tbody", {}, group("Plan"), priceRow, minRow, ...limitRows, group("Features"), ...featureRows))
}

// The sticky header's height feeds scroll-padding and the pricing table's sticky head.
function trackHeader() {
  const header = document.querySelector(".site-header")
  if (!header) return
  const set = () => document.documentElement.style.setProperty("--header-h", `${header.offsetHeight}px`)
  set()
  if ("ResizeObserver" in window) new ResizeObserver(set).observe(header)
}

wireLinks()
trackHeader()
wireMenu()
wireSteps()
wireReveal()
renderTeaser()
renderFeaturePlans()
renderPricing()
for (const el of document.querySelectorAll("[data-year]")) el.textContent = String(new Date().getFullYear())
