import { Component, FileText, GitPullRequest, KeyRound, ShieldCheck, UsersRound, type LucideIcon } from "lucide-react"
import { Reveal } from "../ui/reveal"
import { SectionHead } from "../ui/label"
import { SpotlightCard } from "../ui/spotlight-card"

const ITEMS: [LucideIcon, string, string][] = [
  [FileText, "Your notes are the source", "Every figure in a draft comes from the notes the writer pasted in. A number from anywhere else is flagged."],
  [ShieldCheck, "Checked before anyone reviews", "Unapproved names, internal hosts, secrets, security weaknesses and personal data are caught, and the MDX is compiled."],
  [GitPullRequest, "Pull requests, never pushes", "Each post lands on its own branch. Protected branches stay protected, and your CI and previews run as usual."],
  [Component, "Written in your components", "Drafts use the callouts, figures and diagrams your blog already declares, in a voice guide your team shares."],
  [UsersRound, "Review is part of the flow", "Someone other than the author approves each post. An edit after approval needs approving again."],
  [KeyRound, "Your key, no markup", "Every model call runs on your team's Anthropic key, billed by Anthropic at Anthropic's rates."],
]

export function Benefits() {
  return (
    <section aria-labelledby="why" className="border-t border-line px-4 py-28 sm:px-8">
      <SectionHead label="Why Masthead" id="why">
        Built for posts about <em className="accent">real systems</em>.
      </SectionHead>
      <ul className="mx-auto mt-16 grid max-w-7xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {ITEMS.map(([Icon, title, body], i) => (
          <Reveal as="li" key={title} delay={(i % 3) * 0.06}>
            <SpotlightCard className="h-full">
              <div className="p-7">
                <span className="inline-flex size-10 items-center justify-center rounded-lg border border-white/15 bg-white/[0.04]">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <h3 className="mt-7 text-[19px] font-medium tracking-[-0.01em]">{title}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-muted">{body}</p>
              </div>
            </SpotlightCard>
          </Reveal>
        ))}
      </ul>
    </section>
  )
}
