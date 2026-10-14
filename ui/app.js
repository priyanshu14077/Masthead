// Masthead UI. Plain DOM, no framework: every value from the server is set as text, never as HTML.

const STATUSES = [
  ["idea", "Ideas"],
  ["outlined", "Outlined"],
  ["drafted", "Drafted"],
  ["checked", "Checked"],
  ["scheduled", "Scheduled"],
  ["published", "Published"],
]
const STEPS = [
  ["idea", "Idea"],
  ["outline", "Outline"],
  ["draft", "Draft"],
  ["check", "Check"],
  ["thumbnail", "Thumbnail"],
  ["social", "Distribution"],
  ["publish", "Publish"],
]
const RANK = Object.fromEntries(STATUSES.map(([s], i) => [s, i]))

const state = { info: null, campaigns: [], posts: [], filter: "all" }

// DOM helpers -------------------------------------------------------------
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue
    if (k === "class") el.className = v
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v)
    else if (k === "value") el.value = v
    else el.setAttribute(k, v === true ? "" : v)
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c))
  return el
}
const $ = (sel) => document.querySelector(sel)
/** replaceChildren that skips null and false, like h() does. */
const fill = (el, ...kids) => el.replaceChildren(...kids.flat().filter((k) => k !== null && k !== undefined && k !== false))

function toast(message, kind = "info", action = null) {
  const el = h("div", { class: `toast ${kind === "error" ? "error" : ""}` }, message, action ? [" ", h("a", { href: action.href }, action.label)] : null)
  $("#toasts").append(el)
  setTimeout(() => el.remove(), kind === "error" ? 9000 : 4000)
}

// The chosen workspace and blog are remembered per browser; the server checks membership on every request.
const pref = {
  get: (k) => { try { return localStorage.getItem(`masthead.${k}`) } catch { return null } },
  set: (k, v) => { try { v == null ? localStorage.removeItem(`masthead.${k}`) : localStorage.setItem(`masthead.${k}`, String(v)) } catch { /* private window */ } },
}
function scopeHeaders() {
  const out = {}
  if (pref.get("workspace")) out["x-masthead-workspace"] = pref.get("workspace")
  if (pref.get("site")) out["x-masthead-site"] = pref.get("site")
  return out
}

class ApiError extends Error {
  constructor(message, status, upgradeTo) { super(message); this.status = status; this.upgradeTo = upgradeTo }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "content-type": "application/json", ...scopeHeaders(), ...(options.headers || {}) },
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (res.status === 401) { renderSignIn(); throw new ApiError("Sign in to continue.", 401) }
  if (!res.ok) throw new ApiError(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`, res.status, res.headers.get("x-upgrade-to"))
  return data
}

/** Runs an action with the button disabled and a spinner, and reports errors as toasts. */
async function busy(button, label, fn) {
  const original = [...button.childNodes]
  button.disabled = true
  button.replaceChildren(h("span", { class: "spinner", "aria-hidden": "true" }), label)
  try {
    return await fn()
  } catch (e) {
    reportError(e)
  } finally {
    button.disabled = false
    button.replaceChildren(...original)
  }
}

function reportError(e) {
  if (e.status === 401) return
  toast(e.message, "error", e.status === 402 && state.info?.permissions.includes("manage_billing") ? { href: "#/settings/billing", label: "See plans" } : null)
}
const can = (perm) => !!state.info?.permissions.includes(perm)
const has = (feature) => !!state.info?.plan.features.includes(feature)
const cloud = () => state.info?.mode === "cloud"

const money = (n) => `$${(n || 0).toFixed(n >= 1 ? 2 : 4)}`
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "")
const lines = (text) => text.split("\n").map((s) => s.trim()).filter(Boolean)
const csv = (text) => text.split(",").map((s) => s.trim()).filter(Boolean)
const campaignName = (id) => state.campaigns.find((c) => c.id === id)?.name

// Data --------------------------------------------------------------------
async function load() {
  const [info, campaigns, posts] = await Promise.all([api("/api/state"), api("/api/campaigns"), api("/api/posts")])
  Object.assign(state, { info, campaigns, posts })
  pref.set("workspace", info.workspace.id)
  pref.set("site", info.site?.id ?? null)
}

function upsert(post) {
  const i = state.posts.findIndex((p) => p.id === post.id)
  if (i >= 0) state.posts[i] = post
  else state.posts.push(post)
  return post
}

// Chrome --------------------------------------------------------------------
function switcher(label, items, current, key) {
  const select = h("select", { class: "switch", "aria-label": label },
    ...items.map((i) => h("option", { value: i.id, selected: i.id === current }, i.name)))
  select.addEventListener("change", async () => {
    pref.set(key, select.value)
    if (key === "workspace") pref.set("site", null)
    await load(); location.hash = "#/"; render()
  })
  return select
}

function renderStatus() {
  const { info } = state
  document.title = info.site_name ? `Masthead · ${info.site_name}` : "Masthead"
  $(".brand").textContent = "Masthead"
  const ai = { ready: ["AI ready", false], fake: ["Fake AI mode", true], missing: [cloud() ? "No API key" : "No API credentials", true] }[info.ai]
  const aiPill = h(cloud() && can("manage_keys") ? "a" : "span", { class: `pill ${ai[1] ? "warn" : ""}`, href: cloud() && can("manage_keys") ? "#/settings/key" : null,
    title: !cloud() && info.ai === "missing" ? "Add ANTHROPIC_API_KEY to .env, or run `ant auth login`, then restart." : null }, h("span", { class: "dot" }), ai[0])
  if (!cloud()) {
    $("#status").replaceChildren(
      aiPill,
      h("span", { class: `pill ${info.protected_branch ? "warn" : ""}`, title: info.protected_branch ? "Publishing is blocked on this branch because it deploys the live site." : "Publishing commits here. Nothing is pushed." }, h("span", { class: "dot" }), `branch: ${info.branch || "none"}`),
      h("span", { class: "pill" }, `spent this month ${money(info.spend.month_usd)}`),
    )
    return
  }
  const workspaces = state.workspaces || [info.workspace]
  fill($("#status"),
    workspaces.length > 1 ? switcher("Workspace", workspaces, info.workspace.id, "workspace") : h("span", { class: "pill" }, info.workspace.name),
    info.sites.length > 1 ? switcher("Blog", info.sites, info.site?.id, "site") : info.site ? h("span", { class: "pill" }, info.site.name) : null,
    h("a", { class: "pill", href: "#/settings/billing" }, `${info.plan.name} plan${info.plan.status === "trialing" ? " · trial" : ""}`),
    aiPill,
    h("span", { class: "pill", title: info.user.name || info.user.login }, info.user.avatar_url ? h("img", { class: "avatar", src: info.user.avatar_url, alt: "" }) : null, info.user.login),
    h("form", { method: "post", action: "/auth/logout", class: "inline" }, h("button", { class: "pill linkish", type: "submit" }, "Sign out")),
  )
}

function renderSidebar() {
  const counts = (cid) => state.posts.filter((p) => cid === "all" || (cid === "none" ? !p.campaign_id : p.campaign_id === cid)).length
  const link = (id, label) =>
    h("button", { class: "side-link", "aria-current": String(state.filter === id), onclick: () => { state.filter = id; location.hash = "#/"; render() } },
      h("span", {}, label), h("span", { class: "count" }, counts(id)))
  fill($("#sidebar"),
    can("write") && state.info.site ? h("button", { class: "btn", onclick: newIdeaDialog }, "+ New idea") : null,
    h("div", { class: "side-section" },
      h("p", { class: "side-title" }, "Campaigns"),
      link("all", "All posts"),
      ...state.campaigns.map((c) => link(c.id, c.name)),
      link("none", "No campaign"),
      can("campaigns") ? h("button", { class: "link", style: "text-align:left;padding:6px 10px", onclick: newCampaignDialog }, "+ New campaign") : null,
    ),
    h("div", { class: "side-section" },
      h("p", { class: "side-title" }, "AI spend"),
      h("p", { class: "spend", style: "margin:0" }, money(state.info.spend.total_usd)),
      h("p", { class: "small muted", style: "margin:0" }, `${state.info.spend.calls} calls · drafting on Sonnet 5.5, checks and social on Haiku 5.5`),
    ),
    h("div", { class: "side-section" },
      h("p", { class: "side-title" }, "On the site"),
      h("p", { class: "small muted", style: "margin:0" }, `${state.info.site_posts.filter((p) => !p.draft).length} published · ${state.info.site_posts.filter((p) => p.draft).length} drafts`),
      state.info.blog_preview ? h("a", { class: "small", href: state.info.blog_preview, target: "_blank", rel: "noreferrer" }, "Open the blog on the dev server ↗") : null,
    ),
    cloud() ? h("div", { class: "side-section" },
      h("p", { class: "side-title" }, "Workspace"),
      ...SETTINGS.filter(([, , perm]) => !perm || can(perm)).map(([key, label]) =>
        h("a", { class: "side-link", href: `#/settings/${key}`, "aria-current": String(location.hash === `#/settings/${key}`) }, h("span", {}, label))),
      h("button", { class: "link", style: "text-align:left;padding:6px 10px", onclick: newWorkspaceDialog }, "+ New workspace"),
    ) : null,
  )
}

// Dialogs -------------------------------------------------------------------
function dialog(title, fields, submitLabel, onSubmit) {
  const form = h("form", { class: "stack", method: "dialog" }, h("h2", {}, title), ...fields,
    h("div", { class: "row" }, h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn ghost", onclick: () => dlg.close() }, "Cancel"),
      h("button", { type: "submit", class: "btn" }, submitLabel)))
  const dlg = h("dialog", {}, form)
  form.addEventListener("submit", async (e) => {
    e.preventDefault()
    const button = form.querySelector('button[type="submit"]')
    await busy(button, "Saving", async () => { await onSubmit(new FormData(form)); dlg.close() })
  })
  dlg.addEventListener("close", () => dlg.remove())
  document.body.append(dlg)
  dlg.showModal()
}

function campaignSelect(selected) {
  return h("select", { name: "campaign_id" }, h("option", { value: "" }, "No campaign"),
    ...state.campaigns.map((c) => h("option", { value: c.id, selected: c.id === selected }, c.name)))
}

function newIdeaDialog() {
  const preset = typeof state.filter === "number" ? state.filter : null
  dialog("New idea", [
    h("label", { class: "field" }, "The idea", h("span", { class: "hint" }, "A sentence or two: what the post is about and who it's for."),
      h("textarea", { name: "idea", required: true, rows: 3, placeholder: "How we stream an agent's answer through three services without stalls" })),
    h("label", { class: "field" }, "Notes and source material", h("span", { class: "hint" }, "Paste anything: design docs, numbers, lessons. Numbers in the post will come only from here."),
      h("textarea", { name: "notes", rows: 8 })),
    h("label", { class: "field" }, "Names allowed to appear", h("span", { class: "hint" }, "Companies or products you're allowed to name, comma separated. Everything else is kept generic."),
      h("input", { type: "text", name: "allowed_names", placeholder: "Acme, Anthropic" })),
    h("label", { class: "field" }, "Campaign", campaignSelect(preset)),
  ], "Add idea", async (data) => {
    const post = upsert(await api("/api/posts", { method: "POST", body: {
      idea: data.get("idea"), notes: data.get("notes"), allowed_names: csv(data.get("allowed_names") || ""),
      campaign_id: data.get("campaign_id") ? Number(data.get("campaign_id")) : null,
    } }))
    location.hash = `#/post/${post.id}/idea`
  })
}

function newCampaignDialog() {
  dialog("New campaign", [
    h("label", { class: "field" }, "Name", h("input", { type: "text", name: "name", required: true, placeholder: "System Design 101" })),
    h("label", { class: "field" }, "Kind", h("span", { class: "hint" }, "A series numbers its parts and links them on the site."),
      h("select", { name: "kind" }, h("option", { value: "series" }, "Series"), h("option", { value: "launch" }, "Launch"), h("option", { value: "theme" }, "Theme"))),
    h("label", { class: "field" }, "Description", h("textarea", { name: "description", rows: 3 })),
  ], "Create campaign", async (data) => {
    const c = await api("/api/campaigns", { method: "POST", body: { name: data.get("name"), kind: data.get("kind"), description: data.get("description") } })
    state.campaigns.push({ ...c, post_count: 0 })
    state.filter = c.id
    render()
  })
}

// Board ---------------------------------------------------------------------
function postCard(p) {
  return h("button", { class: "card post-card", onclick: () => (location.hash = `#/post/${p.id}/${nextStep(p)}`) },
    p.campaign_id ? h("p", { class: "eyebrow", style: "font-size:12.5px" }, campaignName(p.campaign_id) + (p.series_order ? ` · Part ${p.series_order}` : "")) : null,
    h("p", { class: "title" }, p.title || p.idea),
    h("div", { class: "meta" },
      p.publish_at ? h("span", {}, `${p.status === "published" ? "Published" : "Goes live"} ${fmtDate(p.status === "published" ? p.published_at : p.publish_at)}`) : null,
      p.check_result ? h("span", { class: `badge ${p.check_result.verdict}` }, p.check_result.verdict) : null,
      p.spend_usd ? h("span", {}, money(p.spend_usd)) : null),
    p.last_error ? h("p", { class: "err" }, `Scheduled publish failed: ${p.last_error}`) : null)
}

function nextStep(p) {
  return { idea: "outline", outlined: "draft", drafted: "check", checked: "publish", scheduled: "publish", published: "publish" }[p.status]
}

function renderBoard() {
  if (!state.info.site) {
    $("#main").replaceChildren(h("div", { class: "card empty stack", style: "align-items:center" },
      h("p", { class: "hand" }, "no blog connected yet"),
      h("h2", {}, "Connect the repository your blog lives in"),
      can("manage_sites") ? h("a", { class: "btn", href: "#/settings/sites" }, "Connect a blog") : h("p", { class: "muted" }, "An owner of this workspace can connect one.")))
    return
  }
  const posts = state.posts.filter((p) => state.filter === "all" || (state.filter === "none" ? !p.campaign_id : p.campaign_id === state.filter))
  const campaign = typeof state.filter === "number" ? state.campaigns.find((c) => c.id === state.filter) : null
  const head = h("div", { class: "panel-head", style: "margin-bottom:20px" },
    h("div", {}, h("p", { class: "eyebrow" }, campaign ? `${campaign.kind[0].toUpperCase()}${campaign.kind.slice(1)} campaign` : "Campaign board"),
      h("h1", {}, campaign ? campaign.name : "Every post, idea to published"),
      campaign?.description ? h("p", { class: "muted", style: "margin:6px 0 0;max-width:60ch" }, campaign.description) : null),
    h("div", { class: "row" },
      can("publish") && has("scheduling") && h("button", { class: "btn ghost small", onclick: (e) => busy(e.currentTarget, "Checking", async () => {
        const { published } = await api("/api/scheduler/run", { method: "POST" })
        await load(); render()
        toast(published.length ? `Published ${published.length} scheduled post(s).` : "Nothing is due today.")
      }) }, "Publish what's due"),
      campaign ? h("button", { class: "btn ghost small", onclick: () => renameCampaign(campaign) }, "Edit campaign") : null))

  if (!state.posts.length) {
    $("#main").replaceChildren(head, h("div", { class: "card empty" }, h("p", { class: "hand" }, "nothing on the board yet"),
      h("p", { class: "muted" }, "Add an idea, and Masthead takes it through outline, draft, check and publish."),
      h("button", { class: "btn", onclick: newIdeaDialog }, "+ New idea")))
    return
  }
  const board = h("div", { class: "board" }, ...STATUSES.map(([status, label]) => {
    const items = posts.filter((p) => p.status === status)
    return h("section", { class: "column", "aria-label": label },
      h("div", { class: "column-head" }, h("h3", {}, label), h("span", { class: "small muted" }, items.length)),
      ...(items.length ? items.map(postCard) : [h("div", { class: "column-empty" }, "None")]))
  }))
  $("#main").replaceChildren(head, board)
}

function renameCampaign(c) {
  dialog("Edit campaign", [
    h("label", { class: "field" }, "Name", h("input", { type: "text", name: "name", required: true, value: c.name })),
    h("label", { class: "field" }, "Series name on the site", h("span", { class: "hint" }, "Shown on each part, like “Part 2 of 5 in System Design 101”."),
      h("input", { type: "text", name: "series_name", value: c.series_name || "" })),
    h("label", { class: "field" }, "Description", h("textarea", { name: "description", rows: 3, value: c.description })),
  ], "Save", async (data) => {
    const updated = await api(`/api/campaigns/${c.id}`, { method: "PATCH", body: { name: data.get("name"), series_name: data.get("series_name") || null, description: data.get("description") } })
    Object.assign(c, updated)
    render()
  })
}

// Post editor ---------------------------------------------------------------
function stepDone(p, step) {
  const r = RANK[p.status]
  return {
    idea: true, outline: r >= 1, draft: r >= 2, check: !!p.check_result, thumbnail: !!p.thumb_spec,
    social: !!p.social, publish: p.status === "published",
  }[step]
}

function renderPost(id, step) {
  const p = state.posts.find((x) => x.id === id)
  if (!p) { $("#main").replaceChildren(h("p", {}, "That post doesn't exist."), h("a", { href: "#/" }, "Back to the board")); return }
  const nav = h("nav", { class: "steps", "aria-label": "Steps" }, ...STEPS.map(([key, label], i) =>
    h("button", { class: `step-link ${stepDone(p, key) ? "done" : ""}`, "aria-current": key === step ? "step" : null, onclick: () => (location.hash = `#/post/${id}/${key}`) },
      h("span", { class: "n" }, i + 1), label)))
  const panel = { idea: ideaPanel, outline: outlinePanel, draft: draftPanel, check: checkPanel, thumbnail: thumbPanel, social: socialPanel, publish: publishPanel }[step]
  $("#main").replaceChildren(
    h("div", { class: "row" }, h("a", { href: "#/", class: "small" }, "← Board"), h("span", { class: "spacer" }),
      h("span", { class: "small muted" }, `Status: ${p.status}${p.spend_usd ? ` · spent ${money(p.spend_usd)}` : ""}`)),
    h("h1", { style: "margin-top:8px" }, p.title || p.idea),
    h("div", { class: "editor" }, nav, h("section", { class: "panel" }, ...(panel || ideaPanel)(p))))
}

const go = (p, step) => (location.hash = `#/post/${p.id}/${step}`)
async function save(p, body) { return upsert(await api(`/api/posts/${p.id}`, { method: "PATCH", body })) }

function ideaPanel(p) {
  const idea = h("textarea", { rows: 3, value: p.idea })
  const notes = h("textarea", { rows: 12, value: p.notes })
  const names = h("input", { type: "text", value: (p.allowed_names || []).join(", ") })
  const campaign = campaignSelect(p.campaign_id)
  const order = h("input", { type: "number", min: 1, value: p.series_order ?? "" })
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 1"), h("h2", {}, "The idea and your notes"))),
    h("label", { class: "field" }, "The idea", idea),
    h("label", { class: "field" }, "Notes and source material", h("span", { class: "hint" }, "The model treats these as the only source of facts and numbers."), notes),
    h("div", { class: "grid-2" },
      h("label", { class: "field" }, "Names allowed to appear", h("span", { class: "hint" }, "Comma separated. Anything else is described generically."), names),
      h("div", { class: "grid-2" }, h("label", { class: "field" }, "Campaign", campaign), h("label", { class: "field" }, "Part number", order))),
    h("div", { class: "row" },
      h("button", { class: "btn ghost", onclick: (e) => busy(e.currentTarget, "Saving", async () => {
        await save(p, { idea: idea.value, notes: notes.value, allowed_names: csv(names.value), campaign_id: campaign.value ? Number(campaign.value) : null, series_order: order.value ? Number(order.value) : null })
        toast("Saved.")
      }) }, "Save"),
      h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Outlining with Claude", async () => {
        await save(p, { idea: idea.value, notes: notes.value, allowed_names: csv(names.value), campaign_id: campaign.value ? Number(campaign.value) : null, series_order: order.value ? Number(order.value) : null })
        upsert(await api(`/api/posts/${p.id}/outline`, { method: "POST" }))
        await refreshInfo(); go(p, "outline")
      }) }, p.outline ? "Regenerate outline →" : "Generate outline →"),
      h("span", { class: "spacer" }),
      !p.written ? h("button", { class: "link", style: "color:var(--ink-60)", onclick: async () => {
        if (!confirm("Delete this post from Masthead? Nothing in the site changes.")) return
        try { await api(`/api/posts/${p.id}`, { method: "DELETE" }); state.posts = state.posts.filter((x) => x.id !== p.id); location.hash = "#/" } catch (e) { toast(e.message, "error") }
      } }, "Delete") : null),
  ]
}

function sectionsToText(sections) {
  return (sections || []).map((s) => `${"#".repeat(s.level)} ${s.heading}\n${s.points.map((pt) => `- ${pt}`).join("\n")}`).join("\n\n")
}
function textToSections(text) {
  const out = []
  for (const line of text.split("\n")) {
    const m = /^(#{2,3})\s+(.+)$/.exec(line.trim())
    if (m) out.push({ heading: m[2].trim(), level: m[1].length, points: [] })
    else if (/^[-*]\s+/.test(line.trim()) && out.length) out[out.length - 1].points.push(line.trim().replace(/^[-*]\s+/, ""))
  }
  return out
}

function outlinePanel(p) {
  if (!p.outline) return [h("div", { class: "callout" }, "No outline yet. Generate one from the idea step."), h("button", { class: "btn", onclick: () => go(p, "idea") }, "← Back to the idea")]
  const f = {
    title: h("input", { type: "text", value: p.title || "" }),
    subtitle: h("input", { type: "text", value: p.subtitle || "" }),
    slug: h("input", { type: "text", value: p.slug || "", disabled: !!p.written }),
    summary: h("textarea", { rows: 3, value: p.summary || "" }),
    tags: h("input", { type: "text", value: (p.tags || []).join(", ") }),
    tldr: h("textarea", { rows: 4, value: (p.tldr || []).join("\n") }),
    sections: h("textarea", { class: "code", style: "min-height:320px", value: sectionsToText(p.outline.sections) }),
  }
  const collect = () => ({
    title: f.title.value, subtitle: f.subtitle.value, summary: f.summary.value, tags: csv(f.tags.value), tldr: lines(f.tldr.value),
    ...(p.written ? {} : { slug: f.slug.value }),
    outline: { ...p.outline, title: f.title.value, sections: textToSections(f.sections.value) },
  })
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 2"), h("h2", {}, "Outline")),
      h("span", { class: "small muted" }, `Existing tags: ${state.info.tags.join(", ") || "none"}`)),
    h("div", { class: "grid-2" }, h("label", { class: "field" }, "Title", f.title), h("label", { class: "field" }, "Slug", h("span", { class: "hint" }, p.written ? "Fixed: the post is already in the site." : "The URL: /blog/<slug>"), f.slug)),
    h("label", { class: "field" }, "Subtitle", f.subtitle),
    h("label", { class: "field" }, "Summary", h("span", { class: "hint" }, "Used on cards, in search results and in the feed."), f.summary),
    h("div", { class: "grid-2" }, h("label", { class: "field" }, "Tags", f.tags), h("label", { class: "field" }, "TL;DR", h("span", { class: "hint" }, "One point per line."), f.tldr)),
    h("label", { class: "field" }, "Sections", h("span", { class: "hint" }, "## or ### headings, each followed by - points. The draft follows this order."), f.sections),
    p.outline.diagram_ideas?.length ? h("div", { class: "callout" }, h("strong", {}, "Diagram ideas: "), p.outline.diagram_ideas.join(" · ")) : null,
    h("div", { class: "row" },
      h("button", { class: "btn ghost", onclick: (e) => busy(e.currentTarget, "Saving", async () => { await save(p, collect()); toast("Outline saved.") }) }, "Save outline"),
      h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Saving", async () => { await save(p, collect()); go(p, "draft") }) }, "Approve and go to the draft →")),
  ]
}

function draftPanel(p) {
  if (!p.outline) return [h("div", { class: "callout" }, "Approve an outline first."), h("button", { class: "btn", onclick: () => go(p, "outline") }, "← Outline")]
  const body = h("textarea", { class: "code", value: p.body || "", spellcheck: "true", "aria-label": "Post body (MDX)" })
  const status = h("p", { class: "small muted", style: "margin:0" }, p.body ? `${p.body.split(/\s+/).length} words` : "No draft yet.")
  const write = h("button", { class: "btn" }, p.body ? "Rewrite with Claude" : "Write the draft with Claude")
  write.addEventListener("click", async () => {
    if (p.body && !confirm("Replace the current draft with a new one?")) return
    body.value = ""
    write.disabled = true
    write.replaceChildren(h("span", { class: "spinner", "aria-hidden": "true" }), "Writing")
    let words = 0
    try {
      const res = await fetch(`/api/posts/${p.id}/draft`, { method: "POST" })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Request failed (${res.status})`)
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      let buffer = ""
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += value
        const frames = buffer.split("\n\n")
        buffer = frames.pop() ?? ""
        for (const frame of frames) {
          const event = /^event: (.*)$/m.exec(frame)?.[1]
          const data = JSON.parse(frame.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n") || "{}")
          if (event === "delta") {
            body.value += data.text
            body.scrollTop = body.scrollHeight
            words = body.value.split(/\s+/).length
            status.textContent = `Writing… ${words} words`
          } else if (event === "done") {
            upsert(data)
            await refreshInfo()
            toast("Draft written. Read it through, then run the check.")
            renderPost(p.id, "draft")
            return
          } else if (event === "error") {
            throw new Error(data.message + (data.partial ? " The partial draft was kept." : ""))
          }
        }
      }
    } catch (e) {
      toast(e.message, "error")
      await load()
      renderPost(p.id, "draft")
    }
  })
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 3"), h("h2", {}, "Draft")), status),
    h("div", { class: "callout" }, "The body is MDX using the site's components. Edit freely; saving after a check means checking again."),
    body,
    h("div", { class: "row" },
      write,
      h("button", { class: "btn ghost", onclick: (e) => busy(e.currentTarget, "Saving", async () => { await save(p, { body: body.value }); toast("Draft saved.") }) }, "Save"),
      h("button", { class: "btn ghost", onclick: (e) => busy(e.currentTarget, "Writing to the site", async () => {
        await save(p, { body: body.value })
        const post = upsert(await api(`/api/posts/${p.id}/preview`, { method: "POST" }))
        toast(cloud() ? "Draft pushed to its pull request. Your blog's preview deploy picks it up." : `Written to ${state.info.posts_dir} as a draft. It shows on the dev server only.`)
        if (post.preview_url) window.open(post.preview_url, "_blank", "noreferrer")
        renderPost(p.id, "draft")
      }) }, cloud() ? "Preview in a pull request ↗" : "Preview on the dev server ↗"),
      h("span", { class: "spacer" }),
      h("button", { class: "link", onclick: () => go(p, "check") }, "Next: check →")),
  ]
}

function checkPanel(p) {
  if (!p.body) return [h("div", { class: "callout" }, "Write a draft first."), h("button", { class: "btn", onclick: () => go(p, "draft") }, "← Draft")]
  const r = p.check_result
  const stale = r && p.gate.missing.some((m) => m.startsWith("Run the confidentiality check"))
  const blocks = []
  if (r) {
    blocks.push(h("div", { class: "row" }, h("span", { class: `badge ${r.verdict}` }, { clear: "Clear to publish", review: "Needs your review", block: "Blocked" }[r.verdict]),
      h("span", { class: "small muted" }, `${r.findings.length} finding(s)`), stale ? h("span", { class: "small", style: "color:var(--accent)" }, "The draft changed since this check. Run it again.") : null))
    if (r.mdx_error) blocks.push(h("div", { class: "callout warn" }, h("strong", {}, "The draft won't build: "), r.mdx_error))
    if (r.findings.length) {
      const order = { high: 0, medium: 1, low: 2 }
      blocks.push(h("ul", { class: "findings" }, ...[...r.findings].sort((a, b) => order[a.severity] - order[b.severity]).map((f) =>
        h("li", { class: `finding ${f.severity}` },
          h("div", { class: "row" }, h("strong", {}, f.severity), h("span", { class: "tag" }, f.kind)),
          h("q", {}, f.quote), h("div", {}, f.why), h("div", { class: "small muted" }, `Suggestion: ${f.suggestion}`)))))
    }
    const canAck = r.verdict === "review" && !r.mdx_error && !stale
    if (canAck) {
      const box = h("input", { type: "checkbox", checked: !!p.check_ack, id: "ack" })
      box.addEventListener("change", async () => {
        try { upsert(await api(`/api/posts/${p.id}/check/ack`, { method: "POST", body: { acknowledged: box.checked } })) } catch (e) { toast(e.message, "error") }
      })
      blocks.push(h("label", { class: "row", for: "ack" }, box, "I've reviewed these findings and they're fine to publish."))
    }
    if (r.verdict === "block") blocks.push(h("div", { class: "callout warn" }, "Fix the high-severity findings in the draft, save, then check again."))
  }
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 4"), h("h2", {}, "Confidentiality and fact check"))),
    h("p", { class: "muted", style: "margin:0;max-width:70ch" }, "Claude Haiku reads the draft for names outside your allowed list, internal details, security weaknesses, personal data and numbers that aren't in your notes. Local checks add secrets, internal hosts and every external link to verify. The MDX is compiled too, so a broken post can't reach the site."),
    h("div", { class: "row" },
      h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Checking", async () => { upsert(await api(`/api/posts/${p.id}/check`, { method: "POST" })); await refreshInfo(); renderPost(p.id, "check") }) }, r ? "Check again" : "Run the check"),
      h("button", { class: "link", onclick: () => go(p, "draft") }, "← Edit the draft")),
    ...blocks,
  ]
}

function thumbPanel(p) {
  const img = p.thumb_spec ? h("img", { class: "thumb", src: `/api/posts/${p.id}/thumbnail.svg?v=${encodeURIComponent(p.updated_at)}`, alt: p.thumb_spec.title }) : h("div", { class: "callout" }, "No thumbnail yet.")
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 5"), h("h2", {}, "Thumbnail diagram"))),
    h("p", { class: "muted", style: "margin:0;max-width:70ch" }, "Claude designs the structure, and Masthead draws it in your blog's thumbnail palette. It's written into the site when you preview or publish."),
    img,
    h("div", { class: "row" },
      h("button", { class: "btn", disabled: !p.body, onclick: (e) => busy(e.currentTarget, "Designing", async () => { upsert(await api(`/api/posts/${p.id}/thumbnail`, { method: "POST" })); await refreshInfo(); renderPost(p.id, "thumbnail") }) }, p.thumb_spec ? "Redesign" : "Design the thumbnail"),
      h("span", { class: "small muted" }, "Optional. Posts without one simply show no image.")),
  ]
}

function socialPanel(p) {
  const s = p.social
  const block = (label, value, key) => {
    const area = h("textarea", { rows: key === "x_thread" ? 8 : 6, value: Array.isArray(value) ? value.join("\n\n---\n\n") : value })
    return h("div", { class: "copy-block" },
      h("div", { class: "row" }, h("h3", {}, label), h("span", { class: "spacer" }),
        h("button", { class: "btn ghost small", onclick: async () => { await navigator.clipboard.writeText(area.value); toast(`${label} copied.`) } }, "Copy")),
      area,
      key === "x_thread" ? h("span", { class: "small muted" }, "Posts are separated by ---. Each stays under 270 characters.") : null)
  }
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 6"), h("h2", {}, "Distribution copy"))),
    h("p", { class: "muted", style: "margin:0;max-width:70ch" }, `Drafted by Claude Haiku from the post, for you to post by hand. Links point to ${p.public_url || "the post"}.`),
    s ? [block("LinkedIn", s.linkedin, "linkedin"), block("X thread", s.x_thread, "x_thread"), block("Newsletter", s.newsletter, "newsletter")] : h("div", { class: "callout" }, "Nothing yet."),
    h("div", { class: "row" },
      h("button", { class: "btn", disabled: !p.body, onclick: (e) => busy(e.currentTarget, "Writing", async () => { upsert(await api(`/api/posts/${p.id}/social`, { method: "POST" })); await refreshInfo(); renderPost(p.id, "social") }) }, s ? "Write again" : "Write the copy")),
  ]
}

function reviewCard(p) {
  const r = p.gate.review
  if (!cloud() || !has("review_workflow")) return null
  const mine = p.author_id === state.info.user.id
  const note = h("textarea", { rows: 2, placeholder: "What should change" })
  const decide = (decision) => (e) => busy(e.currentTarget, "Saving", async () => {
    upsert(await api(`/api/posts/${p.id}/review`, { method: "POST", body: { decision, note: note.value } }))
    renderPost(p.id, "publish")
  })
  return h("div", { class: "card stack" },
    h("h3", {}, "Review"),
    h("p", { class: "small muted", style: "margin:0" }, r.required ? `Needs ${r.required} approval${r.required > 1 ? "s" : ""} from someone other than the author. Any edit after approval needs approving again.` : "No approval is required on this blog."),
    r.approved.length ? h("p", { style: "margin:0" }, `Approved by ${r.approved.join(", ")}`) : null,
    ...r.changes.map((c) => h("div", { class: "callout warn" }, h("strong", {}, `${c.login} asked for changes: `), c.note || "No note.")),
    can("review") && !mine && p.status !== "published" ? [note, h("div", { class: "row" },
      h("button", { class: "btn", onclick: decide("approved") }, "Approve"),
      h("button", { class: "btn ghost", onclick: decide("changes") }, "Request changes"))] : null)
}

function publishPanel(p) {
  const today = new Date().toISOString().slice(0, 10)
  const when = h("input", { type: "date", min: today, value: p.publish_at || today, style: "max-width:200px" })
  const blocked = !cloud() && state.info.protected_branch
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 7"), h("h2", {}, p.status === "published" ? "Published" : "Schedule or publish"))),
    p.gate.ready ? h("div", { class: "callout" }, cloud()
      ? "Ready. Publishing opens a pull request with the post and its thumbnail. Merge it to go live."
      : `Ready. Publishing writes the post into ${state.info.posts_dir}, commits it on the current branch, and never pushes. Push and merge yourself to go live.`)
      : h("div", { class: "callout warn" }, h("strong", {}, "Not ready yet:"), h("ul", { class: "gate" }, ...p.gate.missing.map((m) => h("li", {}, m)))),
    blocked ? h("div", { class: "callout warn" }, `You're on ${state.info.branch}, which deploys the live site. Switch to a working branch before publishing.`) : null,
    p.last_error ? h("div", { class: "callout warn" }, h("strong", {}, "Last scheduled attempt failed: "), p.last_error) : null,
    h("dl", { class: "kv" },
      h("dt", {}, "Status"), h("dd", {}, p.status),
      h("dt", {}, "File"), h("dd", { class: "mono" }, p.slug ? `${state.info.posts_dir}/${p.slug}.mdx` : "—"),
      h("dt", {}, "Campaign"), h("dd", {}, campaignName(p.campaign_id) || "None"),
      p.publish_at ? [h("dt", {}, "Scheduled for"), h("dd", {}, fmtDate(p.publish_at))] : null,
      p.published_at ? [h("dt", {}, "Published"), h("dd", {}, fmtDate(p.published_at))] : null,
      p.commit_sha ? [h("dt", {}, "Commit"), h("dd", { class: "mono" }, p.commit_sha)] : null,
      p.pr_url ? [h("dt", {}, "Pull request"), h("dd", {}, h("a", { href: p.pr_url, target: "_blank", rel: "noreferrer" }, p.pr_url.replace("https://github.com/", "")))] : null,
      p.public_url ? [h("dt", {}, cloud() ? "Live URL after merge" : "Live URL after push"), h("dd", { class: "mono" }, p.public_url)] : null),
    reviewCard(p),
    p.status === "published" || !can("publish") ? null : !has("scheduling") ? h("div", { class: "card stack" }, h("h3", {}, "Schedule"),
      h("p", { class: "small muted", style: "margin:0" }, "Scheduling is on the Team plan."), can("manage_billing") ? h("a", { href: "#/settings/billing" }, "See plans") : null) : h("div", { class: "card stack" },
      h("h3", {}, "Schedule"),
      h("p", { class: "small muted", style: "margin:0" }, cloud() ? "Due posts get their pull request on the morning they're due." : "While Masthead is running, it publishes due posts every minute. If it was closed, use “Publish what's due” on the board."),
      h("div", { class: "row" }, when,
        h("button", { class: "btn ghost", disabled: !p.gate.ready, onclick: (e) => busy(e.currentTarget, "Scheduling", async () => { upsert(await api(`/api/posts/${p.id}/schedule`, { method: "POST", body: { publish_at: when.value } })); toast(`Scheduled for ${fmtDate(when.value)}.`); renderPost(p.id, "publish") }) }, p.status === "scheduled" ? "Reschedule" : "Schedule"),
        p.status === "scheduled" ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Unscheduling", async () => { upsert(await api(`/api/posts/${p.id}/unschedule`, { method: "POST" })); renderPost(p.id, "publish") }) }, "Unschedule") : null)),
    h("div", { class: "row" },
      can("publish") ? h("button", { class: "btn", disabled: !p.gate.ready || blocked, onclick: (e) => busy(e.currentTarget, "Publishing", async () => {
        const ask = cloud() ? (p.status === "published" ? "Update the pull request with this version?" : "Open a pull request with this post?")
          : (p.status === "published" ? "Commit the updated post?" : "Publish now? This commits the post on the current branch.")
        if (!confirm(ask)) return
        const post = upsert(await api(`/api/posts/${p.id}/publish`, { method: "POST" }))
        await refreshInfo()
        toast(cloud() ? "Pull request ready. Merge it to go live." : "Committed. Push and merge when you're ready to go live.", "info", post.pr_url ? { href: post.pr_url, label: "Open it" } : null)
        renderPost(p.id, "publish")
      }) }, cloud() ? (p.status === "published" ? "Update the pull request" : "Open the pull request") : (p.status === "published" ? "Commit an update" : "Publish now"))
        : h("p", { class: "small muted" }, "Editors and owners publish.")),
  ]
}

async function refreshInfo() {
  state.info = await api("/api/state")
  renderStatus()
  renderSidebar()
}


// Sign in ---------------------------------------------------------------------
function renderSignIn() {
  const error = /error=(\w+)/.exec(location.hash)?.[1]
  const reasons = { denied: "GitHub sign-in was cancelled.", state: "That sign-in link expired or came from another tab. Try again.", expired: "That sign-in took too long. Try again.",
    exchange: "GitHub didn't accept the sign-in. Try again.", profile: "GitHub didn't return your profile.", issuer: "That response didn't come from GitHub." }
  document.body.classList.add("signed-out")
  $("#status").replaceChildren()
  $("#sidebar").replaceChildren()
  $("#main").replaceChildren(h("div", { class: "card stack signin" },
    h("p", { class: "eyebrow" }, "Masthead"),
    h("h1", {}, "Sign in"),
    error ? h("div", { class: "callout warn" }, reasons[error] || "Sign-in failed. Try again.") : null,
    h("a", { class: "btn", href: `/auth/login?next=${encodeURIComponent("/#/")}` }, "Continue with GitHub"),
    h("p", { class: "small muted", style: "margin:0" }, "Masthead reads your public GitHub profile only. Repository access is granted separately, per repository, through the Masthead GitHub App.")))
}

// Settings --------------------------------------------------------------------
const SETTINGS = [
  ["members", "Members", null],
  ["sites", "Blogs", "manage_sites"],
  ["key", "API key", "manage_keys"],
  ["billing", "Billing", null],
  ["audit", "Audit log", "view_audit"],
]
const ROLE_LABELS = { owner: "Owner", editor: "Editor", writer: "Writer", reviewer: "Reviewer" }

function newWorkspaceDialog() {
  dialog("New workspace", [h("label", { class: "field" }, "Name", h("input", { type: "text", name: "name", required: true, placeholder: "Developer relations" }))],
    "Create workspace", async (data) => {
      const ws = await api("/api/workspaces", { method: "POST", body: { name: data.get("name") } })
      pref.set("workspace", ws.id); pref.set("site", null)
      state.workspaces = (await api("/api/me")).workspaces
      await load(); location.hash = "#/settings/sites"; render()
    })
}

async function renderSettings(tab) {
  const nav = h("nav", { class: "tabs", "aria-label": "Settings" }, ...SETTINGS.filter(([, , perm]) => !perm || can(perm)).map(([key, label]) =>
    h("a", { class: "tab", href: `#/settings/${key}`, "aria-current": key === tab ? "page" : null }, label)))
  const body = h("section", { class: "panel" }, h("p", { class: "muted" }, "Loading…"))
  $("#main").replaceChildren(h("p", { class: "eyebrow" }, state.info.workspace.name), h("h1", {}, "Settings"), nav, body)
  try {
    const panel = { members: membersPanel, sites: sitesPanel, key: keyPanel, billing: billingPanel, audit: auditPanel }[tab] || membersPanel
    fill(body, ...[await panel()].flat(2))
  } catch (e) {
    body.replaceChildren(h("div", { class: "callout warn" }, e.message, e.status === 402 && can("manage_billing") ? [" ", h("a", { href: "#/settings/billing" }, "See plans")] : null))
  }
}
const rerender = () => render()

async function membersPanel() {
  const data = await api("/api/members")
  const owner = can("manage_members")
  const roleSelect = (m) => {
    const sel = h("select", { "aria-label": `Role for ${m.login}` }, ...Object.entries(ROLE_LABELS).map(([v, l]) => h("option", { value: v, selected: v === m.role }, l)))
    sel.addEventListener("change", async () => {
      try { await api(`/api/members/${m.id}`, { method: "PATCH", body: { role: sel.value } }); toast(`${m.login} is now ${ROLE_LABELS[sel.value].toLowerCase()}.`) } catch (e) { reportError(e); sel.value = m.role }
    })
    return sel
  }
  const limit = data.seats.limit
  const invite = owner ? h("form", { class: "row invite" },
    h("input", { type: "text", name: "login", required: true, placeholder: "GitHub username", pattern: "[A-Za-z0-9-]+", "aria-label": "GitHub username" }),
    h("select", { name: "role", "aria-label": "Role" }, ...Object.entries(ROLE_LABELS).filter(([v]) => v !== "owner").map(([v, l]) => h("option", { value: v, selected: v === "writer" }, l)),
      h("option", { value: "owner" }, "Owner")),
    h("button", { class: "btn", type: "submit" }, "Invite")) : null
  invite?.addEventListener("submit", (e) => {
    e.preventDefault()
    const f = new FormData(invite)
    busy(invite.querySelector("button"), "Inviting", async () => {
      await api("/api/invites", { method: "POST", body: { login: f.get("login"), role: f.get("role") } })
      toast(`Invited ${f.get("login")}. They join when they next sign in with GitHub.`); rerender()
    })
  })
  return [
    h("div", { class: "panel-head" }, h("h2", {}, "Members"), h("span", { class: "small muted" }, limit ? `${data.seats.used} of ${limit} seats` : `${data.seats.used} seats`)),
    h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "Person"), h("th", {}, "Role"), h("th", {}, ""))),
      h("tbody", {},
        ...data.members.map((m) => h("tr", {},
          h("td", {}, h("span", { class: "row" }, m.avatar_url ? h("img", { class: "avatar", src: m.avatar_url, alt: "" }) : null, h("strong", {}, m.login), m.name ? h("span", { class: "muted small" }, m.name) : null)),
          h("td", {}, owner ? roleSelect(m) : ROLE_LABELS[m.role]),
          h("td", {}, owner && m.id !== state.info.user.id ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Removing", async () => {
            if (!confirm(`Remove ${m.login} from ${state.info.workspace.name}?`)) return
            await api(`/api/members/${m.id}`, { method: "DELETE" }); rerender()
          }) }, "Remove") : null))),
        ...data.invites.map((i) => h("tr", {},
          h("td", {}, h("span", { class: "row" }, h("strong", {}, i.github_login), h("span", { class: "tag" }, "Invited"))),
          h("td", {}, ROLE_LABELS[i.role]),
          h("td", {}, owner ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Revoking", async () => { await api(`/api/invites/${i.id}`, { method: "DELETE" }); rerender() }) }, "Revoke") : null))))),
    invite,
    h("dl", { class: "kv small" },
      h("dt", {}, "Owner"), h("dd", {}, "Everything, including members, blogs, the API key and billing."),
      h("dt", {}, "Editor"), h("dd", {}, "Writes, reviews and publishes."),
      h("dt", {}, "Writer"), h("dd", {}, "Writes and runs the AI steps. Can't publish."),
      h("dt", {}, "Reviewer"), h("dd", {}, "Approves or asks for changes.")),
  ]
}

async function sitesPanel() {
  const info = state.info
  const installation = new URLSearchParams(location.hash.split("?")[1] || "").get("installation_id")
  const rows = info.sites.map((s) => h("tr", {},
    h("td", {}, h("strong", {}, s.name)),
    h("td", { class: "mono" }, s.repo || "This machine"),
    h("td", { class: "row" },
      s.repo ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Syncing", async () => { const r = await api(`/api/sites/${s.id}/sync`, { method: "POST" }); toast(`Synced. ${r.posts} posts found.`); await load(); rerender() }) }, "Sync") : null,
      s.repo ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Disconnecting", async () => {
        if (!confirm(`Disconnect ${s.repo}? Its posts in Masthead are deleted. The repository isn't touched.`)) return
        await api(`/api/sites/${s.id}`, { method: "DELETE" }); pref.set("site", null); await load(); rerender()
      }) }, "Disconnect") : null)))
  const out = [
    h("div", { class: "panel-head" }, h("h2", {}, "Blogs"), h("span", { class: "small muted" }, info.limits.repos.limit ? `${info.limits.repos.used} of ${info.limits.repos.limit}` : `${info.limits.repos.used} connected`)),
    rows.length ? h("table", { class: "table" }, h("thead", {}, h("tr", {}, h("th", {}, "Blog"), h("th", {}, "Repository"), h("th", {}, ""))), h("tbody", {}, ...rows)) : null,
  ]
  if (!info.github_app) return [...out, h("div", { class: "callout warn" }, "The GitHub App isn't configured on this server.")]
  if (installation) {
    const repos = await api(`/api/github/repositories?installation_id=${encodeURIComponent(installation)}`)
    const select = h("select", { "aria-label": "Repository" }, ...repos.map((r) => h("option", { value: r.full_name }, r.full_name)))
    out.push(h("div", { class: "card stack" }, h("h3", {}, "Connect a repository"),
      h("p", { class: "small muted", style: "margin:0" }, "The repository needs a blog-studio.toml at its root."),
      h("div", { class: "row" }, select, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Connecting", async () => {
        const site = await api("/api/sites", { method: "POST", body: { installation_id: Number(installation), repo: select.value } })
        pref.set("site", site.id); await load(); toast(`Connected ${site.repo}.`); location.hash = "#/"
      }) }, "Connect"))))
  } else {
    out.push(h("div", { class: "card stack" }, h("h3", {}, "Add a blog"),
      h("p", { class: "small muted", style: "margin:0" }, "Install the Masthead GitHub App on the repository your blog lives in. You come back here to pick it."),
      h("a", { class: "btn", href: info.github_app.install_url }, "Install on GitHub")))
  }
  if (has("approval_rules") && info.site) {
    const n = h("input", { type: "number", min: 0, max: 3, value: 1, style: "max-width:90px", "aria-label": "Required approvals" })
    out.push(h("div", { class: "card stack" }, h("h3", {}, `Approval rule for ${info.site.name}`),
      h("div", { class: "row" }, "Approvals needed before publishing", n,
        h("button", { class: "btn ghost", onclick: (e) => busy(e.currentTarget, "Saving", async () => { await api(`/api/sites/${info.site.id}`, { method: "PATCH", body: { required_reviewers: Number(n.value) } }); toast("Saved.") }) }, "Save"))))
  }
  return out
}

function keyPanel() {
  const info = state.info
  const input = h("input", { type: "password", autocomplete: "off", placeholder: "sk-ant-…", "aria-label": "Anthropic API key", style: "max-width:420px" })
  return [
    h("div", { class: "panel-head" }, h("h2", {}, "Anthropic API key")),
    h("p", { class: "muted", style: "margin:0;max-width:65ch" }, "Every AI step runs on your workspace's own key, so model usage is billed to your Anthropic account. The key is encrypted at rest and never shown again."),
    info.key_last4 ? h("p", { style: "margin:0" }, "Saved key ending in ", h("span", { class: "mono" }, info.key_last4)) : h("div", { class: "callout warn" }, "No key yet. The AI steps stay off until one is saved."),
    h("div", { class: "row" }, input,
      h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Saving", async () => { await api("/api/credentials/anthropic", { method: "PUT", body: { key: input.value.trim() } }); input.value = ""; await refreshInfo(); toast("Key saved."); rerender() }) }, info.key_last4 ? "Replace" : "Save"),
      info.key_last4 ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Removing", async () => {
        if (!confirm("Remove the key? The AI steps stop until a new one is saved.")) return
        await api("/api/credentials/anthropic", { method: "DELETE" }); await refreshInfo(); rerender()
      }) }, "Remove") : null),
    h("p", { class: "small muted", style: "margin:0" }, `Spent through this key this month: ${money(info.spend.month_usd)}.`),
  ]
}

async function billingPanel() {
  const b = await api("/api/billing")
  const info = state.info
  const plan = info.plan
  const usage = info.limits
  const fmt = (u) => (u.limit == null ? `${u.used}` : `${u.used} of ${u.limit}`)
  const out = [
    h("div", { class: "panel-head" }, h("h2", {}, "Billing"), h("span", { class: "badge clear" }, `${plan.name}${b.status === "trialing" ? " · trial" : ""}`)),
    b.status === "past_due" ? h("div", { class: "callout warn" }, "The last payment failed. Stripe will retry. Update the card to keep your plan.") : null,
    b.cancel_at_period_end ? h("div", { class: "callout warn" }, `Your plan ends on ${fmtDate(b.current_period_end && new Date(Number(b.current_period_end) * 1000).toISOString())}. Then the workspace moves to Free.`) : null,
    h("dl", { class: "kv" },
      h("dt", {}, "Seats"), h("dd", {}, fmt(usage.seats)),
      h("dt", {}, "Blogs"), h("dd", {}, fmt(usage.repos)),
      h("dt", {}, "Posts started this month"), h("dd", {}, fmt(usage.posts_per_month)),
      b.current_period_end && !b.cancel_at_period_end ? [h("dt", {}, "Renews"), h("dd", {}, fmtDate(new Date(Number(b.current_period_end) * 1000).toISOString()))] : null),
  ]
  if (!b.enabled) return [...out, h("p", { class: "small muted" }, "Billing isn't configured on this server.")]
  if (!b.can_manage) return [...out, h("p", { class: "small muted" }, "Owners manage billing.")]
  if (b.has_customer && plan.id !== "free") {
    out.push(h("div", { class: "row" }, h("button", { class: "btn", onclick: (e) => busy(e.currentTarget, "Opening Stripe", async () => { location.href = (await api("/api/billing/portal", { method: "POST" })).url }) }, "Manage seats, card and invoices")))
    return out
  }
  const yearly = h("input", { type: "checkbox", id: "yearly" })
  const upgrade = (id) => (e) => busy(e.currentTarget, "Opening Stripe", async () => {
    location.href = (await api("/api/billing/checkout", { method: "POST", body: { plan: id, interval: yearly.checked ? "yearly" : "monthly" } })).url
  })
  out.push(
    h("label", { class: "row", for: "yearly" }, yearly, "Pay yearly. Two months free."),
    h("div", { class: "grid-2" },
      h("div", { class: "card stack" }, h("h3", {}, "Team"), h("p", { style: "margin:0" }, h("span", { class: "spend" }, "$19"), " per seat a month, from 2 seats"),
        h("p", { class: "small muted", style: "margin:0" }, "Review before publishing, roles, scheduling, campaigns and a shared house voice. 14 days free on your first subscription."),
        h("button", { class: "btn", onclick: upgrade("team") }, "Choose Team")),
      h("div", { class: "card stack" }, h("h3", {}, "Business"), h("p", { style: "margin:0" }, h("span", { class: "spend" }, "$39"), " per seat a month, from 5 seats"),
        h("p", { class: "small muted", style: "margin:0" }, "Everything in Team, plus approval rules, the audit log and single sign-on."),
        h("button", { class: "btn ghost", onclick: upgrade("business") }, "Choose Business"))),
    h("p", { class: "small muted", style: "margin:0" }, "Payment runs through Stripe. Your plan changes once Stripe confirms it, usually within seconds."),
  )
  if (/checkout=done/.test(location.hash)) out.splice(1, 0, h("div", { class: "callout" }, "Thanks. Your plan updates as soon as Stripe confirms the payment."))
  return out
}

async function auditPanel() {
  const entries = await api("/api/audit")
  return [
    h("div", { class: "panel-head" }, h("h2", {}, "Audit log"), h("span", { class: "small muted" }, "The latest 200 entries")),
    entries.length ? h("table", { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "When"), h("th", {}, "Who"), h("th", {}, "What"), h("th", {}, "On"))),
      h("tbody", {}, ...entries.map((a) => h("tr", {},
        h("td", { class: "small" }, new Date(a.at || a.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })),
        h("td", {}, a.login || "Masthead"),
        h("td", { class: "mono" }, a.action),
        h("td", {}, a.target))))) : h("p", { class: "muted" }, "Nothing recorded yet."),
  ]
}

// Routing -------------------------------------------------------------------
function render() {
  if (!state.info) return
  renderStatus()
  renderSidebar()
  const m = /^#\/post\/(\d+)(?:\/(\w+))?/.exec(location.hash)
  const settings = /^#\/settings\/(\w+)/.exec(location.hash)
  if (m) renderPost(Number(m[1]), m[2] || "idea")
  else if (settings && cloud()) renderSettings(settings[1])
  else renderBoard()
}

async function start() {
  const me = await api("/api/me")
  if (me.mode === "cloud" && !me.user) return renderSignIn()
  state.workspaces = me.workspaces
  await load()
  render()
}

window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0) })
start().catch((e) => {
  if (e.status === 401) return
  $("#main").replaceChildren(h("div", { class: "callout warn" }, `Masthead couldn't load: ${e.message}`))
})
