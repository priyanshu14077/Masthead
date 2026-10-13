// Compiles MDX from stdin with the same plugins the site uses. Exit 0 when it compiles,
// 1 with the error message on stderr when it doesn't. Run from the Studio, not the site.
import { compile } from "@mdx-js/mdx"
import remarkFrontmatter from "remark-frontmatter"
import remarkGfm from "remark-gfm"

let source = ""
for await (const chunk of process.stdin) source += chunk
try {
  await compile(source, { remarkPlugins: [remarkFrontmatter, remarkGfm] })
  process.exit(0)
} catch (error) {
  const where = error.place ? ` (line ${error.place.line ?? error.place.start?.line})` : ""
  process.stderr.write(`${error.reason ?? error.message}${where}`)
  process.exit(1)
}
