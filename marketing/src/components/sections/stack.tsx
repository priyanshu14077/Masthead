import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { SpotlightCard } from "../ui/spotlight-card"

const ITEMS = [
  ["GH", "Repository", "GitHub App", "Installed per repository. It reads your settings and opens a pull request for each post.", "Contents and pull requests"],
  ["MDX", "Content", "Any MDX blog in git", "Next.js, Astro, Vite or your own build. You say where posts and thumbnails live.", "Your folders, your frontmatter"],
  ["{ }", "Components", "Your MDX components", "Declare the callouts, figures and diagrams your blog has. Drafts use only those.", "Unknown components are caught"],
  ["S", "Writing", "Claude Sonnet 5.5", "Writes the outline, the draft and the thumbnail diagram.", "On your Anthropic key"],
  ["H", "Checking", "Claude Haiku 5.5", "Runs the confidentiality check and writes the distribution copy.", "On your Anthropic key"],
  ["CI", "Delivery", "Your CI and previews", "A post is an ordinary branch, so your checks and preview builds run on it.", "Nothing new to configure"],
] as const

export function Stack() {
  return (
    <section aria-labelledby="stack" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="Your stack" id="stack">
        Fits the blog you <em className="accent">already have</em>.
      </SectionHead>
      <ul className="mx-auto mt-16 grid max-w-7xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ITEMS.map(([mark, group, title, body, line], i) => (
          <Reveal as="li" key={title} delay={(i % 3) * 0.06}>
            <SpotlightCard className="h-full">
              <div className="flex h-full flex-col p-6">
                <div className="flex items-start justify-between">
                  <span className="flex size-11 items-center justify-center rounded-lg border border-white/15 bg-white/[0.05] font-mono text-[12px] font-medium">{mark}</span>
                  <span className="rounded border border-white/12 px-2 py-0.5 font-mono text-[11px] text-neutral-400">{group}</span>
                </div>
                <h3 className="mt-6 text-[18px] font-medium">{title}</h3>
                <p className="mt-2 flex-1 text-[14.5px] leading-relaxed text-muted">{body}</p>
                <p className="mt-5 flex items-center gap-2 border-t border-line pt-4 font-mono text-[12px] text-ok">
                  <span className="size-1.5 rounded-full bg-ok" aria-hidden="true" />{line}
                </p>
              </div>
            </SpotlightCard>
          </Reveal>
        ))}
      </ul>
    </section>
  )
}
