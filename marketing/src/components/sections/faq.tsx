import { Plus } from "lucide-react"
import { AnimatePresence, motion } from "motion/react"
import { useId, useState } from "react"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"

const QA = [
  ["Which blogs does Masthead work with?", "Any blog whose posts are MDX files in a git repository: Next.js, Astro, Vite or your own build. You tell Masthead where posts and thumbnails live and which components the blog has."],
  ["Does Masthead push to our main branch?", "No. Each post arrives as a pull request on its own branch. Protected branches stay protected, and you merge when you're ready."],
  ["Why do we bring our own Anthropic key?", "So model usage is billed to you by Anthropic at Anthropic's rates, with nothing added. Masthead charges per seat."],
  ["What does the confidentiality check look for?", "Company and product names outside the post's approved list, internal hostnames and URLs, secrets, security weaknesses, personal data, and numbers that aren't in the author's notes. It also compiles the MDX."],
  ["Can the check miss something?", "Yes. It combines a model review with pattern checks for secrets and internal hosts, and neither is perfect. It catches the common slips early so your reviewers can spend their time on the post itself."],
  ["Will drafts sound like our blog?", "Drafts follow your shared voice guide, your component guide and a reference post you choose. Writers edit every outline and draft before anything is checked or published."],
  ["Does Masthead post to LinkedIn and X for us?", "No. It writes the LinkedIn post, X thread and newsletter blurb for each post. You copy them and post them yourself."],
] as const

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)
  const base = useId()
  return (
    <section aria-labelledby="faq" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="Questions" id="faq">
        Asked and <em className="accent">answered</em>.
      </SectionHead>
      <Reveal className="mx-auto mt-14 grid max-w-3xl gap-3">
        {QA.map(([q, a], i) => {
          const isOpen = open === i
          return (
            <div key={q} className={`rounded-xl border bg-gradient-to-b from-[#111] to-[#080808] transition-colors ${isOpen ? "border-white/20" : "border-line"}`}>
              <h3>
                <button id={`${base}-q${i}`} aria-expanded={isOpen} aria-controls={`${base}-a${i}`} onClick={() => setOpen(isOpen ? null : i)}
                  className="flex w-full items-center justify-between gap-6 px-5 py-5 text-left text-[16px] font-medium sm:px-6">
                  {q}
                  <motion.span animate={{ rotate: isOpen ? 45 : 0 }} className="flex size-7 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/[0.05]">
                    <Plus size={14} aria-hidden="true" />
                  </motion.span>
                </button>
              </h3>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div id={`${base}-a${i}`} role="region" aria-labelledby={`${base}-q${i}`}
                    initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }} className="overflow-hidden">
                    <p className="px-5 pb-5 text-[15px] leading-relaxed text-muted sm:px-6">{a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}
      </Reveal>
    </section>
  )
}
