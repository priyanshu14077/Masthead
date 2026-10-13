// Blog Studio UI. Plain DOM, no framework: every value from the server is set as text, never as HTML.

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

function toast(message, kind = "info") {
  const el = h("div", { class: `toast ${kind === "error" ? "error" : ""}` }, message)
  $("#toasts").append(el)
  setTimeout(() => el.remove(), kind === "error" ? 9000 : 4000)
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "content-type": "application/json", ...(options.headers || {}) },
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`)
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
    toast(e.message, "error")
  } finally {
    button.disabled = false
    button.replaceChildren(...original)
  }
}

const money = (n) => `$${(n || 0).toFixed(n >= 1 ? 2 : 4)}`
const fmtDate = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "")
const lines = (text) => text.split("\n").map((s) => s.trim()).filter(Boolean)
const csv = (text) => text.split(",").map((s) => s.trim()).filter(Boolean)
const campaignName = (id) => state.campaigns.find((c) => c.id === id)?.name

// Data --------------------------------------------------------------------
async function load() {
  const [info, campaigns, posts] = await Promise.all([api("/api/state"), api("/api/campaigns"), api("/api/posts")])
  Object.assign(state, { info, campaigns, posts })
}

function upsert(post) {
  const i = state.posts.findIndex((p) => p.id === post.id)
  if (i >= 0) state.posts[i] = post
  else state.posts.push(post)
  return post
}

// Chrome --------------------------------------------------------------------
function renderStatus() {
  const { info } = state
  document.title = `Blog Studio · ${info.site_name}`
  $(".brand").textContent = `Blog Studio · ${info.site_name}`
  const ai = { ready: ["AI ready", false], fake: ["Fake AI mode", true], missing: ["No API credentials", true] }[info.ai]
  $("#status").replaceChildren(
    h("span", { class: `pill ${ai[1] ? "warn" : ""}`, title: ai[1] && info.ai === "missing" ? "Add ANTHROPIC_API_KEY to studio/.env, or run `ant auth login`, then restart." : null }, h("span", { class: "dot" }), ai[0]),
    h("span", { class: `pill ${info.protected_branch ? "warn" : ""}`, title: info.protected_branch ? "Publishing is blocked on this branch because it deploys the live site." : "Publishing commits here. Nothing is pushed." }, h("span", { class: "dot" }), `branch: ${info.branch || "none"}`),
    h("span", { class: "pill" }, `spent this month ${money(info.spend.month_usd)}`),
  )
}

function renderSidebar() {
  const counts = (cid) => state.posts.filter((p) => cid === "all" || (cid === "none" ? !p.campaign_id : p.campaign_id === cid)).length
  const link = (id, label) =>
    h("button", { class: "side-link", "aria-current": String(state.filter === id), onclick: () => { state.filter = id; location.hash = "#/"; render() } },
      h("span", {}, label), h("span", { class: "count" }, counts(id)))
  $("#sidebar").replaceChildren(
    h("button", { class: "btn", onclick: newIdeaDialog }, "+ New idea"),
    h("div", { class: "side-section" },
      h("p", { class: "side-title" }, "Campaigns"),
      link("all", "All posts"),
      ...state.campaigns.map((c) => link(c.id, c.name)),
      link("none", "No campaign"),
      h("button", { class: "link", style: "text-align:left;padding:6px 10px", onclick: newCampaignDialog }, "+ New campaign"),
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
      h("input", { type: "text", name: "allowed_names", placeholder: "Proploy, Anthropic" })),
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
  const posts = state.posts.filter((p) => state.filter === "all" || (state.filter === "none" ? !p.campaign_id : p.campaign_id === state.filter))
  const campaign = typeof state.filter === "number" ? state.campaigns.find((c) => c.id === state.filter) : null
  const head = h("div", { class: "panel-head", style: "margin-bottom:20px" },
    h("div", {}, h("p", { class: "eyebrow" }, campaign ? `${campaign.kind[0].toUpperCase()}${campaign.kind.slice(1)} campaign` : "Campaign board"),
      h("h1", {}, campaign ? campaign.name : "Every post, idea to published"),
      campaign?.description ? h("p", { class: "muted", style: "margin:6px 0 0;max-width:60ch" }, campaign.description) : null),
    h("div", { class: "row" },
      h("button", { class: "btn ghost small", onclick: (e) => busy(e.currentTarget, "Checking", async () => {
        const { published } = await api("/api/scheduler/run", { method: "POST" })
        await load(); render()
        toast(published.length ? `Published ${published.length} scheduled post(s).` : "Nothing is due today.")
      }) }, "Publish what's due"),
      campaign ? h("button", { class: "btn ghost small", onclick: () => renameCampaign(campaign) }, "Edit campaign") : null))

  if (!state.posts.length) {
    $("#main").replaceChildren(head, h("div", { class: "card empty" }, h("p", { class: "hand" }, "nothing on the board yet"),
      h("p", { class: "muted" }, "Add an idea, and the Studio will take it through outline, draft, check and publish."),
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
        if (!confirm("Delete this post from the Studio? Nothing in the site changes.")) return
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
        toast(`Written to ${state.info.posts_dir} as a draft. It shows on the dev server only.`)
        window.open(post.preview_url, "_blank", "noreferrer")
        renderPost(p.id, "draft")
      }) }, "Preview on the dev server ↗"),
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
    h("p", { class: "muted", style: "margin:0;max-width:70ch" }, "Claude designs the structure; the Studio draws it in your blog's thumbnail palette. It's written into the site when you preview or publish."),
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

function publishPanel(p) {
  const today = new Date().toISOString().slice(0, 10)
  const when = h("input", { type: "date", min: today, value: p.publish_at || today, style: "max-width:200px" })
  const blocked = state.info.protected_branch
  return [
    h("div", { class: "panel-head" }, h("div", {}, h("p", { class: "eyebrow" }, "Step 7"), h("h2", {}, p.status === "published" ? "Published" : "Schedule or publish"))),
    p.gate.ready ? h("div", { class: "callout" }, `Ready. Publishing writes the post into ${state.info.posts_dir}, commits it on the current branch, and never pushes. Push and merge yourself to go live.`)
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
      p.public_url ? [h("dt", {}, "Live URL after push"), h("dd", { class: "mono" }, p.public_url)] : null),
    p.status === "published" ? null : h("div", { class: "card stack" },
      h("h3", {}, "Schedule"),
      h("p", { class: "small muted", style: "margin:0" }, "While the Studio is running, it publishes due posts every minute. If it was closed, use “Publish what's due” on the board."),
      h("div", { class: "row" }, when,
        h("button", { class: "btn ghost", disabled: !p.gate.ready, onclick: (e) => busy(e.currentTarget, "Scheduling", async () => { upsert(await api(`/api/posts/${p.id}/schedule`, { method: "POST", body: { publish_at: when.value } })); toast(`Scheduled for ${fmtDate(when.value)}.`); renderPost(p.id, "publish") }) }, p.status === "scheduled" ? "Reschedule" : "Schedule"),
        p.status === "scheduled" ? h("button", { class: "link", onclick: (e) => busy(e.currentTarget, "Unscheduling", async () => { upsert(await api(`/api/posts/${p.id}/unschedule`, { method: "POST" })); renderPost(p.id, "publish") }) }, "Unschedule") : null)),
    h("div", { class: "row" },
      h("button", { class: "btn", disabled: !p.gate.ready || blocked, onclick: (e) => busy(e.currentTarget, "Publishing", async () => {
        if (!confirm(p.status === "published" ? "Commit the updated post?" : "Publish now? This commits the post on the current branch.")) return
        upsert(await api(`/api/posts/${p.id}/publish`, { method: "POST" }))
        await refreshInfo()
        toast("Committed. Push and merge when you're ready to go live.")
        renderPost(p.id, "publish")
      }) }, p.status === "published" ? "Commit an update" : "Publish now")),
  ]
}

async function refreshInfo() {
  state.info = await api("/api/state")
  renderStatus()
  renderSidebar()
}

// Routing -------------------------------------------------------------------
function render() {
  renderStatus()
  renderSidebar()
  const m = /^#\/post\/(\d+)(?:\/(\w+))?/.exec(location.hash)
  if (m) renderPost(Number(m[1]), m[2] || "idea")
  else renderBoard()
}

window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0) })
load().then(render).catch((e) => {
  $("#main").replaceChildren(h("div", { class: "callout warn" }, `The Studio couldn't load: ${e.message}`))
})
