import { app, DEMO_URL } from "../../lib/links"
import { ButtonLink } from "../ui/button"
import { Logo } from "../ui/logo"
import { ParticleWave } from "./particle-wave"

export function Cta() {
  return (
    <section className="relative overflow-hidden border-t border-line px-4 py-32 text-center sm:px-8">
      <ParticleWave className="absolute inset-0 h-full w-full opacity-60" />
      <div className="relative mx-auto max-w-3xl">
        <h2 className="text-[clamp(2rem,5vw,3.6rem)] leading-[1.05] font-medium tracking-[-0.04em] text-balance">
          Your next post is already in <em className="accent">someone's notes</em>.
        </h2>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <ButtonLink href={app()}>Start free</ButtonLink>
          <ButtonLink href={DEMO_URL} variant="ghost">Book a demo</ButtonLink>
        </div>
      </div>
    </section>
  )
}

const COLUMNS = [
  ["Product", [["How it works", "#flow"], ["The desk", "#desk"], ["The check", "#check"], ["Features", "#features"], ["Pricing", "#pricing"]]],
  ["Company", [["Brand", "/brand.html"], ["Plan comparison", "/pricing.html"], ["Book a demo", DEMO_URL]]],
  ["Get started", [["Start free", app()], ["Sign in", app()]]],
] as const

export function Footer() {
  return (
    <footer className="border-t border-line px-4 pt-16 pb-10 sm:px-8">
      <div className="mx-auto grid max-w-7xl gap-12 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo />
          <p className="mt-4 max-w-xs text-[14px] leading-relaxed text-muted">The publishing desk for engineering teams.</p>
        </div>
        {COLUMNS.map(([title, links]) => (
          <nav key={title} aria-label={title}>
            <p className="font-mono text-[12px] tracking-[0.16em] text-neutral-300 uppercase">{title}</p>
            <ul className="mt-4 grid gap-2.5">
              {links.map(([label, href]) => (
                <li key={label}><a href={href} className="text-[14px] text-neutral-400 hover:text-white">{label}</a></li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="mx-auto mt-14 flex max-w-7xl flex-wrap justify-between gap-3 border-t border-line pt-6 font-mono text-[12px] text-neutral-500">
        <span>© 2026 Masthead</span>
        <span>Claude and Anthropic are trademarks of Anthropic.</span>
      </div>
    </footer>
  )
}
