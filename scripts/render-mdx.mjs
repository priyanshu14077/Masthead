// Renders a post body (MDX) to an HTML fragment for Masthead's own preview, so a preview needs
// neither the blog's code nor its dev server. Reads MDX on stdin, writes HTML on stdout.
//
// Nothing in the draft is executed. Components become plain elements; JSX attribute values are read
// only when they are literals (strings, numbers, template strings without ${}, arrays of those);
// {expressions} are shown as code; import/export lines are dropped. The result is sanitised.
import rehypeSanitize, { defaultSchema } from "rehype-sanitize"
import rehypeStringify from "rehype-stringify"
import remarkFrontmatter from "remark-frontmatter"
import remarkGfm from "remark-gfm"
import remarkMdx from "remark-mdx"
import remarkParse from "remark-parse"
import remarkRehype from "remark-rehype"
import { unified } from "unified"

const h = (tagName, properties = {}, children = []) => ({ type: "element", tagName, properties, children })
const text = (value) => ({ type: "text", value: String(value) })

function fromEstree(node) {
  if (!node) return undefined
  if (node.type === "Literal") return node.value
  if (node.type === "TemplateLiteral" && node.expressions.length === 0) return node.quasis.map((q) => q.value.cooked).join("")
  if (node.type === "ArrayExpression") return node.elements.map(fromEstree).filter((v) => v !== undefined)
  return undefined
}

function props(node) {
  const out = {}
  for (const attr of node.attributes || []) {
    if (attr.type !== "mdxJsxAttribute") continue
    const v = attr.value
    out[attr.name] = v == null ? true : typeof v === "string" ? v : fromEstree(v.data?.estree?.body?.[0]?.expression)
  }
  return out
}

const LABELS = { TLDR: "TL;DR", Takeaways: "Takeaways", References: "References" }
const list = (items) => h("ul", {}, items.map((i) => h("li", {}, [text(i)])))

function component(state, node) {
  const name = node.name || ""
  const p = props(node)
  const kids = state.all(node)
  const inline = node.type === "mdxJsxTextElement"
  if (/^[a-z]/.test(name)) {
    // Plain HTML written as JSX (<sup>, <kbd>, <br />). The sanitiser keeps safe tags and drops the rest.
    const attrs = Object.fromEntries(Object.entries(p).filter(([, v]) => typeof v === "string"))
    return h(name, attrs, kids)
  }
  switch (name) {
    case "Callout":
      return h("aside", { className: ["callout", `callout-${p.kind || p.type || "note"}`] }, [
        ...(p.title ? [h("p", { className: ["callout-title"] }, [text(p.title)])] : []),
        ...kids,
      ])
    case "Figure": {
      const parts = []
      if (typeof p.src === "string") parts.push(h("img", { src: p.src, alt: p.alt || "" }))
      parts.push(...kids)
      if (p.caption) parts.push(h("figcaption", {}, [text(p.caption)]))
      return h("figure", {}, parts)
    }
    case "Mermaid":
      return h("pre", { className: ["mermaid"] }, [text(typeof p.chart === "string" ? p.chart : "")])
    case "Steps":
      // Steps written on single lines arrive wrapped in a paragraph; lift the steps out of it.
      return h("ol", { className: ["steps"] }, kids.flatMap((k) => (k.tagName === "p" ? k.children.filter((c) => c.tagName === "li") : k.tagName === "li" ? [k] : [])))
    case "Step":
      return h("li", { className: ["step"] }, [...(p.title ? [h("p", { className: ["step-title"] }, [text(p.title)])] : []), ...kids])
    case "TLDR":
    case "Takeaways":
    case "References":
      return h("section", { className: ["box"] }, [h("p", { className: ["box-label"] }, [text(LABELS[name])]), ...kids])
    case "Tradeoffs": {
      const sides = [["Pros", p.pros], ["Cons", p.cons]].filter(([, v]) => Array.isArray(v))
      return h("section", { className: ["box", "tradeoffs"] }, [
        h("p", { className: ["box-label"] }, [text(p.title || "Trade-offs")]),
        ...sides.flatMap(([label, items]) => [h("p", { className: ["tradeoffs-side"] }, [text(label)]), list(items)]),
        ...kids,
      ])
    }
    case "Video":
      return typeof p.src === "string" && p.src.startsWith("https://")
        ? h("video", { src: p.src, controls: true }, [])
        : h("p", { className: ["mdx-placeholder"] }, [text("Video")])
    default:
      // A component the preview doesn't know: show its name and its content.
      return h(inline ? "span" : "div", { className: ["mdx-component"], dataComponent: name || "fragment" }, [
        h("span", { className: ["mdx-component-name"] }, [text(name ? `<${name}>` : "<>")]),
        ...kids,
      ])
  }
}

const expression = (inline) => (_state, node) => {
  const code = h("code", { className: ["mdx-expression"] }, [text(`{${node.value}}`)])
  return inline ? code : h("p", {}, [code])
}

// Tag-specific entries in the default schema narrow className (to language-* on code, task-list
// classes on ol and li), so the elements this renderer styles get className back explicitly.
const STYLED = ["aside", "code", "div", "figure", "li", "ol", "p", "pre", "section", "span", "ul"]
const attributes = { ...defaultSchema.attributes, "*": [...(defaultSchema.attributes["*"] || []), "dataComponent"], video: ["src", "controls"] }
for (const tag of STYLED) attributes[tag] = [...(attributes[tag] || []).filter((a) => a !== "className" && !(Array.isArray(a) && a[0] === "className")), "className"]

const schema = {
  ...defaultSchema,
  tagNames: [...defaultSchema.tagNames, "aside", "figure", "figcaption", "section", "video"],
  attributes,
  protocols: { ...defaultSchema.protocols, src: ["https"] },
  clobberPrefix: "",
}

let source = ""
for await (const chunk of process.stdin) source += chunk
try {
  const html = await unified()
    .use(remarkParse)
    .use(remarkMdx)
    .use(remarkFrontmatter)
    .use(remarkGfm)
    .use(remarkRehype, {
      handlers: {
        mdxJsxFlowElement: component,
        mdxJsxTextElement: component,
        mdxFlowExpression: expression(false),
        mdxTextExpression: expression(true),
        mdxjsEsm: () => undefined,
      },
    })
    .use(rehypeSanitize, schema)
    .use(rehypeStringify)
    .process(source)
  process.stdout.write(String(html))
} catch (error) {
  const where = error.place ? ` (line ${error.place.line ?? error.place.start?.line})` : ""
  process.stderr.write(`${error.reason ?? error.message}${where}`)
  process.exit(1)
}
